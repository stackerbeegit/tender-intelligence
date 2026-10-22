"""Opportunity CRM API: promotion, workflow, people, notes, permissions,
and qualification on the tenders list."""
import uuid

from app.models.enums import EligibilityStatus
from app.models.qualification_result import QualificationResult


def _login(client, email, role_name, full_name="Test User"):
    created = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "full_name": full_name, "role_name": role_name},
    ).json()
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}, created["id"]


def test_promote_a_tender_and_walk_it_to_the_bid_decision(client, sample_tender, outbox):
    sales, _ = _login(client, "sales-o@stackerbee.com", "sales")
    bd, _ = _login(client, "bd-o@stackerbee.com", "bd_manager")

    created = client.post("/api/v1/opportunities", headers=sales, json={"tender_id": str(sample_tender.id)})
    assert created.status_code == 201
    opp = created.json()
    assert opp["status"] == "new" and opp["created_from"] == "manual"
    assert opp["owner"]["email"] == "sales-o@stackerbee.com"
    assert opp["allowed_transitions"] == ["screening", "no_bid"]

    url = f"/api/v1/opportunities/{opp['id']}"
    for step in ("screening", "qualified", "management_review", "bid_no_bid"):
        assert client.post(f"{url}/transitions", headers=sales, json={"to_status": step}).status_code == 200

    blocked = client.post(f"{url}/transitions", headers=sales, json={"to_status": "proposal_in_progress"})
    assert blocked.status_code == 403
    decided = client.post(
        f"{url}/transitions", headers=bd, json={"to_status": "proposal_in_progress", "comment": "Strong fit"}
    ).json()
    assert decided["status"] == "proposal_in_progress"
    assert [h["to_status"] for h in decided["history"]] == [
        "new", "screening", "qualified", "management_review", "bid_no_bid", "proposal_in_progress",
    ]
    assert decided["history"][-1]["changed_by"]["email"] == "bd-o@stackerbee.com"
    assert decided["history"][-1]["comment"] == "Strong fit"


def test_invalid_transitions_and_missing_reasons_are_400(client, sample_tender):
    sales, _ = _login(client, "sales-o2@stackerbee.com", "sales")
    opp = client.post("/api/v1/opportunities", headers=sales, json={"tender_id": str(sample_tender.id)}).json()
    url = f"/api/v1/opportunities/{opp['id']}/transitions"

    skip = client.post(url, headers=sales, json={"to_status": "won"})
    assert skip.status_code == 400 and "Cannot move" in skip.json()["detail"]
    no_reason = client.post(url, headers=sales, json={"to_status": "no_bid"})
    assert no_reason.status_code == 400 and "reason" in no_reason.json()["detail"]


def test_one_opportunity_per_tender_returns_the_existing_id(client, sample_tender):
    sales, _ = _login(client, "sales-o3@stackerbee.com", "sales")
    first = client.post("/api/v1/opportunities", headers=sales, json={"tender_id": str(sample_tender.id)}).json()
    again = client.post("/api/v1/opportunities", headers=sales, json={"tender_id": str(sample_tender.id)})
    assert again.status_code == 409
    assert again.json()["detail"]["opportunity_id"] == first["id"]

    ref = client.get(f"/api/v1/tenders/{sample_tender.id}/opportunity", headers=sales).json()
    assert ref["opportunity"]["id"] == first["id"]


def test_assign_owner_and_notes(client, sample_tender, outbox):
    bd, _ = _login(client, "bd-o4@stackerbee.com", "bd_manager")
    tech, tech_id = _login(client, "tech-o4@stackerbee.com", "technical", "Tech Lead")
    opp = client.post("/api/v1/opportunities", headers=bd, json={"tender_id": str(sample_tender.id)}).json()
    url = f"/api/v1/opportunities/{opp['id']}"

    assigned = client.post(f"{url}/assignments", headers=bd, json={"user_id": tech_id, "team": "technical"})
    assert assigned.status_code == 201
    assignment = assigned.json()["assignments"][0]
    assert assignment["user"]["full_name"] == "Tech Lead" and assignment["team"] == "technical"
    assert [m.to for m in outbox.sent] == ["tech-o4@stackerbee.com"]

    owner = client.patch(url, headers=bd, json={"owner_id": tech_id}).json()
    assert owner["owner"]["id"] == tech_id

    note = client.post(f"{url}/notes", headers=tech, json={"note_text": "Checked the SLA annexure."})
    assert note.status_code == 201
    assert client.get(url, headers=tech).json()["notes"][0]["note_text"] == "Checked the SLA annexure."

    # Technical can comment but not move the workflow or reassign.
    assert client.post(f"{url}/transitions", headers=tech, json={"to_status": "screening"}).status_code == 403
    assert client.delete(f"{url}/assignments/{assignment['id']}", headers=tech).status_code == 403
    assert client.delete(f"{url}/assignments/{assignment['id']}", headers=bd).status_code == 204


def test_list_filters_mine_and_status(client, sample_tender, sample_source, db_session):
    from app.models.tender import Tender

    sales, _ = _login(client, "sales-o5@stackerbee.com", "sales")
    bd, _ = _login(client, "bd-o5@stackerbee.com", "bd_manager")
    other = Tender(source_id=sample_source.id, fingerprint_hash=uuid.uuid4().hex, title="Other tender")
    db_session.add(other)
    db_session.commit()
    mine = client.post("/api/v1/opportunities", headers=sales, json={"tender_id": str(sample_tender.id)}).json()
    client.post("/api/v1/opportunities", headers=bd, json={"tender_id": str(other.id)})
    client.post(f"/api/v1/opportunities/{mine['id']}/transitions", headers=sales, json={"to_status": "screening"})

    everything = client.get("/api/v1/opportunities", headers=sales).json()
    assert everything["total"] == 2
    only_mine = client.get("/api/v1/opportunities?mine=true", headers=sales).json()
    assert [o["id"] for o in only_mine["items"]] == [mine["id"]]
    screening = client.get("/api/v1/opportunities?status=screening", headers=bd).json()
    assert [o["tender"]["title"] for o in screening["items"]] == [sample_tender.title]


def test_viewer_can_read_but_not_change(client, sample_tender):
    sales, _ = _login(client, "sales-o6@stackerbee.com", "sales")
    viewer, _ = _login(client, "viewer-o6@stackerbee.com", "viewer")
    opp = client.post("/api/v1/opportunities", headers=sales, json={"tender_id": str(sample_tender.id)}).json()

    assert client.get(f"/api/v1/opportunities/{opp['id']}", headers=viewer).json()["allowed_transitions"] == []
    assert client.post("/api/v1/opportunities", headers=viewer, json={"tender_id": str(sample_tender.id)}).status_code == 403
    assert client.post(f"/api/v1/opportunities/{opp['id']}/notes", headers=viewer, json={"note_text": "x"}).status_code == 403


def test_tender_list_shows_qualification_and_sorts_by_relevance(client, sample_source, db_session):
    from datetime import datetime, timezone

    from app.models.tender import Tender

    headers, _ = _login(client, "viewer-o7@stackerbee.com", "viewer")
    scores = {"Low": 20, "High": 90, "Unscored": None}
    for title, score in scores.items():
        tender = Tender(source_id=sample_source.id, fingerprint_hash=uuid.uuid4().hex, title=title)
        db_session.add(tender)
        db_session.flush()
        if score is not None:
            db_session.add(
                QualificationResult(
                    tender_id=tender.id, eligibility_status=EligibilityStatus.UNCERTAIN, relevance_score=score,
                    relevance_factors={}, reasons=[], risks=[], engine_version="1.0",
                    computed_at=datetime.now(timezone.utc),
                )
            )
    db_session.commit()

    items = client.get("/api/v1/tenders?sort=relevance", headers=headers).json()["items"]
    assert [i["title"] for i in items] == ["High", "Low", "Unscored"]
    assert items[0]["qualification"] == {"eligibility_status": "UNCERTAIN", "relevance_score": 90}
    assert items[2]["qualification"] is None

    filtered = client.get("/api/v1/tenders?min_relevance=50", headers=headers).json()
    assert [i["title"] for i in filtered["items"]] == ["High"] and filtered["total"] == 1


def test_user_directory_is_available_to_signed_in_users(client):
    headers, _ = _login(client, "sales-o8@stackerbee.com", "sales", "Asha")
    people = client.get("/api/v1/users/directory", headers=headers).json()
    assert {"full_name": "Asha", "role": "sales"}.items() <= people[0].items()
    assert "hashed_password" not in people[0]


def test_digest_preview_and_test_send(client, outbox):
    admin, _ = _login(client, "admin-o9@stackerbee.com", "admin", "Admin Person")
    preview = client.get("/api/v1/notifications/digest/preview", headers=admin).json()
    assert preview["subject"].startswith("Tender digest") and "Hello Admin Person" in preview["html"]

    sent = client.post("/api/v1/notifications/digest/test", headers=admin).json()
    assert sent["status"] == "sent" and sent["subject"].startswith("[Test] Tender digest")
    assert outbox.sent[0].to == "admin-o9@stackerbee.com"
    assert client.get("/api/v1/notifications", headers=admin).json()[0]["event_type"] == "digest.test"

    viewer, _ = _login(client, "viewer-o9@stackerbee.com", "viewer")
    assert client.post("/api/v1/notifications/digest/test", headers=viewer).status_code == 403
