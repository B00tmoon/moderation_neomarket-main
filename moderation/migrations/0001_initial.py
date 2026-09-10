from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


SEED_REASONS = [
    ("a7b8c9d0-1234-5678-ef01-890123456789", "DESCRIPTION_MISMATCH", "Описание не соответствует товару", False),
    ("b8c9d0e1-2345-6789-f012-901234567890", "IMAGE_MISMATCH", "Изображение не соответствует товару", False),
    ("c9d0e1f2-3456-7890-0123-012345678901", "WRONG_CATEGORY", "Некорректная категория товара", False),
    ("d0e1f2a3-4567-8901-1234-123456789012", "NOT_ENOUGH_INFO", "Недостаточно информации о товаре", False),
    ("e1f2a3b4-5678-9012-2345-234567890123", "OFFENSIVE_CONTENT", "Нецензурные или оскорбительные материалы", False),
    ("f2a3b4c5-6789-0123-3456-345678901234", "DUPLICATE_PRODUCT", "Дублирование существующего товара", False),
    ("a3b4c5d6-7890-1234-4567-456789012345", "INVALID_PRICE", "Некорректная цена", False),
    ("b4c5d6e7-8901-2345-5678-567890123456", "COUNTERFEIT", "Контрафактный товар", True),
    ("c5d6e7f8-9012-3456-6789-678901234567", "FORBIDDEN_GOODS", "Товар запрещён к продаже на территории РФ", True),
    ("d6e7f8a9-0123-4567-7890-789012345678", "COPYRIGHT_VIOLATION", "Товар нарушает авторские права", True),
]


def seed_reasons(apps, schema_editor):
    BlockingReason = apps.get_model("moderation", "BlockingReason")
    for reason_id, code, title, hard_block in SEED_REASONS:
        BlockingReason.objects.update_or_create(
            id=reason_id,
            defaults={
                "code": code,
                "title": title,
                "description": "",
                "hard_block": hard_block,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BlockingReason",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=64, unique=True)),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("hard_block", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["hard_block", "title"]},
        ),
        migrations.CreateModel(
            name="ModerationCard",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("product_id", models.UUIDField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("IN_REVIEW", "In Review"),
                            ("MODERATED", "Moderated"),
                            ("BLOCKED", "Blocked"),
                            ("HARD_BLOCKED", "Hard Blocked"),
                        ],
                        default="PENDING",
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "blocking_reason",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cards",
                        to="moderation.blockingreason",
                    ),
                ),
            ],
        ),
        migrations.RunPython(seed_reasons, migrations.RunPython.noop),
    ]
