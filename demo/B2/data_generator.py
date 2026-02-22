#!/usr/bin/env python3
"""
Генератор тестовых данных для проверки критериев B2 (Feature Flags и выдача вариантов).

Создаёт:
  - 3 пользователя (EXPERIMENTER, APPROVER, VIEWER)
  - approver group
  - 1 тип события (exposure) + 1 метрику (exposure_count)
  - 4 feature flag:
      b2_no_experiment    — флаг без эксперимента (B2-1)
      b2_targeting         — флаг с экспериментом + таргетинг country == "RU" (B2-2)
      b2_variant           — флаг с экспериментом, 100% аудитория, без таргетинга (B2-3, B2-4)
      b2_weights           — флаг с экспериментом, два варианта 30/70 (B2-5)
  - 3 эксперимента (RUNNING) для b2_targeting, b2_variant, b2_weights

Запуск:
    pip install requests
    python demo/B2/data_generator.py
    python demo/B2/data_generator.py --base-url http://localhost --admin-email admin@mail.ru --admin-password 123123123aA!

Предусловия:
    docker compose up -d
"""

import argparse
import sys

import requests


# ---------------------------------------------------------------------------
# helpers (копия из seed_demo.py)
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


def create_experiment_and_run(s: requests.Session, base: str, payload: dict, label: str) -> dict:
    """Создаёт эксперимент, проводит через REVIEW → APPROVED → RUNNING."""
    exp = _ok(f"{label}: создан (DRAFT)", s.post(f"{base}/experiments", json=payload))
    exp_id = exp["id"]
    _ok(f"{label}: → REVIEW", s.post(f"{base}/experiments/{exp_id}/submit"))
    _ok(f"{label}: → APPROVED", s.post(
        f"{base}/experiments/{exp_id}/review",
        json={"decision": "ACCEPT", "comment": "Seed B2."},
    ))
    _ok(f"{label}: → RUNNING", s.post(f"{base}/experiments/{exp_id}/start"))
    return exp


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Seed B2 test data")
    ap.add_argument("--base-url",       default="http://localhost")
    ap.add_argument("--admin-email",    default="admin@mail.ru")
    ap.add_argument("--admin-password", default="123123123aA!")
    args = ap.parse_args()

    base = args.base_url.rstrip("/") + "/api/v1"
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"

    # ── 1. Auth ─────────────────────────────────────────────────────────────
    _step("1. Auth (admin)")
    login(s, base, args.admin_email, args.admin_password)

    # ── 2. Users ────────────────────────────────────────────────────────────
    _step("2. Users")
    demo_password = "Demo1234!x"
    experimenter_email = "b2_experimenter@demo.com"
    approver_email     = "b2_approver@demo.com"

    for email, role in [
        (experimenter_email, "EXPERIMENTER"),
        (approver_email,     "APPROVER"),
    ]:
        _ok(f"user {email} ({role})", s.post(
            f"{base}/users",
            json={"email": email, "password": demo_password, "role": role},
        ))

    experimenter_id = find_user(s, base, experimenter_email)
    approver_id     = find_user(s, base, approver_email)

    # ── 3. Approver group ───────────────────────────────────────────────────
    _step("3. Approver group")
    _ok("approver group", s.put(
        f"{base}/users/{experimenter_id}/approvers",
        json={"approver_ids": [approver_id], "min_approvals": 1},
    ))

    # ── 4. Event type + metric (минимум для создания эксперимента) ─────────
    _step("4. Event type + metric")
    _ok("exposure", s.post(f"{base}/events/types", json={
        "type":        "exposure",
        "description": "Показ элемента",
    }))
    _ok("exposure_count", s.post(f"{base}/metrics", json={
        "key":         "exposure_count",
        "name":        "Число показов",
        "description": "COUNT exposure",
        "event_type":  "exposure",
        "aggregation": "COUNT",
    }))

    # ── 5. Feature flags ────────────────────────────────────────────────────
    _step("5. Feature flags")

    _ok("b2_no_experiment (string, default=fallback_value)", s.post(f"{base}/feature-flags", json={
        "key":           "b2_no_experiment",
        "type":          "string",
        "default_value": "fallback_value",
        "description":   "B2-1: флаг без активного эксперимента",
    }))

    _ok("b2_targeting (string, default=default_color)", s.post(f"{base}/feature-flags", json={
        "key":           "b2_targeting",
        "type":          "string",
        "default_value": "default_color_defaultvalue",
        "description":   "B2-2: флаг с таргетингом country == RU",
    }))

    _ok("b2_variant (string, default=old_design)", s.post(f"{base}/feature-flags", json={
        "key":           "b2_variant",
        "type":          "string",
        "default_value": "old_design_defaultvalue",
        "description":   "B2-3/B2-4: флаг с экспериментом без таргетинга",
    }))

    _ok("b2_weights (string, default=control_val)", s.post(f"{base}/feature-flags", json={
        "key":           "b2_weights",
        "type":          "string",
        "default_value": "control_val",
        "description":   "B2-5: флаг для проверки распределения весов",
    }))

    # ── 6. Experiments → RUNNING ────────────────────────────────────────────
    _step("6. Experiments")

    # B2-2: с таргетингом country == "RU"
    create_experiment_and_run(s, base, {
        "name":                "B2-2: таргетинг country",
        "feature_flag_key":    "b2_targeting",
        "targeting_rule":      'country == "RU"',
        "audience_percentage": 100,
        "variants": [
            {"name": "control",   "value": "default_color_variant", "weight": 50, "is_control": True},
            {"name": "treatment", "value": "red_variant",           "weight": 50, "is_control": False},
        ],
        "metrics": [{"metric_key": "exposure_count", "type": "PRIMARY"}],
    }, "b2_targeting")

    # B2-3 / B2-4: без таргетинга, 100% аудитория
    create_experiment_and_run(s, base, {
        "name":                "B2-3: вариант без таргетинга",
        "feature_flag_key":    "b2_variant",
        "audience_percentage": 100,
        "variants": [
            {"name": "control",    "value": "old_design_variant", "weight": 50, "is_control": True},
            {"name": "new_design", "value": "new_design_variant", "weight": 50, "is_control": False},
        ],
        "metrics": [{"metric_key": "exposure_count", "type": "PRIMARY"}],
    }, "b2_variant")

    # B2-5: веса 30/70
    create_experiment_and_run(s, base, {
        "name":                "B2-5: проверка весов 30/70",
        "feature_flag_key":    "b2_weights",
        "audience_percentage": 100,
        "variants": [
            {"name": "control",   "value": "control_val",   "weight": 30, "is_control": True},
            {"name": "treatment", "value": "treatment_val", "weight": 70, "is_control": False},
        ],
        "metrics": [{"metric_key": "exposure_count", "type": "PRIMARY"}],
    }, "b2_weights")

    # ── Done ────────────────────────────────────────────────────────────────
    print("""
✓  B2 seed завершён.

Созданные флаги:
  b2_no_experiment  — без эксперимента, default = "fallback_value"    (B2-1)
  b2_targeting      — эксперимент с targeting_rule country == "RU"    (B2-2)
  b2_variant        — эксперимент без таргетинга, 100% аудитория      (B2-3, B2-4)
  b2_weights        — эксперимент с весами 30/70                      (B2-5)

Далее: см. demo/B2/userscripts.md для сценариев проверки.
""")


if __name__ == "__main__":
    main()