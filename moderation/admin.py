from __future__ import annotations

from django.contrib import admin

from .models import BlockingReason, IncomingProductEvent, ModerationCard, OutgoingModerationEvent


@admin.register(BlockingReason)
class BlockingReasonAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "hard_block", "is_active")
    list_filter = ("hard_block", "is_active")
    search_fields = ("code", "title")
    readonly_fields = ("created_at", "updated_at")
    actions = ("deactivate",)

    @admin.action(description="Deactivate selected reasons")
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)

    def delete_model(self, request, obj):
        obj.delete()

    def delete_queryset(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(ModerationCard)
class ModerationCardAdmin(admin.ModelAdmin):
    list_display = ("product_id", "status", "assigned_moderator_id", "blocking_reason", "decision_at")
    list_filter = ("status", "blocking_reason", "kind")
    search_fields = ("product_id", "seller_id", "assigned_moderator_id")


@admin.register(OutgoingModerationEvent)
class OutgoingModerationEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "card", "delivered", "created_at", "delivered_at")
    list_filter = ("event_type", "delivered")
    search_fields = ("idempotency_key", "card__product_id")


@admin.register(IncomingProductEvent)
class IncomingProductEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "product_id", "idempotency_key", "created_at")
    list_filter = ("event_type",)
    search_fields = ("idempotency_key", "product_id")
