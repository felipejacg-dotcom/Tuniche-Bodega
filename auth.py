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


def _get_user_plantas() -> dict:
    raw = os.environ.get("LOGIN_USER_PLANTAS", "").strip()
    plantas_by_user = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            user, plantas = pair.split(":", 1)
            allowed = {
                planta.strip().upper()
                for planta in plantas.replace("|", ";").split(";")
                if planta.strip()
            }
            if allowed:
                plantas_by_user[user.strip().lower()] = allowed
    return plantas_by_user


def has_login_users() -> bool:
    return bool(_get_users())


def is_user_allowed_for_planta(username: str, planta: str) -> bool:
    allowed_plantas = _get_user_plantas().get(username.strip().lower())
    return not allowed_plantas or planta.strip().upper() in allowed_plantas


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


def verify_admin_password(password: str) -> bool:
    stored_password = _get_users().get("admin")
    if not stored_password:
        return False
    return _verify_password(stored_password, (password or "").strip())


def get_user_display_name(username: str) -> str:
    """Retorna el nombre con la capitalización original definida en LOGIN_USERS."""
    raw = os.environ.get("LOGIN_USERS", "").strip() or DEFAULT_LOGIN_USERS
    username_lower = username.strip().lower()
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            u, _ = pair.split(":", 1)
            u_clean = u.strip()
            if u_clean.lower() == username_lower:
                return u_clean
    return username.title()


def login_user(username: str, password: str, planta: str) -> bool:
    users = _get_users()
    username_key = username.strip().lower()
    stored_password = users.get(username_key)
    if stored_password is not None and _verify_password(stored_password, password.strip()):
        if not is_user_allowed_for_planta(username_key, planta):
            return False
        session.permanent = True
        session["user"] = username_key
        session["user_display"] = get_user_display_name(username)
        session["planta"] = planta
        return True
    return False


def get_current_user() -> str:
    return session.get("user_display", session.get("user", ""))


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
