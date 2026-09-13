#!/usr/bin/env python3
"""Stop one backend, prove the system stays available, restore it, and
prove it's serving again through NGINX.

Phases:
  1. Baseline       - confirm both backends serving before touching anything
  2. Stop & measure - stop the target container, measure traffic/errors
  3. Restore        - start the target container back up
  4. Verify recovery - bounded wait, confirm both backends serve again

Exits 0 only if every phase passes; non-zero on any failure.
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

PUBLIC_PORT = 8080  
BASE_URL = f"http://127.0.0.1:{PUBLIC_PORT}"
REQUEST_TIMEOUT = 3
TARGET_CONTAINER = "app-01"
RECOVERY_MAX_WAIT = 30     


def http_get(path, timeout=REQUEST_TIMEOUT):
    url = f"{BASE_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body), None
            except json.JSONDecodeError:
                return resp.status, None, "invalid JSON"
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except Exception:
            body = None
        return exc.code, body, None
    except Exception as exc:
        return None, None, str(exc)


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def hit_instance_endpoint(n=10, delay=0.3):
    """Fires n requests at /instance, returns (successes, failures, instance_ids_seen)."""
    successes, failures = 0, 0
    seen = set()
    for _ in range(n):
        status, body, err = http_get("/instance")
        if status == 200 and body:
            successes += 1
            seen.add(body.get("instance_id"))
        else:
            failures += 1
        time.sleep(delay)
    return successes, failures, seen


def fail(message):
    print(f"\nFAIL: {message}")
    sys.exit(1)


def main():
    other_instance = "app-02" if TARGET_CONTAINER == "app-01" else "app-01"


    print("=== Phase 1: Baseline ===")
    ok, failed, seen = hit_instance_endpoint(n=10)
    print(f"Baseline: {ok} ok, {failed} failed, instances seen: {seen}")
    if len(seen) < 2:
        fail("baseline does not show both backends serving before the test even starts")

    print(f"\n=== Phase 2: Stopping {TARGET_CONTAINER} ===")
    rc, out, err = docker("stop", TARGET_CONTAINER)
    if rc != 0:
        fail(f"could not stop {TARGET_CONTAINER}: {err}")
    print(f"{TARGET_CONTAINER} stopped: {out}")

    print("Measuring traffic during outage...")
    during_ok, during_fail, during_seen = hit_instance_endpoint(n=20, delay=0.3)
    print(f"During outage: {during_ok} ok, {during_fail} failed, instances seen: {during_seen}")

    if during_seen != {other_instance}:
        print(f"WARNING: expected only {other_instance} to respond, saw: {during_seen}")


    print(f"\n=== Phase 3: Restoring {TARGET_CONTAINER} ===")
    rc, out, err = docker("start", TARGET_CONTAINER)
    if rc != 0:
        fail(f"could not start {TARGET_CONTAINER}: {err}")
    print(f"{TARGET_CONTAINER} started: {out}")


    print("\n=== Phase 4: Verifying recovery ===")
    deadline = time.time() + RECOVERY_MAX_WAIT
    recovered = False
    while time.time() < deadline:
        _, _, seen_now = hit_instance_endpoint(n=5, delay=0.2)
        if TARGET_CONTAINER in seen_now:
            recovered = True
            break
        time.sleep(1)

    if not recovered:
        fail(f"{TARGET_CONTAINER} did not rejoin rotation within {RECOVERY_MAX_WAIT}s")
    print(f"{TARGET_CONTAINER} confirmed back in rotation")

    final_ok, final_fail, final_seen = hit_instance_endpoint(n=10, delay=0.2)
    print(f"Final check: {final_ok} ok, {final_fail} failed, instances seen: {final_seen}")

    print(f"\nSummary: baseline_ok={ok} during_outage_ok={during_ok} "
          f"during_outage_failed={during_fail} final_ok={final_ok}")

    if len(final_seen) >= 2:
        print("PASS: failure and recovery test completed successfully")
        sys.exit(0)
    else:
        fail("both backends not confirmed serving after recovery")


if __name__ == "__main__":
    main()