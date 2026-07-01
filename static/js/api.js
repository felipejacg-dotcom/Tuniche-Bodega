"use strict";

/**
 * api.js — Wrapper centralizado para todas las llamadas al backend Flask.
 * Maneja automaticamente el caso 401 (sesion expirada → logout).
 */
const API = (() => {
    function _getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(";").shift();
        return "";
    }

    async function _req(url, options = {}) {
        const { skipAuthHandler = false, ...fetchOptions } = options;
        const csrfToken = _getCookie("csrf_token");
        const headers = {
            "Content-Type": "application/json",
            ...fetchOptions.headers
        };
        if (csrfToken) {
            headers["X-CSRF-Token"] = csrfToken;
        }
        const config = {
            credentials: "same-origin",
            ...fetchOptions,
            headers,
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
        login: (username, password, planta, modulo = "PANOL") =>
            _req("/api/login", {
                method: "POST",
                body: { username, password, planta, modulo },
                skipAuthHandler: true,
            }),

        logout: () =>
            _req("/api/logout", { method: "POST" }),

        me: (options = {}) => _req("/api/me", options),

        buscarTrabajador: (rut) =>
            _req("/api/buscar_trabajador", { method: "POST", body: { rut } }),

        getArticulos: () => _req("/api/articulos"),

        getRegistros: (estado = "", q = "", desde = "", hasta = "", page = 1, limit = 50) => {
            const params = new URLSearchParams();
            if (estado) params.append("estado", estado);
            if (q) params.append("q", q);
            if (desde) params.append("desde", desde);
            if (hasta) params.append("hasta", hasta);
            if (page) params.append("page", page);
            if (limit) params.append("limit", limit);
            return _req(`/api/registros?${params.toString()}`);
        },

        editarRegistro: (id, payload) =>
            _req(`/api/registros/${encodeURIComponent(id)}`, {
                method: "PATCH",
                body: payload,
            }),

        getCierreTurno: (tipoTurno = "", desde = "", hasta = "") => {
            const params = new URLSearchParams();
            if (tipoTurno) params.append("tipo_turno", tipoTurno);
            if (desde) params.append("desde", desde);
            if (hasta) params.append("hasta", hasta);
            return _req(`/api/cierre_turno?${params.toString()}`);
        },

        confirmarCierreTurno: (tipoTurno = "", desde = "", hasta = "") =>
            _req("/api/cierre_turno", {
                method: "POST",
                body: { tipo_turno: tipoTurno, desde, hasta },
            }),

        downloadCierreTurnoPdf: async (tipoTurno = "", desde = "", hasta = "") => {
            const params = new URLSearchParams();
            if (tipoTurno) params.append("tipo_turno", tipoTurno);
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

        registrar: (accion, rut, trabajador, area, subarea, articulo_id, cantidad = 1) =>
            _req("/api/registrar", {
                method: "POST",
                body: { accion, rut, trabajador, area, subarea, articulo_id, cantidad },
            }),

        registrarMasivo: (rut, trabajador, area, subarea, articulos) =>
            _req("/api/registrar_masivo", {
                method: "POST",
                body: { rut, trabajador, area, subarea, articulos },
            }),

        getPendientes: (rut) =>
            _req(`/api/pendientes?rut=${encodeURIComponent(rut)}`),

        getUltimoRetiro: (rut, articulo_id) =>
            _req(`/api/ultimo_retiro?rut=${encodeURIComponent(rut)}&articulo_id=${articulo_id}`),

        getEmbalajeResumen: (texto = "", ubicacion = "Todas", estado = "Todos", desde = "", hasta = "") => {
            const params = new URLSearchParams();
            if (texto) params.append("texto", texto);
            if (ubicacion) params.append("ubicacion", ubicacion);
            if (estado) params.append("estado", estado);
            if (desde) params.append("desde", desde);
            if (hasta) params.append("hasta", hasta);
            return _req(`/api/embalaje/resumen?${params.toString()}`);
        },

        getEmbalajeExistencias: (texto = "", ubicacion = "Todas", estado = "Todos", desde = "", hasta = "") => {
            const params = new URLSearchParams();
            if (texto) params.append("texto", texto);
            if (ubicacion) params.append("ubicacion", ubicacion);
            if (estado) params.append("estado", estado);
            if (desde) params.append("desde", desde);
            if (hasta) params.append("hasta", hasta);
            return _req(`/api/embalaje/existencias?${params.toString()}`);
        },

        getEmbalajeExistencia: (clave) =>
            _req(`/api/embalaje/existencia?clave=${encodeURIComponent(clave)}`),

        getEmbalajeMovimientos: (texto = "", limite = 200) => {
            const params = new URLSearchParams();
            if (texto) params.append("texto", texto);
            if (limite) params.append("limite", limite);
            return _req(`/api/embalaje/movimientos?${params.toString()}`);
        },

        registrarEmbalajeArmado: (payload) =>
            _req("/api/embalaje/armado", {
                method: "POST",
                body: payload,
            }),

        registrarEmbalajeTraslado: (payload) =>
            _req("/api/embalaje/traslado", {
                method: "POST",
                body: payload,
            }),
    };
})();
