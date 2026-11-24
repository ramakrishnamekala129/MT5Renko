/**
 * Antigravity // Quant Trading Grid — Technical Indicators Engine
 * Pure in-browser JS. No external dependencies.
 * All functions accept candle arrays: [{time, open, high, low, close, volume}]
 * All overlay functions return: [{time, value}]
 * Band functions return: {upper: [...], middle: [...], lower: [...]}
 * Oscillator functions return: [{time, value}] or multi-line objects
 */

var Indicators = (() => {

    // ─────────────────────────────────────────────
    // SMA — Simple Moving Average
    // ─────────────────────────────────────────────
    function sma(candles, period) {
        const result = [];
        for (let i = period - 1; i < candles.length; i++) {
            let sum = 0;
            for (let j = 0; j < period; j++) {
                sum += candles[i - j].close;
            }
            result.push({ time: candles[i].time, value: sum / period });
        }
        return result;
    }

    // ─────────────────────────────────────────────
    // EMA — Exponential Moving Average
    // ─────────────────────────────────────────────
    function ema(candles, period) {
        if (candles.length < period) return [];
        const k = 2 / (period + 1);
        const result = [];
        // Seed with SMA of first `period` candles
        let prevEma = candles.slice(0, period).reduce((s, c) => s + c.close, 0) / period;
        result.push({ time: candles[period - 1].time, value: prevEma });
        for (let i = period; i < candles.length; i++) {
            const val = candles[i].close * k + prevEma * (1 - k);
            result.push({ time: candles[i].time, value: val });
            prevEma = val;
        }
        return result;
    }

    // ─────────────────────────────────────────────
    // WMA / HMA — Weighted and Hull Moving Averages
    // ─────────────────────────────────────────────
    function wma(candles, period) {
        if (candles.length < period) return [];
        const denom = period * (period + 1) / 2;
        const result = [];
        for (let i = period - 1; i < candles.length; i++) {
            let weighted = 0;
            for (let j = 0; j < period; j++) {
                weighted += candles[i - j].close * (period - j);
            }
            result.push({ time: candles[i].time, value: weighted / denom });
        }
        return result;
    }

    function wmaValues(values, period) {
        if (values.length < period) return [];
        const denom = period * (period + 1) / 2;
        const result = [];
        for (let i = period - 1; i < values.length; i++) {
            let weighted = 0;
            for (let j = 0; j < period; j++) {
                weighted += values[i - j] * (period - j);
            }
            result.push(weighted / denom);
        }
        return result;
    }

    function hma(candles, period = 20) {
        if (candles.length < period) return [];
        const closes = candles.map(c => c.close);
        const half = Math.max(1, Math.floor(period / 2));
        const sqrtPeriod = Math.max(1, Math.floor(Math.sqrt(period)));
        const wmaHalf = wmaValues(closes, half);
        const wmaFull = wmaValues(closes, period);
        const offset = period - half;
        const raw = wmaFull.map((full, i) => (2 * wmaHalf[i + offset]) - full);
        const smooth = wmaValues(raw, sqrtPeriod);
        const startIndex = period - 1 + sqrtPeriod - 1;
        return smooth.map((value, i) => ({
            time: candles[startIndex + i]?.time,
            value
        })).filter(item => item.time != null);
    }

    // ─────────────────────────────────────────────
    // EMA on raw value array (used internally for MACD)
    // ─────────────────────────────────────────────
    function emaValues(values, period) {
        if (values.length < period) return [];
        const k = 2 / (period + 1);
        const result = [];
        let prevEma = values.slice(0, period).reduce((s, v) => s + v, 0) / period;
        result.push(prevEma);
        for (let i = period; i < values.length; i++) {
            const val = values[i] * k + prevEma * (1 - k);
            result.push(val);
            prevEma = val;
        }
        return result;
    }

    // ─────────────────────────────────────────────
    // Bollinger Bands — period + stddev multiplier
    // ─────────────────────────────────────────────
    function bollingerBands(candles, period = 20, stdDev = 2) {
        const upper = [], middle = [], lower = [];
        for (let i = period - 1; i < candles.length; i++) {
            const slice = candles.slice(i - period + 1, i + 1);
            const mean = slice.reduce((s, c) => s + c.close, 0) / period;
            const variance = slice.reduce((s, c) => s + Math.pow(c.close - mean, 2), 0) / period;
            const sd = Math.sqrt(variance);
            const t = candles[i].time;
            upper.push({ time: t, value: mean + stdDev * sd });
            middle.push({ time: t, value: mean });
            lower.push({ time: t, value: mean - stdDev * sd });
        }
        return { upper, middle, lower };
    }

    // ─────────────────────────────────────────────
    // VWAP — Volume Weighted Average Price (daily session anchored)
    // ─────────────────────────────────────────────
    function vwap(candles) {
        if (!candles || candles.length === 0) return [];
        const result = [];
        let cumVolume = 0;
        let cumTPV = 0;
        let lastDay = null;

        for (const c of candles) {
            const d = new Date(c.time * 1000);
            const dayKey = d.getUTCFullYear() * 10000 + (d.getUTCMonth() + 1) * 100 + d.getUTCDate();
            if (lastDay === null || dayKey !== lastDay) {
                lastDay = dayKey;
                cumVolume = 0;
                cumTPV = 0;
            }

            const tp = (c.high + c.low + c.close) / 3;
            const vol = (typeof c.volume === 'number' && !isNaN(c.volume) && c.volume > 0) ? c.volume : 1;
            cumTPV += tp * vol;
            cumVolume += vol;

            result.push({
                time: c.time,
                value: cumVolume > 0 ? (cumTPV / cumVolume) : c.close,
                dayKey: dayKey
            });
        }
        return result;
    }

    // ─────────────────────────────────────────────
    // Ichimoku Cloud
    // ─────────────────────────────────────────────
    function midpointRange(candles, endIndex, period) {
        let high = -Infinity;
        let low = Infinity;
        for (let i = endIndex - period + 1; i <= endIndex; i++) {
            high = Math.max(high, candles[i].high);
            low = Math.min(low, candles[i].low);
        }
        return (high + low) / 2;
    }

    function ichimoku(candles, tenkan = 9, kijun = 26, spanB = 52) {
        const conversion = [], base = [], spanA = [], spanBLine = [];
        const minPeriod = Math.max(tenkan, kijun);
        for (let i = tenkan - 1; i < candles.length; i++) {
            conversion.push({ time: candles[i].time, value: midpointRange(candles, i, tenkan) });
        }
        for (let i = kijun - 1; i < candles.length; i++) {
            base.push({ time: candles[i].time, value: midpointRange(candles, i, kijun) });
        }
        for (let i = minPeriod - 1; i < candles.length; i++) {
            const conv = midpointRange(candles, i, tenkan);
            const kij = midpointRange(candles, i, kijun);
            spanA.push({ time: candles[i].time, value: (conv + kij) / 2 });
        }
        for (let i = spanB - 1; i < candles.length; i++) {
            spanBLine.push({ time: candles[i].time, value: midpointRange(candles, i, spanB) });
        }
        return { conversion, base, spanA, spanB: spanBLine };
    }

    // ─────────────────────────────────────────────
    // RSI — Relative Strength Index
    // ─────────────────────────────────────────────
    function rsi(candles, period = 14) {
        if (candles.length < period + 1) return [];
        const result = [];
        let avgGain = 0, avgLoss = 0;

        // Initial average gain/loss
        for (let i = 1; i <= period; i++) {
            const delta = candles[i].close - candles[i - 1].close;
            if (delta > 0) avgGain += delta;
            else avgLoss -= delta;
        }
        avgGain /= period;
        avgLoss /= period;

        const rs0 = avgLoss === 0 ? 100 : avgGain / avgLoss;
        result.push({ time: candles[period].time, value: 100 - 100 / (1 + rs0) });

        for (let i = period + 1; i < candles.length; i++) {
            const delta = candles[i].close - candles[i - 1].close;
            const gain = delta > 0 ? delta : 0;
            const loss = delta < 0 ? -delta : 0;
            avgGain = (avgGain * (period - 1) + gain) / period;
            avgLoss = (avgLoss * (period - 1) + loss) / period;
            const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
            result.push({ time: candles[i].time, value: 100 - 100 / (1 + rs) });
        }
        return result;
    }

    // ─────────────────────────────────────────────
    // MACD — Moving Average Convergence Divergence
    // Returns { macdLine, signalLine, histogram }
    // ─────────────────────────────────────────────
    function macd(candles, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
        if (candles.length < slowPeriod + signalPeriod) return null;
        const closes = candles.map(c => c.close);
        const emaFastAll = emaValues(closes, fastPeriod);
        const emaSlowAll = emaValues(closes, slowPeriod);

        // Align: EMA fast starts at fastPeriod-1, slow at slowPeriod-1
        const offset = slowPeriod - fastPeriod;
        const macdRaw = emaFastAll.slice(offset).map((f, i) => f - emaSlowAll[i]);
        const signalRaw = emaValues(macdRaw, signalPeriod);

        // Time alignment
        const startIndex = slowPeriod - 1; // first candle with both EMAs
        const signalOffset = signalPeriod - 1;

        const macdLine = [], signalLine = [], histogram = [];

        for (let i = signalOffset; i < macdRaw.length; i++) {
            const candleIndex = startIndex + i;
            if (candleIndex >= candles.length) break;
            const t = candles[candleIndex].time;
            const m = macdRaw[i];
            const s = signalRaw[i - signalOffset];
            macdLine.push({ time: t, value: m });
            signalLine.push({ time: t, value: s });
            histogram.push({ time: t, value: m - s, color: (m - s) >= 0 ? 'rgba(0,230,118,0.7)' : 'rgba(255,23,68,0.7)' });
        }

        return { macdLine, signalLine, histogram };
    }

    // ─────────────────────────────────────────────
    // Common panel indicators
    // ─────────────────────────────────────────────
    function momentum(candles, period = 10) {
        if (candles.length <= period) return [];
        const result = [];
        for (let i = period; i < candles.length; i++) {
            result.push({ time: candles[i].time, value: candles[i].close - candles[i - period].close });
        }
        return result;
    }

    function roc(candles, period = 9) {
        if (candles.length <= period) return [];
        const result = [];
        for (let i = period; i < candles.length; i++) {
            const prev = candles[i - period].close;
            result.push({ time: candles[i].time, value: prev !== 0 ? ((candles[i].close - prev) / prev) * 100 : 0 });
        }
        return result;
    }

    function cci(candles, period = 20) {
        if (candles.length < period) return [];
        const tps = candles.map(c => (c.high + c.low + c.close) / 3);
        const result = [];
        for (let i = period - 1; i < candles.length; i++) {
            const slice = tps.slice(i - period + 1, i + 1);
            const mean = slice.reduce((s, v) => s + v, 0) / period;
            const meanDev = slice.reduce((s, v) => s + Math.abs(v - mean), 0) / period;
            result.push({ time: candles[i].time, value: meanDev ? (tps[i] - mean) / (0.015 * meanDev) : 0 });
        }
        return result;
    }

    function stochastic(candles, kPeriod = 14, dPeriod = 3, smooth = 3) {
        if (candles.length < kPeriod + smooth + dPeriod) return { kLine: [], dLine: [] };
        const rawK = [];
        for (let i = kPeriod - 1; i < candles.length; i++) {
            const slice = candles.slice(i - kPeriod + 1, i + 1);
            const high = Math.max(...slice.map(c => c.high));
            const low = Math.min(...slice.map(c => c.low));
            rawK.push({ time: candles[i].time, value: high !== low ? ((candles[i].close - low) / (high - low)) * 100 : 50 });
        }
        const kValues = sma(rawK.map(item => ({ time: item.time, close: item.value })), smooth);
        const dValues = sma(kValues.map(item => ({ time: item.time, close: item.value })), dPeriod);
        return { kLine: kValues, dLine: dValues };
    }

    function obv(candles) {
        if (!candles || candles.length === 0) return [];
        const result = [{ time: candles[0].time, value: candles[0].volume || 0 }];
        let current = candles[0].volume || 0;
        for (let i = 1; i < candles.length; i++) {
            if (candles[i].close > candles[i - 1].close) current += candles[i].volume || 0;
            else if (candles[i].close < candles[i - 1].close) current -= candles[i].volume || 0;
            result.push({ time: candles[i].time, value: current });
        }
        return result;
    }

    function adx(candles, period = 14) {
        if (candles.length < period * 2) return { adxLine: [], plusDI: [], minusDI: [] };
        const tr = [], plusDM = [], minusDM = [];
        for (let i = 1; i < candles.length; i++) {
            const upMove = candles[i].high - candles[i - 1].high;
            const downMove = candles[i - 1].low - candles[i].low;
            plusDM.push(upMove > downMove && upMove > 0 ? upMove : 0);
            minusDM.push(downMove > upMove && downMove > 0 ? downMove : 0);
            tr.push(Math.max(
                candles[i].high - candles[i].low,
                Math.abs(candles[i].high - candles[i - 1].close),
                Math.abs(candles[i].low - candles[i - 1].close)
            ));
        }

        let trSm = tr.slice(0, period).reduce((s, v) => s + v, 0);
        let plusSm = plusDM.slice(0, period).reduce((s, v) => s + v, 0);
        let minusSm = minusDM.slice(0, period).reduce((s, v) => s + v, 0);
        const dx = [], plusDI = [], minusDI = [];

        for (let i = period; i < tr.length; i++) {
            trSm = trSm - trSm / period + tr[i];
            plusSm = plusSm - plusSm / period + plusDM[i];
            minusSm = minusSm - minusSm / period + minusDM[i];
            const plus = trSm ? 100 * (plusSm / trSm) : 0;
            const minus = trSm ? 100 * (minusSm / trSm) : 0;
            const value = (plus + minus) ? 100 * Math.abs(plus - minus) / (plus + minus) : 0;
            const t = candles[i + 1].time;
            plusDI.push({ time: t, value: plus });
            minusDI.push({ time: t, value: minus });
            dx.push({ time: t, value });
        }

        const adxLine = sma(dx.map(item => ({ time: item.time, close: item.value })), period);
        return { adxLine, plusDI, minusDI };
    }

    // ─────────────────────────────────────────────
    // ATR — Average True Range (Helper)
    // ─────────────────────────────────────────────
    function atr(candles, period = 200) {
        if (candles.length === 0) return [];
        const result = [];
        let sumTR = 0;
        let prevClose = candles[0].close;
        for (let i = 0; i < candles.length; i++) {
            const c = candles[i];
            const tr = i === 0 ? (c.high - c.low) : Math.max(
                c.high - c.low,
                Math.abs(c.high - prevClose),
                Math.abs(c.low - prevClose)
            );
            prevClose = c.close;

            if (i < period) {
                sumTR += tr;
                if (i === period - 1) {
                    result.push({ time: c.time, value: sumTR / period });
                } else {
                    result.push({ time: c.time, value: tr }); // seed values
                }
            } else {
                const prevAtr = result[i - 1].value;
                const currentAtr = (prevAtr * (period - 1) + tr) / period;
                result.push({ time: c.time, value: currentAtr });
            }
        }
        return result;
    }

    // ─────────────────────────────────────────────
    // Supertrend
    // ─────────────────────────────────────────────
    function supertrend(candles, period = 10, multiplier = 3) {
        const atrVals = atr(candles, period);
        if (!atrVals || atrVals.length === 0) return { line: [], direction: [] };
        const atrMap = new Map(atrVals.map(item => [item.time, item.value]));
        const line = [], direction = [];
        let finalUpper = null, finalLower = null, trend = 1;

        for (let i = 1; i < candles.length; i++) {
            const c = candles[i];
            const prev = candles[i - 1];
            const atrValue = atrMap.get(c.time);
            if (atrValue == null) continue;
            const hl2 = (c.high + c.low) / 2;
            const basicUpper = hl2 + multiplier * atrValue;
            const basicLower = hl2 - multiplier * atrValue;

            finalUpper = finalUpper == null || basicUpper < finalUpper || prev.close > finalUpper ? basicUpper : finalUpper;
            finalLower = finalLower == null || basicLower > finalLower || prev.close < finalLower ? basicLower : finalLower;

            if (trend === -1 && c.close > finalUpper) trend = 1;
            else if (trend === 1 && c.close < finalLower) trend = -1;

            const value = trend === 1 ? finalLower : finalUpper;
            line.push({ time: c.time, value, color: trend === 1 ? '#089981' : '#F23645' });
            direction.push({ time: c.time, value: trend });
        }
        return { line, direction };
    }

    // ─────────────────────────────────────────────
    // Volume Indicator (Helper)
    // ─────────────────────────────────────────────
    function volume(candles) {
        if (!candles || candles.length === 0) return [];
        return candles.map(c => {
            const isBullish = c.close >= c.open;
            return {
                time: c.time,
                value: c.volume || 0,
                color: isBullish ? 'rgba(8, 153, 129, 0.4)' : 'rgba(242, 54, 69, 0.4)'
            };
        });
    }

    // ─────────────────────────────────────────────
    // ─────────────────────────────────────────────
    // SMC — Smart Money Concepts [LuxAlgo]
    // Faithful JavaScript implementation of LuxAlgo Smart Money Concepts (v5)
    // ─────────────────────────────────────────────
    function smc(candles, settings = {}) {
        // Default settings matching LuxAlgo Pine script
        const cfg = {
            mode: 'Historical',                       // 'Historical' | 'Present'
            style: 'Colored',                         // 'Colored' | 'Monochrome'
            showTrend: false,                         // Color Candles

            showInternals: true,                      // Show Internal Structure
            showInternalBull: 'All',                  // 'All' | 'BOS' | 'CHoCH'
            internalBullColor: '#089981',             // Bullish structure color
            showInternalBear: 'All',                  // 'All' | 'BOS' | 'CHoCH'
            internalBearColor: '#F23645',             // Bearish structure color
            internalFilterConfluence: false,          // Filter non significant internal breakouts
            internalStructureSize: 'Tiny',            // 'Tiny' | 'Small' | 'Normal'

            showStructure: true,                      // Show Swing Structure
            showSwingBull: 'All',                     // 'All' | 'BOS' | 'CHoCH'
            swingBullColor: '#089981',                // Bullish swing color
            showSwingBear: 'All',                     // 'All' | 'BOS' | 'CHoCH'
            swingBearColor: '#F23645',                // Bearish swing color
            swingStructureSize: 'Small',              // 'Tiny' | 'Small' | 'Normal'
            showSwings: false,                        // Show Swings Points (HH, LL, HL, LH)
            swingsLength: 50,                         // Swings length (default 50)
            showHighLowSwings: true,                  // Show Strong/Weak High/Low

            showInternalOrderBlocks: true,            // Display internal order blocks
            internalOrderBlocksSize: 5,               // Number of internal OBs (1-20)
            showSwingOrderBlocks: false,              // Display swing order blocks
            swingOrderBlocksSize: 5,                  // Number of swing OBs (1-20)
            orderBlockFilter: 'Atr',                  // 'Atr' | 'Cumulative Mean Range'
            orderBlockMitigation: 'High/Low',         // 'Close' | 'High/Low'
            internalBullishOrderBlockColor: 'rgba(49, 121, 245, 0.45)',
            internalBearishOrderBlockColor: 'rgba(247, 124, 128, 0.45)',
            swingBullishOrderBlockColor: 'rgba(24, 72, 204, 0.6)',
            swingBearishOrderBlockColor: 'rgba(178, 40, 51, 0.6)',

            showEqualHighsLows: true,                 // Equal High/Low (EQH/EQL)
            equalHighsLowsLength: 3,                  // Bars confirmation
            equalHighsLowsThreshold: 0.1,             // Sensitivity threshold (0.0 to 0.5)
            equalHighsLowsSize: 'Tiny',               // 'Tiny' | 'Small' | 'Normal'

            showFairValueGaps: false,                 // Fair Value Gaps
            fairValueGapsThreshold: true,             // Auto threshold
            fairValueGapsExtend: 1,                   // Extend FVG bars
            fairValueGapsBullColor: 'rgba(0, 255, 104, 0.35)',
            fairValueGapsBearColor: 'rgba(255, 0, 8, 0.35)',

            showDailyLevels: false,                   // Daily MTF Levels (PDH/PDL)
            dailyLevelsStyle: 'Solid',                // 'Solid' | 'Dashed' | 'Dotted'
            dailyLevelsColor: '#2157f3',
            showWeeklyLevels: false,                  // Weekly MTF Levels (PWH/PWL)
            weeklyLevelsStyle: 'Solid',
            weeklyLevelsColor: '#2157f3',
            showMonthlyLevels: false,                 // Monthly MTF Levels (PMH/PML)
            monthlyLevelsStyle: 'Solid',
            monthlyLevelsColor: '#2157f3',

            showPremiumDiscountZones: false,          // Premium, Equilibrium & Discount zones
            premiumZoneColor: '#F23645',
            equilibriumZoneColor: '#878b94',
            discountZoneColor: '#089981',

            ...settings
        };

        if (!candles || candles.length < 5) return null;

        // Ensure swingsLength is valid and bounded by candle length
        const swingsLength = Math.max(2, Math.min(cfg.swingsLength || 50, candles.length - 2));

        // Precompute ATR (200 period)
        const atrVals = atr(candles, 200);

        // Volatility measure (ATR or Cumulative Mean Range)
        const trs = [];
        let prevClose = candles[0].close;
        let cumTr = 0;
        for (let i = 0; i < candles.length; i++) {
            const c = candles[i];
            const tr = i === 0 ? (c.high - c.low) : Math.max(
                c.high - c.low,
                Math.abs(c.high - prevClose),
                Math.abs(c.low - prevClose)
            );
            prevClose = c.close;
            cumTr += tr;
            trs.push({ tr, cumMean: cumTr / (i + 1) });
        }

        // Color theme palette
        const isMono = cfg.style === 'Monochrome';
        const GREEN = isMono ? '#b2b5be' : (cfg.swingBullColor || '#089981');
        const RED = isMono ? '#5d606b' : (cfg.swingBearColor || '#F23645');
        const INT_GREEN = isMono ? '#b2b5be' : (cfg.internalBullColor || '#089981');
        const INT_RED = isMono ? '#5d606b' : (cfg.internalBearColor || '#F23645');

        // State arrays for parsed highs/lows (filtering high volatility bars)
        const parsedHighs = [];
        const parsedLows = [];
        const times = [];

        // State variables for pivots
        let swingHigh = { currentLevel: null, lastLevel: null, crossed: false, barTime: null, barIndex: null };
        let swingLow = { currentLevel: null, lastLevel: null, crossed: false, barTime: null, barIndex: null };

        let internalHigh = { currentLevel: null, lastLevel: null, crossed: false, barTime: null, barIndex: null };
        let internalLow = { currentLevel: null, lastLevel: null, crossed: false, barTime: null, barIndex: null };

        let equalHigh = { currentLevel: null, lastLevel: null, crossed: false, barTime: null, barIndex: null };
        let equalLow = { currentLevel: null, lastLevel: null, crossed: false, barTime: null, barIndex: null };

        let swingTrend = 0;    // BULLISH = 1, BEARISH = -1
        let internalTrend = 0; // BULLISH = 1, BEARISH = -1

        let trailing = { top: null, bottom: null, barTime: null, barIndex: null, lastTopTime: null, lastBottomTime: null };

        // Output collections
        const swingHighsLows = [];
        const equalHighsLows = [];
        const breakouts = [];
        const activeSwingOBs = [];
        const activeInternalOBs = [];
        const activeFvgs = [];
        const candleColors = [];

        // State machine leg states
        let swingLeg = 0;
        let prevSwingLeg = 0;
        let internalLeg = 0;
        let prevInternalLeg = 0;
        let equalLeg = 0;
        let prevEqualLeg = 0;

        // FVG cumulative body diff
        let cumBodyDiff = 0;

        // Iterate bar by bar exactly as in Pine Script
        for (let i = 0; i < candles.length; i++) {
            const c = candles[i];
            const t = c.time;

            // Volatility measures at bar i
            const atrVal = atrVals[i] ? atrVals[i].value : (c.high - c.low);
            const volMeasure = cfg.orderBlockFilter === 'Atr' ? atrVal : trs[i].cumMean;
            const highVol = (c.high - c.low) >= (2 * volMeasure);
            const parsedHigh = highVol ? c.low : c.high;
            const parsedLow = highVol ? c.high : c.low;

            parsedHighs.push(parsedHigh);
            parsedLows.push(parsedLow);
            times.push(t);

            // ─────────────────────────────────────────────
            // 1. SWING PIVOTS (swingsLength)
            // ─────────────────────────────────────────────
            if (i >= swingsLength) {
                const targetIdx = i - swingsLength;
                const targetCandle = candles[targetIdx];

                let maxHigh = -Infinity;
                let minLow = Infinity;
                for (let j = targetIdx + 1; j <= i; j++) {
                    if (candles[j].high > maxHigh) maxHigh = candles[j].high;
                    if (candles[j].low < minLow) minLow = candles[j].low;
                }

                const newLegHigh = targetCandle.high > maxHigh;
                const newLegLow = targetCandle.low < minLow;

                if (newLegHigh) {
                    swingLeg = 0; // BEARISH_LEG
                } else if (newLegLow) {
                    swingLeg = 1; // BULLISH_LEG
                }

                if (swingLeg !== prevSwingLeg) {
                    const isBull = swingLeg === 1; // startOfBullishLeg -> swingLow confirmed
                    if (isBull) {
                        swingLow.lastLevel = swingLow.currentLevel;
                        swingLow.currentLevel = targetCandle.low;
                        swingLow.crossed = false;
                        swingLow.barTime = targetCandle.time;
                        swingLow.barIndex = targetIdx;

                        trailing.bottom = swingLow.currentLevel;
                        trailing.barTime = swingLow.barTime;
                        trailing.barIndex = swingLow.barIndex;
                        trailing.lastBottomTime = swingLow.barTime;

                        if (cfg.showSwings) {
                            const label = (swingLow.lastLevel !== null && swingLow.currentLevel < swingLow.lastLevel) ? 'LL' : 'HL';
                            swingHighsLows.push({
                                time: targetCandle.time,
                                price: swingLow.currentLevel,
                                label,
                                position: 'belowBar',
                                color: GREEN
                            });
                        }
                    } else {
                        // startOfBearishLeg -> swingHigh confirmed
                        swingHigh.lastLevel = swingHigh.currentLevel;
                        swingHigh.currentLevel = targetCandle.high;
                        swingHigh.crossed = false;
                        swingHigh.barTime = targetCandle.time;
                        swingHigh.barIndex = targetIdx;

                        trailing.top = swingHigh.currentLevel;
                        trailing.barTime = swingHigh.barTime;
                        trailing.barIndex = swingHigh.barIndex;
                        trailing.lastTopTime = swingHigh.barTime;

                        if (cfg.showSwings) {
                            const label = (swingHigh.lastLevel !== null && swingHigh.currentLevel > swingHigh.lastLevel) ? 'HH' : 'LH';
                            swingHighsLows.push({
                                time: targetCandle.time,
                                price: swingHigh.currentLevel,
                                label,
                                position: 'aboveBar',
                                color: RED
                            });
                        }
                    }
                    prevSwingLeg = swingLeg;
                }
            }

            // ─────────────────────────────────────────────
            // 2. INTERNAL PIVOTS (Fixed length 5)
            // ─────────────────────────────────────────────
            const intSize = 5;
            if (i >= intSize) {
                const targetIdx = i - intSize;
                const targetCandle = candles[targetIdx];

                let maxHigh = -Infinity;
                let minLow = Infinity;
                for (let j = targetIdx + 1; j <= i; j++) {
                    if (candles[j].high > maxHigh) maxHigh = candles[j].high;
                    if (candles[j].low < minLow) minLow = candles[j].low;
                }

                const newLegHigh = targetCandle.high > maxHigh;
                const newLegLow = targetCandle.low < minLow;

                if (newLegHigh) {
                    internalLeg = 0;
                } else if (newLegLow) {
                    internalLeg = 1;
                }

                if (internalLeg !== prevInternalLeg) {
                    const isBull = internalLeg === 1;
                    if (isBull) {
                        internalLow.lastLevel = internalLow.currentLevel;
                        internalLow.currentLevel = targetCandle.low;
                        internalLow.crossed = false;
                        internalLow.barTime = targetCandle.time;
                        internalLow.barIndex = targetIdx;
                    } else {
                        internalHigh.lastLevel = internalHigh.currentLevel;
                        internalHigh.currentLevel = targetCandle.high;
                        internalHigh.crossed = false;
                        internalHigh.barTime = targetCandle.time;
                        internalHigh.barIndex = targetIdx;
                    }
                    prevInternalLeg = internalLeg;
                }
            }

            // ─────────────────────────────────────────────
            // 3. EQUAL HIGHS / LOWS (equalHighsLowsLength)
            // ─────────────────────────────────────────────
            if (cfg.showEqualHighsLows) {
                const eqSize = cfg.equalHighsLowsLength || 3;
                if (i >= eqSize) {
                    const targetIdx = i - eqSize;
                    const targetCandle = candles[targetIdx];

                    let maxHigh = -Infinity;
                    let minLow = Infinity;
                    for (let j = targetIdx + 1; j <= i; j++) {
                        if (candles[j].high > maxHigh) maxHigh = candles[j].high;
                        if (candles[j].low < minLow) minLow = candles[j].low;
                    }

                    const newLegHigh = targetCandle.high > maxHigh;
                    const newLegLow = targetCandle.low < minLow;

                    if (newLegHigh) {
                        equalLeg = 0;
                    } else if (newLegLow) {
                        equalLeg = 1;
                    }

                    if (equalLeg !== prevEqualLeg) {
                        const isBull = equalLeg === 1;
                        const threshold = (cfg.equalHighsLowsThreshold ?? 0.1) * atrVal;
                        if (isBull) {
                            if (equalLow.currentLevel !== null && Math.abs(equalLow.currentLevel - targetCandle.low) < threshold) {
                                equalHighsLows.push({
                                    type: 'EQL',
                                    start: { time: equalLow.barTime, price: equalLow.currentLevel, index: equalLow.barIndex },
                                    end: { time: targetCandle.time, price: targetCandle.low, index: targetIdx },
                                    color: GREEN
                                });
                            }
                            equalLow.lastLevel = equalLow.currentLevel;
                            equalLow.currentLevel = targetCandle.low;
                            equalLow.crossed = false;
                            equalLow.barTime = targetCandle.time;
                            equalLow.barIndex = targetIdx;
                        } else {
                            if (equalHigh.currentLevel !== null && Math.abs(equalHigh.currentLevel - targetCandle.high) < threshold) {
                                equalHighsLows.push({
                                    type: 'EQH',
                                    start: { time: equalHigh.barTime, price: equalHigh.currentLevel, index: equalHigh.barIndex },
                                    end: { time: targetCandle.time, price: targetCandle.high, index: targetIdx },
                                    color: RED
                                });
                            }
                            equalHigh.lastLevel = equalHigh.currentLevel;
                            equalHigh.currentLevel = targetCandle.high;
                            equalHigh.crossed = false;
                            equalHigh.barTime = targetCandle.time;
                            equalHigh.barIndex = targetIdx;
                        }
                        prevEqualLeg = equalLeg;
                    }
                }
            }

            // ─────────────────────────────────────────────
            // 4. BREAKOUTS & STRUCTURE (BOS / CHoCH)
            // ─────────────────────────────────────────────
            let bullishBar = true;
            let bearishBar = true;
            if (cfg.internalFilterConfluence) {
                bullishBar = (c.high - Math.max(c.close, c.open)) > (Math.min(c.close, c.open) - c.low);
                bearishBar = (c.high - Math.max(c.close, c.open)) < (Math.min(c.close, c.open) - c.low);
            }

            // A. Internal Structure
            if (cfg.showInternals && internalHigh.currentLevel !== null && internalLow.currentLevel !== null) {
                // Bullish Breakout
                if (c.close > internalHigh.currentLevel && !internalHigh.crossed && (internalHigh.currentLevel !== swingHigh.currentLevel && bullishBar)) {
                    const tag = internalTrend === -1 ? 'CHoCH' : 'BOS';
                    internalHigh.crossed = true;
                    internalTrend = 1;

                    const showBullType = cfg.showInternalBull || 'All';
                    if (showBullType === 'All' || (showBullType === 'BOS' && tag === 'BOS') || (showBullType === 'CHoCH' && tag === 'CHoCH')) {
                        breakouts.push({
                            type: 'internal',
                            direction: 'bull',
                            tag,
                            start: { time: internalHigh.barTime, price: internalHigh.currentLevel, index: internalHigh.barIndex },
                            end: { time: t, price: internalHigh.currentLevel, index: i },
                            color: INT_GREEN
                        });
                    }

                    if (cfg.showInternalOrderBlocks) {
                        let minIdx = internalHigh.barIndex;
                        let minVal = Infinity;
                        for (let j = internalHigh.barIndex; j <= i; j++) {
                            if (parsedLows[j] < minVal) {
                                minVal = parsedLows[j];
                                minIdx = j;
                            }
                        }
                        activeInternalOBs.unshift({
                            high: parsedHighs[minIdx],
                            low: parsedLows[minIdx],
                            time: times[minIdx],
                            index: minIdx,
                            bias: 1
                        });
                        if (activeInternalOBs.length > 100) activeInternalOBs.pop();
                    }
                }

                // Bearish Breakout
                if (c.close < internalLow.currentLevel && !internalLow.crossed && (internalLow.currentLevel !== swingLow.currentLevel && bearishBar)) {
                    const tag = internalTrend === 1 ? 'CHoCH' : 'BOS';
                    internalLow.crossed = true;
                    internalTrend = -1;

                    const showBearType = cfg.showInternalBear || 'All';
                    if (showBearType === 'All' || (showBearType === 'BOS' && tag === 'BOS') || (showBearType === 'CHoCH' && tag === 'CHoCH')) {
                        breakouts.push({
                            type: 'internal',
                            direction: 'bear',
                            tag,
                            start: { time: internalLow.barTime, price: internalLow.currentLevel, index: internalLow.barIndex },
                            end: { time: t, price: internalLow.currentLevel, index: i },
                            color: INT_RED
                        });
                    }

                    if (cfg.showInternalOrderBlocks) {
                        let maxIdx = internalLow.barIndex;
                        let maxVal = -Infinity;
                        for (let j = internalLow.barIndex; j <= i; j++) {
                            if (parsedHighs[j] > maxVal) {
                                maxVal = parsedHighs[j];
                                maxIdx = j;
                            }
                        }
                        activeInternalOBs.unshift({
                            high: parsedHighs[maxIdx],
                            low: parsedLows[maxIdx],
                            time: times[maxIdx],
                            index: maxIdx,
                            bias: -1
                        });
                        if (activeInternalOBs.length > 100) activeInternalOBs.pop();
                    }
                }
            }

            // B. Swing Structure
            if (cfg.showStructure && swingHigh.currentLevel !== null && swingLow.currentLevel !== null) {
                // Bullish Swing Breakout
                if (c.close > swingHigh.currentLevel && !swingHigh.crossed) {
                    const tag = swingTrend === -1 ? 'CHoCH' : 'BOS';
                    swingHigh.crossed = true;
                    swingTrend = 1;

                    const showBullType = cfg.showSwingBull || 'All';
                    if (showBullType === 'All' || (showBullType === 'BOS' && tag === 'BOS') || (showBullType === 'CHoCH' && tag === 'CHoCH')) {
                        breakouts.push({
                            type: 'swing',
                            direction: 'bull',
                            tag,
                            start: { time: swingHigh.barTime, price: swingHigh.currentLevel, index: swingHigh.barIndex },
                            end: { time: t, price: swingHigh.currentLevel, index: i },
                            color: GREEN
                        });
                    }

                    if (cfg.showSwingOrderBlocks) {
                        let minIdx = swingHigh.barIndex;
                        let minVal = Infinity;
                        for (let j = swingHigh.barIndex; j <= i; j++) {
                            if (parsedLows[j] < minVal) {
                                minVal = parsedLows[j];
                                minIdx = j;
                            }
                        }
                        activeSwingOBs.unshift({
                            high: parsedHighs[minIdx],
                            low: parsedLows[minIdx],
                            time: times[minIdx],
                            index: minIdx,
                            bias: 1
                        });
                        if (activeSwingOBs.length > 100) activeSwingOBs.pop();
                    }
                }

                // Bearish Swing Breakout
                if (c.close < swingLow.currentLevel && !swingLow.crossed) {
                    const tag = swingTrend === 1 ? 'CHoCH' : 'BOS';
                    swingLow.crossed = true;
                    swingTrend = -1;

                    const showBearType = cfg.showSwingBear || 'All';
                    if (showBearType === 'All' || (showBearType === 'BOS' && tag === 'BOS') || (showBearType === 'CHoCH' && tag === 'CHoCH')) {
                        breakouts.push({
                            type: 'swing',
                            direction: 'bear',
                            tag,
                            start: { time: swingLow.barTime, price: swingLow.currentLevel, index: swingLow.barIndex },
                            end: { time: t, price: swingLow.currentLevel, index: i },
                            color: RED
                        });
                    }

                    if (cfg.showSwingOrderBlocks) {
                        let maxIdx = swingLow.barIndex;
                        let maxVal = -Infinity;
                        for (let j = swingLow.barIndex; j <= i; j++) {
                            if (parsedHighs[j] > maxVal) {
                                maxVal = parsedHighs[j];
                                maxIdx = j;
                            }
                        }
                        activeSwingOBs.unshift({
                            high: parsedHighs[maxIdx],
                            low: parsedLows[maxIdx],
                            time: times[maxIdx],
                            index: maxIdx,
                            bias: -1
                        });
                        if (activeSwingOBs.length > 100) activeSwingOBs.pop();
                    }
                }
            }

            // ─────────────────────────────────────────────
            // 5. MITIGATION OF ORDER BLOCKS
            // ─────────────────────────────────────────────
            const mitigationClose = cfg.orderBlockMitigation === 'Close';
            const bearishMitSrc = mitigationClose ? c.close : c.high;
            const bullishMitSrc = mitigationClose ? c.close : c.low;

            for (let k = activeSwingOBs.length - 1; k >= 0; k--) {
                const ob = activeSwingOBs[k];
                if (ob.bias === -1 && bearishMitSrc > ob.high) {
                    activeSwingOBs.splice(k, 1);
                } else if (ob.bias === 1 && bullishMitSrc < ob.low) {
                    activeSwingOBs.splice(k, 1);
                }
            }

            for (let k = activeInternalOBs.length - 1; k >= 0; k--) {
                const ob = activeInternalOBs[k];
                if (ob.bias === -1 && bearishMitSrc > ob.high) {
                    activeInternalOBs.splice(k, 1);
                } else if (ob.bias === 1 && bullishMitSrc < ob.low) {
                    activeInternalOBs.splice(k, 1);
                }
            }

            // ─────────────────────────────────────────────
            // 6. FAIR VALUE GAPS (FVG)
            // ─────────────────────────────────────────────
            if (cfg.showFairValueGaps && i >= 2) {
                const c0 = candles[i - 2];
                const c1 = candles[i - 1];
                const c2 = candles[i];

                const barDeltaPercent = (c1.close - c1.open) / (c1.open || 1);
                cumBodyDiff += Math.abs(barDeltaPercent);
                const threshold = cfg.fairValueGapsThreshold ? (cumBodyDiff / (i + 1) * 2) : 0;

                const bullFVG = c2.low > c0.high && c1.close > c0.high && barDeltaPercent > threshold;
                const bearFVG = c2.high < c0.low && c1.close < c0.low && -barDeltaPercent > threshold;

                if (bullFVG) {
                    activeFvgs.unshift({
                        top: c2.low,
                        bottom: c0.high,
                        mid: (c2.low + c0.high) / 2,
                        time: c1.time,
                        index: i - 1,
                        bias: 1
                    });
                }
                if (bearFVG) {
                    activeFvgs.unshift({
                        top: c0.low,
                        bottom: c2.high,
                        mid: (c0.low + c2.high) / 2,
                        time: c1.time,
                        index: i - 1,
                        bias: -1
                    });
                }

                // FVG Mitigation
                for (let k = activeFvgs.length - 1; k >= 0; k--) {
                    const fvg = activeFvgs[k];
                    if (fvg.bias === 1 && c.low < fvg.bottom) {
                        activeFvgs.splice(k, 1);
                    } else if (fvg.bias === -1 && c.high > fvg.top) {
                        activeFvgs.splice(k, 1);
                    }
                }
            }

            // ─────────────────────────────────────────────
            // 7. TRAILING SWING EXTREMES
            // ─────────────────────────────────────────────
            if (cfg.showHighLowSwings || cfg.showPremiumDiscountZones) {
                if (trailing.top !== null) {
                    if (c.high > trailing.top) {
                        trailing.top = c.high;
                        trailing.lastTopTime = t;
                    }
                } else {
                    trailing.top = c.high;
                    trailing.lastTopTime = t;
                    trailing.barTime = t;
                    trailing.barIndex = i;
                }

                if (trailing.bottom !== null) {
                    if (c.low < trailing.bottom) {
                        trailing.bottom = c.low;
                        trailing.lastBottomTime = t;
                    }
                } else {
                    trailing.bottom = c.low;
                    trailing.lastBottomTime = t;
                    trailing.barTime = t;
                    trailing.barIndex = i;
                }
            }

            // Record trend candle color if showTrend is enabled
            if (cfg.showTrend) {
                candleColors.push({
                    time: t,
                    color: internalTrend === 1 ? GREEN : (internalTrend === -1 ? RED : null)
                });
            }
        }

        // Mode handling: Present vs Historical
        let finalBreakouts = breakouts;
        if (cfg.mode === 'Present' && breakouts.length > 0) {
            const latest = {};
            for (const b of breakouts) {
                const k = `${b.type}_${b.direction}`;
                if (!latest[k] || b.start.time > latest[k].start.time) {
                    latest[k] = b;
                }
            }
            finalBreakouts = Object.values(latest);
        }

        const maxSwingOBs = Math.max(1, Math.min(20, cfg.swingOrderBlocksSize || 5));
        const maxInternalOBs = Math.max(1, Math.min(20, cfg.internalOrderBlocksSize || 5));

        const finalSwingOBs = activeSwingOBs.slice(0, maxSwingOBs);
        const finalInternalOBs = activeInternalOBs.slice(0, maxInternalOBs);

        // Deduplicate adjacent equal highs / lows (within 5 bars)
        const dedupedEqualHL = [];
        const lastAtr = (atrVals && atrVals.length > 0) ? atrVals[atrVals.length - 1].value : (candles[n - 1].high - candles[n - 1].low);
        for (const eq of equalHighsLows) {
            const isDup = dedupedEqualHL.some(existing =>
                existing.type === eq.type &&
                Math.abs(existing.end.price - eq.end.price) < 0.1 * lastAtr &&
                Math.abs((existing.end.index ?? 0) - (eq.end.index ?? 0)) < 5
            );
            if (!isDup) {
                dedupedEqualHL.push(eq);
            }
        }

        // Multi-timeframe levels (PDH/PDL, PWH/PWL, PMH/PML)
        let mtfLevels = null;
        if (cfg.showDailyLevels || cfg.showWeeklyLevels || cfg.showMonthlyLevels) {
            mtfLevels = computeMTFLevels(candles);
        }

        const effectiveTrend = internalTrend !== 0 ? internalTrend : swingTrend;

        // Filter to most recent active unmitigated FVGs (max 5 bull, max 5 bear) to prevent chart clutter
        const maxFvgsPerSide = cfg.fairValueGapsLimit || 5;
        const recentBullFvgs = activeFvgs.filter(f => f.bias === 1).slice(0, maxFvgsPerSide);
        const recentBearFvgs = activeFvgs.filter(f => f.bias === -1).slice(0, maxFvgsPerSide);
        const finalFvgs = [...recentBullFvgs, ...recentBearFvgs].sort((a, b) => b.time - a.time);

        return {
            swingHighsLows,
            equalHighsLows: dedupedEqualHL,
            breakouts: finalBreakouts,
            swingOBs: cfg.showSwingOrderBlocks ? finalSwingOBs : [],
            internalOBs: cfg.showInternalOrderBlocks ? finalInternalOBs : [],
            fvgs: cfg.showFairValueGaps ? finalFvgs : [],
            trailing: (cfg.showHighLowSwings || cfg.showPremiumDiscountZones) ? {
                top: trailing.top,
                bottom: trailing.bottom,
                lastTopTime: trailing.lastTopTime,
                lastBottomTime: trailing.lastBottomTime,
                barTime: trailing.barTime,
                swingTrendBias: swingTrend,
                trendBias: effectiveTrend
            } : null,
            mtfLevels,
            candleColors: cfg.showTrend ? candleColors : null,
            settings: cfg
        };
    }

    // Helper for MTF levels extraction
    function computeMTFLevels(candles) {
        if (!candles || candles.length < 5) return {};
        const parseCandleDate = (t) => {
            if (typeof t === 'number') return new Date(t * 1000);
            if (typeof t === 'string') return new Date(t);
            if (typeof t === 'object' && t !== null) return new Date(Date.UTC(t.year, t.month - 1, t.day));
            return new Date();
        };

        const dayMap = new Map();
        const weekMap = new Map();
        const monthMap = new Map();

        for (const c of candles) {
            const d = parseCandleDate(c.time);
            const dayKey = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
            const monthKey = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;

            const onejan = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
            const weekNum = Math.ceil((((d - onejan) / 86400000) + onejan.getUTCDay() + 1) / 7);
            const weekKey = `${d.getUTCFullYear()}-W${weekNum}`;

            if (!dayMap.has(dayKey)) dayMap.set(dayKey, { high: -Infinity, low: Infinity, time: c.time });
            const dayEntry = dayMap.get(dayKey);
            if (c.high > dayEntry.high) dayEntry.high = c.high;
            if (c.low < dayEntry.low) dayEntry.low = c.low;

            if (!weekMap.has(weekKey)) weekMap.set(weekKey, { high: -Infinity, low: Infinity, time: c.time });
            const weekEntry = weekMap.get(weekKey);
            if (c.high > weekEntry.high) weekEntry.high = c.high;
            if (c.low < weekEntry.low) weekEntry.low = c.low;

            if (!monthMap.has(monthKey)) monthMap.set(monthKey, { high: -Infinity, low: Infinity, time: c.time });
            const monthEntry = monthMap.get(monthKey);
            if (c.high > monthEntry.high) monthEntry.high = c.high;
            if (c.low < monthEntry.low) monthEntry.low = c.low;
        }

        const dayKeys = Array.from(dayMap.keys());
        const weekKeys = Array.from(weekMap.keys());
        const monthKeys = Array.from(monthMap.keys());

        const result = {};
        if (dayKeys.length >= 2) {
            const prevDay = dayMap.get(dayKeys[dayKeys.length - 2]);
            result.daily = { pdh: prevDay.high, pdl: prevDay.low, startTime: prevDay.time };
        }
        if (weekKeys.length >= 2) {
            const prevWeek = weekMap.get(weekKeys[weekKeys.length - 2]);
            result.weekly = { pwh: prevWeek.high, pwl: prevWeek.low, startTime: prevWeek.time };
        }
        if (monthKeys.length >= 2) {
            const prevMonth = monthMap.get(monthKeys[monthKeys.length - 2]);
            result.monthly = { pmh: prevMonth.high, pml: prevMonth.low, startTime: prevMonth.time };
        }
        return result;
    }

    // ─────────────────────────────────────────────
    // Dr Devendra AI Smart Renko V1.1 (Pine Script V1.1 Port)
    // ─────────────────────────────────────────────
    function drDevendraAiRenko(candles, options = {}) {
        if (!candles || candles.length === 0) {
            return {
                stBullLine: [],
                stBearLine: [],
                renkoCloseLine: [],
                markers: [],
                status: null
            };
        }

        const operatingDivisor = Number(options.operatingDivisor) || 6.0;
        const intradayDivisor = Number(options.intradayDivisor) || 2.0;
        const manualBrick = Number(options.manualBrick) || 0.0;
        const atrLength = parseInt(options.atrLength, 10) || 14;
        const stFactor = Number(options.stFactor) || 3.1;
        const atrSmoothLength = parseInt(options.atrSmoothLength, 10) || 15;
        const diLength = parseInt(options.diLength, 10) || 14;
        const adxSmoothing = parseInt(options.adxSmoothing, 10) || 14;
        const adxThreshold = Number(options.adxThreshold) || 15.0;
        const useAdxFilter = options.useAdxFilter !== false;
        const requireDiDirection = Boolean(options.requireDiDirection);
        const showRejectedFlips = options.showRejectedFlips !== false;
        const showRenkoClose = Boolean(options.showRenkoClose);

        const n = candles.length;
        const candleAtr = new Array(n);
        const diPlus = new Array(n);
        const diMinus = new Array(n);
        const adx = new Array(n);

        let smoothTr = 0, smoothPlusDm = 0, smoothMinusDm = 0;
        let candleAtrRma = 0;
        const alphaAtr = 1.0 / atrLength;
        const alphaDi = 1.0 / diLength;
        const alphaAdx = 1.0 / adxSmoothing;
        const dxHistory = [];

        // Check if candles are already Renko bricks
        const isRenko = n >= 2 && Math.abs((candles[0].close - candles[0].open) - (candles[1].close - candles[1].open)) < 1e-4;

        // Session tracking state
        let mainHigh = null, mainLow = null, mainClose = null;
        let remHigh = null, remLow = null, remClose = null;
        let prevSourceClose = null;
        const sessionTrs = [];
        let completedAtr5 = null;
        let dailySizingAtr5 = null;
        let currentDateKey = null;

        for (let i = 0; i < n; i++) {
            const c = candles[i];
            const prev = i > 0 ? candles[i - 1] : null;

            if (prev == null) {
                candleAtr[i] = c.high - c.low;
                diPlus[i] = 0;
                diMinus[i] = 0;
                adx[i] = 0;
                continue;
            }

            const tr = Math.max(c.high - c.low, Math.abs(c.high - prev.close), Math.abs(c.low - prev.close));
            const upMove = c.high - prev.high;
            const downMove = prev.low - c.low;
            const plusDm = (upMove > downMove && upMove > 0) ? upMove : 0;
            const minusDm = (downMove > upMove && downMove > 0) ? downMove : 0;

            if (i <= atrLength) {
                candleAtrRma += tr;
                candleAtr[i] = candleAtrRma / i;
            } else {
                candleAtr[i] = (alphaAtr * tr) + ((1.0 - alphaAtr) * candleAtr[i - 1]);
            }

            if (i <= diLength) {
                smoothTr += tr;
                smoothPlusDm += plusDm;
                smoothMinusDm += minusDm;
                const smTr = smoothTr / i;
                const smPlus = smoothPlusDm / i;
                const smMinus = smoothMinusDm / i;
                diPlus[i] = smTr > 1e-9 ? 100.0 * (smPlus / smTr) : 0;
                diMinus[i] = smTr > 1e-9 ? 100.0 * (smMinus / smTr) : 0;
            } else {
                smoothTr = (alphaDi * tr) + ((1.0 - alphaDi) * smoothTr);
                smoothPlusDm = (alphaDi * plusDm) + ((1.0 - alphaDi) * smoothPlusDm);
                smoothMinusDm = (alphaDi * minusDm) + ((1.0 - alphaDi) * smoothMinusDm);
                diPlus[i] = smoothTr > 1e-9 ? 100.0 * (smoothPlusDm / smoothTr) : 0;
                diMinus[i] = smoothTr > 1e-9 ? 100.0 * (smoothMinusDm / smoothTr) : 0;
            }

            const diSum = diPlus[i] + diMinus[i];
            const dx = diSum > 0 ? 100.0 * Math.abs(diPlus[i] - diMinus[i]) / diSum : 0;

            if (dxHistory.length < adxSmoothing) {
                dxHistory.push(dx);
                adx[i] = dxHistory.reduce((s, v) => s + v, 0) / dxHistory.length;
            } else {
                adx[i] = (alphaAdx * dx) + ((1.0 - alphaAdx) * adx[i - 1]);
            }

            // Session tracking (Asia/Kolkata UTC+5:30)
            const tMs = (typeof c.time === 'number' ? c.time : Date.parse(c.time) / 1000) * 1000;
            const istDate = new Date(tMs + 5.5 * 3600 * 1000);
            const minuteOfDay = istDate.getUTCHours() * 60 + istDate.getUTCMinutes();
            const dateKey = istDate.getUTCFullYear() * 10000 + (istDate.getUTCMonth() + 1) * 100 + istDate.getUTCDate();

            if (currentDateKey !== dateKey) {
                currentDateKey = dateKey;
                if (completedAtr5 != null) {
                    dailySizingAtr5 = completedAtr5;
                }
            }

            const inMain = minuteOfDay >= 555 && minuteOfDay < 915; // 09:15 - 15:15 IST
            const inRem = minuteOfDay >= 915 && minuteOfDay < 930;  // 15:15 - 15:30 IST

            if (inMain) {
                mainHigh = mainHigh == null ? c.high : Math.max(mainHigh, c.high);
                mainLow = mainLow == null ? c.low : Math.min(mainLow, c.low);
                mainClose = c.close;
            } else if (mainHigh != null && mainLow != null && mainClose != null) {
                const sTr = prevSourceClose == null ? (mainHigh - mainLow) : Math.max(
                    mainHigh - mainLow,
                    Math.abs(mainHigh - prevSourceClose),
                    Math.abs(mainLow - prevSourceClose)
                );
                prevSourceClose = mainClose;
                sessionTrs.push(sTr);
                if (sessionTrs.length >= 5) {
                    completedAtr5 = completedAtr5 == null ?
                        (sessionTrs.slice(0, 5).reduce((s, v) => s + v, 0) / 5) :
                        ((1 / 5) * sTr + (4 / 5) * completedAtr5);
                }
                mainHigh = null; mainLow = null; mainClose = null;
            }

            if (inRem) {
                remHigh = remHigh == null ? c.high : Math.max(remHigh, c.high);
                remLow = remLow == null ? c.low : Math.min(remLow, c.low);
                remClose = c.close;
            } else if (remHigh != null && remLow != null && remClose != null) {
                const sTr = prevSourceClose == null ? (remHigh - remLow) : Math.max(
                    remHigh - remLow,
                    Math.abs(remHigh - prevSourceClose),
                    Math.abs(remLow - prevSourceClose)
                );
                prevSourceClose = remClose;
                sessionTrs.push(sTr);
                if (sessionTrs.length >= 5) {
                    completedAtr5 = completedAtr5 == null ?
                        (sessionTrs.slice(0, 5).reduce((s, v) => s + v, 0) / 5) :
                        ((1 / 5) * sTr + (4 / 5) * completedAtr5);
                }
                remHigh = null; remLow = null; remClose = null;
            }
        }

        // 2. Active Brick Sizing
        let activeBrickSize = 0.01;
        let dayBrick = null;
        let sizingEquation = '';

        if (manualBrick > 0) {
            activeBrickSize = manualBrick;
            sizingEquation = `MANUAL FULL BRICK = ${activeBrickSize.toFixed(2)}`;
        } else if (dailySizingAtr5 != null) {
            dayBrick = dailySizingAtr5 / operatingDivisor;
            activeBrickSize = Math.max(0.01, Math.round((dayBrick / intradayDivisor) * 100) / 100);
            sizingEquation = `${dailySizingAtr5.toFixed(2)} / ${operatingDivisor} / ${intradayDivisor} = ${activeBrickSize.toFixed(2)}`;
        } else {
            const lastAtr = candleAtr[n - 1] || (candles[n - 1].close * 0.001);
            const estDay = lastAtr * 5.0;
            dayBrick = estDay / operatingDivisor;
            const cand = dayBrick / intradayDivisor;
            activeBrickSize = Math.max(candles[n - 1].close < 10 ? 0.0001 : 0.01, Number(cand.toPrecision(4)));
            sizingEquation = `EST ${estDay.toFixed(2)} / ${operatingDivisor} / ${intradayDivisor} = ${activeBrickSize.toFixed(4)}`;
        }

        // 3. Synthetic Renko & AI Supertrend Engine
        let renkoClose = null;
        let renkoDirection = 0;
        let brickAtrEma = null;
        let finalUpper = null;
        let finalLower = null;
        let stDirection = 1;
        let emittedBricks = 0;

        const stLine = [];
        const stBullLine = [];
        const stBearLine = [];
        const renkoCloseLine = [];
        const markers = [];

        const hasUnconfirmedBar = options.hasUnconfirmedBar !== undefined ? Boolean(options.hasUnconfirmedBar) : !isRenko;

        for (let i = 0; i < n; i++) {
            const c = candles[i];
            const isConfirmedBar = !hasUnconfirmedBar || (i < n - 1);
            const curCandleAtr = candleAtr[i];
            const curAdx = adx[i];
            const curDiPlus = diPlus[i];
            const curDiMinus = diMinus[i];

            let bullishFlip = false;
            let bearishFlip = false;

            if (isRenko) {
                const brickOpen = c.open;
                const brickCloseVal = c.close;
                const brickHigh = Math.max(brickOpen, brickCloseVal);
                const brickLow = Math.min(brickOpen, brickCloseVal);
                const brickMid = (brickHigh + brickLow) / 2.0;

                const alphaSt = 2.0 / (atrSmoothLength + 1.0);
                brickAtrEma = brickAtrEma == null ? curCandleAtr : (brickAtrEma + alphaSt * (curCandleAtr - brickAtrEma));

                const basicUpper = brickMid + (stFactor * brickAtrEma);
                const basicLower = brickMid - (stFactor * brickAtrEma);
                const priorUpper = finalUpper;
                const priorLower = finalLower;
                const priorTrend = stDirection;

                if (priorLower != null && priorTrend === 1 && brickCloseVal < priorLower) {
                    stDirection = -1;
                    bearishFlip = true;
                } else if (priorUpper != null && priorTrend === -1 && brickCloseVal > priorUpper) {
                    stDirection = 1;
                    bullishFlip = true;
                }

                finalUpper = (priorUpper == null || basicUpper < priorUpper || (i > 0 && candles[i - 1].close > priorUpper)) ? basicUpper : priorUpper;
                finalLower = (priorLower == null || basicLower > priorLower || (i > 0 && candles[i - 1].close < priorLower)) ? basicLower : priorLower;

                renkoClose = brickCloseVal;
            } else if (isConfirmedBar) {
                // Synthetic Renko is built exclusively from confirmed chart bars (Pine Script: barstate.isconfirmed)
                const src = c.close;
                if (curCandleAtr != null && src != null && activeBrickSize > 0) {
                    if (renkoClose == null) {
                        renkoClose = Math.round(src / activeBrickSize) * activeBrickSize;
                    } else {
                        const delta = src - renkoClose;
                        const moveDirection = delta >= 0 ? 1 : -1;
                        const boxesMoved = Math.floor(Math.abs(delta) / activeBrickSize);
                        const isReversal = (renkoDirection !== 0 && moveDirection !== renkoDirection);
                        const thresholdBoxes = isReversal ? 2 : 1;

                        if (boxesMoved >= thresholdBoxes) {
                            const bricksToEmit = isReversal ? (boxesMoved - 1) : boxesMoved;
                            for (let b = 0; b < bricksToEmit; b++) {
                                const prevClose = renkoClose;
                                const stepSize = (isReversal && b === 0) ? 2.0 : 1.0;
                                const nextClose = prevClose + moveDirection * activeBrickSize * stepSize;
                                const brickOpen = (isReversal && b === 0) ? (prevClose + moveDirection * activeBrickSize) : prevClose;
                                const brickHigh = Math.max(brickOpen, nextClose);
                                const brickLow = Math.min(brickOpen, nextClose);
                                const brickMid = (brickHigh + brickLow) / 2.0;

                                const alphaSt = 2.0 / (atrSmoothLength + 1.0);
                                brickAtrEma = brickAtrEma == null ? curCandleAtr : (brickAtrEma + alphaSt * (curCandleAtr - brickAtrEma));

                                const basicUpper = brickMid + (stFactor * brickAtrEma);
                                const basicLower = brickMid - (stFactor * brickAtrEma);
                                const priorUpper = finalUpper;
                                const priorLower = finalLower;
                                const priorTrend = stDirection;

                                if (priorLower != null && priorTrend === 1 && nextClose < priorLower) {
                                    stDirection = -1;
                                    bearishFlip = true;
                                } else if (priorUpper != null && priorTrend === -1 && nextClose > priorUpper) {
                                    stDirection = 1;
                                    bullishFlip = true;
                                }

                                finalUpper = (priorUpper == null || basicUpper < priorUpper || prevClose > priorUpper) ? basicUpper : priorUpper;
                                finalLower = (priorLower == null || basicLower > priorLower || prevClose < priorLower) ? basicLower : priorLower;

                                renkoClose = nextClose;
                                renkoDirection = moveDirection;
                                emittedBricks++;
                            }
                        }
                    }
                }
            } else {
                // On the forming unconfirmed bar: do not emit synthetic bricks or flip trend.
                // Maintain solid confirmed Supertrend trailing level.
                bullishFlip = false;
                bearishFlip = false;
            }

            // 4. ADX Regime Filter on bar
            const adxTrending = curAdx != null && curAdx >= adxThreshold;
            const bullDiAgrees = (!requireDiDirection) || (curDiPlus != null && curDiMinus != null && curDiPlus > curDiMinus);
            const bearDiAgrees = (!requireDiDirection) || (curDiPlus != null && curDiMinus != null && curDiMinus > curDiPlus);

            const bullFilterPass = (!useAdxFilter) || (adxTrending && bullDiAgrees);
            const bearFilterPass = (!useAdxFilter) || (adxTrending && bearDiAgrees);

            const bullSignal = isConfirmedBar && bullishFlip && bullFilterPass;
            const bearSignal = isConfirmedBar && bearishFlip && bearFilterPass;
            const bullRejected = isConfirmedBar && bullishFlip && !bullFilterPass;
            const bearRejected = isConfirmedBar && bearishFlip && !bearFilterPass;

            // Plot Supertrend line (single active trailing level per bar)
            if (finalUpper != null && finalLower != null) {
                const lineVal = stDirection === 1 ? finalLower : finalUpper;
                stLine.push({ time: c.time, value: lineVal, direction: stDirection });
                if (stDirection === 1) {
                    stBullLine.push({ time: c.time, value: lineVal });
                    stBearLine.push({ time: c.time }); // Whitespace gap for bear series
                } else {
                    stBullLine.push({ time: c.time }); // Whitespace gap for bull series
                    stBearLine.push({ time: c.time, value: lineVal });
                }
            }

            if (showRenkoClose && renkoClose != null) {
                renkoCloseLine.push({ time: c.time, value: renkoClose });
            }

            // Shape / Marker placement
            if (bullSignal) {
                markers.push({
                    time: c.time,
                    position: 'belowBar',
                    color: '#089981',
                    shape: 'arrowUp',
                    text: 'BULL'
                });
            } else if (bearSignal) {
                markers.push({
                    time: c.time,
                    position: 'aboveBar',
                    color: '#f23645',
                    shape: 'arrowDown',
                    text: 'BEAR'
                });
            } else if (showRejectedFlips && bullRejected) {
                markers.push({
                    time: c.time,
                    position: 'belowBar',
                    color: '#878b94',
                    shape: 'circle',
                    text: '×'
                });
            } else if (showRejectedFlips && bearRejected) {
                markers.push({
                    time: c.time,
                    position: 'aboveBar',
                    color: '#878b94',
                    shape: 'circle',
                    text: '×'
                });
            }
        }

        const lastAdx = adx[n - 1];
        const isTrending = lastAdx != null && lastAdx >= adxThreshold;

        return {
            stLine,
            stBullLine,
            stBearLine,
            renkoCloseLine,
            markers,
            status: {
                title: 'Dr Devendra AI Renko V1.1 · DYNAMIC',
                sizingEquation,
                dayBrick: dayBrick != null ? dayBrick.toFixed(2) : '--',
                brickSize: activeBrickSize.toFixed(activeBrickSize < 0.01 ? 4 : 2),
                completedAtr5: completedAtr5 != null ? completedAtr5.toFixed(2) : '--',
                dailySizingAtr5: dailySizingAtr5 != null ? dailySizingAtr5.toFixed(2) : 'NOT AVAILABLE',
                stDirection: stDirection === 1 ? 'BULL' : 'BEAR',
                regime: (lastAdx == null) ? 'WARMUP' : (isTrending ? 'TREND' : 'CHOP / FILTERED'),
                adx: (lastAdx != null ? lastAdx.toFixed(1) : '--'),
                adxThreshold: adxThreshold.toFixed(1),
                atrLength,
                stFactor: stFactor.toFixed(1),
                atrSmoothLength
            }
        };
    }

    return {
        sma, ema, wma, hma, bollingerBands, vwap, ichimoku,
        rsi, macd, momentum, roc, cci, stochastic, obv, adx,
        volume, atr, supertrend, smc, drDevendraAiRenko
    };
})();
