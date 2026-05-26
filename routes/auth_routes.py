# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from auth import (
    has_login_users,
    login_user,
    logout_user,
    get_current_user,
    get_current_planta,
    login_required,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    planta = data.get("planta", "TUNICHE").strip()

    if not username or not password:
        return jsonify({"success": False, "message": "Usuario y contraseña requeridos."}), 400

    if planta not in ("TUNICHE", "PUQUILLAY"):
        return jsonify({"success": False, "message": "Planta invalida."}), 400

    if not has_login_users():
        return jsonify({
            "success": False,
            "message": "Usuarios no configurados en el servidor. Revisa LOGIN_USERS."
        }), 503

    if login_user(username, password, planta):
        return jsonify({"success": True, "user": username, "planta": planta})

    return jsonify({"success": False, "message": "Usuario o contraseña incorrectos."}), 401


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"success": True})


@auth_bp.route("/me")
@login_required
def me():
    return jsonify({
        "success": True,
        "user": get_current_user(),
        "planta": get_current_planta(),
    })
