from flask import Flask, render_template, request, jsonify
import mysql.connector
from datetime import datetime

app = Flask(__name__)

def conectar_db():
    return mysql.connector.connect(
        host="gateway01.us-east-1.prod.aws.tidbcloud.com",
        port=4000,
        user="4K3HGsTvxGEKd2X.root",
        password="4aJEglVrXOotgXhp",
        ssl_verify_cert=False,     
        ssl_verify_identity=False,
        use_pure=True,
        database="bodega_tuniche_real"
    )

@app.route('/')
def index():
    # ¡Lista OFICIAL de áreas sincronizada con el programa de PC!
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

@app.route('/registrar_salida', methods=['POST'])
def registrar_salida():
    datos = request.json
    rut = datos.get('rut', '').strip()
    trabajador = datos.get('trabajador', '').strip()
    area = datos.get('area', '').strip()
    articulo_id = datos.get('articulo_id', '').strip()

    if not all([rut, trabajador, area, articulo_id]):
        return jsonify({"success": False, "message": "Faltan datos por llenar."})

    try:
        conexion = conectar_db()
        cursor = conexion.cursor()

        # Verificar stock
        cursor.execute("SELECT stock_disponible, descripcion FROM articulos WHERE id = %s", (articulo_id,))
        item_data = cursor.fetchone()

        if not item_data:
            return jsonify({"success": False, "message": "El QR escaneado no existe en el inventario."})
        
        if item_data[0] <= 0:
            return jsonify({"success": False, "message": f"¡Sin stock de: {item_data[1]}!"})

        # Registrar salida
        ahora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO transacciones (articulo_id, rut, trabajador, area, hora_salida) VALUES (%s, %s, %s, %s, %s)", 
                       (articulo_id, rut, trabajador, area, ahora_local))
        cursor.execute("UPDATE articulos SET stock_disponible = stock_disponible - 1 WHERE id = %s", (articulo_id,))
        conexion.commit()

        mensaje_exito = f"Entregado: {item_data[1]}"
        cursor.close()
        conexion.close()

        return jsonify({"success": True, "message": mensaje_exito})

    except Exception as e:
        return jsonify({"success": False, "message": f"Error de conexión: {str(e)}"})

if __name__ == '__main__':
    # ssl_context='adhoc' fuerza HTTPS (necesario para que Chrome permita encender la cámara del celular)
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc', debug=True)