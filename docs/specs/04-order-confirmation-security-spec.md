# Order Confirmation and Security Spec

## 安全原则

- 默认不自动交易。
- AI 只能创建订单草稿。
- 订单执行必须有人类确认。
- 创建订单草稿前必须先通过统一风控。
- 确认动作必须可审计。
- 交易接口必须比查询接口有更高权限。

## 订单状态

```text
draft -> confirmed -> submitted
draft -> rejected
request -> risk_blocked
submitted -> broker_filled / broker_cancelled / broker_rejected
```

MVP 代码当前覆盖 `draft -> confirmed -> submitted`。

## 二次确认

二次确认不是风控替代品。正确顺序是：

```text
请求下单 -> 刷新账户购买力 -> 风控检查 -> 创建草稿 -> 用户确认 -> 提交券商
```

如果风控失败，不能生成可确认草稿。

服务端生成确认文本：

```text
CONFIRM BUY 1 AAPL
```

用户提交确认请求时必须原样传回。Web 面板后续可以加入：

- 按钮确认。
- 风险摘要。
- 交易金额估算。
- 短信/邮箱/Passkey 二次验证。

## AI 调用限制

AI/MCP 默认只能访问：

- 账户摘要。
- 持仓。
- 订单草稿创建。
- 审计查询。

AI/MCP 不允许直接调用：

- 真实下单。
- 撤单。
- 修改券商密钥。
- 删除审计日志。

## 密钥处理

首版 `.env` 只用于开发。正式版本必须实现：

- 加密保存券商凭证。
- 主密钥从环境变量或外部 secret manager 注入。
- 配置页面不回显完整密钥。
- 审计日志永不记录密钥明文。

## 部署安全

- 生产必须启用 HTTPS。
- API Key 必须使用强随机值。
- 管理面板必须限制登录。
- 默认不开公网真实交易接口。
- 建议按 IP allowlist 限制管理入口。
