"""
Institutional Risk Sentinel Engine
Protects account capital, enforces Drawdown Shield (HP), Daily Quests, and Circuit Breakers.
"""
from dataclasses import dataclass
from typing import Dict, Any, Tuple
from zentrader.config import AccountTierConfig, ACCOUNT_TIERS


@dataclass
class RiskHUDStatus:
    account_tier: str
    current_equity: float
    peak_equity: float
    starting_balance: float
    net_pnl_usd: float
    net_pnl_pct: float
    current_drawdown_pct: float
    max_drawdown_limit_pct: float
    shield_hp_pct: float
    daily_quest_target_usd: float
    daily_quest_progress_pct: float
    is_halted: bool
    status_message: str


class RiskSentinel:

    def __init__(self, tier_key: str = "50k"):
        self.tier: AccountTierConfig = ACCOUNT_TIERS.get(tier_key, ACCOUNT_TIERS["50k"])
        self.starting_balance = self.tier.starting_balance
        self.current_equity = self.starting_balance
        self.peak_equity = self.starting_balance
        self.daily_pnl = 0.0
        self.is_halted = False
        self.halt_reason = ""

    def set_tier(self, tier_key: str):
        if tier_key in ACCOUNT_TIERS:
            self.tier = ACCOUNT_TIERS[tier_key]
            self.starting_balance = self.tier.starting_balance
            self.current_equity = self.starting_balance
            self.peak_equity = self.starting_balance
            self.daily_pnl = 0.0
            self.is_halted = False
            self.halt_reason = ""

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        atr: float = None
    ) -> float:
        if self.is_halted or entry_price <= 0:
            return 0.0

        risk_budget_usd = self.current_equity * (self.tier.risk_per_trade_pct / 100.0)
        sl_distance = abs(entry_price - stop_loss_price)

        if sl_distance <= 0:
            sl_distance = (atr * 1.5) if (atr and atr > 0) else (entry_price * 0.015)

        raw_size = risk_budget_usd / sl_distance
        max_notional = self.current_equity * self.tier.max_leverage
        if (raw_size * entry_price) > max_notional:
            raw_size = max_notional / entry_price

        return round(raw_size, 4)

    def pre_trade_check(
        self,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        stop_loss_price: float
    ) -> Tuple[bool, str]:
        if self.is_halted:
            return False, f"Trading is HALTED: {self.halt_reason}"

        notional_usd = size * entry_price
        max_allowed_notional = self.current_equity * self.tier.max_leverage

        if notional_usd > max_allowed_notional:
            return False, f"Notional ${notional_usd:,.0f} exceeds max allowed ${max_allowed_notional:,.0f} ({self.tier.max_leverage}x)"

        est_liq_distance_pct = (1.0 / self.tier.max_leverage) * 100.0
        if est_liq_distance_pct < self.tier.min_liquidation_distance_pct:
            return False, f"Liquidation buffer {est_liq_distance_pct:.1f}% is below {self.tier.min_liquidation_distance_pct:.1f}% safety margin"

        return True, "Order Approved by Risk Sentinel"

    def record_pnl(self, realized_pnl: float):
        self.current_equity += realized_pnl
        self.daily_pnl += realized_pnl

        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity

        current_dd_pct = ((self.peak_equity - self.current_equity) / self.peak_equity) * 100.0
        if current_dd_pct >= self.tier.max_drawdown_pct:
            self.trigger_circuit_breaker(
                f"MAX DRAWDOWN HIT: {current_dd_pct:.2f}% reached (Limit: {self.tier.max_drawdown_pct:.1f}%)"
            )

    def trigger_circuit_breaker(self, reason: str):
        self.is_halted = True
        self.halt_reason = reason

    def reset_halt(self):
        self.is_halted = False
        self.halt_reason = ""

    def get_hud_telemetry(self) -> RiskHUDStatus:
        net_pnl_usd = self.current_equity - self.starting_balance
        net_pnl_pct = (net_pnl_usd / self.starting_balance) * 100.0

        current_dd_pct = ((self.peak_equity - self.current_equity) / self.peak_equity) * 100.0 if self.peak_equity > 0 else 0.0

        max_dd = self.tier.max_drawdown_pct
        used_ratio = min(max(current_dd_pct / max_dd, 0.0), 1.0)
        shield_hp = round((1.0 - used_ratio) * 100.0, 1)

        target_usd = self.starting_balance * (self.tier.daily_profit_target_pct / 100.0)
        quest_pct = round(min(max((self.daily_pnl / target_usd) * 100.0, 0.0), 100.0), 1) if target_usd > 0 else 0.0

        status_msg = "NORMAL FLOW"
        if self.is_halted:
            status_msg = f"HALTED: {self.halt_reason}"
        elif quest_pct >= 100.0:
            status_msg = "QUEST COMPLETED! Profit Target Reached"
        elif shield_hp < 40.0:
            status_msg = "WARNING: Low Shield HP - Tighten Stops"

        return RiskHUDStatus(
            account_tier=self.tier.name,
            current_equity=round(self.current_equity, 2),
            peak_equity=round(self.peak_equity, 2),
            starting_balance=round(self.starting_balance, 2),
            net_pnl_usd=round(net_pnl_usd, 2),
            net_pnl_pct=round(net_pnl_pct, 2),
            current_drawdown_pct=round(current_dd_pct, 2),
            max_drawdown_limit_pct=self.tier.max_drawdown_pct,
            shield_hp_pct=shield_hp,
            daily_quest_target_usd=round(target_usd, 2),
            daily_quest_progress_pct=quest_pct,
            is_halted=self.is_halted,
            status_message=status_msg
        )
