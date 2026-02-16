def verify_auth_response(response, request=None, **kwargs):
    data = response.json()
    assert "accessToken" in data, "Missing accessToken"
    assert "expiresIn" in data, "Missing expiresIn"
    assert "user" in data, "Missing user"
    user = data["user"]
    assert "id" in user, "Missing user.id"
    assert "email" in user, "Missing user.email"
    assert isinstance(data["accessToken"], str)
    assert isinstance(data["expiresIn"], int)
    return True


def verify_user_response(response, request=None, **kwargs):
    data = response.json()
    assert "id" in data, "Missing id"
    assert "email" in data, "Missing email"
    assert isinstance(data["id"], str)
    assert isinstance(data["email"], str)
    return True


def verify_users_list(response, request=None, **kwargs):
    data = response.json()
    assert "items" in data, "Missing items"
    assert "total" in data, "Missing total"
    assert "page" in data, "Missing page"
    assert "size" in data, "Missing size"
    assert isinstance(data["items"], list)
    for item in data["items"]:
        assert "id" in item, "Missing id in item"
        assert "email" in item, "Missing email in item"
    return True


def verify_feature_flag_response(response, request=None, **kwargs):
    data = response.json()
    assert "id" in data, "Missing id"
    assert "key" in data, "Missing key"
    assert "type" in data, "Missing type"
    assert "default_value" in data, "Missing default_value"
    assert isinstance(data["id"], str)
    assert isinstance(data["key"], str)
    assert data["type"] in ("string", "number", "bool"), f"Invalid type: {data['type']}"
    assert "createdAt" in data, "Missing createdAt"
    return True


def verify_feature_flags_list(response, request=None, **kwargs):
    data = response.json()
    assert "items" in data, "Missing items"
    assert "total" in data, "Missing total"
    assert "page" in data, "Missing page"
    assert "size" in data, "Missing size"
    assert isinstance(data["items"], list)
    for item in data["items"]:
        assert "id" in item, "Missing id in item"
        assert "key" in item, "Missing key in item"
        assert "type" in item, "Missing type in item"
        assert "default_value" in item, "Missing default_value in item"
    return True


def verify_experiment_response(response, request=None, **kwargs):
    data = response.json()
    assert "id" in data, "Missing id"
    assert "feature_flag_id" in data, "Missing feature_flag_id"
    assert "created_by" in data, "Missing created_by"
    assert "created_at" in data, "Missing created_at"
    assert "version" in data, "Missing version"
    assert "name" in data, "Missing name"
    assert "status" in data, "Missing status"
    assert "audience_percentage" in data, "Missing audience_percentage"
    assert "variants" in data, "Missing variants"
    assert isinstance(data["id"], str)
    assert isinstance(data["variants"], list)
    assert len(data["variants"]) > 0, "variants must not be empty"
    valid_statuses = ("draft", "review", "approved", "rejected", "running", "paused", "finished", "archived")
    assert data["status"] in valid_statuses, f"Invalid status: {data['status']}"
    control_variants = [v for v in data["variants"] if v.get("is_control")]
    assert len(control_variants) == 1, "Exactly one variant must be control"
    return True


def verify_experiments_list(response, request=None, **kwargs):
    data = response.json()
    assert "items" in data, "Missing items"
    assert "total" in data, "Missing total"
    assert "page" in data, "Missing page"
    assert "size" in data, "Missing size"
    assert isinstance(data["items"], list)
    for item in data["items"]:
        assert "id" in item, "Missing id in item"
        assert "name" in item, "Missing name in item"
        assert "status" in item, "Missing status in item"
    return True


def verify_error_response(response, request=None, **kwargs):
    data = response.json()
    assert "code" in data, "Missing code"
    assert "message" in data, "Missing message"
    assert "traceId" in data, "Missing traceId"
    assert "timestamp" in data, "Missing timestamp"
    assert "path" in data, "Missing path"
    return True
