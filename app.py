"""
RK Renko V4 // Quant Trading Grid - High-Performance FastAPI Application
Serves:
- White Theme Multi-Pane Trading Dashboard
- Real-time Renko Brick Builder & Timeline API
- Multi-Symbol Bot Control & Dynamic Runtime Parameter Tuning
- Server-Sent Events (SSE) Live Terminal Console Log Streaming
- MT5 Trading Operations & Live Market Feeds
"""

import os
import sys
import json
import queue
import asyncio
import logging
from typing import Optional, Dict, Any

# Windows asyncio ProactorEventLoop fix: Suppress harmless WinError 10054 on client disconnect
if sys.platform == "win32":
    from asyncio.proactor_events import _ProactorBasePipeTransport
    _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

    def _silence_proactor_connection_lost(self, exc=None):
        try:
            _orig_call_connection_lost(self, exc)
        except ConnectionResetError:
            pass
        except OSError as e:
            if getattr(e, "winerror", None) in (10054, 10053):
                pass
            else:
                raise

    _ProactorBasePipeTransport._call_connection_lost = _silence_proactor_connection_lost

from fastapi import FastAPI, Request, Query, Body, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# Ensure MT5Renko workspace root is on sys.path
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from data_source import data_source
from core.bot_manager import bot_manager, log_ring_buffer
import core.ta_engine as ta_engine

# Setup application logging
logger = logging.getLogger("app")

# Initialize FastAPI App
app = FastAPI(
    title="RK Renko V4 // Quant Trading Grid",
    description="Multi-pane real-time Renko trading dashboard with bot controls and MT5 integration",
    version="4.0.0",
)

# Ensure static & templates directory exist
os.makedirs(os.path.join(WORKSPACE_DIR, "templates"), exist_ok=True)
os.makedirs(os.path.join(WORKSPACE_DIR, "static", "css"), exist_ok=True)
os.makedirs(os.path.join(WORKSPACE_DIR, "static", "js"), exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=os.path.join(WORKSPACE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(WORKSPACE_DIR, "templates"))


# ==============================================================================
# Web Page Routing
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Renders the main white-themed multi-pane Renko trading dashboard."""
    return templates.TemplateResponse(request=request, name="index.html")


# ==============================================================================
# Market Data Endpoints
# ==============================================================================

@app.get("/api/test_mt5")
async def test_mt5():
    """Validates MT5 connection, trade permissions, and account equity."""
    try:
        status_info = data_source.test_mt5_connection()
        return JSONResponse(status_info)
    except Exception as e:
        logger.error(f"Error testing MT5 connection: {e}")
        return JSONResponse({"status": "error", "message": f"Server error: {e}"}, status_code=500)


@app.get("/api/historical")
async def historical(
    source: str = Query(..., description="Data source: mt5, yfinance, hyperliquid"),
    symbol: str = Query(..., description="Instrument symbol (e.g. GBPUSD, XAUUSD)"),
    timeframe: str = Query("5m", description="Timeframe: 1m, 5m, 15m, 1h, 4h, 1d"),
    limit: int = Query(300, description="Number of candles"),
    before: Optional[int] = Query(None, description="Unix timestamp limit for older candles"),
):
    """Fetches historical OHLC candle data."""
    try:
        candles = data_source.get_historical_candles(source, symbol, timeframe, limit, before)
        return JSONResponse(candles)
    except Exception as e:
        logger.error(f"Error fetching historical candles: {e}")
        return JSONResponse({"error": f"Failed to retrieve data: {e}"}, status_code=500)


@app.get("/api/live")
async def live(
    source: str = Query(..., description="Data source: mt5, yfinance, hyperliquid"),
    symbol: str = Query(..., description="Instrument symbol"),
):
    """Fetches real-time price tick."""
    try:
        price_data = data_source.get_live_price(source, symbol)
        if price_data:
            return JSONResponse(price_data)
        return JSONResponse({"error": f"No live price data for {symbol} on {source}."}, status_code=404)
    except Exception as e:
        logger.error(f"Error fetching live price: {e}")
        return JSONResponse({"error": f"Failed to retrieve live price: {e}"}, status_code=500)


@app.get("/api/symbol_format")
async def symbol_format(
    source: str = Query("mt5", description="Data source"),
    symbol: str = Query("GBPUSD", description="Instrument symbol"),
):
    """Returns price precision (digits) and minMove (point step)."""
    try:
        precision, min_move = data_source.get_symbol_format(source, symbol)
        return JSONResponse({"precision": precision, "minMove": min_move})
    except Exception as e:
        logger.error(f"Error getting symbol format: {e}")
        return JSONResponse({"precision": 5, "minMove": 0.00001})


# ==============================================================================
# Renko Engine & Timeline Endpoints
# ==============================================================================

@app.get("/api/renko")
async def get_renko(
    symbol: str = Query("GBPUSD", description="Instrument symbol"),
    mode: str = Query("1m", description="Renko mode: 1m or tick"),
    brick_size: Optional[float] = Query(None, description="Custom brick size or null for dynamic ATR"),
    limit: int = Query(300, description="Max bricks to return"),
    timeline_mode: str = Query("equidistant", description="Timeline mode: equidistant or real"),
):
    """
    Constructs Renko bricks, Supertrend(1, 3.1), EMA 5/9, and Reference Zones.
    Equidistant timeline guarantees uniform visual brick dimensions in Lightweight Charts.
    """
    try:
        data = bot_manager.get_renko_chart_data(
            symbol=symbol,
            mode=mode,
            brick_size=brick_size,
            limit=limit,
            timeline_mode=timeline_mode,
        )
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error generating Renko chart data for {symbol}: {e}")
        return JSONResponse({"error": f"Renko generation failed: {e}"}, status_code=500)


# ==============================================================================
# pandas_ta Universal Indicator Calculation & Catalog Endpoints
# ==============================================================================

@app.get("/api/indicators/catalog")
async def get_indicators_catalog():
    """
    Returns full catalog of supported indicators across all categories,
    including parameters, types, defaults, inputs, and kind (overlay vs oscillator).
    """
    try:
        catalog = ta_engine.get_indicator_catalog()
        return JSONResponse(catalog)
    except Exception as e:
        logger.error(f"Error fetching indicator catalog: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/indicators/compute")
async def compute_indicator_post(payload: dict = Body(...)):
    """
    Computes an indicator dynamically on provided market candles or Renko bricks.
    Accepts custom user parameters, handles warm-up periods gracefully,
    and returns timestamp-aligned series with JSON-safe sanitization.
    """
    indicator_id = payload.get("indicator")
    if not indicator_id:
        raise HTTPException(status_code=400, detail="Missing 'indicator' parameter.")

    info = ta_engine.get_indicator_info(indicator_id)
    if not info:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown indicator '{indicator_id}'. Check /api/indicators/catalog.",
        )

    params = payload.get("params", {})
    candles = payload.get("candles")
    renko_params = payload.get("renko_params")

    if candles is not None:
        try:
            df, bar_times = ta_engine.prepare_dataframe(candles)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid candle data: {e}")
    elif renko_params is not None:
        try:
            df, bar_times = ta_engine.prepare_renko_dataframe(renko_params)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to generate Renko bricks: {e}")
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either 'candles' array or 'renko_params'.",
        )

    try:
        result = ta_engine.compute_indicator(
            indicator_id=indicator_id,
            df=df,
            bar_times=bar_times,
            params=params,
        )
        return JSONResponse(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error computing indicator {indicator_id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/indicators/compute")
async def compute_indicator_get(
    request: Request,
    indicator: str = Query(..., description="Indicator identifier (e.g. rsi, bbands)"),
    symbol: Optional[str] = Query("GBPUSD", description="Instrument symbol for Renko mode"),
    brick_size: Optional[float] = Query(None, description="Custom brick size"),
    timeline_mode: str = Query("equidistant", description="Timeline mode: equidistant or real"),
    limit: int = Query(300, description="Max bars/bricks to compute on"),
):
    """
    Simple GET endpoint for computing an indicator directly on current Renko bricks.
    Additional query parameters (e.g. length=14, std=2.0) are forwarded to the indicator.
    """
    info = ta_engine.get_indicator_info(indicator)
    if not info:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown indicator '{indicator}'. Check /api/indicators/catalog.",
        )

    # Extract extra query parameters as indicator params
    ignored_params = {"indicator", "symbol", "brick_size", "timeline_mode", "limit"}
    params = {}
    for k, v in request.query_params.items():
        if k not in ignored_params:
            params[k] = v

    renko_params = {
        "symbol": symbol,
        "brick_size": brick_size,
        "timeline_mode": timeline_mode,
        "limit": limit,
    }

    try:
        df, bar_times = ta_engine.prepare_renko_dataframe(renko_params)
        result = ta_engine.compute_indicator(
            indicator_id=indicator,
            df=df,
            bar_times=bar_times,
            params=params,
        )
        return JSONResponse(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error computing indicator {indicator}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ==============================================================================
# Multi-Symbol Bot Control & Parameter Adjustments
# ==============================================================================

@app.get("/api/bot/status")
async def bot_status(symbol: Optional[str] = Query(None, description="Symbol name or null for all")):
    """Returns real-time telemetry snapshot for one or all bots."""
    try:
        status_data = bot_manager.get_status(symbol)
        return JSONResponse(status_data)
    except Exception as e:
        logger.error(f"Error querying bot status: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/bot/start")
async def bot_start(payload: dict = Body(...)):
    """Starts a bot thread for a given symbol."""
    symbol = payload.get("symbol")
    live = payload.get("live", False)
    mode = payload.get("mode", "1m")
    if not symbol:
        raise HTTPException(status_code=400, detail="Missing 'symbol' parameter.")
    res = bot_manager.start_bot(symbol=symbol, live=live, mode=mode)
    return JSONResponse(res)


@app.post("/api/bot/stop")
async def bot_stop(payload: dict = Body(...)):
    """Stops a running bot for a given symbol."""
    symbol = payload.get("symbol")
    if not symbol:
        raise HTTPException(status_code=400, detail="Missing 'symbol' parameter.")
    res = bot_manager.stop_bot(symbol=symbol)
    return JSONResponse(res)


@app.post("/api/bot/start_all")
async def bot_start_all(payload: dict = Body(default={})):
    """Starts all 7 configured bots simultaneously."""
    live = payload.get("live", False)
    mode = payload.get("mode", "1m")
    res = bot_manager.start_all(live=live, mode=mode)
    return JSONResponse(res)


@app.post("/api/bot/stop_all")
async def bot_stop_all():
    """Stops all running bots."""
    res = bot_manager.stop_all()
    return JSONResponse(res)


@app.post("/api/bot/emergency_close")
async def emergency_close():
    """Panic button: closes all open positions across all bots."""
    res = bot_manager.emergency_close_all()
    return JSONResponse(res)


@app.get("/api/bot/config")
async def bot_config(symbol: str = Query(..., description="Symbol name")):
    """Fetches current configurable parameters for a symbol."""
    try:
        cfg = bot_manager.get_config(symbol)
        return JSONResponse(cfg)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/bot/adjust")
async def bot_adjust(payload: dict = Body(...)):
    """
    Applies runtime adjustments (SL, TP, trailing, zones, confluence, brick size)
    to a specific symbol or ALL symbols without restarting the process.
    """
    symbol = payload.get("symbol", "ALL")
    params = payload.get("params", {})
    if not params:
        raise HTTPException(status_code=400, detail="Missing 'params' dictionary.")
    res = bot_manager.update_config(symbol=symbol, params=params)
    return JSONResponse(res)


# ==============================================================================
# Live Terminal Console Log Endpoints (REST & SSE Stream)
# ==============================================================================

@app.get("/api/logs")
async def get_logs(
    since_id: int = Query(0, description="Fetch records after this ID"),
    symbol: Optional[str] = Query(None, description="Filter by symbol or ALL"),
    level: Optional[str] = Query(None, description="Filter by level or ALL/TRADES"),
    limit: int = Query(200, description="Max logs to return"),
):
    """REST endpoint to fetch historical logs from the ring buffer."""
    logs = log_ring_buffer.get_logs(since_id=since_id, symbol=symbol, level=level, limit=limit)
    return JSONResponse({"logs": logs, "latest_id": log_ring_buffer.counter})


@app.get("/api/logs/stream")
async def stream_logs(request: Request):
    """
    Server-Sent Events (SSE) endpoint: streams real-time terminal console logs
    to connected frontend clients with sub-second latency.
    """
    sub_queue = log_ring_buffer.subscribe()

    async def event_generator():
        try:
            # First send recent backlog (last 50 logs)
            backlog = log_ring_buffer.get_logs(limit=50)
            for item in backlog:
                yield f"data: {json.dumps(item)}\n\n"

            # Stream incoming logs in real-time
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Non-blocking get with timeout to allow disconnect checking
                    item = sub_queue.get_nowait()
                    yield f"data: {json.dumps(item)}\n\n"
                except queue.Empty:
                    # Keep-alive heartbeat comment every second
                    await asyncio.sleep(0.5)
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            log_ring_buffer.unsubscribe(sub_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ==============================================================================
# MT5 Manual Trading Endpoints
# ==============================================================================

@app.get("/api/trading/state")
async def trading_state(
    source: str = Query("mt5", description="Data source"),
    symbol: Optional[str] = Query(None, description="Symbol filter"),
):
    if source != "mt5":
        return JSONResponse({"positions": [], "orders": [], "error": "Trading only supported for MT5"})
    state = data_source.get_active_orders(symbol)
    return JSONResponse(state)


@app.post("/api/trading/place")
async def trading_place(payload: dict = Body(...)):
    symbol = payload.get("symbol")
    order_type = payload.get("type")
    volume = payload.get("volume")
    price = payload.get("price")
    sl = payload.get("sl")
    tp = payload.get("tp")
    if not symbol or not order_type or not volume:
        raise HTTPException(status_code=400, detail="Missing required order fields.")
    res = data_source.place_order(symbol, order_type, volume, price, sl, tp)
    return JSONResponse(res, status_code=200 if res.get("status") == "success" else 400)


@app.post("/api/trading/modify")
async def trading_modify(payload: dict = Body(...)):
    ticket = payload.get("ticket")
    is_position = payload.get("is_position", False)
    price = payload.get("price")
    sl = payload.get("sl")
    tp = payload.get("tp")
    if not ticket:
        raise HTTPException(status_code=400, detail="Missing ticket ID.")
    res = data_source.modify_order(ticket, is_position, price, sl, tp)
    return JSONResponse(res, status_code=200 if res.get("status") == "success" else 400)


@app.post("/api/trading/cancel")
async def trading_cancel(payload: dict = Body(...)):
    ticket = payload.get("ticket")
    is_position = payload.get("is_position", False)
    symbol = payload.get("symbol")
    volume = payload.get("volume")
    order_type = payload.get("type")
    if not ticket:
        raise HTTPException(status_code=400, detail="Missing ticket ID.")
    res = data_source.cancel_order(ticket, is_position, symbol, volume, order_type)
    return JSONResponse(res, status_code=200 if res.get("status") == "success" else 400)


@app.post("/api/log_error")
async def log_error(payload: dict = Body(...)):
    """Logs client-side browser errors."""
    logger.error(f"CLIENT ERROR: {payload.get('message')} at {payload.get('source')}:{payload.get('lineno')}")
    return JSONResponse({"status": "ok"})


# ==============================================================================
# Server Entrypoint
# ==============================================================================

if __name__ == "__main__":
    logger.info("Starting RK Renko V4 FastAPI server on http://127.0.0.1:3000 ...")
    uvicorn.run(app, host="127.0.0.1", port=3000, reload=False)
