#!/usr/bin/env python3
"""
Генератор тестовых данных для проверки критериев B5 (guardrails и cooling period).

Создаёт:
  - 2 пользователя (EXPERIMENTER, APPROVER)
  - approver group (min_approvals=1)
  - 4 типа событий:
      b5_page_view   — независимое, без payload
      b5_error       — независимое, payload_schema: {"error_code": "number"}
      b5_click       — независимое, payload_schema: {"element": "string"}
      b5_latency     — независимое, payload_schema: {"ms": "number"}
  - 4 метрики:
      b5_page_view_count  — COUNT b5_page_view       (PRIMARY для всех экспериментов)
      b5_error_rate       — COUNT b5_error / COUNT b5_page_view  (GUARDRAIL, action=PAUSE)
      b5_click_count      — COUNT b5_click            (PRIMARY)
      b5_avg_latency      — AVG b5_latency по полю ms (GUARDRAIL, action=ROLLBACK)
  - 3 feature flags: b5_guardrail_pause, b5_guardrail_rollback, b5_cooling
  - 3 эксперимента (RUNNING):
      EXP_PAUSE    — guardrail b5_error_rate с threshold=0.5, action=PAUSE, window=60 мин
      EXP_ROLLBACK — guardrail b5_avg_latency с threshold=500, action=ROLLBACK, window=60 мин
      EXP_COOLING  — для проверки cooling period и max active experiments

Запуск:
    pip install requests
    python demo/B5/data_generator.py

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
        json={"decision": "ACCEPT", "comment": "Seed B5."},
    ))
    _ok(f"{label}: → RUNNING", s_owner.post(f"{base}/experiments/{exp_id}/start"))
    return exp


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Seed B5 test data")
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
    experimenter_email = "b5_experimenter@demo.com"
    approver_email     = "b5_approver@demo.com"

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
    _ok("approver group для b5_experimenter", s_admin.put(
        f"{base}/users/{experimenter_id}/approvers",
        json={"approver_ids": [approver_id], "min_approvals": 1},
    ))

    # ── 4. Event types ───────────────────────────────────────────────────────
    _step("4. Event types")

    _ok("b5_page_view (независимое, без payload)", s_admin.post(
        f"{base}/events/types", json={
            "type":        "b5_page_view",
            "description": "Просмотр страницы",
        }))

    _ok("b5_error (независимое, payload: error_code:number)", s_admin.post(
        f"{base}/events/types", json={
            "type":           "b5_error",
            "description":    "Ошибка на клиенте",
            "payload_schema": {"error_code": "number"},
        }))

    _ok("b5_click (независимое, payload: element:string)", s_admin.post(
        f"{base}/events/types", json={
            "type":           "b5_click",
            "description":    "Клик по элементу",
            "payload_schema": {"element": "string"},
        }))

    _ok("b5_latency (независимое, payload: ms:number)", s_admin.post(
        f"{base}/events/types", json={
            "type":           "b5_latency",
            "description":    "Замер латентности страницы",
            "payload_schema": {"ms": "number"},
        }))

    # ── 5. Metrics ───────────────────────────────────────────────────────────
    _step("5. Metrics")

    _ok("b5_page_view_count (COUNT b5_page_view)", s_admin.post(f"{base}/metrics", json={
        "key":         "b5_page_view_count",
        "name":        "Число просмотров страниц",
        "description": "COUNT b5_page_view",
        "event_type":  "b5_page_view",
        "aggregation": "COUNT",
    }))

    _ok("b5_error_rate (COUNT b5_error / COUNT b5_page_view)", s_admin.post(f"{base}/metrics", json={
        "key":                     "b5_error_rate",
        "name":                    "Доля ошибок",
        "description":             "COUNT b5_error / COUNT b5_page_view",
        "event_type":              "b5_error",
        "aggregation":             "COUNT",
        "denominator_event_type":  "b5_page_view",
        "denominator_aggregation": "COUNT",
    }))

    _ok("b5_click_count (COUNT b5_click)", s_admin.post(f"{base}/metrics", json={
        "key":         "b5_click_count",
        "name":        "Число кликов",
        "description": "COUNT b5_click",
        "event_type":  "b5_click",
        "aggregation": "COUNT",
    }))

    _ok("b5_avg_latency (AVG b5_latency по полю ms)", s_admin.post(f"{base}/metrics", json={
        "key":           "b5_avg_latency",
        "name":          "Средняя латентность (ms)",
        "description":   "AVG b5_latency.ms",
        "event_type":    "b5_latency",
        "aggregation":   "AVG",
        "payload_field": "ms",
    }))

    # ── 6. Feature flags ─────────────────────────────────────────────────────
    _step("6. Feature flags")

    _ok("b5_guardrail_pause (default=old_page)", s_admin.post(f"{base}/feature-flags", json={
        "key":           "b5_guardrail_pause",
        "type":          "string",
        "default_value": "old_page",
        "description":   "B5: эксперимент с guardrail PAUSE (по error_rate)",
    }))

    _ok("b5_guardrail_rollback (default=old_layout)", s_admin.post(f"{base}/feature-flags", json={
        "key":           "b5_guardrail_rollback",
        "type":          "string",
        "default_value": "old_layout",
        "description":   "B5: эксперимент с guardrail ROLLBACK (по avg_latency)",
    }))

    _ok("b5_cooling (default=baseline)", s_admin.post(f"{base}/feature-flags", json={
        "key":           "b5_cooling",
        "type":          "string",
        "default_value": "baseline",
        "description":   "B5: эксперимент для проверки cooling period (шаг 1)",
    }))

    _ok("b5_cooling_second (default=fallback)", s_admin.post(f"{base}/feature-flags", json={
        "key":           "b5_cooling_second",
        "type":          "string",
        "default_value": "fallback",
        "description":   "B5: второй эксперимент для проверки cooling period (шаг 2)",
    }))

    # ── 7. Experiments → RUNNING ─────────────────────────────────────────────
    _step("7. Experiments → RUNNING")

    login(s_experimenter, base, experimenter_email, demo_password)
    login(s_approver, base, approver_email, demo_password)

    # EXP_PAUSE: guardrail error_rate > 0.5 → PAUSE
    exp_pause = create_experiment_and_run(s_experimenter, s_approver, base, {
        "name":                "B5: guardrail PAUSE (error_rate > 0.5)",
        "feature_flag_key":    "b5_guardrail_pause",
        "audience_percentage": 100,
        "variants": [
            {"name": "control",   "value": "old_page",  "weight": 50, "is_control": True},
            {"name": "treatment", "value": "new_page",  "weight": 50, "is_control": False},
        ],
        "metrics": [
            {"metric_key": "b5_page_view_count", "type": "PRIMARY"},
            {"metric_key": "b5_error_rate",      "type": "GUARDRAIL",
             "threshold": 0.5, "window_minutes": 60, "action": "PAUSE"},
        ],
    }, "EXP_PAUSE")

    # EXP_ROLLBACK: guardrail avg_latency > 500 → ROLLBACK
    exp_rollback = create_experiment_and_run(s_experimenter, s_approver, base, {
        "name":                "B5: guardrail ROLLBACK (avg_latency > 500ms)",
        "feature_flag_key":    "b5_guardrail_rollback",
        "audience_percentage": 100,
        "variants": [
            {"name": "control",   "value": "old_layout",  "weight": 50, "is_control": True},
            {"name": "treatment", "value": "new_layout",  "weight": 50, "is_control": False},
        ],
        "metrics": [
            {"metric_key": "b5_click_count",   "type": "PRIMARY"},
            {"metric_key": "b5_avg_latency",   "type": "GUARDRAIL",
             "threshold": 500.0, "window_minutes": 60, "action": "ROLLBACK"},
        ],
    }, "EXP_ROLLBACK")

    # EXP_COOLING: для проверки cooling period (шаг 1 — субъект попадает сюда)
    exp_cooling = create_experiment_and_run(s_experimenter, s_approver, base, {
        "name":                "B5: cooling period test (шаг 1)",
        "feature_flag_key":    "b5_cooling",
        "audience_percentage": 100,
        "variants": [
            {"name": "control",   "value": "baseline",    "weight": 50, "is_control": True},
            {"name": "treatment", "value": "experiment_v", "weight": 50, "is_control": False},
        ],
        "metrics": [
            {"metric_key": "b5_page_view_count", "type": "PRIMARY"},
        ],
    }, "EXP_COOLING")

    # EXP_COOLING_2: для проверки cooling period (шаг 2 — субъект пытается попасть сюда)
    exp_cooling2 = create_experiment_and_run(s_experimenter, s_approver, base, {
        "name":                "B5: cooling period test (шаг 2)",
        "feature_flag_key":    "b5_cooling_second",
        "audience_percentage": 100,
        "variants": [
            {"name": "control",   "value": "fallback",    "weight": 50, "is_control": True},
            {"name": "treatment", "value": "new_feature",  "weight": 50, "is_control": False},
        ],
        "metrics": [
            {"metric_key": "b5_click_count", "type": "PRIMARY"},
        ],
    }, "EXP_COOLING_2")

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"""
✓  B5 seed завершён.

Эксперименты:
  EXP_PAUSE (guardrail PAUSE):
    id:         {exp_pause['id']}
    flag:       b5_guardrail_pause
    guardrail:  b5_error_rate > 0.5 → PAUSE (окно 60 мин)
    варианты:   control="old_page" (50), treatment="new_page" (50)

  EXP_ROLLBACK (guardrail ROLLBACK):
    id:         {exp_rollback['id']}
    flag:       b5_guardrail_rollback
    guardrail:  b5_avg_latency > 500ms → ROLLBACK (окно 60 мин)
    варианты:   control="old_layout" (50), treatment="new_layout" (50)

  EXP_COOLING (cooling period, шаг 1):
    id:         {exp_cooling['id']}
    flag:       b5_cooling
    варианты:   control="baseline" (50), treatment="experiment_v" (50)

  EXP_COOLING_2 (cooling period, шаг 2):
    id:         {exp_cooling2['id']}
    flag:       b5_cooling_second (default = "fallback")
    варианты:   control="fallback" (50), treatment="new_feature" (50)

Типы событий:
  b5_page_view  — без payload
  b5_error      — payload: {{"error_code": "number"}}
  b5_click      — payload: {{"element": "string"}}
  b5_latency    — payload: {{"ms": "number"}}

Метрики:
  b5_page_view_count — COUNT b5_page_view         (PRIMARY)
  b5_error_rate      — COUNT b5_error / COUNT b5_page_view  (GUARDRAIL → PAUSE при > 0.5)
  b5_click_count     — COUNT b5_click              (PRIMARY)
  b5_avg_latency     — AVG b5_latency.ms           (GUARDRAIL → ROLLBACK при > 500)

→ См. demo/B5/userscripts.md для сценариев проверки.
""")


if __name__ == "__main__":
    main()