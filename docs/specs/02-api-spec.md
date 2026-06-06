# API Spec

## 认证

首版使用 `X-API-Key`。当 `.env` 中 `BROKERGATE_API_KEY=change-me` 时，本地开发允许跳过校验；生产部署必须改为强随机密钥。

后续版本增加：

- JWT 登录态。
- Web 面板用户会话。
- MCP read-only token。
- 交易确认独立权限。

## Health

`GET /health`

返回服务状态，不需要认证。

```json
{
  "status": "ok",
  "env": "local",
  "broker_mode": "paper"
}
```

## Brokers

`GET /v1/brokers`

返回当前支持的券商和状态。

```json
{
  "brokers": [
    {"id": "tiger", "status": "paper-ready"},
    {"id": "futu", "status": "planned"},
    {"id": "longbridge", "status": "planned"}
  ]
}
```

## Create Order Draft

`POST /v1/orders/drafts`

请求：

```json
{
  "broker": "tiger",
  "account_id": "paper-account",
  "symbol": "AAPL",
  "side": "buy",
  "order_type": "limit",
  "quantity": "1",
  "limit_price": "100",
  "client_memo": "test order"
}
```

响应：

```json
{
  "draft": {
    "id": "draft_xxx",
    "status": "draft",
    "risk_warnings": []
  },
  "required_confirmation": "CONFIRM BUY 1 AAPL"
}
```

## Confirm Order

`POST /v1/orders/{draft_id}/confirm`

请求：

```json
{
  "confirmation_text": "CONFIRM BUY 1 AAPL",
  "confirmed_by": "web-user"
}
```

确认文本必须和服务端返回的 `required_confirmation` 完全一致。确认成功后，服务才会调用券商适配器。

## Order Preview

`POST /v1/orders/preview`

请求复用下单请求。返回统一风控结果、预估金额、最大可交易数量和券商预览原始信息。老虎会调用券商 `preview_order()`；长桥当前返回统一风控和本地估算。

## Max Tradable Quantity

`POST /v1/orders/max-tradable-quantity`

返回统一最大可交易数量。长桥调用 `estimate_max_purchase_quantity()`，老虎调用 `get_estimate_tradable_quantity()`；本地 paper 模式买入按购买力估算，卖出按持仓估算。

## Orders

`GET /v1/accounts/{account_id}/orders?broker=tiger&symbol=AAPL&status=submitted`

返回统一订单列表。老虎调用 `get_orders()`，长桥调用 `today_orders()`。

`POST /v1/accounts/{account_id}/orders/{broker_order_id}/sync?broker=tiger`

拉取券商订单详情并写入 `order.status_synced` 审计事件。

`POST /v1/accounts/{account_id}/orders/{broker_order_id}/replace?broker=tiger`

改单。请求必须带 `confirmation_text` 和 `confirmed_by`。买入订单改单必须有 `limit_price` 或原订单限价，否则返回 `422`，避免无法估值的买单绕过购买力风控。买入订单改数量或价格时会重新执行购买力风控。

`POST /v1/accounts/{account_id}/orders/{broker_order_id}/cancel?broker=tiger`

撤单。服务端会先查询券商订单，只有 `submitted` 和 `partially_filled` 状态会继续调用券商撤单；订单不存在返回 `404`，终态订单返回 `409`。成功或提交后写入审计事件。

`GET /v1/accounts/{account_id}/orders/{broker_order_id}/fees?broker=tiger`

订单费用。老虎通过 `get_order(..., show_charges=True)` 映射；长桥当前返回 `501`。

## Executions

`GET /v1/accounts/{account_id}/executions/today?broker=longbridge&symbol=700.HK`

当日成交。长桥调用 `today_executions()`，老虎调用 `get_transactions()` 并按当日过滤。

`GET /v1/accounts/{account_id}/executions/history?broker=tiger&symbol=AAPL&date_from=2026-06-01T00:00:00Z&date_to=2026-06-04T23:59:59Z`

历史成交。长桥调用 `history_executions()`，老虎调用 `get_transactions()` 并按日期过滤。

## Market

`GET /v1/market/quotes?broker=tiger&symbols=AAPL,MSFT`

实时报价快照。老虎调用 `get_briefs(..., include_ask_bid=True)`；长桥调用 `realtime_quote()`。

行情接口支持只读 fallback：

- `broker=tiger`：只请求老虎，失败时返回 `501` 或 `502`。
- `broker=longbridge`：只请求长桥，失败时返回 `501` 或 `502`。
- `broker=auto`：按老虎、长桥顺序尝试，前一个券商权限不足、超时或不支持时自动切到下一个。
- `broker=tiger&fallback=true`：先请求老虎，失败后尝试长桥。

如果发生 fallback，响应中的每条行情会标注真实来源：

```json
{
  "quotes": [
    {
      "broker": "longbridge",
      "source_broker": "longbridge",
      "fallback_from": "tiger",
      "fallback_reason": "permission denied"
    }
  ]
}
```

`GET /v1/market/instruments/{symbol}?broker=longbridge`

股票基础信息。老虎调用 `get_contract()`；长桥调用 `static_info()`。同样支持 `broker=auto` 和 `fallback=true`，并返回 `source_broker`、`fallback_from`、`fallback_reason`。

注意：fallback 只用于实时报价、快照和股票基础信息。账户、持仓、订单、费用、成交、下单、改单、撤单不能跨券商 fallback。

## Audit Events

`GET /v1/audit/events`

返回敏感操作审计事件。生产版本应支持分页、时间过滤、主体过滤和导出。

## 错误约定

- `400`：请求不合法或确认文本错误。
- `401`：API Key 错误。
- `404`：资源不存在。
- `409`：订单草稿状态不可确认。
- `502`：券商真实接口调用失败。
- `501`：券商适配器尚未实现。
