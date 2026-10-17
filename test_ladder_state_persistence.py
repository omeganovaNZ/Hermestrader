"""Tests for trim_ladder_state.json persistence in PositionManager.

Covers the failure modes that would otherwise be silent:

  1. A missing state file is a normal first run, not an error.
  2. A corrupt/truncated state file must NOT crash startup — the ladder
     re-initialises from avg_entry_price on first sight. (Previously the
     unguarded json.load raised and bricked every later scan.)
  3. save_ladder_state() writes valid JSON and leaves no .tmp file behind,
     i.e. the write is atomic so a crash cannot truncate the real file.

The Alpaca and ensemble clients are mocked and the module's _HERE is redirected
to a temp dir, so nothing touches the network, the order path, or the real
state file.
"""
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import position_manager
from position_manager import PositionManager


def make_pm(tmp):
    """A real PositionManager with _HERE redirected to tmp and no network."""
    with patch.object(position_manager, '_HERE', tmp), \
         patch.object(position_manager, 'AlpacaTrader', MagicMock(), create=True), \
         patch.object(position_manager, 'EnsembleTrader', MagicMock(), create=True):
        return PositionManager()


def test_missing_state_file_is_fine():
    tmp = tempfile.mkdtemp()
    pm = make_pm(tmp)
    assert pm.ladder_state == {}, f"expected empty state, got {pm.ladder_state}"


def test_corrupt_state_file_reinitialises():
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "trim_ladder_state.json"), 'w') as f:
        f.write('{"MRVL": {"base_price": 235.29, "rungs')      # truncated JSON
    pm = make_pm(tmp)                                          # must not raise
    assert pm.ladder_state == {}, f"expected re-init to empty, got {pm.ladder_state}"


def test_atomic_save_writes_valid_json_and_no_temp():
    tmp = tempfile.mkdtemp()
    pm = make_pm(tmp)
    pm.ladder_state = {"MRVL": {"base_price": 235.29, "rungs_fired": [0.5]}}
    pm.save_ladder_state()
    with open(os.path.join(tmp, "trim_ladder_state.json")) as f:
        loaded = json.load(f)                                  # must be parseable
    assert loaded == pm.ladder_state, f"round-trip mismatch: {loaded}"
    leftovers = [n for n in os.listdir(tmp) if n.endswith('.tmp')]
    assert leftovers == [], f"temp file left behind: {leftovers}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")
