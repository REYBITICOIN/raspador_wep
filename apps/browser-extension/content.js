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

  function firstText(selectors) {
    for (const selector of selectors) {
      const value = text(selector);
      if (value) return {value, selector};
    }
    return {value: "", selector: ""};
  }

  function attr(selectors, name) {
    for (const selector of selectors) {
      const value = document.querySelector(selector)?.getAttribute(name)?.trim();
      if (value) return {value, selector};
    }
    return {value: "", selector: ""};
  }

  function numberFromText(value) {
    const match = String(value || "").replace(/\./g, "").match(/\d+(?:,\d+)?/);
    return match ? Number(match[0].replace(",", ".")) : null;
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
    const source = {};
    const record = (key, value, label) => {
      if (value !== null && value !== undefined && value !== "") source[key] = label;
      return value || null;
    };
    const sellerSchema = typeof offer.seller === "object" ? offer.seller?.name : offer.seller;
    const sellerDom = firstText([".ui-pdp-seller__header__title", ".ui-pdp-seller__header__title a", "[data-testid='seller-info']"]);
    const brandDom = firstText([".ui-pdp-family--REGULAR", ".ui-pdp-specs__table__column span"]);
    const conditionDom = firstText([".ui-pdp-header__subtitle", ".ui-pdp-subtitle"]);
    const ratingDom = firstText([".ui-pdp-review__rating", ".ui-review-capability__rating__average"]);
    const reviewsDom = firstText([".ui-pdp-review__amount", ".ui-review-capability__rating__label"]);
    const soldDom = firstText([".ui-pdp-subtitle", ".ui-pdp-header__subtitle"]);
    const shippingDom = firstText([".ui-pdp-shipping__title", ".ui-pdp-shipping__subtitle", "[data-testid='shipping-message']"]);
    const catalogDom = firstText([".ui-pdp-component-list .ui-pdp-color--BLACK", "[data-testid='catalog-product']"]);
    const listingId = location.pathname.match(/ML[ABU]-?\d+/i)?.[0]?.replace("-", "").toUpperCase() || null;
    const title = record("title", schema.name || meta("og:title") || text("h1"), schema.name ? "JSON-LD Product.name" : meta("og:title") ? "OpenGraph og:title" : "DOM h1");
    const visiblePrice = firstText(['[itemprop="price"]', ".andes-money-amount__fraction", ".a-price .a-offscreen"]);
    const price = record("price", normalizePrice(offer.price || meta("product:price:amount") || visiblePrice.value), offer.price ? "JSON-LD Product.offers.price" : meta("product:price:amount") ? "Meta product:price:amount" : `DOM ${visiblePrice.selector}`);
    const seller = record("seller", sellerSchema || sellerDom.value, sellerSchema ? "JSON-LD Product.offers.seller" : `DOM ${sellerDom.selector}`);
    const brand = record("brand", typeof schema.brand === "object" ? schema.brand?.name : schema.brand || brandDom.value, schema.brand ? "JSON-LD Product.brand" : `DOM ${brandDom.selector}`);
    const condition = record("condition", String(offer.itemCondition || "").split("/").pop() || conditionDom.value.split("|")[0]?.trim(), offer.itemCondition ? "JSON-LD Product.offers.itemCondition" : `DOM ${conditionDom.selector}`);
    const rating = record("rating", Number(schema.aggregateRating?.ratingValue) || numberFromText(ratingDom.value), schema.aggregateRating?.ratingValue ? "JSON-LD aggregateRating.ratingValue" : `DOM ${ratingDom.selector}`);
    const reviewCount = record("review_count", Number(schema.aggregateRating?.reviewCount) || numberFromText(reviewsDom.value), schema.aggregateRating?.reviewCount ? "JSON-LD aggregateRating.reviewCount" : `DOM ${reviewsDom.selector}`);
    const soldCount = /vendid/i.test(soldDom.value) ? record("sold_count", numberFromText(soldDom.value.match(/([\d.]+)\s+vendid/i)?.[0]), `DOM ${soldDom.selector}`) : null;
    const schemaImages = Array.isArray(schema.image) ? schema.image.length : schema.image ? 1 : 0;
    const images = Math.max(schemaImages, document.querySelectorAll(".ui-pdp-gallery__figure img, .ui-pdp-gallery img").length);
    const shipping = record("shipping", shippingDom.value, `DOM ${shippingDom.selector}`);
    const evidence = Object.entries(source).map(([key, label]) => `${key}: ${label}`);
    const missing = ["seller", "brand", "condition", "rating"].filter(key => !source[key]);

    return {
      marketplace: marketplace(), url: location.href,
      canonical_url: document.querySelector('link[rel="canonical"]')?.href || location.href,
      captured_at: new Date().toISOString(), listing_id: listingId,
      title, price, currency: offer.priceCurrency || meta("product:price:currency") || "BRL",
      seller, brand, category: null, condition,
      rating, review_count: reviewCount, sold_count: soldCount,
      image_count: images || null, shipping,
      listing_type: null, seller_reputation: null,
      is_catalog: /cat[aá]logo/i.test(catalogDom.value) || null,
      is_sponsored: /patrocinado/i.test(document.body.innerText.slice(0, 5000)) || null,
      availability: String(offer.availability || "").split("/").pop() || null,
      stock: null, sales_estimate: null, source_map: source, evidence,
      confidence: source.title && source.price ? (evidence.length >= 5 ? "high" : "medium") : "low",
      warnings: [
        ...(missing.length ? [`Não confirmados: ${missing.join(", ")}.`] : []),
        ...(soldCount === null ? ["Vendas não expostas pela página; nenhuma estimativa foi inventada."] : []),
        "Estoque oculto permanece vazio sem API ou evidência verificável."
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
      field("ID anúncio", data.listing_id),
      field("Vendedor", data.seller),
      field("Marca", data.brand),
      field("Condição", data.condition),
      field("Avaliação", data.rating == null ? null : `${data.rating} / 5`),
      field("Avaliações", data.review_count),
      field("Vendidos", data.sold_count),
      field("Imagens", data.image_count),
      field("Entrega", data.shipping),
      field("Catálogo", data.is_catalog == null ? null : data.is_catalog ? "SIM" : "NÃO"),
      field("Patrocinado", data.is_sponsored == null ? null : data.is_sponsored ? "SIM" : "NÃO"),
      field("Estoque", data.stock),
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
