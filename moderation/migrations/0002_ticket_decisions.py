from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("moderation", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="moderationcard",
            name="seller_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="moderationcard",
            name="category_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="moderationcard",
            name="kind",
            field=models.CharField(choices=[("CREATE", "Create"), ("EDIT", "Edit")], default="CREATE", max_length=16),
        ),
        migrations.AddField(
            model_name="moderationcard",
            name="queue_priority",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="moderationcard",
            name="assigned_moderator_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="moderationcard",
            name="claimed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="moderationcard",
            name="claim_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="moderationcard",
            name="decision_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="moderationcard",
            name="decision_comment",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="moderationcard",
            name="json_before",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="moderationcard",
            name="json_after",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="moderationcard",
            name="field_reports",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddIndex(
            model_name="moderationcard",
            index=models.Index(fields=["product_id"], name="moderation__product_1d6958_idx"),
        ),
        migrations.AddIndex(
            model_name="moderationcard",
            index=models.Index(fields=["status", "queue_priority", "created_at"], name="moderation__status_efc1a8_idx"),
        ),
        migrations.CreateModel(
            name="OutgoingModerationEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("idempotency_key", models.UUIDField(default=uuid.uuid4, unique=True)),
                ("event_type", models.CharField(max_length=32)),
                ("payload", models.JSONField(default=dict)),
                ("delivered", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                (
                    "card",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outgoing_events",
                        to="moderation.moderationcard",
                    ),
                ),
            ],
        ),
    ]
