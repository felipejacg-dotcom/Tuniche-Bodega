"use strict";

window.App = window.App || {};

App.checkSession = async function() {
    try {
        const data = await API.me({ skipAuthHandler: true });
        if (data.success) {
            App.state.user = data.user;
            App.state.planta = data.planta;
            App.unlockApp();
            return true;
        }
    } catch (_) {}
    return false;
};

App.doLogin = async function() {
    const u = App.els.loginUser.value.trim();
    const p = App.els.loginPass.value.trim();
    const pl = App.els.loginPlanta.value;

    App.els.loginError.textContent = "";
    if (!u || !p) { App.els.loginError.textContent = "Completa usuario y contraseña."; return; }

    App.els.btnLogin.disabled = true;
    App.els.btnLogin.textContent = "Conectando...";

    try {
        const data = await API.login(u, p, pl);
        if (data.success) {
            App.state.user = data.user;
            App.state.planta = data.planta;
            App.unlockApp();
        } else {
            App.els.loginError.textContent = data.message || "Credenciales incorrectas.";
            App.vibrate([300]);
        }
    } catch (e) {
        App.els.loginError.textContent = e.message || "Error de conexión. Verifica la red.";
    } finally {
        App.els.btnLogin.disabled = false;
        App.els.btnLogin.textContent = "INGRESAR AL SISTEMA";
    }
};

App.unlockApp = function() {
    App.els.loginScreen.classList.add("hidden");
    App.els.appContent.classList.add("visible");
    const sucursalLabel = App.state.planta === "TUNICHE" ? "Graneros" : App.state.planta;
    App.els.headerPlanta.textContent = `Sucursal: ${sucursalLabel}`;
    App.els.headerPlantaBadge.textContent = sucursalLabel;
    App.showView("operacion");
    App.loadArticulos();
};

App.logout = function() {
    API.logout().catch(() => {});
    App.state.user = null;
    App.state.planta = "TUNICHE";
    App.state.articulos = [];
    App.state.historial = [];
    App.state.cierreTurno = null;
    App.state.scannedArticulos = [];
    if (App.state.scanProcessingIds) App.state.scanProcessingIds.clear();
    if (App.state.scanMutedIds) App.state.scanMutedIds.clear();
    App.els.appContent.classList.remove("visible");
    App.els.loginScreen.classList.remove("hidden");
    App.els.loginPass.value = "";
    App.els.loginError.textContent = "";

    if (window.AndroidApp && typeof window.AndroidApp.clearSessionCookies === "function") {
        window.AndroidApp.clearSessionCookies();
    }
};

App.formatRutLive = function(raw) {
    const clean = raw.replace(/[^0-9kK]/g, "").toUpperCase();
    if (clean.length === 0) return "";
    if (clean.length === 1) return clean;

    const dv = clean.slice(-1);
    const body = clean.slice(0, -1);
    if (body.length === 0) return dv;

    const bodyFmt = body.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return `${bodyFmt}-${dv}`;
};

App.onRutInput = function(e) {
    const el = e.target;
    const before = el.value;
    const cursorBefore = el.selectionStart;

    const realBefore = before.slice(0, cursorBefore).replace(/[^0-9kK]/gi, "").length;
    const formatted = App.formatRutLive(before);

    if (formatted !== before) {
        el.value = formatted;

        let realCount = 0;
        let newCursor = 0;
        for (let i = 0; i < formatted.length; i++) {
            if (/[0-9kK]/i.test(formatted[i])) realCount++;
            newCursor = i + 1;
            if (realCount >= realBefore) break;
        }
        el.setSelectionRange(newCursor, newCursor);
    }
    App.updateConfirmButton();
};

App.init = function() {
    // Initialize DOM references
    App.initEls();

    // Login
    App.els.btnLogin.addEventListener("click", App.doLogin);
    App.els.loginPass.addEventListener("keydown", e => { if (e.key === "Enter") App.doLogin(); });

    // Logout
    App.els.btnLogout.addEventListener("click", App.logout);

    // Mode selector
    App.els.modeSalidaBtn.addEventListener("click", () => App.updateMode("SALIDA"));
    App.els.modeDevolucionBtn.addEventListener("click", () => App.updateMode("DEVOLUCION"));

    // Carnet modal
    App.els.btnScanCarnet.addEventListener("click", App.openCarnetModal);
    App.els.btnCloseCarnet.addEventListener("click", App.closeCarnetModal);
    App.els.carnetModal.addEventListener("click", e => { if (e.target === App.els.carnetModal) App.closeCarnetModal(); });

    // Cierre de turno
    if (App.els.btnDownloadCierre) {
        App.els.btnDownloadCierre.addEventListener("click", App.downloadCierrePdf);
    }
    if (App.els.cierreDesde) App.els.cierreDesde.addEventListener("input", () => { App.state.cierreTurno = null; App.renderCierrePlaceholder(); });
    if (App.els.cierreHasta) App.els.cierreHasta.addEventListener("input", () => { App.state.cierreTurno = null; App.renderCierrePlaceholder(); });

    // Laser input for articles
    Scanner.initLaser(App.els.laserInput, App.onArticuloScanned);
    setTimeout(() => App.els.laserInput.focus(), 500);

    // Confirm button
    App.els.btnConfirm.addEventListener("click", App.confirmOperation);

    // Form change & RUT formatting
    App.els.inputRut.addEventListener("input", App.onRutInput);
    App.els.inputRut.addEventListener("change", async (e) => {
        const rutFmt = e.target.value.trim();
        if (rutFmt.length >= 11) {
            try {
                const data = await API.buscarTrabajador(rutFmt);
                if (data.success) {
                    App.els.inputNombre.value = data.nombre;
                    const sel = App.els.inputArea;
                    for (let i = 0; i < sel.options.length; i++) {
                        if (sel.options[i].value === data.area) {
                            sel.selectedIndex = i; break;
                        }
                    }
                }
            } catch (_) {}
            if (App.state.mode === "DEVOLUCION") {
                App.cargarPendientes(rutFmt);
            }
            App.updateConfirmButton();
        }
    });
    App.els.inputNombre.addEventListener("input", App.updateConfirmButton);
    App.els.inputArea.addEventListener("change", App.updateConfirmButton);

    // Stock search with 300ms debounce
    if (App.els.stockSearch) {
        App.els.stockSearch.addEventListener("input", App.debounce(() => App.renderStockList(), 300));
    }

    // Registros search with 300ms debounce
    if (App.els.registrosSearch) {
        App.els.registrosSearch.addEventListener("input", App.debounce((e) => {
            App.state.registrosQuery = e.target.value;
            App.state.registrosPage = 1;
            App.loadRegistros();
        }, 300));
    }

    // Init confirm button state
    App.updateMode("SALIDA");
    App.renderHistorial();

    // Check session on load
    App.checkSession();
};

document.addEventListener("DOMContentLoaded", App.init);
