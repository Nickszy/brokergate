# Longbridge OpenAPI Integration Guide

## 目标

本指南说明 OpenBroker 如何接入长桥证券 (Longbridge) OpenAPI。接入策略与架构需满足以下设计要求：

1. **SDK 适配器主路径 (SDK Adapter)**: OpenBroker 自部署、多券商、统一风控主路径。使用官方 `longbridge` Python SDK。
2. **长桥 Hosted MCP (调研路径)**: 仅作为用户个人工具、参考或调研，不作为 OpenBroker 的订单提交后端。

## 官方资料

- 官方文档: https://open.longbridge.com/docs
- 新手入门: https://open.longbridge.com/docs/getting-started
- 官方 SDK: https://open.longbridge.com/sdk
- 官方 MCP 服务: https://open.longbridge.com/docs/mcp

## 接入步骤

1. **获取凭证**:
   用户在长桥开放平台后台获取：
   - `app_key`: 开发者 App Key。
   - `app_secret`: 开发者 App Secret。
   - `access_token`: 长桥访问令牌。

2. **环境变量配置**:
   在 `.env` 中加入以下配置：
   ```env
   OPENBROKER_LONGBRIDGE_ENABLED=true
   OPENBROKER_LONGBRIDGE_APP_KEY=your-app-key
   OPENBROKER_LONGBRIDGE_APP_SECRET=your-app-secret
   OPENBROKER_LONGBRIDGE_ACCESS_TOKEN=your-access-token
   OPENBROKER_LONGBRIDGE_ACCOUNT=your-account-id
   ```

3. **初始化 SDK Config**:
   使用 `longbridge.Config` 对客户端进行初始化：
   ```python
   from longbridge.config import Config

   config = Config(
       app_key=settings.longbridge_app_key,
       app_secret=settings.longbridge_app_secret,
       access_token=settings.longbridge_access_token,
   )
   ```

## API 映射

| OpenBroker 能力 | Longbridge SDK 客户端 | 接口/方法 | 说明 |
|---|---|---|---|
| 连接测试 | `TradeContext` | `account_balance()` | 获取账户资产，验证连接 |
| 账户摘要 | `TradeContext` | `account_balance()` | 转换为统一 `AccountSummary` 资产与购买力 |
| 持仓列表 | `TradeContext` | `stock_positions()` | 转换为统一 `Position` 列表 |
| 订单草稿 | OpenBroker workflow | - | 不调用长桥 |
| 确认下单 | `TradeContext` | `submit_order()` | 仅能从已确认的草稿提交 |

## 风控与安全规则

- **风控主权**: 长桥的 `estimate_max_purchase_quantity()` 可作为下单前额外的辅助 precheck 逻辑，但绝对不能替代或绕过 OpenBroker `RiskEngine` 统一执行的购买力校验规则。
- **防止绕过**: 所有的下单请求均需经过 OpenBroker 的订单草稿流程，得到用户人工确认（Confirm）并写入审计日志，才能最终调起 `submit_order()` 提交至长桥。

## 双轨设计边界

### 路径 A: SDK Adapter (主路径)
- 目的: OpenBroker 控制面中立的管理层。
- 职责: 提供统一的 HTTP/REST API，接受用户的风控过滤、人工确认，向长桥执行交易并计入统一审计日志。
- 安全级别: 极高。

### 路径 B: Longbridge Hosted MCP (辅助/调研路径)
- 目的: 调研长桥官方 MCP 的能力，供用户作为个人只读或分析工具。
- 限制: **不集成到 OpenBroker 的交易执行管道**。OpenBroker 绝不会把下单后端委托给该 hosted MCP。
