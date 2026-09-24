import os
from datetime import timedelta
from pathlib import Path

from flask import Flask, abort, send_from_directory

from .db import close_db, init_db

# log-server/
#   frontend/dist
#   backend/log_exporter/__init__.py
ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DIST = ROOT_DIR / "frontend" / "dist"


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True, static_folder=None)
    data_dir = Path(os.getenv("DATA_DIR", "/data"))
    frontend_dist = Path(os.getenv("FRONTEND_DIST", str(DEFAULT_DIST)))
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
        DATABASE=str(data_dir / "log-exporter.db"),
        EXPORT_DIR=str(data_dir / "exports"),
        CREDENTIAL_KEY=os.getenv("CREDENTIAL_KEY", ""),
        ADMIN_USERNAME=os.getenv("ADMIN_USERNAME", "admin"),
        ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD", ""),
        FRONTEND_DIST=str(frontend_dist),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_EXPORT_HOURS=24,
        EXPORT_RETENTION_HOURS=24,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["EXPORT_DIR"]).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)

    from .api import api_bp
    from .auth import auth_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    _register_spa(app)

    with app.app_context():
        init_db()
    return app


def _register_spa(app):
    dist = Path(app.config["FRONTEND_DIST"])

    @app.get("/")
    def spa_index():
        if not (dist / "index.html").is_file():
            return (
                "前端尚未构建。开发模式请访问 Vite 开发服务器；"
                "生产模式请先执行 frontend 构建，或设置 FRONTEND_DIST。",
                503,
            )
        return send_from_directory(dist, "index.html")

    @app.get("/<path:path>")
    def spa_assets(path):
        if path.startswith("api/"):
            abort(404)
        if not dist.is_dir():
            abort(404)
        target = (dist / path).resolve()
        if dist.resolve() in target.parents and target.is_file():
            return send_from_directory(dist, path)
        if (dist / "index.html").is_file():
            return send_from_directory(dist, "index.html")
        abort(404)
