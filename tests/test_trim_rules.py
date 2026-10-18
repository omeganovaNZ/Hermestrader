"""Regression check for the trim rules.

Read-only: calls check_trim_signals() and the cooldown helpers, never execute_trim()
or run_position_management() - those place real orders.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta

from src.position_manager import PositionManager

pm = PositionManager()

print("=== TRIM RULES ===")
for k, v in pm.trim_rules.items():
    print(f"    {k:20} {v}")

print()
print("=== 20% IS A TRUE 20% OF SHARES HELD (fractional) ===")
for pos in sorted(pm.alpaca.get_positions(), key=lambda p: p['symbol']):
    qty = float(pos['qty'])
    new = round(qty * 0.20, 4)
    old = int(qty * 0.20)
    note = f"   [old int(): {old} = {old / qty * 100:.1f}%]" if abs(new - old) > 1e-9 else ""
    print(f"    {pos['symbol']:5} {qty:>7.2f} sh -> sell {new:>7.2f} "
          f"({new / qty * 100:5.1f}%){note}")

print()
print("=== COOLDOWN BOUNDARIES ===")
print("    (cooldown was dropped - profit trim is self-limiting via re-basing)")
print()

print("=== LIVE SIGNALS ===")
for pos in sorted(pm.alpaca.get_positions(), key=lambda p: p['symbol']):
    sym = pos['symbol']
    sigs = pm.check_trim_signals(sym, "US_TECH")
    if not sigs:
        print(f"    {sym:5} no trim signal")
        continue
    for s in sigs:
        print(f"    {sym:5} {s['type']}: {s['reason']}")
        if s.get('action') == 'TRIM':
            qty = float(pos['qty'])
            print(f"          -> would order {round(qty * s['trim_pct'], 4)} sh "
                  f"({s['trim_pct']:.0%} of {qty:.0f})")
