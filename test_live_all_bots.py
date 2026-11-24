"""
Live MT5 Multi-Bot Verification & Diagnostic Suite
Tests all 7 RK Renko V4 bots against the live MetaTrader 5 terminal:
- Verifies MT5 account, trade permissions, and terminal status
- Connects to each symbol (XAUUSD, BTCUSD, EURUSD, GBPUSD, USDJPY, AUDUSD, EURJPY)
- Verifies market quotes, bid/ask spread, and contract specs
- Validates dynamic ATR brick size calculation from real MT5 D1 bars
- Validates 1H EMA 50 calculation from real MT5 H1 bars
- Validates AI Smart Renko engine ingestion of live M1 candles
- Tests bot instantiation with no_zones=True (Zones Disabled for testing)
- Verifies live order_check readiness (SL calculation, margin, IOC filling mode)
Strictly self-contained in MT5Renko workspace.
"""

import os
import sys
import datetime
from typing import List, Dict, Any

# Ensure workspace root is on sys.path
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from core.bot_engine import RKRenkoBot
from core.execution import MT5ExecutionEngine


BOT_CONFIGS = [
    {
        "symbol": "XAUUSD",
        "name": "Gold",
        "magic": 777001,
        "session_hours": 22,
        "atr_period": 5,
        "atr_divisor": 22,
        "lot": 0.01,
        "sl_bricks": 5.0,
    },
    {
        "symbol": "BTCUSD",
        "name": "Crypto",
        "magic": 777002,
        "session_hours": 23,
        "atr_period": 7,
        "atr_divisor": 23,
        "lot": 0.01,
        "sl_bricks": 5.0,
    },
    {
        "symbol": "EURUSD",
        "name": "Forex Major",
        "magic": 777003,
        "session_hours": 22,
        "atr_period": 5,
        "atr_divisor": 22,
        "lot": 0.01,
        "sl_bricks": 5.0,
    },
    {
        "symbol": "GBPUSD",
        "name": "Forex Major",
        "magic": 777004,
        "session_hours": 22,
        "atr_period": 5,
        "atr_divisor": 22,
        "lot": 0.01,
        "sl_bricks": 5.0,
    },
    {
        "symbol": "USDJPY",
        "name": "Forex Major",
        "magic": 777005,
        "session_hours": 22,
        "atr_period": 5,
        "atr_divisor": 22,
        "lot": 0.01,
        "sl_bricks": 5.0,
    },
    {
        "symbol": "AUDUSD",
        "name": "Forex Major",
        "magic": 777006,
        "session_hours": 22,
        "atr_period": 5,
        "atr_divisor": 22,
        "lot": 0.01,
        "sl_bricks": 5.0,
    },
    {
        "symbol": "EURJPY",
        "name": "Forex Cross",
        "magic": 777007,
        "session_hours": 22,
        "atr_period": 5,
        "atr_divisor": 22,
        "lot": 0.01,
        "sl_bricks": 5.0,
    },
]


def run_live_diagnostics():
    print("=" * 75)
    print("  RK RENKO V4 - LIVE MT5 ALL BOTS DIAGNOSTICS & TEST SUITE")
    print("  Mode: LIVE MetaTrader 5 | Zones: DISABLED FOR TESTING")
    print("=" * 75)

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("[ERROR] MetaTrader5 python library is not installed.")
        sys.exit(1)

    if not mt5.initialize():
        print(f"[ERROR] Failed to initialize MT5: {mt5.last_error()}")
        sys.exit(1)

    terminal = mt5.terminal_info()
    account = mt5.account_info()

    if terminal is None or account is None:
        print("[ERROR] Could not fetch MT5 terminal or account info.")
        mt5.shutdown()
        sys.exit(1)

    print(f"  Broker / Company: {terminal.company} ({terminal.name})")
    print(f"  Account Login:    {account.login} | Server: {account.server}")
    print(f"  Balance:          ${account.balance:,.2f} {account.currency} | Equity: ${account.equity:,.2f}")
    print(f"  Margin Free:      ${account.margin_free:,.2f} | Leverage: 1:{account.leverage}")
    print(f"  Trade Allowed:    {terminal.trade_allowed} | Connected: {terminal.connected}")
    print("-" * 75)

    results: List[Dict[str, Any]] = []

    for cfg in BOT_CONFIGS:
        symbol = cfg["symbol"]
        magic = cfg["magic"]
        print(f"\n>>> Testing Live Bot: {symbol} (Magic: {magic}, Class: {cfg['name']})...")

        # 1. Instantiate Bot in LIVE mode with zones disabled
        bot = RKRenkoBot(
            symbol=symbol,
            magic=magic,
            lot_size=cfg["lot"],
            session_hours=cfg["session_hours"],
            atr_period=cfg["atr_period"],
            atr_divisor=cfg["atr_divisor"],
            sl_bricks=cfg["sl_bricks"],
            tp_r=0.0,
            trail_bricks=4.0,
            trail_act=4.0,
            zone_streak_bricks=3,
            min_trend_bricks=2,
            max_daily_trades=12,
            max_trades_per_zone=4,
            no_zones=True,        # Zones disabled for testing
            no_zone_only=True,    # Allow mid-air entries
            firstred_shadow_rule=False,
            renko_mode="1m",
            dry_run=False,        # LIVE execution mode
        )

        # 2. Acquire Instance Lock
        lock_ok = bot.execution.acquire_instance_lock()
        assert lock_ok, f"Failed to acquire instance lock for {symbol}"

        try:
            # 3. Connect to MT5 Symbol
            conn_ok = bot.execution.connect()
            if not conn_ok:
                print(f"  [FAIL] Could not connect {symbol} to MT5.")
                results.append({"symbol": symbol, "status": "FAIL", "reason": "MT5 Connect Fail"})
                continue

            # 4. Market Quote & Specs
            bid, ask = bot.execution.get_market_quote()
            spread_pts = (ask - bid) / bot.execution.point if bot.execution.point > 0 else 0.0
            print(f"  Market Quote:    Bid={bid:.5f} | Ask={ask:.5f} | Spread={spread_pts:.1f} pts")
            print(f"  Specs:           Digits={bot.execution.digits} | Point={bot.execution.point} | MinLot={bot.execution.min_lot}")

            # 5. ATR Dynamic Brick Size Calculation from Live MT5
            brick_size = bot.calculate_atr_brick_size()
            bot.renko.reset(brick_size=brick_size)
            bot.trailing.brick_size = brick_size
            print(f"  Live Brick Size: {brick_size:.5f} (ATR({cfg['atr_period']}) / {cfg['atr_divisor']})")

            # 6. Live H1 EMA 50 Macro
            h1_ema = bot.get_h1_ema50()
            h1_str = f"{h1_ema:.5f}" if h1_ema else "N/A"
            print(f"  Live 1H EMA 50:  {h1_str}")

            # 7. Feed 100 Real Historical M1 Candles into Bot Pipeline
            m1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 1, 100)
            initial_bricks_count = len(bot.renko.bricks)
            if m1_rates is not None and len(m1_rates) > 0:
                for bar in m1_rates:
                    bar_time = datetime.datetime.fromtimestamp(bar["time"], tz=datetime.timezone.utc)
                    bot.process_m1_bar(bar["open"], bar["high"], bar["low"], bar["close"], bar_time)

            bricks_built = len(bot.renko.bricks) - initial_bricks_count
            last_brick = bot.renko.latest_brick
            last_st = bot.indicators.supertrend.direction
            st_text = "BULL (+1)" if last_st == 1 else ("BEAR (-1)" if last_st == -1 else "NEUTRAL")
            ema5_val = bot.indicators.ema5.value
            ema9_val = bot.indicators.ema9.value
            ema5_str = f"{ema5_val:.5f}" if ema5_val is not None else "N/A"
            ema9_str = f"{ema9_val:.5f}" if ema9_val is not None else "N/A"
            ai_status = bot.indicators.ai_renko.status
            ai_dir = bot.indicators.ai_renko.direction

            print(f"  Renko Engine:    Ingested {len(m1_rates)} M1 bars -> Built {bricks_built} bricks | Total Bricks={len(bot.renko.bricks)}")
            if last_brick:
                print(f"  Latest Brick:    Index={last_brick.index} | Close={last_brick.close:.5f} | BarNum={last_brick.bar_num}")
            print(f"  Indicators:      Supertrend={st_text} | EMA5={ema5_str} | EMA9={ema9_str}")
            print(f"  AI Smart Renko:  Status={ai_status} | Direction={ai_dir}")
            print(f"  Zone Check:      no_zones={bot.no_zones} | zone_only_trades={bot.zone_only_trades} -> MidAir Allowed!")

            # 8. Live MT5 order_check Validation (Realistic SL based on 5 bricks)
            sl_dist = 5.0 * brick_size
            test_sl = round(ask - sl_dist, bot.execution.digits)
            order_req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(cfg["lot"]),
                "type": mt5.ORDER_TYPE_BUY,
                "price": ask,
                "sl": test_sl,
                "tp": 0.0,
                "deviation": 20,
                "magic": magic,
                "comment": "RK_Live_Test",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            chk = mt5.order_check(order_req)
            retcode = chk.retcode if chk else -1
            comment = chk.comment if chk else str(mt5.last_error())
            print(f"  Order Pre-Check: Retcode={retcode} ({comment}) | Volume={cfg['lot']} | SL={test_sl:.5f}")

            assert retcode == 0, f"Order check failed on {symbol}: retcode {retcode} - {comment}"
            print(f"  -> {symbol} Live Verification: PASSED")
            results.append({
                "symbol": symbol,
                "status": "PASSED",
                "bid": bid,
                "ask": ask,
                "spread": f"{spread_pts:.1f} pts",
                "brick": f"{brick_size:.5f}",
                "order_check": comment,
            })

        finally:
            bot.execution.release_instance_lock()

    mt5.shutdown()

    # Summary Report Table
    print("\n" + "=" * 75)
    print("  LIVE ALL BOTS VERIFICATION SUMMARY (NO ZONES / MID-AIR READY)")
    print("=" * 75)
    print(f"{'SYMBOL':<10} | {'STATUS':<8} | {'BID':<12} | {'ASK':<12} | {'BRICK SIZE':<12} | {'ORDER PRE-CHECK':<15}")
    print("-" * 75)
    all_passed = True
    for r in results:
        sym = r["symbol"]
        st = r["status"]
        if st != "PASSED":
            all_passed = False
        bid_s = f"{r.get('bid', 0.0):.5f}"
        ask_s = f"{r.get('ask', 0.0):.5f}"
        brk_s = r.get("brick", "-")
        oc_s = r.get("order_check", "-")
        print(f"{sym:<10} | {st:<8} | {bid_s:<12} | {ask_s:<12} | {brk_s:<12} | {oc_s:<15}")
    print("=" * 75)

    if all_passed:
        print("  ★ ALL 7 BOTS SUCCESSFULLY VERIFIED IN LIVE MT5 WITH ZONES DISABLED ★")
    else:
        print("  ⚠ ONE OR MORE BOTS FAILED LIVE VERIFICATION")
    print("=" * 75)


if __name__ == "__main__":
    run_live_diagnostics()
