# Broker Adapter Spec

## 目标

Adapter 层把统一账户、持仓、订单模型转换为具体券商 SDK 调用。业务层不能直接依赖 Tiger、Futu 或 Longbridge SDK。

## 通用接口

首版代码只实现 `submit_order()`，正式接口应扩展为：

```python
class BrokerAdapter:
    async def test_connection(self, account_config): ...
    async def get_account_summary(self, account_id): ...
    async def list_positions(self, account_id): ...
    async def list_orders(self, account_id, filters): ...
    async def submit_order(self, draft): ...
    async def cancel_order(self, broker_order_id): ...
```

`get_account_summary()` 是多券商统一风控的强制接口。每个 adapter 必须返回统一 `AccountSummary`，其中 `buying_power` 是首版风控唯一可信输入。拿不到可靠购买力时，adapter 不能返回猜测值，应抛出统一错误并阻断交易流程。

## Tiger

MVP 1 优先接 Tiger：

- 使用官方 `tigeropen` Python SDK。
- 支持 paper account 优先。
- 读取用户自有配置文件或 OpenBroker 加密配置。
- 查询账户。
- 查询持仓。
- 提交 limit order。
- 记录券商原始返回，但对外响应使用统一模型。
- 详细步骤见 `docs/guides/tiger-openapi-integration.md`。

Tiger 接入必须分阶段：

1. `connection-ready`：SDK 初始化和账户查询可用。
2. `query-ready`：账户、现金、持仓查询可用。
3. `paper-trade-ready`：paper 下单可用。
4. `trade-ready`：live 下单可用，并通过确认和审计验收。

## Futu

Futu 需要 OpenD sidecar。部署规格必须明确：

- OpenD 是否运行在同一台服务器。
- OpenD 端口、解锁方式、重连策略。
- OpenD 日志和 OpenBroker 审计日志的关联方式。

## Longbridge

Longbridge 通过官方 `longbridge` Python SDK 接入。旧包名 `longport` 已废弃，不应作为新实现依赖。

Longbridge 接入分两条路径：

- SDK adapter：OpenBroker 主路径，用于账户快照、持仓、风控和确认后下单。
- Hosted MCP：长桥官方 AI 入口，只作为参考或用户单独使用，不作为 OpenBroker 的交易执行后端。

Longbridge adapter 优先阶段：

1. `query-ready`：`account_balance()` 和 `stock_positions()` 可用。
2. `risk-ready`：购买力字段能映射到统一 `AccountSnapshot`。
3. `paper-trade-ready`：限价单经统一风控和人工确认后提交。
4. `trade-ready`：live 下单可用，并通过审计和风控验收。

长桥有 `estimate_max_purchase_quantity()`，可以作为券商特有的额外 precheck，但不能替代 OpenBroker 的统一购买力规则。详细方案见 `docs/guides/longbridge-openapi-integration.md`。

## 适配器状态

- `paper-ready`：可在模拟模式提交。
- `connection-ready`：可初始化 SDK 并完成最小账户查询。
- `query-ready`：只支持查询。
- `paper-trade-ready`：支持 paper account 下单。
- `trade-ready`：支持真实交易。
- `planned`：已规划但未实现。
- `disabled`：用户或系统关闭。

## 失败处理

Adapter 必须把券商异常转换成统一错误：

- 连接失败。
- 鉴权失败。
- 账户状态异常。
- 订单参数被券商拒绝。
- 市场关闭。
- 订单已提交但本地回执失败。

最后一种必须进入人工核查状态，不能自动重试下单。
