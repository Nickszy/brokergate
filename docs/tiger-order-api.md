# Tiger OpenAPI — Adapter Reference & Implementation Status

Source: https://www.itiger.com/openapi/ (tigeropen Python SDK)
SDK: `tigeropen` (installed `>=3.5.8`)
Adapter: `src/brokergate/adapters/tiger.py` → `TigerOpenApiAdapter`

Verified against the **real Tiger paper account** (`20240513191053644`) on 2026-06-07.

---

## Interface verification (whole adapter)

| Adapter method | SDK call | Status | Live verification |
|----------------|----------|--------|-------------------|
| `get_account_summary` | `get_prime_assets()` → segment `S` | ✅ `cash_balance`/`buying_power` correct | live: cash=980,904.02 / bp=3,963,590.08 USD |
| `list_positions` | `get_positions()` | ✅ `quantity`/`market_value`/`average_cost` + contract correct | live: FUTU 200 @ avg 95.48, mv 18,170 |
| `list_orders` / `get_order` | `get_orders()` / `get_order()` | ✅ fixed order_type mapping | live: FUTU LMT filled, AAPL orders submitted/rejected |
| `submit_order` | order_utils + `place_order()` | ✅ expanded (market/limit/stop/trailing, Day/GTC) | live: LMT/Day buy placed, got order_id, cancelled |
| `replace_order` | `modify_order()` | ✅ correct | not exercised live |
| `cancel_order` | `cancel_order()` | ✅ correct | live: order → cancelled |
| `preview_order` | `preview_order()` | ✅ correct | not exercised live |
| `get_max_tradable_quantity` | `get_estimate_tradable_quantity()` | ✅ correct | unit-tested |
| `list_today_executions` | delegates to history (`get_filled_orders`) | ✅ correct | 0 fills (weekend) |
| `list_history_executions` | `get_filled_orders()` / `get_transactions()` | ✅ field names match SDK | 0 fills |
| `get_quote_snapshots` | `get_briefs()` | ✅ code correct | ⚠️ this paper account lacks US market-data permission (broker entitlement, not a code bug) |
| `get_instrument_profile` | `get_contract()` | ✅ correct | live: AAPL → Apple / US / USD |

---

## Submit order — official vs implemented

tigeropen order builders (`tigeropen.common.util.order_utils`):

| Builder | Signature | Used for |
|---------|-----------|----------|
| `limit_order` | `(account, contract, action, quantity, limit_price, time_in_force='DAY')` | limit |
| `market_order` | `(account, contract, action, quantity, time_in_force='DAY')` | market |
| `stop_order` | `(account, contract, action, quantity, aux_price, time_in_force='DAY')` | stop (trigger, no limit) |
| `stop_limit_order` | `(account, contract, action, quantity, limit_price, aux_price, ...)` | stop-limit |
| `trail_order` | `(account, contract, action, quantity, trailing_percent=None, aux_price=None, ...)` | trailing stop |

### Coverage matrix (after fixes)

| Capability | Implemented | Notes |
|------------|-------------|-------|
| Limit (`limit_order`) + Day | ✅ verified live | |
| Market (`market_order`) | ✅ | `order_type=market` → `market_order`; unit-tested |
| Stop / trigger | ✅ | `trigger_price` (+limit → stop-limit, else stop) |
| Trailing stop | ✅ | `trailing_percent` → `trail_order(trailing_percent)`, `trailing_amount` → `aux_price` |
| `time_in_force` Day / GTC | ✅ | mapped to `'DAY'`/`'GTC'` strings |
| `time_in_force` GTD | ❌ not supported | tigeropen order utils have no expire-date param → raises a clear ValueError |
| `outside_rth` | ✅ | sets the order's `outside_rth` bool after building (`any_time`/`overnight` → True, `rth_only`/unset → SDK default) |

`submit_order` now calls `_build_order(request)` which selects the right builder and
threads `time_in_force`, instead of always using `limit_order`.

---

## Bugs found & fixed

### 1. `_order_from_sdk` hardcoded `order_type=limit` — FIXED
The SDK `Order` exposes `order_type` as a string (`'LMT'`/`'MKT'`/...). We now map it
via `_map_order_type` (`MKT`/`MO`/... → market, else limit) instead of hardcoding limit.
Live: the FUTU `LMT` order reports `type=limit`; the rest map correctly.

### 2. submit was limit-only — FIXED (expanded, see coverage matrix)

## Not bugs (broker-side behavior, documented for clarity)

- **Tiger does NOT have the Longbridge "Rust enum" problem.** tigeropen uses real Python
  enums (`OrderStatus.FILLED.name == "FILLED"`) and plain strings (`action == 'BUY'`),
  both handled by `getattr(value, "name", value)`. Verified live: status/side/qty/price
  all map correctly — no `qty=0` / mislabeled-side issues like Longbridge had.
- **US market quotes denied:** `get_briefs(["AAPL"])` → `permission denied (US market)`.
  This paper account simply lacks the US quote entitlement; the gateway already
  auto-falls-back to Longbridge for `broker=auto`.

---

## Live test evidence (paper account `20240513191053644`, 2026-06-07)

```
account_summary -> cash=980,904.02  buying_power=3,963,590.08 USD
positions       -> FUTU qty=200 avg_cost=95.48 market_value=18,170 USD
submit LMT/Day  -> AAPL buy 1 @10  -> order_id 43508841349267456
list_orders     -> 43508841349267456 AAPL buy type=limit qty=1 px=10 status=submitted
                   43475794872910848 FUTU buy type=limit qty=200 px=200 status=filled
cancel          -> order -> cancelled
instrument AAPL -> Apple / US / USD
```

Conclusion: the Tiger adapter is in good shape — field/enum mappings were already correct
(only `order_type` reporting was hardcoded, now fixed), and submit was expanded from
limit-only to market/limit/stop/trailing with Day/GTC. Tests: `uv run pytest` → 58 passed.
