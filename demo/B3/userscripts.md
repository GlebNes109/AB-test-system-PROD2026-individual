# B3. Эксперименты: жизненный цикл и ревью — сценарии проверки

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
# 2. Сгенерировать тестовые данные (запуск из /demo/B3/ перейдите в эту директорию если выполняете в терминале вручную)
pip install requests
python data_generator.py
```

```bash
# 3. Задать BASE_URL (по умолчанию localhost, замените на адрес деплоя)
export BASE_URL="http://localhost"
```

После запуска генератора будут созданы 5 пользователей, 5 feature flag и 5 экспериментов в разных статусах.

> **Важно:** ID экспериментов генерируются на сервере. Генератор выведет их в консоль. Подставьте нужный `exp_id` в команды ниже.

Для выполнения сложных проверок можно делать запросы в [сваггере]($BASE_URL/docs), там же есть спецификация API и описание всех доступных эндпоинтов системы.

### Получение JWT-токенов

Проверка этих сценариев требует проверки ролей пользователей. Для выполнения запросов нужны токены. Выполните скрипт:

```bash
# Токен experimenter
EXPERIMENTER_TOKEN=$(curl -s -X POST ${BASE_URL}/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "b3_experimenter@demo.com", "password": "Demo1234!x"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

# Токен approver_alpha
APPROVER_ALPHA_TOKEN=$(curl -s -X POST ${BASE_URL}/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "b3_approver_alpha@demo.com", "password": "Demo1234!x"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

# Токен approver_beta
APPROVER_BETA_TOKEN=$(curl -s -X POST ${BASE_URL}/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "b3_approver_beta@demo.com", "password": "Demo1234!x"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

# Токен approver_outsider (APPROVER, но НЕ в approve group)
APPROVER_OUTSIDER_TOKEN=$(curl -s -X POST ${BASE_URL}/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "b3_approver_outsider@demo.com", "password": "Demo1234!x"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

# Токен viewer
VIEWER_TOKEN=$(curl -s -X POST ${BASE_URL}/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "b3_viewer@demo.com", "password": "Demo1234!x"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

echo "EXPERIMENTER_TOKEN=$EXPERIMENTER_TOKEN"
echo "APPROVER_ALPHA_TOKEN=$APPROVER_ALPHA_TOKEN"
echo "APPROVER_BETA_TOKEN=$APPROVER_BETA_TOKEN"
echo "APPROVER_OUTSIDER_TOKEN=$APPROVER_OUTSIDER_TOKEN"
echo "VIEWER_TOKEN=$VIEWER_TOKEN"
```

---

## B3-1. Переход `DRAFT → REVIEW` (submit)

**Критерий:** система поддерживает переход `draft → in_review`.

Эксперимент `b3_lifecycle` создан в статусе `DRAFT`. Подставьте его `exp_id` из вывода генератора.

### Запрос

```bash
# Подставьте exp_id из вывода генератора (эксперимент b3_lifecycle). 
# Токен должен подставиться автоматически, если ответ 401 - подставьте его вручную из вывода предыдущего скрипта
EXP_LIFECYCLE="<exp_id>"

curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_LIFECYCLE}/submit" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -m json.tool
```

### Ожидаемый ответ

```json
{
    "id": "<exp_id>",
    "status": "review",
    ...
}
```

**Что проверить:**
- `status` = `"review"` — эксперимент перешёл из DRAFT в REVIEW
- Запрос выполнен от лица EXPERIMENTER (владельца эксперимента)

### Подтверждение: GET эксперимента

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_LIFECYCLE}" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -m json.tool
```

В ответе `status` = `"review"`.

---

## B3-2. Переход `REVIEW → APPROVED` при соблюдении условий

**Критерий:** при выполнении условий (min_approvals=2) статус становится `approved`.

Эксперимент `b3_approval` находится в статусе `REVIEW`. У experimenter-а настроен approver group с `min_approvals=2` (два аппрувера: approver_alpha и approver_beta).

### Шаг 1: Первое одобрение (approver_alpha)

```bash
EXP_APPROVAL="<exp_id>"

curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_APPROVAL}/review" \
  -H "Authorization: Bearer $APPROVER_ALPHA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision": "ACCEPT", "comment": "Выглядит хорошо, одобряю — Alpha"}' \
  | python3 -m json.tool
```

**Ожидаемый результат:** ревью принято, но эксперимент ещё в `"review"` (не хватает одного одобрения).

### Проверка: статус после первого одобрения

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_APPROVAL}" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'status: {d[\"status\"]}')"
```

Ожидается: `status: review` -- ещё не approved, нужно второе одобрение.

### Шаг 2: Второе одобрение (approver_beta)

```bash
curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_APPROVAL}/review" \
  -H "Authorization: Bearer $APPROVER_BETA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision": "ACCEPT", "comment": "Подтверждаю, всё корректно — Beta"}' \
  | python3 -m json.tool
```

### Проверка: статус после второго одобрения

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_APPROVAL}" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'status: {d[\"status\"]}')"
```

**Ожидаем:** `status: approved` — оба одобрения получены, порог `min_approvals=2` достигнут.

---

## B3-3. Блокировка запуска без достаточного числа одобрений

**Критерий:** до порога одобрений запуск блокируется.

Эксперимент `b3_block_start` находится в статусе `REVIEW` — ни одного одобрения ещё нет.

### Попытка запуска (должна быть отклонена)

```bash
EXP_BLOCK_START="<exp_id>"

curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_BLOCK_START}/start" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -m json.tool
```

### Ожидаемый ответ

```json
{
    "code": "CONFLICT",
    "message": "..."
}
```

**Что проверить:**
- HTTP статус **409** (ошибка перехода)
- Эксперимент остался в `"review"`, не перешёл в `"running"`
- Система не позволяет запустить эксперимент без прохождения через APPROVED

### Подтверждение: статус не изменился

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_BLOCK_START}" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'status: {d[\"status\"]}')"
```

Ожидается: `status: review` - запуск заблокирован.

---

## B3-4. Блокировка недопустимых переходов статусов

**Критерий:** запрещённые переходы не выполняются.

Эксперимент `b3_bad_transition` находится в статусе `DRAFT`. Попробуем выполнить запрещённые переходы.

### 4a. DRAFT → RUNNING (запрещено, нужно пройти через REVIEW → APPROVED)

```bash
EXP_BAD_TRANSITION="<exp_id>"

curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_BAD_TRANSITION}/start" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -m json.tool
```

**Ожидаемый ответ:** ошибка (409 или 400). Эксперимент нельзя запустить из DRAFT.

### 4b. DRAFT → PAUSED (запрещено)

```bash
curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_BAD_TRANSITION}/pause" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -m json.tool
```

**Ожидаемый ответ:** ошибка. Пауза доступна только из RUNNING.

### 4c. DRAFT → FINISHED (запрещено)

```bash
curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_BAD_TRANSITION}/finish" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -m json.tool
```

**Ожидаемый ответ:** ошибка. Завершить можно только RUNNING или PAUSED.

### 4d. DRAFT → ARCHIVED (запрещено)

```bash
curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_BAD_TRANSITION}/archive" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -m json.tool
```

**Ожидаемый ответ:** ошибка. Архивировать можно только FINISHED.

### Подтверждение: статус не изменился

```bash
curl -s "${BASE_URL}/api/v1/experiments/${EXP_BAD_TRANSITION}" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'status: {d[\"status\"]}')"
```

**Ожидаем:** `status: draft` — ни один запрещённый переход не сработал.

REQUEST_IMPROVEMENTS на ревью возвращает в статус DRAFT, REJECT - в REJECTED

**Допустимые переходы (state machine):**
```
DRAFT → REVIEW → APPROVED → RUNNING → PAUSED ↔ RUNNING
                                      ↓
                                   FINISHED → ARCHIVED
REVIEW → REJECTED → DRAFT (через REQUEST_IMPROVEMENTS или REJECT)
```

---

## B3-5. Политика ревью применяется к конкретным ролям/группам

**Критерий:** одобрять могут только назначенные роли/пользователи.

Эксперимент `b3_role_policy` находится в `REVIEW`. Проверим, что:
- VIEWER не может оставить ревью
- EXPERIMENTER (автор) не может сам себя одобрить
- APPROVER **вне** approve group не может оставить ревью
- Только APPROVER **из** approve group может оставить ревью

### 5a. VIEWER пытается оставить ревью (запрещено)

```bash
EXP_ROLE_POLICY="<exp_id>"

curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_ROLE_POLICY}/review" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision": "ACCEPT", "comment": "Попытка одобрить от VIEWER"}' \
  | python3 -m json.tool
```

**Ожидаемый ответ:** ошибка **403** (Forbidden). Роль VIEWER не имеет права проводить ревью.

### 5b. EXPERIMENTER (автор) пытается одобрить свой эксперимент (запрещено)

```bash
curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_ROLE_POLICY}/review" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision": "ACCEPT", "comment": "Попытка самоодобрения"}' \
  | python3 -m json.tool
```

**Ожидаемый ответ:** ошибка **403** (Forbidden). Автор не может одобрить собственный эксперимент.

### 5c. APPROVER вне approve group пытается оставить ревью (запрещено)

Пользователь `b3_approver_outsider` имеет роль APPROVER, но **не входит** в approve group для `b3_experimenter`.

```bash
curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_ROLE_POLICY}/review" \
  -H "Authorization: Bearer $APPROVER_OUTSIDER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision": "ACCEPT", "comment": "Попытка одобрить от аппрувера вне группы"}' \
  | python3 -m json.tool
```

**Ожидаемый ответ:** ошибка **403** (Forbidden). Несмотря на роль APPROVER, этот пользователь не назначен в approve group экспериментатора.

### 5d. APPROVER из группы одобряет (разрешено)

```bash
curl -s -X POST "${BASE_URL}/api/v1/experiments/${EXP_ROLE_POLICY}/review" \
  -H "Authorization: Bearer $APPROVER_ALPHA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision": "ACCEPT", "comment": "Одобрено назначенным аппрувером Alpha"}' \
  | python3 -m json.tool
```

**Ожидаемый ответ:** успех (200/201). Ревью принято от назначенного аппрувера.

