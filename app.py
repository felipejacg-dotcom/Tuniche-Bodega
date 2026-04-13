from flask import Flask, render_template, request, jsonify
import mysql.connector
import os
from dotenv import load_dotenv

# Configuración inicial
app = Flask(__name__)
load_dotenv()

# ===========================================================================
# 1. CONFIGURACIÓN DE SEGURIDAD (LOGIN)
# ===========================================================================
# CAMBIA LAS CLAVES AQUÍ PARA QUE COINCIDAN CON TU .EXE
USUARIOS_PERMITIDOS = {
    "bodega": "tuniche2026",  # Pon aquí la clave que usas en el celular
    "admin": "admin123"
}

def validar_acceso(user, password):
    """Verifica si el usuario y contraseña son correctos"""
    return USUARIOS_PERMITIDOS.get(user) == password

# ===========================================================================
# 2. CONFIGURACIÓN DE BASE DE DATOS (TiDB CLOUD)
# ===========================================================================
def get_db_connection(planta):
    """Crea una conexión dinámica según la planta seleccionada"""
    # Mapeo de planta a nombre de base de datos real
    db_name = "bodega_tuniche_real" if planta == "TUNICHE" else "bodega_puquillay_real"
    
    return mysql.connector.connect(
        host="gateway01.us-east-1.prod.aws.tidbcloud.com",
        port=4000,
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASS"),
        database=db_name,
        ssl_verify_cert=False,
        use_pure=True
    )

# ===========================================================================
# 3. RUTAS DEL SERVIDOR
# ===========================================================================

@app.route('/')
def index():
    """Carga la página principal del escáner"""
    # Lista de áreas para el menú desplegable del HTML
    areas = [
        "ABASTECIMIENTO", "ADMINISTRACION", "ASEO", "BAÑOS PLANTA", "BODEGA", 
        "MANTENCION", "OPERACIONES", "PACKING", "PRODUCCION", "RR.HH", "SEGURIDAD", 
        "TODAS LAS AREAS", "UNITEC"
    ]
    return render_template('index.html', areas=areas)

@app.route('/login', methods=['POST'])
def login():
    """Procesa el ingreso desde el celular"""
    data = request.get_json()
    user = data.get('username', '').lower()
    password = data.get('password', '')

    if validar_acceso(user, password):
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Usuario o contraseña incorrectos."})

@app.route('/buscar_trabajador', methods=['POST'])
def buscar_trabajador():
    """Busca automáticamente el nombre y área por RUT"""
    data = request.get_json()
    rut = data.get('rut')
    planta = data.get('planta')
    
    # Validar credenciales en cada petición por seguridad
    if not validar_acceso(data.get('username'), data.get('password')):
        return jsonify({"success": False, "message": "Sesión inválida."})

    try:
        conn = get_db_connection(planta)
        cur = conn.cursor(dictionary=True)
        # Buscamos el último registro de este RUT para autocompletar
        cur.execute("SELECT trabajador, area FROM transacciones WHERE rut = %s ORDER BY id DESC LIMIT 1", (rut,))
        res = cur.fetchone()
        cur.close()
        conn.close()

        if res:
            return jsonify({"success": True, "nombre": res['trabajador'], "area": res['area']})
        return jsonify({"success": False, "message": "Trabajador no encontrado."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/registrar_salida', methods=['POST'])
def registrar_salida():
    """Registra la entrega o devolución de una herramienta"""
    data = request.get_json()
    accion = data.get('accion') # 'SALIDA' o 'DEVOLUCION'
    rut = data.get('rut')
    trabajador = data.get('trabajador')
    area = data.get('area')
    articulo_id = data.get('articulo_id')
    planta = data.get('planta')

    if not validar_acceso(data.get('username'), data.get('password')):
        return jsonify({"success": False, "message": "Sesión inválida."})

    try:
        conn = get_db_connection(planta)
        cur = conn.cursor()

        # 1. Verificar si el artículo existe y tiene stock
        cur.execute("SELECT stock_disponible, descripcion FROM articulos WHERE id = %s", (articulo_id,))
        item = cur.fetchone()

        if not item:
            return jsonify({"success": False, "message": f"ID {articulo_id} no existe."})

        stock_actual, nombre_art = item

        if accion == 'SALIDA':
            if stock_actual <= 0:
                return jsonify({"success": False, "message": f"Sin stock de {nombre_art}."})
            
            # Registrar transacción
            cur.execute(
                "INSERT INTO transacciones (articulo_id, rut, trabajador, area, estado) VALUES (%s, %s, %s, %s, 'EN TERRENO')",
                (articulo_id, rut, trabajador, area)
            )
            # Restar stock
            cur.execute("UPDATE articulos SET stock_disponible = stock_disponible - 1 WHERE id = %s", (articulo_id,))
            msg = f"Entregado: {nombre_art}"

        else: # DEVOLUCION
            # Buscar el registro abierto de este trabajador con esta herramienta
            cur.execute(
                "SELECT id FROM transacciones WHERE rut = %s AND articulo_id = %s AND estado = 'EN TERRENO' LIMIT 1",
                (rut, articulo_id)
            )
            trans_id = cur.fetchone()
            
            if not trans_id:
                return jsonify({"success": False, "message": "No hay salida pendiente para este RUT."})

            # Actualizar transacción
            cur.execute(
                "UPDATE transacciones SET hora_entrada = CURRENT_TIMESTAMP, estado = 'DEVUELTO' WHERE id = %s",
                (trans_id[0],)
            )
            # Sumar stock
            cur.execute("UPDATE articulos SET stock_disponible = stock_disponible + 1 WHERE id = %s", (articulo_id,))
            msg = f"Devuelto: {nombre_art}"

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": msg})

    except Exception as e:
        return jsonify({"success": False, "message": "Error de base de datos."})

if __name__ == '__main__':
    # Render usa gunicorn, pero para pruebas locales usamos esto:
    app.run(debug=True)
