# Deployment and Operations Spec

## 部署目标

OpenBroker 默认面向自部署。首版部署目标是单台香港 VPS，使用 Docker Compose 运行 API 服务和后续的 Web 面板。

## MVP Compose

当前 `docker-compose.yml` 只启动 API：

```powershell
docker compose up --build
```

## 本地开发

项目使用 `uv` 管理依赖和虚拟环境：

```powershell
uv sync --dev
uv run uvicorn openbroker.main:app --reload
uv run pytest -q
uv run ruff check .
```

后续可扩展：

```text
api
web
postgres
redis
futu-opend
prometheus
grafana
```

## 环境变量

- `OPENBROKER_ENV`
- `OPENBROKER_API_KEY`
- `OPENBROKER_CONFIRMATION_REQUIRED`
- `OPENBROKER_BROKER_MODE`
- `OPENBROKER_TIGER_ENABLED`
- `OPENBROKER_TIGER_ACCOUNT`
- `OPENBROKER_TIGER_ID`
- `OPENBROKER_TIGER_LICENSE`
- `OPENBROKER_TIGER_PRIVATE_KEY_PATH`
- `OPENBROKER_TIGER_CONFIG_DIR`
- `OPENBROKER_TIGER_TOKEN_PATH`
- `OPENBROKER_LONGBRIDGE_ENABLED`
- `OPENBROKER_LONGBRIDGE_AUTH_MODE`
- `OPENBROKER_LONGBRIDGE_REGION`
- `OPENBROKER_LONGBRIDGE_ACCOUNT`
- `LONGBRIDGE_APP_KEY`
- `LONGBRIDGE_APP_SECRET`
- `LONGBRIDGE_ACCESS_TOKEN`

生产部署必须新增：

- 数据库连接串。
- 加密主密钥。
- HTTPS 域名。
- 管理员初始账号。

## 运行模式

- `paper`：模拟提交，不连接真实交易。
- `live-query`：允许真实账户查询，不允许真实交易。
- `live-trade`：允许真实交易，必须启用确认和审计。

默认必须是 `paper`。

Tiger 接入配置详见 `docs/guides/tiger-openapi-integration.md`。生产环境不要把 `tiger_openapi_config.properties`、token 文件或私钥放进项目目录。

Longbridge 接入配置详见 `docs/guides/longbridge-openapi-integration.md`。生产环境不要把 `LONGBRIDGE_APP_SECRET` 或 `LONGBRIDGE_ACCESS_TOKEN` 写入镜像、README 或 git 历史。

## 运维检查

- `/health` 返回正常。
- API Key 已替换。
- HTTPS 已启用。
- 交易模式不是误开的 `live-trade`。
- 审计日志可写。
- 备份策略可用。

## 监控

首版暂不实现监控，但规格要求预留：

- 请求延迟。
- 券商连接状态。
- 下单失败率。
- 审计写入失败。
- OpenD sidecar 状态。
- 磁盘空间和备份状态。
