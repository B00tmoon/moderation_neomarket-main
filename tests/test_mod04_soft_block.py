from __future__ import annotations

import uuid

import pytest

from moderation.models import BlockingReason, ModerationCard, OutgoingModerationEvent


def make_review_card(moderator_id=None) -> ModerationCard:
    moderator_id = moderator_id or uuid.uuid4()
    return ModerationCard.objects.create(
        product_id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
        status=ModerationCard.Status.IN_REVIEW,
        assigned_moderator_id=moderator_id,
        kind=ModerationCard.Kind.EDIT,
        queue_priority=2,
        json_after={"skus": [{"id": str(uuid.uuid4())}]},
    )


def soft_reason() -> BlockingReason:
    return BlockingReason.objects.get(code="DESCRIPTION_MISMATCH")


@pytest.mark.django_db
def test_soft_block_transitions_to_blocked_with_field_reports(client) -> None:
    moderator_id = uuid.uuid4()
    card = make_review_card(moderator_id)
    reason = soft_reason()

    response = client.post(
        f"/api/v1/tickets/{card.id}/block",
        {
            "blocking_reason_ids": [str(reason.id)],
            "comment": "Please rewrite copied description",
            "field_reports": [
                {
                    "field_path": "images[0].url",
                    "message": "Photo is blurry",
                    "severity": "WARNING",
                }
            ],
        },
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert {"id", "product_id", "seller_id", "kind", "status", "queue_priority", "created_at"} <= set(payload)
    assert payload["id"] == str(card.id)
    assert payload["product_id"] == str(card.product_id)
    assert payload["seller_id"] == str(card.seller_id)
    assert payload["kind"] == "EDIT"
    assert payload["queue_priority"] == 2
    assert payload["status"] == "BLOCKED"
    assert "ticket_id" not in payload

    card.refresh_from_db()
    assert card.status == ModerationCard.Status.BLOCKED
    assert card.blocking_reason == reason
    assert card.decision_comment == "Please rewrite copied description"
    assert card.field_reports == [
        {
            "field_path": "images[0].url",
            "message": "Photo is blurry",
            "severity": "WARNING",
        }
    ]


@pytest.mark.django_db
def test_soft_block_response_kind_uses_protocol_enum_create(client) -> None:
    moderator_id = uuid.uuid4()
    card = ModerationCard.objects.create(
        product_id=uuid.uuid4(),
        seller_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
        status=ModerationCard.Status.IN_REVIEW,
        assigned_moderator_id=moderator_id,
        json_after={"skus": [{"id": str(uuid.uuid4())}]},
    )
    reason = soft_reason()

    response = client.post(
        f"/api/v1/tickets/{card.id}/block",
        {"blocking_reason_ids": [str(reason.id)], "comment": "Needs fixes", "field_reports": []},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "CREATE"
    assert payload["kind"] in {"CREATE", "EDIT"}
    assert "product" not in payload.values()


@pytest.mark.django_db
def test_soft_block_emits_event_to_b2b(client, settings, monkeypatch) -> None:
    moderator_id = uuid.uuid4()
    card = make_review_card(moderator_id)
    reason = soft_reason()
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
        f"/api/v1/tickets/{card.id}/block",
        {
            "blocking_reason_ids": [str(reason.id)],
            "comment": "Bad content",
            "field_reports": [{"field_path": "description", "message": "Too short"}],
        },
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 200
    assert sent["url"] == "https://b2b.example.test/api/v1/moderation/events"
    assert sent["headers"]["X-Service-Key"] == settings.B2B_SERVICE_KEY
    assert sent["json"]["event_type"] == "BLOCKED"
    assert sent["json"]["product_id"] == str(card.product_id)
    assert sent["json"]["moderator_id"] == str(moderator_id)
    assert sent["json"]["moderator_comment"] == "Bad content"
    assert sent["json"]["blocking_reason_id"] == str(reason.id)
    assert sent["json"]["hard_block"] is False
    assert sent["json"]["field_reports"] == [{"field_name": "description", "comment": "Too short"}]
    assert "idempotency_key" in sent["json"]
    assert "occurred_at" in sent["json"]
    assert OutgoingModerationEvent.objects.filter(card=card, event_type="BLOCKED", delivered=True).exists()


@pytest.mark.django_db
def test_soft_block_unknown_reason_returns_400(client) -> None:
    moderator_id = uuid.uuid4()
    card = make_review_card(moderator_id)

    response = client.post(
        f"/api/v1/tickets/{card.id}/block",
        {"blocking_reason_ids": [str(uuid.uuid4())], "field_reports": []},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "UNKNOWN_REASON"


@pytest.mark.django_db
def test_soft_block_others_card_returns_403(client) -> None:
    card = make_review_card(moderator_id=uuid.uuid4())

    response = client.post(
        f"/api/v1/tickets/{card.id}/block",
        {"blocking_reason_ids": [str(soft_reason().id)], "field_reports": []},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(uuid.uuid4()),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NOT_ASSIGNED"


@pytest.mark.django_db
def test_soft_block_invalid_field_name_returns_400(client) -> None:
    moderator_id = uuid.uuid4()
    card = make_review_card(moderator_id)

    response = client.post(
        f"/api/v1/tickets/{card.id}/block",
        {
            "blocking_reason_ids": [str(soft_reason().id)],
            "field_reports": [{"message": "Field path is required"}],
        },
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_FIELD_REPORTS"


@pytest.mark.django_db
def test_soft_block_hard_only_reason_routes_to_hard_block(client) -> None:
    moderator_id = uuid.uuid4()
    card = make_review_card(moderator_id)
    hard_reason = BlockingReason.objects.get(code="COUNTERFEIT")

    response = client.post(
        f"/api/v1/tickets/{card.id}/block",
        {"blocking_reason_ids": [str(hard_reason.id)], "comment": "Counterfeit", "field_reports": []},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "HARD_BLOCKED"
    card.refresh_from_db()
    assert card.status == ModerationCard.Status.HARD_BLOCKED
    event = OutgoingModerationEvent.objects.get(card=card, event_type="BLOCKED")
    assert event.payload["hard_block"] is True


@pytest.mark.django_db
def test_soft_block_b2b_failure_rolls_back_ticket(client, settings, monkeypatch) -> None:
    moderator_id = uuid.uuid4()
    card = make_review_card(moderator_id)
    reason = soft_reason()
    settings.B2B_BASE_URL = "https://b2b.example.test"

    class Response:
        status_code = 503

    monkeypatch.setattr("moderation.views.requests.post", lambda *args, **kwargs: Response())

    response = client.post(
        f"/api/v1/tickets/{card.id}/block",
        {"blocking_reason_ids": [str(reason.id)], "comment": "Bad content", "field_reports": []},
        content_type="application/json",
        HTTP_X_MODERATOR_ID=str(moderator_id),
    )

    assert response.status_code == 500
    assert response.json()["code"] == "B2B_EVENT_FAILED"
    card.refresh_from_db()
    assert card.status == ModerationCard.Status.IN_REVIEW
    assert card.blocking_reason is None
    assert card.decision_comment == ""
    assert card.field_reports == []
