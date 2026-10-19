const $ = (id) => document.getElementById(id);
const send = (msg) => new Promise((res) => chrome.runtime.sendMessage(msg, (r) => res(r || {})));

async function tab(cmd) {
  const [t] = await chrome.tabs.query({ active: true, currentWindow: true });
  try { await chrome.tabs.sendMessage(t.id, { cmd }); }
  catch (e) {
    await chrome.scripting.insertCSS({ target: { tabId: t.id }, files: ["content.css"] });
    await chrome.scripting.executeScript({ target: { tabId: t.id }, files: ["content.js"] });
    await chrome.tabs.sendMessage(t.id, { cmd });
  }
  window.close();
}

$("page").onclick = () => tab("read-auto");
$("sel").onclick = () => tab("read-selection");
$("toggle").onclick = () => tab("toggle");
$("stop").onclick = () => tab("stop");
$("opts").onclick = (e) => { e.preventDefault(); chrome.runtime.openOptionsPage(); };

(async () => {
  const eng = await send({ type: "engine" });
  const sel = $("voice");
  if (eng.desktop) {
    const v = await send({ type: "voices" });
    if (v.error) { $("engine").textContent = "Sema app found but not paired. Open Settings."; return; }
    $("engine").textContent = `Using the Sema app (${v.backend} voices).`;
    for (const voice of v.voices) sel.add(new Option(voice.name, voice.id, false, voice.id === v.current));
    sel.onchange = () => send({ type: "set-voice", voice: sel.value });
  } else {
    $("engine").textContent = eng.settings?.token ? "Sema app not running: using browser voices."
      : "Using browser voices. Pair the Sema app in Settings for premium AI voices.";
    const fill = () => {
      sel.innerHTML = "";
      const voices = speechSynthesis.getVoices().sort((a, b) => (/Natural|Online/.test(b.name) - /Natural|Online/.test(a.name)));
      sel.add(new Option("Best available", ""));
      for (const v of voices) sel.add(new Option(`${v.name} (${v.lang})`, v.name, false, v.name === eng.settings.browserVoice));
    };
    fill();
    speechSynthesis.onvoiceschanged = fill;
    sel.onchange = () => chrome.storage.sync.set({ browserVoice: sel.value });
  }
  $("voiceWrap").hidden = false;
})();
