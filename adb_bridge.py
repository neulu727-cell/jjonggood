"""
ADB Bridge - Phone call detection & web notification

Runs on shop PC with phone connected via USB:
- Detects incoming calls via ADB
- Sends phone number to web app API
- Browser shows notification popup

Usage:
    python adb_bridge.py

Environment (.env file):
    RENDER_URL=https://your-app.onrender.com
    TASKER_API_KEY=your_secret_key
"""

import os
import re
import sys
import time
import subprocess
import urllib.request
import urllib.parse

# Force UTF-8 stdout for Windows embedded Python
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# === Config ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POLL_INTERVAL = 1.5
HEARTBEAT_INTERVAL = 60


def load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def find_adb():
    local_adb = os.path.join(BASE_DIR, "platform-tools", "adb.exe")
    if os.path.exists(local_adb):
        return local_adb
    try:
        subprocess.run(["adb", "version"], capture_output=True, timeout=5)
        return "adb"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def check_adb(adb_cmd):
    try:
        r = subprocess.run([adb_cmd, "devices"], capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().split("\n")
        for line in lines[1:]:
            if "\tdevice" in line:
                return True, line.split("\t")[0]
        return False, ""
    except FileNotFoundError:
        return False, ""
    except subprocess.TimeoutExpired:
        return False, ""


def send_to_web(render_url, api_key, phone_number):
    url = f"{render_url}/api/incoming-call?key={urllib.parse.quote(api_key, safe='')}"
    data = urllib.parse.urlencode({"phone": phone_number}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print("  -> Notify OK")
            else:
                print(f"  -> Notify: {resp.status}")
    except Exception as e:
        print(f"  -> Notify FAIL: {e}")


def send_heartbeat(render_url, api_key, status, device=""):
    url = f"{render_url}/api/bridge-heartbeat?key={urllib.parse.quote(api_key, safe='')}"
    data = urllib.parse.urlencode({"status": status, "device": device}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception:
        pass


def main():
    load_env()

    render_url = os.environ.get("RENDER_URL", "").rstrip("/")
    api_key = os.environ.get("TASKER_API_KEY", "")

    if not render_url:
        print("[ERROR] RENDER_URL not set. Check .env file.")
        sys.exit(1)

    if not api_key:
        print("[ERROR] TASKER_API_KEY not set. Check .env file.")
        sys.exit(1)

    adb_cmd = find_adb()
    if not adb_cmd:
        print("[ERROR] ADB not found. Check platform-tools folder.")
        sys.exit(1)

    print("=" * 50)
    print("  ADB Bridge - Phone Call Monitor")
    print(f"  ADB: {adb_cmd}")
    print(f"  Server: {render_url}")
    print(f"  Poll: {POLL_INTERVAL}s")
    print("  Exit: Ctrl+C")
    print("=" * 50)

    previous_state = 0
    last_heartbeat = 0

    while True:
        try:
            now = time.time()

            connected, device = check_adb(adb_cmd)

            if now - last_heartbeat > HEARTBEAT_INTERVAL:
                if connected:
                    send_heartbeat(render_url, api_key, "ok", device)
                    print(f"[{time.strftime('%H:%M:%S')}] heartbeat (device: {device})")
                else:
                    send_heartbeat(render_url, api_key, "no_device")
                    print(f"[{time.strftime('%H:%M:%S')}] heartbeat (no device - retrying)")
                last_heartbeat = now

            if not connected:
                time.sleep(POLL_INTERVAL)
                continue

            result = subprocess.run(
                [adb_cmd, "shell", "dumpsys", "telephony.registry"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                output = result.stdout
                state_match = re.search(r"mCallState=(\d+)", output)
                number_match = re.search(r"mCallIncomingNumber=([\d+\-]+)", output)

                if state_match:
                    current_state = int(state_match.group(1))

                    if current_state == 1 and previous_state != 1:
                        if number_match:
                            phone = number_match.group(1)
                            if phone and phone != "0":
                                ts = time.strftime("%H:%M:%S")
                                print(f"\n[{ts}] INCOMING CALL: {phone}")
                                send_to_web(render_url, api_key, phone)

                    previous_state = current_state

        except subprocess.TimeoutExpired:
            pass
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
