import base64
import hashlib

import pytest

from log_exporter import create_app


@pytest.fixture()
def app(tmp_path):
    key = base64.urlsafe_b64encode(hashlib.sha256(b"tests").digest()).decode()
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "EXPORT_DIR": str(tmp_path / "exports"),
        "CREDENTIAL_KEY": key,
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "secret-password",
    })
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth(client):
    response = client.post("/api/login", json={"username": "admin", "password": "secret-password"})
    return response.get_json()["csrf_token"]
