# Data Model and Audit Spec

## 核心实体

### BrokerAccount

- `id`
- `broker`
- `display_name`
- `mode`
- `encrypted_credentials`
- `status`
- `created_at`
- `updated_at`

### Position

- `broker`
- `account_id`
- `symbol`
- `name`
- `quantity`
- `market_value`
- `currency`
- `cost_basis`
- `updated_at`

### OrderDraft

- `id`
- `broker`
- `account_id`
- `symbol`
- `side`
- `order_type`
- `quantity`
- `limit_price`
- `risk_warnings`
- `status`
- `created_by`
- `created_at`

### BrokerOrder

- `id`
- `draft_id`
- `broker`
- `broker_order_id`
- `status`
- `submitted_at`
- `raw_response`

### AuditEvent

- `id`
- `actor`
- `action`
- `subject`
- `details`
- `created_at`

## 审计要求

必须记录：

- 账户配置创建、修改、删除。
- 订单草稿创建。
- 订单确认。
- 订单提交。
- 券商返回异常。
- 登录失败和鉴权失败。
- MCP token 创建或撤销。

不允许记录：

- 券商密钥明文。
- 用户密码明文。
- 完整 JWT。
- 不必要的个人敏感信息。

## 保留策略

- MVP：审计事件可本地查看。
- 正式版：审计日志追加写入，默认保留 180 天。
- 代部署：应提供导出能力。
- 企业/团队：应支持不可变日志存储。

