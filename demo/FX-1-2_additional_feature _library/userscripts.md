# FX-1-2 Learnings Library — Сценарии проверки тестовых данных

> Предусловие: запущен `docker compose up -d`, выполнен `seed_data.py`.

Базовый URL: `http://localhost/api/v1`

---

## 0. Авторизация

```bash
# Получить токен (experimenter)
TOKEN=$(curl -s -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ll_experimenter@demo.com","password":"Demo1234!x"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

echo $TOKEN
```

Все последующие запросы используют заголовок:
```
Authorization: Bearer $TOKEN
```

---

## 1. Список всех learnings (пагинация)

```bash
# Первая страница (по умолчанию size=20)
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings" | python3 -m json.tool
```

Ожидаемый результат: `total = 8`, массив `items` содержит 8 learnings, отсортированных по `created_at` DESC.

```bash
# Пагинация: 3 записи на страницу
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?page=0&size=3" | python3 -m json.tool

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?page=1&size=3" | python3 -m json.tool
```

---

## 2. Полнотекстовый поиск (`q`)

```bash
# Поиск по гипотезе / заметкам — слово "конверсия" (по-русски конверсия можно написать в swagger е)
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?q=%D0%BA%D0%BE%D0%BD%D0%B2%D0%B5%D1%80%D1%81%D0%B8%D1%8F" \
  | python3 -m json.tool
```

Ожидаемый результат: результаты ранжированы по релевантности (`ts_rank`).

```bash
# Поиск по слову "push"
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?q=push" | python3 -m json.tool
```

Ожидаемый результат: learning EXP_6 (push-уведомления).

```bash
# Поиск по имени эксперимента — "чекаут"
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?q=%D1%87%D0%B5%D0%BA%D0%B0%D1%83%D1%82" \
  | python3 -m json.tool
```

Ожидаемый результат: learnings для EXP_1, EXP_2, EXP_8 (связаны с чекаутом). Поиск работает и по названию эксперимента.

---

## 3. Фильтрация по полям

### 3.1 По feature flag

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?feature_flag_key=ll_checkout_flow" \
  | python3 -m json.tool
```

Ожидаемый результат: EXP_1 и EXP_8 (оба привязаны к флагу `ll_checkout_flow`).

### 3.2 По результату

```bash
# Только ROLLOUT
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?result=ROLLOUT" | python3 -m json.tool

# Только ROLLBACK
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?result=ROLLBACK" | python3 -m json.tool
```

Ожидаемый результат ROLLOUT: EXP_1, EXP_3, EXP_4, EXP_6, EXP_7 (5 шт.).
Ожидаемый результат ROLLBACK: EXP_5 (онбординг), EXP_8 (промокод) (2 шт.).

### 3.3 По тегам

```bash
# Learnings с тегом "checkout"
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?tags=checkout" | python3 -m json.tool

# Learnings с тегами "ml" И "relevance" одновременно
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?tags=ml&tags=relevance" | python3 -m json.tool
```

Ожидаемый результат `tags=checkout`: EXP_1, EXP_2, EXP_8 (3 шт.).
Ожидаемый результат `tags=ml&tags=relevance`: только EXP_3 (поиск ML-ранжирование).

### 3.4 По платформе

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?platform=ios" | python3 -m json.tool
```

Ожидаемый результат: только EXP_5 (онбординг, ios).

### 3.5 По метрике

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?primary_metric_key=ll_clicks" | python3 -m json.tool
```

Ожидаемый результат: EXP_3, EXP_4, EXP_7 (3 шт., все с PRIMARY метрикой ll_clicks).

### 3.6 Комбинированный фильтр + поиск

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?q=%D0%BF%D0%BE%D0%B8%D1%81%D0%BA&result=ROLLOUT&tags=search" \
  | python3 -m json.tool
```

Ожидаемый результат: EXP_3 и EXP_4 (поисковые эксперименты с ROLLOUT).

---

## 4. Получение learning по ID

```bash
# Подставьте реальный learning_id из вывода seed_data.py или из списка
LEARNING_ID="<id из шага 1>"

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings/$LEARNING_ID" | python3 -m json.tool
```

Ожидаемый результат: полный объект learning с полями `experiment_name` и `feature_flag_key`.

---

## 5. Обновление learning (PATCH)

```bash
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "http://localhost/api/v1/learnings/$LEARNING_ID" \
  -d '{"notes":"Обновлённые заметки после дополнительного анализа","tags":["checkout","conversion","updated"]}' \
  | python3 -m json.tool
```

Ожидаемый результат: `updated_at` изменился, `notes` и `tags` обновились.

---

## 6. Похожие learnings (`/similar/{experiment_id}`)

### 6.1 Похожие для чекаут-эксперимента (EXP_1)

```bash
EXP_1_ID="<experiment_id EXP_1>"

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings/similar/$EXP_1_ID" | python3 -m json.tool
```

Ожидаемый результат: в выдаче EXP_8 (тот же флаг `ll_checkout_flow` — `same_feature_flag`), EXP_2 (та же метрика `ll_conversion` — `same_primary_metric`), и другие с общими тегами (`checkout`, `conversion`, `mobile`).

Критерии сходства (`similarity_reason`):
- `same_feature_flag` — тот же feature flag (вес 3)
- `same_primary_metric` — та же основная метрика (вес 2)
- `common_tags: ...` — общие теги (вес 1)

### 6.2 Похожие для поискового эксперимента (EXP_3)

```bash
EXP_3_ID="<experiment_id EXP_3>"

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings/similar/$EXP_3_ID" | python3 -m json.tool
```

Ожидаемый результат: EXP_4 с причинами `same_primary_metric` (ll_clicks) и `common_tags: search`.
EXP_7 с причиной `common_tags: ml`.

### 6.3 Похожие для EXP_5 (онбординг)

```bash
EXP_5_ID="<experiment_id EXP_5>"

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings/similar/$EXP_5_ID" | python3 -m json.tool
```

Ожидаемый результат: EXP_6 с причинами `same_primary_metric` (ll_views), `common_tags: retention`. И другие похожие эксперименты по метрикам

---

## 7. Проверка ошибок

### 7.1 Невалидный result

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/learnings?result=INVALID" | python3 -m json.tool
```

Ожидаемый результат: HTTP 400, сообщение о допустимых значениях.

### 7.2 Learning для несуществующего эксперимента

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "http://localhost/api/v1/learnings" \
  -d '{"experiment_id":"00000000-0000-0000-0000-000000000000","hypothesis":"test","primary_metric_key":"ll_views","notes":"test"}' \
  | python3 -m json.tool
```

Ожидаемый результат: HTTP 404, эксперимент не найден.

### 7.3 Пустая гипотеза

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "http://localhost/api/v1/learnings" \
  -d '{"experiment_id":"any","hypothesis":"   ","primary_metric_key":"ll_views","notes":"test"}' \
  | python3 -m json.tool
```

Ожидаемый результат: HTTP 422, валидация — «hypothesis must not be empty».

---

## Карта тестовых данных

| # | Эксперимент | Flag | Результат | Метрика | Теги | Платформа |
|---|-------------|------|-----------|---------|------|-----------|
| 1 | Редизайн чекаута | ll_checkout_flow | ROLLOUT | ll_conversion | checkout, conversion, redesign, mobile | web |
| 2 | Автозаполнение адреса | ll_checkout_flow_v2 | NO_EFFECT | ll_conversion | checkout, conversion, autofill, address | web |
| 3 | ML-ранжирование поиска | ll_search_ranking | ROLLOUT | ll_clicks | search, ranking, ml, relevance | — |
| 4 | Подсказки в поиске | ll_search_suggest | ROLLOUT | ll_clicks | search, suggest, ux, conversion | — |
| 5 | Онбординг интерактивный | ll_onboarding | ROLLBACK | ll_views | onboarding, retention, ux, mobile | ios |
| 6 | Push 2 раза в неделю | ll_push_frequency | ROLLOUT | ll_views | push, notifications, retention, engagement | android |
| 7 | Персональные рекомендации | ll_rec_algorithm | ROLLOUT | ll_clicks | recommendations, ml, personalization, conversion | — |
| 8 | Промокод на чекауте | ll_checkout_flow | ROLLBACK | ll_avg_revenue | checkout, promo, revenue, conversion | web |


## Ограничения и упрощения (FX-2)

### Полнотекстовый поиск
* Поиск реализован через PostgreSQL `tsvector` / `tsquery` - работает для демо-объёмов, но при росте до десятков тысяч learnings будет уступать специализированным решениям (Elasticsearch, Meilisearch).
* Нет GIN-индекса на вычисляемый FTS-вектор - при каждом запросе `to_tsvector` вычисляется на лету. Для ускорения нужен функциональный индекс или хранимый столбец `tsvector`.

### N+1 при обогащении данных
* Метод `_enrich_rows` в `LearningsRepository` для каждого learning делает 2–3 дополнительных SQL-запроса (Experiment, ExperimentVersion, FeatureFlag). При 20 записях на странице это до 60 запросов. Решение - JOIN в основном запросе или batch-загрузка связанных сущностей.

### Отсутствие кэширования
* Результаты поиска и списка learnings не кэшируются. При частых одинаковых запросах (например, главная страница библиотеки) каждый раз выполняется полный SQL-запрос. Для продакшена стоит добавить кэш (Redis) с инвалидацией при создании/обновлении learning.

### Поиск похожих (`find_similar`)
* Алгоритм сходства использует простую весовую модель (feature flag = 3, metric = 2, tags overlap = 1) без нормализации. Не учитывает семантическую близость гипотез или текстов.
* Для каждого результата делается дополнительный запрос на Experiment для определения `same_feature_flag`

### Авторизация и доступ
* Создание и обновление learnings доступно ролям ADMIN и EXPERIMENTER. Нет проверки, что пользователь является владельцем эксперимента — любой EXPERIMENTER может создать learning для чужого эксперимента.
* Нет soft-delete, удаление learnings не реализовано (только создание и обновление).

### Валидация
* Теги (`tags`) принимаются как произвольный список строк без нормализации (регистр, дубли, максимальная длина). В продакшене нужен справочник тегов или хотя бы приведение к нижнему регистру.
* Поля `dashboard_link` и `ticket_link` не валидируются как URL - принимается любая строка.