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

## Audit Events

`GET /v1/audit/events`

返回敏感操作审计事件。生产版本应支持分页、时间过滤、主体过滤和导出。

## 错误约定

- `400`：请求不合法或确认文本错误。
- `401`：API Key 错误。
- `404`：资源不存在。
- `409`：订单草稿状态不可确认。
- `501`：券商适配器尚未实现。

