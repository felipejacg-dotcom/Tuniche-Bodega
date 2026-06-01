# -*- coding: utf-8 -*-
from flask import session, jsonify
import os
import hmac
from functools import wraps
from werkzeug.security import check_password_hash

DEFAULT_LOGIN_USERS = "admin:admin123,bodega:123456"


def _get_users() -> dict:
    raw = os.environ.get("LOGIN_USERS", "").strip() or DEFAULT_LOGIN_USERS
    users = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            u, p = pair.split(":", 1)
            users[u.strip().lower()] = p.strip()
    return users


def has_login_users() -> bool:
    return bool(_get_users())


def _verify_password(stored: str, provided: str) -> bool:
    # Check if stored password has hash prefixes or format (pbkdf2:, scrypt:, bcrypt:, argon2:)
    is_hash = stored.startswith(("pbkdf2:", "scrypt:", "bcrypt:", "argon2:")) or (stored.count("$") >= 2)
    if is_hash:
        try:
            return check_password_hash(stored, provided)
        except Exception:
            pass
    # Fallback to constant-time comparison for plain-text passwords
    return hmac.compare_digest(stored.encode("utf-8"), provided.encode("utf-8"))


def login_user(username: str, password: str, planta: str) -> bool:
    users = _get_users()
    stored_password = users.get(username.strip().lower())
    if stored_password is not None and _verify_password(stored_password, password.strip()):
        session.permanent = True
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
