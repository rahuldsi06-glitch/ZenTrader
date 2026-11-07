"""
ZenTrader FastAPI Web Application & API
Powers the Gamified Trading Terminal with Live Lightweight-Charts and Telemetry.
Serverless-ready for Vercel and local runtimes.
"""
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
import os
import time
import threading
import random
from datetime import datetime, timedelta
import uvicorn

from zentrader.supervisor import ZenSupervisor
from zentrader.config import ACCOUNT_TIERS
from zentrader.execution.ledger import TradeDocument
from zentrader.backtest.walk_forward import WalkForwardEngine

app = FastAPI(title="ZenTrader Autonomous Platform", version="1.0.0")
supervisor = ZenSupervisor(account_tier="50k", selected_strategy="obi_scalper")

# Set active universe safely without synchronous heavy operations
try:
    screener = supervisor.screener
    sample_data = screener.get_sample_perps_market()
    scan = screener.scan_universe(sample_data)
    supervisor.active_universe = scan["approved_universe"]
except Exception as e:
    supervisor.active_universe = [
        {"symbol": "BTC-PERP", "price": 68250.0, "volume_24h_usd": 380000000.0, "spread_bps": 0.4, "depth_2pct_usd": 9500000.0, "estimated_slippage_bps": 1.1},
        {"symbol": "ETH-PERP", "price": 3425.0, "volume_24h_usd": 142000000.0, "spread_bps": 0.8, "depth_2pct_usd": 4200000.0, "estimated_slippage_bps": 1.1},
        {"symbol": "SOL-PERP", "price": 184.5, "volume_24h_usd": 68000000.0, "spread_bps": 1.2, "depth_2pct_usd": 1850000.0, "estimated_slippage_bps": 1.2},
    ]

def seed_initial_trades():
    trades = [
        ("SOL-PERP", "LONG", 15.0, 182.40, 184.85, 0.9, 36.75, 1.34, "TAKE_PROFIT"),
        ("BTC-PERP", "SHORT", 0.5, 68450.00, 68120.00, 0.4, 165.00, 0.48, "TAKE_PROFIT"),
        ("ETH-PERP", "LONG", 4.0, 3410.00, 3395.00, 0.8, -60.00, -0.44, "STOP_LOSS"),
        ("SOL-PERP", "LONG", 20.0, 183.10, 185.20, 1.1, 42.00, 1.15, "TAKE_PROFIT"),
        ("AVAX-PERP", "LONG", 50.0, 27.80, 28.60, 2.1, 40.00, 2.88, "TAKE_PROFIT"),
        ("BTC-PERP", "LONG", 0.4, 67900.00, 68350.00, 0.5, 180.00, 0.66, "TAKE_PROFIT"),
    ]
    now = datetime.utcnow()
    for idx, (sym, side, size, ep, xp, slip, pnl, pct, reason) in enumerate(trades):
        t_entry = (now - timedelta(minutes=(len(trades)-idx)*12)).strftime("%Y-%m-%d %H:%M:%S")
        t_exit = (now - timedelta(minutes=(len(trades)-idx)*12 - 8)).strftime("%Y-%m-%d %H:%M:%S")
        supervisor.risk_sentinel.record_pnl(pnl)
        supervisor.ledger.record_trade(TradeDocument(
            trade_id=f"ZT-{(idx+1):04d}",
            symbol=sym,
            side=side,
            size=size,
            entry_time=t_entry,
            exit_time=t_exit,
            entry_price=ep,
            exit_price=xp,
            fee_usd=round(ep * size * 0.00035 + xp * size * 0.00035, 2),
            slippage_bps=slip,
            realized_pnl_usd=pnl,
            realized_pnl_pct=pct,
            exit_reason=reason
        ))

try:
    seed_initial_trades()
except Exception as e:
    print(f"Warning seeding trades: {e}")

_candle_cache = {}
_last_tick_time = time.time()

def get_or_create_candles(symbol: str = "BTC-PERP"):
    if symbol not in _candle_cache:
        base_price = 68200.0 if "BTC" in symbol else (3420.0 if "ETH" in symbol else 184.0)
        df = WalkForwardEngine.generate_synthetic_perp_data(bars=80, start_price=base_price)
        candles = []
        for idx, row in df.iterrows():
            candles.append({
                "time": int(idx.timestamp()),
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2)
            })
        candles.sort(key=lambda x: x["time"])
        _candle_cache[symbol] = candles
    return _candle_cache[symbol]

def advance_market_tick():
    """Generates an incremental price step (serverless-friendly)."""
    global _last_tick_time
    now = time.time()
    if now - _last_tick_time < 3.0:
        return
    _last_tick_time = now

    symbols = ["BTC-PERP", "ETH-PERP", "SOL-PERP", "AVAX-PERP"]
    for sym in symbols:
        c_list = get_or_create_candles(sym)
        if not c_list:
            continue
        last_c = c_list[-1]
        new_time = last_c["time"] + 300
        change = random.gauss(0.0002, 0.0015)
        new_open = last_c["close"]
        new_close = round(new_open * (1.0 + change), 2)
        spread = abs(new_open - new_close) + round(new_open * 0.0005, 2)
        new_high = round(max(new_open, new_close) + spread, 2)
        new_low = round(min(new_open, new_close) - spread, 2)

        c_list.append({
            "time": new_time,
            "open": new_open,
            "high": new_high,
            "low": new_low,
            "close": new_close
        })
        if len(c_list) > 100:
            c_list.pop(0)

# In non-serverless local environments, run a background ticker
if not os.environ.get("VERCEL"):
    def _local_ticker_loop():
        while True:
            time.sleep(3)
            advance_market_tick()
    threading.Thread(target=_local_ticker_loop, daemon=True).start()


def find_index_html() -> str:
    candidates = [
        os.path.join(os.path.dirname(__file__), "index.html"),
        os.path.join(os.getcwd(), "zentrader", "ui", "index.html"),
        os.path.join(os.getcwd(), "public", "index.html"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "public", "index.html"),
        os.path.join(os.getcwd(), "index.html")
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

    return "<h1>ZenTrader API is Active. Index HTML file not located.</h1>"


@app.get("/", response_class=HTMLResponse)
def get_ui():
    advance_market_tick()
    return find_index_html()


@app.get("/api/health")
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "ZenTrader Platform",
        "runtime": "vercel" if os.environ.get("VERCEL") else "standalone",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/hud")
@app.get("/hud")
def get_hud():
    advance_market_tick()
    hud = supervisor.risk_sentinel.get_hud_telemetry()
    return {
        "tier": supervisor.tier_key,
        "starting_balance": hud.starting_balance,
        "current_equity": hud.current_equity,
        "peak_equity": hud.peak_equity,
        "net_pnl_usd": hud.net_pnl_usd,
        "net_pnl_pct": hud.net_pnl_pct,
        "shield_hp_pct": hud.shield_hp_pct,
        "current_drawdown_pct": hud.current_drawdown_pct,
        "max_drawdown_limit_pct": hud.max_drawdown_limit_pct,
        "daily_quest_target_usd": hud.daily_quest_target_usd,
        "daily_quest_progress_pct": hud.daily_quest_progress_pct,
        "is_halted": hud.is_halted,
        "status_message": hud.status_message
    }


@app.get("/api/trades")
@app.get("/trades")
def get_trades(limit: int = 25):
    advance_market_tick()
    return supervisor.ledger.get_recent_trades(limit=limit)


@app.get("/api/universe")
@app.get("/universe")
def get_universe():
    return supervisor.active_universe


@app.post("/api/tier")
@app.post("/tier")
def switch_tier(tier: str = Query("50k")):
    if tier in ACCOUNT_TIERS:
        supervisor.tier_key = tier
        supervisor.risk_sentinel.set_tier(tier)
        seed_initial_trades()
        return {"status": "success", "tier": tier, "starting_balance": supervisor.risk_sentinel.starting_balance}
    return JSONResponse(status_code=400, content={"error": "Invalid tier"})


@app.post("/api/panic")
@app.post("/panic")
def panic_halt():
    supervisor.risk_sentinel.trigger_circuit_breaker("USER_TRIGGERED_EMERGENCY_HALT")
    supervisor.broker.flatten_all_positions(current_prices={}, reason="PANIC_BUTTON")
    return {"status": "halted", "message": "All positions flattened. Trading locked."}


@app.get("/api/auto_loop")
@app.get("/auto_loop")
def get_auto_loop_status():
    return supervisor.auto_optimizer.get_status()


@app.post("/api/auto_loop/toggle")
@app.post("/auto_loop/toggle")
def toggle_auto_loop(enabled: bool = Query(...), interval_sec: int = Query(60)):
    status = supervisor.auto_optimizer.toggle(enabled=enabled, interval_sec=interval_sec)
    return status


@app.post("/api/auto_loop/run_now")
@app.post("/auto_loop/run_now")
def run_auto_loop_now():
    result = supervisor.auto_optimizer.run_cycle_now()
    return result


@app.get("/api/candles")
@app.get("/candles")
def get_candles(symbol: str = "BTC-PERP"):
    advance_market_tick()
    candles = get_or_create_candles(symbol)
    
    markers = []
    if len(candles) >= 30:
        markers.append({
            "time": candles[15]["time"],
            "position": "belowBar",
            "color": "#10b981",
            "shape": "arrowUp",
            "text": f"▲ LONG ${candles[15]['close']:,.0f}"
        })
        markers.append({
            "time": candles[25]["time"],
            "position": "aboveBar",
            "color": "#38bdf8",
            "shape": "circle",
            "text": "✕ TP +$180"
        })
    if len(candles) >= 50:
        markers.append({
            "time": candles[42]["time"],
            "position": "aboveBar",
            "color": "#f43f5e",
            "shape": "arrowDown",
            "text": f"▼ SHORT ${candles[42]['close']:,.0f}"
        })

    return {"symbol": symbol, "candles": candles, "markers": markers}


if __name__ == "__main__":
    uvicorn.run("zentrader.ui.server:app", host="0.0.0.0", port=8008, reload=False)
