# BrokerGate

## 面向中文用户的自部署多券商账户与交易网关

BrokerGate 想解决一个很具体的问题：

> 有些用户同时使用老虎、长桥、富途、IBKR 等海外券商，但账户、持仓、订单和交易入口分散在不同 App 里。BrokerGate 希望通过券商官方 OpenAPI，把这些能力接回用户自己的控制台。

BrokerGate 同时重视两件事：

- **看账户**：统一查看资产、现金、持仓、订单、成交和券商连接状态。
- **做交易**：通过订单草稿、风控检查和人工确认，把交易指令提交给用户本人已授权的券商账户。

默认策略是：**模拟账户优先，交易默认关闭，真实交易必须显式开启，并且需要人工确认。**

BrokerGate 不是券商，不托管用户资金，不提供投资建议，也不是自动炒股机器人。

---

## 为什么做这个项目

很多中文用户已经拥有海外券商账户，但常见问题是：

- 多个券商 App 来回切换，资产和持仓很难统一看；
- 订单、成交、现金和购买力分散在不同系统里；
- 想把账户数据接入自己的投资看板、脚本或 AI Agent，但每家券商 API 都不一样；
- 需要一个能先跑模拟账户、再谨慎接真实账户的统一中台。

BrokerGate 的目标不是绕过券商，而是使用**券商官方 OpenAPI**，让用户把本人合法持有的券商账户接回自己的自部署环境。

---

## 核心能力

- 老虎、长桥等券商适配器的统一 REST API；
- 账户摘要、现金、持仓、订单、成交和审计日志；
- 订单草稿、人工确认、撤单/订单管理等交易前置能力；
- 首条风控规则：买入金额不能超过账户购买力；
- 行情和股票基础信息支持只读 fallback，可在一个券商失败时切到其他已配置行情源；
- Next.js 网页控制台，用于聚合资产、持仓、券商连接状态和人工确认订单草稿；
- 配置券商凭证后，可走券商 SDK 的模拟账户路径；
- 未配置券商凭证时，提供本地 paper fallback，方便快速体验；
- Docker Compose 本地/VPS 部署。

---

## 产品原则

1. **官方 OpenAPI**：不做屏幕抓取，不模拟点击券商 App。
2. **模拟账户优先**：默认 `BROKERGATE_BROKER_MODE=paper`，先跑通模拟账户或本地 paper fallback。
3. **交易默认关闭**：真实交易必须显式设置 `BROKERGATE_BROKER_MODE=live-trade`。
4. **人工确认执行**：AI 工具或外部客户端可以生成订单草稿，但不能绕过确认直接提交。
5. **用户自主管理密钥**：优先部署在用户本地、NAS、VPS 或用户自己的云账号中。
6. **不提供投资建议**：BrokerGate 只做账户、持仓、订单和交易能力的统一接入。

---

## 一键 Docker 启动

不配置券商凭证，直接本地启动：

```bash
docker compose up --build
```

打开：

- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

这时使用的是本地 paper adapter。如果要连接真实券商的模拟账户，复制环境变量模板并填入自己的凭证：

```bash
cp .env.example .env
docker compose up --build
```

不要把 `.env` 提交到仓库。

---

## 部署方式

### 本地 / VPS

```bash
docker compose up --build
```

### Render 一键部署

后续可通过 Render Blueprint 部署到用户自己的 Render 账号。部署后，用户在 Render 后台填写自己的环境变量和券商模拟账户凭证。

> 原则：BrokerGate 官方不需要接触用户的券商密钥。

---

## 本地开发

```powershell
uv sync --dev
uv run uvicorn brokergate.main:app --reload
```

另开一个终端启动网页控制台：

```powershell
cd web
npm install
npm run dev
```

浏览器 UI 通过 Next.js 服务端路由调用 BrokerGate，不会在浏览器暴露券商密钥。
在 `web/.env.local` 里配置 `BROKERGATE_API_BASE_URL`、`BROKERGATE_API_KEY` 和 `BROKERGATE_WEB_ACCOUNTS`，详见 [BrokerGate Web](web/README.md)。

---

## 券商状态

BrokerGate 会动态返回券商注册和连接状态：

```bash
curl http://127.0.0.1:8000/v1/brokers
```

状态说明：

- `local-paper-ready`：未配置 SDK 凭证，正在使用本地 paper adapter；
- `broker-paper-ready`：已配置 SDK 凭证，券商连接成功，当前是 paper / 模拟模式；
- `trade-ready`：已启用 live-trade，券商连接成功；
- `connection-failed`：adapter 已注册，但连接失败或超时；
- `planned`：该券商 adapter 尚未实现。

---

## 交易安全模型

交易链路始终是：

```text
下单请求 -> 刷新券商账户快照 -> 风控检查 -> 订单草稿 -> 用户确认 -> 调用券商 SDK submit_order
```

默认 `BROKERGATE_BROKER_MODE=paper`，用于券商模拟账户或本地 paper fallback。真实交易必须显式设置：

```env
BROKERGATE_BROKER_MODE=live-trade
BROKERGATE_CONFIRMATION_REQUIRED=true
```

不建议关闭人工确认。

---

## 适合谁

BrokerGate 第一阶段更适合：

- 已经有海外券商账户的中文用户；
- 希望统一查看多券商资产、持仓和交易记录的人；
- 熟悉券商 OpenAPI 或愿意使用模拟账户试跑的人；
- 想把账户数据接入个人投资看板、自动化脚本或 AI Agent 的用户；
- 希望自部署、不希望把券商密钥交给中心化平台的用户。

---

## 当前路线

- v0.1：本地 paper fallback，快速体验账户、持仓、订单草稿和确认链路；
- v0.2：真实券商模拟账户接入，优先跑通官方 OpenAPI；
- v0.3：多券商账户聚合，统一资产、持仓、订单和成交；
- v0.4：网页控制台优化，降低中文用户使用门槛；
- v0.5：交易确认能力增强，包括限额、白名单、审计日志；
- v0.6：AI Agent / MCP 工具接入，让 AI 能读取账户并生成订单草稿，但不能绕过人工确认。

---

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
- [老虎 OpenAPI 接入指南](docs/guides/tiger-openapi-integration.md)
- [长桥 OpenAPI 接入指南](docs/guides/longbridge-openapi-integration.md)
- [BrokerGate Web 控制台](web/README.md)

---

## 免责声明

BrokerGate 是开源软件工具，不是证券经纪商、投资顾问或资产管理服务。用户需要自行确认其券商账户、API 使用方式和交易行为符合所在地法律法规及券商协议。所有交易行为均由用户本人确认并通过其本人券商账户执行。

---

## License

MIT
