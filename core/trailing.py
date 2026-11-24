"""
RK Renko V4 - Trailing Stop Engine
Tick-level trailing stop execution with:
- Activation threshold in bricks of profit (default 4.0)
- Breakeven jump (+0.1 brick buffer)
- Continuous trailing distance behind market
- Dynamic Spread Spike Guard (EMA smoothing & spike pauses)
Zero external folder dependencies.
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class TrailingPositionState:
    ticket: int
    symbol: str
    direction: str          # 'BUY' or 'SELL'
    open_price: float
    current_sl: float
    is_activated: bool = False
    highest_profit_pts: float = 0.0


class TrailingStopEngine:
    def __init__(
        self,
        brick_size: float,
        trail_act_bricks: float = 4.0,
        trail_distance_bricks: float = 4.0,
        spread_guard_mult: float = 1.0,
        enabled: bool = True,
    ):
        self.brick_size = float(brick_size)
        self.trail_act_bricks = float(trail_act_bricks)
        self.trail_distance_bricks = float(trail_distance_bricks)
        self.spread_guard_mult = float(spread_guard_mult)
        self.enabled = enabled

        # Rolling average spread tracking
        self.avg_spread: Optional[float] = None
        self.is_spread_spiked: bool = False

    def update_spread(self, ask: float, bid: float):
        """Update rolling spread and detect spread spikes."""
        current_spread = max(0.0, ask - bid)
        if self.avg_spread is None:
            self.avg_spread = current_spread
        else:
            self.avg_spread = (0.95 * self.avg_spread) + (0.05 * current_spread)

        # Spike detection: current > 1.5 * avg_spread
        if self.avg_spread > 0 and current_spread > (1.5 * self.avg_spread):
            self.is_spread_spiked = True
        else:
            self.is_spread_spiked = False

    def evaluate_tick(
        self,
        pos_state: TrailingPositionState,
        bid: float,
        ask: float,
    ) -> Tuple[bool, Optional[float], str]:
        """
        Evaluates position on each incoming tick.
        Returns: (should_modify_sl: bool, new_sl_price: Optional[float], reason: str)
        """
        if not self.enabled:
            return False, None, "Trailing stop disabled"

        self.update_spread(ask, bid)

        if self.is_spread_spiked:
            return False, None, "Trailing paused: Spread spike detected"

        current_spread = max(0.0, ask - bid)
        spread_guard_offset = current_spread * self.spread_guard_mult
        trail_gap = (self.trail_distance_bricks * self.brick_size) + spread_guard_offset
        activation_dist = self.trail_act_bricks * self.brick_size

        if pos_state.direction == "BUY":
            profit_pts = bid - pos_state.open_price

            # Activation check
            if not pos_state.is_activated:
                if profit_pts >= activation_dist:
                    pos_state.is_activated = True
                    # Breakeven + 0.1 brick
                    be_sl = round(pos_state.open_price + (0.1 * self.brick_size), 6)
                    if be_sl > pos_state.current_sl:
                        return True, be_sl, "Trailing activated: Moved to Breakeven + 0.1 brick"
                return False, None, "Trailing not yet activated"

            # Trailing updates (BUY SL moves UP only)
            proposed_sl = round(bid - trail_gap, 6)
            # Ensure proposed SL is higher than current SL and above breakeven
            min_sl = round(pos_state.open_price + (0.1 * self.brick_size), 6)
            target_sl = max(proposed_sl, min_sl)

            if target_sl > pos_state.current_sl:
                return True, target_sl, f"Trailing SL stepped up to {target_sl:.5f}"

        elif pos_state.direction == "SELL":
            profit_pts = pos_state.open_price - ask

            # Activation check
            if not pos_state.is_activated:
                if profit_pts >= activation_dist:
                    pos_state.is_activated = True
                    # Breakeven - 0.1 brick
                    be_sl = round(pos_state.open_price - (0.1 * self.brick_size), 6)
                    if pos_state.current_sl <= 0 or be_sl < pos_state.current_sl:
                        return True, be_sl, "Trailing activated: Moved to Breakeven - 0.1 brick"
                return False, None, "Trailing not yet activated"

            # Trailing updates (SELL SL moves DOWN only)
            proposed_sl = round(ask + trail_gap, 6)
            min_sl = round(pos_state.open_price - (0.1 * self.brick_size), 6)
            target_sl = min(proposed_sl, min_sl)

            if pos_state.current_sl <= 0 or target_sl < pos_state.current_sl:
                return True, target_sl, f"Trailing SL stepped down to {target_sl:.5f}"

        return False, None, "No SL adjustment needed"
