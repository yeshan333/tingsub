package desktop

import (
	"bufio"
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"sync"
	"testing"
	"time"
)

func TestControllerProcess(t *testing.T) {
	if os.Getenv("TINGSUB_TEST_CONTROLLER") != "1" {
		return
	}
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		var request struct {
			Method string `json:"method"`
			Params []any  `json:"params"`
		}
		_ = json.Unmarshal(scanner.Bytes(), &request)
		switch request.Method {
		case "crash":
			os.Exit(7)
		case "slow":
			time.Sleep(300 * time.Millisecond)
		case "error":
			_, _ = os.Stdout.WriteString("{\"error\":\"Download the local models first\"}\n")
			continue
		}
		_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"result": request.Params})
	}
	os.Exit(0)
}

func testWorker(t *testing.T) *Worker {
	t.Helper()
	cmd := exec.Command(os.Args[0], "-test.run=^TestControllerProcess$")
	cmd.Env = append(os.Environ(), "TINGSUB_TEST_CONTROLLER=1")
	w, err := StartWorker(cmd)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(w.Close)
	return w
}

func TestConcurrentDesktopCallsReceiveTheirOwnReplies(t *testing.T) {
	w := testWorker(t)
	var group sync.WaitGroup
	for i := range 20 {
		group.Go(func() {
			value, err := w.Call(context.Background(), "echo", i)
			if err != nil {
				t.Error(err)
				return
			}
			if value.([]any)[0] != float64(i) {
				t.Errorf("call %d received %v", i, value)
			}
		})
	}
	group.Wait()
}

func TestControllerErrorsReachDesktopAndLeaveNextRequestUsable(t *testing.T) {
	w := testWorker(t)
	if _, err := w.Call(context.Background(), "error"); err == nil || err.Error() != "Download the local models first" {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, err := w.Call(context.Background(), "echo"); err != nil {
		t.Fatal(err)
	}
}

func TestControllerCrashFailsPendingCallWithoutWaitingForTimeout(t *testing.T) {
	w := testWorker(t)
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if _, err := w.Call(ctx, "crash"); err == nil || ctx.Err() != nil {
		t.Fatalf("controller crash: %v", err)
	}
}

func TestClosingDesktopClosesControllerInputAndRejectsFurtherCalls(t *testing.T) {
	w := testWorker(t)
	w.Close()
	w.Close()
	if _, err := w.Call(context.Background(), "echo"); err == nil {
		t.Fatal("closed controller accepted a call")
	}
}

func TestAlreadyCanceledDesktopCallIsRejectedBeforeDispatch(t *testing.T) {
	w := testWorker(t)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	// A context canceled before dispatch must never enter the protocol stream.
	if _, err := w.Call(ctx, "echo"); err == nil {
		t.Fatal("canceled call succeeded")
	}
}

func TestAbandonedDesktopReplyCannotBeReusedByTheNextCall(t *testing.T) {
	w := testWorker(t)
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	if _, err := w.Call(ctx, "slow", "old reply"); err == nil {
		t.Fatal("slow call did not time out")
	}
	if _, err := w.Call(context.Background(), "echo", "next reply"); err == nil {
		t.Fatal("abandoned stream accepted another call")
	}
	w.Close()
}
