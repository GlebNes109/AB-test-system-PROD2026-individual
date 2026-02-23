# B4. События и атрибуция — сценарии проверки

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
# 2. Сгенерировать тестовые данные (запуск из /demo/B4/)
pip install requests
python data_generator.py
```

```bash
# 3. Задать BASE_URL (по умолчанию localhost, замените на адрес деплоя)
export BASE_URL="http://localhost"
```

## Что создаёт генератор

### Эксперимент
- **Имя:** B4: эксперимент checkout flow
- **Флаг:** `b4_checkout_flow` (default = `"legacy_checkout"`)
- **Статус:** RUNNING
- **Варианты:**
  - `control`: `"old_checkout"` (вес 50)
  - `treatment`: `"new_checkout"` (вес 50)
- **Метрики:**
  - `b4_click_count` — COUNT по `b4_click` (PRIMARY)
  - `b4_impression_count` — COUNT по `b4_impression` (SECONDARY)
  - `b4_purchase_count` — COUNT по `b4_purchase` (SECONDARY)

### Типы событий
| Тип | Зависимость | payload_schema | Описание |
|-----|-------------|----------------|----------|
| `b4_click` | нет (независимое) | `{"button_id": "string"}` | Клик по элементу UI |
| `b4_impression` | нет (независимое) | нет | Показ элемента |
| `b4_purchase` | `requires b4_click` | `{"amount": "number", "currency": "string"}` | Покупка (требует предшествующий клик) |

### Decision
Генератор создаёт один decision для субъекта `b4-user-alpha`. `decision_id` выводится в консоль — используйте его в сценариях ниже.

> **Важно:** `decision_id` и `experiment_id` генерируются на сервере. Подставьте их из вывода генератора во все команды ниже.

Для выполнения сложных проверок можно делать запросы в [сваггере]($BASE_URL/docs), там же есть спецификация API и описание всех доступных эндпоинтов системы.


### Получение JWT-токена

Для запросов к отчётам нужен токен:

```bash
EXPERIMENTER_TOKEN=$(curl -s -X POST ${BASE_URL}/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "b4_experimenter@demo.com", "password": "Demo1234!x"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

echo "EXPERIMENTER_TOKEN=$EXPERIMENTER_TOKEN"
```

### Переменные для сценариев

```bash
# Подставьте из вывода генератора:
DECISION_ID="<decision_id из вывода>"
EXP_ID="<experiment id из вывода>"
```

### Как запрашивать отчёт

Отчёт по эксперименту: `GET /api/v1/experiments/{experiment_id}/reports`. Возвращает метрики в разрезе вариантов. Используйте эту команду в любой момент, чтобы проверить текущее состояние метрик:

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_ID}/reports" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -m json.tool
```

> **Примечание об отчетах:** метрики в отчёте считаются по материализованному представлению (MV), которое обновляется каждые 3 секунды. После отправки событий подождите ~3-5 секунд перед запросом отчёта. Убедитесь, что MV отчетов перестраивается каждые несколько секунд (mv_refresh_interval_seconds в env файле, если не передано - то 3 секунды по дефолту для демо). В скриптах для получения отчетов уже отфильтрованы все данные через python, чтобы показывались только нужные значения метрик

---

## B4-1. Валидация типов полей входящего события

**Критерий:** событие с неверным типом поля отклоняется.

Тип `b4_click` имеет `payload_schema: {"button_id": "string"}`. Отправим событие, где `button_id` — число вместо строки.

### Запрос (неверный тип поля)

```bash
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [
      {
        \"event_type\": \"b4_click\",
        \"decision_id\": \"${DECISION_ID}\",
        \"payload\": {\"button_id\": 12345}
      }
    ]
  }" | python3 -m json.tool
```

### Ожидаемый ответ

```json
{
    "results": [
        {
            "index": 0,
            "status_code": 422,
            "event_id": "...",
            "event_status": "REJECTED",
            "error": "... field 'button_id' must be string, got int ..."
        }
    ]
}
```

**Что проверить:**
- `status_code` = `422` — payload не прошёл валидацию
- `event_status` = `"REJECTED"` — событие отклонено
- `error` содержит описание ошибки типа (ожидали string, получили int)

### Контрольный запрос (валидный payload)

```bash
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [
      {
        \"event_type\": \"b4_click\",
        \"decision_id\": \"${DECISION_ID}\",
        \"payload\": {\"button_id\": \"buy-button-01\"}
      }
    ]
  }" | python3 -m json.tool
```

**Ожидаемый ответ:** `status_code` = `201`, `event_status` = `"RECEIVED"` — валидное событие принято.

---

## B4-2. Валидация обязательных полей события

**Критерий:** событие без обязательных полей отклоняется.

Тип `b4_purchase` имеет `payload_schema: {"amount": "number", "currency": "string"}`. Отправим событие без поля `currency`.

> Для B4-2 нужен **отдельный decision**, потому что на предыдущем уже был отправлен `b4_click`.

```bash
# Создаём новый decision для другого субъекта
NEW_DECISION=$(curl -s -X POST ${BASE_URL}/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "b4-user-beta",
    "subject_attr": {},
    "flags_keys": ["b4_checkout_flow"]
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

echo "NEW_DECISION=$NEW_DECISION"
```

### Запрос (отсутствует обязательное поле)

```bash
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [
      {
        \"event_type\": \"b4_purchase\",
        \"decision_id\": \"${NEW_DECISION}\",
        \"payload\": {\"amount\": 99.90}
      }
    ]
  }" | python3 -m json.tool
```

### Ожидаемый ответ

```json
{
    "results": [
        {
            "index": 0,
            "status_code": 422,
            "event_id": "...",
            "event_status": "REJECTED",
            "error": "... missing required field 'currency' ..."
        }
    ]
}
```

**Что проверить:**
- `status_code` = `422` — отсутствует обязательное поле
- `error` содержит имя пропущенного поля (`currency`)

---

## B4-3. Дедупликация дубликатов событий

**Критерий:** дубликат не меняет итоговый расчёт.

Дедупликация работает по составному ключу `(decision_id, event_type)`. Повторная отправка того же события с тем же `decision_id` и `event_type` должна быть отклонена.

### Шаг 1: Первая отправка (успех)

В B4-1 вы уже отправили `b4_click` с `DECISION_ID`. Если нет — отправьте (если уже отправляли, будет конфликт):

```bash
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [
      {
        \"event_type\": \"b4_click\",
        \"decision_id\": \"${DECISION_ID}\",
        \"payload\": {\"button_id\": \"buy-button-01\"}
      }
    ]
  }" | python3 -m json.tool
```

### Шаг 2: Повторная отправка (дубликат)

```bash
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [
      {
        \"event_type\": \"b4_click\",
        \"decision_id\": \"${DECISION_ID}\",
        \"payload\": {\"button_id\": \"buy-button-01\"}
      }
    ]
  }" | python3 -m json.tool
```

### Ожидаемый ответ (дубликат)

```json
{
    "results": [
        {
            "index": 0,
            "status_code": 409,
            "event_id": null,
            "event_status": "REJECTED",
            "error": "Duplicate event: decision_id=..., event_type=b4_click"
        }
    ]
}
```

**Что проверить:**
- `status_code` = `409` — конфликт (дубликат)
- `event_status` = `"REJECTED"` с причиной `DUPLICATE`
- Дубликат не учитывается в метриках — метрика `b4_click_count` не увеличивается даже если попытаться создать много дублей

### Проверка через отчёт

Запросите отчёт:

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_ID}/reports" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for v in data.get('variants', []):
    for m in v.get('metrics', []):
        if m['metric_key'] == 'b4_click_count':
            print(f\"variant={v['variant_name']:<12s}  b4_click_count={m['value']}\")
"
```

**Ожидаем:** `b4_click_count=1` для варианта, в который попал `b4-user-alpha`. Несмотря на дубликат, COUNT остался 1.

---

## B4-4. Связь экспозиции с `decision_id`

**Критерий:** экспозиция содержит корректный `decision_id`.

Событие `b4_impression` (показ/экспозиция) привязано к конкретному decision — решению, принятому для конкретного субъекта в эксперименте.

### Запрос

```bash
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [
      {
        \"event_type\": \"b4_impression\",
        \"decision_id\": \"${DECISION_ID}\"
      }
    ]
  }" | python3 -m json.tool
```

### Ожидаемый ответ

```json
{
    "results": [
        {
            "index": 0,
            "status_code": 201,
            "event_id": "<uuid>",
            "event_status": "RECEIVED",
            "error": null
        }
    ]
}
```

### Проверка через отчёт

Запросите отчёт, фильтруя по `b4_impression_count`:

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_ID}/reports" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for v in data.get('variants', []):
    for m in v.get('metrics', []):
        if m['metric_key'] == 'b4_impression_count':
            print(f\"variant={v['variant_name']:<12s}  b4_impression_count={m['value']}\")
"
```

**Что проверить:**
- `status_code` = `201` — событие принято
- `event_id` не null — создано событие, привязанное к `decision_id`
- В отчёте метрика `b4_impression_count` = `1` для варианта, в который попал `b4-user-alpha`

### Негативный кейс: несуществующий decision_id

```bash
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "event_type": "b4_impression",
        "decision_id": "00000000-0000-0000-0000-000000000000"
      }
    ]
  }' | python3 -m json.tool
```

**Ожидаемый ответ:** `status_code` = `404` — decision не найден, событие отклонено. Система не принимает события без валидной связи с решением.

---

## B4-5. Атрибуция конверсии только при валидной связи с экспозицией

**Критерий:** конверсия без пары «решение/экспозиция» не учитывается.

Тип `b4_purchase` настроен с `requires_event_type: "b4_click"`. Это означает, что покупка (конверсия) будет принята только если по тому же `decision_id` уже зафиксирован клик (предшествующее действие).

### 5a. Конверсия БЕЗ предшествующего клика → PENDING

Создадим новый decision для нового субъекта и сразу отправим `b4_purchase` **без** предшествующего `b4_click`:

```bash
# Новый субъект — без клика
DECISION_GAMMA=$(curl -s -X POST ${BASE_URL}/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "b4-user-gamma",
    "subject_attr": {},
    "flags_keys": ["b4_checkout_flow"]
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

echo "DECISION_GAMMA=$DECISION_GAMMA"
```

```bash
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [
      {
        \"event_type\": \"b4_purchase\",
        \"decision_id\": \"${DECISION_GAMMA}\",
        \"payload\": {\"amount\": 49.99, \"currency\": \"RUB\"}
      }
    ]
  }" | python3 -m json.tool
```

### Ожидаемый ответ

```json
{
    "results": [
        {
            "index": 0,
            "status_code": 202,
            "event_id": "...",
            "event_status": "PENDING",
            "error": null
        }
    ]
}
```

### Проверка: покупка НЕ учтена в метриках

Подождите ~5 секунд и проверьте отчёт — `b4_purchase_count` не должен увеличиться:

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_ID}/reports" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for v in data.get('variants', []):
    for m in v.get('metrics', []):
        if m['metric_key'] == 'b4_purchase_count':
            print(f\"variant={v['variant_name']:<12s}  b4_purchase_count={m['value']}\")
"
```

**Ожидаем:** `b4_purchase_count=0` (или отсутствует) — покупка в PENDING, не учтена.

**Что проверить:**
- `status_code` = `202` (Accepted, но не обработано)
- `event_status` = `"PENDING"` — конверсия ожидает предшествующий клик
- Метрика `b4_purchase_count` не изменилась, пока не придёт `b4_click`

### 5b. Отправляем предшествующий клик → конверсия промотируется

```bash
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [
      {
        \"event_type\": \"b4_click\",
        \"decision_id\": \"${DECISION_GAMMA}\",
        \"payload\": {\"button_id\": \"checkout-btn\"}
      }
    ]
  }" | python3 -m json.tool
```

**Ожидаемый ответ:** `status_code` = `201`, `event_status` = `"RECEIVED"`.

### Проверка: после клика покупка промотирована

Проверьте отчёт - теперь обе метрики должны обновиться:

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_ID}/reports" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for v in data.get('variants', []):
    print(f\"--- {v['variant_name']} ---\")
    for m in v.get('metrics', []):
        if m['metric_key'] in ('b4_click_count', 'b4_purchase_count'):
            print(f\"  {m['metric_key']}: {m['value']}\")
"
```

**Ожидаем** (для варианта, куда попал `b4-user-gamma`):
- `b4_click_count` = `1` — клик принят
- `b4_purchase_count` = `1` — покупка промотирована из PENDING в RECEIVED

Система автоматически промотировала ранее PENDING `b4_purchase` из `events_raw` в таблицу `events` (статус обновлён на RECEIVED). Покупка теперь учитывается в метриках.

### 5c. Конверсия С предшествующим кликом → сразу RECEIVED

Для `DECISION_ID` (субъект `b4-user-alpha`) мы уже отправили `b4_click` в сценарии B4-1. Теперь отправим `b4_purchase`:

```bash
curl -s -X POST ${BASE_URL}/api/v1/events/batch \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [
      {
        \"event_type\": \"b4_purchase\",
        \"decision_id\": \"${DECISION_ID}\",
        \"payload\": {\"amount\": 199.90, \"currency\": \"USD\"}
      }
    ]
  }" | python3 -m json.tool
```

### Ожидаемый ответ

```json
{
    "results": [
        {
            "index": 0,
            "status_code": 201,
            "event_id": "<uuid>",
            "event_status": "RECEIVED",
            "error": null
        }
    ]
}
```

### Проверка через отчёт

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_ID}/reports" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for v in data.get('variants', []):
    print(f\"--- {v['variant_name']} ---\")
    for m in v.get('metrics', []):
        print(f\"  {m['metric_key']}: {m['value']}\")
"
```

**Что проверить:**
- `status_code` = `201` — сразу принято (не 202)
- `event_status` = `"RECEIVED"` — конверсия атрибутирована немедленно, т.к. клик уже был
- В отчёте `b4_purchase_count` увеличился для варианта `b4-user-alpha`

