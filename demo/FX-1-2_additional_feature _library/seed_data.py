#!/usr/bin/env python3
"""
Генератор тестовых данных для Learnings Library (FX-1-2).

Создаёт:
  - 2 пользователя (EXPERIMENTER, APPROVER)
  - approver group (min_approvals=1)
  - 3 типа событий: ll_page_view, ll_click, ll_purchase
  - 5 метрик: ll_views, ll_clicks, ll_conversion, ll_avg_revenue, ll_bounce_rate
  - 6 feature flags (разные продуктовые зоны)
  - 8 экспериментов → FINISHED (с result/result_description)
  - 8 learnings с разными гипотезами, тегами, платформами, сегментами
    для демонстрации полнотекстового поиска и нахождения похожих

Запуск:
    pip install requests
    python "demo/FX-1-2 additional_feature library/seed_data.py"

Предусловия:
    docker compose up -d
"""

import argparse
import sys

import requests


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _step(title: str) -> None:
    print(f"\n[{title}]")


def _ok(label: str, r: requests.Response) -> dict:
    try:
        data = r.json()
    except Exception:
        data = {}

    if r.status_code in (200, 201, 204):
        hint = data.get("id") or data.get("key") or ""
        print(f"  ✓  {label}" + (f"  [{hint}]" if hint else ""))
        return data

    if r.status_code == 409:
        print(f"  ~  {label}  (уже существует)")
        return data

    print(f"  ✗  {label}  →  {r.status_code}: {r.text}", file=sys.stderr)
    sys.exit(1)


def login(s: requests.Session, base: str, email: str, password: str) -> dict:
    r = s.post(f"{base}/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        print(f"Ошибка входа ({email}): {r.status_code} {r.text}", file=sys.stderr)
        sys.exit(1)
    body = r.json()
    s.headers["Authorization"] = f"Bearer {body['accessToken']}"
    print(f"  ✓  logged in as {email}")
    return body["user"]


def find_user(s: requests.Session, base: str, email: str) -> str | None:
    r = s.get(f"{base}/users", params={"size": 100})
    r.raise_for_status()
    users = r.json().get("items", [])
    user = next((u for u in users if u["email"] == email), None)
    return user["id"] if user else None


def create_experiment_and_run(
    s_owner: requests.Session,
    s_reviewer: requests.Session,
    base: str,
    payload: dict,
    label: str,
) -> dict:
    """Создаёт эксперимент (owner), ревьюит (reviewer), запускает (owner)."""
    exp = _ok(f"{label}: создан (DRAFT)", s_owner.post(f"{base}/experiments", json=payload))
    exp_id = exp["id"]
    _ok(f"{label}: → REVIEW", s_owner.post(f"{base}/experiments/{exp_id}/submit"))
    _ok(f"{label}: → APPROVED", s_reviewer.post(
        f"{base}/experiments/{exp_id}/review",
        json={"decision": "ACCEPT", "comment": "Seed FX-1-2."},
    ))
    _ok(f"{label}: → RUNNING", s_owner.post(f"{base}/experiments/{exp_id}/start"))
    return exp


def finish_experiment(
    s_owner: requests.Session,
    base: str,
    exp_id: str,
    result: str,
    result_description: str,
    label: str,
) -> dict:
    """Финиширует эксперимент с результатом."""
    data = _ok(f"{label}: → FINISHED ({result})", s_owner.post(
        f"{base}/experiments/{exp_id}/finish",
        json={"result": result, "result_description": result_description},
    ))
    return data


def create_learning(
    s: requests.Session,
    base: str,
    payload: dict,
    label: str,
) -> dict:
    """Создаёт learning-запись."""
    data = _ok(f"Learning: {label}", s.post(f"{base}/learnings", json=payload))
    return data


# ---------------------------------------------------------------------------
# Данные экспериментов и learnings
# ---------------------------------------------------------------------------

EXPERIMENTS = [
    {
        "flag_key": "ll_checkout_flow",
        "flag_default": "classic",
        "flag_type": "string",
        "flag_description": "Дизайн страницы оформления заказа",
        "exp_name": "Редизайн чекаута: одностраничная форма",
        "variants": [
            {"name": "control", "value": "classic", "weight": 50, "is_control": True},
            {"name": "treatment", "value": "one_page", "weight": 50, "is_control": False},
        ],
        "metrics": [{"metric_key": "ll_conversion", "type": "PRIMARY"}],
        "result": "ROLLOUT",
        "result_description": "Конверсия выросла на 12% (p<0.01). Одностраничная форма значительно упростила процесс.",
        "learning": {
            "hypothesis": "Одностраничная форма оформления заказа снизит отток на этапе чекаута и повысит конверсию",
            "primary_metric_key": "ll_conversion",
            "tags": ["checkout", "conversion", "redesign", "mobile"],
            "platform": "web",
            "segment": "Все пользователи",
            "notes": "Одностраничная форма показала рост конверсии на 12%. Особенно сильный эффект на мобильных устройствах (+18%). Рекомендуется раскатывать.",
            "dashboard_link": "http://localhost/metabase/dashboard/1",
        },
    },
    {
        "flag_key": "ll_checkout_flow_v2",
        "flag_default": "one_page",
        "flag_type": "string",
        "flag_description": "Второй эксперимент на чекауте: автозаполнение адреса",
        "exp_name": "Чекаут: автозаполнение адреса через DaData",
        "variants": [
            {"name": "control", "value": "one_page", "weight": 50, "is_control": True},
            {"name": "treatment", "value": "autofill", "weight": 50, "is_control": False},
        ],
        "metrics": [{"metric_key": "ll_conversion", "type": "PRIMARY"}],
        "result": "NO_EFFECT",
        "result_description": "Статистически значимой разницы не обнаружено (p=0.42). Автозаполнение не повлияло на конверсию.",
        "learning": {
            "hypothesis": "Автозаполнение адреса через DaData ускорит заполнение формы и повысит конверсию чекаута",
            "primary_metric_key": "ll_conversion",
            "tags": ["checkout", "conversion", "autofill", "address"],
            "platform": "web",
            "segment": "Все пользователи",
            "notes": "Автозаполнение не повлияло на конверсию. Вероятно, большинство пользователей уже сохраняют адрес в профиле. Не рекомендуется тратить ресурсы на интеграцию.",
        },
    },
    {
        "flag_key": "ll_search_ranking",
        "flag_default": "bm25",
        "flag_type": "string",
        "flag_description": "Алгоритм ранжирования поиска",
        "exp_name": "Поиск: ML-ранжирование vs BM25",
        "variants": [
            {"name": "control", "value": "bm25", "weight": 50, "is_control": True},
            {"name": "treatment", "value": "ml_v1", "weight": 50, "is_control": False},
        ],
        "metrics": [{"metric_key": "ll_clicks", "type": "PRIMARY"}],
        "result": "ROLLOUT",
        "result_description": "CTR поиска вырос на 8% (p<0.05). ML-ранжирование лучше учитывает контекст.",
        "learning": {
            "hypothesis": "ML-модель ранжирования с учётом поведения пользователя покажет более релевантные результаты поиска",
            "primary_metric_key": "ll_clicks",
            "tags": ["search", "ranking", "ml", "relevance"],
            "platform": None,
            "segment": "Все пользователи",
            "notes": "ML-ранжирование дало +8% CTR. Модель особенно хорошо работает для длинных запросов (>3 слов). Короткие запросы почти не отличаются от BM25.",
            "ticket_link": "https://jira.example.com/SEARCH-1234",
        },
    },
    {
        "flag_key": "ll_search_suggest",
        "flag_default": "off",
        "flag_type": "string",
        "flag_description": "Подсказки в строке поиска",
        "exp_name": "Поиск: автоподсказки при наборе запроса",
        "variants": [
            {"name": "control", "value": "off", "weight": 50, "is_control": True},
            {"name": "treatment", "value": "suggest_v1", "weight": 50, "is_control": False},
        ],
        "metrics": [{"metric_key": "ll_clicks", "type": "PRIMARY"}],
        "result": "ROLLOUT",
        "result_description": "Конверсия поиска +15% (p<0.001). Пользователи быстрее находят нужный товар.",
        "learning": {
            "hypothesis": "Подсказки в поиске ускорят нахождение товара и повысят конверсию поиска",
            "primary_metric_key": "ll_clicks",
            "tags": ["search", "suggest", "ux", "conversion"],
            "platform": None,
            "segment": "Все пользователи",
            "notes": "Подсказки дали +15% конверсии поиска и -22% отказов. Сильный позитивный эффект. Раскатано на 100%.",
        },
    },
    {
        "flag_key": "ll_onboarding",
        "flag_default": "standard",
        "flag_type": "string",
        "flag_description": "Тип онбординга для новых пользователей",
        "exp_name": "Онбординг: интерактивный тур vs статичные подсказки",
        "variants": [
            {"name": "control", "value": "standard", "weight": 50, "is_control": True},
            {"name": "treatment", "value": "interactive", "weight": 50, "is_control": False},
        ],
        "metrics": [{"metric_key": "ll_views", "type": "PRIMARY"}],
        "result": "ROLLBACK",
        "result_description": "Retention D7 упал на 5% (p<0.05). Интерактивный тур раздражал пользователей.",
        "learning": {
            "hypothesis": "Интерактивный онбординг-тур повысит retention новых пользователей за счёт лучшего понимания продукта",
            "primary_metric_key": "ll_views",
            "tags": ["onboarding", "retention", "ux", "mobile"],
            "platform": "ios",
            "segment": "Новые пользователи (регистрация < 7 дней)",
            "notes": "Интерактивный тур УХУДШИЛ retention на 5%. Пользователи закрывали тур, не дочитав. Многие жаловались в отзывах. Возврат к статичным подсказкам.",
            "ticket_link": "https://jira.example.com/ONBOARD-567",
        },
    },
    {
        "flag_key": "ll_push_frequency",
        "flag_default": "daily",
        "flag_type": "string",
        "flag_description": "Частота push-уведомлений",
        "exp_name": "Push-уведомления: ежедневные vs 2 раза в неделю",
        "variants": [
            {"name": "control", "value": "daily", "weight": 50, "is_control": True},
            {"name": "treatment", "value": "twice_weekly", "weight": 50, "is_control": False},
        ],
        "metrics": [{"metric_key": "ll_views", "type": "PRIMARY"}],
        "result": "ROLLOUT",
        "result_description": "Отписки от push сократились на 30% при сохранении DAU. Менее частые push = меньше раздражения.",
        "learning": {
            "hypothesis": "Снижение частоты push-уведомлений уменьшит число отписок без потери вовлечённости",
            "primary_metric_key": "ll_views",
            "tags": ["push", "notifications", "retention", "engagement"],
            "platform": "android",
            "segment": "Пользователи с включёнными push-уведомлениями",
            "notes": "Снижение частоты push с ежедневных до 2 раз в неделю сократило отписки на 30%. DAU не изменился. Вывод: пользователи не открывали каждый push, но отписывались от раздражения.",
        },
    },
    {
        "flag_key": "ll_rec_algorithm",
        "flag_default": "collaborative",
        "flag_type": "string",
        "flag_description": "Алгоритм рекомендаций на главной",
        "exp_name": "Рекомендации: персональные vs коллаборативная фильтрация",
        "variants": [
            {"name": "control", "value": "collaborative", "weight": 50, "is_control": True},
            {"name": "treatment", "value": "personal_v2", "weight": 50, "is_control": False},
        ],
        "metrics": [{"metric_key": "ll_clicks", "type": "PRIMARY"}],
        "result": "ROLLOUT",
        "result_description": "CTR рекомендаций +22% (p<0.001). Персональный алгоритм значительно точнее.",
        "learning": {
            "hypothesis": "Персональные рекомендации на основе истории покупок покажут более высокий CTR, чем коллаборативная фильтрация",
            "primary_metric_key": "ll_clicks",
            "tags": ["recommendations", "ml", "personalization", "conversion"],
            "platform": None,
            "segment": "Пользователи с >= 3 покупками",
            "notes": "Персональный алгоритм дал +22% CTR в сегменте 3+ покупок. Для новых пользователей (без истории) разницы нет — оставляем коллаборативную фильтрацию как fallback.",
            "dashboard_link": "http://localhost/metabase/dashboard/2",
        },
    },
    {
        "flag_key": "ll_checkout_flow",
        "flag_default": "classic",
        "flag_type": "string",
        "flag_description": "Дизайн страницы оформления заказа",
        "exp_name": "Чекаут: промокод на первой странице",
        "skip_flag": True,
        "variants": [
            {"name": "control", "value": "classic", "weight": 50, "is_control": True},
            {"name": "treatment", "value": "promo_top", "weight": 50, "is_control": False},
        ],
        "metrics": [{"metric_key": "ll_avg_revenue", "type": "PRIMARY"}],
        "result": "ROLLBACK",
        "result_description": "Средний чек упал на 8% — пользователи стали активнее искать промокоды. Негативный эффект.",
        "learning": {
            "hypothesis": "Размещение поля промокода на первом экране чекаута повысит конверсию за счёт удобства",
            "primary_metric_key": "ll_avg_revenue",
            "tags": ["checkout", "promo", "revenue", "conversion"],
            "platform": "web",
            "segment": "Все пользователи",
            "notes": "Промокод на первом экране привёл к ПАДЕНИЮ среднего чека на 8%. Пользователи уходили искать промокоды в Google. Убрали поле обратно. Важный вывод: видимость промокода провоцирует 'coupon hunting'.",
        },
    },
]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Seed Learnings Library (FX-1-2) test data")
    ap.add_argument("--base-url",       default="http://localhost")
    ap.add_argument("--admin-email",    default="admin@mail.ru")
    ap.add_argument("--admin-password", default="123123123aA!")
    args = ap.parse_args()

    base = args.base_url.rstrip("/") + "/api/v1"

    s_admin = requests.Session()
    s_admin.headers["Content-Type"] = "application/json"

    s_experimenter = requests.Session()
    s_experimenter.headers["Content-Type"] = "application/json"

    s_approver = requests.Session()
    s_approver.headers["Content-Type"] = "application/json"

    # ── 1. Auth (admin) ──────────────────────────────────────────────────────
    _step("1. Auth (admin)")
    login(s_admin, base, args.admin_email, args.admin_password)

    # ── 2. Users ─────────────────────────────────────────────────────────────
    _step("2. Users")
    demo_password = "Demo1234!x"
    experimenter_email = "ll_experimenter@demo.com"
    approver_email     = "ll_approver@demo.com"

    for email, role in [
        (experimenter_email, "EXPERIMENTER"),
        (approver_email,     "APPROVER"),
    ]:
        _ok(f"user {email} ({role})", s_admin.post(
            f"{base}/users",
            json={"email": email, "password": demo_password, "role": role},
        ))

    experimenter_id = find_user(s_admin, base, experimenter_email)
    approver_id     = find_user(s_admin, base, approver_email)

    # ── 3. Approver group ────────────────────────────────────────────────────
    _step("3. Approver group")
    _ok("approver group для ll_experimenter", s_admin.put(
        f"{base}/users/{experimenter_id}/approvers",
        json={"approver_ids": [approver_id], "min_approvals": 1},
    ))

    # ── 4. Event types ───────────────────────────────────────────────────────
    _step("4. Event types")

    _ok("ll_page_view", s_admin.post(f"{base}/events/types", json={
        "type": "ll_page_view", "description": "Просмотр страницы",
    }))
    _ok("ll_click", s_admin.post(f"{base}/events/types", json={
        "type": "ll_click", "description": "Клик по элементу",
        "payload_schema": {"element": "string"},
    }))
    _ok("ll_purchase (зависит от ll_click)", s_admin.post(f"{base}/events/types", json={
        "type": "ll_purchase", "description": "Покупка",
        "payload_schema": {"amount": "number", "currency": "string"},
        "prerequisite_event_type": "ll_click",
    }))

    # ── 5. Metrics ───────────────────────────────────────────────────────────
    _step("5. Metrics")

    _ok("ll_views (COUNT ll_page_view)", s_admin.post(f"{base}/metrics", json={
        "key": "ll_views", "name": "Число просмотров",
        "description": "COUNT ll_page_view",
        "event_type": "ll_page_view", "aggregation": "COUNT",
    }))
    _ok("ll_clicks (COUNT ll_click)", s_admin.post(f"{base}/metrics", json={
        "key": "ll_clicks", "name": "Число кликов",
        "description": "COUNT ll_click",
        "event_type": "ll_click", "aggregation": "COUNT",
    }))
    _ok("ll_conversion (COUNT ll_purchase / COUNT ll_click)", s_admin.post(f"{base}/metrics", json={
        "key": "ll_conversion", "name": "Конверсия",
        "description": "COUNT ll_purchase / COUNT ll_click",
        "event_type": "ll_purchase", "aggregation": "COUNT",
        "denominator_event_type": "ll_click", "denominator_aggregation": "COUNT",
    }))
    _ok("ll_avg_revenue (AVG ll_purchase.amount)", s_admin.post(f"{base}/metrics", json={
        "key": "ll_avg_revenue", "name": "Средний чек",
        "description": "AVG ll_purchase.amount",
        "event_type": "ll_purchase", "aggregation": "AVG",
        "payload_field": "amount",
    }))
    _ok("ll_bounce_rate (COUNT ll_page_view / COUNT ll_click)", s_admin.post(f"{base}/metrics", json={
        "key": "ll_bounce_rate", "name": "Bounce rate",
        "description": "COUNT ll_page_view / COUNT ll_click",
        "event_type": "ll_page_view", "aggregation": "COUNT",
        "denominator_event_type": "ll_click", "denominator_aggregation": "COUNT",
    }))

    # ── 6. Feature flags ─────────────────────────────────────────────────────
    _step("6. Feature flags")

    created_flags = set()
    for exp_cfg in EXPERIMENTS:
        fk = exp_cfg["flag_key"]
        if fk in created_flags or exp_cfg.get("skip_flag"):
            continue
        _ok(f"{fk} (default={exp_cfg['flag_default']})", s_admin.post(
            f"{base}/feature-flags", json={
                "key": fk,
                "type": exp_cfg["flag_type"],
                "default_value": exp_cfg["flag_default"],
                "description": exp_cfg["flag_description"],
            }))
        created_flags.add(fk)

    # ── 7. Experiments → RUNNING → FINISHED + Learnings ───────────────────
    _step("7. Experiments → RUNNING → FINISHED + Learnings")

    login(s_experimenter, base, experimenter_email, demo_password)
    login(s_approver, base, approver_email, demo_password)

    results = []
    for i, exp_cfg in enumerate(EXPERIMENTS, 1):
        label = f"EXP_{i}"

        exp = create_experiment_and_run(s_experimenter, s_approver, base, {
            "name":                exp_cfg["exp_name"],
            "feature_flag_key":    exp_cfg["flag_key"],
            "audience_percentage": 100,
            "variants":            exp_cfg["variants"],
            "metrics":             exp_cfg["metrics"],
        }, label)

        finish_experiment(
            s_experimenter, base, exp["id"],
            exp_cfg["result"],
            exp_cfg["result_description"],
            label,
        )

        learning_payload = {
            "experiment_id":     exp["id"],
            **exp_cfg["learning"],
        }
        lr = create_learning(s_experimenter, base, learning_payload, exp_cfg["exp_name"])

        results.append({
            "label": label,
            "exp_id": exp["id"],
            "learning_id": lr.get("id", "?"),
            "name": exp_cfg["exp_name"],
            "flag": exp_cfg["flag_key"],
            "result": exp_cfg["result"],
            "tags": exp_cfg["learning"]["tags"],
        })

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"""
{'='*72}
✓  FX-1-2 Learnings Library seed завершён.
{'='*72}

Эксперименты и learnings:
""")

    for r in results:
        tags_str = ", ".join(r["tags"])
        print(f"""  {r['label']}: {r['name']}
    experiment_id: {r['exp_id']}
    learning_id:   {r['learning_id']}
    flag:          {r['flag']}
    result:        {r['result']}
    tags:          [{tags_str}]
""")

    print(f"""Метрики:
  ll_views        — COUNT ll_page_view             (PRIMARY)
  ll_clicks       — COUNT ll_click                 (PRIMARY)
  ll_conversion   — COUNT ll_purchase / COUNT ll_click  (PRIMARY)
  ll_avg_revenue  — AVG ll_purchase.amount         (PRIMARY)
  ll_bounce_rate  — COUNT ll_page_view / COUNT ll_click

Общие теги для проверки похожих:
  checkout:       EXP_1, EXP_2, EXP_8  (один feature flag ll_checkout_flow)
  search:         EXP_3, EXP_4
  conversion:     EXP_1, EXP_2, EXP_4, EXP_7, EXP_8
  ml:             EXP_3, EXP_7
  mobile:         EXP_1, EXP_5
  retention:      EXP_5, EXP_6

→ См. "demo/FX-1-2 additional_feature library/userscripts.md" для сценариев проверки.
""")


if __name__ == "__main__":
    main()
