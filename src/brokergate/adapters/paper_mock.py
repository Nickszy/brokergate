"""Deterministic mock market data for the *PaperAdapter classes.

Paper adapters have no broker SDK, but the dashboard still needs a quote and an
order book to render in ``paper`` mode. These helpers synthesise a stable,
symbol-derived snapshot and depth so the UI shows realistic (clearly fake)
data without any credentials. Output is deterministic for a given symbol so
tests can assert on it.
"""

from __future__ import annotations

from decimal import Decimal

from brokergate.models import BrokerId, DepthLevel, QuoteDepth, QuoteSnapshot

_DEPTH_LEVELS = 5


def _base_price(symbol: str) -> Decimal:
    """Stable pseudo price in [50, 550) derived from the symbol characters."""
    seed = sum(ord(char) for char in symbol.upper()) or 1
    return Decimal(50 + (seed * 37) % 500)


def _currency_for(broker: BrokerId, symbol: str) -> str:
    upper = symbol.upper()
    if upper.endswith(".HK") or upper.endswith(".HKEX"):
        return "HKD"
    if upper.endswith(".SS") or upper.endswith(".SZ") or upper.endswith(".SH"):
        return "CNY"
    return "USD"


def mock_quote_snapshot(broker: BrokerId, symbol: str) -> QuoteSnapshot:
    last = _base_price(symbol)
    tick = (last * Decimal("0.0005")).quantize(Decimal("0.01"))
    return QuoteSnapshot(
        broker=broker,
        symbol=symbol,
        currency=_currency_for(broker, symbol),
        last_price=last,
        bid_price=last - tick,
        ask_price=last + tick,
        open_price=last - tick * 4,
        high_price=last + tick * 6,
        low_price=last - tick * 7,
        previous_close=last - tick * 2,
        raw={"mode": "paper"},
    )


def mock_market_depth(broker: BrokerId, symbol: str) -> QuoteDepth:
    last = _base_price(symbol)
    tick = (last * Decimal("0.0005")).quantize(Decimal("0.01")) or Decimal("0.01")
    asks = [
        DepthLevel(
            price=last + tick * (i + 1),
            volume=Decimal(1000 + ((i * 317) % 1200)),
            order_count=1 + (i * 3) % 9,
        )
        for i in range(_DEPTH_LEVELS)
    ]
    bids = [
        DepthLevel(
            price=last - tick * (i + 1),
            volume=Decimal(1000 + ((i * 251) % 1200)),
            order_count=1 + (i * 5) % 9,
        )
        for i in range(_DEPTH_LEVELS)
    ]
    return QuoteDepth(
        broker=broker,
        symbol=symbol,
        currency=_currency_for(broker, symbol),
        asks=asks,
        bids=bids,
        raw={"mode": "paper"},
    )
