"""
Behavioural probe for the deployed soul service, run as its own process.

It lives inside deploy/soul and is run by test_deploy_soul.py in a subprocess,
never imported. Importing it in-process would put the vendored `services` tree
first on sys.path for the rest of the session, and two of those packages are
deliberately trimmed, so the platform's own tests would start importing the
wrong `services.intelligence`. A subprocess keeps that contained.

Prints one JSON object of findings on stdout. Asserts nothing itself, so the
failure messages live with the tests.
"""

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import os  # noqa: E402

os.environ["CONSOLE_TOKEN"] = "probe-token"
os.environ.pop("PINECONE_API_KEY", None)

import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(main.app, raise_server_exceptions=False)
AUTH = {"Authorization": "Bearer probe-token"}

out = {
    # Every route the app exposes, with the methods it answers on.
    "routes": sorted(
        {
            "path": r.path,
            "methods": sorted(m for m in (getattr(r, "methods", None) or []) if m != "HEAD"),
        }.__repr__()
        for r in main.app.routes
    ),
    "effect_routes": sorted(
        {
            f"{m} {r.path}"
            for r in main.app.routes
            for m in (getattr(r, "methods", None) or [])
            if m not in ("GET", "HEAD", "OPTIONS")
        }
    ),
    # A high byte in the Authorization header used to escape the gate as a 500.
    # Sent as raw bytes: httpx refuses to ascii-encode a str header, but a
    # real client can put obs-text on the wire and Starlette latin-1 decodes
    # it into the non-ascii str that used to blow up hmac.compare_digest.
    "non_ascii_auth_status": client.get(
        "/api/v1/soul/status", headers={b"Authorization": b"Bearer \xff"}
    ).status_code,
    "non_ascii_auth_recall": client.get(
        "/api/v1/soul/recall?q=hi", headers={b"Authorization": b"Bearer caf\xc3\xa9"}
    ).status_code,
    # The console is not a public page.
    "console_anonymous": client.get("/console").status_code,
    "console_wrong_token": client.get("/console?t=nope").status_code,
    "console_query_token": client.get("/console?t=probe-token").status_code,
    "console_header_token": client.get("/console", headers=AUTH).status_code,
    # Whatever the anonymous console page is, it must not be the real one.
    "anonymous_body_has_state": "const STATE" in client.get("/console").text,
    "anonymous_body_has_airtable": "app28z7XnKzjfTXwc" in client.get("/console").text,
    # A caller with no token learns nothing about the parameters.
    "recall_anonymous_no_q": client.get("/api/v1/soul/recall").status_code,
    "recall_anonymous_bad_q": client.get("/api/v1/soul/recall?q=&top_k_tee=99").status_code,
    "recall_authed_no_q": client.get("/api/v1/soul/recall", headers=AUTH).status_code,
    "status_anonymous": client.get("/api/v1/soul/status").status_code,
    # Health is open on purpose and says only whether the two are set.
    "health_anonymous": client.get("/api/v1/health").status_code,
    "health_body": client.get("/api/v1/health").json(),
    # The bare hostname has to be usable by a person holding a phone.
    "root_browser_status": client.get("/", headers={"Accept": "text/html"}).status_code,
    "root_browser_is_html": "text/html"
    in client.get("/", headers={"Accept": "text/html"}).headers["content-type"],
    "root_browser_has_paste_field": 'id="t"'
    in client.get("/", headers={"Accept": "text/html"}).text,
    "root_browser_leaks_state": "const STATE"
    in client.get("/", headers={"Accept": "text/html"}).text,
    "root_json_still_json": client.get(
        "/", headers={"Accept": "application/json"}
    ).headers["content-type"],
    # The default has to be the door, whatever the caller's Accept says or
    # does not say. These are the shapes a real client sends.
    # A stale cached page is how a fixed deploy keeps looking broken, and a
    # cacheable authenticated page is worse than stale.
    "cache_control_console_anon": client.get("/console").headers.get("cache-control"),
    "cache_control_console_authed": client.get("/console", headers=AUTH).headers.get(
        "cache-control"
    ),
    "cache_control_root": client.get("/").headers.get("cache-control"),
    "cache_control_recall": client.get(
        "/api/v1/soul/recall?q=x", headers=AUTH
    ).headers.get("cache-control"),
    "root_no_accept_is_door": 'id="t"' in client.get("/").text,
    "root_star_accept_is_door": 'id="t"'
    in client.get("/", headers={"Accept": "*/*"}).text,
    "root_safari_accept_is_door": 'id="t"'
    in client.get(
        "/",
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        },
    ).text,
    "root_chrome_accept_is_door": 'id="t"'
    in client.get(
        "/",
        headers={
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            )
        },
    ).text,
    # A closed console is a door with a paste field, not a dead end, and it
    # says which of the three walls you hit.
    "console_closed_has_paste_field": 'id="t"' in client.get("/console").text,
    "console_no_token_says_so": "No token yet" in client.get("/console").text,
    "console_bad_token_says_refused": "was refused"
    in client.get("/console?t=nope").text,
    "console_bad_token_not_confused_with_no_token": "No token yet"
    not in client.get("/console?t=nope").text,
    # Signing in once has to mean once: a top level navigation carries no
    # header, so without the cookie every home screen launch would land on
    # the door again.
    "console_cookie_opens_it": client.get(
        "/console", cookies={"devon_console": "probe-token"}
    ).status_code,
    "console_cookie_serves_the_real_console": "const STATE"
    in client.get("/console", cookies={"devon_console": "probe-token"}).text,
    "console_wrong_cookie_refused": client.get(
        "/console", cookies={"devon_console": "wrong"}
    ).status_code,
    "recall_cookie_opens_it": client.get(
        "/api/v1/soul/status", cookies={"devon_console": "probe-token"}
    ).status_code,
    # A header must win over a stale cookie, or a rotated token can never
    # be used by an API caller whose browser still holds the old one.
    "header_beats_stale_cookie": client.get(
        "/api/v1/soul/status",
        headers=AUTH,
        cookies={"devon_console": "stale-and-wrong"},
    ).status_code,
}

# With no CONSOLE_TOKEN at all the service closes rather than opening.
os.environ.pop("CONSOLE_TOKEN", None)
out["no_token_status"] = client.get("/api/v1/soul/status").status_code
out["no_token_console"] = client.get("/console").status_code
out["no_token_console_body_has_state"] = "const STATE" in client.get("/console").text
out["no_token_console_names_the_host"] = (
    "no CONSOLE_TOKEN set on the host" in client.get("/console").text
)
out["no_token_console_has_paste_field"] = 'id="t"' in client.get("/console").text
out["no_token_health"] = client.get("/api/v1/health").status_code

print(json.dumps(out))
