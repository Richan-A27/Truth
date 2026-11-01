# Truth browser extension

Right-click any selected text on the web to verify it, or select a screenshot region to OCR and verify. Chrome/Edge/Brave (Manifest V3), no build step.

## Load it (development)

1. Make sure the backend is running at `http://127.0.0.1:8000` (`uvicorn app.main:app --reload` from the repo root) — the backend's CORS is already configured to allow requests from `chrome-extension://` origins.
2. Open `chrome://extensions`.
3. Turn on **Developer mode** (top right).
4. Click **Load unpacked** and select this `extension/` folder.
5. Pin the "Truth — Verify with Truth" icon to the toolbar if you'd like quick access to the popup.

## Using it

- **Select text on any page → right-click → "Verify with Truth"**. A card appears near the selection with the trust score, verdict, and a link to the full report.
- **Click the toolbar icon → "Select region to verify"**. The page dims; drag a rectangle over any text (including text inside an image or a screenshot-only area). The region is OCR'd locally (Tesseract.js, no server calls for OCR) and the extracted text is verified the same way.

## Before shipping beyond your own machine

- Edit `config.js`: point `API_BASE_URL` at your deployed backend and `WEBSITE_ORIGIN` at your deployed site.
- Edit `manifest.json`'s `host_permissions` to match the deployed backend's origin.
- The extension does not have its own sign-in — results aren't saved to your Truth history from here (only from the website). That's a deliberate v1 limitation.
