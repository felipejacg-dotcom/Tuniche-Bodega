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
