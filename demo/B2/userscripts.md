# B2. Feature Flags и выдача вариантов — сценарии проверки

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
# 2. Сгенерировать тестовые данные (запуск из /demo/B2/ перейдите в эту директорию если выполняете в терминале вручную)
pip install requests
python data_generator.py
```

После запуска генератора будут созданы 4 feature flag и 3 эксперимента в статусе RUNNING. 

Для выполнения сложных проверок можно делать запросы в [сваггере](http://localhost/docs), там же есть спецификация API и описание всех доступных эндпоинтов системы


---

## B2-1. Флаг без активного эксперимента → `default`

**Критерий:** система возвращает `default_value` флага, если нет активного эксперимента.

Флаг `b2_no_experiment` создан с `default_value = "fallback_value"`, эксперимент на нём **не создан**.

### Запрос

```bash
curl -s -X POST http://localhost/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "user-001",
    "subject_attr": {},
    "flags_keys": ["b2_no_experiment"]
  }' | python3 -m json.tool
```

### Ожидаемый ответ

```json
[
  {
    "id": null,
    "created_at": "...",
    "value": "fallback_value"
  }
]
```

**Что проверить:**
- `value` = `"fallback_value"` (значение `default_value` флага)
- `id` = `null` (решение по эксперименту не создавалось)

---

## B2-2. Таргетинг: пользователь проходит / не проходит правило

**Критерий:** если пользователь не проходит правило участия (targeting_rule), возвращается `default`.

Эксперимент на флаге `b2_targeting` имеет правило `country == "RU"`.

### 2a. Субъект проходит таргетинг (`country == "RU"`)

```bash
curl -s -X POST http://localhost/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "user-ru-001",
    "subject_attr": {"country": "RU"},
    "flags_keys": ["b2_targeting"]
  }' | python3 -m json.tool
```

**Ожидаемый ответ:**

```json
[
  {
    "id": "<uuid — не null>",
    "created_at": "...",
    "value": "default_color_variant или red_variant"
  }
]
```

**Что проверить:**
- `id` ≠ `null` — пользователь попал в эксперимент. решение принято, но не сохранено, потому что пользователь вне эксперимента и события от него не интересны в системе.
- `value` — один из вариантов (`"default_color_variant"` или `"red_variant"`), а не дефолт флага. В данном случае это варианты эксперимента, default_color_variant - это контрольный вариант, главное чтобы id decision было не null - это значит что пользователь попал в эксперимент. default_color_defaultvalue - это дефолтное значение, оно не должно возвращаться.

### 2b. Субъект НЕ проходит таргетинг (`country == "US"`)

```bash
curl -s -X POST http://localhost/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "user-us-001",
    "subject_attr": {"country": "US"},
    "flags_keys": ["b2_targeting"]
  }' | python3 -m json.tool
```

**Ожидаемый ответ:**

```json
[
  {
    "id": null,
    "created_at": "...",
    "value": "default_color_defaultvalue"
  }
]
```

**Что проверяем:**
- `id` = `null` — пользователь НЕ попал в эксперимент
- `value` = `"default_color_defaultvalue"` — дефолтное значение флага

---

## B2-3. Активный эксперимент → возвращается вариант

**Критерий:** если эксперимент применим к пользователю, возвращается вариант (не default).

Эксперимент на флаге `b2_variant` — без таргетинга, 100% аудитория, два варианта: `"old_design"` (control) и `"new_design"`.

```bash
curl -s -X POST http://localhost/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "user-exp-001",
    "subject_attr": {},
    "flags_keys": ["b2_variant"]
  }' | python3 -m json.tool
```

**Ожидаемый ответ:**

```json
[
  {
    "id": "<uuid — не null>",
    "created_at": "...",
    "value": "old_design_variant или new_design_variant"
  }
]
```

**Что проверяем:**
- `id` ≠ `null` — создано решение (decision)
- `value` — один из вариантов эксперимента (`"old_design"` или `"new_design"`)

---

## B2-4. Детерминированность: повторные запросы дают тот же результат

**Критерий:** повторные запросы одного и того же субъекта при неизменной конфигурации дают одинаковый результат.

Используем тот же флаг `b2_variant`. Выполняем **тот же запрос** с тем же `id` **3 раза подряд**:

```bash
# Запрос 1
curl -s -X POST http://localhost/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "user-sticky-001",
    "subject_attr": {},
    "flags_keys": ["b2_variant"]
  }' | python3 -m json.tool

# Запрос 2 (тот же субъект)
curl -s -X POST http://localhost/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "user-sticky-001",
    "subject_attr": {},
    "flags_keys": ["b2_variant"]
  }' | python3 -m json.tool

# Запрос 3 (тот же субъект)
curl -s -X POST http://localhost/api/v1/decision \
  -H "Content-Type: application/json" \
  -d '{
    "id": "user-sticky-001",
    "subject_attr": {},
    "flags_keys": ["b2_variant"]
  }' | python3 -m json.tool
```

**Что проверяем:**
- Все 3 ответа содержат **одинаковые** `id` и `value`
- Механизм stickiness: после первого запроса решение сохраняется в БД, последующие запросы возвращают то же решение

**Ожидаемый ответ (одинаковый для всех 3 запросов):**

```json
[
  {
    "id": "<один и тот же uuid>",
    "created_at": "...",
    "value": "<одно и то же значение>"
  }
]
```

---

## B2-5. Распределение по весам

**Критерий:** фактическое распределение субъектов по вариантам близко к заданным весам.

Эксперимент на флаге `b2_weights` имеет два варианта: `control_val` (вес 30) и `treatment_val` (вес 70). Чтобы убедиться в этом, можете посмотреть на список активных экспериментов и найти там эксперимент на `b2_weights` флаге (GET api/v1/experiments с jwt токеном админа, легче всего в сваггере)

### Способ проверки

Выполнить серию запросов с разными `id` субъектов и подсчитать распределение. Для этого предлагается запустить встроенный bash + python скрипт ниже который сам все посчитает. 

Для генерации большого объема данных с задержкой вы можете использовать систему-эмулятор (например для генерации 10 тысяч пользователей чтобы посмотреть их распределение).

На процент отклонения и фактическое распредление вы можете также посмотреть в [metabase](localhost/metabase) (главное выбрать правильный id эксперимента, в этом пакете тестовых данных их 3. id генерируется на стороне сервера случайно при генерации тестовых данных, поэтому я не могу его здесь указать, к сожалению)

> **Важно:** из-за механизма охлаждения (cooling period = 1 день) повторная раздача варианта **новому** субъекту, который уже участвует в другом эксперименте, может вернуть default. Поэтому если будете тестировать вручную или своими скриптами, используйте субъектов, которые **не участвовали** в предыдущих экспериментах (уникальные id). В скрипте ниже такой проблемы нет.

```bash
for i in $(seq 1 100); do
  curl -s -X POST http://localhost/api/v1/decision \
    -H "Content-Type: application/json" \
    -d "{
      \"id\": \"weight-test-$i\",
      \"subject_attr\": {},
      \"flags_keys\": [\"b2_weights\"]
    }"
done | python3 -c "
import sys, json

results = {'control_val': 0, 'treatment_val': 0, 'other': 0}
raw = sys.stdin.read()

import re
for match in re.finditer(r'\[.*?\]', raw, re.DOTALL):
    try:
        arr = json.loads(match.group())
        val = arr[0]['value']
        if val in results:
            results[val] += 1
        else:
            results['other'] += 1
    except:
        pass

total = results['control_val'] + results['treatment_val']
if total > 0:
    print(f\"control_val  (вес 30): {results['control_val']:3d}  ({results['control_val']*100/total:.0f}%)\")
    print(f\"treatment_val (вес 70): {results['treatment_val']:3d}  ({results['treatment_val']*100/total:.0f}%)\")
    if results['other']:
        print(f\"other (default/cooldown): {results['other']}\")
"
```

**Ожидаемый результат:**
- `control_val` около 30% запросов
- `treatment_val` около 70% запросов
- Допустимое отклонение ±10% при 100 субъектах (статистическая вариация)
