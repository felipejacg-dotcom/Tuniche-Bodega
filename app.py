from flask import Flask, request, jsonify, render_template
import mysql.connector
import os
import hashlib
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Cargamos la "caja fuerte" de variables (funciona en PC local y en Render)
load_dotenv()

app = Flask(__name__)

AREAS_COMUNES = [
    "ABASTECIMIENTO", "ADMINISTRACION", "ASEO", "BAÑOS PLANTA", "BODEGA", 
    "BODEGA AGRICOLA LIBERTAD (TAMBO)", "BODEGA AGRICOLA QUINAHUE", 
    "BODEGA AGRICOLA SAN ALBERTO (FRUSAL)", "BODEGA AGRICOLA TUNITEC (PEUMO)", 
    "BRC", "CAMARA CEREZA", "CAMARA M.INTERNO", "CASILLA ROPA-FILTRO", "CASINO", 
    "COMPAC 1-2", "CONTABILIDAD", "CONTROL CALIDAD", "DATOS E INFORMATICA", 
    "DESAROLLO", "DPTO. COMERCIAL", "ENFERMERIA", "ENSAYO PACKING", "ENVASES", 
    "FILTRO SANITARIO", "FRIGORIFICO", "GERENCIA", "GUARDAROPA FILTRO", 
    "HAND PACK", "I+D", "INOCUIDAD", "INOCUIDAD CENTRAL", 
    "LAVANDERIA MIRIAM SANHUEZA", "LINEA COMPAC 1", "LINEA COMPAC 2", 
    "LOGISTICA", "MANTENCION", "MANTENCION CENTRAL", "MERCADO INTERNO", 
    "MERMA ROPA MAL ESTADO", "OFICINAS ADMINISTRACION", "OPERACIONES", 
    "PACKING", "PACKING SATELITE", "PAÑOL CENTRAL", "PCK CAROZOS", 
    "PCK CEREZAS", "PLANTA RILES", "PLANTA TRATAMIENTO", 
    "PLANTA TUNICHE FRUITS 2 PUQUILLAY", "PORTERIA 1", "PORTERIA 2", 
    "PREVENCION CENTRAL", "PREVENCION DE RIESGOS", "PRODUCCION", 
    "RECEPCION FRUTA", "RR.HH", "SADEMA", "SADEMA CENTRAL", "SAG", 
    "SEGURIDAD", "SERV GRALES CENTRAL", "SERVICIOS GENERALES", "TALLER", 
    "TODAS LAS AREAS", "UNITEC"
]

# ====================================================
# 🛡️ MEJORA 1 y 2: VERIFICACIÓN CENTRALIZADA + SHA-256
# ====================================================
def _verificar_admin(req_data):
    """
    Toma los datos de la petición, hashea la contraseña entrante con SHA-256
    y la compara con la contraseña real escondida en las variables de entorno.
    """
    user = req_data.get('username', '').strip().upper()
    pwd = req_data.get('password', '').strip()
    
    if not user or not pwd:
        return False

    # Encriptamos la clave que escribió el usuario en su celular
    hash_intento = hashlib.sha256(pwd.encode('utf-8')).hexdigest()
    
    # Buscamos la clave real en la caja fuerte de Render (Ej: APP_PASS_BODEGA)
    pwd_real = os.getenv(f"APP_PASS_{user}")
    
    if not pwd_real:
        return False
        
    # Encriptamos la clave real y comparamos (Seguridad Nivel Bancario)
    hash_real = hashlib.sha256(pwd_real.encode('utf-8')).hexdigest()
    
    return hash_intento == hash_real

# ====================================================
# 🛡️ MEJORA 3: ALGORITMO MÓDULO 11 (RUT CHILENO)
# ====================================================
def validar_rut_modulo11(rut):
    """
    Verifica matemáticamente que el RUT sea real. Bloquea dedazos y errores de escáner.
    """
    rut_limpio = rut.replace(".", "").replace("-", "").upper()
    if len(rut_limpio) < 2: return False
    
    cuerpo = rut_limpio[:-1]
    dv_esperado = rut_limpio[-1]
    
    if not cuerpo.isdigit(): return False
    
    suma = 0
    multiplo = 2
    for d in reversed(cuerpo):
        suma += int(d) * multiplo
        multiplo = multiplo + 1 if multiplo < 7 else 2
        
    dv_calculado = 11 - (suma % 11)
    if dv_calculado == 11: dv_final = "0"
    elif dv_calculado == 10: dv_final = "K"
    else: dv_final = str(dv_calculado)
    
    return dv_final == dv_esperado

# ====================================================
# 🛡️ MEJORA 4: CREDENCIALES BD DESDE EL .ENV
# ====================================================
def conectar_db(planta):
    db_name = "bodega_puquillay_real" if planta == "PUQUILLAY" else "bodega_tuniche_real"
    # Obtenemos usuario y clave desde las variables de entorno
    db_usr = os.getenv("DB_USER")
    db_pw = os.getenv("DB_PASS")
    
    if not db_usr or not db_pw:
        print("CRÍTICO: No se encontraron credenciales de BD en el entorno.")
        return None, None

    try:
        conexion = mysql.connector.connect(
            host="gateway01.us-east-1.prod.aws.tidbcloud.com",
            port=4000,
            user=db_usr,
            password=db_pw,
            database=db_name,
            ssl_verify_cert=False,     
            ssl_verify_identity=False,
            use_pure=True
        )
        return conexion, conexion.cursor()
    except Exception as e:
        print(f"Error de conexión a BD {db_name}: {e}")
        return None, None

def obtener_hora_chile():
    hora_utc = datetime.utcnow()
    hora_chile = hora_utc - timedelta(hours=4)
    return hora_chile.strftime("%Y-%m-%d %H:%M:%S")

@app.route('/')
def index():
    return render_template('index.html', areas=AREAS_COMUNES)

@app.route('/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json(force=True, silent=True) or {}
        if _verificar_admin(data):
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Usuario o contraseña incorrectos"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error interno: {str(e)}"})

@app.route('/buscar_trabajador', methods=['POST'])
def api_buscar_trabajador():
    data = request.get_json(force=True, silent=True) or {}
    
    if not _verificar_admin(data):
        return jsonify({"success": False})

    rut = data.get('rut', '')
    planta = data.get('planta', 'TUNICHE')
    
    if not rut or not validar_rut_modulo11(rut):
        return jsonify({"success": False})

    conexion, cursor = conectar_db(planta)
    if not conexion:
        return jsonify({"success": False})

    try:
        cursor.execute("SELECT trabajador, area FROM transacciones WHERE rut = %s ORDER BY id DESC LIMIT 1", (rut,))
        fila = cursor.fetchone()
        if fila:
            return jsonify({"success": True, "nombre": fila[0], "area": fila[1]})
        return jsonify({"success": False})
    except Exception:
        return jsonify({"success": False})
    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()

@app.route('/registrar_salida', methods=['POST'])
def api_registrar_salida():
    data = request.get_json(force=True, silent=True) or {}
    
    if not _verificar_admin(data):
        return jsonify({"success": False, "message": "Acceso denegado. Credenciales inválidas."})

    accion = data.get('accion', 'SALIDA')
    id_prenda_bruto = data.get('articulo_id')
    planta = data.get('planta', 'TUNICHE')
    rut = data.get('rut', '')

    # Validar RUT matemáticamente antes de tocar la base de datos
    if accion == 'SALIDA' and not validar_rut_modulo11(rut):
        return jsonify({"success": False, "message": "RUT Inválido. Revise los números digitados."})

    if not id_prenda_bruto:
        return jsonify({"success": False, "message": "Código QR inválido."})

    id_limpio = str(id_prenda_bruto).split(" | ")[0].strip()

    conexion, cursor = conectar_db(planta)
    if not conexion:
        return jsonify({"success": False, "message": "Fallo de conexión con la Base de Datos."})

    hora_chile = obtener_hora_chile()

    try:
        if accion == 'DEVOLUCION':
            cursor.execute("""
                SELECT id FROM transacciones 
                WHERE articulo_id = %s AND estado = 'EN TERRENO' 
                ORDER BY id DESC LIMIT 1
            """, (id_limpio,))
            transaccion_abierta = cursor.fetchone()

            if not transaccion_abierta:
                return jsonify({"success": False, "message": "La herramienta no registra salida."})

            id_registro = transaccion_abierta[0]
            cursor.execute("UPDATE transacciones SET hora_entrada = %s, estado = 'DEVUELTO' WHERE id = %s", (hora_chile, id_registro))
            cursor.execute("UPDATE articulos SET stock_disponible = stock_disponible + 1 WHERE id = %s", (id_limpio,))
            conexion.commit()
            return jsonify({"success": True, "message": "Devolución exitosa."})

        else:
            trabajador = data.get('trabajador')
            area = data.get('area')

            if not rut or not trabajador or not area:
                return jsonify({"success": False, "message": "Faltan datos del trabajador."})

            cursor.execute("SELECT stock_disponible, descripcion FROM articulos WHERE id = %s", (id_limpio,))
            item_data = cursor.fetchone()

            if not item_data:
                return jsonify({"success": False, "message": "Artículo no existe."})

            if item_data[0] <= 0:
                return jsonify({"success": False, "message": f"Sin stock de: {item_data[1]}."})

            cursor.execute("""
                INSERT INTO transacciones (articulo_id, rut, trabajador, area, hora_salida, estado) 
                VALUES (%s, %s, %s, %s, %s, 'EN TERRENO')
            """, (id_limpio, rut, trabajador, area, hora_chile))
            
            cursor.execute("UPDATE articulos SET stock_disponible = stock_disponible - 1 WHERE id = %s", (id_limpio,))
            conexion.commit()
            return jsonify({"success": True, "message": f"Salida de {item_data[1]} registrada."})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
