const targets = await (await fetch("http://127.0.0.1:9229/json")).json();
let page = targets.find(item => item.type === "page" && item.url === "chrome://extensions/");
if (!page) {
  page = await (await fetch("http://127.0.0.1:9229/json/new?chrome://extensions/", {method:"PUT"})).json();
}
const ws = new WebSocket(page.webSocketDebuggerUrl);
let sequence = 0;
const pending = new Map();
ws.onmessage = event => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
  }
};
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
const send = (method, params = {}) => new Promise(resolve => {
  const id = ++sequence; pending.set(id, resolve);
  ws.send(JSON.stringify({id, method, params}));
});
await new Promise(resolve => setTimeout(resolve, 1500));
const result = await send("Runtime.evaluate", {expression:`(() => {
  const manager = document.querySelector("extensions-manager")?.shadowRoot;
  const list = manager?.querySelector("extensions-item-list")?.shadowRoot;
  const items = [...(list?.querySelectorAll("extensions-item") || [])];
  const target = items.find(item => item.shadowRoot?.querySelector("#name")?.textContent?.includes("Toca Commerce Intelligence"));
  const button = target?.shadowRoot?.querySelector("#dev-reload-button");
  if (button) button.click();
  return {reloaded:Boolean(button), extension_id:target?.id || null};
})()`, returnByValue:true});
console.log(JSON.stringify(result.result.result.value, null, 2));
ws.close();