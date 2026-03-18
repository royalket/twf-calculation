"""
main.py — Pipeline orchestrator
================================
Runs the full India tourism footprint pipeline.

Usage (CLI)
-----------
    python main.py --water               # water pipeline only
    python main.py --energy              # energy pipeline only
    python main.py --all                 # water + energy + combined report
    python main.py --steps build_io coefficients indirect
    python main.py --stressor energy --steps indirect sda
    python main.py --list-steps

Usage (interactive — no args)
------------------------------
    python main.py                       # launches interactive menu

Steps (post-merge naming)
--------------------------
    build_io        — build_io.py              (SUT → L)
    demand          — build_demand.py          (TSA demand vectors)
    coefficients    — build_coefficients.py    (F.txt → SUT 140, water + energy)
    indirect        — indirect.py              (C×L×Y, water + energy)
    direct          — direct.py                (activity-based direct TWF)
    outbound        — outbound.py              (outbound footprint + net balance)
    sda             — decompose.py             (SDA + MC + supply-chain)
    report          — compare.py               (cross-year report + Markdown)
    visualise       — visualise.py             (all charts)
    validate        — validate_outputs.py      (sanity checks)

TODO-1: Remove sys.path.insert() after packaging with pyproject.toml + pip install -e .
        Replace with proper package imports.
TODO-2: Replace __import__ in step registry with importlib.import_module.
"""

from __future__ import annotations
import argparse
import importlib
import sys
import time
import traceback
from pathlib import Path

# TODO-1: remove after packaging
sys.path.insert(0, str(Path(__file__).parent))

from config import DIRS, STUDY_YEARS, STRESSORS
from utils import Logger, Timer, section, ok, warn, table_str


# ══════════════════════════════════════════════════════════════════════════════
# STEP REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

def _get_step_fns() -> dict:
    """
    Lazy import all step run() functions.

    Post-merge file mapping (6 files → 3):
        build_coefficients.py  replaces  build_water_coefficients.py +
                                          build_energy_coefficients.py
        indirect.py            replaces  calculate_indirect_twf.py +
                                          calculate_indirect_energy.py
        outbound.py            replaces  outbound_twf.py + energy.py

    Renamed (no merge):
        build_io.py            ← build_io_tables.py
        build_demand.py        ← build_tourism_demand.py
        direct.py              ← calculate_direct_twf.py
        decompose.py           ← calculate_sda_mc.py
        compare.py             ← compare_years.py
        visualise.py           ← visualise_results.py

    TODO-2: Replace __import__ with importlib.import_module(name).run.
    """
    def _mod(name):
        """Lazy module importer — avoids importing all modules at startup."""
        return importlib.import_module(name)

    return {
        # ── IO + demand ──────────────────────────────────────────────────────
        "build_io":     lambda stressor, **kw: _mod("build_io").run(**kw),
        "demand":       lambda stressor, **kw: _mod("build_demand").run(**kw),

        # ── Merged stressor-agnostic steps ──────────────────────────────────
        # build_coefficients.py accepts stressor="water"|"energy"
        "coefficients": lambda stressor, **kw: _mod("build_coefficients").run(stressor=stressor, **kw),
        # indirect.py accepts stressor="water"|"energy"
        "indirect":     lambda stressor, **kw: _mod("indirect").run(stressor=stressor, **kw),
        # outbound.py accepts stressor="water"|"energy"
        "outbound":     lambda stressor, **kw: _mod("outbound").run(stressor=stressor, **kw),

        # ── Stressor-specific steps (still separate) ────────────────────────
        "direct":       lambda stressor, **kw: _mod("direct").run(stressor=stressor, **kw),
        "sda":          lambda stressor, **kw: _mod("decompose").run(stressor=stressor, **kw),

        # ── Reporting + validation ──────────────────────────────────────────
        "report":       lambda stressor, **kw: _mod("compare").run(
                            mode="combined" if stressor == "combined" else stressor, **kw),
        "visualise":    lambda stressor, **kw: _mod("visualise").run(stressor=stressor, **kw),
        "validate":     lambda stressor, **kw: _run_validate(),
    }


# ── Step dependencies ─────────────────────────────────────────────────────────

DEPS: dict[str, list[str]] = {
    "build_io":     [],
    "demand":       ["build_io"],
    "coefficients": ["build_io"],
    "indirect":     ["build_io", "demand", "coefficients"],
    "direct":       ["demand"],
    "outbound":     ["indirect"],
    "sda":          ["indirect"],
    "report":       ["indirect", "direct"],
    "visualise":    ["indirect", "direct", "report"],
    "validate":     ["indirect", "direct"],
}

# ── Step descriptions (for interactive menu) ──────────────────────────────────

STEP_DESCS: dict[str, str] = {
    "build_io":     "Build IO tables from SUT  (build_io.py)",
    "demand":       "Tourism demand vectors  (build_demand.py)",
    "coefficients": "EXIOBASE extract + concordance  (build_coefficients.py)",
    "indirect":     "Indirect footprint C·L·Y  (indirect.py)",
    "direct":       "Direct operational footprint  (direct.py)",
    "outbound":     "Outbound footprint + net balance  (outbound.py)",
    "sda":          "SDA + Monte Carlo + Supply-Chain  (decompose.py)",
    "report":       "Cross-year report + Markdown  (compare.py)",
    "visualise":    "All chart generation  (visualise.py)",
    "validate":     "Sanity checks on final outputs  (validate_outputs.py)",
}

WATER_STEPS  = ["build_io", "demand", "coefficients", "indirect",
                "direct", "outbound", "sda", "report", "visualise", "validate"]
ENERGY_STEPS = ["build_io", "demand", "coefficients", "indirect",
                "direct", "outbound", "sda", "report", "visualise", "validate"]
ALL_STEPS    = list(dict.fromkeys(WATER_STEPS + ENERGY_STEPS))  # dedup, preserve order

PIPELINE = ALL_STEPS  # canonical order for interactive menu


# ══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY CHECKER
# ══════════════════════════════════════════════════════════════════════════════

def _run_validate():
    """
    Run validate_outputs.main() without letting sys.exit() propagate.
    validate_outputs calls sys.exit(1) on failures — we catch SystemExit and
    convert non-zero codes to RuntimeError so the pipeline logs them as FAIL.
    """
    import validate_outputs
    try:
        validate_outputs.main()
    except SystemExit as e:
        if e.code not in (None, 0):
            raise RuntimeError(
                f"validate_outputs: {e.code} check(s) failed — see output above"
            ) from None


def check_deps(step: str, completed: set[str], ignore: bool = False) -> list[str]:
    """Return list of unmet dependencies for `step`."""
    if ignore:
        return []
    return [d for d in DEPS.get(step, []) if d not in completed]


# ══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE MENU
# ══════════════════════════════════════════════════════════════════════════════

def interactive_menu() -> tuple[list[str], str]:
    """Display numbered step menu. Returns (steps_to_run, stressor)."""
    bar = "=" * 65

    while True:
        print(f"\n{bar}")
        print("  India Tourism Footprint — Pipeline")
        print(bar)
        print(f"  {'#':<4}  {'Step':<22}  {'Description'}")
        print(f"  {'─'*4}  {'─'*22}  {'─'*34}")
        for i, key in enumerate(PIPELINE, 1):
            deps = DEPS.get(key, [])
            dep_note = f"  [needs: {', '.join(deps)}]" if deps else ""
            print(f"  {i:<4}  {key:<22}  {STEP_DESCS.get(key, '')}{dep_note}")

        print()
        print("  Stressor presets:")
        print("    W   — Run full WATER pipeline")
        print("    E   — Run full ENERGY pipeline")
        print("    A   — Run ALL steps (water + energy + combined report)")
        print()
        print("  Or enter step numbers separated by spaces/commas (e.g. 1 2 3)")
        print("    Q   — Quit")
        print(bar)

        raw = input("  Your choice: ").strip().upper()

        if raw in ("Q", ""):
            return [], "water"
        if raw == "W":
            print("\n  → Stressor: WATER")
            return WATER_STEPS[:], "water"
        if raw == "E":
            print("\n  → Stressor: ENERGY")
            return ENERGY_STEPS[:], "energy"
        if raw == "A":
            return ALL_STEPS[:], "combined"

        # Parse individual step numbers / names
        tokens   = raw.replace(",", " ").split()
        selected: list[str] = []
        invalid:  list[str] = []
        for tok in tokens:
            if tok.isdigit():
                idx = int(tok)
                if 1 <= idx <= len(PIPELINE):
                    selected.append(PIPELINE[idx - 1])
                else:
                    invalid.append(tok)
            elif tok.lower() in DEPS:
                selected.append(tok.lower())
            else:
                invalid.append(tok)

        if invalid:
            print(f"\n  ⚠  Unknown input(s): {', '.join(invalid)} — try again.")
            continue
        if not selected:
            print("\n  ⚠  Nothing selected — try again.")
            continue

        stressor = _ask_stressor()
        return selected, stressor


def _ask_stressor() -> str:
    print("\n  Stressor for this run:")
    print("    1  water    (default)")
    print("    2  energy")
    print("    3  combined")
    raw = input("  Choice [1]: ").strip()
    mapping = {
        "1": "water", "2": "energy", "3": "combined",
        "water": "water", "energy": "energy", "combined": "combined",
    }
    return mapping.get(raw, "water")


# ══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(steps: list[str], stressor: str, log: Logger,
                 ignore_deps: bool = False) -> dict[str, str]:
    """Run a list of steps in order. Returns {step: 'OK'|'SKIP'|'FAIL'}."""
    fns       = _get_step_fns()
    completed: set[str]       = set()
    results:   dict[str, str] = {}
    timing:    dict[str, float] = {}

    for step in steps:
        missing = check_deps(step, completed, ignore=ignore_deps)
        if missing:
            warn(f"Skipping '{step}' — unfulfilled deps: {missing}", log)
            results[step] = "SKIP"
            continue

        if step not in fns:
            warn(f"Unknown step '{step}'", log)
            results[step] = "SKIP"
            continue

        log.section(f"STEP: {step.upper()}  [{stressor}]")
        t0 = time.time()
        try:
            fns[step](stressor)
            elapsed = time.time() - t0
            ok(f"Step '{step}' completed in {elapsed:.1f}s", log)
            results[step] = "OK"
            completed.add(step)
            timing[step]  = elapsed
        except Exception as exc:
            elapsed = time.time() - t0
            log.fail(f"Step '{step}' FAILED after {elapsed:.1f}s: {exc}")
            log._log(traceback.format_exc())
            results[step] = "FAIL"
            timing[step]  = elapsed

    # Summary table
    log.section("PIPELINE SUMMARY")
    log.table(
        ["Step", "Status", "Time (s)"],
        [[s, results.get(s, "—"), f"{timing.get(s, 0):.1f}"] for s in steps],
    )
    n_ok   = sum(1 for v in results.values() if v == "OK")
    n_fail = sum(1 for v in results.values() if v == "FAIL")
    n_skip = sum(1 for v in results.values() if v == "SKIP")
    log.info(f"OK: {n_ok}  |  FAIL: {n_fail}  |  SKIP: {n_skip}")
    return results


def _run_combined(log: Logger, ignore_deps: bool = False):
    ok("Running WATER stressor steps...", log)
    run_pipeline(WATER_STEPS,  "water",  log, ignore_deps)
    ok("Running ENERGY stressor steps...", log)
    run_pipeline(ENERGY_STEPS, "energy", log, ignore_deps)
    ok("Running combined report...", log)
    try:
        compare = importlib.import_module("compare")
        compare.run(mode="combined")
    except Exception as exc:
        log.fail(f"Combined report failed: {exc}")
        log._log(traceback.format_exc())


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def _parse_args():
    p = argparse.ArgumentParser(
        description="India Tourism Water + Energy Footprint Pipeline",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                          # interactive menu\n"
            "  python main.py --water                  # full water pipeline\n"
            "  python main.py --energy                 # full energy pipeline\n"
            "  python main.py --all                    # water + energy + combined\n"
            "  python main.py --steps build_io demand coefficients\n"
            "  python main.py --stressor energy --steps indirect sda\n"
            "  python main.py --steps validate --ignore-deps\n"
            "  python main.py --list-steps\n"
        ),
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--water",  action="store_true", help="Run water pipeline")
    mode.add_argument("--energy", action="store_true", help="Run energy pipeline")
    mode.add_argument("--all",    action="store_true", help="Run water + energy + combined")

    p.add_argument("--stressor", choices=list(STRESSORS) + ["combined"],
                   default=None, help="Override stressor")
    p.add_argument("--steps", nargs="+", default=None,
                   choices=list(_get_step_fns()), metavar="STEP",
                   help="Run specific steps only")
    p.add_argument("--list-steps", action="store_true",
                   help="Print all steps and exit")
    p.add_argument("--ignore-deps", action="store_true",
                   help="Skip dependency checks")
    p.add_argument("--years", nargs="+", default=STUDY_YEARS,
                   help=f"Study years (default: {STUDY_YEARS})")
    return p.parse_args()


def main():
    args = _parse_args()

    if args.list_steps:
        print("\n  Steps and dependencies:")
        for key in PIPELINE:
            deps    = DEPS.get(key, [])
            dep_str = f"  [needs: {', '.join(deps)}]" if deps else "  [no deps]"
            print(f"    {key:<22}  {STEP_DESCS.get(key, '')}{dep_str}")
        print(f"\n  Order: {' → '.join(PIPELINE)}")
        sys.exit(0)

    # ── Determine steps + stressor ────────────────────────────────────────────
    interactive = False
    if args.all:
        stressor, steps = "combined", ALL_STEPS[:]
    elif args.water:
        stressor, steps = "water",    WATER_STEPS[:]
    elif args.energy:
        stressor, steps = "energy",   ENERGY_STEPS[:]
    elif args.stressor:
        stressor = args.stressor
        steps    = args.steps or (
            WATER_STEPS  if stressor == "water"  else
            ENERGY_STEPS if stressor == "energy" else
            ALL_STEPS
        )
    elif args.steps:
        stressor = "water"
        steps    = args.steps
    else:
        interactive = True
        steps, stressor = interactive_menu()
        if not steps:
            print("  Nothing to run. Exiting.")
            sys.exit(0)

    # ── Run ───────────────────────────────────────────────────────────────────
    DIRS["logs"].mkdir(parents=True, exist_ok=True)
    with Logger("pipeline", DIRS["logs"]) as log:
        t = Timer()
        log.section(f"INDIA TOURISM FOOTPRINT PIPELINE  [{stressor.upper()}]")
        log.info(f"Steps    : {' → '.join(steps)}")
        log.info(f"Stressor : {stressor}")
        log.info(f"Years    : {args.years if not interactive else STUDY_YEARS}")
        if args.ignore_deps:
            log.info("Deps     : checks DISABLED (--ignore-deps)")

        if stressor == "combined":
            _run_combined(log, ignore_deps=args.ignore_deps)
        else:
            run_pipeline(steps, stressor, log, ignore_deps=args.ignore_deps)

        log.ok(f"Pipeline complete in {t.elapsed()}")


if __name__ == "__main__":
    main()
