# Multi-Broker Target Architecture

## 核心判断

BrokerGate 的架构核心不是“把多个券商 API 包一层统一 REST”，而是建立一个券商中立的交易控制平面：

```text
券商连接层 -> 统一账户/订单模型 -> 统一风控 -> 订单生命周期 -> 人工确认 -> 券商执行 -> 审计账本
```

MVP 只实现这条链路里很小的一段：单券商、单账户、买入金额不超过购买力。但所有模型和边界都应该按多券商目标架构设计。

## 目标架构

```text
Client / Web / AI / MCP
  -> API Gateway
  -> Auth and permission layer
  -> Order Intent Service
  -> Broker Account Snapshot Service
  -> Risk Engine
  -> Order Draft Service
  -> Human Confirmation
  -> Execution Coordinator
  -> Broker Adapter Registry
      -> Tiger Adapter
      -> Futu Adapter
      -> Longbridge Adapter
  -> Audit Ledger
```

## 关键域模型

### BrokerAccount

券商账户配置，不等于账户资产。

- `broker`
- `account_id`
- `display_name`
- `mode`: `paper` / `live-query` / `live-trade`
- `capabilities`
- `credential_ref`
- `status`

### AccountSnapshot

某一时刻从券商拉回来的账户事实。

- `broker`
- `account_id`
- `snapshot_id`
- `base_currency`
- `cash_by_currency`
- `buying_power_by_currency`
- `margin_enabled`
- `positions`
- `open_orders`
- `raw_ref`
- `fetched_at`
- `expires_at`

风控只能读取 `AccountSnapshot`，不能直接读取券商 SDK 原始对象。

### OrderIntent

用户、Web 或 AI 想做的一笔交易意图。它还不是订单草稿。

- `broker`
- `account_id`
- `symbol`
- `market`
- `side`
- `order_type`
- `quantity`
- `limit_price`
- `currency`
- `source`: `web` / `api` / `mcp` / `ai`

### RiskDecision

风控对 `OrderIntent + AccountSnapshot` 的判断。

- `decision`: `pass` / `block` / `manual_review`
- `rule_results`
- `snapshot_id`
- `checked_at`
- `expires_at`

### OrderDraft

只有通过风控的 `OrderIntent` 才能变成草稿。

- `draft_id`
- `intent`
- `risk_decision`
- `required_confirmation`
- `status`

### BrokerOrder

券商真实回执。

- `draft_id`
- `broker_order_id`
- `broker_status`
- `submitted_at`
- `last_synced_at`

## 多券商边界

每个券商 adapter 只负责三件事：

1. 连接券商。
2. 把券商事实归一化成 BrokerGate 模型。
3. 执行已经确认的订单。

adapter 不负责：

- 决定订单是否安全。
- 判断 AI 能不能下单。
- 跳过人工确认。
- 写业务审计结论。
- 做跨券商聚合。

## Adapter 能力接口

目标接口：

```python
class BrokerAdapter:
    async def get_capabilities(self) -> BrokerCapabilities: ...
    async def test_connection(self, account_id: str) -> ConnectionStatus: ...
    async def refresh_account_snapshot(self, account_id: str) -> AccountSnapshot: ...
    async def list_positions(self, account_id: str) -> list[Position]: ...
    async def list_orders(self, account_id: str, filters: OrderFilters) -> list[BrokerOrder]: ...
    async def submit_order(self, draft: OrderDraft) -> BrokerOrderReceipt: ...
    async def sync_order_status(self, broker_order_id: str) -> BrokerOrder: ...
```

`refresh_account_snapshot()` 是统一风控的入口。任何交易前风控都必须先拿到新鲜 snapshot。

## 风控架构

风控引擎是规则编排器，不是券商接口。

```text
OrderIntent
  + AccountSnapshot
  + BrokerCapabilities
  -> RiskEngine
  -> RiskDecision
```

首期只启用一个规则：

```text
buying_power_limit:
  buy_required_amount <= account_snapshot.buying_power_by_currency[order.currency]
```

但规则框架要支持后续增加：

- 单笔订单金额上限。
- 单票集中度。
- 行业集中度。
- 黑名单标的。
- 日内交易次数。
- AI 来源订单更严格阈值。
- 期权/融资/做空禁用规则。

## 购买力规则的正确抽象

不要把“购买力”写死成某个券商字段。不同券商可能返回：

- cash available。
- buying power。
- available funds。
- max buying amount。
- margin buying power。

adapter 负责把这些字段映射成：

```python
buying_power_by_currency: dict[str, Decimal]
```

首版可以只有：

```python
{"USD": Decimal("100000")}
```

如果券商只返回综合购买力，但无法确定币种，不能直接放行，应标记为不可风控。

## 多账户和跨券商

风控默认按 `broker + account_id + currency` 隔离：

```text
Tiger U123 USD buying power 不能补 Longbridge 账户不足。
Futu HKD buying power 不能补 Tiger USD 订单。
```

跨券商聚合只用于展示和分析，不用于首版交易风控。后续如果要支持组合级风控，也是在账户级风控之后叠加，而不是替代账户级风控。

## 订单生命周期

```text
intent_created
  -> snapshot_refreshed
  -> risk_passed / risk_blocked / manual_review
  -> draft_created
  -> user_confirmed
  -> broker_submitted
  -> broker_accepted / broker_rejected
  -> filled / cancelled / expired
```

MVP 可以少做状态，但不能改变顺序：

```text
刷新账户 -> 风控 -> 草稿 -> 确认 -> 提交
```

## MVP Slice

MVP 只做目标架构的一小段：

- 一个 adapter：Tiger paper 或 Tiger live-query。
- 一个账户。
- 一个账户快照字段：`buying_power`。
- 一个风控规则：买入金额不能超过购买力。
- 一个订单类型：限价买入/卖出。
- 一个执行路径：人工确认后提交。

不做：

- 跨券商组合风控。
- 多币种自动换汇。
- 期权、融资、做空。
- 市价单购买力估算。
- 自动重试下单。
- AI 直接执行交易。

## 架构 ADR

### ADR-001: 风控放在 BrokerGate 统一层，不放在 broker adapter

决定：adapter 只提供账户事实和执行能力，RiskEngine 统一判断订单是否允许。

理由：

- 后续新增券商时不重复写规则。
- AI/MCP/Web/API 得到同一套风控结果。
- 审计日志可以解释每笔订单为什么通过或被阻断。

代价：

- adapter 必须做更严格的数据归一化。
- 初期需要定义统一模型，不能只快接 SDK。

### ADR-002: 首版购买力按账户隔离，不做跨券商抵扣

决定：首版风控只看目标下单账户自己的购买力。

理由：

- 券商之间资金不可即时互抵。
- 多币种和保证金口径差异大。
- 最小规则更容易审计和解释。

代价：

- 组合级风险暂时不能表达。
- 某些真实可调拨资金不会被用于放行订单。

### ADR-003: 市价买入首版默认阻断

决定：没有确定价格的买入订单不能通过购买力规则。

理由：

- 无法可靠计算占用金额。
- 不应该用行情快照随意估算真实交易风险。

代价：

- MVP 交易类型更窄。
- 用户需要先用限价单验证流程。

### ADR-004: 长桥 hosted MCP 不作为 BrokerGate 交易后端

决定：长桥官方 hosted MCP 可以作为用户调研、只读体验和工具命名参考，但 BrokerGate 不通过它执行交易。

理由：

- hosted MCP 的下单路径不经过 BrokerGate 的统一风控。
- OAuth 凭证由 AI client 管理，审计边界不在 BrokerGate 内。
- BrokerGate 的定位是自部署交易控制平面，而不是 MCP 转发器。

代价：

- 需要单独实现 Longbridge SDK adapter。
- 无法直接复用官方 MCP 的工具能力完成 MVP。
