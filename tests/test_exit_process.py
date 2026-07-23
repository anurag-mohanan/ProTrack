"""Exit process — generic employee exit interview (PP-HRD-FO-30)."""

from tests.conftest import IDS, login


def test_exit_interview_form_and_crud(client, session):
    headers = login(client, "admin@prosohm.com")

    form = client.get("/api/v1/hr/exit-process/form", headers=headers)
    assert form.status_code == 200, form.text
    questions = form.json()
    assert len(questions) >= 8
    assert any(q["id"] == "reason_for_leaving" for q in questions)

    create = client.post(
        "/api/v1/hr/exit-process",
        headers=headers,
        json={
            "employee_name": "Exit Test Person",
            "employee_user_id": str(IDS["user_binil"]),
            "designation": "Designer",
            "last_working_date": "2026-08-15",
            "answers": {
                "reason_for_leaving": "Career growth / new opportunity",
                "overall_experience": 4,
            },
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["form_code"] == "PP-HRD-FO-30"
    assert body["status"] == "draft"
    assert body["answers"]["reason_for_leaving"] == "Career growth / new opportunity"
    assert len(body["questions"]) >= 8
    interview_id = body["id"]

    listed = client.get("/api/v1/hr/exit-process?status=draft", headers=headers)
    assert listed.status_code == 200
    assert any(row["id"] == interview_id for row in listed.json())

    patched = client.patch(
        f"/api/v1/hr/exit-process/{interview_id}",
        headers=headers,
        json={
            "status": "completed",
            "answers": {"additional_comments": "All the best."},
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "completed"
    assert patched.json()["answers"]["additional_comments"] == "All the best."
    assert patched.json()["answers"]["reason_for_leaving"] == "Career growth / new opportunity"
    assert patched.json()["completed_at"] is not None

    deleted = client.delete(f"/api/v1/hr/exit-process/{interview_id}", headers=headers)
    assert deleted.status_code == 204


def test_exit_process_forbidden_for_designer(client, session):
    headers = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/hr/exit-process", headers=headers)
    assert response.status_code == 403
