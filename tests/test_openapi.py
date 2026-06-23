from fastapi.testclient import TestClient

from app.main import app


def test_openapi_json_loads():
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["openapi"].startswith("3.")
    assert payload["components"]["securitySchemes"]["OAuth2PasswordBearer"]
    assert "/api/v1/auth/login" in payload["paths"]
    assert "/api/v1/projects" in payload["paths"]


def test_swagger_ui_loads():
    client = TestClient(app)
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text
    assert "/openapi.json" in response.text


def test_openapi_has_no_ref_siblings():
    schema = app.openapi()

    def has_ref_siblings(node: object) -> bool:
        if isinstance(node, dict):
            if "$ref" in node and len(node) > 1:
                return True
            return any(has_ref_siblings(value) for value in node.values())
        if isinstance(node, list):
            return any(has_ref_siblings(item) for item in node)
        return False

    assert not has_ref_siblings(schema)
