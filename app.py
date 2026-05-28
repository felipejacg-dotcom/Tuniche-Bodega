# -*- coding: utf-8 -*-
from flask import Flask, render_template, make_response
from dotenv import load_dotenv
import os
from datetime import timedelta

load_dotenv(override=True)

from config import AREAS

app = Flask(__name__)

# Enforce secure SECRET_KEY in production
secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    if os.environ.get("FLASK_ENV") == "production" or os.environ.get("RENDER") == "true":
        raise RuntimeError("La variable de entorno SECRET_KEY es requerida en producción.")
    secret_key = "dev-secret-CHANGE-IN-PRODUCTION"
app.secret_key = secret_key

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
    response = make_response(render_template("index.html", areas=AREAS))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
