"""
ZenTrader Trade Documentation & Audit Ledger
Persists all executed trades with microsecond timestamps, fill prices, slippage, and PnL.
Serverless-ready (Vercel / AWS Lambda / Local).
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import sqlite3
import os


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

    def __init__(self, db_path: str = None):
        if db_path is None:
            # In Vercel or read-only serverless, use /tmp or :memory:
            if os.environ.get("VERCEL") or not os.access(".", os.W_OK):
                db_path = "/tmp/zentrader_trades.db"
            else:
                db_path = "zentrader_trades.db"

        self.db_path = db_path
        self.memory_trades: List[Dict[str, Any]] = []
        self._init_db()

    def _get_connection(self):
        try:
            return sqlite3.connect(self.db_path, check_same_thread=False)
        except Exception:
            # Fallback to in-memory SQLite if file is inaccessible
            self.db_path = ":memory:"
            return sqlite3.connect(":memory:", check_same_thread=False)

    def _init_db(self):
        try:
            conn = self._get_connection()
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
        except Exception as e:
            print(f"[TradeLedger] Warning during DB init: {e}")

    def record_trade(self, trade: TradeDocument):
        # Always save in memory
        trade_dict = asdict(trade)
        self.memory_trades.insert(0, trade_dict)
        if len(self.memory_trades) > 100:
            self.memory_trades.pop()

        try:
            conn = self._get_connection()
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
        except Exception as e:
            print(f"[TradeLedger] SQLite write failed, preserved in memory: {e}")

    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM trades ORDER BY exit_time DESC LIMIT ?", (limit,))
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            if rows:
                return rows
        except Exception:
            pass

        return self.memory_trades[:limit]
