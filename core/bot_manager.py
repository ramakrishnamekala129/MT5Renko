"""
RK Renko V4 - Multi-Bot Manager & Live Telemetry Orchestrator
Handles:
- Thread-safe execution of multiple RKRenkoBot instances simultaneously
- Start, stop, panic close across individual or all symbols
- Dynamic parameter adjustments (SL, TP, trailing, zones, confluence filters, brick sizing)
- In-memory circular log buffer with subscriber queue for real-time SSE streaming
- Renko historical and live brick generation with Supertrend and Reference Zones for charts
"""

import os
import sys
import time
import queue
import logging
import datetime
import threading
from typing import Dict, List, Optional, Any, Generator

# Ensure workspace root is on sys.path
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from core.bot_engine import RKRenkoBot
from core.renko import RenkoEngine, RenkoBrick
from core.indicators import Supertrend, RenkoEMA

logger = logging.getLogger("RKRenko.Manager")


# ==============================================================================
# In-Memory Circular Log Buffer & Custom Logging Handler
# ==============================================================================

class LogRecordItem:
    def __init__(self, record_id: int, timestamp: str, level: str, name: str, message: str, symbol: Optional[str] = None):
        self.id = record_id
        self.timestamp = timestamp
        self.level = level
        self.name = name
        self.message = message
        self.symbol = symbol
        # Detect trade execution related messages (avoid matching generic network messages like 'forcibly closed')
        msg_upper = message.upper()
        if name and name.startswith("asyncio"):
            self.is_trade = False
        else:
            self.is_trade = any(term in msg_upper for term in [
                "★ CONFLUENCE", "ENTRY", "EXIT", "ORDER", "POSITION", "DEAL",
                "MODIFY_SL", "CLOSE_POSITION", "POSITION CLOSED", "ORDER CLOSED", "EXECUTED"
            ])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "level": self.level,
            "name": self.name,
            "message": self.message,
            "symbol": self.symbol,
            "is_trade": self.is_trade,
        }


class InMemoryLogRingBuffer:
    def __init__(self, max_size: int = 2000):
        self.max_size = max_size
        self.buffer: List[LogRecordItem] = []
        self.lock = threading.RLock()
        self.counter = 0
        self.subscribers: List[queue.Queue] = []

    def add(self, level: str, name: str, message: str, symbol: Optional[str] = None):
        with self.lock:
            self.counter += 1
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            item = LogRecordItem(
                record_id=self.counter,
                timestamp=now_str,
                level=level,
                name=name,
                message=message,
                symbol=symbol,
            )
            self.buffer.append(item)
            if len(self.buffer) > self.max_size:
                self.buffer.pop(0)

            # Broadcast to active SSE subscribers
            item_dict = item.to_dict()
            dead_subs = []
            for q in self.subscribers:
                try:
                    q.put_nowait(item_dict)
                except queue.Full:
                    dead_subs.append(q)
            for d in dead_subs:
                if d in self.subscribers:
                    self.subscribers.remove(d)

    def get_logs(self, since_id: int = 0, symbol: Optional[str] = None, level: Optional[str] = None, limit: int = 200) -> List[dict]:
        with self.lock:
            results = []
            for item in reversed(self.buffer):
                if item.id <= since_id:
                    continue
                if symbol and symbol.upper() != "ALL":
                    if not item.symbol or item.symbol.upper() != symbol.upper():
                        continue
                if level and level.upper() != "ALL":
                    if level.upper() == "TRADES":
                        if not item.is_trade:
                            continue
                    elif item.level.upper() != level.upper():
                        continue

                results.append(item.to_dict())
                if len(results) >= limit:
                    break
            results.reverse()
            return results

    def subscribe(self) -> queue.Queue:
        q = queue.Queue(maxsize=500)
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)


class RingBufferLogHandler(logging.Handler):
    """Custom logging handler that intercepts all records and puts them in the ring buffer."""
    def __init__(self, ring_buffer: InMemoryLogRingBuffer):
        super().__init__()
        self.ring_buffer = ring_buffer

    def emit(self, record):
        try:
            if (
                record.name.startswith("uvicorn")
                or record.name.startswith("asyncio")
                or "GET /api/" in record.getMessage()
                or "HTTP/1.1" in record.getMessage()
            ):
                return
            msg = self.format(record)
            # Try to deduce symbol from logger name or message (e.g. [GBPUSD])
            symbol = None
            known_symbols = ["GBPUSD", "EURUSD", "XAUUSD", "BTCUSD", "USDJPY", "AUDUSD", "EURJPY"]
            for s in known_symbols:
                if f"[{s}]" in msg or f"[{s}]" in record.name:
                    symbol = s
                    break
            self.ring_buffer.add(
                level=record.levelname,
                name=record.name,
                message=msg,
                symbol=symbol,
            )
        except Exception:
            self.handleError(record)


# Global Log Buffer Singleton
log_ring_buffer = InMemoryLogRingBuffer(max_size=2500)
log_handler = RingBufferLogHandler(log_ring_buffer)
log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"))
logging.getLogger().addHandler(log_handler)
logging.getLogger().setLevel(logging.INFO)


# ==============================================================================
# Bot Configurations & Bot Manager
# ==============================================================================

DEFAULT_BOT_CONFIGS = {
    "GBPUSD": {
        "symbol": "GBPUSD", "magic": 777004, "session_hours": 22,
        "atr_period": 5, "atr_divisor": 22, "lot_size": 0.01, "sl_bricks": 5.0,
        "tp_r": 0.0, "trail_bricks": 4.0, "trail_act": 4.0,
        "zone_streak_bricks": 3, "min_trend_bricks": 2, "max_daily_trades": 12, "max_trades_per_zone": 4,
        "no_zones": True, "no_zone_only": True, "firstred_shadow_rule": False, "renko_mode": "1m", "dry_run": True,
    },
    "EURUSD": {
        "symbol": "EURUSD", "magic": 777003, "session_hours": 22,
        "atr_period": 5, "atr_divisor": 22, "lot_size": 0.01, "sl_bricks": 5.0,
        "tp_r": 0.0, "trail_bricks": 4.0, "trail_act": 4.0,
        "zone_streak_bricks": 3, "min_trend_bricks": 2, "max_daily_trades": 12, "max_trades_per_zone": 4,
        "no_zones": True, "no_zone_only": True, "firstred_shadow_rule": False, "renko_mode": "1m", "dry_run": True,
    },
    "XAUUSD": {
        "symbol": "XAUUSD", "magic": 777001, "session_hours": 22,
        "atr_period": 5, "atr_divisor": 22, "lot_size": 0.01, "sl_bricks": 5.0,
        "tp_r": 0.0, "trail_bricks": 4.0, "trail_act": 4.0,
        "zone_streak_bricks": 3, "min_trend_bricks": 2, "max_daily_trades": 12, "max_trades_per_zone": 4,
        "no_zones": True, "no_zone_only": True, "firstred_shadow_rule": False, "renko_mode": "1m", "dry_run": True,
    },
    "BTCUSD": {
        "symbol": "BTCUSD", "magic": 777002, "session_hours": 23,
        "atr_period": 7, "atr_divisor": 23, "lot_size": 0.01, "sl_bricks": 5.0,
        "tp_r": 0.0, "trail_bricks": 4.0, "trail_act": 4.0,
        "zone_streak_bricks": 3, "min_trend_bricks": 2, "max_daily_trades": 12, "max_trades_per_zone": 4,
        "no_zones": True, "no_zone_only": True, "firstred_shadow_rule": False, "renko_mode": "1m", "dry_run": True,
    },
    "USDJPY": {
        "symbol": "USDJPY", "magic": 777005, "session_hours": 22,
        "atr_period": 5, "atr_divisor": 22, "lot_size": 0.01, "sl_bricks": 5.0,
        "tp_r": 0.0, "trail_bricks": 4.0, "trail_act": 4.0,
        "zone_streak_bricks": 3, "min_trend_bricks": 2, "max_daily_trades": 12, "max_trades_per_zone": 4,
        "no_zones": True, "no_zone_only": True, "firstred_shadow_rule": False, "renko_mode": "1m", "dry_run": True,
    },
    "AUDUSD": {
        "symbol": "AUDUSD", "magic": 777006, "session_hours": 22,
        "atr_period": 5, "atr_divisor": 22, "lot_size": 0.01, "sl_bricks": 5.0,
        "tp_r": 0.0, "trail_bricks": 4.0, "trail_act": 4.0,
        "zone_streak_bricks": 3, "min_trend_bricks": 2, "max_daily_trades": 12, "max_trades_per_zone": 4,
        "no_zones": True, "no_zone_only": True, "firstred_shadow_rule": False, "renko_mode": "1m", "dry_run": True,
    },
    "EURJPY": {
        "symbol": "EURJPY", "magic": 777007, "session_hours": 22,
        "atr_period": 5, "atr_divisor": 22, "lot_size": 0.01, "sl_bricks": 5.0,
        "tp_r": 0.0, "trail_bricks": 4.0, "trail_act": 4.0,
        "zone_streak_bricks": 3, "min_trend_bricks": 2, "max_daily_trades": 12, "max_trades_per_zone": 4,
        "no_zones": True, "no_zone_only": True, "firstred_shadow_rule": False, "renko_mode": "1m", "dry_run": True,
    },
}


class BotManager:
    """Thread-safe orchestrator managing multi-symbol RKRenkoBot instances."""

    def __init__(self):
        self.lock = threading.RLock()
        self.bots: Dict[str, RKRenkoBot] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.configs: Dict[str, dict] = dict(DEFAULT_BOT_CONFIGS)
        self._init_default_bots()

    def _init_default_bots(self):
        """Pre-instantiate bots for configured symbols."""
        for sym, cfg in self.configs.items():
            self._create_bot_instance(sym, cfg)

    def _create_bot_instance(self, symbol: str, cfg: dict) -> RKRenkoBot:
        bot = RKRenkoBot(
            symbol=symbol,
            magic=cfg.get("magic", 777000 + len(self.bots) + 1),
            lot_size=cfg.get("lot_size", 0.01),
            session_hours=cfg.get("session_hours", 22),
            atr_period=cfg.get("atr_period", 5),
            atr_divisor=cfg.get("atr_divisor", 22),
            fixed_brick_size=cfg.get("fixed_brick_size"),
            sl_bricks=cfg.get("sl_bricks", 5.0),
            tp_r=cfg.get("tp_r", 0.0),
            trail_bricks=cfg.get("trail_bricks", 4.0),
            trail_act=cfg.get("trail_act", 4.0),
            zone_streak_bricks=cfg.get("zone_streak_bricks", 3),
            min_trend_bricks=cfg.get("min_trend_bricks", 2),
            max_daily_trades=cfg.get("max_daily_trades", 12),
            max_trades_per_zone=cfg.get("max_trades_per_zone", 4),
            no_trailing_stop=cfg.get("no_trailing_stop", False),
            no_early_exit=cfg.get("no_early_exit", False),
            no_zones=cfg.get("no_zones", True),
            no_zone_only=cfg.get("no_zone_only", True),
            no_h1_ema50=cfg.get("no_h1_ema50", False),
            no_renko_ema=cfg.get("no_renko_ema", False),
            firstred_shadow_rule=cfg.get("firstred_shadow_rule", False),
            renko_mode=cfg.get("renko_mode", "1m"),
            dry_run=cfg.get("dry_run", True),
        )
        self.bots[symbol] = bot
        return bot

    def get_or_create_bot(self, symbol: str) -> RKRenkoBot:
        sym = symbol.upper()
        with self.lock:
            if sym not in self.bots:
                cfg = self.configs.get(sym, {
                    "symbol": sym,
                    "magic": 777000 + len(self.bots) + 1,
                    "lot_size": 0.01,
                    "session_hours": 22,
                    "atr_period": 5,
                    "atr_divisor": 22,
                    "sl_bricks": 5.0,
                    "tp_r": 0.0,
                    "trail_bricks": 4.0,
                    "trail_act": 4.0,
                    "zone_streak_bricks": 3,
                    "min_trend_bricks": 2,
                    "max_daily_trades": 12,
                    "max_trades_per_zone": 4,
                    "no_zones": True,
                    "no_zone_only": True,
                    "renko_mode": "1m",
                    "dry_run": True,
                })
                self.configs[sym] = cfg
                return self._create_bot_instance(sym, cfg)
            return self.bots[sym]

    def start_bot(self, symbol: str, live: bool = False, mode: str = "1m") -> dict:
        """Starts a bot thread for the specified symbol."""
        sym = symbol.upper()
        bot = self.get_or_create_bot(sym)

        with self.lock:
            if bot.is_running:
                return {"status": "ok", "message": f"{sym} bot is already running."}

            bot.dry_run = not live
            bot.execution.dry_run = not live
            bot.renko_mode = mode

            t = threading.Thread(target=bot.run_live, name=f"BotThread-{sym}", daemon=True)
            self.threads[sym] = t
            t.start()
            logger.info(f"[{sym}] Bot launched in background thread. Mode: {mode}, Live: {live}")
            return {"status": "success", "message": f"{sym} bot started successfully in {'LIVE' if live else 'PAPER'} mode."}

    def stop_bot(self, symbol: str) -> dict:
        """Stops the bot running for the specified symbol."""
        sym = symbol.upper()
        with self.lock:
            if sym not in self.bots:
                return {"status": "error", "message": f"No bot found for symbol {sym}"}
            bot = self.bots[sym]
            bot.stop()
            logger.info(f"[{sym}] Bot stop signal sent.")
            return {"status": "success", "message": f"{sym} bot stop signaled."}

    def start_all(self, live: bool = False, mode: str = "1m") -> dict:
        """Starts all configured bots."""
        results = {}
        for sym in list(self.configs.keys()):
            results[sym] = self.start_bot(sym, live=live, mode=mode)
        return {"status": "success", "results": results}

    def stop_all(self) -> dict:
        """Stops all running bots."""
        results = {}
        for sym in list(self.bots.keys()):
            results[sym] = self.stop_bot(sym)
        return {"status": "success", "results": results}

    def emergency_close_all(self) -> dict:
        """Closes all open positions across all bots."""
        logger.warning("EMERGENCY CLOSE ALL triggered across all symbols!")
        closed_count = 0
        details = []
        with self.lock:
            for sym, bot in self.bots.items():
                if bot.execution.connected:
                    positions = bot.execution.get_open_positions()
                    for pos in positions:
                        ticket = pos["ticket"]
                        res = bot.execution.close_position(ticket, reason="EMERGENCY_PANIC_CLOSE")
                        if res:
                            closed_count += 1
                            details.append(f"Closed {sym} pos #{ticket}")
        return {"status": "success", "closed_count": closed_count, "details": details}

    def get_status(self, symbol: Optional[str] = None) -> Any:
        """Retrieves live telemetry snapshot for symbol or all symbols."""
        if symbol and symbol.upper() != "ALL":
            bot = self.get_or_create_bot(symbol.upper())
            return bot.get_telemetry()

        # All symbols
        telemetry = {}
        with self.lock:
            for sym, bot in self.bots.items():
                telemetry[sym] = bot.get_telemetry()
        return telemetry

    def get_config(self, symbol: str) -> dict:
        sym = symbol.upper()
        bot = self.get_or_create_bot(sym)
        return bot.get_telemetry()["config"]

    def update_config(self, symbol: str, params: dict) -> dict:
        """Updates parameters for a single symbol or ALL symbols."""
        sym = symbol.upper()
        with self.lock:
            target_symbols = list(self.bots.keys()) if sym == "ALL" else [sym]
            for s in target_symbols:
                bot = self.get_or_create_bot(s)
                bot.update_parameters(params)
                # Store in config cache
                if s in self.configs:
                    self.configs[s].update(params)
        return {"status": "success", "message": f"Updated parameters for {sym}", "params": params}

    def get_renko_chart_data(
        self,
        symbol: str,
        mode: str = "1m",
        brick_size: Optional[float] = None,
        limit: int = 300,
        timeline_mode: str = "equidistant",
    ) -> dict:
        """
        Builds Renko bricks, Supertrend, EMA 5/9, and Reference Zones from historical data.
        Returns ready-to-render series for Lightweight Charts.
        """
        sym = symbol.upper()
        bot = self.get_or_create_bot(sym)

        # 1. Determine Brick Size
        effective_brick = brick_size
        if effective_brick is None or effective_brick <= 0:
            effective_brick = bot.calculate_atr_brick_size()

        renko_engine = RenkoEngine(brick_size=effective_brick)
        supertrend_calc = Supertrend(length=1, multiplier=3.1)
        ema5_calc = RenkoEMA(period=5)
        ema9_calc = RenkoEMA(period=9)

        # 2. Fetch Historical M1 or M5 Data
        rates = None
        try:
            import MetaTrader5 as mt5
            if mt5.initialize():
                tf = mt5.TIMEFRAME_M1 if mode == "1m" else mt5.TIMEFRAME_M5
                # Fetch up to 1500 bars to build sufficient Renko history
                rates = mt5.copy_rates_from_pos(sym, tf, 0, 1500)
        except Exception as e:
            logger.warning(f"MT5 historical rates fetch failed for Renko: {e}")

        # If rates unavailable, generate clean synthetic Renko data for offline/test mode
        if rates is None or len(rates) == 0:
            base_price = 2650.0 if "XAU" in sym else (70000.0 if "BTC" in sym else (145.0 if "JPY" in sym else 1.2500))
            now = datetime.datetime.now()
            prices = []
            curr = base_price
            import math
            for i in range(500):
                curr += math.sin(i / 10.0) * effective_brick * 0.8 + (0.1 if i % 2 == 0 else -0.1) * effective_brick
                t = now - datetime.timedelta(minutes=500 - i)
                prices.append((curr, t))

            renko_engine.initialize_from_price(prices[0][0], prices[0][1])
            for p, t in prices:
                renko_engine.process_price(p, t)
        else:
            # Process real MT5 bars
            t0 = datetime.datetime.fromtimestamp(rates[0]["time"], tz=datetime.timezone.utc)
            renko_engine.initialize_from_price(rates[0]["close"], t0)
            for bar in rates:
                bar_time = datetime.datetime.fromtimestamp(bar["time"], tz=datetime.timezone.utc)
                # In 1m mode, close builds bricks
                renko_engine.process_price(bar["close"], bar_time)

        all_bricks = renko_engine.bricks
        # Limit to the most recent bricks requested
        visible_bricks = all_bricks[-limit:] if len(all_bricks) > limit else all_bricks

        # 3. Format bricks with timeline
        chart_bricks = []
        st_series = []
        ema5_series = []
        ema9_series = []

        # Baseline timestamp for equidistant spacing (1 minute interval per brick)
        base_epoch = int(time.time()) - (len(visible_bricks) * 60)
        last_time = 0

        for idx, brick in enumerate(visible_bricks):
            # Calculate indicators on brick close
            st_dir, st_line = supertrend_calc.update(brick)
            e5 = ema5_calc.update(brick.close)
            e9 = ema9_calc.update(brick.close)

            # Timeline assignment
            if timeline_mode == "equidistant":
                brick_time = base_epoch + (idx * 60)
            else:
                # Real timestamp with microsecond deduplication
                ts = int(brick.timestamp.timestamp())
                brick_time = ts if ts > last_time else last_time + 1
            last_time = brick_time

            real_time_str = brick.timestamp.strftime("%Y-%m-%d %H:%M:%S")

            chart_bricks.append({
                "time": brick_time,
                "real_time": real_time_str,
                "brick_index": brick.index,
                "open": brick.open,
                "high": brick.high,
                "low": brick.low,
                "close": brick.close,
                "direction": brick.direction,
                "bar_num": brick.bar_num,
                "is_reversal": brick.is_reversal,
            })

            if supertrend_calc.value is not None:
                st_series.append({
                    "time": brick_time,
                    "value": round(supertrend_calc.value, 5),
                    "direction": st_dir,
                })
            if e5 is not None:
                ema5_series.append({
                    "time": brick_time,
                    "value": round(e5, 5),
                })
            if e9 is not None:
                ema9_series.append({
                    "time": brick_time,
                    "value": round(e9, 5),
                })

        # Reference Zones snapshot
        zones_data = {}
        for z_type, z in bot.zones.zones.items():
            if z:
                zones_data[z_type.value] = {
                    "high": z.high,
                    "low": z.low,
                    "fib_044": z.fib_044,
                    "fib_056": z.fib_056,
                    "color": z.color.value if hasattr(z.color, "value") else str(z.color),
                }

        return {
            "symbol": sym,
            "brick_size": effective_brick,
            "total_bricks": len(all_bricks),
            "timeline_mode": timeline_mode,
            "bricks": chart_bricks,
            "supertrend": st_series,
            "ema5": ema5_series,
            "ema9": ema9_series,
            "zones": zones_data,
        }


# Global Bot Manager Singleton
bot_manager = BotManager()
