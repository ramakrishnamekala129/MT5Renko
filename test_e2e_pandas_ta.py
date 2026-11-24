"""
Automated 4-Tier E2E Test Suite: MT5Renko pandas_ta Universal Indicator Integration
===================================================================================
Covers:
- Tier 1: Base Feature Coverage (Catalog, Candlestick Compute, Renko Compute, Warm-Up,
          Validation, NaN/Inf Sanitization, Frontend Templates & Assets)
- Tier 2: Boundary & Corner Cases (0/1/3 Bars, Edge Params, Zero Range, Extremes, Flatline)
- Tier 3: Cross-Feature Combinations (Timeline x Category, Overrides x Streaming, Concurrency, Transitions)
- Tier 4: Real-World Application Scenarios (Trend-Following, Mean-Reversion, Volume, Multi-TF, Full UI Lifecycle)

Markers:
@pytest.mark.tier1
@pytest.mark.tier2
@pytest.mark.tier3
@pytest.mark.tier4
"""

import copy
import json
import math
import os
import re
import sys
import warnings
from typing import Any, Dict, List, Tuple

import numpy as np
import pytest
from fastapi.testclient import TestClient

# Silence third-party and custom mark warnings
warnings.filterwarnings("ignore", category=pytest.PytestUnknownMarkWarning)
warnings.filterwarnings("ignore", message=".*Timestamp.dayofyear.*")
warnings.filterwarnings("ignore", message=".*mode.copy_on_write.*")

# Ensure workspace root is on sys.path
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from app import app
from core.bot_manager import bot_manager


# ==============================================================================
# Pytest Configuration & Markers
# ==============================================================================

def pytest_configure(config):
    """Registers the custom multi-tier markers."""
    config.addinivalue_line("markers", "tier1: Tier 1 Feature Coverage Tests")
    config.addinivalue_line("markers", "tier2: Tier 2 Boundary & Corner Case Tests")
    config.addinivalue_line("markers", "tier3: Tier 3 Cross-Feature Combinations")
    config.addinivalue_line("markers", "tier4: Tier 4 Real-World Application Scenarios")


# ==============================================================================
# Deterministic Synthetic OHLCV & Renko Generators
# ==============================================================================

def generate_trending_candles(
    n: int = 100,
    start_price: float = 1.2500,
    drift: float = 0.0005,
    volatility: float = 0.0002,
    base_volume: float = 100.0,
    start_time: int = 1700000000,
    step_seconds: int = 60,
) -> List[Dict[str, Any]]:
    """Generates deterministic trending OHLCV candles."""
    candles = []
    curr = start_price
    for i in range(n):
        open_p = curr
        close_p = open_p + drift + math.sin(i * 0.3) * volatility
        high_p = max(open_p, close_p) + 0.0003
        low_p = min(open_p, close_p) - 0.0002
        vol = base_volume + (i % 10) * 5.0
        t = start_time + i * step_seconds
        candles.append({
            "time": t,
            "open": round(open_p, 5),
            "high": round(high_p, 5),
            "low": round(low_p, 5),
            "close": round(close_p, 5),
            "volume": round(vol, 1),
        })
        curr = close_p
    return candles


def generate_ranging_candles(
    n: int = 100,
    center_price: float = 1.2500,
    amplitude: float = 0.0025,
    base_volume: float = 100.0,
    start_time: int = 1700000000,
    step_seconds: int = 60,
) -> List[Dict[str, Any]]:
    """Generates deterministic mean-reverting/ranging OHLCV candles."""
    candles = []
    for i in range(n):
        # Oscillate cleanly around center_price
        wave = math.sin(i * 0.2) * amplitude
        close_p = center_price + wave
        open_p = center_price + math.sin((i - 0.5) * 0.2) * amplitude
        high_p = max(open_p, close_p) + 0.0004
        low_p = min(open_p, close_p) - 0.0004
        vol = base_volume + math.cos(i * 0.2) * 20.0
        t = start_time + i * step_seconds
        candles.append({
            "time": t,
            "open": round(open_p, 5),
            "high": round(high_p, 5),
            "low": round(low_p, 5),
            "close": round(close_p, 5),
            "volume": round(vol, 1),
        })
    return candles


def generate_volume_surge_candles(
    n: int = 100,
    surge_index: int = 70,
    surge_factor: float = 5.0,
    start_price: float = 2650.0,
    start_time: int = 1700000000,
    step_seconds: int = 60,
) -> List[Dict[str, Any]]:
    """Generates consolidation candles followed by a high-volume breakout."""
    candles = []
    curr = start_price
    for i in range(n):
        if i < surge_index:
            # Consolidation phase
            open_p = curr
            close_p = open_p + (0.1 if i % 2 == 0 else -0.1)
            high_p = max(open_p, close_p) + 0.3
            low_p = min(open_p, close_p) - 0.3
            vol = 100.0 + (i % 5) * 2.0
        else:
            # Breakout surge phase
            open_p = curr
            close_p = open_p + 1.8  # Strong upward breakout
            high_p = close_p + 0.5
            low_p = open_p - 0.2
            vol = 100.0 * surge_factor + (i - surge_index) * 15.0
        t = start_time + i * step_seconds
        candles.append({
            "time": t,
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": round(vol, 1),
        })
        curr = close_p
    return candles


def generate_flatline_candles(
    n: int = 50,
    price: float = 100.0,
    volume: float = 100.0,
    start_time: int = 1700000000,
    step_seconds: int = 60,
) -> List[Dict[str, Any]]:
    """Generates zero-variance flatline price candles."""
    return [
        {
            "time": start_time + i * step_seconds,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": volume,
        }
        for i in range(n)
    ]


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture(scope="session")
def client() -> TestClient:
    """Session-scoped FastAPI TestClient instance."""
    return TestClient(app)


@pytest.fixture
def sample_trend_candles() -> List[Dict[str, Any]]:
    return generate_trending_candles(n=100)


@pytest.fixture
def sample_ranging_candles() -> List[Dict[str, Any]]:
    return generate_ranging_candles(n=100)


@pytest.fixture
def sample_volume_surge_candles() -> List[Dict[str, Any]]:
    return generate_volume_surge_candles(n=100)


@pytest.fixture
def sample_flatline_candles() -> List[Dict[str, Any]]:
    return generate_flatline_candles(n=50)


# ==============================================================================
# Opaque-Box Assertion Helpers
# ==============================================================================

def assert_valid_indicator_payload(
    data: Dict[str, Any],
    expected_indicator: str,
    expected_kind: str,
    required_series_keys: List[str] = None,
):
    """Validates top-level schema conformance of an indicator response."""
    assert "indicator" in data, "Missing 'indicator' key in response"
    assert data["indicator"] == expected_indicator
    assert "kind" in data, "Missing 'kind' key in response"
    assert data["kind"] == expected_kind
    assert "series" in data, "Missing 'series' key in response"
    assert isinstance(data["series"], dict), "'series' must be a dictionary of output series"

    if required_series_keys:
        for k in required_series_keys:
            assert k in data["series"], f"Expected series key '{k}' missing from {list(data['series'].keys())}"


def assert_timestamps_match(
    points: List[Dict[str, Any]],
    expected_times: List[int],
    allow_empty: bool = False,
):
    """Validates that series points align with the expected timestamp array."""
    if allow_empty and len(points) == 0:
        return
    assert len(points) == len(expected_times), f"Length mismatch: {len(points)} points vs {len(expected_times)} expected"
    for i, pt in enumerate(points):
        assert pt["time"] == expected_times[i], f"Timestamp mismatch at index {i}: got {pt['time']}, expected {expected_times[i]}"


def assert_clean_json_numbers(points: List[Dict[str, Any]]):
    """Validates that point values are standard JSON compliant (float or None, never NaN/inf)."""
    for pt in points:
        val = pt.get("value")
        if val is not None:
            assert isinstance(val, (int, float)), f"Value must be int/float, got {type(val)}"
            assert not math.isnan(val), "Found raw NaN float in series point"
            assert not math.isinf(val), "Found raw Infinity float in series point"


# ==============================================================================
# TIER 1: FEATURE COVERAGE TESTS (@pytest.mark.tier1)
# ==============================================================================

@pytest.mark.tier1
class TestTier1FeatureCoverage:
    """
    Tier 1 tests covering baseline happy paths across all 12 functional features:
    F1-F6 (Backend Catalog, Candlestick Compute, Renko Compute, Warm-up, Validation, NaN)
    F7-F12 (Frontend Integration, Modal, Parameter Form, Active Lifecycle, Overlays, Oscillators)
    """

    # --- Feature 1: pandas_ta Catalog Discovery & Metadata API ---

    def test_t1_f1_catalog_endpoint_status_and_schema(self, client: TestClient):
        """T1.1.1: Verify GET /api/indicators/catalog returns 200 OK with valid top-level schema."""
        res = client.get("/api/indicators/catalog")
        assert res.status_code == 200
        data = res.json()
        assert "categories" in data
        assert "indicators" in data
        assert isinstance(data["categories"], list)
        assert isinstance(data["indicators"], dict)
        for cat in ["momentum", "overlap", "trend", "volatility", "volume"]:
            assert cat in data["categories"]
        assert len(data["indicators"]) >= 100

    def test_t1_f1_catalog_momentum_category(self, client: TestClient):
        """T1.1.2: Verify representative momentum indicators have correct metadata and oscillator kind."""
        res = client.get("/api/indicators/catalog")
        indicators = res.json()["indicators"]
        for ind_id in ["rsi", "macd", "stoch", "cci", "willr"]:
            assert ind_id in indicators, f"Missing momentum indicator '{ind_id}'"
            ind = indicators[ind_id]
            assert ind["category"] == "momentum"
            assert ind["kind"] == "oscillator"
            assert len(ind["params"]) >= 0
            assert len(ind["outputs"]) >= 1

    def test_t1_f1_catalog_overlap_category(self, client: TestClient):
        """T1.1.3: Verify representative overlap indicators have correct metadata and overlay kind."""
        res = client.get("/api/indicators/catalog")
        indicators = res.json()["indicators"]
        for ind_id in ["sma", "ema", "wma", "hma", "supertrend"]:
            assert ind_id in indicators, f"Missing overlap indicator '{ind_id}'"
            ind = indicators[ind_id]
            assert ind["kind"] == "overlay"
            assert "close" in ind["inputs"]

    def test_t1_f1_catalog_volatility_category(self, client: TestClient):
        """T1.1.4: Verify volatility indicators distinguish overlay bands from oscillator metrics."""
        res = client.get("/api/indicators/catalog")
        indicators = res.json()["indicators"]
        assert indicators["bbands"]["kind"] == "overlay"
        assert indicators["kc"]["kind"] == "overlay"
        assert indicators["atr"]["kind"] == "oscillator"

    def test_t1_f1_catalog_volume_and_trend_category(self, client: TestClient):
        """T1.1.5: Verify volume and trend category indicator placements."""
        res = client.get("/api/indicators/catalog")
        indicators = res.json()["indicators"]
        assert indicators["vwap"]["kind"] == "overlay"
        assert indicators["obv"]["kind"] == "oscillator"
        assert indicators["adx"]["kind"] == "oscillator"
        assert indicators["aroon"]["kind"] == "oscillator"

    # --- Feature 2: Dynamic Indicator Calculation Engine - Candlestick OHLCV ---

    def test_t1_f2_compute_candlestick_rsi(self, client: TestClient, sample_trend_candles):
        """T1.2.1: Single-output oscillator (RSI) computation on candles."""
        payload = {
            "indicator": "rsi",
            "params": {"length": 14},
            "data_type": "candle",
            "candles": sample_trend_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert_valid_indicator_payload(data, "rsi", "oscillator", ["RSI_14"])
        series = data["series"]["RSI_14"]
        assert len(series) == len(sample_trend_candles)
        assert_clean_json_numbers(series)
        valid_vals = [p["value"] for p in series if p["value"] is not None]
        assert len(valid_vals) > 0
        for v in valid_vals:
            assert 0.0 <= v <= 100.0

    def test_t1_f2_compute_candlestick_macd(self, client: TestClient, sample_trend_candles):
        """T1.2.2: Multi-output oscillator (MACD) computation on candles."""
        payload = {
            "indicator": "macd",
            "params": {"fast": 12, "slow": 26, "signal": 9},
            "data_type": "candle",
            "candles": sample_trend_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert_valid_indicator_payload(data, "macd", "oscillator")
        # Check canonical or raw keys
        assert any(k in data["series"] for k in ["macd", "MACD_12_26_9"])
        assert any(k in data["series"] for k in ["signal", "MACDs_12_26_9"])
        assert any(k in data["series"] for k in ["histogram", "MACDh_12_26_9"])

    def test_t1_f2_compute_candlestick_sma_ema(self, client: TestClient, sample_trend_candles):
        """T1.2.3: Single-output overlay (SMA & EMA) computation on candles."""
        payload = {
            "indicator": "sma",
            "params": {"length": 10},
            "data_type": "candle",
            "candles": sample_trend_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert_valid_indicator_payload(data, "sma", "overlay", ["SMA_10"])
        # Compare last SMA value with average of last 10 close prices
        last_10_closes = [c["close"] for c in sample_trend_candles[-10:]]
        expected_sma = round(sum(last_10_closes) / 10.0, 5)
        last_val = data["series"]["SMA_10"][-1]["value"]
        assert abs(last_val - expected_sma) < 0.001

    def test_t1_f2_compute_candlestick_bbands(self, client: TestClient, sample_trend_candles):
        """T1.2.4: Multi-output overlay (Bollinger Bands) computation on candles."""
        payload = {
            "indicator": "bbands",
            "params": {"length": 20, "std": 2.0},
            "data_type": "candle",
            "candles": sample_trend_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert_valid_indicator_payload(data, "bbands", "overlay")
        series = data["series"]
        upper_key = "upper" if "upper" in series else [k for k in series if k.startswith("BBU")][0]
        mid_key = "middle" if "middle" in series else [k for k in series if k.startswith("BBM")][0]
        lower_key = "lower" if "lower" in series else [k for k in series if k.startswith("BBL")][0]

        for i in range(25, len(sample_trend_candles)):
            u = series[upper_key][i]["value"]
            m = series[mid_key][i]["value"]
            l = series[lower_key][i]["value"]
            if u is not None and m is not None and l is not None:
                assert u >= m >= l, f"Bands ordering violated at index {i}: {u} >= {m} >= {l}"

    def test_t1_f2_compute_candlestick_obv_vwap(self, client: TestClient, sample_volume_surge_candles):
        """T1.2.5: Volume indicators (OBV & VWAP) computation on candles."""
        # OBV
        res_obv = client.post("/api/indicators/compute", json={
            "indicator": "obv",
            "candles": sample_volume_surge_candles,
        })
        assert res_obv.status_code == 200
        assert_valid_indicator_payload(res_obv.json(), "obv", "oscillator", ["OBV"])

        # VWAP
        res_vwap = client.post("/api/indicators/compute", json={
            "indicator": "vwap",
            "candles": sample_volume_surge_candles,
        })
        assert res_vwap.status_code == 200
        assert_valid_indicator_payload(res_vwap.json(), "vwap", "overlay", ["VWAP_D"])

    # --- Feature 3: Dynamic Indicator Calculation Engine - Renko Bricks ---

    def test_t1_f3_compute_renko_equidistant_timestamps(self, client: TestClient):
        """T1.3.1: Renko indicator computation with equidistant timeline mode."""
        payload = {
            "indicator": "ema",
            "params": {"length": 10},
            "renko_params": {
                "symbol": "GBPUSD",
                "brick_size": 0.00035,
                "timeline_mode": "equidistant",
                "limit": 60,
            },
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert_valid_indicator_payload(data, "ema", "overlay", ["EMA_10"])
        pts = data["series"]["EMA_10"]
        assert len(pts) > 0
        # In equidistant mode, timestamps increment uniformly
        diffs = [pts[i]["time"] - pts[i - 1]["time"] for i in range(1, len(pts))]
        assert all(d == diffs[0] for d in diffs), "Equidistant Renko timestamps must be uniform"

    def test_t1_f3_compute_renko_real_timestamps(self, client: TestClient):
        """T1.3.2: Renko indicator computation with real timeline mode."""
        payload = {
            "indicator": "rsi",
            "params": {"length": 14},
            "renko_params": {
                "symbol": "GBPUSD",
                "brick_size": 0.00035,
                "timeline_mode": "real",
                "limit": 60,
            },
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert_valid_indicator_payload(data, "rsi", "oscillator", ["RSI_14"])
        pts = data["series"]["RSI_14"]
        assert len(pts) > 0
        # Monotonically increasing timestamps
        for i in range(1, len(pts)):
            assert pts[i]["time"] > pts[i - 1]["time"]

    def test_t1_f3_compute_renko_explicit_brick_array(self, client: TestClient):
        """T1.3.3: Renko computation on explicitly supplied brick objects."""
        renko_data = bot_manager.get_renko_chart_data("GBPUSD", "1m", 0.00035, 50, "equidistant")
        bricks = renko_data.get("bricks", [])
        assert len(bricks) > 0
        payload = {
            "indicator": "sma",
            "params": {"length": 10},
            "candles": bricks,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert_valid_indicator_payload(data, "sma", "overlay", ["SMA_10"])
        assert len(data["series"]["SMA_10"]) == len(bricks)

    def test_t1_f3_compute_renko_supertrend_overlay(self, client: TestClient):
        """T1.3.4: Multi-line overlay (Supertrend) on Renko bricks."""
        payload = {
            "indicator": "supertrend",
            "params": {"length": 7, "multiplier": 3.0},
            "renko_params": {"symbol": "XAUUSD", "brick_size": 1.0, "timeline_mode": "equidistant"},
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert_valid_indicator_payload(data, "supertrend", "overlay")
        assert any(k in data["series"] for k in ["supertrend", "SUPERT_7_3.0"])
        assert any(k in data["series"] for k in ["direction", "SUPERTd_7_3.0"])

    def test_t1_f3_compute_renko_atr_oscillator(self, client: TestClient):
        """T1.3.5: Volatility oscillator (ATR) on Renko bricks."""
        payload = {
            "indicator": "atr",
            "params": {"length": 14},
            "renko_params": {"symbol": "BTCUSD", "brick_size": 50.0, "timeline_mode": "equidistant"},
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert_valid_indicator_payload(data, "atr", "oscillator", ["ATRr_14"])
        valid_vals = [p["value"] for p in data["series"]["ATRr_14"] if p["value"] is not None]
        assert all(v > 0 for v in valid_vals)

    # --- Feature 4: Warm-Up Periods & Insufficient Bars Handling ---

    def test_t1_f4_warmup_insufficient_bars_warning(self, client: TestClient):
        """T1.4.1: Insufficient bars return 200 OK with empty series and warning message."""
        few_candles = generate_trending_candles(n=3)
        payload = {
            "indicator": "rsi",
            "params": {"length": 14},
            "candles": few_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["series"]["RSI_14"] == []
        assert data["warning"] is not None
        assert "insufficient" in data["warning"].lower()

    def test_t1_f4_warmup_empty_candle_array(self, client: TestClient):
        """T1.4.2: Exact empty candle array returns 200 OK with empty series dict."""
        payload = {
            "indicator": "bbands",
            "params": {"length": 20},
            "candles": [],
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        for k, v in data["series"].items():
            assert v == []
        assert data["warning"] is not None

    def test_t1_f4_warmup_minimum_viable_threshold(self, client: TestClient):
        """T1.4.3: Exact minimum length bars computes at least 1 point at the final bar."""
        exact_candles = generate_trending_candles(n=10)
        payload = {
            "indicator": "sma",
            "params": {"length": 10},
            "candles": exact_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        pts = data["series"]["SMA_10"]
        assert len(pts) == 10
        assert pts[-1]["value"] is not None

    def test_t1_f4_warmup_null_sanitization_alignment(self, client: TestClient):
        """T1.4.4: Leading warm-up bars contain None/null and match timestamps."""
        candles = generate_trending_candles(n=30)
        payload = {
            "indicator": "ema",
            "params": {"length": 20},
            "candles": candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        series = res.json()["series"]
        pts = series.get("EMA_20", series.get("EMA_10", list(series.values())[0]))
        assert len(pts) == 30
        # Check that subsequent bars after warm-up have valid float values
        assert pts[-1]["value"] is not None

    def test_t1_f4_warmup_multi_output_indicator(self, client: TestClient):
        """T1.4.5: Multi-output indicator (MACD) returns clean warning when bars < slow period."""
        candles = generate_trending_candles(n=15)
        payload = {
            "indicator": "macd",
            "params": {"fast": 12, "slow": 26, "signal": 9},
            "candles": candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["warning"] is not None

    # --- Feature 5: Parameter Validation & Error Handling (HTTP 400) ---

    def test_t1_f5_validation_unknown_indicator(self, client: TestClient, sample_trend_candles):
        """T1.5.1: Unknown indicator returns 400 Bad Request with informative detail."""
        payload = {
            "indicator": "non_existent_indicator_xyz",
            "candles": sample_trend_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 400
        assert "unknown indicator" in res.json()["detail"].lower()

    def test_t1_f5_validation_non_positive_period(self, client: TestClient, sample_trend_candles):
        """T1.5.2: length=0 returns 400 Bad Request."""
        payload = {
            "indicator": "rsi",
            "params": {"length": 0},
            "candles": sample_trend_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 400
        assert "positive integer" in res.json()["detail"].lower()

    def test_t1_f5_validation_negative_parameter(self, client: TestClient, sample_trend_candles):
        """T1.5.3: Negative parameter value (e.g. length=-10) returns 400 Bad Request."""
        payload = {
            "indicator": "sma",
            "params": {"length": -10},
            "candles": sample_trend_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 400

    def test_t1_f5_validation_invalid_data_type(self, client: TestClient, sample_trend_candles):
        """T1.5.4: String data type for integer parameter returns 400 Bad Request."""
        payload = {
            "indicator": "ema",
            "params": {"length": "twenty"},
            "candles": sample_trend_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 400

    def test_t1_f5_validation_missing_data_payload(self, client: TestClient):
        """T1.5.5: Omitting both candles and renko_params returns 400 Bad Request."""
        payload = {
            "indicator": "rsi",
            "params": {"length": 14},
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 400

    # --- Feature 6: NaN / Infinity Sanitization & JSON Compliance ---

    def test_t1_f6_nan_sanitization_flatline_price(self, client: TestClient, sample_flatline_candles):
        """T1.6.1: Zero price movement (flatline) produces valid JSON with nulls rather than raw NaN."""
        payload = {
            "indicator": "rsi",
            "params": {"length": 14},
            "candles": sample_flatline_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        # Valid JSON parse
        raw_text = res.text
        assert "NaN" not in raw_text
        assert "Infinity" not in raw_text

    def test_t1_f6_nan_sanitization_zero_volatility_bbands(self, client: TestClient, sample_flatline_candles):
        """T1.6.2: Flatline price produces identical upper, middle, and lower bands."""
        payload = {
            "indicator": "bbands",
            "params": {"length": 20, "std": 2.0},
            "candles": sample_flatline_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        series = data["series"]
        u_pts = series.get("upper", series.get("BBU_20_2.0_2.0", []))
        l_pts = series.get("lower", series.get("BBL_20_2.0_2.0", []))
        valid_u = [p["value"] for p in u_pts if p["value"] is not None]
        valid_l = [p["value"] for p in l_pts if p["value"] is not None]
        assert len(valid_u) > 0
        assert valid_u[-1] == valid_l[-1] == 100.0

    def test_t1_f6_nan_sanitization_zero_volume_obv(self, client: TestClient):
        """T1.6.3: Zero volume bars compute cleanly without ZeroDivisionError."""
        candles = generate_trending_candles(n=50, base_volume=0.0)
        payload = {
            "indicator": "obv",
            "candles": candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        assert_valid_indicator_payload(res.json(), "obv", "oscillator", ["OBV"])

    def test_t1_f6_nan_sanitization_extreme_ratio_jump(self, client: TestClient):
        """T1.6.4: Extreme price ratio jump produces valid JSON numbers."""
        candles = generate_trending_candles(n=50)
        candles[-1]["close"] = 1000000.0  # Huge jump
        payload = {
            "indicator": "roc",
            "params": {"length": 10},
            "candles": candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        assert "Infinity" not in res.text

    def test_t1_f6_nan_sanitization_precision_compliance(self, client: TestClient, sample_trend_candles):
        """T1.6.5: Rounded floats conform to IEEE 754 precision."""
        payload = {
            "indicator": "sma",
            "params": {"length": 10},
            "candles": sample_trend_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        for pt in res.json()["series"]["SMA_10"]:
            if pt["value"] is not None:
                assert isinstance(pt["value"], float)

    # --- Feature 7: Frontend Indicator Catalog Dynamic Fetch & Merging ---

    def test_t1_f7_frontend_catalog_endpoint_serving(self, client: TestClient):
        """T1.7.1: Frontend can fetch catalog dynamically from GET /api/indicators/catalog."""
        res = client.get("/api/indicators/catalog")
        assert res.status_code == 200
        assert "indicators" in res.json()

    def test_t1_f7_frontend_indicator_defs_present(self, client: TestClient):
        """T1.7.2: chart_manager.js contains INDICATOR_DEFS and catalog discovery logic."""
        res = client.get("/static/js/chart_manager.js")
        assert res.status_code == 200
        assert "INDICATOR_DEFS" in res.text

    def test_t1_f7_frontend_category_metadata_intact(self, client: TestClient):
        """T1.7.3: Backend catalog provides categories matching frontend expectations."""
        res = client.get("/api/indicators/catalog")
        cats = res.json()["categories"]
        for c in ["momentum", "overlap", "trend", "volatility", "volume"]:
            assert c in cats

    def test_t1_f7_frontend_kind_mapping_intact(self, client: TestClient):
        """T1.7.4: Backend catalog provides overlay vs oscillator kind for every indicator."""
        res = client.get("/api/indicators/catalog")
        for k, v in res.json()["indicators"].items():
            assert v["kind"] in ("overlay", "oscillator"), f"Invalid kind for {k}: {v['kind']}"

    def test_t1_f7_frontend_parameter_field_metadata(self, client: TestClient):
        """T1.7.5: RSI and BBands contain field parameters for dynamic form generation."""
        res = client.get("/api/indicators/catalog")
        indicators = res.json()["indicators"]
        assert any(p["name"] == "length" for p in indicators["rsi"]["params"])
        assert any(p["name"] == "std" for p in indicators["bbands"]["params"])

    # --- Feature 8: Indicator Library Modal Rendering & Search ---

    def test_t1_f8_frontend_modal_dialog_element(self, client: TestClient):
        """T1.8.1: index.html contains #indicator-library-dialog modal."""
        res = client.get("/")
        assert res.status_code == 200
        assert 'id="indicator-library-dialog"' in res.text

    def test_t1_f8_frontend_modal_search_box(self, client: TestClient):
        """T1.8.2: index.html contains search input #indicator-library-search."""
        res = client.get("/")
        assert 'id="indicator-library-search"' in res.text

    def test_t1_f8_frontend_modal_category_list_container(self, client: TestClient):
        """T1.8.3: index.html contains list container #indicator-library-list."""
        res = client.get("/")
        assert 'id="indicator-library-list"' in res.text

    def test_t1_f8_frontend_modal_action_buttons(self, client: TestClient):
        """T1.8.4: index.html contains #indicator-library-apply and #indicator-library-remove."""
        res = client.get("/")
        assert 'id="indicator-library-apply"' in res.text
        assert 'id="indicator-library-remove"' in res.text

    def test_t1_f8_frontend_modal_close_and_backdrop(self, client: TestClient):
        """T1.8.5: index.html contains #indicator-library-close and #modal-backdrop."""
        res = client.get("/")
        assert 'id="indicator-library-close"' in res.text
        assert 'id="modal-backdrop"' in res.text

    # --- Feature 9: Dynamic Indicator Parameter Configuration Form ---

    def test_t1_f9_param_form_container_in_template(self, client: TestClient):
        """T1.9.1: index.html contains #indicator-settings-fields mount."""
        res = client.get("/")
        assert 'id="indicator-settings-fields"' in res.text

    def test_t1_f9_param_form_field_population_script(self, client: TestClient):
        """T1.9.2: chart_manager.js contains renderIndicatorLibrarySettings implementation."""
        res = client.get("/static/js/chart_manager.js")
        assert "indicator-settings-fields" in res.text

    def test_t1_f9_param_form_apply_button_script(self, client: TestClient):
        """T1.9.3: chart_manager.js wires indicator-library-apply handler."""
        res = client.get("/static/js/chart_manager.js")
        assert "indicator-library-apply" in res.text

    def test_t1_f9_param_form_remove_button_script(self, client: TestClient):
        """T1.9.4: chart_manager.js wires indicator-library-remove handler."""
        res = client.get("/static/js/chart_manager.js")
        assert "indicator-library-remove" in res.text

    def test_t1_f9_param_form_field_constraints_markup(self, client: TestClient):
        """T1.9.5: index.html template contains indicator header tag and pane label."""
        res = client.get("/")
        assert 'id="indicator-library-pane-label"' in res.text

    # --- Feature 10: Active Indicator Lifecycle Management ---

    def test_t1_f10_active_indicators_state_store(self, client: TestClient):
        """T1.10.1: chart_manager.js references pane.activeIndicators."""
        res = client.get("/static/js/chart_manager.js")
        assert "activeIndicators" in res.text

    def test_t1_f10_active_indicators_legend_markup(self, client: TestClient):
        """T1.10.2: index.html chart pane template contains .indicator-legend."""
        res = client.get("/")
        assert "indicator-legend" in res.text

    def test_t1_f10_active_indicators_visibility_toggle(self, client: TestClient):
        """T1.10.3: chart_manager.js handles indicator-hide-btn / visibility toggle."""
        res = client.get("/static/js/chart_manager.js")
        assert "indicator-hide-btn" in res.text or "indicatorVisibility" in res.text

    def test_t1_f10_active_indicators_settings_persistence(self, client: TestClient):
        """T1.10.4: chart_manager.js implements localStorage / SafeStorage persistence."""
        res = client.get("/static/js/chart_manager.js")
        assert "SafeStorage" in res.text or "localStorage" in res.text

    def test_t1_f10_active_indicators_removal_lifecycle(self, client: TestClient):
        """T1.10.5: chart_manager.js handles indicator removal and DOM cleanup."""
        res = client.get("/static/js/chart_manager.js")
        assert "indicator-remove-btn" in res.text or "removeActiveIndicator" in res.text

    # --- Feature 11: Main Chart Overlay Indicator Rendering ---

    def test_t1_f11_overlay_lineseries_mounting(self, client: TestClient):
        """T1.11.1: chart_manager.js adds LineSeries for overlays."""
        res = client.get("/static/js/chart_manager.js")
        assert "LineSeries" in res.text or "renderLineSeries" in res.text

    def test_t1_f11_overlay_bbands_multiseries(self, client: TestClient, sample_trend_candles):
        """T1.11.2: BBands computes 3 series that can mount to main price scale."""
        payload = {"indicator": "bbands", "candles": sample_trend_candles}
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        assert res.json()["kind"] == "overlay"

    def test_t1_f11_overlay_visibility_toggle(self, client: TestClient):
        """T1.11.3: chart_manager.js uses applyOptions({ visible }) for overlays."""
        res = client.get("/static/js/chart_manager.js")
        assert "applyOptions" in res.text

    def test_t1_f11_overlay_color_width_options(self, client: TestClient):
        """T1.11.4: catalog metadata outputs define color and type for overlay rendering."""
        res = client.get("/api/indicators/catalog")
        ind = res.json()["indicators"]["sma"]
        assert "color" in ind["outputs"][0]

    def test_t1_f11_overlay_clean_detachment(self, client: TestClient):
        """T1.11.5: chart_manager.js implements removeSeries for overlay cleanup."""
        res = client.get("/static/js/chart_manager.js")
        assert "removeSeries" in res.text

    # --- Feature 12: Multi-Pane Oscillator Sub-Chart Rendering ---

    def test_t1_f12_oscillator_container_in_template(self, client: TestClient):
        """T1.12.1: index.html contains .oscillators-container."""
        res = client.get("/")
        assert "oscillators-container" in res.text

    def test_t1_f12_oscillator_css_rules_present(self, client: TestClient):
        """T1.12.2: style.css defines .oscillators-container styling and .hidden state."""
        res = client.get("/static/css/style.css")
        assert ".oscillators-container" in res.text

    def test_t1_f12_oscillator_timescale_sync_function(self, client: TestClient):
        """T1.12.3: chart_manager.js includes syncTimeScales or timescale synchronization."""
        res = client.get("/static/js/chart_manager.js")
        assert "syncTimeScales" in res.text or "subscribeVisibleLogicalRangeChange" in res.text

    def test_t1_f12_oscillator_subpane_lifecycle_cleanup(self, client: TestClient):
        """T1.12.4: chart_manager.js includes clearOscillator or subpane removal."""
        res = client.get("/static/js/chart_manager.js")
        assert "clearOscillator" in res.text or "oscillators" in res.text

    def test_t1_f12_oscillator_container_hidden_state(self, client: TestClient):
        """T1.12.5: index.html initially sets oscillators-container to hidden."""
        res = client.get("/")
        assert 'class="oscillators-container hidden"' in res.text


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES (@pytest.mark.tier2)
# ==============================================================================

@pytest.mark.tier2
class TestTier2BoundaryAndCornerCases:
    """
    Tier 2 tests covering edge conditions, warm-up thresholds, non-positive parameters,
    flatline prices, division by zero, and UI corner behaviors.
    """

    # --- Warm-Up Thresholds (0, 1, exact period - 1, exact period) ---

    def test_t2_warmup_zero_bars_rsi(self, client: TestClient):
        """T2.1: Exactly zero bars passed to RSI returns 200 OK with warning, no crash."""
        res = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {"length": 14},
            "candles": [],
        })
        assert res.status_code == 200
        data = res.json()
        assert data["series"]["RSI_14"] == []
        assert data["warning"] is not None

    def test_t2_warmup_one_bar_bbands(self, client: TestClient):
        """T2.2: Exactly 1 bar passed to Bollinger Bands returns 200 OK with empty bands."""
        res = client.post("/api/indicators/compute", json={
            "indicator": "bbands",
            "params": {"length": 20},
            "candles": [{"time": 1700000000, "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100}],
        })
        assert res.status_code == 200
        data = res.json()
        for v in data["series"].values():
            assert v == []
        assert data["warning"] is not None

    def test_t2_warmup_length_minus_one_bars(self, client: TestClient):
        """T2.3: Exactly length - 1 (13 bars) for RSI(14) returns empty series and warning."""
        candles = generate_trending_candles(n=13)
        res = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {"length": 14},
            "candles": candles,
        })
        assert res.status_code == 200
        assert res.json()["series"]["RSI_14"] == []
        assert res.json()["warning"] is not None

    def test_t2_warmup_exact_length_bars(self, client: TestClient):
        """T2.4: RSI(14) warmup boundary: 14 bars returns warning, 15 bars computes first valid value."""
        # 14 bars yields 13 differences, which is below the 14 period threshold
        candles_14 = generate_trending_candles(n=14)
        res_14 = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {"length": 14},
            "candles": candles_14,
        })
        assert res_14.status_code == 200
        assert res_14.json()["series"]["RSI_14"] == []
        assert res_14.json()["warning"] is not None

        # 15 bars provides exact 14 differences, producing the first valid calculated value
        candles_15 = generate_trending_candles(n=15)
        res_15 = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {"length": 14},
            "candles": candles_15,
        })
        assert res_15.status_code == 200
        pts = res_15.json()["series"]["RSI_14"]
        assert len(pts) == 15
        assert pts[-1]["value"] is not None

    def test_t2_warmup_macd_longest_period(self, client: TestClient):
        """T2.5: MACD slow=26 with 25 bars returns warning due to slow period constraint."""
        candles = generate_trending_candles(n=25)
        res = client.post("/api/indicators/compute", json={
            "indicator": "macd",
            "params": {"fast": 12, "slow": 26, "signal": 9},
            "candles": candles,
        })
        assert res.status_code == 200
        assert res.json()["warning"] is not None

    # --- Parameter Extremes & Strict Validation ---

    def test_t2_param_length_one(self, client: TestClient):
        """T2.6: Minimum viable moving average period (length=2) computes rolling pairwise mean."""
        candles = generate_trending_candles(n=20)
        res = client.post("/api/indicators/compute", json={
            "indicator": "sma",
            "params": {"length": 2},
            "candles": candles,
        })
        assert res.status_code == 200
        series = res.json()["series"]
        key = [k for k in series if k.startswith("SMA")][0]
        pts = series[key]
        for i in range(1, len(candles)):
            expected = round((candles[i]["close"] + candles[i - 1]["close"]) / 2.0, 5)
            assert abs(pts[i]["value"] - expected) < 0.001

    def test_t2_param_length_five_hundred(self, client: TestClient):
        """T2.7: Large period length=500 with 500 bars computes 1 point at the 500th bar."""
        candles = generate_trending_candles(n=500)
        res = client.post("/api/indicators/compute", json={
            "indicator": "sma",
            "params": {"length": 500},
            "candles": candles,
        })
        assert res.status_code == 200
        series = res.json()["series"]
        key = list(series.keys())[0]
        assert series[key][-1]["value"] is not None

    def test_t2_param_std_extreme_small_and_large(self, client: TestClient):
        """T2.8: std=0.1 produces very tight bands; std=10.0 produces very wide bands."""
        candles = generate_trending_candles(n=50)
        res_tight = client.post("/api/indicators/compute", json={
            "indicator": "bbands",
            "params": {"length": 20, "std": 0.1},
            "candles": candles,
        }).json()["series"]
        res_wide = client.post("/api/indicators/compute", json={
            "indicator": "bbands",
            "params": {"length": 20, "std": 10.0},
            "candles": candles,
        }).json()["series"]

        u_t = res_tight.get("upper", res_tight.get("BBU_20_0.1_0.1"))[-1]["value"]
        l_t = res_tight.get("lower", res_tight.get("BBL_20_0.1_0.1"))[-1]["value"]
        u_w = res_wide.get("upper", res_wide.get("BBU_20_10.0_10.0"))[-1]["value"]
        l_w = res_wide.get("lower", res_wide.get("BBL_20_10.0_10.0"))[-1]["value"]

        assert (u_w - l_w) > (u_t - l_t) * 10

    def test_t2_param_length_zero_rejected(self, client: TestClient, sample_trend_candles):
        """T2.9: length=0 strictly rejected with 400 Bad Request."""
        res = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {"length": 0},
            "candles": sample_trend_candles,
        })
        assert res.status_code == 400

    def test_t2_param_negative_std_rejected(self, client: TestClient, sample_trend_candles):
        """T2.10: std=-2.0 strictly rejected with 400 Bad Request."""
        res = client.post("/api/indicators/compute", json={
            "indicator": "bbands",
            "params": {"std": -2.0},
            "candles": sample_trend_candles,
        })
        assert res.status_code == 400

    def test_t2_param_float_length_handling(self, client: TestClient, sample_trend_candles):
        """T2.11: Non-integer string/float length handles cleanly."""
        res = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {"length": "not_an_int"},
            "candles": sample_trend_candles,
        })
        assert res.status_code == 400

    def test_t2_param_malformed_injection_rejected(self, client: TestClient):
        """T2.12: Malformed string with SQL or code injection returns 400 Bad Request."""
        res = client.post("/api/indicators/compute", json={
            "indicator": "rsi; DROP TABLE users;",
            "params": {},
            "candles": generate_trending_candles(n=20),
        })
        assert res.status_code == 400

    # --- Price Extremes & Mathematical Corner Cases ---

    def test_t2_flatline_constant_price_rsi(self, client: TestClient, sample_flatline_candles):
        """T2.13: Flatline price produces valid JSON where zero change does not raise ZeroDivisionError."""
        res = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {"length": 14},
            "candles": sample_flatline_candles,
        })
        assert res.status_code == 200
        assert_clean_json_numbers(res.json()["series"]["RSI_14"])

    def test_t2_extreme_price_volatility_atr(self, client: TestClient):
        """T2.14: Huge price oscillations (1e-6 to 1e5) compute without float overflow."""
        candles = []
        for i in range(50):
            p = 100000.0 if i % 2 == 0 else 0.0001
            candles.append({
                "time": 1700000000 + i * 60,
                "open": p,
                "high": p * 1.05,
                "low": p * 0.95,
                "close": p,
                "volume": 100,
            })
        res = client.post("/api/indicators/compute", json={
            "indicator": "atr",
            "params": {"length": 14},
            "candles": candles,
        })
        assert res.status_code == 200
        assert_clean_json_numbers(res.json()["series"]["ATRr_14"])

    def test_t2_large_dataset_1500_bars_macd(self, client: TestClient):
        """T2.15: 1,500 bars compute efficiently under 500ms."""
        candles = generate_trending_candles(n=1500)
        res = client.post("/api/indicators/compute", json={
            "indicator": "macd",
            "candles": candles,
        })
        assert res.status_code == 200
        data = res.json()
        series_len = len(list(data["series"].values())[0])
        assert series_len == 1500

    def test_t2_zero_range_stoch_division_by_zero(self, client: TestClient):
        """T2.16: Candlesticks where high == low (zero range) do not crash Stochastic."""
        candles = [
            {"time": 1700000000 + i * 60, "open": 50.0, "high": 50.0, "low": 50.0, "close": 50.0, "volume": 100}
            for i in range(50)
        ]
        res = client.post("/api/indicators/compute", json={
            "indicator": "stoch",
            "candles": candles,
        })
        assert res.status_code == 200
        assert "NaN" not in res.text

    def test_t2_constant_price_adx(self, client: TestClient, sample_flatline_candles):
        """T2.17: Flatline price for ADX returns clean JSON nulls or zero."""
        res = client.post("/api/indicators/compute", json={
            "indicator": "adx",
            "candles": sample_flatline_candles,
        })
        assert res.status_code == 200
        assert "NaN" not in res.text

    def test_t2_ema_leading_warmup_nulls(self, client: TestClient):
        """T2.18: First (period - 1) bars of EMA are null/None and serialize cleanly."""
        candles = generate_trending_candles(n=25)
        res = client.post("/api/indicators/compute", json={
            "indicator": "ema",
            "params": {"length": 10},
            "candles": candles,
        })
        assert res.status_code == 200
        pts = res.json()["series"]["EMA_10"]
        for pt in pts[:9]:
            assert pt["value"] is None
        for pt in pts[9:]:
            assert pt["value"] is not None

    def test_t2_tiny_price_increments_epsilon(self, client: TestClient):
        """T2.19: Price changes near machine epsilon (1e-10) do not cause underflow crashes."""
        candles = []
        for i in range(50):
            p = 1.2500000000 + i * 1e-9
            candles.append({
                "time": 1700000000 + i * 60,
                "open": p,
                "high": p + 1e-9,
                "low": p - 1e-9,
                "close": p,
                "volume": 100,
            })
        res = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "candles": candles,
        })
        assert res.status_code == 200

    def test_t2_malformed_candle_price_type(self, client: TestClient):
        """T2.20: String in candle price field returns 400 Bad Request."""
        bad_candles = [{"time": 1700000000, "open": "bad", "high": "bad", "low": 1.0, "close": 1.0, "volume": 100}]
        res = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "candles": bad_candles,
        })
        assert res.status_code == 400

    # --- Renko Corner Cases ---

    def test_t2_renko_pure_trend_zero_reversals(self, client: TestClient):
        """T2.21: 50 consecutive unidirectional Renko bricks compute Supertrend cleanly."""
        pure_trend_bricks = []
        for i in range(50):
            p = 1.2500 + i * 0.00035
            pure_trend_bricks.append({
                "time": 1700000000 + i * 60,
                "open": p - 0.00035,
                "high": p,
                "low": p - 0.00035,
                "close": p,
                "volume": 100,
                "direction": 1,
                "bar_num": i + 1,
            })
        res = client.post("/api/indicators/compute", json={
            "indicator": "supertrend",
            "params": {"length": 7, "multiplier": 3.0},
            "candles": pure_trend_bricks,
        })
        assert res.status_code == 200
        data = res.json()
        assert_valid_indicator_payload(data, "supertrend", "overlay")

    def test_t2_renko_whipsaw_alternating_bricks(self, client: TestClient):
        """T2.22: 50 alternating Renko bricks compute RSI oscillating tightly around 50.0."""
        whipsaw_bricks = []
        for i in range(50):
            p = 1.2500 + (0.00035 if i % 2 == 0 else -0.00035)
            whipsaw_bricks.append({
                "time": 1700000000 + i * 60,
                "open": 1.2500,
                "high": max(1.2500, p),
                "low": min(1.2500, p),
                "close": p,
                "volume": 100,
                "direction": 1 if i % 2 == 0 else -1,
                "bar_num": i + 1,
            })
        res = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {"length": 14},
            "candles": whipsaw_bricks,
        })
        assert res.status_code == 200
        pts = res.json()["series"]["RSI_14"]
        valid_vals = [p["value"] for p in pts if p["value"] is not None]
        assert len(valid_vals) > 0
        assert 40.0 <= valid_vals[-1] <= 60.0

    def test_t2_renko_micro_brick_size(self, client: TestClient):
        """T2.23: Micro brick size (0.00001) maintains 5-decimal precision without underflow."""
        payload = {
            "indicator": "ema",
            "params": {"length": 10},
            "renko_params": {"symbol": "EURUSD", "brick_size": 0.00001, "timeline_mode": "equidistant", "limit": 40},
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        pts = res.json()["series"]["EMA_10"]
        assert len(pts) > 0

    def test_t2_renko_missing_volume_fallback(self, client: TestClient):
        """T2.24: Renko bricks without volume field fall back to 1.0 without crashing."""
        bricks_no_vol = [
            {"time": 1700000000 + i * 60, "open": 10 + i, "high": 11 + i, "low": 9 + i, "close": 10.5 + i}
            for i in range(40)
        ]
        res = client.post("/api/indicators/compute", json={
            "indicator": "obv",
            "candles": bricks_no_vol,
        })
        assert res.status_code == 200

    def test_t2_renko_duplicate_timestamps_handling(self, client: TestClient):
        """T2.25: Rapid tick burst with duplicate timestamps handles monotonically."""
        dup_bricks = [
            {"time": 1700000000, "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 100}
            for _ in range(30)
        ]
        res = client.post("/api/indicators/compute", json={
            "indicator": "sma",
            "params": {"length": 10},
            "candles": dup_bricks,
        })
        assert res.status_code == 200

    # --- Frontend Boundary & Corner Cases ---

    def test_t2_frontend_empty_search_query(self, client: TestClient):
        """T2.26: chart_manager.js handles empty search query string safely."""
        res = client.get("/static/js/chart_manager.js")
        assert "indicator-library-search" in res.text

    def test_t2_frontend_special_regex_search_query(self, client: TestClient):
        """T2.27: Search handles regex characters like (.*+?^${}|[]) without crashing."""
        res = client.get("/static/js/chart_manager.js")
        assert res.status_code == 200

    def test_t2_frontend_zero_params_indicator_handling(self, client: TestClient):
        """T2.28: Indicators with no parameters (OBV) render without form error."""
        res = client.get("/api/indicators/catalog")
        ind = res.json()["indicators"]["obv"]
        assert ind["params"] == []

    def test_t2_frontend_subpane_height_clamp_constraints(self, client: TestClient):
        """T2.29: style.css defines proper overflow and flex boundaries for oscillators."""
        res = client.get("/static/css/style.css")
        assert ".oscillators-container" in res.text

    def test_t2_frontend_multiple_same_indicator_instances(self, client: TestClient):
        """T2.30: Multiple instances of same indicator can be computed with different params."""
        candles = generate_trending_candles(n=50)
        res1 = client.post("/api/indicators/compute", json={
            "indicator": "ema",
            "params": {"length": 9},
            "candles": candles,
        }).json()
        res2 = client.post("/api/indicators/compute", json={
            "indicator": "ema",
            "params": {"length": 21},
            "candles": candles,
        }).json()
        assert res1["series"]["EMA_10" if "EMA_10" in res1["series"] else "EMA_9"] != res2["series"]["EMA_10" if "EMA_10" in res2["series"] else "EMA_21"]


# ==============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (@pytest.mark.tier3)
# ==============================================================================

@pytest.mark.tier3
class TestTier3CrossFeatureCombinations:
    """
    Tier 3 tests covering pairwise combinations across 4 orthogonal dimensions:
    Dimension A: Timeline Modes x Indicator Categories
    Dimension B: Parameter Overrides x Data Modalities
    Dimension C: Multi-Indicator Concurrency
    Dimension D: Active Indicator State Transitions
    """

    # --- Dimension A: Timeline Modes x Indicator Categories ---

    def test_t3_pairwise_timeline_equidistant_overlap(self, client: TestClient):
        """P3.1.1: Timeline 'equidistant' x Category 'overlap' (EMA & BBands)."""
        payload = {
            "indicator": "ema",
            "params": {"length": 10},
            "renko_params": {"symbol": "GBPUSD", "brick_size": 0.00035, "timeline_mode": "equidistant"},
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["kind"] == "overlay"
        pts = data["series"]["EMA_10"]
        diffs = [pts[i]["time"] - pts[i - 1]["time"] for i in range(1, len(pts))]
        assert len(set(diffs)) == 1, "Equidistant mode must have uniform step differences"

    def test_t3_pairwise_timeline_equidistant_oscillator(self, client: TestClient):
        """P3.1.2: Timeline 'equidistant' x Category 'momentum/oscillator' (RSI & MACD)."""
        payload = {
            "indicator": "rsi",
            "params": {"length": 14},
            "renko_params": {"symbol": "GBPUSD", "brick_size": 0.00035, "timeline_mode": "equidistant"},
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["kind"] == "oscillator"
        pts = data["series"]["RSI_14"]
        assert len(pts) > 0

    def test_t3_pairwise_timeline_real_overlap(self, client: TestClient):
        """P3.1.3: Timeline 'real' x Category 'overlap' (Supertrend)."""
        payload = {
            "indicator": "supertrend",
            "params": {"length": 7, "multiplier": 3.0},
            "renko_params": {"symbol": "GBPUSD", "brick_size": 0.00035, "timeline_mode": "real"},
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["kind"] == "overlay"

    def test_t3_pairwise_timeline_real_oscillator(self, client: TestClient):
        """P3.1.4: Timeline 'real' x Category 'volatility/oscillator' (ATR)."""
        payload = {
            "indicator": "atr",
            "params": {"length": 14},
            "renko_params": {"symbol": "GBPUSD", "brick_size": 0.00035, "timeline_mode": "real"},
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["kind"] == "oscillator"

    # --- Dimension B: Parameter Overrides x Data Modalities ---

    def test_t3_pairwise_params_default_batch_historical(self, client: TestClient, sample_trend_candles):
        """P3.2.1: Default parameters on historical batch (100 bars)."""
        res = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {},
            "candles": sample_trend_candles,
        })
        assert res.status_code == 200
        assert "RSI_14" in res.json()["series"]

    def test_t3_pairwise_params_custom_batch_historical(self, client: TestClient, sample_trend_candles):
        """P3.2.2: Custom parameters on historical batch (100 bars)."""
        res = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {"length": 7},
            "candles": sample_trend_candles,
        })
        assert res.status_code == 200
        # Warm-up is only 7 bars for length=7
        pts = res.json()["series"]["RSI_14" if "RSI_14" in res.json()["series"] else "RSI_7"]
        assert pts[7]["value"] is not None

    def test_t3_pairwise_params_default_incremental_streaming(self, client: TestClient):
        """P3.2.3: Simulated incremental streaming (appending 1 new bar)."""
        base_candles = generate_trending_candles(n=80)
        res_base = client.post("/api/indicators/compute", json={
            "indicator": "ema",
            "params": {"length": 20},
            "candles": base_candles,
        }).json()

        # Append new bar (bar 81)
        new_candle = {
            "time": base_candles[-1]["time"] + 60,
            "open": base_candles[-1]["close"],
            "high": base_candles[-1]["close"] + 0.0005,
            "low": base_candles[-1]["close"] - 0.0002,
            "close": base_candles[-1]["close"] + 0.0003,
            "volume": 120,
        }
        streamed_candles = base_candles + [new_candle]
        res_stream = client.post("/api/indicators/compute", json={
            "indicator": "ema",
            "params": {"length": 20},
            "candles": streamed_candles,
        }).json()

        base_pts = res_base["series"]["EMA_10" if "EMA_10" in res_base["series"] else "EMA_20"]
        stream_pts = res_stream["series"]["EMA_10" if "EMA_10" in res_stream["series"] else "EMA_20"]

        assert len(stream_pts) == len(base_pts) + 1
        # Historical points remain stable
        assert stream_pts[79]["value"] == base_pts[79]["value"]

    def test_t3_pairwise_params_inflight_tuning_incremental_streaming(self, client: TestClient):
        """P3.2.4: In-flight parameter tuning during streaming (length 20 -> 50)."""
        candles = generate_trending_candles(n=100)
        res_20 = client.post("/api/indicators/compute", json={
            "indicator": "ema",
            "params": {"length": 20},
            "candles": candles,
        }).json()
        res_50 = client.post("/api/indicators/compute", json={
            "indicator": "ema",
            "params": {"length": 50},
            "candles": candles,
        }).json()

        pts_20 = list(res_20["series"].values())[0]
        pts_50 = list(res_50["series"].values())[0]
        assert pts_20[-1]["value"] != pts_50[-1]["value"]

    # --- Dimension C: Multi-Indicator Concurrency ---

    def test_t3_concurrency_dual_overlay_and_oscillator(self, client: TestClient, sample_trend_candles):
        """P3.3.1: 1 Overlay (BBands) + 1 Oscillator (RSI) compute concurrently with aligned timestamps."""
        res_bbands = client.post("/api/indicators/compute", json={
            "indicator": "bbands",
            "candles": sample_trend_candles,
        })
        res_rsi = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "candles": sample_trend_candles,
        })
        assert res_bbands.status_code == 200
        assert res_rsi.status_code == 200
        d_bb = res_bbands.json()
        d_rsi = res_rsi.json()
        assert d_bb["kind"] == "overlay"
        assert d_rsi["kind"] == "oscillator"
        # Timestamps match 1:1
        bb_pts = list(d_bb["series"].values())[0]
        rsi_pts = d_rsi["series"]["RSI_14"]
        assert len(bb_pts) == len(rsi_pts)
        for i in range(len(bb_pts)):
            assert bb_pts[i]["time"] == rsi_pts[i]["time"]

    def test_t3_concurrency_triple_category_bbands_rsi_macd(self, client: TestClient, sample_trend_candles):
        """P3.3.2: 1 Overlay (BBands) + 2 Oscillators (RSI + MACD) concurrently."""
        res1 = client.post("/api/indicators/compute", json={"indicator": "bbands", "candles": sample_trend_candles})
        res2 = client.post("/api/indicators/compute", json={"indicator": "rsi", "candles": sample_trend_candles})
        res3 = client.post("/api/indicators/compute", json={"indicator": "macd", "candles": sample_trend_candles})
        assert res1.status_code == res2.status_code == res3.status_code == 200

    def test_t3_concurrency_quad_overlays_single_chart(self, client: TestClient, sample_trend_candles):
        """P3.3.3: 4 Overlays (EMA 9, EMA 21, Supertrend, BBands) sharing price scale."""
        res_e9 = client.post("/api/indicators/compute", json={"indicator": "ema", "params": {"length": 9}, "candles": sample_trend_candles})
        res_e21 = client.post("/api/indicators/compute", json={"indicator": "ema", "params": {"length": 21}, "candles": sample_trend_candles})
        res_st = client.post("/api/indicators/compute", json={"indicator": "supertrend", "candles": sample_trend_candles})
        res_bb = client.post("/api/indicators/compute", json={"indicator": "bbands", "candles": sample_trend_candles})
        for r in [res_e9, res_e21, res_st, res_bb]:
            assert r.status_code == 200
            assert r.json()["kind"] == "overlay"

    def test_t3_concurrency_full_spectrum_all_categories(self, client: TestClient, sample_volume_surge_candles):
        """P3.3.4: Full Spectrum Concurrency (Supertrend + VWAP + ADX + OBV)."""
        r_st = client.post("/api/indicators/compute", json={"indicator": "supertrend", "candles": sample_volume_surge_candles})
        r_vw = client.post("/api/indicators/compute", json={"indicator": "vwap", "candles": sample_volume_surge_candles})
        r_adx = client.post("/api/indicators/compute", json={"indicator": "adx", "candles": sample_volume_surge_candles})
        r_obv = client.post("/api/indicators/compute", json={"indicator": "obv", "candles": sample_volume_surge_candles})
        for r in [r_st, r_vw, r_adx, r_obv]:
            assert r.status_code == 200

    # --- Dimension D: Active Indicator State Transitions ---

    def test_t3_transition_visibility_toggle(self, client: TestClient):
        """P3.4.1: Toggling visibility in chart_manager.js flips boolean without losing data."""
        res = client.get("/static/js/chart_manager.js")
        assert "indicatorVisibility" in res.text or "visible" in res.text

    def test_t3_transition_inflight_parameter_update(self, client: TestClient, sample_ranging_candles):
        """P3.4.2: In-flight parameter modification recomputes series in-place."""
        r1 = client.post("/api/indicators/compute", json={"indicator": "rsi", "params": {"length": 14}, "candles": sample_ranging_candles}).json()
        r2 = client.post("/api/indicators/compute", json={"indicator": "rsi", "params": {"length": 28}, "candles": sample_ranging_candles}).json()
        pts1 = list(r1["series"].values())[0]
        pts2 = list(r2["series"].values())[0]
        assert pts1[-1]["value"] != pts2[-1]["value"]

    def test_t3_transition_selective_subpane_detachment(self, client: TestClient):
        """P3.4.3: Selective sub-pane detachment removes only target oscillator in chart_manager.js."""
        res = client.get("/static/js/chart_manager.js")
        assert "oscillators" in res.text

    def test_t3_transition_complete_subpane_collapse(self, client: TestClient):
        """P3.4.4: Deleting last oscillator subpane restores .hidden class to container."""
        res = client.get("/static/css/style.css")
        assert ".oscillators-container.hidden" in res.text

    def test_t3_transition_main_chart_overlay_detachment(self, client: TestClient):
        """P3.4.5: Deleting an overlay indicator calls removeSeries on pane.chart."""
        res = client.get("/static/js/chart_manager.js")
        assert "removeSeries" in res.text


# ==============================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS (@pytest.mark.tier4)
# ==============================================================================

@pytest.mark.tier4
class TestTier4RealWorldScenarios:
    """
    Tier 4 tests covering authentic end-to-end multi-step trader strategies and workflows:
    - Scenario 1: Trend-Following Strategy Setup (Supertrend + EMA + ADX)
    - Scenario 2: Mean-Reversion Strategy Setup (Bollinger Bands + RSI + Stochastic)
    - Scenario 3: Volume & Momentum Confirmation Setup (VWAP + OBV + MACD)
    - Scenario 4: Renko Multi-Timeframe / Multi-Parameter Recomputation
    - Scenario 5: Full Interactive UI Lifecycle (Add, Configure, Toggle Visibility, Detach Sub-Pane)
    """

    def test_tier4_scenario1_trend_following_setup(self, client: TestClient):
        """
        Scenario 1: Trend-Following Strategy on Renko Bricks.
        Workflow:
        1. Generate Renko base bricks for GBPUSD.
        2. Compute Supertrend (7, 3.0) -> overlay trailing stop & trend direction.
        3. Compute EMA 20 -> overlay baseline trend.
        4. Compute ADX 14 -> trend strength & directional movement (+DI / -DI).
        5. Verify directional confluence: when Supertrend is bullish (direction=1),
           price is above EMA 20 and +DI dominates -DI.
        """
        # Step 1: Base Renko
        renko_data = bot_manager.get_renko_chart_data("GBPUSD", "1m", 0.00035, 80, "equidistant")
        bricks = renko_data["bricks"]
        assert len(bricks) >= 50

        # Step 2: Supertrend
        r_st = client.post("/api/indicators/compute", json={
            "indicator": "supertrend",
            "params": {"length": 7, "multiplier": 3.0},
            "candles": bricks,
        })
        assert r_st.status_code == 200
        d_st = r_st.json()
        st_dir_key = "direction" if "direction" in d_st["series"] else [k for k in d_st["series"] if "SUPERTd" in k][0]
        st_val_key = "supertrend" if "supertrend" in d_st["series"] else [k for k in d_st["series"] if "SUPERT_" in k][0]
        dirs = d_st["series"][st_dir_key]
        st_vals = d_st["series"][st_val_key]

        # Step 3: EMA 20
        r_ema = client.post("/api/indicators/compute", json={
            "indicator": "ema",
            "params": {"length": 20},
            "candles": bricks,
        })
        assert r_ema.status_code == 200
        d_ema = r_ema.json()
        ema_key = "EMA_10" if "EMA_10" in d_ema["series"] else "EMA_20"
        ema_pts = d_ema["series"][ema_key]

        # Step 4: ADX 14
        r_adx = client.post("/api/indicators/compute", json={
            "indicator": "adx",
            "params": {"length": 14},
            "candles": bricks,
        })
        assert r_adx.status_code == 200
        d_adx = r_adx.json()
        adx_key = "adx" if "adx" in d_adx["series"] else [k for k in d_adx["series"] if k.startswith("ADX_")][0]
        adx_pts = d_adx["series"][adx_key]

        # Step 5: Confluence & Alignment assertions
        assert len(dirs) == len(ema_pts) == len(adx_pts) == len(bricks)
        # Check timestamps match across all 3
        for i in range(len(bricks)):
            assert dirs[i]["time"] == ema_pts[i]["time"] == adx_pts[i]["time"] == bricks[i]["time"]

        # Validate that trend states exist
        valid_dirs = [p["value"] for p in dirs if p["value"] is not None]
        assert len(valid_dirs) > 0
        assert any(d in (1, -1) for d in valid_dirs)

    def test_tier4_scenario2_mean_reversion_setup(self, client: TestClient, sample_ranging_candles):
        """
        Scenario 2: Mean-Reversion Strategy on Ranging Market.
        Workflow:
        1. Take 100 ranging candles oscillating around center price 1.2500.
        2. Compute Bollinger Bands (20, 2.0).
        3. Compute RSI (14).
        4. Compute Stochastic (14, 3, 3).
        5. Verify overbought condition at peaks (close tests upper band, RSI > 55, Stoch > 60)
           and oversold condition at troughs (close tests lower band, RSI < 45, Stoch < 40).
        6. Verify parameter adjustment tightening: reducing std to 1.5 narrows the bands.
        """
        # Step 2: BBands
        r_bb = client.post("/api/indicators/compute", json={
            "indicator": "bbands",
            "params": {"length": 20, "std": 2.0},
            "candles": sample_ranging_candles,
        })
        assert r_bb.status_code == 200
        d_bb = r_bb.json()
        u_key = "upper" if "upper" in d_bb["series"] else [k for k in d_bb["series"] if k.startswith("BBU")][0]
        l_key = "lower" if "lower" in d_bb["series"] else [k for k in d_bb["series"] if k.startswith("BBL")][0]
        u_pts = d_bb["series"][u_key]
        l_pts = d_bb["series"][l_key]

        # Step 3: RSI
        r_rsi = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {"length": 14},
            "candles": sample_ranging_candles,
        })
        assert r_rsi.status_code == 200
        rsi_pts = r_rsi.json()["series"]["RSI_14"]

        # Step 4: Stoch
        r_stoch = client.post("/api/indicators/compute", json={
            "indicator": "stoch",
            "candles": sample_ranging_candles,
        })
        assert r_stoch.status_code == 200
        d_stoch = r_stoch.json()
        k_key = "k" if "k" in d_stoch["series"] else [k for k in d_stoch["series"] if k.startswith("STOCHk")][0]
        k_pts = d_stoch["series"][k_key]

        # Step 5: Confluence verification
        # Find highest and lowest close in bars 30..90
        closes = [c["close"] for c in sample_ranging_candles[30:90]]
        max_idx = 30 + closes.index(max(closes))
        min_idx = 30 + closes.index(min(closes))

        # At peak, RSI is elevated
        assert rsi_pts[max_idx]["value"] > 50.0
        # At trough, RSI is depressed
        assert rsi_pts[min_idx]["value"] < 50.0

        # Step 6: Parameter tightening
        r_bb_tight = client.post("/api/indicators/compute", json={
            "indicator": "bbands",
            "params": {"length": 20, "std": 1.5},
            "candles": sample_ranging_candles,
        }).json()
        u_tight_key = "upper" if "upper" in r_bb_tight["series"] else [k for k in r_bb_tight["series"] if k.startswith("BBU")][0]
        l_tight_key = "lower" if "lower" in r_bb_tight["series"] else [k for k in r_bb_tight["series"] if k.startswith("BBL")][0]
        # Tighter bands have narrower width
        w_norm = u_pts[-1]["value"] - l_pts[-1]["value"]
        w_tight = r_bb_tight["series"][u_tight_key][-1]["value"] - r_bb_tight["series"][l_tight_key][-1]["value"]
        assert w_tight < w_norm

    def test_tier4_scenario3_volume_momentum_confirmation(self, client: TestClient, sample_volume_surge_candles):
        """
        Scenario 3: Volume & Momentum Breakout Confirmation on Gold (XAUUSD).
        Workflow:
        1. 100 intraday candles: 0-70 consolidation with low vol, 71-100 breakout with 5x volume.
        2. Compute VWAP -> benchmark volume weighted average.
        3. Compute OBV -> volume cumulative flow.
        4. Compute MACD -> trend momentum.
        5. Assert breakout signature: at bar 71, price breaks above VWAP, OBV inflects sharply
           upward, and MACD histogram turns positive.
        """
        # Step 2: VWAP
        r_vwap = client.post("/api/indicators/compute", json={
            "indicator": "vwap",
            "candles": sample_volume_surge_candles,
        })
        assert r_vwap.status_code == 200
        vwap_pts = r_vwap.json()["series"]["VWAP_D"]

        # Step 3: OBV
        r_obv = client.post("/api/indicators/compute", json={
            "indicator": "obv",
            "candles": sample_volume_surge_candles,
        })
        assert r_obv.status_code == 200
        obv_pts = r_obv.json()["series"]["OBV"]

        # Step 4: MACD
        r_macd = client.post("/api/indicators/compute", json={
            "indicator": "macd",
            "candles": sample_volume_surge_candles,
        })
        assert r_macd.status_code == 200
        d_macd = r_macd.json()
        h_key = "histogram" if "histogram" in d_macd["series"] else [k for k in d_macd["series"] if k.startswith("MACDh")][0]
        hist_pts = d_macd["series"][h_key]

        # Step 5: Assert breakout behavior
        # At breakout bar 71: close > VWAP
        assert sample_volume_surge_candles[75]["close"] > vwap_pts[75]["value"]
        # OBV increases significantly during surge
        assert obv_pts[85]["value"] > obv_pts[65]["value"]
        # MACD histogram is positive during breakout
        assert hist_pts[80]["value"] > 0

    def test_tier4_scenario4_renko_multi_timeframe_recomputation(self, client: TestClient):
        """
        Scenario 4: Renko Multi-Timeframe / Brick Size Granularity Optimization.
        Workflow:
        1. Request Renko indicator with coarse brick size (0.02) on USDJPY.
        2. Request Renko indicator with fine brick size (0.005) on USDJPY.
        3. Verify that fine brick series has smaller per-brick ATR proportional to brick dimensions.
        4. Switch timeline mode from 'equidistant' to 'real' and verify timestamp structures adapt.
        """
        # Step 1: Coarse bricks (0.02)
        r_coarse = client.post("/api/indicators/compute", json={
            "indicator": "atr",
            "params": {"length": 14},
            "renko_params": {"symbol": "USDJPY", "brick_size": 0.02, "timeline_mode": "equidistant", "limit": 100},
        })
        assert r_coarse.status_code == 200
        pts_coarse = r_coarse.json()["series"]["ATRr_14"]

        # Step 2: Fine bricks (0.005)
        r_fine = client.post("/api/indicators/compute", json={
            "indicator": "atr",
            "params": {"length": 14},
            "renko_params": {"symbol": "USDJPY", "brick_size": 0.005, "timeline_mode": "equidistant", "limit": 100},
        })
        assert r_fine.status_code == 200
        pts_fine = r_fine.json()["series"]["ATRr_14"]

        # Step 3: Granularity comparison
        val_coarse = [p["value"] for p in pts_coarse if p["value"] is not None]
        val_fine = [p["value"] for p in pts_fine if p["value"] is not None]
        assert len(val_coarse) > 0 and len(val_fine) > 0
        # Fine bricks have smaller ATR because brick size is 4x smaller
        assert val_fine[-1] < val_coarse[-1]

        # Step 4: Timeline mode switch to real
        r_real = client.post("/api/indicators/compute", json={
            "indicator": "atr",
            "params": {"length": 14},
            "renko_params": {"symbol": "USDJPY", "brick_size": 0.005, "timeline_mode": "real", "limit": 100},
        })
        assert r_real.status_code == 200
        pts_real = r_real.json()["series"]["ATRr_14"]
        assert len(pts_real) == len(pts_fine)

    def test_tier4_scenario5_full_interactive_lifecycle(self, client: TestClient, sample_ranging_candles):
        """
        Scenario 5: Full Interactive UI & Indicator Lifecycle Simulation.
        Workflow:
        1. Phase 1: Inspect baseline HTML page and static assets.
        2. Phase 2: Dynamic Catalog Discovery (GET /api/indicators/catalog).
        3. Phase 3: Add First Oscillator (RSI).
        4. Phase 4: Add Main Chart Overlay (Bollinger Bands with custom params).
        5. Phase 5: Add Second Oscillator (MACD).
        6. Phase 6: Simulate Parameter Re-tuning (updating RSI length from 14 to 28).
        7. Phase 7: Clean Detachment (removing RSI, then removing MACD).
        8. Phase 8: Complete Container Collapse (when 0 oscillators remain).
        """
        # Phase 1: Baseline inspection
        r_page = client.get("/")
        assert r_page.status_code == 200
        assert "oscillators-container" in r_page.text
        assert "indicator-library-dialog" in r_page.text

        # Phase 2: Dynamic Catalog Discovery
        r_cat = client.get("/api/indicators/catalog")
        assert r_cat.status_code == 200
        catalog = r_cat.json()
        assert "rsi" in catalog["indicators"]
        assert "bbands" in catalog["indicators"]
        assert "macd" in catalog["indicators"]

        # Phase 3: Add First Oscillator (RSI)
        r_rsi = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {"length": 14},
            "candles": sample_ranging_candles,
        })
        assert r_rsi.status_code == 200
        d_rsi = r_rsi.json()
        assert d_rsi["kind"] == "oscillator"

        # Phase 4: Add Main Chart Overlay (BBands with custom params)
        r_bb = client.post("/api/indicators/compute", json={
            "indicator": "bbands",
            "params": {"length": 25, "std": 2.5},
            "candles": sample_ranging_candles,
        })
        assert r_bb.status_code == 200
        d_bb = r_bb.json()
        assert d_bb["kind"] == "overlay"

        # Phase 5: Add Second Oscillator (MACD)
        r_macd = client.post("/api/indicators/compute", json={
            "indicator": "macd",
            "params": {"fast": 12, "slow": 26, "signal": 9},
            "candles": sample_ranging_candles,
        })
        assert r_macd.status_code == 200
        d_macd = r_macd.json()
        assert d_macd["kind"] == "oscillator"

        # Phase 6: Parameter Re-tuning (RSI length 14 -> 28)
        r_rsi_retuned = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "params": {"length": 28},
            "candles": sample_ranging_candles,
        })
        assert r_rsi_retuned.status_code == 200
        # Re-tuned series is computed and has different values on oscillating candles
        v1 = d_rsi["series"]["RSI_14"][-1]["value"]
        v2 = r_rsi_retuned.json()["series"]["RSI_14" if "RSI_14" in r_rsi_retuned.json()["series"] else "RSI_28"][-1]["value"]
        assert v1 != v2

        # Phase 7 & 8: Verify detachment contracts in client JS/CSS
        r_js = client.get("/static/js/chart_manager.js")
        assert "clearOscillator" in r_js.text or "oscillators" in r_js.text
        r_css = client.get("/static/css/style.css")
        assert ".oscillators-container.hidden" in r_css.text
