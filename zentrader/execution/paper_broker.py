"""
Paper Trading Execution Engine for Perpetual Contracts
Simulates exchange matching engine, fills, slippage, and position tracking.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
import uuid
from zentrader.config import DEFAULT_FRICTION_CONFIG
from zentrader.risk.sentinel import RiskSentinel
from zentrader.execution.ledger import TradeLedger, TradeDocument


@dataclass
class Position:
    symbol: str
    side: str          # "LONG" or "SHORT"
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: str
    unrealized_pnl: float = 0.0


class PaperBroker:

    def __init__(self, risk_sentinel: RiskSentinel, ledger: TradeLedger = None):
        self.risk = risk_sentinel
        self.ledger = ledger or TradeLedger()
        self.positions: Dict[str, Position] = {}
        self.friction = DEFAULT_FRICTION_CONFIG

    def execute_signal(
        self,
        symbol: str,
        signal: int,
        current_price: float,
        stop_loss: float,
        take_profit: float,
        timestamp: str = None
    ) -> Optional[Dict[str, Any]]:
        timestamp = timestamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        if symbol in self.positions:
            pos = self.positions[symbol]
            if (pos.side == "LONG" and signal <= 0) or (pos.side == "SHORT" and signal >= 0):
                self.close_position(symbol, current_price, reason="SIGNAL_REVERSAL", timestamp=timestamp)

        if signal == 0:
            return None

        if symbol in self.positions:
            return None

        side = "LONG" if signal == 1 else "SHORT"
        size = self.risk.calculate_position_size(current_price, stop_loss)

        if size <= 0:
            return None

        approved, reason = self.risk.pre_trade_check(symbol, side, size, current_price, stop_loss)
        if not approved:
            print(f"[PAPER BROKER REJECTED] {symbol} {side}: {reason}")
            return None

        slippage_bps = self.friction.get("default_slippage_bps", 1.2)
        slip_ratio = slippage_bps / 10000.0
        fill_price = current_price * (1.0 + slip_ratio if side == "LONG" else 1.0 - slip_ratio)

        pos = Position(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=round(fill_price, 3),
            stop_loss=round(stop_loss, 3),
            take_profit=round(take_profit, 3),
            entry_time=timestamp
        )
        self.positions[symbol] = pos

        return {
            "action": "OPEN",
            "symbol": symbol,
            "side": side,
            "size": size,
            "fill_price": fill_price,
            "time": timestamp
        }

    def check_active_positions(self, symbol: str, high: float, low: float, current_price: float, timestamp: str = None):
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        timestamp = timestamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        hit_sl = (pos.side == "LONG" and low <= pos.stop_loss) or (pos.side == "SHORT" and high >= pos.stop_loss)
        hit_tp = (pos.side == "LONG" and high >= pos.take_profit) or (pos.side == "SHORT" and low <= pos.take_profit)

        if hit_tp:
            self.close_position(symbol, pos.take_profit, reason="TAKE_PROFIT", timestamp=timestamp)
        elif hit_sl:
            self.close_position(symbol, pos.stop_loss, reason="STOP_LOSS", timestamp=timestamp)

    def close_position(self, symbol: str, exit_price: float, reason: str = "MANUAL", timestamp: str = None):
        if symbol not in self.positions:
            return

        pos = self.positions.pop(symbol)
        timestamp = timestamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        slippage_bps = self.friction.get("default_slippage_bps", 1.2)
        fee_rate = self.friction.get("taker_fee_pct", 0.00035)

        slip_ratio = slippage_bps / 10000.0
        actual_exit = exit_price * (1.0 - slip_ratio if pos.side == "LONG" else 1.0 + slip_ratio)

        gross_pnl = (actual_exit - pos.entry_price) * pos.size if pos.side == "LONG" else (pos.entry_price - actual_exit) * pos.size
        fee_usd = (pos.entry_price * pos.size * fee_rate) + (actual_exit * pos.size * fee_rate)
        net_pnl = gross_pnl - fee_usd
        pnl_pct = ((actual_exit - pos.entry_price) / pos.entry_price * 100.0) if pos.side == "LONG" else ((pos.entry_price - actual_exit) / pos.entry_price * 100.0)

        self.risk.record_pnl(net_pnl)

        trade_doc = TradeDocument(
            trade_id=f"ZT-{uuid.uuid4().hex[:6].upper()}",
            symbol=symbol,
            side=pos.side,
            size=pos.size,
            entry_time=pos.entry_time,
            exit_time=timestamp,
            entry_price=pos.entry_price,
            exit_price=round(actual_exit, 3),
            fee_usd=round(fee_usd, 3),
            slippage_bps=slippage_bps,
            realized_pnl_usd=round(net_pnl, 2),
            realized_pnl_pct=round(pnl_pct, 2),
            exit_reason=reason
        )
        self.ledger.record_trade(trade_doc)

    def flatten_all_positions(self, current_prices: Dict[str, float] = None, reason: str = "CIRCUIT_BREAKER"):
        current_prices = current_prices or {}
        symbols = list(self.positions.keys())
        for sym in symbols:
            price = current_prices.get(sym, self.positions[sym].entry_price)
            self.close_position(sym, price, reason=reason)
