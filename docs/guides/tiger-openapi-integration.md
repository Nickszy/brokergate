# Tiger OpenAPI Integration Guide

## 目标

这份文档说明 BrokerGate 如何接入老虎证券 OpenAPI。接入顺序必须是：

1. 先跑通 SDK 连接。
2. 再接账户和持仓查询。
3. 再接 paper 下单。
4. 最后才允许 live 下单，并且必须走 BrokerGate 的订单草稿和人工确认流程。

不要把老虎 SDK 直接暴露给 AI/MCP 或外部 API。BrokerGate 的交易入口只能是：

```text
POST /v1/orders/drafts -> POST /v1/orders/{draft_id}/confirm -> Tiger Adapter
```

## 官方资料

- 官方 Python SDK 仓库：https://github.com/tigerfintech/openapi-python-sdk
- 官方新版文档：https://docs-en.itigerup.com/docs/intro
- 旧版 Python 文档：https://quant.itigerup.com/openapi/en/python/overview/introduction.html
- 开发者信息页：https://developer.itigerup.com

官方文档说明 OpenAPI 支持账户、持仓、下单、改单、撤单、行情和实时推送；支持 global account、prime account、paper account。Python SDK 包名是 `tigeropen`。

## 前置条件

在老虎开发者信息页拿到：

- `tiger_id`：开发者 ID。
- `account`：交易账户号，可以是实盘账户，也可以是 paper account。
- `private_key`：RSA 私钥。Python SDK 使用 PKCS#1 格式。
- `license`：例如 `TBHK`。
- `tiger_openapi_token.properties`：如果是 TBHK 牌照，通常需要 token 文件；token 有有效期，需要刷新。

注意：

- 私钥只保存一次，刷新页面后可能不再展示。必须本地安全保存。
- 不要把私钥、token、账户号提交到 git。
- 行情权限和 App 里的行情权限不一定等价，OpenAPI 行情可能需要单独订阅。
- 可以在开发者页面配置 IP 白名单，生产部署建议配置香港 VPS 公网 IP。

## 安装 SDK

项目使用 `uv` 管理依赖：

```powershell
uv add tigeropen
```

如果只想先本地试 SDK，也可以在当前环境里临时安装：

```powershell
uv pip install tigeropen
```

## 本地配置方式

推荐把老虎官方配置文件放在不进仓库的目录，例如：

```text
C:\Users\zheyu\.brokergate\tiger\
  tiger_openapi_config.properties
  tiger_openapi_token.properties
  private_key_pk1.pem
```

`.env` 中只保存路径和开关：

```env
BROKERGATE_TIGER_ENABLED=true
BROKERGATE_TIGER_ACCOUNT=20191106192858300
BROKERGATE_TIGER_ID=20150001
BROKERGATE_TIGER_LICENSE=TBHK
BROKERGATE_TIGER_CONFIG_DIR=C:/Users/zheyu/.brokergate/tiger
BROKERGATE_TIGER_PRIVATE_KEY_PATH=C:/Users/zheyu/.brokergate/tiger/private_key_pk1.pem
BROKERGATE_TIGER_TOKEN_PATH=C:/Users/zheyu/.brokergate/tiger/tiger_openapi_token.properties
BROKERGATE_BROKER_MODE=paper
```

Windows 路径建议在 `.env` 里使用 `/`，避免反斜杠转义问题。

## SDK 初始化方式

BrokerGate 的 Tiger adapter 应支持两种初始化方式。

### 方式一：官方 properties 文件

```python
from tigeropen.tiger_open_config import TigerOpenClientConfig

config = TigerOpenClientConfig(props_path="C:/Users/zheyu/.brokergate/tiger")
```

适合直接使用老虎下载的 `tiger_openapi_config.properties` 和 token 文件。

### 方式二：BrokerGate 环境变量

```python
from pathlib import Path

from tigeropen.tiger_open_config import TigerOpenClientConfig

config = TigerOpenClientConfig()
config.tiger_id = settings.tiger_id
config.account = settings.tiger_account
config.private_key = Path(settings.tiger_private_key_path).read_text(encoding="utf-8")
```

适合后续 Web 配置面板和加密凭证存储。

## BrokerGate 适配器落点

真实 Tiger 接入应该改这些文件：

- `pyproject.toml`：加入 `tigeropen` 依赖。
- `src/brokergate/config.py`：加入 Tiger 配置项。
- `src/brokergate/adapters/tiger.py`：把 `TigerPaperAdapter` 拆成 `TigerOpenApiAdapter` 和 `TigerPaperAdapter`。
- `src/brokergate/adapters/base.py`：补全 `test_connection()`、`get_account_summary()`、`list_positions()`、`list_orders()`。
- `src/brokergate/services.py`：根据 `BROKERGATE_TIGER_ENABLED` 和 `BROKERGATE_BROKER_MODE` 注册真实或 paper adapter。
- `src/brokergate/main.py`：增加账户、持仓、订单查询 API。
- `tests/`：保留 paper 单元测试，新增 Tiger SDK mock 测试，不在 CI 里打真实券商 API。

## API 映射

BrokerGate 统一 API 和 Tiger SDK 的职责映射：

| BrokerGate 能力 | Tiger SDK 客户端 | 说明 |
|---|---|---|
| 连接测试 | TradeClient / account query | 用最小账户查询验证配置 |
| 账户摘要 | TradeClient | 查询资产、现金、购买力 |
| 持仓列表 | TradeClient | 转成统一 Position 模型 |
| 订单草稿 | BrokerGate workflow | 不调用 Tiger |
| 确认下单 | TradeClient | 只允许从 confirmed draft 调用 |
| 订单状态 | TradeClient | 用 broker_order_id 查询 |
| 行情查询 | QuoteClient | 可选，行情权限可能单独收费 |

## 下单安全规则

Tiger adapter 不能自己决定是否下单。它只能接收已确认的 `OrderDraft`：

```python
async def submit_order(self, draft: OrderDraft) -> BrokerOrderReceipt:
    if draft.status != OrderStatus.confirmed:
        raise ValueError("Tiger adapter only accepts confirmed order drafts")
```

必须保留这些保护：

- `BROKERGATE_BROKER_MODE=paper` 是默认值。
- live 模式必须显式开启。
- live 模式必须设置强 API Key。
- live 下单必须写审计日志。
- SDK 原始异常必须转换成统一错误。
- 订单已发出但本地回执失败时，进入人工核查，不自动重试。

## 最小验收流程

### 1. SDK 连接

```powershell
uv run python scripts/check_tiger_connection.py
```

预期：

- 能读取配置。
- 能创建 Tiger client。
- 能查询账户或 paper account 基础信息。

### 2. BrokerGate 查询

```powershell
uv run uvicorn brokergate.main:app --reload
```

访问：

- `GET /health`
- `GET /v1/brokers`
- `GET /v1/accounts/{account_id}/summary`
- `GET /v1/accounts/{account_id}/positions`

### 3. Paper 下单

1. `POST /v1/orders/drafts` 创建草稿。
2. 检查 `required_confirmation`。
3. `POST /v1/orders/{draft_id}/confirm` 提交确认。
4. 确认返回 `broker_order_id`。
5. 检查 `GET /v1/audit/events` 有 `order.draft_created`、`order.confirmed`、`order.submitted`。

### 4. Live 下单前检查

live 前必须逐项确认：

- API Key 已替换，不是 `change-me`。
- `BROKERGATE_BROKER_MODE=live-trade` 是手动设置。
- Tiger 账户号是目标账户，不是误用其他账户。
- IP 白名单包含当前服务器。
- 确认文本和审计日志正常。
- 已经用最小数量 paper 订单测过完整流程。

## 常见问题

### 配置文件能不能直接放项目目录？

不能。项目目录会被 git 管理，容易误提交。应放在用户目录或 secret volume。

### 能不能让 AI 直接调用 Tiger 下单？

不能。AI 只能创建订单草稿。真实下单必须经过 BrokerGate 的确认接口。

### paper account 和 live account 怎么切？

用 `BROKERGATE_BROKER_MODE` 和 `BROKERGATE_TIGER_ACCOUNT` 同时控制。不要只换账户号而不换模式。

### token 过期怎么办？

TBHK token 有有效期。先按官方机制重新生成 token 文件；后续再实现自动刷新和过期告警。

### 行情查不到是不是 SDK 没接好？

不一定。OpenAPI 行情权限可能需要单独订阅。先用账户查询和持仓查询验证交易接口，再单独排查行情权限。
