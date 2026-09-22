const API = "http://127.0.0.1:8091";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "TOCA_SAVE_SNAPSHOT") return;
  fetch(API + "/v1/extension/snapshots", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(message.payload)
  })
    .then(async response => {
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "Backend indisponível");
      sendResponse({ok: true, snapshot: body});
    })
    .catch(error => sendResponse({ok: false, error: error.message}));
  return true;
});
