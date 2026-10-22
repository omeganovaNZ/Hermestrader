#!/usr/bin/env python
"""Onboarding script for Hermestrader.

Verifies the environment without touching live trading.
Usage: python setup_repo.py
"""

import os
import sys
import subprocess
import shutil

REPO = os.path.dirname(os.path.abspath(__file__))
MIN_PYTHON = (3, 10)


def step(msg):
    print(f"\n== {msg} ==")


def main():
    # 1. Python version
    step("Checking Python version")
    if sys.version_info < MIN_PYTHON:
        print(f"  FAIL: Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, got {sys.version}")
        return 1
    print(f"  OK: Python {sys.version.split()[0]}")

    # 2. Dependencies
    step("Installing dependencies")
    req = os.path.join(REPO, "requirements.txt")
    if os.path.exists(req):
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", req], check=False)
    else:
        print("  requirements.txt missing")

    # 3. Credential template
    step("Checking credentials")
    cfg = os.path.join(REPO, "alpaca_config.txt")
    example = os.path.join(REPO, "alpaca_config.example.txt")
    if not os.path.exists(cfg) and os.path.exists(example):
        shutil.copyfile(example, cfg)
        print("  Created alpaca_config.txt from template — edit it with your keys.")
    elif os.path.exists(cfg):
        print("  alpaca_config.txt already exists.")
    else:
        print("  No credential template found.")

    # 4. Pure-rule smoke tests
    step("Running pure-rule tests")
    pure = [
        "test_account_registry.py",
        "test_portfolio_rules.py",
        "test_position_sizing.py",
        "test_profit_trim.py",
        "test_ladder_state_persistence.py",
        "test_cap_trim_guard.py",
    ]
    tests_dir = os.path.join(REPO, "tests")
    failed = 0
    for name in pure:
        path = os.path.join(tests_dir, name)
        if not os.path.exists(path):
            continue
        r = subprocess.run([sys.executable, path], capture_output=True, text=True)
        if r.returncode == 0:
            print(f"  PASS  {name}")
        else:
            failed += 1
            print(f"  FAIL  {name}")
            if r.stderr.strip():
                print(f"        {r.stderr.strip()[:200]}")

    # 5. Next steps
    step("Next steps")
    print("  1. Edit alpaca_config.txt with your Alpaca paper-trading keys.")
    print("  2. Run 'python src/position_manager.py --dry-run' (no orders placed).")
    print("  3. Run 'python src/stock_screener.py' to scan the market.")
    print("  4. See README.md for the full progression and safety rules.")
    print("\n  All tests passed." if failed == 0 else f"\n  {failed} test(s) failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
