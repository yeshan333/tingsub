"""Native macOS status menu, sharing the desktop's service ownership and settings."""

import logging
import threading

WORDS = {
    "zh-CN": {
        "stopped": "服务未启动",
        "starting": "正在启动服务…",
        "ready": "服务已就绪",
        "busy": "正在生成字幕",
        "preparing": "正在准备模型…",
        "stopping": "正在停止…",
        "error": "服务出现问题",
        "conflict": "服务端口已被占用",
        "external": "由其他窗口管理",
        "show": "打开 TingSub",
        "start": "启动字幕服务",
        "stop": "停止字幕服务",
        "cancel": "取消模型准备",
        "models": "打开模型文件夹",
        "logs": "在访达中显示日志",
        "quit": "退出 TingSub",
        "working": "正在处理…",
        "failed": "操作未完成",
        "ok": "好",
    },
    "en": {
        "stopped": "Service stopped",
        "starting": "Starting service…",
        "ready": "Ready for captions",
        "busy": "Generating captions",
        "preparing": "Preparing models…",
        "stopping": "Stopping…",
        "error": "Service needs attention",
        "conflict": "Service port is in use",
        "external": "Managed by another window",
        "show": "Open TingSub",
        "start": "Start caption service",
        "stop": "Stop caption service",
        "cancel": "Cancel model preparation",
        "models": "Open model folder",
        "logs": "Reveal logs in Finder",
        "quit": "Quit TingSub",
        "working": "Working…",
        "failed": "Could not complete the action",
        "ok": "OK",
    },
}


def menu_state(status, locale, working=False):
    words = WORDS.get(locale, WORDS["zh-CN"])
    state = status["state"]
    external = state == "ready" and not status["owned"]
    action = "cancel" if state == "preparing" else "stop" if status["owned"] else "start"
    label = "busy" if state == "ready" and status["busy"] else state
    return {
        "status": words.get(label, words["error"]),
        "service": words["external" if external else "working" if working else action],
        "enabled": not working and state not in {"stopping", "conflict"} and not external,
        "symbol": "exclamationmark.bubble"
        if state in {"error", "conflict"}
        else ("captions.bubble.fill" if state == "ready" else "captions.bubble"),
    }


class MenuBar:
    def __init__(self, window, controller, api):
        self.window, self.controller, self.api = window, controller, api
        self._stop = threading.Event()
        self._action_lock = threading.Lock()
        self._quitting = False
        self._native_quit = False
        self.item = None
        self.locale = api.get_interface()["locale"]
        self.status = {"state": "stopped", "owned": False, "busy": False}

    def install(self):
        # before_show is synchronous on Cocoa's main thread (pinned pywebview 6.2.1).
        import AppKit
        from PyObjCTools import AppHelper
        from webview.platforms.cocoa import BrowserView

        self.cocoa, self.dispatch = AppKit, AppHelper.callAfter
        owner = self

        class TingSubMenuTarget(AppKit.NSObject):
            def activate_(self, sender):
                owner.perform(str(sender.representedObject()))

        class TingSubAppDelegate(BrowserView.AppDelegate):
            def applicationShouldHandleReopen_hasVisibleWindows_(self, app, visible):
                owner.show()
                return False

            def applicationShouldTerminate_(self, app):
                owner.request_quit(native=True)
                return AppKit.NSTerminateLater

        self.target = TingSubMenuTarget.alloc().init()
        self.app_delegate = TingSubAppDelegate.alloc().init()
        self.menu = AppKit.NSMenu.alloc().initWithTitle_("TingSub")
        self.menu.setAutoenablesItems_(False)
        self.items = {}
        for action in ("status", "show", "service", "-", "models", "logs", "-", "quit"):
            if action == "-":
                self.menu.addItem_(AppKit.NSMenuItem.separatorItem())
                continue
            item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "", None if action == "status" else "activate:", ""
            )
            item.setTarget_(self.target)
            item.setRepresentedObject_(action)
            item.setEnabled_(action != "status")
            self.menu.addItem_(item)
            self.items[action] = item
        self.item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
            AppKit.NSVariableStatusItemLength
        )
        self.item.setMenu_(self.menu)
        self.render(self.status, self.locale)
        BrowserView._shared_app_delegate = self.app_delegate
        BrowserView.app.setDelegate_(self.app_delegate)
        self.window.events.closing += self.on_close
        threading.Thread(target=self._poll, name="tingsub-menu-status", daemon=True).start()

    def render(self, status, locale):
        if self.item is None or self._quitting:
            return
        self.status, self.locale = status, locale
        words = WORDS[locale]
        view = menu_state(status, locale, self._action_lock.locked())
        for action, item in self.items.items():
            item.setTitle_(view[action] if action in {"status", "service"} else words[action])
            item.setEnabled_(action != "status" and (action != "service" or view["enabled"]))
        button = self.item.button()
        icon = self.cocoa.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            view["symbol"], "TingSub"
        )
        if icon:
            icon.setTemplate_(True)
            icon.setSize_((18, 18))
            button.setImage_(icon)
            button.setTitle_("")
        else:
            button.setTitle_("TingSub")
        button.setToolTip_(f"TingSub · {view['status']}")
        button.setAccessibilityLabel_(f"TingSub · {view['status']}")

    def _poll(self):
        while not self._stop.is_set():
            try:
                status = self.controller.service_status()
                locale = self.api.get_interface()["locale"]
                self.dispatch(self.render, status, locale)
            except Exception:
                logging.getLogger(__name__).exception("Menu status refresh failed")
            self._stop.wait(2)

    def show(self):
        if not self._quitting:
            self.window.restore()
            self.window.show()

    def on_close(self):
        if not self._quitting and self.item is not None:
            self.window.hide()
            return False
        return True

    def perform(self, action):
        if self._quitting:
            return
        if action == "show":
            self.show()
            return
        if action == "quit":
            self.request_quit()
            return
        if action not in {"service", "models", "logs"} or not self._action_lock.acquire(False):
            return
        self.render(self.status, self.locale)

        def work():
            try:
                if action == "service":
                    current = self.controller.service_status()
                    if current["owned"] and current["state"] != "stopping":
                        self.controller.stop_service()
                    elif current["state"] in {"stopped", "error"}:
                        self.controller.start_service()
                else:
                    self.api.open_resource(action)
            except Exception as exc:
                self.dispatch(
                    self.show_error, str(exc).replace(self.controller._token, "[redacted]")
                )
            finally:
                self._action_lock.release()

        threading.Thread(target=work, name="tingsub-menu-action", daemon=True).start()

    def show_error(self, message):
        if self._quitting:
            return
        self.show()
        words = WORDS[self.locale]
        alert = self.cocoa.NSAlert.alloc().init()
        alert.setMessageText_(words["failed"])
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_(words["ok"])
        alert.runModal()

    def request_quit(self, native=False):
        self._native_quit = self._native_quit or native
        if self._quitting:
            return
        self._quitting = True
        self._stop.set()
        for item in self.items.values():
            item.setEnabled_(False)

        def finish():
            self.dispose()
            if self._native_quit:
                self.cocoa.NSApplication.sharedApplication().replyToApplicationShouldTerminate_(
                    True
                )
            else:
                self.window.destroy()

        def close():
            try:
                self.controller.close()
            finally:
                self.dispatch(finish)

        threading.Thread(target=close, name="tingsub-menu-quit", daemon=True).start()

    def dispose(self):
        self._stop.set()
        if self.item is not None:
            self.cocoa.NSStatusBar.systemStatusBar().removeStatusItem_(self.item)
            self.item = None
