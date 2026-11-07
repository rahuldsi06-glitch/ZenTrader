from zentrader.strategies.base import ZenStrategyBase
from zentrader.strategies.obi_scalper import OBIScalperStrategy
from zentrader.strategies.momentum_breakout import MomentumBreakoutStrategy

STRATEGY_REGISTRY = {
    "obi_scalper": OBIScalperStrategy,
    "momentum_breakout": MomentumBreakoutStrategy,
}

__all__ = ["ZenStrategyBase", "OBIScalperStrategy", "MomentumBreakoutStrategy", "STRATEGY_REGISTRY"]
