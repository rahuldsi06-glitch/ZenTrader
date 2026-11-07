"""
Liquidity & Token Universe Screener
Filters perpetual contracts to ensure deep liquidity, tight spreads, and minimal market impact.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from zentrader.config import DEFAULT_SCREENER_CONFIG


@dataclass
class TokenMetric:
    symbol: str
    price: float
    volume_24h_usd: float
    spread_bps: float
    depth_2pct_usd: float
    funding_rate_8h: float
    estimated_slippage_bps: float
    is_approved: bool
    rejection_reason: str = ""


class LiquidityScreener:
    """
    Evaluates orderbook metrics and filters the tradeable universe
    to only high-liquidity, low-slippage tokens.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or DEFAULT_SCREENER_CONFIG

    def estimate_slippage(self, order_size_usd: float, depth_2pct_usd: float) -> float:
        if depth_2pct_usd <= 0:
            return 999.0
        ratio = order_size_usd / depth_2pct_usd
        return round(1.0 + (12.0 * (ratio ** 0.8)), 2)

    def evaluate_token(self, token_data: Dict[str, Any], order_size_usd: float = 10_000.0) -> TokenMetric:
        symbol = token_data.get("symbol", "UNKNOWN")
        price = token_data.get("price", 0.0)
        vol = token_data.get("volume_24h_usd", 0.0)
        spread_bps = token_data.get("spread_bps", 999.0)
        depth_2pct = token_data.get("depth_2pct_usd", 0.0)
        funding = token_data.get("funding_rate_8h", 0.0)

        slippage = self.estimate_slippage(order_size_usd, depth_2pct)

        reasons = []
        if vol < self.config["min_volume_24h_usd"]:
            reasons.append(f"Vol ${vol/1e6:.1f}M < ${self.config['min_volume_24h_usd']/1e6:.0f}M min")
        if spread_bps > self.config["max_spread_bps"]:
            reasons.append(f"Spread {spread_bps:.1f} bps > {self.config['max_spread_bps']:.1f} bps max")
        if depth_2pct < self.config["min_depth_2pct_usd"]:
            reasons.append(f"Depth ${depth_2pct/1e3:.0f}k < ${self.config['min_depth_2pct_usd']/1e3:.0f}k min")
        if abs(funding) > self.config["max_funding_rate_8h"]:
            reasons.append(f"Funding {funding*100:.3f}% exceeds max threshold")

        is_approved = len(reasons) == 0
        rejection_reason = " | ".join(reasons) if not is_approved else ""

        return TokenMetric(
            symbol=symbol,
            price=price,
            volume_24h_usd=vol,
            spread_bps=spread_bps,
            depth_2pct_usd=depth_2pct,
            funding_rate_8h=funding,
            estimated_slippage_bps=slippage,
            is_approved=is_approved,
            rejection_reason=rejection_reason
        )

    def scan_universe(self, candidates: List[Dict[str, Any]], order_size_usd: float = 10_000.0) -> Dict[str, Any]:
        approved: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        for c in candidates:
            metric = self.evaluate_token(c, order_size_usd)
            if metric.is_approved:
                approved.append(asdict(metric))
            else:
                rejected.append(asdict(metric))

        approved.sort(key=lambda x: (x["spread_bps"], -x["depth_2pct_usd"]))

        return {
            "total_scanned": len(candidates),
            "approved_count": len(approved),
            "approved_universe": approved,
            "rejected_universe": rejected
        }

    @staticmethod
    def get_sample_perps_market() -> List[Dict[str, Any]]:
        return [
            {
                "symbol": "SOL-PERP",
                "price": 184.50,
                "volume_24h_usd": 68_000_000.0,
                "spread_bps": 1.2,
                "depth_2pct_usd": 1_850_000.0,
                "funding_rate_8h": 0.0001,
            },
            {
                "symbol": "ETH-PERP",
                "price": 3425.00,
                "volume_24h_usd": 142_000_000.0,
                "spread_bps": 0.8,
                "depth_2pct_usd": 4_200_000.0,
                "funding_rate_8h": 0.00005,
            },
            {
                "symbol": "BTC-PERP",
                "price": 68250.00,
                "volume_24h_usd": 380_000_000.0,
                "spread_bps": 0.4,
                "depth_2pct_usd": 9_500_000.0,
                "funding_rate_8h": 0.00008,
            },
            {
                "symbol": "AVAX-PERP",
                "price": 28.40,
                "volume_24h_usd": 32_000_000.0,
                "spread_bps": 2.4,
                "depth_2pct_usd": 480_000.0,
                "funding_rate_8h": 0.00012,
            },
            {
                "symbol": "MEME-PERP",
                "price": 0.0142,
                "volume_24h_usd": 6_500_000.0,
                "spread_bps": 12.5,
                "depth_2pct_usd": 65_000.0,
                "funding_rate_8h": 0.0018,
            },
            {
                "symbol": "ILLIQUID-PERP",
                "price": 1.45,
                "volume_24h_usd": 1_200_000.0,
                "spread_bps": 28.0,
                "depth_2pct_usd": 20_000.0,
                "funding_rate_8h": 0.0004,
            }
        ]
