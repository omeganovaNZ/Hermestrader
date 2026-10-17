"""Regression check for the trim rules.

Read-only: calls check_trim_signals() and the cooldown helpers, never execute_trim()
or run_position_management() - those place real orders.
"""
from datetime import datetime, timedelta

from position_manager import PositionManager

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
print(f"    phantom LLY entries (never filled) -> {pm.in_cooldown('LLY')}   expect (False, 0)")
print(f"    no history (RKLB)                  -> {pm.in_cooldown('RKLB')}   expect (False, 0)")

saved = list(pm.trim_log)
for days, expect in ((0, "(True, 30)"), (29, "(True, 1)"), (31, "(False, 0)")):
    pm.trim_log = [{
        'date': (datetime.now() - timedelta(days=days)).isoformat(),
        'symbol': 'RKLB', 'action': 'TRIM', 'fill_state': 'FILLED',
        'shares_sold': 51.6, 'trim_pct': 0.2, 'order_id': 'synthetic', 'reason': 'test',
    }]
    print(f"    trimmed {days:>2}d ago -> {pm.in_cooldown('RKLB')}   expect {expect}")
pm.trim_log = saved

print()
print("=== LIVE SIGNALS ===")
for pos in sorted(pm.alpaca.get_positions(), key=lambda p: p['symbol']):
    sym = pos['symbol']
    sigs = pm.check_trim_signals(sym, "US_TECH")
    on_cd, left = pm.in_cooldown(sym)
    if not sigs:
        print(f"    {sym:5} no trim signal")
        continue
    for s in sigs:
        print(f"    {sym:5} {s['type']}: {s['reason']}")
        if s.get('action') == 'TRIM':
            qty = float(pos['qty'])
            state = f"SUPPRESSED, {left}d cooldown left" if on_cd else "cooldown clear"
            print(f"          -> would order {round(qty * s['trim_pct'], 4)} sh "
                  f"({s['trim_pct']:.0%} of {qty:.0f})  {state}")
