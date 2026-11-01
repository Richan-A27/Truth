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

  function createCard(requestId, anchorRect) {
    const host = document.createElement("div");
    host.style.cssText = `
      position: fixed;
      z-index: 2147483647;
      left: ${Math.max(8, Math.min(anchorRect.left, window.innerWidth - 328))}px;
      top: ${anchorRect.bottom + 8}px;
    `;
    const shadow = host.attachShadow({ mode: "open" });
    document.body.appendChild(host);
    cards.set(requestId, { host, shadow });
    renderLoading(requestId);
    return { host, shadow };
  }

  function baseStyles() {
    return `
      .card {
        width: 320px;
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

  function renderLoading(requestId) {
    const entry = cards.get(requestId);
    if (!entry) return;
    entry.shadow.innerHTML = `
      <style>${baseStyles()}</style>
      <div class="card">
        <div class="row">
          <div class="row" style="gap:8px;"><span class="pulse"></span><span>Verifying…</span></div>
          <button class="close" data-close>&times;</button>
        </div>
      </div>
    `;
    entry.shadow.querySelector("[data-close]").addEventListener("click", () => closeCard(requestId));
  }

  function renderResult(requestId, result, websiteOrigin) {
    const entry = cards.get(requestId);
    if (!entry) return;
    const color = verdictColor(result.verdict_label);
    const explanation =
      result.explanation.length > 220 ? `${result.explanation.slice(0, 220)}…` : result.explanation;

    entry.shadow.innerHTML = `
      <style>${baseStyles()}</style>
      <div class="card">
        <div class="row">
          <div class="score" style="color:${color}">${Math.round(result.trust_score)}</div>
          <button class="close" data-close>&times;</button>
        </div>
        <span class="badge" style="background:${color}1a; color:${color};">
          ${(result.verdict_label || "").replace(/_/g, " ")}
        </span>
        <div class="explanation">${explanation}</div>
        <a class="link" href="${websiteOrigin}/result/${result.run_id}" target="_blank" rel="noopener noreferrer">
          View full report →
        </a>
      </div>
    `;
    entry.shadow.querySelector("[data-close]").addEventListener("click", () => closeCard(requestId));
  }

  function renderError(requestId, message) {
    const entry = cards.get(requestId);
    if (!entry) return;
    entry.shadow.innerHTML = `
      <style>${baseStyles()}</style>
      <div class="card">
        <div class="row">
          <span class="muted">${message}</span>
          <button class="close" data-close>&times;</button>
        </div>
      </div>
    `;
    entry.shadow.querySelector("[data-close]").addEventListener("click", () => closeCard(requestId));
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
      createCard(requestId, { left: rect.x, bottom: rect.y + rect.height });
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
