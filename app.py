<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bodega Tuniche - Escáner</title>
    <meta name="description" content="Sistema de escaneo y gestión de bodega Tuniche Fruits">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-secondary: #111827;
            --bg-card: rgba(17, 24, 39, 0.7);
            --bg-card-hover: rgba(30, 41, 59, 0.8);
            --border-subtle: rgba(148, 163, 184, 0.1);
            --border-glow: rgba(99, 102, 241, 0.4);
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-indigo: #6366f1;
            --accent-indigo-light: #818cf8;
            --accent-emerald: #10b981;
            --accent-emerald-glow: rgba(16, 185, 129, 0.25);
            --accent-amber: #f59e0b;
            --accent-amber-glow: rgba(245, 158, 11, 0.25);
            --accent-red: #ef4444;
            --accent-red-glow: rgba(239, 68, 68, 0.2);
            --gradient-main: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%);
            --gradient-emerald: linear-gradient(135deg, #059669 0%, #10b981 100%);
            --gradient-amber: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);
            --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.3), 0 1px 2px rgba(0, 0, 0, 0.2);
            --shadow-glow-indigo: 0 0 30px rgba(99, 102, 241, 0.15);
            --radius-lg: 16px;
            --radius-md: 12px;
            --radius-sm: 8px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }

        body::before {
            content: '';
            position: fixed;
            top: -50%; left: -50%; width: 200%; height: 200%;
            background: radial-gradient(ellipse at 20% 50%, rgba(99, 102, 241, 0.08) 0%, transparent 50%),
                        radial-gradient(ellipse at 80% 20%, rgba(139, 92, 246, 0.06) 0%, transparent 50%),
                        radial-gradient(ellipse at 50% 80%, rgba(16, 185, 129, 0.04) 0%, transparent 50%);
            z-index: 0;
            animation: bgShift 20s ease-in-out infinite alternate;
        }

        @keyframes bgShift {
            0% { transform: translate(0, 0) rotate(0deg); }
            100% { transform: translate(-5%, 3%) rotate(3deg); }
        }

        /* ==================================================================== */
        /* NUEVO: PANTALLA DE BLOQUEO (CANDADO VISUAL) */
        /* ==================================================================== */
        #lockScreen {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background-color: var(--bg-primary);
            z-index: 99999;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
            transition: opacity 0.5s ease, visibility 0.5s ease;
        }

        .lock-container {
            background: var(--bg-card);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 40px 30px;
            text-align: center;
            max-width: 350px;
            width: 100%;
            box-shadow: 0 0 50px rgba(99, 102, 241, 0.1);
        }

        .lock-icon {
            font-size: 3rem;
            margin-bottom: 15px;
            display: block;
            color: var(--accent-indigo);
            text-shadow: var(--shadow-glow-indigo);
        }

        .lock-title {
            font-size: 1.4rem;
            font-weight: 800;
            margin-bottom: 5px;
            letter-spacing: -0.02em;
        }

        .lock-subtitle {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 25px;
        }

        .pin-input {
            width: 100%;
            background: rgba(15, 23, 42, 0.8);
            border: 2px solid var(--border-subtle);
            color: white;
            font-size: 2rem;
            font-weight: 800;
            text-align: center;
            letter-spacing: 15px;
            padding: 15px;
            border-radius: var(--radius-md);
            margin-bottom: 20px;
            outline: none;
            transition: all 0.3s ease;
        }

        .pin-input:focus {
            border-color: var(--accent-indigo);
            box-shadow: 0 0 15px rgba(99, 102, 241, 0.3);
        }

        .pin-error {
            color: var(--accent-red);
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 15px;
            min-height: 20px;
            opacity: 0;
            transition: opacity 0.3s;
        }

        .btn-unlock {
            width: 100%;
            background: var(--gradient-main);
            color: white;
            border: none;
            padding: 14px;
            border-radius: var(--radius-md);
            font-weight: 700;
            font-size: 1rem;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .btn-unlock:active { transform: scale(0.98); }
        
        /* Ocultar la app principal inicialmente */
        #appContent {
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.6s ease 0.2s;
        }
        /* ==================================================================== */

        .top-bar {
            position: relative;
            z-index: 10;
            background: rgba(17, 24, 39, 0.85);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border-subtle);
            padding: 14px 0;
        }

        .top-bar .brand { display: flex; align-items: center; gap: 12px; }

        .brand-icon {
            width: 38px; height: 38px; border-radius: 10px;
            background: var(--gradient-main);
            display: flex; align-items: center; justify-content: center;
            font-size: 1.1rem; box-shadow: 0 0 20px rgba(99, 102, 241, 0.3);
        }

        .brand-text { font-weight: 700; font-size: 1.15rem; color: var(--text-primary); }
        .brand-sub { font-size: 0.7rem; color: var(--text-muted); font-weight: 500; text-transform: uppercase; letter-spacing: 0.08em; }

        .main-container {
            position: relative; z-index: 5; max-width: 520px; margin: 0 auto; padding: 20px 16px 40px;
        }

        .glass-card {
            background: var(--bg-card); backdrop-filter: blur(16px);
            border: 1px solid var(--border-subtle); border-radius: var(--radius-lg);
            box-shadow: var(--shadow-card); margin-bottom: 16px; overflow: hidden;
        }

        .card-inner { padding: 20px; }

        .section-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
        .section-number {
            width: 28px; height: 28px; border-radius: 8px; background: var(--gradient-main);
            display: flex; align-items: center; justify-content: center;
            font-size: 0.75rem; font-weight: 700; color: white;
        }
        .section-title { font-size: 0.95rem; font-weight: 600; color: var(--text-primary); }

        .mode-card { position: relative; overflow: hidden; }
        .mode-card::before {
            content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
            border-radius: 0 4px 4px 0; transition: background 0.4s ease;
        }
        .mode-card.mode-salida::before { background: var(--gradient-amber); }
        .mode-card.mode-devolucion::before { background: var(--gradient-emerald); }
        .mode-card.mode-salida { background: linear-gradient(135deg, rgba(245, 158, 11, 0.06) 0%, var(--bg-card) 100%); }
        .mode-card.mode-devolucion { background: linear-gradient(135deg, rgba(16, 185, 129, 0.06) 0%, var(--bg-card) 100%); }

        .mode-inner { padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; }
        .mode-label { display: flex; align-items: center; gap: 10px; }
        .mode-icon { font-size: 1.4rem; }
        .mode-text-group { display: flex; flex-direction: column; }
        .mode-text-sub { font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em; font-weight: 500; }

        #textoModo { font-weight: 800; font-size: 1.05rem; transition: color 0.4s ease; }
        .modo-salida-text { color: var(--accent-amber); }
        .modo-devolucion-text { color: var(--accent-emerald); }

        .switch-ios { position: relative; display: inline-block; width: 56px; height: 30px; margin: 0; }
        .switch-ios input { opacity: 0; width: 0; height: 0; }
        .slider {
            position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
            background-color: var(--accent-amber); transition: all 0.4s; border-radius: 30px;
        }
        .slider:before {
            position: absolute; content: ""; height: 24px; width: 24px; left: 3px; bottom: 3px;
            background-color: white; transition: all 0.4s; border-radius: 50%;
        }
        input:checked + .slider { background-color: var(--accent-emerald); }
        input:checked + .slider:before { transform: translateX(26px); }

        .form-input {
            width: 100%; padding: 12px 16px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);
            background: rgba(15, 23, 42, 0.6); color: var(--text-primary); font-size: 0.9rem; margin-bottom: 10px; outline: none;
        }
        .form-input:focus { border-color: var(--accent-indigo); background: rgba(15, 23, 42, 0.8); }
        
        select.form-input { appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%2394a3b8' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10l-5 5z'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 14px center; padding-right: 36px; }
        select.form-input option { background: var(--bg-secondary); color: var(--text-primary); }

        .method-pills { display: flex; gap: 6px; background: rgba(15, 23, 42, 0.5); border-radius: var(--radius-md); padding: 4px; margin-bottom: 16px; }
        .method-pills input[type="radio"] { display: none; }
        .method-pill { flex: 1; text-align: center; padding: 10px 8px; border-radius: var(--radius-sm); font-size: 0.8rem; font-weight: 600; color: var(--text-muted); cursor: pointer; transition: all 0.3s; }
        .method-pill:hover { background: rgba(99, 102, 241, 0.08); }
        .method-pills input[type="radio"]:checked + .method-pill { background: var(--gradient-main); color: white; }

        .laser-box {
            width: 100%; padding: 18px 16px; border-radius: var(--radius-md); border: 2px dashed rgba(99, 102, 241, 0.3);
            background: rgba(99, 102, 241, 0.04); color: var(--accent-indigo-light); font-size: 1.1rem; font-weight: 700; text-align: center; outline: none;
        }
        .laser-box:focus { border-color: var(--accent-indigo); background: rgba(99, 102, 241, 0.08); }

        #reader { width: 100%; border-radius: var(--radius-md); overflow: hidden; margin-bottom: 12px; border: 1px solid var(--border-subtle); }
        
        .help-text { font-size: 0.78rem; color: var(--text-muted); margin-bottom: 12px; display: flex; align-items: center; gap: 6px; }
        .help-text .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent-indigo); animation: pulse-dot 2s infinite; }
        @keyframes pulse-dot { 0%, 100% { opacity: 0.4; transform: scale(1); } 50% { opacity: 1; transform: scale(1.3); } }

        .result-box { border-radius: var(--radius-md); padding: 14px 16px; font-size: 0.88rem; font-weight: 600; margin-top: 16px; display: none; }
        .result-idle { background: rgba(100, 116, 139, 0.08); color: var(--text-muted); }
        .result-loading { background: rgba(99, 102, 241, 0.08); color: var(--accent-indigo-light); }
        .result-success { background: rgba(16, 185, 129, 0.08); color: var(--accent-emerald); }
        .result-error { background: rgba(239, 68, 68, 0.08); color: var(--accent-red); }
        .result-warning { background: rgba(245, 158, 11, 0.08); color: var(--accent-amber); }

        .status-bar { position: fixed; bottom: 0; left: 0; right: 0; z-index: 50; background: rgba(17, 24, 39, 0.92); padding: 10px; display: flex; justify-content: center; align-items: center; gap: 8px; border-top: 1px solid var(--border-subtle); }
        .status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent-emerald); animation: pulse-dot 2s infinite; }
        .status-text { font-size: 0.72rem; color: var(--text-muted); }

        .scan-carnet-btn { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; padding: 12px; margin-bottom: 12px; border-radius: var(--radius-md); border: 1px solid rgba(99, 102, 241, 0.3); background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(139, 92, 246, 0.08)); color: var(--accent-indigo-light); font-weight: 600; cursor: pointer; }
        .scan-carnet-btn .btn-badge { background: var(--gradient-main); color: white; font-size: 0.62rem; padding: 2px 7px; border-radius: 4px; }

        .carnet-modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.85); z-index: 1000; display: flex; align-items: center; justify-content: center; padding: 16px; opacity: 0; visibility: hidden; transition: 0.3s; }
        .carnet-modal-overlay.active { opacity: 1; visibility: visible; }
        .carnet-modal { width: 100%; max-width: 440px; background: var(--bg-secondary); border-radius: var(--radius-lg); transform: scale(0.9); transition: 0.3s; }
        .carnet-modal-overlay.active .carnet-modal { transform: scale(1); }
        .carnet-modal-header { padding: 16px; display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); }
        .carnet-modal-body { padding: 16px; }

        .history-list { display: flex; flex-direction: column; gap: 8px; }
        .history-item { display: flex; gap: 12px; padding: 12px; border-radius: var(--radius-md); background: rgba(15, 23, 42, 0.5); border: 1px solid var(--border-subtle); }
        .history-item.salida-item { border-left: 3px solid var(--accent-amber); }
        .history-item.devolucion-item { border-left: 3px solid var(--accent-emerald); }
        .history-item.error-item { border-left: 3px solid var(--accent-red); opacity: 0.7; }
        .history-msg { font-size: 0.82rem; font-weight: 600; }
        .history-time { font-size: 0.7rem; color: var(--text-muted); }
    </style>
</head>
<body>

<div id="lockScreen">
    <div class="lock-container">
        <span class="lock-icon">🔒</span>
        <h2 class="lock-title">SGB Móvil</h2>
        <p class="lock-subtitle">Ingrese PIN de acceso a Bodega</p>
        
        <input type="password" id="pinInput" class="pin-input" maxlength="4" placeholder="••••" inputmode="numeric" pattern="[0-9]*">
        
        <div id="pinError" class="pin-error"></div>
        
        <button class="btn-unlock" onclick="verificarPin()">DESBLOQUEAR SISTEMA</button>
    </div>
</div>

<div id="appContent">
    <div class="top-bar">
        <div class="container" style="max-width:520px;">
            <div class="brand">
                <div class="brand-icon">⚙️</div>
                <div>
                    <div class="brand-text">Tuniche Móvil</div>
                    <div class="brand-sub">Sistema de Bodega</div>
                </div>
            </div>
        </div>
    </div>

    <div class="main-container">
        <div class="glass-card mode-card mode-salida" id="cardModo">
            <div class="mode-inner">
                <div class="mode-label">
                    <span class="mode-icon" id="modeIcon">📤</span>
                    <div class="mode-text-group">
                        <span class="mode-text-sub">Modo activo</span>
                        <span id="textoModo" class="modo-salida-text">SALIDA</span>
                    </div>
                </div>
                <label class="switch-ios">
                    <input type="checkbox" id="toggleModo" onchange="cambiarModo()">
                    <span class="slider"></span>
                </label>
            </div>
        </div>

        <div class="glass-card">
            <div class="card-inner">
                <div class="section-header">
                    <div class="section-number">1</div>
                    <span class="section-title">Datos del Trabajador</span>
                </div>
                <button type="button" class="scan-carnet-btn" onclick="abrirEscanerCarnet()">
                    <span class="btn-icon">🪪</span> Escanear Carnet Chileno <span class="btn-badge">QR</span>
                </button>
                <input type="text" id="rut" class="form-input" placeholder="RUT (Ej: 12.345.678-9)">
                <input type="text" id="trabajador" class="form-input" placeholder="Nombre completo">
                <select id="area" class="form-input">
                    <option value="" disabled selected>Seleccione Área...</option>
                    {% for area in areas %}
                    <option value="{{ area }}">{{ area }}</option>
                    {% endfor %}
                </select>
            </div>
        </div>

        <div class="glass-card">
            <div class="card-inner">
                <div class="section-header">
                    <div class="section-number">2</div>
                    <span class="section-title">Método de Escaneo</span>
                </div>

                <div class="method-pills" role="group">
                    <input type="radio" name="btnradio" id="btn_laser" checked onclick="activarLaser()">
                    <label class="method-pill" for="btn_laser">🔫 Láser</label>

                    <input type="radio" name="btnradio" id="btn_cam_trasera" onclick="activarCamara('environment')">
                    <label class="method-pill" for="btn_cam_trasera">📸 Trasera</label>

                    <input type="radio" name="btnradio" id="btn_cam_frontal" onclick="activarCamara('user')">
                    <label class="method-pill" for="btn_cam_frontal">🤳 Frontal</label>
                </div>

                <div id="laser_section">
                    <div class="help-text"><span class="dot"></span> Dispara el gatillo de la Zebra aquí</div>
                    <input type="text" id="laser_input" class="laser-box" placeholder="[ DISPARA AQUÍ ]" autocomplete="off" readonly onfocus="this.removeAttribute('readonly')">
                </div>

                <div id="camara_section" style="display: none;">
                    <div id="reader"></div>
                </div>

                <div id="resultado" class="result-box result-idle">Esperando escaneo...</div>
            </div>
        </div>

        <div class="glass-card">
            <div class="card-inner">
                <div class="section-header">
                    <div class="section-number">3</div>
                    <span class="section-title">Últimos Registros</span>
                </div>
                <div id="historyList" class="history-list">
                    <div style="text-align: center; color: var(--text-muted); font-size: 0.8rem;">📋 Sin registros en esta sesión</div>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="carnet-modal-overlay" id="carnetModalOverlay">
    <div class="carnet-modal">
        <div class="carnet-modal-header">
            <div style="font-weight: 700; color: white;">🪪 Escanear Carnet</div>
            <button style="background:none; border:none; color:red; font-size:1.2rem;" onclick="cerrarEscanerCarnet()">✕</button>
        </div>
        <div class="carnet-modal-body">
            <div id="carnetReader"></div>
        </div>
    </div>
</div>

<div class="status-bar">
    <span class="status-dot"></span>
    <span class="status-text">Conectado — Tuniche Fruits</span>
</div>

<script>
    // =====================================================
    // LÓGICA DEL CANDADO
    // =====================================================
    const PIN_SECRETO = "2026"; // <-- AQUÍ CAMBIAS LA CLAVE DEL MES
    
    // Enfocar automáticamente el input del PIN al cargar
    window.onload = () => {
        document.getElementById('pinInput').focus();
    };

    // Permitir usar la tecla Enter para desbloquear
    document.getElementById('pinInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            verificarPin();
        }
    });

    function verificarPin() {
        const input = document.getElementById('pinInput').value;
        const errorDiv = document.getElementById('pinError');
        
        if (input === PIN_SECRETO) {
            // Clave Correcta: Ocultar Candado, Mostrar App y prender cámara
            errorDiv.style.opacity = '0';
            document.getElementById('lockScreen').style.opacity = '0';
            document.getElementById('lockScreen').style.visibility = 'hidden';
            
            document.getElementById('appContent').style.opacity = '1';
            document.getElementById('appContent').style.visibility = 'visible';
            
            // Encendemos los motores del escáner solo cuando ya entró
            html5QrCode = new Html5Qrcode("reader");
            activarLaser(); 
        } else {
            // Clave Incorrecta
            errorDiv.innerText = "PIN Incorrecto. Intente nuevamente.";
            errorDiv.style.opacity = '1';
            document.getElementById('pinInput').value = '';
            document.getElementById('pinInput').focus();
            
            // Efecto de vibración de error en la caja
            const box = document.querySelector('.lock-container');
            box.style.transform = 'translateX(10px)';
            setTimeout(() => box.style.transform = 'translateX(-10px)', 50);
            setTimeout(() => box.style.transform = 'translateX(10px)', 100);
            setTimeout(() => box.style.transform = 'translateX(0)', 150);
            vibrarCelular([300]);
        }
    }


    // =====================================================
    // LÓGICA DE LA APP ORIGINAL
    // =====================================================
    let isProcessing = false;
    let lastScannedCode = "";
    let html5QrCode;
    let carnetQrScanner = null;

    function abrirEscanerCarnet() {
        document.getElementById('carnetModalOverlay').classList.add('active');
        if (!carnetQrScanner) carnetQrScanner = new Html5Qrcode("carnetReader");
        carnetQrScanner.start(
            { facingMode: "environment" }, { fps: 10, qrbox: { width: 250, height: 250 } },
            (decodedText) => { procesarCarnetDesdeScanner(decodedText); },
            (errorMessage) => { }
        ).catch(() => { alert("Error de cámara"); });
    }

    function cerrarEscanerCarnet() {
        document.getElementById('carnetModalOverlay').classList.remove('active');
        if (carnetQrScanner && carnetQrScanner.isScanning) carnetQrScanner.stop();
    }

    function procesarCarnetDesdeScanner(data) {
        let rut = null; let nombre = null;
        if (data.includes('RUN=') || data.includes('run=')) {
            let qs = data.includes('?') ? data.substring(data.indexOf('?') + 1) : data;
            const params = new URLSearchParams(qs);
            rut = params.get('RUN') || params.get('run');
            if (params.get('name')) nombre = decodeURIComponent(params.get('name')).replace(/\+/g, ' ').replace(/\s+/g, ' ').trim();
        }
        if (!rut && data.length >= 70) {
            let rawRut = data.substring(0, 9).trim().replace(/^0+/, '');
            if (rawRut.length >= 7) { rut = rawRut; nombre = data.substring(19, 49).replace(/[^A-Za-záéíóúñÁÉÍÓÚÑ .]/g, '').trim(); }
        }
        if (!rut) {
            const match = data.match(/\b(\d{1,2}\.?\d{3}\.?\d{3}-[\dkK])\b/i);
            if (match) rut = match[1];
        }

        if (rut) {
            document.getElementById('rut').value = formatearRut(rut);
            if (nombre) document.getElementById('trabajador').value = nombre;
            vibrarCelular([100]);
            cerrarEscanerCarnet();
        } else {
            vibrarCelular([300]);
        }
    }

    function cambiarModo() {
        const toggle = document.getElementById("toggleModo");
        const texto = document.getElementById("textoModo");
        const card = document.getElementById("cardModo");
        const icon = document.getElementById("modeIcon");

        if (toggle.checked) {
            texto.innerText = "DEVOLUCIÓN"; texto.className = "modo-devolucion-text";
            icon.innerText = "📥"; card.className = "glass-card mode-card mode-devolucion";
        } else {
            texto.innerText = "SALIDA"; texto.className = "modo-salida-text";
            icon.innerText = "📤"; card.className = "glass-card mode-card mode-salida";
        }
    }

    function routerEscaneo(codigo) {
        const rut = document.getElementById('rut').value;
        const trabajador = document.getElementById('trabajador').value;
        const area = document.getElementById('area').value;
        const accion = document.getElementById('toggleModo').checked ? 'DEVOLUCION' : 'SALIDA';
        const resDiv = document.getElementById('resultado');

        if(accion === 'SALIDA' && (!rut || !trabajador || !area)) {
            resDiv.className = "result-box result-warning"; resDiv.style.display = "block";
            resDiv.innerText = "⚠️ Faltan datos del trabajador."; vibrarCelular([300]); return;
        }

        resDiv.className = "result-box result-loading"; resDiv.style.display = "block";
        resDiv.innerText = "⏳ Procesando..."; isProcessing = true;

        fetch('/registrar_salida', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ accion: accion, rut: rut, trabajador: trabajador, area: area, articulo_id: codigo })
        }).then(r => r.json()).then(data => {
            if(data.success) {
                resDiv.className = "result-box result-success"; resDiv.innerHTML = "✅ " + data.message;
                vibrarCelular([100]);
            } else {
                resDiv.className = "result-box result-error"; resDiv.innerHTML = "❌ " + data.message;
                vibrarCelular([300]);
            }
            setTimeout(() => { resDiv.className = "result-box result-idle"; resDiv.innerText = "Esperando..."; isProcessing = false; }, 1500);
        });
    }

    function activarLaser() {
        if (html5QrCode && html5QrCode.isScanning) html5QrCode.stop();
        document.getElementById('camara_section').style.display = 'none';
        document.getElementById('laser_section').style.display = 'block';
    }

    function activarCamara(modo) {
        if (html5QrCode && html5QrCode.isScanning) html5QrCode.stop();
        document.getElementById('laser_section').style.display = 'none';
        document.getElementById('camara_section').style.display = 'block';
        html5QrCode.start({ facingMode: modo }, { fps: 10 }, (txt) => {
            if (txt !== lastScannedCode) { lastScannedCode = txt; routerEscaneo(txt); setTimeout(() => lastScannedCode="", 2000); }
        }, () => {});
    }

    const laserInput = document.getElementById('laser_input');
    let scanTimer;
    laserInput.addEventListener('input', () => {
        clearTimeout(scanTimer);
        if(laserInput.value.trim().length > 0) {
            scanTimer = setTimeout(() => { routerEscaneo(laserInput.value.trim()); laserInput.value = ''; }, 150);
        }
    });

    function formatearRut(r) {
        let l = r.replace(/[^0-9kK]/g, '').toUpperCase(); if(l.length<2) return l;
        return l.slice(0,-1).replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "-" + l.slice(-1);
    }
    
    function vibrarCelular(p) { if(navigator.vibrate) navigator.vibrate(p); }
</script>
</body>
</html>
