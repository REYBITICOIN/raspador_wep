const status = document.querySelector("#status");
document.querySelector("#inspect").addEventListener("click", async () => {
  status.textContent = "Analisando...";
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  if (!tab?.id) return;
  chrome.tabs.sendMessage(tab.id, {type: "TOCA_INSPECT"}, response => {
    if (chrome.runtime.lastError) {
      status.textContent = "Página não compatível ou recarregue a guia.";
      return;
    }
    status.textContent = response?.ok ? "Painel aberto na página." : "Não foi possível analisar.";
  });
});
