"""
75% In-Sample / 25% Out-of-Sample Walk-Forward Engine
Provides institutional validation and overfitting prevention for ZenTrader.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from zentrader.config import DEFAULT_FRICTION_CONFIG
from zentrader.strategies.base import ZenStrategyBase


@dataclass
class BacktestResult:
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    equity_curve: List[float]
    trades: List[Dict[str, Any]]


@dataclass
class WalkForwardValidationReport:
    strategy_name: str
    symbol: str
    train_ratio: float
    in_sample: BacktestResult
    out_of_sample: BacktestResult
    walk_forward_efficiency: float
    passed_audit: bool
    audit_notes: List[str]


class WalkForwardEngine:

    def __init__(
        self,
        train_ratio: float = 0.75,
        friction_config: Dict[str, float] = None,
        min_sharpe: float = 1.3,
        min_wfe: float = 0.60,
        max_allowed_drawdown_pct: float = 6.0
    ):
        self.train_ratio = train_ratio
        self.friction = friction_config or DEFAULT_FRICTION_CONFIG
        self.min_sharpe = min_sharpe
        self.min_wfe = min_wfe
        self.max_allowed_drawdown_pct = max_allowed_drawdown_pct

    def run_single_simulation(
        self,
        strategy: ZenStrategyBase,
        df: pd.DataFrame,
        starting_capital: float = 50_000.0,
        risk_per_trade_pct: float = 1.0
    ) -> BacktestResult:
        signals_df = strategy.generate_signals(df).dropna(subset=["close"])
        equity = starting_capital
        peak_equity = starting_capital
        equity_curve = [starting_capital]
        trades = []

        position = 0
        entry_price = 0.0
        stop_loss = 0.0
        take_profit = 0.0
        position_size = 0.0
        entry_time = None

        fee_rate = self.friction.get("taker_fee_pct", 0.00035)
        slippage_rate = (self.friction.get("default_slippage_bps", 1.2) / 10000.0)

        for i in range(len(signals_df)):
            row = signals_df.iloc[i]
            price = row["close"]
            time_val = row.name if hasattr(row, "name") else i

            if position != 0:
                hit_sl = (position == 1 and row["low"] <= stop_loss) or (position == -1 and row["high"] >= stop_loss)
                hit_tp = (position == 1 and row["high"] >= take_profit) or (position == -1 and row["low"] <= take_profit)
                reverse_signal = (position == 1 and row["signal"] == -1) or (position == -1 and row["signal"] == 1)

                if hit_sl or hit_tp or reverse_signal:
                    exit_raw = stop_loss if hit_sl else (take_profit if hit_tp else price)
                    exit_price = exit_raw * (1.0 - slippage_rate if position == 1 else 1.0 + slippage_rate)
                    gross_pnl = (exit_price - entry_price) * position_size if position == 1 else (entry_price - exit_price) * position_size
                    trade_fee = (entry_price * position_size * fee_rate) + (exit_price * position_size * fee_rate)
                    net_pnl = gross_pnl - trade_fee

                    equity += net_pnl
                    if equity > peak_equity:
                        peak_equity = equity

                    trades.append({
                        "trade_id": f"T-{len(trades)+1:04d}",
                        "entry_time": str(entry_time),
                        "exit_time": str(time_val),
                        "side": "LONG" if position == 1 else "SHORT",
                        "size": round(position_size, 3),
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "net_pnl": round(net_pnl, 2),
                        "exit_reason": "TAKE_PROFIT" if hit_tp else ("STOP_LOSS" if hit_sl else "SIGNAL_FLIP")
                    })

                    position = 0
                    entry_price = 0.0
                    position_size = 0.0

            if position == 0 and row["signal"] in (1, -1):
                position = int(row["signal"])
                entry_raw = price
                entry_price = entry_raw * (1.0 + slippage_rate if position == 1 else 1.0 - slippage_rate)
                stop_loss = row["stop_loss"] if pd.notnull(row["stop_loss"]) else (entry_price * 0.98 if position == 1 else entry_price * 1.02)
                take_profit = row["take_profit"] if pd.notnull(row["take_profit"]) else (entry_price * 1.04 if position == 1 else entry_price * 0.96)

                risk_amount = equity * (risk_per_trade_pct / 100.0)
                sl_distance = abs(entry_price - stop_loss)
                position_size = (risk_amount / sl_distance) if sl_distance > 0 else (risk_amount / (entry_price * 0.01))
                entry_time = time_val

            equity_curve.append(equity)

        returns = pd.Series(equity_curve).pct_change().dropna()
        total_ret = ((equity - starting_capital) / starting_capital) * 100.0

        sharpe = float(np.sqrt(365 * 24 * 12) * (returns.mean() / (returns.std() + 1e-8))) if len(returns) > 1 else 0.0
        ann_return = float(total_ret * 4.0)

        eq_series = pd.Series(equity_curve)
        rolling_max = eq_series.cummax()
        dd = (rolling_max - eq_series) / rolling_max
        max_dd_pct = float(dd.max() * 100.0)

        winning_trades = [t for t in trades if t["net_pnl"] > 0]
        losing_trades = [t for t in trades if t["net_pnl"] < 0]
        win_rate = (len(winning_trades) / len(trades) * 100.0) if trades else 0.0

        gross_profit = sum(t["net_pnl"] for t in winning_trades)
        gross_loss = abs(sum(t["net_pnl"] for t in losing_trades))
        profit_factor = round((gross_profit / gross_loss), 2) if gross_loss > 0 else 9.99

        return BacktestResult(
            total_trades=len(trades),
            win_rate_pct=round(win_rate, 1),
            profit_factor=profit_factor,
            total_return_pct=round(total_ret, 2),
            annualized_return_pct=round(ann_return, 2),
            sharpe_ratio=round(sharpe, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            equity_curve=equity_curve,
            trades=trades
        )

    def evaluate(
        self,
        strategy: ZenStrategyBase,
        data: pd.DataFrame,
        symbol: str = "SOL-PERP",
        starting_capital: float = 50_000.0
    ) -> WalkForwardValidationReport:
        split_idx = int(len(data) * self.train_ratio)
        df_is = data.iloc[:split_idx].copy()
        df_oos = data.iloc[split_idx:].copy()

        res_is = self.run_single_simulation(strategy, df_is, starting_capital=starting_capital)
        res_oos = self.run_single_simulation(strategy, df_oos, starting_capital=starting_capital)

        if res_is.annualized_return_pct > 0 and res_oos.annualized_return_pct > 0:
            wfe = res_oos.annualized_return_pct / res_is.annualized_return_pct
        else:
            wfe = 0.0
        wfe = round(wfe, 2)

        audit_notes = []
        passed = True

        if res_oos.sharpe_ratio < self.min_sharpe:
            passed = False
            audit_notes.append(f"OOS Sharpe {res_oos.sharpe_ratio:.2f} < {self.min_sharpe:.2f} minimum")

        if wfe < self.min_wfe:
            passed = False
            audit_notes.append(f"Walk-Forward Efficiency {wfe*100:.1f}% < {self.min_wfe*100:.0f}% minimum (Overfit Alert)")

        if res_oos.max_drawdown_pct > self.max_allowed_drawdown_pct:
            passed = False
            audit_notes.append(f"OOS Max Drawdown {res_oos.max_drawdown_pct:.1f}% > {self.max_allowed_drawdown_pct:.1f}% limit")

        if res_oos.total_trades < 5:
            passed = False
            audit_notes.append(f"Insufficient trade count in OOS ({res_oos.total_trades} trades)")

        if passed:
            audit_notes.append("✅ ALL INSTITUTIONAL GATES PASSED: Strategy approved for live paper deployment.")

        return WalkForwardValidationReport(
            strategy_name=strategy.name,
            symbol=symbol,
            train_ratio=self.train_ratio,
            in_sample=res_is,
            out_of_sample=res_oos,
            walk_forward_efficiency=wfe,
            passed_audit=passed,
            audit_notes=audit_notes
        )

    @staticmethod
    def generate_synthetic_perp_data(
        bars: int = 1200,
        start_price: float = 180.0,
        volatility: float = 0.003
    ) -> pd.DataFrame:
        np.random.seed(42)
        dates = pd.date_range("2026-11-01 00:00", periods=bars, freq="5min")
        returns = np.random.normal(0.0001, volatility, bars)
        returns[200:450] += 0.0012
        returns[600:850] -= 0.0010
        returns[950:1100] += 0.0015

        price_series = start_price * np.exp(np.cumsum(returns))

        highs = price_series * (1.0 + np.abs(np.random.normal(0.0005, 0.0015, bars)))
        lows = price_series * (1.0 - np.abs(np.random.normal(0.0005, 0.0015, bars)))
        opens = price_series * (1.0 + np.random.normal(0.0, 0.0005, bars))
        closes = price_series
        volumes = np.random.lognormal(mean=8.5, sigma=0.8, size=bars)

        return pd.DataFrame({
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes
        }, index=dates)
