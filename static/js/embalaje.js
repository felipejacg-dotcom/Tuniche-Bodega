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
    App.setEmbalajeSubView("traslados");
    if (!App.state.embalaje.loaded) {
        App.renderEmbalajeCurrent();
        App.renderEmbalajeSummary();
        App.renderEmbalajeExistencias();
        App.renderEmbalajeMovimientos();
    }
    await App.refreshEmbalaje();
    if (App.els.embalajeSearch) {
        setTimeout(() => App.els.embalajeSearch.focus(), 120);
    }
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
};

App.renderEmbalajeCurrent = function() {
    const container = App.els.embalajeCurrent;
    if (!container) return;

    const current = App.state.embalaje.selected;
    if (!current) {
        container.innerHTML = `
            <div class="embalaje-current-empty">
                Escanea un QR o selecciona un pallet desde la lista para revisar o trasladar su existencia.
            </div>
        `;
        return;
    }

    const chipClass = App.embalajeChipClass(current.bodega_actual || current.estado || "");
    const destinoSugerido = App.embalajeSuggestDestino(current.bodega_actual || "");

    container.innerHTML = `
        <div class="embalaje-current">
            <div class="embalaje-current-head">
                <div>
                    <div class="embalaje-current-title">${App.escHtml(current.correlativo || current.qr_payload || "Pallet")}</div>
                    <div class="embalaje-current-sub">${App.escHtml(current.codigo_material || "")} · ${App.escHtml(current.descripcion || "")}</div>
                </div>
                <span class="embalaje-chip ${chipClass}">${App.escHtml(current.estado || "ARMADO")}</span>
            </div>

            <div class="embalaje-meta-grid">
                <div class="embalaje-meta-card">
                    <span>Lote</span>
                    <strong>${App.escHtml(current.lote || "-")}</strong>
                </div>
                <div class="embalaje-meta-card">
                    <span>Ubicación</span>
                    <strong>${App.escHtml(current.bodega_actual || "-")}</strong>
                </div>
                <div class="embalaje-meta-card">
                    <span>Cantidad neta</span>
                    <strong>${App.embalajeNumber(current.cantidad_neta)}</strong>
                </div>
                <div class="embalaje-meta-card">
                    <span>Merma</span>
                    <strong>${App.embalajeNumber(current.merma)}</strong>
                </div>
            </div>

            <div class="embalaje-item-meta">
                Armado: ${App.escHtml(current.fecha_armado || "-")} · Usuario: ${App.escHtml(current.usuario_armado || "-")}
            </div>
            <div class="embalaje-item-meta">
                QR: ${App.escHtml(current.qr_payload || current.correlativo || "-")} · Destino sugerido: ${App.escHtml(destinoSugerido || "Sin sugerencia")}
            </div>
        </div>
    `;
};

App.renderEmbalajeSummary = function() {
    const container = App.els.embalajeSummary;
    if (!container) return;

    const resumen = App.state.embalaje.resumen || {};
    const cards = [
        ["Pallets armados", resumen.total_armado || 0],
        ["Stock neto", resumen.stock_actual || 0],
        ["En packing", resumen.en_packing || 0],
        ["En altillo", resumen.en_altillo || 0],
        ["Trasladado hoy", resumen.trasladado_hoy || 0],
        ["Mermas", resumen.mermas || 0],
    ];

    container.innerHTML = `
        <div class="embalaje-summary-grid">
            ${cards.map(([label, value]) => `
                <div class="embalaje-summary-card">
                    <strong>${App.embalajeNumber(value)}</strong>
                    <span>${App.escHtml(label)}</span>
                </div>
            `).join("")}
        </div>
    `;
};

App.renderEmbalajeExistencias = function() {
    const container = App.els.embalajeExistencias;
    if (!container) return;

    const items = App.state.embalaje.existencias || [];
    if (items.length === 0) {
        container.innerHTML = `
            <div class="embalaje-empty">
                No hay existencias para los filtros actuales.
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="embalaje-list">
            ${items.map(item => {
                const chipClass = App.embalajeChipClass(item.bodega_actual || item.estado || "");
                return `
                    <div class="embalaje-item">
                        <div class="embalaje-item-top">
                            <div>
                                <div class="embalaje-item-title">
                                    ${App.escHtml(item.correlativo || item.qr_payload || "Pallet")}
                                </div>
                                <div class="embalaje-item-meta">
                                    ${App.escHtml(item.codigo_material || "")} · ${App.escHtml(item.descripcion || "")}
                                </div>
                            </div>
                            <span class="embalaje-item-chip ${chipClass}">${App.escHtml(item.estado || "ARMADO")}</span>
                        </div>
                        <div class="embalaje-item-meta">
                            Lote: ${App.escHtml(item.lote || "-")} · Fecha: ${App.escHtml(item.fecha_armado || "-")}
                        </div>
                        <div class="embalaje-meta-grid" style="margin-top: 8px;">
                            <div class="embalaje-meta-card">
                                <span>Cantidad neta</span>
                                <strong>${App.embalajeNumber(item.cantidad_neta)}</strong>
                            </div>
                            <div class="embalaje-meta-card">
                                <span>Merma</span>
                                <strong>${App.embalajeNumber(item.merma)}</strong>
                            </div>
                            <div class="embalaje-meta-card">
                                <span>Ubicación</span>
                                <strong>${App.escHtml(item.bodega_actual || "-")}</strong>
                            </div>
                            <div class="embalaje-meta-card">
                                <span>Usuario</span>
                                <strong>${App.escHtml(item.usuario_armado || "-")}</strong>
                            </div>
                        </div>
                        <div class="embalaje-item-footer">
                            <div class="embalaje-item-badges">
                                <span class="embalaje-item-chip ${chipClass}">${App.escHtml(item.bodega_actual || "-")}</span>
                                <span class="embalaje-item-chip">QR: ${App.escHtml(item.qr_payload || "-")}</span>
                            </div>
                            <button type="button" class="embalaje-item-link" onclick="App.selectEmbalajeExistenciaById(${item.id})">Ver</button>
                        </div>
                    </div>
                `;
            }).join("")}
        </div>
    `;
};

App.renderEmbalajeMovimientos = function() {
    const container = App.els.embalajeMovimientos;
    if (!container) return;

    const items = App.state.embalaje.movimientos || [];
    if (items.length === 0) {
        container.innerHTML = `
            <div class="embalaje-empty">
                No hay movimientos recientes para mostrar.
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="embalaje-list">
            ${items.map(item => `
                <div class="embalaje-item">
                    <div class="embalaje-item-top">
                        <div>
                            <div class="embalaje-item-title">${App.escHtml(item.correlativo || "-")}</div>
                            <div class="embalaje-item-meta">
                                ${App.escHtml(item.fecha_hora || "-")} · Usuario: ${App.escHtml(item.usuario || "-")}
                            </div>
                        </div>
                        <span class="embalaje-item-chip">${App.escHtml(item.cantidad || 0)} UND</span>
                    </div>
                    <div class="embalaje-item-meta">
                        ${App.escHtml(item.origen || "-")} → ${App.escHtml(item.destino || "-")}
                    </div>
                    ${item.observacion ? `<div class="embalaje-item-meta">Obs: ${App.escHtml(item.observacion)}</div>` : ""}
                </div>
            `).join("")}
        </div>
    `;
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

App.setEmbalajeSubView = function(viewName) {
    const tabTraslados = document.getElementById("embTabTrasladosBtn");
    const tabConsultas = document.getElementById("embTabConsultasBtn");
    const contentTraslados = document.getElementById("embalajeSubViewTraslados");
    const contentConsultas = document.getElementById("embalajeSubViewConsultas");

    if (!contentTraslados || !contentConsultas) return;

    if (viewName === "traslados") {
        if (tabTraslados) tabTraslados.classList.add("active");
        if (tabConsultas) tabConsultas.classList.remove("active");
        contentTraslados.style.display = "block";
        contentConsultas.style.display = "none";
    } else {
        if (tabTraslados) tabTraslados.classList.remove("active");
        if (tabConsultas) tabConsultas.classList.add("active");
        contentTraslados.style.display = "none";
        contentConsultas.style.display = "block";
        // Al entrar a consultas, refrescar para mostrar datos actualizados
        App.refreshEmbalaje();
    }
};
