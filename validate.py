#!/usr/bin/env python3
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

PUBLIC_PORT = 8080  
BASE_URL = f"http://127.0.0.1:{PUBLIC_PORT}"
REQUEST_TIMEOUT = 3
READY_MAX_WAIT = 30 
BACKEND_NETWORK = "barq-assessment_backend"

results = []


def record(name, passed, detail):
    results.append((name, passed, detail))
    tag = "PASS" if passed else "FAIL"
    print(f"[{tag}] {name} - {detail}")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def http_get(path, timeout=REQUEST_TIMEOUT):
    """Returns (status_code, parsed_json_or_None, error_or_None)."""
    url = f"{BASE_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body), None
            except json.JSONDecodeError:
                return resp.status, None, "response was not valid JSON"
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except Exception:
            body = None
        return exc.code, body, None
    except Exception as exc:
        return None, None, str(exc)


def http_post(path, payload, timeout=REQUEST_TIMEOUT):
    """Returns (status_code, parsed_json_or_None, error_or_None)."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body), None
            except json.JSONDecodeError:
                return resp.status, None, "response was not valid JSON"
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except Exception:
            body = None
        return exc.code, body, None
    except Exception as exc:
        return None, None, str(exc)


# ---------------------------------------------------------------------------
# Functional / endpoint checks
# ---------------------------------------------------------------------------

def check_endpoint(name, path, expected_status=200):
    status, body, err = http_get(path)
    if err:
        record(name, False, f"request failed: {err}")
        return
    if status != expected_status:
        record(name, False, f"expected status {expected_status}, got {status}")
        return
    record(name, True, f"status {status}, body keys: {list(body.keys()) if body else 'none'}")


def check_ready_with_wait():
    deadline = time.time() + READY_MAX_WAIT
    last_body = None
    while time.time() < deadline:
        status, body, err = http_get("/ready")
        last_body = body
        if status == 200 and body and body.get("status") == "ready":
            record("ready_endpoint", True, f"ready within wait window: {body.get('dependencies')}")
            return
        time.sleep(1)
    record("ready_endpoint", False, f"not ready after {READY_MAX_WAIT}s, last body: {last_body}")


def check_both_backends_serving(samples=10):
    seen = set()
    for _ in range(samples):
        _, body, err = http_get("/instance")
        if body:
            seen.add(body.get("instance_id"))
    passed = len(seen) >= 2
    record("both_backends_serving", passed, f"saw instance_ids over {samples} requests: {seen}")


def check_records_get():
    status, body, err = http_get("/records")
    if err or status != 200 or "records" not in (body or {}):
        record("records_get", False, f"status={status} err={err} body={body}")
        return
    record("records_get", True, f"status 200, {len(body['records'])} record(s) returned")


def check_records_post():
    title = f"validate-check-{int(time.time())}"
    status, body, err = http_post("/records", {"title": title})
    if err or status != 201 or not body or "record" not in body:
        record("records_post", False, f"status={status} err={err} body={body}")
        return
    created_title = body["record"].get("title")
    record("records_post", created_title == title,
           f"status 201, created record: {body['record']}")


def check_counter_increments():
    _, first, err1 = http_get("/counter")
    _, second, err2 = http_get("/counter")
    if err1 or err2 or not first or not second:
        record("counter_increments", False, f"err1={err1} err2={err2}")
        return
    a, b = first.get("counter"), second.get("counter")
    record("counter_increments", isinstance(a, int) and isinstance(b, int) and b > a,
           f"counter went {a} -> {b}")


# ---------------------------------------------------------------------------
# prohibited ports and network isolation
# ---------------------------------------------------------------------------

def check_no_published_port(container, internal_port):
    """Fails if the container has a host port mapped for internal_port."""
    result = subprocess.run(["docker", "port", container], capture_output=True, text=True)
    if result.returncode != 0:
        record(f"{container}_port_not_published", False,
               f"docker port command failed: {result.stderr.strip()}")
        return
    output = result.stdout.strip()
    exposed = str(internal_port) in output
    record(f"{container}_port_not_published", not exposed,
           f"docker port {container} -> '{output or '(empty)'}'")


def check_only_nginx_published():
    check_no_published_port("postgres", 5432)
    check_no_published_port("redis", 6379)
    check_no_published_port("app-01", 8080)
    check_no_published_port("app-02", 8080)

    result = subprocess.run(["docker", "port", "nginx"], capture_output=True, text=True)
    has_port = bool(result.stdout.strip())
    record("nginx_port_published", has_port, f"docker port nginx -> '{result.stdout.strip()}'")


def check_nginx_not_on_backend():
    result = subprocess.run(
        ["docker", "network", "inspect", BACKEND_NETWORK,
         "--format", "{{range .Containers}}{{.Name}} {{end}}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        record("nginx_isolated_from_backend", False,
               f"network inspect failed: {result.stderr.strip()}")
        return
    members = result.stdout.split()
    nginx_present = "nginx" in members
    record("nginx_isolated_from_backend", not nginx_present,
           f"backend network members: {members}")


def check_backend_is_internal():
    result = subprocess.run(
        ["docker", "network", "inspect", BACKEND_NETWORK, "--format", "{{.Internal}}"],
        capture_output=True, text=True,
    )
    is_internal = result.stdout.strip() == "true"
    record("backend_network_is_internal", is_internal,
           f"backend network Internal={result.stdout.strip()}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Validating BARQ environment at {BASE_URL}\n")

    check_endpoint("root_endpoint", "/")
    check_endpoint("health", "/health")
    check_ready_with_wait()
    check_both_backends_serving()
    check_records_get()
    check_records_post()
    check_counter_increments()
    check_only_nginx_published()
    check_nginx_not_on_backend()
    check_backend_is_internal()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED CHECKS:")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
        sys.exit(1)

    print("ALL CHECKS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()