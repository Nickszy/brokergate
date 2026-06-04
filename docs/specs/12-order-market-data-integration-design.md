# 订单和行情扩展接入设计

## 背景

BrokerGate 当前已经完成最小交易闭环：账户快照、购买力风控、订单草稿、人工确认、券商提交和审计。下一阶段要补齐交易后续管理和最小行情查询能力：

- 订单查询
- 订单预览
- 最大可交易数量
- 改单
- 撤单
- 订单费用
- 当日成交
- 历史成交
- 订单状态同步
- 实时报价和快照
- 股票基础信息

这些能力需要继续走统一模型，不能让上层 API 直接暴露老虎、长桥、富途 SDK 的对象结构。

## 当前实现状态

第一版已经落地统一模型、统一 API 和老虎/长桥的主要 SDK 映射：

| 能力 | 长桥 | 老虎 | 富途 |
| --- | --- | --- | --- |
| 订单查询 | 已接入 `today_orders()` | 已接入 `get_orders()` | 未接入 |
| 订单状态同步 | 已接入 `order_detail()` 拉取式同步 | 已接入 `get_order()` 拉取式同步 | 未接入 |
| 订单预览 | 统一风控和本地估算，券商侧预览未接入 | 已接入 `preview_order()` | 未接入 |
| 最大可交易数量 | 已接入 `estimate_max_purchase_quantity()` | 已接入 `get_estimate_tradable_quantity()` | 未接入 |
| 改单 | 已接入 `replace_order()`，提交前校验确认文本并重新风控 | 已接入 `modify_order()`，提交前校验确认文本并重新风控 | 未接入 |
| 撤单 | 已接入 `cancel_order()` | 已接入 `cancel_order()` | 未接入 |
| 订单费用 | 未接入，继续返回 `501` | 已接入 `get_order(..., show_charges=True)` | 未接入 |
| 当日成交 | 已接入 `today_executions()` | 已接入 `get_transactions()` 当日过滤 | 未接入 |
| 历史成交 | 已接入 `history_executions()` | 已接入 `get_transactions()` 日期过滤 | 未接入 |
| 实时报价和快照 | 已接入 `realtime_quote()` | 已接入 `get_briefs(..., include_ask_bid=True)` | 未接入 |
| 股票基础信息 | 已接入 `static_info()` | 已接入 `get_contract()` | 未接入 |

没有真实 SDK 映射的能力必须继续返回 `501`，不能返回空列表伪装成功。

## 设计原则

1. 只读能力可以直接调用券商适配器，但必须返回统一模型。
2. 会改变账户状态的能力必须写审计事件。
3. 改单如果增加买入金额或改变标的、方向、数量、价格，必须重新走统一风控。
4. 撤单是交易变更能力，必须有审计和幂等处理。
5. 订单状态以券商为准，BrokerGate 本地状态只做缓存和审计，不伪造成交状态。
6. 行情能力先做快照查询，不做订阅推送。
7. 实时报价、快照和股票基础信息是只读市场数据，可以通过 `broker=auto` 或 `fallback=true` 走多券商 fallback；响应必须标注真实数据来源。
8. 账户、持仓、订单、费用、成交、下单、改单、撤单不能 fallback 到其他券商，必须绑定账户所属券商。
9. 富途先按接口契约和 OpenD 部署边界接入；没有 OpenD 时必须返回明确的 `501` 或连接失败，不允许走本地假成功。

## 统一模型

### BrokerOrder

```python
class BrokerOrder(BaseModel):
    broker: BrokerId
    account_id: str
    broker_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    filled_quantity: Decimal = Decimal("0")
    limit_price: Decimal | None = None
    average_fill_price: Decimal | None = None
    status: BrokerOrderStatus
    currency: str
    submitted_at: datetime | None = None
    updated_at: datetime
    raw: dict[str, Any] = Field(default_factory=dict)
```

### BrokerOrderStatus

```python
class BrokerOrderStatus(StrEnum):
    unknown = "unknown"
    submitted = "submitted"
    partially_filled = "partially_filled"
    filled = "filled"
    cancelled = "cancelled"
    rejected = "rejected"
    expired = "expired"
```

### OrderPreview

```python
class OrderPreview(BaseModel):
    broker: BrokerId
    account_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    limit_price: Decimal | None = None
    estimated_amount: Decimal | None = None
    estimated_fees: Decimal | None = None
    max_tradable_quantity: Decimal | None = None
    risk_checks: list[RiskCheckResult] = Field(default_factory=list)
    broker_preview: dict[str, Any] = Field(default_factory=dict)
```

### TradableQuantity

```python
class TradableQuantity(BaseModel):
    broker: BrokerId
    account_id: str
    symbol: str
    side: OrderSide
    price: Decimal | None = None
    currency: str
    max_quantity: Decimal
    raw: dict[str, Any] = Field(default_factory=dict)
```

### OrderFee

```python
class OrderFee(BaseModel):
    broker: BrokerId
    account_id: str
    broker_order_id: str | None = None
    symbol: str | None = None
    currency: str
    total_fee: Decimal | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
```

### OrderExecution

```python
class OrderExecution(BaseModel):
    broker: BrokerId
    account_id: str
    broker_order_id: str | None = None
    execution_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    currency: str
    executed_at: datetime
    raw: dict[str, Any] = Field(default_factory=dict)
```

### QuoteSnapshot

```python
class QuoteSnapshot(BaseModel):
    broker: BrokerId
    source_broker: BrokerId | None = None
    fallback_from: BrokerId | None = None
    fallback_reason: str | None = None
    symbol: str
    name: str | None = None
    currency: str
    last_price: Decimal | None = None
    bid_price: Decimal | None = None
    ask_price: Decimal | None = None
    open_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    previous_close: Decimal | None = None
    timestamp: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
```

### InstrumentProfile

```python
class InstrumentProfile(BaseModel):
    broker: BrokerId
    source_broker: BrokerId | None = None
    fallback_from: BrokerId | None = None
    fallback_reason: str | None = None
    symbol: str
    name: str | None = None
    market: str | None = None
    currency: str | None = None
    instrument_type: str | None = None
    lot_size: Decimal | None = None
    tradable: bool | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
```

## 统一 API

### 订单查询

`GET /v1/accounts/{account_id}/orders?broker=tiger&symbol=AAPL&status=submitted&from=2026-06-01&to=2026-06-04`

返回：

```json
{
  "orders": []
}
```

### 单个订单状态同步

`POST /v1/accounts/{account_id}/orders/{broker_order_id}/sync?broker=tiger`

行为：

- 调用适配器查询券商订单详情。
- 返回统一 `BrokerOrder`。
- 写入 `order.status_synced` 审计事件。
- 如果券商查不到订单，返回 `404`。

### 订单预览

`POST /v1/orders/preview`

请求复用 `TradeOrderRequest`。

行为：

- 查询账户快照。
- 执行统一风控。
- 调用券商侧预览能力；如果该券商没有可用预览，则返回统一风控结果和本地估算。
- 不创建订单草稿，不提交订单。

### 最大可交易数量

`POST /v1/orders/max-tradable-quantity`

请求：

```json
{
  "broker": "longbridge",
  "account_id": "paper-account",
  "symbol": "700.HK",
  "side": "buy",
  "price": "380",
  "currency": "HKD"
}
```

行为：

- 优先调用券商侧最大可交易数量接口。
- 如果券商不支持，使用 `buying_power / price` 做保守估算，并在 `raw.source` 标注 `local_estimate`。
- 对卖出方向，后续应基于持仓数量估算；首版可以只支持买入方向。

### 改单

`POST /v1/accounts/{account_id}/orders/{broker_order_id}/replace?broker=tiger`

请求：

```json
{
  "quantity": "2",
  "limit_price": "101",
  "confirmation_text": "CONFIRM REPLACE 2 AAPL 101",
  "confirmed_by": "web-user"
}
```

行为：

- 改单必须写 `order.replace_requested` 和 `order.replace_submitted` 审计事件。
- 改单前查询原订单。
- 如果买入订单的数量或价格增加，必须用新数量和新价格重新执行购买力风控。
- 确认文本必须由服务端生成并完全匹配。实现时可以先提供 `POST /v1/orders/{broker_order_id}/replace/preview` 生成确认文本，再提交改单。

### 撤单

`POST /v1/accounts/{account_id}/orders/{broker_order_id}/cancel?broker=tiger`

请求：

```json
{
  "confirmed_by": "web-user",
  "reason": "user requested"
}
```

行为：

- 撤单必须幂等。如果订单已经取消或已终态，返回当前订单状态，不重复调用券商撤单。
- 写 `order.cancel_requested` 和 `order.cancel_submitted` 审计事件。

### 订单费用

`GET /v1/accounts/{account_id}/orders/{broker_order_id}/fees?broker=futu`

行为：

- 如果券商支持订单费用查询，返回统一 `OrderFee`。
- 如果券商只支持预估费用，不支持已提交订单费用，返回 `501` 并说明原因。

### 当日成交

`GET /v1/accounts/{account_id}/executions/today?broker=longbridge&symbol=700.HK`

返回统一 `OrderExecution` 列表。

### 历史成交

`GET /v1/accounts/{account_id}/executions/history?broker=futu&from=2026-06-01&to=2026-06-04&symbol=AAPL`

返回统一 `OrderExecution` 列表。

### 实时报价和快照

`GET /v1/market/quotes?broker=tiger&symbols=AAPL,MSFT`

返回：

```json
{
  "quotes": []
}
```

首版只做拉取式快照，不做订阅。

只读行情支持 fallback：

- `broker=tiger`：只请求老虎。
- `broker=longbridge`：只请求长桥。
- `broker=auto`：按老虎、长桥顺序尝试。
- `fallback=true`：显式券商失败后继续尝试其他已配置券商。

发生 fallback 时，每条 `QuoteSnapshot` 必须包含：

- `source_broker`：真实返回数据的券商。
- `fallback_from`：第一个失败的请求券商。
- `fallback_reason`：第一个失败原因，便于调用方排查权限、超时或不支持能力。

该机制只用于行情和标的基础信息，不能用于交易、账户、订单、费用和成交。

### 股票基础信息

`GET /v1/market/instruments/{symbol}?broker=longbridge`

返回统一 `InstrumentProfile`。同样支持 `broker=auto` 和 `fallback=true`，并返回 `source_broker`、`fallback_from`、`fallback_reason`。

### 行情路由器

新增 `MarketDataRouter`，位于统一服务层，不放进单个券商适配器。

行为：

- 默认优先级：老虎、长桥。
- `broker=auto` 时按优先级尝试所有已配置适配器。
- 显式 `broker=tiger&fallback=true` 时先尝试老虎，再尝试长桥。
- `NotImplementedError`、权限不足、连接超时、券商服务失败都可以触发只读 fallback。
- 所有尝试失败时，如果最后失败是不支持能力，返回 `501`；如果最后失败是券商调用错误，返回 `502`。
- 成功响应必须标注真实来源，不能让调用方误判数据来自请求里的券商。

## 适配器契约

`BrokerAdapter` 需要扩展为：

```python
class BrokerAdapter:
    async def test_connection(self, account_id: str) -> bool: ...
    async def get_account_summary(self, account_id: str, currency: str | None = None) -> AccountSummary: ...
    async def list_positions(self, account_id: str) -> list[Position]: ...
    async def list_orders(self, account_id: str, filters: OrderQueryFilters | None = None) -> list[BrokerOrder]: ...
    async def get_order(self, account_id: str, broker_order_id: str) -> BrokerOrder: ...
    async def preview_order(self, request: TradeOrderRequest, account_summary: AccountSummary) -> OrderPreview: ...
    async def get_max_tradable_quantity(self, request: MaxTradableQuantityRequest) -> TradableQuantity: ...
    async def submit_order(self, draft: OrderDraft) -> BrokerOrderReceipt: ...
    async def replace_order(self, request: ReplaceOrderRequest) -> BrokerOrder: ...
    async def cancel_order(self, request: CancelOrderRequest) -> BrokerOrder: ...
    async def get_order_fees(self, request: OrderFeeRequest) -> OrderFee: ...
    async def list_today_executions(self, account_id: str, filters: ExecutionQueryFilters | None = None) -> list[OrderExecution]: ...
    async def list_history_executions(self, account_id: str, filters: ExecutionQueryFilters) -> list[OrderExecution]: ...
    async def get_quote_snapshots(self, symbols: list[str]) -> list[QuoteSnapshot]: ...
    async def get_instrument_profile(self, symbol: str) -> InstrumentProfile: ...
```

不支持的能力必须抛出统一 `NotImplementedError` 或项目自定义 `BrokerCapabilityNotSupported`，由 API 层转换为 `501`。

## 券商方法映射

### 长桥

| 能力 | 官方能力 | BrokerGate 实现要求 |
| --- | --- | --- |
| 订单查询 | 当日订单、历史订单、订单详情 | 先接 `today_orders()`；历史订单和详情按 SDK 能力补齐 |
| 订单预览 | 估算最大可买数量可作为预检查 | `preview_order()` 先返回统一风控和本地估算；最大可买数量单独调用券商能力 |
| 最大可交易数量 | 估算最大可买数量 | 接入为 `get_max_tradable_quantity()` |
| 改单 | 修改订单 | 接入 `replace_order()`，改大买入金额时重新风控 |
| 撤单 | 取消订单 | 接入 `cancel_order()`，要求幂等 |
| 订单费用 | 文档主交易目录没有单列订单费用 | 首版返回 `501`，除非 SDK 有明确费用接口 |
| 当日成交 | 当日成交 | 接入 `list_today_executions()` |
| 历史成交 | 历史成交 | 接入 `list_history_executions()` |
| 状态同步 | 订单详情或订单查询 | `sync_order_status()` 可用 `get_order()` 实现 |
| 实时报价和快照 | 股票报价 | 接入 `QuoteContext` 快照查询 |
| 股票基础信息 | 股票静态信息 | 接入静态信息接口 |

### 老虎

| 能力 | 官方能力 | BrokerGate 实现要求 |
| --- | --- | --- |
| 订单查询 | 订单列表、未成交、已成交、已取消 | 扩展现有 `list_orders()`，增加过滤参数并公开 HTTP 接口 |
| 订单预览 | 订单预览、交易订单预览 | 接入为 `preview_order()`，并合并统一风控结果 |
| 最大可交易数量 | 最大可交易数量 | 接入为 `get_max_tradable_quantity()` |
| 改单 | 修改订单 | 接入 `replace_order()`，改大买入金额时重新风控 |
| 撤单 | 撤销订单 | 接入 `cancel_order()`，要求幂等 |
| 订单费用 | 官方交易目录没有单列订单费用 | 首版返回 `501`，除非 SDK 有明确费用接口 |
| 当日成交 | 成交记录 | 先接成交记录并按日期过滤 |
| 历史成交 | 成交记录 | 先接成交记录并按日期过滤 |
| 状态同步 | 订单查询 | `sync_order_status()` 可用 `get_order()` 或订单列表过滤实现 |
| 实时报价和快照 | 实时报价 | 接入 `QuoteClient` 快照查询 |
| 股票基础信息 | 合约查询 | 接入合约查询，返回 `InstrumentProfile` |

### 富途

| 能力 | 官方能力 | BrokerGate 实现要求 |
| --- | --- | --- |
| 订单查询 | 订单列表、历史订单 | 新增 `FutuOpenApiAdapter`，通过 OpenD 查询 |
| 订单预览 | 官方交易总览没有单列订单预览 | 首版可返回统一风控和本地估算；没有券商预览时标注 `local_estimate` |
| 最大可交易数量 | 最大可买卖数量 | 接入为 `get_max_tradable_quantity()` |
| 改单 | 改单 | 接入 `replace_order()` |
| 撤单 | 撤单 | 接入 `cancel_order()` |
| 订单费用 | 订单费用 | 接入 `get_order_fees()` |
| 当日成交 | 当日成交 | 接入 `list_today_executions()` |
| 历史成交 | 历史成交 | 接入 `list_history_executions()` |
| 状态同步 | 订单列表、订单回调 | 首版用拉取式 `get_order()`；推送后续再接 |
| 实时报价和快照 | 市场快照、实时报价 | 接入行情上下文快照查询 |
| 股票基础信息 | 股票基础信息 | 接入基础信息查询 |

## 错误和审计

| 场景 | HTTP 状态 | 审计动作 |
| --- | --- | --- |
| 券商不支持能力 | `501` | 不写审计，除非是交易变更请求 |
| 券商连接失败 | `502` | `broker.call_failed` |
| 订单不存在 | `404` | 不写审计 |
| 改单风控不通过 | `422` | `risk.order_replace_blocked` |
| 改单提交成功 | `200` | `order.replace_submitted` |
| 撤单提交成功 | `200` | `order.cancel_submitted` |
| 状态同步成功 | `200` | `order.status_synced` |

## 开发拆分

### 第一阶段：统一模型和只读接口

- 增加统一模型。
- 扩展适配器抽象类。
- 暴露订单查询、订单状态同步、当日成交、历史成交、实时报价、股票基础信息。
- 老虎和长桥先实现可明确映射的能力。
- 富途先返回 `501`，同时保留适配器结构。

### 第二阶段：预检查和费用

- 增加订单预览。
- 增加最大可交易数量。
- 增加订单费用。
- 没有券商原生能力时返回明确 `501` 或本地保守估算，不能伪装成券商结果。

### 第三阶段：交易变更

- 增加改单预览和改单确认。
- 增加撤单。
- 改单重新走风控。
- 所有交易变更写审计。

### 第四阶段：富途真实接入

- 增加 OpenD 配置项。
- 增加 `FutuOpenApiAdapter`。
- 明确 OpenD 进程部署、交易解锁、重连和健康检查。

## 测试要求

- 每个新增模型有序列化测试。
- 每个新增 HTTP 接口至少有本地 paper 或 mock 测试。
- 老虎和长桥 SDK 调用必须 mock，不在 CI 里调用真实券商。
- 改单增加买入金额必须有风控阻断测试。
- 撤单重复调用必须有幂等测试。
- 不支持能力必须返回 `501`，不能返回空列表伪装成功。
