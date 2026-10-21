// Package desktop connects the MyGo host to its private Python controller.
package desktop

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os/exec"
	"sync"
	"syscall"
	"time"
)

// Worker owns exactly one sidecar and serializes its request/reply stream.
type Worker struct {
	cmd       *exec.Cmd
	input     io.WriteCloser
	replies   chan []byte
	done      chan struct{}
	gate      chan struct{}
	closing   chan struct{}
	closeOnce sync.Once
}

func StartWorker(cmd *exec.Cmd) (*Worker, error) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	input, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	output, err := cmd.StdoutPipe()
	if err != nil {
		input.Close()
		return nil, err
	}
	if err := cmd.Start(); err != nil {
		input.Close()
		output.Close()
		return nil, err
	}
	w := &Worker{cmd: cmd, input: input, replies: make(chan []byte), done: make(chan struct{}), gate: make(chan struct{}, 1), closing: make(chan struct{})}
	w.gate <- struct{}{}
	go func() {
		scanner := bufio.NewScanner(output)
		scanner.Buffer(make([]byte, 4096), 1024*1024)
		for scanner.Scan() {
			line := append([]byte(nil), scanner.Bytes()...)
			select {
			case w.replies <- line:
			case <-w.closing:
			}
		}
		if scanner.Err() != nil {
			w.kill()
		}
		// Drain stdout before Wait closes its pipe.
		_ = cmd.Wait()
		w.kill() // Reap any owned descendants if the controller itself crashed.
		close(w.done)
	}()
	return w, nil
}

func (w *Worker) Call(ctx context.Context, method string, params ...any) (any, error) {
	ctx, cancel := context.WithTimeout(ctx, 20*time.Second)
	defer cancel()
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	select {
	case <-w.closing:
		return nil, errors.New("Desktop is shutting down")
	case <-w.done:
		return nil, errors.New("Python controller exited; reopen TingSub")
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-w.gate:
	}
	defer func() { w.gate <- struct{}{} }()
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	select {
	case <-w.closing:
		return nil, errors.New("Desktop is shutting down")
	default:
	}
	if params == nil {
		params = []any{}
	}
	request, err := json.Marshal(map[string]any{"method": method, "params": params})
	if err != nil {
		return nil, err
	}
	if len(request) >= 64*1024 {
		return nil, errors.New("Desktop request is too large")
	}
	written := make(chan error, 1)
	go func() { _, err := w.input.Write(append(request, '\n')); written <- err }()
	select {
	case err := <-written:
		if err != nil {
			w.beginClose()
			return nil, fmt.Errorf("Python controller: %w", err)
		}
	case <-ctx.Done():
		w.beginClose()
		return nil, ctx.Err()
	case <-w.closing:
		return nil, errors.New("Desktop is shutting down")
	}
	select {
	case data := <-w.replies:
		var response struct {
			Result any    `json:"result"`
			Error  string `json:"error"`
		}
		if err := json.Unmarshal(data, &response); err != nil {
			w.beginClose()
			return nil, fmt.Errorf("Invalid controller response: %w", err)
		}
		if response.Error != "" {
			return nil, errors.New(response.Error)
		}
		return response.Result, nil
	case <-w.done:
		return nil, errors.New("Python controller exited; reopen TingSub")
	case <-w.closing:
		return nil, errors.New("Desktop is shutting down")
	case <-ctx.Done():
		// Never reuse a stream after abandoning a reply: it could answer the
		// next request. Closing stdin also cleans up the owned service.
		w.beginClose()
		return nil, ctx.Err()
	}
}

func (w *Worker) kill() {
	// Only our process group, including an unresponsive owned inference child.
	_ = syscall.Kill(-w.cmd.Process.Pid, syscall.SIGKILL)
}

func (w *Worker) beginClose() {
	w.closeOnce.Do(func() {
		close(w.closing)
		_ = w.input.Close() // Python's EOF handler stops its owned work.
		go func() {
			select {
			case <-w.done:
			case <-time.After(18 * time.Second):
				w.kill()
			}
		}()
	})
}

func (w *Worker) Close() {
	w.beginClose()
	<-w.done
}
