const targets = await (await fetch("http://127.0.0.1:9229/json")).json();
const page = targets.find(item => item.type === "page" && item.url === "chrome://extensions/");
if (!page) throw new Error("Página de extensões não encontrada");
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, {once: true});
  socket.addEventListener("error", reject, {once: true});
});
let sequence = 0;
const pending = new Map();
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
  }
});
const send = (method, params={}) => new Promise(resolve => {
  const id = ++sequence;
  pending.set(id, resolve);
  socket.send(JSON.stringify({id, method, params}));
});
let locate = await send("Runtime.evaluate", {expression: `(() => {
  const root = document.querySelector("extensions-manager")?.shadowRoot
    ?.querySelector("extensions-toolbar")?.shadowRoot;
  const toggle = root?.querySelector("#devMode");
  if (toggle && !toggle.checked) toggle.click();
  const button = root?.querySelector("#loadUnpacked");
  if (!button) return {ok:false};
  const box = button.getBoundingClientRect();
  return {ok:true, x:box.left + box.width/2, y:box.top + box.height/2, toggleChecked:toggle.checked, toggleDisabled:toggle.disabled, loadDisabled:button.disabled};
})()`, returnByValue:true});
const point = locate.result.result.value;
if (!point?.ok) throw new Error("Botão Carregar sem compactação não encontrado");
await send("Input.dispatchMouseEvent", {type:"mouseMoved", x:point.x, y:point.y});
await send("Input.dispatchMouseEvent", {type:"mousePressed", x:point.x, y:point.y, button:"left", clickCount:1});
await send("Input.dispatchMouseEvent", {type:"mouseReleased", x:point.x, y:point.y, button:"left", clickCount:1});
console.log(JSON.stringify({ok:true, trusted_click:true, ...point}));
socket.close();
