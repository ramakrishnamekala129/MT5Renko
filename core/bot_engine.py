"""
RK Renko V4 - Unified Bot Engine
Orchestrates:
- Dynamic ATR-based brick size calculation with daily rollover
- Reference zone construction from IST candles (Shadow, IB, FirstRed, 12:30, 17:30)
- Ingestion of M1 candles or streaming ticks into Renko brick builder
- Indicator tracking (Supertrend, EMA 5/9, 1H EMA 50, AI Smart Renko)
- Multi-priority signal generation & 9-layer confluence filtering
- Exit management (Supertrend flip, bar_num +/-2 early reversal)
- Tick-level trailing stop with spread spike guard
- Position management & deal synchronization
Zero external folder dependencies.
"""

import time
import math
import logging
import datetime
from typing import Dict, List, Optional, Any
import pytz

from .renko import RenkoEngine, RenkoBrick
from .indicators import Indicators
from .zones import ReferenceZoneEngine, ZoneType, ZoneColor
from .filters import ConfluenceFilterStack
from .trailing import TrailingStopEngine, TrailingPositionState
from .execution import MT5ExecutionEngine

IST = pytz.timezone("Asia/Kolkata")
logger = logging.getLogger("RKRenko.Bot")


class RKRenkoBot:
    def __init__(
        self,
        symbol: str,
        magic: int,
        lot_size: float = 0.01,
        session_hours: int = 22,
        atr_period: int = 5,
        atr_divisor: int = 22,
        fixed_brick_size: Optional[float] = None,
        sl_bricks: float = 5.0,
        tp_r: float = 0.0,
        trail_bricks: float = 4.0,
        trail_act: float = 4.0,
        zone_streak_bricks: int = 3,
        min_trend_bricks: int = 2,
        max_daily_trades: int = 12,
        max_trades_per_zone: int = 4,
        no_trailing_stop: bool = False,
        no_early_exit: bool = False,
        no_zones: bool = False,
        no_zone_only: bool = False,
        no_h1_ema50: bool = False,
        no_renko_ema: bool = False,
        firstred_shadow_rule: bool = False,
        renko_mode: str = "1m",
        dry_run: bool = True,
        zone_trade_toggles: Optional[Dict[str, bool]] = None,
        zone_display_toggles: Optional[Dict[str, bool]] = None,
    ):
        self.symbol = symbol
        self.magic = magic
        self.lot_size = lot_size
        self.session_hours = session_hours
        self.atr_period = atr_period
        self.atr_divisor = atr_divisor
        self.fixed_brick_size = fixed_brick_size

        self.sl_bricks = sl_bricks
        self.tp_r = tp_r
        self.trail_bricks = trail_bricks
        self.trail_act = trail_act
        self.zone_streak_bricks = zone_streak_bricks
        self.min_trend_bricks = min_trend_bricks

        self.no_trailing_stop = no_trailing_stop
        self.no_early_exit = no_early_exit
        self.no_zones = no_zones
        self.zone_only_trades = (not no_zone_only) and (not no_zones)
        self.no_h1_ema50 = no_h1_ema50
        self.no_renko_ema = no_renko_ema
        self.firstred_shadow_rule = firstred_shadow_rule
        self.renko_mode = renko_mode
        self.dry_run = dry_run

        # Initialize Core Engines
        initial_brick = self.calculate_atr_brick_size()
        self.renko = RenkoEngine(brick_size=initial_brick)
        self.indicators = Indicators()
        self.zones = ReferenceZoneEngine(
            zone_trade_toggles=zone_trade_toggles,
            zone_display_toggles=zone_display_toggles,
        )
        self.filters = ConfluenceFilterStack(
            max_daily_trades=max_daily_trades,
            max_trades_per_zone=max_trades_per_zone,
            zone_streak_bricks=zone_streak_bricks,
            use_renko_ema=not no_renko_ema,
            use_h1_ema50=not no_h1_ema50,
            firstred_shadow_rule=firstred_shadow_rule,
            no_zones=no_zones,
        )
        self.trailing = TrailingStopEngine(
            brick_size=initial_brick,
            trail_act_bricks=trail_act,
            trail_distance_bricks=trail_bricks,
            enabled=not no_trailing_stop,
        )
        self.execution = MT5ExecutionEngine(
            symbol=self.symbol,
            magic=self.magic,
            lot_size=self.lot_size,
            dry_run=self.dry_run,
        )

        # Runtime Tracking
        self.current_trading_date: Optional[datetime.date] = None
        self.open_position_state: Optional[TrailingPositionState] = None
        self._last_processed_m1_time: Optional[datetime.datetime] = None
        self.is_running: bool = False

    def calculate_atr_brick_size(self) -> float:
        """
        Calculates dynamic brick size: ATR(atr_period) / atr_divisor
        using 22-hour (or 23-hour for BTC) session-split bars aggregated from M30 candles.
        Falls back to D1 candles, and lastly to safe symbol defaults.
        """
        if self.fixed_brick_size and self.fixed_brick_size > 0:
            return self.fixed_brick_size

        default_map = {
            "XAUUSD": 2.05,
            "BTCUSD": 500.0,
            "EURUSD": 0.0015,
            "GBPUSD": 0.0018,
            "USDJPY": 0.20,
            "AUDUSD": 0.0012,
            "EURJPY": 0.22,
        }

        try:
            import MetaTrader5 as mt5
            if mt5.initialize():
                # 1. Primary Method: Continuous alternating sequence (22H, 2H, 22H, 2H...) from H1 bars
                rates_h1 = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_H1, 0, 500)
                if rates_h1 is not None and len(rates_h1) > 0:
                    from collections import defaultdict
                    by_day: Dict[datetime.date, Dict[int, Any]] = defaultdict(dict)
                    for r in rates_h1:
                        dt = datetime.datetime.fromtimestamp(r["time"], tz=datetime.timezone.utc)
                        by_day[dt.date()][dt.hour] = r

                    bars_seq = []
                    for day in sorted(by_day.keys()):
                        hours = by_day[day]
                        sorted_h = sorted(hours.keys())
                        if len(sorted_h) >= 22:
                            # 22H Main Candle (0..21 for FX, 1..22 for Gold)
                            h22_rates = [hours[h] for h in sorted_h[:22]]
                            h22_h = max(float(r["high"]) for r in h22_rates)
                            h22_l = min(float(r["low"]) for r in h22_rates)
                            h22_c = float(h22_rates[-1]["close"])
                            bars_seq.append({
                                "high": h22_h,
                                "low": h22_l,
                                "close": h22_c,
                                "range": h22_h - h22_l,
                            })

                            # Remaining Candle (2H for FX, 1H for Gold)
                            rem_keys = sorted_h[22:]
                            if rem_keys:
                                rem_rates = [hours[h] for h in rem_keys]
                                rem_h = max(float(r["high"]) for r in rem_rates)
                                rem_l = min(float(r["low"]) for r in rem_rates)
                                rem_c = float(rem_rates[-1]["close"])
                                bars_seq.append({
                                    "high": rem_h,
                                    "low": rem_l,
                                    "close": rem_c,
                                    "range": rem_h - rem_l,
                                })

                    if len(bars_seq) >= self.atr_period + 1:
                        tr_list = []
                        for i in range(1, len(bars_seq)):
                            h = bars_seq[i]["high"]
                            l = bars_seq[i]["low"]
                            prev_c = bars_seq[i - 1]["close"]
                            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
                            tr_list.append(tr)

                        # Wilder's RMA over atr_period across continuous sequence
                        atr = sum(tr_list[:self.atr_period]) / self.atr_period
                        for tr in tr_list[self.atr_period:]:
                            atr = (atr * (self.atr_period - 1) + tr) / self.atr_period

                        brick = round(atr / self.atr_divisor, 6)
                        if brick > 0:
                            logger.info(
                                f"[{self.symbol}] Dynamic Continuous (22H/2H) Brick Size: {brick:.6f} "
                                f"(ATR({self.atr_period})={atr:.5f}, Divisor={self.atr_divisor})"
                            )
                            return brick

                # 2. Secondary Fallback: Standard Daily (D1) bars
                rates_d1 = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_D1, 0, 15)
                if rates_d1 is not None and len(rates_d1) >= self.atr_period + 1:
                    tr_list = []
                    for i in range(1, len(rates_d1)):
                        h = rates_d1[i]["high"]
                        l = rates_d1[i]["low"]
                        prev_c = rates_d1[i - 1]["close"]
                        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
                        tr_list.append(tr)

                    atr = sum(tr_list[:self.atr_period]) / self.atr_period
                    for tr in tr_list[self.atr_period:]:
                        atr = (atr * (self.atr_period - 1) + tr) / self.atr_period

                    brick = round(atr / self.atr_divisor, 6)
                    if brick > 0:
                        logger.info(
                            f"[{self.symbol}] Dynamic D1 Brick Size (Fallback): {brick:.6f} "
                            f"(ATR={atr:.5f}, Divisor={self.atr_divisor})"
                        )
                        return brick
        except Exception as e:
            logger.warning(f"[{self.symbol}] Error calculating 22H ATR brick size: {e}")

        # 3. Final Fallback: Symbol default map
        fallback = default_map.get(self.symbol, 0.0015)
        logger.info(f"[{self.symbol}] Using default fallback brick size: {fallback}")
        return fallback

    def check_daily_rollover(self, current_time: datetime.datetime):
        """Detects day rollover and updates zones, brick size, and counters."""
        ist_now = current_time.astimezone(IST)
        today = ist_now.date()

        if self.current_trading_date is None or today != self.current_trading_date:
            logger.info(f"[{self.symbol}] Daily Rollover detected. Date: {today}")
            self.current_trading_date = today

            # 1. Update brick size
            new_brick = self.calculate_atr_brick_size()
            self.renko.reset(brick_size=new_brick)
            self.trailing.brick_size = new_brick

            # 2. Reset daily zones and counters
            self.zones.reset_daily_zones()
            self.filters.reset_daily_counters()

            # 3. Sync deal count from MT5 history
            historical_trades = self.execution.sync_daily_trades_from_history(today)
            self.filters.daily_trade_count = historical_trades
            logger.info(f"[{self.symbol}] Synchronized historical daily trades: {historical_trades}")

            # 4. Construct Reference Zones from historical data
            self.build_reference_zones(ist_now)

    def build_reference_zones(self, ist_now: datetime.datetime):
        """Constructs reference zones (Shadow, IB, FirstRed, 12:30, 5:30) for current day."""
        if self.no_zones:
            logger.info(f"[{self.symbol}] Zones disabled for testing. Skipping reference zone construction.")
            return

        if not self.execution.connected or self.dry_run:
            # Setup sample baseline reference zones for dry-run simulation
            ref_price = 2650.0 if "XAU" in self.symbol else (70000.0 if "BTC" in self.symbol else 1.0800)
            self.zones.set_zone(ZoneType.SHADOW, ref_price + 5.0, ref_price - 5.0, ZoneColor.NEUTRAL)
            self.zones.set_zone(ZoneType.FIRST_RED, ref_price + 3.0, ref_price - 1.0, ZoneColor.GREEN)
            return

        try:
            import MetaTrader5 as mt5
            # Fetch M30 candles covering yesterday and today
            rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M30, 0, 100)
            if rates is None or len(rates) == 0:
                return

            first_red_found = False

            for bar in rates:
                bar_dt_utc = datetime.datetime.fromtimestamp(bar["time"], tz=datetime.timezone.utc)
                bar_dt_ist = bar_dt_utc.astimezone(IST)

                # Shadow Zone: Yesterday 03:30–05:30 IST
                if bar_dt_ist.date() == (self.current_trading_date - datetime.timedelta(days=1)):
                    if (bar_dt_ist.hour == 3 and bar_dt_ist.minute >= 30) or bar_dt_ist.hour in [4, 5]:
                        curr_shadow = self.zones.zones[ZoneType.SHADOW]
                        new_h = max(bar["high"], curr_shadow.high if curr_shadow else bar["high"])
                        new_l = min(bar["low"], curr_shadow.low if curr_shadow else bar["low"])
                        self.zones.set_zone(ZoneType.SHADOW, new_h, new_l, ZoneColor.NEUTRAL)

                # Today's Zones
                elif bar_dt_ist.date() == self.current_trading_date:
                    # IB Zone: Today ~03:30 IST candle
                    if bar_dt_ist.hour == 3 and bar_dt_ist.minute == 30:
                        self.zones.set_zone(ZoneType.IB, bar["high"], bar["low"], ZoneColor.NEUTRAL)

                    # FirstRed Zone: First red 30m candle before 12:30 IST
                    if not first_red_found and (bar_dt_ist.hour < 12 or (bar_dt_ist.hour == 12 and bar_dt_ist.minute < 30)):
                        if bar["close"] < bar["open"]:
                            self.zones.set_zone(ZoneType.FIRST_RED, bar["high"], bar["low"])
                            first_red_found = True

                    # 12:30PM Zone: 12:30–13:00 IST candle
                    if bar_dt_ist.hour == 12 and bar_dt_ist.minute == 30:
                        color = ZoneColor.GREEN if bar["close"] >= bar["open"] else ZoneColor.RED
                        self.zones.set_zone(ZoneType.C1230, bar["high"], bar["low"], color)

                    # 5:30PM Zone: 17:30–18:00 IST candle
                    if bar_dt_ist.hour == 17 and bar_dt_ist.minute == 30:
                        color = ZoneColor.GREEN if bar["close"] >= bar["open"] else ZoneColor.RED
                        self.zones.set_zone(ZoneType.C1730, bar["high"], bar["low"], color)

        except Exception as e:
            logger.error(f"Error building reference zones: {e}")

    def get_h1_ema50(self) -> Optional[float]:
        """Fetches H1 closes and computes cached 50-period EMA."""
        if self.no_h1_ema50 or not self.execution.connected or self.dry_run:
            return None

        now = datetime.datetime.now()
        h1_cache = self.indicators.h1_ema50
        if h1_cache.cached_ema and h1_cache.last_fetch_time:
            if (now - h1_cache.last_fetch_time).total_seconds() < h1_cache.cache_ttl:
                return h1_cache.cached_ema

        try:
            import MetaTrader5 as mt5
            rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_H1, 0, 70)
            if rates is not None and len(rates) >= 50:
                closes = [r["close"] for r in rates]
                ema_val = h1_cache.calculate_from_closes(closes)
                h1_cache.cached_ema = ema_val
                h1_cache.last_fetch_time = now
                return ema_val
        except Exception as e:
            logger.warning(f"Failed to fetch H1 EMA50: {e}")

        return None

    def on_new_renko_brick(self, brick: RenkoBrick):
        """Handles completed Renko brick: evaluates indicators, exits, and entry confluence."""
        # 1. Update Indicators
        ind_data = self.indicators.on_new_brick(brick)
        st_dir = ind_data["st_direction"]
        ema5 = ind_data["ema5"]
        ema9 = ind_data["ema9"]
        bar_num = brick.bar_num
        h1_ema50 = self.get_h1_ema50()

        logger.info(
            f"[{self.symbol}] Brick #{brick.index} | Close: {brick.close:.5f} | "
            f"BarNum: {bar_num} | ST: {'BULL' if st_dir == 1 else 'BEAR'} | "
            f"EMA5: {ema5:.5f} | EMA9: {ema9:.5f}"
        )

        # 2. Check Open Position Exits
        open_positions = self.execution.get_open_positions()
        if open_positions:
            pos = open_positions[0]
            pos_type = pos["type"]
            ticket = pos["ticket"]

            # Exit Priority 1: Supertrend Flip Exit
            if (pos_type == "BUY" and st_dir == -1) or (pos_type == "SELL" and st_dir == 1):
                logger.info(f"[{self.symbol}] EXIT: Supertrend flipped against open {pos_type} position.")
                self.execution.close_position(ticket, reason="Supertrend_Flip")
                self.open_position_state = None
                return

            # Exit Priority 2: Early Reversal Exit (bar_num <= -2 for BUY, >= +2 for SELL)
            if not self.no_early_exit:
                if (pos_type == "BUY" and bar_num <= -2) or (pos_type == "SELL" and bar_num >= 2):
                    logger.info(f"[{self.symbol}] EXIT: Early Reversal hit (bar_num={bar_num}) against {pos_type}.")
                    self.execution.close_position(ticket, reason="Early_Reversal")
                    self.open_position_state = None
                    return

            # Position is still active, no new entry allowed (Hedge prevention)
            return

        # 3. Priority 0 Check: INSIDE any active zone corridor?
        if not self.no_zones:
            is_inside, inside_zone = self.zones.is_price_inside_any_active_zone(brick.close)
            if is_inside and inside_zone:
                logger.debug(f"[{self.symbol}] HOLD: Price inside {inside_zone.zone_type.value} 0.44–0.56 chop corridor.")
                return

        # 4. Generate Candidate Signals
        candidate_signals = []
        if not self.no_zones:
            # Zone signals (Priority 2)
            zone_signals = self.zones.evaluate_brick_signals(
                brick_close=brick.close,
                brick_dir=brick.direction,
                st_dir=st_dir,
                is_reversal_brick=brick.is_reversal,
            )
            for sig_type, zone, direction in zone_signals:
                candidate_signals.append((direction, zone, f"Zone_{sig_type}"))

        # Mid-air / Free-space entry if zone_only_trades == False
        if not self.zone_only_trades and not candidate_signals:
            if abs(bar_num) >= self.min_trend_bricks:
                if st_dir == 1:
                    candidate_signals.append(("BUY", None, "MidAir_Supertrend"))
                elif st_dir == -1:
                    candidate_signals.append(("SELL", None, "MidAir_Supertrend"))

        # 5. Validate Signals Against 9-Layer Confluence Stack
        ai_status = self.indicators.ai_renko.status
        ai_dir = self.indicators.ai_renko.direction

        for direction, zone, source in candidate_signals:
            passed, reason = self.filters.validate_signal(
                direction=direction,
                zone=zone,
                price=brick.close,
                bar_num=bar_num,
                st_dir=st_dir,
                ema5=ema5,
                ema9=ema9,
                h1_ema50=h1_ema50,
                ai_renko_status=ai_status,
                ai_renko_dir=ai_dir,
                zone_engine=self.zones,
            )

            if passed:
                logger.info(f"[{self.symbol}] ★ CONFLUENCE CONFIRMED ★ ({source}) -> Executing {direction}")
                # Calculate SL & TP
                sl_distance = self.sl_bricks * self.renko.brick_size
                sl_price = (brick.close - sl_distance) if direction == "BUY" else (brick.close + sl_distance)
                tp_price = 0.0
                if self.tp_r > 0:
                    tp_price = (brick.close + (self.tp_r * sl_distance)) if direction == "BUY" else (brick.close - (self.tp_r * sl_distance))

                ticket = self.execution.open_position(direction=direction, sl_price=sl_price, tp_price=tp_price)
                if ticket:
                    zone_name = zone.zone_type.value if zone else None
                    self.filters.record_trade(zone_name=zone_name)
                    self.open_position_state = TrailingPositionState(
                        ticket=ticket,
                        symbol=self.symbol,
                        direction=direction,
                        open_price=brick.close,
                        current_sl=sl_price,
                    )
                break
            else:
                logger.info(f"[{self.symbol}] Signal {direction} rejected: {reason}")

    def on_tick(self, bid: float, ask: float, timestamp: datetime.datetime):
        """Tick event: updates trailing stop engine and feeds Renko if in tick mode."""
        self.check_daily_rollover(timestamp)

        # Tick-level Trailing Stop Engine
        if self.open_position_state:
            should_mod, new_sl, reason = self.trailing.evaluate_tick(
                pos_state=self.open_position_state,
                bid=bid,
                ask=ask,
            )
            if should_mod and new_sl:
                success = self.execution.modify_sl(self.open_position_state.ticket, new_sl)
                if success:
                    logger.info(f"[{self.symbol}] {reason}")
                    self.open_position_state.current_sl = new_sl

        # If in tick mode, feed each tick to Renko
        if self.renko_mode == "tick":
            mid_price = (bid + ask) / 2.0
            new_bricks = self.renko.process_price(mid_price, timestamp)
            for brick in new_bricks:
                self.on_new_renko_brick(brick)

    def process_m1_bar(self, open_: float, high: float, low: float, close: float, timestamp: datetime.datetime):
        """Processes completed M1 candle: updates AI Renko and feeds Renko in 1m mode."""
        self.check_daily_rollover(timestamp)

        # Update AI Smart Renko engine with M1 bar
        self.indicators.ai_renko.update_m1_bar(open_, high, low, close)

        # In 1m mode, completed candle close builds Renko bricks
        if self.renko_mode == "1m":
            new_bricks = self.renko.process_price(close, timestamp)
            for brick in new_bricks:
                self.on_new_renko_brick(brick)

    def run_live(self):
        """Main live loop fetching MT5 data and managing the bot execution."""
        if not self.execution.acquire_instance_lock():
            logger.error(f"Cannot start {self.symbol} bot. Another instance is already running.")
            return

        try:
            if not self.execution.connect():
                logger.error(f"Failed to connect to MT5 for symbol {self.symbol}.")
                return

            self.is_running = True
            logger.info(f"[{self.symbol}] RK Renko V4 Bot started. Mode: {self.renko_mode}, DryRun: {self.dry_run}")

            # Baseline ATR brick sizing
            initial_brick = self.calculate_atr_brick_size()
            self.renko.reset(brick_size=initial_brick)
            self.trailing.brick_size = initial_brick

            while self.is_running:
                now_utc = datetime.datetime.now(datetime.timezone.utc)

                # Fetch and handle current quote
                bid, ask = self.execution.get_market_quote()
                if bid > 0 and ask > 0:
                    self.on_tick(bid, ask, now_utc)

                # Fetch latest completed M1 candle
                if not self.dry_run and self.execution.connected:
                    import MetaTrader5 as mt5
                    rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M1, 1, 1)
                    if rates is not None and len(rates) > 0:
                        bar = rates[0]
                        bar_time = datetime.datetime.fromtimestamp(bar["time"], tz=datetime.timezone.utc)
                        if self._last_processed_m1_time is None or bar_time > self._last_processed_m1_time:
                            self.process_m1_bar(bar["open"], bar["high"], bar["low"], bar["close"], bar_time)
                            self._last_processed_m1_time = bar_time

                time.sleep(0.5 if self.renko_mode == "tick" else 1.0)

        except KeyboardInterrupt:
            logger.info(f"[{self.symbol}] Bot interrupted by user.")
        finally:
            self.is_running = False
            self.execution.release_instance_lock()
            logger.info(f"[{self.symbol}] Bot shut down and lock released.")

    def stop(self):
        """Signals the bot loop to stop cleanly."""
        self.is_running = False

    def update_parameters(self, params: dict):
        """Dynamically applies updated parameters to the live bot instance."""
        if "lot_size" in params:
            self.lot_size = float(params["lot_size"])
            self.execution.lot_size = self.lot_size
        if "dry_run" in params:
            self.dry_run = bool(params["dry_run"])
            self.execution.dry_run = self.dry_run
        if "sl_bricks" in params:
            self.sl_bricks = float(params["sl_bricks"])
        if "tp_r" in params:
            self.tp_r = float(params["tp_r"])
        if "trail_bricks" in params:
            self.trail_bricks = float(params["trail_bricks"])
            self.trailing.trail_distance_bricks = self.trail_bricks
        if "trail_act" in params:
            self.trail_act = float(params["trail_act"])
            self.trailing.trail_act_bricks = self.trail_act
        if "no_trailing_stop" in params:
            self.no_trailing_stop = bool(params["no_trailing_stop"])
            self.trailing.enabled = not self.no_trailing_stop
        if "no_early_exit" in params:
            self.no_early_exit = bool(params["no_early_exit"])
        if "no_zones" in params:
            self.no_zones = bool(params["no_zones"])
            self.filters.no_zones = self.no_zones
            self.zone_only_trades = (not getattr(self, "no_zone_only", False)) and (not self.no_zones)
        if "no_zone_only" in params:
            self.no_zone_only = bool(params["no_zone_only"])
            self.zone_only_trades = (not self.no_zone_only) and (not self.no_zones)
        if "zone_only_trades" in params:
            self.zone_only_trades = bool(params["zone_only_trades"]) and (not self.no_zones)
        if "no_h1_ema50" in params:
            self.no_h1_ema50 = bool(params["no_h1_ema50"])
            self.filters.use_h1_ema50 = not self.no_h1_ema50
        if "no_renko_ema" in params:
            self.no_renko_ema = bool(params["no_renko_ema"])
            self.filters.use_renko_ema = not self.no_renko_ema
        if "firstred_shadow_rule" in params:
            self.firstred_shadow_rule = bool(params["firstred_shadow_rule"])
            self.filters.firstred_shadow_rule = self.firstred_shadow_rule
        if "renko_mode" in params and params["renko_mode"] in ["1m", "tick"]:
            self.renko_mode = params["renko_mode"]
        if "max_daily_trades" in params:
            self.max_daily_trades = int(params["max_daily_trades"])
            self.filters.max_daily_trades = self.max_daily_trades
        if "max_trades_per_zone" in params:
            self.max_trades_per_zone = int(params["max_trades_per_zone"])
            self.filters.max_trades_per_zone = self.max_trades_per_zone
        if "zone_streak_bricks" in params:
            self.zone_streak_bricks = int(params["zone_streak_bricks"])
            self.filters.zone_streak_bricks = self.zone_streak_bricks
        if "min_trend_bricks" in params:
            self.min_trend_bricks = int(params["min_trend_bricks"])
        recalc_brick = False
        if "atr_period" in params:
            self.atr_period = int(params["atr_period"])
            recalc_brick = True
        if "atr_divisor" in params:
            self.atr_divisor = int(params["atr_divisor"])
            recalc_brick = True

        if "fixed_brick_size" in params:
            fbs = params["fixed_brick_size"]
            self.fixed_brick_size = float(fbs) if fbs and float(fbs) > 0 else None
            recalc_brick = True

        if recalc_brick:
            new_brick = self.calculate_atr_brick_size()
            self.renko.reset(brick_size=new_brick)
            self.trailing.brick_size = new_brick

        if "zone_trade_toggles" in params and isinstance(params["zone_trade_toggles"], dict):
            for k, v in params["zone_trade_toggles"].items():
                self.zones.set_trade_toggle(k, bool(v))

        if "zone_display_toggles" in params and isinstance(params["zone_display_toggles"], dict):
            for k, v in params["zone_display_toggles"].items():
                self.zones.set_display_toggle(k, bool(v))

        logger.info(f"[{self.symbol}] Parameters updated: {params}")

    def get_telemetry(self) -> dict:
        """Returns real-time telemetry snapshot of the bot."""
        st_dir = self.indicators.supertrend.direction
        st_text = "BULL" if st_dir == 1 else ("BEAR" if st_dir == -1 else "NEUTRAL")
        
        open_pos = None
        if self.execution.connected:
            positions = self.execution.get_open_positions()
            if positions:
                p = positions[0]
                open_pos = {
                    "ticket": p["ticket"],
                    "type": p["type"],
                    "volume": p["volume"],
                    "open_price": p["open_price"],
                    "current_price": p.get("current_price", p["open_price"]),
                    "sl": p["sl"],
                    "tp": p["tp"],
                    "profit": p["profit"],
                }

        zones_data = {}
        for z_type, z in self.zones.zones.items():
            if z:
                zones_data[z_type.value] = {
                    "high": z.high,
                    "low": z.low,
                    "fib_044": z.fib_044,
                    "fib_056": z.fib_056,
                    "color": z.color.value if hasattr(z.color, "value") else str(z.color),
                    "trade_enabled": self.zones.trade_toggles.get(z_type, True),
                    "display_enabled": self.zones.display_toggles.get(z_type, True),
                }

        return {
            "symbol": self.symbol,
            "magic": self.magic,
            "is_running": self.is_running,
            "dry_run": self.dry_run,
            "renko_mode": self.renko_mode,
            "lot_size": self.lot_size,
            "brick_size": self.renko.brick_size,
            "fixed_brick_size": self.fixed_brick_size,
            "bar_num": self.renko.bar_num,
            "direction": self.renko.current_direction,
            "supertrend": {
                "direction": st_dir,
                "label": st_text,
                "value": self.indicators.supertrend.value,
            },
            "ema5": self.indicators.ema5.value,
            "ema9": self.indicators.ema9.value,
            "h1_ema50": self.indicators.h1_ema50.cached_ema,
            "daily_trades": self.filters.daily_trade_count,
            "max_daily_trades": self.filters.max_daily_trades,
            "open_position": open_pos,
            "zones": zones_data,
            "config": {
                "lot_size": self.lot_size,
                "sl_bricks": self.sl_bricks,
                "tp_r": self.tp_r,
                "trail_bricks": self.trail_bricks,
                "trail_act": self.trail_act,
                "no_trailing_stop": self.no_trailing_stop,
                "no_early_exit": self.no_early_exit,
                "no_zones": self.no_zones,
                "no_zone_only": getattr(self, "no_zone_only", True),
                "zone_only_trades": self.zone_only_trades,
                "no_h1_ema50": self.no_h1_ema50,
                "no_renko_ema": self.no_renko_ema,
                "firstred_shadow_rule": self.firstred_shadow_rule,
                "fixed_brick_size": self.fixed_brick_size,
                "atr_period": self.atr_period,
                "atr_divisor": self.atr_divisor,
                "session_hours": self.session_hours,
                "max_daily_trades": self.filters.max_daily_trades,
                "max_trades_per_zone": self.filters.max_trades_per_zone,
                "zone_streak_bricks": self.filters.zone_streak_bricks,
                "min_trend_bricks": self.min_trend_bricks,
            }
        }
