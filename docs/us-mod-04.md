# US-MOD-04: мягкая блокировка с замечаниями

## Что покрыто

- `POST /api/v1/tickets/{ticket_id}/block` принимает `BlockDecisionRequest`: `blocking_reason_ids`, `comment`, `field_reports`.
- При причине с `hard_block=false` тикет переходит из `IN_REVIEW` в `BLOCKED`.
- `field_reports` сохраняются во внутренней OpenAPI-форме Moderation: `field_path`, `message`, `severity`.
- В B2B уходит `ModerationEventRequest` на `/api/v1/moderation/events`.
- При отправке в B2B поле `field_path` маппится в `field_name`, а `message` в `comment`.
- Ответ endpoint соответствует `TicketResponse`: `id`, `product_id`, `seller_id`, `kind`, `status`, `queue_priority`, `created_at`.
- Если B2B недоступен, решение откатывается, тикет остаётся в `IN_REVIEW`.

## ADR

Рассматривались три способа хранения `field_reports`: отдельная таблица с FK, JSON-массив в карточке и event sourcing. Выбран JSON-массив в `ModerationCard`: он проще для MVP, не требует отдельной миграции при добавлении нового поля замечания и без лишних join отдаёт payload модераторскому UI. Отдельная таблица удобнее для аналитики по конкретным полям, но повышает сложность схемы и запросов. Event sourcing даёт лучший аудит, но избыточен для текущего сервиса и увеличивает размер хранимых событий.

Если выбрана hard-only причина, общий `/block` маршрутизирует решение в `HARD_BLOCKED`; это сохраняет единый endpoint из OpenAPI и закрывает сценарий MOD-05.
