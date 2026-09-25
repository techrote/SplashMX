// SMX-051G author-facing localization boundary.
// Ordinary editor copy is addressed by stable SplashMX-owned keys. English is
// the built-in fallback; additional locale catalogues may register at runtime.
const catalogs = new Map();

export const ENGLISH_AUTHOR_COPY = Object.freeze({
  "app.stage": "Stage",
  "app.properties": "Properties",
  "app.library": "Library",
  "app.rules": "Rules",
  "app.connections": "Connections",
  "app.timeline": "Timeline",
  "app.play": "Play",
  "app.stop": "Stop",
  "app.save": "Save",
  "app.reload": "Reload saved",
  "app.inspect": "Inspect",
  "app.saved": "Saved",
  "app.dirty": "Unsaved changes",
  "app.never_saved": "Not saved yet",
  "app.group": "Group selected",
  "app.ungroup": "Ungroup",
  "app.make_reusable": "Make reusable",
  "app.add_rule": "Add Rule",
  "app.back": "Send backward",
  "app.forward": "Bring forward",
  "app.zoom_out": "Zoom out",
  "app.zoom_reset": "100%",
  "app.zoom_in": "Zoom in",
  "app.backup": "Download backup",
  "app.restore": "Restore backup",
  "app.shortcuts": "Keyboard & shortcuts",
  "app.recovery": "Project recovery",
  "app.advanced_details": "Raw diagnostic data",
  "app.no_diagnostics": "No diagnostics.",
  "status.saved": "Saved locally.",
  "status.reloaded": "Reloaded the verified saved project.",
  "status.restore_complete": "Backup restored into the editor. Save when you are ready to replace the durable local head.",
  "status.backup_downloaded": "Backup downloaded.",
  "status.zoom": "Stage zoom: {percent}%.",
  "status.layer_back": "Sent {label} backward.",
  "status.layer_forward": "Brought {label} forward.",
  "confirm.reload": "Reload the last saved revision? Unsaved changes will be discarded.",
  "confirm.restore": "Restore this backup into the editor? Current unsaved changes will be replaced, but the durable saved revision remains unchanged until you press Save.",
  "help.stage": "Drag an object to move it. Drag its corner handle to resize. Arrow keys move a focused object; Shift+Arrow resizes it.",
  "help.recovery": "Backups use the verified SplashMX recovery format. Restore prepares and validates the whole project before replacing the current editor state.",
  "help.shortcuts.save": "Save — Ctrl/⌘+S",
  "help.shortcuts.play": "Play — Ctrl/⌘+Enter",
  "help.shortcuts.stop": "Stop — Escape",
  "help.shortcuts.inspect": "Inspect — Alt+I",
  "help.shortcuts.group": "Group/Ungroup — Ctrl/⌘+G / Ctrl/⌘+Shift+G",
  "help.shortcuts.zoom": "Zoom — Ctrl/⌘+- / Ctrl/⌘+0 / Ctrl/⌘+=",
  "help.shortcuts.layer": "Stacking — Alt+[ / Alt+]"
});

catalogs.set("en", ENGLISH_AUTHOR_COPY);
let locale = "en";

export function registerLocale(code, messages) {
  if (typeof code !== "string" || !code || !messages || typeof messages !== "object") {
    throw new TypeError("A locale code and message catalogue are required.");
  }
  catalogs.set(code, Object.freeze({ ...messages }));
}

export function setLocale(code) {
  locale = catalogs.has(code) ? code : "en";
  document.documentElement.lang = locale;
  applyTranslations(document);
  return locale;
}

export function t(key, values = {}) {
  const table = catalogs.get(locale) || ENGLISH_AUTHOR_COPY;
  let value = table[key] ?? ENGLISH_AUTHOR_COPY[key];
  if (value === undefined) return key;
  for (const [name, replacement] of Object.entries(values)) {
    value = value.replaceAll(`{${name}}`, String(replacement));
  }
  return value;
}

export function applyTranslations(root = document) {
  for (const element of root.querySelectorAll("[data-i18n]")) {
    element.textContent = t(element.dataset.i18n);
  }
  for (const element of root.querySelectorAll("[data-i18n-aria-label]")) {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  }
  for (const element of root.querySelectorAll("[data-i18n-title]")) {
    element.setAttribute("title", t(element.dataset.i18nTitle));
  }
}

export function availableLocales() {
  return Array.from(catalogs.keys()).sort();
}

export function currentLocale() {
  return locale;
}
