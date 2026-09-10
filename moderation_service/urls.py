from __future__ import annotations

from django.contrib import admin
from django.urls import path

from moderation import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/product-blocking-reasons", views.blocking_reasons, name="product-blocking-reasons"),
    path("api/v1/blocking-reasons", views.blocking_reasons, name="blocking-reasons"),
    path("api/v1/blocking-reasons/<uuid:reason_id>", views.blocking_reason_detail, name="blocking-reason-detail"),
    path("api/v1/tickets/<uuid:ticket_id>/approve", views.approve_ticket, name="approve-ticket"),
    path("api/v1/tickets/<uuid:ticket_id>/block", views.block_ticket, name="block-ticket"),
    path("api/v1/tickets/<uuid:ticket_id>/decline", views.decline_ticket, name="decline-ticket"),
    path("api/v1/products/<uuid:product_id>/approve", views.approve_product, name="approve-product"),
    path("api/v1/products/<uuid:product_id>/decline", views.decline_product, name="decline-product"),
    path("api/v1/b2b/events", views.product_event, name="b2b-events"),
    path("api/v1/events/product", views.product_event, name="product-event"),
]
