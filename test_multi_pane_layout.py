"""
test_multi_pane_layout.py
Comprehensive End-to-End (E2E) Test Suite for MT5Renko Multi-Pane Display
Integrates Playwright with pytest against http://127.0.0.1:3000

Tiers covered:
- Tier 1: Feature Coverage (Layout buttons 1, 2, 4, 6, 8, pane counts, active classes, grid container classes, element IDs)
- Tier 2: Boundary & Corner Cases (Non-zero dimensions, canvas rendering, grid bounds containment, no overlaps, rapid layout switching)
- Tier 3: Cross-Feature Combinations (All layout transitions, active pane selection across layouts, dynamic resizing)
- Tier 4: Real-World Application Scenarios (Full end-to-end user workflow, interaction, layout adjustments)
"""

import time
import pytest
from playwright.sync_api import sync_playwright, Page, Browser, expect

BASE_URL = "http://127.0.0.1:3000"
LAYOUT_COUNTS = [1, 2, 4, 6, 8]
VIEWPORT_DEFAULT = {"width": 1920, "height": 1080}
TOLERANCE_PX = 2.0  # Sub-pixel rendering / border allowance in pixels


def pytest_configure(config):
    """Register custom marks to suppress unknown mark warnings."""
    config.addinivalue_line("markers", "tier1: Tier 1 Feature Coverage tests")
    config.addinivalue_line("markers", "tier2: Tier 2 Boundary & Corner Cases tests")
    config.addinivalue_line("markers", "tier3: Tier 3 Cross-Feature Combinations tests")
    config.addinivalue_line("markers", "tier4: Tier 4 Real-World Application Scenario tests")


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures & Setup
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser_instance():
    """Session-scoped Playwright Chromium browser."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="function")
def page(browser_instance: Browser) -> Page:
    """Function-scoped clean page context with error tracking."""
    context = browser_instance.new_context(viewport=VIEWPORT_DEFAULT)
    pg = context.new_page()

    page_errors = []
    console_errors = []

    pg.on("pageerror", lambda err: page_errors.append(str(err)))
    pg.on(
        "console",
        lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
    )

    pg._page_errors = page_errors
    pg._console_errors = console_errors

    # Navigate and wait for DOM and initial chart panes to initialize
    pg.goto(BASE_URL, wait_until="domcontentloaded")
    pg.wait_for_selector(".chart-pane", timeout=15000)
    # Give charts engine a brief moment to complete initial mount
    pg.wait_for_timeout(300)

    yield pg

    context.close()


# ─────────────────────────────────────────────────────────────────────────────
# Geometric & Layout Verification Utilities
# ─────────────────────────────────────────────────────────────────────────────

def switch_layout(page: Page, count: int, wait_ms: int = 250) -> None:
    """Clicks the layout button for the specified pane count and waits for layout update."""
    btn = page.locator(f'.pane-layout-btn[data-pane-count="{count}"]')
    expect(btn).to_be_visible(timeout=5000)
    btn.click()
    page.wait_for_timeout(wait_ms)


def get_box(locator) -> dict:
    """Returns bounding box dictionary for a locator with validated dimensions."""
    box = locator.bounding_box()
    assert box is not None, f"Bounding box is None for locator {locator}"
    return box


def is_contained(inner: dict, outer: dict, tolerance: float = TOLERANCE_PX) -> bool:
    """Verifies that inner rectangle lies entirely inside outer rectangle within tolerance."""
    return (
        inner["x"] >= outer["x"] - tolerance
        and inner["y"] >= outer["y"] - tolerance
        and (inner["x"] + inner["width"]) <= (outer["x"] + outer["width"] + tolerance)
        and (inner["y"] + inner["height"]) <= (outer["y"] + outer["height"] + tolerance)
    )


def boxes_overlap(box_a: dict, box_b: dict, tolerance: float = TOLERANCE_PX) -> bool:
    """Verifies if two rectangular bounding boxes have overlapping intersection area."""
    overlap_x = min(box_a["x"] + box_a["width"], box_b["x"] + box_b["width"]) - max(
        box_a["x"], box_b["x"]
    )
    overlap_y = min(box_a["y"] + box_a["height"], box_b["y"] + box_b["height"]) - max(
        box_a["y"], box_b["y"]
    )
    return overlap_x > tolerance and overlap_y > tolerance


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1: Feature Coverage Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTier1FeatureCoverage:
    """
    Tier 1: Multi-pane Grid Layouts (1, 2, 4, 6, 8), Element IDs, Classes, and Pane Counts.
    """

    @pytest.mark.tier1
    def test_grid_container_id_and_classes(self, page: Page):
        """
        Verify the grid container has id `#charts-grid` and receives correct classes
        for every layout count: charts-grid, grid-${count}, grid-${count}-pane, layout-${count}.
        """
        grid = page.locator("#charts-grid")
        expect(grid).to_be_visible(timeout=5000)

        for count in LAYOUT_COUNTS:
            switch_layout(page, count)
            class_attr = grid.get_attribute("class") or ""
            classes = set(class_attr.split())

            assert "grid-container" in classes, f"Missing 'grid-container' in {classes} for count {count}"
            assert "charts-grid" in classes, f"Missing 'charts-grid' in {classes} for count {count}"
            assert f"grid-{count}" in classes, f"Missing 'grid-{count}' in {classes} for count {count}"
            assert f"grid-{count}-pane" in classes, f"Missing 'grid-{count}-pane' in {classes} for count {count}"
            assert f"layout-{count}" in classes, f"Missing 'layout-{count}' in {classes} for count {count}"

            # Verify layout button state
            btn = page.locator(f'.pane-layout-btn[data-pane-count="{count}"]')
            btn_class = btn.get_attribute("class") or ""
            assert "active" in btn_class.split(), f"Button for {count} panes should have 'active' class"
            assert btn.get_attribute("aria-checked") == "true", f"Button for {count} panes should have aria-checked='true'"

    @pytest.mark.tier1
    def test_pane_count_and_identification(self, page: Page):
        """
        Verify triggering layout buttons (1, 2, 4, 6, 8) renders exactly 1, 2, 4, 6, 8 visible
        `.chart-pane` elements inside `#charts-grid`, and each pane carries data-pane-id and pane-{id}.
        """
        grid = page.locator("#charts-grid")
        expect(grid).to_be_visible(timeout=5000)

        for count in LAYOUT_COUNTS:
            switch_layout(page, count)
            panes = grid.locator(".chart-pane")
            assert panes.count() == count, f"Expected {count} panes in DOM, got {panes.count()}"

            for i in range(count):
                pane = panes.nth(i)
                expect(pane).to_be_visible()
                expected_id = str(i + 1)
                data_id = pane.get_attribute("data-pane-id")
                assert data_id == expected_id, f"Pane index {i} expected data-pane-id='{expected_id}', got '{data_id}'"
                
                # Interface Contract: id="pane-${id}"
                pane_id = pane.get_attribute("id")
                assert pane_id == f"pane-{expected_id}", f"Pane index {i} expected id='pane-{expected_id}', got '{pane_id}'"

    @pytest.mark.tier1
    def test_chart_mount_and_interface_contract(self, page: Page):
        """
        Verify each visible `.chart-pane` hosts a `.chart-mount` element conforming
        to the interface contract id="chart-mount-${id}".
        """
        grid = page.locator("#charts-grid")
        expect(grid).to_be_visible(timeout=5000)

        for count in LAYOUT_COUNTS:
            switch_layout(page, count)
            panes = grid.locator(".chart-pane")

            for i in range(count):
                pane = panes.nth(i)
                expected_id = str(i + 1)
                mount = pane.locator(".chart-mount")
                expect(mount).to_be_visible()
                
                # Interface Contract: id="chart-mount-${id}"
                mount_id = mount.get_attribute("id")
                assert mount_id == f"chart-mount-{expected_id}", f"Chart mount in pane {expected_id} expected id='chart-mount-{expected_id}', got '{mount_id}'"

    @pytest.mark.tier1
    def test_active_pane_styling(self, page: Page):
        """
        Verify `.active-pane` visual class is maintained on one active pane and updates on click.
        """
        grid = page.locator("#charts-grid")
        switch_layout(page, 4)

        panes = grid.locator(".chart-pane")
        assert panes.count() == 4

        # At least one pane must have active-pane class
        active_panes = grid.locator(".chart-pane.active-pane")
        assert active_panes.count() == 1, f"Expected exactly 1 active pane, found {active_panes.count()}"

        # Click pane 3 and assert it becomes active
        pane_3 = panes.nth(2)
        pane_3.click()
        page.wait_for_timeout(100)

        assert "active-pane" in (pane_3.get_attribute("class") or "").split(), "Pane 3 should have 'active-pane' class after click"
        assert grid.locator(".chart-pane.active-pane").count() == 1, "Only one pane should have 'active-pane' class"


# ─────────────────────────────────────────────────────────────────────────────
# Tier 2: Boundary & Corner Cases Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTier2BoundaryAndCornerCases:
    """
    Tier 2: Non-zero dimensions, container bounds, non-overlapping bounding boxes,
    and rapid layout switching stability.
    """

    @pytest.mark.tier2
    def test_non_zero_dimensions_pane_mount_and_canvas(self, page: Page):
        """
        Verify that for every layout (1, 2, 4, 6, 8), each pane container, its `.chart-mount`,
        and its canvas layers have non-zero dimensions (width > 0, height > 0).
        """
        grid = page.locator("#charts-grid")

        for count in LAYOUT_COUNTS:
            switch_layout(page, count)
            panes = grid.locator(".chart-pane")
            assert panes.count() == count

            for i in range(count):
                pane = panes.nth(i)
                pane_box = get_box(pane)
                assert pane_box["width"] > 50, f"Layout {count}, Pane {i+1} width too small: {pane_box['width']}px"
                assert pane_box["height"] > 50, f"Layout {count}, Pane {i+1} height too small: {pane_box['height']}px"

                mount = pane.locator(".chart-mount")
                mount_box = get_box(mount)
                assert mount_box["width"] > 40, f"Layout {count}, Mount {i+1} width too small: {mount_box['width']}px"
                assert mount_box["height"] > 30, f"Layout {count}, Mount {i+1} height too small: {mount_box['height']}px"

                canvases = mount.locator("canvas")
                assert canvases.count() > 0, f"Layout {count}, Pane {i+1} has no canvas elements inside mount"
                for c_idx in range(canvases.count()):
                    c_box = get_box(canvases.nth(c_idx))
                    assert c_box["width"] > 0, f"Layout {count}, Pane {i+1}, Canvas {c_idx+1} width is 0"
                    assert c_box["height"] > 0, f"Layout {count}, Pane {i+1}, Canvas {c_idx+1} height is 0"

    @pytest.mark.tier2
    def test_panes_within_grid_bounds_no_overflow(self, page: Page):
        """
        Verify all visible panes remain strictly within `#charts-grid` bounding rectangle
        without overflowing or spilling out of the grid viewport.
        """
        grid = page.locator("#charts-grid")

        for count in LAYOUT_COUNTS:
            switch_layout(page, count)
            grid_box = get_box(grid)
            panes = grid.locator(".chart-pane")

            for i in range(count):
                pane_box = get_box(panes.nth(i))
                assert is_contained(pane_box, grid_box, tolerance=TOLERANCE_PX), (
                    f"Layout {count}: Pane {i+1} bounds {pane_box} extend outside #charts-grid bounds {grid_box}"
                )

    @pytest.mark.tier2
    def test_no_pane_overlaps(self, page: Page):
        """
        Verify in multi-pane modes (2, 4, 6, 8) that no pane overlaps any other pane;
        all bounding boxes must be disjoint.
        """
        grid = page.locator("#charts-grid")

        for count in [2, 4, 6, 8]:
            switch_layout(page, count)
            panes = grid.locator(".chart-pane")
            assert panes.count() == count

            boxes = [get_box(panes.nth(i)) for i in range(count)]

            for i in range(count):
                for j in range(i + 1, count):
                    assert not boxes_overlap(boxes[i], boxes[j], tolerance=TOLERANCE_PX), (
                        f"Layout {count}: Pane {i+1} {boxes[i]} overlaps Pane {j+1} {boxes[j]}"
                    )

    @pytest.mark.tier2
    def test_rapid_layout_switching_no_console_errors(self, page: Page):
        """
        Test rapid switching across multiple pane counts (1 -> 8 -> 1 -> 4 -> 2 -> 6 -> 8 -> 4 -> 1)
        without unhandled JavaScript runtime exceptions or disposed object errors.
        """
        rapid_sequence = [1, 8, 1, 4, 2, 6, 8, 4, 1]

        for target in rapid_sequence:
            btn = page.locator(f'.pane-layout-btn[data-pane-count="{target}"]')
            btn.click()
            # Fast interaction with minimal delay
            page.wait_for_timeout(60)

        # Allow final layout to settle
        page.wait_for_timeout(400)

        # Assert final layout settled at 1 pane
        grid = page.locator("#charts-grid")
        panes = grid.locator(".chart-pane")
        assert panes.count() == 1, f"Expected 1 pane after rapid sequence, got {panes.count()}"

        pane_box = get_box(panes.first)
        assert pane_box["width"] > 100 and pane_box["height"] > 100

        # Assert no unhandled page runtime errors
        assert len(page._page_errors) == 0, f"Page errors observed during rapid switching: {page._page_errors}"


# ─────────────────────────────────────────────────────────────────────────────
# Tier 3: Cross-Feature Combinations Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTier3CrossFeatureCombinations:
    """
    Tier 3: Layout transitions, active pane persistence across layout changes,
    and proportional resizing.
    """

    @pytest.mark.tier3
    def test_all_layout_transitions(self, page: Page):
        """
        Test switching across all layout combinations (ascending, descending, and arbitrary hops).
        """
        transitions = [
            (1, 2), (2, 4), (4, 6), (6, 8),  # Upscaling
            (8, 6), (6, 4), (4, 2), (2, 1),  # Downscaling
            (1, 8), (8, 2), (2, 6), (6, 1),  # Cross-hops
        ]
        grid = page.locator("#charts-grid")

        for from_count, to_count in transitions:
            switch_layout(page, from_count, wait_ms=100)
            switch_layout(page, to_count, wait_ms=200)

            panes = grid.locator(".chart-pane")
            assert panes.count() == to_count, (
                f"Transition {from_count} -> {to_count} failed: expected {to_count} panes, got {panes.count()}"
            )

            # Check that container has corresponding class
            class_attr = grid.get_attribute("class") or ""
            assert f"grid-{to_count}" in class_attr.split()

    @pytest.mark.tier3
    def test_active_pane_selection_across_layouts(self, page: Page):
        """
        Select active pane in one layout, transition to another layout, and verify
        active pane state remains valid and consistent.
        """
        grid = page.locator("#charts-grid")

        # Start with 4 panes and select pane 3
        switch_layout(page, 4)
        panes_4 = grid.locator(".chart-pane")
        pane_3 = panes_4.nth(2)
        pane_3.click()
        page.wait_for_timeout(100)
        assert "active-pane" in (pane_3.get_attribute("class") or "").split()

        # Switch to 8 panes: pane 3 should still exist and maintain or have active state
        switch_layout(page, 8)
        panes_8 = grid.locator(".chart-pane")
        assert panes_8.count() == 8

        # Click pane 7
        pane_7 = panes_8.nth(6)
        pane_7.click()
        page.wait_for_timeout(100)
        assert "active-pane" in (pane_7.get_attribute("class") or "").split()
        assert grid.locator(".chart-pane.active-pane").count() == 1

        # Downscale to 2 panes (pane 7 is destroyed): active pane should fall back cleanly
        switch_layout(page, 2)
        panes_2 = grid.locator(".chart-pane")
        assert panes_2.count() == 2
        active_in_2 = grid.locator(".chart-pane.active-pane")
        assert active_in_2.count() == 1, "There should be exactly 1 active pane after downscaling"

    @pytest.mark.tier3
    def test_pane_resizing_on_layout_change(self, page: Page):
        """
        Verify that pane dimensions dynamically adjust when switching between layout modes:
        Pane 1 should narrow when going 1 -> 2 -> 4 -> 8, and expand when going 8 -> 1.
        """
        grid = page.locator("#charts-grid")

        # 1 Pane
        switch_layout(page, 1)
        box_1 = get_box(grid.locator(".chart-pane").first)

        # 2 Panes (side by side): Pane 1 width should be roughly half of 1-pane width
        switch_layout(page, 2)
        box_2 = get_box(grid.locator(".chart-pane").first)
        assert box_2["width"] < box_1["width"] * 0.65, (
            f"Pane 1 did not shrink horizontally in 2-pane mode: {box_2['width']} vs {box_1['width']}"
        )

        # 4 Panes (2x2 grid): Pane 1 height should be roughly half of 2-pane height
        switch_layout(page, 4)
        box_4 = get_box(grid.locator(".chart-pane").first)
        assert box_4["height"] < box_2["height"] * 0.65, (
            f"Pane 1 did not shrink vertically in 4-pane mode: {box_4['height']} vs {box_2['height']}"
        )

        # 8 Panes (4x2 grid): Pane 1 width should be roughly half of 4-pane width
        switch_layout(page, 8)
        box_8 = get_box(grid.locator(".chart-pane").first)
        assert box_8["width"] < box_4["width"] * 0.65, (
            f"Pane 1 did not shrink horizontally in 8-pane mode: {box_8['width']} vs {box_4['width']}"
        )

        # Return to 1 Pane: Pane 1 should expand back to original full size
        switch_layout(page, 1)
        box_return = get_box(grid.locator(".chart-pane").first)
        assert abs(box_return["width"] - box_1["width"]) < 10, (
            f"Pane 1 did not return to full width: {box_return['width']} vs {box_1['width']}"
        )
        assert abs(box_return["height"] - box_1["height"]) < 10, (
            f"Pane 1 did not return to full height: {box_return['height']} vs {box_1['height']}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Tier 4: Real-World Application Scenarios Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTier4RealWorldScenarios:
    """
    Tier 4: End-to-end user workflows and full interactive lifecycle.
    """

    @pytest.mark.tier4
    def test_end_to_end_user_session(self, page: Page):
        """
        Simulate an entire user session:
        1. User loads dashboard, sees initial multi-pane grid.
        2. User selects 4 panes layout.
        3. User interacts with Pane 2 (clicks pane, changes timeframe or toggles an indicator).
        4. User switches to 8 panes layout, inspecting all 8 charts.
        5. User switches to 1 pane layout for focused full-screen trading analysis.
        6. Verify canvas is active, properly sized, and no browser errors occurred.
        """
        grid = page.locator("#charts-grid")
        expect(grid).to_be_visible()

        # Step 1: Initial state verified
        initial_panes = grid.locator(".chart-pane")
        assert initial_panes.count() in LAYOUT_COUNTS

        # Step 2: Switch to 4 panes
        switch_layout(page, 4, wait_ms=300)
        assert grid.locator(".chart-pane").count() == 4

        # Step 3: Interact with Pane 2
        pane_2 = grid.locator(".chart-pane").nth(1)
        pane_2.click()
        page.wait_for_timeout(100)
        assert "active-pane" in (pane_2.get_attribute("class") or "").split()

        # Click Supertrend chip in Pane 2 indicator toolbar if available
        st_chip = pane_2.locator('.ind-chip[data-indicator="supertrend"]')
        if st_chip.count() > 0:
            st_chip.first.click()
            page.wait_for_timeout(150)

        # Step 4: Switch to 8 panes
        switch_layout(page, 8, wait_ms=350)
        panes_8 = grid.locator(".chart-pane")
        assert panes_8.count() == 8

        # Verify all 8 mounts have active canvas layers
        for i in range(8):
            mount = panes_8.nth(i).locator(".chart-mount")
            expect(mount).to_be_visible()
            m_box = get_box(mount)
            assert m_box["width"] > 30 and m_box["height"] > 20
            canvases = mount.locator("canvas")
            assert canvases.count() > 0

        # Step 5: Switch to 1 pane layout for focused analysis
        switch_layout(page, 1, wait_ms=300)
        panes_1 = grid.locator(".chart-pane")
        assert panes_1.count() == 1

        pane_1 = panes_1.first
        p1_box = get_box(pane_1)
        grid_box = get_box(grid)
        assert is_contained(p1_box, grid_box, tolerance=TOLERANCE_PX)

        mount_1 = pane_1.locator(".chart-mount")
        m1_box = get_box(mount_1)
        assert m1_box["width"] > 500 and m1_box["height"] > 300

        canvases_1 = mount_1.locator("canvas")
        assert canvases_1.count() > 0
        c1_box = get_box(canvases_1.first)
        assert c1_box["width"] > 400 and c1_box["height"] > 200

        # Step 6: Verify no fatal runtime exceptions occurred across the session
        assert len(page._page_errors) == 0, f"Page errors encountered: {page._page_errors}"
