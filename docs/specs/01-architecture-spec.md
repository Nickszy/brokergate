# Architecture Spec

## 架构目标

首版采用单体服务，而不是提前拆成多个微服务。核心原因是 MVP 需要快速验证真实使用、部署难度和安全边界。服务内部按模块拆分，保留未来扩展到多券商、多账户、MCP 和 Pro 分析的空间。

目标架构先按多券商交易控制平面设计，MVP 只是其中一个很小的实现切片。完整多券商边界见 `docs/specs/10-multi-broker-target-architecture.md`。

## 组件

```text
Client / AI Agent / Web Panel
  -> OpenBroker REST API
  -> Auth and safety middleware
  -> Order workflow
  -> Unified risk engine
  -> Broker adapter registry
  -> Tiger / Futu / Longbridge adapter
  -> Audit log
```

## 模块边界

- API 层：只处理 HTTP、认证、请求校验、响应模型。
- Workflow 层：负责订单草稿、确认、提交、审计串联。
- RiskEngine 层：基于统一账户快照执行交易前风控，首版只检查买入金额不超过账户购买力。
- Adapter 层：把统一模型转换成券商 SDK 调用。
- Store 层：保存账户配置、订单草稿、订单结果、审计日志。
- AI Integration 层：只读查询优先，交易能力必须走草稿和确认。

## 当前代码骨架

- `src/openbroker/main.py`：FastAPI 入口。
- `src/openbroker/models.py`：统一请求、订单、审计模型。
- `src/openbroker/services.py`：订单工作流。
- `src/openbroker/risk.py`：统一风控引擎。
- `src/openbroker/adapters/`：券商适配器接口和 Tiger paper 占位实现。
- `src/openbroker/storage.py`：MVP 内存存储，后续替换为数据库。

## 后续持久化

MVP 运行骨架使用内存存储，只用于接口和流程验证。正式版本应切换到 PostgreSQL 或 SQLite：

- 本地和轻量部署：SQLite。
- 多账户和代部署：PostgreSQL。
- 审计日志：追加写入，不允许业务层物理删除。

## 多券商和统一风控

多券商接入的关键不是把 Tiger、Futu、Longbridge 的 SDK 方法名对齐，而是让每个 adapter 输出同一份账户事实：

- 账户 ID。
- 基础币种。
- 现金。
- 购买力。
- 持仓。
- 券商原始返回。

风控层只读取统一模型，不直接依赖任何券商 SDK。首版唯一规则是：买入订单的预估占用金额不能超过该账户当前购买力。详细规格见 `docs/specs/09-unified-risk-engine-spec.md`。
