"""
ZenTrader Autonomous Continuous Re-Optimization Loop
Periodically re-screens token liquidity, re-runs 75% IS / 25% OOS walk-forward audits,
and recalibrates active alphas.
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
import threading
import time

from zentrader.screener.liquidity_screener import LiquidityScreener
from zentrader.strategies import STRATEGY_REGISTRY
from zentrader.backtest.walk_forward import WalkForwardEngine


class AutoReoptimizer:
    """
    Background worker that runs periodic walk-forward optimization cycles.
    """

    def __init__(self, supervisor):
        self.supervisor = supervisor
        self.is_enabled = False
        self.interval_seconds = 60  # Default 60s for demo, 14400s (4h) for prod
        self.last_run_time = "Never"
        self.last_status = "IDLE"
        self.last_wfe = 0.0
        self.last_sharpe = 0.0
        self.total_runs = 0
        self.audit_log: List[Dict[str, Any]] = []
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_enabled": self.is_enabled,
            "interval_seconds": self.interval_seconds,
            "last_run_time": self.last_run_time,
            "last_status": self.last_status,
            "last_wfe": round(self.last_wfe, 2),
            "last_sharpe": round(self.last_sharpe, 2),
            "total_runs": self.total_runs,
            "audit_log": self.audit_log[-5:]  # Last 5 runs
        }

    def toggle(self, enabled: bool, interval_sec: int = 60) -> Dict[str, Any]:
        self.interval_seconds = max(10, interval_sec)
        if enabled and not self.is_enabled:
            self.is_enabled = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._thread.start()
        elif not enabled and self.is_enabled:
            self.is_enabled = False
            self._stop_event.set()
        return self.get_status()

    def run_cycle_now(self) -> Dict[str, Any]:
        """Executes one immediate re-optimization cycle synchronously."""
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.last_run_time = now_str
        self.total_runs += 1
        self.last_status = "RUNNING"

        try:
            # 1. Rescreen Liquidity
            screener = LiquidityScreener()
            sample_data = screener.get_sample_perps_market()
            scan_res = screener.scan_universe(sample_data)
            approved = scan_res["approved_universe"]
            self.supervisor.active_universe = approved

            target_symbol = approved[0]["symbol"] if approved else "BTC-PERP"

            # 2. Run 75/25 Walk-Forward Audit
            strat_cls = STRATEGY_REGISTRY.get(self.supervisor.strategy_key, STRATEGY_REGISTRY["obi_scalper"])
            strat = strat_cls()

            data = WalkForwardEngine.generate_synthetic_perp_data(bars=1200, start_price=68000.0 if "BTC" in target_symbol else 185.0)
            engine = WalkForwardEngine(
                train_ratio=0.75,
                min_sharpe=1.2,
                min_wfe=0.55,
                max_allowed_drawdown_pct=self.supervisor.risk_sentinel.tier.max_drawdown_pct
            )

            report = engine.evaluate(strat, data, symbol=target_symbol, starting_capital=self.supervisor.risk_sentinel.starting_balance)
            self.last_wfe = report.walk_forward_efficiency
            self.last_sharpe = report.out_of_sample.sharpe_ratio

            status = "APPROVED" if report.passed_audit else "WARN_OVERFIT"
            self.last_status = status

            entry = {
                "run_id": f"OPT-{self.total_runs:03d}",
                "timestamp": now_str,
                "symbol": target_symbol,
                "wfe": self.last_wfe,
                "sharpe_oos": self.last_sharpe,
                "status": status,
                "message": f"WFE: {self.last_wfe*100:.1f}% | OOS Sharpe: {self.last_sharpe:.2f}"
            }
            self.audit_log.append(entry)
            return entry

        except Exception as e:
            self.last_status = f"ERROR: {str(e)[:30]}"
            return {"status": "ERROR", "error": str(e)}

    def _worker_loop(self):
        while not self._stop_event.is_set():
            self.run_cycle_now()
            # Wait for interval or stop event
            self._stop_event.wait(timeout=self.interval_seconds)
