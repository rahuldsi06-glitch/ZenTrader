"""
ZenTrader Global Configuration
Defines Account Tiers, Risk Sentinel parameters, and Liquidity thresholds.
"""
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class AccountTierConfig:
    name: str
    starting_balance: float
    max_drawdown_pct: float       # Hard circuit breaker stop (e.g. 5.0 = 5%)
    daily_profit_target_pct: float # Daily quest goal (e.g. 2.5 = 2.5%)
    risk_per_trade_pct: float     # Percentage of equity risked per trade (e.g. 1.0%)
    max_leverage: float           # Max gross leverage allowed
    min_liquidation_distance_pct: float # Mark price buffer (e.g. 25%)

ACCOUNT_TIERS: Dict[str, AccountTierConfig] = {
    "10k": AccountTierConfig(
        name="Novice ($10k)",
        starting_balance=10000.0,
        max_drawdown_pct=5.0,
        daily_profit_target_pct=2.5,
        risk_per_trade_pct=1.0,
        max_leverage=3.0,
        min_liquidation_distance_pct=25.0
    ),
    "25k": AccountTierConfig(
        name="Trader ($25k)",
        starting_balance=25000.0,
        max_drawdown_pct=5.0,
        daily_profit_target_pct=2.5,
        risk_per_trade_pct=1.0,
        max_leverage=3.5,
        min_liquidation_distance_pct=25.0
    ),
    "50k": AccountTierConfig(
        name="Pro ($50k)",
        starting_balance=50000.0,
        max_drawdown_pct=5.0,
        daily_profit_target_pct=2.5,
        risk_per_trade_pct=1.0,
        max_leverage=4.0,
        min_liquidation_distance_pct=25.0
    ),
    "100k": AccountTierConfig(
        name="Grandmaster ($100k)",
        starting_balance=100000.0,
        max_drawdown_pct=6.0,
        daily_profit_target_pct=2.0,
        risk_per_trade_pct=0.75,
        max_leverage=5.0,
        min_liquidation_distance_pct=25.0
    ),
}

# Default Liquidity Filters for Token Universe Selection
DEFAULT_SCREENER_CONFIG = {
    "min_volume_24h_usd": 25_000_000.0,  # $25M daily volume
    "max_spread_bps": 3.5,               # Max 3.5 bps bid-ask spread
    "min_depth_2pct_usd": 250_000.0,     # $250k orderbook depth within +/-2%
    "max_funding_rate_8h": 0.0008,       # 0.08% max funding skew
}

# Friction Models for Backtesting & Paper Trading
DEFAULT_FRICTION_CONFIG = {
    "taker_fee_pct": 0.035 / 100.0,      # 3.5 bps taker fee
    "maker_rebate_pct": 0.010 / 100.0,   # 1.0 bps maker rebate
    "default_slippage_bps": 1.2,         # 1.2 bps simulated slippage
}
