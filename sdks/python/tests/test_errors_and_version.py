from __future__ import annotations

import warnings

import pytest

from waqt_client._envelope import check_version, unwrap
from waqt_client.errors import WaqtApiError, WaqtTransportError, WaqtVersionMismatch


def test_unwrap_success():
    body = {"meta": {"api_version": "1.3.0"}, "data": {"hello": "world"}, "error": None}
    assert unwrap(200, body, "ignore") == {"hello": "world"}


def test_unwrap_error_envelope_raises_waqt_api_error():
    body = {
        "meta": {"api_version": "1.3.0"}, "data": None,
        "error": {"code": "INVALID_INSTANT", "message": "bad", "details": {"received": "x"}},
    }
    with pytest.raises(WaqtApiError) as excinfo:
        unwrap(400, body, "ignore")
    assert excinfo.value.code == "INVALID_INSTANT"
    assert excinfo.value.details == {"received": "x"}


@pytest.mark.parametrize("code", ["INVALID_HIJRI_DATE", "UNKNOWN_TIMEZONE", "OUT_OF_RANGE"])
def test_unwrap_preserves_sprint16_error_codes_and_details(code):
    body = {
        "meta": {"api_version": "1.6.0"}, "data": None,
        "error": {"code": code, "message": "bad input", "details": {"received": "x"}},
    }
    with pytest.raises(WaqtApiError) as excinfo:
        unwrap(400, body, "ignore")
    assert excinfo.value.code == code
    assert excinfo.value.details == {"received": "x"}


def test_unwrap_malformed_body_raises_transport_error():
    with pytest.raises(WaqtTransportError):
        unwrap(200, {"not": "an envelope"}, "ignore")
    with pytest.raises(WaqtTransportError):
        unwrap(200, None, "ignore")


def test_version_check_ignore_policy_never_raises():
    check_version("99.0.0", "ignore")  # no exception


def test_version_check_warn_policy_warns_on_mismatch():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        check_version("2.0.0", "warn")
        assert len(w) == 1
        assert "outside this SDK's tested range" in str(w[0].message)


def test_version_check_warn_policy_silent_on_supported_version():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        check_version("1.3.0", "warn")
        assert len(w) == 0


def test_version_check_raise_policy_raises_version_mismatch():
    with pytest.raises(WaqtVersionMismatch):
        check_version("2.0.0", "raise")


def test_version_check_raise_policy_ok_within_supported_major():
    check_version("1.0.0", "raise")
    check_version("1.9.9", "raise")  # additive minor bumps within major 1 are fine
