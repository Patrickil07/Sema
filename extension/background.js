// Sema extension background: talks to the Sema desktop app (best voices, your API keys)
// over 127.0.0.1, and relays its progress to the page for highlighting.
const BRIDGE = "http://127.0.0.1:51789";

async function settings() {
  return Object.assign({ mode: "auto", token: "", browserVoice: "", rate: 1.0 },
    await chrome.storage.sync.get(["mode", "token", "browserVoice", "rate"]));
}

async function bridge(path, body) {
  const s = await settings();
  const res = await fetch(BRIDGE + path, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json", "X-Sema-Token": s.token },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(res.status === 401 ? "not paired" : "bridge " + res.status);
  return res.json();
}

async function desktopAvailable() {
  const s = await settings();
  if (s.mode === "browser" || !s.token) return false;
  try {
    const ctrl = new AbortController();
    setTimeout(() => ctrl.abort(), 600);
    const r = await fetch(BRIDGE + "/ping", { signal: ctrl.signal });
    return r.ok;
  } catch (e) {
    return false;
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "sema-selection", title: "Read with Sema", contexts: ["selection"] });
  chrome.contextMenus.create({ id: "sema-here", title: "Sema: read from here", contexts: ["page", "link", "image"] });
  chrome.contextMenus.create({ id: "sema-page", title: "Sema: read this page", contexts: ["page"] });
});

function tell(tabId, msg) {
  return chrome.tabs.sendMessage(tabId, msg).catch(async () => {
    // content script not injected yet (tab opened before install): inject and retry
    await chrome.scripting.insertCSS({ target: { tabId }, files: ["content.css"] });
    await chrome.scripting.executeScript({ target: { tabId }, files: ["content.js"] });
    return chrome.tabs.sendMessage(tabId, msg);
  });
}

chrome.contextMenus.onClicked.addListener((info, tab) => {
  const action = { "sema-selection": "read-selection", "sema-here": "read-here", "sema-page": "read-page" }[info.menuItemId];
  if (action && tab) tell(tab.id, { cmd: action });
});

chrome.commands.onCommand.addListener(async (command) => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return;
  tell(tab.id, { cmd: command === "toggle" ? "toggle" : "read-auto" });
});

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  (async () => {
    try {
      switch (msg.type) {
        case "engine":
          reply({ desktop: await desktopAvailable(), settings: await settings() });
          break;
        case "speak":
          reply(await bridge("/speak", { segments: msg.segments, source: "web", kind: msg.kind }));
          break;
        case "control":
          reply(await bridge("/control", { action: msg.action, value: msg.value, segment: msg.segment }));
          break;
        case "status":
          reply(await bridge("/status"));
          break;
        case "voices":
          reply(await bridge("/voices"));
          break;
        case "set-voice":
          reply(await bridge("/settings", { backend: msg.backend, voice: msg.voice }));
          break;
        default:
          reply({ error: "unknown" });
      }
    } catch (e) {
      reply({ error: String(e.message || e) });
    }
  })();
  return true; // async reply
});
