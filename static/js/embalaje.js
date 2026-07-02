"use strict";

window.App = window.App || {};

App.state = App.state || {};
App.state.embalaje = App.state.embalaje || {
    loaded: false,
    initialized: false,
    loading: false,
    scannerOpen: false,
    selected: null,
    resumen: null,
    existencias: [],
    movimientos: [],
    filtros: {
        texto: "",
        ubicacion: "Todas",
        estado: "Todos",
    },
};

App.embalajeNumber = function(value) {
    const num = Number(value || 0);
    try {
        return num.toLocaleString("es-CL");
    } catch (_) {
        return String(num);
    }
};

App.embalajeChipClass = function(text) {
    const value = String(text || "").toUpperCase();
    if (value.includes("PACKING")) return "packing";
    if (value.includes("ALTILLO")) return "altillo";
    if (value.includes("BODEGA")) return "bodega";
    if (value.includes("ARMADO")) return "armado";
    return "";
};

App.embalajeSuggestDestino = function(bodegaActual) {
    const value = String(bodegaActual || "").toUpperCase();
    if (value.startsWith("PACKING")) return value.replace("PACKING", "ALTILLO");
    if (value.startsWith("ALTILLO")) return value.replace("ALTILLO", "BODEGA");
    if (value.startsWith("BODEGA")) return value.replace("BODEGA", "PACKING");
    return "";
};

App.initEmbalajeView = function() {
    if (App.state.embalaje.initialized) return;
    App.state.embalaje.initialized = true;

    if (App.els.embalajeSearch) {
        App.els.embalajeSearch.addEventListener("input", App.debounce(() => {
            App.state.embalaje.filtros.texto = App.els.embalajeSearch.value.trim();
            App.refreshEmbalaje();
        }, 250));
        App.els.embalajeSearch.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                App.consultarEmbalaje();
            }
        });
    }

    if (App.els.embalajeQr) {
        App.els.embalajeQr.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                App.consultarEmbalaje(true);
            }
        });
    }

    if (App.els.embalajeUbicacion) {
        App.els.embalajeUbicacion.addEventListener("change", () => App.refreshEmbalaje());
    }
    if (App.els.embalajeEstado) {
        App.els.embalajeEstado.addEventListener("change", () => App.refreshEmbalaje());
    }
    if (App.els.embalajeConsultarBtn) {
        App.els.embalajeConsultarBtn.addEventListener("click", () => App.consultarEmbalaje());
    }
    if (App.els.embalajeTrasladarBtn) {
        App.els.embalajeTrasladarBtn.addEventListener("click", () => App.trasladarEmbalaje());
    }
    if (App.els.embalajeRefreshBtn) {
        App.els.embalajeRefreshBtn.addEventListener("click", () => App.refreshEmbalaje());
    }
    if (App.els.embalajeScanBtn) {
        App.els.embalajeScanBtn.addEventListener("click", () => App.toggleEmbalajeScanner());
    }
};

App.loadEmbalajeView = async function() {
    App.initEmbalajeView();
    App.setEmbalajeView("dashboard");

    // Set greeting planta
    const greet = document.getElementById("embGreetingPlanta");
    if (greet) greet.textContent = "Planta " + (App.state.planta || "");
    const masNombre = document.getElementById("embMasNombre");
    if (masNombre) masNombre.textContent = App.state.usuario || "Operario";

    if (!App.state.embalaje.loaded) {
        App.renderEmbalajeCurrent();
        App.renderEmbalajeSummary();
        App.renderEmbalajeExistencias();
        App.renderEmbalajeMovimientos();
        App.renderEmbDashboardMovimientos();
    }
    await App.refreshEmbalaje();
};

App.getEmbalajeFilters = function() {
    return {
        texto: App.els.embalajeSearch ? App.els.embalajeSearch.value.trim() : "",
        ubicacion: App.els.embalajeUbicacion ? App.els.embalajeUbicacion.value : "Todas",
        estado: App.els.embalajeEstado ? App.els.embalajeEstado.value : "Todos",
    };
};

App.refreshEmbalaje = async function() {
    if (App.state.embalaje.loading) return;

    const filtros = App.getEmbalajeFilters();
    App.state.embalaje.filtros = filtros;
    App.state.embalaje.loading = true;
    App.showLoading();

    try {
        const [resumenResp, existenciasResp, movimientosResp] = await Promise.all([
            API.getEmbalajeResumen(filtros.texto, filtros.ubicacion, filtros.estado),
            API.getEmbalajeExistencias(filtros.texto, filtros.ubicacion, filtros.estado),
            API.getEmbalajeMovimientos(filtros.texto, 80),
        ]);

        App.state.embalaje.resumen = resumenResp.resumen || {};
        App.state.embalaje.existencias = existenciasResp.existencias || [];
        App.state.embalaje.movimientos = movimientosResp.movimientos || [];

        if (App.state.embalaje.selected) {
            const selectedId = App.state.embalaje.selected.id;
            const refreshed = App.state.embalaje.existencias.find(item => item.id === selectedId);
            if (refreshed) {
                App.state.embalaje.selected = refreshed;
            }
        }

        App.state.embalaje.loaded = true;
        App.renderEmbalajeDashboard();
    } catch (e) {
        console.error("Error cargando embalaje:", e);
        App.toast(e.message || "No se pudo cargar embalaje.", "error");
    } finally {
        App.hideLoading();
        App.state.embalaje.loading = false;
    }
};

App.renderEmbalajeDashboard = function() {
    App.renderEmbalajeCurrent();
    App.renderEmbalajeSummary();
    App.renderEmbalajeExistencias();
    App.renderEmbalajeMovimientos();
    App.renderEmbDashboardMovimientos();
    App.renderEmbReportes();
};

App.renderEmbalajeCurrent = function() {
    const container = App.els.embalajeCurrent;
    if (!container) return;

    const current = App.state.embalaje.selected;
    if (!current) {
        container.innerHTML = `
            <div class="emb-pallet-info-card" style="background:#f9fafb; border-color:#e5e7eb;">
                <div class="emb-pallet-info-head">
                    <div class="emb-pallet-info-name" style="color:#9ca3af;">Ningún pallet seleccionado</div>
                </div>
                <div style="font-size:12px; color:#9ca3af;">Escanea o busca un código para ver el detalle.</div>
            </div>
        `;
        return;
    }

    const estado = current.estado || "ARMADO";
    const destinoSugerido = App.embalajeSuggestDestino(current.bodega_actual || "");
    if (App.els.embalajeDestino && destinoSugerido) {
        App.els.embalajeDestino.value = destinoSugerido;
    }

    container.innerHTML = `
        <div class="emb-pallet-info-card">
            <div class="emb-pallet-info-head">
                <div class="emb-pallet-info-name">${App.escHtml(current.correlativo || current.qr_payload || "Pallet")}</div>
                <div class="emb-pallet-info-badge">${App.escHtml(estado)}</div>
            </div>
            <div class="emb-pallet-info-grid">
                <div class="emb-pallet-info-item">
                    <div class="emb-pallet-info-label">Código</div>
                    <div class="emb-pallet-info-value">${App.escHtml(current.codigo_material || "-")}</div>
                </div>
                <div class="emb-pallet-info-item">
                    <div class="emb-pallet-info-label">Lote</div>
                    <div class="emb-pallet-info-value">${App.escHtml(current.lote || "-")}</div>
                </div>
                <div class="emb-pallet-info-item">
                    <div class="emb-pallet-info-label">Ubicación actual</div>
                    <div class="emb-pallet-info-value">${App.escHtml(current.bodega_actual || "-")}</div>
                </div>
                <div class="emb-pallet-info-item">
                    <div class="emb-pallet-info-label">Cantidad neta</div>
                    <div class="emb-pallet-info-value">${App.embalajeNumber(current.cantidad_neta)}</div>
                </div>
                <div class="emb-pallet-info-item">
                    <div class="emb-pallet-info-label">Merma</div>
                    <div class="emb-pallet-info-value">${App.embalajeNumber(current.merma)}</div>
                </div>
                <div class="emb-pallet-info-item">
                    <div class="emb-pallet-info-label">Destino sugerido</div>
                    <div class="emb-pallet-info-value" style="color:#27ae60;">${App.escHtml(destinoSugerido || "-")}</div>
                </div>
            </div>
        </div>
    `;
};

App.renderEmbalajeSummary = function() {
    // Update the KPI value elements in the static dashboard cards
    const resumen = App.state.embalaje.resumen || {};
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = App.embalajeNumber(val); };
    set("kpiTotalArmado", resumen.total_armado || 0);
    set("kpiStockActual", resumen.stock_actual || 0);
    set("kpiEnPacking", resumen.en_packing || 0);
    set("kpiEnAltillo", resumen.en_altillo || 0);
    set("kpiTrasladado", resumen.trasladado_hoy || 0);
    set("kpiMermas", resumen.mermas || 0);
    // Also update Reportes view
    App.renderEmbReportes();
};

App.renderEmbReportes = function() {
    const resumen = App.state.embalaje.resumen || {};
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = App.embalajeNumber(val); };
    set("repTotalArmado", resumen.total_armado || 0);
    set("repStockActual", resumen.stock_actual || 0);
    set("repEnPacking", resumen.en_packing || 0);
    set("repEnAltillo", resumen.en_altillo || 0);
    set("repTrasladado", resumen.trasladado_hoy || 0);
    set("repMermas", resumen.mermas || 0);
};

App.renderEmbalajeExistencias = function() {
    const container = App.els.embalajeExistencias;
    if (!container) return;

    const items = App.state.embalaje.existencias || [];
    if (items.length === 0) {
        container.innerHTML = `<div class="emb-empty"><p>No hay pallets para los filtros actuales.</p></div>`;
        return;
    }

    const dotClass = (ubicacion) => {
        const u = String(ubicacion || "").toUpperCase();
        if (u.includes("PACKING")) return "dot-packing";
        if (u.includes("ALTILLO")) return "dot-altillo";
        if (u.includes("BODEGA")) return "dot-bodega";
        return "dot-armado";
    };
    const badgeClass = (ubicacion) => {
        const u = String(ubicacion || "").toUpperCase();
        if (u.includes("PACKING")) return "badge-packing";
        if (u.includes("ALTILLO")) return "badge-altillo";
        if (u.includes("BODEGA")) return "badge-bodega";
        return "badge-armado";
    };

    container.innerHTML = `<div class="emb-list">${items.map(item => `
        <div class="emb-pallet-row" onclick="App.selectEmbalajeExistenciaById(${item.id}); App.setEmbalajeView('movimientos');">
            <div class="emb-pallet-dot ${dotClass(item.bodega_actual)}"></div>
            <div class="emb-pallet-body">
                <div class="emb-pallet-code">${App.escHtml(item.correlativo || item.qr_payload || "Pallet")}</div>
                <div class="emb-pallet-desc">${App.escHtml(item.codigo_material || "")} · ${App.escHtml(item.descripcion || "")}</div>
                <div class="emb-pallet-meta">Lote: ${App.escHtml(item.lote || "-")} · Neto: ${App.embalajeNumber(item.cantidad_neta)}</div>
            </div>
            <span class="emb-pallet-badge ${badgeClass(item.bodega_actual)}">${App.escHtml(item.bodega_actual || "ARMADO")}</span>
        </div>
    `).join("")}</div>`;
};

App.renderEmbalajeMovimientos = function() {
    // Full list in Reportes view
    const container = App.els.embalajeMovimientos;
    if (!container) return;

    const items = App.state.embalaje.movimientos || [];
    if (items.length === 0) {
        container.innerHTML = `<div class="emb-empty"><p>No hay movimientos para mostrar.</p></div>`;
        return;
    }

    container.innerHTML = `<div class="emb-list">${items.map(item => `
        <div class="emb-pallet-row" style="cursor:default;">
            <div class="emb-mov-arrow">
                <svg viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2">
                    <polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/>
                    <polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>
                </svg>
            </div>
            <div class="emb-pallet-body">
                <div class="emb-pallet-code">${App.escHtml(item.correlativo || "-")}</div>
                <div class="emb-pallet-desc">${App.escHtml(item.origen || "-")} → ${App.escHtml(item.destino || "-")}</div>
                <div class="emb-pallet-meta">${App.escHtml(item.fecha_hora || "-")} · ${App.escHtml(item.usuario || "-")}</div>
            </div>
            <span class="emb-pallet-badge badge-altillo">${App.escHtml(item.cantidad || 0)} uds</span>
        </div>
    `).join("")}</div>`;
};

App.renderEmbDashboardMovimientos = function() {
    // Last 5 movements in Dashboard card
    const container = document.getElementById("embDashboardMovimientos");
    if (!container) return;

    const items = (App.state.embalaje.movimientos || []).slice(0, 5);
    if (items.length === 0) {
        container.innerHTML = `<div class="emb-empty"><p>Sin movimientos recientes.</p></div>`;
        return;
    }

    container.innerHTML = items.map(item => `
        <div class="emb-mov-item">
            <div class="emb-mov-arrow">
                <svg viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2">
                    <polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/>
                    <polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>
                </svg>
            </div>
            <div class="emb-mov-body">
                <div class="emb-mov-correlativo">${App.escHtml(item.correlativo || "-")}</div>
                <div class="emb-mov-route">${App.escHtml(item.origen || "-")} → ${App.escHtml(item.destino || "-")}</div>
            </div>
            <div class="emb-mov-time">${App.escHtml((item.fecha_hora || "-").split(" ")[1] || item.fecha_hora || "-")}</div>
        </div>
    `).join("");
};

App.selectEmbalajeExistenciaById = function(id) {
    const item = (App.state.embalaje.existencias || []).find(row => row.id === id);
    if (!item) return;

    App.state.embalaje.selected = item;
    if (App.els.embalajeQr) {
        App.els.embalajeQr.value = item.qr_payload || item.correlativo || item.codigo_material || "";
    }
    if (App.els.embalajeDestino) {
        App.els.embalajeDestino.value = App.embalajeSuggestDestino(item.bodega_actual || "");
    }
    App.renderEmbalajeCurrent();
    App.toast("Pallet cargado en el detalle.", "info", 1400);
};

App.consultarEmbalaje = async function(forceExact = false) {
    const qr = App.els.embalajeQr ? App.els.embalajeQr.value.trim() : "";
    const texto = App.els.embalajeSearch ? App.els.embalajeSearch.value.trim() : "";

    if (!qr && !texto) {
        await App.refreshEmbalaje();
        return;
    }

    if (!qr && texto && !forceExact) {
        await App.refreshEmbalaje();
        return;
    }

    const clave = qr || texto;
    App.showLoading();
    try {
        const data = await API.getEmbalajeExistencia(clave);
        App.state.embalaje.selected = data.existencia || null;
        if (App.state.embalaje.selected) {
            if (App.els.embalajeDestino) {
                App.els.embalajeDestino.value = App.embalajeSuggestDestino(App.state.embalaje.selected.bodega_actual || "");
            }
            if (App.els.embalajeQr) {
                App.els.embalajeQr.value = App.state.embalaje.selected.qr_payload || App.state.embalaje.selected.correlativo || clave;
            }
        }
        App.renderEmbalajeCurrent();
        App.toast("Pallet encontrado.", "success", 1800);
    } catch (e) {
        App.state.embalaje.selected = null;
        App.renderEmbalajeCurrent();
        App.toast(e.message || "No se encontró el pallet.", "warning");
        await App.refreshEmbalaje();
    } finally {
        App.hideLoading();
    }
};

App.trasladarEmbalaje = async function() {
    const destino = App.els.embalajeDestino ? App.els.embalajeDestino.value.trim() : "";
    const observacion = App.els.embalajeObservacion ? App.els.embalajeObservacion.value.trim() : "";
    const clave = App.els.embalajeQr ? App.els.embalajeQr.value.trim() : "";
    const current = App.state.embalaje.selected || (clave ? (App.state.embalaje.existencias || []).find(item => {
        const key = String(item.qr_payload || item.correlativo || item.codigo_material || "").trim();
        return key === clave;
    }) : null);

    if (!current) {
        App.toast("Primero consulta o selecciona un pallet.", "warning");
        return;
    }
    if (!destino) {
        App.toast("Selecciona una bodega destino.", "warning");
        return;
    }
    if (String(current.bodega_actual || "").trim() === destino) {
        App.toast("La bodega destino debe ser distinta a la actual.", "warning");
        return;
    }

    App.showLoading();
    try {
        const data = await API.registrarEmbalajeTraslado({
            clave: current.qr_payload || current.correlativo || current.codigo_material,
            bodega_destino: destino,
            observacion,
        });
        if (data.success) {
            App.vibrate([80, 40, 80]);
            App.toast(data.message || "Traslado registrado.", "success", 3200);
            if (App.els.embalajeObservacion) App.els.embalajeObservacion.value = "";
            App.state.embalaje.selected = {
                ...(App.state.embalaje.selected || current),
                bodega_actual: destino,
                estado: data.traslado?.estado || current.estado,
            };
            if (App.els.embalajeQr) {
                App.els.embalajeQr.value = data.traslado?.qr_payload || current.qr_payload || current.correlativo || "";
            }
            await App.refreshEmbalaje();
            App.renderEmbalajeCurrent();
        } else {
            App.toast(data.message || "No se pudo registrar el traslado.", "error");
        }
    } catch (e) {
        App.toast(e.message || "No se pudo registrar el traslado.", "error", 4000);
    } finally {
        App.hideLoading();
    }
};

App.onEmbalajeQrScanned = function(text) {
    const value = String(text || "").trim();
    if (!value) return;
    if (App.els.embalajeQr) App.els.embalajeQr.value = value;
    App.stopEmbalajeScanner("scan");
    App.consultarEmbalaje(true);
};

App.startEmbalajeScanner = async function() {
    if (App.state.embalaje.scannerOpen) return;
    App.state.embalaje.scannerOpen = true;
    if (App.els.embalajeScannerWrap) App.els.embalajeScannerWrap.style.display = "block";

    try {
        await Scanner.startArticleCamera("readerEmbalaje", App.onEmbalajeQrScanned);
    } catch (e) {
        App.state.embalaje.scannerOpen = false;
        if (App.els.embalajeScannerWrap) App.els.embalajeScannerWrap.style.display = "none";
        App.toast("No se pudo iniciar la cámara.", "error");
        console.error(e);
    }
};

App.stopEmbalajeScanner = function() {
    App.state.embalaje.scannerOpen = false;
    if (App.els.embalajeScannerWrap) App.els.embalajeScannerWrap.style.display = "none";
    if (typeof Scanner !== "undefined" && typeof Scanner.stopArticleCamera === "function") {
        Scanner.stopArticleCamera();
    }
};

App.toggleEmbalajeScanner = function() {
    if (App.state.embalaje.scannerOpen) {
        App.stopEmbalajeScanner("toggle");
    } else {
        App.startEmbalajeScanner();
    }
};

App.setEmbalajeView = function(viewName) {
    const views = ["dashboard", "armados", "movimientos", "reportes", "mas"];
    const navIds = ["embNavDashboard", "embNavArmados", "embNavMovimientos", "embNavReportes", "embNavMas"];

    views.forEach((name, i) => {
        const el = document.getElementById("embView" + name.charAt(0).toUpperCase() + name.slice(1));
        const nav = document.getElementById(navIds[i]);
        if (el) el.style.display = name === viewName ? "block" : "none";
        if (nav) nav.classList.toggle("active", name === viewName);
    });

    // Stop scanner if leaving movimientos
    if (viewName !== "movimientos" && App.state.embalaje.scannerOpen) {
        App.stopEmbalajeScanner();
    }

    // Load data for specific views
    if (viewName === "reportes" && App.state.embalaje.loaded) {
        App.renderEmbalajeMovimientos();
        App.renderEmbReportes();
    }
};

// Backward compat alias
App.setEmbalajeSubView = function(viewName) {
    if (viewName === "traslados") App.setEmbalajeView("movimientos");
    else if (viewName === "consultas") App.setEmbalajeView("armados");
    else App.setEmbalajeView(viewName);
};
