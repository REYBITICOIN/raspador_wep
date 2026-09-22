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
    ["Comando", LayoutDashboard], ["Execução", Command], ["Laboratório", FlaskConical], ["Histórico", History]
  ]},
  { label: "Comércio", items: [
    ["Catálogo", Package], ["Agentes", Activity], ["Canais", Store], ["Publicações", Send]
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
  const [agents, setAgents] = useState([]);
  const [mediaResult, setMediaResult] = useState(null);
  const [pipelineRun, setPipelineRun] = useState(null);
  const [importUrl, setImportUrl] = useState("");

  async function refresh() {
    const [h, p, s, j, c, products, a] = await Promise.all([
      request("/health"), request("/v1/providers"), request("/v1/stats"), request("/v1/jobs"),
      request("/v1/commerce/overview"), request("/v1/catalog/products"), request("/v1/agents")
    ]);
    setHealth(h); setProviders(p.providers || []); setStats(s); setJobs(j);
    setCommerce(c); setCatalog(products); setAgents(a.agents || []);
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

  async function prepareProductImages(productId) {
    setLoading(true); setError("");
    try {
      const result = await request("/v1/media/prepare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ product_id: productId, size: 1200, quality: 94 }) });
      setMediaResult(result);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }

  async function runVisiblePipeline(product) {
    const steps = agents.map(agent => ({
      ...agent, runState: "waiting", message: "Aguardando a etapa anterior"
    }));
    const update = (stage, runState, message, extra = {}) => {
      setPipelineRun(current => ({
        ...current,
        ...extra,
        steps: current.steps.map(step =>
          step.stage === stage ? {...step, runState, message} : step
        )
      }));
    };
    setView("Execução");
    setError("");
    setPipelineRun({product, steps, images: [], startedAt: new Date().toISOString()});
    await new Promise(resolve => setTimeout(resolve, 350));
    update(1, "working", "Lendo o produto do catálogo central");
    await new Promise(resolve => setTimeout(resolve, 500));
    update(1, "completed", "Produto carregado da fonte autorizada");
    update(2, "working", "Conferindo título, preço, estoque, SKU e imagens");
    await new Promise(resolve => setTimeout(resolve, 600));
    const missing = ["title", "price", "stock", "images"].filter(key => !product[key] && product[key] !== 0);
    if (missing.length) {
      update(2, "blocked", "Campos ausentes: " + missing.join(", "));
      return;
    }
    update(2, "completed", "Dados comerciais conferidos");
    update(3, "working", "Recortando, centralizando e melhorando as imagens");
    try {
      const media = await request("/v1/media/prepare", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({product_id: product.id, size: 1200, quality: 94})
      });
      setMediaResult(media);
      update(3, "completed", media.prepared_count + " imagens prontas em 1200×1200", {
        images: media.prepared
      });
      update(4, "blocked", "Aguardando medidas reais do fornecedor");
      [5,6,7,8,9].forEach(stage => update(stage, "paused", "Pausado: a etapa 4 precisa ser resolvida"));
    } catch (e) {
      update(3, "blocked", e.message);
      setError(e.message);
    }
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

      {view === "Execução" && <div className="execution-layout">
        <article className="execution-board">
          <div className="title"><div><p className="eyebrow">OPERAÇÃO AO VIVO</p><h2>Fluxo visual dos agentes</h2></div>
            {!pipelineRun && catalog[0] && <button onClick={()=>runVisiblePipeline(catalog[0])}>EXECUTAR PRODUTO</button>}
          </div>
          {!pipelineRun && <div className="empty">Clique em EXECUTAR PRODUTO para acompanhar cada etapa trabalhando.</div>}
          {pipelineRun?.steps.map(step=><div className={"agent-node "+step.runState} key={step.id}>
            <div className="node-number">{String(step.stage).padStart(2,"0")}</div>
            <div className="node-copy"><b>{step.name}</b><small>{step.message}</small></div>
            <span className="node-state">{step.runState==="working"?"TRABALHANDO":step.runState==="completed"?"CONCLUÍDO":step.runState==="blocked"?"BLOQUEADO":step.runState==="paused"?"PAUSADO":"AGUARDANDO"}</span>
          </div>)}
        </article>
        <article className="product-stage"><p className="eyebrow">PRODUTO EM PROCESSAMENTO</p>
          {pipelineRun?<><h2>{pipelineRun.product.title}</h2>
            <div className="live-product">
              <img src={pipelineRun.images?.[0]?API+pipelineRun.images[0].url:pipelineRun.product.images?.[0]} alt="Produto"/>
              <div><strong>{new Intl.NumberFormat("pt-BR",{style:"currency",currency:pipelineRun.product.currency||"BRL"}).format(pipelineRun.product.price||0)}</strong><small>Estoque: {pipelineRun.product.stock}</small><small>SKU: {pipelineRun.product.sku||"não informado"}</small></div>
            </div>
            {pipelineRun.images?.length>0&&<div className="prepared-gallery">{pipelineRun.images.map(image=><img key={image.url} src={API+image.url} alt="Imagem preparada"/>)}</div>}
            <div className="publish-lock"><b>MERCADO LIVRE: NÃO PUBLICADO</b><span>Faltam medidas/categoria e autorização OAuth oficial.</span></div>
          </>:<div className="empty">O produto aparecerá aqui durante a execução.</div>}
        </article>
      </div>}

      {view === "Laboratório" && <div className="columns lab"><article><p className="eyebrow">NOVA MISSÃO</p><h2>Configurar coleta</h2><form onSubmit={submit}><label>URL pública autorizada<input type="url" value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://exemplo.com/produto" required/></label><label>Objetivo da extração<textarea value={instruction} onChange={e=>setInstruction(e.target.value)} minLength="5" required/></label><label>Rota de inteligência<select value={provider} onChange={e=>setProvider(e.target.value)}><option value="auto">Automática e econômica</option><option value="nvidia">NVIDIA</option><option value="grok">Grok — requer autorização</option></select></label><div className="guard">◈ URLs privadas são bloqueadas. CAPTCHA, login e proteções não serão contornados.</div><button disabled={loading}>{loading ? "COLETANDO..." : "INICIAR COLETA"}</button></form></article><article className="pipeline"><p className="eyebrow">PIPELINE</p>{["Validação de segurança","Captura real da página","Extração estruturada","Registro no banco","Auditoria e evidências"].map((x,i)=><div key={x}><span>{String(i+1).padStart(2,"0")}</span><b>{x}</b></div>)}</article></div>}

      {view === "Histórico" && <div className="columns history"><article><div className="title"><div><p className="eyebrow">MISSÕES</p><h2>Histórico de coletas</h2></div><button className="ghost" onClick={()=>refresh().catch(e=>setError(e.message))}>ATUALIZAR</button></div>{jobs.map(job=><div className={"jobrow "+(selected?.id===job.id?"selected":"")} key={job.id} onClick={()=>setSelected(job)}><div><b>{job.result?.title || new URL(job.url).hostname}</b><small>{job.url}</small></div><Badge status={job.status}/><time>{new Date(job.created_at).toLocaleDateString("pt-BR")}</time></div>)}{!jobs.length&&<div className="empty">Seu histórico aparecerá aqui.</div>}</article><article className="detail"><p className="eyebrow">EVIDÊNCIA</p>{selected?<><h2>{selected.result?.title||"Coleta sem título"}</h2><Badge status={selected.status}/>{selected.result?.blocked&&<div className="errorbox">A página bloqueou a coleta com verificação. Nenhum produto foi recebido.</div>}<dl><dt>URL</dt><dd>{selected.url}</dd><dt>Solicitado</dt><dd>{selected.provider}</dd><dt>Usado</dt><dd>{selected.result?.actual_provider||"—"}</dd><dt>HTTP</dt><dd>{selected.result?.http_status||"—"}</dd></dl>{selected.error&&<div className="errorbox">{selected.error}</div>}{selected.result?.extraction?.products?.length>0?<div className="products">{selected.result.extraction.products.map((product,i)=><div className="product" key={i}>{product.image_url&&<img src={product.image_url} alt=""/>}<div><b>{product.title}</b><strong>{product.price?new Intl.NumberFormat("pt-BR",{style:"currency",currency:product.currency||"BRL"}).format(product.price):"Preço não informado"}</strong><small>{product.seller||product.availability}</small></div></div>)}</div>:<p>{selected.result?.note}</p>}<pre>{JSON.stringify(selected.result?.extraction||selected.result,null,2)}</pre></>:<div className="empty">Selecione uma missão.</div>}</article></div>}

      {view === "Agentes" && <div className="columns providers">
        <article><p className="eyebrow">LINHA DE PRODUÇÃO</p><h2>{agents.length} minagentes especializados</h2>
          {agents.map(agent=><div className="provider" key={agent.id}><div className="logo">{String(agent.stage).padStart(2,"0")}</div><div><b>{agent.name}</b><small>{agent.input} → {agent.output}</small></div><span className={agent.state==="active"?"ok":"off"}>{agent.state==="active"?"ATIVO":agent.state.replaceAll("_"," ").toUpperCase()}</span></div>)}
        </article>
        <article><p className="eyebrow">ARQUITETURA</p><h2>Uma tarefa por agente</h2><p>Cada etapa valida sua saída antes de entregar para a próxima. Falta de preço, medida, imagem, categoria ou autorização interrompe somente aquela etapa.</p><div className="guard">NVIDIA e Grok melhoram conteúdo. APIs oficiais transportam e publicam os dados.</div></article>
      </div>}

      {view === "Catálogo" && <div className="columns lab">
        <article><p className="eyebrow">CATÁLOGO CENTRAL</p><h2>Importar da Toca da Onça</h2>
          <form onSubmit={importToCatalog}><label>URL do produto<input type="url" value={importUrl} onChange={e=>setImportUrl(e.target.value)} placeholder="https://tocadaoncamodas.com.br/produto/..." required/></label><button disabled={loading}>{loading?"IMPORTANDO...":"IMPORTAR PRODUTO"}</button></form>
          <div className="guard">O produto entra primeiro no catálogo. Nada é publicado automaticamente.</div>
        </article>
        <article><p className="eyebrow">PRODUTOS</p><h2>{catalog.length} item(ns)</h2>
          {catalog.map(product=><div className="product" key={product.id}>{product.images?.[0]&&<img src={product.images[0]} alt=""/>}<div><b>{product.title}</b><strong>{new Intl.NumberFormat("pt-BR",{style:"currency",currency:product.currency||"BRL"}).format(product.price||0)}</strong><small>Estoque: {product.stock} · {product.sku||"sem SKU"}</small><button className="ghost" disabled={loading} onClick={()=>prepareProductImages(product.id)}>PREPARAR IMAGENS</button><button className="ghost run-button" disabled={loading} onClick={()=>runVisiblePipeline(product)}>VER AGENTES TRABALHANDO</button></div></div>)}
          {!catalog.length&&<div className="empty">Importe o primeiro produto da loja.</div>}
          {mediaResult&&<div className="guard">✓ {mediaResult.prepared_count} imagem(ns) preparada(s) pelo Curador. Aprovação visual obrigatória antes da publicação.</div>}
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
