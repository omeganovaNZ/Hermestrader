"""
Position Management — profit-trim framework.

Trimming is risk management, not a reaction to weakness. "Selling is what you do when the
business is broken. Trimming is what you do when the winner has grown."

THE PROFIT-TRIM RULE (replaced the trim ladder, 2026-10-17).
A position is trimmed ONLY when ALL FOUR of these hold:

  1. it has been held LONGER than 6 months
  2. it is up +100% ROI from its reference price — the average entry price until the first
     trim, then the price at which that trim was placed
  3. the last 2 days both closed DOWN
  4. it is still above its 200-day average, so the pullback is against the trend rather
     than a trend break

...and then it sells 20% of the shares held.

Growth alone never trims: a position that keeps rising is left to run. After a trim the
reference re-bases to the trim price, so the next trim needs another +100% FROM THERE —
one trim event per doubling, never a cascade. At no other time is invested capital trimmed.

This replaced the +50%/+100%/+150% ladder and its adaptive parabolic gate. The old ladder
trimmed at +50%, which sold into the early stage of the best performers; this rule leaves a
position alone until it has doubled, and even then takes only 20% off, and only into a
pullback rather than into strength.

Also enforced:
  - max_position_pct — no position above this share of portfolio equity. An over-cap
    position is trimmed down to the cap, but WINNERS ONLY: an over-cap position that is
    DOWN is left alone (it stays an add candidate), because enforcing the cap on a loser
    sells it at a loss.
  - add_drawdown — a position this far below its 52-week high is an ADD candidate.
    Weakness is a buying opportunity, not a trim trigger.

Selling a position OUTRIGHT is deliberately not automatic. A broken thesis is a judgement
about the business, which no price can compute, so thesis_break_exit() is an explicit call
and the scan only reports candidates.
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.alpaca_trader import AlpacaTrader
from src.ensemble_trader import EnsembleTrader
from src.trading_strategy_engine import fetch_data
from src.portfolio_rules import (MAX_THEME_PCT, theme_exposure, unclassified_exposure,
                             thesis_review)

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PositionManager:
    """Trimming and profit-taking under the Tom Nash framework."""

    def __init__(self):
        self.alpaca = AlpacaTrader()
        self.ensemble = EnsembleTrader()

        self.trim_rules = {
            # THE profit-trim rule (2026-10-17). One rung, one trigger, one size:
            #   +100% ROI, held LONGER than 6 months, on a 2-day pullback, still above
            #   the 200-day average.
            # Nothing else ever trims invested capital. A trim re-bases the ROI reference
            # to the trim price, so the next trim needs another +100% from THERE - one
            # trim event per doubling, never a cascade.
            'profit_trim_pct': 1.00,     # +100% ROI from the reference price
            'profit_trim_size': 0.20,    # sell 20% of shares held
            'min_hold_days': 183,        # held LONGER than 6 months
            'pullback_days': 2,          # consecutive down days that trigger the trim
            'trend_ma': 200,             # the pullback must still be above this average
            'max_position_pct': 0.10,    # cap trim (Winners Only) - Nash 5-10%
            'add_drawdown': 0.20,        # add when 20% off the 52-week high
        }

        self.trim_log = []
        self.trim_log_path = os.path.join(_HERE, "data", "trim_log.json")
        if os.path.exists(self.trim_log_path):
            try:
                with open(self.trim_log_path, 'r') as f:
                    self.trim_log = json.load(f)
            except (ValueError, OSError):
                print("  WARNING: trim_log.json unreadable - starting fresh")
                self.trim_log = []

        # Per-symbol ladder state: {"MRVL": {"base_price": 235.29, "rungs_fired": [0.5]}}
        self.ladder_state_path = os.path.join(_HERE, "data", "trim_ladder_state.json")
        self.ladder_state = {}
        if os.path.exists(self.ladder_state_path):
            loaded = None
            try:
                with open(self.ladder_state_path, 'r') as f:
                    loaded = json.load(f)
            except (ValueError, OSError):
                pass
            if isinstance(loaded, dict):
                self.ladder_state = loaded
            else:
                # Corrupt, truncated, or valid JSON that is not an object (e.g. a
                # list or string): every symbol re-initialises from avg_entry_price
                # on first sight, so a bad file must never brick the scanner.
                print("  WARNING: trim_ladder_state.json unreadable - re-initialising")
                self.ladder_state = {}

    # ── ladder state ────────────────────────────────────────────────────────────────

    def save_ladder_state(self) -> None:
        # Write to a temp file and rename, so a crash mid-write cannot leave a
        # truncated (unparseable) state file behind.
        os.makedirs(os.path.dirname(self.ladder_state_path), exist_ok=True)
        tmp = self.ladder_state_path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(self.ladder_state, f, indent=2)
        os.replace(tmp, self.ladder_state_path)

    def ladder_entry(self, symbol: str, avg_entry_price: float) -> Dict:
        """Ladder state for symbol, initialised from the entry price on first sight."""
        entry = self.ladder_state.get(symbol)
        if not isinstance(entry, dict):
            entry = {'base_price': float(avg_entry_price), 'rungs_fired': [],
                     'initialised_at': datetime.now().isoformat()}
            self.ladder_state[symbol] = entry
        entry.setdefault('rungs_fired', [])
        return entry

    def profit_trim_status(self, symbol: str, avg_entry_price: float,
                           current_price: float) -> Dict:
        """Where this position sits against the single +100% profit-trim rung. Read-only.

        `base_price` is the ROI reference: the average entry price until the first trim,
        then the price at which that trim was placed. So `gain_from_base` is the ROI that
        matters, and it resets to 0 on every trim.

        Read-only: does NOT call ladder_entry() or mutate any state. If the symbol has
        no ladder entry yet, falls back to avg_entry_price as the base.
        """
        entry = self.ladder_state.get(symbol)
        if not isinstance(entry, dict):
            base = float(avg_entry_price)
            trim_count = 0
            last_trim_price = None
        else:
            base = float(entry.get('base_price', avg_entry_price))
            trim_count = int(entry.get('trim_count', 0))
            last_trim_price = entry.get('last_trim_price')
        gain = (current_price / base) - 1 if base > 0 else 0.0
        target = float(self.trim_rules['profit_trim_pct'])
        return {
            'base_price': base,
            'gain_from_base': gain,
            'target': target,
            'distance_to_trim': target - gain,
            'eligible_on_gain': gain >= target,
            'trim_count': trim_count,
            'last_trim_price': last_trim_price,
        }

    def _daily_closes(self, symbol: str) -> Optional[List[float]]:
        """Completed daily closes, oldest first. None when they cannot be fetched.

        Sourced from Alpaca, not yfinance: yfinance intermittently returns a trailing
        partial bar (Volume present, OHLC NaN), which is exactly the kind of silent
        corruption that must never reach a trim decision.
        """
        try:
            data = self.alpaca.get_historical_data(symbol, days=400)
            if data is None or 'Close' not in data:
                return None
            closes = [float(x) for x in data['Close'].tolist() if x == x]   # drop NaN
            return closes or None
        except Exception:
            return None

    def consecutive_down_days(self, closes: List[float]) -> int:
        """How many days in a row the close has fallen, counting back from the latest."""
        n = 0
        for i in range(len(closes) - 1, 0, -1):
            if closes[i] < closes[i - 1]:
                n += 1
            else:
                break
        return n

    # ── trims ───────────────────────────────────────────────────────────────────────

    def check_trim_signals(self, symbol: str, config_name: Optional[str] = None) -> List[Dict]:
        """THE profit-trim rule. All four conditions must hold, or nothing is trimmed:

          1. held LONGER than 6 months
          2. +100% ROI from the reference price (cost basis, then the last trim price)
          3. the last 2 days both closed DOWN
          4. still above the 200-day average, so the pullback is against the trend
             rather than a trend break

        Growth alone never trims - a position that keeps rising is left to run. This is
        the ONLY thing that trims invested capital; the position cap is a separate rule
        that only ever trims winners.
        """
        signals = []
        position = next((p for p in self.alpaca.get_positions() if p['symbol'] == symbol), None)
        if position is None:
            return signals

        try:
            avg_entry = float(position['avg_entry_price'])
            current = float(position['current_price'])
            qty = float(position['qty'])

            # 1. holding period. "Unknown" must NOT read as "old enough" - trimming a
            # position held under 6 months is the one thing this rule forbids.
            opened = self.alpaca.get_first_buy_date(symbol)
            if opened is None:
                print(f"  {symbol}: holding period unknown - not trimming")
                return signals
            now = datetime.now(opened.tzinfo) if opened.tzinfo else datetime.now()
            held_days = (now - opened).days
            min_days = int(self.trim_rules['min_hold_days'])
            if held_days <= min_days:
                return signals

            # 2. the ROI that matters
            st = self.profit_trim_status(symbol, avg_entry, current)
            target = float(self.trim_rules['profit_trim_pct'])
            if st['gain_from_base'] < target:
                return signals

            # 3. a pullback: consecutive down days
            closes = self._daily_closes(symbol)
            ma_days = int(self.trim_rules['trend_ma'])
            if closes is None or len(closes) < ma_days:
                print(f"  {symbol}: not enough price history to judge the pullback "
                      f"- not trimming")
                return signals
            down = self.consecutive_down_days(closes)
            if down < int(self.trim_rules['pullback_days']):
                return signals

            # 4. the pullback must not match the trend: still above the 200-day average
            sma = sum(closes[-ma_days:]) / ma_days
            if current <= sma:
                print(f"  {symbol}: {down} down days but below its {ma_days}-day average "
                      f"(${sma:,.2f}) - a trend break, not a pullback - not trimming")
                return signals

            # never stack a second order while one is pending
            try:
                pending = {o['symbol'] for o in self.alpaca.get_open_orders()
                           if str(o.get('side', '')).lower() == 'sell'}
            except Exception:
                pending = set()
            if symbol in pending:
                print(f"  {symbol}: a sell order is already pending - not trimming")
                return signals

            size = float(self.trim_rules['profit_trim_size'])
            signals.append({
                'type': 'PROFIT_TRIM_100',
                'action': 'TRIM',
                'trim_pct': size,
                'rung': target,
                'gain_from_base': st['gain_from_base'],
                'base_price': st['base_price'],
                'held_days': held_days,
                'down_days': down,
                'sma200': round(sma, 2),
                'shares_to_sell': round(qty * size, 4),
                'reason': (f'+{st["gain_from_base"]:.0%} ROI from ${st["base_price"]:,.2f}, '
                           f'held {held_days}d, {down} down days but still above the '
                           f'{ma_days}-day (${sma:,.2f}) - trim {size:.0%} of shares held'),
            })
        except Exception as e:
            import traceback
            print(f"  {symbol}: check_trim_signals FAILED - {type(e).__name__}: {e}")
            traceback.print_exc()
            return signals
        return signals

    def position_cap_signals(self) -> List[Dict]:
        """Positions above max_position_pct of equity, to be trimmed back to the cap."""
        account = self.alpaca.get_account()
        equity = float(account['equity'])
        if equity <= 0:
            return []

        # A cap trim is placed with no ladder rung, so the ladder's fired-rung
        # guard does not cover it: while a cap-trim sell order is still pending
        # the position still looks over-cap and a second identical order would
        # be placed. Skip symbols that already have a pending sell order.
        # If the query fails we trim as before (fail open) - silently refusing
        # to trim would disable the cap.
        try:
            pending_sells = {o['symbol'] for o in self.alpaca.get_open_orders()
                             if str(o.get('side', '')).lower() == 'sell'}
        except Exception:
            pending_sells = set()

        out = []
        for pos in self.alpaca.get_positions():
            try:
                mv = float(pos['market_value'])
                pct = mv / equity
                cap = self.trim_rules['max_position_pct']
                if pct > cap:
                    # Trim WINNERS ONLY. Trimming is risk management on something that
                    # has grown, never a reaction to weakness. An over-cap position that
                    # is DOWN is left alone even though that leaves the cap breached,
                    # because enforcing the cap on a loser sells it at a loss - the one
                    # thing the trim path must not do. It remains an ADD candidate.
                    pl = float(pos['unrealized_pl'])
                    if not (pl > 0):  # NaN-safe: NaN > 0 is False
                        print(f"  {pos['symbol']}: over cap ({pct:.1%} vs {cap:.0%}) but "
                              f"down {pl:,.2f} - a loser, not trimming")
                        continue
                    if pos['symbol'] in pending_sells:
                        print(f"  {pos['symbol']}: over cap but a cap trim is already "
                              f"pending - skipping")
                        continue
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
            except Exception as e:
                print(f"  {pos.get('symbol', '?')}: position_cap_signals SKIPPED - "
                      f"{type(e).__name__}: {e}")
                continue
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
                    except Exception as e:
                        print(f"  Ensemble score failed for {sym}: {type(e).__name__}: {e}")
                    out.append({
                        'type': 'ADD_CANDIDATE',
                        'action': 'REPORT_ONLY',
                        'symbol': sym,
                        'drawdown_from_52w_high': dd,
                        'reason': (f'{dd:.0%} off its 52-week high (${high:,.2f}) - an ADD '
                                   f'candidate, not a trim{note}'),
                    })
            except Exception as e:
                print(f"  {sym}: add_signals SKIPPED - {type(e).__name__}: {e}")
                continue
        return out

    def theme_signals(self) -> List[Dict]:
        """Theme (sleeve) exposure against the cap, plus anything unclassified.

        REPORT ONLY. The cap itself is enforced at the buy path
        (`portfolio_rules.theme_cap_check`); this exists so the exposure is visible on every
        scan instead of being discovered months later at 75% of long market value.
        """
        account = self.alpaca.get_account()
        equity = float(account['equity'])
        positions = self.alpaca.get_positions()

        out = []
        for th, b in sorted(theme_exposure(positions, equity).items(),
                            key=lambda kv: -kv[1]['value']):
            over = b['pct'] > MAX_THEME_PCT
            out.append({
                'type': 'THEME_EXPOSURE', 'action': 'REPORT_ONLY', 'theme': th,
                'pct': b['pct'], 'value': b['value'], 'symbols': b['symbols'],
                'over_cap': over,
                'reason': (f"{th} is {b['pct']:.1%} of equity - "
                           f"{'OVER' if over else 'within'} the {MAX_THEME_PCT:.0%} cap "
                           f"({', '.join(b['symbols'])})"),
            })

        un = unclassified_exposure(positions, equity)
        if un['symbols']:
            out.append({
                'type': 'THEME_UNCLASSIFIED', 'action': 'REPORT_ONLY', 'theme': None,
                'pct': un['pct'], 'value': un['value'], 'symbols': un['symbols'],
                'over_cap': False,
                'reason': (f"UNCLASSIFIED {un['pct']:.1%} of equity "
                           f"({', '.join(un['symbols'])}) - no theme cap applies to these, "
                           f"so add them to portfolio_rules.THEMES"),
            })
        return out

    def thesis_review_signals(self) -> List[Dict]:
        """Positions worth a human look: held long and materially down.

        NEVER SELLS. The owner's rule is that invested capital is not trimmed on weakness,
        so this only surfaces the ones that deserve a decision - which is the gap the system
        had, since the profit trim needs +100% and the cap trim only sells winners.
        """
        positions = self.alpaca.get_positions()
        held = {}
        for p in positions:
            sym = p['symbol']
            try:
                opened = self.alpaca.get_first_buy_date(sym)
            except Exception:
                opened = None
            if opened is None:
                held[sym] = None                      # unknown age is not "old enough"
                continue
            now = datetime.now(opened.tzinfo) if opened.tzinfo else datetime.now()
            held[sym] = (now - opened).days
        return thesis_review(positions, held)

    # ── execution ───────────────────────────────────────────────────────────────────

    def execute_trim(self, symbol: str, trim_pct: float, reason: str,
                     rung: Optional[float] = None, re_base: bool = False) -> bool:
        """Place a trim (fractional). Records the real order state, never assumes a fill."""
        # Validate trim_pct is between 0 and 1
        if not (0 < trim_pct <= 1) or trim_pct != trim_pct:
            print(f"  {symbol}: invalid trim_pct {trim_pct} - must be in (0, 1]")
            return False

        # Never stack a second sell order while one is pending
        try:
            pending = {o['symbol'] for o in self.alpaca.get_open_orders()
                       if str(o.get('side', '')).lower() == 'sell'}
            if symbol in pending:
                print(f"  {symbol}: a sell order is already pending - not stacking trim")
                return False
        except Exception:
            pass  # fail open — if we can't check, proceed

        position = next((p for p in self.alpaca.get_positions() if p['symbol'] == symbol), None)
        if position is None:
            return False

        qty = float(position['qty'])
        if not (qty > 0) or qty != qty:  # NaN or non-positive
            return False
        shares_to_sell = round(qty * trim_pct, 4)
        # Cap at qty — never sell more than we hold
        shares_to_sell = min(shares_to_sell, qty)
        if not (shares_to_sell > 0) or shares_to_sell != shares_to_sell:  # NaN or non-positive
            return False

        try:
            order = self.alpaca.place_sell_order(symbol, shares_to_sell)
            if order is None:
                print(f"  {symbol}: place_sell_order returned None - not re-basing ladder")
                return False
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
            _tmp = self.trim_log_path + '.tmp'
            with open(_tmp, 'w') as f:
                json.dump(self.trim_log, f, indent=2)
            os.replace(_tmp, self.trim_log_path)

            # Re-base the ROI reference to the price at which this trim was PLACED, so it
            # cannot re-fire while the order is pending. The next trim therefore needs
            # another +100% from HERE - that is what makes this one trim event per
            # doubling instead of a cascade.
            if rung is not None and filled:
                entry = self.ladder_entry(symbol, float(position['avg_entry_price']))
                if rung not in entry['rungs_fired']:
                    entry['rungs_fired'].append(rung)
                entry['trim_count'] = int(entry.get('trim_count', 0)) + 1
                entry['last_trim_price'] = float(position['current_price'])
                entry['last_trim_at'] = datetime.now().isoformat()
                if re_base:
                    entry['base_price'] = float(position['current_price'])
                    entry['rungs_fired'] = []
                self.save_ladder_state()
            elif rung is not None and not filled:
                print(f"  {symbol}: order {order_status} - NOT re-basing ladder")
            return True
        except Exception:
            return False

    def thesis_break_exit(self, symbol: str, reason: str) -> bool:
        """Sell a position OUTRIGHT. Explicit call only - never triggered by price.

        Selling is for a broken business: deteriorating fundamentals, a lost competitive
        position, a thesis that simply did not happen. It is not a reaction to a drawdown.
        """
        try:
            position = next((p for p in self.alpaca.get_positions() if p['symbol'] == symbol), None)
            if position is None:
                return False
            # Never stack a second sell order while one is pending
            pending = {o['symbol'] for o in self.alpaca.get_open_orders()
                       if str(o.get('side', '')).lower() == 'sell'}
            if symbol in pending:
                print(f"  {symbol}: a sell order is already pending - not stacking thesis exit")
                return False
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
            _tmp = self.trim_log_path + '.tmp'
            with open(_tmp, 'w') as f:
                json.dump(self.trim_log, f, indent=2)
            os.replace(_tmp, self.trim_log_path)
            self.ladder_state.pop(symbol, None)
            self.save_ladder_state()
            return True
        except Exception:
            return False

    # ── scan ────────────────────────────────────────────────────────────────────────

    def run_position_management(self, dry_run: bool = False) -> int:
        print("=" * 80)
        print("  POSITION MANAGEMENT — Profit-Trim Rule")
        if dry_run:
            print("  *** DRY RUN — no orders will be placed ***")
        print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        r = self.trim_rules
        print(f"  Trim when ALL hold: +{r['profit_trim_pct']:.0%} ROI, held > "
              f"{r['min_hold_days']}d, {r['pullback_days']} down days, still above the "
              f"{r['trend_ma']}-day -> sell {r['profit_trim_size']:.0%} of shares held")
        print(f"  Nothing else trims invested capital. The reference re-bases to the trim "
              f"price, so the next trim needs another +{r['profit_trim_pct']:.0%} from there.")
        print(f"  Position cap: {r['max_position_pct']:.0%} of equity (winners only)")
        print("=" * 80)

        try:
            account = self.alpaca.get_account()
            positions = self.alpaca.get_positions()
            equity = float(account['equity'])
        except Exception as e:
            print(f"  FATAL: could not fetch account/positions - {type(e).__name__}: {e}")
            return 0
        print(f"\n  Cash: ${float(account['cash']):,.2f} | Equity: ${equity:,.2f}")
        print(f"  Positions: {len(positions)}")

        print(f"\n  {'sym':6}{'qty':>9}{'entry':>11}{'base':>11}{'now':>10}{'ROI':>9}"
              f"{'to trim':>10}{'held':>7}{'% eq':>8}")
        for pos in sorted(positions, key=lambda p: -float(p.get('market_value', 0))):
            try:
                sym = pos['symbol']
                avg = float(pos['avg_entry_price'])
                now = float(pos['current_price'])
                st = self.profit_trim_status(sym, avg, now)
                held = "?"
                try:
                    opened = self.alpaca.get_first_buy_date(sym)
                    if opened is not None:
                        ref = datetime.now(opened.tzinfo) if opened.tzinfo else datetime.now()
                        held = f"{(ref - opened).days}d"
                except Exception as e:
                    held = "?"
                print(f"  {sym:6}{float(pos['qty']):>9.2f}{avg:>11,.2f}{st['base_price']:>11,.2f}"
                      f"{now:>10,.2f}{st['gain_from_base']:>+9.1%}"
                      f"{st['distance_to_trim']:>+10.0%}{held:>7}"
                      f"{float(pos['market_value'])/equity:>8.1%}")
            except Exception as e:
                print(f"  {pos.get('symbol', '?'):6} DISPLAY SKIPPED - {type(e).__name__}: {e}")

        executed = 0

        print(f"\n{'-' * 80}\n  PROFIT TRIMS (+100% ROI on a 2-day pullback)\n{'-' * 80}")
        any_trim = False
        for pos in positions:
            sym = pos['symbol']
            signals = self.check_trim_signals(sym)
            if not signals:
                continue
            any_trim = True
            s = signals[0]
            print(f"\n  {sym}: {s['reason']}")
            if dry_run:
                print(f"    WOULD TRIM: {s['trim_pct']:.0%} of shares held "
                      f"({s['shares_to_sell']:,.2f} sh)")
                continue
            if self.execute_trim(sym, s['trim_pct'], s['reason'], rung=s['rung'], re_base=True):
                print(f"    TRIMMED: ordered {s['trim_pct']:.0%} of shares held "
                      f"({s['shares_to_sell']:,.2f} sh) - reference re-based to "
                      f"${s['base_price']:,.2f}, so the next trim needs +100% from there")
                executed += 1
            else:
                print("    TRIM FAILED")
        if not any_trim:
            print("  nothing eligible (needs +100% ROI, held >6 months, and 2 down days)")

        print(f"\n{'-' * 80}\n  POSITION CAP\n{'-' * 80}")
        try:
            caps = self.position_cap_signals()
        except Exception as e:
            print(f"  position_cap_signals FAILED - {type(e).__name__}: {e}")
            caps = []
        if not caps:
            print("  no cap trims to place")
        for c in caps:
            print(f"  {c['symbol']}: {c['reason']}")
            if dry_run:
                print(f"    WOULD TRIM: {c['shares_to_sell']:,.2f} shares")
                continue
            if self.execute_trim(c['symbol'], c['trim_pct'], c['reason'],
                                 rung=c.get('cap_rung', 0.10), re_base=False):
                print(f"    TRIMMED: ordered {c['shares_to_sell']:,.2f} shares")
                executed += 1
            else:
                print("    TRIM FAILED")

        print(f"\n{'-' * 80}\n  THEME EXPOSURE (cap {MAX_THEME_PCT:.0%})\n{'-' * 80}")
        try:
            for t in self.theme_signals():
                print(f"  {t['reason']}")
        except Exception as e:
            print(f"  theme_signals FAILED - {type(e).__name__}: {e}")

        print(f"\n{'-' * 80}\n  THESIS REVIEW (report only - never sells)\n{'-' * 80}")
        try:
            revs = self.thesis_review_signals()
        except Exception as e:
            print(f"  thesis_review_signals FAILED - {type(e).__name__}: {e}")
            revs = []
        if not revs:
            print("  nothing flagged")
        for r in revs:
            print(f"  {r['symbol']}: {r['reason']}")

        print(f"\n{'-' * 80}\n  ADD CANDIDATES (report only - never auto-bought)\n{'-' * 80}")
        try:
            adds = self.add_signals()
        except Exception as e:
            print(f"  add_signals FAILED - {type(e).__name__}: {e}")
            adds = []
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
        self.save_ladder_state()
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
