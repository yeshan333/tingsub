"""Cocoa policy for the bundled document, installed before its first navigation.

Kept separate because the native integration uses the pinned pywebview 6.2.1 API.
"""

import json
from urllib.parse import urldefrag


def trusted_document(url, expected, main_frame):
    return bool(main_frame and expected and urldefrag(url)[0] == urldefrag(expected)[0])


def allowed_message(body, url, expected, main_frame, functions):
    return (
        trusted_document(url, expected, main_frame)
        and isinstance(body, dict)
        and isinstance(body.get("funcName"), str)
        and body["funcName"] in functions
        and isinstance(body.get("params"), list)
        and isinstance(body.get("id"), str)
    )


def install_cocoa_guards(window):
    from webview.platforms.cocoa import BrowserView
    from webview.util import js_bridge_call

    instance = BrowserView.instances[window.uid]
    trusted_url = str(window.real_url)
    content = instance.webview.configuration().userContentController()

    class TingSubNavigationGuard(BrowserView.BrowserDelegate):
        def webView_decidePolicyForNavigationAction_decisionHandler_(
            self, webview, action, handler
        ):
            frame = action.targetFrame()
            url = str(action.request().URL().absoluteString())
            handler(1 if trusted_document(url, trusted_url, frame and frame.isMainFrame()) else 0)

    class TingSubBridgeGuard(BrowserView.JSBridge):
        def userContentController_didReceiveScriptMessage_(self, controller, message):
            try:
                frame = message.frameInfo()
                url = str(frame.request().URL().absoluteString())
                body = json.loads(message.body())
                if allowed_message(body, url, trusted_url, frame.isMainFrame(), window._functions):
                    js_bridge_call(window, body["funcName"], body["params"], body["id"])
            except (ValueError, TypeError, AttributeError):
                return

    try:
        instance._navigation_guard = TingSubNavigationGuard.alloc().init()
        instance.webview.setNavigationDelegate_(instance._navigation_guard)
        instance.js_bridge = TingSubBridgeGuard.alloc().initWithObject_(window)
        content.removeScriptMessageHandlerForName_("jsBridge")
        content.addScriptMessageHandler_name_(instance.js_bridge, "jsBridge")
    except Exception:
        content.removeScriptMessageHandlerForName_("jsBridge")
        window._functions.clear()
        raise
