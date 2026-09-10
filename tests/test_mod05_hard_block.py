from __future__ import annotations

import uuid

import pytest

from moderation.models import BlockingReason, ModerationCard, IncomingProductEvent, OutgoingModerationEvent


def make_review_card(moderator_id=None) -> ModerationCard:
    moderator_id = moderator_id or uuid.uuid4()
    return ModerationCard.objects.create(
        product_id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        status=ModerationCard.Status.IN_REVIEW,
        assigned_moderator_id=moderator_id,
        json_after={"skus": [{"id": str(uuid.uuid4())}]},
    )


@pytest.mark.django_db
def test_hard_block_transitions_to_terminal_and_emits_event(client, settings, monkeypatch) -> None:
    moderator_id = uuid.uuid4()
    card = make_review_card(moderator_id)
    reason = BlockingReason.objects.get(code="COUNTERFEIT")
    sent = {}
    settings.B2B_BASE_URL = "https://b2b.example.test"

    class Response:
        status_code = 200

    def fake_post(url, json, headers, timeout):
        sent["url"] = url
        sent["json"] = json
        sent["headers"] = headers
        return Response()

    monkeypatch.setattr("moderation.views.requests.post", fake_post)

    response = client.post(
        f"/api/v1/products/{card.product_id}/decline",
        {
            "blocking_reason_id": str(reason.id),
            "moderator_comment": "counterfeit",
            "field_reports": [],
        },
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "HARD_BLOCKED"
    card.refresh_from_db()
    assert card.status == ModerationCard.Status.HARD_BLOCKED
    assert card.blocking_reason == reason
    assert card.decision_comment == "counterfeit"
    assert sent["url"] == "https://b2b.example.test/api/v1/moderation/events"
    assert sent["headers"]["X-Service-Key"] == settings.B2B_SERVICE_KEY
    assert sent["json"]["event_type"] == "BLOCKED"
    assert sent["json"]["blocking_reason_id"] == str(reason.id)
    assert sent["json"]["moderator_id"] == str(moderator_id)
    assert sent["json"]["moderator_comment"] == "counterfeit"
    assert sent["json"]["field_reports"] == []
    assert "idempotency_key" in sent["json"]
    assert "occurred_at" in sent["json"]
    assert OutgoingModerationEvent.objects.filter(card=card, event_type="BLOCKED", delivered=True).exists()


@pytest.mark.django_db
def test_hard_block_event_carries_hard_block_true(client) -> None:
    moderator_id = uuid.uuid4()
    card = make_review_card(moderator_id)
    reason = BlockingReason.objects.get(code="FORBIDDEN_GOODS")

    response = client.post(
        f"/api/v1/tickets/{card.id}/block",
        {"blocking_reason_ids": [str(reason.id)], "comment": "forbidden", "field_reports": []},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(card.id)
    assert payload["status"] == "HARD_BLOCKED"
    event = OutgoingModerationEvent.objects.get(card=card, event_type="BLOCKED")
    assert event.payload["hard_block"] is True
    assert event.payload["event_type"] == "BLOCKED"
    assert event.payload["blocking_reason_id"] == str(reason.id)
    assert "occurred_at" in event.payload


@pytest.mark.django_db
def test_any_modify_on_hard_blocked_returns_403(client) -> None:
    moderator_id = uuid.uuid4()
    card = make_review_card(moderator_id)
    card.status = ModerationCard.Status.HARD_BLOCKED
    card.save(update_fields=["status", "updated_at"])
    reason = BlockingReason.objects.get(code="COPYRIGHT_VIOLATION")

    approve = client.post(
        f"/api/v1/products/{card.product_id}/approve",
        {},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )
    decline = client.post(
        f"/api/v1/products/{card.product_id}/decline",
        {"blocking_reason_id": str(reason.id), "field_reports": []},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert approve.status_code == 403
    assert decline.status_code == 403
    assert approve.json()["code"] == "HARD_BLOCKED"
    assert decline.json()["code"] == "HARD_BLOCKED"


@pytest.mark.django_db
def test_edited_event_on_hard_blocked_is_ignored(client, settings) -> None:
    card = ModerationCard.objects.create(
        product_id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        status=ModerationCard.Status.HARD_BLOCKED,
        json_after={"title": "old", "skus": [{"id": str(uuid.uuid4())}]},
    )

    response = client.post(
        "/api/v1/events/product",
        {
            "idempotency_key": "edited-on-hard-blocked",
            "event": "EDITED",
            "product_id": str(card.product_id),
            "json_after": {"title": "new"},
        },
        content_type="application/json",
        HTTP_X_SERVICE_KEY=settings.SERVICE_KEY,
    )

    assert response.status_code == 202
    assert response.json()["status"] == "ignored_hard_blocked"
    card.refresh_from_db()
    assert card.status == ModerationCard.Status.HARD_BLOCKED
    assert card.json_after["title"] == "old"
    assert IncomingProductEvent.objects.filter(idempotency_key="edited-on-hard-blocked").exists()


@pytest.mark.django_db
def test_deleted_event_removes_hard_blocked(client, settings) -> None:
    card = ModerationCard.objects.create(
        product_id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        status=ModerationCard.Status.HARD_BLOCKED,
    )

    response = client.post(
        "/api/v1/events/product",
        {
            "idempotency_key": "delete-hard-blocked",
            "event": "DELETED",
            "product_id": str(card.product_id),
        },
        content_type="application/json",
        HTTP_X_SERVICE_KEY=settings.SERVICE_KEY,
    )

    assert response.status_code == 202
    assert response.json()["status"] == "archived"
    assert not ModerationCard.objects.filter(id=card.id).exists()


@pytest.mark.django_db
def test_soft_reason_routes_to_blocked_not_hard_blocked(client) -> None:
    moderator_id = uuid.uuid4()
    card = make_review_card(moderator_id)
    reason = BlockingReason.objects.get(code="DESCRIPTION_MISMATCH")

    response = client.post(
        f"/api/v1/products/{card.product_id}/decline",
        {
            "blocking_reason_id": str(reason.id),
            "field_reports": [{"field_path": "description", "message": "too short"}],
        },
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "BLOCKED"
    card.refresh_from_db()
    assert card.field_reports == [{"field_path": "description", "message": "too short", "severity": "ERROR"}]
    event = OutgoingModerationEvent.objects.get(card=card, event_type="BLOCKED")
    assert event.payload["field_reports"] == [{"field_name": "description", "comment": "too short"}]


@pytest.mark.django_db
def test_blocked_event_matches_b2b_openapi_request(client, settings, monkeypatch) -> None:
    moderator_id = uuid.uuid4()
    card = make_review_card(moderator_id)
    reason = BlockingReason.objects.get(code="COUNTERFEIT")
    sent = {}
    settings.B2B_BASE_URL = "https://b2b.example.test"

    class Response:
        status_code = 200

    def fake_post(url, json, headers, timeout):
        sent["url"] = url
        sent["json"] = json
        return Response()

    monkeypatch.setattr("moderation.views.requests.post", fake_post)

    response = client.post(
        f"/api/v1/products/{card.product_id}/decline",
        {
            "blocking_reason_id": str(reason.id),
            "moderator_comment": "counterfeit",
            "field_reports": [{"field_path": "images[0]", "message": "bad image"}],
        },
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 200
    assert sent["url"].endswith("/api/v1/moderation/events")
    assert {
        "idempotency_key",
        "product_id",
        "event_type",
        "occurred_at",
        "moderator_id",
        "moderator_comment",
        "blocking_reason_id",
        "hard_block",
        "field_reports",
    } <= set(sent["json"])
    assert sent["json"]["event_type"] == "BLOCKED"
    assert sent["json"]["blocking_reason_id"] == str(reason.id)
    assert "blocking_reason" not in sent["json"]
    assert "status" not in sent["json"]
    assert sent["json"]["field_reports"] == [{"field_name": "images[0]", "comment": "bad image"}]


@pytest.mark.django_db
def test_b2b_event_path_accepts_product_edited_for_hard_blocked(client, settings) -> None:
    card = ModerationCard.objects.create(
        product_id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        status=ModerationCard.Status.HARD_BLOCKED,
        json_after={"title": "old", "skus": [{"id": str(uuid.uuid4())}]},
    )

    response = client.post(
        "/api/v1/b2b/events",
        {
            "idempotency_key": str(uuid.uuid4()),
            "event_type": "PRODUCT_EDITED",
            "occurred_at": "2026-06-09T00:00:00Z",
            "payload": {
                "product_id": str(card.product_id),
                "seller_id": str(card.seller_id),
                "json_before": {"title": "old"},
                "json_after": {"title": "new"},
            },
        },
        content_type="application/json",
        HTTP_X_SERVICE_KEY=settings.SERVICE_KEY,
    )

    assert response.status_code == 202
    assert response.json()["status"] == "ignored_hard_blocked"
    card.refresh_from_db()
    assert card.status == ModerationCard.Status.HARD_BLOCKED
    assert card.json_after["title"] == "old"
    assert IncomingProductEvent.objects.filter(product_id=card.product_id, event_type="EDITED").exists()


@pytest.mark.django_db
def test_b2b_event_path_accepts_product_deleted_for_hard_blocked(client, settings) -> None:
    card = ModerationCard.objects.create(
        product_id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        status=ModerationCard.Status.HARD_BLOCKED,
    )

    response = client.post(
        "/api/v1/b2b/events",
        {
            "idempotency_key": str(uuid.uuid4()),
            "event_type": "PRODUCT_DELETED",
            "occurred_at": "2026-06-09T00:00:00Z",
            "payload": {"product_id": str(card.product_id)},
        },
        content_type="application/json",
        HTTP_X_SERVICE_KEY=settings.SERVICE_KEY,
    )

    assert response.status_code == 202
    assert response.json()["status"] == "archived"
    assert not ModerationCard.objects.filter(id=card.id).exists()
