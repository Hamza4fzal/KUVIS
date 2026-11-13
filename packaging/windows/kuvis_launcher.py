"""KUVIS portable launcher (Windows).

Started by START_KUVIS.bat with the bundled Python. It
  1. on first run, creates a private PostgreSQL + PostGIS database inside this folder (data/pgdata) and restores
     the KUVIS results into it from data/kuvis.dump (takes a few minutes, once);
  2. starts that database on a free local port (localhost only);
  3. starts the KUVIS API, which also serves the web app, on a free local port, and opens the browser.
Closing the window or pressing Ctrl+C stops everything. Nothing is installed on the computer and nothing outside
this folder is changed.
"""

from __future__ import annotations

import os
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
PG_BIN = HERE / "runtime" / "pgsql" / "bin"
DATA = HERE / "data"
PGDATA = DATA / "pgdata"
DUMP = DATA / "kuvis.dump"
PWFILE = DATA / "db_password.txt"
RESTORED = DATA / "restore.ok"
RUNNING = DATA / "running_url.txt"
LOGS = DATA / "logs"
DB_USER = DB_NAME = "kuvis"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def say(msg: str = "") -> None:
    print(msg, flush=True)


def fail(msg: str) -> None:
    say("\n  ERROR: " + msg)
    say(f"  Logs are in {LOGS}")
    raise SystemExit(1)


def pg(tool: str, *args: str, check: bool = True, env: dict | None = None, quiet: bool = True):
    exe = PG_BIN / f"{tool}.exe"
    r = subprocess.run([str(exe), *args], capture_output=True, text=True, env=env, creationflags=NO_WINDOW)
    if check and r.returncode != 0:
        (LOGS / f"{tool}.err.log").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
        fail(f"{tool} failed:\n{(r.stderr or r.stdout).strip()[-1500:]}")
    return r


def free_port(preferred: int) -> int:
    for port in [preferred, *range(preferred + 1, preferred + 200)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    fail(f"no free port near {preferred}")


def pg_running() -> bool:
    return (PGDATA / "postmaster.pid").exists() and pg("pg_ctl", "status", "-D", str(PGDATA), check=False).returncode == 0


def pg_stop() -> None:
    if pg_running():
        pg("pg_ctl", "stop", "-D", str(PGDATA), "-m", "fast", "-w", check=False)


def pg_start(port: int) -> None:
    # The server inherits pg_ctl's stdout/stderr, so they must not be pipes (reading a pipe would wait for the
    # server to exit); send them to a log file instead.
    out = LOGS / "pg_ctl.log"
    with open(out, "w", encoding="utf-8") as f:
        r = subprocess.run([str(PG_BIN / "pg_ctl.exe"), "start", "-D", str(PGDATA), "-l", str(LOGS / "postgres.log"),
                            "-w", "-t", "120", "-o", f"-p {port} -c listen_addresses=localhost"],
                           stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    if r.returncode != 0:
        fail("the database did not start:\n" + out.read_text(encoding="utf-8", errors="replace")[-1500:])


def db_env(port: int) -> dict:
    return {**os.environ, "PGPASSWORD": PWFILE.read_text(encoding="utf-8").strip(), "PGHOST": "localhost",
            "PGPORT": str(port), "PGUSER": DB_USER}


def first_run_setup(port: int) -> None:
    if not DUMP.exists():
        fail(f"database file {DUMP} is missing - re-extract the release zip")
    if not (PGDATA / "PG_VERSION").exists():
        say("  First start: creating the local database (one time only) ...")
        PWFILE.write_text(secrets.token_urlsafe(24), encoding="utf-8")
        pg("initdb", "-D", str(PGDATA), "-U", DB_USER, f"--pwfile={PWFILE}", "--auth=scram-sha-256",
           "-E", "UTF8", "--locale=C", "--no-instructions")
    pg_start(port)
    env = db_env(port)
    say("  Loading the KUVIS results into the database (about 1-3 minutes) ...")
    pg("psql", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-q", "-c", f"DROP DATABASE IF EXISTS {DB_NAME}", env=env)
    pg("psql", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-q", "-c", f"CREATE DATABASE {DB_NAME}", env=env)
    r = pg("pg_restore", "-d", DB_NAME, "--no-owner", "--no-acl", "-j", "4", str(DUMP), check=False, env=env)
    (LOGS / "restore.log").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    n = pg("psql", "-d", DB_NAME, "-Atc", "SELECT count(*) FROM kuvis.spatial_cells", check=False, env=env)
    if n.returncode != 0 or not n.stdout.strip().isdigit() or int(n.stdout.strip()) == 0:
        fail("the database restore did not complete (see restore.log)")
    RESTORED.write_text(n.stdout.strip(), encoding="utf-8")
    say(f"  Database ready ({int(n.stdout.strip()):,} grid cells).")


def open_browser_when_ready(url: str) -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.5)
    say(f"\n  KUVIS is running:  {url}")
    say("  (keep this window open; press Ctrl+C or close it to stop)\n")
    if not os.getenv("KUVIS_NO_BROWSER"):
        webbrowser.open(url)


def already_running() -> str | None:
    """URL of a KUVIS started from this folder that is still answering, if any."""
    if not RUNNING.exists():
        return None
    url = RUNNING.read_text(encoding="utf-8").strip()
    try:
        with urllib.request.urlopen(url + "/health", timeout=3) as r:
            return url if r.status == 200 else None
    except Exception:
        return None


def main() -> None:
    os.chdir(HERE)
    LOGS.mkdir(parents=True, exist_ok=True)
    say("=" * 64 + "\n  KUVIS - Karachi Urban Vulnerability Intelligence System\n" + "=" * 64)
    if not PG_BIN.exists():
        fail("runtime/pgsql is missing - re-extract the release zip")
    url = already_running()
    if url:  # double-clicked again while KUVIS is open: just show it
        say(f"\n  KUVIS is already running in another window: {url}\n  Opening it in the browser.")
        if not os.getenv("KUVIS_NO_BROWSER"):
            webbrowser.open(url)
        time.sleep(3)
        return

    pg_stop()  # left over from a window that was closed without stopping
    db_port = free_port(55433)
    if not RESTORED.exists():
        first_run_setup(db_port)
    else:
        say("  Starting the database ...")
        pg_start(db_port)

    os.environ.update({"KUVIS_DB_HOST": "localhost", "KUVIS_DB_PORT": str(db_port), "KUVIS_DB_NAME": DB_NAME,
                       "KUVIS_DB_USER": DB_USER, "KUVIS_DB_PASSWORD": PWFILE.read_text(encoding="utf-8").strip(),
                       "KUVIS_STATIC_DIR": str(HERE / "frontend" / "dist")})
    app_port = free_port(int(os.getenv("KUVIS_PORT", "8000")))
    url = f"http://localhost:{app_port}"

    def shutdown(*_):
        say("\n  Stopping KUVIS ...")
        RUNNING.unlink(missing_ok=True)
        pg_stop()
        os._exit(0)

    if hasattr(signal, "SIGBREAK"):  # closing the console window arrives as SIGBREAK on Windows
        signal.signal(signal.SIGBREAK, shutdown)

    sys.path.insert(0, str(HERE))
    say("  Starting the KUVIS server ...")
    try:
        import uvicorn
        from backend.app.main import app
        threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
        RUNNING.write_text(url, encoding="utf-8")
        uvicorn.run(app, host="127.0.0.1", port=app_port, log_level="warning")
    finally:
        RUNNING.unlink(missing_ok=True)
        say("\n  Stopping the database ...")
        pg_stop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pg_stop()
