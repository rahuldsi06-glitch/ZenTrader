#!/usr/bin/env python3
"""
ZenTrader Launcher Script
Run:
    python3 run_zentrader.py --ui          # Launches the Gamified Web UI on http://localhost:8008
    python3 run_zentrader.py --pipeline    # Runs the autonomous agentic loop in terminal
"""
import argparse
import sys
import uvicorn
from zentrader.supervisor import ZenSupervisor

def main():
    parser = argparse.ArgumentParser(description="ZenTrader Autonomous Perp Trading Platform")
    parser.add_argument("--ui", action="store_true", help="Launch the interactive Web UI")
    parser.add_argument("--tier", default="50k", choices=["10k", "25k", "50k", "100k"], help="Account balance tier")
    parser.add_argument("--strategy", default="obi_scalper", choices=["obi_scalper", "momentum_breakout"], help="Strategy")
    parser.add_argument("--port", type=int, default=8008, help="Port for the Web UI (default: 8008)")
    args = parser.parse_args()

    if args.ui:
        print(f"\n🚀 Launching ZenTrader Gamified Terminal on http://localhost:{args.port} ...")
        uvicorn.run("zentrader.ui.server:app", host="0.0.0.0", port=args.port, reload=False)
    else:
        print(f"\n⚡ Running ZenTrader Autonomous Pipeline for Tier [{args.tier}] with [{args.strategy}] ...")
        supervisor = ZenSupervisor(account_tier=args.tier, selected_strategy=args.strategy)
        universe = supervisor.step1_screen_token_universe()
        if universe:
            top_token = universe[0]["symbol"]
            supervisor.step2_select_and_validate_strategy(symbol=top_token)
            supervisor.step4_deploy_and_run_paper_session(symbol=top_token, num_live_bars=150)

if __name__ == "__main__":
    main()
