from __future__ import annotations

import uuid

import pytest

from moderation.models import BlockingReason, ModerationCard


OPENAPI_REASON_FIELDS = {"id", "code", "title", "hard_block", "is_active"}


@pytest.mark.django_db
def test_list_returns_active_reasons(client) -> None:
    response = client.get("/api/v1/product-blocking-reasons")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 10
    assert {"id", "title", "hard_block"} <= set(payload[0])
    assert all(item["is_active"] is True for item in payload)


@pytest.mark.django_db
def test_protocol_path_returns_blocking_reason_response_shape(client) -> None:
    response = client.get("/api/v1/blocking-reasons")

    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert OPENAPI_REASON_FIELDS <= set(payload[0])
    assert isinstance(payload[0]["id"], str)
    assert isinstance(payload[0]["code"], str)
    assert isinstance(payload[0]["title"], str)
    assert isinstance(payload[0]["hard_block"], bool)
    assert isinstance(payload[0]["is_active"], bool)


@pytest.mark.django_db
def test_inactive_reasons_not_visible(client) -> None:
    inactive = BlockingReason.objects.create(
        code="LEGACY_REASON",
        title="Старая причина",
        hard_block=False,
        is_active=False,
    )

    response = client.get("/api/v1/product-blocking-reasons")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert str(inactive.id) not in ids


@pytest.mark.django_db
def test_inactive_reasons_visible_only_when_requested(client) -> None:
    inactive = BlockingReason.objects.create(
        code="ARCHIVED_REASON",
        title="Архивная причина",
        hard_block=False,
        is_active=False,
    )

    response = client.get("/api/v1/blocking-reasons?is_active=false")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert str(inactive.id) in ids


@pytest.mark.django_db
def test_hard_block_filter_returns_only_requested_type(client) -> None:
    response = client.get("/api/v1/blocking-reasons?hard_block=true")

    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert all(item["hard_block"] is True for item in payload)


@pytest.mark.django_db
def test_referenced_reason_cannot_be_deleted() -> None:
    reason = BlockingReason.objects.get(code="DESCRIPTION_MISMATCH")
    ModerationCard.objects.create(
        product_id=uuid.uuid4(),
        status=ModerationCard.Status.BLOCKED,
        blocking_reason=reason,
    )

    reason.delete()

    reason.refresh_from_db()
    assert reason.is_active is False
    assert BlockingReason.objects.filter(id=reason.id).exists()
    assert ModerationCard.objects.filter(blocking_reason=reason).exists()


@pytest.mark.django_db
def test_delete_endpoint_soft_deactivates_reason(client) -> None:
    reason = BlockingReason.objects.create(
        code="TEMP_REASON",
        title="Временная причина",
        hard_block=False,
    )

    response = client.delete(f"/api/v1/blocking-reasons/{reason.id}")

    assert response.status_code == 204
    reason.refresh_from_db()
    assert reason.is_active is False
