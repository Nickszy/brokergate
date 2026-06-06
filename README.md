# BrokerGate

> Connect broker accounts. Confirm every trade. Understand every portfolio.

BrokerGate is a self-hosted broker gateway for developers, AI agents, and modern investing workflows. It connects multiple broker APIs behind one local control plane, keeps execution human-confirmed, and provides the foundation for portfolio analytics, risk monitoring, and AI-powered account insights.

中文版本见下方 [中文说明](#中文说明)。

## Overview

BrokerGate connects broker APIs behind one local control plane. AI tools and external clients can query accounts and create order drafts, but execution must pass BrokerGate risk checks and human confirmation before the broker SDK is called.

BrokerGate is not an auto-trading bot, not a broker, and does not provide investment advice.

The long-term product direction is:

```text
Open-source Broker Gateway
+
Portfolio Intelligence Layer
```

In other words: the connection and execution layer should remain safe, self-hosted, and developer-friendly; the value-added layer can build on unified account data to support portfolio aggregation, trading review, risk alerts, and AI account analysis.

## Features

- Unified REST API for Tiger and Longbridge adapters
- Account summary, positions, order drafts, confirmation, order management, executions, and audit events
- First risk rule: buy orders cannot exceed account buying power
- Read-only quote and instrument profile fallback across configured market data adapters
- Next.js web dashboard for aggregated assets, positions, broker connection state, and human-confirmed order drafts
- Broker SDK paper-account path when credentials are configured
- Local paper fallback when no broker credentials are configured
- Docker Compose deployment for local and VPS installs
- Foundation for portfolio intelligence: asset aggregation, trading review, risk monitoring, and AI insights

## Product Layers

### 1. Broker Gateway

The open-source gateway layer provides a unified interface for broker accounts.

It normalizes:

- Accounts
- Assets
- Positions
- Orders
- Trades / executions
- Audit events

The safety model is intentionally conservative: AI tools may prepare order drafts, but real execution must go through risk checks and human confirmation.

### 2. Portfolio Intelligence

The intelligence layer builds on the unified account model.

Planned directions include:

- Multi-account asset aggregation
- Portfolio exposure and concentration analysis
- Profit and loss attribution
- Trading behavior review
- Risk alerts and holding monitoring
- AI account Q&A and investment workflow integrations

This layer is designed to describe what happened in the account, not to tell users what to buy or sell.

## One-Command Docker Start

Run BrokerGate locally without broker credentials:

```bash
docker compose up --build
```

Then open:

- API health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- OpenAPI docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

This starts local paper adapters. To connect real broker paper accounts, copy the example env file and fill in your own credentials:

```bash
cp .env.example .env
docker compose up --build
```

Never commit `.env`.

## Local Development

```powershell
uv sync --dev
uv run uvicorn brokergate.main:app --reload
```

Run the web dashboard in a second terminal:

```powershell
cd web
npm install
npm run dev
```

The browser UI uses server-side Next.js routes to call BrokerGate. Configure
`web/.env.local` with `BROKERGATE_API_BASE_URL`, `BROKERGATE_API_KEY`, and
`BROKERGATE_WEB_ACCOUNTS`; see [BrokerGate Web](web/README.md).

## Broker Status

Broker readiness is reported dynamically:

```bash
curl http://127.0.0.1:8000/v1/brokers
```

- `local-paper-ready`: no SDK credentials configured; using local paper adapter
- `broker-paper-ready`: SDK credentials configured and broker connection passed in paper mode
- `trade-ready`: live-trade mode is enabled and broker connection passed
- `connection-failed`: adapter is registered but connection failed or timed out
- `planned`: adapter is not implemented yet

## Safety Model

The execution path is always:

```text
order request -> broker account snapshot -> risk checks -> order draft -> human confirmation -> broker SDK submit_order
```

The default `BROKERGATE_BROKER_MODE=paper` is intended for broker paper/simulated accounts or local paper fallback. Live trading requires explicitly setting `BROKERGATE_BROKER_MODE=live-trade`.

## Roadmap

### V0.1 Broker Gateway

- Tiger adapter
- Account, asset, position, order, and execution APIs
- Paper mode and local fallback
- Human-confirmed order drafts
- Docker deployment

### V0.2 Multi-Broker Model

- Longbridge adapter hardening
- Futu adapter exploration
- Unified broker/account schema
- More complete broker status and connection diagnostics

### V0.3 Portfolio Analytics

- Multi-account aggregation
- Daily portfolio snapshots
- Exposure and concentration analysis
- Basic profit and loss attribution

### V0.4 AI Portfolio Insights

- Trading behavior review
- Risk monitoring and alert events
- AI account Q&A
- MCP / agent workflow integration

### V1.0 Broker Ecosystem

- More broker adapters
- Managed deployment patterns
- Potential official broker authorization flows if partnerships become available

## Documentation

- [Product Spec](docs/specs/00-product-spec.md)
- [Architecture Spec](docs/specs/01-architecture-spec.md)
- [API Spec](docs/specs/02-api-spec.md)
- [Broker Adapter Spec](docs/specs/03-broker-adapter-spec.md)
- [Order Safety Spec](docs/specs/04-order-confirmation-security-spec.md)
- [Data and Audit Spec](docs/specs/05-data-model-audit-spec.md)
- [Deployment Spec](docs/specs/06-deployment-operations-spec.md)
- [AI Integration Spec](docs/specs/07-mcp-ai-integration-spec.md)
- [Roadmap and Validation Spec](docs/specs/08-roadmap-validation-spec.md)
- [Unified Risk Engine Spec](docs/specs/09-unified-risk-engine-spec.md)
- [Multi-Broker Target Architecture](docs/specs/10-multi-broker-target-architecture.md)
- [Broker OpenAPI Coverage Matrix](docs/specs/11-broker-openapi-coverage.md)
- [Order and Market Data Integration Design](docs/specs/12-order-market-data-integration-design.md)
- [BrokerGate Web Dashboard](web/README.md)
- [Tiger OpenAPI Integration Guide](docs/guides/tiger-openapi-integration.md)
- [Longbridge OpenAPI Integration Guide](docs/guides/longbridge-openapi-integration.md)

## License

MIT

# 中文说明

BrokerGate 是一个自部署、多券商交易网关，面向开发者、AI Agent 和现代投资工作流。它的核心不是替用户自动交易，而是在本地控制平面里统一连接券商账户、统一风控、人工确认执行，并为后续资产聚合、交易复盘、风险监控和 AI 账户分析提供数据基础。

它把老虎、长桥等券商 API 接到一个本地控制平面后面。AI 工具和外部客户端可以查询账户、生成订单草稿，但真正提交到券商 SDK 前，必须经过 BrokerGate 的风控检查和用户确认。

BrokerGate 不是自动炒股机器人，不是券商，也不提供投资建议。

长期产品方向是：

```text
开源 Broker Gateway
+
Portfolio Intelligence Layer
```

也就是：连接和执行层保持自部署、安全、开发者友好；增值分析层建立在统一账户数据之上，支持多账户聚合、交易复盘、风险提醒和 AI 账户洞察。

## 功能

- 老虎、长桥适配器的统一 REST API
- 账户摘要、持仓、订单草稿、确认执行、订单管理、成交查询、审计日志
- 首条风控规则：买入金额不能超过账户购买力
- 行情和股票基础信息支持只读 fallback，可在一个券商失败时切到其他已配置行情源
- Next.js 网页交易台，用于聚合资产、持仓、券商连接状态和人工确认订单草稿
- 配置券商凭证后，可走券商 SDK 的模拟账户路径
- 未配置券商凭证时，提供本地 paper fallback，方便快速体验
- 支持 Docker Compose 本地/VPS 部署
- 为资产聚合、交易复盘、风险监控和 AI 账户分析预留 Portfolio Intelligence 能力

## 产品分层

### 1. Broker Gateway

开源连接层提供统一的券商账户接口。

它统一抽象：

- 账户
- 资产
- 持仓
- 订单
- 成交
- 审计事件

安全模型保持保守：AI 工具可以生成订单草稿，但真实执行必须经过风控检查和用户确认。

### 2. Portfolio Intelligence

分析层建立在统一账户模型之上。

规划方向包括：

- 多账户资产聚合
- 持仓敞口和集中度分析
- 盈亏归因
- 交易行为复盘
- 风险提醒和持仓监控
- AI 账户问答和投资工作流集成

这一层只描述账户里发生了什么，不告诉用户应该买什么或卖什么。

## 一键 Docker 启动

不配置券商凭证，直接本地启动：

```bash
docker compose up --build
```

打开：

- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

这时使用的是本地 paper adapter。如果要连接真实券商模拟账户，复制环境变量模板并填入自己的凭证：

```bash
cp .env.example .env
docker compose up --build
```

不要把 `.env` 提交到仓库。

## 本地开发

```powershell
uv sync --dev
uv run uvicorn brokergate.main:app --reload
```

另开一个终端启动网页交易台：

```powershell
cd web
npm install
npm run dev
```

浏览器 UI 通过 Next.js 服务端路由调用 BrokerGate，不会在浏览器暴露券商密钥。
在 `web/.env.local` 里配置 `BROKERGATE_API_BASE_URL`、`BROKERGATE_API_KEY`
和 `BROKERGATE_WEB_ACCOUNTS`，详见 [BrokerGate Web](web/README.md)。

## 券商状态

BrokerGate 会动态返回券商注册和连接状态：

```bash
curl http://127.0.0.1:8000/v1/brokers
```

- `local-paper-ready`：未配置 SDK 凭证，正在使用本地 paper adapter
- `broker-paper-ready`：已配置 SDK 凭证，券商连接成功，当前是 paper 模式
- `trade-ready`：已启用 live-trade，券商连接成功
- `connection-failed`：adapter 已注册，但连接失败或超时
- `planned`：该券商 adapter 尚未实现

## 安全模型

交易链路始终是：

```text
下单请求 -> 刷新券商账户快照 -> 风控检查 -> 订单草稿 -> 用户确认 -> 调用券商 SDK submit_order
```

默认 `BROKERGATE_BROKER_MODE=paper`，用于券商模拟账户或本地 paper fallback。真实交易必须显式设置 `BROKERGATE_BROKER_MODE=live-trade`。

## 路线图

### V0.1 Broker Gateway

- 老虎适配器
- 账户、资产、持仓、订单、成交 API
- paper 模式和本地 fallback
- 人工确认订单草稿
- Docker 部署

### V0.2 Multi-Broker Model

- 长桥适配器完善
- 富途适配器调研
- 统一券商/账户模型
- 更完整的券商连接状态和诊断能力

### V0.3 Portfolio Analytics

- 多账户聚合
- 每日资产快照
- 敞口和集中度分析
- 基础盈亏归因

### V0.4 AI Portfolio Insights

- 交易行为复盘
- 风险监控和提醒事件
- AI 账户问答
- MCP / Agent 工作流集成

### V1.0 Broker Ecosystem

- 更多券商适配器
- 托管部署模式
- 如果后续有券商合作，再探索官方授权连接方式

## 文档

- [产品规格](docs/specs/00-product-spec.md)
- [架构规格](docs/specs/01-architecture-spec.md)
- [API 规格](docs/specs/02-api-spec.md)
- [券商适配器规格](docs/specs/03-broker-adapter-spec.md)
- [订单安全规格](docs/specs/04-order-confirmation-security-spec.md)
- [数据与审计规格](docs/specs/05-data-model-audit-spec.md)
- [部署运维规格](docs/specs/06-deployment-operations-spec.md)
- [AI/MCP 集成规格](docs/specs/07-mcp-ai-integration-spec.md)
- [路线与验证规格](docs/specs/08-roadmap-validation-spec.md)
- [统一风控规格](docs/specs/09-unified-risk-engine-spec.md)
- [多券商目标架构](docs/specs/10-multi-broker-target-architecture.md)
- [券商开放接口覆盖矩阵](docs/specs/11-broker-openapi-coverage.md)
- [订单和行情扩展接入设计](docs/specs/12-order-market-data-integration-design.md)
- [BrokerGate 网页交易台](web/README.md)
- [老虎 OpenAPI 接入指南](docs/guides/tiger-openapi-integration.md)
- [长桥 OpenAPI 接入指南](docs/guides/longbridge-openapi-integration.md)
