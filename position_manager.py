"""
Position Management System
Implements trimming strategy: sell 20% of position when:
1. Return reaches 100% (profit-taking milestone)
2. Ensemble signal turns negative (weakness)
3. Technical indicators show overextension
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


class PositionManager:
    """Manages position trimming and profit-taking."""
    
    def __init__(self):
        self.alpaca = AlpacaTrader()
        self.ensemble = EnsembleTrader()
        
        # Trimming rules
        self.trim_rules = {
            'milestone_return': 1.00,      # Sell 20% at 100% return
            'ensemble_threshold': -0.1,     # Sell 20% when ensemble score < -0.1
            'rsi_overbought': 70,           # Sell 20% when RSI > 70
            'overextension': 0.50,          # Sell 20% when >50% above 200 DMA
            'trim_size': 0.20,             # Sell 20% of position
        }
        
        # Track trimmed positions
        self.trim_log = []
        self.trim_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trim_log.json")
        if os.path.exists(self.trim_log_path):
            with open(self.trim_log_path, 'r') as f:
                self.trim_log = json.load(f)
    
    def get_position_return(self, symbol: str) -> Optional[float]:
        """Calculate current return for a position."""
        positions = self.alpaca.get_positions()
        for pos in positions:
            if pos['symbol'] == symbol:
                return pos['unrealized_pl'] / (pos['avg_entry_price'] * pos['qty'])
        return None
    
    def check_trim_signals(self, symbol: str, config_name: str) -> List[Dict]:
        """Check if a position should be trimmed."""
        signals = []
        
        # Get current position
        positions = self.alpaca.get_positions()
        position = None
        for pos in positions:
            if pos['symbol'] == symbol:
                position = pos
                break
        
        if position is None:
            return signals
        
        # Get current data
        try:
            data = fetch_data(symbol, "6mo")
            if data is None or len(data) < 50:
                return signals
            
            # Calculate indicators
            latest = data.iloc[-1]
            close = float(latest['Close'])
            
            # RSI
            delta = data['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = float(100 - (100 / (1 + rs.iloc[-1])))
            
            # Distance from 200 DMA
            sma_200 = float(data['Close'].rolling(200).mean().iloc[-1])
            dist_200 = (close / sma_200) - 1 if sma_200 > 0 else 0
            
            # Current return
            current_return = position['unrealized_pl'] / (position['avg_entry_price'] * position['qty'])
            
            # Check milestone return (100%)
            if current_return >= self.trim_rules['milestone_return']:
                signals.append({
                    'type': 'MILESTONE_RETURN',
                    'reason': f'Return reached {current_return:.0%} (target: {self.trim_rules["milestone_return"]:.0%})',
                    'action': 'TRIM',
                    'trim_pct': self.trim_rules['trim_size'],
                    'current_return': current_return,
                })
            
            # Check RSI overbought
            if rsi > self.trim_rules['rsi_overbought']:
                signals.append({
                    'type': 'RSI_OVERBOUGHT',
                    'reason': f'RSI {rsi:.1f} > {self.trim_rules["rsi_overbought"]}',
                    'action': 'TRIM',
                    'trim_pct': self.trim_rules['trim_size'],
                    'rsi': rsi,
                })
            
            # Check overextension
            if dist_200 > self.trim_rules['overextension']:
                signals.append({
                    'type': 'OVEREXTENSION',
                    'reason': f'Price {dist_200:.0%} above 200 DMA (threshold: {self.trim_rules["overextension"]:.0%})',
                    'action': 'TRIM',
                    'trim_pct': self.trim_rules['trim_size'],
                    'dist_200': dist_200,
                })
            
            # Check ensemble signal
            ensemble_signals = self.ensemble.generate_ensemble_signal(symbol, config_name)
            ensemble_score = ensemble_signals.get('ensemble_score', 0)
            
            if ensemble_score < self.trim_rules['ensemble_threshold']:
                signals.append({
                    'type': 'ENSEMBLE_WEAKNESS',
                    'reason': f'Ensemble score {ensemble_score:.3f} < {self.trim_rules["ensemble_threshold"]}',
                    'action': 'TRIM',
                    'trim_pct': self.trim_rules['trim_size'],
                    'ensemble_score': ensemble_score,
                })
            
        except Exception as e:
            pass
        
        return signals
    
    def execute_trim(self, symbol: str, trim_pct: float, reason: str) -> bool:
        """Execute a trim order (sell % of position)."""
        positions = self.alpaca.get_positions()
        position = None
        for pos in positions:
            if pos['symbol'] == symbol:
                position = pos
                break
        
        if position is None:
            return False
        
        shares_to_sell = int(position['qty'] * trim_pct)
        if shares_to_sell == 0:
            return False
        
        try:
            self.alpaca.place_sell_order(symbol, shares_to_sell)
            
            self.trim_log.append({
                'date': datetime.now().isoformat(),
                'symbol': symbol,
                'action': 'TRIM',
                'shares_sold': shares_to_sell,
                'trim_pct': trim_pct,
                'reason': reason,
                'remaining_shares': position['qty'] - shares_to_sell,
            })
            
            # Save trim log
            with open(self.trim_log_path, 'w') as f:
                json.dump(self.trim_log, f, indent=2)
            
            return True
            
        except Exception as e:
            return False
    
    def run_position_management(self):
        """Run position management scan."""
        print("=" * 80)
        print("  POSITION MANAGEMENT — Trimming Strategy")
        print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"  Rules: 100% return | RSI > 70 | >50% above 200 DMA | Ensemble < -0.1")
        print("=" * 80)
        
        account = self.alpaca.get_account()
        positions = self.alpaca.get_positions()
        
        print(f"\n  Cash: ${account['cash']:,.2f} | Portfolio Value: ${account['portfolio_value']:,.2f}")
        print(f"  Positions: {len(positions)}")
        
        for pos in positions:
            symbol = pos['symbol']
            current_return = pos['unrealized_pl'] / (pos['avg_entry_price'] * pos['qty'])
            print(f"\n  {symbol}: {pos['qty']} shares @ ${pos['avg_entry_price']:.2f} = ${pos['market_value']:,.2f} (return: {current_return:+.1%})")
        
        print(f"\n{'─'*80}")
        print(f"  CHECKING TRIM SIGNALS")
        print(f"{'─'*80}")
        
        trims_executed = 0
        
        for pos in positions:
            symbol = pos['symbol']
            
            # Find config for this symbol
            config_name = "US_TECH"
            for ticker, name, config in self.alpaca.watchlist:
                if ticker == symbol:
                    config_name = config
                    break
            
            # Check trim signals
            signals = self.check_trim_signals(symbol, config_name)
            
            if signals:
                print(f"\n  {symbol}: {len(signals)} trim signal(s)")
                for signal in signals:
                    print(f"    {signal['type']}: {signal['reason']}")
                
                # Execute trim (only one trim per position per scan)
                first_signal = signals[0]
                success = self.execute_trim(symbol, first_signal['trim_pct'], first_signal['reason'])
                
                if success:
                    print(f"    TRIMMED: Sold {first_signal['trim_pct']:.0%} of position")
                    trims_executed += 1
                else:
                    print(f"    TRIM FAILED")
            else:
                print(f"\n  {symbol}: No trim signals")
        
        print(f"\n{'─'*80}")
        print(f"  SUMMARY")
        print(f"{'─'*80}")
        print(f"  Trims executed: {trims_executed}")
        print(f"  Total trims in log: {len(self.trim_log)}")
        
        if self.trim_log:
            print(f"\n  Recent trims:")
            for trim in self.trim_log[-5:]:
                print(f"    {trim['date'][:10]}: {trim['symbol']} — {trim['action']} {trim['shares_sold']} shares ({trim['reason']})")
        
        print("=" * 80)
        
        return trims_executed


def main():
    """Run position management."""
    manager = PositionManager()
    manager.run_position_management()


if __name__ == "__main__":
    main()
