from flask import Flask, render_template, request, jsonify
import mysql.connector
import os
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

# ===========================================================================
# 1. CONFIGURACIÓN DE SEGURIDAD (LOGIN WEB)
# ===========================================================================
USUARIOS_PERMITIDOS = {
    "bodega": "123456",  # <--- Esta es la clave que usas en el celular
    "admin": "admin123"
}

def validar_acceso(user, password):
    return USUARIOS_PERMITIDOS.get(user) == password

# ===========================================================================
# 2. CONEXIÓN A BASE DE DATOS (TIDB CLOUD)
# ===========================================================================
def get_db_connection(planta):
    db_name = "bodega_tuniche_real" if planta == "TUNICHE" else "bodega_puquillay_real"
    
    # Usamos las credenciales que me pasaste para asegurar la conexión
    return mysql.connector.connect(
        host="gateway01.us-east-1.prod.aws.tidbcloud.com",
        port=4000,
        user=os.environ.get("DB_USER", "4K3HGsTvxGEKd2X.root"),
        password=os.environ.get("DB_PASS", "4aJEglVrXOotgXhp"),
        database=db_name,
        ssl_verify_cert=False,
        use_pure=True
    )

# ===========================================================================
# 3. RUTAS DEL SERVIDOR
# ===========================================================================

@app.route('/')
def index():
    areas = [
        "ABASTECIMIENTO", "ADMINISTRACION", "ASEO", "BAÑOS PLANTA", "BODEGA", 
        "MANTENCION", "OPERACIONES", "PACKING", "PRODUCCION", "RR.HH", "SEGURIDAD", 
        "TODAS LAS AREAS", "UNITEC"
    ]
    return render_template('index.html', areas=areas)

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = data.get('username', '').lower()
    password = data.get('password', '')
    if validar_acceso(user, password):
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Usuario o contraseña incorrectos."})

@app.route('/buscar_trabajador', methods=['POST'])
def buscar_trabajador():
    data = request.get_json()
    rut = data.get('rut')
    planta = data.get('planta')
    try:
        conn = get_db_connection(planta)
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT trabajador, area FROM transacciones WHERE rut = %s ORDER BY id DESC LIMIT 1", (rut,))
        res = cur.fetchone()
        cur.close()
        conn.close()
        if res:
            return jsonify({"success": True, "nombre": res['trabajador'], "area": res['area']})
        return jsonify({"success": False, "message": "Trabajador nuevo."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error BD: {str(e)}"})

@app.route('/registrar_salida', methods=['POST'])
def registrar_salida():
    data = request.get_json()
    accion, rut, trabajador, area, articulo_id, planta = data.get('accion'), data.get('rut'), data.get('trabajador'), data.get('area'), data.get('articulo_id'), data.get('planta')
    try:
        conn = get_db_connection(planta)
        cur = conn.cursor()
        cur.execute("SELECT stock_disponible, descripcion FROM articulos WHERE id = %s", (articulo_id,))
        item = cur.fetchone()
        if not item: return jsonify({"success": False, "message": f"ID {articulo_id} no existe."})
        stock_actual, nombre_art = item

        if accion == 'SALIDA':
            if stock_actual <= 0: return jsonify({"success": False, "message": f"Sin stock de {nombre_art}."})
            cur.execute("INSERT INTO transacciones (articulo_id, rut, trabajador, area, estado) VALUES (%s, %s, %s, %s, 'EN TERRENO')", (articulo_id, rut, trabajador, area))
            cur.execute("UPDATE articulos SET stock_disponible = stock_disponible - 1 WHERE id = %s", (articulo_id,))
            msg = f"Entregado: {nombre_art}"
        else:
            cur.execute("SELECT id FROM transacciones WHERE rut = %s AND articulo_id = %s AND estado = 'EN TERRENO' LIMIT 1", (rut, articulo_id))
            trans_id = cur.fetchone()
            if not trans_id: return jsonify({"success": False, "message": "No hay salida pendiente."})
            cur.execute("UPDATE transacciones SET hora_entrada = CURRENT_TIMESTAMP, estado = 'DEVUELTO' WHERE id = %s", (trans_id[0],))
            cur.execute("UPDATE articulos SET stock_disponible = stock_disponible + 1 WHERE id = %s", (articulo_id,))
            msg = f"Devuelto: {nombre_art}"
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error BD: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
