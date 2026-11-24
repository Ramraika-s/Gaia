"""
sim_core/society/wtc_market.py
World Trade Centre (WTC) order-book exchange and macroeconomic inflation engine.
Follows SOCIETY_AND_GOVERNANCE_SPEC.md Section 2.
"""

from __future__ import annotations

from typing import Any

from sim_core.schemas import WTCMarketSnapshot

COMMODITIES = ["food", "wood", "stone", "iron", "tools", "land_deeds"]

BASE_PRICES = {
    "food": 1.0,
    "wood": 1.5,
    "stone": 2.0,
    "iron": 4.0,
    "tools": 6.5,
    "land_deeds": 50.0,
}


class WTCExchange:
    """
    Central order-book exchange and CPI inflation calculator.
    Prices clear based on supply/demand and aggregate M / Q.
    """

    def __init__(
        self,
        base_m: float = 100_000.0,
        base_q: float = 100_000.0,
    ):
        self.base_m: float = max(1.0, base_m)
        self.base_q: float = max(1.0, base_q)
        self.current_m: float = self.base_m
        self.current_q: float = self.base_q
        self.cpi: float = 1.0
        self.frozen: bool = False
        self.current_prices: dict[str, float] = dict(BASE_PRICES)
        self.history: list[WTCMarketSnapshot] = []

        # Order books: commodity -> list of order dicts
        self.bids: dict[str, list[dict[str, Any]]] = {c: [] for c in COMMODITIES}
        self.asks: dict[str, list[dict[str, Any]]] = {c: [] for c in COMMODITIES}

    def calibrate_baseline(self, initial_m: float, initial_q: float) -> None:
        """Anchors baseline macro aggregates M0, Q0 and resets CPI to 1.000."""
        self.base_m = max(1.0, initial_m)
        self.base_q = max(0.1, initial_q)
        self.current_m = self.base_m
        self.current_q = self.base_q
        self.cpi = 1.0
        self.current_prices = dict(BASE_PRICES)

    def update_macro_aggregates(self, money_supply_m: float, real_output_q: float) -> float:
        """
        Updates circulating money supply M and real output Q,
        recomputing the Consumer Price Index (CPI) using Fisher's Equation:
        CPI = (M / M_0) / (Q / Q_0).
        """
        self.current_m = max(1.0, money_supply_m)
        self.current_q = max(0.1, real_output_q)

        m_ratio = self.current_m / self.base_m
        q_ratio = self.current_q / self.base_q

        # Unbounded inflation, floored at 0.20
        self.cpi = max(0.20, m_ratio / max(0.01, q_ratio))

        # Re-anchor base commodity prices to current CPI
        for item, base_p in BASE_PRICES.items():
            self.current_prices[item] = base_p * self.cpi

        return self.cpi

    def place_order(
        self,
        agent_id: str,
        side: str,  # "BUY" or "SELL"
        commodity: str,
        quantity: float,
        limit_price: float,
    ) -> tuple[bool, str]:
        """Submits a limit order to the WTC exchange."""
        if self.frozen:
            return False, "MARKET_FROZEN"

        if commodity not in COMMODITIES:
            return False, f"UNKNOWN_COMMODITY: {commodity}"

        if quantity <= 0:
            return False, "INVALID_QUANTITY"

        order = {
            "agent_id": agent_id,
            "quantity": quantity,
            "limit_price": limit_price,
        }

        if side == "BUY":
            self.bids[commodity].append(order)
            self.bids[commodity].sort(key=lambda o: o["limit_price"], reverse=True)
        elif side == "SELL":
            self.asks[commodity].append(order)
            self.asks[commodity].sort(key=lambda o: o["limit_price"])
        else:
            return False, f"INVALID_SIDE: {side}"

        return True, "ORDER_PLACED"

    def clear_market(
        self,
        current_day: int,
        current_tick: int,
    ) -> WTCMarketSnapshot:
        """
        Clears bids and asks for all commodities.
        Clamps price movements to +-15% per market cycle.
        """
        if self.frozen:
            snapshot = WTCMarketSnapshot(
                day=current_day,
                tick=current_tick,
                cpi=self.cpi,
                money_supply_m=self.current_m,
                real_output_q=self.current_q,
                prices=dict(self.current_prices),
                frozen=True,
            )
            self.history.append(snapshot)
            return snapshot

        for commodity in COMMODITIES:
            bids = self.bids[commodity]
            asks = self.asks[commodity]

            if bids and asks:
                highest_bid = bids[0]["limit_price"]
                lowest_ask = asks[0]["limit_price"]

                if highest_bid >= lowest_ask:
                    raw_clearing_price = (highest_bid + lowest_ask) / 2.0
                    old_price = self.current_prices[commodity]
                    # Clamp price delta to +-15%
                    max_allowed = old_price * 1.15
                    min_allowed = old_price * 0.85
                    clamped_price = max(min_allowed, min(max_allowed, raw_clearing_price))
                    self.current_prices[commodity] = clamped_price

            # Clear executed or expired orders
            self.bids[commodity].clear()
            self.asks[commodity].clear()

        snapshot = WTCMarketSnapshot(
            day=current_day,
            tick=current_tick,
            cpi=self.cpi,
            money_supply_m=self.current_m,
            real_output_q=self.current_q,
            prices=dict(self.current_prices),
            frozen=False,
        )
        self.history.append(snapshot)
        return snapshot

    @staticmethod
    def estimate_real_output_q(living_agent_count: int) -> float:
        """Single source of truth for estimated real output aggregate Q."""
        return max(10.0, float(living_agent_count) * 5.0)

    def freeze_market(self) -> None:
        """God/Admin market freeze."""
        self.frozen = True

    def unfreeze_market(self) -> None:
        """God/Admin market unfreeze."""
        self.frozen = False
