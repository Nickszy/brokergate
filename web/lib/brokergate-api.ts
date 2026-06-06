import type {
  Account,
  Connection,
  DashboardSummary,
  DataStatus,
  Position,
} from "@/lib/dashboard-types";

type BrokerTone = Account["color"];

type BrokerStatus = {
  id: string;
  status: string;
  registered: boolean;
  connected: boolean;
  adapter?: string;
  broker_mode?: string;
  error?: string;
};

type AccountSummary = {
  broker: string;
  account_id: string;
  base_currency: string;
  cash: string;
  buying_power: string;
  updated_at: string;
  raw: Record<string, unknown>;
};

type BrokerPosition = {
  broker: string;
  account_id: string;
  symbol: string;
  name: string | null;
  quantity: string;
  market_value: string | null;
  currency: string;
  cost_basis: string;
  updated_at: string;
};

type AccountConfig = {
  broker: string;
  accountId: string;
  label: string;
};

type ApiHealth = {
  status: string;
  env: string;
  broker_mode: string;
};

type FxTable = {
  baseCurrency: string;
  rates: Record<string, number>;
  source: string;
  asOf?: string;
  errors: string[];
};

export type CurrencyBucket = {
  currency: string;
  value: number;
};

export type DashboardData = {
  accounts: Account[];
  positions: Position[];
  connections: Connection[];
  aggregates: {
    totalByCurrency: CurrencyBucket[];
    cashByCurrency: CurrencyBucket[];
    connectedCount: number;
    totalBrokers: number;
  };
  summary: DashboardSummary;
  dataStatus: DataStatus;
  errors: string[];
};

const BROKER_META: Record<string, { code: string; color: BrokerTone; label: string }> = {
  tiger: { code: "TG", color: "ink", label: "Tiger" },
  longbridge: { code: "LB", color: "blue", label: "Longbridge" },
  futu: { code: "FT", color: "red", label: "Futu" },
};

const DEFAULT_ACCOUNTS: AccountConfig[] = [
  { broker: "tiger", accountId: "paper-account", label: "Tiger 模拟账户" },
  {
    broker: "longbridge",
    accountId: "paper-longbridge-account",
    label: "Longbridge 模拟账户",
  },
];

const DEFAULT_DISPLAY_CURRENCIES = ["USD", "HKD", "CNY"];

function getBaseUrl(): string {
  return (process.env.BROKERGATE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
}

function parseAccountConfig(value: string): AccountConfig[] {
  const parsed = JSON.parse(value) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error("BROKERGATE_WEB_ACCOUNTS must be a JSON array.");
  }

  return parsed.map((item, index) => {
    if (!item || typeof item !== "object") {
      throw new Error(`BROKERGATE_WEB_ACCOUNTS[${index}] must be an object.`);
    }

    const record = item as Record<string, unknown>;
    const broker = String(record.broker || "").trim();
    const accountId = String(record.account_id || record.accountId || "").trim();
    const label = String(record.display_name || record.label || accountId || broker).trim();

    if (!broker || !accountId) {
      throw new Error(`BROKERGATE_WEB_ACCOUNTS[${index}] requires broker and account_id.`);
    }

    return { broker, accountId, label };
  });
}

function getAccountConfigs(): AccountConfig[] {
  const explicitJson = process.env.BROKERGATE_WEB_ACCOUNTS;
  if (explicitJson) {
    return parseAccountConfig(explicitJson);
  }

  const configs: AccountConfig[] = [];
  const tiger = process.env.BROKERGATE_TIGER_ACCOUNT;
  if (tiger) {
    configs.push({ broker: "tiger", accountId: tiger, label: "Tiger" });
  }

  const longbridge = process.env.BROKERGATE_LONGBRIDGE_ACCOUNT;
  if (longbridge) {
    configs.push({ broker: "longbridge", accountId: longbridge, label: "Longbridge" });
  }

  return configs.length > 0 ? configs : DEFAULT_ACCOUNTS;
}

function getDisplayCurrencies(): string[] {
  const raw = process.env.BROKERGATE_WEB_DISPLAY_CURRENCIES;
  const currencies = raw
    ? raw.split(",").map((currency) => currency.trim().toUpperCase()).filter(Boolean)
    : DEFAULT_DISPLAY_CURRENCIES;

  return Array.from(new Set(currencies.length > 0 ? currencies : DEFAULT_DISPLAY_CURRENCIES));
}

async function apiFetch<T>(path: string): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const apiKey = process.env.BROKERGATE_API_KEY;
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  const baseUrl = getBaseUrl();
  const fallbackBaseUrl = baseUrl.includes("127.0.0.1")
    ? baseUrl.replace("127.0.0.1", "localhost")
    : baseUrl.includes("localhost")
      ? baseUrl.replace("localhost", "127.0.0.1")
      : "";
  const urls = [baseUrl, fallbackBaseUrl].filter(Boolean);
  let lastNetworkError: unknown;

  for (const url of urls) {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      let response: Response;
      try {
        response = await fetch(`${url}${path}`, {
          cache: "no-store",
          headers,
        });
      } catch (error) {
        lastNetworkError = error;
        await new Promise((resolve) => setTimeout(resolve, 120));
        continue;
      }

      if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(
          `BrokerGate API ${response.status} ${response.statusText}${body ? `: ${body.slice(0, 160)}` : ""}`,
        );
      }

      return response.json() as Promise<T>;
    }
  }

  throw new Error(`BrokerGate API network error: ${formatError(lastNetworkError)}`);
}

function formatError(error: unknown): string {
  if (error instanceof Error) {
    const cause = "cause" in error ? (error as Error & { cause?: unknown }).cause : undefined;
    return cause instanceof Error ? `${error.message}; cause: ${cause.message}` : error.message;
  }

  return String(error);
}

function formatBrokerMode(mode: string | undefined): string {
  const normalized = (mode || "").toLowerCase();
  const labels: Record<string, string> = {
    paper: "模拟模式",
    live: "真实交易模式",
    local: "本地模式",
  };

  return labels[normalized] || mode || "未知";
}

function formatBrokerDetail(detail: string | undefined): string {
  const normalized = (detail || "").toLowerCase();
  const labels: Record<string, string> = {
    "broker-paper-ready": "模拟连接就绪",
    "connection test timed out": "连接测试超时",
    planned: "待接入",
    ready: "就绪",
    online: "在线",
    stale: "待刷新",
    paper: "模拟模式",
  };

  return labels[normalized] || detail || "状态未知";
}

function toNumber(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function maskAccountId(id: string): string {
  if (id.length <= 8) {
    return id;
  }

  return `${id.slice(0, 2)}...${id.slice(-4)}`;
}

function formatCurrency(value: number, currency: string): string {
  return `${currency} ${value.toLocaleString("en-US", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  })}`;
}

function formatQuantity(value: number): string {
  return value.toLocaleString("en-US", {
    maximumFractionDigits: 4,
    minimumFractionDigits: 0,
  });
}

function formatFxMeta(fx: FxTable): string {
  const suffix = fx.asOf ? `, ${fx.asOf}` : "";
  return `${fx.source}${suffix}`;
}

function formatFxRates(displayCurrencies: string[], fx: FxTable): string[] {
  const base = fx.baseCurrency.toUpperCase();
  return displayCurrencies
    .filter((currency) => currency !== base)
    .map((currency) => {
      const rate = convertCurrency(1, base, currency, fx);
      return rate === null ? `缺少 ${base}/${currency} 汇率` : `1 ${base} = ${rate.toFixed(4)} ${currency}`;
    });
}

function parseEnvFxRates(displayCurrencies: string[]): FxTable | null {
  const raw = process.env.BROKERGATE_WEB_FX_RATES;
  if (!raw) {
    return null;
  }

  const parsed = JSON.parse(raw) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("BROKERGATE_WEB_FX_RATES must be a JSON object.");
  }

  const baseCurrency = (process.env.BROKERGATE_WEB_FX_BASE || "USD").toUpperCase();
  const rates: Record<string, number> = { [baseCurrency]: 1 };

  Object.entries(parsed as Record<string, unknown>).forEach(([currency, value]) => {
    const rate = Number(value);
    if (Number.isFinite(rate) && rate > 0) {
      rates[currency.toUpperCase()] = rate;
    }
  });

  displayCurrencies.forEach((currency) => {
    if (currency === baseCurrency) {
      rates[currency] = 1;
    }
  });

  return {
    baseCurrency,
    rates,
    source: "手动配置汇率",
    errors: [],
  };
}

async function fetchFxRates(requiredCurrencies: string[]): Promise<FxTable> {
  const displayCurrencies = getDisplayCurrencies();
  const allCurrencies = Array.from(
    new Set([...requiredCurrencies, ...displayCurrencies].map((currency) => currency.toUpperCase())),
  );

  try {
    const envRates = parseEnvFxRates(displayCurrencies);
    if (envRates) {
      return envRates;
    }
  } catch (error) {
    return {
      baseCurrency: "USD",
      rates: { USD: 1 },
      source: "手动汇率配置无效",
      errors: [formatError(error)],
    };
  }

  const baseCurrency = "USD";
  const symbols = allCurrencies.filter((currency) => currency !== baseCurrency).join(",");

  if (!symbols) {
    return { baseCurrency, rates: { [baseCurrency]: 1 }, source: "无需换汇", errors: [] };
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    let response: Response;

    try {
      response = await fetch(
        `https://api.frankfurter.dev/v1/latest?base=${baseCurrency}&symbols=${encodeURIComponent(symbols)}`,
        { cache: "no-store", signal: controller.signal },
      );
    } finally {
      clearTimeout(timeout);
    }

    if (!response.ok) {
      throw new Error(`Frankfurter FX ${response.status} ${response.statusText}`);
    }

    const payload = (await response.json()) as {
      base?: string;
      date?: string;
      rates?: Record<string, number>;
    };

    return {
      baseCurrency: (payload.base || baseCurrency).toUpperCase(),
      rates: { [baseCurrency]: 1, ...(payload.rates || {}) },
      source: "Frankfurter/ECB 参考汇率",
      asOf: payload.date,
      errors: [],
    };
  } catch (error) {
    return {
      baseCurrency,
      rates: { [baseCurrency]: 1 },
      source: "汇率不可用",
      errors: [formatError(error)],
    };
  }
}

function convertCurrency(
  amount: number,
  fromCurrency: string,
  toCurrency: string,
  fx: FxTable,
): number | null {
  const from = fromCurrency.toUpperCase();
  const to = toCurrency.toUpperCase();
  const base = fx.baseCurrency.toUpperCase();

  if (from === to) {
    return amount;
  }

  const fromRate = from === base ? 1 : fx.rates[from];
  const toRate = to === base ? 1 : fx.rates[to];

  if (!fromRate || !toRate) {
    return null;
  }

  return (amount / fromRate) * toRate;
}

function formatConvertedCurrency(
  amount: number,
  fromCurrency: string,
  toCurrency: string,
  fx: FxTable,
): string {
  const converted = convertCurrency(amount, fromCurrency, toCurrency, fx);
  return converted === null ? `${toCurrency} 汇率缺失` : formatCurrency(converted, toCurrency);
}

function displayByCurrency(
  amount: number,
  fromCurrency: string,
  displayCurrencies: string[],
  fx: FxTable,
): Record<string, string> {
  return Object.fromEntries(
    displayCurrencies.map((currency) => [
      currency,
      formatConvertedCurrency(amount, fromCurrency, currency, fx),
    ]),
  );
}

function sumBucketsInCurrency(
  buckets: CurrencyBucket[],
  displayCurrency: string,
  fx: FxTable,
): string {
  if (buckets.length === 0) {
    return "等待接口数据";
  }

  let total = 0;
  for (const bucket of buckets) {
    const converted = convertCurrency(bucket.value, bucket.currency, displayCurrency, fx);
    if (converted === null) {
      return `${displayCurrency} 汇率缺失`;
    }
    total += converted;
  }

  return formatCurrency(total, displayCurrency);
}

function bucketDisplays(
  buckets: CurrencyBucket[],
  displayCurrencies: string[],
  fx: FxTable,
): Record<string, string> {
  return Object.fromEntries(
    displayCurrencies.map((currency) => [currency, sumBucketsInCurrency(buckets, currency, fx)]),
  );
}

function formatBuckets(buckets: CurrencyBucket[], emptyLabel = "等待接口数据"): string {
  if (buckets.length === 0) {
    return emptyLabel;
  }

  return buckets.map((bucket) => formatCurrency(bucket.value, bucket.currency)).join(" + ");
}

function addBucket(map: Map<string, number>, currency: string, value: number): void {
  map.set(currency, (map.get(currency) || 0) + value);
}

function bucketsFrom(map: Map<string, number>): CurrencyBucket[] {
  return Array.from(map.entries()).map(([currency, value]) => ({ currency, value }));
}

function buildUnavailableData(error: string, accounts: AccountConfig[]): DashboardData {
  const now = new Date().toISOString();
  return {
    accounts: accounts.map((account) => {
      const meta = BROKER_META[account.broker] || {
        code: account.broker.slice(0, 2).toUpperCase(),
        color: "ink" as const,
        label: account.broker,
      };

      return {
        id: `${account.broker}:${account.accountId}`,
        broker: account.broker,
        brokerCode: meta.code,
        brokerName: account.label,
        accountId: account.accountId,
        accountSuffix: maskAccountId(account.accountId),
        status: "stale",
        statusText: "API 不可用",
        value: "API 不可用",
        originalValue: "API 不可用",
        valuesByCurrency: Object.fromEntries(
          getDisplayCurrencies().map((currency) => [currency, "API 不可用"]),
        ),
        cash: "API 不可用",
        originalCash: "API 不可用",
        cashByCurrency: Object.fromEntries(
          getDisplayCurrencies().map((currency) => [currency, "API 不可用"]),
        ),
        buyingPower: "API 不可用",
        originalBuyingPower: "API 不可用",
        buyingPowerByCurrency: Object.fromEntries(
          getDisplayCurrencies().map((currency) => [currency, "API 不可用"]),
        ),
        change: "暂无实时快照",
        trend: [10, 10, 10, 10, 10, 10],
        color: meta.color,
      };
    }),
    positions: [],
    connections: [
      {
        name: "BrokerGate API",
        detail: error,
        status: "stale",
      },
    ],
    aggregates: {
      totalByCurrency: [],
      cashByCurrency: [],
      connectedCount: 0,
      totalBrokers: 1,
    },
    summary: {
      totalAssets: "等待接口数据",
      totalAssetsByCurrency: Object.fromEntries(
        getDisplayCurrencies().map((currency) => [currency, "等待接口数据"]),
      ),
      totalMeta: [`已配置 ${accounts.length} 个账户`, "浏览器侧不保存券商密钥"],
      cash: "等待接口数据",
      cashByCurrency: Object.fromEntries(
        getDisplayCurrencies().map((currency) => [currency, "等待接口数据"]),
      ),
      cashMeta: "请启动 Python API 或设置 BROKERGATE_API_BASE_URL",
      buyingPower: "等待接口数据",
      buyingPowerByCurrency: Object.fromEntries(
        getDisplayCurrencies().map((currency) => [currency, "等待接口数据"]),
      ),
      buyingPowerMeta: "仅由服务端获取",
      connection: "0 / 1",
      connectionMeta: "API 不可用",
      defaultCurrency: getDisplayCurrencies()[0] || "USD",
      displayCurrencies: getDisplayCurrencies(),
      fxMeta: "汇率不可用",
      fxRates: [],
    },
    dataStatus: {
      label: "API 不可用",
      detail: error,
      tone: "error",
      updatedAt: now,
      apiBaseUrl: getBaseUrl(),
    },
    errors: [error],
  };
}

async function fetchHealth(): Promise<ApiHealth> {
  return apiFetch<ApiHealth>("/health");
}

async function fetchBrokers(): Promise<BrokerStatus[]> {
  const data = await apiFetch<{ brokers: BrokerStatus[] }>("/v1/brokers");
  return data.brokers;
}

async function fetchSummary(accountId: string, broker: string): Promise<AccountSummary> {
  return apiFetch<AccountSummary>(
    `/v1/accounts/${encodeURIComponent(accountId)}/summary?broker=${encodeURIComponent(broker)}`,
  );
}

async function fetchPositions(accountId: string, broker: string): Promise<BrokerPosition[]> {
  return apiFetch<BrokerPosition[]>(
    `/v1/accounts/${encodeURIComponent(accountId)}/positions?broker=${encodeURIComponent(broker)}`,
  );
}

export async function fetchDashboardData(): Promise<DashboardData> {
  let accountConfigs: AccountConfig[];
  try {
    accountConfigs = getAccountConfigs();
  } catch (error) {
    return buildUnavailableData(error instanceof Error ? error.message : String(error), []);
  }

  try {
    const displayCurrencies = getDisplayCurrencies();
    const [health, brokers] = await Promise.all([fetchHealth(), fetchBrokers()]);
    const brokerMap = new Map(brokers.map((broker) => [broker.id, broker]));
    const accountResults: PromiseSettledResult<{
      config: AccountConfig;
      positions: BrokerPosition[];
      summary: AccountSummary;
    }>[] = [];

    for (const config of accountConfigs) {
      try {
        const summary = await fetchSummary(config.accountId, config.broker);
        const positions = await fetchPositions(config.accountId, config.broker);
        accountResults.push({ status: "fulfilled", value: { config, positions, summary } });
      } catch (error) {
        accountResults.push({ status: "rejected", reason: error });
      }
    }

    const observedCurrencies = new Set<string>(displayCurrencies);

    const errors: string[] = [];
    const accountRows: Array<{
      accountId: string;
      broker: string;
      brokerCode: string;
      brokerName: string;
      color: BrokerTone;
      status: Account["status"];
      statusText: string;
      totalValue: number;
      cashValue: number;
      buyingPower: number;
      currency: string;
    }> = [];
    const rawPositions: Array<BrokerPosition & { accountLabel: string }> = [];
    const totalByCurrency = new Map<string, number>();
    const cashByCurrency = new Map<string, number>();
    const buyingPowerByCurrency = new Map<string, number>();

    accountResults.forEach((result, index) => {
      const config = accountConfigs[index];
      if (result.status === "rejected") {
        errors.push(`${config.label}: ${result.reason instanceof Error ? result.reason.message : String(result.reason)}`);
        return;
      }

      const { positions, summary } = result.value;
      const meta = BROKER_META[config.broker] || {
        code: config.broker.slice(0, 2).toUpperCase(),
        color: "ink" as const,
        label: config.broker,
      };
      const brokerStatus = brokerMap.get(config.broker);
      const cashValue = toNumber(summary.cash);
      const positionValue = positions.reduce(
        (sum, position) => sum + toNumber(position.market_value),
        0,
      );
      const buyingPower = toNumber(summary.buying_power);
      const totalValue = cashValue + positionValue;
      const cur = summary.base_currency.toUpperCase();

      observedCurrencies.add(cur);
      positions.forEach((position) => observedCurrencies.add(position.currency.toUpperCase()));
      addBucket(totalByCurrency, cur, totalValue);
      addBucket(cashByCurrency, cur, cashValue);
      addBucket(buyingPowerByCurrency, cur, buyingPower);

      accountRows.push({
        accountId: summary.account_id,
        broker: config.broker,
        brokerCode: meta.code,
        brokerName: config.label || meta.label,
        status: brokerStatus?.connected ? "ready" : "stale",
        statusText: brokerStatus?.connected
          ? "就绪"
          : formatBrokerDetail(brokerStatus?.error || brokerStatus?.status),
        totalValue,
        cashValue,
        buyingPower,
        currency: cur,
        color: meta.color,
      });

      positions.forEach((position) => {
        rawPositions.push({ ...position, accountLabel: config.label || meta.label });
      });
    });

    const fx = await fetchFxRates(Array.from(observedCurrencies));
    const fxErrors = fx.errors.map((error) => `汇率：${error}`);
    errors.push(...fxErrors);

    const accounts: Account[] = accountRows.map((account) => ({
      id: `${account.brokerName}:${account.accountId}`,
      broker: account.broker,
      brokerCode: account.brokerCode,
      brokerName: account.brokerName,
      accountId: account.accountId,
      accountSuffix: maskAccountId(account.accountId),
      status: account.status,
      statusText: account.statusText,
      value: formatConvertedCurrency(account.totalValue, account.currency, displayCurrencies[0] || account.currency, fx),
      originalValue: formatCurrency(account.totalValue, account.currency),
      valuesByCurrency: displayByCurrency(account.totalValue, account.currency, displayCurrencies, fx),
      cash: formatConvertedCurrency(account.cashValue, account.currency, displayCurrencies[0] || account.currency, fx),
      originalCash: formatCurrency(account.cashValue, account.currency),
      cashByCurrency: displayByCurrency(account.cashValue, account.currency, displayCurrencies, fx),
      buyingPower: formatConvertedCurrency(
        account.buyingPower,
        account.currency,
        displayCurrencies[0] || account.currency,
        fx,
      ),
      originalBuyingPower: formatCurrency(account.buyingPower, account.currency),
      buyingPowerByCurrency: displayByCurrency(account.buyingPower, account.currency, displayCurrencies, fx),
      change: account.currency === displayCurrencies[0] ? "实时快照" : `原始币种 ${account.currency}`,
      trend: [10, 10, 10, 10, 10, 10],
      color: account.color,
    }));

    const groupedPositions = new Map<
      string,
      {
        accounts: string[];
        currency: string;
        lots: { title: string; detail: string }[];
        name: string;
        quantity: number;
        value: number;
      }
    >();

    rawPositions.forEach((position) => {
      const key = `${position.symbol}:${position.currency}`;
      const quantity = toNumber(position.quantity);
      const marketValue = toNumber(position.market_value);
      const lot = {
        title: position.accountLabel,
        detail: `数量 ${formatQuantity(quantity)}，成本 ${formatCurrency(toNumber(position.cost_basis), position.currency)}${
          position.market_value ? `，市值 ${formatCurrency(marketValue, position.currency)}` : "，市值待返回"
        }`,
      };
      const existing = groupedPositions.get(key);

      if (existing) {
        existing.quantity += quantity;
        existing.value += marketValue;
        existing.lots.push(lot);
        if (!existing.accounts.includes(position.accountLabel)) {
          existing.accounts.push(position.accountLabel);
        }
        return;
      }

      groupedPositions.set(key, {
        accounts: [position.accountLabel],
        currency: position.currency,
        lots: [lot],
        name: position.name || position.symbol,
        quantity,
        value: marketValue,
      });
    });

    const positions: Position[] = Array.from(groupedPositions.entries()).map(([key, value]) => {
      const [symbol] = key.split(":");
      return {
        symbol,
        name: value.name,
        quantity: formatQuantity(value.quantity),
        marketValue:
          value.value > 0
            ? formatConvertedCurrency(value.value, value.currency, displayCurrencies[0] || value.currency, fx)
            : "待返回",
        originalMarketValue: value.value > 0 ? formatCurrency(value.value, value.currency) : "待返回",
        marketValueByCurrency:
          value.value > 0 ? displayByCurrency(value.value, value.currency, displayCurrencies, fx) : {},
        accounts: value.accounts,
        lots: value.lots,
      };
    });

    const connections: Connection[] = brokers.map((broker) => {
      const config = accountConfigs.find((account) => account.broker === broker.id);
      return {
        name: config?.label || BROKER_META[broker.id]?.label || broker.id,
        detail: broker.connected
          ? `${formatBrokerDetail(broker.status)}${config ? `，账号 ${config.accountId}` : ""}`
          : formatBrokerDetail(broker.error || broker.status),
        status: broker.registered ? (broker.connected ? "online" : "stale") : "planned",
      };
    });

    const totalBuckets = bucketsFrom(totalByCurrency);
    const cashBuckets = bucketsFrom(cashByCurrency);
    const buyingPowerBuckets = bucketsFrom(buyingPowerByCurrency);
    const totalAssetsByCurrency = bucketDisplays(totalBuckets, displayCurrencies, fx);
    const cashByDisplayCurrency = bucketDisplays(cashBuckets, displayCurrencies, fx);
    const buyingPowerByDisplayCurrency = bucketDisplays(buyingPowerBuckets, displayCurrencies, fx);
    const connectedCount = connections.filter((connection) => connection.status === "online").length;
    const now = new Date().toISOString();
    const defaultCurrency = displayCurrencies[0] || "USD";

    return {
      accounts,
      positions,
      connections,
      aggregates: {
        totalByCurrency: totalBuckets,
        cashByCurrency: cashBuckets,
        connectedCount,
        totalBrokers: connections.length,
      },
      summary: {
        totalAssets: totalAssetsByCurrency[defaultCurrency] || formatBuckets(totalBuckets),
        totalAssetsByCurrency,
        totalMeta: [
          `${accounts.length} 个账户快照`,
          `${positions.length} 项持仓汇总`,
          formatBrokerMode(health.broker_mode),
        ],
        cash: cashByDisplayCurrency[defaultCurrency] || formatBuckets(cashBuckets),
        cashByCurrency: cashByDisplayCurrency,
        cashMeta: "来自账户资产接口",
        buyingPower: buyingPowerByDisplayCurrency[defaultCurrency] || formatBuckets(buyingPowerBuckets),
        buyingPowerByCurrency: buyingPowerByDisplayCurrency,
        buyingPowerMeta: "按账户统计，不做资金池合并",
        connection: `${connectedCount} / ${connections.length}`,
        connectionMeta: errors.length > 0 ? `${errors.length} 个账户拉取失败` : "来自券商状态接口",
        defaultCurrency,
        displayCurrencies,
        fxMeta: formatFxMeta(fx),
        fxRates: formatFxRates(displayCurrencies, fx),
      },
      dataStatus: {
        label: errors.length > 0 ? "部分接口数据" : "实时接口数据",
        detail: `服务端于 ${new Date(now).toLocaleTimeString("zh-CN", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })} 拉取 ${getBaseUrl()}`,
        tone: errors.length > 0 ? "warning" : "live",
        updatedAt: now,
        apiBaseUrl: getBaseUrl(),
        brokerMode: formatBrokerMode(health.broker_mode),
      },
      errors,
    };
  } catch (error) {
    return buildUnavailableData(error instanceof Error ? error.message : String(error), accountConfigs);
  }
}
