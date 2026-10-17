"""Tests for the adaptive first-rung gate in PositionManager.check_trim_signals.

The gate skips the +50% rung's 10% trim when the move is already parabolic
(close / 50-day SMA >= 1.20). These tests pin the behaviour down:

  1. Parabolic at +50%  -> no signal, and the rung is marked passed permanently.
  2. Choppy at +50%     -> the 10% trim fires as normal.
  3. The gate applies to the FIRST rung only; the +100% rung fires regardless.
  4. If the extension cannot be computed (no data), the rung fires — refusing to
     trim is the riskier failure.
  5. The gate re-applies to the first rung of each fresh cycle after a re-base.

The Alpaca client and the data fetch are mocked, so nothing touches the network,
the order path, or the filesystem.
"""
import os
import tempfile
from unittest.mock import MagicMock

from position_manager import PositionManager


def make_pm(ext):
    """A PositionManager with no network, no filesystem, and a fixed extension."""
    tmp = tempfile.mkdtemp()
    pm = PositionManager.__new__(PositionManager)      # skip __init__ (connects to Alpaca)
    pm.alpaca = MagicMock()
    pm.ensemble = MagicMock()
    pm.trim_rules = {
        'ladder': [(0.50, 0.10), (1.00, 0.20), (1.50, 0.30)],
        'reset_after_gain': 1.50,
        'max_position_pct': 0.10,
        'add_drawdown': 0.20,
        'parabolic_ma': 50,
        'parabolic_ext': 1.20,
    }
    pm.trim_log = []
    pm.trim_log_path = os.path.join(tmp, "trim_log.json")
    pm.ladder_state_path = os.path.join(tmp, "ladder_state.json")
    pm.ladder_state = {}
    pm.ma_extension = MagicMock(return_value=ext)
    pm.save_ladder_state = MagicMock()
    return pm


def position(symbol, entry, current):
    return [{'symbol': symbol, 'avg_entry_price': entry, 'current_price': current,
             'qty': 100.0, 'market_value': 100.0 * current}]


def test_parabolic_skips_first_rung():
    pm = make_pm(1.30)
    pm.alpaca.get_positions.return_value = position('XYZ', 100.0, 150.0)   # +50%, extended
    sigs = pm.check_trim_signals('XYZ')
    assert sigs == [], f"expected no trim when parabolic, got {sigs}"
    assert 0.50 in pm.ladder_state['XYZ']['rungs_fired'], "rung must be marked passed"


def test_choppy_fires_first_rung():
    pm = make_pm(1.05)
    pm.alpaca.get_positions.return_value = position('XYZ', 100.0, 150.0)   # +50%, not extended
    sigs = pm.check_trim_signals('XYZ')
    assert len(sigs) == 1, f"expected one trim, got {sigs}"
    assert sigs[0]['rung'] == 0.50 and sigs[0]['trim_pct'] == 0.10


def test_gate_applies_to_first_rung_only():
    """At +100% the stock is deeply extended. The gate applies to the first rung only,
    so the +100% rung still fires — on the next scan, since one rung fires per scan."""
    pm = make_pm(2.50)
    pm.alpaca.get_positions.return_value = position('XYZ', 100.0, 200.0)   # +100%
    first = pm.check_trim_signals('XYZ')
    assert first == [], f"first scan should skip the +50% rung, got {first}"
    assert 0.50 in pm.ladder_state['XYZ']['rungs_fired']
    second = pm.check_trim_signals('XYZ')
    assert len(second) == 1 and second[0]['rung'] == 1.00, f"got {second}"


def test_uncomputable_extension_fires_normally():
    """No data -> cannot conclude parabolic -> trim rather than hold."""
    pm = make_pm(None)
    pm.alpaca.get_positions.return_value = position('XYZ', 100.0, 150.0)
    sigs = pm.check_trim_signals('XYZ')
    assert len(sigs) == 1 and sigs[0]['rung'] == 0.50, f"got {sigs}"


def test_gate_reapplies_each_cycle():
    """After a re-base, the first rung of the new cycle is gated again.

    The re-base itself (top rung fires, state clears, base resets) is already covered by
    test_nash_ladder.py's saturated-state case, so this puts the ladder directly into a
    post-re-base state and checks the gate still applies to the fresh cycle's first rung.
    """
    pm = make_pm(1.30)
    pm.ladder_state['XYZ'] = {'base_price': 300.0, 'rungs_fired': [],
                              'initialised_at': '2026-10-17T00:00:00'}
    # +50% above the new base is $450. Parabolic again -> skipped.
    pm.alpaca.get_positions.return_value = position('XYZ', 300.0, 450.0)
    sigs = pm.check_trim_signals('XYZ')
    assert sigs == [], f"cycle 2 should also skip, got {sigs}"
    assert 0.50 in pm.ladder_state['XYZ']['rungs_fired']


def test_no_position_returns_empty():
    pm = make_pm(1.30)
    pm.alpaca.get_positions.return_value = []
    assert pm.check_trim_signals('NOPE') == []


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")
