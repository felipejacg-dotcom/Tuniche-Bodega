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
        scannedArticulos: [],     // carro de multi-escaneo para salida masiva
        historial: [],            // session history
        registros: [],            // loaded from /api/registros
        registrosFilter: "",      // "EN TERRENO" | "DEVUELTO" | ""
        registrosQuery: "",
        cierreTurno: null,
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
        modeSalidaBtn: $("modeSalidaBtn"),
        modeDevolucionBtn: $("modeDevolucionBtn"),
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
        kpiTotal: $("kpiTotal"),
        kpiTerreno: $("kpiTerreno"),
        kpiDevueltos: $("kpiDevueltos"),
        cierreModal: $("cierreModal"),
        cierreContent: $("cierreContent"),
        btnCloseCierre: $("btnCloseCierre"),
        btnDownloadCierre: $("btnDownloadCierre"),
        // Modal carnet
        carnetModal: $("carnetModal"),
        btnCloseCarnet: $("btnCloseCarnet"),
        // Nuevos contenedores dinamicos
        devolucionesPendientesSection: $("devolucionesPendientesSection"),
        devolucionesPendientesList: $("devolucionesPendientesList"),
        multiScanSection: $("multiScanSection"),
        multiScanList: $("multiScanList"),
        // Overlays
        loadingOverlay: $("loadingOverlay"),
        toastContainer: $("toastContainer"),
    };

    function getSucursalLabel(planta) {
        return planta === "TUNICHE" ? "Graneros" : planta;
    }

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
            els.loginError.textContent = e.message || "Error de conexion. Verifica la red.";
        } finally {
            els.btnLogin.disabled = false;
            els.btnLogin.textContent = "INGRESAR AL SISTEMA";
        }
    }

    function unlockApp() {
        els.loginScreen.classList.add("hidden");
        els.appContent.classList.add("visible");
        const sucursalLabel = getSucursalLabel(state.planta);
        els.headerPlanta.textContent = `Sucursal: ${sucursalLabel}`;
        els.headerPlantaBadge.textContent = sucursalLabel;
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
    function updateMode(mode) {
        state.mode = mode === "DEVOLUCION" ? "DEVOLUCION" : "SALIDA";
        const isDevolucion = state.mode === "DEVOLUCION";
        els.modeSalidaBtn.classList.toggle("active", !isDevolucion);
        els.modeDevolucionBtn.classList.toggle("active", isDevolucion);
        els.modeSalidaBtn.setAttribute("aria-pressed", String(!isDevolucion));
        els.modeDevolucionBtn.setAttribute("aria-pressed", String(isDevolucion));
        els.btnConfirm.className = `btn-confirm mode-${state.mode.toLowerCase()}`;
        els.btnConfirm.querySelector("span").textContent = state.mode === "SALIDA" ? "CONFIRMAR SALIDA" : "CONFIRMAR DEVOLUCION";

        clearArticulo();

        if (state.mode === "DEVOLUCION") {
            Scanner.stopArticleCamera();
            els.articleScanCard.style.display = "none";
            els.multiScanSection.style.display = "none";
            els.btnConfirm.style.display = "none";
            const rut = els.inputRut.value.trim();
            if (rut) {
                cargarPendientes(rut);
            } else {
                ocultarPendientes();
            }
        } else {
            els.articleScanCard.style.display = "block";
            els.btnConfirm.style.display = "flex";
            ocultarPendientes();
            setScanMethod(state.scanMethod);
            renderMultiScanList();
        }

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

        if (state.mode === "DEVOLUCION") {
            cargarPendientes(rutFmt);
        }

        updateConfirmButton();
    }

    // ── Articulo scan ─────────────────────────────────────────────
    function onArticuloScanned(rawText) {
        if (state.mode !== "SALIDA") {
            toast("El escaneo de articulos solo se usa en modo salida.", "info");
            return;
        }

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

    async function selectArticulo(art) {
        const rut = els.inputRut.value.trim();
        const nombre = els.inputNombre.value.trim();
        const area = els.inputArea.value;

        if (state.mode === "SALIDA") {
            if (art.stock_disponible <= 0) {
                toast(`Sin stock disponible de ${art.descripcion}`, "error");
                vibrate([300]);
                return;
            }

            let warningText = "";
            if (rut) {
                try {
                    const freq = await API.getUltimoRetiro(rut, art.id);
                    if (freq.success && freq.alerta) {
                        warningText = `⚠️ Retirado hace ${freq.dias} dias (${freq.fecha})`;
                    }
                } catch (_) {}
            }

            if (state.scannedArticulos.some(a => a.id === art.id)) {
                toast("Este articulo ya esta en la lista.", "warning");
                return;
            }

            state.scannedArticulos.push({
                id: art.id,
                descripcion: art.descripcion,
                talla: art.talla,
                medida: art.medida,
                stock_disponible: art.stock_disponible,
                warning: warningText
            });

            vibrate([80]);
            renderMultiScanList();

            els.articuloDisplay.className = "articulo-display found";
            els.articuloNombre.textContent = `Agregado: ${art.descripcion} [${art.talla || ""}]`;
            els.articuloStock.textContent = "";

            if (state.scanMethod === "laser") {
                els.laserInput.value = "";
                setTimeout(() => els.laserInput.focus(), 100);
            }
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

        let canConfirm = false;
        if (state.mode === "SALIDA") {
            canConfirm = rut && nombre && area && state.scannedArticulos.length > 0;
            const n = state.scannedArticulos.length;
            els.btnConfirm.querySelector("span").textContent = n > 1
                ? `CONFIRMAR SALIDA (${n} ITEMS)`
                : "CONFIRMAR SALIDA";
        } else {
            canConfirm = false;
        }
        els.btnConfirm.disabled = !canConfirm;
    }

    // ── Scan method switching ─────────────────────────────────────
    function setScanMethod(method) {
        if (state.mode !== "SALIDA") {
            Scanner.stopArticleCamera();
            return;
        }

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

        if (!rut || !nombre || !area) {
            toast("Completa los datos del trabajador.", "warning"); return;
        }

        if (state.mode === "SALIDA") {
            if (state.scannedArticulos.length === 0) {
                toast("Escanea al menos un articulo.", "warning"); return;
            }

            showLoading();
            try {
                const ids = state.scannedArticulos.map(a => a.id);
                const data = await API.registrarMasivo(rut, nombre, area, ids);
                hideLoading();

                if (data.success) {
                    vibrate([100, 50, 100]);
                    toast(data.message, "success", 4000);

                    // Update stocks in local cache
                    data.entregados.forEach(item => {
                        const idx = state.articulos.findIndex(a => a.id === item.id);
                        if (idx !== -1) state.articulos[idx].stock_disponible = item.nuevo_stock;
                    });

                    // Add to session history
                    state.historial.unshift({
                        tipo: "salida",
                        msg: data.message,
                        rut,
                        area,
                        hora: data.hora || "",
                    });
                    renderHistorial();

                    // Reset form and multi-scan cart
                    state.scannedArticulos = [];
                    renderMultiScanList();
                    clearArticulo();

                    if (state.scanMethod === "laser") {
                        setTimeout(() => els.laserInput.focus(), 200);
                    }
                } else {
                    vibrate([300]);
                    toast(data.message || "Error al registrar entrega.", "error", 4000);
                }
            } catch (e) {
                hideLoading();
                toast(e.message || "Error de conexion.", "error", 5000);
            }
        }
    }

    // ── Multi-Scan List Render ────────────────────────────────────
    function renderMultiScanList() {
        const container = els.multiScanList;
        if (state.scannedArticulos.length === 0) {
            els.multiScanSection.style.display = "none";
            container.innerHTML = "";
            return;
        }

        els.multiScanSection.style.display = "block";
        container.innerHTML = state.scannedArticulos.map((art, idx) => {
            const warnHtml = art.warning
                ? `<div class="multi-scan-alert">${art.warning}</div>`
                : "";
            return `
                <div class="multi-scan-item" data-index="${idx}">
                    <div class="multi-scan-details">
                        <div>${escHtml(art.descripcion)} [${escHtml(art.talla || "-")}]</div>
                        ${warnHtml}
                    </div>
                    <button type="button" class="btn-remove-item" onclick="App.removeItemFromMultiScan(${idx})" aria-label="Eliminar">&times;</button>
                </div>
            `;
        }).join("");
    }

    function removeItemFromMultiScan(idx) {
        state.scannedArticulos.splice(idx, 1);
        renderMultiScanList();
        updateConfirmButton();
        if (state.scannedArticulos.length === 0) {
            clearArticulo();
        }
    }

    // ── Devoluciones Pendientes ───────────────────────────────────
    async function cargarPendientes(rut) {
        if (!rut) return;
        try {
            const data = await API.getPendientes(rut);
            if (data.success && data.pendientes && data.pendientes.length > 0) {
                els.devolucionesPendientesSection.style.display = "block";
                els.devolucionesPendientesList.innerHTML = data.pendientes.map(p => `
                    <div class="pending-return-item"
                         data-articulo-id="${p.articulo_id}"
                         data-transaccion-id="${p.transaccion_id}"
                         data-trabajador="${escHtml(p.trabajador || "")}"
                         data-area="${escHtml(p.area || "")}">
                        <div class="pending-return-info">
                            <div class="pending-return-title">${escHtml(p.descripcion)}</div>
                            <div class="pending-return-date">Retirado el ${escHtml(p.hora_salida)}</div>
                        </div>
                        <button type="button" class="btn-quick-return"
                                onclick="App.devolverRapido(${p.articulo_id})">
                            Devolver
                        </button>
                    </div>
                `).join("");
            } else {
                ocultarPendientes();
            }
        } catch (e) {
            console.error("Error al cargar pendientes:", e);
            ocultarPendientes();
        }
    }

    function ocultarPendientes() {
        els.devolucionesPendientesSection.style.display = "none";
        els.devolucionesPendientesList.innerHTML = "";
    }

    async function devolverRapido(articuloId) {
        const pendingItem = document.querySelector(`.pending-return-item[data-articulo-id="${articuloId}"]`);
        const descripcion = pendingItem?.querySelector(".pending-return-title")?.textContent || "articulo";
        const rut = els.inputRut.value.trim();
        const nombre = els.inputNombre.value.trim() || pendingItem?.dataset.trabajador || "Trabajador";
        const area = els.inputArea.value || pendingItem?.dataset.area || "BODEGA";

        if (!rut) {
            toast("Ingresa o escanea el RUT del trabajador.", "warning");
            return;
        }

        showLoading();
        try {
            const data = await API.registrar("DEVOLUCION", rut, nombre, area, articuloId);
            hideLoading();
            if (data.success) {
                vibrate([100, 50, 100]);
                toast(`Devuelto con exito: ${descripcion}`, "success");

                cargarPendientes(rut);

                state.historial.unshift({
                    tipo: "devolucion",
                    msg: data.message,
                    rut,
                    area,
                    hora: data.hora || "",
                });
                renderHistorial();
            } else {
                toast(data.message || "Error al registrar devolucion.", "error");
            }
        } catch (e) {
            hideLoading();
            toast(e.message || "Error de conexion.", "error", 5000);
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
            toast(e.message || "Error cargando articulos.", "error", 5000);
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
            toast(e.message || "Error cargando registros.", "error", 5000);
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

    async function openCierreTurno(desde = null, hasta = null) {
        if (!els.cierreModal) return;
        els.cierreModal.classList.add("active");
        
        const inputDesdeEl = document.getElementById("cierreDesde");
        const inputHastaEl = document.getElementById("cierreHasta");
        
        const isReloading = inputDesdeEl && inputHastaEl;
        if (!isReloading) {
            els.cierreContent.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 5h16M4 12h16M4 19h10"/></svg><p>Generando cierre...</p></div>`;
        } else {
            inputDesdeEl.disabled = true;
            inputHastaEl.disabled = true;
            const btnUpdate = document.getElementById("btnUpdateCierre");
            if (btnUpdate) {
                btnUpdate.disabled = true;
                btnUpdate.textContent = "Cargando...";
            }
        }

        try {
            const data = await API.getCierreTurno(desde, hasta);
            if (!data.success) throw new Error(data.message || "No se pudo generar el cierre.");
            state.cierreTurno = data;
            renderCierreTurno(data);
        } catch (e) {
            if (!isReloading) {
                els.cierreContent.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 3.9 2.8 17a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg><p>${escHtml(e.message || "Error generando cierre.")}</p></div>`;
            } else {
                toast(e.message || "Error al actualizar cierre.", "error", 5000);
                inputDesdeEl.disabled = false;
                inputHastaEl.disabled = false;
                const btnUpdate = document.getElementById("btnUpdateCierre");
                if (btnUpdate) {
                    btnUpdate.disabled = false;
                    btnUpdate.textContent = "Actualizar";
                }
            }
        }
    }

    function closeCierreTurno() {
        if (els.cierreModal) els.cierreModal.classList.remove("active");
    }

    function renderCierreTurno(data) {
        const kpi = data.kpi || {};
        const pendientes = data.pendientes || [];
        const stockCritico = data.stock_critico || [];

        function buildPendientesHtml(list) {
            if (!list.length) {
                return `<div class="cierre-empty">Sin pendientes en este turno.</div>`;
            }
            return list.map(worker => {
                const artsHtml = worker.articulos.map(art => `
                    <div class="cierre-sub-item">
                        <div class="cierre-sub-item-name">${escHtml(art.articulo)}</div>
                        <div class="cierre-sub-item-time">${escHtml(art.hora_salida)}</div>
                    </div>
                `).join("");

                return `
                    <div class="cierre-worker-card">
                        <div class="cierre-worker-info">
                            <strong>${escHtml(worker.trabajador)}</strong>
                            <span>${escHtml(worker.rut)} · ${escHtml(worker.area || "Sin área")}</span>
                        </div>
                        <div class="cierre-worker-items">
                            ${artsHtml}
                        </div>
                    </div>
                `;
            }).join("");
        }

        const pendientesHtml = buildPendientesHtml(pendientes);

        const stockHtml = stockCritico.length
            ? stockCritico.slice(0, 20).map(item => `
                <div class="cierre-item cierre-stock">
                    <div class="cierre-item-main">
                        <strong>${escHtml(item.descripcion)} ${item.talla ? `[${escHtml(item.talla)}]` : ""}</strong>
                        <span>ID ${escHtml(item.id)} · Alerta ${escHtml(item.limite_alerta)}</span>
                    </div>
                    <div class="cierre-stock-count">${escHtml(item.stock_disponible)}</div>
                </div>
            `).join("")
            : `<div class="cierre-empty">Sin stock critico.</div>`;

        els.cierreContent.innerHTML = `
            <div class="cierre-range-ctrls">
                <div class="cierre-ctrl-group">
                    <label class="cierre-ctrl-label" for="cierreDesde">Desde</label>
                    <input type="datetime-local" id="cierreDesde" class="cierre-datetime-input" value="${data.desde_iso}">
                </div>
                <div class="cierre-ctrl-group">
                    <label class="cierre-ctrl-label" for="cierreHasta">Hasta</label>
                    <input type="datetime-local" id="cierreHasta" class="cierre-datetime-input" value="${data.hasta_iso}">
                </div>
                <button type="button" id="btnUpdateCierre" class="btn-refresh btn-cierre-update">Actualizar</button>
            </div>
            <div class="cierre-head" style="margin-top: 4px;">
                <div>
                    <div class="cierre-eyebrow">Generado ${escHtml(data.hora_generacion || "--:--")}</div>
                    <div class="cierre-title">Turno ${escHtml(data.turno || "")} · ${escHtml(data.planta_display || data.planta || state.planta)}</div>
                </div>
            </div>
            <div class="cierre-kpi-grid">
                <div class="cierre-kpi"><strong>${escHtml(kpi.total ?? 0)}</strong><span>Movimientos</span></div>
                <div class="cierre-kpi"><strong>${escHtml(kpi.salidas ?? 0)}</strong><span>Salidas</span></div>
                <div class="cierre-kpi"><strong>${escHtml(kpi.devoluciones ?? 0)}</strong><span>Devoluciones</span></div>
                <div class="cierre-kpi warning"><strong>${escHtml(kpi.pendientes ?? 0)}</strong><span>Pendientes</span></div>
                <div class="cierre-kpi warning"><strong>${escHtml(kpi.trabajadores_pendientes ?? 0)}</strong><span>Trabajadores</span></div>
                <div class="cierre-kpi danger"><strong>${escHtml(kpi.stock_critico ?? 0)}</strong><span>Stock critico</span></div>
            </div>
            <div class="cierre-section-title">Pendientes del Turno</div>
            <div class="cierre-list">${pendientesHtml}</div>
            <div class="cierre-section-title">Stock critico</div>
            <div class="cierre-list">${stockHtml}</div>
        `;

        const btnUpdate = document.getElementById("btnUpdateCierre");
        if (btnUpdate) {
            btnUpdate.addEventListener("click", () => {
                const desdeVal = document.getElementById("cierreDesde")?.value;
                const hastaVal = document.getElementById("cierreHasta")?.value;
                openCierreTurno(desdeVal, hastaVal);
            });
        }
    }

    async function downloadCierrePdf() {
        if (!state.cierreTurno) {
            toast("Primero genera el cierre.", "warning");
            return;
        }

        const desdeVal = document.getElementById("cierreDesde")?.value || "";
        const hastaVal = document.getElementById("cierreHasta")?.value || "";

        const originalText = els.btnDownloadCierre ? els.btnDownloadCierre.textContent : "";
        try {
            if (els.btnDownloadCierre) {
                els.btnDownloadCierre.disabled = true;
                els.btnDownloadCierre.textContent = "Generando PDF...";
            }
            const { blob, filename } = await API.downloadCierreTurnoPdf(desdeVal, hastaVal);
            const sanitizedFilename = (filename || "cierre-turno.pdf").replace(/[^a-zA-Z0-9._-]/g, "_");
            const file = new File([blob], sanitizedFilename, { type: "application/pdf" });
            const sucursal = state.cierreTurno?.planta_display || state.cierreTurno?.planta || state.planta || "";

            // 1. Caso: ejecucion dentro de la app Android nativa.
            if (window.AndroidApp && typeof window.AndroidApp.sharePdf === "function") {
                const reader = new FileReader();
                reader.onerror = function() {
                    toast("Error al leer el archivo PDF.", "error");
                };
                reader.onloadend = function() {
                    try {
                        const result = typeof reader.result === "string" ? reader.result : "";
                        const base64data = result.split(",")[1];
                        if (!base64data) throw new Error("PDF vacio");
                        window.AndroidApp.sharePdf(base64data, sanitizedFilename);
                    } catch (e) {
                        toast("Error al procesar el archivo en la aplicacion.", "error");
                    }
                };
                reader.readAsDataURL(blob);
            }
            // 2. Caso: navegador movil compatible con Web Share
            else if (navigator.canShare && navigator.canShare({ files: [file] })) {
                await navigator.share({
                    files: [file],
                    title: sanitizedFilename,
                    text: `Cierre de turno de la sucursal ${sucursal}`,
                });
                toast("Cierre compartido.", "success");
            }
            // 3. Fallback: descarga clasica de archivo en escritorio
            else {
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = sanitizedFilename;
                document.body.appendChild(link);
                link.click();
                link.remove();
                URL.revokeObjectURL(url);
                toast("PDF descargado.", "success");
            }
        } catch (e) {
            if (e.name !== "AbortError") {
                toast(e.message || "No se pudo descargar o compartir el PDF.", "error", 5000);
            }
        } finally {
            if (els.btnDownloadCierre) {
                els.btnDownloadCierre.disabled = false;
                els.btnDownloadCierre.textContent = originalText || "Descargar PDF";
            }
        }
    }

    // ── Utilities ─────────────────────────────────────────────────
    function escHtml(str) {
        return String(str ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    /**
     * Formatea un RUT chileno en tiempo real mientras el usuario escribe.
     * Ejemplos:
     *   "208269216"  →  "20.826.921-6"
     *   "20826921k"  →  "20.826.921-K"
     * Regla: solo permite digitos + K; aplica puntos al cuerpo y guion antes del DV.
     * Requiere minimo 2 caracteres para mostrar el guion.
     */
    function formatRutLive(raw) {
        // 1. Limpiar: solo digitos y K
        const clean = raw.replace(/[^0-9kK]/g, "").toUpperCase();
        if (clean.length === 0) return "";
        if (clean.length === 1) return clean;

        // 2. Separar cuerpo y digito verificador
        const dv = clean.slice(-1);
        const body = clean.slice(0, -1);
        if (body.length === 0) return dv;

        // 3. Agregar puntos al cuerpo (cada 3 digitos desde la derecha)
        const bodyFmt = body.replace(/\B(?=(\d{3})+(?!\d))/g, ".");

        return `${bodyFmt}-${dv}`;
    }

    /**
     * Handler del campo RUT: formatea mientras el usuario escribe
     * y reposiciona el cursor correctamente despues de formatear.
     */
    function onRutInput(e) {
        const el = e.target;
        const before = el.value;
        const cursorBefore = el.selectionStart;

        // Contar cuantos caracteres reales (digitos/K) hay ANTES del cursor
        const realBefore = before.slice(0, cursorBefore).replace(/[^0-9kK]/gi, "").length;

        const formatted = formatRutLive(before);

        // Solo actualizar si el valor cambia (evitar bucles)
        if (formatted !== before) {
            el.value = formatted;

            // Reposicionar cursor: avanzar en el string formateado
            // hasta haber contado la misma cantidad de chars reales
            let realCount = 0;
            let newCursor = 0;
            for (let i = 0; i < formatted.length; i++) {
                if (/[0-9kK]/i.test(formatted[i])) realCount++;
                newCursor = i + 1;
                if (realCount >= realBefore) break;
            }
            el.setSelectionRange(newCursor, newCursor);
        }

        updateConfirmButton();
    }

    // ── Init ──────────────────────────────────────────────────────
    function init() {
        // Login
        els.btnLogin.addEventListener("click", doLogin);
        els.loginPass.addEventListener("keydown", e => { if (e.key === "Enter") doLogin(); });

        // Logout
        els.btnLogout.addEventListener("click", logout);

        // Mode selector
        els.modeSalidaBtn.addEventListener("click", () => updateMode("SALIDA"));
        els.modeDevolucionBtn.addEventListener("click", () => updateMode("DEVOLUCION"));

        // Carnet modal
        els.btnScanCarnet.addEventListener("click", openCarnetModal);
        els.btnCloseCarnet.addEventListener("click", closeCarnetModal);
        els.carnetModal.addEventListener("click", e => { if (e.target === els.carnetModal) closeCarnetModal(); });

        // Cierre de turno
        if (els.btnCloseCierre) {
            els.btnCloseCierre.addEventListener("click", closeCierreTurno);
            els.btnDownloadCierre.addEventListener("click", downloadCierrePdf);
            els.cierreModal.addEventListener("click", e => { if (e.target === els.cierreModal) closeCierreTurno(); });
        }

        // Laser input for articles
        Scanner.initLaser(els.laserInput, onArticuloScanned);
        setTimeout(() => els.laserInput.focus(), 500);

        // Confirm button
        els.btnConfirm.addEventListener("click", confirmOperation);

        // Form change → re-validate confirm button
        // RUT: formatea en tiempo real mientras se escribe
        els.inputRut.addEventListener("input", onRutInput);
        els.inputRut.addEventListener("change", async (e) => {
            const rutFmt = e.target.value.trim();
            if (rutFmt.length >= 11) {
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
                if (state.mode === "DEVOLUCION") {
                    cargarPendientes(rutFmt);
                }
                updateConfirmButton();
            }
        });
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
        updateMode("SALIDA");
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
        openCierreTurno,
        closeCierreTurno,
        downloadCierrePdf,
        logout,
        removeItemFromMultiScan,
        devolverRapido,
    };
})();
