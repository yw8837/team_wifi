"""Check the public API and restart only its connector after a confirmed tunnel outage."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HOST = "moduyuga-api.yeolmaeapps.kr"
ROOT = Path.home() / "Team_Wifi"
RUNTIME = ROOT / ".runtime/cloudflare"
STATE = RUNTIME / "watchdog-last-attempt"
INTERVAL = 30
THRESHOLD = 3
COOLDOWN = 1800


def probe(url, host=None):
    headers = {"User-Agent": "ModuYuga-Health/1.0", "Accept": "application/json", "Cache-Control": "no-cache"}
    if host:
        headers["Host"] = host
    try:
        with urlopen(Request(url, headers=headers), timeout=6) as response:
            return response.status, response.read(8192)
    except HTTPError as error:
        with error:
            try:
                return error.code, error.read(32768)
            except OSError:
                return error.code, b""
    except OSError:
        return 0, b""


def payload(response):
    try:
        data = json.loads(response[1])
        return data if isinstance(data, dict) else {}
    except (UnicodeError, ValueError):
        return {}


def healthy(response):
    data = payload(response)
    return response[0] == 200 and data.get("status") == "ok" and data.get("mode") == "public-release"


def classify(public, origin, connector):
    if healthy(public):
        return "healthy"
    if not healthy(origin):
        return "origin-unavailable"
    status, body = public
    if status == 530 and b"1033" in body:
        return "tunnel-disconnected"
    if status in (0, 502, 503, 504, 530):
        if connector[0] == 503 or payload(connector).get("readyConnections") == 0:
            return "tunnel-disconnected"
    return "public-check-inconclusive"


def check():
    public = probe(f"https://{HOST}/api/health")
    if healthy(public):
        return "healthy"
    return classify(public, probe("http://127.0.0.1:8000/api/health", HOST),
                    probe("http://127.0.0.1:20241/ready"))


def should_restart(streak, timestamp, last_attempt):
    return streak >= THRESHOLD and timestamp - last_attempt >= COOLDOWN


def monitor():
    last_attempt = float(STATE.read_text()) if STATE.exists() else 0
    previous, streak = None, 0
    while True:
        status = check()
        if status != previous:
            print(status, flush=True)
            previous = status
        streak = streak + 1 if status == "tunnel-disconnected" else 0
        timestamp = time.time()
        if should_restart(streak, timestamp, last_attempt):
            temporary = STATE.with_suffix(".tmp")
            temporary.write_text(str(timestamp))
            os.replace(temporary, STATE)
            last_attempt, streak = timestamp, 0
            command = [str(ROOT / ".venv/bin/supervisorctl"), "-c", str(RUNTIME / "supervisord.conf"),
                       "restart", "moduyuga-cloudflare"]
            try:
                result = subprocess.run(command, timeout=45, check=False, capture_output=True)
                print(f"connector restart exit={result.returncode}", flush=True)
            except (OSError, subprocess.TimeoutExpired):
                print("connector restart command unavailable", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        status = check()
        print(status)
        sys.exit(0 if status == "healthy" else 1)
    monitor()
