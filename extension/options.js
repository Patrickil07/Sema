const $ = (id) => document.getElementById(id);
chrome.storage.sync.get(["token", "mode", "bubble"], (s) => {
  $("token").value = s.token || "";
  $("mode").value = s.mode || "auto";
  $("bubble").checked = s.bubble !== false;
});
const save = () => chrome.storage.sync.set({ token: $("token").value.trim(), mode: $("mode").value, bubble: $("bubble").checked });
["token", "mode", "bubble"].forEach((id) => $(id).addEventListener("change", save));
$("test").onclick = async () => {
  save();
  $("result").textContent = "Checking…";
  const r = await new Promise((res) => chrome.runtime.sendMessage({ type: "status" }, res));
  $("result").textContent = r && !r.error ? `Connected: ${r.backend} · ${r.voice}`
    : r?.error === "not paired" ? "The Sema app is running but the code doesn't match." : "Can't reach the Sema app. Is it running?";
};
