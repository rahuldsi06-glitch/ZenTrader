# 🧘 ZenTrader

**Institutional-Grade Autonomous Perp Trading Platform & Gamified Terminal**

ZenTrader is an autonomous quantitative trading platform designed for Perpetual Futures (Hyperliquid, Aster, Aevo, or paper simulation). It combines deep liquidity screening, 75/25 walk-forward overfitting guards, institutional drawdown circuit breakers, automated continuous re-optimization, and a gamified terminal with TradingView Lightweight Charts.

---

## ⚡ Key Architecture Features

1. **Token Universe Screener**:
   - Filters perpetuals by 24h Volume (> $25M), Bid-Ask Spread (< 3.5 bps), and Orderbook Depth (+/-2% > $250k).
   - Dynamic market impact & slippage calculation.

2. **Modular Strategy Engine**:
   - Pluggable alpha architecture (`ZenStrategyBase`).
   - Includes **Order Book Imbalance (OBI) Micro-Scalper** and **Donchian/ATR Volatility Breakout**.

3. **75% In-Sample / 25% Out-of-Sample Walk-Forward Engine**:
   - Trains on 75% historical data, validates on untouched 25% holdout.
   - Computes Walk-Forward Efficiency (WFE), Out-of-Sample Sharpe, and simulated exchange friction (fees + slippage).

4. **Risk Sentinel & Capital Tiers**:
   - Pre-configured tiers: **$10k, $25k, $50k, and $100k**.
   - **Shield (Drawdown HP Bar)**: Real-time visual health bar with automatic emergency circuit breaker.
   - **Daily Quest Tracker**: Achievable daily profit target with lock-in protection.

5. **Automated Continuous Re-Optimization Loop**:
   - Interactive toggle in the UI to enable background walk-forward re-auditing (every 30s in demo, 4h in production).
   - Automatically recalibrates active alphas when market regime shifts.

6. **Interactive Gamified UI**:
   - Dark obsidian luxury aesthetic with TradingView Lightweight Charts.
   - Direct execution pins (▲ Long, ▼ Short, ✕ Exit with PnL tags).
   - 1-Click panic kill-switch.

---

## 🚀 Quickstart (Local)

### 1. Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Launch the Web Terminal
```bash
python3 run_zentrader.py --ui --port 8008
```
Open [http://localhost:8008](http://localhost:8008) in your browser.

### 3. Run the Autonomous Pipeline in Terminal
```bash
python3 run_zentrader.py --tier 50k --strategy obi_scalper
```

---

## 🌐 Deploy to Vercel

ZenTrader is pre-configured for instant serverless deployment on Vercel using `vercel.json` and `api/index.py`.

### Method A: Via Vercel CLI
```bash
# In the ZenTrader folder:
npx vercel
```
Follow the prompts (accept default settings).

### Method B: Via GitHub & Vercel Dashboard
1. Push this repository to GitHub (see below).
2. Go to [vercel.com/new](https://vercel.com/new).
3. Import your `ZenTrader` repository.
4. Click **Deploy**. Vercel will automatically detect `vercel.json` and deploy the ASGI FastAPI application!

---

## 📦 Push to GitHub

To push this codebase to your GitHub account:

```bash
cd /Users/rahul/Documents/ZenTrader

# 1. Initialize git
git init
git add .
git commit -m "feat: initial commit of ZenTrader autonomous perp platform"

# 2. Link your GitHub remote repository
# (Create a new empty repo named 'ZenTrader' on github.com first)
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/ZenTrader.git
git branch -M main
git push -u origin main
```
