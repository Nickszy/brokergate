# BrokerGate 文档

这个目录保存 BrokerGate 的产品、架构、接口、风控、券商适配器、部署运维和后续智能工具接入说明。

当前实现是交易网关的最小闭环，不是完整券商开放平台复制品。`docs/specs` 是产品边界、接口形态、风控规则和适配器契约的主要依据；`docs/guides` 保存具体券商接入步骤。

重点文档：

- `docs/specs/00-product-spec.md`：产品边界。
- `docs/specs/01-architecture-spec.md`：整体架构。
- `docs/specs/02-api-spec.md`：统一接口。
- `docs/specs/03-broker-adapter-spec.md`：券商适配器契约。
- `docs/specs/09-unified-risk-engine-spec.md`：统一风控。
- `docs/specs/10-multi-broker-target-architecture.md`：多券商目标架构。
- `docs/specs/11-broker-openapi-coverage.md`：各券商开放接口能力和当前项目覆盖范围。
- `docs/specs/12-order-market-data-integration-design.md`：订单查询、改单撤单、成交、行情快照和股票基础信息的接入设计。
