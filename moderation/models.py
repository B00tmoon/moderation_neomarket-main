from __future__ import annotations

import uuid

from django.db import models


class BlockingReason(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    hard_block = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["hard_block", "title"]

    def __str__(self) -> str:
        return self.title

    def delete(self, using=None, keep_parents=False):
        self.is_active = False
        self.save(update_fields=["is_active", "updated_at"])


class ModerationCard(models.Model):
    class Kind(models.TextChoices):
        CREATE = "CREATE"
        EDIT = "EDIT"

    class Status(models.TextChoices):
        PENDING = "PENDING"
        IN_REVIEW = "IN_REVIEW"
        MODERATED = "MODERATED"
        BLOCKED = "BLOCKED"
        HARD_BLOCKED = "HARD_BLOCKED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product_id = models.UUIDField()
    seller_id = models.UUIDField(null=True, blank=True)
    category_id = models.UUIDField(null=True, blank=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.CREATE)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    queue_priority = models.PositiveSmallIntegerField(default=1)
    assigned_moderator_id = models.UUIDField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    claim_expires_at = models.DateTimeField(null=True, blank=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    decision_comment = models.TextField(blank=True)
    json_before = models.JSONField(null=True, blank=True)
    json_after = models.JSONField(default=dict, blank=True)
    field_reports = models.JSONField(default=list, blank=True)
    blocking_reason = models.ForeignKey(
        BlockingReason,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cards",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["product_id"]),
            models.Index(fields=["status", "queue_priority", "created_at"]),
        ]


class OutgoingModerationEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True)
    card = models.ForeignKey(ModerationCard, on_delete=models.CASCADE, related_name="outgoing_events")
    event_type = models.CharField(max_length=32)
    payload = models.JSONField(default=dict)
    delivered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)


class IncomingProductEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.CharField(max_length=128, unique=True)
    event_type = models.CharField(max_length=32)
    product_id = models.UUIDField()
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
