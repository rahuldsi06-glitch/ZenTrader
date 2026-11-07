"""
ZenTrader Master Supervisor
Orchestrates:
1. Token Universe Screener
2. Strategy Selection
3. 75/25 Walk-Forward Validation
4. Risk Sentinel & Account Tier Configuration
5. Live Paper Trading Execution & Telemetry Streaming
6. Autonomous Continuous Re-Optimization Loop
"""
from dataclasses import asdict
from typing import Dict, Any, List
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from zentrader.config import ACCOUNT_TIERS
from zentrader.screener.liquidity_screener import LiquidityScreener
from zentrader.strategies import STRATEGY_REGISTRY
from zentrader.backtest.walk_forward import WalkForwardEngine
from zentrader.risk.sentinel import RiskSentinel
from zentrader.execution.paper_broker import PaperBroker
from zentrader.execution.ledger import TradeLedger
from zentrader.auto_optimizer import AutoReoptimizer

console = Console()


class ZenSupervisor:

    def __init__(self, account_tier: str = "50k", selected_strategy: str = "obi_scalper"):
        self.tier_key = account_tier
        self.strategy_key = selected_strategy
        self.screener = LiquidityScreener()
        self.risk_sentinel = RiskSentinel(tier_key=self.tier_key)
        self.ledger = TradeLedger()
        self.broker = PaperBroker(self.risk_sentinel, self.ledger)
        self.auto_optimizer = AutoReoptimizer(self)
        self.active_universe: List[Dict[str, Any]] = []
        self.latest_report = None

    def step1_screen_token_universe(self) -> List[Dict[str, Any]]:
        console.print("\n[bold cyan]─── STEP 1: LIQUIDITY & TOKEN UNIVERSE SCREENER ───[/bold cyan]")
        market_data = self.screener.get_sample_perps_market()
        scan_res = self.screener.scan_universe(market_data)

        table = Table(title="Screener Results (Deep Liquidity / Minimal Slippage)")
        table.add_column("Symbol", style="bold white")
        table.add_column("24h Volume", justify="right")
        table.add_column("Spread (bps)", justify="right")
        table.add_column("2% Depth ($)", justify="right")
        table.add_column("Est. Slippage", justify="right")
        table.add_column("Status", justify="center")

        for item in scan_res["approved_universe"]:
            table.add_row(
                item["symbol"],
                f"${item['volume_24h_usd']/1e6:.1f}M",
                f"{item['spread_bps']:.1f}",
                f"${item['depth_2pct_usd']/1e3:.0f}k",
                f"{item['estimated_slippage_bps']:.1f} bps",
                "[green]APPROVED[/green]"
            )

        for item in scan_res["rejected_universe"]:
            table.add_row(
                item["symbol"],
                f"${item['volume_24h_usd']/1e6:.1f}M",
                f"{item['spread_bps']:.1f}",
                f"${item['depth_2pct_usd']/1e3:.0f}k",
                f"{item['estimated_slippage_bps']:.1f} bps",
                f"[red]REJECTED[/red]"
            )

        console.print(table)
        self.active_universe = scan_res["approved_universe"]
        return self.active_universe

    def step2_select_and_validate_strategy(self, symbol: str = "SOL-PERP") -> bool:
        console.print(f"\n[bold cyan]─── STEP 2 & 3: STRATEGY VALIDATION (75% IS / 25% OOS) ON {symbol} ───[/bold cyan]")
        strat_cls = STRATEGY_REGISTRY.get(self.strategy_key)
        if not strat_cls:
            raise ValueError(f"Unknown strategy: {self.strategy_key}")

        strategy = strat_cls()
        console.print(f"Selected Strategy: [bold yellow]{strategy.name}[/bold yellow]")

        market_candles = WalkForwardEngine.generate_synthetic_perp_data(bars=1000, start_price=184.0)

        engine = WalkForwardEngine(
            train_ratio=0.75,
            min_sharpe=1.2,
            min_wfe=0.55,
            max_allowed_drawdown_pct=self.risk_sentinel.tier.max_drawdown_pct
        )

        report = engine.evaluate(strategy, market_candles, symbol=symbol, starting_capital=self.risk_sentinel.starting_balance)
        self.latest_report = report

        report_table = Table(title=f"75/25 Walk-Forward Audit: {strategy.name} on {symbol}")
        report_table.add_column("Metric", style="bold white")
        report_table.add_column("75% In-Sample (Train)", justify="right")
        report_table.add_column("25% Out-of-Sample (Holdout)", justify="right")
        report_table.add_column("Gate Requirement", justify="center")

        report_table.add_row(
            "Sharpe Ratio",
            f"{report.in_sample.sharpe_ratio:.2f}",
            f"{report.out_of_sample.sharpe_ratio:.2f}",
            ">= 1.20"
        )
        report_table.add_row(
            "Max Drawdown",
            f"{report.in_sample.max_drawdown_pct:.1f}%",
            f"{report.out_of_sample.max_drawdown_pct:.1f}%",
            f"<= {self.risk_sentinel.tier.max_drawdown_pct:.1f}%"
        )
        report_table.add_row(
            "Walk-Forward Efficiency",
            "-",
            f"{report.walk_forward_efficiency*100:.1f}%",
            ">= 55.0%"
        )

        console.print(report_table)
        return report.passed_audit

    def step4_deploy_and_run_paper_session(self, symbol: str = "SOL-PERP", num_live_bars: int = 150):
        console.print(f"\n[bold cyan]─── STEP 4 & 5: LIVE PAPER EXECUTION ON {symbol} ({self.risk_sentinel.tier.name}) ───[/bold cyan]")
        strat_cls = STRATEGY_REGISTRY[self.strategy_key]
        strategy = strat_cls()

        live_data = WalkForwardEngine.generate_synthetic_perp_data(bars=num_live_bars, start_price=185.0)
        signals_df = strategy.generate_signals(live_data)

        for i in range(len(signals_df)):
            row = signals_df.iloc[i]
            timestamp_str = str(row.name)

            self.broker.check_active_positions(
                symbol=symbol,
                high=row["high"],
                low=row["low"],
                current_price=row["close"],
                timestamp=timestamp_str
            )

            if row["signal"] != 0:
                self.broker.execute_signal(
                    symbol=symbol,
                    signal=int(row["signal"]),
                    current_price=row["close"],
                    stop_loss=row["stop_loss"],
                    take_profit=row["take_profit"],
                    timestamp=timestamp_str
                )

            if self.risk_sentinel.is_halted:
                console.print(f"[bold red]CIRCUIT BREAKER TRIGGERED: {self.risk_sentinel.halt_reason}[/bold red]")
                break

        hud = self.risk_sentinel.get_hud_telemetry()
        recent_trades = self.ledger.get_recent_trades(limit=10)

        panel_content = f"""
[bold white]Account Tier:[/bold white] {hud.account_tier}
[bold white]Starting Balance:[/bold white] ${hud.starting_balance:,.2f}
[bold white]Current Equity:[/bold white] [bold green]${hud.current_equity:,.2f}[/bold green] (Peak: ${hud.peak_equity:,.2f})
[bold white]Net PnL:[/bold white] ${hud.net_pnl_usd:+,.2f} ({hud.net_pnl_pct:+.2f}%)
[bold white]Shield HP (Max DD Guard):[/bold white] {hud.shield_hp_pct:.1f}% remaining
[bold white]Daily Quest Target:[/bold white] ${hud.daily_quest_target_usd:,.2f} | Progress: {hud.daily_quest_progress_pct:.1f}%
        """
        console.print(Panel(panel_content.strip(), title="ZenTrader Live Paper Trading HUD", border_style="cyan"))


if __name__ == "__main__":
    supervisor = ZenSupervisor(account_tier="50k", selected_strategy="obi_scalper")
    universe = supervisor.step1_screen_token_universe()
    if universe:
        top_token = universe[0]["symbol"]
        supervisor.step2_select_and_validate_strategy(symbol=top_token)
        supervisor.step4_deploy_and_run_paper_session(symbol=top_token)
