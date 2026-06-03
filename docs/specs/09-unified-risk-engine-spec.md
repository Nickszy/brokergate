# Unified Risk Engine Spec

## 结论

多券商接入不能让每个券商 adapter 自己做风控。BrokerGate 应该把 Tiger、Futu、Longbridge 的账户信息先归一化为同一份 `AccountSummary`，再由统一 `RiskEngine` 执行交易前检查。

首版只有一条规则：

```text
买入订单的预估占用金额不能超过该账户当前购买力。
```

这条规则必须在创建订单草稿之前执行。被风控拦截的订单不能进入可确认状态。

注意：这是目标风控架构里的第一个 MVP 规则，不是完整风控架构。完整多券商目标架构见 `docs/specs/10-multi-broker-target-architecture.md`。

## 多券商架构

```text
Client / Web / AI
  -> BrokerGate API
  -> Order Workflow
  -> Broker Adapter Registry
  -> Broker Adapter refreshes AccountSummary
  -> Unified RiskEngine
  -> OrderDraft
  -> Human Confirmation
  -> Broker Adapter submit_order
```

关键点：

- Adapter 负责连接券商和归一化账户快照。
- RiskEngine 只读取统一模型，不直接依赖 Tiger、Futu、Longbridge SDK。
- Workflow 负责保证风控在草稿创建前执行。
- Adapter 不能绕过 Workflow 自己下单。

## 统一账户快照

所有券商都必须映射到：

```python
class AccountSummary:
    broker: BrokerId
    account_id: str
    base_currency: str
    cash: Decimal
    buying_power: Decimal
    updated_at: datetime
    raw: dict
```

### 字段解释

- `cash`：账户现金或现金等价字段。
- `buying_power`：券商返回的可买入能力。首版风控只信这个字段。
- `base_currency`：账户基础币种。MVP 可先只支持 USD。
- `raw`：券商原始返回，用于排查，但不能给风控直接读取。

## Broker Adapter 要求

所有 adapter 必须实现：

```python
async def get_account_summary(account_id: str) -> AccountSummary:
    ...
```

返回前必须处理：

- 字段缺失。
- 多币种账户。
- 券商返回为空。
- 账户不可交易。
- 接口超时。

如果拿不到可靠购买力，不能默认放行，应返回错误或让风控阻断。

## 购买力规则

### 适用范围

- 只检查买入订单。
- 卖出订单首版默认不消耗购买力。
- 首版只允许有确定价格的买入订单通过风控。

### 计算

```text
required_amount = quantity * limit_price
```

然后比较：

```text
required_amount <= account_summary.buying_power
```

如果不满足，则阻断订单。

### 市价单

市价买入没有确定价格，首版不能可靠判断是否超过购买力，因此直接阻断。

后续可以引入行情快照和滑点 buffer：

```text
required_amount = quantity * latest_ask_price * 1.03
```

但这不是首版范围。

## 多币种处理

MVP 可以先限制：

- 美股订单只用 USD 购买力。
- 港股订单只用 HKD 购买力。
- 不做自动换汇估算。

如果订单币种和账户购买力币种不一致，首版应阻断，而不是自行估算汇率。

后续再加入：

- FX rate snapshot。
- 券商真实可用融资额度。
- 多币种购买力拆分。

## 时效性

购买力必须在创建订单草稿时刷新，不能使用长时间缓存。

建议：

- 查询账户快照。
- 立即执行风控。
- 立即创建订单草稿。
- 确认提交前，如果草稿超过 60 秒未确认，重新跑一次风控。

后续代码应增加 `risk_checked_at` 和 `risk_expires_at`。

## 审计

必须记录：

- 风控通过。
- 风控阻断。
- 使用的账户购买力。
- 预估占用金额。
- 规则 ID。
- 订单草稿 ID 或被阻断请求摘要。

审计示例：

```json
{
  "action": "risk.order_blocked",
  "subject": "tiger:paper-account:AAPL",
  "details": {
    "rule_id": "buying_power_limit",
    "required_amount": "10000000",
    "available_buying_power": "100000",
    "currency": "USD"
  }
}
```

## 为什么不放在券商 adapter 里

如果每个券商各自判断购买力，会出现三个问题：

- AI/MCP 无法获得一致的风控结果。
- 多账户聚合后无法比较风险。
- 后续增加仓位、集中度、黑名单等规则时会重复实现。

正确边界是：

```text
Broker Adapter = 获取事实
RiskEngine = 执行规则
Order Workflow = 保证顺序
```

## 当前代码骨架

当前 MVP 代码已经有：

- `src/brokergate/risk.py`：统一风控引擎。
- `AccountSummary`：统一账户快照。
- `RiskCheckResult`：风控结果。
- `TigerPaperAdapter.get_account_summary()`：paper 账户购买力占位。
- `OrderWorkflow.create_draft()`：创建草稿前执行风控。

后续接真实 Tiger/Futu/Longbridge 时，只需要让各 adapter 返回真实 `AccountSummary`，不要改风控规则本身。
