"""V1.7 API Contract tests — validate unified {ok, data, meta, error} envelope."""

from tradingagents.astock.api.envelope import (
    assert_success, assert_error, ok, fail, created,
)


# ── Envelope unit tests ──────────────────────────────────────────────────────


def test_success_envelope():
    payload, status = ok({"foo": "bar"})
    assert status == 200
    assert_success(payload)
    assert payload["data"] == {"foo": "bar"}


def test_created_envelope():
    payload, status = ok({"id": 1}, status=201)
    assert status == 201
    assert_success(payload)
    assert payload["data"]["id"] == 1


def test_success_data_state_in_meta():
    payload, _ = ok([], data_state="partial")
    assert payload["meta"]["data_state"] == "partial"


def test_error_envelope():
    payload, status = fail("something went wrong", 400)
    assert status == 400
    assert_error(payload, "INVALID_REQUEST")
    assert payload["error"]["retryable"] is False


def test_error_503_provider_unavailable():
    payload, _ = fail("provider down", 503, code="PROVIDER_UNAVAILABLE")
    assert_error(payload, "PROVIDER_UNAVAILABLE")
    assert payload["error"]["retryable"] is True


def test_error_500_internal():
    payload, status = fail("oops", 500)
    assert_error(payload, "INTERNAL_ERROR")
    assert payload["error"]["retryable"] is True


def test_error_422_unprocessable():
    payload, _ = fail("bad date format", 422)
    assert_error(payload, "UNPROCESSABLE_ENTITY")


def test_error_with_details():
    payload, _ = fail("symbol invalid", 400, details={"field": "symbol"})
    assert payload["error"]["details"]["field"] == "symbol"


def test_error_404():
    payload, _ = fail("not found", 404)
    assert_error(payload, "NOT_FOUND")


def test_meta_contains_request_id():
    payload, _ = ok(None)
    rid = payload["meta"]["request_id"]
    assert rid.startswith("req_")
    assert "/" not in rid


def test_meta_contains_schema_version():
    payload, _ = ok(None)
    assert payload["meta"]["schema_version"] == "1.0"


def test_meta_contains_timestamp():
    payload, _ = ok(None)
    ts = payload["meta"]["timestamp"]
    assert "T" in ts  # ISO format


def test_legacy_success_response_works():
    """Old callers still using success_response() should work."""
    from tradingagents.astock.api.envelope import success_response
    payload, status = success_response({"a": 1})
    assert status == 200
    assert_success(payload)


def test_legacy_error_response_works():
    from tradingagents.astock.api.envelope import error_response
    payload, status = error_response("test error", 400)
    assert status == 400
    assert_error(payload)
