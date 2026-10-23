// Unity -> Grafana: the Unity panel listens for this event and stores its
// argument in the dashboard variable mapped to it (OpenEgiz Unity contract).
mergeInto(LibraryManager.library, {
  SelectTwin: function (id) {
    if (typeof window.dispatchReactUnityEvent === "function") {
      window.dispatchReactUnityEvent("SelectTwin", UTF8ToString(id));
    }
  }
});
