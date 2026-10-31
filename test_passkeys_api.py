"""Integration tests for DEVON Command Center WebAuthn ceremonies."""

import sys
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.core.config import settings


async def test_passkey_status_starts_empty(client, auth_headers):
    response = await client.get("/api/v1/auth/passkeys/status", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is False
    assert body["credentials"] == 0
    assert body["rp_id"] == settings.PASSKEY_RP_ID


async def test_passkey_registration_options_require_auth(client):
    response = await client.post("/api/v1/auth/passkeys/register/options")
    assert response.status_code == 401


async def test_passkey_registration_options_are_discoverable_and_verified(client, auth_headers):
    response = await client.post(
        "/api/v1/auth/passkeys/register/options", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["challenge_id"]
    options = body["publicKey"]
    assert options["rp"]["id"] == settings.PASSKEY_RP_ID
    assert options["challenge"]
    assert options["authenticatorSelection"]["residentKey"] == "required"
    assert options["authenticatorSelection"]["userVerification"] == "required"


async def test_passkey_login_options_need_no_password_or_email(client):
    response = await client.post("/api/v1/auth/passkeys/login/options")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["challenge_id"]
    options = body["publicKey"]
    assert options["rpId"] == settings.PASSKEY_RP_ID
    assert options["userVerification"] == "required"
    assert options["challenge"]


def test_passkey_defaults_name_one_live_host():
    """The default rp id and origin must name the same, existing host.

    Pinned here rather than in each ceremony test, which assert the wiring
    instead: that every endpoint reports whatever host is configured. A literal
    repeated across three ceremonies pins the value in three places and tests
    the plumbing in none.

    The host matters because a WebAuthn credential is bound to the rp id. A
    default naming a retired project applies exactly when the deployment
    override is missing, and presents as a rejected passkey rather than as
    missing configuration.
    """
    assert settings.PASSKEY_RP_ID == "meta-supreme-apex-genesis-web.vercel.app"
    assert settings.PASSKEY_ORIGIN == f"https://{settings.PASSKEY_RP_ID}"


# ---------------------------------------------------------------------------
# A real android-key attestation, so pyasn1 decodes something.
# ---------------------------------------------------------------------------
#
# pyasn1 is in the closure only through webauthn, and webauthn hands it
# attacker-supplied bytes in one place: verify_android_key BER-decodes the
# attestation certificate and its Android key description extension. Every
# other ceremony above sends no attestation at all, so the pyasn1 bump of PR
# #442 passed CI with nothing executing the decoder its four advisories are
# about. Ruled by Tee on a card on 2026-10-31: add this test.
#
# The vector is py_webauthn's own, an attestation a Pixel 8a made in January
# 2025 for rp id "localhost": tests/test_verify_registration_response_android_key.py
# in duo-labs/py_webauthn at v3.0.0 (44330eb), BSD-3-Clause, Copyright (c)
# 2017-2021 Duo Security, Inc. Its certificate chain expired on 2025-02-02, so
# the store webauthn validates against is given 2025-01-08 as the time, which
# is what upstream does; the clock it replaces is only the X.509 one.

ANDROID_KEY_CHALLENGE = "t4LWI0iYJSTWPl9WXUdNhdHAnrPDLF9eWAP9lHgmHP8"
ANDROID_KEY_RP_ID = "localhost"
ANDROID_KEY_ORIGIN = "http://localhost:8000"
ANDROID_KEY_CREDENTIAL_ID = "AYNe4CBKc8H30FuAb8uaht6JbEQfbSBnS0SX7B6MFg8ofI92oR5lheRDJCgwY-JqB_QSJtezdhMbf8Wzt_La5N0"
ANDROID_KEY_ATTESTATION_OBJECT = (
    "o2NmbXRrYW5kcm9pZC1rZXlnYXR0U3RtdKNjYWxnJmNzaWdYSDBGAiEAs9Aufj5f5HyLKEFsgfmq"
    "yaXfAih-hGuTJqgmxZGijzYCIQDAMddAq1gwH3MtesYR6WE6IAockRz8ilR7CFw_kgdmv2N4NWOF"
    "WQLQMIICzDCCAnKgAwIBAgIBATAKBggqhkjOPQQDAjA5MSkwJwYDVQQDEyBkNjAyYTAzYTY3MmQ4"
    "NjViYTVhNDg1ZTMzYTIwN2M3MzEMMAoGA1UEChMDVEVFMB4XDTcwMDEwMTAwMDAwMFoXDTQ4MDEw"
    "MTAwMDAwMFowHzEdMBsGA1UEAxMUQW5kcm9pZCBLZXlzdG9yZSBLZXkwWTATBgcqhkjOPQIBBggq"
    "hkjOPQMBBwNCAATXVi3-n-rBsrP3A4Pj9P8e6PNh3eNdC38PaFiCZyMWdUVA6PbE6985PSUDDcnk"
    "3Knnpyc66J_HFOu_geuqiWtAo4IBgzCCAX8wDgYDVR0PAQH_BAQDAgeAMIIBawYKKwYBBAHWeQIB"
    "EQSCAVswggFXAgIBLAoBAQICASwKAQEEIFZS4txFVJqW-Wr6IlUC-H-twIpgvAITksC-jFBi_V9e"
    "BAAwd7-FPQgCBgGUcHc4or-FRWcEZTBjMT0wGwQWY29tLmdvb2dsZS5hbmRyb2lkLmdzZgIBIzAe"
    "BBZjb20uZ29vZ2xlLmFuZHJvaWQuZ21zAgQO6jzjMSIEIPD9bFtBDyXLJcO1M0bIly-uMPjudBHf"
    "kQSArWstYNuDMIGpoQUxAwIBAqIDAgEDowQCAgEApQUxAwIBBKoDAgEBv4N4AwIBA7-DeQMCAQq_"
    "hT4DAgEAv4VATDBKBCCd4l-wK7VTDUQUnRSEN8guJn5VcyJTCqbwOwrC6Skx2gEB_woBAAQg6y0p"
    "x0ZXc5v2bsVb45w-6IiMbXzp3gyHIWKS1mbz6gu_hUEFAgMCSfC_hUIFAgMDFwW_hU4GAgQBNP35"
    "v4VPBgIEATT9-TAKBggqhkjOPQQDAgNIADBFAiEAzNz6wyTo4t5ixo9G4zXPwh4zSB9F854sU_KD"
    "GTf0dxYCICaQVSWzWgTZLQYv13MXJJee8S8_luQB3W5lPPzP0exsWQHjMIIB3zCCAYWgAwIBAgIR"
    "ANYCoDpnLYZbpaSF4zogfHMwCgYIKoZIzj0EAwIwKTETMBEGA1UEChMKR29vZ2xlIExMQzESMBAG"
    "A1UEAxMJRHJvaWQgQ0EzMB4XDTI1MDEwNzE3MDg0M1oXDTI1MDIwMjEwMzUyN1owOTEpMCcGA1UE"
    "AxMgZDYwMmEwM2E2NzJkODY1YmE1YTQ4NWUzM2EyMDdjNzMxDDAKBgNVBAoTA1RFRTBZMBMGByqG"
    "SM49AgEGCCqGSM49AwEHA0IABFPbPYqm91rYvZVCBdFaHRMg0tw7U07JA1EcD9ZP4d0lK2NFM4A0"
    "wGKS4jbTR_bu7NTt_YyF388S0PWAJTluqnOjfjB8MB0GA1UdDgQWBBSXyrsZ_A1NnJGRq0sm2G9n"
    "m-NC5zAfBgNVHSMEGDAWgBTFUX4F2MtjWykYrAIa8sh9bBL-kjAPBgNVHRMBAf8EBTADAQH_MA4G"
    "A1UdDwEB_wQEAwICBDAZBgorBgEEAdZ5AgEeBAuiAQgDZkdvb2dsZTAKBggqhkjOPQQDAgNIADBF"
    "AiEAysd6JDoI8X4NEdrRwUwtIAy-hLxSEKUVS2XVWS2CP04CIFNQQzM4TkA_xaZj8KyiS61nb-aO"
    "BP35tlA34JCOlv9nWQHcMIIB2DCCAV2gAwIBAgIUAIUK9vrO5iIEbQx0izdwqlWwtk0wCgYIKoZI"
    "zj0EAwMwKTETMBEGA1UEChMKR29vZ2xlIExMQzESMBAGA1UEAxMJRHJvaWQgQ0EyMB4XDTI0MTIw"
    "OTA2Mjg1M1oXDTI1MDIxNzA2Mjg1MlowKTETMBEGA1UEChMKR29vZ2xlIExMQzESMBAGA1UEAxMJ"
    "RHJvaWQgQ0EzMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEPjbr-yt9xhgcbKLXoN3RK-1FcCjw"
    "IpeMPJZjayW0dqNtFflHp2smO0DxN_6x7M7NAGbcC9lM1_E-N6z51ODv-6NjMGEwDgYDVR0PAQH_"
    "BAQDAgIEMA8GA1UdEwEB_wQFMAMBAf8wHQYDVR0OBBYEFMVRfgXYy2NbKRisAhryyH1sEv6SMB8G"
    "A1UdIwQYMBaAFKYLhqTwyH8ztWE5Ys0956c6QoNIMAoGCCqGSM49BAMDA2kAMGYCMQCuzU0wV_Nk"
    "OQzgqzyqP66SJN6lilrU-NDVU6qNCnbFsUoZQOm4wBwUw7LqfoUhx7YCMQDFEvqHfc2hwN2J4I9Z"
    "4rTHiLlsy6gA33WvECzIZmVMpKcyEiHlm4c9XR0nVkAjQ_5ZA4QwggOAMIIBaKADAgECAgoDiCZn"
    "YGWJloYOMA0GCSqGSIb3DQEBCwUAMBsxGTAXBgNVBAUTEGY5MjAwOWU4NTNiNmIwNDUwHhcNMjIw"
    "MTI2MjI0OTQ1WhcNMzcwMTIyMjI0OTQ1WjApMRMwEQYDVQQKEwpHb29nbGUgTExDMRIwEAYDVQQD"
    "EwlEcm9pZCBDQTIwdjAQBgcqhkjOPQIBBgUrgQQAIgNiAAT72ZtYJ0I2etFhouvtVs0sBzvYsx8t"
    "hNCZV1wsDPvsMDSTPij-M1wBFD00OUn2bfU5b7K2_t2NkXc2-_V9g--mdb6SoRGmJ_AG9ScY60LK"
    "SA7iPT7gZ_5-q0tnEPPZJCqjZjBkMB0GA1UdDgQWBBSmC4ak8Mh_M7VhOWLNPeenOkKDSDAfBgNV"
    "HSMEGDAWgBQ2YeEAfIgFCVGLRGxH_xpMyepPEjASBgNVHRMBAf8ECDAGAQH_AgECMA4GA1UdDwEB"
    "_wQEAwIBBjANBgkqhkiG9w0BAQsFAAOCAgEArpB2eLbKHNcS6Q3Td3N7ZCgVLN0qA7CboM-Ftu4Y"
    "YAcHxh-e_sk7T7XOg5S4d9a_DD7mIXgENSBPB_fVqCnBaSDKNJ3nUuC1_9gcT95p4kKJo0tqcsWw"
    "8WgKVJhNuZCN7d_ziHLiRRcrKtaj944THzsy7vB-pSai7gTah_RJrDQI91bDUJgld8_p_QAbVnYA"
    "8o-msO0sRKxgF1V5QuBwBTfpdkqshqL3nwBm0sofqI_rM-JOQava3-IurHvfkzioiOJ0uFJnBGVj"
    "pZFwGwsmyKwzl-3qRKlkHggAOKt3lQQ4GiJnOCm10JrxPa2Za0K6_kyk6YyvvRcFNai5ej3nMKJP"
    "g-eeG2nST6N6ePFuaeoNQnD4XkagGFEQYzcqvsdFsmsbUFMghFl7zEVYdscuSgCG939wxW1JgKyG"
    "5ce7CI40328w9IuOf8mUS_W3i4jSfxqCJbegyo_SKDpDILnhJUBy0T3fN8mv9AyO0uoJBlvnogIV"
    "v2SdpYUt92vyOiGMy3Jx_ZRWjIRa7iIV3VnjLI__pgCrXQLMinZWEWsxVxg25nrk8u32nZd67DJN"
    "3k2FufRbsmHZly9CLo0P79lkIEC3rifLqqJeDyHQNaBMUC6BSDZ5RJCtMjSZw2xL5z0X9_zBsKVP"
    "kMW61hMhKzVmYNLe1DJQANRP-enru5i1oXlZBSAwggUcMIIDBKADAgECAgkA1Q_yW6Py1rMwDQYJ"
    "KoZIhvcNAQELBQAwGzEZMBcGA1UEBRMQZjkyMDA5ZTg1M2I2YjA0NTAeFw0xOTExMjIyMDM3NTha"
    "Fw0zNDExMTgyMDM3NThaMBsxGTAXBgNVBAUTEGY5MjAwOWU4NTNiNmIwNDUwggIiMA0GCSqGSIb3"
    "DQEBAQUAA4ICDwAwggIKAoICAQCvtseCK7GnAewrtC6LzFQWY6vvmC8yx391MQMMl1JLG1_oCfvH"
    "KqlFH3Q8vZpvEzV0SqVed_a2rDU17hfCXmOVF92ckuY3SlPL_iWPj_u2_RKTeKIqTKmcRS1HpZ8y"
    "AfRBl8oczX52L7L1MVG2_rL__Stv5P5bxr2ew0v-CCOdqvzrjrWo7Ss6zZxeOneQ4bUUQnkxWYWY"
    "Ea2esqlrvdelfJOpHEH8zSfWf9b2caoLgVJhrThPo3lEhkYE3bPYxPkgoZsWVsLxStbQPFbsBgiZ"
    "BBwe0aX-bTRAtVa60dChUlicU-VdNwdi8BIu75GGGxsObEyAknSZwOm-wLg-O8H5PHLASWBLvS8T"
    "ReYsP44m2-wGyUdm88EoI51PQxL62BI4h-Br7PVnWDv4NVqB_uq6-ZqDyN8-KjIq_Gcr8SCxNRWL"
    "aCHOrzCbbu53-YgzsBjaoQ5FHwajdNUHgfNZCClmu3eLkwiUJpjnTgvNJGKKAcLMA-UfCz5bSsHk"
    "356vn_akkqd8FIOIKIUBW0Is5nuAuIybSOE7YHq1Rccj_4xE-PLTaLn2Ug0xFF6_noYq1x32o7_S"
    "RQlZ1lN0DZehLzaLE-9m1dClSm4vXZpv70RoMrxnhEclhh8JPdDm80BdqJZD7w9NabZCAFH9uTBJ"
    "Zz42lQWA0830-9CLxYSDlSYAYwIDAQABo2MwYTAdBgNVHQ4EFgQUNmHhAHyIBQlRi0RsR_8aTMnq"
    "TxIwHwYDVR0jBBgwFoAUNmHhAHyIBQlRi0RsR_8aTMnqTxIwDwYDVR0TAQH_BAUwAwEB_zAOBgNV"
    "HQ8BAf8EBAMCAgQwDQYJKoZIhvcNAQELBQADggIBAE4xoFzyi6Zdva-hztcJae5cqEEErd7YowbP"
    "f23uUDdddF7ZkssCQsznLcnu1RGR_lrVK61907JcCZ4TpJGjzdSHpazOh2YyTErkYzgkaue3ikGK"
    "y7mKBcTJ1pbuqrYJ0LoM4aMb6YSQ3z9MDqndyegv-w_LPp692MuVJ4nysUEfrFbIhkJutylgQnNd"
    "pQ4RrHFfGBjPn9xOJUo3YzUbaiRAFQhhJjpuMQvhpQ3lx-juiA_dS-WISjcSjRiDC7NHa_QpHoLV"
    "xmpklJOeCEgL-8APfYp01D5zc36-XY5OxRUwLUaJaSeA3HU47X6Rdb5hOedNQ604izBQ_9Wp3lJi"
    "AAiYwB9jxT3-IiCRCPpPZboWxJzL3gg318WETVS3OYugEi5QWxVckxPP4m5y2H4iqhYW5r2_VH3f"
    "-T3ynjWmO0Vf4fwOyVWB8_T3u-O7goOWo3rjFXWCvDdkuXgKI578D3Wh4ubZQc6rrCfd6wHivYQh"
    "ApvqNNUa7mxgJx1alevQBRWpwAE92Av4fuomC4HDT2iObrE0ivDY6hysMqy52T-iSv8DCoTI8rD1"
    "acyVCAsgrDWs4MbY29T2hHcZUZ0yRQFm60vxW4WQRFAa3q9DY4LDSxXjtUyS5htpwr_HJkWJFys8"
    "k9vjXOBtCP1cATIsoId7HRJ0OvH61ZQOobwC3YkcaGF1dGhEYXRhWMVJlg3liA6MaHQ0Fw9kdmBb"
    "j-SuuaKGMseZXPO6gx2XY0UAAAAAuT_ZYfLmRi-xIoIAIkfeeABBAYNe4CBKc8H30FuAb8uaht6J"
    "bEQfbSBnS0SX7B6MFg8ofI92oR5lheRDJCgwY-JqB_QSJtezdhMbf8Wzt_La5N2lAQIDJiABIVgg"
    "11Yt_p_qwbKz9wOD4_T_HujzYd3jXQt_D2hYgmcjFnUiWCBFQOj2xOvfOT0lAw3J5Nyp56cnOuif"
    "xxTrv4HrqolrQA"
)
ANDROID_KEY_CLIENT_DATA_JSON = (
    "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIiwiY2hhbGxlbmdlIjoidDRMV0kwaVlKU1RXUGw5V1hVZE5oZEhBbnJQRExGOWVXQVA5bEhnbUhQOCIsIm9yaWdpbiI6Imh0dHA6Ly9sb2NhbGhvc3Q6ODAwMCIsImNyb3NzT3JpZ2luIjpmYWxzZX0"
)


def _android_key_credential():
    return {
        "id": ANDROID_KEY_CREDENTIAL_ID,
        "rawId": ANDROID_KEY_CREDENTIAL_ID,
        "response": {
            "attestationObject": ANDROID_KEY_ATTESTATION_OBJECT,
            "clientDataJSON": ANDROID_KEY_CLIENT_DATA_JSON,
        },
        "type": "public-key",
        "clientExtensionResults": {"credProps": {"rk": False}},
        "authenticatorAttachment": "platform",
    }


@pytest.fixture
def android_key_ceremony(monkeypatch):
    """Point the routes at the vector's rp, challenge and certificate time.

    The routes are not edited: the settings they read are, the options route
    is given the vector's challenge through the challenge argument webauthn
    already takes, and the X.509 store gets a fixed time. Every decode and
    check between the request and the stored row is the shipped code's.
    """
    import webauthn.helpers.validate_certificate_chain  # noqa: F401
    from OpenSSL.crypto import X509Store
    from webauthn.helpers import base64url_to_bytes
    from webauthn.registration.formats import android_key

    from app.api.v1 import auth as auth_routes

    monkeypatch.setattr(settings, "PASSKEY_RP_ID", ANDROID_KEY_RP_ID)
    monkeypatch.setattr(settings, "PASSKEY_ORIGIN", ANDROID_KEY_ORIGIN)

    real_options = auth_routes.generate_registration_options

    def options_with_the_vector_challenge(**kwargs):
        kwargs["challenge"] = base64url_to_bytes(ANDROID_KEY_CHALLENGE)
        return real_options(**kwargs)

    monkeypatch.setattr(
        auth_routes, "generate_registration_options", options_with_the_vector_challenge
    )

    chain_module = sys.modules["webauthn.helpers.validate_certificate_chain"]

    def store_at_the_vector_time():
        store = X509Store()
        store.set_time(datetime(2025, 1, 8, 0, 0, 0))
        return store

    monkeypatch.setattr(chain_module, "_generate_new_cert_store", store_at_the_vector_time)

    ceremony = SimpleNamespace(decoded=[], rewrite_key_description=None)
    real_decode = android_key.ber_decode

    def recording_decode(substrate, *args, **kwargs):
        value, rest = real_decode(substrate, *args, **kwargs)
        spec = type(kwargs.get("asn1Spec")).__name__
        ceremony.decoded.append(spec)
        if spec == "KeyDescription" and ceremony.rewrite_key_description:
            ceremony.rewrite_key_description(value)
        return value, rest

    monkeypatch.setattr(android_key, "ber_decode", recording_decode)
    return ceremony


async def _register_the_vector(client, auth_headers):
    options = await client.post("/api/v1/auth/passkeys/register/options", headers=auth_headers)
    assert options.status_code == 200, options.text
    assert options.json()["publicKey"]["challenge"] == ANDROID_KEY_CHALLENGE
    return await client.post(
        "/api/v1/auth/passkeys/register/complete",
        headers=auth_headers,
        json={
            "challenge_id": options.json()["challenge_id"],
            "credential": _android_key_credential(),
            "label": "Pixel 8a vector",
        },
    )


async def test_an_android_key_attestation_registers_through_pyasn1(
    client, auth_headers, android_key_ceremony
):
    response = await _register_the_vector(client, auth_headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"registered": True, "credential_id": ANDROID_KEY_CREDENTIAL_ID}
    # Both pyasn1 decodes ran on the device's bytes, and returned values the
    # format check accepted: the attestation certificate, then the key
    # description extension that carries the challenge and the hardware origin.
    assert android_key_ceremony.decoded == ["Certificate", "KeyDescription"]

    status_body = (
        await client.get("/api/v1/auth/passkeys/status", headers=auth_headers)
    ).json()
    assert status_body["credentials"] == 1
    assert status_body["rp_id"] == ANDROID_KEY_RP_ID


async def test_the_route_acts_on_what_pyasn1_decoded(
    client, auth_headers, android_key_ceremony
):
    """The decode is used, not only called.

    The key description carries the hash of the client data as its
    attestation challenge, and the format check compares the two. Swapping
    the decoded challenge for 32 zero bytes, after pyasn1 returns it and
    before the check reads it, must turn the same device response into a
    refusal. This one proves the route reads the decoded value; the test
    above proves the decoder returns the device's value. Each needs the
    other: an empty KeyDescription fails the first and still passes this.
    """
    from pyasn1.type.univ import OctetString

    def wrong_challenge(key_description):
        key_description["attestationChallenge"] = OctetString(bytes(32))

    android_key_ceremony.rewrite_key_description = wrong_challenge
    response = await _register_the_vector(client, auth_headers)

    assert response.status_code == 400, response.text
    assert "attestationChallenge" in response.json()["detail"]
    assert android_key_ceremony.decoded == ["Certificate", "KeyDescription"]
    status_body = (
        await client.get("/api/v1/auth/passkeys/status", headers=auth_headers)
    ).json()
    assert status_body["credentials"] == 0
