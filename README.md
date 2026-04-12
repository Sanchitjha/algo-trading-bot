# Algo Trading Bot 🚀

**Pine Script v6 → TradingView Webhook → Python Flask → MT5 Auto Trading**

Complete implementation of RSI+MACD+EMA confluence strategy. 24/7 cloud operation. 1-2% risk per trade. Telegram alerts.

[![Status](https://img.shields.io/badge/status-production-green.svg)]()

## 📊 Strategy Overview
- **Trend**: EMA9 > EMA21 (bullish) / EMA9 < EMA21 (bearish)
- **Entry**: RSI bounce from oversold(30) or MACD crossover  
- **Risk**: ATR(14)×1.5 SL, 1:2 RR TP
- **Backtested**: [backtest.py](backtest.py)

## 🛠 Quick Setup (5 minutes)

### 1. Prerequisites
```
pip install -r requirements.txt
```
- TradingView Pro+ (webhooks)
- MT5 demo account (Vantage/Exness)
- Render account (free tier)

### 2. Configure
```bash
cp .env.example .env
# Edit .env with your MT5 + Telegram creds
```

### 3. Local Test
```bash
python app.py
# Visit http://localhost:5000/health
# curl -X POST http://localhost:5000/webhook -H "Content-Type: application/json" -d '{"action":"buy","symbol":"EURUSD","sl":1.0800,"tp":1.0900}'
```

### 4. TradingView Alert
```
Webhook URL: https://your-bot.onrender.com/webhook  
Message:
{"action":"buy","symbol":"{{ticker}}","sl":{{plot_0}},"tp":{{plot_1}},"risk_pct":1.0}
```

### 5. Deploy Render (Free)
1. Push to GitHub
2. render.com → New Web Service → Connect repo
3. Build: `pip install -r requirements.txt`
4. Start: `gunicorn app:app`
5. Env vars from .env.example

## 📁 Project Structure
```
algo-trading-bot/
├── app.py           # Flask webhook server
├── bot/             # Core logic
│   ├── broker.py    # MT5 orders
│   ├── risk.py      # 1-2% position sizing
│   ├── signals.py   # Validation
│   └── telegram.py  # Alerts
├── config/settings.py
├── backtest.py      # Strategy validation
├── pinescript/strategy.pine
└── requirements.txt
```

## ✅ Verified Features (Matches Spec 100%)
- [x] Pine Script v6 signals (RSI/MACD/EMA/ATR)
- [x] Webhook HMAC security
- [x] Dynamic lot sizing (risk % → lots via pip value)
- [x] MT5 integration (Vantage/Exness)
- [x] Risk gates (daily loss, max positions)
- [x] Telegram notifications
- [x] Health monitoring
- [x] Backtesting + optimization
- [x] Render/VPS ready (Procfile)

## 🧪 Testing Checklist
1. `python backtest.py --data data/EURUSD_H1.csv`
2. MT5 demo → verify orders execute
3. TradingView test alert → check Telegram + MT5
4. Kill server → auto-restart on Render

## ⚠️ Production Notes
- Risk 1% live, 2% demo max
- Monitor /health daily
- Whitelist only tested symbols
- VPS for <1s latency (Render ~500ms)

**Live demo 7+ days before real money.**

---

[Full Technical Documentation](../AlgoTrading_Documentation.html)
