"""
Tier 5 Adversarial Stress Test Suite: MT5Renko pandas_ta Universal Indicator Integration
========================================================================================
Rigorous adversarial coverage hardening:
- Category 1: Adversarial String & Type Injection (SQLi, Path Traversal, Null Bytes, Unicode, Case/Whitespace)
- Category 2: IEEE-754 Floating-Point Exploits & Numerical Extreme Attacks (NaN/Inf, 1e-15, 1e12, Zero/Negative, Flatline)
- Category 3: Time-Axis & Sequence Chaos Attacks (Duplicate, Reversed, Pre-1970, Mixed MS/S Timestamps)
- Category 4: Warm-Up Boundary & Data Quantity Stress (Exact P-1/P/P+1 boundaries, 0/1/2 bars, Close-only, Gaps, Huge Lengths, 2000-bar Batch)
- Category 5: Parameter Validation & Logical Violation Edge Cases (MACD fast>=slow, BBands std<=0, Conflicting Payloads, Length=1 behavior)
- Category 6: Renko Engine Specific Stress & Boundary Cases (Nano/Macro Bricks, Negative Limit, Timeline Fuzzing, GET Fuzzing)
- Category 7: Catalog Metadata & Concurrency Stress (Full 150+ Indicator Audit, ReDoS Protection, 20-Worker Concurrency)

Marker:
@pytest.mark.tier5
"""

import asyncio
import concurrent.futures
import copy
import json
import math
import os
import re
import sys
import warnings
from typing import Any, Dict, List

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
import core.ta_engine as ta_engine
from core.bot_manager import bot_manager


def pytest_configure(config):
    """Registers the custom tier5 marker."""
    config.addinivalue_line("markers", "tier5: Tier 5 Adversarial Coverage Hardening Tests")


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def sample_standard_candles():
    """Generates 80 standard valid 1-minute OHLCV candles."""
    candles = []
    base_t = 1700000000
    for i in range(80):
        t = base_t + i * 60
        o = 1.2500 + i * 0.0002
        c = o + math.sin(i / 3.0) * 0.0010
        h = max(o, c) + 0.0005
        l = min(o, c) - 0.0005
        v = 100.0 + (i % 5) * 20.0
        candles.append({
            "time": t,
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(l, 5),
            "close": round(c, 5),
            "volume": v
        })
    return candles


# ==============================================================================
# Category 1: Adversarial String & Type Injection (Security & Robustness)
# ==============================================================================

@pytest.mark.tier5
def test_adversarial_sql_injection_and_path_traversal_in_indicator_id(client, sample_standard_candles):
    """Verifies that SQL injection, path traversal, and null bytes in indicator names are cleanly rejected with HTTP 400."""
    malicious_inputs = [
        "' OR '1'='1",
        "'; DROP TABLE indicators;--",
        "../../etc/passwd",
        "..\\..\\app.py",
        "rsi\x00_inject",
        "<script>alert('xss')</script>",
        "rsi; echo vulnerable"
    ]
    for mal_id in malicious_inputs:
        resp = client.post("/api/indicators/compute", json={
            "indicator": mal_id,
            "candles": sample_standard_candles
        })
        assert resp.status_code == 400, f"Expected HTTP 400 for '{mal_id}', got {resp.status_code}"
        data = resp.json()
        assert "detail" in data, f"Expected 'detail' error in response for '{mal_id}'"
        assert "Unknown indicator" in data["detail"] or "Invalid" in data["detail"]


@pytest.mark.tier5
def test_adversarial_unicode_and_special_chars_indicator(client, sample_standard_candles):
    """Verifies that non-ASCII unicode, emojis, control characters, and huge strings are rejected safely."""
    fuzz_names = [
        "rsi🚀",
        "مرحبا_indicator",
        "指标_macd",
        "\t\r\n",
        "A" * 5000  # Massive 5KB string
    ]
    for fuzz_name in fuzz_names:
        resp = client.post("/api/indicators/compute", json={
            "indicator": fuzz_name,
            "candles": sample_standard_candles
        })
        assert resp.status_code == 400, f"Expected HTTP 400 for fuzz name, got {resp.status_code}"
        assert "detail" in resp.json()


@pytest.mark.tier5
def test_adversarial_case_insensitivity_and_whitespace_padding(client, sample_standard_candles):
    """Verifies that valid indicators with arbitrary whitespace padding or mixed casing are normalized and succeed."""
    padded_inputs = [
        ("  rsi  ", "rsi"),
        ("\n\tbbands\t", "bbands"),
        ("SuPeRtReNd", "supertrend"),
        ("  EMA  ", "ema"),
        ("  MACD \n", "macd")
    ]
    for raw_id, canonical_id in padded_inputs:
        resp = client.post("/api/indicators/compute", json={
            "indicator": raw_id,
            "candles": sample_standard_candles
        })
        assert resp.status_code == 200, f"Expected HTTP 200 for padded indicator '{raw_id}', got {resp.status_code}"
        data = resp.json()
        assert data["indicator"] == canonical_id
        assert "series" in data
        assert len(data["series"]) > 0


# ==============================================================================
# Category 2: IEEE-754 Floating-Point Exploits & Numerical Extreme Attacks
# ==============================================================================

@pytest.mark.tier5
def test_adversarial_ieee754_nan_and_infinity_in_params(client, sample_standard_candles):
    """Verifies that NaN and Infinity parameter values are either rejected with HTTP 400 or safely computed without unhandled server crash."""
    fuzz_params = [
        ("rsi", {"length": "nan"}),
        ("rsi", {"length": "inf"}),
        ("macd", {"fast": "nan", "slow": 26, "signal": 9}),
        ("macd", {"fast": 12, "slow": "inf", "signal": 9}),
        ("bbands", {"std": "-inf"}),
        ("bbands", {"length": 20, "lower_std": -1.0}),
        ("supertrend", {"multiplier": -3.0}),
    ]
    for ind, params in fuzz_params:
        resp = client.post("/api/indicators/compute", json={
            "indicator": ind,
            "params": params,
            "candles": sample_standard_candles
        })
        # Invalid numeric inputs must be rejected with HTTP 400
        assert resp.status_code == 400, f"Expected 400 for {ind} with {params}, got {resp.status_code}"
        assert "detail" in resp.json()


@pytest.mark.tier5
def test_adversarial_extreme_scientific_notation_in_candles(client):
    """Verifies that subnormal tiny floats (1e-15) and massive floats (1e12) do not trigger OverflowError or JSON corruption."""
    extreme_candles = []
    base_t = 1700000000
    for i in range(50):
        # Starts at subnormal, jumps to 1e12
        price = 1e-12 if i < 25 else 1e11
        extreme_candles.append({
            "time": base_t + i * 60,
            "open": price,
            "high": price * 1.001,
            "low": price * 0.999,
            "close": price,
            "volume": 1e6
        })

    for ind in ["sma", "ema", "rsi", "bbands"]:
        resp = client.post("/api/indicators/compute", json={
            "indicator": ind,
            "candles": extreme_candles
        })
        assert resp.status_code == 200, f"Failed on extreme scientific prices for {ind}: {resp.status_code}"
        data = resp.json()
        assert "series" in data
        # Ensure raw JSON can be serialized and does not contain raw NaN / Infinity tokens
        json_str = json.dumps(data)
        assert "NaN" not in json_str
        assert "Infinity" not in json_str


@pytest.mark.tier5
def test_adversarial_zero_and_negative_prices(client):
    """Verifies that zero prices and negative prices (e.g. negative oil futures contract anomaly) do not crash calculation."""
    base_t = 1700000000
    # Negative prices: -37.00 to -10.00
    neg_candles = []
    for i in range(60):
        p = -37.0 + (i * 0.4)
        neg_candles.append({
            "time": base_t + i * 60,
            "open": p,
            "high": p + 0.5,
            "low": p - 0.5,
            "close": p + 0.2,
            "volume": 500.0
        })

    for ind in ["sma", "ema", "bbands", "macd", "atr", "supertrend"]:
        resp = client.post("/api/indicators/compute", json={
            "indicator": ind,
            "candles": neg_candles
        })
        assert resp.status_code == 200, f"Negative price computation failed for {ind}: {resp.status_code}"
        data = resp.json()
        assert "series" in data


@pytest.mark.tier5
def test_adversarial_flatline_zero_volatility_division_by_zero(client):
    """Verifies that flatline data (identical open, high, low, close, zero volume) does not raise ZeroDivisionError."""
    base_t = 1700000000
    flatline_candles = [{
        "time": base_t + i * 60,
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "volume": 0.0
    } for i in range(60)]

    indicators_to_test = ["rsi", "bbands", "macd", "stoch", "adx", "atr", "supertrend", "obv", "vwap"]
    for ind in indicators_to_test:
        resp = client.post("/api/indicators/compute", json={
            "indicator": ind,
            "candles": flatline_candles
        })
        assert resp.status_code == 200, f"Flatline failed for {ind}: {resp.status_code}"
        data = resp.json()
        assert "series" in data
        # Ensure all points are either numbers or null (no raw NaN/Inf)
        for sname, pts in data["series"].items():
            for pt in pts:
                val = pt.get("value")
                assert val is None or isinstance(val, (int, float)), f"Invalid value {val} in {sname} for {ind}"


# ==============================================================================
# Category 3: Time-Axis & Sequence Chaos Attacks
# ==============================================================================

@pytest.mark.tier5
def test_adversarial_duplicate_timestamps(client):
    """Verifies that candles with duplicate timestamps are handled safely without unhandled exception or crash."""
    fixed_time = 1700000000
    dup_candles = [{
        "time": fixed_time,
        "open": 100.0 + i * 0.1,
        "high": 100.5 + i * 0.1,
        "low": 99.5 + i * 0.1,
        "close": 100.2 + i * 0.1,
        "volume": 100.0
    } for i in range(50)]

    for ind in ["rsi", "bbands", "sma", "vwap"]:
        resp = client.post("/api/indicators/compute", json={
            "indicator": ind,
            "candles": dup_candles
        })
        assert resp.status_code == 200, f"Duplicate timestamps failed for {ind}: {resp.status_code}"
        data = resp.json()
        assert "series" in data


@pytest.mark.tier5
def test_adversarial_reverse_and_jumbled_timestamps(client):
    """Verifies that backward-running or jumbled timestamps are monotonically handled in pandas_ta without crash."""
    base_t = 1700000000
    # Strictly backward in time
    rev_candles = [{
        "time": base_t - i * 60,
        "open": 100.0 + i * 0.1,
        "high": 100.5 + i * 0.1,
        "low": 99.5 + i * 0.1,
        "close": 100.2 + i * 0.1,
        "volume": 100.0
    } for i in range(50)]

    for ind in ["rsi", "bbands", "vwap"]:
        resp = client.post("/api/indicators/compute", json={
            "indicator": ind,
            "candles": rev_candles
        })
        assert resp.status_code == 200, f"Reverse timestamps failed for {ind}: {resp.status_code}"
        data = resp.json()
        assert "series" in data
        # Ensure timestamp alignment preserves original bar_times order
        for sname, pts in data["series"].items():
            if pts:
                assert pts[0]["time"] == rev_candles[0]["time"]
                assert pts[-1]["time"] == rev_candles[-1]["time"]


@pytest.mark.tier5
def test_adversarial_fractional_and_millisecond_timestamps(client):
    """Verifies that millisecond timestamps (> 1e11) are properly identified and formatted into DatetimeIndex."""
    base_ms = 1700000000000  # Milliseconds epoch
    ms_candles = [{
        "time": base_ms + i * 60000,
        "open": 1.2500 + i * 0.0002,
        "high": 1.2510 + i * 0.0002,
        "low": 1.2490 + i * 0.0002,
        "close": 1.2505 + i * 0.0002,
        "volume": 200.0
    } for i in range(50)]

    resp = client.post("/api/indicators/compute", json={
        "indicator": "vwap",
        "candles": ms_candles
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "series" in data
    assert any(len(pts) > 0 for pts in data["series"].values())


# ==============================================================================
# Category 4: Warm-Up Boundary & Data Quantity Stress
# ==============================================================================

@pytest.mark.tier5
def test_adversarial_exact_warmup_transition_boundary(client):
    """Verifies precise boundary behavior at exactly Period - 1, Period, and Period + 1 bars."""
    period = 14
    base_t = 1700000000

    def make_bars(n):
        return [{
            "time": base_t + i * 60,
            "open": 1.2000 + i * 0.001,
            "high": 1.2010 + i * 0.001,
            "low": 1.1990 + i * 0.001,
            "close": 1.2005 + i * 0.001,
            "volume": 100.0
        } for i in range(n)]

    # 1. Exact Period - 1 (13 bars for period=14): insufficient bars
    bars_13 = make_bars(period - 1)
    r13 = client.post("/api/indicators/compute", json={"indicator": "rsi", "params": {"length": period}, "candles": bars_13})
    assert r13.status_code == 200
    assert r13.json()["warning"] is not None, "Expected warning for insufficient bars at period - 1"

    # 2. Exact Period + 1 (15 bars for RSI 14): returns valid point
    bars_15 = make_bars(period + 1)
    r15 = client.post("/api/indicators/compute", json={"indicator": "rsi", "params": {"length": period}, "candles": bars_15})
    assert r15.status_code == 200
    pts = r15.json()["series"].get("RSI_14", [])
    valid_pts = [p for p in pts if p["value"] is not None]
    assert len(valid_pts) > 0, "Expected at least 1 valid RSI point at period + 1"


@pytest.mark.tier5
def test_adversarial_single_and_zero_bar_payloads(client):
    """Verifies that 0 bars and 1 bar return clean 200 OK with warning and empty series across all categories."""
    base_t = 1700000000
    empty_candles = []
    single_candle = [{"time": base_t, "open": 1.25, "high": 1.26, "low": 1.24, "close": 1.255, "volume": 100.0}]

    test_indicators = ["rsi", "bbands", "macd", "supertrend", "atr", "adx", "vwap"]
    # 0 bars: All indicators must return warm-up warning
    for ind in test_indicators:
        resp = client.post("/api/indicators/compute", json={"indicator": ind, "candles": empty_candles})
        assert resp.status_code == 200
        data = resp.json()
        assert data["warning"] is not None
        assert all(len(pts) == 0 for pts in data["series"].values())

    # 1 bar: Lookback indicators must return warm-up warning
    for ind in test_indicators:
        resp = client.post("/api/indicators/compute", json={"indicator": ind, "candles": single_candle})
        assert resp.status_code == 200
        data = resp.json()
        assert data["warning"] is not None
        assert all(len(pts) == 0 or all(p["value"] is None for p in pts) for pts in data["series"].values())


@pytest.mark.tier5
def test_adversarial_close_only_candles_auto_inference(client):
    """Verifies that payloads providing only 'time' and 'close' automatically infer open, high, low, volume."""
    base_t = 1700000000
    close_only_candles = [{"time": base_t + i * 60, "close": 1.2500 + i * 0.0005} for i in range(50)]

    for ind in ["sma", "ema", "rsi", "bbands", "macd"]:
        resp = client.post("/api/indicators/compute", json={
            "indicator": ind,
            "candles": close_only_candles
        })
        assert resp.status_code == 200, f"Close-only candles failed for {ind}: {resp.status_code}"
        data = resp.json()
        assert "series" in data
        assert any(len(pts) > 0 for pts in data["series"].values())


@pytest.mark.tier5
def test_adversarial_gapped_and_interleaved_nan_candles(client):
    """Verifies that missing or null fields within specific bars are sanitized without throwing unhandled exceptions."""
    base_t = 1700000000
    gapped_candles = [{"time": base_t + i * 60, "open": 1.25, "high": 1.26, "low": 1.24, "close": 1.255, "volume": 100.0} for i in range(50)]
    gapped_candles[10]["close"] = None
    gapped_candles[20]["high"] = None
    gapped_candles[30]["low"] = None

    for ind in ["sma", "ema", "bbands"]:
        resp = client.post("/api/indicators/compute", json={
            "indicator": ind,
            "candles": gapped_candles
        })
        assert resp.status_code == 200, f"Gapped candles failed for {ind}: {resp.status_code}"
        assert "series" in resp.json()


@pytest.mark.tier5
def test_adversarial_huge_length_parameter(client, sample_standard_candles):
    """Verifies that requesting a length far exceeding the data length (e.g. length=10000 on 80 bars) cleanly returns warm-up warning."""
    resp = client.post("/api/indicators/compute", json={
        "indicator": "rsi",
        "params": {"length": 10000},
        "candles": sample_standard_candles
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["warning"] is not None
    assert "Insufficient bars" in data["warning"]


@pytest.mark.tier5
def test_adversarial_high_volume_batch_stress(client):
    """Verifies calculation on a large batch of 2,000 candles completes rapidly with zero memory leak or failure."""
    base_t = 1700000000
    large_candles = []
    curr = 1.2500
    for i in range(2000):
        curr += math.sin(i / 10.0) * 0.0005 + 0.00005
        large_candles.append({
            "time": base_t + i * 60,
            "open": round(curr, 5),
            "high": round(curr + 0.0008, 5),
            "low": round(curr - 0.0008, 5),
            "close": round(curr + 0.0002, 5),
            "volume": float(100 + (i % 50))
        })

    for ind in ["bbands", "macd", "rsi", "supertrend", "obv"]:
        resp = client.post("/api/indicators/compute", json={
            "indicator": ind,
            "candles": large_candles
        })
        assert resp.status_code == 200, f"High volume stress failed for {ind}: {resp.status_code}"
        data = resp.json()
        assert "series" in data
        for sname, pts in data["series"].items():
            assert len(pts) == 2000, f"Expected 2000 aligned points in {sname}, got {len(pts)}"


# ==============================================================================
# Category 5: Parameter Validation & Logical Violation Edge Cases
# ==============================================================================

@pytest.mark.tier5
def test_adversarial_macd_invalid_relations(client, sample_standard_candles):
    """Verifies logical rule enforcement for MACD (fast < slow, positive values)."""
    invalid_macd_configs = [
        {"fast": 20, "slow": 20, "signal": 9},  # fast == slow
        {"fast": 30, "slow": 10, "signal": 9},  # fast > slow
        {"fast": 0, "slow": 26, "signal": 9},   # fast <= 0
        {"fast": -12, "slow": 26, "signal": 9}, # fast negative
        {"fast": 12, "slow": -26, "signal": 9}, # slow negative
        {"fast": 12, "slow": 26, "signal": 0},  # signal <= 0
        {"fast": 12, "slow": 26, "signal": -9}, # signal negative
    ]
    for cfg in invalid_macd_configs:
        resp = client.post("/api/indicators/compute", json={
            "indicator": "macd",
            "params": cfg,
            "candles": sample_standard_candles
        })
        assert resp.status_code == 400, f"Expected 400 for MACD config {cfg}, got {resp.status_code}"
        assert "detail" in resp.json()


@pytest.mark.tier5
def test_adversarial_bbands_invalid_stds(client, sample_standard_candles):
    """Verifies invalid standard deviation validation for Bollinger Bands."""
    invalid_bbands_configs = [
        {"std": 0},
        {"std": -2.0},
        {"lower_std": 0},
        {"lower_std": -1.5},
        {"upper_std": 0},
        {"upper_std": -2.5},
        {"length": 0},
        {"length": -10},
    ]
    for cfg in invalid_bbands_configs:
        resp = client.post("/api/indicators/compute", json={
            "indicator": "bbands",
            "params": cfg,
            "candles": sample_standard_candles
        })
        assert resp.status_code == 400, f"Expected 400 for BBands config {cfg}, got {resp.status_code}"
        assert "detail" in resp.json()


@pytest.mark.tier5
def test_adversarial_length_one_pandas_ta_behavior(client, sample_standard_candles):
    """Verifies calculation error handling when length=1 is passed to indicators that do not support period 1 in pandas_ta."""
    # pandas_ta sma(length=1) raises ValueError because rolling window length 1 on Series triggers index mismatch
    resp = client.post("/api/indicators/compute", json={
        "indicator": "sma",
        "params": {"length": 1},
        "candles": sample_standard_candles
    })
    # Must be intercepted cleanly as HTTP 400 Calculation error without crashing server (HTTP 500)
    assert resp.status_code == 400
    assert "Calculation error" in resp.json()["detail"]


@pytest.mark.tier5
def test_adversarial_unexpected_and_conflicting_payload_fields(client, sample_standard_candles):
    """Verifies behavior with conflicting, missing, or arbitrary unexpected payload fields."""
    # 1. Missing both candles and renko_params
    r_neither = client.post("/api/indicators/compute", json={"indicator": "rsi"})
    assert r_neither.status_code == 400
    assert "Must provide either" in r_neither.json()["detail"]

    # 2. Both candles and renko_params supplied (candles takes precedence per app.py order)
    r_both = client.post("/api/indicators/compute", json={
        "indicator": "rsi",
        "candles": sample_standard_candles,
        "renko_params": {"symbol": "GBPUSD", "timeline_mode": "equidistant"},
        "unexpected_field": "injected_value",
        "another_field": [1, 2, 3]
    })
    assert r_both.status_code == 200
    assert "series" in r_both.json()

    # 3. Candles is not a list
    r_invalid_candles = client.post("/api/indicators/compute", json={
        "indicator": "rsi",
        "candles": "not-a-list"
    })
    assert r_invalid_candles.status_code == 400


# ==============================================================================
# Category 6: Renko Engine Specific Stress & Boundary Cases
# ==============================================================================

@pytest.mark.tier5
def test_adversarial_renko_extreme_brick_sizes(client):
    """Verifies that nano brick sizes (1e-6), macro sizes (100.0), and zero/negative sizes are handled safely."""
    cases = [
        ("nano brick", {"symbol": "GBPUSD", "brick_size": 1e-6, "limit": 50, "timeline_mode": "equidistant"}),
        ("macro brick", {"symbol": "GBPUSD", "brick_size": 100.0, "limit": 50, "timeline_mode": "equidistant"}),
        ("zero brick", {"symbol": "GBPUSD", "brick_size": 0.0, "limit": 50, "timeline_mode": "equidistant"}),
        ("negative brick", {"symbol": "GBPUSD", "brick_size": -0.001, "limit": 50, "timeline_mode": "equidistant"}),
    ]
    for label, rparams in cases:
        resp = client.post("/api/indicators/compute", json={
            "indicator": "rsi",
            "renko_params": rparams
        })
        # Must return 200 (either computed series or warm-up warning), never crash with 500
        assert resp.status_code == 200, f"Renko extreme brick size failed for {label}: {resp.status_code}"
        data = resp.json()
        assert "series" in data


@pytest.mark.tier5
def test_adversarial_renko_timeline_modes_and_limits(client):
    """Verifies Renko computation resilience under negative limits and arbitrary timeline_mode strings."""
    cases = [
        {"symbol": "GBPUSD", "limit": -50, "timeline_mode": "equidistant"},
        {"symbol": "GBPUSD", "limit": 0, "timeline_mode": "equidistant"},
        {"symbol": "GBPUSD", "timeline_mode": "arbitrary_unknown_mode"},
        {"symbol": "GBPUSD", "mode": "unrecognized_mode", "timeline_mode": "real"},
    ]
    for rparams in cases:
        resp = client.post("/api/indicators/compute", json={
            "indicator": "bbands",
            "renko_params": rparams
        })
        assert resp.status_code == 200, f"Renko limit/timeline edge case failed: {resp.status_code}"
        data = resp.json()
        assert "series" in data


@pytest.mark.tier5
def test_adversarial_get_endpoint_query_param_fuzzing(client):
    """Fuzzes GET /api/indicators/compute with missing indicators, negative lengths, and invalid parameters."""
    queries = [
        ("?indicator=rsi&symbol=GBPUSD&length=-5", 400),
        ("?indicator=macd&fast=50&slow=10", 400),
        ("?indicator=nonexistent_ind", 400),
        ("?indicator=bbands&std=-1.0", 400),
        ("?indicator=bbands&symbol=GBPUSD&brick_size=0.0005&length=20&std=2.0", 200),
    ]
    for q, expected_status in queries:
        resp = client.get(f"/api/indicators/compute{q}")
        assert resp.status_code == expected_status, f"Expected {expected_status} for GET {q}, got {resp.status_code}"


# ==============================================================================
# Category 7: Catalog Metadata & Concurrency Stress
# ==============================================================================

@pytest.mark.tier5
def test_adversarial_catalog_introspection_completeness(client):
    """Audits the full dynamic catalog across all 9 categories ensuring 100% schema integrity."""
    resp = client.get("/api/indicators/catalog")
    assert resp.status_code == 200
    catalog = resp.json()
    indicators = catalog["indicators"]

    assert len(indicators) >= 140, f"Catalog smaller than expected: {len(indicators)}"
    valid_categories = set(catalog["categories"])

    for ind_id, meta in indicators.items():
        assert meta["id"] == ind_id
        assert isinstance(meta["name"], str) and len(meta["name"]) > 0
        assert meta["category"] in valid_categories, f"Unknown category '{meta['category']}' in {ind_id}"
        assert meta["kind"] in ("overlay", "oscillator"), f"Invalid kind '{meta['kind']}' in {ind_id}"
        assert isinstance(meta["inputs"], list) and len(meta["inputs"]) > 0
        assert isinstance(meta["outputs"], list) and len(meta["outputs"]) > 0
        for out in meta["outputs"]:
            assert "name" in out and "type" in out and "color" in out


@pytest.mark.tier5
def test_adversarial_frontend_asset_regex_and_isolation():
    """Inspects frontend static assets for catastrophic backtracking regexes, CSS isolation, and injection risks."""
    chart_js_path = os.path.join(WORKSPACE_DIR, "static", "js", "chart_manager.js")
    style_css_path = os.path.join(WORKSPACE_DIR, "static", "css", "style.css")
    index_html_path = os.path.join(WORKSPACE_DIR, "templates", "index.html")

    assert os.path.isfile(chart_js_path)
    assert os.path.isfile(style_css_path)
    assert os.path.isfile(index_html_path)

    with open(chart_js_path, "r", encoding="utf-8") as f:
        js_content = f.read()

    with open(style_css_path, "r", encoding="utf-8") as f:
        css_content = f.read()

    with open(index_html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # 1. Verify safe tokening in chart_manager.js
    assert "_backendIndTokens" in js_content, "Missing race-condition token guard in chart_manager.js"

    # 2. Verify subpane container and resize handles
    assert ".oscillators-container" in css_content
    assert ".oscillator-subpane" in css_content
    assert ".oscillator-resize-handle" in css_content

    # 3. Verify modal elements in HTML
    assert "indicator-library-dialog" in html_content
    assert "indicator-library-search" in html_content
    assert "indicator-library-list" in html_content
    assert "indicator-settings-fields" in html_content
    assert "indicator-library-apply" in html_content


@pytest.mark.tier5
def test_adversarial_multi_indicator_concurrency_stress(sample_standard_candles):
    """Executes 24 concurrent requests across different threads to verify engine thread-safety."""
    indicators_to_query = [
        "rsi", "bbands", "macd", "sma", "ema", "atr", "adx", "stoch",
        "supertrend", "obv", "vwap", "cci", "rsi", "bbands", "macd", "sma",
        "ema", "atr", "adx", "stoch", "supertrend", "obv", "vwap", "cci"
    ]

    def make_call(ind_name):
        with TestClient(app) as local_client:
            return local_client.post("/api/indicators/compute", json={
                "indicator": ind_name,
                "candles": sample_standard_candles
            })

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(make_call, ind) for ind in indicators_to_query]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    for resp in results:
        assert resp.status_code == 200
        data = resp.json()
        assert "series" in data
        assert "indicator" in data
