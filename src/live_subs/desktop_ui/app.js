"use strict";
const $ = (id) => document.getElementById(id);
const words = {
  "zh-CN": {
    brandSub: "听桥 · 本地字幕",
    workspace: "工作空间",
    captions: "字幕",
    models: "本地模型",
    connection: "浏览器连接",
    settings: "设置",
    localNote: "声音留在你的电脑",
    captionsDescription: "英文、日文原声，中文与英文字幕。",
    modelsDescription: "两个模型，一条完全本地的字幕链路。",
    connectionDescription: "一次配对，从当前标签页开始。",
    settingsDescription: "把工作空间调整成习惯的样子。",
    preview: "样式预览",
    sampleNote: "示例文字 · 非实时转录",
    captionOptions: "字幕偏好",
    nextSession: "下一次开始字幕时生效",
    sourceLanguage: "原声语言",
    sourceHint: "指定语言通常比自动识别更稳定",
    english: "英语",
    japanese: "日语",
    automatic: "自动识别",
    displayLanguage: "字幕语言",
    displayHint: "翻译与原声识别均在本机完成",
    bilingual: "中文 + English",
    sourceChinese: "中文 + 原文",
    partials: "实时预览",
    partialsHint: "先显示识别草稿，再用完整句子更新",
    fontSize: "字幕字号",
    installedModels: "推理模型",
    metal: "MLX · Metal 加速",
    downloadHint:
      "首次准备需要联网下载模型。完成后，字幕识别和翻译可离线运行。",
    prepare: "准备模型",
    prepared: "模型已准备",
    licenseTitle: "模型有各自的许可证",
    licenseHint:
      "默认翻译模型 Qwen2.5-3B 使用 Qwen Research License，商业使用需另行获得授权。TingSub 代码使用 MIT 许可证。",
    licenseLink: "查看模型许可",
    logs: "运行日志",
    asr: "语音识别",
    translation: "双语翻译",
    downloaded: "已下载",
    missing: "待下载",
    connectTitle: "让浏览器连接本机模型",
    connectHint: "只采集你主动开启字幕的标签页。",
    step1: "加载浏览器插件",
    step1Hint:
      "在 Chrome 的扩展程序页面打开「开发者模式」，选择「加载已解压的扩展程序」，加载 extension 文件夹。",
    openExtension: "打开插件文件夹",
    step2: "粘贴配对码",
    step2Hint: "打开 TingSub 插件，在「本机配对」中粘贴配对码。仅需设置一次。",
    copyPairing: "复制配对码",
    step3: "开始听一段直播",
    step3Hint:
      "启动下方的本机服务。打开视频或直播，在插件中点击「开始字幕」。字幕会直接显示在视频页面上。",
    guide: "完整安装指南",
    appearance: "界面",
    uiLanguage: "界面语言",
    theme: "外观",
    dark: "深色",
    light: "浅色",
    system: "跟随系统",
    about: "关于本机运行",
    audioPrivacy: "音频与字幕",
    privacyHint: "保留在内存中，不上传云端，不保存录音",
    localOnly: "仅本地",
    closeBehavior: "关闭窗口",
    closeHint: "会停止由此窗口启动的服务；终端启动的服务不受影响",
    start: "启动服务",
    stop: "停止服务",
    cancel: "取消",
    stopped: "服务未启动",
    starting: "正在预热模型",
    ready: "模型已就绪",
    busy: "正在生成字幕",
    stopping: "正在停止",
    preparing: "正在准备模型",
    error: "启动未完成",
    conflict: "端口已被占用",
    external: "外部服务已连接",
    stoppedHint: "启动后，在浏览器插件中开启字幕。",
    startingHint: "首次加载可能需要几十秒，请稍候。",
    readyHint: "在视频标签页打开 TingSub 插件，开始字幕。",
    busyHint: "当前浏览器会话正在使用本机模型。",
    stoppingHint: "正在释放本机模型与音频连接。",
    preparingHint: "正在下载或检查模型；可在本地模型中查看日志。",
    errorHint: "请打开本地模型页查看日志，然后重试。",
    conflictHint: "请先停止旧服务，或使用相同的数据目录启动。",
    externalHint: "此服务从其他窗口启动，请在原窗口停止。",
    missingHint: "请先准备语音识别与翻译模型。",
    saved: "已保存，下次开始字幕时生效",
    copied: "配对码已复制",
    uiSaved: "界面设置已保存",
    bridgeError: "无法连接桌面控制器，请重新打开 TingSub。",
    operationError: "操作未完成：",
  },
  en: {
    brandSub: "LOCAL CAPTIONS",
    workspace: "WORKSPACE",
    captions: "Captions",
    models: "Local models",
    connection: "Browser connection",
    settings: "Settings",
    localNote: "Your audio stays here",
    captionsDescription:
      "English and Japanese audio. Chinese and English captions.",
    modelsDescription: "Two models. One entirely local caption pipeline.",
    connectionDescription: "Pair once. Start with the tab you are watching.",
    settingsDescription: "A workspace that feels familiar.",
    preview: "STYLE PREVIEW",
    sampleNote: "Sample text · not a live transcript",
    captionOptions: "Caption preferences",
    nextSession: "Applied when you next start captions",
    sourceLanguage: "Spoken language",
    sourceHint: "A specific language is usually more reliable than auto-detect",
    english: "English",
    japanese: "Japanese",
    automatic: "Auto-detect",
    displayLanguage: "Caption languages",
    displayHint: "Speech recognition and translation both run on your Mac",
    bilingual: "中文 + English",
    sourceChinese: "Chinese + original",
    partials: "Live drafts",
    partialsHint: "Show an early transcript, then refine the complete sentence",
    fontSize: "Caption size",
    installedModels: "Inference models",
    metal: "MLX · Metal acceleration",
    downloadHint:
      "An internet connection is needed for the first download. Recognition and translation then work offline.",
    prepare: "Prepare models",
    prepared: "Models available",
    licenseTitle: "Models have their own licenses",
    licenseHint:
      "The default Qwen2.5-3B translation model uses the Qwen Research License; commercial use requires separate authorization. TingSub code is MIT licensed.",
    licenseLink: "Read model license",
    logs: "Process log",
    asr: "Speech recognition",
    translation: "Bilingual translation",
    downloaded: "Downloaded",
    missing: "Not downloaded",
    connectTitle: "Connect your browser to local models",
    connectHint: "Only the tab you explicitly start is captured.",
    step1: "Load the browser extension",
    step1Hint:
      "In Chrome extensions, enable Developer mode and choose Load unpacked. Select the extension folder.",
    openExtension: "Open extension folder",
    step2: "Paste your pairing code",
    step2Hint:
      "Open the TingSub extension and paste the code under local pairing. You only need to do this once.",
    copyPairing: "Copy pairing code",
    step3: "Start with a video or live stream",
    step3Hint:
      "Start the local service below. Open a video and click Start captions in the extension. Captions appear directly on the video page.",
    guide: "Full installation guide",
    appearance: "Interface",
    uiLanguage: "Interface language",
    theme: "Appearance",
    dark: "Dark",
    light: "Light",
    system: "System",
    about: "Running locally",
    audioPrivacy: "Audio & captions",
    privacyHint: "Kept in memory. No cloud uploads or saved recordings.",
    localOnly: "Local only",
    closeBehavior: "Closing this window",
    closeHint:
      "Stops services started here. Services started in a terminal are unaffected.",
    start: "Start service",
    stop: "Stop service",
    cancel: "Cancel",
    stopped: "Service is stopped",
    starting: "Warming up models",
    ready: "Models are ready",
    busy: "Generating captions",
    stopping: "Stopping service",
    preparing: "Preparing models",
    error: "Service could not start",
    conflict: "Port is already in use",
    external: "External service connected",
    stoppedHint: "Start the service, then enable captions in your browser.",
    startingHint: "The first warm-up can take a little while.",
    readyHint: "Open TingSub in your video tab to start captions.",
    busyHint: "A browser session is using your local models.",
    stoppingHint: "Releasing models and the audio connection.",
    preparingHint: "Downloading or checking files. See Local models for logs.",
    errorHint: "Check the log in Local models, then try again.",
    conflictHint:
      "Stop the old service, or launch with the same data directory.",
    externalHint:
      "This service was started elsewhere. Stop it in its original window.",
    missingHint: "Prepare the speech and translation models first.",
    saved: "Saved. Applies to the next caption session.",
    copied: "Pairing code copied",
    uiSaved: "Interface settings saved",
    bridgeError: "Cannot reach the desktop controller. Please reopen TingSub.",
    operationError: "Could not complete the operation: ",
  },
};
let locale = "zh-CN";
let page = "captions";
let snapshot;
let busy = false;
let api;
let toastTimer;
let pollTimer;
let queue = Promise.resolve();
const dirty = new Set();
const t = (key) => words[locale][key] || key;
const themeQuery = matchMedia("(prefers-color-scheme: dark)");
function applyTheme() {
  document.documentElement.dataset.theme =
    $("theme").value === "system"
      ? themeQuery.matches
        ? "dark"
        : "light"
      : $("theme").value;
}
themeQuery.addEventListener("change", applyTheme);
function translate() {
  document.documentElement.lang = locale;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  $("pageTitle").textContent = $("breadcrumbPage").textContent = t(page);
  $("pageDescription").textContent = t(`${page}Description`);
  if (snapshot) render(snapshot);
}
function showPage(name) {
  page = name;
  document.querySelectorAll(".page").forEach((el) => {
    el.hidden = el.id !== `page-${page}`;
  });
  document.querySelectorAll(".nav-item").forEach((el) => {
    const selected = el.dataset.page === page;
    el.classList.toggle("selected", selected);
    if (selected) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  });
  translate();
}
function toast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    $("toast").hidden = true;
  }, 3000);
}
function error(message) {
  $("error").textContent = message;
  $("error").hidden = !message;
}
function updatePreview() {
  const size = Number($("fontSize").value);
  $("fontSizeValue").textContent = size;
  $("previewZh").style.fontSize = `${size}px`;
  $("previewEn").style.fontSize = `${Math.round(size * 0.6)}px`;
  const japanese = $("language").value === "ja";
  const original = $("display").value === "source-zh";
  const source = japanese
    ? "世界は広い。ゆっくり耳を傾けよう。"
    : "There's a whole world out there. Take it in.";
  $("previewZh").textContent = "世界很大，慢慢听。";
  $("previewEn").textContent = original
    ? source
    : "There's a whole world out there. Take it in.";
  document.querySelector(".preview-tag").textContent =
    `${japanese ? "JA" : "EN"} → ${original ? "中 / 原" : "中 / EN"}`;
}
function render(data) {
  snapshot = data;
  const state = data.state;
  const label =
    state === "ready"
      ? data.busy
        ? "busy"
        : data.owned
          ? "ready"
          : "external"
      : state;
  $("serviceBadge").lastElementChild.textContent = t(label);
  $("serviceBadge").className = `badge ${state}`;
  $("serviceDot").className = `status-dot ${state}`;
  $("serviceTitle").textContent = t(label);
  const allModels = data.models.every((model) => model.ready);
  $("serviceHint").textContent = t(
    state === "stopped" && !allModels ? "missingHint" : `${label}Hint`,
  );
  const stopping =
    ["starting", "preparing", "ready"].includes(state) && data.owned;
  $("serviceAction").textContent = t(
    stopping
      ? state === "ready"
        ? "stop"
        : "cancel"
      : !allModels && state === "stopped"
        ? "prepare"
        : "start",
  );
  $("serviceAction").disabled =
    busy ||
    ["stopping", "conflict"].includes(state) ||
    (state === "ready" && !data.owned);
  $("prepare").disabled =
    busy || allModels || !["stopped", "error"].includes(state);
  $("prepare").textContent = t(allModels ? "prepared" : "prepare");
  $("modelsDot").hidden = allModels;
  for (const [key, value] of Object.entries(data.preferences)) {
    if (dirty.has(key) || document.activeElement === $(key)) continue;
    if (key === "partials") $(key).checked = value;
    else $(key).value = value;
  }
  updatePreview();
  $("logs").textContent = data.logs || "—";
  const signature = JSON.stringify([locale, data.models]);
  if ($("modelList").dataset.signature !== signature) {
    $("modelList").replaceChildren();
    data.models.forEach((model) => {
      const row = document.createElement("div");
      row.className = "model-row";
      row.innerHTML =
        '<span class="model-icon"><svg><use href="#i-model"/></svg></span><div class="model-body"><h3></h3><p></p></div><div class="model-state"><span></span><small></small></div>';
      row.querySelector("h3").textContent = t(model.kind);
      row.querySelector("p").textContent = model.repo;
      row.querySelector(".model-state").classList.toggle("ready", model.ready);
      row.querySelector(".model-state span").textContent = t(
        model.ready ? "downloaded" : "missing",
      );
      row.querySelector("small").textContent = model.bytes
        ? `${(model.bytes / 1024 ** 3).toFixed(2)} GB`
        : "—";
      $("modelList").append(row);
    });
    $("modelList").dataset.signature = signature;
  }
}
async function refresh() {
  render(await api.snapshot());
}
async function action(method, ...args) {
  if (!api || busy) return;
  busy = true;
  error("");
  if (snapshot) render(snapshot);
  try {
    const result = await api[method](...args);
    await refresh();
    return result;
  } catch (exception) {
    error(t("operationError") + (exception.message || String(exception)));
  } finally {
    busy = false;
    if (snapshot) render(snapshot);
  }
}
for (const key of ["language", "display", "partials", "fontSize"]) {
  $(key).addEventListener("input", updatePreview);
  $(key).addEventListener("change", () => {
    if (!api) return;
    const value =
      key === "partials"
        ? $(key).checked
        : key === "fontSize"
          ? Number($(key).value)
          : $(key).value;
    dirty.add(key);
    queue = queue
      .then(async () => {
        try {
          await api.save_preferences({ [key]: value });
          toast(t("saved"));
          error("");
        } catch (exception) {
          error(t("operationError") + exception.message);
        }
      })
      .finally(async () => {
        dirty.delete(key);
        await refresh().catch(() => {});
      });
  });
}
for (const key of ["locale", "theme"])
  $(key).addEventListener("change", async () => {
    locale = $("locale").value;
    applyTheme();
    translate();
    if (api)
      await action("save_interface", { locale, theme: $("theme").value });
  });
document
  .querySelectorAll("[data-page]")
  .forEach((button) =>
    button.addEventListener("click", () => showPage(button.dataset.page)),
  );
document
  .querySelectorAll("[data-resource]")
  .forEach((button) =>
    button.addEventListener("click", () =>
      action("open_resource", button.dataset.resource),
    ),
  );
$("copyPairing").addEventListener("click", async () => {
  if (await action("copy_pairing")) toast(t("copied"));
});
$("prepare").addEventListener("click", () => action("prepare_models"));
$("serviceAction").addEventListener("click", () => {
  if (!snapshot) return;
  if (snapshot.owned) action("stop_service");
  else if (!snapshot.models.every((model) => model.ready)) showPage("models");
  else action("start_service");
});
async function poll() {
  try {
    await refresh();
  } catch {
    error(t("bridgeError"));
    $("serviceAction").disabled = true;
  }
  pollTimer = setTimeout(poll, 1500);
}
async function connect() {
  if (api) return;
  api = window.pywebview?.api;
  if (!api) return;
  try {
    const appearance = await api.get_interface();
    locale = appearance.locale;
    $("locale").value = locale;
    $("theme").value = appearance.theme;
    applyTheme();
    translate();
    await poll();
  } catch {
    error(t("bridgeError"));
  }
}
window.addEventListener("pywebviewready", connect);
window.addEventListener("beforeunload", () => clearTimeout(pollTimer));
translate();
connect();
