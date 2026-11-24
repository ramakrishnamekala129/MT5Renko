import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1600, 'height': 900})
        await page.goto('http://127.0.0.1:3000')
        await page.wait_for_timeout(2000)

        # 1-pane layout
        await page.evaluate("""() => {
            const btn = document.querySelector('.panes-btn[data-panes="1"]');
            if (btn) btn.click();
        }""")
        await page.wait_for_timeout(2000)

        # Set symbol XAUUSD and timeframe 15m on pane 1
        await page.evaluate("""() => {
            const pane = window.ChartManager.STATE.panes[1];
            pane.symbol = 'XAUUSD';
            pane.timeframe = '15m';
            const symInp = pane.element.querySelector('.symbol-input');
            if (symInp) symInp.value = 'XAUUSD';
            const tfSel = pane.element.querySelector('.timeframe-select');
            if (tfSel) tfSel.value = '15m';
            window.ChartManager.loadChartData(1);
        }""")
        await page.wait_for_timeout(4000)

        # Turn ON VWAP
        await page.evaluate("""() => {
            const pane = window.ChartManager.STATE.panes[1];
            const vwapBtn = pane.element.querySelector('.ind-chip[data-indicator="vwap"]');
            if (vwapBtn && !pane.activeIndicators.vwap) {
                vwapBtn.click();
            } else {
                window.ChartManager.renderIndicator(pane, 'vwap');
            }
        }""")
        await page.wait_for_timeout(2000)

        res = await page.evaluate("""() => {
            const pane = window.ChartManager.STATE.panes[1];
            const candles = pane.candles;
            const vwapData = window.Indicators.vwap(candles);
            const pool = pane._vwapPool ? pane._vwapPool.vwap : [];
            
            return {
                candlesCount: candles.length,
                vwapPointsCount: vwapData.length,
                first5Points: vwapData.slice(0, 5),
                last5Points: vwapData.slice(-5),
                poolSeriesCount: pool ? pool.length : 0,
                activeIndicators: pane.activeIndicators
            };
        }""")

        print(json.dumps(res, indent=2))
        await page.screenshot(path="test_vwap_screenshot.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
