"""
RK Renko V4 - 9-Layer Confluence Filter Stack
Implements the strict multi-stage validation pipeline:
1. Daily Trade Cap (max 12)
2. Per-Zone Trade Cap (max 4)
3. Supertrend Direction (+1 for BUY, -1 for SELL)
4. Brick Streak (>= 3 for BUY, <= -3 for SELL)
5. Renko EMA 5/9 (EMA5 > EMA9 for BUY, EMA5 < EMA9 for SELL)
6. 1H EMA 50 Macro (close >= EMA50 for BUY, close < EMA50 for SELL)
7. Zone Boundary Block (no RED zone has price inside for BUY, no GREEN for SELL)
8. FirstRed-Shadow Structural Gate (optional)
9. AI Renko Alignment (status == READY, direction == +1 or -1)
Zero external folder dependencies.
"""

from typing import Dict, Optional, Tuple
from .zones import ReferenceZoneEngine, ZoneLevel, ZoneType, ZoneColor, PriceZoneRel


class ConfluenceFilterStack:
    def __init__(
        self,
        max_daily_trades: int = 12,
        max_trades_per_zone: int = 4,
        zone_streak_bricks: int = 3,
        use_renko_ema: bool = True,
        use_h1_ema50: bool = True,
        firstred_shadow_rule: bool = False,
        no_zones: bool = False,
    ):
        self.max_daily_trades = max_daily_trades
        self.max_trades_per_zone = max_trades_per_zone
        self.zone_streak_bricks = zone_streak_bricks
        self.use_renko_ema = use_renko_ema
        self.use_h1_ema50 = use_h1_ema50
        self.firstred_shadow_rule = firstred_shadow_rule
        self.no_zones = no_zones

        # Trade tracking counters
        self.daily_trade_count: int = 0
        self.zone_trade_counts: Dict[str, int] = {
            ZoneType.SHADOW.value: 0,
            ZoneType.IB.value: 0,
            ZoneType.FIRST_RED.value: 0,
            ZoneType.C1230.value: 0,
            ZoneType.C1730.value: 0,
        }

        # FirstRed-Shadow tracking state
        self._fr_shadow_crossed_above: bool = False

    def reset_daily_counters(self):
        """Reset trade counts at daily rollover."""
        self.daily_trade_count = 0
        for k in self.zone_trade_counts:
            self.zone_trade_counts[k] = 0
        self._fr_shadow_crossed_above = False

    def record_trade(self, zone_name: Optional[str] = None):
        """Record an executed trade towards the daily and zone caps."""
        self.daily_trade_count += 1
        if zone_name and zone_name in self.zone_trade_counts:
            self.zone_trade_counts[zone_name] += 1

    def validate_signal(
        self,
        direction: str,  # 'BUY' or 'SELL'
        zone: Optional[ZoneLevel],
        price: float,
        bar_num: int,
        st_dir: int,
        ema5: float,
        ema9: float,
        h1_ema50: Optional[float],
        ai_renko_status: str,
        ai_renko_dir: int,
        zone_engine: ReferenceZoneEngine,
    ) -> Tuple[bool, str]:
        """
        Validates all 9 confluence layers.
        Returns: (passed: bool, reason: str)
        """
        # Layer 1: Daily Trade Cap
        if self.daily_trade_count >= self.max_daily_trades:
            return False, f"Layer 1 Fail: Daily cap reached ({self.daily_trade_count}/{self.max_daily_trades})"

        # Layer 2: Per-Zone Trade Cap
        if not self.no_zones and zone:
            count = self.zone_trade_counts.get(zone.zone_type.value, 0)
            if count >= self.max_trades_per_zone:
                return False, f"Layer 2 Fail: Zone {zone.zone_type.value} cap reached ({count}/{self.max_trades_per_zone})"

        # Layer 3: Supertrend Direction
        if direction == "BUY" and st_dir != 1:
            return False, f"Layer 3 Fail: Supertrend is not Bullish (st_dir={st_dir})"
        if direction == "SELL" and st_dir != -1:
            return False, f"Layer 3 Fail: Supertrend is not Bearish (st_dir={st_dir})"

        # Layer 4: Brick Streak
        if direction == "BUY" and bar_num < self.zone_streak_bricks:
            return False, f"Layer 4 Fail: BUY streak {bar_num} < {self.zone_streak_bricks}"
        if direction == "SELL" and bar_num > -self.zone_streak_bricks:
            return False, f"Layer 4 Fail: SELL streak {bar_num} > -{self.zone_streak_bricks}"

        # Layer 5: Renko EMA 5/9 Momentum
        if self.use_renko_ema:
            if direction == "BUY" and not (ema5 > ema9):
                return False, f"Layer 5 Fail: EMA5 ({ema5:.5f}) not > EMA9 ({ema9:.5f})"
            if direction == "SELL" and not (ema5 < ema9):
                return False, f"Layer 5 Fail: EMA5 ({ema5:.5f}) not < EMA9 ({ema9:.5f})"

        # Layer 6: 1H EMA 50 Macro Filter
        if self.use_h1_ema50 and h1_ema50 is not None:
            if direction == "BUY" and price < h1_ema50:
                return False, f"Layer 6 Fail: BUY price {price:.5f} < 1H EMA50 {h1_ema50:.5f}"
            if direction == "SELL" and price >= h1_ema50:
                return False, f"Layer 6 Fail: SELL price {price:.5f} >= 1H EMA50 {h1_ema50:.5f}"

        # Layer 7: Zone Boundary Block
        # For BUY: No RED zone has price INSIDE
        # For SELL: No GREEN zone has price INSIDE
        if not self.no_zones:
            for z in zone_engine.zones.values():
                if z and z.is_active and z.trade_enabled:
                    rel = z.classify_price(price)
                    if rel == PriceZoneRel.INSIDE:
                        if direction == "BUY" and z.color == ZoneColor.RED:
                            return False, f"Layer 7 Fail: BUY blocked - price INSIDE RED zone {z.zone_type.value}"
                        if direction == "SELL" and z.color == ZoneColor.GREEN:
                            return False, f"Layer 7 Fail: SELL blocked - price INSIDE GREEN zone {z.zone_type.value}"

        # Layer 8: FirstRed-Shadow Rule (Optional)
        if not self.no_zones and self.firstred_shadow_rule:
            fr = zone_engine.zones.get(ZoneType.FIRST_RED)
            sh = zone_engine.zones.get(ZoneType.SHADOW)
            c1730 = zone_engine.zones.get(ZoneType.C1730)
            if fr and sh:
                # If 5:30PM zone is active, normal rules resume
                if not (c1730 and c1730.is_active):
                    if fr.low >= sh.high:
                        # FR above shadow -> BUY only
                        if direction == "SELL":
                            return False, "Layer 8 Fail: FirstRed above Shadow blocks SELL orders"
                    elif fr.high <= sh.low:
                        # FR below shadow
                        max_h = max(fr.high, sh.high)
                        if price > max_h:
                            self._fr_shadow_crossed_above = True

                        if not self._fr_shadow_crossed_above:
                            # Not crossed above -> SELL only
                            if direction == "BUY":
                                return False, "Layer 8 Fail: FirstRed below Shadow blocks BUY until breakout"
                        else:
                            # Crossed above -> Only 12:30PM zone entries allowed
                            if zone and zone.zone_type != ZoneType.C1230:
                                return False, "Layer 8 Fail: Post-breakout restricted to 12:30PM zone only"

        # Layer 9: AI Renko Alignment
        if ai_renko_status != "READY":
            return False, f"Layer 9 Fail: AI Renko not ready (status={ai_renko_status})"
        if direction == "BUY" and ai_renko_dir != 1:
            return False, f"Layer 9 Fail: AI Renko direction not Bullish (dir={ai_renko_dir})"
        if direction == "SELL" and ai_renko_dir != -1:
            return False, f"Layer 9 Fail: AI Renko direction not Bearish (dir={ai_renko_dir})"

        return True, "All 9 Layers Passed"
