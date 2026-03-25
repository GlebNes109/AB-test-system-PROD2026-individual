# A/B Test Platform

Бэкенд-платформа для управления A/B тестами: создание экспериментов, выдача вариантов, сбор событий, подсчёт метрик и автоматические guardrails.

> Проект выполнен в рамках олимпиады [PROD 2026](https://prodcontest.ru/) (Backend, индивидуальный трек).

## Возможности

- **Feature Flags** — создание флагов с default-значениями, таргетингом по атрибутам субъектов (DSL-парсер)
- **Эксперименты** — полный жизненный цикл: `DRAFT → REVIEW → APPROVED → RUNNING → PAUSED → FINISHED → ARCHIVED`
- **Ревью и аппрувер-группы** — настраиваемые группы аппруверов, порог одобрений, RBAC (ADMIN / EXPERIMENTER / APPROVER / VIEWER)
- **Детерминированная раздача вариантов** — hash-based stickiness (SHA-256), настраиваемые веса, % аудитории
- **Сбор событий** — batch-обработка, валидация payload по схеме, дедупликация, экспозиция с out-of-order delivery
- **Guardrails** — автоматический мониторинг метрик с действиями PAUSE / ROLLBACK при превышении порогов
- **Отчёты** — summary и timeseries с фильтрацией по периоду, разбивкой по вариантам, каталогом метрик
- **Cooling period** — ограничение на одновременное участие субъекта в экспериментах
- **Learnings Library** — база знаний по завершённым экспериментам с полнотекстовым поиском

## Стек

| Компонент | Технология |
|---|---|
| API | Python, FastAPI, SQLModel |
| БД | PostgreSQL (Materialized Views, хранимые функции) |
| Кеш | Redis (fulfilled-состояния событий, TTL) |
| Reverse proxy | Nginx |
| Тесты | Pytest, Tavern (integration/e2e), coverage.py |
| Визуализация | Metabase |
| Инфраструктура | Docker Compose, pre-commit (ruff) |

## Архитектура

4-слойная архитектура: `api/routes/` (HTTP) → `application/` (бизнес-логика) → `infra/` (репозитории, Redis) → `models/` (ORM).

### C4 Level 1 — System Context
![C4 L1](demo/B7/C4L1.png)

### C4 Level 2 — Container
![C4 L2](demo/B7/C4L2.png)

### C4 Level 3 — Component
![C4 L3](demo/B7/C4L3.png)

Подробное описание архитектурных решений, оптимизаций и компромиссов — в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Быстрый старт

```bash
cp .env.example .env
docker compose up -d
```

После старта:
- http://localhost — API платформы ([Swagger UI](http://localhost/docs))
- http://localhost/emulator — система-эмулятор (генерация нагрузки)
- http://localhost/metabase — визуализация метрик

Проверка готовности:
```bash
curl http://localhost/ready
# {"status": "ready", "checks": {"postgres": "ok", "redis": "ok"}}
```

Подробная инструкция: [demo/B1/runbook.md](demo/B1/runbook.md)

## Тестирование

```bash
docker compose --profile test up --abort-on-container-exit
```

Интеграционные тесты (Tavern) проходят полный путь через API: создание эксперимента → ревью → запуск → выдача вариантов → события → отчёт. Включают негативные сценарии (400/403/404/409/422). Отчёт покрытия сохраняется в `ab_test_platform/coverage_html/`.

## Структура репозитория

```
├── ab_test_platform/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── scripts/                      # вспомогательные скрипты (coverage и т.д.)
│   ├── coverage_html/                # отчёт покрытия тестами
│   └── src/
│       ├── api/
│       │   ├── deps.py               # DI (Depends FastAPI)
│       │   └── routes/               # HTTP-эндпоинты
│       ├── application/              # бизнес-логика
│       │   ├── decisions_service.py  # выдача вариантов (критичный путь)
│       │   ├── events_sevice.py      # обработка batch-событий (критичный путь)
│       │   ├── guardrail_service.py  # проверка guardrails (критичный путь)
│       │   ├── reports_service.py    # построение отчётов (критичный путь)
│       │   └── worker.py             # фоновые задачи (guardrails, MV refresh)
│       ├── core/                     # инициализация БД, настройки, env
│       ├── domain/                   # интерфейсы, exceptions
│       ├── infra/                    # репозитории (Postgres, Redis), DSL-парсер
│       ├── models/                   # ORM-модели (SQLModel)
│       ├── schemas/                  # Pydantic-схемы запросов/ответов
│       └── main.py
├── external_system_emulator/         # эмулятор внешней системы (FastAPI)
├── demo/                             # демо-сценарии, тестовые данные, документация
├── tests/                            # интеграционные тесты (Tavern YAML)
├── docker/                           # init-данные для Docker
├── docs/
│   ├── ARCHITECTURE.md               # архитектурные решения и диаграммы
│   └── COMPLIANCE_MATRIX.md          # матрица соответствия критериям олимпиады
└── docker-compose.yml
```

## Демо-сценарии

Пакеты демо-сценариев с тестовыми данными и Postman-коллекциями находятся в [demo/](demo/):

| Сценарий | Описание |
|---|---|
| [B1](demo/B1/) | Happy Path — полный цикл A/B теста |
| [B2](demo/B2/) | Feature Flags и выдача вариантов |
| [B3](demo/B3/) | Жизненный цикл и ревью экспериментов |
| [B4](demo/B4/) | События и атрибуция |
| [B5](demo/B5/) | Guardrails и cooling period |
| [B6](demo/B6/) | Отчёты и фиксация решений |

## Документация

- [Архитектура, C4 диаграммы, ключевые решения и компромиссы](docs/ARCHITECTURE.md)
- [Матрица соответствия критериям олимпиады](docs/COMPLIANCE_MATRIX.md)
- [Runbook (инструкция по запуску)](demo/B1/runbook.md)