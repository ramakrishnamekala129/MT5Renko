"""
RK Renko V4 - MT5 Execution Engine
Handles:
- MT5 Terminal connection & validation
- Single-instance PID process locking
- Magic number position isolation
- Hedge prevention (strictly one directional position at a time)
- Order placement, SL/TP modification, and position closure
- Deal history trade count synchronization
Zero external folder dependencies.
"""

import os
import sys
import logging
from typing import List, Optional, Tuple
import datetime

logger = logging.getLogger("RKRenko.Execution")


class MT5ExecutionEngine:
    def __init__(
        self,
        symbol: str,
        magic: int,
        lot_size: float = 0.01,
        dry_run: bool = False,
    ):
        self.symbol = symbol
        self.magic = magic
        self.lot_size = lot_size
        self.dry_run = dry_run
        self.connected = False
        self.point = 0.00001
        self.digits = 5
        self.min_lot = 0.01
        self.max_lot = 100.0
        self.lot_step = 0.01

        self._pid_lock_file = f"bot_{self.symbol}_{self.magic}.pid"

    def acquire_instance_lock(self) -> bool:
        """Acquires a PID lock to prevent duplicate bot instances for same symbol/magic."""
        pid = os.getpid()
        if os.path.exists(self._pid_lock_file):
            try:
                with open(self._pid_lock_file, "r") as f:
                    existing_pid = int(f.read().strip())
                # Check if process is still running
                if os.name == "nt":
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, existing_pid)
                    if existing_pid != pid and handle != 0:
                        kernel32.CloseHandle(handle)
                        logger.error(f"Duplicate bot instance detected! PID {existing_pid} is still running.")
                        return False
                    elif handle != 0:
                        kernel32.CloseHandle(handle)
            except Exception:
                pass  # Stale lock file, safe to overwrite

        with open(self._pid_lock_file, "w") as f:
            f.write(str(pid))
        return True

    def release_instance_lock(self):
        """Releases the PID lock file on shutdown."""
        if os.path.exists(self._pid_lock_file):
            try:
                os.remove(self._pid_lock_file)
            except Exception:
                pass

    def connect(self) -> bool:
        """Initializes connection to MT5 terminal and loads symbol properties."""
        if self.dry_run:
            logger.info(f"[{self.symbol}] DRY RUN mode enabled. Virtual execution active.")
            self.connected = True
            return True

        try:
            import MetaTrader5 as mt5
            if not mt5.initialize():
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False

            if not mt5.symbol_select(self.symbol, True):
                logger.error(f"Failed to select symbol {self.symbol}: {mt5.last_error()}")
                return False

            info = mt5.symbol_info(self.symbol)
            if info is None:
                logger.error(f"Symbol {self.symbol} not found in MT5.")
                return False

            self.point = info.point
            self.digits = info.digits
            self.min_lot = info.volume_min
            self.max_lot = info.volume_max
            self.lot_step = info.volume_step
            self.connected = True
            logger.info(f"Connected to MT5. Symbol: {self.symbol}, Digits: {self.digits}, Point: {self.point}")
            return True
        except ImportError:
            logger.warning("MetaTrader5 package not importable. Running in fallback simulation mode.")
            self.dry_run = True
            self.connected = True
            return True

    def get_open_positions(self) -> List[dict]:
        """Returns open positions matching this bot's symbol and magic number."""
        if self.dry_run or not self.connected:
            return []

        import MetaTrader5 as mt5
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return []

        bot_positions = []
        for pos in positions:
            if pos.magic == self.magic:
                bot_positions.append({
                    "ticket": pos.ticket,
                    "symbol": pos.symbol,
                    "type": "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                    "volume": pos.volume,
                    "price_open": pos.price_open,
                    "sl": pos.sl,
                    "tp": pos.tp,
                    "profit": pos.profit,
                })
        return bot_positions

    def get_market_quote(self) -> Tuple[float, float]:
        """Returns current (bid, ask) prices."""
        if self.dry_run or not self.connected:
            return 0.0, 0.0

        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return 0.0, 0.0
        return tick.bid, tick.ask

    def sync_daily_trades_from_history(self, start_date: datetime.date) -> int:
        """Counts closed deals for this magic number since start of current trading day."""
        if self.dry_run or not self.connected:
            return 0

        import MetaTrader5 as mt5
        start_dt = datetime.datetime.combine(start_date, datetime.time.min)
        end_dt = datetime.datetime.now()

        deals = mt5.history_deals_get(start_dt, end_dt, group=f"*{self.symbol}*")
        if deals is None:
            return 0

        trade_count = sum(1 for d in deals if d.magic == self.magic and d.entry == mt5.DEAL_ENTRY_IN)
        return trade_count

    def open_position(
        self,
        direction: str,  # 'BUY' or 'SELL'
        sl_price: float,
        tp_price: float = 0.0,
    ) -> Optional[int]:
        """
        Executes a market order with hedge prevention and magic number isolation.
        """
        # Hedge Prevention: verify no opposing position is open
        open_positions = self.get_open_positions()
        opposing = "SELL" if direction == "BUY" else "BUY"
        if any(p["type"] == opposing for p in open_positions):
            logger.warning(f"Hedge prevented! Opposing {opposing} position currently active.")
            return None

        if self.dry_run:
            logger.info(f"[SIMULATION] OPEN {direction} {self.lot_size} lots at market | SL: {sl_price:.5f} | TP: {tp_price:.5f}")
            return 999999

        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            logger.error("Failed to get current market quote for order entry.")
            return None

        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick.ask if direction == "BUY" else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": float(self.lot_size),
            "type": order_type,
            "price": price,
            "sl": float(round(sl_price, self.digits)) if sl_price > 0 else 0.0,
            "tp": float(round(tp_price, self.digits)) if tp_price > 0 else 0.0,
            "deviation": 20,
            "magic": self.magic,
            "comment": "RK_Renko_V4",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            retcode = result.retcode if result else "None"
            comment = result.comment if result else mt5.last_error()
            logger.error(f"Order send failed! Retcode: {retcode}, Comment: {comment}")
            return None

        logger.info(f"Position opened successfully! Ticket: {result.order}, Direction: {direction}, Price: {price}")
        return result.order

    def modify_sl(self, ticket: int, new_sl: float) -> bool:
        """Modifies Stop Loss level for an open position."""
        if self.dry_run:
            logger.info(f"[SIMULATION] Modify SL for Ticket {ticket} -> {new_sl:.5f}")
            return True

        import MetaTrader5 as mt5
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False

        pos = positions[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": self.symbol,
            "sl": float(round(new_sl, self.digits)),
            "tp": pos.tp,
        }
        res = mt5.order_send(request)
        return res is not None and res.retcode == mt5.TRADE_RETCODE_DONE

    def close_position(self, ticket: int, reason: str = "Signal") -> bool:
        """Closes an open position at market."""
        if self.dry_run:
            logger.info(f"[SIMULATION] CLOSE Ticket {ticket} | Reason: {reason}")
            return True

        import MetaTrader5 as mt5
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False

        pos = positions[0]
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return False

        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": self.symbol,
            "volume": pos.volume,
            "type": close_type,
            "price": price,
            "deviation": 20,
            "magic": self.magic,
            "comment": f"Close: {reason}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(request)
        if res is not None and res.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Closed ticket {ticket} ({reason}) at {price}")
            return True
        return False
