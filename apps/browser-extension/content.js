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

  function renderProduct() {
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

  function priceFromCard(card) {
    const current = card.querySelector(".poly-price__current .andes-money-amount, .poly-component__price > .andes-money-amount");
    if (!current) return null;
    const fraction = current.querySelector(".andes-money-amount__fraction")?.textContent || "";
    const cents = current.querySelector(".andes-money-amount__cents")?.textContent || "00";
    return normalizePrice(`${fraction},${cents}`);
  }

  function inspectSearchPage() {
    const cards = [...document.querySelectorAll(".ui-search-layout__item")];
    const products = cards.map((item, index) => {
      const card = item.querySelector(".poly-card") || item;
      const link = card.querySelector("a.poly-component__title");
      const href = link?.href || "";
      const listingId = decodeURIComponent(href).match(/ML[ABU]-?\d+/i)?.[0]?.replace("-", "").toUpperCase() || null;
      const seller = card.querySelector(".poly-component__seller .polylabel-label")?.textContent?.trim() || null;
      const ratingText = card.querySelector(".poly-component__review-compacted .polylabel-label")?.textContent?.trim() || "";
      const rating = Number.parseFloat(ratingText.replace(",", ".")) || null;
      const shippingNode = [...card.querySelectorAll(".polylabel-pill, .poly-component__shipping")].find(node => /grátis|frete|chegar/i.test(node.textContent || ""));
      const shipping = shippingNode?.textContent?.trim() || null;
      const discount = card.querySelector(".poly-price__disc_label, .andes-money-amount__discount")?.textContent?.trim() || null;
      const badge = card.querySelector(".poly-component__poly-label")?.textContent?.trim() || null;
      const official = Boolean(card.querySelector('[aria-label="Loja oficial"]'));
      const sponsored = href.includes("is_advertising=true") || /(^|\n)Ad($|\n)/.test(card.innerText);
      return {
        position: index + 1, listing_id: listingId,
        title: link?.textContent?.trim() || null, price: priceFromCard(card),
        currency: "BRL", url: href || null, seller, rating, shipping,
        discount, badge, official_store: official, sponsored,
        image_url: card.querySelector("img.poly-component__picture")?.src || null,
        evidence: ["DOM .ui-search-layout__item", "DOM .poly-card"]
      };
    }).filter(product => product.title && product.price !== null);
    const prices = products.map(product => product.price);
    const query = document.querySelector(".nav-search-input")?.value?.trim() ||
      decodeURIComponent(location.pathname.split("/").pop() || "").replace(/-/g, " ");
    return {
      marketplace: "mercadolivre", page_type: "search", url: location.href,
      captured_at: new Date().toISOString(), query,
      visible_results: cards.length, captured_results: products.length,
      sponsored_count: products.filter(product => product.sponsored).length,
      official_store_count: products.filter(product => product.official_store).length,
      free_shipping_count: products.filter(product => /gr[aá]tis/i.test(product.shipping || "")).length,
      min_price: prices.length ? Math.min(...prices) : null,
      max_price: prices.length ? Math.max(...prices) : null,
      products,
      confidence: products.length ? "high" : "low",
      warnings: ["Vendas, visitas e estoque não são estimados sem fonte verificável."]
    };
  }

  function searchProductCard(product) {
    const card = document.createElement("article");
    card.className = "toca-search-product";
    const flags = [product.sponsored ? "PATROCINADO" : null, product.official_store ? "LOJA OFICIAL" : null, product.badge].filter(Boolean);
    card.innerHTML = `<span>#${product.position}</span><strong></strong><b></b><small></small>`;
    card.querySelector("strong").textContent = product.title;
    card.querySelector("b").textContent = new Intl.NumberFormat("pt-BR", {style: "currency", currency: "BRL"}).format(product.price);
    card.querySelector("small").textContent = [product.seller, product.rating ? `★ ${product.rating}` : null, product.shipping, ...flags].filter(Boolean).join(" · ");
    return card;
  }

  function renderHistory(container, history) {
    container.replaceChildren();
    const title = document.createElement("strong");
    title.textContent = `HISTÓRICO · ${history.snapshot_count} CAPTURA(S)`;
    container.append(title);
    if (!history.has_comparison) {
      const message = document.createElement("p");
      message.textContent = "A segunda captura permitirá calcular mudanças de preço e posição.";
      container.append(message);
      return;
    }
    history.competitors.slice(0, 8).forEach(product => {
      const row = document.createElement("div");
      row.className = "toca-history-row";
      const position = product.position_change == null ? "novo" :
        product.position_change > 0 ? `subiu ${product.position_change}` :
        product.position_change < 0 ? `caiu ${Math.abs(product.position_change)}` : "posição estável";
      const price = product.price_change == null ? "" :
        product.price_change > 0 ? ` · preço +R$ ${product.price_change.toFixed(2)}` :
        product.price_change < 0 ? ` · preço -R$ ${Math.abs(product.price_change).toFixed(2)}` : " · preço estável";
      row.textContent = `#${product.current_position} ${product.title} · ${position}${price}`;
      container.append(row);
    });
  }

    function renderSearch() {
    document.getElementById(PANEL_ID)?.remove();
    const data = inspectSearchPage();
    const panel = document.createElement("aside");
    panel.id = PANEL_ID;
    panel.className = "toca-search-panel";
    const header = document.createElement("header");
    header.innerHTML = "<strong>TOCA · RADAR DE PESQUISA</strong>";
    const close = document.createElement("button");
    close.textContent = "×";
    close.onclick = () => panel.remove();
    header.append(close);
    panel.append(header);
    const body = document.createElement("section");
    body.append(
      field("Busca", data.query),
      field("Visíveis", data.visible_results),
      field("Capturados", data.captured_results),
      field("Patrocinados", data.sponsored_count),
      field("Lojas oficiais", data.official_store_count),
      field("Frete grátis", data.free_shipping_count),
      field("Preço mínimo", data.min_price == null ? null : `R$ ${data.min_price.toFixed(2)}`),
      field("Preço máximo", data.max_price == null ? null : `R$ ${data.max_price.toFixed(2)}`)
    );
    const list = document.createElement("div");
    list.className = "toca-search-list";
    data.products.slice(0, 10).forEach(product => list.append(searchProductCard(product)));
    body.append(list);
    const historyBox = document.createElement("div");
    historyBox.className = "toca-history";
    historyBox.textContent = "CARREGANDO HISTÓRICO...";
    body.append(historyBox);
    chrome.runtime.sendMessage({type: "TOCA_GET_SEARCH_HISTORY", query: data.query}, response => {
      if (response?.ok) renderHistory(historyBox, response.history);
      else historyBox.textContent = "Histórico indisponível: " + (response?.error || "sem conexão");
    });
    const warning = document.createElement("p");
    warning.className = "toca-ray-warning";
    warning.textContent = data.warnings.join(" ");
    body.append(warning);
    const save = document.createElement("button");
    save.className = "toca-ray-save";
    save.textContent = "SALVAR PESQUISA";
    save.onclick = () => {
      save.disabled = true; save.textContent = "SALVANDO...";
      chrome.runtime.sendMessage({type: "TOCA_SAVE_SEARCH_SNAPSHOT", payload: data}, response => {
        save.disabled = false;
        save.textContent = response?.ok ? "PESQUISA SALVA ✓" : "ERRO: " + (response?.error || "sem conexão");
        if (response?.ok) {
          chrome.runtime.sendMessage({type: "TOCA_GET_SEARCH_HISTORY", query: data.query}, historyResponse => {
            if (historyResponse?.ok) renderHistory(historyBox, historyResponse.history);
          });
        }
      });
    };
    body.append(save);
    panel.append(body);
    document.documentElement.append(panel);
    return data;
  }

  function render() {
    return document.querySelectorAll(".ui-search-layout__item").length ? renderSearch() : renderProduct();
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
