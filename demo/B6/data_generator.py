#!/usr/bin/env python3
"""
Генератор тестовых данных для проверки критериев B6 (отчёты и фиксация решений).

Создаёт:
  - 2 пользователя (EXPERIMENTER, APPROVER)
  - approver group (min_approvals=1)
  - 3 типа событий:
      b6_page_view  — независимое, без payload
      b6_click      — независимое, payload_schema: {"element": "string"}
      b6_purchase   — зависимое от b6_click, payload_schema: {"amount": "number"}
  - 3 метрики:
      b6_views_count    — COUNT b6_page_view       (PRIMARY)
      b6_clicks_count   — COUNT b6_click            (SECONDARY)
      b6_conversion     — COUNT b6_purchase / COUNT b6_click  (SECONDARY)
  - 2 feature flags: b6_reports, b6_finish
  - 2 эксперимента (RUNNING):
      EXP_REPORTS — для проверки отчётов (B6-1, B6-2, B6-3)
      EXP_FINISH  — для проверки фиксации решения (B6-4, B6-5)
  - 5 decisions + события для EXP_REPORTS (чтобы отчёт был непустым)

Запуск:
    pip install requests
    python demo/B6/data_generator.py

Предусловия:
    docker compose up -d
"""

import argparse
import sys
import time

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
        json={"decision": "ACCEPT", "comment": "Seed B6."},
    ))
    _ok(f"{label}: → RUNNING", s_owner.post(f"{base}/experiments/{exp_id}/start"))
    return exp


def get_decision(base: str, subject_id: str, flag_key: str) -> dict:
    r = requests.post(
        f"{base}/decision",
        headers={"Content-Type": "application/json"},
        json={"id": subject_id, "subject_attr": {}, "flags_keys": [flag_key]},
    )
    if r.status_code != 200:
        print(f"  ✗  decision ({subject_id})  →  {r.status_code}: {r.text}", file=sys.stderr)
        sys.exit(1)
    d = r.json()[0]
    print(f"  ✓  decision {subject_id}: value={d['value']}, id={d['id']}")
    return d


def send_event(base: str, decision_id: str, event_type: str, payload: dict | None = None) -> dict:
    event = {"event_type": event_type, "decision_id": decision_id}
    if payload:
        event["payload"] = payload
    r = requests.post(
        f"{base}/events/batch",
        headers={"Content-Type": "application/json"},
        json={"events": [event]},
    )
    result = r.json().get("results", [{}])[0]
    status_code = result.get("status_code", r.status_code)
    event_status = result.get("event_status", "?")
    print(f"  ✓  event {event_type} → {status_code} ({event_status})")
    return result


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Seed B6 test data")
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
    experimenter_email = "b6_experimenter@demo.com"
    approver_email     = "b6_approver@demo.com"

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
    _ok("approver group для b6_experimenter", s_admin.put(
        f"{base}/users/{experimenter_id}/approvers",
        json={"approver_ids": [approver_id], "min_approvals": 1},
    ))

    # ── 4. Event types ───────────────────────────────────────────────────────
    _step("4. Event types")

    _ok("b6_page_view (независимое, без payload)", s_admin.post(
        f"{base}/events/types", json={
            "type":        "b6_page_view",
            "description": "Просмотр страницы",
        }))

    _ok("b6_click (независимое, payload: element:string)", s_admin.post(
        f"{base}/events/types", json={
            "type":           "b6_click",
            "description":    "Клик по элементу",
            "payload_schema": {"element": "string"},
        }))

    _ok("b6_purchase (зависимое от b6_click, payload: amount:number)", s_admin.post(
        f"{base}/events/types", json={
            "type":                "b6_purchase",
            "description":         "Покупка",
            "requires_event_type": "b6_click",
            "payload_schema":      {"amount": "number"},
        }))

    # ── 5. Metrics ───────────────────────────────────────────────────────────
    _step("5. Metrics")

    _ok("b6_views_count (COUNT b6_page_view)", s_admin.post(f"{base}/metrics", json={
        "key":         "b6_views_count",
        "name":        "Число просмотров",
        "description": "COUNT b6_page_view",
        "event_type":  "b6_page_view",
        "aggregation": "COUNT",
    }))

    _ok("b6_clicks_count (COUNT b6_click)", s_admin.post(f"{base}/metrics", json={
        "key":         "b6_clicks_count",
        "name":        "Число кликов",
        "description": "COUNT b6_click",
        "event_type":  "b6_click",
        "aggregation": "COUNT",
    }))

    _ok("b6_conversion (COUNT b6_purchase / COUNT b6_click)", s_admin.post(f"{base}/metrics", json={
        "key":                     "b6_conversion",
        "name":                    "Конверсия (покупки / клики)",
        "description":             "COUNT b6_purchase / COUNT b6_click",
        "event_type":              "b6_purchase",
        "aggregation":             "COUNT",
        "denominator_event_type":  "b6_click",
        "denominator_aggregation": "COUNT",
    }))

    _ok("b6_avg_revenue (AVG b6_purchase.amount)", s_admin.post(f"{base}/metrics", json={
        "key":           "b6_avg_revenue",
        "name":          "Средний чек (amount)",
        "description":   "AVG b6_purchase.amount — зависит от payload",
        "event_type":    "b6_purchase",
        "aggregation":   "AVG",
        "payload_field": "amount",
    }))

    # ── 6. Feature flags ─────────────────────────────────────────────────────
    _step("6. Feature flags")

    _ok("b6_reports (default=old_design)", s_admin.post(f"{base}/feature-flags", json={
        "key":           "b6_reports",
        "type":          "string",
        "default_value": "old_design",
        "description":   "B6: эксперимент для проверки отчётов",
    }))

    _ok("b6_finish (default=baseline)", s_admin.post(f"{base}/feature-flags", json={
        "key":           "b6_finish",
        "type":          "string",
        "default_value": "baseline",
        "description":   "B6: эксперимент для проверки фиксации решения",
    }))

    # ── 7. Experiments → RUNNING ─────────────────────────────────────────────
    _step("7. Experiments → RUNNING")

    login(s_experimenter, base, experimenter_email, demo_password)
    login(s_approver, base, approver_email, demo_password)

    # EXP_REPORTS: для проверки отчётов
    exp_reports = create_experiment_and_run(s_experimenter, s_approver, base, {
        "name":                "B6: отчёты (views, clicks, conversion)",
        "feature_flag_key":    "b6_reports",
        "audience_percentage": 100,
        "variants": [
            {"name": "control",   "value": "old_design", "weight": 50, "is_control": True},
            {"name": "treatment", "value": "new_design", "weight": 50, "is_control": False},
        ],
        "metrics": [
            {"metric_key": "b6_views_count",  "type": "PRIMARY"},
            {"metric_key": "b6_clicks_count", "type": "SECONDARY"},
            {"metric_key": "b6_conversion",   "type": "SECONDARY"},
            {"metric_key": "b6_avg_revenue",  "type": "SECONDARY"},
        ],
    }, "EXP_REPORTS")

    # EXP_FINISH: для проверки фиксации решения
    exp_finish = create_experiment_and_run(s_experimenter, s_approver, base, {
        "name":                "B6: фиксация решения (finish)",
        "feature_flag_key":    "b6_finish",
        "audience_percentage": 100,
        "variants": [
            {"name": "control",   "value": "baseline",    "weight": 50, "is_control": True},
            {"name": "treatment", "value": "experiment_v", "weight": 50, "is_control": False},
        ],
        "metrics": [
            {"metric_key": "b6_views_count", "type": "PRIMARY"},
        ],
    }, "EXP_FINISH")

    # ── 8. Decisions + events для EXP_REPORTS ────────────────────────────────
    _step("8. Decisions + events для EXP_REPORTS")

    n_subjects = 20
    decisions = []
    for i in range(1, n_subjects + 1):
        d = get_decision(base, f"b6-user-{i:03d}", "b6_reports")
        decisions.append(d)

    _step("9. Отправка событий")

    stats = {"page_view": 0, "click": 0, "purchase": 0, "skipped": 0}

    for idx, d in enumerate(decisions):
        did = d["id"]
        if did is None:
            stats["skipped"] += 1
            print(f"  -  skip b6-user-{idx+1:03d} (default, no decision)")
            continue

        # page_view — все субъекты
        send_event(base, did, "b6_page_view")
        stats["page_view"] += 1

        # click — 70% субъектов (первые 14 из 20)
        if idx < int(n_subjects * 0.7):
            send_event(base, did, "b6_click", {"element": "buy-btn"})
            stats["click"] += 1

            # purchase — 40% кликнувших (первые ~6)
            if idx < int(n_subjects * 0.7 * 0.4):
                send_event(base, did, "b6_purchase", {"amount": round(50 + idx * 15.5, 2)})
                stats["purchase"] += 1

    print(f"\n  Итого: {stats['page_view']} page_view, {stats['click']} click, "
          f"{stats['purchase']} purchase, {stats['skipped']} skipped (default)")

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"""
✓  B6 seed завершён.

Эксперименты:
  EXP_REPORTS (для отчётов):
    id:       {exp_reports['id']}
    flag:     b6_reports (default = "old_design")
    варианты: control="old_design" (50), treatment="new_design" (50)
    метрики:
      b6_views_count  — COUNT b6_page_view       (PRIMARY)
      b6_clicks_count — COUNT b6_click            (SECONDARY)
      b6_conversion   — COUNT b6_purchase / COUNT b6_click  (SECONDARY)
      b6_avg_revenue  — AVG b6_purchase.amount    (SECONDARY, payload-зависимая)

  EXP_FINISH (для фиксации решения):
    id:       {exp_finish['id']}
    flag:     b6_finish (default = "baseline")
    варианты: control="baseline" (50), treatment="experiment_v" (50)
    метрики:
      b6_views_count  — COUNT b6_page_view       (PRIMARY)

Отправлено событий (b6-user-001..{n_subjects:03d}):
  - {stats['page_view']} page_view (все субъекты с decision)
  - {stats['click']} click (70% субъектов)
  - {stats['purchase']} purchase (40% кликнувших)

→ Подождите ~5 секунд для обновления MV, затем запрашивайте отчёты.
→ См. demo/B6/userscripts.md для сценариев проверки.
""")


if __name__ == "__main__":
    main()