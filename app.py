from flask import Flask, render_template, request, jsonify
import mysql.connector
import os
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

# ===========================================================================
# 1. CONFIGURACIÓN DE SEGURIDAD
# ===========================================================================
USUARIOS_WEB = {
    "bodega": "123456",  # Tu clave del celular
    "admin": "admin123"
}

# ===========================================================================
# 2. CONEXIÓN A BASE DE DATOS (TiDB CLOUD) - FIJA Y SEGURA
# ===========================================================================
def get_db_connection(planta):
    db_name = "bodega_tuniche_real" if planta == "TUNICHE" else "bodega_puquillay_real"
    
    return mysql.connector.connect(
        host="gateway01.us-east-1.prod.aws.tidbcloud.com",
        port=4000,
        user="4K3HGsTvxGEKd2X.root", # Usuario completo exigido por TiDB
        password="4aJEglVrXOotgXhp", # Tu clave real de TiDB
        database=db_name,
        ssl_verify_cert=False,
        use_pure=True
    )

# ===========================================================================
# 3. RUTAS
# ===========================================================================

@app.route('/')
def index():
    # ¡TODAS TUS ÁREAS ORIGINALES RESTAURADAS!
    areas = [
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
    return render_template('index.html', areas=areas)

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    u, p = data.get('username', '').lower(), data.get('password', '')
    if USUARIOS_WEB.get(u) == p:
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Usuario o contraseña incorrectos."})

@app.route('/buscar_trabajador', methods=['POST'])
def buscar_trabajador():
    data = request.get_json()
    rut, planta = data.get('rut'), data.get('planta')
    try:
        conn = get_db_connection(planta)
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT trabajador, area FROM transacciones WHERE rut = %s ORDER BY id DESC LIMIT 1", (rut,))
        res = cur.fetchone()
        cur.close(); conn.close()
        if res:
            return jsonify({"success": True, "nombre": res['trabajador'], "area": res['area']})
        return jsonify({"success": False, "message": "Trabajador no encontrado."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error BD: {str(e)}"})

@app.route('/registrar_salida', methods=['POST'])
def registrar_salida():
    data = request.get_json()
    accion, rut, tr, ar, art_id, planta = data.get('accion'), data.get('rut'), data.get('trabajador'), data.get('area'), data.get('articulo_id'), data.get('planta')
    try:
        conn = get_db_connection(planta)
        cur = conn.cursor()
        cur.execute("SELECT stock_disponible, descripcion FROM articulos WHERE id = %s", (art_id,))
        item = cur.fetchone()
        if not item: return jsonify({"success": False, "message": f"ID {art_id} no existe."})
        
        if accion == 'SALIDA':
            if item[0] <= 0: return jsonify({"success": False, "message": f"Sin stock de {item[1]}."})
            cur.execute("INSERT INTO transacciones (articulo_id, rut, trabajador, area, estado) VALUES (%s, %s, %s, %s, 'EN TERRENO')", (art_id, rut, tr, ar))
            cur.execute("UPDATE articulos SET stock_disponible = stock_disponible - 1 WHERE id = %s", (art_id,))
            msg = f"Entregado: {item[1]}"
        else:
            cur.execute("SELECT id FROM transacciones WHERE rut = %s AND articulo_id = %s AND estado = 'EN TERRENO' LIMIT 1", (rut, art_id))
            tid = cur.fetchone()
            if not tid: return jsonify({"success": False, "message": "No hay salida pendiente."})
            cur.execute("UPDATE transacciones SET hora_entrada = CURRENT_TIMESTAMP, estado = 'DEVUELTO' WHERE id = %s", (tid[0],))
            cur.execute("UPDATE articulos SET stock_disponible = stock_disponible + 1 WHERE id = %s", (art_id,))
            msg = f"Devuelto: {item[1]}"
        
        conn.commit(); cur.close(); conn.close()
        return jsonify({"success": True, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error BD: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
