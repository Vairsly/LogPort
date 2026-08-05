from datetime import datetime, timedelta, timezone

from log_exporter.db import get_db, utcnow
from log_exporter.security import encrypt_secret


def headers(csrf):
    return {"X-CSRF-Token": csrf}


def add_server(app, fingerprint="SHA256:test"):
    with app.app_context():
        db = get_db()
        cursor = db.execute(
            "INSERT INTO servers(name,host,port,username,auth_type,secret_encrypted,containers,host_fingerprint,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("生产一", "10.0.0.1", 22, "ops", "password", encrypt_secret("hidden"), '["api"]', fingerprint, utcnow(), utcnow()),
        )
        return cursor.lastrowid


def test_login_and_csrf(client):
    assert client.get("/api/servers").status_code == 401
    assert client.post("/api/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    assert client.post("/api/login", json={"username": "admin", "password": "secret-password"}).status_code == 200
    assert client.post("/api/servers", json={}).status_code == 403


def test_server_secret_is_not_returned(client, auth):
    response = client.post("/api/servers", headers=headers(auth), json={
        "name": "prod", "host": "example.internal", "port": 22, "username": "ops",
        "auth_type": "password", "secret": "super-secret", "containers": ["api", "worker"],
    })
    assert response.status_code == 200
    assert "secret" not in response.get_data(as_text=True)


def test_task_time_and_allowlist_validation(app, client, auth):
    server_id = add_server(app)
    now = datetime.now(timezone.utc)
    valid = {"server_id": server_id, "container": "api", "start": (now - timedelta(minutes=30)).isoformat(), "end": now.isoformat()}
    assert client.post("/api/export-tasks", headers=headers(auth), json=valid).status_code == 201
    assert client.post("/api/export-tasks", headers=headers(auth), json=valid | {"container": "other"}).status_code == 400
    assert client.post("/api/export-tasks", headers=headers(auth), json=valid | {"start": (now - timedelta(hours=25)).isoformat()}).status_code == 400
    assert client.post("/api/export-tasks", headers=headers(auth), json=valid | {"end": (now + timedelta(hours=1)).isoformat()}).status_code == 400


def test_download_rejects_path_outside_export_dir(app, client, auth, tmp_path):
    server_id = add_server(app)
    with app.app_context():
        db = get_db()
        cursor = db.execute("INSERT INTO export_tasks(server_id,server_name,container,start_time,end_time,status,file_path,created_at) VALUES(?,?,?,?,?,'succeeded',?,?)",
            (server_id, "prod", "api", utcnow(), utcnow(), str(tmp_path / "outside.log"), utcnow()))
        task_id = cursor.lastrowid
    (tmp_path / "outside.log").write_text("secret")
    assert client.get(f"/api/export-tasks/{task_id}/download").status_code == 404
