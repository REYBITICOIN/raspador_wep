const targets = await (await fetch("http://127.0.0.1:9229/json")).json();
const page = targets.find(item => item.type === "page" && item.url.includes("mercadolivre.com.br"));
if (!page) throw new Error("Página do Mercado Livre não encontrada");
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, {once:true});
  socket.addEventListener("error", reject, {once:true});
});
socket.send(JSON.stringify({id:1, method:"Runtime.evaluate", params:{
  expression:`(async () => {
    const button = document.querySelector("#toca-commerce-ray-x .toca-ray-save");
    if (!button) return {ok:false, error:"Botão salvar não encontrado"};
    button.click();
    await new Promise(resolve => setTimeout(resolve, 2500));
    return {ok:button.textContent.includes("✓"), text:button.textContent,
      history:document.querySelector(".toca-history")?.innerText?.slice(0,2000) || null};
  })()`,
  awaitPromise:true,
  returnByValue:true
}}));
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.id !== 1) return;
  console.log(JSON.stringify(message.result.result.value, null, 2));
  socket.close();
});
setTimeout(() => process.exit(1), 15000);
