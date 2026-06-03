# MCP and AI Integration Spec

## 定位

BrokerGate 的 AI 集成不是让模型自动炒股，而是让模型成为账户查询、交易草稿生成和复盘分析的辅助入口。

## 首版 MCP 能力

MCP MVP 应先做只读：

- `get_account_summary`
- `list_positions`
- `list_recent_orders`
- `create_order_draft`

`create_order_draft` 可以生成草稿，但不能提交真实订单。

## 禁止能力

MCP 首版不提供：

- `submit_order`
- `cancel_order`
- `update_broker_credentials`
- `delete_audit_logs`

如果未来要加入撤单，也必须走独立权限和人工确认。

## Prompt 安全边界

工具说明必须明确：

- 不是投资建议工具。
- 不保证收益。
- 所有交易建议都只是草稿。
- 用户必须自行确认风险。

## 与 OpenClaw / Claude / Codex 的关系

BrokerGate 提供标准 REST API 和 MCP Server。Claude、Codex、OpenClaw、Cursor 等工具可以接入，但交易执行仍然回到 BrokerGate 的确认流程。

## AI 账户分析 Pro

Pro 方向包括：

- 持仓日报/周报。
- 收益归因。
- 风险暴露。
- 交易复盘。
- 策略记录。
- 异常提醒。

这些能力应优先依赖账户和订单历史，而不是直接读取聊天上下文。

