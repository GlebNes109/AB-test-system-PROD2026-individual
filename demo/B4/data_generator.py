#!/usr/bin/env python3
"""
Генератор тестовых данных для проверки критериев B4 (события и атрибуция).

Создаёт:
  - 2 пользователя (EXPERIMENTER, APPROVER)
  - approver group (min_approvals=1)
  - 3 типа событий:
      b4_click       — независимое, payload_schema: {"button_id": "string"}
      b4_impression  — независимое, без payload_schema
      b4_purchase    — зависимое, requires b4_click, payload_schema: {"amount": "number", "currency": "string"}
  - 3 метрики:
      b4_click_count       — COUNT b4_click         (PRIMARY)
      b4_impression_count  — COUNT b4_impression     (SECONDARY)
      b4_purchase_count    — COUNT b4_purchase       (SECONDARY)
  - 1 feature flag: b4_checkout_flow
  - 1 эксперимент (RUNNING) на b4_checkout_flow:
      control:   "old_checkout"   (вес 50)
      treatment: "new_checkout"   (вес 50)
      метрики: b4_click_count (PRIMARY), b4_impression_count (SECONDARY), b4_purchase_count (SECONDARY)
  - 1 decision для субъекта "b4-user-alpha" (для отправки событий)

Запуск:
    pip install requests
    python demo/B4/data_generator.py

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
        json={"decision": "ACCEPT", "comment": "Seed B4."},
    ))
    _ok(f"{label}: → RUNNING", s_owner.post(f"{base}/experiments/{exp_id}/start"))
    return exp


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Seed B4 test data")
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
    experimenter_email = "b4_experimenter@demo.com"
    approver_email     = "b4_approver@demo.com"

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
    _ok("approver group для b4_experimenter", s_admin.put(
        f"{base}/users/{experimenter_id}/approvers",
        json={"approver_ids": [approver_id], "min_approvals": 1},
    ))

    # ── 4. Event types ───────────────────────────────────────────────────────
    _step("4. Event types")

    et_click = _ok("b4_click (независимое, payload: button_id:string)", s_admin.post(
        f"{base}/events/types", json={
            "type":           "b4_click",
            "description":    "Клик по элементу UI",
            "payload_schema": {"button_id": "string"},
        }))

    et_impression = _ok("b4_impression (независимое, без payload_schema)", s_admin.post(
        f"{base}/events/types", json={
            "type":        "b4_impression",
            "description": "Показ элемента (экспозиция)",
        }))

    et_purchase = _ok("b4_purchase (зависимое от b4_click, payload: amount:number, currency:string)",
        s_admin.post(f"{base}/events/types", json={
            "type":              "b4_purchase",
            "description":       "Покупка (требует предшествующий клик)",
            "requires_event_type": "b4_click",
            "payload_schema":    {"amount": "number", "currency": "string"},
        }))

    # ── 5. Metrics ───────────────────────────────────────────────────────────
    _step("5. Metrics")

    _ok("b4_click_count (COUNT b4_click)", s_admin.post(f"{base}/metrics", json={
        "key":         "b4_click_count",
        "name":        "Число кликов",
        "description": "COUNT b4_click",
        "event_type":  "b4_click",
        "aggregation": "COUNT",
    }))

    _ok("b4_impression_count (COUNT b4_impression)", s_admin.post(f"{base}/metrics", json={
        "key":         "b4_impression_count",
        "name":        "Число показов",
        "description": "COUNT b4_impression",
        "event_type":  "b4_impression",
        "aggregation": "COUNT",
    }))

    _ok("b4_purchase_count (COUNT b4_purchase)", s_admin.post(f"{base}/metrics", json={
        "key":         "b4_purchase_count",
        "name":        "Число покупок",
        "description": "COUNT b4_purchase",
        "event_type":  "b4_purchase",
        "aggregation": "COUNT",
    }))

    # ── 6. Feature flag ──────────────────────────────────────────────────────
    _step("6. Feature flag")

    _ok("b4_checkout_flow (default=legacy_checkout)", s_admin.post(f"{base}/feature-flags", json={
        "key":           "b4_checkout_flow",
        "type":          "string",
        "default_value": "legacy_checkout",
        "description":   "B4: флаг для эксперимента с чекаутом",
    }))

    # ── 7. Experiment → RUNNING ──────────────────────────────────────────────
    _step("7. Experiment → RUNNING")

    login(s_experimenter, base, experimenter_email, demo_password)
    login(s_approver, base, approver_email, demo_password)

    exp = create_experiment_and_run(s_experimenter, s_approver, base, {
        "name":                "B4: эксперимент checkout flow",
        "feature_flag_key":    "b4_checkout_flow",
        "audience_percentage": 100,
        "variants": [
            {"name": "control",   "value": "old_checkout",  "weight": 50, "is_control": True},
            {"name": "treatment", "value": "new_checkout",  "weight": 50, "is_control": False},
        ],
        "metrics": [
            {"metric_key": "b4_click_count",      "type": "PRIMARY"},
            {"metric_key": "b4_impression_count", "type": "SECONDARY"},
            {"metric_key": "b4_purchase_count",   "type": "SECONDARY"},
        ],
    }, "b4_checkout_flow")

    # ── 8. Decision для субъекта (экспозиция) ────────────────────────────────
    _step("8. Decision (exposure)")

    r = requests.post(
        f"{base}/decision",
        headers={"Content-Type": "application/json"},
        json={
            "id": "b4-user-alpha",
            "subject_attr": {},
            "flags_keys": ["b4_checkout_flow"],
        },
    )
    if r.status_code != 200:
        print(f"  ✗  decision  →  {r.status_code}: {r.text}", file=sys.stderr)
        sys.exit(1)
    decision_list = r.json()
    decision_id = decision_list[0]["id"]
    decision_value = decision_list[0]["value"]
    print(f"  ✓  decision для b4-user-alpha  [decision_id={decision_id}, value={decision_value}]")

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"""
✓  B4 seed завершён.

Эксперимент:
  id:   {exp['id']}
  name: B4: эксперимент checkout flow
  flag: b4_checkout_flow (default = "legacy_checkout")
  варианты:
    control:   "old_checkout"  (вес 50)
    treatment: "new_checkout"  (вес 50)
  метрики:
    b4_click_count       — COUNT b4_click       (PRIMARY)
    b4_impression_count  — COUNT b4_impression   (SECONDARY)
    b4_purchase_count    — COUNT b4_purchase     (SECONDARY)

Типы событий:
  b4_click       — независимое, payload_schema: {{"button_id": "string"}}
  b4_impression  — независимое, без payload_schema
  b4_purchase    — зависимое (requires b4_click), payload_schema: {{"amount": "number", "currency": "string"}}

Decision:
  decision_id: {decision_id}
  subject:     b4-user-alpha
  value:       {decision_value}

→ Используйте decision_id выше для отправки событий в сценариях.
→ См. demo/B4/userscripts.md для сценариев проверки.
""")


if __name__ == "__main__":
    main()