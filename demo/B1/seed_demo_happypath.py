#!/usr/bin/env python3
"""
Seed script — создаёт конфигурационные данные для демо.
Генерацию decisions и events выполняет эмулятор отдельно, чтобы продемонстрировать работу внешней системы.

Что создаётся:
  - 3 пользователя (EXPERIMENTER, APPROVER, VIEWER)
  - approver group для experimenter
  - 3 типа событий: exposure, click (requires exposure), error
  - 2 feature flag: button-color, checkout-flow
  - 4 метрики: exposure_count, unique_users, click_conversion, error_rate
  - Эксперимент 1: button-color  → RUNNING  (готов к прогону эмулятора)
  - Эксперимент 2: checkout-flow → REVIEW   (ожидает одобрения)

Запуск:
    pip install requests
    python scripts/seed_demo.py
    python scripts/seed_demo.py --base-url http://localhost --admin-email admin@mail.ru --admin-password 123123123aA!

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


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Seed demo data")
    ap.add_argument("--base-url",        default="http://localhost")
    ap.add_argument("--admin-email",     default="admin@mail.ru")
    ap.add_argument("--admin-password",  default="123123123aA!")
    args = ap.parse_args()

    base = args.base_url.rstrip("/") + "/api/v1"
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"

    # ── 1. Auth ──────────────────────────────────────────────────────────────
    _step("1. Auth")
    login(s, base, args.admin_email, args.admin_password)

    # ── 2. Users ─────────────────────────────────────────────────────────────
    _step("2. Users")
    demo_password = "Demo1234!x"
    experimenter_email = "experimenter@demo.com"
    approver_email     = "approver@demo.com"
    viewer_email       = "viewer@demo.com"

    for email, role in [
        (experimenter_email, "EXPERIMENTER"),
        (approver_email,     "APPROVER"),
        (viewer_email,       "VIEWER"),
    ]:
        _ok(f"user {email} ({role})", s.post(
            f"{base}/users",
            json={"email": email, "password": demo_password, "role": role},
        ))

    experimenter_id = find_user(s, base, experimenter_email)
    approver_id     = find_user(s, base, approver_email)

    # ── 3. Approver group ────────────────────────────────────────────────────
    _step("3. Approver group")
    _ok(f"approver group для {experimenter_email}", s.put(
        f"{base}/users/{experimenter_id}/approvers",
        json={"approver_ids": [approver_id], "min_approvals": 1},
    ))

    # ── 4. Event types ───────────────────────────────────────────────────────
    _step("4. Event types")
    _ok("exposure (независимое)", s.post(f"{base}/events/types", json={
        "type":        "exposure",
        "description": "Показ элемента пользователю",
    }))
    _ok("click (requires: exposure)", s.post(f"{base}/events/types", json={
        "type":               "click",
        "description":        "Клик по элементу",
        "requires_event_type": "exposure",
    }))
    _ok("error (независимое)", s.post(f"{base}/events/types", json={
        "type":        "error",
        "description": "Ошибка при взаимодействии с элементом",
    }))

    # ── 5. Feature flags ─────────────────────────────────────────────────────
    _step("5. Feature flags")
    _ok("button-color (string, default=white)", s.post(f"{base}/feature-flags", json={
        "key":           "button-color",
        "type":          "string",
        "default_value": "white",
        "description":   "Цвет кнопки оформления заказа",
    }))
    _ok("checkout-flow (string, default=standard)", s.post(f"{base}/feature-flags", json={
        "key":           "checkout-flow",
        "type":          "string",
        "default_value": "standard",
        "description":   "Вариант флоу оформления заказа",
    }))

    # ── 6. Metrics ───────────────────────────────────────────────────────────
    _step("6. Metrics")
    _ok("exposure_count — COUNT(exposure)", s.post(f"{base}/metrics", json={
        "key":         "exposure_count",
        "name":        "Число показов",
        "description": "COUNT всех событий показа",
        "event_type":  "exposure",
        "aggregation": "COUNT",
    }))
    _ok("unique_users — COUNT_UNIQUE(exposure)", s.post(f"{base}/metrics", json={
        "key":         "unique_users",
        "name":        "Уникальные пользователи",
        "description": "Уникальные пользователи, которым показали элемент",
        "event_type":  "exposure",
        "aggregation": "COUNT_UNIQUE",
    }))
    _ok("click_conversion — COUNT(click) / COUNT(exposure)", s.post(f"{base}/metrics", json={
        "key":                      "click_conversion",
        "name":                     "Конверсия в клик",
        "description":              "Доля пользователей, кликнувших после показа",
        "event_type":               "click",
        "aggregation":              "COUNT",
        "denominator_event_type":   "exposure",
        "denominator_aggregation":  "COUNT",
    }))
    _ok("error_rate — COUNT(error) / COUNT(exposure)", s.post(f"{base}/metrics", json={
        "key":                      "error_rate",
        "name":                     "Доля ошибок",
        "description":              "Guardrail: доля ошибок на показ",
        "event_type":               "error",
        "aggregation":              "COUNT",
        "denominator_event_type":   "exposure",
        "denominator_aggregation":  "COUNT",
    }))

    # ── 7. Experiment 1: button-color → RUNNING ──────────────────────────────
    _step("7. Experiment 1: button-color  (DRAFT → REVIEW → APPROVED → RUNNING)")

    # weights должны в сумме равняться audience_percentage
    exp1 = _ok("создан (DRAFT)", s.post(f"{base}/experiments", json={
        "name":                "Тест цвета кнопки",
        "feature_flag_key":    "button-color",
        "audience_percentage": 100,
        "variants": [
            {"name": "белая",   "value": "white", "weight": 60, "is_control": True},
            {"name": "чёрная",  "value": "black", "weight": 40, "is_control": False},
        ],
        "metrics": [
            {"metric_key": "click_conversion", "type": "PRIMARY"},
            {"metric_key": "unique_users",     "type": "SECONDARY"},
            {"metric_key": "exposure_count",   "type": "SECONDARY"},
            {
                "metric_key":     "error_rate",
                "type":           "GUARDRAIL",
                "threshold":      0.3,
                "window_minutes": 60,
                "action":         "PAUSE",
            },
        ],
    }))
    exp1_id = exp1["id"]

    _ok("на ревью (→ REVIEW)", s.post(f"{base}/experiments/{exp1_id}/submit"))

    # Ревью делает admin (ADMIN-роль позволяет)
    _ok("одобрен (→ APPROVED)", s.post(
        f"{base}/experiments/{exp1_id}/review",
        json={"decision": "ACCEPT", "comment": "Автоматическое одобрение seed-скриптом."},
    ))

    _ok("запущен (→ RUNNING)", s.post(f"{base}/experiments/{exp1_id}/start"))

    # ── 8. Experiment 2: checkout-flow → REVIEW ──────────────────────────────
    _step("8. Experiment 2: checkout-flow  (DRAFT → REVIEW)")

    exp2 = _ok("создан (DRAFT)", s.post(f"{base}/experiments", json={
        "name":                "Тест флоу оформления заказа",
        "feature_flag_key":    "checkout-flow",
        "audience_percentage": 100,
        "variants": [
            {"name": "стандартный", "value": "standard", "weight": 50, "is_control": True},
            {"name": "экспресс",    "value": "express",  "weight": 50, "is_control": False},
        ],
        "metrics": [
            {"metric_key": "click_conversion", "type": "PRIMARY"},
            {"metric_key": "exposure_count",   "type": "SECONDARY"},
        ],
    }))
    exp2_id = exp2["id"]

    _ok("на ревью (→ REVIEW)", s.post(f"{base}/experiments/{exp2_id}/submit"))

    # ── Done ─────────────────────────────────────────────────────────────────
    print(f"""
✓  Seed завершён.

  Experiment 1 (RUNNING): {exp1_id}
  Experiment 2 (REVIEW):  {exp2_id}

Следующий шаг — запустить сценарий в эмуляторе:

  POST http://localhost/emulator/scenarios
  {{
    "scenario_name": "demo button-color",
    "subjects_count": 200,
    "experiment": {{
      "feature_flag_key": "button-color",
      "time_delay_seconds": 0,
      "time_variation": 0,
      "variants": [
        {{
          "feature_flag_value": "white",
          "events": [
            {{"event_type": "exposure", "time_delay_seconds": 0, "time_variation": 0, "probability": 1}},
            {{"event_type": "click",    "time_delay_seconds": 0, "time_variation": 0, "probability": 0.6}}
          ]
        }},
        {{
          "feature_flag_value": "black",
          "events": [
            {{"event_type": "exposure", "time_delay_seconds": 0, "time_variation": 0, "probability": 1}},
            {{"event_type": "click",    "time_delay_seconds": 0, "time_variation": 0, "probability": 0.8}}
          ]
        }}
      ]
    }}
  }}
""")


if __name__ == "__main__":
    main()
