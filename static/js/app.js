"use strict";

/**
 * app.js — Logica principal de la SPA Tuniche Bodega.
 * Depende de: api.js y scanner.js (cargados antes).
 */
const App = (() => {
    // ── Estado ────────────────────────────────────────────────────
    const state = {
        user: null,
        planta: "TUNICHE",
        mode: "SALIDA",           // "SALIDA" | "DEVOLUCION"
        scanMethod: "laser",      // "laser" | "camera"
        currentWorker: null,      // { rut, nombre, area }
        currentArticulo: null,    // { id, descripcion, stock }
        articulos: [],            // cache from /api/articulos
        historial: [],            // session history
        registros: [],            // loaded from /api/registros
        registrosFilter: "",      // "EN TERRENO" | "DEVUELTO" | ""
        registrosQuery: "",
        stockFilter: "all",
        stockQuery: "",
    };

    // ── DOM Refs ──────────────────────────────────────────────────
    const $ = (id) => document.getElementById(id);

    const els = {
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
        modeBanner: $("modeBanner"),
        modeIcon: $("modeIcon"),
        modeName: $("modeName"),
        modeToggle: $("modeToggle"),
        btnScanCarnet: $("btnScanCarnet"),
        inputRut: $("inputRut"),
        inputNombre: $("inputNombre"),
        inputArea: $("inputArea"),
        tabLaser: $("tabLaser"),
        tabCamara: $("tabCamara"),
        laserInput: $("laserInput"),
        camaraSection: $("camaraSection"),
        articuloDisplay: $("articuloDisplay"),
        articuloNombre: $("articuloNombre"),
        articuloStock: $("articuloStock"),
        articuloIcon: $("articuloIcon"),
        btnConfirm: $("btnConfirm"),
        historialList: $("historialList"),
        histCount: $("histCount"),
        // Stock
        stockSearch: $("stockSearch"),
        stockList: $("stockList"),
        // Registros
        registrosSearch: $("registrosSearch"),
        registrosList: $("registrosList"),
        kpiTotal: $("kpiTotal"),
        kpiTerreno: $("kpiTerreno"),
        kpiDevueltos: $("kpiDevueltos"),
        // Modal carnet
        carnetModal: $("carnetModal"),
        btnCloseCarnet: $("btnCloseCarnet"),
        // Overlays
        loadingOverlay: $("loadingOverlay"),
        toastContainer: $("toastContainer"),
    };

    // ── Toast ─────────────────────────────────────────────────────
    function toast(msg, type = "info", duration = 3200) {
        const el = document.createElement("div");
        el.className = `toast ${type}`;
        el.textContent = msg;
        els.toastContainer.appendChild(el);
        requestAnimationFrame(() => {
            requestAnimationFrame(() => el.classList.add("show"));
        });
        setTimeout(() => {
            el.classList.remove("show");
            setTimeout(() => el.remove(), 350);
        }, duration);
    }

    // ── Loading ───────────────────────────────────────────────────
    function showLoading() { els.loadingOverlay.classList.add("active"); }
    function hideLoading() { els.loadingOverlay.classList.remove("active"); }

    // ── Vibrate (haptic feedback) ─────────────────────────────────
    function vibrate(pattern) {
        if (navigator.vibrate) navigator.vibrate(pattern);
    }

    // ── Auth ──────────────────────────────────────────────────────
    async function checkSession() {
        try {
            const data = await API.me({ skipAuthHandler: true });
            if (data.success) {
                state.user = data.user;
                state.planta = data.planta;
                unlockApp();
                return true;
            }
        } catch (_) {}
        return false;
    }

    async function doLogin() {
        const u = els.loginUser.value.trim();
        const p = els.loginPass.value.trim();
        const pl = els.loginPlanta.value;

        els.loginError.textContent = "";
        if (!u || !p) { els.loginError.textContent = "Completa usuario y contraseña."; return; }

        els.btnLogin.disabled = true;
        els.btnLogin.textContent = "Conectando...";

        try {
            const data = await API.login(u, p, pl);
            if (data.success) {
                state.user = data.user;
                state.planta = data.planta;
                unlockApp();
            } else {
                els.loginError.textContent = data.message || "Credenciales incorrectas.";
                vibrate([300]);
            }
        } catch (e) {
            els.loginError.textContent = "Error de conexion. Verifica la red.";
        } finally {
            els.btnLogin.disabled = false;
            els.btnLogin.textContent = "INGRESAR AL SISTEMA";
        }
    }

    function unlockApp() {
        els.loginScreen.classList.add("hidden");
        els.appContent.classList.add("visible");
        els.headerPlanta.textContent = `Planta: ${state.planta}`;
        els.headerPlantaBadge.textContent = state.planta;
        showView("operacion");
        loadArticulos();
    }

    function logout() {
        API.logout().catch(() => {});
        state.user = null;
        state.planta = "TUNICHE";
        state.articulos = [];
        state.historial = [];
        els.appContent.classList.remove("visible");
        els.loginScreen.classList.remove("hidden");
        els.loginPass.value = "";
        els.loginError.textContent = "";
    }

    // ── Navigation ────────────────────────────────────────────────
    function showView(name) {
        document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
        document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
        const viewId = { operacion: "viewOperacion", stock: "viewStock", registros: "viewRegistros" }[name];
        const navId = { operacion: "navOperacion", stock: "navStock", registros: "navRegistros" }[name];
        if (viewId) $(viewId).classList.add("active");
        if (navId) $(navId).classList.add("active");

        if (name === "stock") renderStockList();
        if (name === "registros") loadRegistros();
    }

    // ── Mode (SALIDA / DEVOLUCION) ────────────────────────────────
    function updateMode(isDevolucion) {
        state.mode = isDevolucion ? "DEVOLUCION" : "SALIDA";
        const b = els.modeBanner;
        b.className = `mode-banner mode-${state.mode.toLowerCase()}`;
        els.modeName.textContent = state.mode;
        els.modeIcon.innerHTML = isDevolucion
            ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="20" height="20"><path d="M12 21V9M7 16l5 5 5-5M5 5v6h14V5"/></svg>`
            : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="20" height="20"><path d="M12 3v12M7 8l5-5 5 5M5 13v6h14v-6"/></svg>`;
        els.btnConfirm.className = `btn-confirm mode-${state.mode.toLowerCase()}`;
        els.btnConfirm.querySelector("span").textContent = state.mode === "SALIDA" ? "CONFIRMAR SALIDA" : "CONFIRMAR DEVOLUCION";
        updateConfirmButton();
    }

    // ── Worker (RUT scan) ─────────────────────────────────────────
    async function onCredentialScanned(rawText) {
        const { rut, nombre } = Scanner.parseCredential(rawText);
        if (!rut) {
            toast("No se detecto un RUT valido.", "error");
            vibrate([300]);
            return;
        }
        const rutFmt = Scanner.formatRut(rut);
        els.inputRut.value = rutFmt;
        if (nombre) els.inputNombre.value = nombre;
        vibrate([100]);
        closeCarnetModal();

        // Buscar en BD para autocompletar nombre y area
        try {
            const data = await API.buscarTrabajador(rutFmt);
            if (data.success) {
                els.inputNombre.value = data.nombre;
                const sel = els.inputArea;
                for (let i = 0; i < sel.options.length; i++) {
                    if (sel.options[i].value === data.area) {
                        sel.selectedIndex = i; break;
                    }
                }
            }
        } catch (_) {}
        state.currentWorker = { rut: rutFmt };
        updateConfirmButton();
    }

    // ── Articulo scan ─────────────────────────────────────────────
    function onArticuloScanned(rawText) {
        const id = Scanner.parseArticleCode(rawText);
        if (id === null) {
            // Try searching by text
            const found = state.articulos.find(a =>
                a.descripcion.toLowerCase().includes(rawText.toLowerCase())
            );
            if (found) { selectArticulo(found); return; }
            toast("Codigo de articulo no reconocido.", "warning");
            vibrate([200, 100, 200]);
            return;
        }
        const found = state.articulos.find(a => a.id === id);
        if (found) {
            selectArticulo(found);
        } else {
            toast(`Articulo ID ${id} no encontrado en catalogo.`, "error");
            vibrate([300]);
        }
    }

    function selectArticulo(art) {
        state.currentArticulo = art;
        vibrate([80]);
        const hasStock = art.stock_disponible > 0;
        const display = els.articuloDisplay;
        display.className = `articulo-display ${hasStock ? "found" : "no-stock"}`;
        els.articuloNombre.textContent = `${art.descripcion} [${art.talla}]`;
        els.articuloStock.textContent = hasStock
            ? `Stock disponible: ${art.stock_disponible}`
            : "Sin stock disponible";

        const iconEl = display.querySelector(".articulo-icon");
        if (iconEl) {
            iconEl.innerHTML = hasStock
                ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="18" height="18"><path d="M20 6L9 17l-5-5"/></svg>`
                : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="18" height="18"><path d="M18 6L6 18M6 6l12 12"/></svg>`;
        }
        updateConfirmButton();
    }

    function clearArticulo() {
        state.currentArticulo = null;
        els.articuloDisplay.className = "articulo-display";
        els.articuloNombre.textContent = "Esperando escaneo de articulo...";
        els.articuloNombre.style.color = "var(--muted)";
        els.articuloNombre.style.fontWeight = "500";
        els.articuloStock.textContent = "";
        updateConfirmButton();
    }

    function updateConfirmButton() {
        const rut = els.inputRut.value.trim();
        const nombre = els.inputNombre.value.trim();
        const area = els.inputArea.value;
        const hasArt = state.currentArticulo !== null;
        const hasStock = state.currentArticulo && state.currentArticulo.stock_disponible > 0;
        const canConfirm = rut && nombre && area && hasArt && (state.mode === "DEVOLUCION" || hasStock);
        els.btnConfirm.disabled = !canConfirm;
    }

    // ── Scan method switching ─────────────────────────────────────
    function setScanMethod(method) {
        state.scanMethod = method;
        els.laserInput.parentElement.style.display = method === "laser" ? "block" : "none";
        els.camaraSection.style.display = method === "camera" ? "block" : "none";
        els.tabLaser.classList.toggle("active", method === "laser");
        els.tabCamara.classList.toggle("active", method === "camera");

        if (method === "camera") {
            Scanner.startArticleCamera("readerArticulo", onArticuloScanned).catch(e => {
                toast("No se pudo iniciar la camara.", "error");
                console.error(e);
            });
        } else {
            Scanner.stopArticleCamera();
            setTimeout(() => els.laserInput.focus(), 100);
        }
    }

    // ── Confirm operation ─────────────────────────────────────────
    async function confirmOperation() {
        const rut = els.inputRut.value.trim();
        const nombre = els.inputNombre.value.trim();
        const area = els.inputArea.value;
        const art = state.currentArticulo;

        if (!rut || !nombre || !area || !art) {
            toast("Completa todos los campos.", "warning"); return;
        }

        showLoading();
        try {
            const data = await API.registrar(state.mode, rut, nombre, area, art.id);
            hideLoading();

            if (data.success) {
                vibrate([100, 50, 100]);
                toast(data.message, "success", 3000);

                // Update local stock cache
                const idx = state.articulos.findIndex(a => a.id === art.id);
                if (idx !== -1) state.articulos[idx].stock_disponible = data.nuevo_stock;

                // Add to session history
                state.historial.unshift({
                    tipo: state.mode.toLowerCase(),
                    msg: data.message,
                    rut,
                    area,
                    hora: data.hora || "",
                });
                renderHistorial();

                // Reset form for next scan
                clearArticulo();
                if (state.scanMethod === "laser") {
                    setTimeout(() => els.laserInput.focus(), 200);
                }
            } else {
                vibrate([300]);
                toast(data.message || "Error al registrar.", "error", 4000);
            }
        } catch (e) {
            hideLoading();
            toast("Error de conexion.", "error");
        }
    }

    // ── Historial (mini) ──────────────────────────────────────────
    function renderHistorial() {
        const container = els.historialList;
        els.histCount.textContent = state.historial.length > 0 ? `(${state.historial.length})` : "";

        if (state.historial.length === 0) {
            container.innerHTML = `<div class="empty-state" style="padding:16px;"><p>Sin operaciones en esta sesion</p></div>`;
            return;
        }

        const last5 = state.historial.slice(0, 5);
        container.innerHTML = last5.map(h => `
            <div class="hist-item ${h.tipo}">
                <div class="hist-dot"></div>
                <div class="hist-info">
                    <div class="hist-msg">${escHtml(h.msg)}</div>
                    <div class="hist-meta">${escHtml(h.rut)} · ${escHtml(h.area)}</div>
                </div>
                <div class="hist-time">${escHtml(h.hora)}</div>
            </div>
        `).join("");
    }

    // ── Carnet Modal ──────────────────────────────────────────────
    function openCarnetModal() {
        els.carnetModal.classList.add("active");
        Scanner.startCarnetCamera("carnetReader", (text) => {
            onCredentialScanned(text);
        }).catch(e => {
            toast("No se pudo iniciar la camara.", "error");
            closeCarnetModal();
            console.error(e);
        });
    }

    function closeCarnetModal() {
        els.carnetModal.classList.remove("active");
        Scanner.stopCarnetCamera();
    }

    // ── Stock View ────────────────────────────────────────────────
    async function loadArticulos() {
        try {
            const data = await API.getArticulos();
            if (data.success) state.articulos = data.articulos;
        } catch (e) {
            console.error("Error loading articulos:", e);
        }
    }

    function filterStock(filter) {
        state.stockFilter = filter;
        document.querySelectorAll("#viewStock .filter-tab").forEach(t => {
            t.classList.toggle("active", t.dataset.filter === filter);
        });
        renderStockList();
    }

    function renderStockList() {
        const query = els.stockSearch ? els.stockSearch.value.toLowerCase() : "";
        let items = [...state.articulos];

        if (query) {
            items = items.filter(a =>
                a.descripcion.toLowerCase().includes(query) ||
                (a.talla && a.talla.toLowerCase().includes(query))
            );
        }
        if (state.stockFilter === "low") items = items.filter(a => a.stock_disponible > 0 && a.limite_alerta && a.stock_disponible <= a.limite_alerta);
        if (state.stockFilter === "zero") items = items.filter(a => a.stock_disponible <= 0);

        const container = els.stockList;
        if (items.length === 0) {
            container.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z"/><path d="M16 7V5a2 2 0 0 0-4 0v2"/></svg><p>Sin articulos</p></div>`;
            return;
        }

        container.innerHTML = items.map(a => {
            const s = a.stock_disponible;
            const isLow = a.limite_alerta && s > 0 && s <= a.limite_alerta;
            const cls = s <= 0 ? "zero" : isLow ? "low" : "ok";
            return `<div class="stock-item">
                <div class="stock-info">
                    <div class="stock-nombre">${escHtml(a.descripcion)}</div>
                    <div class="stock-sub">Talla ${escHtml(a.talla || "-")} · ${escHtml(a.medida || "")}</div>
                </div>
                <div class="stock-badge ${cls}">${s}</div>
            </div>`;
        }).join("");
    }

    // ── Registros View ────────────────────────────────────────────
    async function loadRegistros() {
        try {
            const data = await API.getRegistros(state.registrosFilter, state.registrosQuery);
            if (data.success) {
                state.registros = data.registros;
                els.kpiTotal.textContent = data.kpi.total;
                els.kpiTerreno.textContent = data.kpi.en_terreno;
                els.kpiDevueltos.textContent = data.kpi.devueltos;
                renderRegistros();
            }
        } catch (e) {
            toast("Error cargando registros.", "error");
        }
    }

    function filterRegistros(estado) {
        state.registrosFilter = estado;
        document.querySelectorAll("#viewRegistros .filter-tab").forEach(t => {
            t.classList.toggle("active", t.dataset.estado === estado);
        });
        loadRegistros();
    }

    function renderRegistros() {
        const container = els.registrosList;
        if (state.registros.length === 0) {
            container.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v6h6"/><path d="M12 7v5l3 2"/></svg><p>Sin registros hoy</p></div>`;
            return;
        }
        container.innerHTML = state.registros.map(r => {
            const cls = r.estado === "EN TERRENO" ? "terreno" : "devuelto";
            const badge = r.estado === "EN TERRENO"
                ? `<span class="reg-badge badge-terreno">En Terreno</span>`
                : `<span class="reg-badge badge-devuelto">Devuelto</span>`;
            return `<div class="reg-card ${cls}">
                <div class="reg-top">
                    <div>
                        <div class="reg-nombre">${escHtml(r.trabajador)}</div>
                        <div class="reg-rut">${escHtml(r.rut)}</div>
                    </div>
                    ${badge}
                </div>
                <div class="reg-articulo">${escHtml(r.articulo)}</div>
                <div class="reg-meta">
                    <span>Salida: ${escHtml(r.hora_salida)}</span>
                    ${r.hora_entrada !== "---" ? `<span>Entrada: ${escHtml(r.hora_entrada)}</span>` : ""}
                    <span>${escHtml(r.area)}</span>
                </div>
            </div>`;
        }).join("");
    }

    // ── Utilities ─────────────────────────────────────────────────
    function escHtml(str) {
        return String(str ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    // ── Init ──────────────────────────────────────────────────────
    function init() {
        // Login
        els.btnLogin.addEventListener("click", doLogin);
        els.loginPass.addEventListener("keydown", e => { if (e.key === "Enter") doLogin(); });

        // Logout
        els.btnLogout.addEventListener("click", logout);

        // Mode toggle
        els.modeToggle.addEventListener("change", () => updateMode(els.modeToggle.checked));

        // Carnet modal
        els.btnScanCarnet.addEventListener("click", openCarnetModal);
        els.btnCloseCarnet.addEventListener("click", closeCarnetModal);
        els.carnetModal.addEventListener("click", e => { if (e.target === els.carnetModal) closeCarnetModal(); });

        // Laser input for articles
        Scanner.initLaser(els.laserInput, onArticuloScanned);
        setTimeout(() => els.laserInput.focus(), 500);

        // Confirm button
        els.btnConfirm.addEventListener("click", confirmOperation);

        // Form change → re-validate confirm button
        els.inputRut.addEventListener("input", updateConfirmButton);
        els.inputNombre.addEventListener("input", updateConfirmButton);
        els.inputArea.addEventListener("change", updateConfirmButton);

        // Stock search
        if (els.stockSearch) {
            els.stockSearch.addEventListener("input", () => renderStockList());
        }

        // Registros search
        if (els.registrosSearch) {
            els.registrosSearch.addEventListener("input", (e) => {
                state.registrosQuery = e.target.value;
                loadRegistros();
            });
        }

        // Init confirm button state
        updateMode(false);
        renderHistorial();

        // Check session on load
        checkSession();
    }

    document.addEventListener("DOMContentLoaded", init);

    // Public API
    return {
        showView,
        filterStock,
        filterRegistros,
        setScanMethod,
        loadRegistros,
        logout,
    };
})();
