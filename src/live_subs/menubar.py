"""Localized menu presentation shared with the MyGo desktop host."""

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
