"""Build the portable Windows release of KUVIS (a single zip that runs on any 64-bit Windows 10/11 PC).

    .venv/Scripts/python scripts/build_release.py [--version 1.0.0] [--no-zip] [--skip-frontend]

Needs, on the build machine: the running development database (scripts/db.sh start), the portable PostgreSQL +
PostGIS binaries in ../_tools/pgsql, the uv-managed CPython 3.12 used by .venv, uv, and npm.
Output: ../release/KUVIS-<version>-windows-x64/ and ../release/KUVIS-<version>-windows-x64.zip

Layout of the release (see packaging/windows/README.txt):
    START_KUVIS.bat, STOP_KUVIS.bat, kuvis_launcher.py, README.txt
    backend/            API source (serves the built web app too)
    frontend/dist/      compiled web app
    data/kuvis.dump     pg_dump (custom format) of the KUVIS database
    runtime/python/     relocatable CPython 3.12 + only the server's packages
    runtime/pgsql/      PostgreSQL + PostGIS (bin, lib, share) + the VC++ runtime DLLs
    docs/               reports and documentation
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(os.getenv("KUVIS_TOOLS", ROOT.parent / "_tools"))
PGSQL = TOOLS / "pgsql"
PKG = ROOT / "packaging" / "windows"

# Only what the API needs at run time, pinned to the versions the project was tested with.
RUNTIME_REQUIREMENTS = [
    "fastapi==0.162.4", "starlette==1.10.0", "pydantic==2.14.3", "uvicorn[standard]==0.54.0",
    "psycopg[binary]==3.3.8", "psycopg-pool==3.3.3", "numpy==2.5.4", "pandas==3.1.1", "scipy==1.18.1",
]
VC_DLLS = ["vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "concrt140.dll"]
DOCS = ["research/reports/FINAL_REPORT.md", "research/RESULTS.md", "research/RESEARCH_METHODOLOGY.md",
        "research/DATA_SOURCES.md", "research/DATA_AVAILABILITY.md", "docs/ARCHITECTURE.md", "README.md"]
EXTRA_DOCS = ["docs/KUVIS_Project_Guide.docx"]  # included when present


def run(cmd: list[str], **kw) -> None:
    print("  $", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def env_file() -> dict:
    out = {}
    f = ROOT / ".env"
    for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def base_python() -> Path:
    cfg = (ROOT / ".venv" / "pyvenv.cfg").read_text(encoding="utf-8")
    home = next(line.split("=", 1)[1].strip() for line in cfg.splitlines() if line.startswith("home"))
    return Path(home)


def copytree(src: Path, dst: Path, ignore=None) -> None:
    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.0.0")
    ap.add_argument("--no-zip", action="store_true")
    ap.add_argument("--skip-frontend", action="store_true", help="reuse the existing frontend/dist")
    a = ap.parse_args()

    name = f"KUVIS-{a.version}-windows-x64"
    out = ROOT.parent / "release" / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    pyc = shutil.ignore_patterns("__pycache__", "*.pyc")

    print("[1/6] web app")
    if not a.skip_frontend:
        run(["npm", "run", "build"], cwd=ROOT / "frontend", shell=True)
    copytree(ROOT / "frontend" / "dist", out / "frontend" / "dist")

    print("[2/6] API + launcher + docs")
    copytree(ROOT / "backend", out / "backend", ignore=pyc)
    for f in ["kuvis_launcher.py", "START_KUVIS.bat", "STOP_KUVIS.bat", "README.txt"]:
        shutil.copy2(PKG / f, out / f)
    (out / "docs").mkdir()
    for d in DOCS + [p for p in EXTRA_DOCS if (ROOT / p).exists()]:
        shutil.copy2(ROOT / d, out / "docs" / Path(d).name)

    print("[3/6] database dump")
    (out / "data").mkdir()
    e = env_file()
    env = {**os.environ, "PGPASSWORD": e.get("KUVIS_DB_PASSWORD", "")}
    run([PGSQL / "bin" / "pg_dump.exe", "-h", e.get("KUVIS_DB_HOST", "localhost"), "-p", e.get("KUVIS_DB_PORT", "5433"),
         "-U", e.get("KUVIS_DB_USER", "kuvis"), "-d", e.get("KUVIS_DB_NAME", "kuvis"), "-Fc", "-Z", "9",
         "--no-owner", "--no-acl", "-f", out / "data" / "kuvis.dump"], env=env)

    print("[4/6] PostgreSQL + PostGIS runtime")
    for sub in ["bin", "lib", "share"]:
        copytree(PGSQL / sub, out / "runtime" / "pgsql" / sub)
    sysdir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    for dll in VC_DLLS:  # app-local VC++ runtime, so PCs without the redistributable still work
        if (sysdir / dll).exists() and not (out / "runtime" / "pgsql" / "bin" / dll).exists():
            shutil.copy2(sysdir / dll, out / "runtime" / "pgsql" / "bin" / dll)

    print("[5/6] Python runtime")
    py = out / "runtime" / "python"
    copytree(base_python(), py, ignore=shutil.ignore_patterns("__pycache__", "test", "tests", "idlelib", "tkinter",
                                                              "turtledemo", "tcl", "site-packages"))
    (py / "Lib" / "site-packages").mkdir(exist_ok=True)
    (py / "Lib" / "EXTERNALLY-MANAGED").unlink(missing_ok=True)
    run(["uv", "pip", "install", "--python", py / "python.exe", "--break-system-packages", "--no-cache",
         "--link-mode", "copy", *RUNTIME_REQUIREMENTS])
    run([py / "python.exe", "-I", "-c", "import fastapi, uvicorn, psycopg, psycopg_pool, numpy, pandas, scipy.spatial; "
         "print('runtime imports OK')"])

    print("[6/6] zip")
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"  folder size {size / 1e6:,.0f} MB")
    if not a.no_zip:
        z = out.with_suffix(".zip")
        z.unlink(missing_ok=True)
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for f in sorted(out.rglob("*")):
                if f.is_file():
                    zf.write(f, Path(name) / f.relative_to(out))
        print(f"  wrote {z} ({z.stat().st_size / 1e6:,.0f} MB)")


if __name__ == "__main__":
    sys.exit(main())
