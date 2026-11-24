"""
Test Suite: pandas_ta Indicator Engine & API Endpoints
Verifies:
- Indicator catalog discovery & schema validation across all categories
- Placement classification: overlay vs oscillator
- Dynamic indicator computation across 5 standard categories (momentum, overlap, trend, volatility, volume)
- Custom user parameter overrides (e.g. length, std, fast/slow/signal)
- Renko brick indicator computation and timestamp alignment
- Warm-up period & insufficient bar resilience (warning, no crash)
- Invalid indicator & parameter error handling (HTTP 400 with detail)
- JSON serialization & NaN/Infinity sanitization (nulls instead of invalid floats)
- FastAPI TestClient integration for GET and POST endpoints
"""

import json
import math
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import app
import core.ta_engine as ta_engine


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def sample_candles():
    """Generates 60 realistic sample 1-minute OHLCV candles."""
    candles = []
    base_time = 1700000000
    base_price = 1.2500

    for i in range(60):
        t = base_time + (i * 60)
        # Deterministic price oscillation
        change = math.sin(i / 5.0) * 0.0050 + (i * 0.0002)
        c = round(base_price + change, 5)
        o = round(c - 0.0004, 5)
        h = round(max(o, c) + 0.0005, 5)
        l = round(min(o, c) - 0.0005, 5)
        vol = float(100 + (i * 10))

        candles.append({
            "time": t,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": vol
        })
    return candles


# ==============================================================================
# 1. Catalog Endpoint & Discovery Tests
# ==============================================================================

def test_catalog_endpoint_success(client):
    """GET /api/indicators/catalog returns 200 with categories and indicators."""
    resp = client.get("/api/indicators/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert "indicators" in data

    # Verify standard 5 categories plus extra categories
    expected_categories = ["momentum", "overlap", "trend", "volatility", "volume"]
    for cat in expected_categories:
        assert cat in data["categories"], f"Missing category {cat}"

    # Verify total count exceeds 140 indicators
    indicators = data["indicators"]
    assert len(indicators) >= 140, f"Expected at least 140 indicators, got {len(indicators)}"


def test_catalog_indicator_schema(client):
    """Verifies that catalog indicators have the required schema fields."""
    resp = client.get("/api/indicators/catalog")
    assert resp.status_code == 200
    indicators = resp.json()["indicators"]

    for ind_id, ind in indicators.items():
        assert ind["id"] == ind_id
        assert isinstance(ind["name"], str) and len(ind["name"]) > 0
        assert isinstance(ind["category"], str)
        assert ind["kind"] in ("overlay", "oscillator")
        assert isinstance(ind["inputs"], list) and len(ind["inputs"]) > 0
        assert isinstance(ind["params"], list)
        assert isinstance(ind["outputs"], list) and len(ind["outputs"]) > 0

        # Validate params schema
        for p in ind["params"]:
            assert "name" in p
            assert "type" in p
            assert p["type"] in ("int", "float", "str", "bool")

        # Validate outputs schema
        for o in ind["outputs"]:
            assert "name" in o
            assert "type" in o
            assert "color" in o


def test_catalog_kind_classification(client):
    """Verifies overlay vs oscillator placement classification."""
    resp = client.get("/api/indicators/catalog")
    indicators = resp.json()["indicators"]

    # Overlays
    assert indicators["sma"]["kind"] == "overlay"
    assert indicators["ema"]["kind"] == "overlay"
    assert indicators["bbands"]["kind"] == "overlay"
    assert indicators["supertrend"]["kind"] == "overlay"
    assert indicators["vwap"]["kind"] == "overlay"

    # Oscillators
    assert indicators["rsi"]["kind"] == "oscillator"
    assert indicators["macd"]["kind"] == "oscillator"
    assert indicators["stoch"]["kind"] == "oscillator"
    assert indicators["atr"]["kind"] == "oscillator"
    assert indicators["adx"]["kind"] == "oscillator"
    assert indicators["obv"]["kind"] == "oscillator"


# ==============================================================================
# 2. Calculation Across Representative Indicators in All 5 Categories
# ==============================================================================

@pytest.mark.parametrize("ind_id,expected_key", [
    ("rsi", "RSI_14"),
    ("macd", "macd"),
    ("stoch", "k"),
    ("sma", "SMA_10"),
    ("ema", "EMA_10"),
    ("bbands", "upper"),
    ("atr", "ATRr_14"),
    ("adx", "adx"),
    ("obv", "OBV"),
    ("vwap", "VWAP_D"),
])
def test_compute_representative_indicators(client, sample_candles, ind_id, expected_key):
    """Verifies calculation of representative indicators across all 5 standard categories."""
    payload = {
        "indicator": ind_id,
        "candles": sample_candles
    }
    resp = client.post("/api/indicators/compute", json=payload)
    assert resp.status_code == 200, f"Failed for {ind_id}: {resp.text}"
    data = resp.json()

    assert data["indicator"] == ind_id
    assert data["warning"] is None
    assert expected_key in data["series"], f"Key '{expected_key}' not in {list(data['series'].keys())}"

    series = data["series"][expected_key]
    assert len(series) == len(sample_candles)

    # Verify that valid float points exist in the series
    valid_points = [p for p in series if p["value"] is not None]
    assert len(valid_points) > 0, f"No valid points calculated for {ind_id}"
    assert isinstance(valid_points[-1]["value"], (int, float))


# ==============================================================================
# 3. Custom Parameter Overrides
# ==============================================================================

def test_custom_parameters_rsi(client, sample_candles):
    """Verifies that overriding length for RSI modifies calculated series."""
    resp14 = client.post("/api/indicators/compute", json={"indicator": "rsi", "params": {"length": 14}, "candles": sample_candles})
    resp21 = client.post("/api/indicators/compute", json={"indicator": "rsi", "params": {"length": 21}, "candles": sample_candles})

    assert resp14.status_code == 200
    assert resp21.status_code == 200

    val14 = resp14.json()["series"]["RSI_14"][-1]["value"]
    val21 = resp21.json()["series"]["RSI_21"][-1]["value"]

    assert val14 is not None and val21 is not None
    assert val14 != val21, "Different RSI lengths should produce different numeric values"


def test_custom_parameters_bbands(client, sample_candles):
    """Verifies custom std for BBANDS widens the bands."""
    resp_std20 = client.post("/api/indicators/compute", json={"indicator": "bbands", "params": {"length": 20, "std": 2.0}, "candles": sample_candles})
    resp_std25 = client.post("/api/indicators/compute", json={"indicator": "bbands", "params": {"length": 20, "std": 2.5}, "candles": sample_candles})

    assert resp_std20.status_code == 200
    assert resp_std25.status_code == 200

    upper20 = resp_std20.json()["series"]["upper"][-1]["value"]
    lower20 = resp_std20.json()["series"]["lower"][-1]["value"]
    upper25 = resp_std25.json()["series"]["upper"][-1]["value"]
    lower25 = resp_std25.json()["series"]["lower"][-1]["value"]

    band_width_20 = upper20 - lower20
    band_width_25 = upper25 - lower25
    assert band_width_25 > band_width_20, "std=2.5 should yield wider Bollinger Bands than std=2.0"


def test_custom_parameters_macd(client, sample_candles):
    """Verifies custom fast/slow/signal parameters for MACD."""
    payload = {
        "indicator": "macd",
        "params": {"fast": 8, "slow": 17, "signal": 9},
        "candles": sample_candles
    }
    resp = client.post("/api/indicators/compute", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "macd" in data["series"]
    assert "signal" in data["series"]
    assert "histogram" in data["series"]
    assert data["series"]["macd"][-1]["value"] is not None


# ==============================================================================
# 4. Renko Brick Calculation & Timestamp Alignment
# ==============================================================================

def test_renko_brick_calculation_and_alignment(client):
    """Verifies indicator calculation directly on Renko bricks with timestamp alignment."""
    # First get actual Renko bricks from /api/renko to compare timestamps
    renko_resp = client.get("/api/renko?symbol=GBPUSD&brick_size=0.00035&limit=50&timeline_mode=equidistant")
    assert renko_resp.status_code == 200
    renko_data = renko_resp.json()
    bricks = renko_data["bricks"]
    expected_times = [b["time"] for b in bricks]

    # Compute RSI directly on bricks
    compute_resp = client.post("/api/indicators/compute", json={
        "indicator": "rsi",
        "params": {"length": 14},
        "candles": bricks
    })
    assert compute_resp.status_code == 200
    result = compute_resp.json()
    assert result["indicator"] == "rsi"
    rsi_series = result["series"]["RSI_14"]

    # Verify timestamps match exactly 1:1 with input bricks
    result_times = [p["time"] for p in rsi_series]
    assert result_times == expected_times, "Indicator timestamps must match Renko brick timestamps identically"

    # Also test computing via renko_params
    renko_param_resp = client.post("/api/indicators/compute", json={
        "indicator": "rsi",
        "params": {"length": 14},
        "renko_params": {
            "symbol": "GBPUSD",
            "brick_size": 0.00035,
            "timeline_mode": "equidistant",
            "limit": 50
        }
    })
    assert renko_param_resp.status_code == 200
    param_data = renko_param_resp.json()
    assert len(param_data["series"]["RSI_14"]) > 0
    param_times = [p["time"] for p in param_data["series"]["RSI_14"]]
    # Verify equidistant timeline spacing
    for i in range(1, len(param_times)):
        assert param_times[i] - param_times[i-1] == 60


def test_renko_brick_real_timeline_alignment(client):
    """Verifies indicator calculation on Renko bricks under real timeline mode."""
    compute_resp = client.post("/api/indicators/compute", json={
        "indicator": "sma",
        "params": {"length": 5},
        "renko_params": {
            "symbol": "GBPUSD",
            "brick_size": 0.00035,
            "timeline_mode": "real",
            "limit": 40
        }
    })
    assert compute_resp.status_code == 200
    data = compute_resp.json()
    assert len(data["series"]) > 0


# ==============================================================================
# 5. Warm-up Period & Insufficient Bars Resilience
# ==============================================================================

def test_insufficient_bars_short_candle_list(client):
    """Verifies that providing fewer bars than indicator length returns clean 200 with warning."""
    short_candles = [
        {"time": 1700000000, "open": 1.25, "high": 1.251, "low": 1.249, "close": 1.250, "volume": 100},
        {"time": 1700000060, "open": 1.25, "high": 1.252, "low": 1.249, "close": 1.251, "volume": 120},
    ]
    resp = client.post("/api/indicators/compute", json={
        "indicator": "rsi",
        "params": {"length": 14},
        "candles": short_candles
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["indicator"] == "rsi"
    assert data["warning"] is not None
    assert "Insufficient bars" in data["warning"]
    assert data["series"] == {"RSI_14": []}


def test_insufficient_bars_empty_candles(client):
    """Verifies that empty candle array returns 200 with warning and does not crash."""
    resp = client.post("/api/indicators/compute", json={
        "indicator": "rsi",
        "candles": []
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["indicator"] == "rsi"
    assert data["warning"] is not None
    assert "Insufficient bars" in data["warning"]
    assert data["series"] == {"RSI_14": []}


# ==============================================================================
# 6. Invalid Indicator Name & Parameter Values (HTTP 400)
# ==============================================================================

def test_unknown_indicator_name(client, sample_candles):
    """POST /api/indicators/compute returns 400 for unknown indicator."""
    resp = client.post("/api/indicators/compute", json={
        "indicator": "non_existent_indicator_xyz",
        "candles": sample_candles
    })
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "Unknown indicator 'non_existent_indicator_xyz'" in detail
    assert "Check /api/indicators/catalog" in detail


def test_invalid_parameter_negative_length(client, sample_candles):
    """POST /api/indicators/compute returns 400 for negative length parameter."""
    resp = client.post("/api/indicators/compute", json={
        "indicator": "rsi",
        "params": {"length": -5},
        "candles": sample_candles
    })
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "Invalid parameter 'length'" in detail
    assert "must be positive integer" in detail


def test_invalid_parameter_non_integer_length(client, sample_candles):
    """POST /api/indicators/compute returns 400 for non-integer length string."""
    resp = client.post("/api/indicators/compute", json={
        "indicator": "rsi",
        "params": {"length": "not_a_number"},
        "candles": sample_candles
    })
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "Invalid parameter 'length'" in detail


def test_invalid_macd_parameters_fast_ge_slow(client, sample_candles):
    """POST /api/indicators/compute returns 400 when MACD fast >= slow."""
    resp = client.post("/api/indicators/compute", json={
        "indicator": "macd",
        "params": {"fast": 26, "slow": 12},
        "candles": sample_candles
    })
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "fast period must be less than slow period" in detail


def test_missing_data_payload(client):
    """POST /api/indicators/compute returns 400 when neither candles nor renko_params provided."""
    resp = client.post("/api/indicators/compute", json={
        "indicator": "rsi"
    })
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "Must provide either 'candles' array or 'renko_params'" in detail


def test_missing_indicator_field(client, sample_candles):
    """POST /api/indicators/compute returns 400 when 'indicator' field is missing."""
    resp = client.post("/api/indicators/compute", json={
        "candles": sample_candles
    })
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "Missing 'indicator' parameter" in detail


# ==============================================================================
# 7. NaN / Infinity Sanitization & JSON Compliance
# ==============================================================================

def test_nan_infinity_sanitization(client, sample_candles):
    """Verifies that warm-up NaNs are converted to None (null) for valid JSON serialization."""
    resp = client.post("/api/indicators/compute", json={
        "indicator": "sma",
        "params": {"length": 10},
        "candles": sample_candles
    })
    assert resp.status_code == 200

    # Ensure json.dumps succeeds without ValueError: Out of range float values
    raw_text = resp.text
    parsed = json.loads(raw_text)
    series = parsed["series"]["SMA_10"]

    # Initial 9 bars for SMA 10 must be null (None in Python)
    initial_values = [p["value"] for p in series[:9]]
    assert all(v is None for v in initial_values), "Warm-up period bars should be null/None"

    # Subsequent bars should have valid float values
    later_values = [p["value"] for p in series[10:]]
    assert any(isinstance(v, (int, float)) for v in later_values)


def test_direct_nan_and_infinity_in_data_sanitization(client):
    """Verifies that if candles have missing/None values, result sanitizes cleanly to None."""
    candles_with_none = [
        {"time": 1700000000 + i * 60, "open": 10.0, "high": 12.0, "low": 8.0, "close": 10.0, "volume": 100.0}
        for i in range(25)
    ]
    # Inject None (JSON null) into a middle bar
    candles_with_none[15]["close"] = None

    resp = client.post("/api/indicators/compute", json={
        "indicator": "sma",
        "params": {"length": 5},
        "candles": candles_with_none
    })
    assert resp.status_code == 200
    # Must serialize to strict valid JSON
    raw_text = resp.text
    assert "NaN" not in raw_text, "Response must not contain non-standard NaN string"
    assert "Infinity" not in raw_text, "Response must not contain non-standard Infinity string"
    parsed = json.loads(raw_text)
    assert parsed["warning"] is None
    # Verify that point 15 or following points sanitize cleanly to None
    series = parsed["series"]["SMA_5"]
    assert any(p["value"] is None for p in series[15:20])


# ==============================================================================
# 8. GET Endpoint Integration Tests
# ==============================================================================

def test_get_compute_endpoint(client):
    """GET /api/indicators/compute calculates indicator on Renko bricks with query params."""
    resp = client.get("/api/indicators/compute?indicator=rsi&length=14&symbol=GBPUSD&brick_size=0.00035&limit=50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["indicator"] == "rsi"
    assert "RSI_14" in data["series"]
    assert len(data["series"]["RSI_14"]) > 0


def test_get_compute_endpoint_unknown_indicator(client):
    """GET /api/indicators/compute returns 400 for unknown indicator."""
    resp = client.get("/api/indicators/compute?indicator=unknown_ind_test")
    assert resp.status_code == 400
    assert "Unknown indicator 'unknown_ind_test'" in resp.json()["detail"]
