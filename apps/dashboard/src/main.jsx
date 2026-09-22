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
    ["MCP & computador", ShieldCheck], ["Provedores", Bot], ["Banco & segurança", Database]
  ]}
];

async function request(path, options) {
  const response = await fetch(API + path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) { const detail=data.detail; throw new Error(typeof detail==="string"?detail:(detail?.message||"Falha na comunicação com o backend")); }
  return data;
}

const Badge = ({ status }) => <span className={"badge " + status}>{status}</span>;

function App() {
  const [view, setView] = useState("MCP & computador");
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
  const [seoDraft, setSeoDraft] = useState(null);
  const [importUrl, setImportUrl] = useState("");
  const [mlStatus, setMlStatus] = useState({state: "loading", connected: false});
  const [mcpScan, setMcpScan] = useState({servers: [], errors: [], policy: null});
  const [mcpLoading, setMcpLoading] = useState(false);

  async function refresh() {
    const [h, p, s, j, c, products, a, ml, mcp] = await Promise.all([
      request("/health"), request("/v1/providers"), request("/v1/stats"), request("/v1/jobs"),
      request("/v1/commerce/overview"), request("/v1/catalog/products"), request("/v1/agents"),
      request("/v1/channels/mercadolivre/status"), request("/v1/mcp/scan-local", {method: "POST"})
    ]);
    setHealth(h); setProviders(p.providers || []); setStats(s); setJobs(j);
    setCommerce(c); setCatalog(products); setAgents(a.agents || []); setMlStatus(ml); setMcpScan(mcp);
  }

  useEffect(() => { refresh().catch(e => setError(e.message)); }, []);

  async function scanMcp() {
    setMcpLoading(true); setError("");
    try {
      setMcpScan(await request("/v1/mcp/scan-local", {method: "POST"}));
    } catch (e) { setError(e.message); } finally { setMcpLoading(false); }
  }

  async function connectMercadoLivre() {
    setLoading(true); setError("");
    try {
      const oauth = await request("/v1/channels/mercadolivre/oauth/start");
      window.open(oauth.authorization_url, "_blank", "noopener,noreferrer");
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }

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
      const result = await request("/v1/media/prepare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ product_id: productId, size: 1600, quality: 96 }) });
      setMediaResult(result);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }

  async function runVisiblePipeline(product) {
    const steps = agents.map(agent => ({...agent, runState: "waiting", message: "Aguardando a etapa anterior"}));
    const update = (stage, runState, message, extra = {}) => setPipelineRun(current => ({
      ...current, ...extra,
      steps: current.steps.map(step => step.stage === stage ? {...step, runState, message} : step)
    }));
    setView("Execução"); setError(""); setSeoDraft(null);
    setPipelineRun({product, steps, images: [], startedAt: new Date().toISOString()});
    await new Promise(resolve => setTimeout(resolve, 300));
    update(1, "working", "Lendo o produto do catálogo central");
    await new Promise(resolve => setTimeout(resolve, 350));
    update(1, "completed", "Produto carregado da fonte autorizada");
    update(2, "working", "Conferindo título, preço, estoque, SKU e imagens");
    const missing = ["title", "price", "stock", "images"].filter(key => !product[key] && product[key] !== 0);
    if (missing.length) { update(2, "blocked", "Campos ausentes: " + missing.join(", ")); return; }
    update(2, "completed", "Dados comerciais conferidos");
    try {
      update(3, "working", "Enquadrando o produto inteiro, ampliando e removendo metadados");
      const media = await request("/v1/media/prepare", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({product_id: product.id, size: 1600, quality: 96})
      });
      setMediaResult(media);
      update(3, "completed", media.prepared_count + " imagens em 1600×2053, sem recorte adicional; limite: foto original do fornecedor", {images: media.prepared});

      update(4, "working", "Lendo tamanho, grade e medidas na fonte");
      const profile = await request("/v1/catalog/products/" + product.id + "/size-profile");
      if (profile.state === "ready") {
        const chart = await request("/v1/media/size-chart/auto", {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({product_id: product.id})
        });
        update(4, "completed", "Tabela criada somente com medidas comprovadas", {images: [...media.prepared, {url: chart.url}]});
      } else {
        update(4, "attention", profile.evidence + " Nenhuma medida foi inventada.");
      }

      update(5, "working", "Consultando sugestões reais de busca do Google");
      const draft = await request("/v1/seo/drafts", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({product_id: product.id, channel: "mercadolivre"})
      });
      setSeoDraft(draft);
      update(5, "completed", draft.research.keywords.length + " palavras candidatas encontradas");
      update(6, "completed", "Título e descrição específicos para Mercado Livre foram montados");
      update(7, draft.review.passed ? "completed" : "attention",
        draft.review.passed ? "Revisão factual aprovada: sem atributos inventados" : "Revisão encontrou: " + draft.review.warnings.join("; "));
      update(8, "attention", "Aguardando Carlos aprovar ou rejeitar o anúncio abaixo");

      update(9, "working", "Validando requisitos técnicos do Mercado Livre");
      const preview = await request("/v1/channels/mercadolivre/preview", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({product_id: product.id})
      });
      update(9, preview.ready ? "completed" : "attention",
        preview.ready ? "Prévia técnica aprovada" : "Ainda falta: " + preview.missing.join(", "));
      update(10, "blocked", "Bloqueado até sua aprovação, categoria e OAuth oficial");
      update(11, "paused", "Monitor começa somente depois da publicação");
    } catch (e) {
      const active = pipelineRun?.steps?.find(step => step.runState === "working");
      update(active?.stage || 5, "blocked", e.message);
      setError(e.message);
    }
  }

  async function decideDraft(decision) {
    if (!seoDraft) return;
    setLoading(true); setError("");
    try {
      const updated = await request("/v1/seo/drafts/" + seoDraft.id + "/decision", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({decision, note: decision === "approved" ? "Aprovado por Carlos no painel" : "Rejeitado por Carlos no painel"})
      });
      setSeoDraft(updated);
      setPipelineRun(current => ({...current, steps: current.steps.map(step =>
        step.stage === 8 ? {...step, runState: decision === "approved" ? "completed" : "blocked",
          message: decision === "approved" ? "Anúncio aprovado por Carlos" : "Anúncio rejeitado; não será publicado"} : step
      )}));
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }

  const cards = [
    ["PRODUTOS", commerce.products, "no catálogo central"],
    ["PUBLICAÇÕES", commerce.publications, "envios registrados"],
    ["CANAIS", commerce.channels.filter(c => ["configured","connected"].includes(c.state)).length, "configurados"],
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
            <span className="node-state">{step.runState==="working"?"TRABALHANDO":step.runState==="completed"?"CONCLUÍDO":step.runState==="attention"?"ATENÇÃO":step.runState==="blocked"?"BLOQUEADO":step.runState==="paused"?"PAUSADO":"AGUARDANDO"}</span>
          </div>)}
        </article>
        <article className="product-stage"><p className="eyebrow">PRODUTO EM PROCESSAMENTO</p>
          {pipelineRun?<><h2>{pipelineRun.product.title}</h2>
            <div className="live-product">
              <img src={pipelineRun.images?.[0]?API+pipelineRun.images[0].url:pipelineRun.product.images?.[0]} alt="Produto"/>
              <div><strong>{new Intl.NumberFormat("pt-BR",{style:"currency",currency:pipelineRun.product.currency||"BRL"}).format(pipelineRun.product.price||0)}</strong><small>Estoque: {pipelineRun.product.stock}</small><small>SKU: {pipelineRun.product.sku||"não informado"}</small></div>
            </div>
            {pipelineRun.images?.length>0&&<div className="prepared-gallery">{pipelineRun.images.map(image=><img key={image.url} src={API+image.url} alt="Imagem preparada"/>)}</div>}
            {seoDraft&&<section className="ad-proposal">
              <p className="eyebrow">ANÚNCIO PROPOSTO · {seoDraft.channel.toUpperCase()}</p>
              <label>TÍTULO ORIGINAL</label><p className="original-title">{pipelineRun.product.title}</p>
              <label>NOVO TÍTULO</label><h3>{seoDraft.proposal.title}</h3>
              <label>PALAVRAS ENCONTRADAS EM BUSCAS REAIS</label>
              <div className="keyword-list">{seoDraft.research.keywords.slice(0,12).map(word=><span key={word}>{word}</span>)}</div>
              <label>DESCRIÇÃO PROPOSTA</label><div className="proposal-description">{seoDraft.proposal.description}</div>
              <div className={seoDraft.review.passed?"review-ok":"review-warning"}>
                {seoDraft.review.passed?"✓ Revisor factual: nenhuma informação inventada detectada.":"⚠ "+seoDraft.review.warnings.join(" · ")}
              </div>
              <small className="research-note">Pesquisa: Google Autocomplete, núcleo gratuito compatível com serp_adjacency_expand do SEOMonster. Volume exato depende da conexão Google Ads/Search Console.</small>
              {seoDraft.approval.state==="pending"?<div className="approval-actions">
                <button disabled={loading||!seoDraft.review.passed} onClick={()=>decideDraft("approved")}>APROVAR ANÚNCIO</button>
                <button className="reject" disabled={loading} onClick={()=>decideDraft("rejected")}>REJEITAR</button>
              </div>:<div className={"approval-result "+seoDraft.approval.state}>{seoDraft.approval.state==="approved"?"APROVADO POR CARLOS":"REJEITADO POR CARLOS"}</div>}
            </section>}
            <div className="publish-lock"><b>MERCADO LIVRE: NÃO PUBLICADO</b><span>{seoDraft?.approval.state==="approved"?"Anúncio aprovado; ainda faltam categoria e OAuth oficial.":"A publicação está bloqueada até sua aprovação, categoria e OAuth oficial."}</span></div>
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

      {view === "Canais" && <div className="columns providers">
        <article><p className="eyebrow">MARKETPLACES</p><h2>Conexões comerciais</h2>
          {commerce.channels.map(channel=><div className="provider" key={channel.id}>
            <div className="logo">{channel.id.slice(0,2).toUpperCase()}</div>
            <div><b>{channel.id}</b><small>{channel.id==="mercadolivre"?"OAuth oficial com renovação automática":"Próxima integração"}</small></div>
            <span className={(channel.id==="mercadolivre"?mlStatus.connected:channel.state==="configured")?"ok":"off"}>
              {channel.id==="mercadolivre"?(mlStatus.connected?"CONECTADO":"AUTORIZAÇÃO PENDENTE"):channel.state==="planned"?"PLANEJADO":"AGUARDA CHAVE"}
            </span>
          </div>)}
          {!mlStatus.connected&&<button disabled={loading||mlStatus.state==="needs_credentials"} onClick={connectMercadoLivre}>CONECTAR MERCADO LIVRE</button>}
        </article>
        <article><p className="eyebrow">TOKEN AUTOMÁTICO</p><h2>{mlStatus.connected?"Proteção ativa":"Aguardando conexão"}</h2>
          <p>O access token é renovado 30 minutos antes de vencer. Se a API responder 401, o sistema renova e tenta novamente uma única vez.</p>
          {mlStatus.expires_at&&<div className="guard">Expira em: {new Date(mlStatus.expires_at).toLocaleString("pt-BR")} · renovação automática ativa.</div>}
          <div className="guard">Access token e refresh token ficam criptografados somente no backend e nunca aparecem no navegador.</div>
        </article>
      </div>}

      {view === "Publicações" && <div className="columns"><article><p className="eyebrow">FILA DE PUBLICAÇÃO</p><h2>Nenhum envio automático</h2><p>As prévias do Mercado Livre aparecerão aqui antes da aprovação final.</p></article><article><p className="eyebrow">STATUS</p><h2>{commerce.publications} publicação(ões)</h2><div className="guard">Modo seguro ativo: publicação real bloqueada.</div></article></div>}

      {view === "MCP & computador" && <div className="mcp-layout">
        <article className="mcp-console">
          <div className="title"><div><p className="eyebrow">CENTRAL MCP</p><h2>Ferramentas detectadas</h2></div>
            <button className="ghost" disabled={mcpLoading} onClick={scanMcp}>{mcpLoading?"ANALISANDO...":"ANALISAR NOVAMENTE"}</button>
          </div>
          <div className="mcp-summary">
            <div><strong>{mcpScan.configs_found||0}</strong><small>CONFIGURAÇÕES</small></div>
            <div><strong>{mcpScan.servers?.length||0}</strong><small>SERVIDORES</small></div>
            <div><strong>{mcpScan.servers?.filter(server=>server.risk==="high").length||0}</strong><small>ALTO RISCO</small></div>
          </div>
          {mcpScan.servers?.map(server=><div className="mcp-server" key={server.name}>
            <div className="mcp-server-head"><div className="logo">MC</div><div><b>{server.name}</b><small>{server.command} {server.args?.join(" ")}</small></div>
              <span className={server.command_found?"ok":"off"}>{server.command_found?"DETECTADO":"COMANDO AUSENTE"}</span></div>
            <div className="mcp-flow">
              <div className="done"><i>1</i><b>Descoberta</b><small>Configuração localizada</small></div>
              <div className="done"><i>2</i><b>Validação</b><small>Comando {server.command_found?"confirmado":"não encontrado"}</small></div>
              <div className="attention"><i>3</i><b>Segurança</b><small>{server.risk==="high"?"Controle real do Windows":"Revisão necessária"}</small></div>
              <div className="blocked"><i>4</i><b>Conexão</b><small>Aguardando aprovação explícita</small></div>
            </div>
            {server.risk_reasons?.map(reason=><div className="mcp-warning" key={reason}>⚠ {reason}</div>)}
          </div>)}
          {!mcpScan.servers?.length&&<div className="empty">Nenhum servidor MCP encontrado.</div>}
        </article>
        <article className="mcp-policy">
          <p className="eyebrow">AGENTE DE DECISÃO</p><h2>Política inteligente</h2>
          <div className="policy-row safe"><b>AUTOMÁTICO</b><span>Descobrir, ler metadados, validar JSON e verificar executáveis.</span></div>
          <div className="policy-row review"><b>PEDE APROVAÇÃO</b><span>Alterar configuração, iniciar MCP, autenticar conta ou escrever arquivos.</span></div>
          <div className="policy-row danger"><b>BLOQUEADO</b><span>Excluir arquivos, alterar registro, executar shell ou clicar em confirmação sem autorização.</span></div>
          <div className="guard">O agente recomenda a conexão e explica o risco. Carlos continua com a decisão final.</div>
          <div className="mcp-live"><i></i><div><b>MONITOR MCP ATIVO</b><small>Leitura segura · nenhuma conexão silenciosa</small></div></div>
        </article>
      </div>}

      {view === "Provedores" && <div className="columns providers"><article><p className="eyebrow">MODEL ROUTER</p><h2>Conexões de inteligência</h2><p>Uma API central seleciona o modelo, mas cada empresa usa sua própria chave.</p>{providers.map(p=><div className="provider" key={p.id}><div className={"logo "+p.id}>{p.id==="nvidia"?"N":"G"}</div><div><b>{p.id==="nvidia"?"NVIDIA NIM":"xAI · GROK"}</b><small>{p.model||"Modelo ainda não definido"}</small></div><span className={p.configured?"ok":"off"}>{p.configured?(p.enabled?"ATIVO":"BLOQUEADO"):"SEM CHAVE"}</span></div>)}</article><article><p className="eyebrow">COFRE DE SEGREDOS</p><h2>Configuração das APIs</h2><code>NVIDIA_API_KEY=••••••••</code><code>XAI_API_KEY=••••••••</code><p>As chaves ficam no servidor. O navegador recebe apenas o estado da conexão.</p><div className="guard">Grok permanece bloqueado enquanto <b>ALLOW_PAID_MODELS=false</b>.</div></article></div>}

      {view === "Banco & segurança" && <div className="columns security"><article><p className="eyebrow">SUPABASE</p><h2>PostgreSQL protegido</h2>{["Autenticação de usuários","RLS em todas as tabelas","Histórico e auditoria","Resultados e produtos","Métricas de modelos e custos"].map(x=><div className="check" key={x}>✓ <span>{x}</span></div>)}</article><article><p className="eyebrow">POLÍTICA DE DADOS</p><h2>Proteções ativas</h2><p>Nenhuma chave secreta chega ao navegador. Cada usuário acessa somente seus registros. Endereços internos são bloqueados pela API.</p><div className="shield"><b>RLS</b><small>DEFESA POR LINHA</small></div></article></div>}
      </div>
    </section>
  </main>;
}

createRoot(document.getElementById("root")).render(<App/>);
