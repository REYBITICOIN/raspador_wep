import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8080";
const views = ["Comando", "Laboratório", "Histórico", "Provedores", "Banco & segurança"];

async function request(path, options) {
  const response = await fetch(API + path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Falha na comunicação com o backend");
  return data;
}

const Badge = ({ status }) => <span className={"badge " + status}>{status}</span>;

function App() {
  const [view, setView] = useState("Comando");
  const [health, setHealth] = useState(null);
  const [providers, setProviders] = useState([]);
  const [stats, setStats] = useState({ total_jobs: 0, completed: 0, failed: 0, pages: 0 });
  const [jobs, setJobs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [url, setUrl] = useState("");
  const [instruction, setInstruction] = useState("Extraia título, preço, imagens e disponibilidade");
  const [provider, setProvider] = useState("auto");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    const [h, p, s, j] = await Promise.all([
      request("/health"), request("/v1/providers"), request("/v1/stats"), request("/v1/jobs")
    ]);
    setHealth(h); setProviders(p.providers || []); setStats(s); setJobs(j);
  }

  useEffect(() => { refresh().catch(e => setError(e.message)); }, []);

  async function submit(e) {
    e.preventDefault(); setLoading(true); setError("");
    try {
      const job = await request("/v1/jobs", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, instruction, provider })
      });
      setSelected(job); await refresh(); setView("Histórico");
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }

  const cards = [
    ["MISSÕES", stats.total_jobs, "trabalhos registrados"],
    ["PÁGINAS", stats.pages, "coletas concluídas"],
    ["SUCESSO", stats.completed, stats.failed ? stats.failed + " falha(s)" : "sem falhas"],
    ["IA ONLINE", providers.filter(p => p.enabled).length, "de 2 provedores"]
  ];

  return <main>
    <aside>
      <div className="brand"><div className="mark">WI</div><div><b>WEB INTEL</b><small>RESEARCH GRID</small></div></div>
      <nav>{views.map(item => <button key={item} className={view === item ? "active" : ""} onClick={() => setView(item)}>{item}</button>)}</nav>
      <div className="core"><i className={health ? "live" : "dead"}/>{health ? "NÚCLEO " + health.version : "NÚCLEO DESCONECTADO"}</div>
    </aside>
    <section className="shell">
      <header><div><p className="eyebrow">TOCA DA ONÇA · WEB INTELLIGENCE</p><h1>{view}</h1><p>Laboratório privado de coleta e inteligência comercial.</p></div><span className={"system " + (health ? "online" : "offline")}>● {health ? "SISTEMA ONLINE" : "SEM CONEXÃO"}</span></header>
      {error && <div className="alert"><b>ATENÇÃO</b><span>{error}</span><button onClick={() => setError("")}>×</button></div>}

      {view === "Comando" && <>
        <div className="stats">{cards.map(([label, value, note]) => <article key={label}><label>{label}</label><strong>{value}</strong><em>{note}</em></article>)}</div>
        <div className="columns"><article className="hero"><p className="eyebrow">CENTRAL DE OPERAÇÕES</p><h2>Transforme páginas em inteligência estruturada.</h2><p>Cadastre uma fonte pública autorizada, colete a página e acompanhe cada evidência.</p><button onClick={() => setView("Laboratório")}>NOVA COLETA →</button></article>
        <article><p className="eyebrow">ATIVIDADE RECENTE</p>{jobs.slice(0,5).map(job => <div className="jobline" key={job.id} onClick={() => {setSelected(job);setView("Histórico")}}><div><b>{job.result?.title || new URL(job.url).hostname}</b><small>{new Date(job.created_at).toLocaleString("pt-BR")}</small></div><Badge status={job.status}/></div>)}{!jobs.length && <div className="empty">Nenhuma missão executada.</div>}</article></div>
      </>}

      {view === "Laboratório" && <div className="columns lab"><article><p className="eyebrow">NOVA MISSÃO</p><h2>Configurar coleta</h2><form onSubmit={submit}><label>URL pública autorizada<input type="url" value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://exemplo.com/produto" required/></label><label>Objetivo da extração<textarea value={instruction} onChange={e=>setInstruction(e.target.value)} minLength="5" required/></label><label>Rota de inteligência<select value={provider} onChange={e=>setProvider(e.target.value)}><option value="auto">Automática e econômica</option><option value="nvidia">NVIDIA</option><option value="grok">Grok — requer autorização</option></select></label><div className="guard">◈ URLs privadas são bloqueadas. CAPTCHA, login e proteções não serão contornados.</div><button disabled={loading}>{loading ? "COLETANDO..." : "INICIAR COLETA"}</button></form></article><article className="pipeline"><p className="eyebrow">PIPELINE</p>{["Validação de segurança","Captura real da página","Extração estruturada","Registro no banco","Auditoria e evidências"].map((x,i)=><div key={x}><span>{String(i+1).padStart(2,"0")}</span><b>{x}</b></div>)}</article></div>}

      {view === "Histórico" && <div className="columns history"><article><div className="title"><div><p className="eyebrow">MISSÕES</p><h2>Histórico de coletas</h2></div><button className="ghost" onClick={()=>refresh().catch(e=>setError(e.message))}>ATUALIZAR</button></div>{jobs.map(job=><div className={"jobrow "+(selected?.id===job.id?"selected":"")} key={job.id} onClick={()=>setSelected(job)}><div><b>{job.result?.title || new URL(job.url).hostname}</b><small>{job.url}</small></div><Badge status={job.status}/><time>{new Date(job.created_at).toLocaleDateString("pt-BR")}</time></div>)}{!jobs.length&&<div className="empty">Seu histórico aparecerá aqui.</div>}</article><article className="detail"><p className="eyebrow">EVIDÊNCIA</p>{selected?<><h2>{selected.result?.title||"Coleta sem título"}</h2><Badge status={selected.status}/>{selected.result?.blocked&&<div className="errorbox">A página bloqueou a coleta com verificação. Nenhum produto foi recebido.</div>}<dl><dt>URL</dt><dd>{selected.url}</dd><dt>Solicitado</dt><dd>{selected.provider}</dd><dt>Usado</dt><dd>{selected.result?.actual_provider||"—"}</dd><dt>HTTP</dt><dd>{selected.result?.http_status||"—"}</dd></dl>{selected.error&&<div className="errorbox">{selected.error}</div>}{selected.result?.extraction?.products?.length>0?<div className="products">{selected.result.extraction.products.map((product,i)=><div className="product" key={i}>{product.image_url&&<img src={product.image_url} alt=""/>}<div><b>{product.title}</b><strong>{product.price?new Intl.NumberFormat("pt-BR",{style:"currency",currency:product.currency||"BRL"}).format(product.price):"Preço não informado"}</strong><small>{product.seller||product.availability}</small></div></div>)}</div>:<p>{selected.result?.note}</p>}<pre>{JSON.stringify(selected.result?.extraction||selected.result,null,2)}</pre></>:<div className="empty">Selecione uma missão.</div>}</article></div>}

      {view === "Provedores" && <div className="columns providers"><article><p className="eyebrow">MODEL ROUTER</p><h2>Conexões de inteligência</h2><p>Uma API central seleciona o modelo, mas cada empresa usa sua própria chave.</p>{providers.map(p=><div className="provider" key={p.id}><div className={"logo "+p.id}>{p.id==="nvidia"?"N":"G"}</div><div><b>{p.id==="nvidia"?"NVIDIA NIM":"xAI · GROK"}</b><small>{p.model||"Modelo ainda não definido"}</small></div><span className={p.configured?"ok":"off"}>{p.configured?(p.enabled?"ATIVO":"BLOQUEADO"):"SEM CHAVE"}</span></div>)}</article><article><p className="eyebrow">COFRE DE SEGREDOS</p><h2>Configuração das APIs</h2><code>NVIDIA_API_KEY=••••••••</code><code>XAI_API_KEY=••••••••</code><p>As chaves ficam no servidor. O navegador recebe apenas o estado da conexão.</p><div className="guard">Grok permanece bloqueado enquanto <b>ALLOW_PAID_MODELS=false</b>.</div></article></div>}

      {view === "Banco & segurança" && <div className="columns security"><article><p className="eyebrow">SUPABASE</p><h2>PostgreSQL protegido</h2>{["Autenticação de usuários","RLS em todas as tabelas","Histórico e auditoria","Resultados e produtos","Métricas de modelos e custos"].map(x=><div className="check" key={x}>✓ <span>{x}</span></div>)}</article><article><p className="eyebrow">POLÍTICA DE DADOS</p><h2>Proteções ativas</h2><p>Nenhuma chave secreta chega ao navegador. Cada usuário acessa somente seus registros. Endereços internos são bloqueados pela API.</p><div className="shield"><b>RLS</b><small>DEFESA POR LINHA</small></div></article></div>}
    </section>
  </main>;
}

createRoot(document.getElementById("root")).render(<App/>);
