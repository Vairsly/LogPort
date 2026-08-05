import os
from datetime import timedelta
from pathlib import Path

from flask import Flask

from .db import close_db, init_db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    data_dir = Path(os.getenv("DATA_DIR", "/data"))
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
        DATABASE=str(data_dir / "log-exporter.db"),
        EXPORT_DIR=str(data_dir / "exports"),
        CREDENTIAL_KEY=os.getenv("CREDENTIAL_KEY", ""),
        ADMIN_USERNAME=os.getenv("ADMIN_USERNAME", "admin"),
        ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD", ""),
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

    from .auth import auth_bp
    from .api import api_bp
    from .views import views_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    with app.app_context():
        init_db()
    return app
