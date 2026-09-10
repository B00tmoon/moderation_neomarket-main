from __future__ import annotations

import uuid

import pytest

from moderation.models import ModerationCard, OutgoingModerationEvent


@pytest.mark.django_db
def test_mod03_approve_event_matches_b2b_openapi_request(client, settings, monkeypatch) -> None:
    moderator_id = uuid.uuid4()
    card = ModerationCard.objects.create(
        product_id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        status=ModerationCard.Status.IN_REVIEW,
        assigned_moderator_id=moderator_id,
        json_after={"skus": [{"id": str(uuid.uuid4())}]},
    )
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
        {"moderator_comment": "approved"},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 200
    assert sent["url"] == "https://b2b.example.test/api/v1/moderation/events"
    assert sent["headers"]["X-Service-Key"] == settings.B2B_SERVICE_KEY
    assert {
        "idempotency_key",
        "product_id",
        "event_type",
        "occurred_at",
        "moderator_id",
        "moderator_comment",
    } <= set(sent["json"])
    assert sent["json"]["product_id"] == str(card.product_id)
    assert sent["json"]["event_type"] == "MODERATED"
    assert sent["json"]["moderator_id"] == str(moderator_id)
    assert sent["json"]["moderator_comment"] == "approved"
    assert "status" not in sent["json"]

    event = OutgoingModerationEvent.objects.get(card=card, event_type="MODERATED")
    assert event.payload["event_type"] == "MODERATED"
    assert event.payload["occurred_at"]
