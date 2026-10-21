// TingSub's native desktop host. MLX stays in the bundled Python runtime.
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sync/atomic"
	"time"

	"github.com/egoist/mygo"
	"github.com/yeshan333/tingsub"
	"github.com/yeshan333/tingsub/internal/desktop"
)

type options struct {
	directory, python, sourceRoot, asr, translation string
	selfTest, noInference                           bool
}

func workerCommand(o options, args ...string) *exec.Cmd {
	var cmd *exec.Cmd
	if o.python != "" {
		cmd = exec.Command(o.python, append([]string{"-m", "live_subs.cli"}, args...)...)
		cmd.Env = append(os.Environ(), "PYTHONPATH="+filepath.Join(o.sourceRoot, "src"))
	} else {
		binary, err := os.Executable()
		if err != nil {
			log.Fatal(err)
		}
		cmd = exec.Command(filepath.Join(filepath.Dir(binary), "TingSub-worker"), args...)
	}
	cmd.Stderr = os.Stderr
	return cmd
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "--worker" {
		cmd := workerCommand(options{}, os.Args[2:]...)
		cmd.Stdin, cmd.Stdout = os.Stdin, os.Stdout
		if err := cmd.Run(); err != nil {
			log.Fatal(err)
		}
		return
	}
	home, err := os.UserHomeDir()
	if err != nil {
		log.Fatal(err)
	}
	var o options
	flag.StringVar(&o.directory, "data-dir", filepath.Join(home, "Library", "Application Support", "TingSub"), "Persistent data directory")
	flag.StringVar(&o.python, "python", "", "Python executable for source development")
	flag.StringVar(&o.sourceRoot, "source-root", "", "Source checkout for Python imports")
	flag.BoolVar(&o.selfTest, "self-test", false, "Run the native desktop smoke check")
	flag.BoolVar(&o.noInference, "no-inference", false, "Skip model loading in the smoke check")
	flag.StringVar(&o.asr, "asr", "", "ASR model to prepare in the smoke check")
	flag.StringVar(&o.translation, "translation", "", "Translation model to prepare in the smoke check")
	flag.Parse()
	if runtime.GOOS != "darwin" || runtime.GOARCH != "arm64" {
		log.Fatal("TingSub desktop requires an Apple Silicon Mac")
	}
	if o.python != "" && o.sourceRoot == "" {
		log.Fatal("--python requires --source-root")
	}
	if err := run(o); err != nil {
		log.Fatal(err)
	}
}

type host struct {
	worker            *desktop.Worker
	window            *mygo.Window
	tray              *mygo.Tray
	items             map[string]*mygo.MenuItem
	quitting, stopped bool // accessed only on the MyGo main thread
	closing           atomic.Bool
	working           atomic.Bool
	rejected          atomic.Int64
}

func run(o options) error {
	worker, err := desktop.StartWorker(workerCommand(o, "--data-dir", o.directory, "desktop-rpc"))
	if err != nil {
		return fmt.Errorf("start Python controller: %w", err)
	}
	defer worker.Close()
	h := &host{worker: worker}
	mygo.App.SetName("TingSub")
	mygo.SetFrontend(tingsub.Frontend())
	mygo.BindAs("Desktop", desktop.NewService(worker))
	mygo.App.SetMenu(mygo.NewMenu([]*mygo.MenuItem{{Role: mygo.RoleAppMenu}, {Role: mygo.RoleEditMenu}, {Role: mygo.RoleWindowMenu}}))
	mygo.App.OnBeforeQuit(func(e *mygo.QuitEvent) {
		if h.stopped {
			return
		}
		e.PreventDefault()
		if h.quitting {
			return
		}
		h.quitting = true
		h.closing.Store(true)
		go func() {
			worker.Close()
			mygo.RunOnMain(func() { h.stopped = true; mygo.App.Quit() })
		}()
	})
	mygo.App.OnActivate(func(bool) {
		if h.window != nil && !h.quitting {
			h.show()
		}
	})
	result := make(chan error, 1)
	mygo.App.WhenReady(func() {
		h.window = mygo.NewWindow(mygo.WindowOptions{
			Title: "TingSub", Width: 1060, Height: 780, MinWidth: 880, MinHeight: 660,
			BackgroundColor: "#151719", Page: mygo.PageOptions{DevTools: mygo.DevToolsDisabled},
		})
		page := h.window.Page()
		page.OnWillNavigate(func(e *mygo.NavigateEvent) {
			if !desktop.TrustedDocument(e.URL) {
				h.rejected.Add(1)
				e.PreventDefault()
			}
		})
		page.SetWindowOpenHandler(func(mygo.WindowOpenRequest) *mygo.WindowOptions { return nil })
		page.SetPermissionHandler(func(mygo.PermissionRequest) bool { return false })
		h.window.OnClose(func(e *mygo.CloseEvent) {
			if !h.stopped && h.tray != nil {
				e.PreventDefault()
				h.window.Hide()
			}
		})
		if err := h.installMenu(); err != nil {
			log.Printf("Menu bar unavailable: %v", err)
		}
		if err := page.LoadURL(desktop.EntryURL); err != nil {
			result <- err
			mygo.App.Quit()
			return
		}
		go h.pollMenu()
		if o.selfTest {
			go func() { result <- h.smoke(o); mygo.App.Quit() }()
		}
	})
	if err := mygo.App.Run(); err != nil {
		return err
	}
	if o.selfTest {
		return <-result
	}
	return nil
}

func (h *host) show() { h.window.Restore(); h.window.Show(); h.window.Focus() }

func (h *host) installMenu() error {
	h.items = make(map[string]*mygo.MenuItem)
	var items []*mygo.MenuItem
	for _, action := range []string{"status", "show", "service", "-", "models", "logs", "-", "quit"} {
		if action == "-" {
			items = append(items, mygo.Separator())
			continue
		}
		item := &mygo.MenuItem{Label: "TingSub", Disabled: action == "status"}
		item.Click = func(*mygo.MenuItem, *mygo.Window) {
			if h.quitting {
				return
			}
			switch action {
			case "show":
				h.show()
			case "quit":
				mygo.App.Quit()
			default:
				go h.perform(action)
			}
		}
		h.items[action] = item
		items = append(items, item)
	}
	tray, err := mygo.NewTray(mygo.TrayOptions{Icon: tingsub.TrayIcon, IconIsTemplate: true, ToolTip: "TingSub", Menu: mygo.NewMenu(items)})
	h.tray = tray
	return err
}

func (h *host) perform(action string) {
	if !h.working.CompareAndSwap(false, true) {
		return
	}
	defer h.working.Store(false)
	var err error
	if action == "service" {
		_, err = h.worker.Call(context.Background(), "service_action")
	} else {
		_, err = h.worker.Call(context.Background(), "open_resource", action)
	}
	if err != nil && !h.closing.Load() {
		mygo.Dialog.Message(mygo.MessageOptions{Parent: h.window, Type: mygo.MessageError, Title: "TingSub", Message: err.Error()})
	}
}

func (h *host) pollMenu() {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	for !h.closing.Load() {
		value, err := h.worker.Call(context.Background(), "menu_snapshot")
		if h.closing.Load() {
			return
		}
		mygo.RunOnMain(func() {
			if h.quitting || h.tray == nil {
				return
			}
			if err != nil {
				h.items["status"].SetLabel("Python controller unavailable")
				h.items["service"].SetEnabled(false)
				h.items["show"].SetLabel("Open TingSub")
				h.items["quit"].SetLabel("Quit TingSub")
				return
			}
			view := value.(map[string]any)
			words := view["words"].(map[string]any)
			for action, item := range h.items {
				label := words[action]
				if action == "status" || action == "service" {
					label = view[action]
				}
				item.SetLabel(label.(string))
			}
			h.items["service"].SetEnabled(view["enabled"].(bool) && !h.working.Load())
			h.tray.SetToolTip("TingSub · " + view["status"].(string))
		})
		<-ticker.C
	}
}
