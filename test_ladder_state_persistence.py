"""Tests for trim_ladder_state.json persistence in PositionManager.

Covers the failure modes that would otherwise be silent:

  1. A missing state file is a normal first run, not an error.
  2. A corrupt/truncated state file must NOT crash startup - the ladder
     re-initialises from avg_entry_price on first sight. (Previously the
     unguarded json.load raised and bricked every later scan.)
  3. Valid JSON that is not an object (a list or a string) must ALSO be
     rejected: it parses fine, then crashes later when ladder_entry() calls
     .get() on it.
  4. save_ladder_state() writes valid JSON and leaves no .tmp file behind.
  5. A write that fails mid-dump must leave the real state file untouched -
     that is the property the atomic write exists to provide, not merely
     "no .tmp is left over".

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

STATE = "trim_ladder_state.json"


def make_pm(tmp):
    """A real PositionManager with _HERE redirected to tmp and no network."""
    with patch.object(position_manager, '_HERE', tmp), \
         patch.object(position_manager, 'AlpacaTrader', MagicMock(), create=True), \
         patch.object(position_manager, 'EnsembleTrader', MagicMock(), create=True):
        return PositionManager()


def write_state(tmp, raw):
    with open(os.path.join(tmp, STATE), 'w') as f:
        f.write(raw)


def test_missing_state_file_is_fine():
    pm = make_pm(tempfile.mkdtemp())
    assert pm.ladder_state == {}, f"expected empty state, got {pm.ladder_state}"


def test_corrupt_state_file_reinitialises():
    tmp = tempfile.mkdtemp()
    write_state(tmp, '{"MRVL": {"base_price": 235.29, "rungs')   # truncated JSON
    pm = make_pm(tmp)                                             # must not raise
    assert pm.ladder_state == {}, f"expected re-init to empty, got {pm.ladder_state}"


def test_non_dict_json_reinitialises():
    """Valid JSON that is not an object parses, then crashes on .get() - reject it."""
    for raw in ('[1, 2, 3]', '"oops"', '42'):
        tmp = tempfile.mkdtemp()
        write_state(tmp, raw)
        pm = make_pm(tmp)                                         # must not raise
        assert pm.ladder_state == {}, f"{raw!r}: expected re-init to empty"
        # and the manager must be usable afterwards
        assert pm.ladder_entry('MRVL', 235.29)['base_price'] == 235.29


def test_atomic_save_writes_valid_json_and_no_temp():
    tmp = tempfile.mkdtemp()
    pm = make_pm(tmp)
    pm.ladder_state = {"MRVL": {"base_price": 235.29, "rungs_fired": [0.5]}}
    pm.save_ladder_state()
    with open(os.path.join(tmp, STATE)) as f:
        loaded = json.load(f)                                     # must be parseable
    assert loaded == pm.ladder_state, f"round-trip mismatch: {loaded}"
    leftovers = [n for n in os.listdir(tmp) if n.endswith('.tmp')]
    assert leftovers == [], f"temp file left behind: {leftovers}"


def test_write_failure_leaves_real_file_intact():
    """A crash mid-dump must not damage the good state file already on disk."""
    tmp = tempfile.mkdtemp()
    pm = make_pm(tmp)
    pm.ladder_state = {"MRVL": {"base_price": 235.29, "rungs_fired": [0.5]}}
    pm.save_ladder_state()
    path = os.path.join(tmp, STATE)
    with open(path) as f:
        good = f.read()

    pm.ladder_state = {"BROKEN": {"base_price": 1.0}}
    with patch.object(position_manager.json, 'dump', side_effect=OSError("disk full")):
        try:
            pm.save_ladder_state()
        except OSError:
            pass                                                  # the crash is expected

    with open(path) as f:
        assert f.read() == good, "a failed write must leave the real file untouched"
    assert json.load(open(path))['MRVL']['rungs_fired'] == [0.5]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")
