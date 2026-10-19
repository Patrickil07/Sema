// Sema content script: finds the readable text on the page, splits it into sentences
// mapped to DOM ranges, reads them (desktop app voices or browser voices) and
// highlights the sentence (and word, with browser voices) being spoken.
(() => {
  if (window.__semaLoaded) return;
  window.__semaLoaded = true;

  const SKIP = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "SVG", "CANVAS", "BUTTON", "SELECT", "TEXTAREA",
    "INPUT", "IFRAME", "OBJECT", "TEMPLATE", "VIDEO", "AUDIO", "MATH"]);
  const CHROME_PARTS = "nav, footer, aside, [role=navigation], [role=banner], [role=contentinfo], " +
    "[role=complementary], .sema-host";
  // interface bits that are never content, wherever they appear (buttons, timestamps, toolbars)
  const UI_PARTS = "[role=toolbar], [role=button], [role=status], [role=tooltip], [role=menu], time, " +
    "[aria-hidden=true], .sema-host";
  const BLOCK = new Set(["P", "DIV", "LI", "H1", "H2", "H3", "H4", "H5", "H6", "BLOCKQUOTE", "TD", "TH",
    "PRE", "FIGCAPTION", "DD", "DT", "SECTION", "ARTICLE", "MAIN", "HEADER", "TR", "CAPTION", "SUMMARY",
    "LABEL", "LEGEND", "BODY", "UL", "OL", "DL", "TABLE", "FORM", "FIELDSET", "DETAILS", "ADDRESS"]);

  let lastContextTarget = null;
  document.addEventListener("contextmenu", (e) => { lastContextTarget = e.target; }, true);

  // ------------------------------------------------------------------ extraction
  const visibleCache = new WeakMap();
  function visible(el) {
    if (visibleCache.has(el)) return visibleCache.get(el);
    let v = true;
    if (el.checkVisibility) v = el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true });
    else { const s = getComputedStyle(el); v = s.display !== "none" && s.visibility !== "hidden"; }
    visibleCache.set(el, v);
    return v;
  }

  function blockOf(node) {
    let el = node.parentElement;
    while (el && !BLOCK.has(el.tagName)) el = el.parentElement;
    return el || document.body;
  }

  function textNodes(root, clampRange, excludeChrome) {
    const out = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        if (n.nodeType === 1) {
          if (SKIP.has(n.tagName.toUpperCase()) || n.hidden) return NodeFilter.FILTER_REJECT;
          if (n !== root && n.matches(UI_PARTS)) return NodeFilter.FILTER_REJECT;
          if (excludeChrome && n !== root && n.matches(CHROME_PARTS)) return NodeFilter.FILTER_REJECT;
          if (!visible(n)) return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_SKIP;
        }
        if (!n.nodeValue.trim()) return NodeFilter.FILTER_SKIP;
        if (clampRange && !clampRange.intersectsNode(n)) return NodeFilter.FILTER_SKIP;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    while (walker.nextNode()) out.push(walker.currentNode);
    return out;
  }

  // Group text nodes into blocks, split blocks into sentences, map each sentence to a Range.
  function buildSegments(nodes, clampRange) {
    const blocks = [];
    let cur = null;
    for (const n of nodes) {
      const b = blockOf(n);
      if (!cur || cur.block !== b) { cur = { block: b, parts: [] }; blocks.push(cur); }
      let start = 0, end = n.nodeValue.length;
      if (clampRange) {
        if (n === clampRange.startContainer) start = clampRange.startOffset;
        if (n === clampRange.endContainer) end = clampRange.endOffset;
      }
      cur.parts.push({ node: n, start, end });
    }
    const segments = [];
    for (const b of blocks) {
      let text = "";
      const map = []; // [textOffset, node, nodeOffset]
      for (const p of b.parts) {
        const piece = p.node.nodeValue.slice(p.start, p.end);
        map.push({ at: text.length, node: p.node, base: p.start, len: piece.length });
        text += piece;
      }
      const isHeading = /^H[1-6]$/.test(b.block.tagName);
      // numbered list items are announced ("3. Double-click setup.bat") like a person reading steps
      const ol = b.block.tagName === "LI" && b.block.parentElement?.tagName === "OL" ? b.block.parentElement : null;
      let prefix = ol ? `${[...ol.children].indexOf(b.block) + (ol.start || 1)}. ` : "";
      for (const s of sentences(text)) {
        const range = document.createRange();
        const [sn, so] = locate(map, s.start, false);
        const [en, eo] = locate(map, s.end, true);
        try { range.setStart(sn, so); range.setEnd(en, eo); } catch (e) { continue; }
        const spoken = prefix + s.text.replace(/\s+/g, " ").trim();
        prefix = "";
        if (!/[\p{L}\p{N}]/u.test(spoken)) continue;
        segments.push({ id: "s" + segments.length, text: spoken, range, pause_after_ms: 0 });
      }
      if (segments.length) segments[segments.length - 1].pause_after_ms = isHeading ? 450 : 300;
    }
    return segments;
  }

  function locate(map, offset, isEnd) {
    for (let i = 0; i < map.length; i++) {
      const m = map[i];
      if (offset < m.at + m.len || (isEnd && offset === m.at + m.len) || i === map.length - 1) {
        return [m.node, m.base + Math.max(0, Math.min(m.len, offset - m.at))];
      }
    }
    return [map[0].node, map[0].base];
  }

  const NO_BREAK = /(?:\b[A-Z]|\b(?:Mr|Mrs|Ms|Dr|Prof|St|Sr|Jr|vs|etc|e\.g|i\.e|Inc|Ltd|Co|No|Fig|approx|U\.S|a\.m|p\.m))\.$/;
  function sentences(text) {
    const out = [];
    // a sentence ends at . ! ? … (plus closing quotes) followed by whitespace or the end
    const re = /(?:[^.!?…]|[.!?…]+(?!["')\]]*(?:\s|$)))*(?:[.!?…]+["')\]]*|$)\s*/g;
    let m, pending = null;
    while ((m = re.exec(text)) && m[0].length) {
      const start = pending ? pending.start : m.index;
      const end = m.index + m[0].length;
      const body = text.slice(start, end);
      const next = text.slice(end, end + 2);
      if (NO_BREAK.test(body.trimEnd()) || (next && /^[a-z]/.test(next))) { pending = { start }; continue; }
      pending = null;
      const lead = body.length - body.trimStart().length;
      out.push({ start: start + lead, end: start + body.trimEnd().length, text: body.trim() });
    }
    if (pending) out.push({ start: pending.start, end: text.length, text: text.slice(pending.start).trim() });
    return out.filter((s) => s.text);
  }

  function mainRoot() {
    const candidates = [...document.querySelectorAll("article, [role=main], main, [itemprop=articleBody]")]
      .filter(visible);
    let best = null, bestScore = 0;
    const consider = (el) => {
      const ps = el.querySelectorAll("p, li, h1, h2, h3, blockquote, pre");
      let score = 0;
      ps.forEach((p) => { const l = p.textContent.trim().length; if (l > 40) score += l; });
      if (score > bestScore) { best = el; bestScore = score; }
    };
    candidates.forEach(consider);
    if (!best || bestScore < 400) {
      // score every block container by paragraph text it directly holds
      const tally = new Map();
      document.querySelectorAll("p").forEach((p) => {
        if (!visible(p)) return;
        const parent = p.parentElement;
        tally.set(parent, (tally.get(parent) || 0) + p.textContent.trim().length);
      });
      for (const [el, score] of tally) if (score > bestScore) { best = el; bestScore = score; }
      // climb a little to include headings next to the paragraphs
      if (best && best.parentElement && best.parentElement !== document.body) best = best.parentElement;
    }
    return bestScore > 200 ? best : document.body;
  }

  function selectionSegments() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.toString().trim()) return null;
    const range = sel.getRangeAt(0);
    const root = range.commonAncestorContainer.nodeType === 1 ? range.commonAncestorContainer
      : range.commonAncestorContainer.parentElement;
    const segs = buildSegments(textNodes(root, range, false), range);
    return segs.length ? segs : [{ id: "s0", text: sel.toString().trim(), range: null }];
  }

  function pageSegments(fromNode) {
    const root = mainRoot();
    let segs = buildSegments(textNodes(root, null, root === document.body));
    if (fromNode) {
      const idx = segs.findIndex((s) => s.range && (s.range.intersectsNode(fromNode) ||
        s.range.comparePoint(fromNode, 0) <= 0));
      if (idx > 0) segs = segs.slice(idx);
      else if (idx < 0) {
        // clicked outside the main content: read from that element in the whole page
        segs = buildSegments(textNodes(document.body, null, true));
        const j = segs.findIndex((s) => s.range && (s.range.intersectsNode(fromNode) || s.range.comparePoint(fromNode, 0) <= 0));
        if (j >= 0) segs = segs.slice(j);
      }
    }
    return segs;
  }

  // ------------------------------------------------------------------ highlighting
  const hasHighlights = typeof CSS !== "undefined" && CSS.highlights && typeof Highlight !== "undefined";
  function highlight(seg, word) {
    if (!hasHighlights) return;
    CSS.highlights.delete("sema-sentence");
    CSS.highlights.delete("sema-word");
    if (seg && seg.range) {
      CSS.highlights.set("sema-sentence", new Highlight(seg.range));
      const r = seg.range.getBoundingClientRect();
      if (r.height && (r.top < 60 || r.bottom > innerHeight - 110)) {
        window.scrollBy({ top: r.top - innerHeight * 0.35, behavior: "smooth" });
      }
    }
    if (word) CSS.highlights.set("sema-word", new Highlight(word));
  }

  function wordRange(seg, charIndex, length) {
    // map a char offset in the spoken sentence back into the DOM range (best effort)
    if (!seg.range) return null;
    try {
      const nodes = textNodes(seg.range.commonAncestorContainer.nodeType === 1
        ? seg.range.commonAncestorContainer : seg.range.commonAncestorContainer.parentElement, seg.range, false);
      let seen = 0;
      for (const n of nodes) {
        const s = n === seg.range.startContainer ? seg.range.startOffset : 0;
        const e = n === seg.range.endContainer ? seg.range.endOffset : n.nodeValue.length;
        const raw = n.nodeValue.slice(s, e).replace(/\s+/g, " ");
        if (charIndex < seen + raw.length) {
          const r = document.createRange();
          const off = s + (charIndex - seen);
          r.setStart(n, Math.min(off, e));
          r.setEnd(n, Math.min(off + (length || 1), e));
          return r;
        }
        seen += raw.length;
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  // ------------------------------------------------------------------ light normalisation for browser voices
  const ABBR = [[/\be\.g\.,?/g, "for example,"], [/\bi\.e\.,?/g, "that is,"], [/\betc\./g, "et cetera."],
    [/\bDr\.(?=\s+[A-Z])/g, "Doctor"], [/\bMr\.(?=\s)/g, "Mister"], [/\bMrs\.(?=\s)/g, "Missus"],
    [/\bSt\.(?=\s+[A-Z])/g, "Saint"], [/\bvs\.?(?=\s)/g, "versus"], [/\s&\s/g, " and "],
    [/(?:https?:\/\/)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)(?:\/[^\s]*)?/gi, (m, d) => /^\d+(\.\d+)+$/.test(d) ? m : d.replace(/\./g, " dot ")],
    [/\$(\d+(?:\.\d+)?)\s?([kKmMbB]|bn)\b/g, (m, n, u) => `${n} ${({ k: "thousand", m: "million", b: "billion", bn: "billion" })[u.toLowerCase()]} dollars`]];
  function lightNormalize(t) {
    for (const [re, rep] of ABBR) t = t.replace(re, rep);
    return t;
  }

  // ------------------------------------------------------------------ playback
  const state = { segs: [], index: 0, mode: null, playing: false, paused: false, poll: null, rate: 1, voice: null };

  function bestBrowserVoice(preferred) {
    const voices = speechSynthesis.getVoices();
    if (preferred) { const v = voices.find((x) => x.name === preferred); if (v) return v; }
    const lang = (document.documentElement.lang || navigator.language || "en").slice(0, 2).toLowerCase();
    const ranked = voices.filter((v) => v.lang.toLowerCase().startsWith(lang));
    // Edge's "Natural" voices are neural; old Windows desktop voices (David, Zira, Mark...) sound robotic
    const score = (v) => (/Natural/i.test(v.name) ? 6 : 0) + (/Online/i.test(v.name) ? 2 : 0) +
      (/Google/i.test(v.name) ? 2 : 0) + (/Multilingual/i.test(v.name) ? 1 : 0) +
      (/\b(David|Zira|Mark|Hazel|George|Susan|Desktop)\b/.test(v.name) && !/Natural/i.test(v.name) ? -5 : 0);
    ranked.sort((a, b) => score(b) - score(a));
    return ranked[0] || voices[0] || null;
  }

  function send(msg) {
    return new Promise((res) => chrome.runtime.sendMessage(msg, (r) => res(r || { error: chrome.runtime.lastError?.message })));
  }

  async function start(segs, startIndex = 0) {
    stop(false);
    if (!segs || !segs.length) return toast("Nothing readable found here.");
    state.segs = segs;
    state.index = startIndex;
    const eng = await send({ type: "engine" });
    state.rate = eng.settings?.rate || 1;
    state.mode = eng.desktop ? "desktop" : "browser";
    ui.show();
    if (state.mode === "desktop") {
      const r = await send({ type: "speak", segments: segs.slice(startIndex).map(({ id, text, pause_after_ms }) => ({ id, text, pause_after_ms })) });
      if (r.error) { state.mode = "browser"; toast("Sema app not reachable (" + r.error + "), using browser voice"); }
      else { state.playing = true; pollDesktop(); ui.update(); return; }
    }
    state.voice = bestBrowserVoice(eng.settings?.browserVoice);
    state.playing = true;
    speakBrowser();
    ui.update();
  }

  function pollDesktop() {
    clearInterval(state.poll);
    let started = false;
    state.poll = setInterval(async () => {
      const st = await send({ type: "status" });
      if (st.error) return;
      ui.label(`${st.backend} · ${shortVoice(st.voice)} · ${st.speed.toFixed(1)}×`);
      if (st.state !== "idle") started = true;
      state.paused = st.state === "paused";
      if (st.segment != null) {
        const i = state.segs.findIndex((s) => s.id === st.segment);
        if (i >= 0 && i !== state.index) state.index = i;
        highlight(state.segs[state.index]);
      }
      if (started && st.state === "idle") { if (st.error) toast(st.error); stop(false); }
      ui.update();
    }, 220);
  }

  function speakBrowser() {
    const seg = state.segs[state.index];
    if (!seg) return stop(false);
    const u = new SpeechSynthesisUtterance(lightNormalize(seg.text));
    if (state.voice) { u.voice = state.voice; u.lang = state.voice.lang; }
    u.rate = state.rate;
    u.onstart = () => highlight(seg);
    u.onboundary = (e) => { if (e.name === "word") highlight(seg, wordRange(seg, e.charIndex, e.charLength)); };
    u.onend = () => {
      if (!state.playing || state.segs[state.index] !== seg) return;
      state.index++;
      if (state.index >= state.segs.length) return stop(false);
      setTimeout(() => state.playing && !state.paused && speakBrowser(), seg.pause_after_ms ? 120 : 0);
    };
    u.onerror = (e) => { if (e.error !== "interrupted" && e.error !== "canceled") toast("Voice error: " + e.error); };
    speechSynthesis.speak(u);
    ui.label(`browser · ${state.voice ? state.voice.name.replace(/^Microsoft\s+/, "").replace(/\s*\(.*$/, "") : "default"} · ${state.rate.toFixed(1)}×`);
  }

  function toggle() {
    if (!state.playing) return;
    if (state.mode === "desktop") { send({ type: "control", action: "toggle" }); state.paused = !state.paused; }
    else if (state.paused) { state.paused = false; speechSynthesis.resume(); if (!speechSynthesis.speaking) speakBrowser(); }
    else { state.paused = true; speechSynthesis.pause(); }
    ui.update();
  }

  function jump(delta) { seek(Math.max(0, Math.min(state.segs.length - 1, state.index + delta))); }

  function seek(i) {
    if (!state.playing) return;
    state.index = i;
    if (state.mode === "desktop") send({ type: "control", action: "seek", segment: state.segs[i].id });
    else { speechSynthesis.cancel(); state.paused = false; setTimeout(speakBrowser, 30); }
  }

  async function setRate(delta) {
    state.rate = Math.max(0.5, Math.min(3, Math.round((state.rate + delta) * 10) / 10));
    chrome.storage.sync.set({ rate: state.rate });
    if (state.mode === "desktop") {
      const st = await send({ type: "status" });
      send({ type: "control", action: "speed", value: Math.max(0.5, Math.min(3.5, (st.speed || 1) + delta)) });
    } else if (state.playing) { speechSynthesis.cancel(); setTimeout(speakBrowser, 30); }
  }

  function stop(tellDesktop = true) {
    clearInterval(state.poll);
    if (state.mode === "desktop" && tellDesktop && state.playing) send({ type: "control", action: "stop" });
    if (state.mode === "browser") speechSynthesis.cancel();
    state.playing = false;
    state.paused = false;
    highlight(null);
    ui.update();
  }

  // click on a sentence while reading = jump there
  document.addEventListener("click", (e) => {
    if (!state.playing || e.composedPath().some((n) => n.classList && n.classList.contains("sema-host"))) return;
    if (!e.altKey) return; // Alt+click to jump, so normal clicks keep working
    const pos = document.caretPositionFromPoint ? document.caretPositionFromPoint(e.clientX, e.clientY) : null;
    const node = pos ? pos.offsetNode : document.caretRangeFromPoint?.(e.clientX, e.clientY)?.startContainer;
    const i = state.segs.findIndex((s) => s.range && node && s.range.intersectsNode(node));
    if (i >= 0) { e.preventDefault(); seek(i); }
  }, true);

  function shortVoice(v) {
    v = v || "default";
    const parts = v.split("-");
    return parts.length >= 3 ? parts[2].replace(/(Multilingual)?Neural$/, "") : v.slice(0, 20);
  }

  // ------------------------------------------------------------------ UI (shadow DOM so pages can't restyle it)
  const ui = (() => {
    let host, root, labelEl, playBtn;
    function build() {
      host = document.createElement("div");
      host.className = "sema-host";
      root = host.attachShadow({ mode: "closed" });
      root.innerHTML = `
        <style>
          .bar{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:2147483647;display:flex;
            align-items:center;gap:4px;padding:8px 12px;border-radius:999px;background:#14161c;color:#f2f3f5;
            font:13px/1.2 "Segoe UI",system-ui,sans-serif;box-shadow:0 8px 30px rgba(0,0,0,.35)}
          button{all:unset;cursor:pointer;min-width:30px;height:30px;display:grid;place-items:center;border-radius:50%;font-size:15px}
          button:hover{background:#2a2e3a} button:focus-visible{outline:2px solid #7c8cff}
          .play{background:#7c8cff;color:#fff} .play:hover{background:#6676ff}
          .label{color:#9aa0ab;padding:0 8px;max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
          .brand{color:#7c8cff;font-weight:600;padding-right:4px}
        </style>
        <div class="bar" role="toolbar" aria-label="Sema reader">
          <span class="brand">Sema</span>
          <button data-a="prev" title="Previous sentence (←)">⏮</button>
          <button data-a="play" class="play" title="Pause / resume">⏸</button>
          <button data-a="next" title="Next sentence">⏭</button>
          <button data-a="slower" title="Slower">−</button>
          <button data-a="faster" title="Faster">+</button>
          <span class="label"></span>
          <button data-a="stop" title="Stop">✕</button>
        </div>`;
      labelEl = root.querySelector(".label");
      playBtn = root.querySelector(".play");
      root.querySelector(".bar").addEventListener("click", (e) => {
        const a = e.target.closest("button")?.dataset.a;
        ({ prev: () => jump(-1), next: () => jump(1), play: toggle, stop: () => { stop(); hide(); },
          slower: () => setRate(-0.1), faster: () => setRate(0.1) })[a]?.();
      });
      document.documentElement.appendChild(host);
    }
    function show() { if (!host) build(); host.style.display = ""; }
    function hide() { if (host) host.style.display = "none"; }
    function update() {
      if (!host) return;
      playBtn.textContent = state.playing && !state.paused ? "⏸" : "▶";
      if (!state.playing) setTimeout(() => { if (!state.playing) hide(); }, 2500);
    }
    function label(t) { if (labelEl) labelEl.textContent = t; }
    return { show, hide, update, label };
  })();

  // floating "play" bubble next to a fresh selection
  const bubble = (() => {
    const host = document.createElement("div");
    host.className = "sema-host";
    const root = host.attachShadow({ mode: "closed" });
    root.innerHTML = `<style>
      b{all:unset;position:fixed;z-index:2147483647;width:30px;height:30px;border-radius:50%;background:#7c8cff;
        color:#fff;display:grid;place-items:center;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.3);font:14px system-ui}
      b:hover{background:#6676ff}</style><b title="Read with Sema" role="button" aria-label="Read selection with Sema">▶</b>`;
    const b = root.querySelector("b");
    host.style.display = "none";
    b.addEventListener("mousedown", (e) => { e.preventDefault(); e.stopPropagation(); });
    b.addEventListener("click", (e) => { e.stopPropagation(); host.style.display = "none"; start(selectionSegments()); });
    let enabled = true;
    chrome.storage.sync.get(["bubble"], (s) => { enabled = s.bubble !== false; });
    document.addEventListener("mouseup", (e) => {
      if (e.composedPath().includes(host)) return;
      setTimeout(() => {
        const sel = window.getSelection();
        if (!enabled || !sel || sel.isCollapsed || sel.toString().trim().length < 3) { host.style.display = "none"; return; }
        const r = sel.getRangeAt(0).getBoundingClientRect();
        b.style.left = Math.min(innerWidth - 40, r.right + 6) + "px";
        b.style.top = Math.max(6, r.top - 36) + "px";
        if (!host.isConnected) document.documentElement.appendChild(host);
        host.style.display = "";
      }, 10);
    });
    document.addEventListener("mousedown", (e) => { if (!e.composedPath().includes(host)) host.style.display = "none"; });
    return host;
  })();

  function toast(msg) {
    const t = document.createElement("div");
    t.className = "sema-host sema-toast";
    t.textContent = "Sema: " + msg;
    document.documentElement.appendChild(t);
    setTimeout(() => t.remove(), 4000);
  }

  document.addEventListener("keydown", (e) => {
    if (!state.playing || !e.altKey || !e.shiftKey) return;
    if (e.key === "ArrowRight") { jump(1); e.preventDefault(); }
    if (e.key === "ArrowLeft") { jump(-1); e.preventDefault(); }
  }, true);

  chrome.runtime.onMessage.addListener((msg, _s, reply) => {
    const cmd = msg.cmd;
    if (cmd === "read-selection") start(selectionSegments());
    else if (cmd === "read-page") start(pageSegments(null));
    else if (cmd === "read-here") start(pageSegments(lastContextTarget));
    else if (cmd === "read-auto") start(selectionSegments() || pageSegments(null));
    else if (cmd === "toggle") state.playing ? toggle() : start(selectionSegments() || pageSegments(null));
    else if (cmd === "stop") stop();
    reply({ ok: true });
  });

  // exposed for tests
  window.__sema = { sentences, buildSegments, textNodes, mainRoot, pageSegments, lightNormalize };
})();
