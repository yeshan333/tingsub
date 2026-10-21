// MyGo installs its runtime before the bundled document loads. Keep the view's
// API independent of the native transport; browser tests use the same mapping.
if (window.mygo) {
  const methods = {
    snapshot: "Snapshot",
    start_service: "StartService",
    stop_service: "StopService",
    prepare_models: "PrepareModels",
    save_preferences: "SavePreferences",
    get_interface: "GetInterface",
    save_interface: "SaveInterface",
    copy_pairing: "CopyPairing",
    open_resource: "OpenResource",
  };
  window.tingsubDesktop = Object.freeze(Object.fromEntries(
    Object.entries(methods).map(([name, method]) => [
      name, (...args) => window.mygo.call(`Desktop.${method}`, ...args),
    ]),
  ));
}
