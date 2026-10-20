"""Tests for the account registry (accounts.json) — the name/number/config-file binding.

Why this exists: the config filenames were positional (test1/test3) while the accounts had
NAMES, so the file holding the account called "Container Test 1" was alpaca_config_test3.txt
and the account called "Pattern Match" lived in alpaca_config_test1.txt. Two sources disagreed
about which account was which, and a note about one account would send the next reader to the
wrong book. The files are now named after the account, accounts.json is the single binding,
and these tests make drift fail loudly instead of silently.

These tests read NO secrets. They check file EXISTENCE and structure only — never contents
beyond the two key names, and never the values.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

REGISTRY = os.path.join(REPO, "accounts.json")
EXAMPLE = "alpaca_config.example.txt"


def _registry():
    with open(REGISTRY) as f:
        return json.load(f)


def _configs_on_disk():
    """Every alpaca_config*.txt in the repo root, except the committed template."""
    return sorted(f for f in os.listdir(REPO)
                  if f.startswith("alpaca_config") and f.endswith(".txt") and f != EXAMPLE)


# ── the registry is well-formed ─────────────────────────────────────────────────────────

def test_registry_exists_and_parses():
    assert os.path.exists(REGISTRY), "accounts.json is missing — it is the name/number binding"
    data = _registry()
    assert isinstance(data.get("accounts"), list) and data["accounts"], "accounts[] missing or empty"


def test_every_entry_has_a_name_and_a_config_file():
    for a in _registry()["accounts"]:
        assert a.get("name"), f"entry with no name: {a}"
        assert a.get("config_file"), f"{a.get('name')} has no config_file"


def test_no_config_file_is_claimed_twice():
    files = [a["config_file"] for a in _registry()["accounts"]]
    dupes = sorted({f for f in files if files.count(f) > 1})
    assert dupes == [], f"config file claimed by more than one account: {dupes}"


def test_account_numbers_are_unique():
    nums = [a.get("account_number") for a in _registry()["accounts"] if a.get("account_number")]
    dupes = sorted({n for n in nums if nums.count(n) > 1})
    assert dupes == [], f"account number used twice: {dupes}"


# ── the registry matches reality (this is the drift guard) ──────────────────────────────

def test_every_registered_config_file_exists():
    missing = [a["config_file"] for a in _registry()["accounts"]
               if not os.path.exists(os.path.join(REPO, a["config_file"]))]
    assert missing == [], f"registered but absent on disk: {missing}"


def test_no_unregistered_config_file_exists():
    """A new account config must be added to accounts.json, not just dropped on disk.

    Without this, the next reader has no way to know what the file holds or which account
    it points at — which is exactly the confusion this registry was created to end.
    """
    registered = {a["config_file"] for a in _registry()["accounts"]}
    unregistered = [f for f in _configs_on_disk() if f not in registered]
    assert unregistered == [], (
        f"config file(s) on disk but not in accounts.json: {unregistered} — "
        f"add them to accounts.json with the account name and number"
    )


def test_primary_config_is_registered():
    """src/alpaca_trader.py and every cron job read alpaca_config.txt by default, so it must
    be the registered entry that says so."""
    assert os.path.exists(os.path.join(REPO, "alpaca_config.txt")), "primary config missing"
    assert any(a["config_file"] == "alpaca_config.txt" for a in _registry()["accounts"]), \
        "alpaca_config.txt is not in accounts.json"


# ── each config has the two keys the loaders require (names only, never values) ─────────

def test_each_config_carries_both_required_keys():
    for a in _registry()["accounts"]:
        path = os.path.join(REPO, a["config_file"])
        if not os.path.exists(path):
            continue  # covered by test_every_registered_config_file_exists
        with open(path) as f:
            keys = {line.split("=", 1)[0].strip() for line in f if "=" in line}
        assert "API_KEY" in keys, f"{a['config_file']} has no API_KEY line"
        assert "API_SECRET" in keys, f"{a['config_file']} has no API_SECRET line"


# ── no credential file is committable ───────────────────────────────────────────────────

def test_gitignore_ignores_configs_by_glob_but_not_the_template():
    """A filename LIST in .gitignore means a newly added account config is committable until
    someone remembers to add a line. A glob means it is ignored the moment it is created."""
    def ignored(path):
        r = subprocess.run(["git", "check-ignore", "-q", path],
                           cwd=REPO, capture_output=True, text=True)
        return r.returncode == 0

    for f in _configs_on_disk():
        assert ignored(f), f"{f} is NOT gitignored — a live credential file is committable"
    assert not ignored(EXAMPLE), f"{EXAMPLE} should be committed, but it is ignored"


def test_no_config_file_is_tracked_by_git():
    r = subprocess.run(["git", "ls-files", "alpaca_config*"],
                       cwd=REPO, capture_output=True, text=True)
    tracked = [t for t in r.stdout.split() if t != EXAMPLE]
    assert tracked == [], f"credential file(s) tracked by git: {tracked}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")
