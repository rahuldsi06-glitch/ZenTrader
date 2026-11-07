"""
Base Strategy Architecture for ZenTrader
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd


class ZenStrategyBase(ABC):
    """
    Abstract Base Class for all ZenTrader alpha strategies.
    Enforces standardized signal generation, risk bounds, and metadata.
    """

    def __init__(self, name: str, params: Dict[str, Any] = None):
        self.name = name
        self.params = params or {}
        self.position = 0
        self.state: Dict[str, Any] = {}

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        pass

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.name,
            "params": self.params,
        }
