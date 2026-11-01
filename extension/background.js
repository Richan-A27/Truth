import { CONFIG } from "./config.js";

const MENU_ID = "truth-verify-selection";
const PENDING_OCR_KEY = "pendingOcr";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: MENU_ID,
    title: "Verify with Truth",
    contexts: ["selection"],
  });
});

async function ensureContentScript(tabId) {
  try {
    await chrome.tabs.sendMessage(tabId, { type: "PING" });
  } catch {
    await chrome.scripting.executeScript({ target: { tabId }, files: ["content-script.js"] });
  }
}

// Matches the backend's minimum (app/pipeline/stage1_input.py) so a too-short
// selection gets a clear message instead of a server error.
const MIN_CONTENT_CHARS = 10;

// FastAPI returns `detail` as a string for raised errors but as a list of
// {msg, ...} objects for request validation errors.
function describeError(data) {
  const detail = data && data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => (d && d.msg) || "").filter(Boolean).join("; ");
  }
  return "The verification service rejected this request.";
}

async function verifyText(text) {
  const content = text.trim();
  if (content.length < MIN_CONTENT_CHARS) {
    throw new Error("Select a little more text — at least a short sentence.");
  }
  let res;
  try {
    res = await fetch(`${CONFIG.API_BASE_URL}/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
  } catch {
    throw new Error("Couldn't reach the verification service — is the backend running?");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(describeError(data));
  }
  return data;
}

async function handleVerifyRequest(tabId, requestId, text) {
  try {
    const result = await verifyText(text);
    chrome.tabs.sendMessage(tabId, {
      type: "SHOW_RESULT",
      requestId,
      result,
      websiteOrigin: CONFIG.WEBSITE_ORIGIN,
    });
  } catch (err) {
    chrome.tabs.sendMessage(tabId, {
      type: "SHOW_ERROR",
      requestId,
      message: err instanceof Error ? err.message : "Couldn't reach the verification service.",
    });
  }
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== MENU_ID || !tab?.id || !info.selectionText) return;

  const requestId = crypto.randomUUID();
  try {
    await ensureContentScript(tab.id);
    await chrome.tabs.sendMessage(tab.id, { type: "SHOW_LOADING", requestId });
    handleVerifyRequest(tab.id, requestId, info.selectionText);
  } catch (err) {
    console.error("Truth: context-menu verify failed before reaching the page", err);
  }
});

async function ensureOffscreenDocument() {
  const has = await chrome.offscreen.hasDocument();
  if (has) return;
  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: ["DOM_PARSER"],
    justification: "Crop a captured screenshot and run OCR on it with Tesseract.js.",
  });
}

async function rememberPendingOcr(requestId, tabId) {
  const { [PENDING_OCR_KEY]: pending = {} } = await chrome.storage.session.get(PENDING_OCR_KEY);
  pending[requestId] = { tabId };
  await chrome.storage.session.set({ [PENDING_OCR_KEY]: pending });
}

async function takePendingOcr(requestId) {
  const { [PENDING_OCR_KEY]: pending = {} } = await chrome.storage.session.get(PENDING_OCR_KEY);
  const entry = pending[requestId];
  delete pending[requestId];
  await chrome.storage.session.set({ [PENDING_OCR_KEY]: pending });
  return entry;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "START_REGION_SELECT") {
    (async () => {
      try {
        const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!activeTab?.id) return;
        await ensureContentScript(activeTab.id);
        await chrome.tabs.sendMessage(activeTab.id, { type: "START_REGION_SELECT" });
      } catch (err) {
        console.error("Truth: couldn't start region select on this page", err);
      }
    })();
    return;
  }

  if (message.type === "REGION_CAPTURED" && sender.tab?.id) {
    const { requestId, rect, dpr } = message;
    const tabId = sender.tab.id;
    (async () => {
      try {
        await rememberPendingOcr(requestId, tabId);
        const imageDataUrl = await chrome.tabs.captureVisibleTab(sender.tab.windowId, {
          format: "png",
        });
        await ensureOffscreenDocument();
        chrome.runtime.sendMessage({ type: "OCR_REGION", requestId, imageDataUrl, rect, dpr });
      } catch (err) {
        console.error("Truth: region capture/OCR setup failed", err);
        await takePendingOcr(requestId);
        chrome.tabs.sendMessage(tabId, {
          type: "SHOW_ERROR",
          requestId,
          message: err instanceof Error ? err.message : "Couldn't capture that region.",
        });
      }
    })();
    return;
  }

  if (message.type === "OCR_RESULT" || message.type === "OCR_ERROR") {
    (async () => {
      const entry = await takePendingOcr(message.requestId);
      if (!entry) return;

      if (message.type === "OCR_ERROR") {
        chrome.tabs.sendMessage(entry.tabId, {
          type: "SHOW_ERROR",
          requestId: message.requestId,
          message: message.message,
        });
        return;
      }

      const text = (message.text || "").trim();
      if (text.length < 3) {
        chrome.tabs.sendMessage(entry.tabId, {
          type: "SHOW_ERROR",
          requestId: message.requestId,
          message: "Couldn't read any text in that region — try a wider or clearer selection.",
        });
        return;
      }

      handleVerifyRequest(entry.tabId, message.requestId, text);
    })();
    return;
  }

  sendResponse();
});
