"""Tests for multi-account position management (--all / --account).

Why this exists: the scanner was wired to ONE book (the one in alpaca_config.txt) while
two more paper accounts ran with no cap trim, no theme cap check and no thesis review.
Running it on every account is only safe if each book gets its OWN state files — the
trim log, redeploy log and ladder state are keyed by symbol and by ROI reference price,
so two books sharing one file would silently overwrite each other's trim history and
re-base each other's references.

These tests are NETWORK-FREE: AlpacaTrader is stubbed out, because PositionManager
connects to the API in __init__.
"""
import io
import json
import os
import sys
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import src.position_manager as pm_mod
from src.alpaca_trader import load_credentials

REGISTRY = os.path.join(REPO, "accounts.json")


# ── helpers ────────────────────────────────────────────────────────────────────────────

class _FakeTrader:
    def __init__(self, config_file=None):
        self.config_file = config_file or "alpaca_config.txt"


class _FakeEnsemble:
    pass


def _manager(config_file):
    """A PositionManager with both network layers stubbed out."""
    real_t, real_e = pm_mod.AlpacaTrader, pm_mod.EnsembleTrader
    pm_mod.AlpacaTrader, pm_mod.EnsembleTrader = _FakeTrader, _FakeEnsemble
    try:
        return pm_mod.PositionManager(config_file=config_file)
    finally:
        pm_mod.AlpacaTrader, pm_mod.EnsembleTrader = real_t, real_e


def _run_main(argv):
    """Invoke position_manager.main() with argv patched; returns (text, calls)."""
    calls = []
    real_run = pm_mod.PositionManager.run_position_management

    def _fake_run(self, dry_run=False):
        calls.append((self.config_file, dry_run))

    pm_mod.PositionManager.run_position_management = _fake_run
    old_argv = sys.argv
    sys.argv = ["position_manager.py"] + argv
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            pm_mod.main()
    finally:
        sys.argv = old_argv
        pm_mod.PositionManager.run_position_management = real_run
    return buf.getvalue(), calls


def _state_paths(m):
    """Every per-account state file this manager writes.

    `redeploy_log_path` belongs to a SEPARATE uncommitted feature, so it is included only
    when present — the multi-account separation must hold with or without it. A test that
    hard-required it would fail on a checkout of this change alone.
    """
    paths = [m.trim_log_path, m.ladder_state_path]
    if hasattr(m, "redeploy_log_path"):
        paths.append(m.redeploy_log_path)
    return paths


# ── the legacy default must not move ──────────────────────────────────────────────────

def test_default_config_keeps_the_legacy_unsuffixed_state_files():
    """Core's existing data/trim_ladder_state.json must keep being read.

    Re-initialising it would reset every ROI reference to avg_entry_price and change
    when a profit trim fires, so the default path has to be byte-identical to before.
    """
    m = _manager(None)
    assert m.trim_log_path.endswith("trim_log.json"), m.trim_log_path
    assert m.ladder_state_path.endswith("trim_ladder_state.json"), m.ladder_state_path
    assert _manager("alpaca_config.txt").ladder_state_path == m.ladder_state_path
    for p in _state_paths(m):
        assert "_pattern_match" not in p and "_container_test1" not in p, p


# ── each account gets its own state files ──────────────────────────────────────────────

def test_each_account_gets_its_own_state_files():
    m = _manager("alpaca_config_pattern_match.txt")
    assert m.ladder_state_path.endswith("trim_ladder_state_pattern_match.json"), m.ladder_state_path
    assert m.trim_log_path.endswith("trim_log_pattern_match.json"), m.trim_log_path

    c = _manager("alpaca_config_container_test1.txt")
    assert c.ladder_state_path.endswith("trim_ladder_state_container_test1.json"), c.ladder_state_path


def test_no_two_accounts_share_a_state_file():
    """The whole point: a shared file would silently corrupt both books' state."""
    paths = set()
    checked = 0
    for _, cfg in pm_mod.registered_accounts():
        for p in _state_paths(_manager(cfg)):
            assert p not in paths, f"state file shared between accounts: {p}"
            paths.add(p)
            checked += 1
    # At least the trim log and ladder state per account; redeploy_log only when present.
    assert checked >= 2 * len(pm_mod.registered_accounts()), (
        f"only {checked} state files checked for {len(pm_mod.registered_accounts())} accounts")


# ── the registry drives the loop ──────────────────────────────────────────────────────

def test_registered_accounts_matches_the_registry():
    with open(REGISTRY) as f:
        reg = json.load(f)
    got = pm_mod.registered_accounts()
    assert len(got) == len(reg["accounts"]), f"{len(got)} != {len(reg['accounts'])}"
    for (name, cfg), entry in zip(got, reg["accounts"]):
        assert name == entry["name"]
        assert cfg == entry["config_file"]


def test_all_flag_runs_every_account_exactly_once():
    text, calls = _run_main(["--all", "--dry-run"])
    assert len(calls) == len(pm_mod.registered_accounts()), calls
    seen = [c for c, _ in calls]
    assert len(set(seen)) == len(seen), f"an account ran twice: {seen}"
    for _, cfg in pm_mod.registered_accounts():
        assert cfg in seen, f"{cfg} never ran"
    assert all(dry for _, dry in calls), "—dry-run did not propagate to every account"


def test_all_flag_does_not_place_orders():
    _, calls = _run_main(["--all", "--dry-run"])
    assert calls and all(dry for _, dry in calls)


def test_no_flag_is_still_just_the_default_book():
    """A cron prompt that passes no flag must behave exactly as it did before."""
    text, calls = _run_main([])
    assert len(calls) == 1, calls
    assert calls[0][0] == "alpaca_config.txt", calls[0]


def test_single_account_flag_targets_that_book_only():
    _, calls = _run_main(["--account", "alpaca_config_pattern_match.txt"])
    assert len(calls) == 1, calls
    assert calls[0][0] == "alpaca_config_pattern_match.txt", calls[0]


def test_all_and_account_are_mutually_exclusive():
    try:
        _run_main(["--all", "--account", "alpaca_config.txt"])
    except SystemExit:
        return
    raise AssertionError("--all and --account together should be rejected")


# ── credential routing ────────────────────────────────────────────────────────────────

def test_load_credentials_reads_the_named_config():
    for _, cfg in pm_mod.registered_accounts():
        key, secret = load_credentials(cfg)
        assert key and secret, f"{cfg} returned no credentials"
        assert key.startswith("PK"), f"{cfg} returned a non-paper key: {key[:6]}"


def test_load_credentials_defaults_to_the_core_config():
    assert load_credentials() == load_credentials("alpaca_config.txt")


def test_load_credentials_refuses_a_missing_file():
    try:
        load_credentials("alpaca_config_does_not_exist.txt")
    except (OSError, ValueError):
        return
    raise AssertionError("a missing config file should raise")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
