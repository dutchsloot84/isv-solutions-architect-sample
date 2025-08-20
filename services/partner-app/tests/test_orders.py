from fastapi.testclient import TestClient
from unittest.mock import patch
import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from partner_app.main import app  # noqa

client = TestClient(app)


def test_idempotent_creation():
    key = "abc123"
    with patch("partner_app.main.publish_order"):
        r1 = client.post(
            "/orders",
            json={"product": "foo"},
            headers={"Idempotency-Key": key},
        )
        r2 = client.post(
            "/orders",
            json={"product": "foo"},
            headers={"Idempotency-Key": key},
        )
    assert r1.json()["id"] == r2.json()["id"]
