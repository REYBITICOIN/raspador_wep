(() => {
  const PANEL_ID = "toca-commerce-ray-x";

  function marketplace() {
    const host = location.hostname;
    if (host.includes("mercadolivre") || host.includes("mercadolibre")) return "mercadolivre";
    if (host.includes("shopee")) return "shopee";
    if (host.includes("amazon")) return "amazon";
    return "unknown";
  }

  function text(selector) {
    return document.querySelector(selector)?.textContent?.trim() || "";
  }

  function meta(property) {
    return document.querySelector(`meta[property="${property}"],meta[name="${property}"]`)?.content?.trim() || "";
  }

  function productSchema() {
    for (const node of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const raw = JSON.parse(node.textContent);
        const values = Array.isArray(raw) ? raw : raw["@graph"] || [raw];
        const product = values.find(item => item?.["@type"] === "Product");
        if (product) return product;
      } catch {}
    }
    return {};
  }
  function offerOf(schema) {
    if (Array.isArray(schema.offers)) return schema.offers[0] || {};
    return schema.offers || {};
  }

  function normalizePrice(value) {
    if (typeof value === "number") return value;
    const cleaned = String(value || "").replace(/[^0-9,.-]/g, "");
    if (!cleaned) return null;
    const normalized = cleaned.includes(",")
      ? cleaned.replace(/\./g, "").replace(",", ".")
      : cleaned;
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function inspectPage() {
    const schema = productSchema();
    const offer = offerOf(schema);
    const seller = typeof offer.seller === "object" ? offer.seller?.name : offer.seller;
    const title = schema.name || meta("og:title") || text("h1");
    const visiblePrice = text('[itemprop="price"]') ||
      text(".andes-money-amount__fraction") ||
      text(".a-price .a-offscreen");
    const price = normalizePrice(offer.price || meta("product:price:amount") || visiblePrice);
    const availability = String(offer.availability || "").split("/").pop() || null;
    const evidence = [];
    if (schema.name) evidence.push("JSON-LD Product.name");
    if (offer.price) evidence.push("JSON-LD Product.offers.price");
    if (seller) evidence.push("JSON-LD Product.offers.seller");
    if (!schema.name && meta("og:title")) evidence.push("OpenGraph og:title");
    if (!offer.price && visiblePrice) evidence.push("Preço visível no DOM");

    return {
      marketplace: marketplace(),
      url: location.href,
      canonical_url: document.querySelector('link[rel="canonical"]')?.href || location.href,
      captured_at: new Date().toISOString(),
      title: title || null,
      price,
      currency: offer.priceCurrency || meta("product:price:currency") || "BRL",
      seller: seller || null,
      availability,
      stock: null,
      sales_estimate: null,
      evidence,
      confidence: evidence.length >= 2 ? "high" : evidence.length ? "medium" : "low",
      warnings: [
        ...(seller ? [] : ["Vendedor não confirmado pela página."]),
        "Estoque e vendas estimadas permanecem vazios sem fonte verificável."
      ]
    };
  }

  function field(label, value) {
    const row = document.createElement("div");
    row.className = "toca-ray-row";
    const key = document.createElement("span");
    key.textContent = label;
    const data = document.createElement("b");
    data.textContent = value ?? "NÃO CONFIRMADO";
    row.append(key, data);
    return row;
  }
  function marginCalculator(data) {
    const box = document.createElement("div");
    box.className = "toca-margin";
    box.innerHTML = `<strong>CALCULADORA DE LUCRO</strong>
      <label>Custo do produto <input data-cost type="number" min="0" step="0.01"></label>
      <label>Comissão % <input data-commission type="number" min="0" max="100" step="0.01"></label>
      <label>Frete + taxa fixa <input data-fixed type="number" min="0" step="0.01"></label>
      <button type="button">CALCULAR MARGEM</button><output></output>`;
    box.querySelector("button").onclick = () => {
      const output = box.querySelector("output");
      output.textContent = "CALCULANDO...";
      const payload = {
        sale_price: data.price,
        acquisition_cost: Number(box.querySelector("[data-cost]").value || 0),
        commission_percent: Number(box.querySelector("[data-commission]").value || 0),
        shipping_cost: Number(box.querySelector("[data-fixed]").value || 0)
      };
      chrome.runtime.sendMessage({type: "TOCA_CALCULATE_MARGIN", payload}, response => {
        if (!response?.ok) {
          output.textContent = "ERRO: " + (response?.error || "sem conexão");
          return;
        }
        const value = response.result;
        output.textContent = `Lucro líquido: R$ ${value.net_profit.toFixed(2)} · Margem: ${value.net_margin_percent.toFixed(2)}% · Mínimo: R$ ${value.break_even_price.toFixed(2)}`;
      });
    };
    return box;
  }

  function render() {
    document.getElementById(PANEL_ID)?.remove();
    const data = inspectPage();
    const panel = document.createElement("aside");
    panel.id = PANEL_ID;
    const header = document.createElement("header");
    header.innerHTML = "<strong>TOCA · RAIO-X</strong>";
    const close = document.createElement("button");
    close.textContent = "×";
    close.title = "Fechar";
    close.onclick = () => panel.remove();
    header.append(close);
    panel.append(header);

    const body = document.createElement("section");
    body.append(
      field("Marketplace", data.marketplace),
      field("Título", data.title),
      field("Preço", data.price == null ? null : new Intl.NumberFormat("pt-BR", {style: "currency", currency: data.currency}).format(data.price)),
      field("Vendedor", data.seller),
      field("Estoque", data.stock),
      field("Vendas", data.sales_estimate),
      field("Confiança", data.confidence.toUpperCase())
    );
    const proof = document.createElement("small");
    proof.textContent = "Fontes: " + (data.evidence.join(" · ") || "nenhuma evidência estruturada");
    body.append(proof);
    const warning = document.createElement("p");
    warning.className = "toca-ray-warning";
    warning.textContent = data.warnings.join(" ");
    body.append(warning);
    if (data.price != null) body.append(marginCalculator(data));

    const save = document.createElement("button");
    save.className = "toca-ray-save";
    save.textContent = "SALVAR NO LABORATÓRIO";
    save.onclick = () => {
      save.disabled = true;
      save.textContent = "SALVANDO...";
      chrome.runtime.sendMessage({type: "TOCA_SAVE_SNAPSHOT", payload: data}, response => {
        save.disabled = false;
        save.textContent = response?.ok ? "SALVO ✓" : "ERRO: " + (response?.error || "sem conexão");
      });
    };
    body.append(save);
    panel.append(body);
    document.documentElement.append(panel);
    return data;
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type === "TOCA_INSPECT") {
      render();
      sendResponse({ok: true});
    }
  });

  if (["mercadolivre", "shopee", "amazon"].includes(marketplace())) {
    render();
  }
})();
