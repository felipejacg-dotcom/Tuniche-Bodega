"use strict";

window.App = window.App || {};

App.toDatetimeLocal = function(value) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
};

App.updateCierreTurnoTabs = function() {
    const isDia = App.state.cierreTipoTurno === "dia";
    if (App.els.cierreTurnoDia) {
        App.els.cierreTurnoDia.classList.toggle("active", isDia);
        App.els.cierreTurnoDia.setAttribute("aria-pressed", String(isDia));
    }
    if (App.els.cierreTurnoNoche) {
        App.els.cierreTurnoNoche.classList.toggle("active", !isDia);
        App.els.cierreTurnoNoche.setAttribute("aria-pressed", String(!isDia));
    }
};

App.renderCierrePlaceholder = function() {
    if (!App.els.cierreContent) return;
    App.els.cierreContent.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 5h16M4 12h16M4 19h10"/></svg><p>Selecciona turno y rango para generar el cierre.</p></div>`;
    App.updateCierreActions();
};

App.updateCierreActions = function() {
    const data = App.state.cierreTurno;
    const isGenerated = !!data;
    const isClosed = !!data?.cerrado;
    if (App.els.btnConfirmarCierre) {
        App.els.btnConfirmarCierre.disabled = !isGenerated || isClosed;
        App.els.btnConfirmarCierre.textContent = isClosed ? "Turno cerrado" : "Confirmar cierre";
    }
    if (App.els.btnDownloadCierre) {
        App.els.btnDownloadCierre.disabled = !isClosed;
    }
};

App.setSuggestedCierreRange = function(tipo = App.state.cierreTipoTurno) {
    if (!App.els.cierreDesde || !App.els.cierreHasta) return;
    const now = new Date();
    const start = new Date(now);
    const end = new Date(now);

    if (tipo === "noche") {
        start.setHours(20, 0, 0, 0);
        end.setDate(start.getDate() + 1);
        end.setHours(8, 0, 0, 0);
        if (now.getHours() < 8) {
            start.setDate(start.getDate() - 1);
            end.setDate(end.getDate() - 1);
        }
    } else {
        start.setHours(8, 0, 0, 0);
        end.setHours(20, 0, 0, 0);
    }

    App.els.cierreDesde.value = App.toDatetimeLocal(start);
    App.els.cierreHasta.value = App.toDatetimeLocal(end);
    App.state.cierreTurno = null;
    App.renderCierrePlaceholder();
};

App.initCierreView = function() {
    if (!App.els.cierreDesde?.value || !App.els.cierreHasta?.value) {
        App.setSuggestedCierreRange(App.state.cierreTipoTurno);
    }
    App.updateCierreTurnoTabs();
    App.updateCierreActions();
};

App.setCierreTurno = function(tipoTurno) {
    App.state.cierreTipoTurno = tipoTurno === "noche" ? "noche" : "dia";
    App.updateCierreTurnoTabs();
    App.setSuggestedCierreRange(App.state.cierreTipoTurno);
};

App.getCierreFormValues = function() {
    const tipoTurno = App.state.cierreTipoTurno;
    const desde = App.els.cierreDesde?.value || "";
    const hasta = App.els.cierreHasta?.value || "";
    if (!tipoTurno) throw new Error("Selecciona si el cierre es Día o Noche.");
    if (!desde || !hasta) throw new Error("Completa Desde y Hasta para generar el cierre.");
    if (new Date(desde) >= new Date(hasta)) throw new Error("Desde debe ser anterior a Hasta.");
    const hours = (new Date(hasta) - new Date(desde)) / 36e5;
    if (hours > 24) throw new Error("El rango del cierre no puede superar 24 horas.");
    return { tipoTurno, desde, hasta };
};

App.generateCierreTurno = async function() {
    let values;
    try {
        values = App.getCierreFormValues();
    } catch (e) {
        App.toast(e.message, "warning", 4200);
        return;
    }

    if (App.els.btnGenerarCierre) {
        App.els.btnGenerarCierre.disabled = true;
        App.els.btnGenerarCierre.textContent = "Generando...";
    }
    App.els.cierreContent.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 5h16M4 12h16M4 19h10"/></svg><p>Generando cierre...</p></div>`;

    try {
        const data = await API.getCierreTurno(values.tipoTurno, values.desde, values.hasta);
        if (!data.success) throw new Error(data.message || "No se pudo generar el cierre.");
        App.state.cierreTurno = data;
        App.renderCierreTurno(data);
        App.toast(data.cerrado ? "Este turno ya estaba cerrado." : "Vista previa generada.", data.cerrado ? "warning" : "success");
    } catch (e) {
        App.state.cierreTurno = null;
        App.els.cierreContent.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 3.9 2.8 17a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg><p>${App.escHtml(e.message || "Error generando cierre.")}</p></div>`;
        App.toast(e.message || "Error al generar cierre.", "error", 5000);
    } finally {
        if (App.els.btnGenerarCierre) {
            App.els.btnGenerarCierre.disabled = false;
            App.els.btnGenerarCierre.textContent = "Generar cierre";
        }
        App.updateCierreActions();
    }
};

App.confirmCierreTurno = async function() {
    let values;
    try {
        values = App.getCierreFormValues();
    } catch (e) {
        App.toast(e.message, "warning", 4200);
        return;
    }

    const originalText = App.els.btnConfirmarCierre ? App.els.btnConfirmarCierre.textContent : "";
    try {
        if (App.els.btnConfirmarCierre) {
            App.els.btnConfirmarCierre.disabled = true;
            App.els.btnConfirmarCierre.textContent = "Confirmando...";
        }
        const data = await API.confirmarCierreTurno(values.tipoTurno, values.desde, values.hasta);
        if (!data.success) throw new Error(data.message || "No se pudo confirmar el cierre.");
        App.state.cierreTurno = data;
        App.renderCierreTurno(data);
        App.toast("Cierre confirmado.", "success");
    } catch (e) {
        App.toast(e.message || "No se pudo confirmar el cierre.", "error", 5200);
        await App.generateCierreTurno();
    } finally {
        if (App.els.btnConfirmarCierre) {
            App.els.btnConfirmarCierre.textContent = originalText || "Confirmar cierre";
        }
        App.updateCierreActions();
    }
};

App.renderCierreTurno = function(data) {
    const kpi = data.kpi || {};
    const pendientes = data.pendientes || [];
    const cierre = data.cierre || {};
    const isClosed = !!data.cerrado;
    const responsable = cierre.responsable || data.responsable || App.state.user || "Sin responsable";
    const horaCierre = cierre.hora_cierre || data.hora_generacion || "--:--";

    function buildPendientesHtml(list) {
        if (!list.length) {
            return `<div class="cierre-empty">Sin pendientes en este turno.</div>`;
        }
        return list.map(worker => {
            const artsHtml = worker.articulos.map(art => `
                <div class="cierre-sub-item">
                    <div class="cierre-sub-item-name">${App.escHtml(art.articulo)}</div>
                    <div class="cierre-sub-item-time">${App.escHtml(art.hora_salida)}</div>
                </div>
            `).join("");

            return `
                <div class="cierre-worker-card">
                    <div class="cierre-worker-info">
                        <strong>${App.escHtml(worker.trabajador)}</strong>
                        <span>${App.escHtml(worker.rut)} · ${App.escHtml(worker.area || "Sin área")}</span>
                    </div>
                    <div class="cierre-worker-items">
                        ${artsHtml}
                    </div>
                </div>
            `;
        }).join("");
    }

    const pendientesHtml = buildPendientesHtml(pendientes);

    App.els.cierreContent.innerHTML = `
        <!-- SECCIÓN 1: RESUMEN GENERADO Y KPIS -->
        <div class="card" style="margin-top:10px;">
            <div class="card-header" style="background:#f9fafb;">
                <span class="card-title">Resumen Generado & KPIs</span>
            </div>
            <div class="card-body" style="display:flex; flex-direction:column; gap:12px;">
                <div class="cierre-head" style="border:none; padding:0; background:none;">
                    <div>
                        <div class="cierre-eyebrow">Generado ${App.escHtml(data.hora_generacion || "--:--")}</div>
                        <div class="cierre-title">Turno ${App.escHtml(data.turno || "")} - ${App.escHtml(data.planta_display || data.planta || App.state.planta)}</div>
                        <div class="cierre-range-text">Rango: ${App.escHtml(data.desde || "")} a ${App.escHtml(data.hasta || "")}</div>
                        <div class="cierre-range-text">Responsable: ${App.escHtml(responsable)}</div>
                    </div>
                </div>
                <div class="cierre-status ${isClosed ? "is-closed" : "is-preview"}">
                    ${isClosed
                        ? `Turno cerrado por ${App.escHtml(responsable)} el ${App.escHtml(horaCierre)}.`
                        : "Vista previa sin cerrar. Confirma el cierre para bloquear este turno y habilitar el PDF."}
                </div>
                <div class="cierre-kpi-grid">
                    <div class="cierre-kpi"><strong>${App.escHtml(kpi.total ?? 0)}</strong><span>Movimientos</span></div>
                    <div class="cierre-kpi"><strong>${App.escHtml(kpi.salidas ?? 0)}</strong><span>Salidas</span></div>
                    <div class="cierre-kpi"><strong>${App.escHtml(kpi.devoluciones ?? 0)}</strong><span>Devoluciones</span></div>
                    <div class="cierre-kpi warning"><strong>${App.escHtml(kpi.pendientes ?? 0)}</strong><span>Pendientes</span></div>
                    <div class="cierre-kpi warning"><strong>${App.escHtml(kpi.trabajadores_pendientes ?? 0)}</strong><span>Trabajadores</span></div>
                </div>
                
            </div>
        </div>

        <!-- SECCIÓN 2: PENDIENTES DEL TURNO -->
        <div class="card">
            <div class="card-header" style="background:#fffbeb; border-bottom-color:#fcd34d;">
                <span class="card-title" style="color:var(--warning); font-weight:800;">Pendientes del Turno</span>
            </div>
            <div class="card-body cierre-list">
                ${pendientesHtml}
            </div>
        </div>
    `;
    App.updateCierreActions();
};

App.downloadCierrePdf = async function() {
    if (!App.state.cierreTurno) {
        App.toast("Primero genera el cierre.", "warning");
        return;
    }
    if (!App.state.cierreTurno.cerrado) {
        App.toast("Primero confirma el cierre para habilitar el PDF.", "warning", 4200);
        return;
    }

    let values;
    try {
        values = App.getCierreFormValues();
    } catch (e) {
        App.toast(e.message, "warning", 4200);
        return;
    }

    const originalText = App.els.btnDownloadCierre ? App.els.btnDownloadCierre.textContent : "";
    try {
        if (App.els.btnDownloadCierre) {
            App.els.btnDownloadCierre.disabled = true;
            App.els.btnDownloadCierre.textContent = "Generando PDF...";
        }
        const { blob, filename } = await API.downloadCierreTurnoPdf(values.tipoTurno, values.desde, values.hasta);
        const sanitizedFilename = (filename || "cierre-turno.pdf").replace(/[^a-zA-Z0-9._-]/g, "_");
        const file = new File([blob], sanitizedFilename, { type: "application/pdf" });
        const sucursal = App.state.cierreTurno?.planta_display || App.state.cierreTurno?.planta || App.state.planta || "";

        // 1. Caso: ejecución dentro de la app Android nativa.
        if (window.AndroidApp && typeof window.AndroidApp.sharePdf === "function") {
            const reader = new FileReader();
            reader.onerror = function() {
                App.toast("Error al leer el archivo PDF.", "error");
            };
            reader.onloadend = function() {
                try {
                    const result = typeof reader.result === "string" ? reader.result : "";
                    const base64data = result.split(",")[1];
                    if (!base64data) throw new Error("PDF vacío");
                    
                    // Contrato unificado: (base64, filename, tipo_turno, desde, hasta)
                    window.AndroidApp.sharePdf(base64data, sanitizedFilename, values.tipoTurno, values.desde, values.hasta);
                } catch (e) {
                    App.toast("Error al procesar el archivo en la aplicación.", "error");
                }
            };
            reader.readAsDataURL(blob);
        }
        // 2. Caso: navegador móvil compatible con Web Share
        else if (navigator.canShare && navigator.canShare({ files: [file] })) {
            await navigator.share({
                files: [file],
                title: sanitizedFilename,
                text: `Cierre de turno de la sucursal ${sucursal}`,
            });
            App.toast("Cierre compartido.", "success");
        }
        // 3. Fallback: descarga clásica
        else {
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = sanitizedFilename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
            App.toast("PDF descargado.", "success");
        }
    } catch (e) {
        if (e.name !== "AbortError") {
            App.toast(e.message || "No se pudo descargar o compartir el PDF.", "error", 5000);
        }
    } finally {
        if (App.els.btnDownloadCierre) {
            App.els.btnDownloadCierre.disabled = false;
            App.els.btnDownloadCierre.textContent = originalText || "Descargar PDF";
        }
    }
};
