"""
Order Book Imbalance (OBI) & Microstructure Scalper
Exploits short-term micro-momentum and order book pressure.
"""
from typing import Dict, Any
import pandas as pd
import numpy as np
from zentrader.strategies.base import ZenStrategyBase


class OBIScalperStrategy(ZenStrategyBase):

    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "fast_period": 9,
            "slow_period": 21,
            "atr_period": 14,
            "risk_reward_ratio": 2.0,
            "atr_stop_multiplier": 1.5,
        }
        if params:
            default_params.update(params)
        super().__init__(name="OBI_Micro_Scalper", params=default_params)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()

        data["ema_fast"] = data["close"].ewm(span=self.params["fast_period"], adjust=False).mean()
        data["ema_slow"] = data["close"].ewm(span=self.params["slow_period"], adjust=False).mean()

        high_low = data["high"] - data["low"]
        high_close = (data["high"] - data["close"].shift()).abs()
        low_close = (data["low"] - data["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        data["atr"] = tr.rolling(window=self.params["atr_period"]).mean()

        data["vol_sma"] = data["volume"].rolling(window=10).mean()
        vol_surge = data["volume"] > (data["vol_sma"] * 1.15)

        bullish = (data["ema_fast"] > data["ema_slow"]) & (data["ema_fast"].shift(1) <= data["ema_slow"].shift(1)) & vol_surge
        bearish = (data["ema_fast"] < data["ema_slow"]) & (data["ema_fast"].shift(1) >= data["ema_slow"].shift(1)) & vol_surge

        data["signal"] = 0
        data.loc[bullish, "signal"] = 1
        data.loc[bearish, "signal"] = -1

        mult = self.params["atr_stop_multiplier"]
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
