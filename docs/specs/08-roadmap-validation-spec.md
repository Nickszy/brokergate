# Roadmap and Validation Spec

## 路线

### MVP 1: Tiger Gateway

- Docker + FastAPI。
- Tiger OpenAPI SDK 接入。
- Tiger paper adapter / paper account 验证。
- 查询账户和持仓。
- 创建订单草稿。
- 人工确认后提交。
- 审计日志。

### MVP 2: Web and MCP

- Web 配置面板。
- 只读 MCP 查询。
- MCP 创建交易草稿。
- Web 面板确认交易。

### MVP 3: Multi-Broker

- Futu OpenD sidecar。
- Longbridge adapter。
- 多账户聚合。
- 统一持仓视图。

### MVP 4: Pro Analytics

- 账户分析。
- 收益归因。
- 风险暴露。
- 交易复盘。
- AI 周报。

## 当前最该验证的问题

1. 用户是否愿意把券商 API 接到自部署服务。
2. 用户更想自己部署，还是愿意付费代部署。
3. 用户更在意交易执行，还是账户分析。
4. AI Skill/MCP 是真实需求，还是展示性功能。

## 验证方式

- GitHub README 和 MVP demo。
- V2EX / 掘金 / 知乎 / 量化社群发布建设过程。
- 访谈 10 个目标用户。
- 记录他们是否愿意提供券商 API、是否愿意付费部署、是否愿意购买账户分析。

## 进入下一阶段标准

MVP 1 进入 MVP 2 的条件：

- Tiger SDK 连接、paper 查询、paper 确认下单流程可用。
- 至少 3 个真实目标用户完成本地部署或跟随演示。
- 没有发现无法接受的合规或 ToS 风险。
- 用户对 AI 查询或交易草稿有明确兴趣。

MVP 2 进入 MVP 3 的条件：

- MCP 只读能力被真实使用。
- 用户明确需要 Futu 或 Longbridge。
- Web 面板确认流程比 API 确认更容易被接受。
