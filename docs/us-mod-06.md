# US-MOD-06: справочник причин блокировки

## Что покрывает PR

Этот PR фиксирует единый acceptance surface для квеста US-MOD-06.

- Read API: `GET /api/v1/product-blocking-reasons` возвращает только активные причины.
- Protocol API: `GET /api/v1/blocking-reasons` поддерживает фильтры `hard_block` и `is_active`.
- CRUD для администрирования реализован через Django Admin и API-методы создания, обновления и деактивации.
- Физическое удаление причины заменено на soft delete: `is_active=false`.
- Исторические карточки модерации не ломаются, потому что `ModerationCard.blocking_reason` остаётся защищённым FK.

## Тесты

Ключевые сценарии квеста закреплены тестами:

- `test_list_returns_active_reasons`
- `test_inactive_reasons_not_visible`
- `test_referenced_reason_cannot_be_deleted`
- `test_mod06_single_artifact_covers_canonical_read_api_and_filters`
- `test_mod06_single_artifact_preserves_referenced_reason_on_delete`

## ADR

Рассматривались три способа хранения справочника причин: enum в коде, таблица в БД с CRUD-админкой и i18n-каталог. Выбрана таблица в БД с Django Admin, потому что новую причину можно добавить без релиза сервиса, а исторические ссылки сохраняются через FK и soft delete. Enum проще для первой версии, но каждое изменение требует миграции кода и деплоя. i18n-каталог полезен для многоязычности, но усложняет MVP и не решает сам по себе сохранность исторических ссылок.
