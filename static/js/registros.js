"use strict";

window.App = window.App || {};

App.loadRegistros = async function() {
    try {
        // Date filters are optional on records history
        const desde = App.els.registrosDesde ? App.els.registrosDesde.value : "";
        const hasta = App.els.registrosHasta ? App.els.registrosHasta.value : "";

        const data = await API.getRegistros(
            App.state.registrosFilter,
            App.state.registrosQuery,
            desde,
            hasta,
            App.state.registrosPage,
            App.state.registrosLimit
        );
        if (data.success) {
            App.state.registros = data.registros;
            App.state.registrosTotalPages = data.total_pages;
            App.state.registrosPage = data.page;

            App.els.kpiTotal.textContent = data.kpi.total;
            App.els.kpiTerreno.textContent = data.kpi.en_terreno;
            App.els.kpiDevueltos.textContent = data.kpi.devueltos;

            App.renderRegistros();
            App.renderRegistrosPagination();
        }
    } catch (e) {
        console.error("Error loading registros:", e);
        App.toast(e.message || "Error cargando registros.", "error", 5000);
    }
};

App.filterRegistros = function(estado) {
    App.state.registrosFilter = estado;
    App.state.registrosPage = 1; // reset page on filter change
    document.querySelectorAll("#viewRegistros .filter-tab").forEach(t => {
        t.classList.toggle("active", t.dataset.estado === estado);
    });
    App.loadRegistros();
};

App.renderRegistros = function() {
    const container = App.els.registrosList;
    if (!container) return;

    if (App.state.registros.length === 0) {
        container.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v6h6"/><path d="M12 7v5l3 2"/></svg><p>Sin registros en este rango</p></div>`;
        return;
    }
    container.innerHTML = App.state.registros.map(r => {
        let cls = "devuelto";
        let badge = `<span class="reg-badge badge-devuelto">Devuelto</span>`;
        if (r.estado === "EN TERRENO") {
            cls = "terreno";
            badge = `<span class="reg-badge badge-terreno">En Terreno</span>`;
        } else if (r.estado === "CONSUMIDO") {
            cls = "consumido";
            badge = `<span class="reg-badge badge-consumido">Consumido</span>`;
        }

        const cantStr = r.cantidad && r.cantidad > 1 ? ` x ${r.cantidad}` : "";

        return `<div class="reg-card ${cls}">
            <div class="reg-top">
                <div class="reg-top-left">
                    <div class="reg-nombre">${App.escHtml(r.trabajador)}</div>
                    <div class="reg-rut">${App.escHtml(r.rut)}</div>
                </div>
                ${badge}
            </div>
            <div class="reg-articulo">${App.escHtml(r.articulo)}${cantStr}</div>
            <div class="reg-meta">
                <span>Salida: ${App.escHtml(r.hora_salida)}</span>
                ${r.hora_entrada !== "---" ? `<span>Entrada: ${App.escHtml(r.hora_entrada)}</span>` : ""}
                <span>${App.escHtml(r.area)}</span>
            </div>
        </div>`;
    }).join("");
};

App.renderRegistrosPagination = function() {
    const container = App.els.registrosPagination;
    if (!container) return;

    const page = App.state.registrosPage;
    const totalPages = App.state.registrosTotalPages;

    if (totalPages <= 1) {
        container.innerHTML = "";
        return;
    }

    container.innerHTML = `
        <div class="cierre-range-ctrls" style="margin-top: 10px; justify-content: center; display: flex; align-items: center; gap: 15px; width: 100%;">
            <button type="button" class="btn-refresh" id="btnPrevRegistros" ${page <= 1 ? "disabled" : ""}>
                &laquo; Anterior
            </button>
            <span style="font-size: 0.8rem; font-weight: 700; color: var(--muted);">Pág. ${page} de ${totalPages}</span>
            <button type="button" class="btn-refresh" id="btnNextRegistros" ${page >= totalPages ? "disabled" : ""}>
                Siguiente &raquo;
            </button>
        </div>
    `;

    const prevBtn = document.getElementById("btnPrevRegistros");
    const nextBtn = document.getElementById("btnNextRegistros");

    if (prevBtn) prevBtn.addEventListener("click", () => App.changeRegistrosPage(page - 1));
    if (nextBtn) nextBtn.addEventListener("click", () => App.changeRegistrosPage(page + 1));
};

App.changeRegistrosPage = function(newPage) {
    if (newPage < 1 || newPage > App.state.registrosTotalPages) return;
    App.state.registrosPage = newPage;
    App.loadRegistros();
};

App.toggleRegistrosDateFilter = function() {
    const container = App.els.registrosDateFilterContainer;
    const btn = App.els.btnToggleDateFilter;
    if (!container) return;

    if (container.style.display === "none") {
        container.style.display = "block";
        if (btn) btn.classList.add("active");
    } else {
        container.style.display = "none";
        if (btn) btn.classList.remove("active");
    }
};

App.applyRegistrosDateFilter = function() {
    App.state.registrosPage = 1;
    
    const desdeVal = App.els.registrosDesde ? App.els.registrosDesde.value : "";
    const hastaVal = App.els.registrosHasta ? App.els.registrosHasta.value : "";
    const kpiLabel = document.querySelector("#viewRegistros .kpi-card:first-child .kpi-label");
    if (kpiLabel) {
        if (desdeVal || hastaVal) {
            kpiLabel.textContent = "Total período";
        } else {
            kpiLabel.textContent = "Total hoy";
        }
    }
    
    App.loadRegistros();
};

App.clearRegistrosDateFilter = function() {
    if (App.els.registrosDesde) App.els.registrosDesde.value = "";
    if (App.els.registrosHasta) App.els.registrosHasta.value = "";
    
    const kpiLabel = document.querySelector("#viewRegistros .kpi-card:first-child .kpi-label");
    if (kpiLabel) kpiLabel.textContent = "Total hoy";
    
    App.state.registrosPage = 1;
    App.loadRegistros();
};
