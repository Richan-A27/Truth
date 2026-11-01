(() => {
  if (window.__truthLoaded) return;
  window.__truthLoaded = true;

  const PALETTE = {
    bg: "rgb(250 250 248)",
    surface: "rgb(255 255 255)",
    ink: "rgb(26 26 24)",
    inkMuted: "rgb(92 92 87)",
    accent: "rgb(166 43 63)",
    border: "rgb(226 225 220)",
    success: "rgb(63 122 82)",
    danger: "rgb(139 30 30)",
  };

  const cards = new Map();

  function verdictColor(label) {
    const normalized = (label || "").toLowerCase();
    if (normalized.includes("support") || normalized.includes("true") || normalized.includes("entail")) {
      return PALETTE.success;
    }
    if (normalized.includes("contradict") || normalized.includes("false")) {
      return PALETTE.danger;
    }
    return PALETTE.inkMuted;
  }

  const CARD_WIDTH = 320;
  const VIEWPORT_MARGIN = 8;

  // Builds an element from trusted structure + untrusted text. Everything
  // that comes from the API (explanation, verdict label, error messages) is
  // set via textContent, never innerHTML: the explanation is LLM-written
  // from web evidence, so it can contain markup, and these cards render
  // inside whatever page the user is on.
  function el(tag, { className, style, text, attrs } = {}, children = []) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (style) node.style.cssText = style;
    if (text !== undefined) node.textContent = text;
    for (const [name, value] of Object.entries(attrs || {})) node.setAttribute(name, value);
    for (const child of children) node.appendChild(child);
    return node;
  }

  function createCard(requestId, anchorRect) {
    const host = document.createElement("div");
    host.style.cssText = "position: fixed; z-index: 2147483647; left: 0; top: 0;";
    const shadow = host.attachShadow({ mode: "open" });
    document.body.appendChild(host);
    cards.set(requestId, { host, shadow, anchorRect });
    renderLoading(requestId);
    return { host, shadow };
  }

  // Below the selection by default; above it when there's no room below.
  // Clamped so the card never runs off either edge of the viewport.
  function positionCard(entry) {
    const { host, anchorRect } = entry;
    const width = Math.min(CARD_WIDTH, window.innerWidth - VIEWPORT_MARGIN * 2);
    const height = host.getBoundingClientRect().height;
    const left = Math.max(VIEWPORT_MARGIN, Math.min(anchorRect.left, window.innerWidth - width - VIEWPORT_MARGIN));
    let top = anchorRect.bottom + 8;
    if (top + height > window.innerHeight - VIEWPORT_MARGIN) {
      const above = (anchorRect.top ?? anchorRect.bottom) - height - 8;
      top = above >= VIEWPORT_MARGIN ? above : Math.max(VIEWPORT_MARGIN, window.innerHeight - height - VIEWPORT_MARGIN);
    }
    host.style.left = `${left}px`;
    host.style.top = `${top}px`;
  }

  function baseStyles() {
    return `
      .card {
        box-sizing: border-box;
        width: min(${CARD_WIDTH}px, calc(100vw - ${VIEWPORT_MARGIN * 2}px));
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: ${PALETTE.surface};
        color: ${PALETTE.ink};
        border: 1px solid ${PALETTE.border};
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 8px 40px rgba(26, 26, 24, 0.18);
        font-size: 13px;
        line-height: 1.5;
      }
      .row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
      .close {
        background: none; border: none; cursor: pointer; color: ${PALETTE.inkMuted};
        font-size: 16px; line-height: 1; padding: 2px 4px;
      }
      .score { font-size: 22px; font-weight: 700; }
      .badge {
        display: inline-block; text-transform: capitalize; font-weight: 600;
        font-size: 11px; padding: 2px 8px; border-radius: 999px; margin-top: 6px;
      }
      .explanation { margin-top: 8px; color: ${PALETTE.inkMuted}; }
      .link {
        display: inline-block; margin-top: 10px; color: ${PALETTE.accent};
        text-decoration: none; font-weight: 600; font-size: 12px;
      }
      .muted { color: ${PALETTE.inkMuted}; }
      .pulse {
        width: 10px; height: 10px; border-radius: 999px; background: ${PALETTE.accent};
        animation: truth-pulse 1s ease-in-out infinite;
      }
      @keyframes truth-pulse { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
    `;
  }

  function closeCard(requestId) {
    const entry = cards.get(requestId);
    if (!entry) return;
    entry.host.remove();
    cards.delete(requestId);
  }

  // Replaces the card's contents - a header row (headerContent + close
  // button) and optional nodes below it - then re-positions it for its new
  // height.
  function render(requestId, headerContent, extra = []) {
    const entry = cards.get(requestId);
    if (!entry) return;
    const close = el("button", { className: "close", text: "\u00d7", attrs: { "aria-label": "Close" } });
    close.addEventListener("click", () => closeCard(requestId));
    entry.shadow.replaceChildren(
      el("style", { text: baseStyles() }),
      el("div", { className: "card" }, [el("div", { className: "row" }, [headerContent, close]), ...extra])
    );
    positionCard(entry);
  }

  function renderLoading(requestId) {
    render(
      requestId,
      el("div", { className: "row", style: "gap:8px;" }, [el("span", { className: "pulse" }), el("span", { text: "Verifying…" })])
    );
  }

  const RUN_ID_PATTERN = /^[0-9a-f-]{36}$/i;

  function renderResult(requestId, result, websiteOrigin) {
    const color = verdictColor(result.verdict_label);
    const explanation = String(result.explanation || "");
    const extra = [
      el("span", {
        className: "badge",
        style: `background: color-mix(in srgb, ${color} 10%, transparent); color: ${color};`,
        text: String(result.verdict_label || "").replace(/_/g, " "),
      }),
      el("div", {
        className: "explanation",
        text: explanation.length > 220 ? `${explanation.slice(0, 220)}…` : explanation,
      }),
    ];
    const runId = String(result.run_id || "");
    if (RUN_ID_PATTERN.test(runId)) {
      extra.push(
        el("a", {
          className: "link",
          text: "View full report →",
          attrs: { href: `${websiteOrigin}/result/${runId}`, target: "_blank", rel: "noopener noreferrer" },
        })
      );
    }
    render(requestId, el("div", { className: "score", style: `color:${color}`, text: String(Math.round(Number(result.trust_score) || 0)) }), extra);
  }

  function renderError(requestId, message) {
    render(requestId, el("span", { className: "muted", text: String(message || "Something went wrong.") }));
  }

  function selectionAnchorRect() {
    const selection = window.getSelection();
    if (selection && selection.rangeCount > 0) {
      const rect = selection.getRangeAt(0).getBoundingClientRect();
      if (rect.width || rect.height) return rect;
    }
    return { left: window.innerWidth / 2 - 160, bottom: window.innerHeight / 2 };
  }

  // --- Region-select overlay -------------------------------------------

  function startRegionSelect() {
    const overlay = document.createElement("div");
    overlay.style.cssText = `
      position: fixed; inset: 0; z-index: 2147483646;
      background: rgba(26, 26, 24, 0.15); cursor: crosshair;
    `;
    const box = document.createElement("div");
    box.style.cssText = `
      position: fixed; border: 2px dashed ${PALETTE.accent};
      background: rgba(166, 43, 63, 0.1); display: none; z-index: 2147483647;
    `;
    document.body.appendChild(overlay);
    document.body.appendChild(box);

    let start = null;

    function onKeyDown(e) {
      if (e.key === "Escape") cleanup();
    }

    function onMouseDown(e) {
      start = { x: e.clientX, y: e.clientY };
      box.style.left = `${start.x}px`;
      box.style.top = `${start.y}px`;
      box.style.width = "0px";
      box.style.height = "0px";
      box.style.display = "block";
    }

    function onMouseMove(e) {
      if (!start) return;
      const x = Math.min(start.x, e.clientX);
      const y = Math.min(start.y, e.clientY);
      const w = Math.abs(e.clientX - start.x);
      const h = Math.abs(e.clientY - start.y);
      box.style.left = `${x}px`;
      box.style.top = `${y}px`;
      box.style.width = `${w}px`;
      box.style.height = `${h}px`;
    }

    function onMouseUp(e) {
      if (!start) return;
      const rect = {
        x: Math.min(start.x, e.clientX),
        y: Math.min(start.y, e.clientY),
        width: Math.abs(e.clientX - start.x),
        height: Math.abs(e.clientY - start.y),
      };
      start = null; // guards against the capture+bubble fallback both firing
      cleanup();

      if (rect.width < 10 || rect.height < 10) return;

      const requestId = crypto.randomUUID();
      createCard(requestId, { left: rect.x, top: rect.y, bottom: rect.y + rect.height });
      chrome.runtime.sendMessage({
        type: "REGION_CAPTURED",
        requestId,
        rect,
        dpr: window.devicePixelRatio || 1,
      });
    }

    function cleanup() {
      overlay.remove();
      box.remove();
      document.removeEventListener("keydown", onKeyDown, true);
      document.removeEventListener("mouseup", onMouseUp, true);
      window.removeEventListener("blur", cleanup);
    }

    overlay.addEventListener("mousedown", onMouseDown);
    overlay.addEventListener("mousemove", onMouseMove);
    overlay.addEventListener("mouseup", onMouseUp);
    // Capture-phase fallbacks on document: on some pages a script upstream of
    // the overlay stops event propagation, which would otherwise leave the
    // overlay stuck forever with no way to finish or cancel the selection.
    document.addEventListener("mouseup", onMouseUp, true);
    document.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("blur", cleanup);
  }

  // --- Message handling ---------------------------------------------------

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type === "PING") {
      sendResponse({ pong: true });
      return;
    }
    if (message.type === "SHOW_LOADING") {
      createCard(message.requestId, selectionAnchorRect());
      return;
    }
    if (message.type === "SHOW_RESULT") {
      if (!cards.has(message.requestId)) createCard(message.requestId, selectionAnchorRect());
      renderResult(message.requestId, message.result, message.websiteOrigin);
      return;
    }
    if (message.type === "SHOW_ERROR") {
      if (!cards.has(message.requestId)) createCard(message.requestId, selectionAnchorRect());
      renderError(message.requestId, message.message);
      return;
    }
    if (message.type === "START_REGION_SELECT") {
      startRegionSelect();
      return;
    }
  });
})();
