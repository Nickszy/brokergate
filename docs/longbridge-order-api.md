# Longbridge OpenAPI — Adapter Reference & Implementation Status

Source: https://open.longbridge.com/en/docs
SDK: `longbridge` (Python, installed `>=4.2.2`)
Adapter: `src/brokergate/adapters/longbridge.py` → `LongbridgeOpenApiAdapter`

Verified against the **real Longbridge paper system** (account `LBPT10089671`) on 2026-06-07.

---

## Interface verification (whole adapter)

Every `LongbridgeOpenApiAdapter` method was checked against the official docs and the
installed SDK, and exercised against the live paper system where data allowed.

| Adapter method | SDK call | Status | Live verification |
|----------------|----------|--------|-------------------|
| `get_account_summary` | `account_balance()` | ✅ correct | live: `cash=14,936,700 HKD` |
| `list_positions` | `stock_positions()` | ✅ fields match SDK | account had 0 positions — not exercised live |
| `list_orders` / `get_order` | `today_orders()` / `order_detail()` | ✅ fixed (was qty=0/price=None) | live: `qty=100 px=50 side=buy status=cancelled` |
| `submit_order` | `submit_order(...)` | ✅ expanded (LO/MO/LIT/MIT/TSLP*, Day/GTC/GTD, outside_rth) | live: LO/Day + LO/GTC placed; MO format accepted |
| `replace_order` | `replace_order(...)` | ✅ correct | not exercised (no live open order to amend safely) |
| `cancel_order` | `cancel_order(...)` | ✅ correct | live: order moved to `cancelled` |
| `get_max_tradable_quantity` | `estimate_max_purchase_quantity(...)` | ✅ correct | live: `cash_max_qty=2800` |
| `list_today_executions` | `today_executions()` | ✅ fields match SDK | 0 executions (weekend) — not exercised live |
| `list_history_executions` | `history_executions()` | ✅ fields match SDK | 0 executions — not exercised live |
| `get_quote_snapshots` | ~~`realtime_quote()`~~ → `quote()` | ✅ fixed (was always empty) | live: `700.HK=453.2 HKD`, `AAPL.US=307.34 USD` |
| `get_instrument_profile` | `static_info()` | ✅ correct | live: `700.HK TENCENT HKD lot=100` |

Enum/field mapping (`_enum_name`, `_order_from_sdk`, `_quote_from_sdk`,
`_execution_from_sdk`) is shared across all of the above — the fixes below apply
adapter-wide, not just to orders.

---

## Endpoint (submit order)

`POST /v3/trade/order` — submit a new order. (Called via the SDK, not raw HTTP.)

## Official request parameters

From the docs + the installed SDK signature:

```
submit_order(symbol, order_type, side, submitted_quantity, time_in_force,
             submitted_price=None, trigger_price=None, limit_offset=None,
             trailing_amount=None, trailing_percent=None, expire_date=None,
             outside_rth=None, limit_depth_level=None, trigger_count=None,
             monitor_price=None, remark=None)
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `symbol` | string | YES | `ticker.region`, e.g. `AAPL.US`, `700.HK` |
| `order_type` | enum | YES | see OrderType below |
| `side` | enum | YES | `Buy` / `Sell` |
| `submitted_quantity` | string/Decimal | YES | e.g. `100` (HK board lots apply) |
| `time_in_force` | enum | YES | `Day` / `GoodTilCanceled` / `GoodTilDate` |
| `submitted_price` | string/Decimal | NO | required for `LO/ELO/ALO/ODD/LIT` |
| `trigger_price` | string/Decimal | NO | required for `LIT/MIT` |
| `limit_offset` | string/Decimal | NO | required for `TSLPAMT/TSLPPCT` when `limit_depth_level=0` |
| `trailing_amount` | string/Decimal | NO | required for `TSLPAMT` |
| `trailing_percent` | string/Decimal | NO | required for `TSLPPCT` |
| `expire_date` | string | NO | `YYYY-MM-DD`, required when `time_in_force=GTD` |
| `outside_rth` | enum | NO | `RTH_ONLY` / `ANY_TIME` / `OVERNIGHT` (US) |
| `limit_depth_level` | int32 | NO | -5~0~5, for trailing-stop orders |
| `trigger_count` | int32 | NO | 0~3, for LIT/MIT/trailing orders |
| `monitor_price` | string/Decimal | NO | for trailing-stop orders |
| `remark` | string | NO | max 255 chars |

### Enums (from installed SDK — source of truth)

- **OrderType**: `LO`, `ELO`, `ALO`, `ODD`, `MO`, `AO`, `LIT`, `MIT`, `SLO`, `TSLPAMT`, `TSLPPCT`, `TSMAMT`, `TSMPCT`
- **OrderSide**: `Buy`, `Sell`
- **TimeInForceType**: `Day`, `GoodTilCanceled` (GTC), `GoodTilDate` (GTD)
- **OutsideRTH**: `RTHOnly`, `AnyTime`, `Overnight`

---

## Implementation status (`LongbridgeOpenApiAdapter.submit_order`)

### What we send today

```python
submit_order(
    symbol      = draft.request.symbol,
    order_type  = LBOrderType.LO,          # HARDCODED
    side        = Buy / Sell,
    submitted_quantity = Decimal(qty),
    time_in_force = TimeInForceType.Day,    # HARDCODED
    submitted_price = Decimal(limit_price) or None,
    remark      = client_memo or "BrokerGate Trade",
)
```

### Coverage matrix (after fixes)

| Capability | Official | Implemented | Accurate |
|------------|----------|-------------|----------|
| Limit order (`LO`) + `Day` | ✅ | ✅ | ✅ verified live (real `order_id`) |
| Market order (`MO`) | ✅ | ✅ `order_type=market` → `MO`, no price sent | ✅ live: broker accepted format (rejected on short-sell business rule, expected) |
| Stop / trigger (`LIT`/`MIT`, `trigger_price`) | ✅ | ✅ `trigger_price` + limit → `LIT`, else `MIT` | unit-tested |
| Trailing stop (`TSLPAMT`/`TSLPPCT`) | ✅ | ✅ `trailing_amount`/`trailing_percent` | unit-tested |
| `time_in_force` GTC / GTD (+`expire_date`) | ✅ | ✅ mapped; GTD requires `expire_date` (validated) | ✅ GTC verified live |
| `outside_rth` | ✅ | ✅ `rth_only`/`any_time`/`overnight` | unit-tested |
| Other limit types (`ELO/ALO/ODD`) | ✅ | ❌ not exposed (rarely needed) | — |
| `limit_depth_level` / `trigger_count` / `monitor_price` | ✅ | ❌ not exposed | — |
| `remark` | ✅ | ✅ | ✅ |

Model fields added to `TradeOrderRequest`: `time_in_force` (enum `TimeInForce`),
`expire_date`, `trigger_price`, `trailing_amount`, `trailing_percent`,
`outside_rth` (enum `OutsideRth`). The adapter derives the concrete LB `OrderType`
from these (`_resolve_order_type`) instead of hardcoding `LO`.

Tiger adapter is unchanged: new fields are optional and default to None, so Tiger's
limit-only path still works.

---

## Bugs found & fixed (verified on the live paper system)

### 1. Query field-name mismatch — FIXED
`_order_from_sdk` read **submit-request** names instead of the **query-response**
`Order` object names. The SDK `Order` exposes `quantity`/`price`, not
`submitted_quantity`/`submitted_price`.

| Was | Now | Effect |
|-----|-----|--------|
| `order.submitted_quantity` | `order.quantity` | quantity was always **0** |
| `order.submitted_price` | `order.price` | limit_price was always **None** |
| hardcoded `OrderType.limit` | `_map_order_type(order.order_type)` | type now real |

### 2. Rust-enum name normalization — FIXED (found only via live system)
The Longbridge SDK enums are Rust/PyO3-backed: their `.name` attribute is **None**
and `str(value)` renders as `"OrderStatus.Canceled"`. The old `_map_*` helpers used
`getattr(value, "name", value)`, so against the real SDK **every status collapsed to
`submitted` and every side collapsed to `buy`** (sell orders misreported). Unit tests
missed it because mocks set `.name` to plain strings.

Fix: `_enum_name()` reads `.name` when it is a real string (mocks) and otherwise
parses the variant from `str(value)` (real SDK). Applied to `_map_order_status`,
`_map_order_side`, `_map_order_type`.

### 3. Quotes used the wrong SDK method — FIXED (found only via live system)
`get_quote_snapshots` called `QuoteContext.realtime_quote(symbols)`, which only
returns symbols already subscribed to the **streaming** feed — so it returned an empty
list every time. The pull/snapshot API is `QuoteContext.quote(symbols)`.

Verified live: `realtime_quote(["700.HK"])` → `[]`; `quote(["700.HK"])` → full
`SecurityQuote` (last_done, open, high, low, prev_close, timestamp). Fix: call `quote()`.

### 4. Quote/Execution currency was hardcoded USD — FIXED
`SecurityQuote` and the execution object carry **no** `currency` field, so every quote
and execution was reported as `USD` (wrong for HK/CN/SG). Fix: `_currency_for_symbol()`
infers the currency from the `ticker.region` suffix (`.HK`→HKD, `.US`→USD, `.SG`→SGD,
`.SH`/`.SZ`→CNY) when the SDK object has no currency. Verified live: `700.HK`→HKD,
`AAPL.US`→USD.

---

## Live test evidence (paper account `LBPT10089671`, 2026-06-07)

```
# submit
LO Day  700.HK Buy 100 @50   -> order_id 1248283498632982528          # OK
LO GTC  700.HK Buy 100 @50   -> order_id 1248285972437676032          # OK (GoodTilCanceled accepted)
MO      700.HK Sell 100      -> 603301 "does not support short selling" # format OK, business reject (expected)

# query (after enum + field-name fixes)
1248285972437676032 700.HK side=buy type=limit qty=100 px=50 status=cancelled
1248283498632982528 700.HK side=buy type=limit qty=100 px=50 status=cancelled
#   before fixes this read: side=buy type=limit qty=0 px=None status=submitted

# other interfaces (live)
account_summary -> cash=14,936,700 HKD
quote 700.HK    -> last=453.2 HKD   (was [] before the realtime_quote->quote fix)
quote AAPL.US   -> last=307.34 USD
instrument 700.HK -> TENCENT HKD lot=100
max_tradable 700.HK @350 -> cash_max_qty=2800
```

Conclusion: the whole adapter was checked against the real paper system. Submit/query/
cancel, balance, quotes, instrument info, and max-tradable are correct; order/quote
reporting (qty, price, side, type, status, currency) is now accurate. Positions and
executions could not be exercised live (the paper account had none) but their field
mappings match the SDK. Tests: `uv run pytest` → 52 passed.
