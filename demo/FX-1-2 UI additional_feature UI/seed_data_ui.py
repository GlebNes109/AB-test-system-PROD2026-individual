#!/usr/bin/env python3
"""
Генератор тестовых данных для демонстрации UI (допфича FX-1/FX-2).

Создаёт:
  - 2 пользователя (EXPERIMENTER, APPROVER)
  - approver group
  - 3 типа событий:
      ui_exposure  — независимое, payload: {country, device, platform}
      ui_click     — независимое, payload: {element, country, device}
      ui_purchase  — зависимое от ui_click, payload: {amount, currency, country}
  - 4 метрики:
      ui_exposure_count  — COUNT ui_exposure              (PRIMARY)
      ui_clicks_count    — COUNT ui_click                  (SECONDARY)
      ui_conversion      — COUNT ui_purchase / COUNT ui_click  (SECONDARY)
      ui_avg_revenue     — AVG ui_purchase.amount          (SECONDARY)
  - 1 feature flag: ui_checkout_flow
  - 1 эксперимент (RUNNING): UI checkout A/B test

  После seed'а запустите сценарий эмулятора:
    POST http://localhost:80//scenarios  (тело — см. scenario_ui.json)

Запуск:
    pip install requests
    python "demo/FX-1-2 UI additional_feature UI/seed_data_ui.py"

Предусловия:
    docker compose up -d
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

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
        json={"decision": "ACCEPT", "comment": "Seed UI demo."},
    ))
    _ok(f"{label}: → RUNNING", s_owner.post(f"{base}/experiments/{exp_id}/start"))
    return exp


# ---------------------------------------------------------------------------
# Emulator scenario builder
# ---------------------------------------------------------------------------

COUNTRIES = ["RU", "US", "DE", "BR"]
DEVICES = ["mobile", "desktop", "tablet"]
PLATFORMS = ["ios", "android", "web"]
CURRENCIES = {"RU": "RUB", "US": "USD", "DE": "EUR", "BR": "BRL"}


def _build_variant_events(variant_value: str, is_control: bool) -> list[dict]:
    """
    Строит список EventsConfig для варианта.
    Каждая комбинация country/device/platform — отдельный EventsConfig
    с разной probability, чтобы получить разнообразные данные в UI.
    """
    events = []

    # Вероятности кликов/покупок зависят от варианта
    click_base = 0.5 if is_control else 0.7
    purchase_base = 0.2 if is_control else 0.35

    for ci, country in enumerate(COUNTRIES):
        for di, device in enumerate(DEVICES):
            platform = PLATFORMS[di % len(PLATFORMS)]

            # exposure — всегда отправляется
            events.append({
                "event_type": "ui_exposure",
                "time_delay_seconds": 0,
                "time_variation": 0,
                "probability": 1.0,
                "payload": {
                    "country": country,
                    "device": device,
                    "platform": platform,
                },
            })

            # click — с вариацией вероятности по стране/устройству
            p_click = round(min(1.0, click_base + ci * 0.05 - di * 0.1), 2)
            events.append({
                "event_type": "ui_click",
                "time_delay_seconds": 2,
                "time_variation": 1,
                "probability": max(0.1, p_click),
                "payload": {
                    "element": "checkout-btn",
                    "country": country,
                    "device": device,
                },
            })

            # purchase — зависимое от click, probability < click
            p_purchase = round(min(1.0, purchase_base + ci * 0.03), 2)
            amount = round(30 + ci * 20 + di * 5, 2)
            events.append({
                "event_type": "ui_purchase",
                "time_delay_seconds": 5,
                "time_variation": 2,
                "probability": max(0.05, p_purchase),
                "payload": {
                    "amount": amount,
                    "currency": CURRENCIES[country],
                    "country": country,
                },
            })

    return events


def build_scenario() -> dict:
    """Строит сценарий для эмулятора."""
    return {
        "scenario_name": "UI demo: checkout A/B test",
        "subjects_count": 200,
        "use_real_time": False,
        "sim_base_time": datetime.now(timezone.utc).isoformat(),
        "experiment": {
            "feature_flag_key": "ui_checkout_flow",
            "time_delay_seconds": 30,
            "time_variation": 10,
            "variants": [
                {
                    "feature_flag_value": "classic_checkout",
                    "events": _build_variant_events("classic_checkout", is_control=True),
                },
                {
                    "feature_flag_value": "new_checkout",
                    "events": _build_variant_events("new_checkout", is_control=False),
                },
            ],
        },
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Seed UI demo data (FX-1/FX-2)")
    ap.add_argument("--base-url",       default="http://localhost")
    ap.add_argument("--admin-email",    default="admin@mail.ru")
    ap.add_argument("--admin-password", default="123123123aA!")
    ap.add_argument("--emulator-url",   default="http://localhost:80/emulator")
    ap.add_argument("--run-scenario",   action="store_true",
                    help="Автоматически запустить сценарий в эмуляторе")
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

    _ok("ui_exposure (payload: country, device, platform)", s_admin.post(
        f"{base}/events/types", json={
            "type":           "ui_exposure",
            "description":    "Показ страницы checkout",
            "payload_schema": {"country": "string", "device": "string", "platform": "string"},
        }))

    _ok("ui_click (payload: element, country, device)", s_admin.post(
        f"{base}/events/types", json={
            "type":           "ui_click",
            "description":    "Клик по элементу checkout",
            "payload_schema": {"element": "string", "country": "string", "device": "string"},
        }))

    _ok("ui_purchase (зависимое от ui_click, payload: amount, currency, country)", s_admin.post(
        f"{base}/events/types", json={
            "type":                "ui_purchase",
            "description":         "Покупка через checkout",
            "requires_event_type": "ui_click",
            "payload_schema":      {"amount": "number", "currency": "string", "country": "string"},
        }))

    # ── 5. Metrics ───────────────────────────────────────────────────────────
    _step("5. Metrics")

    _ok("ui_exposure_count (COUNT ui_exposure)", s_admin.post(f"{base}/metrics", json={
        "key":         "ui_exposure_count",
        "name":        "Число показов checkout",
        "description": "COUNT ui_exposure — основная метрика экспозиции",
        "event_type":  "ui_exposure",
        "aggregation": "COUNT",
    }))

    _ok("ui_clicks_count (COUNT ui_click)", s_admin.post(f"{base}/metrics", json={
        "key":         "ui_clicks_count",
        "name":        "Число кликов checkout",
        "description": "COUNT ui_click",
        "event_type":  "ui_click",
        "aggregation": "COUNT",
    }))

    _ok("ui_conversion (COUNT ui_purchase / COUNT ui_click)", s_admin.post(f"{base}/metrics", json={
        "key":                     "ui_conversion",
        "name":                    "Конверсия checkout (покупки / клики)",
        "description":             "COUNT ui_purchase / COUNT ui_click — метрика конверсии",
        "event_type":              "ui_purchase",
        "aggregation":             "COUNT",
        "denominator_event_type":  "ui_click",
        "denominator_aggregation": "COUNT",
    }))

    _ok("ui_avg_revenue (AVG ui_purchase.amount)", s_admin.post(f"{base}/metrics", json={
        "key":           "ui_avg_revenue",
        "name":          "Средний чек checkout",
        "description":   "AVG ui_purchase.amount — payload-зависимая метрика",
        "event_type":    "ui_purchase",
        "aggregation":   "AVG",
        "payload_field": "amount",
    }))

    # ── 6. Feature flag ──────────────────────────────────────────────────────
    _step("6. Feature flag")

    _ok("ui_checkout_flow (default=classic_checkout)", s_admin.post(f"{base}/feature-flags", json={
        "key":           "ui_checkout_flow",
        "type":          "string",
        "default_value": "classic_checkout",
        "description":   "UI demo: A/B тест checkout flow",
    }))

    # ── 7. Experiment → RUNNING ──────────────────────────────────────────────
    _step("7. Experiment → RUNNING")

    login(s_experimenter, base, experimenter_email, demo_password)
    login(s_approver, base, approver_email, demo_password)

    exp = create_experiment_and_run(s_experimenter, s_approver, base, {
        "name":                "UI demo: checkout A/B test",
        "feature_flag_key":    "ui_checkout_flow",
        "audience_percentage": 100,
        "variants": [
            {"name": "control",   "value": "classic_checkout", "weight": 50, "is_control": True},
            {"name": "treatment", "value": "new_checkout",     "weight": 50, "is_control": False},
        ],
        "metrics": [
            {"metric_key": "ui_exposure_count", "type": "PRIMARY"},
            {"metric_key": "ui_clicks_count",   "type": "SECONDARY"},
            {"metric_key": "ui_conversion",     "type": "SECONDARY"},
            {"metric_key": "ui_avg_revenue",    "type": "SECONDARY"},
        ],
    }, "UI_CHECKOUT")

    # ── 8. Сохранить сценарий эмулятора ──────────────────────────────────────
    _step("8. Сценарий эмулятора")

    scenario = build_scenario()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scenario_path = os.path.join(script_dir, "scenario_ui.json")
    with open(scenario_path, "w", encoding="utf-8") as f:
        json.dump(scenario, f, ensure_ascii=False, indent=2)
    print(f"  ✓  сценарий сохранён в {scenario_path}")

    # ── 9. (опционально) запустить сценарий ──────────────────────────────────
    if args.run_scenario:
        _step("9. Запуск сценария в эмуляторе")
        r = requests.post(
            f"{args.emulator_url}/scenarios",
            headers={"Content-Type": "application/json"},
            json=scenario,
        )
        if r.status_code in (200, 201):
            status = r.json()
            print(f"  ✓  сценарий запущен: id={status.get('id')}")
        else:
            print(f"  ✗  ошибка запуска: {r.status_code} {r.text}", file=sys.stderr)
            print("     Запустите вручную: POST http://localhost:80/emulator/scenarios < scenario_ui.json")

    # ── Done ─────────────────────────────────────────────────────────────────
    print(f"""
✓  UI demo seed завершён.

Эксперимент:
  id:       {exp['id']}
  flag:     ui_checkout_flow (default = "classic_checkout")
  варианты: control="classic_checkout" (50), treatment="new_checkout" (50)
  метрики:
    ui_exposure_count  — COUNT ui_exposure              (PRIMARY, экспозиция)
    ui_clicks_count    — COUNT ui_click                  (SECONDARY)
    ui_conversion      — COUNT ui_purchase / COUNT ui_click  (SECONDARY, конверсия)
    ui_avg_revenue     — AVG ui_purchase.amount          (SECONDARY, payload-метрика)

Payload-разрезы для UI:
    country:  {', '.join(COUNTRIES)}
    device:   {', '.join(DEVICES)}
    platform: {', '.join(PLATFORMS)}

Далее:
  1. Запустите сценарий эмулятора:
     curl -X POST http://localhost:80/emulator/scenarios -H "Content-Type: application/json" -d @"{scenario_path}"
     или: python seed_data_ui.py --run-scenario
  2. Дождитесь завершения (~5 сек для sim_time)
  3. Откройте дашборд: {{base_url}}/metabase
  4. Выберите эксперимент "UI demo: checkout A/B test"
  5. См. demo/FX-1-2 UI additional_feature UI/userscripts.md
""")


if __name__ == "__main__":
    main()
