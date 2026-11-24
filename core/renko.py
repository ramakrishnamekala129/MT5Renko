"""
Renko Brick Engine
Constructs Renko bricks using 1-box continuation and 2-box reversal logic.
Maintains brick streak counters (bar_num).
Zero external folder dependencies.
"""

from dataclasses import dataclass
from typing import List, Optional
import datetime


@dataclass
class RenkoBrick:
    index: int
    timestamp: datetime.datetime
    open: float
    high: float
    low: float
    close: float
    direction: int     # +1 for UP (green), -1 for DOWN (red)
    bar_num: int       # Streak: +1, +2, +3... or -1, -2, -3...
    is_reversal: bool  # True if this brick was formed by a 2-box reversal


class RenkoEngine:
    def __init__(self, brick_size: float):
        if brick_size <= 0:
            raise ValueError(f"brick_size must be positive, got {brick_size}")
        self.brick_size = float(brick_size)
        self.bricks: List[RenkoBrick] = []
        self._last_brick_close: Optional[float] = None
        self._current_direction: int = 0
        self._bar_num: int = 0

    def reset(self, brick_size: Optional[float] = None):
        """Reset the engine state, optionally updating brick_size."""
        if brick_size is not None and brick_size > 0:
            self.brick_size = float(brick_size)
        self.bricks.clear()
        self._last_brick_close = None
        self._current_direction = 0
        self._bar_num = 0

    @property
    def latest_brick(self) -> Optional[RenkoBrick]:
        return self.bricks[-1] if self.bricks else None

    @property
    def bar_num(self) -> int:
        return self._bar_num

    @property
    def current_direction(self) -> int:
        return self._current_direction

    def initialize_from_price(self, price: float, timestamp: datetime.datetime):
        """Initial baseline price point to start Renko construction."""
        if not self.bricks and self._last_brick_close is None:
            self._last_brick_close = round(price, 6)

    def process_price(self, price: float, timestamp: datetime.datetime) -> List[RenkoBrick]:
        """
        Process a new price tick or candle close.
        Returns a list of any newly completed Renko bricks formed by this price.
        """
        new_bricks: List[RenkoBrick] = []

        if self._last_brick_close is None:
            self._last_brick_close = round(price, 6)
            return new_bricks

        # Iterate in case price moved multiple bricks in a single tick or bar
        while True:
            if self._current_direction == 0:
                # Initial brick setup: requires at least 1 brick size move in either direction
                diff = price - self._last_brick_close
                if diff >= self.brick_size:
                    close_val = round(self._last_brick_close + self.brick_size, 6)
                    self._current_direction = 1
                    self._bar_num = 1
                    brick = RenkoBrick(
                        index=len(self.bricks),
                        timestamp=timestamp,
                        open=self._last_brick_close,
                        high=close_val,
                        low=self._last_brick_close,
                        close=close_val,
                        direction=1,
                        bar_num=self._bar_num,
                        is_reversal=False,
                    )
                    self.bricks.append(brick)
                    new_bricks.append(brick)
                    self._last_brick_close = close_val
                elif diff <= -self.brick_size:
                    close_val = round(self._last_brick_close - self.brick_size, 6)
                    self._current_direction = -1
                    self._bar_num = -1
                    brick = RenkoBrick(
                        index=len(self.bricks),
                        timestamp=timestamp,
                        open=self._last_brick_close,
                        high=self._last_brick_close,
                        low=close_val,
                        close=close_val,
                        direction=-1,
                        bar_num=self._bar_num,
                        is_reversal=False,
                    )
                    self.bricks.append(brick)
                    new_bricks.append(brick)
                    self._last_brick_close = close_val
                else:
                    break

            elif self._current_direction == 1:
                # Currently in Bullish trend
                # 1. Check Continuation (1 box up)
                if price >= round(self._last_brick_close + self.brick_size, 6):
                    close_val = round(self._last_brick_close + self.brick_size, 6)
                    self._bar_num = max(1, self._bar_num + 1)
                    brick = RenkoBrick(
                        index=len(self.bricks),
                        timestamp=timestamp,
                        open=self._last_brick_close,
                        high=close_val,
                        low=self._last_brick_close,
                        close=close_val,
                        direction=1,
                        bar_num=self._bar_num,
                        is_reversal=False,
                    )
                    self.bricks.append(brick)
                    new_bricks.append(brick)
                    self._last_brick_close = close_val
                # 2. Check Reversal (2 boxes down)
                elif price <= round(self._last_brick_close - (2.0 * self.brick_size), 6):
                    close_val = round(self._last_brick_close - (2.0 * self.brick_size), 6)
                    self._current_direction = -1
                    self._bar_num = -1
                    brick = RenkoBrick(
                        index=len(self.bricks),
                        timestamp=timestamp,
                        open=self._last_brick_close,
                        high=self._last_brick_close,
                        low=close_val,
                        close=close_val,
                        direction=-1,
                        bar_num=self._bar_num,
                        is_reversal=True,
                    )
                    self.bricks.append(brick)
                    new_bricks.append(brick)
                    self._last_brick_close = close_val
                else:
                    break

            elif self._current_direction == -1:
                # Currently in Bearish trend
                # 1. Check Continuation (1 box down)
                if price <= round(self._last_brick_close - self.brick_size, 6):
                    close_val = round(self._last_brick_close - self.brick_size, 6)
                    self._bar_num = min(-1, self._bar_num - 1)
                    brick = RenkoBrick(
                        index=len(self.bricks),
                        timestamp=timestamp,
                        open=self._last_brick_close,
                        high=self._last_brick_close,
                        low=close_val,
                        close=close_val,
                        direction=-1,
                        bar_num=self._bar_num,
                        is_reversal=False,
                    )
                    self.bricks.append(brick)
                    new_bricks.append(brick)
                    self._last_brick_close = close_val
                # 2. Check Reversal (2 boxes up)
                elif price >= round(self._last_brick_close + (2.0 * self.brick_size), 6):
                    close_val = round(self._last_brick_close + (2.0 * self.brick_size), 6)
                    self._current_direction = 1
                    self._bar_num = 1
                    brick = RenkoBrick(
                        index=len(self.bricks),
                        timestamp=timestamp,
                        open=self._last_brick_close,
                        high=close_val,
                        low=self._last_brick_close,
                        close=close_val,
                        direction=1,
                        bar_num=self._bar_num,
                        is_reversal=True,
                    )
                    self.bricks.append(brick)
                    new_bricks.append(brick)
                    self._last_brick_close = close_val
                else:
                    break

        return new_bricks
