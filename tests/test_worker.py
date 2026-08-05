from pathlib import Path

from log_exporter.db import get_db, utcnow
from log_exporter.security import encrypt_secret
from log_exporter.worker import claim_task


def test_claim_task_only_once(app):
    with app.app_context():
        db = get_db()
        server = db.execute("INSERT INTO servers(name,host,port,username,auth_type,secret_encrypted,containers,host_fingerprint,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("prod", "host", 22, "ops", "password", encrypt_secret("x"), '["api"]', "fp", utcnow(), utcnow())).lastrowid
        db.execute("INSERT INTO export_tasks(server_id,server_name,container,start_time,end_time,status,created_at) VALUES(?,?,?,?,?,'queued',?)", (server, "prod", "api", utcnow(), utcnow(), utcnow()))
        assert claim_task("one")["status"] == "running"
        assert claim_task("two") is None
