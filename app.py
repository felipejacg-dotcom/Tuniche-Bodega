# -*- coding: utf-8 -*-
from flask import Flask, render_template, make_response, session, request, jsonify
from dotenv import load_dotenv
import os
import secrets
import hmac
from datetime import timedelta

load_dotenv(override=True)

from config import AREAS

app = Flask(__name__)


@app.before_request
def ensure_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)


@app.before_request
def csrf_protect():
    if app.testing:
        return
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        token = request.headers.get("X-CSRF-Token")
        session_token = session.get("csrf_token")
        if not session_token or not token or not hmac.compare_digest(str(session_token), str(token)):
            return jsonify({
                "success": False,
                "message": "Petición de seguridad inválida (CSRF token faltante o expirado)."
            }), 400


@app.after_request
def set_csrf_cookie(response):
    if "csrf_token" in session:
        response.set_cookie(
            "csrf_token",
            session["csrf_token"],
            samesite="Lax",
            secure=request.is_secure,
            httponly=False  # Readable by client JS
        )
    return response

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

from db import ensure_cierres_table_exists
ensure_cierres_table_exists()


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
