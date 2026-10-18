"""Test runner — discovers and runs all tests/test_*.py files.

Usage: python run_tests.py
Exits non-zero if any test fails.
"""
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(HERE, "tests")

def main():
    test_files = sorted(
        f for f in os.listdir(TESTS_DIR) if f.startswith("test_") and f.endswith(".py")
    )
    if not test_files:
        print("No test files found in tests/")
        return 1

    print(f"Running {len(test_files)} test files...\n")
    passed = 0
    failed = 0
    failures = []

    for fname in test_files:
        path = os.path.join(TESTS_DIR, fname)
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            passed += 1
            # Extract last line for summary
            last_line = result.stdout.strip().split('\n')[-1] if result.stdout.strip() else "PASS"
            print(f"  PASS  {fname} — {last_line}")
        else:
            failed += 1
            failures.append(fname)
            print(f"  FAIL  {fname}")
            if result.stderr.strip():
                print(f"        {result.stderr.strip()[:200]}")

    print(f"\n{'='*60}")
    print(f"  {passed} passed, {failed} failed")
    if failures:
        print(f"  Failed: {', '.join(failures)}")
    print(f"{'='*60}")

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
