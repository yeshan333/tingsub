package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/egoist/mygo"
	"github.com/yeshan333/tingsub/internal/desktop"
)

func (h *host) waitJS(expression string, timeout time.Duration) error {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	for {
		value, err := h.window.Page().EvalContext(ctx, expression)
		if err == nil && value == true {
			return nil
		}
		select {
		case <-ctx.Done():
			diagnostic, stop := context.WithTimeout(context.Background(), 2*time.Second)
			value, _ := h.window.Page().EvalContext(diagnostic, `JSON.stringify({url:location.href, ready:document.readyState, bridge:!!window.tingsubDesktop, runtime:!!window.mygo, error:document.getElementById('error')?.textContent, scripts:[...document.scripts].map(s=>s.src)})`)
			stop()
			return fmt.Errorf("native UI timeout: %s (%v)", expression, fmt.Errorf("%v; page=%v", err, value))
		case <-time.After(100 * time.Millisecond):
		}
	}
}

func (h *host) smoke(o options) error {
	if err := h.waitJS(`!!window.tingsubDesktop && !document.getElementById('serviceAction').disabled`, 25*time.Second); err != nil {
		return err
	}
	page := h.window.Page()
	appearance, err := h.worker.Call(context.Background(), "get_interface")
	if err != nil {
		return err
	}
	defer func() { _, _ = h.worker.Call(context.Background(), "save_interface", appearance) }()
	before := h.rejected.Load()
	if _, err := page.Eval(`location.href = 'mygo://localhost/untrusted.html'; true`); err != nil {
		return err
	}
	deadline := time.Now().Add(5 * time.Second)
	for h.rejected.Load() == before {
		if time.Now().After(deadline) {
			return errors.New("navigation guard did not reject a foreign document")
		}
		time.Sleep(50 * time.Millisecond)
	}
	if err := h.waitJS(`location.href === '`+desktop.EntryURL+`'`, time.Second); err != nil {
		return err
	}
	if err := h.waitJS(`(async () => { try { await mygo.call('Desktop.Close'); return false; } catch { return true; } })()`, time.Second); err != nil {
		return err
	}
	if err := h.waitJS(`(async () => { try { await mygo.call('Desktop.OpenResource', 'https://untrusted.example'); return false; } catch { return true; } })()`, time.Second); err != nil {
		return err
	}
	var menuPresent bool
	mygo.RunOnMain(func() { menuPresent = h.tray != nil })
	if !menuPresent {
		return errors.New("native menu bar was not installed")
	}
	h.window.Close()
	if h.window.IsVisible() {
		return errors.New("closing the window did not hide it")
	}
	mygo.RunOnMain(func() { h.items["show"].Click(nil, nil) })
	if !h.window.IsVisible() {
		return errors.New("menu did not reopen the window")
	}
	if _, err := page.Eval(`mygo.call('Desktop.SaveInterface', {locale:'en', theme:'dark'})`); err != nil {
		return err
	}
	deadline = time.Now().Add(6 * time.Second)
	for {
		var label string
		mygo.RunOnMain(func() { label = h.items["show"].Label })
		if label == "Open TingSub" {
			break
		}
		if time.Now().After(deadline) {
			return errors.New("menu did not follow the interface language")
		}
		time.Sleep(100 * time.Millisecond)
	}
	if !o.noInference {
		if o.asr != "" || o.translation != "" {
			value, err := h.worker.Call(context.Background(), "snapshot")
			if err != nil {
				return err
			}
			selection := value.(map[string]any)["selection"].(map[string]any)
			if o.asr != "" {
				selection["asr"] = o.asr
			}
			if o.translation != "" {
				selection["translation"] = o.translation
			}
			encoded, _ := json.Marshal(selection)
			if _, err := page.Eval(`mygo.call('Desktop.PrepareModels', ` + string(encoded) + `, null)`); err != nil {
				return err
			}
			if err := h.waitJS(`(async () => { const s = await mygo.call('Desktop.Snapshot'); if(s.error) throw Error(s.error); return s.state === 'stopped'; })()`, 180*time.Second); err != nil {
				return err
			}
		}
		if _, err := page.Eval(`mygo.call('Desktop.StartService')`); err != nil {
			return err
		}
		if err := h.waitJS(`document.getElementById('serviceDot').classList.contains('ready')`, 120*time.Second); err != nil {
			return err
		}
		if _, err := page.Eval(`mygo.call('Desktop.StopService')`); err != nil {
			return err
		}
		if err := h.waitJS(`document.getElementById('serviceDot').classList.contains('stopped')`, 20*time.Second); err != nil {
			return err
		}
	}
	fmt.Println(`{"mygo_native_bridge":"passed","navigation_guard":"passed","menu_close_reopen_locale":"passed"}`)
	return nil
}
