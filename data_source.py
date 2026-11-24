"""
Data Source Manager for MT5, Hyperliquid, and yfinance.
Provides market data, symbol precision specifications, and MT5 order execution.
"""

import time
import datetime
import logging
import requests
from typing import Dict, List, Optional, Tuple, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("data_source")

# Try importing MetaTrader 5
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 python package not available.")

# Try importing yfinance
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance python package not available.")


class DataSourceManager:
    def __init__(self):
        self.mt5_initialized = False
        self.initialize_mt5()

    def initialize_mt5(self) -> bool:
        """Initializes connection to MT5 terminal if available."""
        if not MT5_AVAILABLE:
            return False

        if self.mt5_initialized:
            try:
                if mt5.terminal_info() is not None:
                    return True
            except Exception:
                pass
            self.mt5_initialized = False

        try:
            if mt5.initialize():
                logger.info("MetaTrader 5 initialized successfully.")
                self.mt5_initialized = True
                return True
            else:
                logger.error(f"mt5.initialize() failed. Error: {mt5.last_error()}")
                return False
        except Exception as e:
            logger.error(f"Exception initializing MT5: {e}")
            return False

    def test_mt5_connection(self) -> dict:
        """Tests the MT5 terminal connection and returns status and account summary."""
        if not MT5_AVAILABLE:
            return {
                "status": "error",
                "message": "MetaTrader5 Python library is not installed in the environment."
            }

        success = self.initialize_mt5()
        if not success:
            err = mt5.last_error()
            return {
                "status": "disconnected",
                "message": f"Could not connect to MT5 terminal. Ensure MT5 is running. Error: {err}"
            }

        try:
            info = mt5.terminal_info()
            version = mt5.version()
            account = mt5.account_info()
            if info is None:
                return {
                    "status": "disconnected",
                    "message": "Connected to MT5 library, but could not retrieve terminal info."
                }

            acc_dict = {}
            if account:
                acc_dict = {
                    "login": account.login,
                    "trade_mode": "Demo" if account.trade_mode == 0 else "Real",
                    "server": account.server,
                    "balance": account.balance,
                    "equity": account.equity,
                    "profit": account.profit,
                    "margin": account.margin,
                    "margin_free": account.margin_free,
                    "margin_level": account.margin_level,
                    "currency": account.currency,
                }

            return {
                "status": "connected",
                "message": "Successfully connected to MetaTrader 5 terminal!",
                "version": f"5.00 Build {version[1]} ({version[2]})",
                "company": info.company,
                "name": info.name,
                "connected": info.connected,
                "trade_allowed": info.trade_allowed,
                "account": acc_dict,
            }
        except Exception as e:
            return {"status": "error", "message": f"Error querying MT5: {e}"}

    def get_historical_candles(self, source: str, symbol: str, timeframe: str = "5m", limit: int = 300, before: Optional[int] = None) -> List[dict]:
        src = source.lower()
        if src == "mt5":
            return self._get_mt5_candles(symbol, timeframe, limit, before)
        elif src == "hyperliquid":
            return self._get_hyperliquid_candles(symbol, timeframe, limit, before)
        elif src == "yfinance":
            return self._get_yfinance_candles(symbol, timeframe, limit, before)
        return []

    def _get_mt5_candles(self, symbol: str, timeframe: str, limit: int, before: Optional[int]) -> List[dict]:
        if not self.initialize_mt5():
            return []

        mt5_tf_map = {
            "1m": mt5.TIMEFRAME_M1,
            "5m": mt5.TIMEFRAME_M5,
            "15m": mt5.TIMEFRAME_M15,
            "1h": mt5.TIMEFRAME_H1,
            "4h": mt5.TIMEFRAME_H4,
            "1d": mt5.TIMEFRAME_D1,
        }
        mt5_tf = mt5_tf_map.get(timeframe.lower(), mt5.TIMEFRAME_M5)

        try:
            mt5.symbol_select(symbol, True)
            if before is not None:
                dt_to = datetime.datetime.fromtimestamp(before, tz=datetime.timezone.utc)
                rates = mt5.copy_rates_from(symbol, mt5_tf, dt_to, limit)
            else:
                rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, limit)

            if rates is None or len(rates) == 0:
                logger.warning(f"No MT5 rates found for {symbol} on {timeframe}")
                return []

            candles = []
            for r in rates:
                candles.append({
                    "time": int(r["time"]),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["tick_volume"]),
                })
            candles.sort(key=lambda x: x["time"])
            return candles
        except Exception as e:
            logger.error(f"Error fetching MT5 candles: {e}")
            return []

    def _get_hyperliquid_candles(self, symbol: str, timeframe: str, limit: int, before: Optional[int]) -> List[dict]:
        url = "https://api.hyperliquid.xyz/info"
        headers = {"Content-Type": "application/json"}
        end_time = int(before * 1000) if before else int(time.time() * 1000)
        tf_mins = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}.get(timeframe, 5)
        start_time = end_time - (limit * tf_mins * 60 * 1000)

        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": symbol.upper(),
                "interval": timeframe,
                "startTime": start_time,
                "endTime": end_time,
            }
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code != 200:
                return []
            data = res.json()
            if not isinstance(data, list):
                return []
            candles = []
            for item in data:
                candles.append({
                    "time": int(item["t"]) // 1000,
                    "open": float(item["o"]),
                    "high": float(item["h"]),
                    "low": float(item["l"]),
                    "close": float(item["c"]),
                    "volume": float(item["v"]),
                })
            candles.sort(key=lambda x: x["time"])
            return candles[:limit]
        except Exception as e:
            logger.error(f"Hyperliquid candle error: {e}")
            return []

    def _get_yfinance_candles(self, symbol: str, timeframe: str, limit: int, before: Optional[int]) -> List[dict]:
        if not YFINANCE_AVAILABLE:
            return []
        yf_tf_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "60m", "4h": "60m", "1d": "1d"}
        interval = yf_tf_map.get(timeframe.lower(), "5m")
        period_map = {"1m": "5d", "5m": "1mo", "15m": "1mo", "1h": "3mo", "4h": "3mo", "1d": "1y"}
        period = period_map.get(timeframe.lower(), "1mo")

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                return []
            candles = []
            for ts, row in df.iterrows():
                t_sec = int(ts.timestamp())
                if before and t_sec >= before:
                    continue
                candles.append({
                    "time": t_sec,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row.get("Volume", 0)),
                })
            candles.sort(key=lambda x: x["time"])
            return candles[-limit:]
        except Exception as e:
            logger.error(f"yfinance candle error: {e}")
            return []

    def get_live_price(self, source: str, symbol: str) -> Optional[dict]:
        src = source.lower()
        if src == "mt5":
            if not self.initialize_mt5():
                return None
            mt5.symbol_select(symbol, True)
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                return {
                    "symbol": symbol,
                    "price": (tick.bid + tick.ask) / 2.0,
                    "bid": tick.bid,
                    "ask": tick.ask,
                    "time": int(tick.time),
                }
        elif src == "hyperliquid":
            url = "https://api.hyperliquid.xyz/info"
            payload = {"type": "allMids"}
            try:
                r = requests.post(url, json=payload, timeout=5)
                if r.status_code == 200:
                    mids = r.json()
                    c = symbol.upper()
                    if c in mids:
                        p = float(mids[c])
                        return {"symbol": symbol, "price": p, "bid": p, "ask": p, "time": int(time.time())}
            except Exception:
                pass
        return None

    def get_symbol_format(self, source: str, symbol: str) -> Tuple[int, float]:
        src = source.lower()
        if src == "mt5" and self.initialize_mt5():
            mt5.symbol_select(symbol, True)
            info = mt5.symbol_info(symbol)
            if info:
                digits = int(info.digits)
                point = float(info.point) if info.point and info.point > 0 else 1 / (10 ** digits)
                return digits, point
        if "JPY" in symbol.upper():
            return 3, 0.001
        if "XAU" in symbol.upper():
            return 2, 0.01
        if "BTC" in symbol.upper():
            return 2, 0.01
        return 5, 0.00001

    # ==========================================
    # Trading Endpoints & Order Management
    # ==========================================

    def _calc_order_profit(self, action: int, symbol: str, volume: float, price_open: float, target_price: float) -> Optional[float]:
        if not target_price or target_price <= 0:
            return None
        try:
            val = mt5.order_calc_profit(action, symbol, volume, price_open, target_price)
            if val is not None:
                return round(float(val), 2)
        except Exception:
            pass
        # Fallback calculation using tick_size & tick_value
        try:
            sinfo = mt5.symbol_info(symbol)
            if sinfo and sinfo.trade_tick_size and sinfo.trade_tick_size > 0:
                diff = (target_price - price_open) if action == mt5.ORDER_TYPE_BUY else (price_open - target_price)
                val = (diff / sinfo.trade_tick_size) * sinfo.trade_tick_value * volume
                return round(float(val), 2)
        except Exception:
            pass
        return None

    def get_active_orders(self, symbol: Optional[str] = None) -> dict:
        if not self.initialize_mt5():
            return {"positions": [], "orders": [], "error": "MT5 not initialized"}
        try:
            pos_list = []
            ord_list = []
            positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
            if positions:
                for p in positions:
                    pos_data = {
                        "ticket": p.ticket,
                        "symbol": p.symbol,
                        "type": "buy" if p.type == mt5.ORDER_TYPE_BUY else "sell",
                        "volume": p.volume,
                        "price_open": p.price_open,
                        "price_current": p.price_current,
                        "sl": p.sl,
                        "tp": p.tp,
                        "profit": p.profit,
                        "magic": p.magic,
                        "time": p.time,
                    }
                    action = p.type
                    try:
                        pv = mt5.order_calc_profit(action, p.symbol, p.volume, p.price_open, p.price_open + 1.0)
                        if pv is not None:
                            pos_data["point_value"] = float(pv)
                    except Exception:
                        pass
                    if p.tp and p.tp > 0:
                        tp_p = self._calc_order_profit(action, p.symbol, p.volume, p.price_open, p.tp)
                        if tp_p is not None:
                            pos_data["tp_profit"] = tp_p
                    if p.sl and p.sl > 0:
                        sl_p = self._calc_order_profit(action, p.symbol, p.volume, p.price_open, p.sl)
                        if sl_p is not None:
                            pos_data["sl_profit"] = sl_p
                    pos_list.append(pos_data)
            orders = mt5.orders_get(symbol=symbol) if symbol else mt5.orders_get()
            if orders:
                for o in orders:
                    type_str = "buy_limit" if o.type == mt5.ORDER_TYPE_BUY_LIMIT else (
                        "sell_limit" if o.type == mt5.ORDER_TYPE_SELL_LIMIT else (
                            "buy_stop" if o.type == mt5.ORDER_TYPE_BUY_STOP else "sell_stop"
                        )
                    )
                    order_action = mt5.ORDER_TYPE_BUY if "buy" in type_str else mt5.ORDER_TYPE_SELL
                    ord_data = {
                        "ticket": o.ticket,
                        "symbol": o.symbol,
                        "type": type_str,
                        "volume": o.volume_initial,
                        "price_open": o.price_open,
                        "price_current": o.price_current,
                        "sl": o.sl,
                        "tp": o.tp,
                        "magic": o.magic,
                        "time_setup": o.time_setup,
                    }
                    try:
                        pv = mt5.order_calc_profit(order_action, o.symbol, o.volume_initial, o.price_open, o.price_open + 1.0)
                        if pv is not None:
                            ord_data["point_value"] = float(pv)
                    except Exception:
                        pass
                    if o.tp and o.tp > 0:
                        tp_p = self._calc_order_profit(order_action, o.symbol, o.volume_initial, o.price_open, o.tp)
                        if tp_p is not None:
                            ord_data["tp_profit"] = tp_p
                    if o.sl and o.sl > 0:
                        sl_p = self._calc_order_profit(order_action, o.symbol, o.volume_initial, o.price_open, o.sl)
                        if sl_p is not None:
                            ord_data["sl_profit"] = sl_p
                    ord_list.append(ord_data)
            return {"positions": pos_list, "orders": ord_list}
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            return {"positions": [], "orders": [], "error": str(e)}

    def place_order(self, symbol: str, order_type_str: str, volume: float, price: Optional[float] = None, sl: Optional[float] = None, tp: Optional[float] = None) -> dict:
        if not self.initialize_mt5():
            return {"status": "error", "message": "MT5 not initialized"}

        mt5.symbol_select(symbol, True)
        order_type_map = {
            "buy_market": mt5.ORDER_TYPE_BUY,
            "sell_market": mt5.ORDER_TYPE_SELL,
            "buy_limit": mt5.ORDER_TYPE_BUY_LIMIT,
            "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT,
            "buy_stop": mt5.ORDER_TYPE_BUY_STOP,
            "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
        }
        mt5_order_type = order_type_map.get(order_type_str.lower())
        if mt5_order_type is None:
            return {"status": "error", "message": f"Invalid order type: {order_type_str}"}

        if mt5_order_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL]:
            action = mt5.TRADE_ACTION_DEAL
            if price is None or price == 0:
                tick = mt5.symbol_info_tick(symbol)
                price = tick.ask if mt5_order_type == mt5.ORDER_TYPE_BUY else tick.bid
        else:
            action = mt5.TRADE_ACTION_PENDING
            if price is None:
                return {"status": "error", "message": "Pending orders require price"}

        req = {
            "action": action,
            "symbol": symbol,
            "volume": float(volume),
            "type": mt5_order_type,
            "price": float(price),
            "deviation": 20,
            "magic": 234000,
            "comment": "Antigravity UI",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if sl is not None and float(sl) > 0:
            req["sl"] = float(sl)
        if tp is not None and float(tp) > 0:
            req["tp"] = float(tp)

        result = mt5.order_send(req)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"status": "error", "message": f"Order failed: {result.comment}", "retcode": result.retcode}
        return {"status": "success", "ticket": result.order, "message": "Order placed successfully"}

    def modify_order(self, ticket: int, is_position: bool = False, price: Optional[float] = None, sl: Optional[float] = None, tp: Optional[float] = None) -> dict:
        if not self.initialize_mt5():
            return {"status": "error", "message": "MT5 not initialized"}

        req = {
            "action": mt5.TRADE_ACTION_SLTP if is_position else mt5.TRADE_ACTION_MODIFY,
            "position" if is_position else "order": int(ticket),
        }
        if is_position:
            pos = mt5.positions_get(ticket=ticket)
            if pos and len(pos) > 0:
                p = pos[0]
                req["symbol"] = p.symbol
                req["sl"] = p.sl
                req["tp"] = p.tp
        else:
            ord_res = mt5.orders_get(ticket=ticket)
            if ord_res and len(ord_res) > 0:
                o = ord_res[0]
                req["price"] = o.price_open
                req["sl"] = o.sl
                req["tp"] = o.tp

        if not is_position and price is not None:
            req["price"] = float(price)
        if sl is not None:
            req["sl"] = float(sl)
        if tp is not None:
            req["tp"] = float(tp)

        result = mt5.order_send(req)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"status": "error", "message": f"Modify failed: {result.comment}", "retcode": result.retcode}
        return {"status": "success", "ticket": ticket, "message": "Modified successfully"}

    def cancel_order(self, ticket: int, is_position: bool = False, symbol: Optional[str] = None, volume: Optional[float] = None, order_type: Optional[str] = None) -> dict:
        if not self.initialize_mt5():
            return {"status": "error", "message": "MT5 not initialized"}

        ticket = int(ticket)
        if is_position:
            if not symbol or not volume or not order_type:
                return {"status": "error", "message": "Closing position requires symbol, volume, order_type"}
            tick = mt5.symbol_info_tick(symbol)
            close_type = mt5.ORDER_TYPE_SELL if order_type.lower() == "buy" else mt5.ORDER_TYPE_BUY
            price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),
                "type": close_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "Close from UI",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
        else:
            req = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": ticket,
            }

        result = mt5.order_send(req)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"status": "error", "message": f"Cancel failed: {result.comment}", "retcode": result.retcode}
        return {"status": "success", "ticket": ticket, "message": "Canceled successfully"}


data_source = DataSourceManager()
