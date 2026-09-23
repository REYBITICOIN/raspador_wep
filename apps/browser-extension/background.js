const API = "http://127.0.0.1:8091";
const CONTENT_SCRIPT_ID = "toca-commerce-ray-x";
const CONTENT_MATCHES = [
  "https://*.mercadolivre.com.br/*",
  "https://*.mercadolibre.com/*",
  "https://*.shopee.com.br/*",
  "https://*.amazon.com.br/*"
];

async function ensureContentScript() {
  const existing = await chrome.scripting.getRegisteredContentScripts({ids: [CONTENT_SCRIPT_ID]});
  if (existing.length) return;
  await chrome.scripting.registerContentScripts([{
    id: CONTENT_SCRIPT_ID,
    matches: CONTENT_MATCHES,
    js: ["content.js"],
    css: ["styles.css"],
    runAt: "document_idle",
    persistAcrossSessions: true
  }]);
}

ensureContentScript().catch(error => console.error("Falha ao registrar Raio-X:", error));

async function api(path, payload) {
  const response = await fetch(API + path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Backend indisponível");
  return body;
}

async function apiGet(path) {
  const response = await fetch(API + path);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Backend indisponível");
  return body;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "TOCA_SAVE_SNAPSHOT") {
    api("/v1/extension/snapshots", message.payload)
      .then(snapshot => sendResponse({ok: true, snapshot}))
      .catch(error => sendResponse({ok: false, error: error.message}));
    return true;
  }
  if (message?.type === "TOCA_SAVE_SEARCH_SNAPSHOT") {
    api("/v1/extension/search-snapshots", message.payload)
      .then(snapshot => sendResponse({ok: true, snapshot}))
      .catch(error => sendResponse({ok: false, error: error.message}));
    return true;
  }
  if (message?.type === "TOCA_GET_SEARCH_HISTORY") {
    apiGet("/v1/extension/search-history?query=" + encodeURIComponent(message.query || ""))
      .then(history => sendResponse({ok: true, history}))
      .catch(error => sendResponse({ok: false, error: error.message}));
    return true;
  }
  if (message?.type === "TOCA_GET_SEARCH_INTELLIGENCE") {
    apiGet("/v1/extension/search-intelligence?query=" + encodeURIComponent(message.query || ""))
      .then(intelligence => sendResponse({ok: true, intelligence}))
      .catch(error => sendResponse({ok: false, error: error.message}));
    return true;
  }
  if (message?.type === "TOCA_QUOTE_ML_FEES") {
    api("/v1/margins/mercadolivre/quote", message.payload)
      .then(quote => sendResponse({ok: true, quote}))
      .catch(error => sendResponse({ok: false, error: error.message}));
    return true;
  }
  if (message?.type === "TOCA_CALCULATE_MARGIN") {
    api("/v1/margins/calculate", message.payload)
      .then(result => sendResponse({ok: true, result}))
      .catch(error => sendResponse({ok: false, error: error.message}));
    return true;
  }
});
