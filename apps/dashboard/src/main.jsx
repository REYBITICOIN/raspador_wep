import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8080";

function App() {
  const [providers, setProviders] = useState([]);
  const [url, setUrl] = useState("");
  const [instruction, setInstruction] = useState("Extraia título, preço, imagens e disponibilidade");
  const [provider, setProvider] = useState("auto");
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetch(`${API}/v1/providers`).then(r => r.json()).then(d => setProviders(d.providers || [])).catch(() => setProviders([]));
  }, []);

  async function submit(e) {
    e.preventDefault();
    const response = await fetch(`${API}/v1/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, instruction, provider })
    });
    setResult(await response.json());
  }

  return <main>
    <aside>
      <div className="mark">WI</div>
      <nav><span className="active">Visão orbital</span><span>Fontes</span><span>Laboratório</span><span>Extrações</span><span>Produtos</span><span>Banco & auditoria</span></nav>
      <small>AMBIENTE ISOLADO · v0.1</small>
    </aside>
    <section className="shell">
      <header><div><p className="eyebrow">TOCA DA ONÇA · INTELLIGENCE CORE</p><h1>Web Intelligence Lab</h1></div><div className="pulse">● SISTEMA ONLINE</div></header>
      <div className="grid stats">
        <article><label>COLETAS HOJE</label><strong>0</strong><em>aguardando primeiro teste</em></article>
        <article><label>EXTRAÇÕES</label><strong>0</strong><em>JSON estruturado</em></article>
        <article><label>PROVEDORES</label><strong>{providers.filter(p => p.configured).length}/2</strong><em>NVIDIA + Grok</em></article>
      </div>
      <div className="grid body">
        <article className="lab"><p className="eyebrow">NOVA MISSÃO</p><h2>Laboratório de extração</h2><form onSubmit={submit}>
          <label>URL pública autorizada<input type="url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://fornecedor.com/produto" required /></label>
          <label>O que deseja extrair?<textarea value={instruction} onChange={e => setInstruction(e.target.value)} /></label>
          <label>Rota de inteligência<select value={provider} onChange={e => setProvider(e.target.value)}><option value="auto">Automática</option><option value="nvidia">NVIDIA</option><option value="grok">Grok (pago/bloqueado)</option></select></label>
          <button>INICIAR COLETA</button>
        </form>{result && <pre>{JSON.stringify(result, null, 2)}</pre>}</article>
        <article><p className="eyebrow">MODEL ROUTER</p><h2>Conexões de IA</h2>{["nvidia", "grok"].map(id => { const p=providers.find(x=>x.id===id); return <div className="provider" key={id}><b>{id.toUpperCase()}</b><span className={p?.configured ? "ok" : "off"}>{p?.configured ? "CONFIGURADA" : "SEM CHAVE"}</span><small>{id === "grok" ? "Uso pago exige liberação" : "Rota principal"}</small></div>})}<p className="notice">As chaves são inseridas no servidor. Elas nunca aparecem no navegador ou no banco.</p></article>
      </div>
    </section>
  </main>;
}

createRoot(document.getElementById("root")).render(<App />);

