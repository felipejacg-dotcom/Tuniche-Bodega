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
        if (res.status === 401) {
            // Sesion expirada — forzar logout
            if (!skipAuthHandler && typeof App !== "undefined") App.logout();
            throw new Error("Sesion expirada");
        }
        return res.json();
    }

    return {
        login: (username, password, planta) =>
            _req("/api/login", { method: "POST", body: { username, password, planta } }),

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
    };
})();
