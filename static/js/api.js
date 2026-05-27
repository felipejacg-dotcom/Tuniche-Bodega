"use strict";

/**
 * api.js — Wrapper centralizado para todas las llamadas al backend Flask.
 * Maneja automaticamente el caso 401 (sesion expirada → logout).
 */
const API = (() => {
    async function _req(url, options = {}) {
        const { skipAuthHandler = false, ...fetchOptions } = options;
        const config = {
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            ...fetchOptions,
        };
        if (config.body && typeof config.body === "object") {
            config.body = JSON.stringify(config.body);
        }
        const res = await fetch(url, config);
        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            data = {};
        }

        if (res.status === 401) {
            // Sesion expirada — forzar logout
            if (!skipAuthHandler && typeof App !== "undefined") App.logout();
            throw new Error(data.message || "Sesion expirada");
        }
        if (!res.ok) {
            throw new Error(data.message || `Error HTTP ${res.status}`);
        }
        return data;
    }

    function _filenameFromDisposition(disposition) {
        if (!disposition) return "cierre-turno.pdf";
        const match = disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
        return match ? decodeURIComponent(match[1].replace(/"/g, "")) : "cierre-turno.pdf";
    }

    return {
        login: (username, password, planta) =>
            _req("/api/login", {
                method: "POST",
                body: { username, password, planta },
                skipAuthHandler: true,
            }),

        logout: () =>
            _req("/api/logout", { method: "POST" }),

        me: (options = {}) => _req("/api/me", options),

        buscarTrabajador: (rut) =>
            _req("/api/buscar_trabajador", { method: "POST", body: { rut } }),

        getArticulos: () => _req("/api/articulos"),

        getRegistros: (estado = "", q = "") =>
            _req(`/api/registros?estado=${encodeURIComponent(estado)}&q=${encodeURIComponent(q)}`),

        getCierreTurno: (desde = "", hasta = "") => {
            const params = new URLSearchParams();
            if (desde) params.append("desde", desde);
            if (hasta) params.append("hasta", hasta);
            return _req(`/api/cierre_turno?${params.toString()}`);
        },

        downloadCierreTurnoPdf: async (desde = "", hasta = "") => {
            const params = new URLSearchParams();
            if (desde) params.append("desde", desde);
            if (hasta) params.append("hasta", hasta);
            const res = await fetch(`/api/cierre_turno/pdf?${params.toString()}`, {
                credentials: "same-origin",
            });
            if (res.status === 401) {
                if (typeof App !== "undefined") App.logout();
                throw new Error("Sesion expirada");
            }
            if (!res.ok) {
                let data = {};
                try {
                    data = await res.json();
                } catch (_) {}
                throw new Error(data.message || `Error HTTP ${res.status}`);
            }
            return {
                blob: await res.blob(),
                filename: _filenameFromDisposition(res.headers.get("Content-Disposition")),
            };
        },

        registrar: (accion, rut, trabajador, area, articulo_id) =>
            _req("/api/registrar", {
                method: "POST",
                body: { accion, rut, trabajador, area, articulo_id },
            }),

        registrarMasivo: (rut, trabajador, area, articulo_ids) =>
            _req("/api/registrar_masivo", {
                method: "POST",
                body: { rut, trabajador, area, articulo_ids },
            }),

        getPendientes: (rut) =>
            _req(`/api/pendientes?rut=${encodeURIComponent(rut)}`),

        getUltimoRetiro: (rut, articulo_id) =>
            _req(`/api/ultimo_retiro?rut=${encodeURIComponent(rut)}&articulo_id=${articulo_id}`),
    };
})();
