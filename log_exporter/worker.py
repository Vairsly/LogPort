import os
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import create_app
from .db import get_db, utcnow
from .ssh_client import export_logs


def claim_task(worker_id):
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        task = db.execute("SELECT * FROM export_tasks WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
        if not task:
            db.execute("COMMIT")
            return None
        changed = db.execute("UPDATE export_tasks SET status='running',started_at=?,worker_id=? WHERE id=? AND status='queued'", (utcnow(), worker_id, task["id"]))
        db.execute("COMMIT")
        return db.execute("SELECT * FROM export_tasks WHERE id=?", (task["id"],)).fetchone() if changed.rowcount else None
    except Exception:
        db.execute("ROLLBACK")
        raise


def process_task(task):
    db = get_db()
    server = db.execute("SELECT * FROM servers WHERE id=?", (task["server_id"],)).fetchone()
    export_dir = Path(app.config["EXPORT_DIR"])
    final_path = export_dir / f"task-{task['id']}.log"
    temp_path = export_dir / f"task-{task['id']}.part"
    try:
        if not server:
            raise RuntimeError("服务器配置已不存在")
        export_logs(server, task["container"], task["start_time"], task["end_time"], temp_path)
        os.replace(temp_path, final_path)
        finished = datetime.now(timezone.utc)
        expires = finished + timedelta(hours=app.config["EXPORT_RETENTION_HOURS"])
        db.execute("UPDATE export_tasks SET status='succeeded',file_path=?,file_size=?,finished_at=?,expires_at=? WHERE id=?",
                   (str(final_path), final_path.stat().st_size, finished.isoformat(), expires.isoformat(), task["id"]))
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        message = str(exc).replace(server["host"] if server else "", "[server]")[:1000]
        db.execute("UPDATE export_tasks SET status='failed',error=?,finished_at=? WHERE id=?", (message, utcnow(), task["id"]))


def maintenance():
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    db.execute("UPDATE export_tasks SET status='failed',error='Worker 中断，任务未完成',finished_at=? WHERE status='running' AND started_at<?", (utcnow(), cutoff))
    now = utcnow()
    rows = db.execute("SELECT id,file_path FROM export_tasks WHERE status='succeeded' AND expires_at<?", (now,)).fetchall()
    for row in rows:
        if row["file_path"]:
            Path(row["file_path"]).unlink(missing_ok=True)
        db.execute("UPDATE export_tasks SET status='expired',file_path=NULL WHERE id=?", (row["id"],))


app = None


def main(once=False):
    global app
    app = create_app()
    worker_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    with app.app_context():
        maintenance()
        while True:
            task = claim_task(worker_id)
            if task:
                process_task(task)
            else:
                maintenance()
                if once:
                    return
                time.sleep(2)


if __name__ == "__main__":
    main()
