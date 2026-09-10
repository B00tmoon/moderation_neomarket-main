from __future__ import annotations

import uuid

import pytest

from moderation.models import ModerationCard, OutgoingModerationEvent


def make_card(
    *,
    status=ModerationCard.Status.IN_REVIEW,
    moderator_id=None,
    skus=None,
) -> ModerationCard:
    moderator_id = moderator_id or uuid.uuid4()
    return ModerationCard.objects.create(
        product_id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        status=status,
        assigned_moderator_id=moderator_id,
        json_after={"skus": skus if skus is not None else [{"id": str(uuid.uuid4())}]},
    )


@pytest.mark.django_db
def test_approve_transitions_to_moderated_and_emits_event(client, settings, monkeypatch) -> None:
    moderator_id = uuid.uuid4()
    card = make_card(moderator_id=moderator_id)
    sent = {}
    settings.B2B_BASE_URL = "https://b2b.example.test"

    class Response:
        status_code = 200

    def fake_post(url, json, headers, timeout):
        sent["url"] = url
        sent["json"] = json
        sent["headers"] = headers
        sent["timeout"] = timeout
        return Response()

    monkeypatch.setattr("moderation.views.requests.post", fake_post)

    response = client.post(
        f"/api/v1/products/{card.product_id}/approve",
        {"moderator_comment": "ok"},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "MODERATED"
    card.refresh_from_db()
    assert card.status == ModerationCard.Status.MODERATED
    assert card.decision_comment == "ok"
    assert sent["url"] == "https://b2b.example.test/api/v1/moderation/events"
    assert sent["headers"]["X-Service-Key"] == settings.B2B_SERVICE_KEY
    assert sent["json"]["product_id"] == str(card.product_id)
    assert sent["json"]["event_type"] == "MODERATED"
    assert sent["json"]["moderator_id"] == str(moderator_id)
    assert sent["json"]["moderator_comment"] == "ok"
    assert "idempotency_key" in sent["json"]
    assert "occurred_at" in sent["json"]
    assert OutgoingModerationEvent.objects.filter(card=card, event_type="MODERATED", delivered=True).exists()


@pytest.mark.django_db
def test_protocol_approve_returns_ticket_response_shape(client) -> None:
    moderator_id = uuid.uuid4()
    card = make_card(moderator_id=moderator_id)

    response = client.post(
        f"/api/v1/tickets/{card.id}/approve",
        {},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert {"id", "product_id", "seller_id", "kind", "status", "queue_priority", "created_at"} <= set(payload)
    assert payload["id"] == str(card.id)
    assert payload["status"] == "APPROVED"


@pytest.mark.django_db
def test_approve_others_card_returns_403(client) -> None:
    card = make_card(moderator_id=uuid.uuid4())

    response = client.post(
        f"/api/v1/products/{card.product_id}/approve",
        {},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(uuid.uuid4()),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NOT_ASSIGNED"


@pytest.mark.django_db
def test_approve_after_edited_returns_409(client) -> None:
    moderator_id = uuid.uuid4()
    card = make_card(status=ModerationCard.Status.PENDING, moderator_id=moderator_id)

    response = client.post(
        f"/api/v1/products/{card.product_id}/approve",
        {},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_STATUS"


@pytest.mark.django_db
def test_approve_without_sku_returns_409(client) -> None:
    moderator_id = uuid.uuid4()
    card = make_card(moderator_id=moderator_id, skus=[])

    response = client.post(
        f"/api/v1/products/{card.product_id}/approve",
        {},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "NO_SKUS"


@pytest.mark.django_db
def test_missing_moderator_identity_returns_401(client) -> None:
    card = make_card()

    response = client.post(
        f"/api/v1/products/{card.product_id}/approve",
        {},
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"
