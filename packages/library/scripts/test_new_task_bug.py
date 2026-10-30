"""
Reproduction script for the "新任务行校验永远 4/4 missing" bug.

Usage:
    python scripts/test_new_task_bug.py [--port 5000] [--url http://127.0.0.1:5000/]

Drives a real Chromium via Playwright through the actual UI flow:
  1. open /
  2. switch to dim page (维表)
  3. click +新增 on tasks tab (optionally after typing 'test' into the search)
  4. fill product / task / tool / process
  5. screenshot after each fill + probe dimPageState.tasks.rows and tr.data-key

Writes screenshots to scripts/shots/ and prints a structured JSON trace.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "scripts" / "shots"
SHOTS.mkdir(parents=True, exist_ok=True)


PROBE_JS = r"""
() => {
  const tr = document.querySelector('tr[data-key^="__new_"]');
  const hint = tr ? tr.querySelector('.task-row-hint') : null;
  const rows = window.dimPageState && window.dimPageState.tasks && window.dimPageState.tasks.rows;
  const newRow = rows ? rows.find(r => r._tmpKey) : null;
  const searchEl = document.getElementById('dimSearchTasks');
  const allNewTrs = document.querySelectorAll('tr[data-key^="__new_"]');
  const inputs = tr
    ? Array.from(tr.querySelectorAll('input[data-field]')).map(i => ({
        field: i.dataset.field,
        value: i.value,
        type: i.type || null,
        cls: i.className || '',
        hiddenVal: (tr.querySelector('input.searchable-sel-val[data-field="' + i.dataset.field + '"]') || {}).value,
      }))
    : [];
  return {
    trFound: !!tr,
    trKey: tr ? tr.dataset.key : null,
    newTrCount: allNewTrs.length,
    hintText: hint ? hint.textContent : null,
    hintHtml: hint ? hint.outerHTML : null,
    newRowFields: newRow ? {
      product: newRow.product,
      task: newRow.task,
      tool: newRow.tool,
      process: newRow.process,
      difficulty: newRow.difficulty,
      task_id: newRow.task_id,
      _tmpKey: newRow._tmpKey,
    } : null,
    rowsCount: rows ? rows.length : null,
    rowsSample: rows ? rows.slice(0, 3).map(r => ({ primary: r[r._tmpKey ? '_tmpKey' : (window.dimPageState.tasks.schema[0])], keys: Object.keys(r) })) : null,
    filteredSearch: searchEl ? searchEl.value : null,
    rowInputs: inputs,
    dimRenderTableType: typeof window.dimRenderTable,
    dimAddRowType: typeof window.dimAddRow,
    dimRowInputType: typeof window.dimRowInput,
    _taskRefreshRowHintType: typeof window._taskRefreshRowHint,
    _uiFieldsType: typeof window._uiFields,
    _capType: typeof window._cap,
    _taskValidateRowType: typeof window._taskValidateRow,
  };
}
"""


def switch_to_tasks_page(page):
    """Each dim table is its own top-level page in this app. Click the '📝 任务' tab."""
    candidates = [
        "[data-page='tasks']",
        "button.tab[data-page='tasks']",
        "button:has-text('任务')",
    ]
    for sel in candidates:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                el.click(timeout=2000)
                page.wait_for_timeout(800)
                return f"clicked({sel})"
        except Exception:
            pass
    page.evaluate("switchPage('tasks')")
    page.wait_for_timeout(800)
    return "fallback-evaluate-switchPage('tasks')"


def fill_field(page, field, value, shot_n):
    page.evaluate(
        """({field, value}) => {
          const tr = document.querySelector('tr[data-key^="__new_"]');
          if (!tr) { console.warn('no new tr to fill', field); return false; }
          const input = tr.querySelector(`input[data-field="${field}"]`);
          if (!input) { console.warn('no input for field', field); return false; }
          input.focus();
          input.value = value;
          // dispatch input event so oninput="dimRowInput(...)" fires
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
          return true;
        }""",
        {"field": field, "value": value},
    )
    page.wait_for_timeout(250)
    page.screenshot(path=str(SHOTS / f"shot_{shot_n:02d}_after_{field}.png"), full_page=True)


def run_scenario(page, label, prefilter):
    print(f"\n========== SCENARIO: {label} (prefilter={prefilter!r}) ==========")
    page.goto("http://127.0.0.1:5000/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1000)

    # initial probe
    init = page.evaluate(PROBE_JS)
    print("[init probe]")
    safe_init = json.loads(json.dumps(init, ensure_ascii=True))
    print(json.dumps(safe_init, indent=2))

    nav_info = switch_to_tasks_page(page)
    print(f"[dim nav] {nav_info}")
    page.wait_for_timeout(500)
    page.screenshot(path=str(SHOTS / f"shot_00_after_dim_nav_{label}.png"), full_page=True)

    if prefilter:
        # type 'test' into search
        search_sel = "#dimSearchTasks"
        try:
            page.fill(search_sel, prefilter)
            page.wait_for_timeout(500)
            page.screenshot(path=str(SHOTS / f"shot_00_prefilter_{label}.png"), full_page=True)
            probe = page.evaluate(PROBE_JS)
            print(f"[after filter '{prefilter}'] visible rows in DOM? hint={probe.get('hintText')} trFound={probe.get('trFound')}")
        except Exception as e:
            print(f"[prefilter failed] {e}")

    # click "+ 新增"
    add_clicked = False
    for sel in [
        "button:has-text('+ 新增')",
        "button:has-text('新增')",
        "[onclick*=\"dimAddRow('tasks')\"]",
        "[onclick*='dimAddRow(\"tasks\")']",
        "button:has-text('+新增')",
    ]:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                el.click(timeout=2000)
                add_clicked = True
                print(f"[add click] ok via {sel}")
                break
        except Exception:
            pass
    if not add_clicked:
        # try direct evaluate
        try:
            page.evaluate("dimAddRow('tasks')")
            print("[add click] via dimAddRow('tasks') evaluate")
            add_clicked = True
        except Exception as e:
            print(f"[add click] FAILED: {e}")
    page.wait_for_timeout(800)
    page.screenshot(path=str(SHOTS / f"shot_00_after_add_{label}.png"), full_page=True)

    probe = page.evaluate(PROBE_JS)
    print("[probe after add]")
    safe = json.loads(json.dumps(probe, ensure_ascii=True))
    print(json.dumps(safe, indent=2))

    fields = ["product", "task", "tool", "process"]
    for i, fld in enumerate(fields, start=1):
        fill_field(page, fld, f"{fld.capitalize()}A_{label}", shot_n=i)
        probe = page.evaluate(PROBE_JS)
        print(f"\n[after fill {fld}]")
        safe_probe = json.loads(json.dumps({
            "hint": probe.get("hintText"),
            "trKey": probe.get("trKey"),
            "newRowFields": probe.get("newRowFields"),
            "rowInputs": probe.get("rowInputs"),
        }, ensure_ascii=True))
        print(json.dumps(safe_probe, indent=2))

    return probe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--url", default=None)
    ap.add_argument("--headless", action="store_true", default=True)
    ap.add_argument("--headed", dest="headless", action="store_false")
    args = ap.parse_args()

    console_msgs = []
    page_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = ctx.new_page()
        page.on("console", lambda msg: console_msgs.append({"type": msg.type, "text": msg.text}))
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        # scenario A: no filter
        probe_a = run_scenario(page, label="nofilter", prefilter=None)
        # scenario B: with filter 'test'
        probe_b = run_scenario(page, label="filtered", prefilter="test")

        # try to dump console / errors
        with open(SHOTS / "console.log", "w", encoding="utf-8") as f:
            for m in console_msgs:
                f.write(f"[{m['type']}] {m['text']}\n")
        with open(SHOTS / "page_errors.log", "w", encoding="utf-8") as f:
            for e in page_errors:
                f.write(e + "\n")

        # save final probes
        with open(SHOTS / "probe_A.json", "w", encoding="utf-8") as f:
            json.dump(probe_a, f, ensure_ascii=False, indent=2)
        with open(SHOTS / "probe_B.json", "w", encoding="utf-8") as f:
            json.dump(probe_b, f, ensure_ascii=False, indent=2)

        # final summary
        print("\n=========== FINAL SUMMARY ===========")
        print(f"page errors count: {len(page_errors)}")
        for e in page_errors:
            print(f"  ERR: {e}")
        interesting_console = [m for m in console_msgs if m["type"] in ("error", "warning")]
        print(f"console error/warn count: {len(interesting_console)}")
        for m in interesting_console[-30:]:
            print(f"  [{m['type']}] {m['text']}")

        browser.close()


if __name__ == "__main__":
    main()