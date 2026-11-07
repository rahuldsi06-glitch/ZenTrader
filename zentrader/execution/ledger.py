"""
ZenTrader Trade Documentation & Audit Ledger
Persists all executed trades with microsecond timestamps, fill prices, slippage, and PnL.
"""
from dataclasses import dataclass
from typing import List, Dict, Any
import sqlite3


@dataclass
class TradeDocument:
    trade_id: str
    symbol: str
    side: str
    size: float
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    fee_usd: float
    slippage_bps: float
    realized_pnl_usd: float
    realized_pnl_pct: float
    exit_reason: str


class TradeLedger:

    def __init__(self, db_path: str = "zentrader_trades.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                symbol TEXT,
                side TEXT,
                size REAL,
                entry_time TEXT,
                exit_time TEXT,
                entry_price REAL,
                exit_price REAL,
                fee_usd REAL,
                slippage_bps REAL,
                realized_pnl_usd REAL,
                realized_pnl_pct REAL,
                exit_reason TEXT
            )
        """)
        conn.commit()
        conn.close()

    def record_trade(self, trade: TradeDocument):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO trades VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            trade.trade_id, trade.symbol, trade.side, trade.size,
            trade.entry_time, trade.exit_time, trade.entry_price,
            trade.exit_price, trade.fee_usd, trade.slippage_bps,
            trade.realized_pnl_usd, trade.realized_pnl_pct, trade.exit_reason
        ))
        conn.commit()
        conn.close()

    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM trades ORDER BY exit_time DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
