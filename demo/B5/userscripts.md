# B5. Guardrails и cooling period — сценарии проверки

## Подготовка
```bash
# 1. Поднять платформу
docker compose up -d
```
```bash
# если нет виртуального окружения
python -m venv venv
source venv/bin/activate
```

```bash
# 2. Сгенерировать тестовые данные (запуск из /demo/B5/)
pip install requests
python data_generator.py
```

```bash
# 3. Задать BASE_URL (по умолчанию localhost, замените на адрес деплоя)
export BASE_URL="http://localhost"
```

## Что создаёт генератор

### Эксперименты

| Эксперимент | Флаг | Guardrail-метрика | Порог | Действие | Окно |
|-------------|------|-------------------|-------|----------|------|
| EXP_PAUSE | `b5_guardrail_pause` | `b5_error_rate` (COUNT b5_error / COUNT b5_page_view) | 0.5 | PAUSE | 60 мин |
| EXP_ROLLBACK | `b5_guardrail_rollback` | `b5_avg_latency` (AVG b5_latency.ms) | 500 | ROLLBACK | 60 мин |
| EXP_COOLING | `b5_cooling` | нет | — | — | — |
| EXP_COOLING_2 | `b5_cooling_second` | нет | — | — | — |

Все эксперименты в статусе **RUNNING**, аудитория 100%, 2 варианта (50/50).

### Типы событий
| Тип | payload_schema | Описание |
|-----|----------------|----------|
| `b5_page_view` | нет | Просмотр страницы |
| `b5_error` | `{"error_code": "number"}` | Ошибка на клиенте |
| `b5_click` | `{"element": "string"}` | Клик по элементу |
| `b5_latency` | `{"ms": "number"}` | Замер латентности |

### Метрики
| Ключ | Формула | Роль |
|------|---------|------|
| `b5_page_view_count` | COUNT b5_page_view | PRIMARY |
| `b5_error_rate` | COUNT b5_error / COUNT b5_page_view | GUARDRAIL (PAUSE при > 0.5) |
| `b5_click_count` | COUNT b5_click | PRIMARY |
| `b5_avg_latency` | AVG b5_latency.ms | GUARDRAIL (ROLLBACK при > 500) |

> **Важно:** `EXP_PAUSE_ID`, `EXP_ROLLBACK_ID`, `EXP_COOLING_ID` — подставьте из вывода генератора.

Для выполнения сложных проверок можно делать запросы в [сваггере]($BASE_URL/docs), там же есть спецификация API и описание всех доступных эндпоинтов системы.

### Переменные для сценариев

```bash
# Подставьте из вывода генератора:
EXP_PAUSE_ID="<id EXP_PAUSE из вывода>"
EXP_ROLLBACK_ID="<id EXP_ROLLBACK из вывода>"
EXP_COOLING_ID="<id EXP_COOLING из вывода>"
EXP_COOLING2_ID="<id EXP_COOLING_2 из вывода>"
```

### Получение JWT-токена

```bash
EXPERIMENTER_TOKEN=$(curl -s -X POST ${BASE_URL}/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "b5_experimenter@demo.com", "password": "Demo1234!x"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

echo "EXPERIMENTER_TOKEN=$EXPERIMENTER_TOKEN"
```

> **Примечание об отчётах:** метрики считаются по материализованному представлению (MV), которое обновляется каждые несколько секунд (`mv_refresh_interval_seconds`). Guardrails проверяются каждые `guardrail_check_interval_seconds` (по умолчанию 2 сек). После отправки событий подождите ~5–10 секунд перед проверкой статуса.

---

## B5-1. Привязка guardrail-метрики к эксперименту

**Критерий:** при создании эксперимента можно указать метрику с `type=GUARDRAIL`, задав `threshold`, `window_minutes`, `action`.

Генератор уже создал эксперименты с guardrail-метриками. Проверим, что параметры сохранились.

### Проверка EXP_PAUSE

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_PAUSE_ID}" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Experiment: {data['name']}\")
print(f\"Status: {data['status']}\")
for m in data.get('metrics', []):
    if m['type'] == 'GUARDRAIL':
        print(f\"GUARDRAIL metric: {m['metric_key']}\")
        print(f\"  threshold:      {m['threshold']}\")
        print(f\"  window_minutes: {m['window_minutes']}\")
        print(f\"  action:         {m['action']}\")
"
```

### Ожидаемый ответ

```
Experiment: B5: guardrail PAUSE (error_rate > 0.5)
Status: RUNNING
GUARDRAIL metric: b5_error_rate
  threshold:      0.5
  window_minutes: 60
  action:         PAUSE
```

### Проверка EXP_ROLLBACK

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_ROLLBACK_ID}" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Experiment: {data['name']}\")
print(f\"Status: {data['status']}\")
for m in data.get('metrics', []):
    if m['type'] == 'GUARDRAIL':
        print(f\"GUARDRAIL metric: {m['metric_key']}\")
        print(f\"  threshold:      {m['threshold']}\")
        print(f\"  window_minutes: {m['window_minutes']}\")
        print(f\"  action:         {m['action']}\")
"
```

### Ожидаемый ответ

```
Experiment: B5: guardrail ROLLBACK (avg_latency > 500ms)
Status: RUNNING
GUARDRAIL metric: b5_avg_latency
  threshold:      500.0
  window_minutes: 60
  action:         ROLLBACK
```

**Что проверить:**
- Метрика с `type=GUARDRAIL` присутствует в ответе
- `threshold`, `window_minutes`, `action` соответствуют заданным при создании

---

## B5-2. Сохранение guardrail-параметров при редактировании

**Критерий:** guardrail-параметры не теряются при обновлении эксперимента.

> Эксперимент нельзя редактировать в статусе RUNNING (заморозка конфига). Для проверки этого критерия создайте новый эксперимент в DRAFT и отредактируйте его, или проверьте, что генератор корректно создал guardrail-параметры (см. B5-1). Редактирование подразумевает изменение параметров в статусе DRAFT/REJECTED.

Создадим новый эксперимент в DRAFT, проверим guardrail-параметры, изменим threshold, проверим снова:

```bash
# Создаём эксперимент в DRAFT
NEW_EXP=$(curl -s -X POST "${BASE_URL}/api/v1/experiments" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "B5-2: проверка обновления guardrail",
    "feature_flag_key": "b5_guardrail_pause",
    "audience_percentage": 100,
    "variants": [
      {"name": "control", "value": "old_page", "weight": 50, "is_control": true},
      {"name": "treatment", "value": "new_page", "weight": 50, "is_control": false}
    ],
    "metrics": [
      {"metric_key": "b5_page_view_count", "type": "PRIMARY"},
      {"metric_key": "b5_error_rate", "type": "GUARDRAIL",
       "threshold": 0.3, "window_minutes": 30, "action": "PAUSE"}
    ]
  }')

NEW_EXP_ID=$(echo "$NEW_EXP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "NEW_EXP_ID=$NEW_EXP_ID"
```

```bash
# Обновляем threshold и action
curl -s -X PATCH "${BASE_URL}/api/v1/experiments/${NEW_EXP_ID}" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": [
      {"metric_key": "b5_page_view_count", "type": "PRIMARY"},
      {"metric_key": "b5_error_rate", "type": "GUARDRAIL",
       "threshold": 0.8, "window_minutes": 120, "action": "ROLLBACK"}
    ]
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('metrics', []):
    if m['type'] == 'GUARDRAIL':
        print(f\"Updated GUARDRAIL: {m['metric_key']}\")
        print(f\"  threshold:      {m['threshold']}  (было 0.3, стало 0.8)\")
        print(f\"  window_minutes: {m['window_minutes']}  (было 30, стало 120)\")
        print(f\"  action:         {m['action']}  (было PAUSE, стало ROLLBACK)\")
"
```

**Что проверить:**
- `threshold` обновился с 0.3 на 0.8
- `window_minutes` обновился с 30 на 120
- `action` обновился с PAUSE на ROLLBACK

---

## B5-3. Обнаружение превышения порога (action=PAUSE)

**Критерий:** фоновый цикл обнаруживает, что guardrail-метрика превысила порог, и ставит эксперимент на паузу.

EXP_PAUSE: guardrail `b5_error_rate > 0.5` → PAUSE. Нужно отправить события так, чтобы error_rate (доля ошибок) превысила 0.5 для тестового варианта.

### Шаг 1: Получить decision для субъекта

```bash
DECISION_PAUSE=$(curl -s -X POST ${BASE_URL}/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "b5-user-pause-01",
    "subject_attr": {},
    "flags_keys": ["b5_guardrail_pause"]
  }' | python3 -c "import sys,json; d=json.load(sys.stdin)[0]; print(d['id'])")

echo "DECISION_PAUSE=$DECISION_PAUSE"
```

> Повторите для нескольких субъектов (b5-user-pause-02, -03, ...), пока не попадёте в тестовый вариант (value = `"new_page"`). Контрольный вариант (`"old_page"`) не проверяется guardrail.

### Шаг 2: Отправить 1 page_view + 1 error (error_rate = 1.0 > 0.5)

```bash
# page_view
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [{
      \"event_type\": \"b5_page_view\",
      \"decision_id\": \"${DECISION_PAUSE}\"
    }]
  }" | python3 -m json.tool
```

```bash
# error (error_rate станет 1/1 = 1.0 > 0.5)
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [{
      \"event_type\": \"b5_error\",
      \"decision_id\": \"${DECISION_PAUSE}\",
      \"payload\": {\"error_code\": 500}
    }]
  }" | python3 -m json.tool
```

### Шаг 3: Подождать ~10 секунд и проверить статус

```bash

curl -s "${BASE_URL}/api/v1/experiments/${EXP_PAUSE_ID}" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Status: {data['status']}\")
print(f\"Result: {data.get('result')}\")
print(f\"Result description: {data.get('result_description')}\")
"
```

### Ожидаемый результат

```
Status: PAUSED
Result: None
Result description: None
```

**Что проверить:**
- Статус сменился с `RUNNING` на `PAUSED`
- `result` = `None` (эксперимент поставлен на паузу, не завершён)

---

## B5-4. Выполнение действия ROLLBACK при срабатывании guardrail

**Критерий:** при action=ROLLBACK эксперимент автоматически финишируется со статусом ROLLBACK и описанием.

EXP_ROLLBACK: guardrail `b5_avg_latency > 500ms` → ROLLBACK.

### Вариант A: Вручную через curl

#### Шаг 1: Получить decision

```bash
DECISION_ROLLBACK=$(curl -s -X POST ${BASE_URL}/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "b5-user-rollback-01",
    "subject_attr": {},
    "flags_keys": ["b5_guardrail_rollback"]
  }' | python3 -c "import sys,json; d=json.load(sys.stdin)[0]; print(d['id'])")

echo "DECISION_ROLLBACK=$DECISION_ROLLBACK"
```

> Повторите для нескольких субъектов, пока не попадёте в тестовый вариант (`"new_layout"`).

#### Шаг 2: Отправить события с высокой латентностью (avg > 500)

```bash
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [{
      \"event_type\": \"b5_latency\",
      \"decision_id\": \"${DECISION_ROLLBACK}\",
      \"payload\": {\"ms\": 1200}
    }]
  }" | python3 -m json.tool
```

#### Шаг 3: Подождать и проверить

```bash

curl -s "${BASE_URL}/api/v1/experiments/${EXP_ROLLBACK_ID}" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Status: {data['status']}\")
print(f\"Result: {data.get('result')}\")
print(f\"Result description: {data.get('result_description')}\")
"
```

### Ожидаемый результат

```
Status: FINISHED
Result: ROLLBACK
Result description: Остановлен автоматически: guardrail метрика 'b5_avg_latency' превысила порог (1200.0000 > 500.0000)
```

### Вариант B: Через систему-эмулятор

Конфиг для эмулятора — создаёт 50 субъектов, каждый из которых отправляет `b5_latency` с высокой вероятностью. Средняя латентность будет ~1000ms > 500ms порога.

```json
{
  "scenario_name": "B5-4: trigger ROLLBACK guardrail (avg_latency > 500ms)",
  "subjects_count": 50,
  "use_real_time": false,
  "experiment": {
    "feature_flag_key": "b5_guardrail_rollback",
    "time_delay_seconds": 0,
    "time_variation": 0,
    "variants": [
      {
        "feature_flag_value": "old_layout",
        "events": [
          {
            "event_type": "b5_latency",
            "time_delay_seconds": 0,
            "time_variation": 0,
            "probability": 1.0
          }
        ]
      },
      {
        "feature_flag_value": "new_layout",
        "events": [
          {
            "event_type": "b5_latency",
            "time_delay_seconds": 0,
            "time_variation": 0,
            "probability": 1.0
          }
        ]
      }
    ]
  }
}
```

> **Примечание:** эмулятор не поддерживает произвольные payload-значения — он отправляет события без payload. Для guardrail-метрики `AVG` по полю `ms` необходимо отправлять payload вручную. Используйте **Вариант A** (curl) для надёжной проверки этого сценария.

**Что проверить после эмулятора или curl:**
- `status` = `FINISHED`
- `result` = `ROLLBACK`
- `result_description` содержит информацию о превышении порога

---

## B5-5. История срабатываний guardrail (guardrail-triggers)

**Критерий:** после срабатывания guardrail в системе сохраняется запись с деталями.

> Выполните сценарий B5-3 или B5-4 перед этим шагом, чтобы guardrail сработал.

### Проверка triggers для EXP_PAUSE

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_PAUSE_ID}/guardrail-triggers" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
if not data:
    print('Нет записей (guardrail не срабатывал)')
else:
    for t in data:
        print(f\"Trigger:\")
        print(f\"  metric_id:    {t['metric_id']}\")
        print(f\"  threshold:    {t['threshold']}\")
        print(f\"  actual_value: {t['actual_value']}\")
        print(f\"  action_taken: {t['action_taken']}\")
        print(f\"  triggered_at: {t['triggered_at']}\")
"
```

### Ожидаемый ответ (после B5-3)

```
Trigger:
  metric_id:    <uuid>
  threshold:    0.5
  actual_value: 1.0
  action_taken: PAUSE
  triggered_at: 2026-02-23T...
```

### Проверка triggers для EXP_ROLLBACK

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_ROLLBACK_ID}/guardrail-triggers" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
if not data:
    print('Нет записей (guardrail не срабатывал)')
else:
    for t in data:
        print(f\"Trigger:\")
        print(f\"  metric_id:    {t['metric_id']}\")
        print(f\"  threshold:    {t['threshold']}\")
        print(f\"  actual_value: {t['actual_value']}\")
        print(f\"  action_taken: {t['action_taken']}\")
        print(f\"  triggered_at: {t['triggered_at']}\")
"
```

### Конфиг эмулятора для генерации данных (для PAUSE-сценария)

Если нужно сгенерировать много событий для срабатывания error_rate guardrail:

```json
{
  "scenario_name": "B5-5: trigger PAUSE guardrail (error_rate > 0.5)",
  "subjects_count": 100,
  "use_real_time": false,
  "experiment": {
    "feature_flag_key": "b5_guardrail_pause",
    "time_delay_seconds": 0,
    "time_variation": 0,
    "variants": [
      {
        "feature_flag_value": "old_page",
        "events": [
          {
            "event_type": "b5_page_view",
            "time_delay_seconds": 0,
            "time_variation": 0,
            "probability": 1.0
          },
          {
            "event_type": "b5_error",
            "time_delay_seconds": 0,
            "time_variation": 0,
            "probability": 0.1
          }
        ]
      },
      {
        "feature_flag_value": "new_page",
        "events": [
          {
            "event_type": "b5_page_view",
            "time_delay_seconds": 0,
            "time_variation": 0,
            "probability": 1.0
          },
          {
            "event_type": "b5_error",
            "time_delay_seconds": 0,
            "time_variation": 0,
            "probability": 0.9
          }
        ]
      }
    ]
  }
}
```

> В control-варианте error_rate ~0.1 (10% ошибок), в treatment ~0.9 (90% ошибок) — guardrail сработает на treatment.

**Что проверить:**
- Массив содержит хотя бы одну запись
- `threshold` соответствует заданному в эксперименте
- `actual_value` > `threshold`
- `action_taken` = `PAUSE` или `ROLLBACK`
- `triggered_at` — время срабатывания

---

## B5-6. Cooling period и лимит активных экспериментов

**Критерий:** субъект не попадает в новый эксперимент, если не прошёл cooling period или превышен лимит активных экспериментов.

Cooling period настраивается через переменные окружения:
- `COOLING_PERIOD_DAYS` (по умолчанию 1)
- `MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT` (по умолчанию 10)

### 6a. Cooling period

Субъект, который только что получил decision в одном эксперименте, должен получить `default` при запросе к другому эксперименту (если прошло меньше `COOLING_PERIOD_DAYS` дней).

Для этого теста используются два **отдельных** RUNNING-эксперимента на разных флагах:
- **EXP_COOLING** (флаг `b5_cooling`) — субъект попадает сюда на шаге 1
- **EXP_COOLING_2** (флаг `b5_cooling_second`) — субъект пытается попасть сюда на шаге 2, но получает default из-за cooling

#### Шаг 1: Получить decision в EXP_COOLING

```bash
curl -s -X POST ${BASE_URL}/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "b5-user-cooling-test",
    "subject_attr": {},
    "flags_keys": ["b5_cooling"]
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
for d in data:
    print(f\"flag=b5_cooling  value={d['value']}  id={d['id']}\")
"
```

#### Шаг 2: Сразу запросить decision для другого флага (EXP_COOLING_2)

```bash
curl -s -X POST ${BASE_URL}/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "b5-user-cooling-test",
    "subject_attr": {},
    "flags_keys": ["b5_cooling_second"]
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
for d in data:
    print(f\"flag=b5_cooling_second  value={d['value']}  id={d['id']}\")
"
```

### Ожидаемый результат

```
# Шаг 1: субъект получает вариант (не default)
flag=b5_cooling  value=baseline  id=<uuid>    # или experiment_v

# Шаг 2: субъект получает default (cooling period)
flag=b5_cooling_second  value=fallback  id=None
```

**Что проверить:**
- В шаге 1 `id` не `None` — субъект попал в эксперимент
- В шаге 2 `id` = `None` — субъект получил default из-за cooling period
- `value` в шаге 2 равно `default_value` флага `b5_cooling_second` (`"fallback"`)

### 6b. Лимит активных экспериментов

По умолчанию лимит `MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT=10`. Для демонстрации можно уменьшить до 1 в `.env`:

```
MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT=1
```

После этого субъект, уже участвующий в 1 эксперименте, получит `default` при запросе к любому другому.

> **Примечание:** cooling period и max active experiments проверяются **независимо**. Если cooling period = 0 дней, но лимит = 1, субъект всё равно не попадёт во второй эксперимент.