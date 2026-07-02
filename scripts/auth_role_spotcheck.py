"""Quick auth and role permission spot-check for RC certification."""
from app.api.deps import get_db
from app.db.session import SessionLocal
from app.main import app
from fastapi.testclient import TestClient

PASSWORD = "Password@123"


def override():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override
client = TestClient(app)

checks = [
    ("admin@prosohm.com", "/api/v1/users", 200),
    ("admin@prosohm.com", "/api/v1/settings/branding", 200),
    ("pm@prosohm.com", "/api/v1/users", 403),
    ("binil@prosohm.com", "/api/v1/users", 403),
    ("binil@prosohm.com", "/api/v1/timesheet-entries", 200),
    ("ranjith@prosohm.com", "/api/v1/timesheet-entries", 200),
]

print("AUTH SPOT CHECK")
login = client.post("/api/v1/auth/login", json={"email": "admin@prosohm.com", "password": PASSWORD})
print("login", login.status_code)
headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
print("me", client.get("/api/v1/auth/me", headers=headers).status_code)
print("profile", client.get("/api/v1/auth/me/profile", headers=headers).status_code)
refresh = client.post("/api/v1/auth/refresh", headers=headers)
print("refresh", refresh.status_code)

for email, path, expected in checks:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"FAIL login {email}: {resp.status_code}")
        continue
    h = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=h).json()
    got = client.get(path, headers=h).status_code
    ok = "OK" if got == expected else "FAIL"
    print(f"{ok} {email} ({me.get('role_name')}) GET {path}: {got} (expected {expected})")
