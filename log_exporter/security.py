import base64
import hashlib
import json
import secrets
from functools import wraps

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, jsonify, redirect, request, session, url_for


def _fernet():
    key = current_app.config["CREDENTIAL_KEY"]
    if not key:
        if current_app.config.get("TESTING"):
            key = base64.urlsafe_b64encode(hashlib.sha256(b"log-exporter-test-key").digest()).decode()
        else:
            raise RuntimeError("必须配置 CREDENTIAL_KEY")
    return Fernet(key.encode())


def encrypt_secret(value):
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value):
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("凭据无法解密，请检查 CREDENTIAL_KEY") from exc


def new_csrf_token():
    token = secrets.token_urlsafe(32)
    session["csrf_token"] = token
    return token


def require_login(api=True):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return (jsonify(error="请先登录"), 401) if api else redirect(url_for("views.login_page"))
            return func(*args, **kwargs)
        return wrapped
    return decorator


def require_csrf(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        if not supplied or not secrets.compare_digest(supplied, session.get("csrf_token", "")):
            return jsonify(error="CSRF 校验失败，请刷新页面"), 403
        return func(*args, **kwargs)
    return wrapped


def parse_containers(value):
    if isinstance(value, list):
        items = value
    else:
        items = str(value or "").splitlines()
    result = sorted({item.strip() for item in items if item.strip()})
    if not result or any(len(item) > 128 for item in result):
        raise ValueError("请至少填写一个有效容器名称")
    return json.dumps(result, ensure_ascii=False)
