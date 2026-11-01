import { CONFIG } from "./config.js";

document.getElementById("open-site").href = CONFIG.WEBSITE_ORIGIN;

document.getElementById("select-region").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "START_REGION_SELECT" });
  window.close();
});
