from __future__ import annotations

import uuid

import pytest

from moderation.models import BlockingReason, ModerationCard


@pytest.mark.django_db
def test_mod06_single_artifact_covers_canonical_read_api_and_filters(client) -> None:
    soft_reason = BlockingReason.objects.create(
        code="SINGLE_ARTIFACT_SOFT",
        title="Soft reason",
        hard_block=False,
    )
    hard_reason = BlockingReason.objects.create(
        code="SINGLE_ARTIFACT_HARD",
        title="Hard reason",
        hard_block=True,
    )
    inactive_reason = BlockingReason.objects.create(
        code="SINGLE_ARTIFACT_INACTIVE",
        title="Inactive reason",
        hard_block=False,
        is_active=False,
    )

    canonical = client.get("/api/v1/product-blocking-reasons")
    assert canonical.status_code == 200
    canonical_ids = {item["id"] for item in canonical.json()}
    assert str(soft_reason.id) in canonical_ids
    assert str(hard_reason.id) in canonical_ids
    assert str(inactive_reason.id) not in canonical_ids

    hard_only = client.get("/api/v1/blocking-reasons?hard_block=true")
    assert hard_only.status_code == 200
    assert {item["id"] for item in hard_only.json()} >= {str(hard_reason.id)}
    assert all(item["hard_block"] is True for item in hard_only.json())

    inactive_only = client.get("/api/v1/blocking-reasons?is_active=false")
    assert inactive_only.status_code == 200
    assert str(inactive_reason.id) in {item["id"] for item in inactive_only.json()}


@pytest.mark.django_db
def test_mod06_single_artifact_preserves_referenced_reason_on_delete(client) -> None:
    reason = BlockingReason.objects.create(
        code="SINGLE_ARTIFACT_REFERENCED",
        title="Referenced reason",
        hard_block=False,
    )
    card = ModerationCard.objects.create(
        product_id=uuid.uuid4(),
        status=ModerationCard.Status.BLOCKED,
        blocking_reason=reason,
    )

    response = client.delete(f"/api/v1/blocking-reasons/{reason.id}")

    assert response.status_code == 204
    reason.refresh_from_db()
    card.refresh_from_db()
    assert reason.is_active is False
    assert card.blocking_reason_id == reason.id
    assert BlockingReason.objects.filter(id=reason.id).exists()
