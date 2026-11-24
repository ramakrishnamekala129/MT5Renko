"""
Automated Verification Test Suite: Milestone 3 - Multi-Pane & Overlay Chart Visualization
========================================================================================
Covers:
- CSS Styling for Multi-Pane Oscillator Sub-Charts & Resize Handles (style.css)
- Static Asset Serving & Integrity via FastAPI TestClient
- Dynamic Indicator Compute Pipeline & Parameter Passthrough (/api/indicators/compute)
- Multi-Series Handling (LineSeries, HistogramSeries, Overlays vs Oscillators)
- Sub-Pane Lifecycle, Detachment, and Bi-directional Synchronization Architecture
"""

import math
import os
import re
import sys
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

# Ensure workspace root is on sys.path
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from app import app


# ==============================================================================
# Deterministic Synthetic Data Fixtures
# ==============================================================================

def make_test_candles(n: int = 60, start_price: float = 1.2500) -> List[Dict[str, Any]]:
    """Generates deterministic OHLCV candles for indicator verification."""
    candles = []
    p = start_price
    start_time = 1700000000
    for i in range(n):
        drift = 0.0004 * math.sin(i * 0.25)
        open_p = p
        close_p = open_p + drift
        high_p = max(open_p, close_p) + 0.0003
        low_p = min(open_p, close_p) - 0.0003
        vol = 100.0 + (i % 5) * 10.0
        candles.append({
            "time": start_time + i * 60,
            "open": round(open_p, 5),
            "high": round(high_p, 5),
            "low": round(low_p, 5),
            "close": round(close_p, 5),
            "volume": round(vol, 1),
        })
        p = close_p
    return candles


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sample_candles() -> List[Dict[str, Any]]:
    return make_test_candles(n=60)


# ==============================================================================
# Suite 1: CSS Styling for Multi-Pane Sub-Charts & Resize Handles
# ==============================================================================

class TestOscillatorCSSStyling:
    """Verifies that style.css defines all required CSS rules for sub-panes and handles."""

    @pytest.fixture(autouse=True)
    def load_css(self):
        css_path = os.path.join(WORKSPACE_DIR, "static", "css", "style.css")
        assert os.path.exists(css_path), f"style.css not found at {css_path}"
        with open(css_path, "r", encoding="utf-8") as f:
            self.css_text = f.read()

    def test_oscillator_subpane_rule_presence(self):
        """Verify .oscillator-subpane rule exists in style.css."""
        assert ".oscillator-subpane" in self.css_text

    def test_oscillator_subpane_mandatory_layout_properties(self):
        """Verify .oscillator-subpane defines position: relative, width: 100%, and overflow: hidden."""
        pattern = r"\.oscillator-subpane\s*\{([^}]+)\}"
        match = re.search(pattern, self.css_text)
        assert match is not None, "Could not find .oscillator-subpane rule block in style.css"
        block = match.group(1).lower()

        assert "position: relative" in block or "position:relative" in block
        assert "width: 100%" in block or "width:100%" in block
        assert "overflow: hidden" in block or "overflow:hidden" in block

    def test_oscillator_resize_handle_rule_presence(self):
        """Verify .oscillator-resize-handle rule exists in style.css."""
        assert ".oscillator-resize-handle" in self.css_text

    def test_oscillator_resize_handle_properties(self):
        """Verify .oscillator-resize-handle defines required positioning, height, cursor, and z-index."""
        pattern = r"\.oscillator-resize-handle\s*\{([^}]+)\}"
        match = re.search(pattern, self.css_text)
        assert match is not None, "Could not find .oscillator-resize-handle rule block in style.css"
        block = match.group(1).lower()

        assert "position: absolute" in block or "position:absolute" in block
        assert "top: 0" in block or "top:0" in block
        assert "height: 5px" in block or "height:5px" in block
        assert "cursor: ns-resize" in block or "cursor:ns-resize" in block
        assert "z-index: 30" in block or "z-index:30" in block

    def test_oscillator_resize_handle_hover_feedback(self):
        """Verify .oscillator-resize-handle hover state displays accent color feedback."""
        pattern = r"\.oscillator-resize-handle:hover[^{]*\{([^}]+)\}"
        match = re.search(pattern, self.css_text)
        assert match is not None, "Missing .oscillator-resize-handle:hover rule in style.css"
        block = match.group(1).lower()
        assert "background-color" in block
        assert "accent" in block

    def test_body_is_resizing_panel_cursor(self):
        """Verify body.is-resizing-panel enforces ns-resize cursor and disables user selection."""
        assert "body.is-resizing-panel" in self.css_text
        pattern = r"body\.is-resizing-panel\s*\{([^}]+)\}"
        match = re.search(pattern, self.css_text)
        assert match is not None
        block = match.group(1).lower()
        assert "ns-resize" in block
        assert "user-select: none" in block or "user-select:none" in block

    def test_oscillators_container_hidden_state(self):
        """Verify .oscillators-container and .oscillators-container.hidden styling."""
        assert ".oscillators-container" in self.css_text
        assert ".oscillators-container.hidden" in self.css_text
        pattern = r"\.oscillators-container\.hidden\s*\{([^}]+)\}"
        match = re.search(pattern, self.css_text)
        assert match is not None
        assert "display: none" in match.group(1).lower() or "display:none" in match.group(1).lower()


# ==============================================================================
# Suite 2: Static Asset Serving & File Integrity
# ==============================================================================

class TestStaticFileServingAndIntegrity:
    """Verifies static asset routes and template integrity via FastAPI TestClient."""

    def test_serve_style_css(self, client: TestClient):
        """Verify GET /static/css/style.css serves valid CSS with 200 OK."""
        res = client.get("/static/css/style.css")
        assert res.status_code == 200
        assert "text/css" in res.headers.get("content-type", "").lower()
        assert ".oscillator-subpane" in res.text
        assert ".oscillator-resize-handle" in res.text

    def test_serve_chart_manager_js(self, client: TestClient):
        """Verify GET /static/js/chart_manager.js serves valid JavaScript with 200 OK."""
        res = client.get("/static/js/chart_manager.js")
        assert res.status_code == 200
        assert any(t in res.headers.get("content-type", "").lower() for t in ["javascript", "text/plain"])
        text = res.text
        # Verify dynamic compute pipeline functions
        assert "computeIndicatorOnBackend" in text
        assert "renderBackendIndicatorSeries" in text
        assert "isPandasTaIndicator" in text
        assert "/api/indicators/compute" in text
        # Verify lifecycle and sync functions
        assert "ensureOscChart" in text
        assert "clearOscillator" in text
        assert "syncTimeScales" in text
        assert "subscribeVisibleLogicalRangeChange" in text
        assert "_isSyncing" in text

    def test_serve_dashboard_index_html(self, client: TestClient):
        """Verify GET / renders dashboard HTML containing oscillator container and charts grid."""
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "").lower()
        assert "oscillators-container" in res.text
        assert "charts-grid" in res.text
        assert "indicator-library-dialog" in res.text


# ==============================================================================
# Suite 3: Indicator Compute Endpoint Integration & Parameter Passthrough
# ==============================================================================

class TestIndicatorComputeIntegration:
    """Verifies POST /api/indicators/compute handling of Candlestick and Renko data."""

    def test_candlestick_single_line_overlay_sma(self, client: TestClient, sample_candles):
        """Verify single-line overlay (SMA) calculation on candlestick data."""
        payload = {
            "indicator": "sma",
            "params": {"length": 14},
            "data_type": "candle",
            "candles": sample_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["indicator"] == "sma"
        assert data["kind"] == "overlay"
        assert "series" in data
        assert "SMA_14" in data["series"]
        pts = data["series"]["SMA_14"]
        assert len(pts) == len(sample_candles)
        # Leading warm-up nulls, followed by valid numbers
        valid_pts = [p["value"] for p in pts if p["value"] is not None]
        assert len(valid_pts) > 0
        assert abs(pts[-1]["value"] - sum(c["close"] for c in sample_candles[-14:]) / 14.0) < 0.001

    def test_candlestick_multi_line_overlay_bbands(self, client: TestClient, sample_candles):
        """Verify multi-line overlay (Bollinger Bands) returns upper, middle, lower bands."""
        payload = {
            "indicator": "bbands",
            "params": {"length": 20, "std": 2.0},
            "data_type": "candle",
            "candles": sample_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["indicator"] == "bbands"
        assert data["kind"] == "overlay"
        series = data["series"]
        assert "upper" in series
        assert "middle" in series
        assert "lower" in series
        # Verify mathematical ordering: upper >= middle >= lower
        u = series["upper"][-1]["value"]
        m = series["middle"][-1]["value"]
        l = series["lower"][-1]["value"]
        assert u is not None and m is not None and l is not None
        assert u >= m >= l

    def test_candlestick_single_line_oscillator_rsi(self, client: TestClient, sample_candles):
        """Verify single-line oscillator (RSI) returns bounded values in [0, 100]."""
        payload = {
            "indicator": "rsi",
            "params": {"length": 14},
            "data_type": "candle",
            "candles": sample_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["indicator"] == "rsi"
        assert data["kind"] == "oscillator"
        pts = data["series"]["RSI_14"]
        valid_vals = [p["value"] for p in pts if p["value"] is not None]
        assert len(valid_vals) > 0
        for v in valid_vals:
            assert 0.0 <= v <= 100.0

    def test_candlestick_multi_line_oscillator_macd(self, client: TestClient, sample_candles):
        """Verify multi-line oscillator (MACD) returns macd, signal, and histogram series."""
        payload = {
            "indicator": "macd",
            "params": {"fast": 12, "slow": 26, "signal": 9},
            "data_type": "candle",
            "candles": sample_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["indicator"] == "macd"
        assert data["kind"] == "oscillator"
        series = data["series"]
        assert "macd" in series
        assert "signal" in series
        assert "histogram" in series
        # Verify timestamp alignment across all series
        times_macd = [p["time"] for p in series["macd"]]
        times_sig = [p["time"] for p in series["signal"]]
        times_hist = [p["time"] for p in series["histogram"]]
        assert times_macd == times_sig == times_hist

    def test_candlestick_volatility_oscillator_atr(self, client: TestClient, sample_candles):
        """Verify volatility oscillator (ATR) returns positive metrics."""
        payload = {
            "indicator": "atr",
            "params": {"length": 14},
            "data_type": "candle",
            "candles": sample_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["indicator"] == "atr"
        assert data["kind"] == "oscillator"
        valid_vals = [p["value"] for p in data["series"]["ATRr_14"] if p["value"] is not None]
        assert len(valid_vals) > 0
        assert all(v > 0 for v in valid_vals)

    def test_candlestick_trend_oscillator_adx(self, client: TestClient, sample_candles):
        """Verify trend oscillator (ADX) returns adx, dmp, and dmn series."""
        payload = {
            "indicator": "adx",
            "params": {"length": 14},
            "data_type": "candle",
            "candles": sample_candles,
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["indicator"] == "adx"
        assert data["kind"] == "oscillator"
        series = data["series"]
        assert "adx" in series
        assert "dmp" in series
        assert "dmn" in series

    def test_renko_mode_equidistant_alignment(self, client: TestClient):
        """Verify indicator computation on Renko bricks in equidistant timeline mode."""
        payload = {
            "indicator": "sma",
            "params": {"length": 10},
            "data_type": "renko",
            "renko_params": {
                "symbol": "GBPUSD",
                "brick_size": 0.00035,
                "timeline_mode": "equidistant",
                "limit": 50,
            },
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["kind"] == "overlay"
        pts = data["series"]["SMA_10"]
        assert len(pts) > 0
        # Timestamps must increment with uniform interval in equidistant mode
        diffs = [pts[i]["time"] - pts[i - 1]["time"] for i in range(1, len(pts))]
        assert len(set(diffs)) == 1

    def test_renko_mode_real_timeline(self, client: TestClient):
        """Verify indicator computation on Renko bricks in real timeline mode."""
        payload = {
            "indicator": "rsi",
            "params": {"length": 14},
            "data_type": "renko",
            "renko_params": {
                "symbol": "GBPUSD",
                "brick_size": 0.00035,
                "timeline_mode": "real",
                "limit": 50,
            },
        }
        res = client.post("/api/indicators/compute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["kind"] == "oscillator"
        pts = data["series"]["RSI_14"]
        assert len(pts) > 0
        # Timestamps strictly monotonic increasing
        for i in range(1, len(pts)):
            assert pts[i]["time"] > pts[i - 1]["time"]

    def test_parameter_passthrough_custom_length(self, client: TestClient, sample_candles):
        """Verify parameter overrides alter calculated numerical values."""
        res_fast = client.post("/api/indicators/compute", json={
            "indicator": "sma",
            "params": {"length": 5},
            "data_type": "candle",
            "candles": sample_candles,
        }).json()
        res_slow = client.post("/api/indicators/compute", json={
            "indicator": "sma",
            "params": {"length": 25},
            "data_type": "candle",
            "candles": sample_candles,
        }).json()
        val_fast = res_fast["series"]["SMA_5"][-1]["value"]
        val_slow = res_slow["series"]["SMA_25"][-1]["value"]
        assert val_fast != val_slow


# ==============================================================================
# Suite 4: Frontend Chart Manager Architecture & Lifecycle Checks
# ==============================================================================

class TestChartManagerArchitecture:
    """Verifies that static/js/chart_manager.js adheres to the architecture contracts."""

    @pytest.fixture(autouse=True)
    def load_js(self):
        js_path = os.path.join(WORKSPACE_DIR, "static", "js", "chart_manager.js")
        assert os.path.exists(js_path), f"chart_manager.js not found at {js_path}"
        with open(js_path, "r", encoding="utf-8") as f:
            self.js_text = f.read()

    def test_backend_compute_dispatch_logic(self):
        """Verify computeIndicatorOnBackend constructs both renko and candle payloads."""
        assert "computeIndicatorOnBackend" in self.js_text
        assert "data_type: 'renko'" in self.js_text or 'data_type: "renko"' in self.js_text
        assert "data_type: 'candle'" in self.js_text or 'data_type: "candle"' in self.js_text
        assert "renko_params" in self.js_text

    def test_multi_series_handling_lines_and_histograms(self):
        """Verify chart_manager.js handles both LineSeries and HistogramSeries."""
        assert "LightweightCharts.LineSeries" in self.js_text
        assert "LightweightCharts.HistogramSeries" in self.js_text
        # Verifies canonical series handling
        assert "renderBackendIndicatorSeries" in self.js_text
        assert "sanitizeSeriesData" in self.js_text

    def test_subpane_and_resize_handle_dom_generation(self):
        """Verify ensureOscChart generates .oscillator-subpane, .oscillator-resize-handle, and .oscillator-label."""
        assert "oscillator-subpane" in self.js_text
        assert "oscillator-resize-handle" in self.js_text
        assert "oscillator-label" in self.js_text
        assert "wireOscillatorPanelResize" in self.js_text
        assert "ResizeObserver" in self.js_text

    def test_clean_detachment_and_container_collapse(self):
        """Verify clearOscillator removes charts, DOM nodes, disconnects ResizeObserver, and collapses container."""
        assert "clearOscillator" in self.js_text
        assert "resizeObserver.disconnect" in self.js_text
        assert "chart.remove" in self.js_text
        assert "subpaneEl.parentNode.removeChild" in self.js_text
        assert "oscillatorsContainer.classList.add('hidden')" in self.js_text

    def test_bidirectional_timescale_sync_guard(self):
        """Verify syncTimeScales implements re-entrancy protection with _isSyncing."""
        assert "syncTimeScales" in self.js_text
        assert "subscribeVisibleLogicalRangeChange" in self.js_text
        assert "_isSyncing" in self.js_text

    def test_visibility_toggling_without_data_loss(self):
        """Verify toggleIndicatorVisibility uses applyOptions({ visible }) to hide/show series."""
        assert "toggleIndicatorVisibility" in self.js_text
        assert "applyOptions" in self.js_text
        assert "visible: nextVisible" in self.js_text or "visible: isVisible" in self.js_text
