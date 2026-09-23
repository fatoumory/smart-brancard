# tests/conftest.py
# Les tests tournent sur une base SQLite temporaire: pas besoin de PostgreSQL

import os
import sys
import tempfile
from pathlib import Path

_db = Path(tempfile.gettempdir()) / "smart_brancard_test.db"
_db.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_db.as_posix()}"
os.environ["SECRET_KEY"] = "cle_de_test"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from database import Base, SessionLocal, engine
from main import app
from models.utilisateur import Utilisateur
from services.auth_service import hash_password


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(Utilisateur(nom="Admin", prenom="Reg", email="reg@test.fr",
                       mot_de_passe_hash=hash_password("motdepasse"), role="regulateur"))
    db.commit()
    db.close()
    with TestClient(app) as c:
        yield c


def login(client, email, mot_de_passe):
    r = client.post("/auth/login", data={"username": email, "password": mot_de_passe})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
