"""
ZenTrader FastAPI Web Application & API
Powers the Gamified Trading Terminal with Live Lightweight-Charts and Telemetry.
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

# Pre-screen universe
supervisor.step1_screen_token_universe()

# Seed initial realistic paper trades so the UI journal has rich data immediately
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

seed_initial_trades()

# Dynamic market candle store
_candle_cache = {}

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


# Background live market streamer (simulates incoming perp ticks every 3 seconds)
def _market_ticker_daemon():
    symbols = ["BTC-PERP", "ETH-PERP", "SOL-PERP", "AVAX-PERP"]
    while True:
        try:
            time.sleep(3)
            if supervisor.risk_sentinel.is_halted:
                continue

            for sym in symbols:
                c_list = get_or_create_candles(sym)
                if not c_list:
                    continue
                last_c = c_list[-1]
                new_time = last_c["time"] + 300  # 5 min step

                # Slight random walk
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

            # Occasionally generate a live paper trade (1 out of 5 cycles)
            if random.random() < 0.25:
                sym = random.choice(["SOL-PERP", "BTC-PERP", "ETH-PERP"])
                side = random.choice(["LONG", "SHORT"])
                price = _candle_cache[sym][-1]["close"]
                pnl = round(random.choice([15.0, 32.5, 48.0, 75.0, -22.0, 95.0, -35.0]), 2)
                size = round(15.0 if "SOL" in sym else (0.2 if "BTC" in sym else 1.5), 3)

                now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                supervisor.risk_sentinel.record_pnl(pnl)
                supervisor.ledger.record_trade(TradeDocument(
                    trade_id=f"ZT-{random.randint(1000, 9999)}",
                    symbol=sym,
                    side=side,
                    size=size,
                    entry_time=(datetime.utcnow() - timedelta(minutes=4)).strftime("%Y-%m-%d %H:%M:%S"),
                    exit_time=now_str,
                    entry_price=price,
                    exit_price=round(price + (pnl / size if side == "LONG" else -pnl / size), 2),
                    fee_usd=round(price * size * 0.00035, 2),
                    slippage_bps=1.1,
                    realized_pnl_usd=pnl,
                    realized_pnl_pct=round((pnl / (price * size)) * 100, 2),
                    exit_reason="TAKE_PROFIT" if pnl > 0 else "STOP_LOSS"
                ))

        except Exception as e:
            pass

threading.Thread(target=_market_ticker_daemon, daemon=True).start()


@app.get("/", response_class=HTMLResponse)
def get_ui():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r") as f:
        return f.read()


@app.get("/api/hud")
def get_hud():
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
def get_trades(limit: int = 25):
    return supervisor.ledger.get_recent_trades(limit=limit)


@app.get("/api/universe")
def get_universe():
    return supervisor.active_universe


@app.post("/api/tier")
def switch_tier(tier: str = Query("50k")):
    if tier in ACCOUNT_TIERS:
        supervisor.tier_key = tier
        supervisor.risk_sentinel.set_tier(tier)
        seed_initial_trades()
        return {"status": "success", "tier": tier, "starting_balance": supervisor.risk_sentinel.starting_balance}
    return JSONResponse(status_code=400, content={"error": "Invalid tier"})


@app.post("/api/panic")
def panic_halt():
    supervisor.risk_sentinel.trigger_circuit_breaker("USER_TRIGGERED_EMERGENCY_HALT")
    supervisor.broker.flatten_all_positions(current_prices={}, reason="PANIC_BUTTON")
    return {"status": "halted", "message": "All positions flattened. Trading locked."}


@app.get("/api/auto_loop")
def get_auto_loop_status():
    return supervisor.auto_optimizer.get_status()


@app.post("/api/auto_loop/toggle")
def toggle_auto_loop(enabled: bool = Query(...), interval_sec: int = Query(60)):
    status = supervisor.auto_optimizer.toggle(enabled=enabled, interval_sec=interval_sec)
    return status


@app.post("/api/auto_loop/run_now")
def run_auto_loop_now():
    result = supervisor.auto_optimizer.run_cycle_now()
    return result


@app.get("/api/candles")
def get_candles(symbol: str = "BTC-PERP"):
    candles = get_or_create_candles(symbol)
    
    # Calculate markers on known bars
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
