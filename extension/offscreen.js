/* global Tesseract */

let workerPromise = null;

function getWorker() {
  if (!workerPromise) {
    workerPromise = Tesseract.createWorker("eng", 1, {
      workerPath: chrome.runtime.getURL("lib/worker.min.js"),
      corePath: chrome.runtime.getURL("lib/tesseract-core-simd-lstm.js"),
      langPath: chrome.runtime.getURL("lib/tessdata/"),
      workerBlobURL: false,
      gzip: true,
    });
  }
  return workerPromise;
}

function loadImage(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Couldn't load the captured screenshot."));
    img.src = dataUrl;
  });
}

async function cropImage(dataUrl, rect, dpr) {
  const img = await loadImage(dataUrl);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(rect.width * dpr));
  canvas.height = Math.max(1, Math.round(rect.height * dpr));
  const ctx = canvas.getContext("2d");
  ctx.drawImage(
    img,
    rect.x * dpr,
    rect.y * dpr,
    rect.width * dpr,
    rect.height * dpr,
    0,
    0,
    canvas.width,
    canvas.height
  );
  return canvas;
}

chrome.runtime.onMessage.addListener((message) => {
  if (message.type !== "OCR_REGION") return;

  (async () => {
    try {
      const canvas = await cropImage(message.imageDataUrl, message.rect, message.dpr);
      const worker = await getWorker();
      const {
        data: { text },
      } = await worker.recognize(canvas);
      chrome.runtime.sendMessage({ type: "OCR_RESULT", requestId: message.requestId, text });
    } catch (err) {
      chrome.runtime.sendMessage({
        type: "OCR_ERROR",
        requestId: message.requestId,
        message: err instanceof Error ? err.message : "OCR failed.",
      });
    }
  })();
});
