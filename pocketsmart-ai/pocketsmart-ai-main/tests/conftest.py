import os
import tempfile
from io import BytesIO

_tmp = tempfile.mkdtemp(prefix="pocketsmart_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["GEMINI_API_KEY"] = ""
os.environ["GEMINI_MODEL"] = ""
os.environ["DEMO_MODE"] = "false"
os.environ["SECRET_KEY"] = "test-secret-key"

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.database import Base, engine
from app.main import app

settings.upload_dir = __import__("pathlib").Path(_tmp) / "uploads"
settings.gemini_retry_delay = 0


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


def register(c, username="alice", email="alice@example.com", password="Passw0rd123"):
    return c.post("/register", data={"username": username, "email": email, "password": password,
                                     "confirm_password": password}, follow_redirects=False)


@pytest.fixture()
def auth_client(client):
    assert register(client).status_code == 303
    return client


@pytest.fixture()
def live(monkeypatch):
    """Pretend a Gemini key + model are configured (no real network calls are ever made)."""
    monkeypatch.setattr(settings, "gemini_api_key", "fake-key-for-tests")
    monkeypatch.setattr(settings, "gemini_model", "fake-model")


def png_bytes(size=(40, 40), color=(200, 30, 60), fmt="PNG"):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


HOME = {"total_budget": 60000, "room_type": "Living Room", "num_rooms": 1, "num_fans": 2, "num_lights": 6,
        "num_furniture": 3, "num_dining_tables": 1, "other_furniture": "bookshelf", "style": "Modern",
        "colors": "warm neutrals", "additional": ""}
PARTY = {"total_budget": 50000, "event_type": "Birthday", "guest_count": 30, "location": "Coimbatore",
         "venue_preference": "Banquet hall", "needs_catering": True, "needs_decoration": True,
         "needs_entertainment": True, "additional": ""}
JEWELRY = {"total_budget": "25000", "occasion": "Wedding", "jewelry_type": "Any", "style": "traditional",
           "metal": "Gold", "colors": "", "additional": ""}
