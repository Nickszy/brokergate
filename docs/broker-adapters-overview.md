# Broker Adapters — Comparison Overview

Side-by-side status of the two live broker adapters. Both were audited against the
official SDKs and exercised on real paper accounts on 2026-06-07.

- Detail: [longbridge-order-api.md](longbridge-order-api.md) · [tiger-order-api.md](tiger-order-api.md)
- Code: `src/brokergate/adapters/longbridge.py` · `src/brokergate/adapters/tiger.py`

---

## Order placement capability

| Capability | Longbridge | Tiger |
|------------|------------|-------|
| Limit order | ✅ | ✅ |
| Market order | ✅ (`MO`) | ✅ (`market_order`) |
| Stop / trigger | ✅ (`LIT`/`MIT`) | ✅ (`stop_order`/`stop_limit_order`) |
| Trailing stop | ✅ (`TSLPAMT`/`TSLPPCT`) | ✅ (`trail_order`) |
| TIF: Day | ✅ | ✅ |
| TIF: GTC | ✅ | ✅ |
| TIF: GTD (+ expire date) | ✅ | ❌ SDK has no expire param → clear ValueError |
| Outside RTH (pre/post/overnight) | ✅ enum → `OutsideRTH` | ✅ bool `order.outside_rth` |
| `remark` / memo | ✅ | n/a |

All capabilities are driven by the shared generic `TradeOrderRequest`
(`order_type`, `time_in_force`, `trigger_price`, `trailing_amount/percent`,
`expire_date`, `outside_rth`); each adapter translates it to its SDK.

## Read interfaces

| Interface | Longbridge | Tiger |
|-----------|------------|-------|
| Account summary | ✅ `account_balance()` | ✅ `get_prime_assets()` |
| Positions | ✅ `stock_positions()` | ✅ `get_positions()` |
| Orders (today / detail) | ✅ | ✅ |
| Executions (today / history) | ✅ | ✅ |
| Quotes | ✅ `quote()` | ✅ `get_briefs()` (account lacks US entitlement) |
| Instrument info | ✅ `static_info()` | ✅ `get_contract()` |
| Max tradable qty | ✅ | ✅ |

## Live verification (paper accounts)

| Check | Longbridge (`LBPT…671`) | Tiger (`…3644`) |
|-------|------------------------|-----------------|
| Submit + query + cancel | ✅ LO/Day + LO/GTC placed, cancelled | ✅ LMT/Day placed, cancelled |
| Order reporting (qty/price/side/type/status) | ✅ accurate after fixes | ✅ accurate |
| Account / positions / instrument | ✅ balance, instrument | ✅ balance, FUTU position, AAPL contract |
| Quotes | ✅ 700.HK / AAPL.US | ⚠️ US entitlement denied (auto-falls-back to LB) |

---

## Key difference: SDK enum handling

This was the single biggest correctness gap and it differs by broker:

| | Longbridge | Tiger |
|--|-----------|-------|
| SDK type | Rust / PyO3 | pure Python |
| Enum `.name` | **`None`** (str() = `"OrderStatus.Canceled"`) | works (`OrderStatus.FILLED.name == "FILLED"`) |
| Side/type as | enums | plain strings (`'BUY'`, `'LMT'`) |
| Mapping helper | `_enum_name()` parses `str(value)` | `getattr(value, "name", value)` is enough |

Because the unit-test mocks set `.name` to plain strings, the Longbridge Rust-enum
bug was invisible until the adapter was run against the live SDK — every status
collapsed to `submitted` and every side to `buy`. Tiger never had this problem.

## Bugs fixed during the audit

| # | Broker | Bug | Fix |
|---|--------|-----|-----|
| 1 | Longbridge | order query read submit-request field names (`submitted_quantity`/`submitted_price`) → qty=0, price=None | read `quantity`/`price` |
| 2 | Longbridge | Rust-enum `.name` is None → status/side mislabeled | `_enum_name()` parses `str()` |
| 3 | Longbridge | quotes used `realtime_quote()` (streaming-only) → always empty | use `quote()` |
| 4 | Longbridge | quote/execution currency hardcoded USD | `_currency_for_symbol()` by region suffix |
| 5 | Both | submit was limit-only | derive order type/TIF; market/stop/trailing/GTC(+GTD on LB)/outside_rth |
| 6 | Tiger | order query hardcoded `order_type=limit` | `_map_order_type()` from SDK `order_type` |

## Known limitations (not bugs)

- **Tiger GTD** not supported by the tigeropen order utils (no expire param).
- **Tiger US quotes** require a market-data entitlement this paper account lacks;
  `broker=auto` auto-falls-back to Longbridge.
- **Advanced LB types** (`ELO/ALO/ODD`, `limit_depth_level`, `trigger_count`,
  `monitor_price`) are not exposed by the generic request model.
- Positions/executions field mappings for both brokers match the SDK but could not be
  exercised live where the paper account had none.

Tests: `uv run pytest` → 59 passed. `ruff check src tests` → clean.
