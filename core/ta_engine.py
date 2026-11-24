"""
RK Renko V4 - Dedicated pandas_ta Indicator Engine
Provides:
- Dynamic pandas_ta indicator catalog introspection across all 9 categories
- Parameter extraction, type inference, bounds, and defaults
- Placement classification: overlay vs oscillator
- OHLCV DataFrame preparation with ordered pd.DatetimeIndex for market candles and Renko bricks
- Dynamic indicator computation, timestamp alignment, and JSON sanitization (NaN/Inf -> None)
- Warm-up period and insufficient bar resilience (clean warning responses, no crashes)
"""

import inspect
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import pandas_ta as ta

logger = logging.getLogger("ta_engine")

# Input parameter names used by pandas_ta functions
INPUT_PARAM_NAMES = {"open_", "open", "high", "low", "close", "volume"}

# Internal / non-user configurable parameters to omit from metadata params
SKIP_PARAM_NAMES = {"kwargs", "talib", "offset"}

# Indicators classified as Overlays (rendered directly on main price chart)
OVERLAY_INDICATORS = {
    "bbands", "kc", "accbands", "donchian", "chandelier_exit", "aberration", "hwc",
    "supertrend", "alphatrend", "amat", "psar", "zigzag", "ht_trendline",
    "vwap", "vwma", "ha"
}

# Standard TradingView / chart palette for line colors
PALETTE = [
    "#2962FF", "#EF5350", "#26A69A", "#FF9800", "#7E57C2",
    "#AB47BC", "#26C6DA", "#FFA726", "#8D6E63", "#EC407A"
]

# Standard category presentation order
CATEGORIES_ORDER = [
    "momentum", "overlap", "trend", "volatility", "volume",
    "statistics", "candle", "cycle", "performance"
]

# Curated metadata overrides for core high-frequency indicators to match PROJECT.md contracts
CURATED_INDICATORS = {
    "rsi": {
        "name": "Relative Strength Index",
        "description": "Momentum oscillator measuring speed and change of price movements",
        "inputs": ["close"],
        "params": [
            {"name": "length", "type": "int", "default": 14, "min": 1, "max": 200, "step": 1},
            {"name": "scalar", "type": "float", "default": 100.0}
        ],
        "outputs": [{"name": "RSI_14", "type": "line", "color": "#7E57C2"}]
    },
    "bbands": {
        "name": "Bollinger Bands",
        "description": "Volatility bands placed above and below a moving average",
        "inputs": ["close"],
        "params": [
            {"name": "length", "type": "int", "default": 20, "min": 1, "max": 200, "step": 1},
            {"name": "std", "type": "float", "default": 2.0, "min": 0.1, "max": 10.0, "step": 0.1}
        ],
        "outputs": [
            {"name": "upper", "type": "line", "color": "#26A69A"},
            {"name": "middle", "type": "line", "color": "#FF9800"},
            {"name": "lower", "type": "line", "color": "#EF5350"}
        ]
    },
    "macd": {
        "name": "Moving Average Convergence Divergence",
        "description": "Trend-following momentum indicator showing relationship between two moving averages",
        "inputs": ["close"],
        "params": [
            {"name": "fast", "type": "int", "default": 12, "min": 1, "max": 100, "step": 1},
            {"name": "slow", "type": "int", "default": 26, "min": 1, "max": 200, "step": 1},
            {"name": "signal", "type": "int", "default": 9, "min": 1, "max": 50, "step": 1}
        ],
        "outputs": [
            {"name": "macd", "type": "line", "color": "#2962FF"},
            {"name": "signal", "type": "line", "color": "#FF9800"},
            {"name": "histogram", "type": "histogram", "color": "#26A69A"}
        ]
    },
    "stoch": {
        "name": "Stochastic Oscillator",
        "description": "Momentum indicator comparing a closing price to a range of prices over a period",
        "inputs": ["high", "low", "close"],
        "params": [
            {"name": "k", "type": "int", "default": 14, "min": 1, "max": 100, "step": 1},
            {"name": "d", "type": "int", "default": 3, "min": 1, "max": 50, "step": 1},
            {"name": "smooth_k", "type": "int", "default": 3, "min": 1, "max": 50, "step": 1}
        ],
        "outputs": [
            {"name": "k", "type": "line", "color": "#2962FF"},
            {"name": "d", "type": "line", "color": "#FF9800"}
        ]
    },
    "sma": {
        "name": "Simple Moving Average",
        "description": "Calculates the average of a selected range of prices",
        "inputs": ["close"],
        "params": [
            {"name": "length", "type": "int", "default": 10, "min": 1, "max": 500, "step": 1}
        ],
        "outputs": [{"name": "SMA_10", "type": "line", "color": "#2962FF"}]
    },
    "ema": {
        "name": "Exponential Moving Average",
        "description": "Moving average that places greater weight on the most recent data points",
        "inputs": ["close"],
        "params": [
            {"name": "length", "type": "int", "default": 10, "min": 1, "max": 500, "step": 1}
        ],
        "outputs": [{"name": "EMA_10", "type": "line", "color": "#26A69A"}]
    },
    "atr": {
        "name": "Average True Range",
        "description": "Volatility indicator showing how much an asset moves on average during a given time frame",
        "inputs": ["high", "low", "close"],
        "params": [
            {"name": "length", "type": "int", "default": 14, "min": 1, "max": 200, "step": 1}
        ],
        "outputs": [{"name": "ATRr_14", "type": "line", "color": "#AB47BC"}]
    },
    "adx": {
        "name": "Average Directional Movement Index",
        "description": "Quantifies trend strength without regard to trend direction",
        "inputs": ["high", "low", "close"],
        "params": [
            {"name": "length", "type": "int", "default": 14, "min": 1, "max": 200, "step": 1}
        ],
        "outputs": [
            {"name": "adx", "type": "line", "color": "#7E57C2"},
            {"name": "dmp", "type": "line", "color": "#26A69A"},
            {"name": "dmn", "type": "line", "color": "#EF5350"}
        ]
    },
    "obv": {
        "name": "On-Balance Volume",
        "description": "Momentum indicator using volume flow to predict changes in stock price",
        "inputs": ["close", "volume"],
        "params": [],
        "outputs": [{"name": "OBV", "type": "line", "color": "#2962FF"}]
    },
    "vwap": {
        "name": "Volume Weighted Average Price",
        "description": "Benchmark representing average price traded throughout the day based on volume and price",
        "inputs": ["high", "low", "close", "volume"],
        "params": [
            {"name": "anchor", "type": "str", "default": "D"}
        ],
        "outputs": [{"name": "VWAP_D", "type": "line", "color": "#FF9800"}]
    },
    "supertrend": {
        "name": "Supertrend",
        "description": "Trend following indicator plotting a line above or below price based on ATR",
        "inputs": ["high", "low", "close"],
        "params": [
            {"name": "length", "type": "int", "default": 7, "min": 1, "max": 100, "step": 1},
            {"name": "multiplier", "type": "float", "default": 3.0, "min": 0.1, "max": 20.0, "step": 0.1}
        ],
        "outputs": [
            {"name": "supertrend", "type": "line", "color": "#26A69A"},
            {"name": "direction", "type": "line", "color": "#7E57C2"}
        ]
    }
}


def _build_catalog() -> Dict[str, Any]:
    """Dynamically inspects pandas_ta to build the full indicator catalog across all categories."""
    indicators_dict: Dict[str, Any] = {}

    for cat in CATEGORIES_ORDER:
        ind_names = ta.Category.get(cat, [])
        for ind in ind_names:
            if not hasattr(ta, ind):
                continue
            fn = getattr(ta, ind)
            doc = fn.__doc__ or ""
            sig = inspect.signature(fn)

            # Indicator placement classification
            kind = "overlay" if (cat == "overlap" or ind in OVERLAY_INDICATORS) else "oscillator"

            # Detect required input columns
            inputs: List[str] = []
            for p in sig.parameters.values():
                if p.name in INPUT_PARAM_NAMES:
                    cname = "open" if p.name == "open_" else p.name
                    if cname not in inputs:
                        inputs.append(cname)
            if not inputs:
                inputs = ["close"]

            # Docstring introspection: title and description
            doc_lines = [l.strip() for l in doc.split("\n") if l.strip()]
            title = doc_lines[0] if doc_lines else ind.upper()
            if any(title.lower().startswith(x) for x in ("sources:", "parameters:", "returns:", "note:", "tip:")):
                title = ind.upper()

            desc = ""
            for l in doc_lines[1:]:
                if any(l.startswith(x) for x in ("Sources:", "Parameters:", "Returns:", "Other Parameters:", "Warning:", "Tip:", "Note:")):
                    break
                desc += (" " + l) if desc else l
            if not desc:
                desc = f"{title} indicator calculation."

            # Parse parameter defaults and types from docstring
            doc_params: Dict[str, Dict[str, Any]] = {}
            for l in doc.split("\n"):
                l = l.strip()
                m = re.match(r"(\w+)\s*\(([^)]+)\):\s*(.*)", l)
                if m:
                    pname, ptype, pdesc = m.groups()
                    def_m = re.search(r"Default:\s*(.+)", pdesc)
                    d_str = None
                    if def_m:
                        d_str = def_m.group(1).replace("```", "").replace("`", "").strip(' \t\r\n."\'')
                    doc_params[pname] = {"type": ptype.strip(), "default": d_str}

            # Parameter list construction
            params: List[Dict[str, Any]] = []
            for p in sig.parameters.values():
                if p.name in INPUT_PARAM_NAMES or p.name in SKIP_PARAM_NAMES:
                    continue
                p_info = doc_params.get(p.name, {})
                raw_t = p_info.get("type", "")
                raw_d = p_info.get("default")

                p_type = "str"
                p_def = None
                if "int" in raw_t.lower() and "float" not in raw_t.lower():
                    p_type = "int"
                    if raw_d:
                        try:
                            p_def = int(raw_d)
                        except Exception:
                            p_def = None
                elif any(x in raw_t.lower() for x in ("float", "number", "intfloat")):
                    p_type = "float"
                    if raw_d:
                        try:
                            p_def = float(raw_d)
                        except Exception:
                            p_def = None
                elif "bool" in raw_t.lower():
                    p_type = "bool"
                    if raw_d:
                        p_def = raw_d.lower() in ("true", "1")
                else:
                    p_def = raw_d

                if p_def is None and p.default is not inspect.Parameter.empty and p.default is not None:
                    p_def = p.default
                    p_type = type(p.default).__name__

                param_entry = {"name": p.name, "type": p_type, "default": p_def}
                if p_type == "int":
                    param_entry["min"] = 1
                    param_entry["max"] = 500
                    param_entry["step"] = 1
                elif p_type == "float":
                    param_entry["min"] = 0.01
                    param_entry["max"] = 100.0
                    param_entry["step"] = 0.1
                params.append(param_entry)

            # Default generic output
            outputs = [{"name": ind.upper(), "type": "line", "color": PALETTE[0]}]

            # Apply curated overrides if available
            if ind in CURATED_INDICATORS:
                curated = CURATED_INDICATORS[ind]
                title = curated.get("name", title)
                desc = curated.get("description", desc)
                inputs = curated.get("inputs", inputs)
                params = curated.get("params", params)
                outputs = curated.get("outputs", outputs)

            indicators_dict[ind] = {
                "id": ind,
                "name": title,
                "category": cat,
                "kind": kind,
                "description": desc,
                "inputs": inputs,
                "params": params,
                "outputs": outputs,
            }

    return {
        "categories": CATEGORIES_ORDER,
        "indicators": indicators_dict,
    }


# Singleton cached catalog
_GLOBAL_CATALOG = _build_catalog()


def get_indicator_catalog() -> Dict[str, Any]:
    """Returns the full indicator catalog grouped by category."""
    return _GLOBAL_CATALOG


def get_indicator_info(indicator_id: str) -> Optional[Dict[str, Any]]:
    """Returns metadata for a specific indicator or None if unknown."""
    if not indicator_id:
        return None
    return _GLOBAL_CATALOG["indicators"].get(indicator_id.lower().strip())


def prepare_dataframe(candles_or_bricks: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, List[int]]:
    """
    Converts candlestick or Renko brick objects into a pandas DataFrame
    with required columns (open, high, low, close, volume) and strictly ordered pd.DatetimeIndex.
    """
    if not candles_or_bricks:
        return pd.DataFrame(), []

    bar_times: List[int] = []
    opens: List[float] = []
    highs: List[float] = []
    lows: List[float] = []
    closes: List[float] = []
    volumes: List[float] = []

    for item in candles_or_bricks:
        t = int(item.get("time", 0))
        raw_c = item.get("close")
        c = float(raw_c) if (raw_c is not None and not pd.isna(raw_c)) else np.nan

        raw_o = item.get("open")
        o = float(raw_o) if (raw_o is not None and not pd.isna(raw_o)) else c

        raw_h = item.get("high")
        if raw_h is not None and not pd.isna(raw_h):
            h = float(raw_h)
        else:
            h = max(o, c) if (not pd.isna(o) and not pd.isna(c)) else np.nan

        raw_l = item.get("low")
        if raw_l is not None and not pd.isna(raw_l):
            l = float(raw_l)
        else:
            l = min(o, c) if (not pd.isna(o) and not pd.isna(c)) else np.nan

        raw_v = item.get("volume")
        v = float(raw_v) if (raw_v is not None and not pd.isna(raw_v)) else 1.0

        bar_times.append(t)
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        volumes.append(v)

    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )

    # Construct DatetimeIndex required by intraday indicators (e.g. VWAP)
    max_t = max(bar_times) if bar_times else 0
    unit = "ms" if max_t > 1e11 else "s"
    dt_index = pd.to_datetime(bar_times, unit=unit, utc=True)

    # Ensure strictly monotonic increasing index for VWAP & time-anchored metrics
    if not dt_index.is_monotonic_increasing:
        base_t = dt_index[0] if len(dt_index) > 0 else pd.Timestamp.now(tz="UTC")
        dt_index = base_t + pd.to_timedelta(np.arange(len(bar_times)), unit="min")

    df.index = dt_index
    return df, bar_times


def prepare_renko_dataframe(renko_params: Dict[str, Any]) -> Tuple[pd.DataFrame, List[int]]:
    """
    Generates Renko bricks via bot_manager and converts into an indicator-ready DataFrame.
    """
    from core.bot_manager import bot_manager

    symbol = renko_params.get("symbol", "GBPUSD")
    mode = renko_params.get("mode", "1m")
    brick_size = renko_params.get("brick_size")
    limit = int(renko_params.get("limit", 300))
    timeline_mode = renko_params.get("timeline_mode", "equidistant")

    renko_data = bot_manager.get_renko_chart_data(
        symbol=symbol,
        mode=mode,
        brick_size=brick_size,
        limit=limit,
        timeline_mode=timeline_mode,
    )

    bricks = renko_data.get("bricks", [])
    return prepare_dataframe(bricks)


def validate_and_sanitize_params(indicator_id: str, raw_params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validates user parameters against the indicator schema and sanitizes types.
    Raises ValueError on invalid indicators or malformed parameter values.
    """
    indicator_id = indicator_id.lower().strip()
    info = get_indicator_info(indicator_id)
    if not info:
        raise ValueError(f"Unknown indicator '{indicator_id}'. Check /api/indicators/catalog.")

    raw = raw_params or {}
    sanitized: Dict[str, Any] = {}

    # Quick validation of standard numerical parameters
    if "length" in raw:
        try:
            length_val = int(raw["length"])
            if length_val <= 0:
                raise ValueError("Invalid parameter 'length': must be positive integer.")
            sanitized["length"] = length_val
        except (ValueError, TypeError) as e:
            if "must be positive integer" in str(e):
                raise
            raise ValueError(f"Invalid parameter 'length': must be positive integer.")

    if indicator_id == "macd":
        fast = int(raw.get("fast", 12))
        slow = int(raw.get("slow", 26))
        signal = int(raw.get("signal", 9))
        if fast <= 0:
            raise ValueError("Invalid parameter 'fast': must be positive integer.")
        if slow <= 0:
            raise ValueError("Invalid parameter 'slow': must be positive integer.")
        if signal <= 0:
            raise ValueError("Invalid parameter 'signal': must be positive integer.")
        if fast >= slow:
            raise ValueError("Invalid parameter 'fast': fast period must be less than slow period.")
        sanitized["fast"] = fast
        sanitized["slow"] = slow
        sanitized["signal"] = signal

    elif indicator_id == "bbands":
        std = raw.get("std")
        if std is not None:
            try:
                std_f = float(std)
                if std_f <= 0:
                    raise ValueError("Invalid parameter 'std': must be positive number.")
                sanitized["lower_std"] = std_f
                sanitized["upper_std"] = std_f
            except (ValueError, TypeError) as e:
                if "must be positive number" in str(e):
                    raise
                raise ValueError(f"Invalid parameter 'std': must be positive number.")
        if "lower_std" in raw and "std" not in raw:
            try:
                l_std = float(raw["lower_std"])
                if l_std <= 0:
                    raise ValueError("Invalid parameter 'lower_std': must be positive number.")
                sanitized["lower_std"] = l_std
            except (ValueError, TypeError) as e:
                if "must be positive" in str(e):
                    raise
                raise ValueError("Invalid parameter 'lower_std': must be positive number.")
        if "upper_std" in raw and "std" not in raw:
            try:
                u_std = float(raw["upper_std"])
                if u_std <= 0:
                    raise ValueError("Invalid parameter 'upper_std': must be positive number.")
                sanitized["upper_std"] = u_std
            except (ValueError, TypeError) as e:
                if "must be positive" in str(e):
                    raise
                raise ValueError("Invalid parameter 'upper_std': must be positive number.")

    # Validate remaining parameters matching schema
    param_meta_map = {p["name"]: p for p in info.get("params", [])}
    for k, v in raw.items():
        if k in sanitized or k in ("std",):
            continue
        if k in param_meta_map:
            p_spec = param_meta_map[k]
            ptype = p_spec["type"]
            if ptype == "int":
                try:
                    iv = int(v)
                    if iv <= 0 and k in ("length", "k", "d", "smooth_k", "atr_length"):
                        raise ValueError(f"Invalid parameter '{k}': must be positive integer.")
                    sanitized[k] = iv
                except (ValueError, TypeError) as e:
                    if "must be positive integer" in str(e):
                        raise
                    raise ValueError(f"Invalid parameter '{k}': expected integer, got '{v}'.")
            elif ptype == "float":
                try:
                    fv = float(v)
                    if fv <= 0 and k in ("multiplier", "scalar"):
                        raise ValueError(f"Invalid parameter '{k}': must be positive number.")
                    sanitized[k] = fv
                except (ValueError, TypeError) as e:
                    if "must be positive number" in str(e):
                        raise
                    raise ValueError(f"Invalid parameter '{k}': expected float, got '{v}'.")
            elif ptype == "bool":
                if isinstance(v, str):
                    sanitized[k] = v.lower() in ("true", "1")
                else:
                    sanitized[k] = bool(v)
            else:
                sanitized[k] = v
        else:
            # Allow additional valid kwargs
            sanitized[k] = v

    return sanitized


def compute_indicator(
    indicator_id: str,
    df: pd.DataFrame,
    bar_times: List[int],
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Computes any pandas_ta indicator on the provided DataFrame and aligns timestamps.
    Handles warm-up periods, insufficient bars, and NaN sanitization gracefully.
    """
    indicator_id = indicator_id.lower().strip()
    info = get_indicator_info(indicator_id)
    if not info:
        raise ValueError(f"Unknown indicator '{indicator_id}'. Check /api/indicators/catalog.")

    kind = info["kind"]
    expected_outputs = [o["name"] for o in info.get("outputs", [])] or [indicator_id.upper()]

    # Validate parameters
    call_params = validate_and_sanitize_params(indicator_id, params)

    # Empty data check
    if len(df) == 0:
        return {
            "indicator": indicator_id,
            "kind": kind,
            "series": {out: [] for out in expected_outputs},
            "warning": f"Insufficient bars to compute {indicator_id} with given parameters",
        }

    fn = getattr(ta, indicator_id)
    sig = inspect.signature(fn)

    # Prepare input column arguments
    kwargs: Dict[str, Any] = {}
    input_col_map = {
        "open_": df["open"],
        "open": df["open"],
        "high": df["high"],
        "low": df["low"],
        "close": df["close"],
        "volume": df["volume"],
    }
    for p in sig.parameters.values():
        if p.name in input_col_map:
            kwargs[p.name] = input_col_map[p.name]

    # Pass sanitized hyperparameters
    for k, v in call_params.items():
        if k in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            kwargs[k] = v

    # Dynamic calculation with graceful error interception
    try:
        result = fn(**kwargs)
    except Exception as e:
        err_msg = str(e).lower()
        if any(x in err_msg for x in ("window shape", "index out of range", "insufficient", "larger than input array")):
            return {
                "indicator": indicator_id,
                "kind": kind,
                "series": {out: [] for out in expected_outputs},
                "warning": f"Insufficient bars to compute {indicator_id} with given parameters",
            }
        logger.warning(f"Error calculating {indicator_id}: {e}")
        raise ValueError(f"Calculation error for {indicator_id}: {str(e)}")

    # Warm-up / None return handling
    if result is None:
        return {
            "indicator": indicator_id,
            "kind": kind,
            "series": {out: [] for out in expected_outputs},
            "warning": f"Insufficient bars to compute {indicator_id} with given parameters",
        }

    # Extract output series columns
    cols_data: Dict[str, Union[pd.Series, np.ndarray]] = {}
    if isinstance(result, pd.Series):
        cname = result.name or indicator_id.upper()
        cols_data[str(cname)] = result
    elif isinstance(result, pd.DataFrame):
        for col in result.columns:
            cols_data[str(col)] = result[col]
    elif isinstance(result, tuple):
        for item in result:
            if isinstance(item, pd.Series):
                cols_data[str(item.name or "series")] = item
            elif isinstance(item, pd.DataFrame):
                for col in item.columns:
                    cols_data[str(col)] = item[col]

    # Timestamp alignment and NaN/Inf sanitization (convert to None for strict JSON compliance)
    series_dict: Dict[str, List[Dict[str, Any]]] = {}
    has_valid_val = False

    for cname, s in cols_data.items():
        pts: List[Dict[str, Any]] = []
        for i in range(len(bar_times)):
            val = s.iloc[i] if i < len(s) else None
            if val is None or pd.isna(val) or np.isinf(val):
                clean_val = None
            else:
                clean_val = round(float(val), 6)
                has_valid_val = True
            pts.append({"time": bar_times[i], "value": clean_val})
        series_dict[cname] = pts

    # If entire result is NaN due to insufficient warm-up bars
    if not has_valid_val:
        return {
            "indicator": indicator_id,
            "kind": kind,
            "series": {out: [] for out in expected_outputs},
            "warning": f"Insufficient bars to compute {indicator_id} with given parameters",
        }

    # Canonical aliases mapping for seamless frontend & test consumption
    if indicator_id == "bbands":
        for k, v in list(series_dict.items()):
            if k.startswith("BBU"):
                series_dict["upper"] = v
            elif k.startswith("BBM"):
                series_dict["middle"] = v
            elif k.startswith("BBL"):
                series_dict["lower"] = v
    elif indicator_id == "macd":
        for k, v in list(series_dict.items()):
            if k.startswith("MACDh"):
                series_dict["histogram"] = v
            elif k.startswith("MACDs"):
                series_dict["signal"] = v
            elif k.startswith("MACD"):
                series_dict["macd"] = v
    elif indicator_id == "stoch":
        for k, v in list(series_dict.items()):
            if k.startswith("STOCHk"):
                series_dict["k"] = v
            elif k.startswith("STOCHd"):
                series_dict["d"] = v
    elif indicator_id == "supertrend":
        for k, v in list(series_dict.items()):
            if k.startswith("SUPERTd"):
                series_dict["direction"] = v
            elif k.startswith("SUPERT_"):
                series_dict["supertrend"] = v
    elif indicator_id == "adx":
        for k, v in list(series_dict.items()):
            if k.startswith("ADX_"):
                series_dict["adx"] = v
            elif k.startswith("DMP_"):
                series_dict["dmp"] = v
            elif k.startswith("DMN_"):
                series_dict["dmn"] = v

    return {
        "indicator": indicator_id,
        "kind": kind,
        "series": series_dict,
        "warning": None,
    }
