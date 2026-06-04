"use strict";

window.App = window.App || {};

App.state = {
    user: null,
    planta: "TUNICHE",
    mode: "SALIDA",           // "SALIDA" | "DEVOLUCION"
    scanMethod: "laser",      // "laser" | "camera"
    currentWorker: null,      // { rut }
    currentArticulo: null,    // { id, descripcion, stock }
    articulos: [],            // cache de /api/articulos
    scannedArticulos: [],     // carro de multi-escaneo para salida masiva
    historial: [],            // historial de sesión local
    registros: [],            // cargado de /api/registros
    registrosFilter: "",      // "EN TERRENO" | "DEVUELTO" | ""
    registrosQuery: "",
    registrosPage: 1,         // Paginación de registros
    registrosLimit: 50,       // Paginación de registros
    registrosTotalPages: 1,   // Paginación de registros
    cierreTurno: null,
    cierreTipoTurno: "dia",
    stockFilter: "all",
    stockQuery: "",
    scanProcessingIds: new Set(),
    scanMutedIds: new Map(),
};

App.$ = (id) => document.getElementById(id);

App.escHtml = function(str) {
    return String(str ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#x27;")
        .replace(/\//g, "&#x2F;");
};

App.debounce = function(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
};

App.els = {};

App.initEls = function() {
    const $ = App.$;
    App.els = {
        loginScreen: $("loginScreen"),
        loginError: $("loginError"),
        loginUser: $("loginUser"),
        loginPass: $("loginPass"),
        loginPlanta: $("loginPlanta"),
        btnLogin: $("btnLogin"),
        appContent: $("appContent"),
        headerPlanta: $("headerPlanta"),
        headerPlantaBadge: $("headerPlantaBadge"),
        btnLogout: $("btnLogout"),
        // Operacion
        modeSalidaBtn: $("modeSalidaBtn"),
        modeDevolucionBtn: $("modeDevolucionBtn"),
        btnScanCarnet: $("btnScanCarnet"),
        inputRut: $("inputRut"),
        inputNombre: $("inputNombre"),
        inputArea: $("inputArea"),
        tabLaser: $("tabLaser"),
        tabCamara: $("tabCamara"),
        tabManual: $("tabManual"),
        laserInput: $("laserInput"),
        camaraSection: $("camaraSection"),
        manualSection: $("manualSection"),
        manualSearchInput: $("manualSearchInput"),
        manualSearchResults: $("manualSearchResults"),
        articuloDisplay: $("articuloDisplay"),
        articuloNombre: $("articuloNombre"),
        articuloStock: $("articuloStock"),
        articuloIcon: $("articuloIcon"),
        articleScanCard: $("articleScanCard"),
        btnConfirm: $("btnConfirm"),
        historialList: $("historialList"),
        histCount: $("histCount"),
        // Stock
        stockSearch: $("stockSearch"),
        stockList: $("stockList"),
        // Registros
        registrosSearch: $("registrosSearch"),
        registrosList: $("registrosList"),
        registrosPagination: $("registrosPagination"),
        kpiTotal: $("kpiTotal"),
        kpiTerreno: $("kpiTerreno"),
        kpiDevueltos: $("kpiDevueltos"),
        viewCierre: $("viewCierre"),
        cierreContent: $("cierreContent"),
        cierreDesde: $("cierreDesde"),
        cierreHasta: $("cierreHasta"),
        cierreTurnoDia: $("cierreTurnoDia"),
        cierreTurnoNoche: $("cierreTurnoNoche"),
        btnGenerarCierre: $("btnGenerarCierre"),
        btnConfirmarCierre: $("btnConfirmarCierre"),
        btnDownloadCierre: $("btnDownloadCierre"),
        // Modal carnet
        carnetModal: $("carnetModal"),
        btnCloseCarnet: $("btnCloseCarnet"),
        // Contenedores dinámicos
        devolucionesPendientesSection: $("devolucionesPendientesSection"),
        devolucionesPendientesList: $("devolucionesPendientesList"),
        multiScanSection: $("multiScanSection"),
        multiScanList: $("multiScanList"),
        // Overlays
        loadingOverlay: $("loadingOverlay"),
        toastContainer: $("toastContainer"),
    };
};

App.toast = function(msg, type = "info", duration = 3200) {
    const container = App.els.toastContainer || document.getElementById("toastContainer");
    if (!container) return;
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    requestAnimationFrame(() => {
        requestAnimationFrame(() => el.classList.add("show"));
    });
    setTimeout(() => {
        el.classList.remove("show");
        setTimeout(() => el.remove(), 350);
    }, duration);
};

App.showLoading = function() {
    if (App.els.loadingOverlay) App.els.loadingOverlay.classList.add("active");
};

App.hideLoading = function() {
    if (App.els.loadingOverlay) App.els.loadingOverlay.classList.remove("active");
};

App.vibrate = function(pattern) {
    if (navigator.vibrate) App.vibrateInternal(pattern);
};

App.vibrateInternal = function(pattern) {
    try {
        if (navigator.vibrate) navigator.vibrate(pattern);
    } catch (_) {}
};

App.shouldNotifyDuplicateScan = function(id, cooldownMs = 2500) {
    const now = Date.now();
    const last = App.state.scanMutedIds.get(id) || 0;
    if (now - last < cooldownMs) return false;
    App.state.scanMutedIds.set(id, now);
    return true;
};

App.stopArticleScanner = function(reason = "", options = {}) {
    Scanner.stopArticleCamera();
    if (App.state.scanMethod === "camera") {
        if (typeof App.setScanMethod === "function") {
            App.setScanMethod("laser", options);
        } else {
            App.state.scanMethod = "laser";
        }
    } else if (options.focusLaser === true) {
        setTimeout(() => {
            if (App.els.laserInput) App.els.laserInput.focus();
        }, 100);
    }
};

App.showView = function(name) {
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
    const viewId = { operacion: "viewOperacion", stock: "viewStock", registros: "viewRegistros", cierre: "viewCierre" }[name];
    const navId = { operacion: "navOperacion", stock: "navStock", registros: "navRegistros", cierre: "navCierre" }[name];
    if (viewId) {
        const el = App.$(viewId);
        if (el) el.classList.add("active");
    }
    if (navId) {
        const el = App.$(navId);
        if (el) el.classList.add("active");
    }

    if (name !== "operacion") {
        App.stopArticleScanner("view_change", { focusLaser: false });
    }

    if (name === "stock") App.renderStockList();
    if (name === "registros") App.loadRegistros();
    if (name === "cierre") App.initCierreView();
};
