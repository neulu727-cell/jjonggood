"""
ADB Bridge - Phone call detection & DB backup (GUI)

Runs on shop PC with phone connected via USB:
- Detects incoming calls via ADB
- Sends phone number to web app API
- Auto-backup DB every 1 hour
- Shows status in a small GUI window

Usage:
    python adb_bridge.py

Environment (.env file):
    RENDER_URL=https://your-app.onrender.com
    TASKER_API_KEY=your_secret_key
    DATABASE_URL=postgresql://user:pass@host:port/dbname
"""

import os
import re
import sys
import time
import threading
import subprocess
import urllib.request
import urllib.parse
import tkinter as tk

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
BACKUP_INTERVAL = 3600  # 1시간
BACKUP_DIR = os.path.join(BASE_DIR, "backup")
MAX_LOG_LINES = 3


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


def restart_adb_server(adb_cmd):
    try:
        subprocess.run([adb_cmd, "kill-server"], capture_output=True, timeout=5)
        time.sleep(1)
        subprocess.run([adb_cmd, "start-server"], capture_output=True, timeout=10)
        time.sleep(1)
    except Exception:
        pass


def check_adb(adb_cmd, auto_restart=True):
    try:
        r = subprocess.run([adb_cmd, "devices"], capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().split("\n")
        for line in lines[1:]:
            if "\tdevice" in line:
                return True, line.split("\t")[0]
        if auto_restart:
            restart_adb_server(adb_cmd)
            return check_adb(adb_cmd, auto_restart=False)
        return False, ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        if auto_restart:
            restart_adb_server(adb_cmd)
            return check_adb(adb_cmd, auto_restart=False)
        return False, ""


def send_to_web(render_url, api_key, phone_number):
    url = f"{render_url}/api/incoming-call?key={urllib.parse.quote(api_key, safe='')}"
    data = urllib.parse.urlencode({"phone": phone_number}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def send_heartbeat(render_url, api_key, status, device=""):
    url = f"{render_url}/api/bridge-heartbeat?key={urllib.parse.quote(api_key, safe='')}"
    data = urllib.parse.urlencode({"status": status, "device": device}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception:
        pass


# === DB Backup ===

def run_backup(render_url, api_key):
    """서버 API로 DB 백업 다운로드. (성공여부, 메시지) 반환"""
    from datetime import datetime
    os.makedirs(BACKUP_DIR, exist_ok=True)

    now = datetime.now()
    filename = f"backup_{now.strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(BACKUP_DIR, filename)

    url = f"{render_url}/api/backup?key={urllib.parse.quote(api_key, safe='')}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            with open(filepath, "wb") as f:
                f.write(data)
            size = len(data)
            return True, f"{now.strftime('%H:%M')} ({size:,}B)"
    except Exception as e:
        return False, str(e)[:40]


# === GUI ===

class ADBBridgeGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("\U0001f4f1 \uac00\uac8c \ubaa8\ub2c8\ud130")
        self.root.geometry("300x210")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        self.connected = False
        self.server_ok = True
        self.log_lines = []
        self.running = True

        self._build_ui()

    def _build_ui(self):
        # Status area
        self.status_frame = tk.Frame(self.root, height=70)
        self.status_frame.pack(fill=tk.X)
        self.status_frame.pack_propagate(False)

        self.status_label = tk.Label(
            self.status_frame,
            text="\u26aa \uc2dc\uc791 \uc911...",
            font=("", 20, "bold"),
            fg="white",
            bg="#888888",
        )
        self.status_label.pack(fill=tk.BOTH, expand=True)

        # Info area
        info_frame = tk.Frame(self.root, padx=8, pady=4)
        info_frame.pack(fill=tk.X)

        self.time_label = tk.Label(
            info_frame, text="\ub9c8\uc9c0\ub9c9 \uc218\uc2e0: -", anchor="w", font=("", 9)
        )
        self.time_label.pack(fill=tk.X)

        self.server_label = tk.Label(
            info_frame, text="\uc11c\ubc84: \ud655\uc778 \uc911...", anchor="w", font=("", 9)
        )
        self.server_label.pack(fill=tk.X)

        self.backup_label = tk.Label(
            info_frame, text="\ubc31\uc5c5: \ub300\uae30 \uc911...", anchor="w", font=("", 9)
        )
        self.backup_label.pack(fill=tk.X)

        # Log area
        log_frame = tk.Frame(self.root, padx=8, pady=2)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_label = tk.Label(
            log_frame, text="", anchor="nw", justify=tk.LEFT,
            font=("", 8), fg="#555555",
        )
        self.log_label.pack(fill=tk.BOTH, expand=True)

    def set_connected(self, connected):
        self.connected = connected
        if connected:
            self.status_label.config(text="\U0001f7e2 \uc5f0\uacb0\ub428", bg="#2e7d32")
        else:
            self.status_label.config(text="\U0001f534 \uc5f0\uacb0 \uc548\ub428", bg="#c62828")

    def set_server_status(self, ok):
        self.server_ok = ok
        self.server_label.config(
            text="\uc11c\ubc84: \uc815\uc0c1" if ok else "\uc11c\ubc84: \uc751\ub2f5 \uc5c6\uc74c"
        )

    def set_backup_status(self, text):
        self.backup_label.config(text=f"\ubc31\uc5c5: {text}")

    def set_last_receive(self, time_str):
        self.time_label.config(text=f"\ub9c8\uc9c0\ub9c9 \uc218\uc2e0: {time_str}")

    def add_log(self, msg):
        self.log_lines.append(msg)
        if len(self.log_lines) > MAX_LOG_LINES:
            self.log_lines = self.log_lines[-MAX_LOG_LINES:]
        self.log_label.config(text="\n".join(self.log_lines))

    def update_ui(self, func, *args):
        if self.running:
            self.root.after(0, func, *args)

    def on_close(self):
        self.running = False
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()


# === Threads ===

def polling_loop(gui, adb_cmd, render_url, api_key):
    previous_state = 0
    last_heartbeat = 0
    last_device = ""
    last_adb_ok = 0
    last_restart_attempt = 0

    while gui.running:
        try:
            now = time.time()

            allow_restart = (now - last_restart_attempt) > 60
            connected, device = check_adb(adb_cmd, auto_restart=allow_restart)
            if allow_restart and not connected:
                last_restart_attempt = now
            if connected:
                last_device = device
                last_adb_ok = now

            gui.update_ui(gui.set_connected, connected)

            if now - last_heartbeat > HEARTBEAT_INTERVAL:
                if (now - last_adb_ok) < 30:
                    send_heartbeat(render_url, api_key, "ok", last_device)
                    gui.update_ui(gui.set_server_status, True)
                    ts = time.strftime("%H:%M:%S")
                    gui.update_ui(gui.add_log, f"[{ts}] heartbeat OK")
                else:
                    send_heartbeat(render_url, api_key, "no_device")
                    gui.update_ui(gui.set_server_status, True)
                    ts = time.strftime("%H:%M:%S")
                    gui.update_ui(gui.add_log, f"[{ts}] heartbeat (\ub514\ubc14\uc774\uc2a4 \uc5c6\uc74c)")
                last_heartbeat = now

            if not connected:
                time.sleep(POLL_INTERVAL)
                continue

            result = subprocess.run(
                [adb_cmd, "shell", "dumpsys", "telephony.registry"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                last_adb_ok = time.time()
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
                                gui.update_ui(gui.set_last_receive, ts)
                                gui.update_ui(gui.add_log, f"[{ts}] \uc218\uc2e0: {phone}")
                                ok = send_to_web(render_url, api_key, phone)
                                gui.update_ui(gui.set_server_status, ok)
                    previous_state = current_state

        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            ts = time.strftime("%H:%M:%S")
            gui.update_ui(gui.add_log, f"[{ts}] \uc624\ub958: {e}")

        time.sleep(POLL_INTERVAL)


def backup_loop(gui, render_url, api_key):
    while gui.running:
        gui.update_ui(gui.set_backup_status, "\ubc31\uc5c5 \uc911...")
        ok, msg = run_backup(render_url, api_key)
        if ok:
            gui.update_ui(gui.set_backup_status, f"\uc644\ub8cc {msg}")
            ts = time.strftime("%H:%M:%S")
            gui.update_ui(gui.add_log, f"[{ts}] DB \ubc31\uc5c5 \uc644\ub8cc")
        else:
            gui.update_ui(gui.set_backup_status, f"\uc2e4\ud328: {msg}")
            ts = time.strftime("%H:%M:%S")
            gui.update_ui(gui.add_log, f"[{ts}] DB \ubc31\uc5c5 \uc2e4\ud328: {msg}")

        # 1시간 대기 (10초 단위로 체크하여 종료 시 빠르게 반응)
        for _ in range(BACKUP_INTERVAL // 10):
            if not gui.running:
                return
            time.sleep(10)


def main():
    load_env()

    render_url = os.environ.get("RENDER_URL", "").rstrip("/")
    api_key = os.environ.get("TASKER_API_KEY", "")

    if not render_url or not api_key:
        root = tk.Tk()
        root.title("\uc624\ub958")
        root.geometry("300x100")
        msg = ""
        if not render_url:
            msg += "RENDER_URL \ubbf8\uc124\uc815\n"
        if not api_key:
            msg += "TASKER_API_KEY \ubbf8\uc124\uc815\n"
        msg += "\n.env \ud30c\uc77c\uc744 \ud655\uc778\ud558\uc138\uc694."
        tk.Label(root, text=msg, font=("", 11), fg="red", justify=tk.LEFT, padx=10, pady=10).pack()
        root.mainloop()
        sys.exit(1)

    adb_cmd = find_adb()
    if not adb_cmd:
        root = tk.Tk()
        root.title("\uc624\ub958")
        root.geometry("300x80")
        tk.Label(
            root,
            text="ADB\ub97c \ucc3e\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.\nplatform-tools \ud3f4\ub354\ub97c \ud655\uc778\ud558\uc138\uc694.",
            font=("", 11), fg="red", justify=tk.LEFT, padx=10, pady=10,
        ).pack()
        root.mainloop()
        sys.exit(1)

    gui = ADBBridgeGUI()

    # ADB polling thread
    threading.Thread(
        target=polling_loop,
        args=(gui, adb_cmd, render_url, api_key),
        daemon=True,
    ).start()

    # DB backup thread
    threading.Thread(
        target=backup_loop,
        args=(gui, render_url, api_key),
        daemon=True,
    ).start()

    gui.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"\n[FATAL ERROR]\n{err_msg}")
        try:
            root = tk.Tk()
            root.title("오류")
            root.geometry("400x200")
            tk.Label(root, text=f"프로그램 오류:\n\n{e}", font=("", 11),
                     fg="red", justify=tk.LEFT, padx=10, pady=10, wraplength=380).pack()
            root.mainloop()
        except Exception:
            pass
        input("Press Enter to exit...")
