"""
Position Management — Tom Nash framework.

Trimming is risk management, not a reaction to weakness. "Selling is what you do when the
business is broken. Trimming is what you do when the winner has grown."

TRIM LADDER — gain measured from that symbol's ladder base price:
    +50%  -> sell 10% of the shares held
   +100%  -> sell 20%
   +150%  -> sell 30%, then RE-BASE to the current price and climb again

One rung fires per scan, lowest unfired first, so a gap-up climbs the ladder over
successive scans rather than dumping every rung at once.

ADAPTIVE FIRST-RUNG GATE (added 2026-10-17, from a 20-name cross-validation — see
TRADING_PLAYBOOK.md). The first rung's 10% trim is SKIPPED when the move is already
parabolic: at the moment the price first reaches +50% of the ladder base, if
`close / 50-day SMA >= parabolic_ext` (1.20), the rung is marked passed without selling and
the position is allowed to run. The rationale is that a parabolic +50% is usually the early
stage of a multi-bagger, whereas a choppy +50% is a rally worth harvesting — and the two
cannot be told apart by price alone, only by extension. Without the gate the ladder sold
into the early stage of every 5-15x move; with it, the cost on flat/choppy names is
measurably zero (-0.006 mean). The rung is marked passed permanently, matching the design
that was backtested.

Also enforced from the same framework:
  - max_position_pct — no position above this share of portfolio equity. An over-cap
    position is trimmed down to the cap.
  - add_drawdown — a position this far below its 52-week high is an ADD candidate.
    Weakness is a buying opportunity, not a trim trigger.

Selling a position OUTRIGHT is deliberately not automatic. A broken thesis is a judgement
about the business, which no price can compute, so thesis_break_exit() is an explicit call
and the scan only reports candidates.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alpaca_trader import AlpacaTrader
from ensemble_trader import EnsembleTrader
from market_aware_strategy import MarketAwareHybridStrategy, MARKET_CONFIGS
from trading_strategy_engine import fetch_data

_HERE = os.path.dirname(os.path.abspath(__file__))


class PositionManager:
    """Trimming and profit-taking under the Tom Nash framework."""

    def __init__(self):
        self.alpaca = AlpacaTrader()
        self.ensemble = EnsembleTrader()

        self.trim_rules = {
            # (gain from ladder base, fraction of shares held to sell)
            'ladder': [(0.50, 0.10), (1.00, 0.20), (1.50, 0.30)],
            'reset_after_gain': 1.50,   # above the top rung, re-base and climb again
            'max_position_pct': 0.10,   # Nash: 5-10% cap per satellite position
            'add_drawdown': 0.20,       # add when 20% off the 52-week high
            # Adaptive first-rung gate: skip the +50% trim when the move is already
            # parabolic, i.e. close / (parabolic_ma-day SMA) >= parabolic_ext.
            'parabolic_ma': 50,
            'parabolic_ext': 1.20,
        }

        self.trim_log = []
        self.trim_log_path = os.path.join(_HERE, "trim_log.json")
        if os.path.exists(self.trim_log_path):
            with open(self.trim_log_path, 'r') as f:
                self.trim_log = json.load(f)

        # Per-symbol ladder state: {"MRVL": {"base_price": 235.29, "rungs_fired": [0.5]}}
        self.ladder_state_path = os.path.join(_HERE, "trim_ladder_state.json")
        self.ladder_state = {}
        if os.path.exists(self.ladder_state_path):
            with open(self.ladder_state_path, 'r') as f:
                self.ladder_state = json.load(f)

    # ── ladder state ────────────────────────────────────────────────────────────────

    def save_ladder_state(self) -> None:
        with open(self.ladder_state_path, 'w') as f:
            json.dump(self.ladder_state, f, indent=2)

    def ladder_entry(self, symbol: str, avg_entry_price: float) -> Dict:
        """Ladder state for symbol, initialised from the entry price on first sight."""
        entry = self.ladder_state.get(symbol)
        if not isinstance(entry, dict):
            entry = {'base_price': float(avg_entry_price), 'rungs_fired': [],
                     'initialised_at': datetime.now().isoformat()}
            self.ladder_state[symbol] = entry
        entry.setdefault('rungs_fired', [])
        return entry

    def next_rung(self, symbol: str, avg_entry_price: float, current_price: float) -> Dict:
        """Describe where this position sits on its ladder. Read-only."""
        entry = self.ladder_entry(symbol, avg_entry_price)
        base = float(entry['base_price'])
        gain = (current_price / base) - 1 if base > 0 else 0.0
        fired = entry['rungs_fired']
        # Self-heal: a fully-fired ladder should already have re-based when the top rung was
        # placed. If it is still saturated (stale state, or a trim that never got recorded),
        # start a fresh climb from the current price instead of sitting stuck forever.
        if all(g in fired for g, _ in self.trim_rules['ladder']):
            entry['base_price'] = float(current_price)
            entry['rungs_fired'] = []
            entry['rebased_at'] = datetime.now().isoformat()
            base, gain, fired = float(current_price), 0.0, []
        pending = [(g, p) for g, p in self.trim_rules['ladder'] if g not in fired]
        return {
            'base_price': base,
            'gain_from_base': gain,
            'rungs_fired': list(fired),
            'next_rung': pending[0] if pending else None,
            'next_rung_distance': (pending[0][0] - gain) if pending else None,
            'all_rungs_fired': not pending,
        }

    def ma_extension(self, symbol: str, current_price: float) -> Optional[float]:
        """How extended the move already is: current_price / N-day SMA.

        Returns None when the average cannot be computed (no data, or a non-positive
        average); the caller then treats the gate as untriggered and fires the rung
        normally, since refusing to trim is the riskier failure.
        """
        ma = int(self.trim_rules.get('parabolic_ma', 50))
        try:
            data = fetch_data(symbol, "1y")
            sma = float(data['Close'].rolling(ma).mean().iloc[-1])
            if sma <= 0:
                return None
            return float(current_price) / sma
        except Exception:
            return None

    # ── trims ───────────────────────────────────────────────────────────────────────

    def check_trim_signals(self, symbol: str, config_name: Optional[str] = None) -> List[Dict]:
        """Ladder rungs only. A crossed-but-unfired rung is the sole trim trigger.

        The first rung is subject to the adaptive parabolic gate: if the move is already
        extended when the price first reaches +50% of the base, the rung is marked passed
        without selling and the position is allowed to run.
        """
        signals = []
        position = next((p for p in self.alpaca.get_positions() if p['symbol'] == symbol), None)
        if position is None:
            return signals

        try:
            avg_entry = float(position['avg_entry_price'])
            current = float(position['current_price'])
            st = self.next_rung(symbol, avg_entry, current)
            entry = self.ladder_entry(symbol, avg_entry)

            for idx, (gain_rung, trim_pct) in enumerate(self.trim_rules['ladder']):
                if gain_rung in st['rungs_fired']:
                    continue
                if st['gain_from_base'] >= gain_rung:
                    if idx == 0:
                        ext = self.ma_extension(symbol, current)
                        if ext is not None and ext >= float(self.trim_rules['parabolic_ext']):
                            entry['rungs_fired'].append(gain_rung)
                            self.save_ladder_state()
                            break
                    signals.append({
                        'type': f'LADDER_{int(gain_rung * 100)}',
                        'action': 'TRIM',
                        'trim_pct': trim_pct,
                        'rung': gain_rung,
                        'gain_from_base': st['gain_from_base'],
                        'base_price': st['base_price'],
                        'reason': (f'+{st["gain_from_base"]:.0%} from ladder base '
                                   f'${st["base_price"]:,.2f} crossed the +{gain_rung:.0%} rung '
                                   f'- trim {trim_pct:.0%}'),
                    })
                    break   # one rung per scan, lowest unfired first
        except Exception:
            return signals
        return signals

    def position_cap_signals(self) -> List[Dict]:
        """Positions above max_position_pct of equity, to be trimmed back to the cap."""
        account = self.alpaca.get_account()
        equity = float(account['equity'])
        if equity <= 0:
            return []
        out = []
        for pos in self.alpaca.get_positions():
            mv = float(pos['market_value'])
            pct = mv / equity
            cap = self.trim_rules['max_position_pct']
            if pct > cap:
                target_mv = equity * cap
                excess = mv - target_mv
                qty = float(pos['qty'])
                shares = min(round(excess / float(pos['current_price']), 4), qty)
                out.append({
                    'type': 'OVER_POSITION_CAP',
                    'action': 'TRIM_TO_CAP',
                    'symbol': pos['symbol'],
                    'trim_pct': round(shares / qty, 4) if qty else 0,
                    'current_pct': pct,
                    'cap_pct': cap,
                    'shares_to_sell': shares,
                    'reason': (f'{pct:.1%} of equity vs the {cap:.0%} cap '
                               f'- trim {shares:,.2f} of {qty:,.2f} sh back to cap'),
                })
        return out

    def add_signals(self) -> List[Dict]:
        """Positions far enough below their 52-week high to be ADD candidates."""
        out = []
        for pos in self.alpaca.get_positions():
            sym = pos['symbol']
            try:
                data = fetch_data(sym, "1y")
                high = float(data['Close'].max())
                current = float(pos['current_price'])
                if high <= 0:
                    continue
                dd = (current / high) - 1
                if dd <= -self.trim_rules['add_drawdown']:
                    note = ' | ensemble n/a'
                    try:
                        score = self.ensemble.generate_ensemble_signal(sym, "US_TECH").get('ensemble_score')
                        if score == score:
                            note = f' | ensemble {score:+.3f}'
                    except Exception:
                        pass
                    out.append({
                        'type': 'ADD_CANDIDATE',
                        'action': 'REPORT_ONLY',
                        'symbol': sym,
                        'drawdown_from_52w_high': dd,
                        'reason': (f'{dd:.0%} off its 52-week high (${high:,.2f}) - an ADD '
                                   f'candidate, not a trim{note}'),
                    })
            except Exception:
                continue
        return out

    # ── execution ───────────────────────────────────────────────────────────────────

    def execute_trim(self, symbol: str, trim_pct: float, reason: str,
                     rung: Optional[float] = None, re_base: bool = False) -> bool:
        """Place a trim (fractional). Records the real order state, never assumes a fill."""
        position = next((p for p in self.alpaca.get_positions() if p['symbol'] == symbol), None)
        if position is None:
            return False

        qty = float(position['qty'])
        shares_to_sell = round(qty * trim_pct, 4)
        if shares_to_sell <= 0:
            return False

        try:
            order = self.alpaca.place_sell_order(symbol, shares_to_sell)
            order_id = getattr(order, 'id', None)
            order_status = str(getattr(order, 'status', 'unknown'))
            filled = order_status.lower().endswith('filled')

            self.trim_log.append({
                'date': datetime.now().isoformat(),
                'symbol': symbol,
                'action': 'TRIM',
                'order_id': str(order_id) if order_id else None,
                'order_status': order_status,
                'fill_state': 'FILLED' if filled else 'PENDING',
                'shares_sold': shares_to_sell if filled else 0,
                'shares_ordered': shares_to_sell,
                'trim_pct': trim_pct,
                'ladder_rung': rung,
                'reason': reason,
                'remaining_shares': round(qty - shares_to_sell, 4),
            })
            with open(self.trim_log_path, 'w') as f:
                json.dump(self.trim_log, f, indent=2)

            # Mark the rung fired as soon as the order is PLACED, so it cannot re-fire while
            # pending. A re-base starts the ladder over from the current price.
            if rung is not None:
                entry = self.ladder_entry(symbol, float(position['avg_entry_price']))
                if rung not in entry['rungs_fired']:
                    entry['rungs_fired'].append(rung)
                if re_base:
                    entry['base_price'] = float(position['current_price'])
                    entry['rungs_fired'] = []
                    entry['rebased_at'] = datetime.now().isoformat()
                self.save_ladder_state()
            return True
        except Exception:
            return False

    def thesis_break_exit(self, symbol: str, reason: str) -> bool:
        """Sell a position OUTRIGHT. Explicit call only - never triggered by price.

        Selling is for a broken business: deteriorating fundamentals, a lost competitive
        position, a thesis that simply did not happen. It is not a reaction to a drawdown.
        """
        position = next((p for p in self.alpaca.get_positions() if p['symbol'] == symbol), None)
        if position is None:
            return False
        try:
            order = self.alpaca.place_sell_order(symbol, round(float(position['qty']), 4))
            status = str(getattr(order, 'status', 'unknown'))
            self.trim_log.append({
                'date': datetime.now().isoformat(),
                'symbol': symbol,
                'action': 'THESIS_BREAK_EXIT',
                'order_id': str(getattr(order, 'id', None)),
                'order_status': status,
                'fill_state': 'FILLED' if status.lower().endswith('filled') else 'PENDING',
                'shares_ordered': float(position['qty']),
                'reason': reason,
            })
            with open(self.trim_log_path, 'w') as f:
                json.dump(self.trim_log, f, indent=2)
            self.ladder_state.pop(symbol, None)
            self.save_ladder_state()
            return True
        except Exception:
            return False

    # ── scan ────────────────────────────────────────────────────────────────────────

    def run_position_management(self, dry_run: bool = False) -> int:
        print("=" * 80)
        print("  POSITION MANAGEMENT — Tom Nash Trim Ladder")
        if dry_run:
            print("  *** DRY RUN — no orders will be placed ***")
        print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        ladder = " | ".join(f"+{g:.0%}->{p:.0%}" for g, p in self.trim_rules['ladder'])
        print(f"  Ladder: {ladder}, then re-base and climb again")
        print(f"  Position cap: {self.trim_rules['max_position_pct']:.0%} of equity")
        print("=" * 80)

        account = self.alpaca.get_account()
        positions = self.alpaca.get_positions()
        equity = float(account['equity'])
        print(f"\n  Cash: ${float(account['cash']):,.2f} | Equity: ${equity:,.2f}")
        print(f"  Positions: {len(positions)}")

        print(f"\n  {'sym':6}{'qty':>9}{'entry':>11}{'base':>11}{'now':>10}{'gain':>9}"
              f"{'next rung':>14}{'% eq':>8}")
        for pos in sorted(positions, key=lambda p: -float(p['market_value'])):
            sym = pos['symbol']
            avg = float(pos['avg_entry_price'])
            now = float(pos['current_price'])
            st = self.next_rung(sym, avg, now)
            nxt = f"+{st['next_rung'][0]:.0%}->{st['next_rung'][1]:.0%}" if st['next_rung'] else "all fired"
            print(f"  {sym:6}{float(pos['qty']):>9.2f}{avg:>11,.2f}{st['base_price']:>11,.2f}"
                  f"{now:>10,.2f}{st['gain_from_base']:>+9.1%}{nxt:>14}"
                  f"{float(pos['market_value'])/equity:>8.1%}")

        executed = 0

        print(f"\n{'-' * 80}\n  LADDER TRIMS\n{'-' * 80}")
        any_ladder = False
        for pos in positions:
            sym = pos['symbol']
            signals = self.check_trim_signals(sym)
            if not signals:
                continue
            any_ladder = True
            s = signals[0]
            print(f"\n  {sym}: {s['reason']}")
            if dry_run:
                print(f"    WOULD TRIM: {s['trim_pct']:.0%} of shares held "
                      f"({round(float(pos['qty']) * s['trim_pct'], 4):,.2f} sh)")
                continue
            if self.execute_trim(sym, s['trim_pct'], s['reason'], rung=s['rung'],
                                 re_base=(s['rung'] >= self.trim_rules['reset_after_gain'])):
                extra = " (re-based - ladder restarts from here)" if s['rung'] >= self.trim_rules['reset_after_gain'] else ""
                print(f"    TRIMMED: ordered {s['trim_pct']:.0%} of shares held{extra}")
                executed += 1
            else:
                print("    TRIM FAILED")
        if not any_ladder:
            print("  no rung crossed")

        print(f"\n{'-' * 80}\n  POSITION CAP\n{'-' * 80}")
        caps = self.position_cap_signals()
        if not caps:
            print("  all positions within cap")
        for c in caps:
            print(f"  {c['symbol']}: {c['reason']}")
            if dry_run:
                print(f"    WOULD TRIM: {c['shares_to_sell']:,.2f} shares")
                continue
            if self.execute_trim(c['symbol'], c['trim_pct'], c['reason']):
                print(f"    TRIMMED: ordered {c['shares_to_sell']:,.2f} shares")
                executed += 1
            else:
                print("    TRIM FAILED")

        print(f"\n{'-' * 80}\n  ADD CANDIDATES (report only - never auto-bought)\n{'-' * 80}")
        adds = self.add_signals()
        if not adds:
            print("  none")
        for a in adds:
            print(f"  {a['symbol']}: {a['reason']}")

        print(f"\n{'-' * 80}\n  SUMMARY\n{'-' * 80}")
        print(f"  Trims executed: {executed}")
        print(f"  Total trims in log: {len(self.trim_log)}")
        print("\n  Outright exits are never automatic: a position is SOLD only when its")
        print("  thesis breaks, via thesis_break_exit(symbol, reason).")
        print("=" * 80)
        return executed


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Position management — Tom Nash trim ladder.")
    ap.add_argument('--dry-run', action='store_true',
                    help="report what would be trimmed without placing any order")
    args = ap.parse_args()
    PositionManager().run_position_management(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
