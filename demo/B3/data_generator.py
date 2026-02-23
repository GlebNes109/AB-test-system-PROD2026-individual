#!/usr/bin/env python3
"""
Генератор тестовых данных для проверки критериев B3 (жизненный цикл экспериментов и ревью).

Создаёт:
  - 5 пользователей: b3_experimenter, b3_approver_alpha, b3_approver_beta, b3_approver_outsider, b3_viewer
  - approver group для b3_experimenter (2 одобряющих: alpha + beta, min_approvals=2)
  - b3_approver_outsider — APPROVER, но НЕ в группе (для проверки B3-5)
  - 1 тип события (page_view) + 1 метрику (page_view_count)
  - 5 feature flag:
      b3_lifecycle     — для проверки перехода draft → review (B3-1)
      b3_approval      — для проверки review → approved при min_approvals=2 (B3-2)
      b3_block_start   — для проверки блокировки запуска без одобрений (B3-3)
      b3_bad_transition — для проверки запрещённых переходов (B3-4)
      b3_role_policy   — для проверки политики ревью по ролям (B3-5)
  - 5 экспериментов (каждый в нужном для проверки статусе)

Запуск:
    pip install requests
    python demo/B3/data_generator.py
    python demo/B3/data_generator.py --base-url http://localhost --admin-email admin@mail.ru --admin-password 123123123aA!

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


def _expect_error(label: str, r: requests.Response, expected_status: int) -> dict:
    """Ожидаем ошибку — проверяем что запрос НЕ прошёл."""
    try:
        data = r.json()
    except Exception:
        data = {}

    if r.status_code == expected_status:
        print(f"  ✓  {label}  (отклонено: {r.status_code}, как и ожидалось)")
        return data

    print(f"  ✗  {label}  →  ожидали {expected_status}, получили {r.status_code}: {r.text}", file=sys.stderr)
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


def create_experiment(s: requests.Session, base: str, payload: dict, label: str) -> dict:
    """Создаёт эксперимент (остаётся в DRAFT)."""
    exp = _ok(f"{label}: создан (DRAFT)", s.post(f"{base}/experiments", json=payload))
    return exp


def submit_experiment(s: requests.Session, base: str, exp_id: str, label: str) -> None:
    _ok(f"{label}: → REVIEW", s.post(f"{base}/experiments/{exp_id}/submit"))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Seed B3 test data")
    ap.add_argument("--base-url",       default="http://localhost")
    ap.add_argument("--admin-email",    default="admin@mail.ru")
    ap.add_argument("--admin-password", default="123123123aA!")
    args = ap.parse_args()

    base = args.base_url.rstrip("/") + "/api/v1"

    # Сессии для разных ролей
    s_admin = requests.Session()
    s_admin.headers["Content-Type"] = "application/json"

    s_experimenter = requests.Session()
    s_experimenter.headers["Content-Type"] = "application/json"

    s_approver_alpha = requests.Session()
    s_approver_alpha.headers["Content-Type"] = "application/json"

    s_approver_beta = requests.Session()
    s_approver_beta.headers["Content-Type"] = "application/json"

    s_approver_outsider = requests.Session()
    s_approver_outsider.headers["Content-Type"] = "application/json"

    s_viewer = requests.Session()
    s_viewer.headers["Content-Type"] = "application/json"

    # ── 1. Auth (admin) ──────────────────────────────────────────────────────
    _step("1. Auth (admin)")
    login(s_admin, base, args.admin_email, args.admin_password)

    # ── 2. Users ─────────────────────────────────────────────────────────────
    _step("2. Users")
    demo_password = "Demo1234!x"
    experimenter_email     = "b3_experimenter@demo.com"
    approver_alpha_email   = "b3_approver_alpha@demo.com"
    approver_beta_email    = "b3_approver_beta@demo.com"
    approver_outsider_email = "b3_approver_outsider@demo.com"
    viewer_email           = "b3_viewer@demo.com"

    for email, role in [
        (experimenter_email,      "EXPERIMENTER"),
        (approver_alpha_email,    "APPROVER"),
        (approver_beta_email,     "APPROVER"),
        (approver_outsider_email, "APPROVER"),
        (viewer_email,            "VIEWER"),
    ]:
        _ok(f"user {email} ({role})", s_admin.post(
            f"{base}/users",
            json={"email": email, "password": demo_password, "role": role},
        ))

    experimenter_id     = find_user(s_admin, base, experimenter_email)
    approver_alpha_id   = find_user(s_admin, base, approver_alpha_email)
    approver_beta_id    = find_user(s_admin, base, approver_beta_email)

    # ── 3. Approver group (min_approvals=2, оба одобряющих) ──────────────
    _step("3. Approver group (min_approvals=2)")
    _ok("approver group для b3_experimenter", s_admin.put(
        f"{base}/users/{experimenter_id}/approvers",
        json={"approver_ids": [approver_alpha_id, approver_beta_id], "min_approvals": 2},
    ))

    # ── 4. Event type + metric ────────────────────────────────────────────
    _step("4. Event type + metric")
    _ok("page_view", s_admin.post(f"{base}/events/types", json={
        "type":        "page_view",
        "description": "Просмотр страницы",
    }))
    _ok("page_view_count", s_admin.post(f"{base}/metrics", json={
        "key":         "page_view_count",
        "name":        "Число просмотров",
        "description": "COUNT page_view",
        "event_type":  "page_view",
        "aggregation": "COUNT",
    }))

    # ── 5. Feature flags ─────────────────────────────────────────────────
    _step("5. Feature flags")

    flags = {
        "b3_lifecycle": {
            "key": "b3_lifecycle", "type": "string",
            "default_value": "lifecycle_default",
            "description": "B3-1: проверка перехода DRAFT → REVIEW",
        },
        "b3_approval": {
            "key": "b3_approval", "type": "string",
            "default_value": "approval_default",
            "description": "B3-2: проверка REVIEW → APPROVED при min_approvals=2",
        },
        "b3_block_start": {
            "key": "b3_block_start", "type": "string",
            "default_value": "block_start_default",
            "description": "B3-3: блокировка запуска без одобрений",
        },
        "b3_bad_transition": {
            "key": "b3_bad_transition", "type": "string",
            "default_value": "bad_transition_default",
            "description": "B3-4: запрещённые переходы статусов",
        },
        "b3_role_policy": {
            "key": "b3_role_policy", "type": "string",
            "default_value": "role_policy_default",
            "description": "B3-5: политика ревью по ролям/группам",
        },
    }

    for key, payload in flags.items():
        _ok(f"{key} (default={payload['default_value']})", s_admin.post(f"{base}/feature-flags", json=payload))

    # ── 6. Базовый шаблон вариантов ──────────────────────────────────────
    def make_variants(control_val: str, treatment_val: str):
        return [
            {"name": "control",   "value": control_val,   "weight": 50, "is_control": True},
            {"name": "treatment", "value": treatment_val, "weight": 50, "is_control": False},
        ]

    metric_ref = [{"metric_key": "page_view_count", "type": "PRIMARY"}]

    # ── 7. Логин под experimenter ────────────────────────────────────────
    _step("6. Login experimenter")
    login(s_experimenter, base, experimenter_email, demo_password)

    # ── 8. Experiments ────────────────────────────────────────────────────
    _step("7. Experiments")

    # B3-1: DRAFT (для ручного submit)
    exp_lifecycle = create_experiment(s_experimenter, base, {
        "name": "B3-1: жизненный цикл DRAFT→REVIEW",
        "feature_flag_key": "b3_lifecycle",
        "audience_percentage": 100,
        "variants": make_variants("lifecycle_control_v", "lifecycle_treatment_v"),
        "metrics": metric_ref,
    }, "b3_lifecycle")
    print(f"       → exp_id: {exp_lifecycle['id']} (оставлен в DRAFT для ручной проверки submit)")

    # B3-2: REVIEW (для проверки одобрений)
    exp_approval = create_experiment(s_experimenter, base, {
        "name": "B3-2: одобрение двумя аппруверами",
        "feature_flag_key": "b3_approval",
        "audience_percentage": 100,
        "variants": make_variants("approval_control_v", "approval_treatment_v"),
        "metrics": metric_ref,
    }, "b3_approval")
    submit_experiment(s_experimenter, base, exp_approval["id"], "b3_approval")
    print(f"       → exp_id: {exp_approval['id']} (в REVIEW, ждёт 2 одобрения)")

    # B3-3: REVIEW (для проверки блокировки запуска)
    exp_block_start = create_experiment(s_experimenter, base, {
        "name": "B3-3: блокировка запуска без одобрений",
        "feature_flag_key": "b3_block_start",
        "audience_percentage": 100,
        "variants": make_variants("block_start_control_v", "block_start_treatment_v"),
        "metrics": metric_ref,
    }, "b3_block_start")
    submit_experiment(s_experimenter, base, exp_block_start["id"], "b3_block_start")
    print(f"       → exp_id: {exp_block_start['id']} (в REVIEW, для попытки /start)")

    # B3-4: DRAFT (для проверки запрещённых переходов)
    exp_bad_transition = create_experiment(s_experimenter, base, {
        "name": "B3-4: запрещённые переходы",
        "feature_flag_key": "b3_bad_transition",
        "audience_percentage": 100,
        "variants": make_variants("bad_trans_control_v", "bad_trans_treatment_v"),
        "metrics": metric_ref,
    }, "b3_bad_transition")
    print(f"       → exp_id: {exp_bad_transition['id']} (в DRAFT для попытки /start напрямую)")

    # B3-5: REVIEW (для проверки ролей)
    exp_role_policy = create_experiment(s_experimenter, base, {
        "name": "B3-5: политика ревью по ролям",
        "feature_flag_key": "b3_role_policy",
        "audience_percentage": 100,
        "variants": make_variants("role_policy_control_v", "role_policy_treatment_v"),
        "metrics": metric_ref,
    }, "b3_role_policy")
    submit_experiment(s_experimenter, base, exp_role_policy["id"], "b3_role_policy")
    print(f"       → exp_id: {exp_role_policy['id']} (в REVIEW, для проверки кто может ревьюить)")

    # ── Done ──────────────────────────────────────────────────────────────
    print(f"""
✓  B3 seed завершён.

Созданные пользователи:
  {experimenter_email:<40s}  EXPERIMENTER   (пароль: {demo_password})
  {approver_alpha_email:<40s}  APPROVER       (пароль: {demo_password})  ← в группе
  {approver_beta_email:<40s}  APPROVER       (пароль: {demo_password})  ← в группе
  {approver_outsider_email:<40s}  APPROVER       (пароль: {demo_password})  ← НЕ в группе
  {viewer_email:<40s}  VIEWER         (пароль: {demo_password})

Approver group для experimenter:
  min_approvals = 2
  одобряющие: approver_alpha, approver_beta
  НЕ в группе: approver_outsider (для проверки B3-5)

Созданные эксперименты:
  b3_lifecycle      [{exp_lifecycle['id']}]      DRAFT     (B3-1)
  b3_approval       [{exp_approval['id']}]      REVIEW    (B3-2)
  b3_block_start    [{exp_block_start['id']}]      REVIEW    (B3-3)
  b3_bad_transition [{exp_bad_transition['id']}]      DRAFT     (B3-4)
  b3_role_policy    [{exp_role_policy['id']}]      REVIEW    (B3-5)

Далее: см. demo/B3/userscripts.md для сценариев проверки.
""")


if __name__ == "__main__":
    main()
