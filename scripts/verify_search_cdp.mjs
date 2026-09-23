const targets = await (await fetch("http://127.0.0.1:9229/json")).json();
const page = targets.find(item => item.type === "page" && item.url.includes("lista.mercadolivre.com.br"));
if (!page) throw new Error("Página de pesquisa do Mercado Livre não encontrada");
const socket = new WebSocket(page.webSocketDebuggerUrl);
let sequence = 0;
const pending = new Map();
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++sequence;
  const timer = setTimeout(() => reject(new Error(`${method} timeout`)), 15000);
  pending.set(id, value => { clearTimeout(timer); resolve(value); });
  socket.send(JSON.stringify({id, method, params}));
});
socket.onmessage = event => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
  }
};
await new Promise((resolve, reject) => {
  socket.onopen = resolve;
  socket.onerror = reject;
});
const inspect = async () => {
  const response = await send("Runtime.evaluate", {
    expression: `(() => {
      const panel = document.querySelector("#toca-commerce-ray-x");
      return {panel_found: Boolean(panel), panel_text: panel?.innerText?.slice(0,4000) || "",
        product_cards: document.querySelectorAll(".toca-search-product").length,
        visible_cards: document.querySelectorAll(".ui-search-layout__item").length};
    })()`, returnByValue: true
  });
  return response.result.result.value;
};
await send("Page.reload", {ignoreCache: true});
await new Promise(resolve => setTimeout(resolve, 7000));
const result = await inspect();
console.log(JSON.stringify({ok: result.panel_found && result.product_cards > 0, ...result}, null, 2));
if (!result.panel_found || !result.product_cards) process.exitCode = 1;
socket.close();