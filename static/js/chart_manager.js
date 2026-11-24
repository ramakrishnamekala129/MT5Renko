/**
 * Antigravity // Quant Trading Grid — Chart & Data Manager
 * With Full Indicator Panel + Drawing Tools
 * Bulletproof Sandboxed-Compliant Edition
 */

function startApp() {
    console.log("Antigravity Quant Trading Grid: Initializing...");

    // ──────────────────────────────────────────────
    // SafeStorage — localStorage wrapper
    // ──────────────────────────────────────────────
    const SafeStorage = {
        _data: {},
        getItem(key) {
            try { return localStorage.getItem(key); }
            catch (e) { return this._data[key] || null; }
        },
        setItem(key, value) {
            try { localStorage.setItem(key, value); }
            catch (e) { this._data[key] = String(value); }
        }
    };

    // ──────────────────────────────────────────────
    // App State
    // ──────────────────────────────────────────────
    const STATE = {
        activePanesCount: 6,
        panes: {},           // paneId → pane instance
        mt5Status: 'disconnected',
        executionMode: SafeStorage.getItem('ag_execution_mode') || 'paper'
    };
    window.STATE = STATE;

    const TRADING_STATE = {
        positions: [],
        orders: [],
        dragActive: false
    };

    const cMenu = document.getElementById('chart-context-menu');
    let cMenuTargetPane = null;
    let cMenuPrice = 0;
    let activeSMCSettingsPaneId = null;
    let activeIndicatorLibraryPaneId = null;
    let selectedIndicatorKey = null;
    let editingIndicatorKey = null;


    // DOM refs
    const chartCountSelect = document.getElementById('chart-count-select');
    const paneLayoutButtons = Array.from(document.querySelectorAll('.pane-layout-btn'));
    const mt5StatusPanel = document.getElementById('mt5-status-panel');
    const gridContainer = document.getElementById('charts-grid') || document.getElementById('grid-container');
    const chartPaneTemplate = document.getElementById('chart-pane-template');

    // Default per-pane configs (RK Renko V4 7 Primary Symbols)
    const DEFAULT_PANE_CONFIGS = {
        1: { source: 'mt5', symbol: 'GBPUSD', timeframe: 'renko' },
        2: { source: 'mt5', symbol: 'EURUSD', timeframe: 'renko' },
        3: { source: 'mt5', symbol: 'XAUUSD', timeframe: 'renko' },
        4: { source: 'mt5', symbol: 'BTCUSD', timeframe: 'renko' },
        5: { source: 'mt5', symbol: 'USDJPY', timeframe: 'renko' },
        6: { source: 'mt5', symbol: 'AUDUSD', timeframe: 'renko' },
        7: { source: 'mt5', symbol: 'EURJPY', timeframe: 'renko' },
        8: { source: 'mt5', symbol: 'GBPUSD', timeframe: '1m' }
    };

    const HISTORY_BACKFILL_LIMIT = 500;
    const HISTORY_BACKFILL_EDGE_BARS = 20;
    const MAX_CANDLES_IN_MEMORY = 5000;
    const OSCILLATOR_PANEL_DEFAULT_HEIGHT = 120;
    const OSCILLATOR_PANEL_MIN_HEIGHT = 70;

    // Indicator colour palette
    const IND_COLORS = {
        sma20: '#F5A623',  // amber
        sma50: '#4CD9FF',  // sky blue
        ema9: '#FF6B6B',  // coral
        ema21: '#B07FFF',  // violet
        bbUpper: '#4ECDC4',  // teal
        bbMiddle: '#888',    // grey
        bbLower: '#4ECDC4',  // teal
        vwap: '#FFD166',  // gold
        rsi: '#00F2FE',  // cyan
        macdLine: '#4ECDC4', // teal
        macdSig: '#FF6B6B', // coral
        volume: 'auto'
    };

    let CATALOG_CATEGORIES = ['All', 'Momentum', 'Overlap', 'Trend', 'Volatility', 'Volume', 'Statistics', 'Candle', 'Cycle', 'Performance'];
    let activeCategoryFilter = 'all';

    // ── Offline / Fallback Definitions for Built-in & pandas_ta Indicators ──
    const INDICATOR_DEFS = {
        sma20: { id: 'sma20', name: 'Simple Moving Average', short: 'SMA 20', category: 'Moving Averages', kind: 'overlay', defaults: { period: 20, color: IND_COLORS.sma20, width: 2 }, fields: [['period', 'Length', 'number', 1, 500], ['color', 'Color', 'color'], ['width', 'Line width', 'number', 1, 5]] },
        sma50: { id: 'sma50', name: 'Simple Moving Average 50', short: 'SMA 50', category: 'Moving Averages', kind: 'overlay', defaults: { period: 50, color: IND_COLORS.sma50, width: 2 }, fields: [['period', 'Length', 'number', 1, 500], ['color', 'Color', 'color'], ['width', 'Line width', 'number', 1, 5]] },
        ema9: { id: 'ema9', name: 'Exponential Moving Average', short: 'EMA 9', category: 'Moving Averages', kind: 'overlay', defaults: { period: 9, color: IND_COLORS.ema9, width: 2 }, fields: [['period', 'Length', 'number', 1, 500], ['color', 'Color', 'color'], ['width', 'Line width', 'number', 1, 5]] },
        ema21: { id: 'ema21', name: 'Exponential Moving Average 21', short: 'EMA 21', category: 'Moving Averages', kind: 'overlay', defaults: { period: 21, color: IND_COLORS.ema21, width: 2 }, fields: [['period', 'Length', 'number', 1, 500], ['color', 'Color', 'color'], ['width', 'Line width', 'number', 1, 5]] },
        wma20: { id: 'wma20', name: 'Weighted Moving Average', short: 'WMA', category: 'Moving Averages', kind: 'overlay', defaults: { period: 20, color: '#fbc02d', width: 2 }, fields: [['period', 'Length', 'number', 1, 500], ['color', 'Color', 'color'], ['width', 'Line width', 'number', 1, 5]] },
        hma20: { id: 'hma20', name: 'Hull Moving Average', short: 'HMA', category: 'Moving Averages', kind: 'overlay', defaults: { period: 20, color: '#ff9800', width: 2 }, fields: [['period', 'Length', 'number', 1, 500], ['color', 'Color', 'color'], ['width', 'Line width', 'number', 1, 5]] },
        bb20: { id: 'bb20', name: 'Bollinger Bands', short: 'BB', category: 'Volatility', kind: 'overlay', defaults: { period: 20, stdDev: 2, color: IND_COLORS.bbUpper, middleColor: '#787b86' }, fields: [['period', 'Length', 'number', 1, 500], ['stdDev', 'StdDev', 'number', 0.1, 10, 0.1], ['color', 'Band color', 'color'], ['middleColor', 'Basis color', 'color']] },
        vwap: { id: 'vwap', name: 'VWAP', short: 'VWAP', category: 'Volume', kind: 'overlay', defaults: { color: IND_COLORS.vwap, width: 2 }, fields: [['color', 'Color', 'color'], ['width', 'Line width', 'number', 1, 5]] },
        ichimoku: { id: 'ichimoku', name: 'Ichimoku Cloud', short: 'Ichimoku', category: 'Trend', kind: 'overlay', defaults: { tenkan: 9, kijun: 26, spanB: 52, conversionColor: '#2962ff', baseColor: '#b71c1c', cloudColor: '#787b86' }, fields: [['tenkan', 'Conversion', 'number', 1, 100], ['kijun', 'Base', 'number', 1, 200], ['spanB', 'Span B', 'number', 1, 300], ['conversionColor', 'Conversion color', 'color'], ['baseColor', 'Base color', 'color'], ['cloudColor', 'Cloud color', 'color']] },
        supertrend: { id: 'supertrend', name: 'Supertrend', short: 'Supertrend', category: 'Trend', kind: 'overlay', defaults: { period: 10, multiplier: 3, width: 2 }, fields: [['period', 'ATR length', 'number', 1, 100], ['multiplier', 'Factor', 'number', 0.1, 20, 0.1], ['width', 'Line width', 'number', 1, 5]] },
        rsi14: { id: 'rsi14', name: 'Relative Strength Index', short: 'RSI', category: 'Oscillators', kind: 'panel', defaults: { period: 14, color: IND_COLORS.rsi, overbought: 70, oversold: 30 }, fields: [['period', 'Length', 'number', 1, 100], ['overbought', 'Upper band', 'number', 1, 100], ['oversold', 'Lower band', 'number', 0, 99], ['color', 'Color', 'color']] },
        macd: { id: 'macd', name: 'MACD', short: 'MACD', category: 'Oscillators', kind: 'panel', defaults: { fast: 12, slow: 26, signal: 9, macdColor: IND_COLORS.macdLine, signalColor: IND_COLORS.macdSig }, fields: [['fast', 'Fast length', 'number', 1, 100], ['slow', 'Slow length', 'number', 1, 200], ['signal', 'Signal smoothing', 'number', 1, 100], ['macdColor', 'MACD color', 'color'], ['signalColor', 'Signal color', 'color']] },
        stoch: { id: 'stoch', name: 'Stochastic', short: 'Stoch', category: 'Oscillators', kind: 'panel', defaults: { k: 14, d: 3, smooth: 3, kColor: '#2962ff', dColor: '#ff6d00' }, fields: [['k', '%K length', 'number', 1, 100], ['d', '%D smoothing', 'number', 1, 50], ['smooth', 'Smooth', 'number', 1, 50], ['kColor', '%K color', 'color'], ['dColor', '%D color', 'color']] },
        cci: { id: 'cci', name: 'Commodity Channel Index', short: 'CCI', category: 'Oscillators', kind: 'panel', defaults: { period: 20, color: '#26a69a' }, fields: [['period', 'Length', 'number', 1, 200], ['color', 'Color', 'color']] },
        momentum: { id: 'momentum', name: 'Momentum', short: 'MOM', category: 'Oscillators', kind: 'panel', defaults: { period: 10, color: '#ab47bc' }, fields: [['period', 'Length', 'number', 1, 200], ['color', 'Color', 'color']] },
        roc: { id: 'roc', name: 'Rate of Change', short: 'ROC', category: 'Oscillators', kind: 'panel', defaults: { period: 9, color: '#29b6f6' }, fields: [['period', 'Length', 'number', 1, 200], ['color', 'Color', 'color']] },
        atr: { id: 'atr', name: 'Average True Range', short: 'ATR', category: 'Volatility', kind: 'panel', defaults: { period: 14, color: '#ffb74d' }, fields: [['period', 'Length', 'number', 1, 200], ['color', 'Color', 'color']] },
        adx: { id: 'adx', name: 'Average Directional Index', short: 'ADX', category: 'Trend', kind: 'panel', defaults: { period: 14, adxColor: '#fbc02d', plusColor: '#089981', minusColor: '#f23645' }, fields: [['period', 'Length', 'number', 1, 100], ['adxColor', 'ADX color', 'color'], ['plusColor', '+DI color', 'color'], ['minusColor', '-DI color', 'color']] },
        obv: { id: 'obv', name: 'On Balance Volume', short: 'OBV', category: 'Volume', kind: 'panel', defaults: { color: '#7e57c2' }, fields: [['color', 'Color', 'color']] },
        volume: { id: 'volume', name: 'Volume', short: 'VOL', category: 'Volume', kind: 'panel', defaults: {}, fields: [] },
        smc: { id: 'smc', name: 'Smart Money Concepts', short: 'SMC', category: 'Smart Money', kind: 'overlay', defaults: {}, fields: [] },
        ai_renko: {
            id: 'ai_renko',
            name: 'Dr Devendra AI Smart Renko V1.1',
            short: 'AI Renko',
            category: 'Smart Money',
            kind: 'overlay',
            defaults: {
                manualBrick: 0.0,
                operatingDivisor: 6.0,
                intradayDivisor: 2.0,
                stFactor: 3.1,
                atrLength: 14,
                atrSmoothLength: 15,
                diLength: 14,
                adxSmoothing: 14,
                adxThreshold: 15.0,
                useAdxFilter: true,
                requireDiDirection: false,
                showRejectedFlips: true,
                showRenkoClose: false,
                showInfo: false
            },
            fields: [
                ['manualBrick', 'Manual brick (0=auto)', 'number', 0, 1000, 0.01],
                ['operatingDivisor', 'Operating divisor', 'number', 0.1, 50, 0.1],
                ['intradayDivisor', 'Intraday divisor', 'number', 0.1, 50, 0.1],
                ['stFactor', 'ST Factor', 'number', 0.1, 20, 0.1],
                ['atrLength', 'ATR length', 'number', 1, 100],
                ['adxThreshold', 'ADX threshold', 'number', 1, 100, 0.5],
                ['useAdxFilter', 'Filter flips by ADX', 'boolean'],
                ['requireDiDirection', 'Require DI direction', 'boolean'],
                ['showRejectedFlips', 'Show rejected flips (×)', 'boolean'],
                ['showRenkoClose', 'Show synthetic Renko close', 'boolean']
            ]
        },
        // Fallback pandas_ta standard indicators
        rsi: {
            id: 'rsi', name: 'Relative Strength Index', short: 'RSI', category: 'Momentum', kind: 'panel',
            description: 'Momentum oscillator measuring speed and change of price movements',
            inputs: ['close'],
            params: [
                { name: 'length', type: 'int', default: 14, min: 1, max: 200, step: 1 },
                { name: 'scalar', type: 'float', default: 100.0 }
            ],
            outputs: [{ name: 'RSI_14', type: 'line', color: '#7E57C2' }]
        },
        bbands: {
            id: 'bbands', name: 'Bollinger Bands', short: 'BBands', category: 'Volatility', kind: 'overlay',
            description: 'Volatility bands placed above and below a moving average',
            inputs: ['close'],
            params: [
                { name: 'length', type: 'int', default: 20, min: 1, max: 200, step: 1 },
                { name: 'std', type: 'float', default: 2.0, min: 0.1, max: 10.0, step: 0.1 }
            ],
            outputs: [
                { name: 'upper', type: 'line', color: '#26A69A' },
                { name: 'middle', type: 'line', color: '#FF9800' },
                { name: 'lower', type: 'line', color: '#EF5350' }
            ]
        },
        sma: {
            id: 'sma', name: 'Simple Moving Average', short: 'SMA', category: 'Overlap', kind: 'overlay',
            description: 'Simple Moving Average over a specified period',
            inputs: ['close'],
            params: [{ name: 'length', type: 'int', default: 20, min: 1, max: 500, step: 1 }],
            outputs: [{ name: 'SMA_20', type: 'line', color: '#2962FF' }]
        },
        ema: {
            id: 'ema', name: 'Exponential Moving Average', short: 'EMA', category: 'Overlap', kind: 'overlay',
            description: 'Exponential Moving Average giving more weight to recent prices',
            inputs: ['close'],
            params: [{ name: 'length', type: 'int', default: 10, min: 1, max: 500, step: 1 }],
            outputs: [{ name: 'EMA_10', type: 'line', color: '#FF6B6B' }]
        },
        dema: {
            id: 'dema', name: 'Double Exponential Moving Average', short: 'DEMA', category: 'Overlap', kind: 'overlay',
            description: 'Double Exponential Moving Average with reduced lag',
            inputs: ['close'],
            params: [{ name: 'length', type: 'int', default: 10, min: 1, max: 500, step: 1 }],
            outputs: [{ name: 'DEMA_10', type: 'line', color: '#00E676' }]
        },
        tema: {
            id: 'tema', name: 'Triple Exponential Moving Average', short: 'TEMA', category: 'Overlap', kind: 'overlay',
            description: 'Triple Exponential Moving Average',
            inputs: ['close'],
            params: [{ name: 'length', type: 'int', default: 10, min: 1, max: 500, step: 1 }],
            outputs: [{ name: 'TEMA_10', type: 'line', color: '#E040FB' }]
        },
        aroon: {
            id: 'aroon', name: 'Aroon & Aroon Oscillator', short: 'Aroon', category: 'Trend', kind: 'panel',
            description: 'Aroon measures trend strength and direction',
            inputs: ['high', 'low'],
            params: [{ name: 'length', type: 'int', default: 14, min: 1, max: 200, step: 1 }],
            outputs: [{ name: 'AROOND_14', type: 'line', color: '#EF5350' }, { name: 'AROONU_14', type: 'line', color: '#26A69A' }]
        },
        mfi: {
            id: 'mfi', name: 'Money Flow Index', short: 'MFI', category: 'Volume', kind: 'panel',
            description: 'Volume-weighted momentum oscillator',
            inputs: ['high', 'low', 'close', 'volume'],
            params: [{ name: 'length', type: 'int', default: 14, min: 1, max: 200, step: 1 }],
            outputs: [{ name: 'MFI_14', type: 'line', color: '#26C6DA' }]
        },
        willr: {
            id: 'willr', name: 'Williams %R', short: 'WillR', category: 'Momentum', kind: 'panel',
            description: 'Williams %R momentum oscillator',
            inputs: ['high', 'low', 'close'],
            params: [{ name: 'length', type: 'int', default: 14, min: 1, max: 200, step: 1 }],
            outputs: [{ name: 'WILLR_14', type: 'line', color: '#AB47BC' }]
        },
        zscore: {
            id: 'zscore', name: 'Z-Score', short: 'Z-Score', category: 'Statistics', kind: 'panel',
            description: 'Standard score measuring number of standard deviations from mean',
            inputs: ['close'],
            params: [
                { name: 'length', type: 'int', default: 30, min: 1, max: 500, step: 1 },
                { name: 'std', type: 'float', default: 1.0, min: 0.1, max: 10.0, step: 0.1 }
            ],
            outputs: [{ name: 'ZS_30', type: 'line', color: '#FFA726' }]
        }
    };

    // ── Catalog Parser & Merge Logic ──
    function mergeCatalogDefinitions(catalogData) {
        if (!catalogData || typeof catalogData !== 'object') return;

        if (Array.isArray(catalogData.categories) && catalogData.categories.length > 0) {
            const normalizedCats = catalogData.categories.map(c => c.charAt(0).toUpperCase() + c.slice(1).toLowerCase());
            CATALOG_CATEGORIES = ['All', ...normalizedCats.filter((c, idx, arr) => arr.indexOf(c) === idx)];
        }

        const indicators = catalogData.indicators || {};
        for (const [id, ind] of Object.entries(indicators)) {
            if (!ind || !id) continue;
            const categoryName = ind.category ? (ind.category.charAt(0).toUpperCase() + ind.category.slice(1).toLowerCase()) : 'General';
            const kind = ind.kind === 'overlay' ? 'overlay' : 'panel';

            const defaults = {};
            if (Array.isArray(ind.params)) {
                ind.params.forEach(p => {
                    if (p.name) defaults[p.name] = p.default;
                });
            }
            if (Array.isArray(ind.outputs) && ind.outputs.length > 0 && ind.outputs[0].color) {
                defaults.color = ind.outputs[0].color;
                defaults.width = 2;
            }

            const fields = (ind.params || []).map(p => [
                p.name,
                p.name.charAt(0).toUpperCase() + p.name.slice(1).replace(/_/g, ' '),
                p.type === 'int' || p.type === 'float' ? 'number' : (p.type === 'bool' ? 'boolean' : 'text'),
                p.min,
                p.max,
                p.step
            ]);

            if (INDICATOR_DEFS[id]) {
                // Enrich existing definition with catalog metadata
                INDICATOR_DEFS[id].id = id;
                INDICATOR_DEFS[id].name = ind.name || INDICATOR_DEFS[id].name;
                INDICATOR_DEFS[id].description = ind.description || INDICATOR_DEFS[id].description;
                INDICATOR_DEFS[id].params = ind.params || INDICATOR_DEFS[id].params || [];
                INDICATOR_DEFS[id].outputs = ind.outputs || INDICATOR_DEFS[id].outputs || [];
                INDICATOR_DEFS[id].inputs = ind.inputs || INDICATOR_DEFS[id].inputs || ['close'];
                INDICATOR_DEFS[id].defaults = { ...defaults, ...INDICATOR_DEFS[id].defaults };
            } else {
                INDICATOR_DEFS[id] = {
                    id: id,
                    name: ind.name || id,
                    short: (ind.name && ind.name.length <= 8 ? ind.name : id).toUpperCase(),
                    category: categoryName,
                    kind: kind,
                    description: ind.description || '',
                    inputs: ind.inputs || ['close'],
                    params: ind.params || [],
                    outputs: ind.outputs || [],
                    defaults: defaults,
                    fields: fields
                };
            }
        }

        renderCategoryTabs();
        const modal = document.getElementById('indicator-library-dialog');
        if (modal && !modal.classList.contains('hidden')) {
            renderIndicatorLibrary();
        }
    }

    async function fetchIndicatorCatalog() {
        try {
            const resp = await fetch('/api/indicators/catalog');
            if (!resp.ok) {
                console.warn(`[chart_manager] /api/indicators/catalog returned HTTP ${resp.status}`);
                return;
            }
            const data = await resp.json();
            mergeCatalogDefinitions(data);
        } catch (err) {
            console.warn('[chart_manager] Failed to fetch /api/indicators/catalog, using fallback catalog:', err);
        }
    }

    // ──────────────────────────────────────────────
    // INIT
    // ──────────────────────────────────────────────
    function init() {
        const savedCount = SafeStorage.getItem('ag_pane_count');
        if (savedCount && ['1', '2', '4', '6', '8'].includes(savedCount)) {
            STATE.activePanesCount = parseInt(savedCount);
            if (chartCountSelect) chartCountSelect.value = savedCount;
        }

        if (chartCountSelect)
            chartCountSelect.addEventListener('change', e => updateGridCount(parseInt(e.target.value)));

        paneLayoutButtons.forEach(btn => {
            btn.addEventListener('click', () => updateGridCount(parseInt(btn.dataset.paneCount, 10)));
        });

        if (mt5StatusPanel)
            mt5StatusPanel.addEventListener('click', testMT5Connection);

        updateGridCount(STATE.activePanesCount);
        testMT5Connection();
        window.addEventListener('resize', handleResize);
        initSMCSettingsEvents();
        initIndicatorLibraryEvents();
        initGlobalBotControls();
        initBotAdjustmentsModal();
        initTerminalConsole();
        fetchIndicatorCatalog();
    }

    // ──────────────────────────────────────────────
    // GRID
    // ──────────────────────────────────────────────
    function syncPaneLayoutControl(count) {
        if (chartCountSelect) chartCountSelect.value = String(count);
        paneLayoutButtons.forEach(btn => {
            const active = btn.dataset.paneCount === String(count);
            btn.classList.toggle('active', active);
            btn.setAttribute('aria-checked', active ? 'true' : 'false');
        });
    }

    function updateGridCount(count) {
        STATE.activePanesCount = count;
        SafeStorage.setItem('ag_pane_count', count);
        syncPaneLayoutControl(count);

        if (gridContainer) {
            gridContainer.className = `grid-container charts-grid grid-${count} grid-${count}-pane layout-${count}`;
        }

        Object.keys(STATE.panes).forEach(id => {
            if (parseInt(id) > count) destroyPane(parseInt(id));
        });

        for (let i = 1; i <= count; i++) {
            if (!STATE.panes[i]) createPane(i);
        }

        const activePane = document.querySelector('.chart-pane.active-pane');
        if (!activePane) {
            const firstPane = document.querySelector('.chart-pane');
            if (firstPane) firstPane.classList.add('active-pane');
        }

        setTimeout(handleResize, 80);
    }

    // ──────────────────────────────────────────────
    // CREATE PANE
    // ──────────────────────────────────────────────
    function createPane(paneId) {
        if (!chartPaneTemplate || !gridContainer) return;

        let clone;
        if (chartPaneTemplate.content && typeof chartPaneTemplate.content.cloneNode === 'function') {
            clone = chartPaneTemplate.content.cloneNode(true);
        } else {
            const tmp = document.createElement('div');
            tmp.innerHTML = chartPaneTemplate.innerHTML;
            clone = tmp;
        }

        const paneEl = clone.querySelector('.chart-pane');
        if (!paneEl) return;

        paneEl.id = `pane-${paneId}`;
        paneEl.setAttribute('data-pane-id', paneId);
        const numEl = paneEl.querySelector('.pane-num');
        if (numEl) numEl.textContent = paneId;

        gridContainer.appendChild(paneEl);

        const sourceSelect = paneEl.querySelector('.pane-source-select');
        const symbolInput = paneEl.querySelector('.pane-symbol-input');
        const tfSelect = paneEl.querySelector('.pane-tf-select');
        const chartMount = paneEl.querySelector('.chart-mount');
        if (chartMount) chartMount.id = `chart-mount-${paneId}`;
        const oscillatorsContainer = paneEl.querySelector('.oscillators-container');
        const overlay = paneEl.querySelector('.pane-loading-overlay');

        if (typeof LightweightCharts === 'undefined') {
            if (overlay) overlay.querySelector('.loading-text').innerHTML = '<span class="bear-text">LightweightCharts library not loaded.</span>';
            return;
        }

        // Load saved or default config
        const rawConfig = SafeStorage.getItem(`ag_pane_config_${paneId}`);
        let config = DEFAULT_PANE_CONFIGS[paneId] || { source: 'hyperliquid', symbol: 'BTC', timeframe: '5m' };
        if (rawConfig) {
            try { config = JSON.parse(rawConfig); } catch (e) { }
        }

        if (sourceSelect) sourceSelect.value = config.source;
        if (symbolInput) symbolInput.value = config.symbol;
        if (tfSelect) tfSelect.value = config.timeframe;

        // Load saved indicator states
        const rawIndicators = SafeStorage.getItem(`ag_pane_indicators_${paneId}`);
        let activeIndicators = {};
        if (rawIndicators) {
            try {
                const parsed = JSON.parse(rawIndicators);
                if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) activeIndicators = parsed;
            } catch (e) { }
        }

        const rawIndicatorSettings = SafeStorage.getItem(`ag_pane_indicator_settings_${paneId}`);
        let indicatorSettings = {};
        if (rawIndicatorSettings) {
            try {
                const parsed = JSON.parse(rawIndicatorSettings);
                if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) indicatorSettings = parsed;
            } catch (e) { }
        }

        const rawIndicatorVisibility = SafeStorage.getItem(`ag_pane_indicator_visibility_${paneId}`);
        let indicatorVisibility = {};
        if (rawIndicatorVisibility) {
            try {
                const parsed = JSON.parse(rawIndicatorVisibility);
                if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) indicatorVisibility = parsed;
            } catch (e) { }
        }

        const rawOscillatorSizes = SafeStorage.getItem(`ag_pane_oscillator_sizes_${paneId}`);
        let oscillatorSizes = {};
        if (rawOscillatorSizes) {
            try {
                const parsed = JSON.parse(rawOscillatorSizes);
                if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) oscillatorSizes = parsed;
            } catch (e) { }
        }

        // ── Main Chart (White Theme) ──
        const chart = LightweightCharts.createChart(chartMount, {
            layout: {
                background: { type: 'solid', color: '#FFFFFF' },
                textColor: '#475569',
                fontFamily: 'Inter, sans-serif',
                fontSize: 11
            },
            grid: {
                vertLines: { color: '#F1F5F9' },
                horzLines: { color: '#F1F5F9' }
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: '#94A3B8', width: 1, style: LightweightCharts.LineStyle.Solid },
                horzLine: { color: '#94A3B8', width: 1, style: LightweightCharts.LineStyle.Solid }
            },
            rightPriceScale: {
                borderColor: '#E2E8F0', visible: true, autoScale: true, minimumWidth: 80
            },
            timeScale: {
                borderColor: '#E2E8F0',
                timeVisible: true, secondsVisible: false,
                rightOffset: 6
            }
        });

        // ── Double-click to reset price & time scale ──
        chartMount.addEventListener('dblclick', (e) => {
            e.preventDefault();
            resetPaneChartScale(paneId);
        });

        // ── Candlestick Series ──
        const series = chart.addSeries(LightweightCharts.CandlestickSeries, {
            upColor: '#10B981', downColor: '#EF4444',
            borderUpColor: '#10B981', borderDownColor: '#EF4444',
            wickUpColor: '#10B981', wickDownColor: '#EF4444',
            priceLineStyle: LightweightCharts.LineStyle.Solid,
            priceLineWidth: 1
        });

        // ── Oscillator Charts Stack ──
        const oscillators = {}; // { rsi14: { chart, series: {}, mountEl, resizeObserver }, ... }

        // Load saved SMC settings
        const savedSmcSettings = SafeStorage.getItem(`ag_pane_smc_settings_${paneId}`);
        let smcSettings = {};
        if (savedSmcSettings) {
            try { smcSettings = JSON.parse(savedSmcSettings); } catch (e) { }
        }

        // ── Pane state object ──
        const pane = {
            id: paneId,
            element: paneEl,
            source: config.source,
            symbol: config.symbol,
            timeframe: config.timeframe,
            timelineMode: 'equidistant',
            renkoMode: '1m',
            stSeries: null,
            zoneLines: [],
            renkoPollingTimer: null,
            chart,
            series,
            oscillators,
            oscillatorsContainer,
            resizeObserver: null,
            ws: null,
            pollingTimer: null,
            lastPrice: null,
            lastCandle: null,
            candles: [],
            isBackfilling: false,
            hasMoreHistory: true,
            activeIndicators,
            indicatorSettings,
            indicatorVisibility,
            oscillatorSizes,
            overlaySeries: {},
            smcSeries: [],
            smcSettings: smcSettings,
            activeTool: null,
            drawings: [],
            isDisposed: false
        };
        STATE.panes[paneId] = pane;

        // ── ResizeObserver ──
        const resizeObserver = new ResizeObserver(entries => {
            if (pane.isDisposed || !STATE.panes[paneId] || !pane.chart) return;
            for (const entry of entries) {
                const { width, height } = entry.contentRect;
                if (width > 0 && height > 0) {
                    const floorW = Math.floor(width);
                    const floorH = Math.floor(height);
                    if (pane._lastW === floorW && pane._lastH === floorH) continue;
                    pane._lastW = floorW;
                    pane._lastH = floorH;
                    try {
                        pane.chart.resize(floorW, floorH);
                    } catch (e) { }
                    if (pane.activeIndicators?.smc) {
                        drawSMCCanvas(pane);
                    }
                }
            }
        });
        resizeObserver.observe(chartMount);
        pane.resizeObserver = resizeObserver;

        wireHistoryBackfill(STATE.panes[paneId]);

        // ── Wire event listeners ──
        if (sourceSelect) sourceSelect.addEventListener('change', () => handlePaneConfigChange(paneId));
        if (symbolInput) {
            symbolInput.addEventListener('change', () => handlePaneConfigChange(paneId));
            symbolInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') handlePaneConfigChange(paneId);
            });
        }
        if (tfSelect) tfSelect.addEventListener('change', () => handlePaneConfigChange(paneId));

        // Wire AutoScale Reset Button
        const autoScaleBtn = paneEl.querySelector('.btn-pane-autoscale');
        if (autoScaleBtn) {
            autoScaleBtn.addEventListener('click', () => {
                resetPaneChartScale(paneId);
            });
        }

        // Wire Renko Timeline Toggle Button
        const renkoTlBtn = paneEl.querySelector('.renko-timeline-toggle');
        if (renkoTlBtn) {
            renkoTlBtn.addEventListener('click', () => {
                const pane = STATE.panes[paneId];
                if (!pane) return;
                pane.timelineMode = (pane.timelineMode === 'equidistant') ? 'real' : 'equidistant';
                renkoTlBtn.textContent = pane.timelineMode === 'equidistant' ? 'EQ' : 'REAL';
                renkoTlBtn.classList.toggle('active', pane.timelineMode === 'equidistant');
                loadChartData(paneId);
            });
        }

        // Wire Pane Execution Mode Button (Paper vs Live MT5)
        const paneModeBtn = paneEl.querySelector('.bot-pane-mode-btn');
        pane.executionMode = SafeStorage.getItem(`ag_pane_mode_${paneId}`) || STATE.executionMode || 'paper';
        if (paneModeBtn) {
            paneModeBtn.textContent = (pane.executionMode === 'live') ? 'LIVE' : 'PAPER';
            paneModeBtn.className = `bot-pane-mode-btn mode-${pane.executionMode}`;
            paneModeBtn.addEventListener('click', () => {
                const newMode = (pane.executionMode === 'live') ? 'paper' : 'live';
                if (newMode === 'live') {
                    if (!confirm(`⚠️ Switch Pane #${paneId} [${pane.symbol}] to LIVE MT5 REAL MONEY mode?`)) return;
                }
                pane.executionMode = newMode;
                SafeStorage.setItem(`ag_pane_mode_${paneId}`, newMode);
                paneModeBtn.textContent = (newMode === 'live') ? 'LIVE' : 'PAPER';
                paneModeBtn.className = `bot-pane-mode-btn mode-${newMode}`;
            });
        }

        // Wire Bot Start/Stop Button
        const botActionBtn = paneEl.querySelector('.btn-bot-action');
        if (botActionBtn) {
            botActionBtn.addEventListener('click', () => {
                const pane = STATE.panes[paneId];
                if (!pane) return;
                const isRunning = botActionBtn.classList.contains('btn-bot-stop');
                const endpoint = isRunning ? '/api/bot/stop' : '/api/bot/start';
                const isLive = (pane.executionMode === 'live');
                if (!isRunning && isLive) {
                    if (!confirm(`⚠️ WARNING: Start ${pane.symbol} bot in LIVE MT5 REAL MONEY mode?`)) return;
                }
                fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbol: pane.symbol, live: isLive, mode: pane.renkoMode || '1m' })
                })
                    .then(r => r.json())
                    .then(() => {
                        setTimeout(() => fetchBotStatus(pane), 400);
                    });
            });
        }

        // Wire Bot Adjustments Button
        const botAdjustBtn = paneEl.querySelector('.btn-bot-adjust');
        if (botAdjustBtn) {
            botAdjustBtn.addEventListener('click', () => {
                const pane = STATE.panes[paneId];
                if (pane) openAdjustmentsModal(pane.symbol);
            });
        }

        // Wire Quick Close Position Button
        const quickCloseBtn = paneEl.querySelector('.btn-quick-close');
        if (quickCloseBtn) {
            quickCloseBtn.addEventListener('click', () => {
                const pane = STATE.panes[paneId];
                if (!pane) return;
                if (confirm(`Close open position for ${pane.symbol}?`)) {
                    fetch('/api/bot/status?symbol=' + encodeURIComponent(pane.symbol))
                        .then(r => r.json())
                        .then(st => {
                            if (st && st.open_position) {
                                const p = st.open_position;
                                fetch('/api/trading/cancel', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        ticket: p.ticket,
                                        is_position: true,
                                        symbol: pane.symbol,
                                        volume: p.volume,
                                        type: p.type
                                    })
                                });
                            }
                        });
                }
            });
        }

        // Active pane highlight
        paneEl.addEventListener('click', () => {
            document.querySelectorAll('.chart-pane').forEach(el => el.classList.remove('active-pane'));
            paneEl.classList.add('active-pane');
        });

        // Right-click context menu for trading
        paneEl.addEventListener('contextmenu', (evt) => {
            evt.preventDefault();
            const p = STATE.panes[paneId];
            if (p.source !== 'mt5' || STATE.mt5Status !== 'connected') return;
            showContextMenu(evt, paneId);
        });

        // Re-render overlays when chart pans/zooms using a robust animation loop
        // because LWC doesn't provide a hook for vertical price-scale dragging.
        const syncOverlays = () => {
            if (pane.isDisposed || !STATE.panes[paneId]) return;
            if (STATE.panes[paneId].source === 'mt5') {
                syncTradingOverlays(paneId);
            }
            if (!pane.isDisposed && STATE.panes[paneId]) {
                pane._rafSyncOverlays = requestAnimationFrame(syncOverlays);
            }
        };
        pane._rafSyncOverlays = requestAnimationFrame(syncOverlays);

        // Indicator toolbar wiring
        paneEl.querySelectorAll('.ind-chip').forEach(btn => {
            const ind = btn.dataset.indicator;
            if (Object.entries(activeIndicators || {}).some(([key, active]) => active && getIndicatorBaseKey(key) === ind)) {
                btn.classList.add('active');
                const group = btn.closest('.ind-chip-group');
                if (group) group.classList.add('active');
            }
            btn.addEventListener('click', e => {
                e.stopPropagation();
                toggleIndicator(paneId, ind, btn);
            });
        });

        const indicatorLibraryBtn = paneEl.querySelector('.indicator-library-btn');
        if (indicatorLibraryBtn) {
            indicatorLibraryBtn.addEventListener('click', e => {
                e.stopPropagation();
                openIndicatorLibrary(paneId);
            });
        }

        // Settings gear wiring
        paneEl.querySelectorAll('.ind-settings-icon').forEach(btn => {
            const ind = btn.dataset.indicator;
            btn.addEventListener('click', e => {
                e.stopPropagation();
                if (ind === 'smc') {
                    openSMCSettings(paneId);
                }
            });
        });

        // Drawing tool wiring
        paneEl.querySelectorAll('.tool-chip').forEach(btn => {
            btn.addEventListener('click', e => {
                e.stopPropagation();
                handleToolClick(paneId, btn.dataset.tool, btn);
            });
        });

        // Drawing tool click on chart
        chartMount.addEventListener('click', e => handleChartClick(e, paneId));

        // Load data
        loadChartData(paneId);
    }

    // ──────────────────────────────────────────────
    // DESTROY PANE
    // ──────────────────────────────────────────────
    function destroyPane(paneId) {
        const pane = STATE.panes[paneId];
        if (!pane) return;
        pane.isDisposed = true;

        if (pane.resizeObserver) {
            try { pane.resizeObserver.disconnect(); } catch (e) { }
        }
        if (pane.oscResizeObserver) {
            try { pane.oscResizeObserver.disconnect(); } catch (e) { }
        }
        if (pane._backfillTimeout) {
            clearTimeout(pane._backfillTimeout);
            pane._backfillTimeout = null;
        }
        if (pane._pollTimer) {
            clearInterval(pane._pollTimer);
            pane._pollTimer = null;
        }
        if (pane.pollingTimer) {
            clearInterval(pane.pollingTimer);
            pane.pollingTimer = null;
        }
        if (pane.renkoPollingTimer) {
            clearInterval(pane.renkoPollingTimer);
            pane.renkoPollingTimer = null;
        }
        if (pane._rafSyncOverlays) {
            cancelAnimationFrame(pane._rafSyncOverlays);
            pane._rafSyncOverlays = null;
        }

        cleanupFeeds(pane, true);

        if (pane.oscillators) {
            Object.values(pane.oscillators).forEach(osc => {
                try { if (osc.resizeObserver) osc.resizeObserver.disconnect(); } catch (e) { }
                try { if (osc.chart) osc.chart.remove(); } catch (e) { }
            });
            pane.oscillators = {};
        }
        try { if (pane.oscChart) pane.oscChart.remove(); } catch (e) { }
        try { if (pane.chart) pane.chart.remove(); } catch (e) { }
        if (pane.element && pane.element.parentNode)
            pane.element.parentNode.removeChild(pane.element);
        delete STATE.panes[paneId];
    }

    function resetPaneChartScale(paneId) {
        const pane = STATE.panes[paneId];
        if (!pane || !pane.chart) return;
        try {
            pane.chart.priceScale('right').applyOptions({
                autoScale: true,
                mode: LightweightCharts.PriceScaleMode.Normal,
                scaleMargins: { top: 0.1, bottom: 0.1 }
            });
            pane.chart.timeScale().fitContent();
        } catch (e) { }
    }

    function cleanupFeeds(pane, isDisposing = false) {
        if (pane.ws) { try { pane.ws.close(); } catch (e) { } pane.ws = null; }
        if (pane.pollingTimer) { clearInterval(pane.pollingTimer); pane.pollingTimer = null; }
        if (pane.renkoPollingTimer) { clearInterval(pane.renkoPollingTimer); pane.renkoPollingTimer = null; }
        if (pane._pollTimer) { clearInterval(pane._pollTimer); pane._pollTimer = null; }
        if (pane._backfillTimeout) { clearTimeout(pane._backfillTimeout); pane._backfillTimeout = null; }
        pane._isSyncingHistorical = false;
        pane._lastSyncTime = null;

        if (!isDisposing && !pane.isDisposed && pane.chart) {
            if (pane.stSeries) { try { pane.chart.removeSeries(pane.stSeries); } catch (e) { } }
            if (pane.zoneLines && Array.isArray(pane.zoneLines) && pane.series) {
                pane.zoneLines.forEach(l => { try { pane.series.removePriceLine(l); } catch (e) { } });
            }
            if (pane._aiRenkoPool && Array.isArray(pane._aiRenkoPool)) {
                pane._aiRenkoPool.forEach(s => { try { pane.chart.removeSeries(s); } catch (e) { } });
                pane._aiRenkoPool = [];
            }
            if (pane._vwapPool) {
                Object.values(pane._vwapPool).forEach(pool => {
                    if (Array.isArray(pool)) pool.forEach(s => { try { pane.chart.removeSeries(s); } catch (e) { } });
                });
                pane._vwapPool = {};
            }
        }
        pane.stSeries = null;
        pane.zoneLines = [];
        pane._aiRenkoPool = [];
        pane._vwapPool = {};
    }

    // ──────────────────────────────────────────────
    // CONFIG CHANGE
    // ──────────────────────────────────────────────
    function handlePaneConfigChange(paneId) {
        const pane = STATE.panes[paneId];
        if (!pane) return;
        const source = pane.element.querySelector('.pane-source-select').value;
        const symbol = pane.element.querySelector('.pane-symbol-input').value.trim().toUpperCase();
        const timeframe = pane.element.querySelector('.pane-tf-select').value;

        pane.source = source; pane.symbol = symbol; pane.timeframe = timeframe;
        SafeStorage.setItem(`ag_pane_config_${paneId}`, JSON.stringify({ source, symbol, timeframe }));
        loadChartData(paneId);
    }

    // ──────────────────────────────────────────────
    // LOAD CHART DATA
    // ──────────────────────────────────────────────
    function loadChartData(paneId) {
        const pane = STATE.panes[paneId];
        if (!pane) return;

        cleanupFeeds(pane);
        pane.lastPrice = null; pane.lastCandle = null; pane.candles = [];
        pane.isBackfilling = false;
        pane.hasMoreHistory = true;

        // Reset price scale auto-scale immediately on symbol / config change
        pane.chart.priceScale('right').applyOptions({
            autoScale: true,
            mode: LightweightCharts.PriceScaleMode.Normal,
            scaleMargins: { top: 0.1, bottom: 0.1 }
        });

        // Fast synchronous price format based on asset class
        const initialFmt = getPriceFormatOptions(pane.source, pane.symbol, null);
        pane.series.applyOptions({ priceFormat: initialFmt });

        // Clear all overlay series
        Object.values(pane.overlaySeries).forEach(s => {
            try { pane.chart.removeSeries(s); } catch (e) { }
        });
        pane.overlaySeries = {};
        clearSMC(pane);
        clearAiRenko(pane);

        // Clear oscillator
        clearOscillator(pane);

        // Update ticker
        pane.element.querySelector('.ticker-symbol').textContent = pane.symbol;
        pane.element.querySelector('.ticker-price').textContent = '--';
        pane.element.querySelector('.ticker-direction').textContent = '--';

        // Toggle Renko controls visibility
        const isRenko = (pane.timeframe && pane.timeframe.toLowerCase() === 'renko');
        const renkoStrip = pane.element.querySelector('.renko-controls-strip');
        if (renkoStrip) renkoStrip.style.display = isRenko ? 'inline-flex' : 'none';

        // Fetch bot status for new symbol immediately
        fetchBotStatus(pane);

        // Check if Renko mode is requested
        if (isRenko) {
            loadRenkoData(pane);
            return;
        }

        // Show spinner
        const overlay = pane.element.querySelector('.pane-loading-overlay');
        if (overlay) {
            overlay.classList.remove('hidden');
            overlay.querySelector('.loading-text').innerHTML =
                '<div class="spinner"></div><span class="loading-text">Fetching historical data...</span>';
        }

        const url = buildHistoricalUrl(pane, 500);
        fetch(url)
            .then(r => r.json())
            .then(data => {
                if (pane.isDisposed || !STATE.panes[pane.id] || !pane.chart) return;
                if (data.error || !Array.isArray(data) || data.length === 0)
                    throw new Error(data.error || 'No data returned');

                pane.candles = data;
                rebuildTimeIndexMap(pane);

                pane.series.setData(data);
                pane.chart.priceScale('right').applyOptions({ autoScale: true });
                pane.chart.timeScale().fitContent();

                if (data.length > 0) {
                    pane.lastCandle = { ...data[data.length - 1] };
                    pane.lastPrice = pane.lastCandle.close;
                    updateTickerDisplay(pane, pane.lastPrice, 0.0);
                }

                if (overlay) overlay.classList.add('hidden');

                // Dynamic price format from backend
                applySymbolFormat(pane);

                // Re-render all active indicators
                Object.keys(pane.activeIndicators).forEach(ind => {
                    if (pane.activeIndicators[ind]) renderIndicator(pane, ind);
                });

                wireLiveFeed(paneId);
            })
            .catch(err => {
                if (pane.isDisposed || !STATE.panes[pane.id]) return;
                console.error(`Pane #${paneId} data error:`, err);
                if (overlay)
                    overlay.querySelector('.loading-text').innerHTML =
                        `<span class="bear-text">Failed to fetch data.<br>${err.message}</span>`;
            });
    }

    function buildHistoricalUrl(pane, limit, beforeTime = null) {
        const params = new URLSearchParams({
            source: pane.source,
            symbol: pane.symbol,
            timeframe: pane.timeframe,
            limit: String(limit)
        });
        if (beforeTime != null) params.set('before', String(beforeTime));
        return `/api/historical?${params.toString()}`;
    }

    function rebuildTimeIndexMap(pane) {
        pane.timeToIndexMap = new Map();
        pane.candles.forEach((c, idx) => pane.timeToIndexMap.set(c.time, idx));
    }

    function mergeCandles(existing, incoming, preferIncoming = false) {
        const byTime = new Map();
        const list = preferIncoming ? [...existing, ...incoming] : [...incoming, ...existing];
        list.forEach(candle => {
            if (candle && candle.time != null) byTime.set(candle.time, candle);
        });
        return Array.from(byTime.values()).sort((a, b) => a.time - b.time);
    }

    function applySymbolFormat(pane) {
        if (pane.isDisposed || !STATE.panes[pane.id] || !pane.chart || !pane.series) return;
        fetch(`/api/symbol_format?source=${pane.source}&symbol=${pane.symbol}`)
            .then(r => r.json())
            .then(fd => {
                if (pane.isDisposed || !STATE.panes[pane.id] || !pane.chart || !pane.series) return;
                pane.series.applyOptions({
                    priceFormat: { type: 'price', precision: fd.precision, minMove: fd.minMove }
                });
                pane.chart.priceScale('right').applyOptions({ autoScale: true });
            })
            .catch(() => {
                if (pane.isDisposed || !STATE.panes[pane.id] || !pane.chart || !pane.series) return;
                const fo = getPriceFormatOptions(pane.source, pane.symbol, pane.lastPrice);
                pane.series.applyOptions({ priceFormat: fo });
                pane.chart.priceScale('right').applyOptions({ autoScale: true });
            });
    }

    // ══════════════════════════════════════════════
    //  INDICATOR ENGINE
    // ══════════════════════════════════════════════

    function toggleIndicator(paneId, indKey, btn) {
        const pane = STATE.panes[paneId];
        if (!pane) return;

        const isActive = getActiveIndicatorKeysByBase(pane, indKey).length > 0;

        if (isActive) {
            if (indKey === 'smc' || indKey === 'ai_renko') {
                // SMC and AI Renko are singleton overlays
                removeIndicatorsByBase(pane, indKey);
                btn.classList.remove('active');
                const group = btn.closest('.ind-chip-group');
                if (group) group.classList.remove('active');
            } else {
                const instanceKey = createIndicatorInstanceKey(pane, indKey);
                pane.indicatorVisibility = pane.indicatorVisibility || {};
                pane.indicatorVisibility[instanceKey] = true;
                renderIndicator(pane, instanceKey);
                pane.activeIndicators[instanceKey] = true;
                btn.classList.add('active');
            }
        } else {
            // Add
            if (pane.candles.length === 0) {
                console.warn(`Pane #${paneId}: No data loaded yet. Load chart first.`);
                return;
            }

            pane.indicatorVisibility = pane.indicatorVisibility || {};
            pane.indicatorVisibility[indKey] = true;
            renderIndicator(pane, indKey);
            pane.activeIndicators[indKey] = true;
            btn.classList.add('active');
            const group = btn.closest('.ind-chip-group');
            if (group) group.classList.add('active');
        }

        saveIndicatorState(pane);
        updateActiveIndicatorLegend(pane);
        renderIndicatorLibrary();
    }

    function getIndicatorBaseKey(indKey) {
        return String(indKey || '').split('__')[0];
    }

    function getIndicatorDef(indKey) {
        const baseKey = getIndicatorBaseKey(indKey);
        if (INDICATOR_DEFS[baseKey]) return INDICATOR_DEFS[baseKey];
        const aliasMap = {
            rsi14: 'rsi',
            bb20: 'bbands',
            sma20: 'sma',
            sma50: 'sma',
            ema9: 'ema',
            ema21: 'ema'
        };
        if (aliasMap[baseKey] && INDICATOR_DEFS[aliasMap[baseKey]]) {
            return INDICATOR_DEFS[aliasMap[baseKey]];
        }
        return null;
    }

    function getActiveIndicatorKeysByBase(pane, baseKey) {
        return Object.entries(pane.activeIndicators || {})
            .filter(([key, active]) => active && getIndicatorBaseKey(key) === baseKey)
            .map(([key]) => key);
    }

    function createIndicatorInstanceKey(pane, baseKey) {
        if (!pane.activeIndicators?.[baseKey]) return baseKey;
        let key;
        do {
            key = `${baseKey}__${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
        } while (pane.activeIndicators?.[key]);
        return key;
    }

    function seriesKey(indKey, suffix = 'line') {
        return getIndicatorBaseKey(indKey) === indKey && suffix === 'line'
            ? indKey
            : `${indKey}:${suffix}`;
    }

    function getIndicatorConfig(pane, indKey) {
        const def = getIndicatorDef(indKey) || { defaults: {} };
        const cfg = { ...(def.defaults || {}), ...((pane.indicatorSettings || {})[indKey] || {}) };

        // Validate & clamp based on def.params (backend metadata schema)
        if (def.params && Array.isArray(def.params)) {
            def.params.forEach(p => {
                const val = cfg[p.name];
                if (p.type === 'int' || p.type === 'float') {
                    let num = Number(val);
                    if (!Number.isFinite(num)) {
                        num = p.default != null ? Number(p.default) : 0;
                    }
                    if (p.min != null && num < p.min) num = p.min;
                    if (p.max != null && num > p.max) num = p.max;
                    if (p.type === 'int') num = Math.round(num);
                    cfg[p.name] = num;
                } else if (p.type === 'bool') {
                    cfg[p.name] = val !== undefined ? Boolean(val) : Boolean(p.default);
                }
            });
        }

        // Validate legacy fields if present
        if (def.fields && Array.isArray(def.fields)) {
            def.fields.forEach(field => {
                const [key, , type, min, max] = field;
                if (type !== 'number') return;
                const value = Number(cfg[key]);
                cfg[key] = Number.isFinite(value) && (min == null || value >= min) && (max == null || value <= max)
                    ? value
                    : (def.defaults?.[key] ?? value);
            });
        }
        return cfg;
    }

    function setIndicatorConfig(pane, indKey, cfg) {
        pane.indicatorSettings = pane.indicatorSettings || {};
        pane.indicatorSettings[indKey] = { ...(getIndicatorDef(indKey)?.defaults || {}), ...cfg };
        SafeStorage.setItem(`ag_pane_indicator_settings_${pane.id}`, JSON.stringify(pane.indicatorSettings));
    }

    function saveIndicatorState(pane) {
        if (!pane) return;
        const indicators = (pane.activeIndicators && typeof pane.activeIndicators === 'object' && !Array.isArray(pane.activeIndicators)) ? pane.activeIndicators : {};
        const settings = (pane.indicatorSettings && typeof pane.indicatorSettings === 'object' && !Array.isArray(pane.indicatorSettings)) ? pane.indicatorSettings : {};
        const visibility = (pane.indicatorVisibility && typeof pane.indicatorVisibility === 'object' && !Array.isArray(pane.indicatorVisibility)) ? pane.indicatorVisibility : {};
        SafeStorage.setItem(`ag_pane_indicators_${pane.id}`, JSON.stringify(indicators));
        SafeStorage.setItem(`ag_pane_indicator_settings_${pane.id}`, JSON.stringify(settings));
        SafeStorage.setItem(`ag_pane_indicator_visibility_${pane.id}`, JSON.stringify(visibility));
    }

    function isIndicatorVisible(pane, indKey) {
        return (pane.indicatorVisibility || {})[indKey] !== false;
    }

    function setIndicatorVisibility(pane, indKey, visible) {
        pane.indicatorVisibility = pane.indicatorVisibility || {};
        pane.indicatorVisibility[indKey] = visible;
        saveIndicatorState(pane);
    }

    function toggleIndicatorVisibility(pane, indKey) {
        if (!pane || !pane.activeIndicators?.[indKey]) return;

        const nextVisible = !isIndicatorVisible(pane, indKey);
        setIndicatorVisibility(pane, indKey, nextVisible);

        const baseKey = getIndicatorBaseKey(indKey);
        if (baseKey === 'supertrend') {
            if (pane.stSeries) pane.stSeries.applyOptions({ visible: nextVisible });
            if (pane._supertrendPool && pane._supertrendPool[indKey]) {
                pane._supertrendPool[indKey].forEach(s => s.applyOptions({ visible: nextVisible }));
            }
        }
        if (baseKey === 'vwap' && pane._vwapPool && pane._vwapPool[indKey]) {
            pane._vwapPool[indKey].forEach(s => s.applyOptions({ visible: nextVisible }));
        }

        // Toggle overlays on main chart
        Object.keys(pane.overlaySeries || {}).forEach(k => {
            if (k === indKey || k.startsWith(`${indKey}:`)) {
                try { pane.overlaySeries[k].applyOptions({ visible: nextVisible }); } catch (e) { }
            }
        });

        // Toggle oscillator series & panel label
        if (pane.oscillators?.[indKey]) {
            const osc = pane.oscillators[indKey];
            Object.values(osc.series || {}).forEach(s => {
                try { s.applyOptions({ visible: nextVisible }); } catch (e) { }
            });
            const lbl = osc.subpaneEl?.querySelector('.oscillator-label');
            if (lbl) lbl.classList.toggle('is-hidden', !nextVisible);
            const hideBtn = lbl?.querySelector('.indicator-hide-btn');
            if (hideBtn) {
                hideBtn.textContent = nextVisible ? '👁' : '⊘';
                hideBtn.title = nextVisible ? 'Hide indicator' : 'Show indicator';
            }
        }

        if (nextVisible) {
            renderIndicator(pane, indKey);
        }

        updateActiveIndicatorLegend(pane);
        renderIndicatorLibrary();
    }

    function setIndicatorActive(pane, indKey, active) {
        if (!pane || !indKey) return;
        pane.activeIndicators = (pane.activeIndicators && typeof pane.activeIndicators === 'object' && !Array.isArray(pane.activeIndicators)) ? pane.activeIndicators : {};
        pane.indicatorVisibility = (pane.indicatorVisibility && typeof pane.indicatorVisibility === 'object' && !Array.isArray(pane.indicatorVisibility)) ? pane.indicatorVisibility : {};
        pane.indicatorSettings = (pane.indicatorSettings && typeof pane.indicatorSettings === 'object' && !Array.isArray(pane.indicatorSettings)) ? pane.indicatorSettings : {};
        if (active) {
            pane.activeIndicators[indKey] = true;
            pane.indicatorVisibility[indKey] = true;
            if (pane.candles && pane.candles.length > 0) renderIndicator(pane, indKey);
        } else {
            removeIndicator(pane, indKey);
            delete pane.activeIndicators[indKey];
            if (pane.indicatorSettings) delete pane.indicatorSettings[indKey];
            if (pane.indicatorVisibility) delete pane.indicatorVisibility[indKey];
            if (pane.oscillatorSizes) delete pane.oscillatorSizes[indKey];
        }
        saveIndicatorState(pane);
        updateToolbarIndicatorState(pane, indKey);
        updateActiveIndicatorLegend(pane);
    }

    function addIndicatorFromLibrary(pane, baseKey) {
        if (!pane || !baseKey || !getIndicatorDef(baseKey)) return null;

        const indKey = createIndicatorInstanceKey(pane, baseKey);
        setIndicatorConfig(pane, indKey, readIndicatorSettingsForm(baseKey));
        setIndicatorActive(pane, indKey, true);
        selectedIndicatorKey = indKey;
        return indKey;
    }

    function removeIndicatorsByBase(pane, baseKey) {
        getActiveIndicatorKeysByBase(pane, baseKey).forEach(indKey => {
            removeIndicator(pane, indKey);
            delete pane.activeIndicators[indKey];
            if (pane.indicatorSettings) delete pane.indicatorSettings[indKey];
            if (pane.indicatorVisibility) delete pane.indicatorVisibility[indKey];
            if (pane.oscillatorSizes) delete pane.oscillatorSizes[indKey];
        });
        saveIndicatorState(pane);
        updateToolbarIndicatorState(pane, baseKey);
        updateActiveIndicatorLegend(pane);
    }

    function updateToolbarIndicatorState(pane, indKey) {
        const baseKey = getIndicatorBaseKey(indKey);
        const btn = pane.element.querySelector(`.ind-chip[data-indicator="${baseKey}"]`);
        if (!btn) return;
        const active = getActiveIndicatorKeysByBase(pane, baseKey).length > 0;
        btn.classList.toggle('active', active);
        const group = btn.closest('.ind-chip-group');
        if (group) group.classList.toggle('active', active);
    }

    function getIndicatorLegendLabel(pane, indKey) {
        const baseKey = getIndicatorBaseKey(indKey);
        const def = getIndicatorDef(indKey);
        const cfg = getIndicatorConfig(pane, indKey);
        if (!def) return indKey;

        switch (baseKey) {
            case 'sma':
            case 'sma20':
            case 'sma50':
                return `SMA ${cfg.period || cfg.length || 20}`;
            case 'ema':
            case 'ema9':
            case 'ema21':
                return `EMA ${cfg.period || cfg.length || 9}`;
            case 'wma':
            case 'wma20':
                return `WMA ${cfg.period || cfg.length || 20}`;
            case 'hma':
            case 'hma20':
                return `HMA ${cfg.period || cfg.length || 20}`;
            case 'bbands':
            case 'bb20':
                return `BB ${cfg.period || cfg.length || 20} ${cfg.stdDev || cfg.std || 2}`;
            case 'ichimoku':
                return `Ichimoku ${cfg.tenkan} ${cfg.kijun} ${cfg.spanB}`;
            case 'supertrend': {
                const isRenko = (pane.timeframe && pane.timeframe.toLowerCase() === 'renko');
                return isRenko ? 'Supertrend 1 3.1' : `Supertrend ${cfg.period || cfg.length || 10} ${cfg.multiplier || 3}`;
            }
            case 'ai_renko':
                return `AI Renko (${cfg.atrLength}, ${cfg.stFactor}, ${cfg.adxThreshold})`;
            case 'rsi':
            case 'rsi14':
                return `RSI ${cfg.period || cfg.length || 14}`;
            case 'macd':
                return `MACD ${cfg.fast || 12} ${cfg.slow || 26} ${cfg.signal || 9}`;
            case 'stoch':
                return `Stoch ${cfg.k || 14} ${cfg.d || 3} ${cfg.smooth || 3}`;
            case 'cci':
                return `CCI ${cfg.period || cfg.length || 20}`;
            case 'momentum':
                return `Mom ${cfg.period || cfg.length || 10}`;
            case 'roc':
                return `ROC ${cfg.period || cfg.length || 9}`;
            case 'atr':
                return `ATR ${cfg.period || cfg.length || 14}`;
            case 'adx':
                return `ADX ${cfg.period || cfg.length || 14}`;
            default: {
                const len = cfg.length ?? cfg.period;
                return len != null ? `${def.short || def.name} (${len})` : (def.short || def.name);
            }
        }
    }

    function openIndicatorSettings(paneId, indKey) {
        if (getIndicatorBaseKey(indKey) === 'smc') {
            openSMCSettings(paneId);
            return;
        }

        const pane = STATE.panes[paneId];
        if (!pane) return;
        activeIndicatorLibraryPaneId = paneId;
        selectedIndicatorKey = indKey;
        editingIndicatorKey = indKey;

        const paneLabel = document.getElementById('indicator-library-pane-label');
        if (paneLabel) paneLabel.textContent = `Pane #${paneId} · ${pane.symbol} · ${pane.timeframe}`;
        const search = document.getElementById('indicator-library-search');
        if (search) search.value = '';
        const modal = document.getElementById('indicator-library-dialog');
        const backdrop = document.getElementById('modal-backdrop');
        if (modal) modal.classList.remove('hidden');
        if (backdrop) backdrop.classList.remove('hidden');
        renderIndicatorLibrary();
    }

    function makeIndicatorLegendItem(pane, indKey) {
        const item = document.createElement('div');
        item.className = 'indicator-legend-item';
        item.dataset.indicatorKey = indKey;
        item.classList.toggle('is-hidden', !isIndicatorVisible(pane, indKey));

        const name = document.createElement('span');
        name.className = 'indicator-legend-name';
        name.textContent = getIndicatorLegendLabel(pane, indKey);
        item.appendChild(name);

        const actions = document.createElement('span');
        actions.className = 'indicator-legend-actions';

        const hideBtn = document.createElement('button');
        hideBtn.type = 'button';
        hideBtn.className = 'indicator-action-btn indicator-hide-btn';
        hideBtn.title = isIndicatorVisible(pane, indKey) ? 'Hide indicator' : 'Show indicator';
        hideBtn.setAttribute('aria-label', `${hideBtn.title}: ${name.textContent}`);
        hideBtn.textContent = isIndicatorVisible(pane, indKey) ? '👁' : '⊘';
        hideBtn.addEventListener('click', event => {
            event.stopPropagation();
            toggleIndicatorVisibility(pane, indKey);
        });

        const settingsBtn = document.createElement('button');
        settingsBtn.type = 'button';
        settingsBtn.className = 'indicator-action-btn indicator-settings-btn';
        settingsBtn.title = 'Indicator settings';
        settingsBtn.setAttribute('aria-label', `${name.textContent} settings`);
        settingsBtn.textContent = '⚙';
        settingsBtn.addEventListener('click', event => {
            event.stopPropagation();
            openIndicatorSettings(pane.id, indKey);
        });

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'indicator-action-btn indicator-remove-btn';
        removeBtn.title = 'Remove indicator';
        removeBtn.setAttribute('aria-label', `Remove ${name.textContent}`);
        removeBtn.textContent = '✕';
        removeBtn.addEventListener('click', event => {
            event.stopPropagation();
            setIndicatorActive(pane, indKey, false);
            renderIndicatorLibrary();
        });

        actions.appendChild(hideBtn);
        actions.appendChild(settingsBtn);
        actions.appendChild(removeBtn);
        item.appendChild(actions);
        return item;
    }

    function updateActiveIndicatorLegend(pane) {
        if (!pane?.element) return;
        const legend = pane.element.querySelector('.indicator-legend');
        if (!legend) return;

        legend.innerHTML = '';
        Object.entries(pane.activeIndicators || {}).forEach(([indKey, active]) => {
            const def = getIndicatorDef(indKey);
            if (!active || !def) return;
            if (def.kind !== 'overlay' && isIndicatorVisible(pane, indKey)) return;
            legend.appendChild(makeIndicatorLegendItem(pane, indKey));
        });
    }

    function isPandasTaIndicator(baseKey) {
        if (!baseKey || ['smc', 'ai_renko'].includes(baseKey)) return false;
        const def = INDICATOR_DEFS[baseKey];
        if (def && (def.inputs || def.outputs || def.params)) return true;
        const legacyOnly = ['sma20', 'sma50', 'ema9', 'ema21', 'wma20', 'hma20', 'bb20', 'rsi14', 'volume'];
        return !legacyOnly.includes(baseKey);
    }

    function sanitizeSeriesData(points, isHistogram = false) {
        if (!Array.isArray(points)) return [];
        if (isHistogram) {
            return points
                .filter(p => p && p.time != null && p.value !== null && p.value !== undefined && !Number.isNaN(p.value))
                .map(p => ({
                    time: p.time,
                    value: p.value,
                    color: p.value >= 0 ? '#26A69A' : '#EF5350'
                }));
        }
        return points
            .filter(p => p && p.time != null && p.value !== null && p.value !== undefined && !Number.isNaN(p.value))
            .map(p => ({ time: p.time, value: p.value }));
    }

    function renderBackendIndicatorSeries(pane, indKey, data) {
        if (!pane || pane.isDisposed || !STATE.panes[pane.id] || !pane.chart) return;
        if (!data || !data.series) return;

        const baseKey = getIndicatorBaseKey(indKey);
        const def = getIndicatorDef(indKey);
        const cfg = getIndicatorConfig(pane, indKey);
        const indicatorId = data.indicator || def?.id || baseKey;
        const kind = data.kind || def?.kind || 'overlay';
        const isOverlay = (kind === 'overlay');

        // Select canonical series to render
        let keysToRender = [];
        const seriesKeys = Object.keys(data.series);

        if (data.series.upper && data.series.middle && data.series.lower) {
            keysToRender = ['upper', 'middle', 'lower'];
        } else if (data.series.macd && data.series.signal && data.series.histogram) {
            keysToRender = ['macd', 'signal', 'histogram'];
        } else if (data.series.k && data.series.d) {
            keysToRender = ['k', 'd'];
        } else if (data.series.supertrend) {
            keysToRender = ['supertrend'];
        } else if (data.series.adx && data.series.dmp && data.series.dmn) {
            keysToRender = ['adx', 'dmp', 'dmn'];
        } else {
            const skipKeys = new Set();
            if (data.series.upper) seriesKeys.filter(k => k.startsWith('BBU') || k.startsWith('BBM') || k.startsWith('BBL')).forEach(k => skipKeys.add(k));
            if (data.series.macd) seriesKeys.filter(k => k.startsWith('MACD')).forEach(k => skipKeys.add(k));
            if (data.series.k) seriesKeys.filter(k => k.startsWith('STOCH')).forEach(k => skipKeys.add(k));
            if (data.series.supertrend) seriesKeys.filter(k => k.startsWith('SUPERT')).forEach(k => skipKeys.add(k));
            if (data.series.adx) seriesKeys.filter(k => k.startsWith('ADX_') || k.startsWith('DMP_') || k.startsWith('DMN_')).forEach(k => skipKeys.add(k));
            keysToRender = seriesKeys.filter(k => !skipKeys.has(k));
        }

        if (keysToRender.length === 0) return;

        const isVisible = isIndicatorVisible(pane, indKey);

        if (isOverlay) {
            // Render on main pane.chart
            keysToRender.forEach(sName => {
                const rawPts = data.series[sName];
                const isHist = sName.toLowerCase().includes('hist') || sName.toLowerCase().includes('vol');
                const cleanPts = sanitizeSeriesData(rawPts, isHist);
                const sKey = (keysToRender.length === 1) ? seriesKey(indKey) : seriesKey(indKey, sName);

                let color = cfg.color || '#2962FF';
                let width = cfg.width || 1.5;
                let extraOpts = {};

                if (sName === 'upper') {
                    color = cfg.color || '#26A69A';
                    width = 1.5;
                } else if (sName === 'middle') {
                    color = cfg.middleColor || '#FF9800';
                    width = 1;
                } else if (sName === 'lower') {
                    color = cfg.color || '#EF5350';
                    width = 1.5;
                } else if (sName === 'supertrend' || sName.startsWith('SUPERT_')) {
                    color = cfg.color || '#10B981';
                    width = 2;
                } else if (def?.outputs) {
                    const outDef = def.outputs.find(o => o.name === sName);
                    if (outDef?.color) color = outDef.color;
                }

                if (pane.overlaySeries[sKey]) {
                    pane.overlaySeries[sKey].applyOptions({
                        color,
                        lineWidth: width,
                        visible: isVisible,
                        ...extraOpts
                    });
                    pane.overlaySeries[sKey].setData(cleanPts);
                } else {
                    const s = pane.chart.addSeries(LightweightCharts.LineSeries, {
                        color,
                        lineWidth: width,
                        priceLineVisible: false,
                        lastValueVisible: true,
                        crosshairMarkerVisible: false,
                        visible: isVisible,
                        ...extraOpts
                    });
                    s.setData(cleanPts);
                    pane.overlaySeries[sKey] = s;
                }
            });
        } else {
            // Render in dedicated sub-pane inside .oscillators-container
            const label = getIndicatorLegendLabel(pane, indKey);
            const osc = ensureOscChart(pane, indKey, label);
            if (!osc) return;

            // Store primary series data for crosshair alignment
            const primaryKey = keysToRender.find(k => !k.toLowerCase().includes('hist') && !k.toLowerCase().includes('guide')) || keysToRender[0];
            if (primaryKey && data.series[primaryKey]) {
                osc.alignedData = sanitizeSeriesData(data.series[primaryKey]);
            }

            keysToRender.forEach(sName => {
                const rawPts = data.series[sName];
                const isHist = sName.toLowerCase().includes('hist') || sName.toLowerCase().includes('vol');
                const cleanPts = sanitizeSeriesData(rawPts, isHist);

                let color = cfg.color || '#7E57C2';
                let width = 1.5;
                let extraOpts = {};

                if (sName === 'macd') {
                    color = cfg.macdColor || '#2962FF';
                    width = 1.5;
                } else if (sName === 'signal') {
                    color = cfg.signalColor || '#FF6D00';
                    width = 1;
                    extraOpts.lineStyle = LightweightCharts.LineStyle.Dotted;
                } else if (sName === 'k') {
                    color = cfg.kColor || '#2962FF';
                    width = 1.5;
                } else if (sName === 'd') {
                    color = cfg.dColor || '#FF6D00';
                    width = 1;
                } else if (sName === 'adx') {
                    color = cfg.adxColor || '#FBC02D';
                    width = 1.5;
                } else if (sName === 'dmp') {
                    color = cfg.plusColor || '#089981';
                    width = 1;
                } else if (sName === 'dmn') {
                    color = cfg.minusColor || '#F23645';
                    width = 1;
                } else if (def?.outputs) {
                    const outDef = def.outputs.find(o => o.name === sName);
                    if (outDef?.color) color = outDef.color;
                }

                if (!osc.series[sName]) {
                    if (isHist) {
                        osc.series[sName] = osc.chart.addSeries(LightweightCharts.HistogramSeries, {
                            priceLineVisible: false,
                            lastValueVisible: false,
                            visible: isVisible
                        });
                    } else {
                        osc.series[sName] = osc.chart.addSeries(LightweightCharts.LineSeries, {
                            color,
                            lineWidth: width,
                            priceLineVisible: false,
                            lastValueVisible: true,
                            crosshairMarkerVisible: false,
                            visible: isVisible,
                            ...extraOpts
                        });
                    }
                } else {
                    if (isHist) {
                        osc.series[sName].applyOptions({ visible: isVisible });
                    } else {
                        osc.series[sName].applyOptions({
                            color,
                            lineWidth: width,
                            visible: isVisible,
                            ...extraOpts
                        });
                    }
                }
                osc.series[sName].setData(cleanPts);
            });

            // Set guide lines for known oscillator types
            const tFirst = pane.candles[0]?.time;
            const tLast = pane.candles[pane.candles.length - 1]?.time;
            if (tFirst != null && tLast != null) {
                if (indicatorId === 'rsi') {
                    const ob = cfg.overbought || 70;
                    const os = cfg.oversold || 30;
                    setGuideLine(osc.series, osc.chart, 'rsiOB', tFirst, tLast, { value: ob, color: 'rgba(255,23,68,0.4)' });
                    setGuideLine(osc.series, osc.chart, 'rsiOS', tFirst, tLast, { value: os, color: 'rgba(0,230,118,0.4)' });
                } else if (indicatorId === 'stoch') {
                    setGuideLine(osc.series, osc.chart, 'stochUpper', tFirst, tLast, { value: 80, color: 'rgba(255,23,68,0.35)' });
                    setGuideLine(osc.series, osc.chart, 'stochLower', tFirst, tLast, { value: 20, color: 'rgba(0,230,118,0.35)' });
                } else if (indicatorId === 'cci') {
                    setGuideLine(osc.series, osc.chart, 'cciUpper', tFirst, tLast, { value: 100, color: 'rgba(255,23,68,0.35)' });
                    setGuideLine(osc.series, osc.chart, 'cciLower', tFirst, tLast, { value: -100, color: 'rgba(0,230,118,0.35)' });
                }
            }

            syncTimeScales(pane);
        }

        updateActiveIndicatorLegend(pane);
    }

    async function computeIndicatorOnBackend(pane, indKey) {
        if (!pane || pane.isDisposed || !STATE.panes[pane.id] || !pane.chart) return;
        if (!pane.candles || pane.candles.length === 0) return;
        if (!isIndicatorVisible(pane, indKey)) return;

        const baseKey = getIndicatorBaseKey(indKey);
        const def = getIndicatorDef(indKey);
        const indicatorId = def?.id || baseKey;

        // Build parameters from indicatorSettings and getIndicatorConfig
        const cfg = getIndicatorConfig(pane, indKey);
        const customParams = (pane.indicatorSettings && pane.indicatorSettings[indKey]) || {};
        const mergedParams = { ...cfg, ...customParams };

        const params = {};
        Object.entries(mergedParams).forEach(([k, v]) => {
            if (['color', 'width', 'middleColor', 'kColor', 'dColor', 'macdColor', 'signalColor', 'adxColor', 'plusColor', 'minusColor', 'conversionColor', 'baseColor', 'cloudColor'].includes(k)) return;
            params[k] = v;
        });

        if (params.period !== undefined && params.length === undefined) {
            params.length = params.period;
        }

        const isRenko = Boolean(pane.timeframe && pane.timeframe.toLowerCase() === 'renko');
        let payload;

        if (isRenko) {
            const renkoParams = {
                symbol: pane.symbol || 'GBPUSD',
                brick_size: pane.brickSize || pane.fixedBrickSize || (pane.symbol && pane.symbol.includes('XAU') ? 1.0 : (pane.symbol && pane.symbol.includes('BTC') ? 50.0 : 0.00035)),
                timeline_mode: pane.timelineMode || 'equidistant'
            };
            payload = {
                indicator: indicatorId,
                params: params,
                data_type: 'renko',
                renko_params: renkoParams
            };
        } else {
            payload = {
                indicator: indicatorId,
                params: params,
                data_type: 'candle',
                candles: pane.candles
            };
        }

        pane._backendIndTokens = pane._backendIndTokens || {};
        const token = (pane._backendIndTokens[indKey] || 0) + 1;
        pane._backendIndTokens[indKey] = token;

        try {
            const resp = await fetch('/api/indicators/compute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!resp.ok) {
                console.warn(`[chart_manager] /api/indicators/compute returned HTTP ${resp.status} for ${indKey}`);
                return;
            }

            const data = await resp.json();

            // Ignore stale responses or if pane was disposed/indicator deactivated
            if (pane._backendIndTokens[indKey] !== token || pane.isDisposed || !STATE.panes[pane.id] || !pane.activeIndicators?.[indKey]) {
                return;
            }

            if (data.warning) {
                console.warn(`[chart_manager] Indicator ${indKey} warning:`, data.warning);
            }

            if (data.series && typeof data.series === 'object') {
                renderBackendIndicatorSeries(pane, indKey, data);
            }
        } catch (err) {
            console.warn(`[chart_manager] Failed to compute indicator ${indKey}:`, err);
        }
    }

    function renderIndicator(pane, indKey) {
        if (!pane.candles || pane.candles.length === 0) return;

        if (!isIndicatorVisible(pane, indKey)) {
            Object.keys(pane.overlaySeries || {}).forEach(k => {
                if (k === indKey || k.startsWith(`${indKey}:`)) {
                    try { pane.overlaySeries[k].applyOptions({ visible: false }); } catch (e) { }
                }
            });
            if (pane.oscillators?.[indKey]) {
                Object.values(pane.oscillators[indKey].series || {}).forEach(s => {
                    try { s.applyOptions({ visible: false }); } catch (e) { }
                });
            }
            updateActiveIndicatorLegend(pane);
            return;
        }

        const c = pane.candles;
        const cfg = getIndicatorConfig(pane, indKey);
        const baseKey = getIndicatorBaseKey(indKey);

        if (baseKey === 'smc') {
            renderSMC(pane);
            updateActiveIndicatorLegend(pane);
            return;
        }

        if (baseKey === 'ai_renko') {
            renderAiRenko(pane, cfg, indKey);
            updateActiveIndicatorLegend(pane);
            return;
        }

        if (isPandasTaIndicator(baseKey)) {
            computeIndicatorOnBackend(pane, indKey);
            return;
        }

        switch (baseKey) {
            case 'sma':
            case 'sma20': renderLineSeries(pane, seriesKey(indKey), Indicators.sma(c, cfg.period || cfg.length || 20), cfg.color || '#2962FF', cfg.width || 2); break;
            case 'sma50': renderLineSeries(pane, seriesKey(indKey), Indicators.sma(c, cfg.period || cfg.length || 50), cfg.color || '#B07FFF', cfg.width || 2); break;
            case 'ema':
            case 'ema9': renderLineSeries(pane, seriesKey(indKey), Indicators.ema(c, cfg.period || cfg.length || 9), cfg.color || '#FF6B6B', cfg.width || 2); break;
            case 'ema21': renderLineSeries(pane, seriesKey(indKey), Indicators.ema(c, cfg.period || cfg.length || 21), cfg.color || '#B07FFF', cfg.width || 2); break;
            case 'wma':
            case 'wma20': renderLineSeries(pane, seriesKey(indKey), Indicators.wma(c, cfg.period || cfg.length || 20), cfg.color || '#fbc02d', cfg.width || 2); break;
            case 'hma':
            case 'hma20': renderLineSeries(pane, seriesKey(indKey), Indicators.hma(c, cfg.period || cfg.length || 20), cfg.color || '#ff9800', cfg.width || 2); break;
            case 'dema': renderLineSeries(pane, seriesKey(indKey), Indicators.ema(c, cfg.length || 10), cfg.color || '#00E676', cfg.width || 2); break;
            case 'vwap': renderVWAP(pane, cfg, indKey); break;

            case 'bbands':
            case 'bb20': {
                const period = cfg.period || cfg.length || 20;
                const stdDev = cfg.stdDev || cfg.std || 2;
                const bb = Indicators.bollingerBands(c, period, stdDev);
                renderLineSeries(pane, seriesKey(indKey, 'bbUpper'), bb.upper, cfg.color || IND_COLORS.bbUpper, 1.5);
                renderLineSeries(pane, seriesKey(indKey, 'bbMiddle'), bb.middle, cfg.middleColor || '#888', 1);
                renderLineSeries(pane, seriesKey(indKey, 'bbLower'), bb.lower, cfg.color || IND_COLORS.bbLower, 1.5);
                break;
            }

            case 'ichimoku': renderIchimoku(pane, cfg, indKey); break;
            case 'supertrend': renderSupertrend(pane, cfg, indKey); break;
            case 'rsi':
            case 'rsi14': renderOscillatorRSI(pane, cfg, indKey); break;
            case 'macd': renderOscillatorMACD(pane, cfg, indKey); break;
            case 'stoch': renderOscillatorStochastic(pane, cfg, indKey); break;
            case 'cci': renderOscillatorLine(pane, indKey, `CCI (${cfg.period || cfg.length || 20})`, Indicators.cci(c, cfg.period || cfg.length || 20), cfg.color || '#26a69a', 2, [{ value: 100, color: 'rgba(255,23,68,0.35)' }, { value: -100, color: 'rgba(0,230,118,0.35)' }]); break;
            case 'momentum': renderOscillatorLine(pane, indKey, `Momentum (${cfg.period || cfg.length || 10})`, Indicators.momentum(c, cfg.period || cfg.length || 10), cfg.color || '#ab47bc', 4, [{ value: 0, color: 'rgba(120,123,134,0.35)' }]); break;
            case 'roc': renderOscillatorLine(pane, indKey, `ROC (${cfg.period || cfg.length || 9})`, Indicators.roc(c, cfg.period || cfg.length || 9), cfg.color || '#29b6f6', 2, [{ value: 0, color: 'rgba(120,123,134,0.35)' }]); break;
            case 'atr': renderOscillatorLine(pane, indKey, `ATR (${cfg.period || cfg.length || 14})`, Indicators.atr(c, cfg.period || cfg.length || 14), cfg.color || '#ffb74d', 5); break;
            case 'obv': renderOscillatorLine(pane, indKey, 'OBV', Indicators.obv(c), cfg.color || '#7e57c2', 0); break;
            case 'adx': renderOscillatorADX(pane, cfg, indKey); break;
            case 'volume': renderOscillatorVolume(pane, indKey); break;
            default:
                computeIndicatorOnBackend(pane, indKey);
                break;
        }

        updateActiveIndicatorLegend(pane);
    }

    function removeIndicator(pane, indKey) {
        const baseKey = getIndicatorBaseKey(indKey);
        if (baseKey === 'smc') {
            clearSMC(pane);
            return;
        }

        if (baseKey === 'ai_renko') {
            clearAiRenko(pane);
            return;
        }

        if (baseKey === 'supertrend') {
            if (pane.stSeries) {
                try { pane.chart.removeSeries(pane.stSeries); } catch (e) { }
                pane.stSeries = null;
            }
            if (pane._supertrendPool && pane._supertrendPool[indKey]) {
                pane._supertrendPool[indKey].forEach(s => {
                    try { pane.chart.removeSeries(s); } catch (e) { }
                });
                delete pane._supertrendPool[indKey];
            }
        }

        if (baseKey === 'vwap' && pane._vwapPool && pane._vwapPool[indKey]) {
            pane._vwapPool[indKey].forEach(s => {
                try { pane.chart.removeSeries(s); } catch (e) { }
            });
            delete pane._vwapPool[indKey];
        }

        const legacyOverlayKeys = {
            sma: ['sma'],
            sma20: ['sma20'],
            sma50: ['sma50'],
            ema: ['ema'],
            ema9: ['ema9'],
            ema21: ['ema21'],
            wma: ['wma'],
            wma20: ['wma20'],
            hma: ['hma'],
            hma20: ['hma20'],
            dema: ['dema'],
            vwap: ['vwap'],
            bbands: ['bbUpper', 'bbMiddle', 'bbLower'],
            bb20: ['bbUpper', 'bbMiddle', 'bbLower'],
            ichimoku: ['ichiConversion', 'ichiBase', 'ichiSpanA', 'ichiSpanB'],
            supertrend: ['supertrend']
        };

        Object.keys(pane.overlaySeries || {}).forEach(k => {
            const isInstanceSeries = k === indKey || k.startsWith(`${indKey}:`);
            const isLegacySeries = baseKey === indKey && legacyOverlayKeys[baseKey]?.includes(k);
            if (!isInstanceSeries && !isLegacySeries) return;
            try { pane.chart.removeSeries(pane.overlaySeries[k]); } catch (e) { }
            delete pane.overlaySeries[k];
        });

        // Oscillator removal
        const isKnownOsc = ['rsi', 'rsi14', 'macd', 'volume', 'stoch', 'cci', 'momentum', 'roc', 'atr', 'obv', 'adx'].includes(baseKey);
        const def = getIndicatorDef(indKey);
        const isPanelKind = def && (def.kind === 'panel' || def.kind === 'oscillator');
        if (isKnownOsc || isPanelKind || pane.oscillators?.[indKey]) {
            clearOscillator(pane, indKey);
        }
    }

    // ── Helper to pad indicator data arrays to match candles 1:1 ──
    function alignDataToCandles(indicatorData, candles) {
        if (!indicatorData || !candles) return [];
        const dataMap = new Map();
        for (const item of indicatorData) {
            if (item && item.time) dataMap.set(item.time, item);
        }
        return candles.map(c => {
            if (dataMap.has(c.time)) {
                return dataMap.get(c.time);
            } else {
                return { time: c.time }; // Point with time but no value creates a gap
            }
        });
    }

    // ── Render an overlay LineSeries on the main chart ──
    function renderLineSeries(pane, key, data, color, lineWidth = 1.5, extraOpts = {}) {
        if (!data || data.length === 0) return;

        if (pane.overlaySeries[key]) {
            pane.overlaySeries[key].applyOptions({ color, lineWidth, ...extraOpts });
            pane.overlaySeries[key].setData(data);
            return;
        }

        const s = pane.chart.addSeries(LightweightCharts.LineSeries, {
            color,
            lineWidth,
            priceLineVisible: false,
            lastValueVisible: true,
            crosshairMarkerVisible: false,
            ...extraOpts
        });
        s.setData(data);
        pane.overlaySeries[key] = s;
    }

    function renderIchimoku(pane, cfg, indKey = 'ichimoku') {
        const data = Indicators.ichimoku(pane.candles, cfg.tenkan, cfg.kijun, cfg.spanB);
        renderLineSeries(pane, seriesKey(indKey, 'ichiConversion'), data.conversion, cfg.conversionColor, 1.5);
        renderLineSeries(pane, seriesKey(indKey, 'ichiBase'), data.base, cfg.baseColor, 1.5);
        renderLineSeries(pane, seriesKey(indKey, 'ichiSpanA'), data.spanA, cfg.cloudColor, 1, { lineStyle: 2 });
        renderLineSeries(pane, seriesKey(indKey, 'ichiSpanB'), data.spanB, cfg.cloudColor, 1, { lineStyle: 2 });
    }

    function renderVWAP(pane, cfg, indKey = 'vwap') {
        if (!pane || !pane.chart || !pane.candles || pane.candles.length === 0) return;
        const vwapData = Indicators.vwap(pane.candles);
        if (!vwapData || vwapData.length === 0) return;

        // Partition by dayKey into daily segments so no connecting lines across midnight
        const segments = [];
        let curSeg = null;
        for (const pt of vwapData) {
            if (!curSeg || curSeg.dayKey !== pt.dayKey) {
                curSeg = { dayKey: pt.dayKey, points: [] };
                segments.push(curSeg);
            }
            curSeg.points.push({ time: pt.time, value: pt.value });
        }

        pane._vwapPool = pane._vwapPool || {};
        pane._vwapPool[indKey] = pane._vwapPool[indKey] || [];
        const pool = pane._vwapPool[indKey];

        while (pool.length < segments.length) {
            const s = pane.chart.addSeries(LightweightCharts.LineSeries, {
                lineWidth: cfg.width || 2,
                priceLineVisible: false,
                crosshairMarkerVisible: false
            });
            pool.push(s);
        }

        segments.forEach((seg, idx) => {
            const isLast = (idx === segments.length - 1);
            const s = pool[idx];
            s.applyOptions({
                color: cfg.color || IND_COLORS.vwap,
                lineWidth: cfg.width || 2,
                lastValueVisible: isLast,
                title: isLast ? 'VWAP' : '',
                visible: true
            });
            s.setData(seg.points);
        });

        for (let i = segments.length; i < pool.length; i++) {
            pool[i].applyOptions({ visible: false, lastValueVisible: false });
            pool[i].setData([]);
        }

        const k = seriesKey(indKey);
        if (pane.overlaySeries && pane.overlaySeries[k]) {
            try { pane.chart.removeSeries(pane.overlaySeries[k]); } catch (e) { }
            delete pane.overlaySeries[k];
        }
    }

    function renderSupertrend(pane, cfg, indKey = 'supertrend') {
        const data = Indicators.supertrend(pane.candles, cfg.period, cfg.multiplier);
        if (!data || !data.line || data.line.length === 0) return;

        // Partition by direction into contiguous segments to prevent diagonal connecting lines across flips
        const segments = [];
        let curSeg = null;
        for (let i = 0; i < data.line.length; i++) {
            const pt = data.line[i];
            const dir = (data.direction[i] && data.direction[i].value != null) ? data.direction[i].value : 1;
            if (!curSeg || curSeg.direction !== dir) {
                curSeg = { direction: dir, points: [] };
                segments.push(curSeg);
            }
            curSeg.points.push({ time: pt.time, value: pt.value });
        }

        pane._supertrendPool = pane._supertrendPool || {};
        pane._supertrendPool[indKey] = pane._supertrendPool[indKey] || [];
        const pool = pane._supertrendPool[indKey];

        while (pool.length < segments.length) {
            const s = pane.chart.addSeries(LightweightCharts.LineSeries, {
                lineWidth: cfg.width || 2,
                priceLineVisible: false,
                crosshairMarkerVisible: false
            });
            pool.push(s);
        }

        segments.forEach((seg, idx) => {
            const isLast = (idx === segments.length - 1);
            const isBull = (seg.direction === 1);
            const s = pool[idx];
            s.applyOptions({
                color: isBull ? '#089981' : '#F23645',
                lineWidth: cfg.width || 2,
                lastValueVisible: isLast,
                title: isLast ? (isBull ? 'ST Bull' : 'ST Bear') : '',
                visible: true
            });
            s.setData(seg.points);
        });

        for (let i = segments.length; i < pool.length; i++) {
            pool[i].applyOptions({ visible: false, lastValueVisible: false });
            pool[i].setData([]);
        }

        const k = seriesKey(indKey);
        if (pane.overlaySeries && pane.overlaySeries[k]) {
            try { pane.chart.removeSeries(pane.overlaySeries[k]); } catch (e) { }
            delete pane.overlaySeries[k];
        }
    }

    function renderAiRenko(pane, cfg, indKey = 'ai_renko') {
        if (!pane || !pane.chart || !pane.candles || pane.candles.length === 0) return;
        const res = Indicators.drDevendraAiRenko(pane.candles, cfg);
        if (!res || !res.stLine || res.stLine.length === 0) return;

        // Partition stLine into contiguous single-direction segments (clean line breaks on flips)
        const segments = [];
        let curSeg = null;
        for (const pt of res.stLine) {
            if (!curSeg || curSeg.direction !== pt.direction) {
                curSeg = { direction: pt.direction, points: [] };
                segments.push(curSeg);
            }
            curSeg.points.push({ time: pt.time, value: pt.value });
        }

        // Persistent series pool to prevent diagonal cross-lines and canvas recreation / flickering
        pane._aiRenkoPool = pane._aiRenkoPool || [];

        // Ensure pool has sufficient line series
        while (pane._aiRenkoPool.length < segments.length) {
            const s = pane.chart.addSeries(LightweightCharts.LineSeries, {
                lineWidth: cfg.width || 2,
                priceLineVisible: false,
                crosshairMarkerVisible: false
            });
            pane._aiRenkoPool.push(s);
        }

        // Update active segment series
        segments.forEach((seg, idx) => {
            const isLast = (idx === segments.length - 1);
            const isBull = (seg.direction === 1);
            const color = isBull ? '#089981' : '#F23645';
            const title = isLast ? (isBull ? 'AI ST Bull' : 'AI ST Bear') : '';
            const s = pane._aiRenkoPool[idx];

            s.applyOptions({
                color: color,
                lineWidth: cfg.width || 2,
                lastValueVisible: isLast,
                title: title,
                visible: true
            });
            s.setData(seg.points);
        });

        // Hide any unused series in the pool
        for (let i = segments.length; i < pane._aiRenkoPool.length; i++) {
            pane._aiRenkoPool[i].applyOptions({ visible: false, lastValueVisible: false });
            pane._aiRenkoPool[i].setData([]);
        }

        // Clean up legacy two-series overlay keys if present
        ['bull', 'bear'].forEach(suffix => {
            const k = seriesKey(indKey, suffix);
            if (pane.overlaySeries && pane.overlaySeries[k]) {
                try { pane.chart.removeSeries(pane.overlaySeries[k]); } catch (e) { }
                delete pane.overlaySeries[k];
            }
        });

        // 3. Optional Synthetic Renko Close Line
        const closeKey = seriesKey(indKey, 'close');
        if (cfg.showRenkoClose && res.renkoCloseLine && res.renkoCloseLine.length > 0) {
            renderLineSeries(pane, closeKey, res.renkoCloseLine, '#878b94', 1, {
                lineStyle: 2,
                priceLineVisible: false,
                lastValueVisible: false,
                title: 'Syn Renko'
            });
        } else if (pane.overlaySeries[closeKey]) {
            try { pane.chart.removeSeries(pane.overlaySeries[closeKey]); } catch (e) { }
            delete pane.overlaySeries[closeKey];
        }

        // 4. Render Markers (BULL, BEAR, and filtered ×) on confirmed bars
        if (pane.series) {
            try {
                const existing = (pane._customMarkers || []).filter(m => !m._isAiRenko);
                (res.markers || []).forEach(m => { m._isAiRenko = true; });
                const merged = [...existing, ...(res.markers || [])].sort((a, b) => a.time - b.time);
                pane.series.setMarkers(merged);
                pane._aiRenkoMarkers = res.markers;
            } catch (e) {
                console.warn('Error setting AI Renko markers:', e);
            }
        }

        // 5. Floating Status HUD Panel (removed per user request)
        updateAiRenkoHUD(pane, null);
    }

    function clearAiRenko(pane) {
        if (!pane) return;
        if (pane._aiRenkoPool) {
            pane._aiRenkoPool.forEach(s => {
                try { pane.chart.removeSeries(s); } catch (e) { }
            });
            pane._aiRenkoPool = [];
        }
        if (pane._aiRenkoSeriesList) {
            pane._aiRenkoSeriesList.forEach(s => {
                try { pane.chart.removeSeries(s); } catch (e) { }
            });
            pane._aiRenkoSeriesList = null;
        }

        ['bull', 'bear', 'close'].forEach(suffix => {
            const k = seriesKey('ai_renko', suffix);
            if (pane.overlaySeries && pane.overlaySeries[k]) {
                try { pane.chart.removeSeries(pane.overlaySeries[k]); } catch (e) { }
                delete pane.overlaySeries[k];
            }
        });

        if (pane.series && pane._aiRenkoMarkers) {
            try {
                const remaining = (pane._customMarkers || []).filter(m => !m._isAiRenko);
                pane.series.setMarkers(remaining);
            } catch (e) { }
            pane._aiRenkoMarkers = null;
        }

        updateAiRenkoHUD(pane, null);
    }

    function updateAiRenkoHUD(pane, status = null) {
        if (!pane || !pane.element) return;
        const mount = pane.element.querySelector('.chart-mount');
        if (!mount) return;
        const hud = mount.querySelector('.ai-renko-hud');
        if (hud) hud.remove();
    }

    function setGuideLine(seriesMap, chart, key, firstTime, lastTime, guide) {
        if (!seriesMap[key]) {
            seriesMap[key] = chart.addSeries(LightweightCharts.LineSeries, {
                color: guide.color,
                lineWidth: 1,
                lineStyle: 2,
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false
            });
        } else {
            seriesMap[key].applyOptions({ color: guide.color });
        }
        seriesMap[key].setData([{ time: firstTime, value: guide.value }, { time: lastTime, value: guide.value }]);
    }

    function renderOscillatorLine(pane, indKey, label, data, color, precision = 2, guides = []) {
        if (!data || data.length === 0) return;
        const alignedData = alignDataToCandles(data, pane.candles);
        const osc = ensureOscChart(pane, indKey, label);
        if (!osc) return;
        osc.alignedData = alignedData;

        if (!osc.series.mainLine) {
            osc.series.mainLine = osc.chart.addSeries(LightweightCharts.LineSeries, {
                color,
                lineWidth: 1.5,
                priceLineVisible: false,
                lastValueVisible: true,
                crosshairMarkerVisible: false,
                priceFormat: { type: 'price', precision, minMove: Math.pow(10, -precision) }
            });
        } else {
            osc.series.mainLine.applyOptions({ color });
        }
        osc.series.mainLine.setData(alignedData);

        const tFirst = pane.candles[0].time;
        const tLast = pane.candles[pane.candles.length - 1].time;
        guides.forEach((guide, idx) => setGuideLine(osc.series, osc.chart, `guide${idx}`, tFirst, tLast, guide));

        syncTimeScales(pane);
    }

    // ── RSI sub-pane ──
    function renderOscillatorRSI(pane, cfg = getIndicatorConfig(pane, 'rsi14'), indKey = 'rsi14') {
        const period = cfg.period || cfg.length || 14;
        const rsiData = Indicators.rsi(pane.candles, period);
        if (!rsiData || rsiData.length === 0) return;

        const alignedRsiData = alignDataToCandles(rsiData, pane.candles);
        const osc = ensureOscChart(pane, indKey, `RSI (${period})`);
        if (!osc) return;

        // Store aligned data for crosshair O(1) lookups
        osc.alignedData = alignedRsiData;

        if (!osc.series.rsiLine) {
            const rsiSeries = osc.chart.addSeries(LightweightCharts.LineSeries, {
                color: cfg.color, lineWidth: 1.5,
                priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false,
                priceFormat: { type: 'price', precision: 1, minMove: 0.1 }
            });
            const obLine = osc.chart.addSeries(LightweightCharts.LineSeries, {
                color: 'rgba(255,23,68,0.4)', lineWidth: 1, lineStyle: 2,
                priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false
            });
            const osLine = osc.chart.addSeries(LightweightCharts.LineSeries, {
                color: 'rgba(0,230,118,0.4)', lineWidth: 1, lineStyle: 2,
                priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false
            });
            osc.series.rsiLine = rsiSeries;
            osc.series.rsiOB = obLine;
            osc.series.rsiOS = osLine;
        } else {
            osc.series.rsiLine.applyOptions({ color: cfg.color });
        }

        osc.series.rsiLine.setData(alignedRsiData);

        const tFirst = pane.candles[0].time;
        const tLast = pane.candles[pane.candles.length - 1].time;
        osc.series.rsiOB.setData([{ time: tFirst, value: cfg.overbought }, { time: tLast, value: cfg.overbought }]);
        osc.series.rsiOS.setData([{ time: tFirst, value: cfg.oversold }, { time: tLast, value: cfg.oversold }]);

        syncTimeScales(pane);
    }

    // ── MACD sub-pane ──
    function renderOscillatorMACD(pane, cfg = getIndicatorConfig(pane, 'macd'), indKey = 'macd') {
        const macdData = Indicators.macd(pane.candles, cfg.fast, cfg.slow, cfg.signal);
        if (!macdData) return;

        const alignedMacdLine = alignDataToCandles(macdData.macdLine, pane.candles);
        const alignedSignalLine = alignDataToCandles(macdData.signalLine, pane.candles);
        const alignedHistogram = alignDataToCandles(macdData.histogram, pane.candles);

        const osc = ensureOscChart(pane, indKey, `MACD (${cfg.fast},${cfg.slow},${cfg.signal})`);
        if (!osc) return;

        // Store aligned data for crosshair O(1) lookups
        osc.alignedLineData = alignedMacdLine;

        if (!osc.series.macdLine) {
            const histSeries = osc.chart.addSeries(LightweightCharts.HistogramSeries, {
                priceLineVisible: false, lastValueVisible: false,
                priceFormat: { type: 'price', precision: 5, minMove: 0.00001 }
            });
            const macdLine = osc.chart.addSeries(LightweightCharts.LineSeries, {
                color: cfg.macdColor, lineWidth: 1.5,
                priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
                priceFormat: { type: 'price', precision: 5, minMove: 0.00001 }
            });
            const sigLine = osc.chart.addSeries(LightweightCharts.LineSeries, {
                color: cfg.signalColor, lineWidth: 1, lineStyle: 1,
                priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
                priceFormat: { type: 'price', precision: 5, minMove: 0.00001 }
            });
            osc.series.macdHist = histSeries;
            osc.series.macdLine = macdLine;
            osc.series.macdSig = sigLine;
        } else {
            osc.series.macdLine.applyOptions({ color: cfg.macdColor });
            osc.series.macdSig.applyOptions({ color: cfg.signalColor });
        }

        osc.series.macdHist.setData(alignedHistogram);
        osc.series.macdLine.setData(alignedMacdLine);
        osc.series.macdSig.setData(alignedSignalLine);

        syncTimeScales(pane);
    }

    function renderOscillatorStochastic(pane, cfg, indKey = 'stoch') {
        const data = Indicators.stochastic(pane.candles, cfg.k, cfg.d, cfg.smooth);
        if (!data.kLine || data.kLine.length === 0) return;
        const osc = ensureOscChart(pane, indKey, `Stoch (${cfg.k},${cfg.d},${cfg.smooth})`);
        if (!osc) return;

        const kLine = alignDataToCandles(data.kLine, pane.candles);
        const dLine = alignDataToCandles(data.dLine, pane.candles);
        osc.alignedData = kLine;

        if (!osc.series.kLine) {
            osc.series.kLine = osc.chart.addSeries(LightweightCharts.LineSeries, {
                color: cfg.kColor, lineWidth: 1.5,
                priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false,
                priceFormat: { type: 'price', precision: 1, minMove: 0.1 }
            });
            osc.series.dLine = osc.chart.addSeries(LightweightCharts.LineSeries, {
                color: cfg.dColor, lineWidth: 1,
                priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false,
                priceFormat: { type: 'price', precision: 1, minMove: 0.1 }
            });
        } else {
            osc.series.kLine.applyOptions({ color: cfg.kColor });
            osc.series.dLine.applyOptions({ color: cfg.dColor });
        }
        osc.series.kLine.setData(kLine);
        osc.series.dLine.setData(dLine);

        const tFirst = pane.candles[0].time;
        const tLast = pane.candles[pane.candles.length - 1].time;
        setGuideLine(osc.series, osc.chart, 'upperGuide', tFirst, tLast, { value: 80, color: 'rgba(255,23,68,0.35)' });
        setGuideLine(osc.series, osc.chart, 'lowerGuide', tFirst, tLast, { value: 20, color: 'rgba(0,230,118,0.35)' });
        syncTimeScales(pane);
    }

    function renderOscillatorADX(pane, cfg, indKey = 'adx') {
        const data = Indicators.adx(pane.candles, cfg.period);
        if (!data.adxLine || data.adxLine.length === 0) return;
        const osc = ensureOscChart(pane, indKey, `ADX (${cfg.period})`);
        if (!osc) return;

        const adxLine = alignDataToCandles(data.adxLine, pane.candles);
        const plusDI = alignDataToCandles(data.plusDI, pane.candles);
        const minusDI = alignDataToCandles(data.minusDI, pane.candles);
        osc.alignedData = adxLine;

        if (!osc.series.adxLine) {
            osc.series.adxLine = osc.chart.addSeries(LightweightCharts.LineSeries, { color: cfg.adxColor, lineWidth: 1.5, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false });
            osc.series.plusDI = osc.chart.addSeries(LightweightCharts.LineSeries, { color: cfg.plusColor, lineWidth: 1, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false });
            osc.series.minusDI = osc.chart.addSeries(LightweightCharts.LineSeries, { color: cfg.minusColor, lineWidth: 1, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false });
        } else {
            osc.series.adxLine.applyOptions({ color: cfg.adxColor });
            osc.series.plusDI.applyOptions({ color: cfg.plusColor });
            osc.series.minusDI.applyOptions({ color: cfg.minusColor });
        }

        osc.series.adxLine.setData(adxLine);
        osc.series.plusDI.setData(plusDI);
        osc.series.minusDI.setData(minusDI);
        syncTimeScales(pane);
    }

    // ── Volume sub-pane ──
    function renderOscillatorVolume(pane, indKey = 'volume') {
        const volData = Indicators.volume(pane.candles);
        if (!volData || volData.length === 0) return;

        const alignedVolData = alignDataToCandles(volData, pane.candles);
        const osc = ensureOscChart(pane, indKey, 'Volume');
        if (!osc) return;

        // Store aligned data for crosshair O(1) lookups
        osc.alignedData = alignedVolData;

        if (!osc.series.volBars) {
            const volSeries = osc.chart.addSeries(LightweightCharts.HistogramSeries, {
                priceLineVisible: false, lastValueVisible: false
            });
            osc.series.volBars = volSeries;
        }

        osc.series.volBars.setData(alignedVolData);
        syncTimeScales(pane);
    }

    // ── Ensure oscillator sub-chart exists ──
    function ensureOscChart(pane, indKey, label) {
        const container = pane.oscillatorsContainer;
        if (!container) return null;

        container.classList.remove('hidden');

        if (!pane.oscillators[indKey]) {
            const subpaneEl = document.createElement('div');
            subpaneEl.className = 'oscillator-subpane';
            applyOscillatorPanelHeight(pane, indKey, subpaneEl, pane.oscillatorSizes?.[indKey] || OSCILLATOR_PANEL_DEFAULT_HEIGHT);
            container.appendChild(subpaneEl);

            const resizeHandle = document.createElement('div');
            resizeHandle.className = 'oscillator-resize-handle';
            resizeHandle.title = 'Drag to resize panel';
            subpaneEl.appendChild(resizeHandle);

            const lbl = document.createElement('div');
            lbl.className = 'oscillator-label';
            lbl.dataset.indicatorKey = indKey;
            lbl.classList.toggle('is-hidden', !isIndicatorVisible(pane, indKey));
            const labelName = document.createElement('span');
            labelName.className = 'indicator-legend-name';
            labelName.textContent = getIndicatorLegendLabel(pane, indKey);
            lbl.appendChild(labelName);

            const actions = document.createElement('span');
            actions.className = 'indicator-legend-actions';

            const hideBtn = document.createElement('button');
            hideBtn.type = 'button';
            hideBtn.className = 'indicator-action-btn indicator-hide-btn';
            hideBtn.title = isIndicatorVisible(pane, indKey) ? 'Hide indicator' : 'Show indicator';
            hideBtn.setAttribute('aria-label', `Hide ${labelName.textContent}`);
            hideBtn.textContent = isIndicatorVisible(pane, indKey) ? '👁' : '⊘';
            hideBtn.addEventListener('click', event => {
                event.stopPropagation();
                toggleIndicatorVisibility(pane, indKey);
            });

            const settingsBtn = document.createElement('button');
            settingsBtn.type = 'button';
            settingsBtn.className = 'indicator-action-btn indicator-settings-btn';
            settingsBtn.title = 'Indicator settings';
            settingsBtn.setAttribute('aria-label', `${labelName.textContent} settings`);
            settingsBtn.textContent = '⚙';
            settingsBtn.addEventListener('click', event => {
                event.stopPropagation();
                openIndicatorSettings(pane.id, indKey);
            });

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'indicator-action-btn indicator-remove-btn';
            removeBtn.title = 'Remove indicator';
            removeBtn.setAttribute('aria-label', `Remove ${labelName.textContent}`);
            removeBtn.textContent = '✕';
            removeBtn.addEventListener('click', event => {
                event.stopPropagation();
                setIndicatorActive(pane, indKey, false);
                renderIndicatorLibrary();
            });

            actions.appendChild(hideBtn);
            actions.appendChild(settingsBtn);
            actions.appendChild(removeBtn);
            lbl.appendChild(actions);
            subpaneEl.appendChild(lbl);

            const oscMountEl = document.createElement('div');
            oscMountEl.style.cssText = 'position:absolute;inset:0;';
            subpaneEl.appendChild(oscMountEl);

            const chart = LightweightCharts.createChart(oscMountEl, {
                layout: {
                    background: { type: 'solid', color: '#FFFFFF' },
                    textColor: '#475569',
                    fontFamily: 'Inter, sans-serif',
                    fontSize: 10
                },
                grid: {
                    vertLines: { color: '#F1F5F9' },
                    horzLines: { color: '#F1F5F9' }
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: { color: '#94A3B8', width: 1, style: LightweightCharts.LineStyle.Solid },
                    horzLine: { color: '#94A3B8', width: 1, style: LightweightCharts.LineStyle.Solid }
                },
                rightPriceScale: { borderColor: '#E2E8F0', visible: true, scaleMargins: { top: 0.1, bottom: 0.1 }, minimumWidth: 80 },
                timeScale: { borderColor: '#E2E8F0', visible: true, timeVisible: true, secondsVisible: false }
            });

            const resizeObserver = new ResizeObserver(entries => {
                if (pane.isDisposed || !STATE.panes[pane.id] || !chart) return;
                for (const entry of entries) {
                    const { width, height } = entry.contentRect;
                    if (width > 0 && height > 0) {
                        try { chart.resize(width, height); } catch (e) { }
                    }
                }
            });
            resizeObserver.observe(subpaneEl);

            pane.oscillators[indKey] = {
                chart,
                series: {},
                subpaneEl,
                resizeHandle,
                resizeObserver
            };

            wireOscillatorPanelResize(pane, indKey, subpaneEl, resizeHandle);

            // Initial resize
            const rect = subpaneEl.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                try { chart.resize(rect.width, rect.height); } catch (e) { }
            }
        } else {
            const lbl = pane.oscillators[indKey].subpaneEl?.querySelector('.oscillator-label');
            const labelName = lbl?.querySelector('.indicator-legend-name');
            if (labelName) labelName.textContent = getIndicatorLegendLabel(pane, indKey);
            if (lbl) lbl.classList.toggle('is-hidden', !isIndicatorVisible(pane, indKey));
        }

        return pane.oscillators[indKey];
    }

    function applyOscillatorPanelHeight(pane, indKey, subpaneEl, height) {
        const paneHeight = pane.element?.clientHeight || 360;
        const maxHeight = Math.max(OSCILLATOR_PANEL_MIN_HEIGHT, Math.floor(paneHeight * 0.72));
        const nextHeight = Math.max(OSCILLATOR_PANEL_MIN_HEIGHT, Math.min(Math.round(height), maxHeight));
        subpaneEl.style.height = `${nextHeight}px`;
        subpaneEl.style.flexBasis = `${nextHeight}px`;
        if (pane.oscillatorSizes) pane.oscillatorSizes[indKey] = nextHeight;
        return nextHeight;
    }

    function saveOscillatorPanelSizes(pane) {
        SafeStorage.setItem(`ag_pane_oscillator_sizes_${pane.id}`, JSON.stringify(pane.oscillatorSizes || {}));
    }

    function wireOscillatorPanelResize(pane, indKey, subpaneEl, handle) {
        if (!handle) return;

        handle.addEventListener('mousedown', event => {
            event.preventDefault();
            event.stopPropagation();

            const startY = event.clientY;
            const startHeight = subpaneEl.getBoundingClientRect().height;
            document.body.classList.add('is-resizing-panel');
            subpaneEl.classList.add('is-resizing');

            const onMove = moveEvent => {
                const delta = moveEvent.clientY - startY;
                const nextHeight = applyOscillatorPanelHeight(pane, indKey, subpaneEl, startHeight - delta);
                const osc = pane.oscillators[indKey];
                if (osc?.chart) {
                    const rect = subpaneEl.getBoundingClientRect();
                    if (rect.width > 0 && nextHeight > 0) osc.chart.resize(rect.width, nextHeight);
                }
                handleResize();
            };

            const onUp = () => {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                document.body.classList.remove('is-resizing-panel');
                subpaneEl.classList.remove('is-resizing');
                saveOscillatorPanelSizes(pane);
                handleResize();
            };

            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    }

    function clearOscillator(pane, indKey) {
        if (!pane) return;
        if (indKey == null) {
            if (pane.oscillators) {
                Object.keys(pane.oscillators).forEach(k => clearOscillator(pane, k));
            }
            return;
        }

        const osc = pane.oscillators?.[indKey];
        if (osc) {
            if (osc.resizeObserver) {
                try { osc.resizeObserver.disconnect(); } catch (e) { }
            }
            try { osc.chart.remove(); } catch (e) { }
            if (osc.subpaneEl && osc.subpaneEl.parentNode) {
                osc.subpaneEl.parentNode.removeChild(osc.subpaneEl);
            }
            delete pane.oscillators[indKey];
        }

        // Hide container if no oscillators are left
        if (pane.oscillators && Object.keys(pane.oscillators).length === 0 && pane.oscillatorsContainer) {
            pane.oscillatorsContainer.classList.add('hidden');
        }
        updateActiveIndicatorLegend(pane);
        syncCrosshairs(pane);
        handleResize();
    }

    let _backfillTimeout = null;
    function wireHistoryBackfill(pane) {
        if (!pane || pane._historyBackfillSynced) return;
        pane._historyBackfillSynced = true;

        pane.chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
            if (pane.isDisposed || !STATE.panes[pane.id] || !pane.chart) return;
            if (pane.timeframe && pane.timeframe.toLowerCase() === 'renko') return;
            if (!range || pane._isSyncing || pane._isRestoringBackfillRange || pane.isBackfilling || !pane.hasMoreHistory) return;
            if (range.from <= HISTORY_BACKFILL_EDGE_BARS) {
                if (pane._backfillTimeout) clearTimeout(pane._backfillTimeout);
                if (_backfillTimeout) clearTimeout(_backfillTimeout);
                pane._backfillTimeout = setTimeout(() => {
                    loadOlderCandles(pane);
                }, 200);
            }
        });
    }

    function loadOlderCandles(pane) {
        if (!pane || pane.isDisposed || !STATE.panes[pane.id] || !pane.chart) return;
        if (pane.timeframe && pane.timeframe.toLowerCase() === 'renko') return;
        if (pane.isBackfilling || !pane.hasMoreHistory) return;
        if (!pane.candles || pane.candles.length === 0) return;
        if (pane.candles.length >= MAX_CANDLES_IN_MEMORY) {
            pane.hasMoreHistory = false;
            return;
        }

        const firstTime = pane.candles[0].time;
        if (firstTime == null) return;

        pane.isBackfilling = true;
        const previousCount = pane.candles.length;

        fetch(buildHistoricalUrl(pane, HISTORY_BACKFILL_LIMIT, firstTime))
            .then(r => r.json())
            .then(data => {
                if (pane.isDisposed || !STATE.panes[pane.id] || !pane.chart) return;
                if (!Array.isArray(data) || data.length === 0) {
                    pane.hasMoreHistory = false;
                    return;
                }

                const olderCandles = data.filter(c => c && c.time < firstTime);
                if (olderCandles.length === 0) {
                    pane.hasMoreHistory = false;
                    return;
                }

                // Capture current visible range right before applying new data
                let currentRange = null;
                try {
                    currentRange = pane.chart.timeScale().getVisibleLogicalRange();
                } catch (e) { }

                pane.candles = mergeCandles(pane.candles, olderCandles);
                const addedCount = pane.candles.length - previousCount;
                if (addedCount <= 0) {
                    pane.hasMoreHistory = false;
                    return;
                }

                rebuildTimeIndexMap(pane);
                try {
                    pane.series.setData(pane.candles);
                } catch (e) { }
                pane.lastCandle = pane.candles[pane.candles.length - 1];
                updateActiveIndicators(pane);
                syncTimeScales(pane);

                if (currentRange && !pane.isDisposed && pane.chart) {
                    const restoredRange = {
                        from: currentRange.from + addedCount,
                        to: currentRange.to + addedCount
                    };
                    pane._isRestoringBackfillRange = true;
                    try {
                        pane.chart.timeScale().setVisibleLogicalRange(restoredRange);
                    } catch (e) { }
                    if (pane.oscillators) {
                        Object.values(pane.oscillators).forEach(osc => {
                            if (osc.chart) {
                                try { osc.chart.timeScale().setVisibleLogicalRange(restoredRange); } catch (e) { }
                            }
                        });
                    }
                    requestAnimationFrame(() => {
                        pane._isRestoringBackfillRange = false;
                    });
                }
            })
            .catch(err => {
                if (!pane.isDisposed) {
                    console.warn(`Pane #${pane.id} backfill failed:`, err);
                }
                pane._isRestoringBackfillRange = false;
            })
            .finally(() => {
                setTimeout(() => {
                    if (pane) pane.isBackfilling = false;
                }, 150);
            });
    }

    // Sync main + osc time scales (loose coupling — just keep range in sync)
    function syncTimeScales(pane) {
        if (!pane._mainChartSynced) {
            pane._mainChartSynced = true;
            pane.chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
                if (!range || pane._isSyncing) return;
                pane._isSyncing = true;
                Object.values(pane.oscillators).forEach(osc => {
                    if (osc.chart) osc.chart.timeScale().setVisibleLogicalRange(range);
                });
                pane._isSyncing = false;
            });
        }

        Object.values(pane.oscillators).forEach(osc => {
            if (osc.chart && !osc._synced) {
                osc._synced = true;
                osc.chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
                    if (!range || pane._isSyncing) return;
                    pane._isSyncing = true;
                    pane.chart.timeScale().setVisibleLogicalRange(range);
                    Object.values(pane.oscillators).forEach(otherOsc => {
                        if (otherOsc.chart && otherOsc !== osc) {
                            otherOsc.chart.timeScale().setVisibleLogicalRange(range);
                        }
                    });
                    pane._isSyncing = false;
                });
            }
        });

        // Immediate sync for new oscillators
        const currentRange = pane.chart.timeScale().getVisibleLogicalRange();
        if (currentRange) {
            Object.values(pane.oscillators).forEach(osc => {
                if (osc.chart) osc.chart.timeScale().setVisibleLogicalRange(currentRange);
            });
        }

        // Wire or refresh crosshair sync
        syncCrosshairs(pane);
    }

    // ── High-Performance Crosshair Synchronization ──
    function getPrimaryOscillatorSeries(osc) {
        return osc.series.rsiLine || osc.series.macdLine || osc.series.mainLine ||
            osc.series.kLine || osc.series.adxLine || osc.series.volBars;
    }

    function syncCrosshairs(pane) {
        // Collect all charts to sync
        const sources = [
            { chart: pane.chart, series: pane.series, id: 'main' }
        ];

        Object.entries(pane.oscillators).forEach(([key, osc]) => {
            if (osc.chart) {
                const series = getPrimaryOscillatorSeries(osc);
                if (series) {
                    sources.push({ chart: osc.chart, series: series, id: key, osc: osc });
                }
            }
        });

        sources.forEach(source => {
            if (source.chart && !source._crosshairSynced) {
                source._crosshairSynced = true;
                source.chart.subscribeCrosshairMove(param => {
                    if (pane._isCrosshairSyncing) return;
                    pane._isCrosshairSyncing = true;

                    const time = param.time;
                    const hasPosition = param.point && time;

                    // Dynamically compile targets to support clean live additions/removals without closures issues
                    const targets = [];
                    Object.entries(pane.oscillators).forEach(([key, osc]) => {
                        if (osc.chart && osc.chart !== source.chart) {
                            const series = getPrimaryOscillatorSeries(osc);
                            if (series) {
                                targets.push({ chart: osc.chart, series: series, id: key, osc: osc });
                            }
                        }
                    });
                    if (pane.chart !== source.chart) {
                        targets.push({ chart: pane.chart, series: pane.series, id: 'main' });
                    }

                    targets.forEach(target => {
                        if (!hasPosition) {
                            target.chart.clearCrosshairPosition();
                        } else {
                            let price = 0;
                            if (pane.timeToIndexMap && pane.timeToIndexMap.has(time)) {
                                const idx = pane.timeToIndexMap.get(time);
                                if (target.id === 'main') {
                                    price = pane.candles[idx] ? pane.candles[idx].close : 0;
                                } else if (getIndicatorBaseKey(target.id) === 'macd') {
                                    const item = target.osc.alignedLineData && target.osc.alignedLineData[idx];
                                    price = (item && item.value !== undefined) ? item.value : 0;
                                } else {
                                    const item = target.osc.alignedData && target.osc.alignedData[idx];
                                    price = (item && item.value !== undefined) ? item.value : 0;
                                }
                            }
                            target.chart.setCrosshairPosition(price, time, target.series);
                        }
                    });

                    pane._isCrosshairSyncing = false;
                });
            }
        });
    }

    // ── Recalculate indicators dynamically when live feed ticks occur ──
    function updateActiveIndicators(pane, isBarClose = false) {
        if (!pane.candles || pane.candles.length === 0) return;
        Object.keys(pane.activeIndicators).forEach(indKey => {
            if (pane.activeIndicators[indKey]) {
                const base = getIndicatorBaseKey(indKey);
                // Structural overlays (SMC, etc.) calculate swing structures across confirmed bars
                // Skip re-rendering on 1.5s intrabar ticks to eliminate UI overhead and canvas flickering
                if (!isBarClose && base === 'smc') return;
                renderIndicator(pane, indKey);
            }
        });
    }

    // ── SMC Render & Settings Support (High-Performance Canvas Overlay) ──
    function getOrCreateSMCCanvas(pane) {
        const mount = pane.element ? pane.element.querySelector('.chart-mount') : null;
        if (!mount) return null;
        let canvas = mount.querySelector('.smc-canvas-overlay');
        if (!canvas) {
            canvas = document.createElement('canvas');
            canvas.className = 'smc-canvas-overlay';
            canvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:2;';
            mount.appendChild(canvas);
        }
        const dpr = window.devicePixelRatio || 1;
        const w = mount.clientWidth;
        const h = mount.clientHeight;
        if (w > 0 && h > 0) {
            const pw = Math.floor(w * dpr);
            const ph = Math.floor(h * dpr);
            if (canvas.width !== pw || canvas.height !== ph) {
                canvas.width = pw;
                canvas.height = ph;
            }
        }
        return canvas;
    }

    function wireSMCOverlayEvents(pane) {
        if (pane._smcOverlayWired) return;
        pane._smcOverlayWired = true;

        // 1. Redraw on time scale visible range change (horizontal drag / zoom)
        pane.chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
            if (pane._cachedSMCData && pane.activeIndicators && pane.activeIndicators.smc) {
                drawSMCCanvas(pane);
            }
        });

        // 2. Redraw on mouse drag / wheel inside chart mount (vertical price scale interaction)
        const mount = pane.element ? pane.element.querySelector('.chart-mount') : null;
        if (mount) {
            let isMouseDown = false;
            mount.addEventListener('mousedown', () => { isMouseDown = true; }, { passive: true });
            window.addEventListener('mouseup', () => { isMouseDown = false; }, { passive: true });
            mount.addEventListener('mousemove', () => {
                if (isMouseDown && pane._cachedSMCData && pane.activeIndicators && pane.activeIndicators.smc) {
                    drawSMCCanvas(pane);
                }
            }, { passive: true });
            mount.addEventListener('wheel', () => {
                if (pane._cachedSMCData && pane.activeIndicators && pane.activeIndicators.smc) {
                    requestAnimationFrame(() => drawSMCCanvas(pane));
                }
            }, { passive: true });
        }
    }

    function drawSMCCanvas(pane) {
        const smcData = pane._cachedSMCData;
        if (!smcData || !pane.series || !pane.chart) return;

        const canvas = getOrCreateSMCCanvas(pane);
        if (!canvas || canvas.width === 0 || canvas.height === 0) return;

        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        ctx.save();
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.scale(dpr, dpr);

        const timeScale = pane.chart.timeScale();
        const series = pane.series;
        const candles = pane.candles;
        if (!candles || candles.length === 0) {
            ctx.restore();
            return;
        }

        const totalCandles = candles.length;
        const lastIndex = totalCandles - 1;
        const cfg = smcData.settings || {};
        const isMono = cfg.style === 'Monochrome';

        const greenColor = isMono ? '#b2b5be' : '#089981';
        const redColor = isMono ? '#5d606b' : '#F23645';
        const canvasW = canvas.width / dpr;
        const canvasH = canvas.height / dpr;

        // Clip drawing strictly to chart plot area (excluding right price scale & bottom time scale)
        const priceScaleWidth = (typeof pane.chart.priceScale('right')?.width === 'function')
            ? pane.chart.priceScale('right').width()
            : 75;
        const timeScaleHeight = (typeof timeScale.height === 'function')
            ? timeScale.height()
            : 26;
        const plotWidth = Math.max(0, canvasW - priceScaleWidth);
        const plotHeight = Math.max(0, canvasH - timeScaleHeight);

        ctx.beginPath();
        ctx.rect(0, 0, plotWidth, plotHeight);
        ctx.clip();

        // Coordinate helpers using logical index for 1:1 pixel accuracy
        const getXFromIndex = (idx) => {
            if (idx == null || isNaN(idx)) return null;
            try {
                return timeScale.logicalToCoordinate(idx);
            } catch (e) {
                return null;
            }
        };

        const getX = (t, defaultIdx = null) => {
            if (defaultIdx != null && !isNaN(defaultIdx)) {
                const x = getXFromIndex(defaultIdx);
                if (x !== null) return x;
            }
            if (t != null && pane.timeToIndexMap && pane.timeToIndexMap.has(t)) {
                return getXFromIndex(pane.timeToIndexMap.get(t));
            }
            if (t != null) {
                try {
                    const x = timeScale.timeToCoordinate(t);
                    if (x !== null) return x;
                } catch (e) { }
            }
            return null;
        };

        const getY = (p) => {
            if (p == null || isNaN(p)) return null;
            try {
                return series.priceToCoordinate(p);
            } catch (e) {
                return null;
            }
        };

        // 1. Order Blocks (OBs) — Clean shaded rectangles anchored from origin pivot candle
        if (cfg.showSwingOrderBlocks && smcData.swingOBs) {
            smcData.swingOBs.forEach(ob => {
                const startIdx = (ob.index != null)
                    ? ob.index
                    : (pane.timeToIndexMap ? pane.timeToIndexMap.get(ob.time) : null);
                if (startIdx == null) return;
                const endIdx = (ob.mitigatedIndex != null) ? ob.mitigatedIndex : lastIndex;
                const x1 = getXFromIndex(startIdx);
                const x2 = getXFromIndex(endIdx);
                const y1 = getY(ob.high);
                const y2 = getY(ob.low);
                if (x1 !== null && x2 !== null && y1 !== null && y2 !== null) {
                    const rx = Math.min(x1, x2);
                    const rw = Math.max(2, Math.abs(x2 - x1));
                    const ry = Math.min(y1, y2);
                    const rh = Math.max(1, Math.abs(y2 - y1));
                    ctx.fillStyle = ob.bias === 1
                        ? (isMono ? 'rgba(178, 181, 190, 0.25)' : (cfg.swingBullishOrderBlockColor || 'rgba(24, 72, 204, 0.25)'))
                        : (isMono ? 'rgba(93, 96, 107, 0.25)' : (cfg.swingBearishOrderBlockColor || 'rgba(178, 40, 51, 0.25)'));
                    ctx.fillRect(rx, ry, rw, rh);
                    ctx.strokeStyle = ob.bias === 1
                        ? (isMono ? '#b2b5be' : '#1848cc')
                        : (isMono ? '#5d606b' : '#b22833');
                    ctx.lineWidth = 1;
                    ctx.strokeRect(rx, ry, rw, rh);
                }
            });
        }

        if (cfg.showInternalOrderBlocks && smcData.internalOBs) {
            smcData.internalOBs.forEach(ob => {
                const startIdx = (ob.index != null)
                    ? ob.index
                    : (pane.timeToIndexMap ? pane.timeToIndexMap.get(ob.time) : null);
                if (startIdx == null) return;
                const endIdx = (ob.mitigatedIndex != null) ? ob.mitigatedIndex : lastIndex;
                const x1 = getXFromIndex(startIdx);
                const x2 = getXFromIndex(endIdx);
                const y1 = getY(ob.high);
                const y2 = getY(ob.low);
                if (x1 !== null && x2 !== null && y1 !== null && y2 !== null) {
                    const rx = Math.min(x1, x2);
                    const rw = Math.max(2, Math.abs(x2 - x1));
                    const ry = Math.min(y1, y2);
                    const rh = Math.max(1, Math.abs(y2 - y1));
                    ctx.fillStyle = ob.bias === 1
                        ? (isMono ? 'rgba(178, 181, 190, 0.18)' : (cfg.internalBullishOrderBlockColor || 'rgba(49, 121, 245, 0.18)'))
                        : (isMono ? 'rgba(93, 96, 107, 0.18)' : (cfg.internalBearishOrderBlockColor || 'rgba(247, 124, 128, 0.18)'));
                    ctx.fillRect(rx, ry, rw, rh);
                    ctx.strokeStyle = ob.bias === 1
                        ? (isMono ? '#b2b5be' : '#3179f5')
                        : (isMono ? '#5d606b' : '#f77c80');
                    ctx.lineWidth = 1;
                    ctx.strokeRect(rx, ry, rw, rh);
                }
            });
        }

        // 2. Fair Value Gaps (FVG) — Clean bounded gap rectangles anchored to their exact 3-bar formation
        if (cfg.showFairValueGaps && smcData.fvgs) {
            const extendBars = typeof cfg.fairValueGapsExtend === 'number' ? Math.max(1, cfg.fairValueGapsExtend) : 1;
            smcData.fvgs.forEach(fvg => {
                const startIdx = (fvg.index != null)
                    ? fvg.index
                    : (pane.timeToIndexMap ? pane.timeToIndexMap.get(fvg.time) : null);
                if (startIdx == null) return;
                const endIdx = (fvg.mitigatedIndex != null)
                    ? Math.min(startIdx + extendBars, fvg.mitigatedIndex)
                    : Math.min(lastIndex, startIdx + extendBars);
                const x1 = getXFromIndex(startIdx);
                const x2 = getXFromIndex(endIdx);
                const y1 = getY(fvg.top);
                const y2 = getY(fvg.bottom);
                if (x1 !== null && x2 !== null && y1 !== null && y2 !== null) {
                    const rx = Math.min(x1, x2);
                    const rw = Math.max(2, Math.abs(x2 - x1));
                    const ry = Math.min(y1, y2);
                    const rh = Math.max(1, Math.abs(y2 - y1));
                    ctx.fillStyle = fvg.bias === 1
                        ? (isMono ? 'rgba(178, 181, 190, 0.2)' : (cfg.fairValueGapsBullColor || 'rgba(8, 153, 129, 0.2)'))
                        : (isMono ? 'rgba(93, 96, 107, 0.2)' : (cfg.fairValueGapsBearColor || 'rgba(242, 54, 69, 0.2)'));
                    ctx.fillRect(rx, ry, rw, rh);
                    ctx.strokeStyle = fvg.bias === 1
                        ? (isMono ? '#b2b5be' : '#089981')
                        : (isMono ? '#5d606b' : '#F23645');
                    ctx.lineWidth = 1;
                    ctx.strokeRect(rx, ry, rw, rh);
                }
            });
        }

        // 3. Breakout lines (BOS / CHoCH)
        if (smcData.breakouts) {
            smcData.breakouts.forEach(b => {
                const x1 = getX(b.start.time, b.start.index);
                const x2 = getX(b.end.time, b.end.index);
                const y = getY(b.start.price);
                if (x1 !== null && x2 !== null && y !== null) {
                    const color = b.direction === 'bull' ? greenColor : redColor;
                    ctx.strokeStyle = color;
                    ctx.lineWidth = b.type === 'swing' ? 1.5 : 1;
                    ctx.setLineDash(b.type === 'swing' ? [] : [4, 4]);
                    ctx.beginPath();
                    ctx.moveTo(x1, y);
                    ctx.lineTo(x2, y);
                    ctx.stroke();
                }
            });
            ctx.setLineDash([]);
        }

        // 4. Equal Highs / Lows (EQH / EQL)
        if (cfg.showEqualHighsLows && smcData.equalHighsLows) {
            smcData.equalHighsLows.forEach(eq => {
                const x1 = getX(eq.start.time, eq.start.index);
                const x2 = getX(eq.end.time, eq.end.index);
                const y = getY(eq.start.price);
                if (x1 !== null && x2 !== null && y !== null) {
                    const color = eq.type === 'EQH' ? redColor : greenColor;
                    ctx.strokeStyle = color;
                    ctx.lineWidth = 1;
                    ctx.setLineDash([2, 3]);
                    ctx.beginPath();
                    ctx.moveTo(x1, y);
                    ctx.lineTo(x2, y);
                    ctx.stroke();
                }
            });
            ctx.setLineDash([]);
        }

        // 5. Premium & Discount Zones
        if (cfg.showPremiumDiscountZones && smcData.trailing) {
            const t = smcData.trailing;
            const startIdx = (t.barIndex != null)
                ? t.barIndex
                : (pane.timeToIndexMap ? pane.timeToIndexMap.get(t.barTime) : null);
            const range = t.top - t.bottom;
            if (startIdx != null && range > 0) {
                const x1 = getXFromIndex(startIdx);
                const x2 = getXFromIndex(lastIndex);
                if (x1 !== null && x2 !== null) {
                    const rx = Math.min(x1, x2);
                    const rw = Math.max(2, Math.abs(x2 - x1));
                    // Premium Zone box
                    const premTop = t.top;
                    const premBot = t.top - 0.05 * range;
                    const yPrem1 = getY(premTop);
                    const yPrem2 = getY(premBot);
                    if (yPrem1 !== null && yPrem2 !== null) {
                        ctx.fillStyle = isMono ? 'rgba(93, 96, 107, 0.22)' : 'rgba(242, 54, 69, 0.22)';
                        ctx.fillRect(rx, Math.min(yPrem1, yPrem2), rw, Math.abs(yPrem2 - yPrem1));
                    }
                    // Discount Zone box
                    const discTop = t.bottom + 0.05 * range;
                    const discBot = t.bottom;
                    const yDisc1 = getY(discTop);
                    const yDisc2 = getY(discBot);
                    if (yDisc1 !== null && yDisc2 !== null) {
                        ctx.fillStyle = isMono ? 'rgba(178, 181, 190, 0.22)' : 'rgba(8, 153, 129, 0.22)';
                        ctx.fillRect(rx, Math.min(yDisc1, yDisc2), rw, Math.abs(yDisc2 - yDisc1));
                    }
                }
            }
        }

        ctx.restore();
    }

    function clearSMC(pane) {
        if (pane.smcPriceLines && pane.smcPriceLines.length > 0) {
            pane.smcPriceLines.forEach(pl => {
                try { pane.series.removePriceLine(pl); } catch (e) { }
            });
            pane.smcPriceLines = [];
        }
        if (pane.smcSeries && pane.smcSeries.length > 0) {
            pane.smcSeries.forEach(s => {
                try { pane.chart.removeSeries(s); } catch (e) { }
            });
            pane.smcSeries = [];
        }
        if (pane.markersPlugin) {
            try { pane.markersPlugin.setMarkers([]); } catch (e) { }
        } else if (pane.series?.setMarkers) {
            try { pane.series.setMarkers([]); } catch (e) { }
        }
        const mount = pane.element ? pane.element.querySelector('.chart-mount') : null;
        const canvas = mount ? mount.querySelector('.smc-canvas-overlay') : null;
        if (canvas) {
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
        pane._cachedSMCData = null;
    }

    function renderSMC(pane) {
        if (!pane.candles || pane.candles.length === 0) return;

        clearSMC(pane);

        const smcData = Indicators.smc(pane.candles, pane.smcSettings || {});
        if (!smcData) return;

        pane._cachedSMCData = smcData;
        const cfg = smcData.settings;
        const candles = pane.candles;
        const lastTime = candles[candles.length - 1].time;
        const isMono = cfg.style === 'Monochrome';

        const greenColor = isMono ? '#b2b5be' : '#089981';
        const redColor = isMono ? '#5d606b' : '#F23645';

        pane.smcSeries = pane.smcSeries || [];
        pane.smcPriceLines = pane.smcPriceLines || [];
        const allMarkers = [];

        // 1. Swing Highs/Lows Markers (HH, HL, LH, LL)
        if (cfg.showSwings && smcData.swingHighsLows) {
            smcData.swingHighsLows.forEach(shl => {
                allMarkers.push({
                    time: shl.time,
                    position: shl.position,
                    color: isMono ? (shl.position === 'aboveBar' ? '#5d606b' : '#b2b5be') : shl.color,
                    shape: shl.position === 'aboveBar' ? 'arrowDown' : 'arrowUp',
                    text: shl.label,
                    size: 1
                });
            });
        }

        // 2. Breakouts (BOS / CHoCH) confirmation markers
        if (smcData.breakouts) {
            smcData.breakouts.forEach(b => {
                const color = b.direction === 'bull' ? greenColor : redColor;
                allMarkers.push({
                    time: b.end.time,
                    position: b.direction === 'bull' ? 'belowBar' : 'aboveBar',
                    color: color,
                    shape: b.direction === 'bull' ? 'arrowUp' : 'arrowDown',
                    text: b.tag,
                    size: 1
                });
            });
        }

        // 3. Equal Highs/Lows (EQH / EQL) confirmation markers
        if (cfg.showEqualHighsLows && smcData.equalHighsLows) {
            smcData.equalHighsLows.forEach(eq => {
                const color = eq.type === 'EQH' ? redColor : greenColor;
                allMarkers.push({
                    time: eq.end.time,
                    position: eq.type === 'EQH' ? 'aboveBar' : 'belowBar',
                    color: color,
                    shape: 'circle',
                    text: eq.type,
                    size: 1
                });
            });
        }

        // 4. Equilibrium Price Line
        if (cfg.showPremiumDiscountZones && smcData.trailing) {
            const t = smcData.trailing;
            if (t.top !== null && t.bottom !== null) {
                const eqLevel = (t.top + t.bottom) / 2;
                const plEq = pane.series.createPriceLine({
                    price: eqLevel,
                    color: '#878b94',
                    lineWidth: 1,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: 'EQ'
                });
                pane.smcPriceLines.push(plEq);
            }
        }

        // 5. Strong & Weak High/Low Trailing Price Lines
        if (cfg.showHighLowSwings && smcData.trailing) {
            const t = smcData.trailing;
            const trend = t.trendBias !== undefined ? t.trendBias : t.swingTrendBias;
            if (t.top !== null) {
                const labelHigh = trend === -1 ? 'Strong High' : 'Weak High';
                const plHigh = pane.series.createPriceLine({
                    price: t.top,
                    color: redColor,
                    lineWidth: 1,
                    lineStyle: LightweightCharts.LineStyle.Dotted,
                    axisLabelVisible: true,
                    title: labelHigh
                });
                pane.smcPriceLines.push(plHigh);
            }
            if (t.bottom !== null) {
                const labelLow = trend === 1 ? 'Strong Low' : 'Weak Low';
                const plLow = pane.series.createPriceLine({
                    price: t.bottom,
                    color: greenColor,
                    lineWidth: 1,
                    lineStyle: LightweightCharts.LineStyle.Dotted,
                    axisLabelVisible: true,
                    title: labelLow
                });
                pane.smcPriceLines.push(plLow);
            }
        }

        // 6. Multi-Timeframe Highs & Lows (PDH/PDL, PWH/PWL, PMH/PML)
        if (smcData.mtfLevels) {
            const getLineStyle = (s) => {
                if (s === 'Dashed') return LightweightCharts.LineStyle.Dashed;
                if (s === 'Dotted') return LightweightCharts.LineStyle.Dotted;
                return LightweightCharts.LineStyle.Solid;
            };
            const mtfColor = isMono ? '#878b94' : '#2157f3';
            if (cfg.showDailyLevels && smcData.mtfLevels.daily) {
                const d = smcData.mtfLevels.daily;
                const style = getLineStyle(cfg.dailyLevelsStyle);
                const plPdh = pane.series.createPriceLine({ price: d.pdh, color: mtfColor, lineWidth: 1, lineStyle: style, axisLabelVisible: true, title: 'PDH' });
                const plPdl = pane.series.createPriceLine({ price: d.pdl, color: mtfColor, lineWidth: 1, lineStyle: style, axisLabelVisible: true, title: 'PDL' });
                pane.smcPriceLines.push(plPdh, plPdl);
            }
            if (cfg.showWeeklyLevels && smcData.mtfLevels.weekly) {
                const w = smcData.mtfLevels.weekly;
                const style = getLineStyle(cfg.weeklyLevelsStyle);
                const plPwh = pane.series.createPriceLine({ price: w.pwh, color: mtfColor, lineWidth: 1, lineStyle: style, axisLabelVisible: true, title: 'PWH' });
                const plPwl = pane.series.createPriceLine({ price: w.pwl, color: mtfColor, lineWidth: 1, lineStyle: style, axisLabelVisible: true, title: 'PWL' });
                pane.smcPriceLines.push(plPwh, plPwl);
            }
            if (cfg.showMonthlyLevels && smcData.mtfLevels.monthly) {
                const m = smcData.mtfLevels.monthly;
                const style = getLineStyle(cfg.monthlyLevelsStyle);
                const plPmh = pane.series.createPriceLine({ price: m.pmh, color: mtfColor, lineWidth: 1, lineStyle: style, axisLabelVisible: true, title: 'PMH' });
                const plPml = pane.series.createPriceLine({ price: m.pml, color: mtfColor, lineWidth: 1, lineStyle: style, axisLabelVisible: true, title: 'PML' });
                pane.smcPriceLines.push(plPmh, plPml);
            }
        }

        // Set all sorted markers on the main candlestick series
        if (allMarkers.length > 0) {
            allMarkers.sort((a, b) => {
                const timeA = typeof a.time === 'object' && a.time !== null ? (new Date(Date.UTC(a.time.year, a.time.month - 1, a.time.day)).getTime()) : (typeof a.time === 'string' ? new Date(a.time).getTime() : a.time);
                const timeB = typeof b.time === 'object' && b.time !== null ? (new Date(Date.UTC(b.time.year, b.time.month - 1, b.time.day)).getTime()) : (typeof b.time === 'string' ? new Date(b.time).getTime() : b.time);
                return timeA - timeB;
            });
            if (LightweightCharts.createSeriesMarkers) {
                if (!pane.markersPlugin) {
                    pane.markersPlugin = LightweightCharts.createSeriesMarkers(pane.series, allMarkers);
                } else {
                    pane.markersPlugin.setMarkers(allMarkers);
                }
            } else {
                pane.series.setMarkers(allMarkers);
            }
        }

        // Render SMC Canvas overlay (Order Blocks, FVGs, Breakouts, Zones)
        getOrCreateSMCCanvas(pane);
        wireSMCOverlayEvents(pane);
        drawSMCCanvas(pane);
    }

    function renderCategoryTabs() {
        const tabsContainer = document.getElementById('indicator-category-tabs');
        if (!tabsContainer) return;

        tabsContainer.innerHTML = CATALOG_CATEGORIES.map(cat => {
            const catLower = cat.toLowerCase();
            const isActive = (activeCategoryFilter === catLower);
            return `<button type="button" class="indicator-cat-tab ${isActive ? 'active' : ''}" data-category="${catLower}" style="padding: 4px 10px; font-size: 11px; font-weight: 600; border-radius: 12px; border: 1px solid ${isActive ? '#2563EB' : 'var(--border-color, #E2E8F0)'}; background: ${isActive ? '#2563EB' : '#FFFFFF'}; color: ${isActive ? '#FFFFFF' : 'var(--text-primary, #334155)'}; cursor: pointer; white-space: nowrap; transition: all 0.15s ease;">${cat}</button>`;
        }).join('');

        tabsContainer.querySelectorAll('.indicator-cat-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                activeCategoryFilter = btn.dataset.category;
                renderCategoryTabs();
                renderIndicatorLibrary();
            });
        });
    }

    function initIndicatorLibraryEvents() {
        const modal = document.getElementById('indicator-library-dialog');
        const backdrop = document.getElementById('modal-backdrop');
        const closeBtn = document.getElementById('indicator-library-close');
        const search = document.getElementById('indicator-library-search');
        const applyBtn = document.getElementById('indicator-library-apply');
        const removeBtn = document.getElementById('indicator-library-remove');
        const visibilityBtn = document.getElementById('indicator-library-visibility');

        const closeModal = () => {
            if (modal) modal.classList.add('hidden');
            if (backdrop && document.getElementById('adjustments-modal')?.classList.contains('hidden') && document.getElementById('smc-settings-dialog')?.classList.contains('hidden')) {
                backdrop.classList.add('hidden');
            }
        };

        if (closeBtn) closeBtn.addEventListener('click', closeModal);
        if (search) search.addEventListener('input', renderIndicatorLibrary);

        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal && !modal.classList.contains('hidden')) {
                closeModal();
            }
        });

        if (backdrop) {
            backdrop.addEventListener('click', () => {
                if (modal && !modal.classList.contains('hidden')) {
                    closeModal();
                }
            });
        }

        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                const pane = STATE.panes[activeIndicatorLibraryPaneId];
                if (!pane || !selectedIndicatorKey) return;
                if (editingIndicatorKey && pane.activeIndicators?.[editingIndicatorKey]) {
                    setIndicatorConfig(pane, editingIndicatorKey, readIndicatorSettingsForm(editingIndicatorKey));
                    setIndicatorActive(pane, editingIndicatorKey, true);
                } else {
                    addIndicatorFromLibrary(pane, getIndicatorBaseKey(selectedIndicatorKey));
                }
                renderIndicatorLibrary();
                closeModal();
            });
        }

        if (removeBtn) {
            removeBtn.addEventListener('click', () => {
                const pane = STATE.panes[activeIndicatorLibraryPaneId];
                if (!pane || !editingIndicatorKey) return;
                setIndicatorActive(pane, editingIndicatorKey, false);
                editingIndicatorKey = null;
                renderIndicatorLibrary();
            });
        }

        if (visibilityBtn) {
            visibilityBtn.addEventListener('click', () => {
                const pane = STATE.panes[activeIndicatorLibraryPaneId];
                if (!pane || !editingIndicatorKey) return;
                toggleIndicatorVisibility(pane, editingIndicatorKey);
                renderIndicatorLibrary();
            });
        }
    }

    function openIndicatorLibrary(paneId) {
        const pane = STATE.panes[paneId];
        if (!pane) return;

        activeIndicatorLibraryPaneId = paneId;
        editingIndicatorKey = null;
        const activeKey = Object.keys(pane.activeIndicators || {}).find(key => pane.activeIndicators[key]);
        selectedIndicatorKey = selectedIndicatorKey && getIndicatorDef(selectedIndicatorKey)
            ? selectedIndicatorKey
            : (activeKey || 'sma20');

        const paneLabel = document.getElementById('indicator-library-pane-label');
        if (paneLabel) paneLabel.textContent = `Pane #${paneId} · ${pane.symbol} · ${pane.timeframe}`;

        const search = document.getElementById('indicator-library-search');
        if (search) search.value = '';

        const modal = document.getElementById('indicator-library-dialog');
        const backdrop = document.getElementById('modal-backdrop');
        if (modal) modal.classList.remove('hidden');
        if (backdrop) backdrop.classList.remove('hidden');

        renderCategoryTabs();
        renderIndicatorLibrary();
    }

    function renderIndicatorLibrary() {
        const pane = STATE.panes[activeIndicatorLibraryPaneId];
        const list = document.getElementById('indicator-library-list');
        if (!pane || !list) return;

        const query = (document.getElementById('indicator-library-search')?.value || '').trim().toLowerCase();
        const entries = Object.entries(INDICATOR_DEFS).filter(([key, def]) => {
            // Category filter
            if (activeCategoryFilter && activeCategoryFilter !== 'all') {
                const defCat = (def.category || '').toLowerCase();
                if (defCat !== activeCategoryFilter) return false;
            }
            // Search query across ID, key, name, short, category, description
            if (query) {
                const searchStr = `${key} ${def.id || ''} ${def.name || ''} ${def.short || ''} ${def.category || ''} ${def.description || ''}`.toLowerCase();
                if (!searchStr.includes(query)) return false;
            }
            return true;
        });

        if (entries.length === 0) {
            list.innerHTML = `<div style="padding: 24px 16px; text-align: center; color: var(--text-muted, #94A3B8); font-size: 12px;">No indicators found matching "${escapeHtml(query)}"</div>`;
            renderIndicatorSettingsPanel(pane);
            return;
        }

        const categories = [];
        entries.forEach(([key, def]) => {
            const catName = def.category || 'General';
            let group = categories.find(item => item.name === catName);
            if (!group) {
                group = { name: catName, items: [] };
                categories.push(group);
            }
            group.items.push([key, def]);
        });

        list.innerHTML = categories.map((group, groupIdx) => `
            <div class="indicator-category-label ${groupIdx === 0 ? 'first-cat' : ''}">${group.name}</div>
            ${group.items.map(([key, def]) => {
            const activeKeys = getActiveIndicatorKeysByBase(pane, key);
            const activeCount = activeKeys.length;
            const isSelected = key === getIndicatorBaseKey(selectedIndicatorKey);
            return `
                <button type="button" class="indicator-list-item ${isSelected ? 'selected' : ''}" data-indicator-key="${key}" title="${def.description || def.name}">
                    <div class="indicator-list-main">
                        <span class="indicator-list-name">${def.name}</span>
                        <div class="indicator-list-meta">
                            <span class="indicator-code-tag">${def.short || key.toUpperCase()}</span>
                            <span>${def.kind === 'overlay' ? 'On chart' : 'Separate panel'}</span>
                        </div>
                    </div>
                    ${activeCount > 0 ? `<span class="indicator-active-badge">${activeCount} active</span>` : ''}
                </button>
            `;
        }).join('')}
        `).join('');

        list.querySelectorAll('.indicator-list-item').forEach(btn => {
            btn.addEventListener('click', () => {
                const baseKey = btn.dataset.indicatorKey;
                selectedIndicatorKey = baseKey;
                const activeKeys = getActiveIndicatorKeysByBase(pane, baseKey);
                if (activeKeys.length > 0) {
                    editingIndicatorKey = activeKeys[0];
                } else {
                    editingIndicatorKey = null;
                }
                renderIndicatorLibrary();
            });
        });

        renderIndicatorSettingsPanel(pane);
    }

    function renderIndicatorSettingsPanel(pane) {
        const activeEditKey = editingIndicatorKey && pane.activeIndicators?.[editingIndicatorKey] ? editingIndicatorKey : null;
        const settingsKey = activeEditKey || selectedIndicatorKey;
        const baseKey = getIndicatorBaseKey(settingsKey);
        const def = getIndicatorDef(settingsKey);
        const fieldsEl = document.getElementById('indicator-settings-fields');
        const nameEl = document.getElementById('indicator-settings-name');
        const categoryEl = document.getElementById('indicator-settings-category');
        const descEl = document.getElementById('indicator-settings-desc');
        const removeBtn = document.getElementById('indicator-library-remove');
        const visibilityBtn = document.getElementById('indicator-library-visibility');
        const applyBtn = document.getElementById('indicator-library-apply');
        if (!def || !fieldsEl) return;

        const cfg = getIndicatorConfig(pane, settingsKey);
        const editingExisting = !!activeEditKey;
        if (nameEl) nameEl.textContent = editingExisting ? getIndicatorLegendLabel(pane, activeEditKey) : def.name;
        if (categoryEl) categoryEl.textContent = `${def.category} · ${def.kind === 'overlay' ? 'On Chart Overlay' : 'Oscillator Panel'}${editingExisting ? ' · (Active)' : ''}`;
        if (descEl) descEl.textContent = editingExisting
            ? 'Adjust parameters for this active indicator instance and click Apply Changes.'
            : (def.description || 'Set parameters and click Add to apply to chart.');
        if (removeBtn) removeBtn.disabled = !editingExisting;
        if (visibilityBtn) {
            if (editingExisting) {
                visibilityBtn.style.display = 'inline-block';
                const isVis = isIndicatorVisible(pane, activeEditKey);
                visibilityBtn.textContent = isVis ? '👁 Hide' : '⊘ Show';
                visibilityBtn.title = isVis ? 'Hide this indicator on chart' : 'Show this indicator on chart';
            } else {
                visibilityBtn.style.display = 'none';
            }
        }
        if (applyBtn) applyBtn.textContent = editingExisting ? 'Apply Changes' : `Add ${def.short || def.name}`;

        // Handle special singleton indicators like SMC
        if (baseKey === 'smc') {
            fieldsEl.innerHTML = `
                <div style="padding: 12px 0; display: flex; flex-direction: column; gap: 10px;">
                    <p class="indicator-list-meta" style="margin: 0; line-height: 1.5;">Smart Money Concepts [LuxAlgo] includes Real-Time Structure (BOS/CHoCH), Order Blocks, Equal Highs/Lows, Fair Value Gaps, MTF Levels, and Premium/Discount Zones.</p>
                    <button type="button" id="btn-open-full-smc-cfg" class="btn-primary" style="align-self: flex-start; height: 32px; font-size: 11.5px; padding: 0 14px; background: #2563EB;">Configure SMC Settings ⚙️</button>
                </div>
            `;
            const btnCfg = document.getElementById('btn-open-full-smc-cfg');
            if (btnCfg) {
                btnCfg.addEventListener('click', () => {
                    const modal = document.getElementById('indicator-library-dialog');
                    if (modal) modal.classList.add('hidden');
                    openSMCSettings(activeIndicatorLibraryPaneId);
                });
            }
            return;
        }

        // Check if indicator has params (backend metadata schema)
        if (def.params && Array.isArray(def.params) && def.params.length > 0) {
            fieldsEl.innerHTML = def.params.map(p => {
                const key = p.name;
                const label = p.name.charAt(0).toUpperCase() + p.name.slice(1).replace(/_/g, ' ');
                const val = cfg[key] ?? p.default ?? '';
                const type = p.type || 'float';

                if (type === 'bool') {
                    const isChecked = Boolean(val);
                    return `
                        <div class="indicator-field-row">
                            <label class="indicator-field-label" for="ind-field-${key}">${label}</label>
                            <input id="ind-field-${key}" type="checkbox" class="indicator-field-checkbox" data-field-key="${key}" data-param-type="bool" ${isChecked ? 'checked' : ''} style="width: 18px; height: 18px; accent-color: var(--brand-blue, #2563EB); cursor: pointer;">
                        </div>
                    `;
                }

                if (type === 'str' && (p.options || key === 'mamode')) {
                    const opts = p.options || ['sma', 'ema', 'wma', 'dema', 'tema', 'hma', 'rma'];
                    return `
                        <div class="indicator-field-row">
                            <label class="indicator-field-label" for="ind-field-${key}">${label}</label>
                            <select id="ind-field-${key}" class="indicator-field-input" data-field-key="${key}" data-param-type="select" style="text-align: left; padding: 0 8px; cursor: pointer;">
                                ${opts.map(opt => `<option value="${opt}" ${String(val).toLowerCase() === String(opt).toLowerCase() ? 'selected' : ''}>${opt.toUpperCase()}</option>`).join('')}
                            </select>
                        </div>
                    `;
                }

                if (type === 'int' || type === 'float') {
                    const step = p.step != null ? p.step : (type === 'int' ? 1 : 0.1);
                    const minAttr = p.min != null ? `min="${p.min}"` : '';
                    const maxAttr = p.max != null ? `max="${p.max}"` : '';
                    return `
                        <div class="indicator-field-row">
                            <label class="indicator-field-label" for="ind-field-${key}">${label}${p.min != null && p.max != null ? ` (${p.min}-${p.max})` : ''}</label>
                            <input id="ind-field-${key}" class="indicator-field-input" data-field-key="${key}" data-param-type="${type}" type="number" ${minAttr} ${maxAttr} step="${step}" value="${val}">
                        </div>
                    `;
                }

                // General string
                return `
                    <div class="indicator-field-row">
                        <label class="indicator-field-label" for="ind-field-${key}">${label}</label>
                        <input id="ind-field-${key}" class="indicator-field-input" data-field-key="${key}" data-param-type="str" type="text" value="${val}">
                    </div>
                `;
            }).join('');

            // Also add color / line width styling row if outputs or styling are present
            if (def.outputs && def.outputs.length > 0) {
                const primaryOutput = def.outputs[0];
                const colorVal = cfg.color || primaryOutput.color || '#2563EB';
                const widthVal = cfg.width || 2;
                const styleRows = `
                    <div class="indicator-field-row" style="margin-top: 6px; border-top: 1px dashed var(--border-color, #E2E8F0); padding-top: 8px;">
                        <label class="indicator-field-label" for="ind-field-color">Line Color</label>
                        <input id="ind-field-color" type="color" class="indicator-field-input" data-field-key="color" data-param-type="color" value="${colorVal}" style="width: 44px; height: 28px; padding: 2px; cursor: pointer;">
                    </div>
                    <div class="indicator-field-row">
                        <label class="indicator-field-label" for="ind-field-width">Line Width (1-5)</label>
                        <input id="ind-field-width" type="number" class="indicator-field-input" data-field-key="width" data-param-type="int" min="1" max="5" step="1" value="${widthVal}">
                    </div>
                `;
                fieldsEl.insertAdjacentHTML('beforeend', styleRows);
            }
            return;
        }

        // Fall back to legacy def.fields if present
        if (def.fields && Array.isArray(def.fields) && def.fields.length > 0) {
            fieldsEl.innerHTML = def.fields.map(field => {
                const [key, label, type, min, max, step] = field;
                const value = cfg[key] ?? def.defaults[key] ?? '';
                if (type === 'boolean') {
                    return `
                        <div class="indicator-field-row">
                            <label class="indicator-field-label" for="ind-field-${key}">${label}</label>
                            <input id="ind-field-${key}" type="checkbox" class="indicator-field-checkbox" data-field-key="${key}" data-param-type="bool" ${Boolean(value) ? 'checked' : ''} style="width: 18px; height: 18px; accent-color: var(--brand-blue, #2563EB); cursor: pointer;">
                        </div>
                    `;
                }
                const attrs = [
                    `data-field-key="${key}"`,
                    `data-param-type="${type}"`,
                    `type="${type}"`,
                    min != null ? `min="${min}"` : '',
                    max != null ? `max="${max}"` : '',
                    step != null ? `step="${step}"` : (type === 'number' ? 'step="1"' : ''),
                    `value="${value}"`
                ].filter(Boolean).join(' ');
                return `
                    <div class="indicator-field-row">
                        <label class="indicator-field-label" for="ind-field-${key}">${label}</label>
                        <input id="ind-field-${key}" class="indicator-field-input" ${attrs}>
                    </div>
                `;
            }).join('');
            return;
        }

        fieldsEl.innerHTML = '<p class="indicator-list-meta" style="padding: 12px 0;">This indicator does not require additional parameter configuration.</p>';
    }

    function readIndicatorSettingsForm(indKey) {
        const def = getIndicatorDef(indKey);
        const cfg = { ...(def?.defaults || {}) };
        document.querySelectorAll('#indicator-settings-fields [data-field-key]').forEach(input => {
            const key = input.dataset.fieldKey;
            const pType = input.dataset.paramType;
            if (input.type === 'checkbox' || pType === 'bool') {
                cfg[key] = input.checked;
            } else if (input.type === 'number' || pType === 'int' || pType === 'float' || pType === 'number') {
                const min = input.min !== '' ? parseFloat(input.min) : null;
                const max = input.max !== '' ? parseFloat(input.max) : null;
                let val = parseFloat(input.value);
                if (Number.isFinite(val)) {
                    if (min !== null && val < min) val = min;
                    if (max !== null && val > max) val = max;
                    if (pType === 'int') val = Math.round(val);
                    cfg[key] = val;
                }
            } else {
                cfg[key] = input.value;
            }
        });
        return cfg;
    }

    function openSMCSettings(paneId) {
        const pane = STATE.panes[paneId];
        if (!pane) return;
        activeSMCSettingsPaneId = paneId;

        const cfg = pane.smcSettings || {};

        const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
        const setCheck = (id, val) => { const el = document.getElementById(id); if (el) el.checked = !!val; };

        setVal('smc-cfg-mode', cfg.mode || 'Historical');
        setVal('smc-cfg-style', cfg.style || 'Colored');
        setCheck('smc-cfg-showTrend', cfg.showTrend);

        setCheck('smc-cfg-showStructure', cfg.showStructure !== false);
        setVal('smc-cfg-swingsLength', cfg.swingsLength !== undefined ? cfg.swingsLength : 50);
        setCheck('smc-cfg-showSwings', cfg.showSwings);
        setVal('smc-cfg-showSwingBull', cfg.showSwingBull || 'All');
        setVal('smc-cfg-showSwingBear', cfg.showSwingBear || 'All');
        setCheck('smc-cfg-showHighLowSwings', cfg.showHighLowSwings !== false);

        setCheck('smc-cfg-showInternals', cfg.showInternals !== false);
        setCheck('smc-cfg-internalFilterConfluence', cfg.internalFilterConfluence);
        setVal('smc-cfg-showInternalBull', cfg.showInternalBull || 'All');
        setVal('smc-cfg-showInternalBear', cfg.showInternalBear || 'All');

        setCheck('smc-cfg-showSwingOrderBlocks', cfg.showSwingOrderBlocks);
        setVal('smc-cfg-swingOrderBlocksSize', cfg.swingOrderBlocksSize !== undefined ? cfg.swingOrderBlocksSize : 5);
        setCheck('smc-cfg-showInternalOrderBlocks', cfg.showInternalOrderBlocks !== false);
        setVal('smc-cfg-internalOrderBlocksSize', cfg.internalOrderBlocksSize !== undefined ? cfg.internalOrderBlocksSize : 5);
        setVal('smc-cfg-orderBlockFilter', cfg.orderBlockFilter || 'Atr');
        setVal('smc-cfg-orderBlockMitigation', cfg.orderBlockMitigation || 'High/Low');

        setCheck('smc-cfg-showEqualHighsLows', cfg.showEqualHighsLows !== false);
        setVal('smc-cfg-equalHighsLowsLength', cfg.equalHighsLowsLength !== undefined ? cfg.equalHighsLowsLength : 3);
        setVal('smc-cfg-equalHighsLowsThreshold', cfg.equalHighsLowsThreshold !== undefined ? cfg.equalHighsLowsThreshold : 0.1);
        setCheck('smc-cfg-showFairValueGaps', cfg.showFairValueGaps);
        setCheck('smc-cfg-fairValueGapsThreshold', cfg.fairValueGapsThreshold !== false);
        setVal('smc-cfg-fairValueGapsExtend', cfg.fairValueGapsExtend !== undefined ? cfg.fairValueGapsExtend : 1);

        setCheck('smc-cfg-showPremiumDiscountZones', cfg.showPremiumDiscountZones);
        setCheck('smc-cfg-showDailyLevels', cfg.showDailyLevels);
        setCheck('smc-cfg-showWeeklyLevels', cfg.showWeeklyLevels);
        setCheck('smc-cfg-showMonthlyLevels', cfg.showMonthlyLevels);

        const modal = document.getElementById('smc-settings-dialog');
        const backdrop = document.getElementById('modal-backdrop');
        if (modal) modal.classList.remove('hidden');
        if (backdrop) backdrop.classList.remove('hidden');
    }

    function initSMCSettingsEvents() {
        const modal = document.getElementById('smc-settings-dialog');
        const backdrop = document.getElementById('modal-backdrop');
        const closeBtn = document.getElementById('smc-settings-close');
        const resetBtn = document.getElementById('smc-settings-reset');
        const saveBtn = document.getElementById('smc-settings-save');

        // Wire tabs inside SMC modal
        document.querySelectorAll('.smc-tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.smc-tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                document.querySelectorAll('.smc-tab-pane').forEach(p => p.classList.remove('active'));
                const target = document.getElementById(btn.dataset.tab);
                if (target) target.classList.add('active');
            });
        });

        const closeSMCModal = () => {
            if (modal) modal.classList.add('hidden');
            if (backdrop && document.getElementById('adjustments-modal')?.classList.contains('hidden') && document.getElementById('indicator-library-dialog')?.classList.contains('hidden')) {
                backdrop.classList.add('hidden');
            }
            activeSMCSettingsPaneId = null;
        };

        if (closeBtn) {
            closeBtn.addEventListener('click', closeSMCModal);
        }

        if (backdrop) {
            backdrop.addEventListener('click', () => {
                if (modal && !modal.classList.contains('hidden')) {
                    closeSMCModal();
                }
            });
        }

        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
                const setCheck = (id, val) => { const el = document.getElementById(id); if (el) el.checked = !!val; };

                setVal('smc-cfg-mode', 'Historical');
                setVal('smc-cfg-style', 'Colored');
                setCheck('smc-cfg-showTrend', false);

                setCheck('smc-cfg-showStructure', true);
                setVal('smc-cfg-swingsLength', 50);
                setCheck('smc-cfg-showSwings', false);
                setVal('smc-cfg-showSwingBull', 'All');
                setVal('smc-cfg-showSwingBear', 'All');
                setCheck('smc-cfg-showHighLowSwings', true);

                setCheck('smc-cfg-showInternals', true);
                setCheck('smc-cfg-internalFilterConfluence', false);
                setVal('smc-cfg-showInternalBull', 'All');
                setVal('smc-cfg-showInternalBear', 'All');

                setCheck('smc-cfg-showSwingOrderBlocks', false);
                setVal('smc-cfg-swingOrderBlocksSize', 5);
                setCheck('smc-cfg-showInternalOrderBlocks', true);
                setVal('smc-cfg-internalOrderBlocksSize', 5);
                setVal('smc-cfg-orderBlockFilter', 'Atr');
                setVal('smc-cfg-orderBlockMitigation', 'High/Low');

                setCheck('smc-cfg-showEqualHighsLows', true);
                setVal('smc-cfg-equalHighsLowsLength', 3);
                setVal('smc-cfg-equalHighsLowsThreshold', 0.1);

                setCheck('smc-cfg-showFairValueGaps', false);
                setCheck('smc-cfg-fairValueGapsThreshold', true);
                setVal('smc-cfg-fairValueGapsExtend', 1);

                setCheck('smc-cfg-showPremiumDiscountZones', false);
                setCheck('smc-cfg-showDailyLevels', false);
                setCheck('smc-cfg-showWeeklyLevels', false);
                setCheck('smc-cfg-showMonthlyLevels', false);
            });
        }

        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                if (activeSMCSettingsPaneId === null) return;
                const pane = STATE.panes[activeSMCSettingsPaneId];
                if (!pane) return;

                const getVal = (id, fallback) => document.getElementById(id)?.value ?? fallback;
                const getCheck = (id) => !!document.getElementById(id)?.checked;
                const getInt = (id, fallback) => parseInt(document.getElementById(id)?.value, 10) || fallback;
                const getFloat = (id, fallback) => parseFloat(document.getElementById(id)?.value) || fallback;

                const settings = {
                    mode: getVal('smc-cfg-mode', 'Historical'),
                    style: getVal('smc-cfg-style', 'Colored'),
                    showTrend: getCheck('smc-cfg-showTrend'),

                    showStructure: getCheck('smc-cfg-showStructure'),
                    swingsLength: getInt('smc-cfg-swingsLength', 50),
                    showSwings: getCheck('smc-cfg-showSwings'),
                    showSwingBull: getVal('smc-cfg-showSwingBull', 'All'),
                    showSwingBear: getVal('smc-cfg-showSwingBear', 'All'),
                    showHighLowSwings: getCheck('smc-cfg-showHighLowSwings'),

                    showInternals: getCheck('smc-cfg-showInternals'),
                    internalFilterConfluence: getCheck('smc-cfg-internalFilterConfluence'),
                    showInternalBull: getVal('smc-cfg-showInternalBull', 'All'),
                    showInternalBear: getVal('smc-cfg-showInternalBear', 'All'),

                    showSwingOrderBlocks: getCheck('smc-cfg-showSwingOrderBlocks'),
                    swingOrderBlocksSize: getInt('smc-cfg-swingOrderBlocksSize', 5),
                    showInternalOrderBlocks: getCheck('smc-cfg-showInternalOrderBlocks'),
                    internalOrderBlocksSize: getInt('smc-cfg-internalOrderBlocksSize', 5),
                    orderBlockFilter: getVal('smc-cfg-orderBlockFilter', 'Atr'),
                    orderBlockMitigation: getVal('smc-cfg-orderBlockMitigation', 'High/Low'),

                    showEqualHighsLows: getCheck('smc-cfg-showEqualHighsLows'),
                    equalHighsLowsLength: getInt('smc-cfg-equalHighsLowsLength', 3),
                    equalHighsLowsThreshold: getFloat('smc-cfg-equalHighsLowsThreshold', 0.1),

                    showFairValueGaps: getCheck('smc-cfg-showFairValueGaps'),
                    fairValueGapsThreshold: getCheck('smc-cfg-fairValueGapsThreshold'),
                    fairValueGapsExtend: getInt('smc-cfg-fairValueGapsExtend', 1),

                    showPremiumDiscountZones: getCheck('smc-cfg-showPremiumDiscountZones'),
                    showDailyLevels: getCheck('smc-cfg-showDailyLevels'),
                    showWeeklyLevels: getCheck('smc-cfg-showWeeklyLevels'),
                    showMonthlyLevels: getCheck('smc-cfg-showMonthlyLevels')
                };

                pane.smcSettings = settings;
                SafeStorage.setItem(`ag_pane_smc_settings_${activeSMCSettingsPaneId}`, JSON.stringify(settings));

                if (pane.activeIndicators['smc']) {
                    renderSMC(pane);
                }

                closeSMCModal();
            });
        }
    }

    // ══════════════════════════════════════════════
    //  DRAWING TOOLS
    // ══════════════════════════════════════════════
    function handleToolClick(paneId, tool, btn) {
        const pane = STATE.panes[paneId];
        if (!pane) return;

        if (tool === 'erase') {
            eraseLastDrawing(pane);
            return;
        }

        // Toggle tool
        if (pane.activeTool === tool) {
            pane.activeTool = null;
            pane.element.querySelector('.chart-mount').classList.remove('drawing-mode');
            pane.element.querySelectorAll('.tool-chip').forEach(b => b.classList.remove('active'));
        } else {
            pane.activeTool = tool;
            pane.element.querySelector('.chart-mount').classList.add('drawing-mode');
            pane.element.querySelectorAll('.tool-chip').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        }
    }

    // Tracks first click for two-point tools
    const _drawingState = {};

    function handleChartClick(evt, paneId) {
        const pane = STATE.panes[paneId];
        if (!pane || !pane.activeTool) return;

        const rect = evt.currentTarget.getBoundingClientRect();
        const x = evt.clientX - rect.left;
        const y = evt.clientY - rect.top;

        // LWC v5: coordinateToPrice lives on the SERIES, not the priceScale object
        let price = null;
        try {
            price = pane.series.coordinateToPrice(y);
        } catch (e) {
            console.warn('coordinateToPrice fallback:', e);
        }

        // coordinateToTime still lives on the timeScale — but may return null if outside range
        let time = null;
        try {
            time = pane.chart.timeScale().coordinateToTime(x);
        } catch (e) {
            console.warn('coordinateToTime fallback:', e);
        }

        // If time is null (click was outside candle range), snap to nearest edge
        if (time == null && pane.candles.length > 0) {
            const ts = pane.chart.timeScale();
            const log = ts.coordinateToLogical(x);
            if (log !== null) {
                const idx = Math.max(0, Math.min(Math.round(log), pane.candles.length - 1));
                time = pane.candles[idx].time;
            } else {
                time = x < rect.width / 2
                    ? pane.candles[0].time
                    : pane.candles[pane.candles.length - 1].time;
            }
        }

        if (price == null || time == null) {
            console.warn(`Pane #${paneId}: Could not resolve click coordinates (price=${price}, time=${time})`);
            return;
        }

        switch (pane.activeTool) {
            case 'hline': drawHorizontalLine(pane, price); break;
            case 'tline': drawTrendLine(pane, paneId, time, price); break;
            case 'rect': drawRectangle(pane, paneId, time, price); break;
        }
    }

    function drawHorizontalLine(pane, price) {
        if (price == null) return;
        const s = pane.chart.addSeries(LightweightCharts.LineSeries, {
            color: 'rgba(255, 214, 102, 0.75)',
            lineWidth: 1.5, lineStyle: LightweightCharts.LineStyle.Solid,
            priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false,
            priceFormat: { type: 'price', precision: 5, minMove: 0.00001 }
        });
        if (pane.candles.length > 0) {
            s.setData([
                { time: pane.candles[0].time, value: price },
                { time: pane.candles[pane.candles.length - 1].time, value: price }
            ]);
        }
        pane.drawings.push({ type: 'hline', series: s });
        console.log(`Pane #${pane.id}: H-Line drawn at ${price}`);
    }

    function drawTrendLine(pane, paneId, time, price) {
        const key = `tline_${paneId}`;
        if (!_drawingState[key]) {
            // First click — store anchor
            _drawingState[key] = { time, price };
            console.log(`Pane #${paneId}: Trend line — first point set.`);
        } else {
            const p1 = _drawingState[key];
            const p2 = { time, price };
            delete _drawingState[key];

            if (p1.time === p2.time) return;

            // Sort by time
            const sorted = [p1, p2].sort((a, b) => a.time - b.time);

            const s = pane.chart.addSeries(LightweightCharts.LineSeries, {
                color: 'rgba(176, 127, 255, 0.85)',
                lineWidth: 1.5, lineStyle: 0,
                priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false
            });
            s.setData([
                { time: sorted[0].time, value: sorted[0].price },
                { time: sorted[1].time, value: sorted[1].price }
            ]);
            pane.drawings.push({ type: 'tline', series: s });
            console.log(`Pane #${paneId}: Trend line drawn.`);
        }
    }

    function drawRectangle(pane, paneId, time, price) {
        const key = `rect_${paneId}`;
        if (!_drawingState[key]) {
            _drawingState[key] = { time, price };
            console.log(`Pane #${paneId}: Rectangle — first corner set.`);
        } else {
            const p1 = _drawingState[key];
            const p2 = { time, price };
            delete _drawingState[key];

            if (p1.time === p2.time) return;
            const sorted = [p1, p2].sort((a, b) => a.time - b.time);
            const high = Math.max(sorted[0].price, sorted[1].price);
            const low = Math.min(sorted[0].price, sorted[1].price);

            // Draw 4 sides of rectangle using LineSeries
            const color = 'rgba(0,230,118,0.5)';
            const draws = [];

            // Top line
            const top = pane.chart.addSeries(LightweightCharts.LineSeries, {
                color, lineWidth: 1, lineStyle: 0,
                priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false
            });
            top.setData([{ time: sorted[0].time, value: high }, { time: sorted[1].time, value: high }]);
            draws.push(top);

            // Bottom line
            const bot = pane.chart.addSeries(LightweightCharts.LineSeries, {
                color, lineWidth: 1, lineStyle: 0,
                priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false
            });
            bot.setData([{ time: sorted[0].time, value: low }, { time: sorted[1].time, value: low }]);
            draws.push(bot);

            // Left line
            const lft = pane.chart.addSeries(LightweightCharts.LineSeries, {
                color, lineWidth: 1, lineStyle: 0,
                priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false
            });
            lft.setData([{ time: sorted[0].time, value: low }, { time: sorted[0].time, value: high }]);
            draws.push(lft);

            // Right line
            const rgt = pane.chart.addSeries(LightweightCharts.LineSeries, {
                color, lineWidth: 1, lineStyle: 0,
                priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false
            });
            rgt.setData([{ time: sorted[1].time, value: low }, { time: sorted[1].time, value: high }]);
            draws.push(rgt);

            pane.drawings.push({ type: 'rect', series: draws });
            console.log(`Pane #${paneId}: Rectangle drawn.`);
        }
    }

    function eraseLastDrawing(pane) {
        const last = pane.drawings.pop();
        if (!last) return;

        const toRemove = Array.isArray(last.series) ? last.series : [last.series];
        toRemove.forEach(s => { try { pane.chart.removeSeries(s); } catch (e) { } });
        console.log(`Pane #${pane.id}: Erased last drawing.`);
    }

    // ══════════════════════════════════════════════
    //  LIVE FEEDS
    // ══════════════════════════════════════════════
    function wireLiveFeed(paneId) {
        const pane = STATE.panes[paneId];
        if (!pane) return;
        if (pane.source === 'hyperliquid') connectHyperliquidWS(pane);
        else startLivePolling(pane);
    }

    function connectHyperliquidWS(pane) {
        const wsUrl = 'wss://api.hyperliquid.xyz/ws';
        try {
            const ws = new WebSocket(wsUrl);
            pane.ws = ws;

            ws.onopen = () => {
                ws.send(JSON.stringify({
                    method: 'subscribe',
                    subscription: { type: 'candle', coin: pane.symbol, interval: pane.timeframe }
                }));
            };

            ws.onmessage = evt => {
                try {
                    const resp = JSON.parse(evt.data);
                    if (resp.channel === 'candle' && resp.data) {
                        const cd = resp.data;
                        if (cd.s.toUpperCase() !== pane.symbol) return;
                        const candle = {
                            time: Math.floor(cd.t / 1000),
                            open: parseFloat(cd.o), high: parseFloat(cd.h),
                            low: parseFloat(cd.l), close: parseFloat(cd.c),
                            volume: parseFloat(cd.v) || (pane.lastCandle && pane.lastCandle.volume ? pane.lastCandle.volume + 1 : 1)
                        };
                        const newPrice = candle.close;
                        if (newPrice !== pane.lastPrice) {
                            triggerTickerFlash(pane, newPrice, pane.lastPrice);
                            pane.lastPrice = newPrice;
                        }
                        pane.series.update(candle);
                        pane.lastCandle = candle;
                        // Update last candle in candles array
                        if (pane.candles.length > 0) {
                            const last = pane.candles[pane.candles.length - 1];
                            if (last.time === candle.time) {
                                pane.candles[pane.candles.length - 1] = candle;
                            } else if (candle.time > last.time) {
                                pane.candles.push(candle);
                                if (pane.timeToIndexMap) {
                                    pane.timeToIndexMap.set(candle.time, pane.candles.length - 1);
                                }
                            }
                            updateActiveIndicators(pane);
                        }
                    }
                } catch (e) { console.error('WS parse error:', e); }
            };

            ws.onerror = () => { };
            ws.onclose = () => {
                if (STATE.panes[pane.id] && STATE.panes[pane.id].source === 'hyperliquid' && STATE.panes[pane.id].ws === ws)
                    setTimeout(() => connectHyperliquidWS(pane), 5000);
            };
        } catch (e) {
            console.warn(`WS blocked for Pane #${pane.id}, falling back to polling`);
            startLivePolling(pane);
        }
    }

    function syncHistoricalCandles(pane, limit = 10) {
        if (!pane || pane.isDisposed || !STATE.panes[pane.id] || !pane.chart) return;
        if (pane.timeframe && pane.timeframe.toLowerCase() === 'renko') return;
        if (pane._isSyncingHistorical) return;
        pane._isSyncingHistorical = true;

        const url = buildHistoricalUrl(pane, limit);
        fetch(url)
            .then(r => r.json())
            .then(hist => {
                pane._isSyncingHistorical = false;
                if (pane.isDisposed || !STATE.panes[pane.id] || !pane.chart) return;
                if (!Array.isArray(hist) || hist.length === 0) return;

                const currentT = pane.lastCandle ? pane.lastCandle.time : null;
                let hasDifference = false;

                for (const hc of hist) {
                    const existing = pane.candles.find(c => c.time === hc.time);
                    if (!existing) {
                        hasDifference = true;
                        break;
                    }
                    if (currentT != null && hc.time < currentT) {
                        if (existing.open !== hc.open || existing.high !== hc.high ||
                            existing.low !== hc.low || existing.close !== hc.close) {
                            hasDifference = true;
                            break;
                        }
                    } else if (currentT != null && hc.time === currentT) {
                        if (hc.high > existing.high || hc.low < existing.low) {
                            hasDifference = true;
                            break;
                        }
                    }
                }

                if (hasDifference) {
                    pane.candles = mergeCandles(pane.candles, hist, true);
                    rebuildTimeIndexMap(pane);
                    pane.series.setData(pane.candles);
                    if (pane.candles.length > 0) {
                        pane.lastCandle = { ...pane.candles[pane.candles.length - 1] };
                    }
                    updateActiveIndicators(pane, true);
                }
            })
            .catch(() => {
                pane._isSyncingHistorical = false;
            });
    }

    function startLivePolling(pane) {
        if (pane.pollingTimer) {
            clearInterval(pane.pollingTimer);
            pane.pollingTimer = null;
        }

        const interval = pane.source === 'mt5' ? 1500 : 3000;
        pane.pollingTimer = setInterval(() => {
            if (pane.isDisposed || !STATE.panes[pane.id] || !pane.chart) return;
            if (pane.timeframe && pane.timeframe.toLowerCase() === 'renko') return;

            fetch(`/api/live?source=${pane.source}&symbol=${pane.symbol}`)
                .then(r => r.json())
                .then(data => {
                    if (pane.isDisposed || !STATE.panes[pane.id] || !pane.chart) return;
                    if (data.error || data.price == null) return;
                    const newPrice = parseFloat(data.price);
                    if (isNaN(newPrice)) return;

                    const oldPrice = pane.lastPrice;
                    if (newPrice !== oldPrice) {
                        if (oldPrice !== null) triggerTickerFlash(pane, newPrice, oldPrice);
                        else updateTickerDisplay(pane, newPrice, 0.0);
                    }
                    pane.lastPrice = newPrice;

                    // Derive current timeframe bucket start using broker server time
                    const serverTime = (data.time && Number(data.time) > 0) ? Number(data.time) : Math.floor(Date.now() / 1000);
                    const tfSec = getTimeframeDurationSeconds(pane.timeframe) || 60;
                    const currentCandleTime = Math.floor(serverTime / tfSec) * tfSec;

                    if (!pane.lastCandle) {
                        if (pane.candles && pane.candles.length > 0) {
                            pane.lastCandle = { ...pane.candles[pane.candles.length - 1] };
                        } else {
                            pane.lastCandle = { time: currentCandleTime, open: newPrice, high: newPrice, low: newPrice, close: newPrice };
                            pane.candles = [pane.lastCandle];
                            pane.series.setData(pane.candles);
                            rebuildTimeIndexMap(pane);
                            updateActiveIndicators(pane, true);
                            return;
                        }
                    }

                    const candleT = pane.lastCandle.time;
                    if (currentCandleTime < candleT) {
                        // Skip stale tick older than the current bar
                        return;
                    }

                    if (currentCandleTime === candleT) {
                        // Same ongoing bar: update OHLC & accumulate volume
                        const curVol = (pane.lastCandle && typeof pane.lastCandle.volume === 'number' && !isNaN(pane.lastCandle.volume))
                            ? pane.lastCandle.volume
                            : 0;
                        const updated = {
                            time: candleT,
                            open: pane.lastCandle.open,
                            high: Math.max(pane.lastCandle.high, newPrice),
                            low: Math.min(pane.lastCandle.low, newPrice),
                            close: newPrice,
                            volume: curVol + 1
                        };
                        pane.series.update(updated);
                        pane.lastCandle = updated;
                        if (pane.candles.length > 0) {
                            pane.candles[pane.candles.length - 1] = updated;
                        }
                        updateActiveIndicators(pane, false);
                    } else if (currentCandleTime > candleT) {
                        // A new bar interval has begun!
                        const newCandle = {
                            time: currentCandleTime,
                            open: newPrice,
                            high: newPrice,
                            low: newPrice,
                            close: newPrice,
                            volume: 1
                        };
                        pane.series.update(newCandle);
                        pane.lastCandle = newCandle;
                        pane.candles.push(newCandle);
                        if (pane.timeToIndexMap) {
                            pane.timeToIndexMap.set(currentCandleTime, pane.candles.length - 1);
                        }
                        updateActiveIndicators(pane, true);

                        const missedBars = Math.floor((currentCandleTime - candleT) / tfSec);
                        const syncLimit = Math.min(50, Math.max(10, missedBars + 2));
                        syncHistoricalCandles(pane, syncLimit);
                    }

                    // Periodic background sync every 20 seconds
                    const nowMs = Date.now();
                    if (!pane._lastSyncTime || (nowMs - pane._lastSyncTime > 20000)) {
                        pane._lastSyncTime = nowMs;
                        syncHistoricalCandles(pane, 10);
                    }
                })
                .catch(() => { });
        }, interval);
    }

    // ══════════════════════════════════════════════
    //  TICKER & VISUAL POLISH
    // ══════════════════════════════════════════════
    function triggerTickerFlash(pane, newPrice, oldPrice) {
        const bar = pane.element.querySelector('.ticker-bar');
        const lbl = pane.element.querySelector('.ticker-price');
        const dir = pane.element.querySelector('.ticker-direction');
        if (!bar || !lbl || !dir) return;

        bar.classList.remove('flash-up', 'flash-down');
        lbl.classList.remove('bull-text', 'bear-text');
        const change = oldPrice !== null ? newPrice - oldPrice : 0;
        const pct = oldPrice && oldPrice !== 0 ? (change / oldPrice) * 100 : 0;
        void bar.offsetWidth; // reflow

        if (change >= 0) {
            bar.classList.add('flash-up');
            lbl.classList.add('bull-text');
            dir.textContent = `▲ +${pct.toFixed(2)}%`;
            dir.className = 'ticker-direction bull-text';
        } else {
            bar.classList.add('flash-down');
            lbl.classList.add('bear-text');
            dir.textContent = `▼ ${pct.toFixed(2)}%`;
            dir.className = 'ticker-direction bear-text';
        }
        lbl.textContent = formatPriceValue(pane.source, newPrice);
    }

    function updateTickerDisplay(pane, price, pctChange) {
        const lbl = pane.element.querySelector('.ticker-price');
        const dir = pane.element.querySelector('.ticker-direction');
        if (!lbl || !dir) return;
        lbl.textContent = formatPriceValue(pane.source, price);
        if (pctChange >= 0) {
            dir.textContent = `▲ +${pctChange.toFixed(2)}%`;
            dir.className = 'ticker-direction bull-text';
        } else {
            dir.textContent = `▼ ${pctChange.toFixed(2)}%`;
            dir.className = 'ticker-direction bear-text';
        }
    }

    // ══════════════════════════════════════════════
    //  HELPERS
    // ══════════════════════════════════════════════
    function handleResize() {
        Object.values(STATE.panes).forEach(pane => {
            if (!pane?.chart || !pane.element || pane.isDisposed) return;
            const mount = pane.element.querySelector('.chart-mount');
            if (mount) {
                const w = mount.clientWidth, h = mount.clientHeight;
                if (w > 0 && h > 0) {
                    try { pane.chart.resize(w, h); } catch (e) { }
                }
            }
            Object.values(pane.oscillators || {}).forEach(osc => {
                if (!osc?.chart || !osc.subpaneEl || pane.isDisposed) return;
                const r = osc.subpaneEl.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) {
                    try { osc.chart.resize(r.width, r.height); } catch (e) { }
                }
            });
        });
    }

    function testMT5Connection() {
        if (!mt5StatusPanel) return;
        mt5StatusPanel.className = 'mt5-status-badge';
        mt5StatusPanel.querySelector('.status-label').textContent = 'MT5: CHECKING...';

        fetch('/api/test_mt5')
            .then(r => r.json())
            .then(data => {
                if (data.status === 'connected') {
                    STATE.mt5Status = 'connected';
                    mt5StatusPanel.className = 'mt5-status-badge connected';
                    mt5StatusPanel.querySelector('.status-label').textContent = 'MT5: CONNECTED';
                    mt5StatusPanel.setAttribute('title', `Connected: ${data.company} — ${data.version}`);
                } else {
                    STATE.mt5Status = 'disconnected';
                    mt5StatusPanel.className = 'mt5-status-badge disconnected';
                    mt5StatusPanel.querySelector('.status-label').textContent = 'MT5: DISCONNECTED';
                    mt5StatusPanel.setAttribute('title', data.message || 'Not connected');
                }
            })
            .catch(() => {
                mt5StatusPanel.className = 'mt5-status-badge disconnected';
                mt5StatusPanel.querySelector('.status-label').textContent = 'MT5: ERROR';
            });
    }

    function getPriceFormatOptions(source, symbol, price) {
        const s = (symbol || '').toUpperCase();
        if (s.includes('JPY')) return { type: 'price', precision: 3, minMove: 0.001 };
        if (s.includes('XAU') || s.includes('GOLD')) return { type: 'price', precision: 2, minMove: 0.01 };
        if (s.includes('BTC') || s.includes('ETH') || s.includes('SOL') || s.includes('CRYPTO')) return { type: 'price', precision: 2, minMove: 0.01 };
        if (s.includes('EUR') || s.includes('GBP') || s.includes('AUD') || s.includes('NZD') || s.includes('CAD') || s.includes('CHF')) {
            return { type: 'price', precision: 5, minMove: 0.00001 };
        }
        if (price != null && price > 0) {
            if (price < 0.01) return { type: 'price', precision: 6, minMove: 0.000001 };
            if (price < 1) return { type: 'price', precision: 4, minMove: 0.0001 };
            if (price < 10) return { type: 'price', precision: 5, minMove: 0.00001 };
            if (price < 100) return { type: 'price', precision: 4, minMove: 0.0001 };
            return { type: 'price', precision: 2, minMove: 0.01 };
        }
        return { type: 'price', precision: 2, minMove: 0.01 };
    }

    function getTimeframeDurationSeconds(tf) {
        return { '1m': 60, '2m': 120, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '4h': 14400, '1d': 86400 }[tf] || 300;
    }

    function addTime(timeVal, durationSeconds) {
        if (typeof timeVal === 'number') {
            return timeVal + durationSeconds;
        }
        if (typeof timeVal === 'string') {
            const date = new Date(timeVal);
            if (!isNaN(date.getTime())) {
                const newTime = date.getTime() + durationSeconds * 1000;
                const newDate = new Date(newTime);
                const yyyy = newDate.getUTCFullYear();
                const mm = String(newDate.getUTCMonth() + 1).padStart(2, '0');
                const dd = String(newDate.getUTCDate()).padStart(2, '0');
                return `${yyyy}-${mm}-${dd}`;
            }
        }
        if (typeof timeVal === 'object' && timeVal !== null && 'year' in timeVal) {
            const date = new Date(Date.UTC(timeVal.year, timeVal.month - 1, timeVal.day));
            const newTime = date.getTime() + durationSeconds * 1000;
            const newDate = new Date(newTime);
            return {
                year: newDate.getUTCFullYear(),
                month: newDate.getUTCMonth() + 1,
                day: newDate.getUTCDate()
            };
        }
        return timeVal;
    }


    function formatPriceValue(source, price) {
        if (price == null) return '--';
        if (source === 'mt5' && price < 10) return price.toFixed(5);
        if (price < 1) return price.toFixed(6);
        if (price < 100) return price.toFixed(4);
        return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    // ══════════════════════════════════════════════
    //  TRADING UI ENGINE (Overlays & Context Menu)
    // ══════════════════════════════════════════════
    setInterval(() => {
        if (STATE.mt5Status === 'connected' && !TRADING_STATE.dragActive) fetchTradingState();
    }, 2000);

    function fetchTradingState() {
        fetch('/api/trading/state?source=mt5')
            .then(r => r.json())
            .then(data => {
                if (data.positions) {
                    TRADING_STATE.positions = data.positions;
                    TRADING_STATE.orders = data.orders;
                    Object.keys(STATE.panes).forEach(id => {
                        const p = STATE.panes[id];
                        if (p && p.source === 'mt5') rebuildTradingOverlays(id);
                    });
                }
            }).catch(console.warn);
    }

    function showContextMenu(evt, paneId) {
        const pane = STATE.panes[paneId];
        if (!pane || !cMenu) return;

        const rect = pane.element.querySelector('.chart-mount').getBoundingClientRect();
        const y = evt.clientY - rect.top;

        try {
            cMenuPrice = pane.series.coordinateToPrice(y);
        } catch (e) { return; } // clicked out of bounds

        if (cMenuPrice == null) return;

        cMenuTargetPane = pane;
        const fmt = formatPriceValue('mt5', cMenuPrice);

        // Update menu text
        cMenu.querySelectorAll('.cmenu-symbol').forEach(el => el.textContent = pane.symbol);
        cMenu.querySelectorAll('.cmenu-price').forEach(el => el.textContent = fmt);

        cMenu.style.left = `${evt.clientX}px`;
        cMenu.style.top = `${evt.clientY}px`;
        cMenu.classList.remove('hidden');
    }

    // Hide menu on any global click
    window.addEventListener('click', () => {
        if (cMenu) cMenu.classList.add('hidden');
    });

    // Sync lot size inputs
    const globalLotInput = document.getElementById('global-lot-size');
    const cMenuLotInput = document.getElementById('cmenu-volume-input');

    if (globalLotInput && cMenuLotInput) {
        globalLotInput.addEventListener('input', (e) => {
            cMenuLotInput.value = e.target.value;
            if (cMenu) cMenu.querySelectorAll('.cmenu-vol-disp').forEach(el => el.textContent = e.target.value);
        });
        cMenuLotInput.addEventListener('input', (e) => {
            globalLotInput.value = e.target.value;
            if (cMenu) cMenu.querySelectorAll('.cmenu-vol-disp').forEach(el => el.textContent = e.target.value);
        });
        cMenuLotInput.addEventListener('mousedown', e => e.stopPropagation());

        // Init
        if (cMenu) cMenu.querySelectorAll('.cmenu-vol-disp').forEach(el => el.textContent = globalLotInput.value);
    }

    // Wire up menu actions using onmousedown to avoid click-away conflicts
    if (cMenu) {
        document.getElementById('cmenu-buy-limit').onmousedown = (e) => { e.stopPropagation(); sendTradeAction('buy_limit', cMenuPrice); cMenu.classList.add('hidden'); };
        document.getElementById('cmenu-sell-limit').onmousedown = (e) => { e.stopPropagation(); sendTradeAction('sell_limit', cMenuPrice); cMenu.classList.add('hidden'); };
        document.getElementById('cmenu-buy-stop').onmousedown = (e) => { e.stopPropagation(); sendTradeAction('buy_stop', cMenuPrice); cMenu.classList.add('hidden'); };
        document.getElementById('cmenu-sell-stop').onmousedown = (e) => { e.stopPropagation(); sendTradeAction('sell_stop', cMenuPrice); cMenu.classList.add('hidden'); };
        document.getElementById('cmenu-close-menu').onmousedown = (e) => { e.stopPropagation(); cMenu.classList.add('hidden'); };
    }

    function sendTradeAction(type, price, volume = null) {
        if (!cMenuTargetPane) return;
        const volInput = document.getElementById('cmenu-volume-input');
        const finalVolume = volume || (volInput ? parseFloat(volInput.value) : 0.1) || 0.1;

        fetch('/api/trading/place', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source: 'mt5', symbol: cMenuTargetPane.symbol, type, price, volume: finalVolume
            })
        }).then(r => r.json()).then(data => {
            console.log('Trade result:', data);
            if (data.status === 'error') {
                alert("Order Failed: " + (data.message || "Unknown error"));
            }
            fetchTradingState();
        }).catch(e => alert("API Error: " + e));
    }

    // The core rendering engine for dragging lines
    function rebuildTradingOverlays(paneId) {
        const pane = STATE.panes[paneId];
        if (!pane || TRADING_STATE.dragActive) return;

        const container = pane.element.querySelector('.trading-overlay-container');
        if (!container) return;

        container.innerHTML = '';

        // Filter for this pane's symbol
        const pos = TRADING_STATE.positions.filter(p => p.symbol === pane.symbol);
        const ord = TRADING_STATE.orders.filter(o => o.symbol === pane.symbol);

        pos.forEach(p => renderTradingLine(pane, container, p, true));
        ord.forEach(o => renderTradingLine(pane, container, o, false));

        syncTradingOverlays(paneId);
    }

    // Runs via requestAnimationFrame to keep lines synced with chart scale
    function syncTradingOverlays(paneId) {
        const pane = STATE.panes[paneId];
        if (!pane || pane.isDisposed || !pane.series || TRADING_STATE.dragActive) return;

        const container = pane.element.querySelector('.trading-overlay-container');
        if (!container) return;

        const wrappers = container.querySelectorAll('.order-line-wrapper');
        wrappers.forEach(w => {
            const price = parseFloat(w.dataset.price);
            if (isNaN(price)) return;
            try {
                const y = Math.round(pane.series.priceToCoordinate(price));
                if (y !== null && !isNaN(y) && y >= -50 && y <= container.clientHeight + 50) {
                    const topStr = `${y}px`;
                    if (w.style.top !== topStr) w.style.top = topStr;
                    if (w.style.display !== 'block') w.style.display = 'block';
                } else {
                    if (w.style.display !== 'none') w.style.display = 'none';
                }
            } catch (e) { }
        });
    }

    function renderTradingLine(pane, container, item, isPosition) {
        // Main entry line
        const entryPrice = isPosition ? item.price_open : item.price_open;
        createDraggableLine(pane, container, item, isPosition, 'entry', entryPrice, item.type.includes('buy') ? 'buy' : 'sell');

        // TP Line
        if (item.tp > 0) {
            createDraggableLine(pane, container, item, isPosition, 'tp', item.tp, 'tp');
        }

        // SL Line
        if (item.sl > 0) {
            createDraggableLine(pane, container, item, isPosition, 'sl', item.sl, 'sl');
        }
    }

    function estimateProfit(item, targetPrice) {
        if (!item || targetPrice == null || item.price_open == null) return null;
        if (item.point_value != null && !isNaN(item.point_value)) {
            return (targetPrice - item.price_open) * item.point_value;
        }
        if (item.tp_profit != null && item.tp && Math.abs(item.tp - item.price_open) > 1e-7) {
            const rate = item.tp_profit / (item.tp - item.price_open);
            return (targetPrice - item.price_open) * rate;
        }
        if (item.sl_profit != null && item.sl && Math.abs(item.sl - item.price_open) > 1e-7) {
            const rate = item.sl_profit / (item.sl - item.price_open);
            return (targetPrice - item.price_open) * rate;
        }
        if (item.profit != null && item.price_current && Math.abs(item.price_current - item.price_open) > 1e-7) {
            const rate = item.profit / (item.price_current - item.price_open);
            return (targetPrice - item.price_open) * rate;
        }
        return null;
    }

    function createDraggableLine(pane, container, item, isPosition, lineRole, priceVal, colorRole) {
        const wrapper = document.createElement('div');
        wrapper.className = `order-line-wrapper order-type-${colorRole}`;
        wrapper.dataset.price = priceVal;

        let y = null;
        try { y = pane.series.priceToCoordinate(priceVal); } catch (e) { }
        if (y !== null && y >= -50 && y <= container.clientHeight + 50) {
            wrapper.style.top = `${y}px`;
        } else {
            wrapper.style.display = 'none';
        }

        // The dashed line
        const dash = document.createElement('div');
        dash.className = 'order-dashed-line';
        wrapper.appendChild(dash);

        // The interactive badge
        const badge = document.createElement('div');
        badge.className = `order-badges`;

        let labelText = '';
        if (lineRole === 'entry') {
            labelText = isPosition ? (item.type === 'buy' ? `BUY ${item.volume}` : `SELL ${item.volume}`) : `${item.type.replace('_', ' ').toUpperCase()} ${item.volume}`;
        } else {
            labelText = lineRole.toUpperCase();
        }

        let extraText = '';
        let addBtns = '';
        if (lineRole === 'entry') {
            if (isPosition) {
                const pnl = item.profit >= 0 ? `+${item.profit.toFixed(2)}` : item.profit.toFixed(2);
                extraText = ` <span class="badge-pnl" style="margin-left:8px; color: ${item.profit >= 0 ? '#00E676' : '#FF1744'}">${pnl}</span>`;
            }
            if (!item.tp || item.tp === 0) {
                addBtns += `<span class="badge-add-btn" data-add="tp" title="Add Take Profit">+TP</span>`;
            }
            if (!item.sl || item.sl === 0) {
                addBtns += `<span class="badge-add-btn" data-add="sl" title="Add Stop Loss">+SL</span>`;
            }
        } else if (lineRole === 'tp') {
            let tpProfit = item.tp_profit;
            if (tpProfit === undefined || tpProfit === null) {
                tpProfit = estimateProfit(item, priceVal);
            }
            if (tpProfit !== undefined && tpProfit !== null && !isNaN(tpProfit)) {
                const pnl = tpProfit >= 0 ? `+${tpProfit.toFixed(2)}` : tpProfit.toFixed(2);
                extraText = ` <span class="badge-pnl" style="margin-left:8px; color: ${tpProfit >= 0 ? '#00E676' : '#FF1744'}">${pnl}</span>`;
            }
        } else if (lineRole === 'sl') {
            let slProfit = item.sl_profit;
            if (slProfit === undefined || slProfit === null) {
                slProfit = estimateProfit(item, priceVal);
            }
            if (slProfit !== undefined && slProfit !== null && !isNaN(slProfit)) {
                const pnl = slProfit >= 0 ? `+${slProfit.toFixed(2)}` : slProfit.toFixed(2);
                extraText = ` <span class="badge-pnl" style="margin-left:8px; color: ${slProfit >= 0 ? '#00E676' : '#FF1744'}">${pnl}</span>`;
            }
        }

        badge.innerHTML = `
            <div class="order-badge badge-type-${colorRole}">
                <span class="badge-label">${labelText}</span>
                ${extraText}
                ${addBtns}
                <span class="badge-close" title="Cancel/Close">×</span>
            </div>
        `;

        // Wire up +TP / +SL buttons
        badge.querySelectorAll('.badge-add-btn').forEach(btn => {
            btn.onmousedown = (e) => {
                e.stopPropagation(); // prevent dragging
                const role = btn.dataset.add;
                const offset = priceVal * 0.002; // 0.2% offset by default
                const isBuy = item.type.includes('buy');

                let newPrice = priceVal;
                if (role === 'tp') {
                    newPrice = isBuy ? (priceVal + offset) : (priceVal - offset);
                } else if (role === 'sl') {
                    newPrice = isBuy ? (priceVal - offset) : (priceVal + offset);
                }

                commitDragAction(item.ticket, isPosition, role, newPrice);
            };
        });

        // Draggable logic
        const badgeEl = badge.querySelector('.order-badge');

        badgeEl.onmousedown = (e) => {
            if (e.target.classList.contains('badge-close') || e.target.classList.contains('badge-add-btn')) return; // let inner clicks pass
            e.preventDefault();
            TRADING_STATE.dragActive = true;
            badgeEl.classList.add('is-dragging');

            const startY = e.clientY;
            const startTop = parseFloat(wrapper.style.top);

            const onMove = (mv) => {
                const dy = mv.clientY - startY;
                let newY = startTop + dy;
                // Clamp
                newY = Math.max(0, Math.min(newY, container.clientHeight));
                wrapper.style.top = `${newY}px`;

                // Live price & profit update visually during drag
                if (pane.series && (lineRole === 'tp' || lineRole === 'sl')) {
                    try {
                        const curPrice = pane.series.coordinateToPrice(newY);
                        if (curPrice != null) {
                            const liveProfit = estimateProfit(item, curPrice);
                            if (liveProfit != null && !isNaN(liveProfit)) {
                                const pnlStr = liveProfit >= 0 ? `+${liveProfit.toFixed(2)}` : liveProfit.toFixed(2);
                                let pnlEl = badgeEl.querySelector('.badge-pnl');
                                if (!pnlEl) {
                                    pnlEl = document.createElement('span');
                                    pnlEl.className = 'badge-pnl';
                                    pnlEl.style.marginLeft = '8px';
                                    const closeBtn = badgeEl.querySelector('.badge-close');
                                    if (closeBtn) {
                                        badgeEl.insertBefore(pnlEl, closeBtn);
                                    } else {
                                        badgeEl.appendChild(pnlEl);
                                    }
                                }
                                pnlEl.textContent = pnlStr;
                                pnlEl.style.color = liveProfit >= 0 ? '#00E676' : '#FF1744';
                            }
                        }
                    } catch (err) { }
                }
            };

            const onUp = (up) => {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                badgeEl.classList.remove('is-dragging');
                TRADING_STATE.dragActive = false;

                const finalY = parseFloat(wrapper.style.top);
                if (Math.abs(finalY - startTop) < 2) return; // Didn't actually drag

                let newPrice = null;
                try { newPrice = pane.series.coordinateToPrice(finalY); } catch (err) { }

                if (newPrice != null) {
                    commitDragAction(item.ticket, isPosition, lineRole, newPrice);
                }
            };

            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        };

        // Close / Cancel logic
        badge.querySelector('.badge-close').onclick = (e) => {
            e.stopPropagation();
            if (lineRole === 'tp') {
                commitDragAction(item.ticket, isPosition, 'tp', 0.0);
            } else if (lineRole === 'sl') {
                commitDragAction(item.ticket, isPosition, 'sl', 0.0);
            } else {
                fetch('/api/trading/cancel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source: 'mt5', ticket: item.ticket, is_position: isPosition,
                        symbol: item.symbol, volume: item.volume, type: item.type
                    })
                }).then(() => fetchTradingState());
            }
        };

        wrapper.appendChild(badge);
        container.appendChild(wrapper);
    }

    function commitDragAction(ticket, isPosition, role, newPrice) {
        const payload = { source: 'mt5', ticket, is_position: isPosition };
        if (role === 'entry' && !isPosition) {
            payload.price = newPrice;
        } else if (role === 'sl') {
            payload.sl = newPrice;
        } else if (role === 'tp') {
            payload.tp = newPrice;
        } else {
            return; // Can't drag a position's entry price
        }

        fetch('/api/trading/modify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(r => r.json()).then(data => {
            console.log('Modify result:', data);
            fetchTradingState();
        }).catch(console.error);
    }


    // ==============================================================================
    //  RENKO ENGINE & TIMELINE LOADER
    // ==============================================================================

    function loadRenkoData(pane) {
        cleanupFeeds(pane);
        pane.lastPrice = null; pane.lastCandle = null; pane.candles = [];

        // Force priceScale back to normal auto-scale immediately on symbol / mode switch
        pane.chart.priceScale('right').applyOptions({
            autoScale: true,
            mode: LightweightCharts.PriceScaleMode.Normal,
            scaleMargins: { top: 0.1, bottom: 0.1 }
        });

        // Fast synchronous price format
        const initialFmt = getPriceFormatOptions(pane.source, pane.symbol, null);
        pane.series.applyOptions({ priceFormat: initialFmt });

        // Clear all overlay series
        Object.values(pane.overlaySeries).forEach(s => {
            try { pane.chart.removeSeries(s); } catch (e) { }
        });
        pane.overlaySeries = {};
        clearSMC(pane);
        clearAiRenko(pane);
        clearOscillator(pane);

        const overlay = pane.element.querySelector('.pane-loading-overlay');
        if (overlay) {
            overlay.classList.remove('hidden');
            overlay.querySelector('.loading-text').innerHTML =
                '<div class="spinner"></div><span class="loading-text">Constructing Renko bricks...</span>';
        }

        const mode = pane.renkoMode || '1m';
        const timeline = pane.timelineMode || 'equidistant';
        const url = `/api/renko?symbol=${encodeURIComponent(pane.symbol)}&mode=${mode}&timeline_mode=${timeline}&limit=300`;

        fetch(url)
            .then(r => r.json())
            .then(data => {
                if (pane.isDisposed || !STATE.panes[pane.id] || !pane.chart) return;
                if (data.error || !data.bricks || !Array.isArray(data.bricks) || data.bricks.length === 0) {
                    throw new Error(data.error || 'No Renko bricks returned');
                }

                pane.candles = data.bricks;
                rebuildTimeIndexMap(pane);
                pane.series.setData(data.bricks);
                pane.chart.priceScale('right').applyOptions({ autoScale: true });
                pane.chart.timeScale().fitContent();

                // Update brick badge
                const brickBadge = pane.element.querySelector('.renko-brick-badge');
                if (brickBadge && data.brick_size) {
                    pane.brickSize = data.brick_size;
                    brickBadge.textContent = `BRICK: ${data.brick_size.toFixed(5)}`;
                }

                // Render or update Supertrend line on Renko
                if (data.supertrend && Array.isArray(data.supertrend)) {
                    if (!pane.stSeries) {
                        pane.stSeries = pane.chart.addSeries(LightweightCharts.LineSeries, {
                            color: '#10B981',
                            lineWidth: 2,
                            title: 'ST(1, 3.1)',
                            priceLineVisible: false,
                        });
                    }
                    pane.stSeries.setData(data.supertrend);
                }

                // Render Reference Zone price lines
                if (data.zones && typeof data.zones === 'object') {
                    renderZonePriceLines(pane, data.zones);
                }

                // Update ticker with latest brick close
                const lastB = data.bricks[data.bricks.length - 1];
                pane._lastBrickCount = data.bricks.length;
                pane._lastBrickIndex = lastB ? lastB.brick_index : null;
                pane._lastBrickClose = lastB ? lastB.close : null;
                pane.lastPrice = lastB ? lastB.close : null;
                pane.lastCandle = lastB;
                updateTickerDisplay(pane, lastB ? lastB.close : 0.0, 0.0);

                if (overlay) overlay.classList.add('hidden');
                applySymbolFormat(pane);

                // Auto-register supertrend in active indicators if present on Renko
                if (data.supertrend && pane.activeIndicators['supertrend'] === undefined) {
                    pane.activeIndicators['supertrend'] = true;
                }

                // Re-render all active overlay indicators on Renko bricks (e.g. SMC, EMA, SMA, Supertrend)
                Object.keys(pane.activeIndicators || {}).forEach(ind => {
                    if (pane.activeIndicators[ind]) renderIndicator(pane, ind);
                });
                updateActiveIndicatorLegend(pane);

                // Wire crosshair hover for Renko details
                wireRenkoCrosshair(pane);

                // Start Renko live polling & bot telemetry
                startRenkoPolling(pane);
            })
            .catch(err => {
                if (pane.isDisposed || !STATE.panes[pane.id]) return;
                console.error(`Renko data error for ${pane.symbol}:`, err);
                if (overlay) {
                    overlay.querySelector('.loading-text').innerHTML =
                        `<span class="bear-text">Failed to construct Renko.<br>${err.message}</span>`;
                }
            });
    }

    function renderZonePriceLines(pane, zones) {
        if (pane.zoneLines && Array.isArray(pane.zoneLines)) {
            pane.zoneLines.forEach(l => {
                try { pane.series.removePriceLine(l); } catch (e) { }
            });
        }
        pane.zoneLines = [];

        Object.entries(zones).forEach(([zName, zData]) => {
            if (!zData || !zData.high || !zData.low) return;
            const zColor = zData.color === 'GREEN' ? '#10B981' : (zData.color === 'RED' ? '#EF4444' : '#64748B');

            // Zone High
            const lHigh = pane.series.createPriceLine({
                price: zData.high,
                color: zColor,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: `${zName} H`,
            });
            pane.zoneLines.push(lHigh);

            // Zone Low
            const lLow = pane.series.createPriceLine({
                price: zData.low,
                color: zColor,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: `${zName} L`,
            });
            pane.zoneLines.push(lLow);

            // Fibo 0.44 & 0.56 Chop Corridor
            if (zData.fib_044 && zData.fib_056) {
                const lF44 = pane.series.createPriceLine({
                    price: zData.fib_044,
                    color: '#F59E0B',
                    lineWidth: 1,
                    lineStyle: LightweightCharts.LineStyle.Dotted,
                    axisLabelVisible: false,
                    title: `0.44`,
                });
                const lF56 = pane.series.createPriceLine({
                    price: zData.fib_056,
                    color: '#F59E0B',
                    lineWidth: 1,
                    lineStyle: LightweightCharts.LineStyle.Dotted,
                    axisLabelVisible: false,
                    title: `0.56`,
                });
                pane.zoneLines.push(lF44, lF56);
            }
        });
    }

    function wireRenkoCrosshair(pane) {
        if (pane._renkoCrosshairWired) return;
        pane._renkoCrosshairWired = true;

        pane.chart.subscribeCrosshairMove(param => {
            const statsEl = pane.element.querySelector('.renko-crosshair-stats');
            if (!statsEl) return;

            if (!param || !param.time || !param.seriesData || !param.seriesData.get(pane.series)) {
                statsEl.innerHTML = '';
                return;
            }

            const dataPoint = param.seriesData.get(pane.series);
            const brick = pane.candles ? pane.candles.find(c => c.time === param.time) : null;
            if (brick && dataPoint) {
                const streakClass = (brick.bar_num > 0) ? 'pos' : (brick.bar_num < 0 ? 'neg' : '');
                const streakText = (brick.bar_num > 0) ? `+${brick.bar_num}` : String(brick.bar_num || 0);
                const revText = brick.is_reversal ? '<span style="color:#F59E0B;font-weight:700;">[REV]</span>' : '';
                const timeText = brick.real_time ? `<span style="color:var(--text-muted);">${brick.real_time}</span>` : '';

                statsEl.innerHTML = `
                    <span style="margin-left: 14px; font-weight: 600;">Brick #${brick.brick_index ?? '--'}</span>
                    ${timeText}
                    <span class="${streakClass}">Streak: ${streakText}</span>
                    ${revText}
                    <span>O: <span class="val">${dataPoint.open.toFixed(5)}</span></span>
                    <span>H: <span class="val">${dataPoint.high.toFixed(5)}</span></span>
                    <span>L: <span class="val">${dataPoint.low.toFixed(5)}</span></span>
                    <span>C: <span class="val">${dataPoint.close.toFixed(5)}</span></span>
                `;
            } else {
                statsEl.innerHTML = '';
            }
        });
    }

    function startRenkoPolling(pane) {
        if (pane.renkoPollingTimer) clearInterval(pane.renkoPollingTimer);

        const poll = () => {
            if (!STATE.panes[pane.id] || pane.timeframe.toLowerCase() !== 'renko') return;

            fetchBotStatus(pane);

            const mode = pane.renkoMode || '1m';
            const timeline = pane.timelineMode || 'equidistant';
            fetch(`/api/renko?symbol=${encodeURIComponent(pane.symbol)}&mode=${mode}&timeline_mode=${timeline}&limit=300`)
                .then(r => r.json())
                .then(data => {
                    if (pane.isDisposed || !STATE.panes[pane.id] || !pane.chart) return;
                    if (data && data.bricks && data.bricks.length > 0) {
                        const newLen = data.bricks.length;
                        const lastB = data.bricks[newLen - 1];
                        const lastIndex = lastB ? lastB.brick_index : null;
                        const lastClose = lastB ? lastB.close : null;
                        const changed = (pane._lastBrickCount !== newLen) ||
                            (pane._lastBrickIndex !== lastIndex) ||
                            (pane._lastBrickClose !== lastClose);
                        if (changed) {
                            pane._lastBrickCount = newLen;
                            pane._lastBrickIndex = lastIndex;
                            pane._lastBrickClose = lastClose;
                            pane.candles = data.bricks;
                            rebuildTimeIndexMap(pane);
                            pane.series.setData(data.bricks);
                            pane.lastPrice = lastB.close;
                            updateTickerDisplay(pane, lastB.close, 0.0);
                            if (pane.stSeries && data.supertrend) {
                                pane.stSeries.setData(data.supertrend);
                            }
                            updateActiveIndicators(pane);
                            updateActiveIndicatorLegend(pane);
                        }
                    }
                })
                .catch(() => { });
        };

        pane.renkoPollingTimer = setInterval(poll, 1500);
        poll();
    }

    function fetchBotStatus(pane) {
        fetch(`/api/bot/status?symbol=${encodeURIComponent(pane.symbol)}`)
            .then(r => r.json())
            .then(st => updatePaneBotBar(pane, st))
            .catch(() => { });
    }

    function updatePaneBotBar(pane, st) {
        if (!st) return;
        const bar = pane.element.querySelector('.pane-bot-bar');
        if (!bar) return;

        const badge = bar.querySelector('.bot-status-badge');
        const paneModeBtn = bar.querySelector('.bot-pane-mode-btn');
        const actBtn = bar.querySelector('.btn-bot-action');
        const streakPill = bar.querySelector('.streak-pill');
        const posPill = bar.querySelector('.pos-pill');

        if (st.is_running) {
            if (st.dry_run) {
                badge.className = 'bot-status-badge bot-status-paper';
                badge.textContent = 'RUNNING (PAPER)';
                pane.executionMode = 'paper';
            } else {
                badge.className = 'bot-status-badge bot-status-live';
                badge.textContent = 'RUNNING (LIVE)';
                pane.executionMode = 'live';
            }
            if (paneModeBtn) {
                paneModeBtn.textContent = pane.executionMode.toUpperCase();
                paneModeBtn.className = `bot-pane-mode-btn mode-${pane.executionMode}`;
            }
            actBtn.textContent = 'Stop';
            actBtn.className = 'btn-bot-action btn-bot-stop';
        } else {
            badge.className = 'bot-status-badge bot-status-stopped';
            badge.textContent = 'STOPPED';
            if (paneModeBtn && pane.executionMode) {
                paneModeBtn.textContent = pane.executionMode.toUpperCase();
                paneModeBtn.className = `bot-pane-mode-btn mode-${pane.executionMode}`;
            }
            actBtn.textContent = 'Start';
            actBtn.className = 'btn-bot-action btn-bot-start';
        }

        if (st.bar_num !== undefined) {
            streakPill.textContent = `STREAK: ${st.bar_num > 0 ? '+' : ''}${st.bar_num}`;
            streakPill.className = `streak-pill ${st.bar_num > 0 ? 'streak-bull' : (st.bar_num < 0 ? 'streak-bear' : 'streak-neutral')}`;
        }

        if (st.open_position) {
            posPill.classList.remove('hidden');
            const pos = st.open_position;
            const pnlStr = pos.profit >= 0 ? `+$${pos.profit.toFixed(2)}` : `-$${Math.abs(pos.profit).toFixed(2)}`;
            posPill.querySelector('.pos-info').textContent = `${pos.type} ${pos.volume} @ ${pos.open_price.toFixed(5)} (${pnlStr})`;
        } else {
            posPill.classList.add('hidden');
        }
    }

    // ==============================================================================
    //  GLOBAL BOT MASTER CONTROLS
    // ==============================================================================

    function initGlobalBotControls() {
        const btnModePaper = document.getElementById('btn-mode-paper');
        const btnModeLive = document.getElementById('btn-mode-live');
        const btnStartAll = document.getElementById('btn-start-all-bots');
        const btnStopAll = document.getElementById('btn-stop-all-bots');
        const btnPanic = document.getElementById('btn-panic-close-all');

        function syncHeaderModeUI() {
            const isLive = (STATE.executionMode === 'live');
            if (btnModePaper) btnModePaper.classList.toggle('active', !isLive);
            if (btnModeLive) btnModeLive.classList.toggle('active', isLive);
        }

        if (btnModePaper) {
            btnModePaper.addEventListener('click', () => {
                STATE.executionMode = 'paper';
                SafeStorage.setItem('ag_execution_mode', 'paper');
                syncHeaderModeUI();
                Object.values(STATE.panes).forEach(p => {
                    p.executionMode = 'paper';
                    SafeStorage.setItem(`ag_pane_mode_${p.id}`, 'paper');
                    const b = p.element ? p.element.querySelector('.bot-pane-mode-btn') : null;
                    if (b) { b.textContent = 'PAPER'; b.className = 'bot-pane-mode-btn mode-paper'; }
                });
            });
        }

        if (btnModeLive) {
            btnModeLive.addEventListener('click', () => {
                if (confirm('⚠️ WARNING: Switch global execution mode to LIVE MT5 REAL MONEY?\n\nStarting bots will execute real trades on your connected MetaTrader 5 account.')) {
                    STATE.executionMode = 'live';
                    SafeStorage.setItem('ag_execution_mode', 'live');
                    syncHeaderModeUI();
                    Object.values(STATE.panes).forEach(p => {
                        p.executionMode = 'live';
                        SafeStorage.setItem(`ag_pane_mode_${p.id}`, 'live');
                        const b = p.element ? p.element.querySelector('.bot-pane-mode-btn') : null;
                        if (b) { b.textContent = 'LIVE'; b.className = 'bot-pane-mode-btn mode-live'; }
                    });
                }
            });
        }

        syncHeaderModeUI();

        if (btnStartAll) {
            btnStartAll.addEventListener('click', () => {
                const isLive = (STATE.executionMode === 'live');
                const promptMsg = isLive
                    ? '⚠️ WARNING: Start all 7 RK Renko Bots in LIVE MT5 REAL MONEY Mode?'
                    : 'Start all 7 RK Renko Bots in Paper Simulation Mode?';
                if (confirm(promptMsg)) {
                    fetch('/api/bot/start_all', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ live: isLive, mode: '1m' })
                    })
                        .then(r => r.json())
                        .then(res => {
                            console.log('Start All Bots:', res);
                            // Refresh all panes
                            Object.values(STATE.panes).forEach(p => fetchBotStatus(p));
                        });
                }
            });
        }

        if (btnStopAll) {
            btnStopAll.addEventListener('click', () => {
                fetch('/api/bot/stop_all', { method: 'POST' })
                    .then(r => r.json())
                    .then(res => {
                        console.log('Stop All Bots:', res);
                        Object.values(STATE.panes).forEach(p => fetchBotStatus(p));
                    });
            });
        }

        if (btnPanic) {
            btnPanic.addEventListener('click', () => {
                if (confirm('⚠️ EMERGENCY CLOSE: Immediately close all open positions across all bots?')) {
                    fetch('/api/bot/emergency_close', { method: 'POST' })
                        .then(r => r.json())
                        .then(res => alert(`Panic close complete: Closed ${res.closed_count} position(s).`));
                }
            });
        }

        // Live Account Summary Poller
        const pollAccount = () => {
            fetch('/api/test_mt5')
                .then(r => r.json())
                .then(data => {
                    const mt5Badge = document.getElementById('mt5-status-panel');
                    if (data.status === 'connected') {
                        if (mt5Badge) {
                            mt5Badge.className = 'mt5-status-badge connected';
                            mt5Badge.querySelector('.status-label').textContent = 'MT5: CONNECTED';
                        }
                        if (data.account) {
                            const balEl = document.getElementById('acc-balance');
                            const eqEl = document.getElementById('acc-equity');
                            const pnlEl = document.getElementById('acc-pnl');
                            if (balEl && data.account.balance !== undefined) balEl.textContent = `$${data.account.balance.toFixed(2)}`;
                            if (eqEl && data.account.equity !== undefined) eqEl.textContent = `$${data.account.equity.toFixed(2)}`;
                            if (pnlEl) {
                                const p = data.account.profit || 0;
                                pnlEl.textContent = p >= 0 ? `+$${p.toFixed(2)}` : `-$${Math.abs(p).toFixed(2)}`;
                                pnlEl.className = `stat-value ${p >= 0 ? 'pnl-pos' : 'pnl-neg'}`;
                            }
                        }
                    } else {
                        if (mt5Badge) {
                            mt5Badge.className = 'mt5-status-badge disconnected';
                            mt5Badge.querySelector('.status-label').textContent = 'MT5: DISCONNECTED';
                        }
                    }
                })
                .catch(() => { });
        };
        setInterval(pollAccount, 4000);
        pollAccount();
    }

    // ==============================================================================
    //  BOT ADJUSTMENTS MODAL
    // ==============================================================================

    let currentAdjustSymbol = 'GBPUSD';

    function initBotAdjustmentsModal() {
        const modal = document.getElementById('adjustments-modal');
        const backdrop = document.getElementById('modal-backdrop');
        const closeBtn = document.getElementById('adjust-modal-close');
        const btnSave = document.getElementById('btn-adjust-save');
        const btnApplyAll = document.getElementById('btn-adjust-apply-all');
        const btnReset = document.getElementById('btn-adjust-reset');
        const tabBtns = document.querySelectorAll('.adjust-tab-btn');

        if (!modal) return;

        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                tabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                document.querySelectorAll('.adjust-tab-content').forEach(c => c.classList.remove('active'));
                const targetTab = document.getElementById(btn.dataset.tab);
                if (targetTab) targetTab.classList.add('active');
            });
        });

        const closeModal = () => {
            modal.classList.add('hidden');
            if (backdrop) backdrop.classList.add('hidden');
        };

        if (closeBtn) closeBtn.addEventListener('click', closeModal);
        if (backdrop) backdrop.addEventListener('click', closeModal);

        if (btnSave) {
            btnSave.addEventListener('click', () => {
                saveAdjustments(currentAdjustSymbol);
                closeModal();
            });
        }

        if (btnApplyAll) {
            btnApplyAll.addEventListener('click', () => {
                if (confirm('Apply these adjustments to ALL 7 bots?')) {
                    saveAdjustments('ALL');
                    closeModal();
                }
            });
        }

        if (btnReset) {
            btnReset.addEventListener('click', () => {
                loadAdjustmentsForSymbol(currentAdjustSymbol);
            });
        }
    }

    function openAdjustmentsModal(symbol) {
        currentAdjustSymbol = symbol;
        const targetPill = document.getElementById('adjust-target-symbol');
        if (targetPill) targetPill.textContent = symbol;
        loadAdjustmentsForSymbol(symbol);
        const modal = document.getElementById('adjustments-modal');
        const backdrop = document.getElementById('modal-backdrop');
        if (modal) modal.classList.remove('hidden');
        if (backdrop) backdrop.classList.remove('hidden');
    }

    function loadAdjustmentsForSymbol(symbol) {
        fetch(`/api/bot/config?symbol=${encodeURIComponent(symbol)}`)
            .then(r => r.json())
            .then(cfg => {
                if (!cfg || cfg.error) return;
                setVal('adj-lot-size', cfg.lot_size);
                setVal('adj-sl-bricks', cfg.sl_bricks);
                setVal('adj-tp-r', cfg.tp_r);
                setVal('adj-trail-act', cfg.trail_act);
                setVal('adj-trail-dist', cfg.trail_bricks);
                setVal('adj-max-daily', cfg.max_daily_trades);
                setChecked('adj-enable-trailing', !cfg.no_trailing_stop);
                setChecked('adj-early-exit', !cfg.no_early_exit);
                setChecked('adj-execution-live', cfg.dry_run === false);

                setVal('adj-fixed-brick', cfg.fixed_brick_size || 0);
                setVal('adj-atr-period', cfg.atr_period);
                setVal('adj-atr-divisor', cfg.atr_divisor);
                setVal('adj-session-hours', cfg.session_hours);

                setChecked('adj-enable-zones', !cfg.no_zones);
                setChecked('adj-zone-only', cfg.zone_only_trades || false);
                setChecked('adj-h1-ema50', !cfg.no_h1_ema50);
                setChecked('adj-renko-ema', !cfg.no_renko_ema);
                setChecked('adj-firstred-shadow', cfg.firstred_shadow_rule);
                setVal('adj-zone-streak', cfg.zone_streak_bricks);
                setVal('adj-min-trend', cfg.min_trend_bricks);
            })
            .catch(() => { });
    }

    function saveAdjustments(symbol) {
        const params = {
            lot_size: parseFloat(getVal('adj-lot-size')),
            sl_bricks: parseFloat(getVal('adj-sl-bricks')),
            tp_r: parseFloat(getVal('adj-tp-r')),
            trail_act: parseFloat(getVal('adj-trail-act')),
            trail_bricks: parseFloat(getVal('adj-trail-dist')),
            max_daily_trades: parseInt(getVal('adj-max-daily')),
            no_trailing_stop: !getChecked('adj-enable-trailing'),
            no_early_exit: !getChecked('adj-early-exit'),
            dry_run: !getChecked('adj-execution-live'),

            fixed_brick_size: parseFloat(getVal('adj-fixed-brick')),
            atr_period: parseInt(getVal('adj-atr-period')),
            atr_divisor: parseInt(getVal('adj-atr-divisor')),
            session_hours: parseInt(getVal('adj-session-hours')),

            no_zones: !getChecked('adj-enable-zones'),
            no_zone_only: !getChecked('adj-zone-only'),
            zone_only_trades: getChecked('adj-zone-only'),
            no_h1_ema50: !getChecked('adj-h1-ema50'),
            no_renko_ema: !getChecked('adj-renko-ema'),
            firstred_shadow_rule: getChecked('adj-firstred-shadow'),
            zone_streak_bricks: parseInt(getVal('adj-zone-streak')),
            min_trend_bricks: parseInt(getVal('adj-min-trend')),
        };

        fetch('/api/bot/adjust', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: symbol, params: params })
        })
            .then(r => r.json())
            .then(res => {
                console.log('Adjustments applied:', res);
                Object.values(STATE.panes).forEach(p => {
                    if (symbol === 'ALL' || p.symbol === symbol) {
                        loadChartData(p.id);
                        fetchBotStatus(p);
                    }
                });
            })
            .catch(err => console.error('Error applying adjustments:', err));
    }

    // ==============================================================================
    //  BOTTOM TERMINAL CONSOLE LOG DRAWER
    // ==============================================================================

    function initTerminalConsole() {
        const drawer = document.getElementById('terminal-console-drawer');
        const logBody = document.getElementById('terminal-log-body');
        const countBadge = document.getElementById('terminal-log-count');
        const unreadBadge = document.getElementById('terminal-unread-badge');
        const symbolFilter = document.getElementById('terminal-symbol-filter');
        const searchInput = document.getElementById('terminal-search-input');
        const levelChips = document.querySelectorAll('.terminal-level-chips .log-chip');
        const btnAutoScroll = document.getElementById('btn-terminal-autoscroll');
        const btnClear = document.getElementById('btn-terminal-clear');
        const btnCopy = document.getElementById('btn-terminal-copy');
        const btnCollapse = document.getElementById('btn-terminal-collapse');

        if (!drawer || !logBody) return;

        let autoScroll = true;
        let selectedLevel = 'ALL';
        let selectedSymbol = 'ALL';
        let searchQuery = '';
        let unreadCount = 0;
        const allLogs = [];

        if (btnAutoScroll) {
            btnAutoScroll.addEventListener('click', () => {
                autoScroll = !autoScroll;
                btnAutoScroll.classList.toggle('active', autoScroll);
            });
        }

        if (btnClear) {
            btnClear.addEventListener('click', () => {
                logBody.innerHTML = '';
                allLogs.length = 0;
                if (countBadge) countBadge.textContent = '0 logs';
            });
        }

        if (btnCopy) {
            btnCopy.addEventListener('click', () => {
                const text = Array.from(logBody.querySelectorAll('.log-row'))
                    .map(r => r.innerText)
                    .join('\n');
                navigator.clipboard.writeText(text).then(() => {
                    const orig = btnCopy.textContent;
                    btnCopy.textContent = 'Copied!';
                    setTimeout(() => { btnCopy.textContent = orig; }, 1500);
                });
            });
        }

        const toggleDrawer = () => {
            drawer.classList.toggle('collapsed');
            const isCollapsed = drawer.classList.contains('collapsed');
            if (btnCollapse) btnCollapse.textContent = isCollapsed ? '▲' : '▼';
            if (!isCollapsed) {
                unreadCount = 0;
                if (unreadBadge) unreadBadge.textContent = '0';
            }
        };
        if (btnCollapse) btnCollapse.addEventListener('click', toggleDrawer);

        const headerToggleBtn = document.getElementById('btn-toggle-terminal');
        if (headerToggleBtn) headerToggleBtn.addEventListener('click', toggleDrawer);

        if (symbolFilter) {
            symbolFilter.addEventListener('change', () => {
                selectedSymbol = symbolFilter.value;
                rerenderLogs();
            });
        }

        levelChips.forEach(chip => {
            chip.addEventListener('click', () => {
                levelChips.forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                selectedLevel = chip.dataset.level;
                rerenderLogs();
            });
        });

        if (searchInput) {
            searchInput.addEventListener('input', () => {
                searchQuery = searchInput.value.toLowerCase().trim();
                rerenderLogs();
            });
        }

        function matchesFilter(item) {
            if (selectedSymbol !== 'ALL' && item.symbol && item.symbol.toUpperCase() !== selectedSymbol.toUpperCase()) {
                return false;
            }
            if (selectedLevel !== 'ALL') {
                if (selectedLevel === 'TRADES' && !item.is_trade) return false;
                if (selectedLevel !== 'TRADES' && item.level.toUpperCase() !== selectedLevel.toUpperCase()) return false;
            }
            if (searchQuery) {
                const combined = `${item.timestamp} ${item.level} ${item.symbol || ''} ${item.message}`.toLowerCase();
                if (!combined.includes(searchQuery)) return false;
            }
            return true;
        }

        function createLogRow(item) {
            const row = document.createElement('div');
            row.className = 'log-row';
            const lvl = (item.level || 'INFO').toLowerCase();
            const tradeClass = item.is_trade ? 'log-lvl-trade' : `log-lvl-${lvl}`;
            const tradeMsgClass = item.is_trade ? 'highlight-trade' : '';
            const symTag = item.symbol ? `[${item.symbol}]` : '[SYS]';

            row.innerHTML = `
                <span class="log-ts">${item.timestamp}</span>
                <span class="log-lvl ${tradeClass}">${item.is_trade ? 'TRADE' : item.level}</span>
                <span class="log-sym">${symTag}</span>
                <span class="log-msg ${tradeMsgClass}">${escapeHtml(item.message)}</span>
            `;
            return row;
        }

        function rerenderLogs() {
            logBody.innerHTML = '';
            const filtered = allLogs.filter(matchesFilter);
            filtered.forEach(item => logBody.appendChild(createLogRow(item)));
            if (countBadge) countBadge.textContent = `${filtered.length} logs`;
            if (autoScroll) logBody.scrollTop = logBody.scrollHeight;
        }

        function appendLog(item) {
            allLogs.push(item);
            if (allLogs.length > 2000) allLogs.shift();

            if (matchesFilter(item)) {
                logBody.appendChild(createLogRow(item));
                if (countBadge) countBadge.textContent = `${logBody.children.length} logs`;
                if (autoScroll) logBody.scrollTop = logBody.scrollHeight;
            }

            if (drawer.classList.contains('collapsed')) {
                unreadCount++;
                if (unreadBadge) unreadBadge.textContent = String(unreadCount);
            }
        }

        // Connect SSE Stream
        try {
            const evtSource = new EventSource('/api/logs/stream');
            evtSource.onmessage = e => {
                try {
                    const item = JSON.parse(e.data);
                    appendLog(item);
                } catch (err) { }
            };
        } catch (e) {
            console.warn('SSE not supported, polling logs instead.');
            let lastId = 0;
            setInterval(() => {
                fetch(`/api/logs?since_id=${lastId}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data && data.logs && Array.isArray(data.logs)) {
                            data.logs.forEach(appendLog);
                            lastId = data.latest_id || lastId;
                        }
                    })
                    .catch(() => { });
            }, 2000);
        }
    }

    // Helper utilities
    function getVal(id) { const el = document.getElementById(id); return el ? el.value : ''; }
    function setVal(id, v) { const el = document.getElementById(id); if (el && v !== undefined && v !== null) el.value = v; }
    function getChecked(id) { const el = document.getElementById(id); return el ? el.checked : false; }
    function setChecked(id, b) { const el = document.getElementById(id); if (el && b !== undefined) el.checked = Boolean(b); }
    function escapeHtml(str) {
        return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }


    // ── Kick off ──
    init();
    window.ChartManager = {
        loadChartData,
        loadRenkoData,
        STATE
    };
}

// Bulletproof DOM-ready guard
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startApp);
} else {
    startApp();
}
