"use strict";

/**
 * scanner.js — Manejo de escaner laser (Zebra TC27) y camara (html5-qrcode).
 *
 * Logica del laser:
 * - El escaner laser (Zebra, Honeywell, etc.) envia los caracteres rapidamente
 *   (tipicamente < 50ms entre teclas) y termina con Enter.
 * - El teclado manual escribe lento (> 80ms).
 * - Este modulo detecta automaticamente si es laser o teclado manual.
 */
const Scanner = (() => {
    // ── Camara (html5-qrcode) ──────────────────────────────────────
    let _articleQr = null;
    let _carnetQr = null;

    async function startArticleCamera(elementId, onScan) {
        if (_articleQr) {
            try { await _articleQr.stop(); } catch (_) {}
        }
        _articleQr = new Html5Qrcode(elementId);
        await _articleQr.start(
            { facingMode: "environment" },
            { fps: 15, qrbox: { width: 240, height: 140 } },
            (text) => { onScan(text.trim()); },
            () => {}
        );
    }

    async function stopArticleCamera() {
        if (_articleQr) {
            try { await _articleQr.stop(); } catch (_) {}
            _articleQr = null;
        }
    }

    async function startCarnetCamera(elementId, onScan) {
        if (_carnetQr) {
            try { await _carnetQr.stop(); } catch (_) {}
        }
        _carnetQr = new Html5Qrcode(elementId);
        await _carnetQr.start(
            { facingMode: "environment" },
            { fps: 15, qrbox: { width: 260, height: 160 } },
            (text) => { onScan(text.trim()); },
            () => {}
        );
    }

    async function stopCarnetCamera() {
        if (_carnetQr) {
            try { await _carnetQr.stop(); } catch (_) {}
            _carnetQr = null;
        }
    }

    // ── Laser (keyboard wedge) ────────────────────────────────────
    function initLaser(inputEl, onScan) {
        inputEl.value = "";

        inputEl.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const val = inputEl.value.trim();
                if (val.length > 0) {
                    onScan(val);
                    inputEl.value = "";
                }
            }
        });

        // Paste event: algunos scanners pegan el codigo completo
        inputEl.addEventListener("paste", () => {
            setTimeout(() => {
                const val = inputEl.value.trim();
                if (val.length > 0) {
                    onScan(val);
                    inputEl.value = "";
                }
            }, 60);
        });
    }

    // ── RUT Parser (carnet chileno) ───────────────────────────────
    function parseCredential(rawText) {
        const text = rawText.trim();
        let rut = null;
        let nombre = null;

        try {
            // Formato 1: URL-style con RUN= y name=
            if (/RUN=/i.test(text) || /run=/i.test(text)) {
                const qs = text.includes("?")
                    ? text.substring(text.indexOf("?") + 1)
                    : text;
                const params = new URLSearchParams(qs);
                rut = params.get("RUN") || params.get("run");
                const nameParam = params.get("name") || params.get("nombre");
                if (nameParam) {
                    nombre = decodeURIComponent(nameParam)
                        .replace(/\+/g, " ")
                        .replace(/\s+/g, " ")
                        .trim();
                }
            }
            // Formato 2: PDF417 chileno raw (>= 70 chars)
            else if (text.length >= 70) {
                const rawRut = text.substring(0, 9).trim().replace(/^0+/, "");
                if (rawRut.length >= 7) {
                    rut = rawRut;
                    nombre = text
                        .substring(19, 55)
                        .replace(/[^A-Za-z\u00C0-\u024F .]/g, "")
                        .trim();
                }
            }
            // Fallback: buscar patron de RUT en cualquier texto
            if (!rut) {
                const match = text.match(/\b(\d{1,2}\.?\d{3}\.?\d{3}-[\dkK])\b/i);
                if (match) rut = match[1];
            }
        } catch (e) {
            console.error("Error parseando credencial:", e);
        }

        return { rut, nombre };
    }

    // ── RUT Formatter ─────────────────────────────────────────────
    function formatRut(rut) {
        const clean = String(rut).replace(/[^0-9kK]/g, "").toUpperCase();
        if (clean.length < 2) return clean;
        const dv = clean.slice(-1);
        const body = clean.slice(0, -1).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        return `${body}-${dv}`;
    }

    // ── Article Code Parser ───────────────────────────────────────
    // Intentamos extraer el ID numerico del articulo del codigo escaneado.
    // La pistola lee el codigo del sticker Zebra, que puede ser solo el ID
    // o un string compuesto como "12 | Chaleco (Talla: M) - Unidad".
    function parseArticleCode(text) {
        const clean = text.trim();
        // Caso 1: solo numero
        const numMatch = clean.match(/^(\d+)$/);
        if (numMatch) return parseInt(numMatch[1], 10);
        // Caso 2: empieza con numero seguido de espacio o |
        const prefixMatch = clean.match(/^(\d+)[\s|]/);
        if (prefixMatch) return parseInt(prefixMatch[1], 10);
        return null;
    }

    return {
        initLaser,
        startArticleCamera,
        stopArticleCamera,
        startCarnetCamera,
        stopCarnetCamera,
        parseCredential,
        parseArticleCode,
        formatRut,
    };
})();
