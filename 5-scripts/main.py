"""
main.py — India Tourism Water Footprint Pipeline
=================================================
Runs the six pipeline steps in order and coordinates logging.
Report generation lives entirely in compare_years.py.
This file contains zero business logic.

Usage
-----
    python main.py --all
    python main.py --step build_io water_coefficients
    python main.py --step compare --ignore-deps
    python main.py --list

Pipeline steps (in order)
--------------------------
    build_io           Build IO tables from SUT via PTA method
    water_coefficients EXIOBASE extract + concordance + SUT-140 mapping
    tourism_demand     TSA scale (NAS) + EXIOBASE demand vectors
    indirect_twf       W * L * Y + structural decomposition + path analysis
    direct_twf         Activity-based operational water
    sda_mc             SDA + Monte Carlo + Supply-Chain Path Analysis
    visualise          All chart generation
    compare            Cross-year totals + Markdown run report

Step dependencies
-----------------
    indirect_twf  requires: tourism_demand, build_io, water_coefficients
    sda_mc        requires: indirect_twf, direct_twf
    visualise     requires: sda_mc
    compare       requires: sda_mc, visualise

FIX: All run() functions now accept **kwargs so pipeline metadata forwarding
     from main.py never raises TypeError regardless of which step is called.
"""

import argparse
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DIRS, STUDY_YEARS


# ══════════════════════════════════════════════════════════════════════════════
# STEP REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

# Each entry: step_key -> (human description, module_name)
# FIX: build_tourism_demand was registered but the module did not exist.
# If you have not yet created build_tourism_demand.py, keep it here and the
# pipeline will error clearly on missing-module rather than silently skipping
# downstream steps. Create the module or comment out this entry to remove it.
STEPS = {
    "build_io":           ("Build IO tables (SUT → PTA → L)",                        "build_io_tables"),
    "water_coefficients": ("EXIOBASE extract + concordance + SUT-140 mapping",        "build_water_coefficients"),
    "tourism_demand":     ("TSA scale (NAS) + EXIOBASE demand vectors",               "build_tourism_demand"),
    "indirect_twf":       ("Indirect TWF (W·L·Y + structural decomp + path analysis)","calculate_indirect_twf"),
    "direct_twf":         ("Direct operational water (activity-based)",               "calculate_direct_twf"),
    "sda_mc":             ("SDA + Monte Carlo + Supply-Chain Path Analysis",          "calculate_sda_mc"),
    "visualise":          ("All chart generation (waterfall/violin/Sankey/etc.)",     "visualise_results"),
    "compare":            ("Cross-year comparison + run report",                      "compare_years"),
}

STEP_DEPS: dict[str, list[str]] = {
    "build_io":           [],
    "water_coefficients": [],
    "tourism_demand":     [],
    "indirect_twf":       ["tourism_demand", "build_io", "water_coefficients"],
    "direct_twf":         [],
    "sda_mc":             ["indirect_twf", "direct_twf"],
    "visualise":          ["sda_mc"],
    "compare":            ["sda_mc", "visualise"],
}

PIPELINE = list(STEPS)  # ordered


# ══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY CHECKER
# ══════════════════════════════════════════════════════════════════════════════

def check_deps(step: str, results: dict, ignore: bool = False) -> tuple[bool, list[str]]:
    if ignore:
        return True, []
    missing = []
    for dep in STEP_DEPS.get(step, []):
        if dep not in results:
            missing.append(f"{dep} (not run)")
        elif not results[dep]:
            missing.append(f"{dep} (FAILED)")
    return len(missing) == 0, missing


# ══════════════════════════════════════════════════════════════════════════════
# STEP RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_step(step_key: str, **kwargs) -> bool:
    """
    Import and call module.run(**kwargs) for the given step.
    Returns True on success, False on any exception.

    FIX: Every pipeline module's run() now accepts **kwargs, so passing extra
    keys (start_ts, steps_req, etc.) never raises TypeError. The compare step
    consumes them; all others ignore them gracefully.
    """
    desc, module = STEPS[step_key]
    bar = "=" * 70
    print(f"\n{bar}\n  STEP: {desc}\n{bar}")
    t0 = time.time()
    try:
        mod = __import__(module)
        mod.run(**kwargs)
        print(f"\n  ✓  {step_key}  ({time.time()-t0:.1f}s)")
        return True
    except FileNotFoundError as e:
        print(f"\n  ✗  {step_key} — missing input file: {e}")
        print("     Ensure prerequisite steps have been run.")
        return False
    except ModuleNotFoundError as e:
        # FIX: surface missing-module errors explicitly rather than letting
        # them appear as generic exceptions.
        print(f"\n  ✗  {step_key} — module not found: {e}")
        print(f"     Expected module file: {module}.py")
        print("     Create the module or remove the step from STEPS registry.")
        return False
    except TypeError as e:
        # FIX: if a run() function still doesn't accept **kwargs this gives
        # a clear, actionable message instead of a cryptic traceback.
        print(f"\n  ✗  {step_key} — run() signature mismatch: {e}")
        print("     Add '**kwargs' to the run() definition in that module.")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n  ✗  {step_key}: {e}")
        traceback.print_exc()
        return False


# ══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE MENU
# ══════════════════════════════════════════════════════════════════════════════

def interactive_menu() -> list[str]:
    print("\n" + "=" * 65)
    print("  India Tourism Water Footprint — Pipeline")
    print("=" * 65)
    for i, (key, (name, _)) in enumerate(STEPS.items(), 1):
        deps = STEP_DEPS.get(key, [])
        note = f"  [needs: {', '.join(deps)}]" if deps else ""
        print(f"    {i}. [{key:<22}] {name}{note}")
    print("\n    A. Run ALL steps")
    print("    Q. Quit\n")
    choice = input("  Enter number(s), A, or Q: ").strip().upper()
    if choice == "Q":
        return []
    if choice == "A":
        return PIPELINE[:]
    selected = []
    for token in choice.replace(",", " ").split():
        if token.isdigit() and 1 <= int(token) <= len(PIPELINE):
            selected.append(PIPELINE[int(token) - 1])
        elif token.lower() in STEPS:
            selected.append(token.lower())
        else:
            print(f"  Unknown choice: {token}")
    return selected


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="India Tourism Water Footprint Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --all\n"
            "  python main.py --step build_io water_coefficients\n"
            "  python main.py --step compare --ignore-deps\n"
            "  python main.py --list"
        ),
    )
    parser.add_argument("--all",  action="store_true", help="Run all steps in order")
    parser.add_argument("--step", nargs="+", choices=list(STEPS), metavar="STEP",
                        help="One or more step names")
    parser.add_argument("--list", action="store_true", help="List steps and exit")
    parser.add_argument("--continue-on-failure", action="store_true",
                        help="Keep running after a step fails (--all mode only)")
    parser.add_argument("--ignore-deps", action="store_true",
                        help="Skip dependency checks")
    args = parser.parse_args()

    # ── --list ────────────────────────────────────────────────────────────────
    if args.list:
        print("\n  Steps and dependencies:")
        for key, (name, _) in STEPS.items():
            deps = STEP_DEPS.get(key, [])
            note = f" [needs: {', '.join(deps)}]" if deps else " [no deps]"
            print(f"    {key:<24} {name}{note}")
        print("\n  Order:", " → ".join(PIPELINE))
        return

    # ── Resolve steps to run ──────────────────────────────────────────────────
    if args.all:
        steps_to_run    = PIPELINE[:]
        halt_on_failure = not args.continue_on_failure
    elif args.step:
        steps_to_run    = list(args.step)
        halt_on_failure = False
    else:
        steps_to_run    = interactive_menu()
        halt_on_failure = not args.continue_on_failure
        if not steps_to_run:
            print("  Nothing to run.")
            return

    print(f"\n  Steps : {' → '.join(steps_to_run)}")
    print(f"  Mode  : {'halt on failure' if halt_on_failure else 'continue on failure'}")
    if args.ignore_deps:
        print("  Deps  : checks disabled")

    # ── Setup logging ─────────────────────────────────────────────────────────
    DIRS["logs"].mkdir(exist_ok=True)
    start        = time.time()
    ts           = int(start)
    pipeline_log = DIRS["logs"] / f"pipeline_run_{ts}.log"

    results: dict  = {}
    skipped: dict  = {}

    # ── Run steps ─────────────────────────────────────────────────────────────
    for step in steps_to_run:
        deps_ok, missing = check_deps(step, results, ignore=args.ignore_deps)
        if not deps_ok:
            print(f"\n  SKIP: {step}")
            print(f"     Unsatisfied deps: {'; '.join(missing)}")
            skipped[step] = missing
            continue

        # compare_years.run() accepts pipeline metadata so it can embed it in
        # the report. All other run() functions accept **kwargs and ignore
        # extra keys — enforced by the **kwargs signature fix applied to all
        # modules in this pipeline.
        extra = {}
        if step == "compare":
            extra = dict(
                start_ts        = start,
                steps_req       = steps_to_run,
                steps_completed = [s for s, ok in results.items() if ok],
                steps_failed    = [s for s, ok in results.items() if not ok],
                total_time      = time.time() - start,
                pipeline_log    = pipeline_log,
            )

        ok = run_step(step, **extra)
        results[step] = ok

        if not ok and halt_on_failure:
            print(f"\n  Pipeline halted at '{step}'.")
            blocked = [s for s in steps_to_run
                       if s not in results and step in STEP_DEPS.get(s, [])]
            if blocked:
                print(f"  Blocked downstream: {', '.join(blocked)}")
            print("  Fix the issue and re-run.")
            break

    total_time = time.time() - start

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  PIPELINE SUMMARY  ({total_time:.0f}s total)")
    print(f"{'='*65}")
    for step in steps_to_run:
        name = STEPS[step][0]
        if step in results:
            tag = "✓ OK  " if results[step] else "✗ FAIL"
            print(f"  {tag}  {step:<24}  {name}")
        elif step in skipped:
            print(f"  SKIP  {step:<24}  missing: {', '.join(skipped[step])}")
        else:
            print(f"  ----  {step:<24}  (halted before this step)")

    # ── Write pipeline log ────────────────────────────────────────────────────
    with open(pipeline_log, "w", encoding="utf-8") as f:
        f.write(f"Run   : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Steps : {', '.join(steps_to_run)}\n")
        f.write(f"Halt  : {halt_on_failure}  |  IgnoreDeps: {args.ignore_deps}\n")
        f.write(f"Time  : {total_time:.0f}s\n\n")
        for step in steps_to_run:
            if step in results:
                f.write(f"{'OK' if results[step] else 'FAILED'}: {step}\n")
            elif step in skipped:
                f.write(f"SKIPPED: {step}  ({', '.join(skipped[step])})\n")
            else:
                f.write(f"NOT_RUN: {step}\n")

    print(f"\n  Pipeline log: {pipeline_log}\n")


if __name__ == "__main__":
    main()