"""
RK Renko V4 - Technical Indicators Engine
Includes:
- Supertrend(1, 3.1) calculated on Renko Brick Closes
- Renko EMA 5 and EMA 9
- 1H EMA 50 Macro Trend Filter
- AI Smart Renko (dr_devendra_ai_smart_renko) on M1 bars
Zero external folder dependencies.
"""

from typing import List, Optional, Tuple
import datetime
import math
from .renko import RenkoBrick


class Supertrend:
    """
    Supertrend indicator calculated over Renko brick stream.
    Default parameters: length = 1, multiplier = 3.1
    """
    def __init__(self, length: int = 1, multiplier: float = 3.1):
        self.length = length
        self.multiplier = multiplier
        self.direction: int = 0  # +1 Bullish, -1 Bearish
        self.value: float = 0.0
        self.upper_band: float = 0.0
        self.lower_band: float = 0.0
        self._prev_close: Optional[float] = None
        self._prev_upper: Optional[float] = None
        self._prev_lower: Optional[float] = None

    def update(self, brick: RenkoBrick) -> Tuple[int, float]:
        """
        Update Supertrend with a new Renko brick.
        Returns: (direction: +1/-1, supertrend_line_value)
        """
        # True Range for Renko brick
        if self._prev_close is None:
            tr = brick.high - brick.low
        else:
            tr = max(
                brick.high - brick.low,
                abs(brick.high - self._prev_close),
                abs(brick.low - self._prev_close),
            )

        hl2 = (brick.high + brick.low) / 2.0
        basic_upper = hl2 + (self.multiplier * tr)
        basic_lower = hl2 - (self.multiplier * tr)

        # Final Upper Band
        if self._prev_upper is None or basic_upper < self._prev_upper or (self._prev_close and self._prev_close > self._prev_upper):
            final_upper = basic_upper
        else:
            final_upper = self._prev_upper

        # Final Lower Band
        if self._prev_lower is None or basic_lower > self._prev_lower or (self._prev_close and self._prev_close < self._prev_lower):
            final_lower = basic_lower
        else:
            final_lower = self._prev_lower

        # Direction calculation
        if self.direction == 0:
            # Initial direction from brick direction
            self.direction = 1 if brick.close >= brick.open else -1
            self.value = final_lower if self.direction == 1 else final_upper
        elif self.direction == 1:
            if brick.close < final_lower:
                self.direction = -1
                self.value = final_upper
            else:
                self.value = final_lower
        else:  # direction == -1
            if brick.close > final_upper:
                self.direction = 1
                self.value = final_lower
            else:
                self.value = final_upper

        self.upper_band = final_upper
        self.lower_band = final_lower
        self._prev_close = brick.close
        self._prev_upper = final_upper
        self._prev_lower = final_lower

        return self.direction, self.value


class RenkoEMA:
    """Calculates EMA incrementally on Renko brick Close prices."""
    def __init__(self, period: int):
        self.period = period
        self.alpha = 2.0 / (period + 1.0)
        self.value: Optional[float] = None

    def update(self, close_price: float) -> float:
        if self.value is None:
            self.value = close_price
        else:
            self.value = (close_price * self.alpha) + (self.value * (1.0 - self.alpha))
        return self.value


class H1MacroEMA50:
    """
    Tracks and caches the 50-period EMA on 1-Hour candles.
    Cached for up to 60 seconds to minimize MT5 API calls.
    """
    def __init__(self, period: int = 50, cache_ttl_seconds: int = 60):
        self.period = period
        self.cache_ttl = cache_ttl_seconds
        self.cached_ema: Optional[float] = None
        self.last_fetch_time: Optional[datetime.datetime] = None

    def calculate_from_closes(self, closes: List[float]) -> Optional[float]:
        if len(closes) < self.period:
            return None
        # Standard EMA calculation
        k = 2.0 / (self.period + 1.0)
        ema = sum(closes[:self.period]) / self.period
        for close in closes[self.period:]:
            ema = (close * k) + (ema * (1.0 - k))
        return ema


class DrDevendraAISmartRenko:
    """
    Dr Devendra AI Smart Renko V1.1 (faithful Python implementation of Pine Script V1.1)
    
    Includes:
    - Session-based ATR(5) sizing / Wilder RMA / operating divisor (6.0) & intraday divisor (2.0)
    - Synthetic Renko brick engine: 2-box reversal, 1-box continuation
    - Per-brick smoothed ATR and AI Supertrend (stFactor=3.1, atrSmoothLength=15)
    - DMI & ADX(14, 14) regime filter with threshold=15.0
    - Signals: Bullish reversal, Bearish reversal, Filtered flips (×)
    """
    def __init__(
        self,
        operating_divisor: float = 6.0,
        intraday_divisor: float = 2.0,
        manual_brick: float = 0.0,
        atr_length: int = 14,
        st_factor: float = 3.1,
        atr_smooth_length: int = 15,
        di_length: int = 14,
        adx_smoothing: int = 14,
        adx_threshold: float = 15.0,
        use_adx_filter: bool = True,
        require_di_direction: bool = False,
        **kwargs,
    ):
        self.operating_divisor = float(operating_divisor)
        self.intraday_divisor = float(intraday_divisor)
        self.manual_brick = float(manual_brick)
        self.atr_length = int(kwargs.get("atr_period", atr_length))
        self.st_factor = float(kwargs.get("st_mult", st_factor))
        self.atr_smooth_length = int(atr_smooth_length)
        self.di_length = int(di_length)
        self.adx_smoothing = int(adx_smoothing)
        self.adx_threshold = float(adx_threshold)
        self.use_adx_filter = bool(use_adx_filter)
        self.require_di_direction = bool(require_di_direction)

        self.bars_count = 0
        self.status = "WARMUP"
        self.direction = 0  # +1 Bullish, -1 Bearish, 0 Chop/Filtered

        # Session tracking state
        self.daily_sizing_atr5: Optional[float] = None
        self.completed_atr5: Optional[float] = None
        self._current_date_key: Optional[int] = None
        self._session_trs: List[float] = []
        self._prev_source_close: Optional[float] = None
        self._main_high: Optional[float] = None
        self._main_low: Optional[float] = None
        self._main_close: Optional[float] = None
        self._rem_high: Optional[float] = None
        self._rem_low: Optional[float] = None
        self._rem_close: Optional[float] = None

        # Bar state
        self._prev_close: Optional[float] = None
        self._prev_high: Optional[float] = None
        self._prev_low: Optional[float] = None

        # DMI / ADX Wilder RMA state
        self._smooth_tr: float = 0.0
        self._smooth_plus_dm: float = 0.0
        self._smooth_minus_dm: float = 0.0
        self.di_plus: float = 0.0
        self.di_minus: float = 0.0
        self.adx: float = 0.0
        self._dx_history: List[float] = []

        # Candle ATR RMA state
        self.candle_atr: float = 0.0
        self._candle_atr_rma: float = 0.0

        # Synthetic Renko & Supertrend state
        self.brick_size: float = 0.0
        self.renko_close: Optional[float] = None
        self.renko_direction: int = 0
        self.brick_atr_ema: Optional[float] = None
        self.final_upper: Optional[float] = None
        self.final_lower: Optional[float] = None
        self.st_direction: int = 1
        self.emitted_bricks: int = 0

        # Flip & Signal flags from latest bar
        self.bullish_flip: bool = False
        self.bearish_flip: bool = False
        self.bull_signal: bool = False
        self.bear_signal: bool = False
        self.bull_rejected: bool = False
        self.bear_rejected: bool = False

    @property
    def st_line(self) -> Optional[float]:
        if self.final_upper is None or self.final_lower is None:
            return None
        return self.final_lower if self.st_direction == 1 else self.final_upper

    @property
    def regime(self) -> str:
        if self.bars_count < max(self.atr_length, self.di_length) + 5:
            return "WARMUP"
        return "TREND" if self.adx >= self.adx_threshold else "CHOP / FILTERED"

    def _update_dmi_adx(self, high: float, low: float, close: float):
        """Calculates Wilder RMA DMI (diPlus, diMinus) and ADX."""
        if self._prev_close is None or self._prev_high is None or self._prev_low is None:
            return

        tr = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))
        up_move = high - self._prev_high
        down_move = self._prev_low - low

        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0

        # Candle ATR update via Wilder RMA (alpha = 1 / atr_length)
        alpha_atr = 1.0 / self.atr_length
        if self.bars_count <= self.atr_length:
            self._candle_atr_rma += tr
            self.candle_atr = self._candle_atr_rma / self.bars_count
        else:
            self.candle_atr = (alpha_atr * tr) + ((1.0 - alpha_atr) * self.candle_atr)

        # DMI Wilder RMA
        alpha_di = 1.0 / self.di_length
        if self.bars_count <= self.di_length:
            self._smooth_tr += tr
            self._smooth_plus_dm += plus_dm
            self._smooth_minus_dm += minus_dm
            sm_tr = self._smooth_tr / self.bars_count
            sm_plus = self._smooth_plus_dm / self.bars_count
            sm_minus = self._smooth_minus_dm / self.bars_count
        else:
            self._smooth_tr = (alpha_di * tr) + ((1.0 - alpha_di) * self._smooth_tr)
            self._smooth_plus_dm = (alpha_di * plus_dm) + ((1.0 - alpha_di) * self._smooth_plus_dm)
            self._smooth_minus_dm = (alpha_di * minus_dm) + ((1.0 - alpha_di) * self._smooth_minus_dm)
            sm_tr = self._smooth_tr
            sm_plus = self._smooth_plus_dm
            sm_minus = self._smooth_minus_dm

        if sm_tr > 1e-9:
            self.di_plus = 100.0 * (sm_plus / sm_tr)
            self.di_minus = 100.0 * (sm_minus / sm_tr)
            di_sum = self.di_plus + self.di_minus
            dx = 100.0 * abs(self.di_plus - self.di_minus) / di_sum if di_sum > 0 else 0.0
        else:
            self.di_plus = 0.0
            self.di_minus = 0.0
            dx = 0.0

        alpha_adx = 1.0 / self.adx_smoothing
        if len(self._dx_history) < self.adx_smoothing:
            self._dx_history.append(dx)
            self.adx = sum(self._dx_history) / len(self._dx_history)
        else:
            self.adx = (alpha_adx * dx) + ((1.0 - alpha_adx) * self.adx)

    def _determine_brick_size(self, close: float) -> float:
        """Determines active Renko brick size from manual or session/daily ATR."""
        if self.manual_brick > 0:
            return max(0.01, round(self.manual_brick, 4))

        if self.daily_sizing_atr5 and self.daily_sizing_atr5 > 0:
            day_brick = self.daily_sizing_atr5 / self.operating_divisor
            candidate = day_brick / self.intraday_divisor
            return max(0.01, round(candidate, 4))

        # Fallback for Forex/Crypto/24h when no fixed NSE session is detected:
        # Scale dynamically from current candle ATR: ATR / (operating * intraday)
        base_atr = self.candle_atr if self.candle_atr > 0 else (close * 0.001)
        # 14-period M1 ATR scaled to represent typical operating swing
        day_est = base_atr * 5.0
        candidate = (day_est / self.operating_divisor) / self.intraday_divisor
        return max(0.0001 if close < 10 else 0.01, round(candidate, 5))

    def update_m1_bar(
        self,
        open_: float,
        high: float,
        low: float,
        close: float,
        timestamp: Optional[datetime.datetime] = None,
    ) -> Tuple[str, int]:
        """
        Processes a confirmed 1-minute OHLC bar.
        Updates DMI, ADX, session ATR, synthetic Renko bricks, and AI Supertrend.
        Returns: (status: 'READY'|'WARMUP', direction: +1|-1|0)
        """
        self.bars_count += 1
        self.bullish_flip = False
        self.bearish_flip = False
        self.bull_signal = False
        self.bear_signal = False
        self.bull_rejected = False
        self.bear_rejected = False

        if self._prev_close is None:
            self._prev_close = close
            self._prev_high = high
            self._prev_low = low
            return self.status, self.direction

        # 1. Update DMI, ADX, and Candle ATR
        self._update_dmi_adx(high, low, close)

        # 2. Session true-range tracking (if timestamp provided)
        if timestamp:
            minute_of_day = timestamp.hour * 60 + timestamp.minute
            date_key = timestamp.year * 10000 + timestamp.month * 100 + timestamp.day
            if self._current_date_key != date_key:
                self._current_date_key = date_key
                if self.completed_atr5:
                    self.daily_sizing_atr5 = self.completed_atr5

            in_main = (minute_of_day >= 555 and minute_of_day < 915)      # 09:15 - 15:15
            in_rem = (minute_of_day >= 915 and minute_of_day < 930)       # 15:15 - 15:30

            if in_main:
                self._main_high = high if self._main_high is None else max(self._main_high, high)
                self._main_low = low if self._main_low is None else min(self._main_low, low)
                self._main_close = close
            elif self._main_high is not None and self._main_low is not None and self._main_close is not None:
                tr = self._main_high - self._main_low if self._prev_source_close is None else max(
                    self._main_high - self._main_low,
                    abs(self._main_high - self._prev_source_close),
                    abs(self._main_low - self._prev_source_close),
                )
                self._prev_source_close = self._main_close
                self._session_trs.append(tr)
                if len(self._session_trs) >= 5:
                    # Wilder RMA of session TRs
                    alpha = 1.0 / 5.0
                    self.completed_atr5 = sum(self._session_trs[:5]) / 5.0 if self.completed_atr5 is None else (
                        alpha * tr + (1.0 - alpha) * self.completed_atr5
                    )
                self._main_high, self._main_low, self._main_close = None, None, None

            if in_rem:
                self._rem_high = high if self._rem_high is None else max(self._rem_high, high)
                self._rem_low = low if self._rem_low is None else min(self._rem_low, low)
                self._rem_close = close
            elif self._rem_high is not None and self._rem_low is not None and self._rem_close is not None:
                tr = self._rem_high - self._rem_low if self._prev_source_close is None else max(
                    self._rem_high - self._rem_low,
                    abs(self._rem_high - self._prev_source_close),
                    abs(self._rem_low - self._prev_source_close),
                )
                self._prev_source_close = self._rem_close
                self._session_trs.append(tr)
                if len(self._session_trs) >= 5:
                    alpha = 1.0 / 5.0
                    self.completed_atr5 = sum(self._session_trs[:5]) / 5.0 if self.completed_atr5 is None else (
                        alpha * tr + (1.0 - alpha) * self.completed_atr5
                    )
                self._rem_high, self._rem_low, self._rem_close = None, None, None

        # 3. Determine active brick size
        self.brick_size = self._determine_brick_size(close)

        # 4. Synthetic Renko construction (2-box reversal, 1-box continuation)
        src = close
        if self.brick_size > 0 and self.candle_atr > 0:
            if self.renko_close is None:
                self.renko_close = round(src / self.brick_size) * self.brick_size
            else:
                delta = src - self.renko_close
                move_dir = 1 if delta >= 0 else -1
                boxes_moved = int(math.floor(abs(delta) / self.brick_size))
                is_reversal = (self.renko_direction != 0 and move_dir != self.renko_direction)
                threshold_boxes = 2 if is_reversal else 1

                if boxes_moved >= threshold_boxes:
                    bricks_to_emit = (boxes_moved - 1) if is_reversal else boxes_moved
                    for i in range(bricks_to_emit):
                        prev_close = self.renko_close
                        step_size = 2.0 if (is_reversal and i == 0) else 1.0
                        next_close = prev_close + move_dir * self.brick_size * step_size
                        brick_open = (prev_close + move_dir * self.brick_size) if (is_reversal and i == 0) else prev_close
                        brick_high = max(brick_open, next_close)
                        brick_low = min(brick_open, next_close)
                        brick_mid = (brick_high + brick_low) / 2.0

                        # Smooth candle ATR once per emitted Renko brick
                        alpha_st = 2.0 / (self.atr_smooth_length + 1.0)
                        self.brick_atr_ema = self.candle_atr if self.brick_atr_ema is None else (
                            self.brick_atr_ema + alpha_st * (self.candle_atr - self.brick_atr_ema)
                        )

                        basic_upper = brick_mid + (self.st_factor * self.brick_atr_ema)
                        basic_lower = brick_mid - (self.st_factor * self.brick_atr_ema)
                        prior_upper = self.final_upper
                        prior_lower = self.final_lower
                        prior_trend = self.st_direction

                        if prior_lower is not None and prior_trend == 1 and next_close < prior_lower:
                            self.st_direction = -1
                            self.bearish_flip = True
                        elif prior_upper is not None and prior_trend == -1 and next_close > prior_upper:
                            self.st_direction = 1
                            self.bullish_flip = True

                        if prior_upper is None or basic_upper < prior_upper or prev_close > prior_upper:
                            self.final_upper = basic_upper
                        else:
                            self.final_upper = prior_upper

                        if prior_lower is None or basic_lower > prior_lower or prev_close < prior_lower:
                            self.final_lower = basic_lower
                        else:
                            self.final_lower = prior_lower

                        self.renko_close = next_close
                        self.renko_direction = move_dir
                        self.emitted_bricks += 1

        # 5. ADX Regime Filter & Signal Confirmation
        adx_trending = self.adx >= self.adx_threshold
        bull_di_agrees = (not self.require_di_direction) or (self.di_plus > self.di_minus)
        bear_di_agrees = (not self.require_di_direction) or (self.di_minus > self.di_plus)

        bull_filter_pass = (not self.use_adx_filter) or (adx_trending and bull_di_agrees)
        bear_filter_pass = (not self.use_adx_filter) or (adx_trending and bear_di_agrees)

        self.bull_signal = self.bullish_flip and bull_filter_pass
        self.bear_signal = self.bearish_flip and bear_filter_pass
        self.bull_rejected = self.bullish_flip and not bull_filter_pass
        self.bear_rejected = self.bearish_flip and not bear_filter_pass

        # 6. Overall Engine Status & Direction
        min_bars_needed = max(self.atr_length, self.di_length) + 10
        if self.bars_count >= min_bars_needed:
            self.status = "READY"
            if self.st_direction == 1 and bull_filter_pass:
                self.direction = 1
            elif self.st_direction == -1 and bear_filter_pass:
                self.direction = -1
            else:
                self.direction = 0  # Filtered / Chop
        else:
            self.status = "WARMUP"
            self.direction = 0

        self._prev_close = close
        self._prev_high = high
        self._prev_low = low
        return self.status, self.direction


# Backward-compatible alias for existing imports in bot_engine and test suites
AIPreRenkoEngine = DrDevendraAISmartRenko


class Indicators:
    """Consolidated Indicators container for a symbol's Renko stream."""
    def __init__(self):
        self.supertrend = Supertrend(length=1, multiplier=3.1)
        self.ema5 = RenkoEMA(period=5)
        self.ema9 = RenkoEMA(period=9)
        self.h1_ema50 = H1MacroEMA50(period=50)
        self.ai_renko = AIPreRenkoEngine(atr_period=14, st_mult=3.1, adx_threshold=15.0)

    def on_new_brick(self, brick: RenkoBrick) -> dict:
        st_dir, st_val = self.supertrend.update(brick)
        ema5_val = self.ema5.update(brick.close)
        ema9_val = self.ema9.update(brick.close)

        return {
            "st_direction": st_dir,
            "st_value": st_val,
            "ema5": ema5_val,
            "ema9": ema9_val,
            "brick_close": brick.close,
            "bar_num": brick.bar_num,
        }
