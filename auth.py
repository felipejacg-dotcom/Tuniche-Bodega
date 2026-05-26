# -*- coding: utf-8 -*-
from flask import session, jsonify
import os
from functools import wraps


def _get_users() -> dict:
    raw = os.environ.get("LOGIN_USERS", "")
    users = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            u, p = pair.split(":", 1)
            users[u.strip().lower()] = p.strip()
    return users


def has_login_users() -> bool:
    return bool(_get_users())


def login_user(username: str, password: str, planta: str) -> bool:
    users = _get_users()
    if users.get(username.strip().lower()) == password.strip():
        session["user"] = username.strip().lower()
        session["planta"] = planta
        return True
    return False


def get_current_user() -> str:
    return session.get("user", "")


def get_current_planta() -> str:
    return session.get("planta", "TUNICHE")


def is_authenticated() -> bool:
    return "user" in session


def logout_user() -> None:
    session.clear()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            return jsonify({
                "success": False,
                "message": "Sesion expirada. Inicia sesion nuevamente."
            }), 401
        return fn(*args, **kwargs)
    return wrapper
