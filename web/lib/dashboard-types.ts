export type Account = {
  id: string;
  broker: string;
  brokerCode: string;
  brokerName: string;
  accountId: string;
  accountSuffix: string;
  status: "ready" | "stale" | "planned";
  statusText?: string;
  value: string;
  originalValue: string;
  valuesByCurrency: Record<string, string>;
  cash: string;
  originalCash: string;
  cashByCurrency: Record<string, string>;
  buyingPower: string;
  originalBuyingPower: string;
  buyingPowerByCurrency: Record<string, string>;
  change: string;
  trend: number[];
  color: "ink" | "blue" | "red";
};

export type Lot = {
  title: string;
  detail: string;
};

export type Position = {
  symbol: string;
  name: string;
  quantity: string;
  marketValue: string;
  originalMarketValue: string;
  marketValueByCurrency: Record<string, string>;
  accounts: string[];
  lots: Lot[];
};

export type Connection = {
  name: string;
  detail: string;
  status: "online" | "stale" | "planned";
};

export type DashboardSummary = {
  totalAssets: string;
  totalAssetsByCurrency: Record<string, string>;
  totalMeta: string[];
  cash: string;
  cashByCurrency: Record<string, string>;
  cashMeta: string;
  buyingPower: string;
  buyingPowerByCurrency: Record<string, string>;
  buyingPowerMeta: string;
  connection: string;
  connectionMeta: string;
  defaultCurrency: string;
  displayCurrencies: string[];
  fxMeta: string;
  fxRates: string[];
};

export type DataStatus = {
  label: string;
  detail: string;
  tone: "live" | "warning" | "error";
  updatedAt: string;
  apiBaseUrl: string;
  brokerMode?: string;
};
