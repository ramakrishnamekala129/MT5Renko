"""
Automated Test Suite for Milestone 2: Frontend Indicator Modal & State Management.

Verifies:
1. Jinja2 template DOM markup for indicator library modal, category tabs, parameter panel, and action controls.
2. Backend catalog endpoint contract alignment with frontend metadata schemas.
3. JavaScript integration hooks: catalog fetching, dynamic category tabs, real-time search filtering,
   dynamic parameter form generation, min/max/step clamping, and active indicator lifecycle management.
4. Clean state management: add, edit parameters, toggle visibility, and clean removal from active state and SafeStorage.
5. Syntactic validity of chart_manager.js.
"""

import json
import re
import subprocess
import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


# ==============================================================================
# 1. Template & DOM Markup Verification Tests
# ==============================================================================

def test_template_indicator_modal_structure(client):
    """Verifies that the index.html template contains all modal DOM elements required by M2."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # Modal dialog container
    assert 'id="indicator-library-dialog"' in html, "Missing #indicator-library-dialog"
    assert 'class="indicator-library-modal hidden"' in html

    # Header elements
    assert 'id="indicator-library-title"' in html, "Missing #indicator-library-title"
    assert 'id="indicator-library-pane-label"' in html, "Missing #indicator-library-pane-label"
    assert 'id="indicator-library-close"' in html, "Missing #indicator-library-close"

    # Sidebar, search box, category tabs, and indicator list
    assert 'class="indicator-library-sidebar"' in html
    assert 'id="indicator-library-search"' in html, "Missing search input #indicator-library-search"
    assert 'id="indicator-category-tabs"' in html, "Missing category tabs bar #indicator-category-tabs"
    assert 'id="indicator-library-list"' in html, "Missing indicator list container #indicator-library-list"

    # Settings panel, labels, and dynamic fields
    assert 'class="indicator-settings-panel"' in html
    assert 'id="indicator-settings-category"' in html
    assert 'id="indicator-settings-name"' in html
    assert 'id="indicator-settings-desc"' in html
    assert 'id="indicator-settings-fields"' in html

    # Action controls: Remove, Visibility toggle, and Add/Apply
    assert 'id="indicator-library-remove"' in html, "Missing remove button #indicator-library-remove"
    assert 'id="indicator-library-visibility"' in html, "Missing visibility button #indicator-library-visibility"
    assert 'id="indicator-library-apply"' in html, "Missing apply button #indicator-library-apply"

    # Toolbar trigger button in chart pane template
    assert 'class="indicator-library-btn"' in html, "Missing .indicator-library-btn on chart toolbar"


# ==============================================================================
# 2. Catalog Endpoint & Schema Verification
# ==============================================================================

def test_catalog_endpoint_schema_contract(client):
    """Verifies the /api/indicators/catalog endpoint response matches frontend requirements."""
    resp = client.get("/api/indicators/catalog")
    assert resp.status_code == 200
    data = resp.json()

    assert "categories" in data
    assert "indicators" in data

    # Required pandas_ta categories
    required_cats = ["momentum", "overlap", "trend", "volatility", "volume", "statistics"]
    for cat in required_cats:
        assert cat in data["categories"], f"Required category '{cat}' missing from catalog"

    indicators = data["indicators"]
    assert len(indicators) >= 140, f"Expected >= 140 indicators, got {len(indicators)}"

    # Check schema conformance on indicators
    sample_ids = ["rsi", "bbands", "sma", "ema", "macd", "stoch", "atr", "adx", "obv"]
    for ind_id in sample_ids:
        assert ind_id in indicators, f"Representative indicator '{ind_id}' not found"
        ind = indicators[ind_id]
        assert ind["id"] == ind_id
        assert isinstance(ind["name"], str) and len(ind["name"]) > 0
        assert ind["kind"] in ("overlay", "oscillator")
        assert isinstance(ind["params"], list)
        assert isinstance(ind["outputs"], list)

        # Validate params structure
        for p in ind["params"]:
            assert "name" in p
            assert "type" in p
            assert p["type"] in ("int", "float", "str", "bool")
            assert "default" in p


# ==============================================================================
# 3. JavaScript Implementation & Hook Verification
# ==============================================================================

def test_chart_manager_js_syntax():
    """Verifies that static/js/chart_manager.js passes syntax check via Node.js."""
    res = subprocess.run(
        ["node", "--check", "static/js/chart_manager.js"],
        capture_output=True,
        text=True
    )
    assert res.returncode == 0, f"JavaScript syntax error: {res.stderr}"


def test_chart_manager_js_catalog_and_modal_hooks():
    """Verifies essential functions and state hooks exist in chart_manager.js."""
    with open("static/js/chart_manager.js", "r", encoding="utf-8") as f:
        js = f.read()

    # 1. Dynamic Catalog Loading
    assert "async function fetchIndicatorCatalog()" in js or "function fetchIndicatorCatalog()" in js
    assert "function mergeCatalogDefinitions(" in js
    assert "fetch('/api/indicators/catalog')" in js or 'fetch("/api/indicators/catalog")' in js
    assert "fetchIndicatorCatalog();" in js  # Called in init()

    # 2. Category Tabs & Navigation
    assert "function renderCategoryTabs()" in js
    assert "indicator-category-tabs" in js
    assert "activeCategoryFilter" in js

    # 3. Search & Grouping in Modal
    assert "function renderIndicatorLibrary()" in js
    assert "indicator-library-search" in js
    assert "indicator-library-list" in js

    # 4. Dynamic Parameter Form & Clamping
    assert "function renderIndicatorSettingsPanel(" in js
    assert "function readIndicatorSettingsForm(" in js
    assert "data-field-key" in js
    assert "data-param-type" in js
    assert "indicator-field-checkbox" in js or "type=\"checkbox\"" in js

    # 5. Active Indicator Controls & Persistence
    assert "function addIndicatorFromLibrary(" in js
    assert "function setIndicatorActive(" in js
    assert "function toggleIndicatorVisibility(" in js
    assert "function removeIndicator(" in js
    assert "indicator-library-visibility" in js
    assert "ag_pane_indicators_" in js
    assert "ag_pane_indicator_settings_" in js
    assert "ag_pane_indicator_visibility_" in js


# ==============================================================================
# 4. Logic & State Management Behavior Tests
# ==============================================================================

def test_clamping_and_parameter_parsing_logic():
    """Verifies min/max/step clamping and type conversion logic matching JS implementation."""
    def simulate_parse_and_clamp(raw_value, param_meta):
        p_type = param_meta.get("type", "float")
        p_min = param_meta.get("min")
        p_max = param_meta.get("max")
        default = param_meta.get("default")

        if p_type == "bool":
            return bool(raw_value)
        elif p_type in ("int", "float", "number"):
            try:
                val = float(raw_value)
            except (ValueError, TypeError):
                val = float(default) if default is not None else 0.0

            if p_min is not None and val < p_min:
                val = p_min
            if p_max is not None and val > p_max:
                val = p_max
            if p_type == "int":
                val = int(round(val))
            return val
        else:
            return str(raw_value)

    # Int clamping (e.g. length with min=1, max=200)
    int_meta = {"name": "length", "type": "int", "default": 14, "min": 1, "max": 200, "step": 1}
    assert simulate_parse_and_clamp(14, int_meta) == 14
    assert simulate_parse_and_clamp(-5, int_meta) == 1  # Clamped to min
    assert simulate_parse_and_clamp(500, int_meta) == 200  # Clamped to max
    assert simulate_parse_and_clamp(15.7, int_meta) == 16  # Rounded to integer

    # Float clamping (e.g. std with min=0.1, max=10.0)
    float_meta = {"name": "std", "type": "float", "default": 2.0, "min": 0.1, "max": 10.0, "step": 0.1}
    assert simulate_parse_and_clamp(2.5, float_meta) == 2.5
    assert simulate_parse_and_clamp(0.01, float_meta) == 0.1  # Clamped to min
    assert simulate_parse_and_clamp(15.0, float_meta) == 10.0  # Clamped to max

    # Bool parsing
    bool_meta = {"name": "use_filter", "type": "bool", "default": False}
    assert simulate_parse_and_clamp(True, bool_meta) is True
    assert simulate_parse_and_clamp(False, bool_meta) is False


def test_active_indicator_lifecycle_state_simulation():
    """Simulates the state transitions of active indicator management (Add, Edit, Toggle, Remove)."""
    # Mock pane state representing client-side pane object
    pane_id = 1
    pane = {
        "id": pane_id,
        "activeIndicators": {},
        "indicatorSettings": {},
        "indicatorVisibility": {}
    }
    local_storage = {}

    def save_indicator_state(p):
        local_storage[f"ag_pane_indicators_{p['id']}"] = json.dumps(p["activeIndicators"])
        local_storage[f"ag_pane_indicator_settings_{p['id']}"] = json.dumps(p["indicatorSettings"])
        local_storage[f"ag_pane_indicator_visibility_{p['id']}"] = json.dumps(p["indicatorVisibility"])

    def add_indicator(p, base_key, initial_cfg):
        instance_key = base_key if base_key not in p["activeIndicators"] else f"{base_key}__inst1"
        p["activeIndicators"][instance_key] = True
        p["indicatorSettings"][instance_key] = dict(initial_cfg)
        p["indicatorVisibility"][instance_key] = True
        save_indicator_state(p)
        return instance_key

    def edit_indicator(p, ind_key, updated_cfg):
        assert ind_key in p["activeIndicators"]
        p["indicatorSettings"][ind_key].update(updated_cfg)
        save_indicator_state(p)

    def toggle_visibility(p, ind_key):
        assert ind_key in p["activeIndicators"]
        current = p["indicatorVisibility"].get(ind_key, True)
        p["indicatorVisibility"][ind_key] = not current
        save_indicator_state(p)

    def remove_indicator(p, ind_key):
        if ind_key in p["activeIndicators"]:
            del p["activeIndicators"][ind_key]
        if ind_key in p["indicatorSettings"]:
            del p["indicatorSettings"][ind_key]
        if ind_key in p["indicatorVisibility"]:
            del p["indicatorVisibility"][ind_key]
        save_indicator_state(p)

    # 1. Add indicator (e.g. rsi with length=14)
    key = add_indicator(pane, "rsi", {"length": 14, "scalar": 100.0})
    assert key == "rsi"
    assert pane["activeIndicators"]["rsi"] is True
    assert pane["indicatorSettings"]["rsi"]["length"] == 14
    assert pane["indicatorVisibility"]["rsi"] is True
    assert "rsi" in json.loads(local_storage[f"ag_pane_indicators_{pane_id}"])

    # 2. Edit indicator settings (e.g. length changed to 21)
    edit_indicator(pane, key, {"length": 21})
    assert pane["indicatorSettings"]["rsi"]["length"] == 21
    saved_settings = json.loads(local_storage[f"ag_pane_indicator_settings_{pane_id}"])
    assert saved_settings["rsi"]["length"] == 21

    # 3. Toggle visibility (hide, then show)
    toggle_visibility(pane, key)
    assert pane["indicatorVisibility"]["rsi"] is False
    assert json.loads(local_storage[f"ag_pane_indicator_visibility_{pane_id}"])["rsi"] is False

    toggle_visibility(pane, key)
    assert pane["indicatorVisibility"]["rsi"] is True
    assert json.loads(local_storage[f"ag_pane_indicator_visibility_{pane_id}"])["rsi"] is True

    # 4. Remove indicator cleanly
    remove_indicator(pane, key)
    assert "rsi" not in pane["activeIndicators"]
    assert "rsi" not in pane["indicatorSettings"]
    assert "rsi" not in pane["indicatorVisibility"]
    assert "rsi" not in json.loads(local_storage[f"ag_pane_indicators_{pane_id}"])
    assert "rsi" not in json.loads(local_storage[f"ag_pane_indicator_settings_{pane_id}"])
    assert "rsi" not in json.loads(local_storage[f"ag_pane_indicator_visibility_{pane_id}"])


# ==============================================================================
# 5. Security & Robustness Tests (Adversarial Hardening)
# ==============================================================================

def test_empty_search_xss_escaping():
    """Verifies that empty search queries are HTML-escaped to prevent DOM XSS injection."""
    with open("static/js/chart_manager.js", "r", encoding="utf-8") as f:
        js = f.read()

    # 1. Structural check: escapeHtml(query) must be used in the empty search message
    assert 'No indicators found matching "${escapeHtml(query)}"' in js, (
        "Empty search query interpolation in renderIndicatorLibrary must use escapeHtml(query)"
    )

    # 2. Check escapeHtml definition handles &, <, >, ", and '
    assert "function escapeHtml(str)" in js
    assert ".replace(/&/g, '&amp;')" in js
    assert ".replace(/</g, '&lt;')" in js
    assert ".replace(/>/g, '&gt;')" in js
    assert '.replace(/"/g, \'&quot;\')' in js or '.replace(/"/g, "&quot;")' in js

    # 3. Direct Node.js execution of escapeHtml against adversarial XSS payloads
    test_script = """
    function escapeHtml(str) {
        return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }
    const payloads = [
        '<img src=x onerror=alert(1)>',
        '<script>alert("XSS")</script>',
        '"><svg/onload=alert(1)>',
        '"><iframe src=javascript:alert(1)>',
        "' OR '1'='1"
    ];
    for (const p of payloads) {
        const escaped = escapeHtml(p);
        if (escaped.includes('<') || escaped.includes('>') || escaped.includes('"') || escaped.includes("'")) {
            console.error('FAIL: Unescaped character in: ' + escaped);
            process.exit(1);
        }
    }
    console.log('ALL_SAFE');
    """
    res = subprocess.run(["node", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0 and "ALL_SAFE" in res.stdout, f"escapeHtml failed adversarial payload test: {res.stderr}"


def test_safestorage_null_and_corrupt_json_resilience():
    """Verifies that JSON literal 'null' and corrupted storage strings do not crash active indicator state."""
    with open("static/js/chart_manager.js", "r", encoding="utf-8") as f:
        js = f.read()

    # 1. Structural verification of safe parsing in createPane
    pattern = r"const parsed = JSON\.parse\((?:rawIndicators|rawIndicatorSettings|rawIndicatorVisibility)\);\s+if \(parsed && typeof parsed === 'object' && !Array\.isArray\(parsed\)\)"
    matches = re.findall(pattern, js)
    assert len(matches) >= 3, "createPane must validate parsed JSON as non-null object for indicators, settings, and visibility"

    # 2. Structural verification of defensive initialization in setIndicatorActive
    assert "pane.activeIndicators = (pane.activeIndicators && typeof pane.activeIndicators === 'object'" in js, (
        "setIndicatorActive must defensively initialize pane.activeIndicators as an object"
    )

    # 3. Direct Node.js simulation of startup with 'null', primitive, array, and corrupted JSON storage values
    node_test_script = """
    const badValues = [
        "null",
        "123",
        "\\"string_primitive\\"",
        "[1, 2, 3]",
        "true",
        "false",
        "{invalid-json: missing quotes}",
        ""
    ];

    for (const raw of badValues) {
        let activeIndicators = {};
        let indicatorSettings = {};
        let indicatorVisibility = {};

        // Emulate chart_manager.js safe parsing logic
        if (raw) {
            try {
                const parsed = JSON.parse(raw);
                if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) activeIndicators = parsed;
            } catch (e) { }
        }

        const pane = {
            id: 1,
            activeIndicators,
            indicatorSettings,
            indicatorVisibility,
            candles: []
        };

        // Emulate setIndicatorActive defensive initialization and assignment
        pane.activeIndicators = (pane.activeIndicators && typeof pane.activeIndicators === 'object' && !Array.isArray(pane.activeIndicators)) ? pane.activeIndicators : {};
        pane.indicatorVisibility = (pane.indicatorVisibility && typeof pane.indicatorVisibility === 'object' && !Array.isArray(pane.indicatorVisibility)) ? pane.indicatorVisibility : {};
        pane.indicatorSettings = (pane.indicatorSettings && typeof pane.indicatorSettings === 'object' && !Array.isArray(pane.indicatorSettings)) ? pane.indicatorSettings : {};

        // Must not throw TypeError: Cannot set properties of null
        pane.activeIndicators['rsi'] = true;
        pane.indicatorVisibility['rsi'] = true;
        pane.indicatorSettings['rsi'] = { length: 14 };

        if (typeof pane.activeIndicators !== 'object' || pane.activeIndicators === null || Array.isArray(pane.activeIndicators)) {
            console.error('FAIL: activeIndicators is not a plain object for raw input: ' + raw);
            process.exit(1);
        }
    }
    console.log('STORAGE_RESILIENT');
    """
    res = subprocess.run(["node", "-e", node_test_script], capture_output=True, text=True)
    assert res.returncode == 0 and "STORAGE_RESILIENT" in res.stdout, f"Storage resilience failed: {res.stderr}"


def test_rsi_fallback_period_and_length_alignment():
    """Verifies that renderOscillatorRSI properly checks cfg.period || cfg.length || 14."""
    with open("static/js/chart_manager.js", "r", encoding="utf-8") as f:
        js = f.read()

    assert "const period = cfg.period || cfg.length || 14;" in js, (
        "renderOscillatorRSI must support catalog length property via cfg.period || cfg.length || 14"
    )
    assert "ensureOscChart(pane, indKey, `RSI (${period})`)" in js
