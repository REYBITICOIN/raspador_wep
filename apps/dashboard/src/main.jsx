import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, Bot, ChevronLeft, ChevronRight, Command, Database,
  FlaskConical, History, LayoutDashboard, Menu, Search, Package, Store,
  Settings, ShieldCheck, Send, X
} from "lucide-react";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8080";
const navGroups = [
  { label: "Operações", items: [
    ["Comando", LayoutDashboard], ["Laboratório", FlaskConical], ["Histórico", History]
  ]},
  { label: "Comércio", items: [
    ["Catálogo", Package], ["Canais", Store], ["Publicações", Send]
  ]},
  { label: "Inteligência", items: [
    ["Provedores", Bot], ["Banco & segurança", Database]
  ]}
];

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
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileNav, setMobileNav] = useState(false);
  const [commerce, setCommerce] = useState({ products: 0, publications: 0, channels: [] });
  const [catalog, setCatalog] = useState([]);
  const [importUrl, setImportUrl] = useState("");

  async function refresh() {
    const [h, p, s, j, c, products] = await Promise.all([
      request("/health"), request("/v1/providers"), request("/v1/stats"), request("/v1/jobs"),
      request("/v1/commerce/overview"), request("/v1/catalog/products")
    ]);
    setHealth(h); setProviders(p.providers || []); setStats(s); setJobs(j);
    setCommerce(c); setCatalog(products);
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

  async function importToCatalog(e) {
    e.preventDefault(); setLoading(true); setError("");
    try {
      await request("/v1/catalog/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: importUrl }) });
      setImportUrl(""); await refresh();
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }

  const cards = [
    ["PRODUTOS", commerce.products, "no catálogo central"],
    ["PUBLICAÇÕES", commerce.publications, "envios registrados"],
    ["CANAIS", commerce.channels.filter(c => c.state === "configured").length, "configurados"],
    ["COLETAS", stats.completed, stats.failed ? stats.failed + " falha(s)" : "sem falhas"]
  ];

  return <main className={sidebarOpen ? "sidebar-open" : "sidebar-closed"}>
    {mobileNav && <button className="nav-scrim" aria-label="Fechar menu" onClick={() => setMobileNav(false)} />}
    <aside className={mobileNav ? "mobile-open" : ""}>
      <div className="workspace">
        <div className="mark">WI</div>
        {sidebarOpen && <div className="workspace-copy"><b>WEB INTELLIGENCE</b><small>TOCA DA ONÇA · LAB</small></div>}
        <button className="mobile-close" onClick={() => setMobileNav(false)} aria-label="Fechar"><X size={18}/></button>
      </div>
      {sidebarOpen && <button className="quick-search"><Search size={16}/><span>Pesquisar</span><kbd>⌘K</kbd></button>}
      <nav>{navGroups.map(group => <div className="nav-group" key={group.label}>
        {sidebarOpen && <label>{group.label}</label>}
        {group.items.map(([item, Icon]) => <button title={item} key={item} className={view === item ? "active" : ""} onClick={() => {setView(item);setMobileNav(false)}}><Icon size={17}/>{sidebarOpen && <span>{item}</span>}</button>)}
      </div>)}</nav>
      <div className="aside-bottom">
        <button className="settings-row"><Settings size={17}/>{sidebarOpen && <span>Configurações</span>}</button>
        <div className="core"><i className={health ? "live" : "dead"}/>{sidebarOpen && (health ? "NÚCLEO " + health.version : "NÚCLEO DESCONECTADO")}</div>
      </div>
    </aside>
    <section className="shell">
      <div className="topbar">
        <div className="topbar-left"><button className="mobile-menu" onClick={() => setMobileNav(true)}><Menu size={19}/></button><button className="collapse" onClick={() => setSidebarOpen(v => !v)}>{sidebarOpen ? <ChevronLeft size={18}/> : <ChevronRight size={18}/>}</button><span>Web Intelligence</span><b>/</b><strong>{view}</strong></div>
        <div className="topbar-actions"><button><Search size={16}/><span>Pesquisar</span></button><div className={"avatar " + (health ? "online" : "offline")}>WI</div></div>
      </div>
      <div className="content">
      <header><div><p className="eyebrow">TOCA DA ONÇA · COMMERCE OS</p><h1>{view}</h1><p>Catálogo, canais, publicações e inteligência comercial em um só lugar.</p></div><span className={"system " + (health ? "online" : "offline")}>● {health ? "SISTEMA ONLINE" : "SEM CONEXÃO"}</span></header>
      {error && <div className="alert"><b>ATENÇÃO</b><span>{error}</span><button onClick={() => setError("")}>×</button></div>}

      {view === "Comando" && <>
        <div className="stats">{cards.map(([label, value, note]) => <article key={label}><label>{label}</label><strong>{value}</strong><em>{note}</em></article>)}</div>
        <div className="columns"><article className="hero"><p className="eyebrow">CENTRAL DE OPERAÇÕES</p><h2>Do seu catálogo para todos os canais.</h2><p>Importe produtos da Toca da Onça, prepare anúncios e sincronize os marketplaces.</p><button onClick={() => setView("Catálogo")}>ABRIR CATÁLOGO →</button></article>
        <article><p className="eyebrow">ATIVIDADE RECENTE</p>{jobs.slice(0,5).map(job => <div className="jobline" key={job.id} onClick={() => {setSelected(job);setView("Histórico")}}><div><b>{job.result?.title || new URL(job.url).hostname}</b><small>{new Date(job.created_at).toLocaleString("pt-BR")}</small></div><Badge status={job.status}/></div>)}{!jobs.length && <div className="empty">Nenhuma missão executada.</div>}</article></div>
      </>}

      {view === "Laboratório" && <div className="columns lab"><article><p className="eyebrow">NOVA MISSÃO</p><h2>Configurar coleta</h2><form onSubmit={submit}><label>URL pública autorizada<input type="url" value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://exemplo.com/produto" required/></label><label>Objetivo da extração<textarea value={instruction} onChange={e=>setInstruction(e.target.value)} minLength="5" required/></label><label>Rota de inteligência<select value={provider} onChange={e=>setProvider(e.target.value)}><option value="auto">Automática e econômica</option><option value="nvidia">NVIDIA</option><option value="grok">Grok — requer autorização</option></select></label><div className="guard">◈ URLs privadas são bloqueadas. CAPTCHA, login e proteções não serão contornados.</div><button disabled={loading}>{loading ? "COLETANDO..." : "INICIAR COLETA"}</button></form></article><article className="pipeline"><p className="eyebrow">PIPELINE</p>{["Validação de segurança","Captura real da página","Extração estruturada","Registro no banco","Auditoria e evidências"].map((x,i)=><div key={x}><span>{String(i+1).padStart(2,"0")}</span><b>{x}</b></div>)}</article></div>}

      {view === "Histórico" && <div className="columns history"><article><div className="title"><div><p className="eyebrow">MISSÕES</p><h2>Histórico de coletas</h2></div><button className="ghost" onClick={()=>refresh().catch(e=>setError(e.message))}>ATUALIZAR</button></div>{jobs.map(job=><div className={"jobrow "+(selected?.id===job.id?"selected":"")} key={job.id} onClick={()=>setSelected(job)}><div><b>{job.result?.title || new URL(job.url).hostname}</b><small>{job.url}</small></div><Badge status={job.status}/><time>{new Date(job.created_at).toLocaleDateString("pt-BR")}</time></div>)}{!jobs.length&&<div className="empty">Seu histórico aparecerá aqui.</div>}</article><article className="detail"><p className="eyebrow">EVIDÊNCIA</p>{selected?<><h2>{selected.result?.title||"Coleta sem título"}</h2><Badge status={selected.status}/>{selected.result?.blocked&&<div className="errorbox">A página bloqueou a coleta com verificação. Nenhum produto foi recebido.</div>}<dl><dt>URL</dt><dd>{selected.url}</dd><dt>Solicitado</dt><dd>{selected.provider}</dd><dt>Usado</dt><dd>{selected.result?.actual_provider||"—"}</dd><dt>HTTP</dt><dd>{selected.result?.http_status||"—"}</dd></dl>{selected.error&&<div className="errorbox">{selected.error}</div>}{selected.result?.extraction?.products?.length>0?<div className="products">{selected.result.extraction.products.map((product,i)=><div className="product" key={i}>{product.image_url&&<img src={product.image_url} alt=""/>}<div><b>{product.title}</b><strong>{product.price?new Intl.NumberFormat("pt-BR",{style:"currency",currency:product.currency||"BRL"}).format(product.price):"Preço não informado"}</strong><small>{product.seller||product.availability}</small></div></div>)}</div>:<p>{selected.result?.note}</p>}<pre>{JSON.stringify(selected.result?.extraction||selected.result,null,2)}</pre></>:<div className="empty">Selecione uma missão.</div>}</article></div>}

      {view === "Catálogo" && <div className="columns lab">
        <article><p className="eyebrow">CATÁLOGO CENTRAL</p><h2>Importar da Toca da Onça</h2>
          <form onSubmit={importToCatalog}><label>URL do produto<input type="url" value={importUrl} onChange={e=>setImportUrl(e.target.value)} placeholder="https://tocadaoncamodas.com.br/produto/..." required/></label><button disabled={loading}>{loading?"IMPORTANDO...":"IMPORTAR PRODUTO"}</button></form>
          <div className="guard">O produto entra primeiro no catálogo. Nada é publicado automaticamente.</div>
        </article>
        <article><p className="eyebrow">PRODUTOS</p><h2>{catalog.length} item(ns)</h2>
          {catalog.map(product=><div className="product" key={product.id}>{product.images?.[0]&&<img src={product.images[0]} alt=""/>}<div><b>{product.title}</b><strong>{new Intl.NumberFormat("pt-BR",{style:"currency",currency:product.currency||"BRL"}).format(product.price||0)}</strong><small>Estoque: {product.stock} · {product.sku||"sem SKU"}</small></div></div>)}
          {!catalog.length&&<div className="empty">Importe o primeiro produto da loja.</div>}
        </article>
      </div>}

      {view === "Canais" && <div className="columns providers"><article><p className="eyebrow">MARKETPLACES</p><h2>Conexões comerciais</h2>{commerce.channels.map(channel=><div className="provider" key={channel.id}><div className="logo">{channel.id.slice(0,2).toUpperCase()}</div><div><b>{channel.id}</b><small>{channel.id==="mercadolivre"?"API oficial e OAuth":"Próxima integração"}</small></div><span className={channel.state==="configured"?"ok":"off"}>{channel.state==="configured"?"CONFIGURADO":channel.state==="planned"?"PLANEJADO":"AGUARDA CHAVE"}</span></div>)}</article><article><p className="eyebrow">SEGURANÇA</p><h2>Publicação controlada</h2><p>As chaves ficam somente no backend. Cada anúncio passa por prévia, validação e aprovação antes do envio.</p><div className="guard">A chave secreta exibida anteriormente deve ser substituída no painel de desenvolvedores.</div></article></div>}

      {view === "Publicações" && <div className="columns"><article><p className="eyebrow">FILA DE PUBLICAÇÃO</p><h2>Nenhum envio automático</h2><p>As prévias do Mercado Livre aparecerão aqui antes da aprovação final.</p></article><article><p className="eyebrow">STATUS</p><h2>{commerce.publications} publicação(ões)</h2><div className="guard">Modo seguro ativo: publicação real bloqueada.</div></article></div>}

      {view === "Provedores" && <div className="columns providers"><article><p className="eyebrow">MODEL ROUTER</p><h2>Conexões de inteligência</h2><p>Uma API central seleciona o modelo, mas cada empresa usa sua própria chave.</p>{providers.map(p=><div className="provider" key={p.id}><div className={"logo "+p.id}>{p.id==="nvidia"?"N":"G"}</div><div><b>{p.id==="nvidia"?"NVIDIA NIM":"xAI · GROK"}</b><small>{p.model||"Modelo ainda não definido"}</small></div><span className={p.configured?"ok":"off"}>{p.configured?(p.enabled?"ATIVO":"BLOQUEADO"):"SEM CHAVE"}</span></div>)}</article><article><p className="eyebrow">COFRE DE SEGREDOS</p><h2>Configuração das APIs</h2><code>NVIDIA_API_KEY=••••••••</code><code>XAI_API_KEY=••••••••</code><p>As chaves ficam no servidor. O navegador recebe apenas o estado da conexão.</p><div className="guard">Grok permanece bloqueado enquanto <b>ALLOW_PAID_MODELS=false</b>.</div></article></div>}

      {view === "Banco & segurança" && <div className="columns security"><article><p className="eyebrow">SUPABASE</p><h2>PostgreSQL protegido</h2>{["Autenticação de usuários","RLS em todas as tabelas","Histórico e auditoria","Resultados e produtos","Métricas de modelos e custos"].map(x=><div className="check" key={x}>✓ <span>{x}</span></div>)}</article><article><p className="eyebrow">POLÍTICA DE DADOS</p><h2>Proteções ativas</h2><p>Nenhuma chave secreta chega ao navegador. Cada usuário acessa somente seus registros. Endereços internos são bloqueados pela API.</p><div className="shield"><b>RLS</b><small>DEFESA POR LINHA</small></div></article></div>}
      </div>
    </section>
  </main>;
}

createRoot(document.getElementById("root")).render(<App/>);
