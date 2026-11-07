"""
ZenTrader FastAPI Web Application & API
Powers the Gamified Trading Terminal with Live Lightweight-Charts and Telemetry.
"""
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
import os
import uvicorn

from zentrader.supervisor import ZenSupervisor
from zentrader.config import ACCOUNT_TIERS

app = FastAPI(title="ZenTrader Autonomous Platform", version="1.0.0")
supervisor = ZenSupervisor(account_tier="50k", selected_strategy="obi_scalper")

# Pre-initialize pipeline
supervisor.step1_screen_token_universe()
if supervisor.active_universe:
    top_sym = supervisor.active_universe[0]["symbol"]
    supervisor.step2_select_and_validate_strategy(symbol=top_sym)
    supervisor.step4_deploy_and_run_paper_session(symbol=top_sym, num_live_bars=80)


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
def get_trades(limit: int = 20):
    return supervisor.ledger.get_recent_trades(limit=limit)


@app.get("/api/universe")
def get_universe():
    return supervisor.active_universe


@app.post("/api/tier")
def switch_tier(tier: str = Query("50k")):
    if tier in ACCOUNT_TIERS:
        supervisor.tier_key = tier
        supervisor.risk_sentinel.set_tier(tier)
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
    from zentrader.backtest.walk_forward import WalkForwardEngine
    candles_df = WalkForwardEngine.generate_synthetic_perp_data(bars=60, start_price=68200.0)
    candles = []
    for idx, row in candles_df.iterrows():
        candles.append({
            "time": str(idx)[:16],
            "open": round(row["open"], 2),
            "high": round(row["high"], 2),
            "low": round(row["low"], 2),
            "close": round(row["close"], 2)
        })

    markers = [
        {"time": candles[15]["time"], "position": "belowBar", "color": "#10b981", "shape": "arrowUp", "text": "▲ LONG $68,150"},
        {"time": candles[28]["time"], "position": "aboveBar", "color": "#38bdf8", "shape": "circle", "text": "✕ TP +$820"},
        {"time": candles[42]["time"], "position": "aboveBar", "color": "#f43f5e", "shape": "arrowDown", "text": "▼ SHORT $68,490"}
    ]

    return {"candles": candles, "markers": markers}


if __name__ == "__main__":
    uvicorn.run("zentrader.ui.server:app", host="0.0.0.0", port=8008, reload=False)
