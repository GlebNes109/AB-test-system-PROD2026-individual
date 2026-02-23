# B6. Отчёты и фиксация решений — сценарии проверки

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
# 2. Сгенерировать тестовые данные (запуск из /demo/B6/)
pip install requests
python data_generator.py
```

```bash
# 3. Задать BASE_URL (по умолчанию localhost, замените на адрес деплоя)
export BASE_URL="http://localhost"
```

## Что создаёт генератор

### Эксперименты

| Эксперимент | Флаг | Метрики | Назначение |
|-------------|------|---------|------------|
| EXP_REPORTS | `b6_reports` | `b6_views_count` (PRIMARY), `b6_clicks_count` (SECONDARY), `b6_conversion` (SECONDARY), `b6_avg_revenue` (SECONDARY) | Проверка отчётов (B6-1, B6-2, B6-3) |
| EXP_FINISH | `b6_finish` | `b6_views_count` (PRIMARY) | Проверка фиксации решения (B6-4, B6-5) |

Оба эксперимента в статусе **RUNNING**, аудитория 100%, 2 варианта (50/50).

### Метрики
| Ключ | Формула | Роль |
|------|---------|------|
| `b6_views_count` | COUNT b6_page_view | PRIMARY |
| `b6_clicks_count` | COUNT b6_click | SECONDARY |
| `b6_conversion` | COUNT b6_purchase / COUNT b6_click | SECONDARY |
| `b6_avg_revenue` | AVG b6_purchase.amount | SECONDARY (payload-зависимая) |

### Предзагруженные события
Генератор создаёт 20 decisions и отправляет события:
- ~20 `b6_page_view` (все субъекты с decision)
- ~14 `b6_click` (70% субъектов)
- ~6 `b6_purchase` (40% кликнувших)

Данные распределяются по обоим вариантам, поэтому конверсия видна и в control, и в treatment.

> **Важно:** `EXP_REPORTS_ID` и `EXP_FINISH_ID` — подставьте из вывода генератора.

Для выполнения сложных проверок можно делать запросы в [сваггере]($BASE_URL/docs), там же есть спецификация API и описание всех доступных эндпоинтов системы.

### Переменные для сценариев

```bash
# Подставьте из вывода генератора:
EXP_REPORTS_ID="<id EXP_REPORTS из вывода>"
EXP_FINISH_ID="<id EXP_FINISH из вывода>"
```

### Получение JWT-токена

```bash
EXPERIMENTER_TOKEN=$(curl -s -X POST ${BASE_URL}/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "b6_experimenter@demo.com", "password": "Demo1234!x"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

echo "EXPERIMENTER_TOKEN=$EXPERIMENTER_TOKEN"
```

> **Примечание об отчётах:** метрики считаются по материализованному представлению (MV), которое обновляется каждые несколько секунд (`mv_refresh_interval_seconds`). После генерации данных подождите ~5 секунд перед запросом отчёта.

---

---
### Чтобы отчёты были интереснее, можно сгенерировать данные в эмуляторе

Конфигурация для эмулятора чтобы сделать большой объем данных и посмотреть отчет по таймсериям (метрики на промежутках времени)


```json
{
  "scenario_name": "B6: reports demo (b6_reports)",
  "subjects_count": 200,
  "use_real_time": true,
  "experiment": {
    "feature_flag_key": "b6_reports",
    "time_delay_seconds": 2,
    "time_variation": 1,
    "variants": [
      {
        "feature_flag_value": "old_design",
        "events": [
          {"event_type": "b6_page_view", "time_delay_seconds": 0, "time_variation": 0, "probability": 1.0},
          {"event_type": "b6_click",     "time_delay_seconds": 1, "time_variation": 0, "probability": 0.6,
           "payload": {"element": "buy-btn"}},
          {"event_type": "b6_purchase",  "time_delay_seconds": 2, "time_variation": 1, "probability": 0.3,
           "payload": {"amount": 79.90}}
        ]
      },
      {
        "feature_flag_value": "new_design",
        "events": [
          {"event_type": "b6_page_view", "time_delay_seconds": 0, "time_variation": 0, "probability": 1.0},
          {"event_type": "b6_click",     "time_delay_seconds": 1, "time_variation": 0, "probability": 0.8,
           "payload": {"element": "buy-btn"}},
          {"event_type": "b6_purchase",  "time_delay_seconds": 2, "time_variation": 1, "probability": 0.5,
           "payload": {"amount": 129.90}}
        ]
      }
    ]
  }
}
```

> Эмулятор поддерживает поле `payload` в конфиге событий — оно передаётся как есть в AB-платформу. В этом конфиге control получает средний чек 79.90, treatment - 129.90. Метрика `b6_avg_revenue` (AVG по `amount`) покажет разницу среднего чека между вариантами.
>
> **Нюанс:** `b6_purchase` это зависимое событие (`requires_event_type: b6_click`). Если клик не пришёл (probability < 1), покупка уйдёт в `PENDING`. Для control: 60% получат клик, из них 30% покупку. Для treatment: 80% клик, 50% покупка. В целом это нормальный сценарий, он повторяет реальную систему, потому что с внешней системы могут приходить не очень правильные данные (действие без экспозиции)

Запуск:
1. `POST ${BASE_URL}/emulator/scenarios` с JSON выше
2. `POST ${BASE_URL}/emulator/scenarios/{id}/run`
3. Подождите несколько минут
4. `GET ${BASE_URL}/api/v1/experiments/${EXP_REPORTS_ID}/reports` -- отчёт с большим количеством данных
5. `GET ${BASE_URL}/api/v1/experiments/${EXP_REPORTS_ID}/reports/timeseries?granularity=minute` -- динамика по времени (гранулярность может быть задана в минутах, часах, днях)



## B6-1. Фильтр отчёта по периоду

**Критерий:** можно задать окно времени, и отчёт перестраивается.

Эндпоинт `GET /api/v1/experiments/{id}/reports` принимает query-параметры `date_from` и `date_to`. Без них автоматически берется период от `started_at` до текущего момента.

### 1a. Отчёт без фильтра (весь период)

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_REPORTS_ID}/reports" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Period: {data['date_from']} — {data['date_to']}\")
print(f\"Total subjects: {data['total_subjects']}\")
for v in data['variants']:
    print(f\"  {v['variant_name']} ({v['variant_value']}): {v['subject_count']} subjects\")
    for m in v['metrics']:
        print(f\"    {m['metric_key']}: {m['value']}\")
print('Total metrics:')
for m in data['total_metrics']:
    print(f\"  {m['metric_key']}: {m['value']}\")
"
```

### 1b. Отчёт с узким периодом (далёкое прошлое — данных нет)

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_REPORTS_ID}/reports?date_from=2020-01-01T00:00:00Z&date_to=2020-01-02T00:00:00Z" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Period: {data['date_from']} — {data['date_to']}\")
print(f\"Total subjects: {data['total_subjects']}\")
for v in data['variants']:
    print(f\"  {v['variant_name']}: {v['subject_count']} subjects\")
    for m in v['metrics']:
        print(f\"    {m['metric_key']}: {m['value']}\")
"
```

### Ожидаемый результат

- В 1a: `total_subjects > 0`, метрики содержат значения
- В 1b: `total_subjects = 0`, метрики `= 0` или `null` (период не содержит событий)
- В обоих случаях: `date_from` и `date_to` в ответе соответствуют запрошенным

**Что проверить:**
- Отчёт принимает `date_from` / `date_to`
- Разные периоды дают разные результаты
- Без параметров период = `started_at..now`

---

## B6-2. Отчёт в разрезе вариантов

**Критерий:** для каждого варианта доступны отдельные показатели.

### Запрос

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_REPORTS_ID}/reports" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Variants count: {len(data['variants'])}\")
for v in data['variants']:
    print(f\"\n--- {v['variant_name']} (value={v['variant_value']}, is_control={v['is_control']}) ---\")
    print(f\"  subject_count: {v['subject_count']}\")
    for m in v['metrics']:
        print(f\"  {m['metric_key']}: {m['value']}\")
"
```

### Ожидаемый результат

```
Variants count: 2

--- control (value=old_design, is_control=True) ---
  subject_count: <N>
  b6_views_count: <val>
  b6_clicks_count: <val>
  b6_conversion: <val>

--- treatment (value=new_design, is_control=False) ---
  subject_count: <N>
  b6_views_count: <val>
  b6_clicks_count: <val>
  b6_conversion: <val>
```

**Что проверить:**
- Массив `variants` содержит 2 записи (control и treatment)
- У каждого варианта свой `variant_name`, `variant_value`, `is_control`
- `subject_count` показывает количество субъектов в каждом варианте
- Метрики рассчитаны **отдельно** для каждого варианта
- Также есть `total_metrics` — общий агрегат по всем вариантам

---

## B6-3. Все выбранные метрики в отчёте

**Критерий:** в отчёте отображаются метрики из конфигурации эксперимента.

### Шаг 1: Проверить конфигурацию метрик эксперимента

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_REPORTS_ID}" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('Metrics in experiment config:')
for m in data['metrics']:
    print(f\"  {m['metric_key']} ({m['type']})\")
"
```

### Шаг 2: Проверить метрики в отчёте

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_REPORTS_ID}/reports" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
variant = data['variants'][0]
print(f\"Metrics in report (variant={variant['variant_name']}):\" )
for m in variant['metrics']:
    print(f\"  {m['metric_key']} = {m['value']}\")
"
```

### Ожидаемый результат

Конфигурация:
```
Metrics in experiment config:
  b6_views_count (PRIMARY)
  b6_clicks_count (SECONDARY)
  b6_conversion (SECONDARY)
```

Отчёт:
```
Metrics in report (variant=control):
  b6_views_count = <val>
  b6_clicks_count = <val>
  b6_conversion = <val>
```

**Что проверить:**
- Все 3 метрики из конфигурации эксперимента (PRIMARY + SECONDARY) присутствуют в отчёте
- Ключи метрик совпадают: `b6_views_count`, `b6_clicks_count`, `b6_conversion`
- GUARDRAIL-метрики (если были бы) не попадают в отчёт — для них отдельный эндпоинт `guardrail-triggers`

---

## B6-4. Фиксация исхода эксперимента

**Критерий:** исход (`ROLLOUT` / `ROLLBACK` / `NO_EFFECT`) можно выбрать и сохранить.

### Запрос: завершение с результатом ROLLOUT

```bash
curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_FINISH_ID}/finish" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "result": "ROLLOUT",
    "result_description": "Тестовый вариант показал рост конверсии на 15%, раскатываем на всех."
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Status:             {data['status']}\")
print(f\"Result:             {data.get('result')}\")
print(f\"Result description: {data.get('result_description')}\")
"
```

### Ожидаемый результат

```
Status:             finished
Result:             ROLLOUT
Result description: Тестовый вариант показал рост конверсии на 15%, раскатываем на всех.
```

### Проверка: GET эксперимента

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_FINISH_ID}" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Status:             {data['status']}\")
print(f\"Result:             {data.get('result')}\")
print(f\"Result description: {data.get('result_description')}\")
"
```

**Что проверить:**
- `status` = `finished`
- `result` = `ROLLOUT` — исход зафиксирован
- `result_description` содержит обоснование
- Допустимые значения `result`: `ROLLOUT`, `ROLLBACK`, `NO_EFFECT`

### Доступные значения result

| Значение | Описание |
|----------|----------|
| `ROLLOUT` | Раскатка: тестовый вариант выигрывает, раскатываем на всех |
| `ROLLBACK` | Откат: тестовый вариант хуже контроля, откатываем |
| `NO_EFFECT` | Нет эффекта: значимой разницы не обнаружено |

---

## B6-5. Обоснование решения обязательно

**Критерий:** к решению сохраняется комментарий/обоснование; без него сохранить нельзя.

> Для проверки этого сценария нужен ещё один RUNNING-эксперимент. Можно использовать EXP_REPORTS (он ещё RUNNING) или создать новый.

### 5a. Попытка завершить без обоснования

```bash
curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_REPORTS_ID}/finish" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "result": "NO_EFFECT"
  }' | python3 -m json.tool
```

### Ожидаемый результат

```json
{
    "detail": [
        {
            "type": "missing",
            "loc": ["body", "result_description"],
            "msg": "Field required",
            ...
        }
    ]
}
```

HTTP статус **422** — поле `result_description` обязательное, без него нельзя зафиксировать решение.

### 5b. Завершение с обоснованием

```bash
curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_REPORTS_ID}/finish" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "result": "NO_EFFECT",
    "result_description": "Разница между вариантами не достигла статистической значимости (p > 0.05). Рекомендуем продлить тест или увеличить выборку."
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Status:             {data['status']}\")
print(f\"Result:             {data.get('result')}\")
print(f\"Result description: {data.get('result_description')}\")
"
```

### Ожидаемый результат

```
Status:             finished
Result:             NO_EFFECT
Result description: Разница между вариантами не достигла статистической значимости (p > 0.05). Рекомендуем продлить тест или увеличить выборку.
```