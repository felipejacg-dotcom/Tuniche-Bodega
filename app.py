# -*- coding: utf-8 -*-
from flask import Flask, render_template, make_response
from dotenv import load_dotenv
import os
from datetime import timedelta

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-CHANGE-IN-PRODUCTION")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)

from routes.auth_routes import auth_bp
from routes.worker_routes import worker_bp
from routes.stock_routes import stock_bp
from routes.operation_routes import operation_bp

app.register_blueprint(auth_bp)
app.register_blueprint(worker_bp)
app.register_blueprint(stock_bp)
app.register_blueprint(operation_bp)


@app.route("/")
def index():
    areas = [
        "ABASTECIMIENTO", "ADMINISTRACION", "ASEO", "BANOS PLANTA", "BODEGA",
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
        "PACKING", "PACKING SATELITE", "PANOL CENTRAL", "PCK CAROZOS",
        "PCK CEREZAS", "PLANTA RILES", "PLANTA TRATAMIENTO",
        "PLANTA TUNICHE FRUITS 2 PUQUILLAY", "PORTERIA 1", "PORTERIA 2",
        "PREVENCION CENTRAL", "PREVENCION DE RIESGOS", "PRODUCCION",
        "RECEPCION FRUTA", "RR.HH", "SADEMA", "SADEMA CENTRAL", "SAG",
        "SEGURIDAD", "SERV GRALES CENTRAL", "SERVICIOS GENERALES", "TALLER",
        "TODAS LAS AREAS", "UNITEC",
    ]
    response = make_response(render_template("index.html", areas=areas))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
