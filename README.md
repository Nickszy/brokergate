# OpenBroker

Self-hosted multi-broker trading gateway for Tiger, Futu, and Longbridge.

- Web-based broker configuration
- Unified REST API
- Human-confirmed order execution
- MCP / Claude / OpenClaw integration path
- Self-hosted, no third-party custody of broker keys

OpenBroker is not an "AI auto-trading bot". It is a self-hosted trading infrastructure layer: AI and external tools may query account data and generate order drafts, but user confirmation is required before execution.

## MVP Scope

The initial MVP is intentionally narrow:

- Tiger-first gateway
- Unified account, position, and order models
- Draft order creation
- Human confirmation before execution
- Audit log for every sensitive action
- Docker-based local deployment

Futu, Longbridge, MCP write flows, and Pro account analytics are documented in `docs/specs`, but are not part of the initial runtime skeleton yet.

## Quick Start

```powershell
uv sync --dev
uv run uvicorn openbroker.main:app --reload
```

Then open:

- API health: `http://127.0.0.1:8000/health`
- OpenAPI docs: `http://127.0.0.1:8000/docs`

## Docker

```powershell
docker compose up --build
```

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
- [Tiger OpenAPI Integration Guide](docs/guides/tiger-openapi-integration.md)
- [Longbridge OpenAPI Integration Guide](docs/guides/longbridge-openapi-integration.md)
