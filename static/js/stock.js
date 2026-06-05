"use strict";

window.App = window.App || {};

App.loadArticulos = async function() {
    try {
        const data = await API.getArticulos();
        if (data.success) App.state.articulos = data.articulos;
    } catch (e) {
        console.error("Error loading articulos:", e);
        App.toast(e.message || "Error cargando artículos.", "error", 5000);
    }
};

App.filterStock = function(filter) {
    App.state.stockFilter = filter;
    document.querySelectorAll("#viewStock .filter-tab").forEach(t => {
        t.classList.toggle("active", t.dataset.filter === filter);
    });
    App.renderStockList();
};

App.renderStockList = function() {
    const query = App.els.stockSearch ? App.els.stockSearch.value.toLowerCase().trim() : "";
    let items = [...App.state.articulos];

    if (query) {
        items = items.filter(a =>
            a.descripcion.toLowerCase().includes(query) ||
            (a.codigo_material && a.codigo_material.toLowerCase().includes(query)) ||
            (a.talla && a.talla.toLowerCase().includes(query))
        );
    }
    if (App.state.stockFilter === "low") items = items.filter(a => a.stock_disponible > 0 && a.limite_alerta && a.stock_disponible <= a.limite_alerta);
    if (App.state.stockFilter === "zero") items = items.filter(a => a.stock_disponible <= 0);
    if (App.state.stockFilter === "available") items = items.filter(a => a.stock_disponible > 0);

    const container = App.els.stockList;
    if (!container) return;

    if (items.length === 0) {
        container.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z"/><path d="M16 7V5a2 2 0 0 0-4 0v2"/></svg><p>Sin artículos</p></div>`;
        return;
    }

    container.innerHTML = items.map(a => {
        const s = a.stock_disponible;
        const isLow = a.limite_alerta && s > 0 && s <= a.limite_alerta;
        const cls = s <= 0 ? "zero" : isLow ? "low" : "ok";
        const sku = a.codigo_material ? `<span style="font-weight:600;color:var(--muted);font-size:0.68rem;letter-spacing:0.04em;">${App.escHtml(a.codigo_material)}</span><span style="color:var(--border);margin:0 4px;">·</span>` : "";
        const badgeLabel = s <= 0 ? "Agotado" : String(s);
        return `<div class="stock-item">
            <div class="stock-info">
                <div class="stock-nombre">${App.escHtml(a.descripcion)}</div>
                <div class="stock-sub">${sku}Talla ${App.escHtml(a.talla || "—")} · ${App.escHtml(a.medida || "")}</div>
            </div>
            <div class="stock-badge ${cls}">${badgeLabel}</div>
        </div>`;
    }).join("");
};
