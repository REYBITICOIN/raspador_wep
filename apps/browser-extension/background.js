const API = "http://127.0.0.1:8091";

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

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "TOCA_SAVE_SNAPSHOT") {
    api("/v1/extension/snapshots", message.payload)
      .then(snapshot => sendResponse({ok: true, snapshot}))
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
