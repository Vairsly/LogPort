import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

from .db import get_db, utcnow
from .security import encrypt_secret, parse_containers, require_csrf, require_login
from .ssh_client import test_server

api_bp = Blueprint("api", __name__, url_prefix="/api")


def server_json(row):
    return {key: row[key] for key in ("id", "name", "host", "port", "username", "auth_type", "host_fingerprint", "created_at", "updated_at")} | {"containers": json.loads(row["containers"])}


def parse_time(value):
    if not value:
        raise ValueError("时间不能为空")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("时间必须包含时区")
    return parsed.astimezone(timezone.utc)


@api_bp.get("/servers")
@require_login()
def list_servers():
    rows = get_db().execute("SELECT * FROM servers ORDER BY name").fetchall()
    return jsonify([server_json(row) for row in rows])


@api_bp.post("/servers")
@require_login()
@require_csrf
def create_server():
    return save_server(None)


@api_bp.put("/servers/<int:server_id>")
@require_login()
@require_csrf
def update_server(server_id):
    return save_server(server_id)


def save_server(server_id):
    data = request.get_json(silent=True) or {}
    try:
        name, host, username = (str(data.get(key, "")).strip() for key in ("name", "host", "username"))
        port = int(data.get("port", 22))
        auth_type = data.get("auth_type")
        if not name or not host or not username or not 1 <= port <= 65535 or auth_type not in ("password", "private_key"):
            raise ValueError("服务器信息不完整")
        containers = parse_containers(data.get("containers"))
        db = get_db()
        existing = db.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone() if server_id else None
        secret = data.get("secret")
        if not secret and not existing:
            raise ValueError("首次创建必须填写 SSH 凭据")
        encrypted = encrypt_secret(secret) if secret else existing["secret_encrypted"]
        passphrase = data.get("key_passphrase")
        passphrase_encrypted = encrypt_secret(passphrase) if passphrase else (existing["key_passphrase_encrypted"] if existing else None)
        now = utcnow()
        if existing:
            db.execute("UPDATE servers SET name=?,host=?,port=?,username=?,auth_type=?,secret_encrypted=?,key_passphrase_encrypted=?,containers=?,updated_at=? WHERE id=?",
                       (name, host, port, username, auth_type, encrypted, passphrase_encrypted, containers, now, server_id))
        else:
            cursor = db.execute("INSERT INTO servers(name,host,port,username,auth_type,secret_encrypted,key_passphrase_encrypted,containers,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (name, host, port, username, auth_type, encrypted, passphrase_encrypted, containers, now, now))
            server_id = cursor.lastrowid
        return jsonify(server_json(db.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()))
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    except Exception as exc:
        if "UNIQUE" in str(exc):
            return jsonify(error="服务器名称已存在"), 409
        raise


@api_bp.delete("/servers/<int:server_id>")
@require_login()
@require_csrf
def delete_server(server_id):
    try:
        result = get_db().execute("DELETE FROM servers WHERE id=?", (server_id,))
    except Exception:
        return jsonify(error="该服务器已有导出记录，不能删除"), 409
    return (jsonify(ok=True), 200) if result.rowcount else (jsonify(error="服务器不存在"), 404)


@api_bp.post("/servers/<int:server_id>/test")
@require_login()
@require_csrf
def test_connection(server_id):
    db = get_db()
    server = db.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()
    if not server:
        return jsonify(error="服务器不存在"), 404
    try:
        actual, docker_version = test_server(server)
        if not server["host_fingerprint"]:
            if not (request.get_json(silent=True) or {}).get("confirm_fingerprint"):
                return jsonify(confirmation_required=True, fingerprint=actual), 409
            db.execute("UPDATE servers SET host_fingerprint=?,updated_at=? WHERE id=?", (actual, utcnow(), server_id))
        return jsonify(ok=True, fingerprint=actual, docker_version=docker_version)
    except Exception as exc:
        return jsonify(error=str(exc)), 400


@api_bp.post("/export-tasks")
@require_login()
@require_csrf
def create_task():
    data = request.get_json(silent=True) or {}
    try:
        server_id = int(data.get("server_id"))
        server = get_db().execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()
        if not server or not server["host_fingerprint"]:
            raise ValueError("服务器不存在或尚未确认指纹")
        container = str(data.get("container", ""))
        if container not in json.loads(server["containers"]):
            raise ValueError("容器不在服务器白名单中")
        end = parse_time(data.get("end"))
        start = parse_time(data.get("start"))
        now = datetime.now(timezone.utc)
        if end <= start:
            raise ValueError("结束时间必须晚于开始时间")
        if end > now + timedelta(minutes=1):
            raise ValueError("结束时间不能晚于当前时间")
        if end - start > timedelta(hours=current_app.config["MAX_EXPORT_HOURS"]):
            raise ValueError("单次导出最多 24 小时")
        cursor = get_db().execute("INSERT INTO export_tasks(server_id,server_name,container,start_time,end_time,status,created_at) VALUES(?,?,?,?,?,'queued',?)",
            (server_id, server["name"], container, start.isoformat(), end.isoformat(), utcnow()))
        return jsonify(id=cursor.lastrowid, status="queued"), 201
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400


def task_json(row):
    return {key: row[key] for key in row.keys() if key not in ("file_path", "worker_id")}


@api_bp.get("/export-tasks")
@require_login()
def list_tasks():
    rows = get_db().execute("SELECT * FROM export_tasks ORDER BY id DESC LIMIT 200").fetchall()
    return jsonify([task_json(row) for row in rows])


@api_bp.get("/export-tasks/<int:task_id>")
@require_login()
def get_task(task_id):
    row = get_db().execute("SELECT * FROM export_tasks WHERE id=?", (task_id,)).fetchone()
    return jsonify(task_json(row)) if row else (jsonify(error="任务不存在"), 404)


@api_bp.get("/export-tasks/<int:task_id>/download")
@require_login()
def download_task(task_id):
    row = get_db().execute("SELECT * FROM export_tasks WHERE id=?", (task_id,)).fetchone()
    if not row or row["status"] != "succeeded" or not row["file_path"]:
        return jsonify(error="文件尚不可下载或已经过期"), 404
    root = Path(current_app.config["EXPORT_DIR"]).resolve()
    path = Path(row["file_path"]).resolve()
    if root not in path.parents or not path.is_file():
        return jsonify(error="日志文件不存在"), 404
    filename = f'{row["server_name"]}_{row["container"]}_{row["start_time"][:19].replace(":", "-")}.log'
    return send_file(path, as_attachment=True, download_name=filename, mimetype="text/plain; charset=utf-8")


@api_bp.get("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return jsonify(status="ok")
