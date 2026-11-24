"""
Automated Verification & Sanity Test Suite for RK Renko V4
Validates:
1. Renko Brick Engine (1-box continuation, 2-box reversal, streak counter)
2. Supertrend(1, 3.1) and Renko EMA 5/9 calculations
3. Reference Zones & Fibonacci 0.44–0.56 Corridor classification
4. 9-Layer Confluence Filter Stack logic
5. Trailing Stop Engine & Spread Spike Guard
6. Zero External Dependency Inspection across all files
"""

import sys
import os
import glob
import re
import datetime

# Add local MT5Renko workspace root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.renko import RenkoEngine, RenkoBrick
from core.indicators import Supertrend, RenkoEMA, AIPreRenkoEngine
from core.zones import ReferenceZoneEngine, ZoneType, ZoneColor, PriceZoneRel
from core.filters import ConfluenceFilterStack
from core.trailing import TrailingStopEngine, TrailingPositionState


def test_renko_brick_engine():
    print("[TEST 1/6] Validating Renko Brick Construction...")
    engine = RenkoEngine(brick_size=10.0)
    t0 = datetime.datetime.now()

    # Initial baseline price
    engine.initialize_from_price(100.0, t0)

    # Move up 10 pts -> 1 Up brick
    bricks = engine.process_price(110.0, t0)
    assert len(bricks) == 1, f"Expected 1 brick, got {len(bricks)}"
    assert bricks[0].direction == 1
    assert bricks[0].bar_num == 1
    assert bricks[0].close == 110.0

    # Move up another 10 pts -> Continuation (bar_num=2)
    bricks = engine.process_price(120.0, t0)
    assert len(bricks) == 1
    assert bricks[0].direction == 1
    assert bricks[0].bar_num == 2
    assert bricks[0].close == 120.0

    # Reversal requires 2 boxes down: from 120.0 to 100.0
    # Price moves to 110.0 -> no reversal brick yet
    bricks = engine.process_price(110.0, t0)
    assert len(bricks) == 0, "1-box move against trend should NOT create a brick"

    # Price moves to 100.0 -> 2-box reversal brick
    bricks = engine.process_price(100.0, t0)
    assert len(bricks) == 1
    assert bricks[0].direction == -1
    assert bricks[0].bar_num == -1
    assert bricks[0].is_reversal is True
    assert bricks[0].close == 100.0

    print("  -> Renko Brick Engine: PASSED")


def test_supertrend_and_ema():
    print("[TEST 2/6] Validating Supertrend(1, 3.1) and EMA...")
    st = Supertrend(length=1, multiplier=3.1)
    ema5 = RenkoEMA(period=5)
    t0 = datetime.datetime.now()

    # Simulate 5 up bricks: 100 -> 110 -> 120 -> 130 -> 140
    for i, c in enumerate([100.0, 110.0, 120.0, 130.0, 140.0]):
        brick = RenkoBrick(
            index=i,
            timestamp=t0,
            open=c - 10.0,
            high=c,
            low=c - 10.0,
            close=c,
            direction=1,
            bar_num=i + 1,
            is_reversal=False,
        )
        d, val = st.update(brick)
        ema_val = ema5.update(c)

    assert d == 1, f"Expected Supertrend Bullish (+1), got {d}"
    assert ema_val < 140.0, "EMA5 should lag behind fast up move"
    print(f"  -> Supertrend: BULLISH, line={val:.2f} | EMA5={ema_val:.2f}: PASSED")


def test_zone_corridors_and_signals():
    print("[TEST 3/6] Validating Reference Zones & Fibo Corridors...")
    zones = ReferenceZoneEngine()

    # Create FirstRed Zone: High=100, Low=50 -> Range=50
    # Fib0.44 = 50 + 22 = 72
    # Eq0.50  = 50 + 25 = 75
    # Fib0.56 = 50 + 28 = 78
    fr = zones.set_zone(ZoneType.FIRST_RED, high=100.0, low=50.0, color=ZoneColor.GREEN)
    assert fr.fib_044 == 72.0
    assert fr.fib_050 == 75.0
    assert fr.fib_056 == 78.0

    # Inside corridor check
    assert fr.classify_price(75.0) == PriceZoneRel.INSIDE
    assert fr.classify_price(105.0) == PriceZoneRel.FAR_ABOVE
    assert fr.classify_price(45.0) == PriceZoneRel.FAR_BELOW

    is_inside, _ = zones.is_price_inside_any_active_zone(75.0)
    assert is_inside is True, "Price at 75.0 must be detected as INSIDE chop zone"

    is_inside, _ = zones.is_price_inside_any_active_zone(102.0)
    assert is_inside is False

    # Breakout signal: prev close 95.0, new close 102.0 (crosses 100.0 high)
    zones._prev_brick_close = 95.0
    sigs = zones.evaluate_brick_signals(brick_close=102.0, brick_dir=1, st_dir=1, is_reversal_brick=False)
    assert len(sigs) == 1
    assert sigs[0][0] == "ZONE_BREAKOUT"
    assert sigs[0][2] == "BUY"
    print("  -> Reference Zones & Fibo Corridors: PASSED")


def test_confluence_filter_stack():
    print("[TEST 4/6] Validating 9-Layer Confluence Filter Stack...")
    filters = ConfluenceFilterStack(
        max_daily_trades=12,
        max_trades_per_zone=4,
        zone_streak_bricks=3,
        use_renko_ema=True,
        use_h1_ema50=True,
    )
    zones = ReferenceZoneEngine()
    zone = zones.set_zone(ZoneType.FIRST_RED, high=100.0, low=50.0, color=ZoneColor.GREEN)

    # Test BUY signal meeting all conditions:
    # streak = 3, st_dir = 1, EMA5 > EMA9, price >= H1 EMA50, price not inside chop
    passed, reason = filters.validate_signal(
        direction="BUY",
        zone=zone,
        price=105.0,
        bar_num=3,
        st_dir=1,
        ema5=104.0,
        ema9=100.0,
        h1_ema50=100.0,
        ai_renko_status="READY",
        ai_renko_dir=1,
        zone_engine=zones,
    )
    assert passed is True, f"Expected confluence to pass, failed with: {reason}"

    # Streak failing (bar_num = 2 < 3)
    passed, reason = filters.validate_signal(
        direction="BUY",
        zone=zone,
        price=105.0,
        bar_num=2,
        st_dir=1,
        ema5=104.0,
        ema9=100.0,
        h1_ema50=100.0,
        ai_renko_status="READY",
        ai_renko_dir=1,
        zone_engine=zones,
    )
    assert passed is False
    assert "Layer 4 Fail" in reason

    # Test no_zones=True mode:
    # Price is inside a RED zone (which would normally fail Layer 7 for BUY),
    # but with no_zones=True, zone checks are bypassed and mid-air signal passes!
    zones.set_zone(ZoneType.FIRST_RED, high=100.0, low=50.0, color=ZoneColor.RED)
    filter_no_zones = ConfluenceFilterStack(
        max_daily_trades=12,
        max_trades_per_zone=4,
        zone_streak_bricks=3,
        use_renko_ema=True,
        use_h1_ema50=True,
        no_zones=True,
    )
    passed_nz, reason_nz = filter_no_zones.validate_signal(
        direction="BUY",
        zone=None,
        price=75.0,
        bar_num=3,
        st_dir=1,
        ema5=104.0,
        ema9=100.0,
        h1_ema50=70.0,
        ai_renko_status="READY",
        ai_renko_dir=1,
        zone_engine=zones,
    )
    assert passed_nz is True, f"no_zones=True should bypass zone checks, got: {reason_nz}"

    print("  -> 9-Layer Confluence Filter Stack: PASSED")


def test_trailing_stop_engine():
    print("[TEST 5/6] Validating Trailing Stop Engine & Spread Guard...")
    engine = TrailingStopEngine(
        brick_size=2.0,
        trail_act_bricks=4.0,  # 8.0 pts profit
        trail_distance_bricks=4.0,  # 8.0 pts trail gap
        spread_guard_mult=1.0,
    )

    pos = TrailingPositionState(
        ticket=1001,
        symbol="XAUUSD",
        direction="BUY",
        open_price=2600.0,
        current_sl=2590.0,
    )

    # Initial tick at open: bid = 2600.0, ask = 2600.2
    mod, new_sl, _ = engine.evaluate_tick(pos, bid=2600.0, ask=2600.2)
    assert mod is False, "Should not modify before activation profit"

    # Price moves to +8.0 pts profit (bid = 2608.0) -> Activation threshold reached!
    mod, new_sl, reason = engine.evaluate_tick(pos, bid=2608.0, ask=2608.2)
    assert mod is True
    # Breakeven + 0.1 brick = 2600.0 + 0.2 = 2600.2
    assert abs(new_sl - 2600.2) < 1e-4, f"Expected BE SL 2600.2, got {new_sl}"
    pos.current_sl = new_sl

    # Price advances further to bid = 2620.0
    mod, new_sl, reason = engine.evaluate_tick(pos, bid=2620.0, ask=2620.2)
    assert mod is True
    assert new_sl > 2600.2
    print(f"  -> Trailing SL stepped to {new_sl:.2f}: PASSED")


def test_zero_external_dependencies():
    print("[TEST 6/6] Verifying Zero External Directory Dependencies...")
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    py_files = glob.glob(os.path.join(workspace_dir, "**", "*.py"), recursive=True)

    # Disallow imports or paths pointing to other folders (e.g. C:\Users\..., D:\other...)
    for py_file in py_files:
        if os.path.abspath(py_file) == os.path.abspath(__file__):
            continue
        with open(py_file, "r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, 1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                # Check for sys.path modifications pointing outside this workspace
                if "sys.path" in line and not any(k in line for k in ["os.path.dirname", "WORKSPACE_DIR", "sys.path.insert"]):
                    raise AssertionError(f"Unexpected sys.path modification in {py_file}:{line_no} -> {line}")
                # Check for absolute directory path strings pointing to outside folders
                if re.search(r"['\"][A-Za-z]:[/\\](?!(?:MT5Renko))", line):
                    raise AssertionError(f"Disallowed external directory path in {py_file}:{line_no} -> {line}")

    print(f"  -> Scanned {len(py_files)} Python files. Zero external references found: PASSED")


if __name__ == "__main__":
    print("=" * 60)
    print("  RUNNING RK RENKO V4 FULL SYSTEM VERIFICATION")
    print("=" * 60)
    test_renko_brick_engine()
    test_supertrend_and_ema()
    test_zone_corridors_and_signals()
    test_confluence_filter_stack()
    test_trailing_stop_engine()
    test_zero_external_dependencies()
    print("=" * 60)
    print("  ALL TESTS PASSED SUCCESSFULLY (6/6)!")
    print("=" * 60)
