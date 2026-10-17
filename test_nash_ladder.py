"""Read-only verification of the Tom Nash trim framework.

Calls the checks and helpers ONLY. Never run_position_management() or execute_trim() -
those place real orders.
"""
import json

from position_manager import PositionManager

pm = PositionManager()

print("=== RULES ===")
for k, v in pm.trim_rules.items():
    print(f"    {k:20} {v}")

print()
print("=== LADDER SIMULATION (synthetic, no orders) ===")
for label, base, now, fired in (
        ("fresh, +40% (below first rung)", 100.0, 140.0, []),
        ("fresh, +60%", 100.0, 160.0, []),
        ("fresh, +110% (one rung per scan)", 100.0, 210.0, []),
        ("+50 fired, now +120%", 100.0, 220.0, [0.5]),
        ("+50,+100 fired, now +160%", 100.0, 260.0, [0.5, 1.0]),
        ("saturated state, +200% (self-heals)", 100.0, 300.0, [0.5, 1.0, 1.5])):
    pm.ladder_state['SYN'] = {'base_price': base, 'rungs_fired': list(fired)}
    st = pm.next_rung('SYN', base, now)
    print(f"    {label:38} gain {st['gain_from_base']:+6.0%}  "
          f"next={st['next_rung']}  fired={st['rungs_fired']}")
pm.ladder_state.pop('SYN', None)

print()
print("=== LIVE LADDER POSITIONS ===")
equity = float(pm.alpaca.get_account()['equity'])
print(f"    equity ${equity:,.2f}")
print(f"    {'sym':6}{'qty':>9}{'base':>11}{'now':>10}{'gain':>9}{'next rung':>14}{'% eq':>8}")
for pos in sorted(pm.alpaca.get_positions(), key=lambda p: -float(p['market_value'])):
    st = pm.next_rung(pos['symbol'], float(pos['avg_entry_price']), float(pos['current_price']))
    nxt = f"+{st['next_rung'][0]:.0%}->{st['next_rung'][1]:.0%}" if st['next_rung'] else "all fired"
    print(f"    {pos['symbol']:6}{float(pos['qty']):>9.2f}{st['base_price']:>11,.2f}"
          f"{float(pos['current_price']):>10,.2f}{st['gain_from_base']:>+9.1%}{nxt:>14}"
          f"{float(pos['market_value']) / equity:>8.1%}")

print()
print("=== LADDER TRIM SIGNALS ===")
fired_any = False
for pos in pm.alpaca.get_positions():
    for s in pm.check_trim_signals(pos['symbol']):
        fired_any = True
        print(f"    {pos['symbol']}: {s['reason']}")
print("    none - no rung crossed" if not fired_any else "")

print()
print("=== POSITION CAP (over 10% of equity) ===")
caps = pm.position_cap_signals()
total = 0.0
for c in caps:
    px = next(float(p['current_price']) for p in pm.alpaca.get_positions()
              if p['symbol'] == c['symbol'])
    total += c['shares_to_sell'] * px
    print(f"    {c['symbol']:6} {c['current_pct']:>6.1%} -> {c['cap_pct']:.0%}   "
          f"sell {c['shares_to_sell']:>7.2f} sh  (${c['shares_to_sell'] * px:>9,.2f})")
print(f"    total cash freed ${total:,.2f}" if caps else "    all within cap")

print()
print("=== ADD CANDIDATES (report only, never auto-bought) ===")
adds = pm.add_signals()
for a in adds:
    print(f"    {a['symbol']}: {a['reason']}")
print("    none" if not adds else "")

print()
print("=== PERSISTED LADDER STATE ===")
print("   ", json.dumps(pm.ladder_state, indent=2) if pm.ladder_state else "(empty - written on first trim)")
