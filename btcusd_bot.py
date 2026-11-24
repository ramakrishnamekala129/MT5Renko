"""
RK Renko V4 - Bitcoin (BTCUSD) Dedicated Bot
Instrument: BTCUSD (Bitcoin Crypto)
Asset Class: Cryptocurrency
Session Hours: 23H | ATR Period: 7 | ATR Divisor: 23
Magic Number: 777002
Strictly self-contained - zero external folder references.
"""

import os
import sys
import argparse
import logging

# Ensure local MT5Renko workspace root is on sys.path
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from core.bot_engine import RKRenkoBot


def main():
    parser = argparse.ArgumentParser(description="RK Renko V4 - BTCUSD (Crypto) Bot")
    parser.add_argument("--live", action="store_true", help="Execute real MT5 trades (default is dry-run)")
    parser.add_argument("--lot", type=float, default=0.01, help="Trade lot size (default: 0.01)")
    parser.add_argument("--mode", choices=["1m", "tick"], default="1m", help="Renko construction mode (default: 1m)")
    parser.add_argument("--brick", type=float, default=None, help="Override dynamic ATR brick size with fixed value")
    parser.add_argument("--no-zones", action="store_true", default=True, help="Disable reference zone engine (default: True for testing)")
    parser.add_argument("--enable-zones", dest="no_zones", action="store_false", help="Enable reference zone engine")
    parser.add_argument("--no-zone-only", action="store_true", default=True, help="Allow mid-air Supertrend entries alongside zone trades (default: True for testing)")
    parser.add_argument("--zone-only", dest="no_zone_only", action="store_false", help="Restrict entries strictly to zone events")
    parser.add_argument("--firstred-shadow", action="store_true", help="Enable FirstRed-Shadow structural rule")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    bot = RKRenkoBot(
        symbol="BTCUSD",
        magic=777002,
        lot_size=args.lot,
        session_hours=23,
        atr_period=7,
        atr_divisor=23,
        fixed_brick_size=args.brick,
        sl_bricks=5.0,
        tp_r=0.0,
        trail_bricks=4.0,
        trail_act=4.0,
        zone_streak_bricks=3,
        min_trend_bricks=2,
        max_daily_trades=12,
        max_trades_per_zone=4,
        no_zones=args.no_zones,
        no_zone_only=args.no_zone_only,
        firstred_shadow_rule=args.firstred_shadow,
        renko_mode=args.mode,
        dry_run=not args.live,
    )

    print("=" * 60)
    print("  RK RENKO V4 - BTCUSD (CRYPTO) BOT")
    print(f"  Symbol: BTCUSD | Magic: 777002 | Lot: {args.lot}")
    print(f"  Mode: {args.mode} | Execution: {'LIVE' if args.live else 'DRY RUN (Paper)'}")
    print(f"  Zones: {'DISABLED (Testing)' if args.no_zones else 'ENABLED'}")
    print("=" * 60)

    bot.run_live()


if __name__ == "__main__":
    main()
