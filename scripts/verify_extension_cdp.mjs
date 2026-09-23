const targets = await (await fetch("http://127.0.0.1:9229/json")).json();
const page = targets.find(item => item.type === "page" && item.url.includes("mercadolivre.com.br"));
if (!page) throw new Error("Página do Mercado Livre não encontrada");
const socket = new WebSocket(page.webSocketDebuggerUrl);
let sequence = 0;
const pending = new Map();
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++sequence;
  const timer = setTimeout(() => reject(new Error(`${method} timeout`)), 15000);
  pending.set(id, value => { clearTimeout(timer); resolve(value); });
  socket.send(JSON.stringify({id, method, params}));
});
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
  }
});
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, {once: true});
  socket.addEventListener("error", reject, {once: true});
});
const inspect = async () => {
  const response = await send("Runtime.evaluate", {
    expression: `(() => {
      const panel = document.querySelector("#toca-commerce-ray-x");
      return {panel_found: Boolean(panel), panel_text: panel?.innerText?.slice(0, 1200) || "", title: document.title, url: location.href};
    })()`,
    returnByValue: true
  });
  return response.result.result.value;
};
let result = await inspect();
if (!result.panel_found) {
  await send("Page.reload", {ignoreCache: true});
  await new Promise(resolve => setTimeout(resolve, 6000));
  result = await inspect();
}
console.log(JSON.stringify({ok: true, ...result}, null, 2));
socket.close();
