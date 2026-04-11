from flask import Flask, request, jsonify, render_template
import mysql.connector
import os
from datetime import datetime
from zoneinfo import ZoneInfo

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
# CREDENCIALES DE SEGURIDAD (Cámbialas cuando quieras)
# ====================================================
def check_auth(username, password):
    credenciales_validas = {
        "bodega": "tuniche2026",
        "admin": "admin123"
    }
    return credenciales_validas.get(username) == password

# ====================================================
# CONEXIÓN DINÁMICA SEGÚN LA PLANTA
# ====================================================
def conectar_db(planta):
    db_name = "bodega_puquillay_real" if planta == "PUQUILLAY" else "bodega_tuniche_real"
    try:
        conexion = mysql.connector.connect(
            host="gateway01.us-east-1.prod.aws.tidbcloud.com",
            port=4000,
            user="4K3HGsTvxGEKd2X.root",
            password="4aJEglVrXOotgXhp",
            database=db_name,
            ssl_verify_cert=False,     
            ssl_verify_identity=False,
            use_pure=True
        )
        return conexion, conexion.cursor()
    except Exception as e:
        print(f"Error de conexión a BD {db_name}: {e}")
        return None, None

@app.route('/')
def index():
    # Carga el HTML. El candado ahora es visual (manejado por el celular)
    return render_template('index.html', areas=AREAS_COMUNES)

@app.route('/login', methods=['POST'])
def api_login():
    data = request.json
    if check_auth(data.get('username'), data.get('password')):
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Usuario o contraseña incorrectos"})

@app.route('/buscar_trabajador', methods=['POST'])
def api_buscar_trabajador():
    data = request.json
    # Validación de seguridad por debajo
    if not check_auth(data.get('username'), data.get('password')):
        return jsonify({"success": False})

    rut = data.get('rut')
    planta = data.get('planta', 'TUNICHE')
    
    if not rut:
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
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "No se recibieron datos."})

    # Validación de seguridad estricta
    if not check_auth(data.get('username'), data.get('password')):
        return jsonify({"success": False, "message": "Acceso denegado. Reinicie la sesión."})

    accion = data.get('accion', 'SALIDA')
    id_prenda_bruto = data.get('articulo_id')
    planta = data.get('planta', 'TUNICHE')

    if not id_prenda_bruto:
        return jsonify({"success": False, "message": "No se leyó el código QR correctamente."})

    id_limpio = str(id_prenda_bruto).split(" | ")[0].strip()

    conexion, cursor = conectar_db(planta)
    if not conexion:
        return jsonify({"success": False, "message": f"Falló la conexión con {planta}."})

    hora_chile = datetime.now(ZoneInfo("America/Santiago")).strftime("%Y-%m-%d %H:%M:%S")

    try:
        if accion == 'DEVOLUCION':
            cursor.execute("""
                SELECT id FROM transacciones 
                WHERE articulo_id = %s AND estado = 'EN TERRENO' 
                ORDER BY id DESC LIMIT 1
            """, (id_limpio,))
            transaccion_abierta = cursor.fetchone()

            if not transaccion_abierta:
                return jsonify({"success": False, "message": "Esta herramienta no registra una salida pendiente."})

            id_registro = transaccion_abierta[0]
            cursor.execute("UPDATE transacciones SET hora_entrada = %s, estado = 'DEVUELTO' WHERE id = %s", (hora_chile, id_registro))
            cursor.execute("UPDATE articulos SET stock_disponible = stock_disponible + 1 WHERE id = %s", (id_limpio,))
            conexion.commit()
            return jsonify({"success": True, "message": "Devolución exitosa. Stock actualizado."})

        else:
            rut = data.get('rut')
            trabajador = data.get('trabajador')
            area = data.get('area')

            if not rut or not trabajador or not area:
                return jsonify({"success": False, "message": "Faltan los datos del trabajador."})

            cursor.execute("SELECT stock_disponible, descripcion FROM articulos WHERE id = %s", (id_limpio,))
            item_data = cursor.fetchone()

            if not item_data:
                return jsonify({"success": False, "message": f"El código ID {id_limpio} no existe en inventario."})

            if item_data[0] <= 0:
                return jsonify({"success": False, "message": f"Sin stock disponible para: {item_data[1]}."})

            cursor.execute("""
                INSERT INTO transacciones (articulo_id, rut, trabajador, area, hora_salida, estado) 
                VALUES (%s, %s, %s, %s, %s, 'EN TERRENO')
            """, (id_limpio, rut, trabajador, area, hora_chile))
            
            cursor.execute("UPDATE articulos SET stock_disponible = stock_disponible - 1 WHERE id = %s", (id_limpio,))
            conexion.commit()
            return jsonify({"success": True, "message": f"Salida de {item_data[1]} registrada."})

    except Exception as e:
        return jsonify({"success": False, "message": f"Error interno: {str(e)}"})
    finally:
        if cursor: cursor.close()
        if conexion: conexion.close()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
