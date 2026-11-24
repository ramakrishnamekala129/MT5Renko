"""
RK Renko V4 - Multi-Bot Concurrent Launcher
Runs all 7 dedicated bots concurrently in background threads:
1. XAUUSD (Magic 777001)
2. BTCUSD (Magic 777002)
3. EURUSD (Magic 777003)
4. GBPUSD (Magic 777004)
5. USDJPY (Magic 777005)
6. AUDUSD (Magic 777006)
7. EURJPY (Magic 777007)

Features:
- Zones disabled by default for testing (use --enable-zones to re-enable)
- Live MT5 trade execution with --live (dry-run by default)
- Graceful Ctrl+C shutdown releasing all PID locks
- Real-time periodic status dashboard
Strictly self-contained in MT5Renko workspace root.
"""

import os
import sys
import time
import signal
import logging
import argparse
import threading
from typing import List, Dict

# Workspace root on sys.path
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from core.bot_engine import RKRenkoBot

BOT_SPECS = [
    {"symbol": "XAUUSD", "magic": 777001, "session": 22, "atr_p": 5, "atr_d": 22, "lot": 0.01},
    {"symbol": "BTCUSD", "magic": 777002, "session": 23, "atr_p": 7, "atr_d": 23, "lot": 0.01},
    {"symbol": "EURUSD", "magic": 777003, "session": 22, "atr_p": 5, "atr_d": 22, "lot": 0.01},
    {"symbol": "GBPUSD", "magic": 777004, "session": 22, "atr_p": 5, "atr_d": 22, "lot": 0.01},
    {"symbol": "USDJPY", "magic": 777005, "session": 22, "atr_p": 5, "atr_d": 22, "lot": 0.01},
    {"symbol": "AUDUSD", "magic": 777006, "session": 22, "atr_p": 5, "atr_d": 22, "lot": 0.01},
    {"symbol": "EURJPY", "magic": 777007, "session": 22, "atr_p": 5, "atr_d": 22, "lot": 0.01},
]


class MultiBotManager:
    def __init__(self, live: bool, lot: float, mode: str, no_zones: bool, verbose: bool):
        self.live = live
        self.lot = lot
        self.mode = mode
        self.no_zones = no_zones
        self.verbose = verbose
        self.bots: List[RKRenkoBot] = []
        self.threads: List[threading.Thread] = []
        self.running = False

    def initialize_bots(self):
        for spec in BOT_SPECS:
            bot = RKRenkoBot(
                symbol=spec["symbol"],
                magic=spec["magic"],
                lot_size=self.lot,
                session_hours=spec["session"],
                atr_period=spec["atr_p"],
                atr_divisor=spec["atr_d"],
                sl_bricks=5.0,
                tp_r=0.0,
                trail_bricks=4.0,
                trail_act=4.0,
                zone_streak_bricks=3,
                min_trend_bricks=2,
                max_daily_trades=12,
                max_trades_per_zone=4,
                no_zones=self.no_zones,
                no_zone_only=self.no_zones,
                renko_mode=self.mode,
                dry_run=not self.live,
            )
            self.bots.append(bot)

    def start(self):
        self.running = True
        print("=" * 75)
        print("  RK RENKO V4 - MULTI-BOT CONCURRENT ENGINE")
        print(f"  Execution: {'LIVE (MetaTrader 5)' if self.live else 'DRY RUN (Paper)'}")
        print(f"  Zones:     {'DISABLED (Testing Mode - MidAir Active)' if self.no_zones else 'ENABLED'}")
        print(f"  Mode:      {self.mode} | Default Lot: {self.lot}")
        print(f"  Active Bots ({len(self.bots)}): {', '.join(b.symbol for b in self.bots)}")
        print("=" * 75)

        for bot in self.bots:
            t = threading.Thread(target=bot.run_live, name=f"Bot-{bot.symbol}", daemon=True)
            self.threads.append(t)
            t.start()
            print(f"  [+] Started thread for {bot.symbol} (Magic: {bot.magic})")

        print("-" * 75)
        print("  All bots are running. Press Ctrl+C to stop all bots cleanly.")
        print("-" * 75)

        try:
            while self.running:
                time.sleep(10)
                self.print_status_summary()
        except KeyboardInterrupt:
            print("\n[!] Shutdown signal received. Stopping all bots...")
            self.stop()

    def print_status_summary(self):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n--- Multi-Bot Heartbeat [{ts}] ---")
        for b in self.bots:
            st = b.indicators.supertrend.direction
            st_str = "BULL" if st == 1 else ("BEAR" if st == -1 else "NEUT")
            bricks = len(b.renko.bricks)
            pos_open = "YES" if b.open_position_state else "NO"
            print(f"  {b.symbol:<8} | Mode: {b.renko_mode} | ST: {st_str:<4} | Bricks: {bricks:<3} | InTrade: {pos_open}")

    def stop(self):
        self.running = False
        for bot in self.bots:
            bot.is_running = False
        for t in self.threads:
            t.join(timeout=2.0)
        print("  All bots successfully stopped.")


def main():
    parser = argparse.ArgumentParser(description="RK Renko V4 - Multi-Bot Launcher")
    parser.add_argument("--live", action="store_true", help="Execute real MT5 trades (default is dry-run)")
    parser.add_argument("--lot", type=float, default=0.01, help="Trade lot size (default: 0.01)")
    parser.add_argument("--mode", choices=["1m", "tick"], default="1m", help="Renko construction mode (default: 1m)")
    parser.add_argument("--no-zones", action="store_true", default=True, help="Disable reference zone engine (default: True for testing)")
    parser.add_argument("--enable-zones", dest="no_zones", action="store_false", help="Enable reference zone engine")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    manager = MultiBotManager(
        live=args.live,
        lot=args.lot,
        mode=args.mode,
        no_zones=args.no_zones,
        verbose=args.verbose,
    )
    manager.initialize_bots()
    manager.start()


if __name__ == "__main__":
    main()
