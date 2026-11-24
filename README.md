# RK Renko V4 Trading Bots

Implementation of the **RK Renko V4 Trading System** for MetaTrader 5, fully self-contained in this workspace with zero external folder dependencies.

---

## 1. Directory Structure

```
d:\MT5Renko\
├── RK_RENKO_V4_RULES_AND_PARAMETERS.md   # Reference specification
├── README.md                             # Documentation & usage guide
├── test_renko_system.py                  # Full automated verification suite
│
├── core/                                 # 100% self-contained local engine
│   ├── __init__.py                       # Package exports
│   ├── renko.py                          # Renko brick builder & streak counter
│   ├── indicators.py                     # Supertrend(1, 3.1), EMA 5/9, 1H EMA 50, AI Smart Renko
│   ├── zones.py                          # 5 Reference zones & Fibonacci 0.44–0.56 corridor engine
│   ├── filters.py                        # 9-Layer confluence filter stack & FirstRed-Shadow logic
│   ├── trailing.py                       # Tick-level trailing stop with spread spike guard
│   ├── execution.py                      # MT5 execution, hedge prevention, PID locks
│   └── bot_engine.py                     # Unified bot execution loop (M1 candle & tick modes)
│
├── xauusd_bot.py                         # Dedicated Gold bot (Session 22H, ATR(5)/22, Magic 777001)
├── btcusd_bot.py                         # Dedicated BTCUSD bot (Session 23H, ATR(7)/23, Magic 777002)
├── eurusd_bot.py                         # Dedicated EURUSD bot (Session 22H, ATR(5)/22, Magic 777003)
├── gbpusd_bot.py                         # Dedicated GBPUSD bot (Session 22H, ATR(5)/22, Magic 777004)
├── usdjpy_bot.py                         # Dedicated USDJPY bot (Session 22H, ATR(5)/22, Magic 777005)
├── audusd_bot.py                         # Dedicated AUDUSD bot (Session 22H, ATR(5)/22, Magic 777006)
└── eurjpy_bot.py                         # Dedicated EURJPY bot (Session 22H, ATR(5)/22, Magic 777007)
```

---

## 2. Dedicated Bot Configurations

Each instrument has its own executable file with preconfigured magic numbers and parameters:

| Bot Script | Symbol | Asset Class | Session | ATR Period | ATR Divisor | Magic Number | Default Lot |
|---|---|---|---|---|---|---|---|
| `xauusd_bot.py` | `XAUUSD` | Gold | 22H | 5 | 22 | `777001` | 0.01 |
| `btcusd_bot.py` | `BTCUSD` | Crypto | 23H | 7 | 23 | `777002` | 0.01 |
| `eurusd_bot.py` | `EURUSD` | Forex Major | 22H | 5 | 22 | `777003` | 0.01 |
| `gbpusd_bot.py` | `GBPUSD` | Forex Major | 22H | 5 | 22 | `777004` | 0.01 |
| `usdjpy_bot.py` | `USDJPY` | Forex Major | 22H | 5 | 22 | `777005` | 0.01 |
| `audusd_bot.py` | `AUDUSD` | Forex Major | 22H | 5 | 22 | `777006` | 0.01 |
| `eurjpy_bot.py` | `EURJPY` | Forex Cross | 22H | 5 | 22 | `777007` | 0.01 |

---

## 3. How to Run

By default, all bots start in **DRY RUN (Paper Trading)** mode for safety.

### Dry-Run Simulation (Default)
```bash
python xauusd_bot.py
python btcusd_bot.py
python eurusd_bot.py
```

### Live MT5 Execution
Pass the `--live` flag to execute real orders on your connected MT5 terminal:
```bash
python xauusd_bot.py --live
python btcusd_bot.py --live --lot 0.02
python eurusd_bot.py --live --lot 0.05
```

### Useful CLI Flags
- `--live`: Send real orders to MetaTrader 5 (default: simulation).
- `--lot <value>`: Override order lot size (default: `0.01`).
- `--mode {1m,tick}`: Brick update mode:
  - `1m` (default): Updates on completed 1-minute candle close.
  - `tick`: Real-time streaming tick execution.
- `--brick <value>`: Manually override the dynamic ATR brick size.
- `--no-zones`: Disable reference zone engine (default: **True** for testing).
- `--enable-zones`: Re-enable reference zone engine.
- `--no-zone-only`: Allow mid-air Supertrend entries alongside zone trades (default: **True** for testing).
- `--zone-only`: Restrict entries strictly to zone events.
- `--firstred-shadow`: Enable the FirstRed-Shadow structural gate.
- `--verbose`: Enable detailed debug logs.

---

### Running All Bots Concurrently
Run all 7 bots simultaneously in live or paper trading mode:
```bash
# Live MT5 multi-bot execution
python run_all_bots.py --live

# Paper simulation multi-bot execution
python run_all_bots.py
```

---

## 4. Automated Verification & Live MT5 Diagnostics

### Offline Verification Suite (6/6 Tests)
```bash
python test_renko_system.py
```
This tests:
1. Renko brick 1-box continuation and 2-box reversal construction.
2. Supertrend(1, 3.1) and EMA 5/9 calculations.
3. Reference Zones and Fibonacci 0.44–0.56 corridor classification.
4. 9-Layer Confluence Filter Stack (including no-zones test).
5. Trailing Stop Engine & Spread Spike Guard.
6. Zero external directory dependencies inspection.

### Live MT5 All-Bots Diagnostic Suite
```bash
python test_live_all_bots.py
```
Validates all 7 bots against the live MT5 terminal:
- Verifies MT5 account, equity, free margin, leverage, and trade permissions.
- Fetches real-time bid/ask quotes and calculates broker spread.
- Computes dynamic ATR brick sizes from live D1 candles.
- Fetches live 1H EMA 50 macro filter values.
- Feeds 100 live M1 candles through the Renko brick builder & AI Pre-Renko engine.
- Validates mid-air Supertrend entry evaluation with zones disabled.
- Tests broker order check (`order_check`) with realistic 5-brick SL and IOC filling mode.
