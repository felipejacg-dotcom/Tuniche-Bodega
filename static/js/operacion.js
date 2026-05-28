"use strict";

window.App = window.App || {};

App.updateMode = function(mode) {
    const targetMode = mode === "DEVOLUCION" ? "DEVOLUCION" : "SALIDA";
    const modeChanged = App.state.mode !== targetMode;

    App.state.mode = targetMode;
    const isDevolucion = App.state.mode === "DEVOLUCION";
    App.els.modeSalidaBtn.classList.toggle("active", !isDevolucion);
    App.els.modeDevolucionBtn.classList.toggle("active", isDevolucion);
    App.els.modeSalidaBtn.setAttribute("aria-pressed", String(!isDevolucion));
    App.els.modeDevolucionBtn.setAttribute("aria-pressed", String(isDevolucion));
    App.els.btnConfirm.className = `btn-confirm mode-${App.state.mode.toLowerCase()}`;
    App.els.btnConfirm.querySelector("span").textContent = App.state.mode === "SALIDA" ? "CONFIRMAR SALIDA" : "CONFIRMAR DEVOLUCION";

    App.clearArticulo();

    if (modeChanged) {
        if (App.state.scanProcessingIds) App.state.scanProcessingIds.clear();
        if (App.state.scanMutedIds) App.state.scanMutedIds.clear();
    }

    if (App.state.mode === "DEVOLUCION") {
        Scanner.stopArticleCamera();
        App.els.articleScanCard.style.display = "none";
        App.els.multiScanSection.style.display = "none";
        App.els.btnConfirm.style.display = "none";
        const rut = App.els.inputRut.value.trim();
        if (rut) {
            App.cargarPendientes(rut);
        } else {
            App.ocultarPendientes();
        }
    } else {
        App.els.articleScanCard.style.display = "block";
        App.els.btnConfirm.style.display = "flex";
        App.ocultarPendientes();
        App.setScanMethod(App.state.scanMethod);
        App.renderMultiScanList();
    }

    App.updateConfirmButton();
};

App.onCredentialScanned = async function(rawText) {
    const { rut, nombre } = Scanner.parseCredential(rawText);
    if (!rut) {
        App.toast("No se detectó un RUT válido.", "error");
        App.vibrate([300]);
        return;
    }
    const rutFmt = Scanner.formatRut(rut);
    App.els.inputRut.value = rutFmt;
    if (nombre) App.els.inputNombre.value = nombre;
    App.vibrate([100]);
    App.closeCarnetModal();

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
    App.state.currentWorker = { rut: rutFmt };

    if (App.state.mode === "DEVOLUCION") {
        App.cargarPendientes(rutFmt);
    }

    App.updateConfirmButton();
};

App.onArticuloScanned = function(rawText) {
    if (App.state.mode !== "SALIDA") {
        App.toast("El escaneo de artículos solo se usa en modo salida.", "info");
        return;
    }

    const id = Scanner.parseArticleCode(rawText);
    let found = null;
    if (id === null) {
        found = App.state.articulos.find(a =>
            a.descripcion.toLowerCase().includes(rawText.toLowerCase())
        );
        if (!found) {
            App.toast("Código de artículo no reconocido.", "warning");
            App.vibrate([200, 100, 200]);
            return;
        }
    } else {
        found = App.state.articulos.find(a => a.id === id);
        if (!found) {
            App.toast(`Artículo ID ${id} no encontrado en catálogo.`, "error");
            App.vibrate([300]);
            return;
        }
    }

    const artId = found.id;

    if (App.state.scannedArticulos.some(a => a.id === artId)) {
        if (App.shouldNotifyDuplicateScan(artId)) {
            App.toast("Este artículo ya está en la lista.", "warning");
        }
        return;
    }

    if (App.state.scanProcessingIds.has(artId)) {
        return;
    }

    App.state.scanProcessingIds.add(artId);
    App.selectArticulo(found);
};

App.selectArticulo = async function(art) {
    try {
        const rut = App.els.inputRut.value.trim();

        if (App.state.mode === "SALIDA") {
            if (art.stock_disponible <= 0) {
                App.toast(`Sin stock disponible de ${art.descripcion}`, "error");
                App.vibrate([300]);
                return;
            }

            let warningText = "";
            if (rut) {
                try {
                    const freq = await API.getUltimoRetiro(rut, art.id);
                    if (freq.success && freq.alerta) {
                        warningText = `⚠️ Retirado hace ${freq.dias} días (${freq.fecha})`;
                    }
                } catch (_) {}
            }

            if (App.state.scannedArticulos.some(a => a.id === art.id)) {
                if (App.shouldNotifyDuplicateScan(art.id)) {
                    App.toast("Este artículo ya está en la lista.", "warning");
                }
                return;
            }

            App.state.scannedArticulos.push({
                id: art.id,
                descripcion: art.descripcion,
                talla: art.talla,
                medida: art.medida,
                stock_disponible: art.stock_disponible,
                warning: warningText
            });

            App.vibrate([80]);
            App.renderMultiScanList();

            App.els.articuloDisplay.className = "articulo-display found";
            App.els.articuloNombre.textContent = `Agregado: ${art.descripcion} [${art.talla || ""}]`;
            App.els.articuloStock.textContent = "";

            if (App.state.scanMethod === "laser") {
                App.els.laserInput.value = "";
                setTimeout(() => App.els.laserInput.focus(), 100);
            }
        }
        App.updateConfirmButton();
    } finally {
        if (App.state.scanProcessingIds) {
            App.state.scanProcessingIds.delete(art.id);
        }
    }
};

App.clearArticulo = function() {
    App.state.currentArticulo = null;
    App.els.articuloDisplay.className = "articulo-display";
    App.els.articuloNombre.textContent = "Esperando escaneo de artículo...";
    App.els.articuloNombre.style.color = "var(--muted)";
    App.els.articuloNombre.style.fontWeight = "500";
    App.els.articuloStock.textContent = "";
    App.updateConfirmButton();
};

App.updateConfirmButton = function() {
    const rut = App.els.inputRut.value.trim();
    const nombre = App.els.inputNombre.value.trim();
    const area = App.els.inputArea.value;

    let canConfirm = false;
    if (App.state.mode === "SALIDA") {
        canConfirm = rut && nombre && area && App.state.scannedArticulos.length > 0;
        const n = App.state.scannedArticulos.length;
        App.els.btnConfirm.querySelector("span").textContent = n > 1
            ? `CONFIRMAR SALIDA (${n} ITEMS)`
            : "CONFIRMAR SALIDA";
    }
    App.els.btnConfirm.disabled = !canConfirm;
};

App.setScanMethod = function(method) {
    if (App.state.mode !== "SALIDA") {
        Scanner.stopArticleCamera();
        return;
    }

    App.state.scanMethod = method;
    App.els.laserInput.parentElement.style.display = method === "laser" ? "block" : "none";
    App.els.camaraSection.style.display = method === "camera" ? "block" : "none";
    App.els.tabLaser.classList.toggle("active", method === "laser");
    App.els.tabCamara.classList.toggle("active", method === "camera");

    if (method === "camera") {
        Scanner.startArticleCamera("readerArticulo", App.onArticuloScanned).catch(e => {
            App.toast("No se pudo iniciar la cámara.", "error");
            console.error(e);
        });
    } else {
        Scanner.stopArticleCamera();
        setTimeout(() => App.els.laserInput.focus(), 100);
    }
};

App.confirmOperation = async function() {
    const rut = App.els.inputRut.value.trim();
    const nombre = App.els.inputNombre.value.trim();
    const area = App.els.inputArea.value;

    if (!rut || !nombre || !area) {
        App.toast("Completa los datos del trabajador.", "warning"); return;
    }

    if (App.state.mode === "SALIDA") {
        if (App.state.scannedArticulos.length === 0) {
            App.toast("Escanea al menos un artículo.", "warning"); return;
        }

        App.showLoading();
        try {
            const ids = App.state.scannedArticulos.map(a => a.id);
            const data = await API.registrarMasivo(rut, nombre, area, ids);
            App.hideLoading();

            if (data.success) {
                App.vibrate([100, 50, 100]);
                App.toast(data.message, "success", 4000);

                data.entregados.forEach(item => {
                    const idx = App.state.articulos.findIndex(a => a.id === item.id);
                    if (idx !== -1) App.state.articulos[idx].stock_disponible = item.nuevo_stock;
                });

                App.state.historial.unshift({
                    tipo: "salida",
                    msg: data.message,
                    rut,
                    area,
                    hora: data.hora || "",
                });
                App.renderHistorial();

                App.state.scannedArticulos = [];
                if (App.state.scanProcessingIds) App.state.scanProcessingIds.clear();
                if (App.state.scanMutedIds) App.state.scanMutedIds.clear();
                App.renderMultiScanList();
                App.clearArticulo();

                if (App.state.scanMethod === "laser") {
                    setTimeout(() => App.els.laserInput.focus(), 200);
                }
            } else {
                App.vibrate([300]);
                App.toast(data.message || "Error al registrar entrega.", "error", 4000);
            }
        } catch (e) {
            App.hideLoading();
            App.toast(e.message || "Error de conexión.", "error", 5000);
        }
    }
};

App.renderMultiScanList = function() {
    const container = App.els.multiScanList;
    if (App.state.scannedArticulos.length === 0) {
        App.els.multiScanSection.style.display = "none";
        container.innerHTML = "";
        return;
    }

    App.els.multiScanSection.style.display = "block";
    container.innerHTML = App.state.scannedArticulos.map((art, idx) => {
        const warnHtml = art.warning
            ? `<div class="multi-scan-alert">${art.warning}</div>`
            : "";
        return `
            <div class="multi-scan-item" data-index="${idx}">
                <div class="multi-scan-details">
                    <div>${App.escHtml(art.descripcion)} [${App.escHtml(art.talla || "-")}]</div>
                    ${warnHtml}
                </div>
                <button type="button" class="btn-remove-item" onclick="App.removeItemFromMultiScan(${idx})" aria-label="Eliminar">&times;</button>
            </div>
        `;
    }).join("");
};

App.removeItemFromMultiScan = function(idx) {
    const art = App.state.scannedArticulos[idx];
    if (art) {
        if (App.state.scanProcessingIds) App.state.scanProcessingIds.delete(art.id);
        if (App.state.scanMutedIds) App.state.scanMutedIds.delete(art.id);
    }
    App.state.scannedArticulos.splice(idx, 1);
    App.renderMultiScanList();
    App.updateConfirmButton();
    if (App.state.scannedArticulos.length === 0) {
        App.clearArticulo();
    }
};

App.cargarPendientes = async function(rut) {
    if (!rut) return;
    try {
        const data = await API.getPendientes(rut);
        if (data.success && data.pendientes && data.pendientes.length > 0) {
            App.els.devolucionesPendientesSection.style.display = "block";
            App.els.devolucionesPendientesList.innerHTML = data.pendientes.map(p => `
                <div class="pending-return-item"
                     data-articulo-id="${p.articulo_id}"
                     data-transaccion-id="${p.transaccion_id}"
                     data-trabajador="${App.escHtml(p.trabajador || "")}"
                     data-area="${App.escHtml(p.area || "")}">
                    <div class="pending-return-info">
                        <div class="pending-return-title">${App.escHtml(p.descripcion)}</div>
                        <div class="pending-return-date">Retirado el ${App.escHtml(p.hora_salida)}</div>
                    </div>
                    <button type="button" class="btn-quick-return"
                            onclick="App.devolverRapido(${p.articulo_id})">
                        Devolver
                    </button>
                </div>
            `).join("");
        } else {
            App.ocultarPendientes();
        }
    } catch (e) {
        console.error("Error al cargar pendientes:", e);
        App.ocultarPendientes();
    }
};

App.ocultarPendientes = function() {
    App.els.devolucionesPendientesSection.style.display = "none";
    App.els.devolucionesPendientesList.innerHTML = "";
};

App.devolverRapido = async function(articuloId) {
    const pendingItem = document.querySelector(`.pending-return-item[data-articulo-id="${articuloId}"]`);
    const descripcion = pendingItem?.querySelector(".pending-return-title")?.textContent || "artículo";
    const rut = App.els.inputRut.value.trim();
    const nombre = App.els.inputNombre.value.trim() || pendingItem?.dataset.trabajador || "Trabajador";
    const area = App.els.inputArea.value || pendingItem?.dataset.area || "BODEGA";

    if (!rut) {
        App.toast("Ingresa o escanea el RUT del trabajador.", "warning");
        return;
    }

    App.showLoading();
    try {
        const data = await API.registrar("DEVOLUCION", rut, nombre, area, articuloId);
        App.hideLoading();
        if (data.success) {
            App.vibrate([100, 50, 100]);
            App.toast(`Devuelto con éxito: ${descripcion}`, "success");

            App.cargarPendientes(rut);

            App.state.historial.unshift({
                tipo: "devolucion",
                msg: data.message,
                rut,
                area,
                hora: data.hora || "",
            });
            App.renderHistorial();
        } else {
            App.toast(data.message || "Error al registrar devolución.", "error");
        }
    } catch (e) {
        App.hideLoading();
        App.toast(e.message || "Error de conexión.", "error", 5000);
    }
};

App.renderHistorial = function() {
    const container = App.els.historialList;
    App.els.histCount.textContent = App.state.historial.length > 0 ? `(${App.state.historial.length})` : "";

    if (App.state.historial.length === 0) {
        container.innerHTML = `<div class="empty-state" style="padding:16px;"><p>Sin operaciones en esta sesión</p></div>`;
        return;
    }

    const last5 = App.state.historial.slice(0, 5);
    container.innerHTML = last5.map(h => `
        <div class="hist-item ${h.tipo}">
            <div class="hist-dot"></div>
            <div class="hist-info">
                <div class="hist-msg">${App.escHtml(h.msg)}</div>
                <div class="hist-meta">${App.escHtml(h.rut)} · ${App.escHtml(h.area)}</div>
            </div>
            <div class="hist-time">${App.escHtml(h.hora)}</div>
        </div>
    `).join("");
};

App.openCarnetModal = function() {
    App.els.carnetModal.classList.add("active");
    Scanner.startCarnetCamera("carnetReader", (text) => {
        App.onCredentialScanned(text);
    }).catch(e => {
        App.toast("No se pudo iniciar la cámara.", "error");
        App.closeCarnetModal();
        console.error(e);
    });
};

App.closeCarnetModal = function() {
    App.els.carnetModal.classList.remove("active");
    Scanner.stopCarnetCamera();
};
