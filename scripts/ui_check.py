"""Visual smoke test: drive the installed Microsoft Edge with Playwright, visit every page, wait for data and map
tiles, collect console errors and failed requests, and save screenshots.

Usage: python scripts/ui_check.py [out_dir] [base_url]
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "ui_screens")
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:5173"
PAGES = ["/", "/explore", "/heat", "/flood", "/urbanization", "/infrastructure", "/vulnerability",
         "/discoveries", "/history", "/compare", "/methodology", "/sources"]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True,
                                    args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        errors = []
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: errors.append(f"requestfailed: {r.url} {r.failure}"))
        page.on("response", lambda r: errors.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None)
        for path in PAGES:
            errors.clear()
            page.goto(BASE + path, wait_until="networkidle", timeout=90_000)
            page.wait_for_timeout(4000)  # let MapLibre draw tiles after the network settles
            name = path.strip("/") or "overview"
            page.screenshot(path=str(OUT / f"{name}.png"))
            # requests the client cancelled itself (navigation, MapLibre dropping off-screen tiles) are not failures
            errors[:] = [e for e in errors if "AbortError" not in e and "net::ERR_ABORTED" not in e]
            if errors:
                problems.append((path, list(errors)))
            print(f"{path:<18} {'OK' if not errors else f'{len(errors)} problem(s)'}")
        # interaction: open a location report on the explore map (click a cell in central Karachi)
        page.goto(BASE + "/explore", wait_until="networkidle")
        page.wait_for_timeout(3000)
        page.mouse.click(1000, 760)
        page.wait_for_timeout(5000)
        page.screenshot(path=str(OUT / "explore_report.png"))
        report_open = page.locator("text=Location intelligence report").count() > 0
        print("report panel open:", report_open)
        if not report_open:
            problems.append(("/explore report", ["report panel did not open after clicking a cell"]))
        else:
            # PDF export: the download must arrive, start with the PDF magic bytes and be non-trivial in size
            with page.expect_download(timeout=60_000) as dl:
                page.get_by_role("button", name="PDF").click()
            pdf_path = OUT / dl.value.suggested_filename
            dl.value.save_as(pdf_path)
            head = pdf_path.read_bytes()[:5]
            size = pdf_path.stat().st_size
            ok = head == b"%PDF-" and size > 20_000
            print(f"pdf export: {pdf_path.name} {size / 1024:.0f} KB {'OK' if ok else 'INVALID'}")
            if not ok:
                problems.append(("/explore pdf", [f"invalid PDF: header {head!r}, {size} bytes"]))
        browser.close()
    for path, errs in problems:
        print(f"\n{path}:")
        for e in errs[:8]:
            print("   ", e[:220])
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
