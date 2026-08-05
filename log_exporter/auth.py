import time
from collections import defaultdict

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import Blueprint, jsonify, request, session

from .db import get_db
from .security import new_csrf_token, require_csrf

auth_bp = Blueprint("auth", __name__, url_prefix="/api")
attempts = defaultdict(list)


@auth_bp.post("/login")
def login():
    address = request.remote_addr or "unknown"
    now = time.time()
    attempts[address] = [value for value in attempts[address] if now - value < 300]
    if len(attempts[address]) >= 10:
        return jsonify(error="登录尝试过多，请稍后再试"), 429
    data = request.get_json(silent=True) or request.form
    user = get_db().execute("SELECT * FROM users WHERE username=?", (data.get("username", ""),)).fetchone()
    try:
        valid = user and PasswordHasher().verify(user["password_hash"], data.get("password", ""))
    except VerifyMismatchError:
        valid = False
    if not valid:
        attempts[address].append(now)
        return jsonify(error="用户名或密码错误"), 401
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    return jsonify(ok=True, csrf_token=new_csrf_token())


@auth_bp.post("/logout")
@require_csrf
def logout():
    session.clear()
    return jsonify(ok=True)


@auth_bp.get("/session")
def session_info():
    if not session.get("user_id"):
        return jsonify(authenticated=False), 401
    return jsonify(authenticated=True, csrf_token=session.get("csrf_token") or new_csrf_token())
