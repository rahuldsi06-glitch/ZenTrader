"""
Volatility Breakout Strategy (Donchian / ATR Trend Follower)
"""
from typing import Dict, Any
import pandas as pd
import numpy as np
from zentrader.strategies.base import ZenStrategyBase


class MomentumBreakoutStrategy(ZenStrategyBase):

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "channel_period": 20,
            "atr_period": 14,
            "atr_mult": 2.0,
            "risk_reward_ratio": 2.5
        }
        if params:
            default_params.update(params)
        super().__init__(name="Momentum_Breakout", params=default_params)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()

        data["upper_channel"] = data["high"].rolling(window=self.params["channel_period"]).max().shift(1)
        data["lower_channel"] = data["low"].rolling(window=self.params["channel_period"]).min().shift(1)

        high_low = data["high"] - data["low"]
        high_close = (data["high"] - data["close"].shift()).abs()
        low_close = (data["low"] - data["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        data["atr"] = tr.rolling(window=self.params["atr_period"]).mean()

        data["signal"] = 0
        long_trigger = data["close"] > data["upper_channel"]
        short_trigger = data["close"] < data["lower_channel"]

        data.loc[long_trigger, "signal"] = 1
        data.loc[short_trigger, "signal"] = -1

        mult = self.params["atr_mult"]
        rr = self.params["risk_reward_ratio"]

        data["stop_loss"] = np.where(
            data["signal"] == 1,
            data["close"] - (data["atr"] * mult),
            np.where(data["signal"] == -1, data["close"] + (data["atr"] * mult), np.nan)
        )

        data["take_profit"] = np.where(
            data["signal"] == 1,
            data["close"] + (data["atr"] * mult * rr),
            np.where(data["signal"] == -1, data["close"] - (data["atr"] * mult * rr), np.nan)
        )

        return data
