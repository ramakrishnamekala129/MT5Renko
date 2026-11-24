"""
RK Renko V4 - Reference Zones Engine
Implements the 5 structural reference zones:
- Shadow (Yesterday's 03:30–05:30 IST)
- IB (Initial Balance, today's 03:30 IST candle)
- FirstRed (First red 30-min candle before 12:30 IST)
- 12:30PM (12:30–13:00 IST candle)
- 5:30PM (17:30–18:00 IST candle)
Computes Fibonacci 0.44 / 0.50 / 0.56 equilibrium corridors.
Detects ZONE_BREAKOUT, ZONE_BREAKDOWN, and ZONE_REVERSAL signals.
Zero external folder dependencies.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")


class ZoneType(str, Enum):
    SHADOW = "Shadow"
    IB = "IB"
    FIRST_RED = "FirstRed"
    C1230 = "12:30PM"
    C1730 = "5:30PM"


class ZoneColor(str, Enum):
    GREEN = "GREEN"      # Bullish support
    RED = "RED"          # Bearish resistance
    NEUTRAL = "NEUTRAL"  # Structural reference / balanced


class PriceZoneRel(str, Enum):
    FAR_ABOVE = "FAR_ABOVE"  # price > high
    ABOVE = "ABOVE"          # fib_0.56 <= price <= high
    INSIDE = "INSIDE"        # fib_0.44 <= price <= fib_0.56 (CHOP ZONE -> NO TRADE)
    BELOW = "BELOW"          # low <= price < fib_0.44
    FAR_BELOW = "FAR_BELOW"  # price < low


@dataclass
class ZoneLevel:
    zone_type: ZoneType
    high: float
    low: float
    fib_044: float
    fib_050: float
    fib_056: float
    color: ZoneColor
    is_active: bool = False
    trade_enabled: bool = True
    display_enabled: bool = True
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None

    @classmethod
    def create(
        cls,
        zone_type: ZoneType,
        high: float,
        low: float,
        color: ZoneColor = ZoneColor.NEUTRAL,
        trade_enabled: bool = True,
        display_enabled: bool = True,
        start_time: Optional[datetime.datetime] = None,
        end_time: Optional[datetime.datetime] = None,
    ) -> "ZoneLevel":
        rng = high - low
        fib_044 = round(low + (0.44 * rng), 6)
        fib_050 = round(low + (0.50 * rng), 6)
        fib_056 = round(low + (0.56 * rng), 6)
        return cls(
            zone_type=zone_type,
            high=round(high, 6),
            low=round(low, 6),
            fib_044=fib_044,
            fib_050=fib_050,
            fib_056=fib_056,
            color=color,
            is_active=True,
            trade_enabled=trade_enabled,
            display_enabled=display_enabled,
            start_time=start_time,
            end_time=end_time,
        )

    def classify_price(self, price: float) -> PriceZoneRel:
        """Classify where price sits relative to this zone's boundaries."""
        if price > self.high:
            return PriceZoneRel.FAR_ABOVE
        elif price >= self.fib_056:
            return PriceZoneRel.ABOVE
        elif price >= self.fib_044:
            return PriceZoneRel.INSIDE
        elif price >= self.low:
            return PriceZoneRel.BELOW
        else:
            return PriceZoneRel.FAR_BELOW


class ReferenceZoneEngine:
    def __init__(
        self,
        zone_trade_toggles: Optional[Dict[str, bool]] = None,
        zone_display_toggles: Optional[Dict[str, bool]] = None,
    ):
        # Default toggles as specified in Section 2.3:
        # Shadow: trade=false, display=true
        # IB: trade=false, display=false
        # FirstRed: trade=true, display=true
        # 12:30PM: trade=true, display=true
        # 5:30PM: trade=true, display=true
        self.trade_toggles = {
            ZoneType.SHADOW.value: False,
            ZoneType.IB.value: False,
            ZoneType.FIRST_RED.value: True,
            ZoneType.C1230.value: True,
            ZoneType.C1730.value: True,
        }
        if zone_trade_toggles:
            self.trade_toggles.update(zone_trade_toggles)

        self.display_toggles = {
            ZoneType.SHADOW.value: True,
            ZoneType.IB.value: False,
            ZoneType.FIRST_RED.value: True,
            ZoneType.C1230.value: True,
            ZoneType.C1730.value: True,
        }
        if zone_display_toggles:
            self.display_toggles.update(zone_display_toggles)

        self.zones: Dict[ZoneType, Optional[ZoneLevel]] = {
            ZoneType.SHADOW: None,
            ZoneType.IB: None,
            ZoneType.FIRST_RED: None,
            ZoneType.C1230: None,
            ZoneType.C1730: None,
        }

        # Track reversals pending inside zones: zone_type -> reversal_direction (+1 or -1)
        self._pending_zone_reversals: Dict[ZoneType, int] = {}
        self._prev_brick_close: Optional[float] = None

    def reset_daily_zones(self):
        """Reset zones at midnight rollover (Shadow is preserved or updated from yesterday)."""
        shadow = self.zones[ZoneType.SHADOW]
        self.zones = {
            ZoneType.SHADOW: shadow,
            ZoneType.IB: None,
            ZoneType.FIRST_RED: None,
            ZoneType.C1230: None,
            ZoneType.C1730: None,
        }
        self._pending_zone_reversals.clear()
        self._prev_brick_close = None

    def set_zone(
        self,
        zone_type: ZoneType,
        high: float,
        low: float,
        color: ZoneColor = ZoneColor.NEUTRAL,
        start_time: Optional[datetime.datetime] = None,
        end_time: Optional[datetime.datetime] = None,
    ) -> ZoneLevel:
        trade_on = self.trade_toggles.get(zone_type.value, True)
        disp_on = self.display_toggles.get(zone_type.value, True)

        zone = ZoneLevel.create(
            zone_type=zone_type,
            high=high,
            low=low,
            color=color,
            trade_enabled=trade_on,
            display_enabled=disp_on,
            start_time=start_time,
            end_time=end_time,
        )
        self.zones[zone_type] = zone

        # If FirstRed was just set, dynamically determine its color from Shadow
        if zone_type == ZoneType.FIRST_RED:
            self._evaluate_first_red_color()

        return zone

    def _evaluate_first_red_color(self):
        """Evaluate FirstRed directional bias relative to Shadow (Section 2.4)."""
        fr = self.zones[ZoneType.FIRST_RED]
        shadow = self.zones[ZoneType.SHADOW]
        if not fr or not shadow:
            return

        if fr.low >= shadow.high or fr.fib_050 > shadow.fib_056:
            fr.color = ZoneColor.GREEN
        elif fr.high <= shadow.low or fr.fib_050 < shadow.fib_044:
            fr.color = ZoneColor.RED
        else:
            fr.color = ZoneColor.NEUTRAL

    def is_price_inside_any_active_zone(self, price: float) -> Tuple[bool, Optional[ZoneLevel]]:
        """
        Priority 0 Check: Is price inside any trading zone's 0.44–0.56 corridor?
        If True, ALL entries are strictly blocked (Chop zone).
        """
        for zone in self.zones.values():
            if zone and zone.is_active and zone.trade_enabled:
                if zone.classify_price(price) == PriceZoneRel.INSIDE:
                    return True, zone
        return False, None

    def evaluate_brick_signals(
        self,
        brick_close: float,
        brick_dir: int,
        st_dir: int,
        is_reversal_brick: bool,
    ) -> List[Tuple[str, ZoneLevel, str]]:
        """
        Evaluate Zone signals on brick completion:
        Returns list of tuples: (signal_type, zone, trade_direction: 'BUY' or 'SELL')
        Signal types:
        - 'ZONE_REVERSAL' (highest priority)
        - 'ZONE_BREAKOUT' (BUY)
        - 'ZONE_BREAKDOWN' (SELL)
        """
        signals: List[Tuple[str, ZoneLevel, str]] = []
        if self._prev_brick_close is None:
            self._prev_brick_close = brick_close
            return signals

        prev_c = self._prev_brick_close

        for zone in self.zones.values():
            if not zone or not zone.is_active or not zone.trade_enabled:
                continue

            # 1. Check for Renko reversal detected inside zone range [low, high]
            if is_reversal_brick:
                if zone.low <= prev_c <= zone.high or zone.low <= brick_close <= zone.high:
                    self._pending_zone_reversals[zone.zone_type] = brick_dir

            # 2. Check for ZONE_REVERSAL exit
            if zone.zone_type in self._pending_zone_reversals:
                rev_dir = self._pending_zone_reversals[zone.zone_type]
                if rev_dir == 1 and brick_dir == 1 and st_dir == 1:
                    # Exits above candle_high in reversal direction
                    if prev_c <= zone.high and brick_close > zone.high:
                        signals.append(("ZONE_REVERSAL", zone, "BUY"))
                        del self._pending_zone_reversals[zone.zone_type]
                        continue
                elif rev_dir == -1 and brick_dir == -1 and st_dir == -1:
                    # Exits below candle_low in reversal direction
                    if prev_c >= zone.low and brick_close < zone.low:
                        signals.append(("ZONE_REVERSAL", zone, "SELL"))
                        del self._pending_zone_reversals[zone.zone_type]
                        continue

            # 3. Check for standard ZONE_BREAKOUT (BUY)
            if brick_dir == 1 and prev_c <= zone.high and brick_close > zone.high:
                signals.append(("ZONE_BREAKOUT", zone, "BUY"))

            # 4. Check for standard ZONE_BREAKDOWN (SELL)
            elif brick_dir == -1 and prev_c >= zone.low and brick_close < zone.low:
                signals.append(("ZONE_BREAKDOWN", zone, "SELL"))

        self._prev_brick_close = brick_close

        # Reversal signals take precedence over breakout/breakdowns
        reversals = [s for s in signals if s[0] == "ZONE_REVERSAL"]
        if reversals:
            return reversals

        return signals
