#!/usr/bin/env python3
"""
Seed script — создаёт конфигурационные данные для UI демо (FX-1/FX-2).
Генерацию events выполняет эмулятор отдельно.

Что создаётся:
  - 2 пользователя (EXPERIMENTER, APPROVER)
  - approver group для experimenter
  - 2 типа событий: ui_exposure, ui_click (requires ui_exposure)
    payload: {country, device}
  - 1 feature flag: ui_banner_style
  - 3 метрики: ui_exposure_count, ui_click_count, ui_click_conversion
  - 1 эксперимент (RUNNING): Тест стиля баннера

После seed'а запустите сценарий эмулятора (см. userscripts.md).

Запуск:
    pip install requests
    python "demo/FX-1-2 UI additional_feature UI/seed_data_ui.py"

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
    ap = argparse.ArgumentParser(description="Seed UI demo data (FX-1/FX-2)")
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
    experimenter_email = "ui_experimenter@demo.com"
    approver_email     = "ui_approver@demo.com"

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
    _ok("approver group для ui_experimenter", s_admin.put(
        f"{base}/users/{experimenter_id}/approvers",
        json={"approver_ids": [approver_id], "min_approvals": 1},
    ))

    # ── 4. Event types ───────────────────────────────────────────────────────
    _step("4. Event types")

    _ok("ui_exposure (payload: country, device)", s_admin.post(
        f"{base}/events/types", json={
            "type":           "ui_exposure",
            "description":    "Показ баннера пользователю",
            "payload_schema": {"country": "string", "device": "string"},
        }))

    _ok("ui_click (requires: ui_exposure, payload: country, device)", s_admin.post(
        f"{base}/events/types", json={
            "type":                "ui_click",
            "description":         "Клик по баннеру",
            "requires_event_type": "ui_exposure",
            "payload_schema":      {"country": "string", "device": "string"},
        }))

    # ── 5. Metrics ───────────────────────────────────────────────────────────
    _step("5. Metrics")

    _ok("ui_exposure_count — COUNT(ui_exposure)", s_admin.post(f"{base}/metrics", json={
        "key":         "ui_exposure_count",
        "name":        "Число показов баннера",
        "description": "COUNT ui_exposure",
        "event_type":  "ui_exposure",
        "aggregation": "COUNT",
    }))

    _ok("ui_click_count — COUNT(ui_click)", s_admin.post(f"{base}/metrics", json={
        "key":         "ui_click_count",
        "name":        "Число кликов по баннеру",
        "description": "COUNT ui_click",
        "event_type":  "ui_click",
        "aggregation": "COUNT",
    }))

    _ok("ui_click_conversion — COUNT(ui_click) / COUNT(ui_exposure)", s_admin.post(
        f"{base}/metrics", json={
            "key":                     "ui_click_conversion",
            "name":                    "Конверсия в клик",
            "description":             "COUNT ui_click / COUNT ui_exposure",
            "event_type":              "ui_click",
            "aggregation":             "COUNT",
            "denominator_event_type":  "ui_exposure",
            "denominator_aggregation": "COUNT",
        }))

    # ── 6. Feature flag ──────────────────────────────────────────────────────
    _step("6. Feature flag")

    _ok("ui_banner_style (default=classic)", s_admin.post(f"{base}/feature-flags", json={
        "key":           "ui_banner_style",
        "type":          "string",
        "default_value": "classic",
        "description":   "Стиль баннера на главной странице",
    }))

    # ── 7. Experiment → RUNNING ──────────────────────────────────────────────
    _step("7. Experiment → RUNNING")

    login(s_experimenter, base, experimenter_email, demo_password)
    login(s_approver, base, approver_email, demo_password)

    exp = _ok("создан (DRAFT)", s_experimenter.post(f"{base}/experiments", json={
        "name":                "Тест стиля баннера",
        "feature_flag_key":    "ui_banner_style",
        "audience_percentage": 100,
        "variants": [
            {"name": "classic", "value": "classic",  "weight": 50, "is_control": True},
            {"name": "modern",  "value": "modern",   "weight": 50, "is_control": False},
        ],
        "metrics": [
            {"metric_key": "ui_click_conversion", "type": "PRIMARY"},
            {"metric_key": "ui_exposure_count",   "type": "SECONDARY"},
            {"metric_key": "ui_click_count",      "type": "SECONDARY"},
        ],
    }))
    exp_id = exp["id"]

    _ok("→ REVIEW", s_experimenter.post(f"{base}/experiments/{exp_id}/submit"))
    _ok("→ APPROVED", s_approver.post(
        f"{base}/experiments/{exp_id}/review",
        json={"decision": "ACCEPT", "comment": "Seed UI demo."},
    ))
    _ok("→ RUNNING", s_experimenter.post(f"{base}/experiments/{exp_id}/start"))

    # ── Done ─────────────────────────────────────────────────────────────────
    print(f"""
✓  UI demo seed завершён.

  Experiment (RUNNING): {exp_id}
  Flag:     ui_banner_style (default = "classic")
  Варианты: classic (50%), modern (50%)
  Метрики:
    ui_click_conversion  — COUNT ui_click / COUNT ui_exposure  (PRIMARY)
    ui_exposure_count    — COUNT ui_exposure                    (SECONDARY)
    ui_click_count       — COUNT ui_click                      (SECONDARY)

  Payload-разрезы: country (RU, US), device (mobile, desktop)

→ См. "demo/FX-1-2 UI additional_feature UI/userscripts.md" для сценария эмулятора.
""")


if __name__ == "__main__":
    main()
