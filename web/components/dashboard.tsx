"use client";

import {
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  BriefcaseBusiness,
  ChevronDown,
  DatabaseZap,
  LayoutDashboard,
  List,
  Menu,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  WalletCards,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useTransition } from "react";
import type { ReactNode } from "react";
import type {
  Account,
  Connection,
  DashboardSummary,
  DataStatus,
  Position,
} from "@/lib/dashboard-types";

type DashboardProps = {
  accounts: Account[];
  positions: Position[];
  connections: Connection[];
  summary: DashboardSummary;
  dataStatus: DataStatus;
  errors: string[];
};

type TabId = "assets" | "positions" | "orders" | "accounts";

type SymbolLookup = {
  errors: string[];
  instrument: {
    currency?: string | null;
    market?: string | null;
    name?: string | null;
    symbol?: string;
    tradable?: boolean | null;
  } | null;
  quote: {
    ask_price?: string | null;
    bid_price?: string | null;
    currency?: string | null;
    last_price?: string | null;
    name?: string | null;
    symbol?: string;
  } | null;
  symbol: string;
};

type OrderSide = "buy" | "sell";
type OrderType = "limit" | "market";
type OrderActionKind = "preview" | "draft" | "submit";
type OrderActionStatus = "idle" | "loading" | "success" | "error";

type OrderActionResult = {
  kind: OrderActionKind;
  payload: Record<string, unknown>;
};

const tabMeta: Record<TabId, { eyebrow: string; title: string }> = {
  assets: { eyebrow: "券商聚合账户", title: "总资产" },
  positions: { eyebrow: "持仓查询", title: "持仓" },
  orders: { eyebrow: "交易草稿", title: "下单" },
  accounts: { eyebrow: "账户连接", title: "账户" },
};

const statusClass: Record<Account["status"] | Connection["status"], string> = {
  ready: "pill green",
  stale: "pill amber",
  planned: "pill",
  online: "pill green",
};

const dataStatusClass: Record<DataStatus["tone"], string> = {
  live: "apiBanner live",
  warning: "apiBanner warning",
  error: "apiBanner error",
};

const statusLabel: Record<Account["status"] | Connection["status"], string> = {
  ready: "就绪",
  stale: "待刷新",
  planned: "待接入",
  online: "在线",
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }

  return String(value);
}

function inferCurrency(symbol: string, lookupCurrency?: string | null): string {
  const explicit = lookupCurrency?.trim().toUpperCase();
  if (explicit && explicit.length === 3) {
    return explicit;
  }

  const normalized = symbol.trim().toUpperCase();
  if (normalized.endsWith(".HK") || normalized.endsWith(".HKEX") || normalized.startsWith("HK.")) {
    return "HKD";
  }

  if (normalized.endsWith(".SS") || normalized.endsWith(".SZ")) {
    return "CNY";
  }

  return "USD";
}

function formatOrderAmount(value: unknown, currency: string): string {
  const text = stringValue(value);
  if (!text) {
    return "待返回";
  }

  return `${currency} ${Number(text).toLocaleString("en-US", {
    maximumFractionDigits: 4,
    minimumFractionDigits: 0,
  })}`;
}

function riskChecksFrom(payload: Record<string, unknown>): Record<string, unknown>[] {
  const draft = asRecord(payload.draft);
  const checks = Array.isArray(payload.risk_checks)
    ? payload.risk_checks
    : Array.isArray(draft?.risk_checks)
      ? draft?.risk_checks
      : [];

  return checks.map(asRecord).filter((item): item is Record<string, unknown> => Boolean(item));
}

function draftIdFrom(payload: Record<string, unknown>): string {
  return stringValue(asRecord(payload.draft)?.id);
}

function OrderResultPanel({
  brokerMode,
  confirmationText,
  currency,
  onConfirmationTextChange,
  onSubmitDraft,
  result,
  submitDisabled,
  submitStatus,
}: {
  brokerMode?: string;
  confirmationText: string;
  currency: string;
  onConfirmationTextChange: (value: string) => void;
  onSubmitDraft: () => void;
  result: OrderActionResult;
  submitDisabled: boolean;
  submitStatus: OrderActionStatus;
}) {
  const payload = result.payload;
  const draft = asRecord(payload.draft);
  const request = asRecord(draft?.request);
  const brokerPreview = asRecord(payload.broker_preview);
  const previewDetail = asRecord(brokerPreview?.preview);
  const checks = riskChecksFrom(payload);
  const symbol = stringValue(payload.symbol || request?.symbol);
  const side = stringValue(payload.side || request?.side);
  const quantity = stringValue(payload.quantity || request?.quantity);
  const limitPrice = stringValue(payload.limit_price || request?.limit_price);
  const estimatedAmount = payload.estimated_amount;
  const estimatedFees = payload.estimated_fees || previewDetail?.commission;
  const maxTradableQuantity = payload.max_tradable_quantity;
  const requiredConfirmation = stringValue(payload.required_confirmation);
  const brokerOrderId = stringValue(payload.broker_order_id);
  const submitStatusLabel = stringValue(payload.status);
  const canSubmit = result.kind === "draft" && Boolean(draftIdFrom(payload)) && Boolean(requiredConfirmation);
  const isLiveMode = brokerMode === "真实交易模式";

  return (
    <>
      <strong>
        {result.kind === "preview"
          ? "预览成功"
          : result.kind === "submit"
            ? "已提交到券商"
            : "草稿已创建"}
      </strong>
      <div className="resultGrid">
        {draft?.id ? (
          <span>
            <small>草稿 ID</small>
            <b>{stringValue(draft.id)}</b>
          </span>
        ) : null}
        {symbol ? (
          <span>
            <small>订单</small>
            <b>
              {side === "sell" ? "卖出" : "买入"} {quantity} {symbol}
            </b>
          </span>
        ) : null}
        {limitPrice ? (
          <span>
            <small>限价</small>
            <b>{formatOrderAmount(limitPrice, currency)}</b>
          </span>
        ) : null}
        {estimatedAmount ? (
          <span>
            <small>预估金额</small>
            <b>{formatOrderAmount(estimatedAmount, currency)}</b>
          </span>
        ) : null}
        {estimatedFees ? (
          <span>
            <small>预估费用</small>
            <b>{formatOrderAmount(estimatedFees, currency)}</b>
          </span>
        ) : null}
        {maxTradableQuantity ? (
          <span>
            <small>最大可交易</small>
            <b>{stringValue(maxTradableQuantity)}</b>
          </span>
        ) : null}
        {requiredConfirmation ? (
          <span className="wide">
            <small>后续确认口令</small>
            <b>{requiredConfirmation}</b>
          </span>
        ) : null}
        {brokerOrderId ? (
          <span className="wide">
            <small>券商订单号</small>
            <b>{brokerOrderId}</b>
          </span>
        ) : null}
        {submitStatusLabel && result.kind === "submit" ? (
          <span>
            <small>提交状态</small>
            <b>{submitStatusLabel}</b>
          </span>
        ) : null}
      </div>
      {checks.length > 0 ? (
        <div className="checkList">
          {checks.map((check) => (
            <span className={`check ${stringValue(check.status)}`} key={stringValue(check.rule_id)}>
              <b>{stringValue(check.status) === "blocked" ? "拦截" : "通过"}</b>
              {stringValue(check.reason)}
            </span>
          ))}
        </div>
      ) : null}
      {canSubmit ? (
        <div className={`confirmBox ${isLiveMode ? "live" : "paper"}`}>
          <div>
            <strong>{isLiveMode ? "真实交易确认" : "当前不是实盘模式"}</strong>
            <span>
              {isLiveMode
                ? "输入确认口令后会提交到券商。"
                : `当前后端模式是 ${brokerMode || "未知"}，提交不会进入真实老虎交易环境。`}
            </span>
          </div>
          <label className="field">
            <span>确认口令</span>
            <input
              value={confirmationText}
              onChange={(event) => onConfirmationTextChange(event.target.value)}
              placeholder={requiredConfirmation}
            />
          </label>
          <button
            className="action danger"
            type="button"
            disabled={submitDisabled || confirmationText.trim() !== requiredConfirmation}
            onClick={onSubmitDraft}
          >
            {submitStatus === "loading" ? "正在提交到券商..." : "提交到券商"}
          </button>
        </div>
      ) : null}
      <span className="orderNote">
        {result.kind === "submit"
          ? "这一步已调用券商提交接口，是否出现在 App 取决于当前后端模式和券商账号环境。"
          : "预览不会下单；草稿创建后，输入确认口令并点击提交才会调用券商接口。"}
      </span>
    </>
  );
}

function Sparkline({ values, tone }: { values: number[]; tone: Account["color"] }) {
  const safeValues = values.length > 1 ? values : [10, 10, 10, 10, 10, 10];
  const max = Math.max(...safeValues);
  const min = Math.min(...safeValues);
  const points = safeValues
    .map((value, index) => {
      const x = (index / (safeValues.length - 1)) * 88 + 1;
      const y = 29 - ((value - min) / Math.max(max - min, 1)) * 25;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg className="spark" viewBox="0 0 90 32" aria-hidden="true">
      <polyline className={`spark-line ${tone}`} points={points} />
    </svg>
  );
}

function DataStatusBanner({
  dataStatus,
  errors,
  isRefreshing,
  onRefresh,
}: {
  dataStatus: DataStatus;
  errors: string[];
  isRefreshing: boolean;
  onRefresh: () => void;
}) {
  return (
    <section className={dataStatusClass[dataStatus.tone]} aria-label="接口数据状态">
      <div className="apiBannerIcon">
        {dataStatus.tone === "live" ? <DatabaseZap /> : <AlertTriangle />}
      </div>
      <div>
        <strong>{dataStatus.label}</strong>
        <span>{dataStatus.detail}</span>
        <div className="apiBannerActions">
          <small>每分钟自动刷新</small>
          <button type="button" onClick={onRefresh} disabled={isRefreshing}>
            <RefreshCw className={isRefreshing ? "spin" : ""} />
            {isRefreshing ? "刷新中" : "手动刷新"}
          </button>
        </div>
        {errors.length > 0 ? (
          <div className="apiErrors">
            {errors.slice(0, 2).map((error) => (
              <small key={error}>{error}</small>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}

export function Dashboard({
  accounts,
  positions,
  connections,
  summary,
  dataStatus,
  errors,
}: DashboardProps) {
  const router = useRouter();
  const [isRefreshing, startRefreshTransition] = useTransition();
  const [activeTab, setActiveTab] = useState<TabId>("assets");
  const [selectedAccount, setSelectedAccount] = useState("all");
  const [selectedCurrency, setSelectedCurrency] = useState(summary.defaultCurrency);
  const [query, setQuery] = useState("");
  const [orderAccountId, setOrderAccountId] = useState(accounts[0]?.id || "");
  const [orderSide, setOrderSide] = useState<OrderSide>("buy");
  const [orderType, setOrderType] = useState<OrderType>("limit");
  const [orderSymbol, setOrderSymbol] = useState(positions[0]?.symbol || "");
  const [orderQuantity, setOrderQuantity] = useState("");
  const [limitPrice, setLimitPrice] = useState("");
  const [priceTouched, setPriceTouched] = useState(false);
  const [orderActionStatus, setOrderActionStatus] = useState<OrderActionStatus>("idle");
  const [orderActionLabel, setOrderActionLabel] = useState("");
  const [orderResult, setOrderResult] = useState<OrderActionResult | null>(null);
  const [orderError, setOrderError] = useState("");
  const [confirmationText, setConfirmationText] = useState("");
  const [symbolLookup, setSymbolLookup] = useState<SymbolLookup | null>(null);
  const [symbolLookupStatus, setSymbolLookupStatus] = useState<
    "idle" | "loading" | "found" | "error"
  >("idle");
  const [openRows, setOpenRows] = useState<Set<string>>(
    () => new Set(positions[0]?.symbol ? [positions[0].symbol] : []),
  );

  const selectedAccountName = useMemo(
    () => accounts.find((account) => account.id === selectedAccount)?.brokerName,
    [accounts, selectedAccount],
  );

  const filteredPositions = useMemo(() => {
    const normalized = query.trim().toUpperCase();
    return positions.filter((position) => {
      const matchesAccount =
        selectedAccount === "all" ||
        Boolean(selectedAccountName && position.accounts.includes(selectedAccountName));
      const matchesQuery =
        !normalized ||
        position.symbol.toUpperCase().includes(normalized) ||
        position.name.toUpperCase().includes(normalized);

      return matchesAccount && matchesQuery;
    });
  }, [positions, query, selectedAccount, selectedAccountName]);

  const primaryAccountId = accounts[0]?.id || "";
  const selectedOrderAccount = useMemo(
    () => accounts.find((account) => account.id === orderAccountId) || accounts[0],
    [accounts, orderAccountId],
  );
  const totalAssets = summary.totalAssetsByCurrency[selectedCurrency] || summary.totalAssets;
  const buyingPower = summary.buyingPowerByCurrency[selectedCurrency] || summary.buyingPower;
  const currentMeta = tabMeta[activeTab];
  const lookupName = symbolLookup?.instrument?.name || symbolLookup?.quote?.name;
  const lookupCurrency = symbolLookup?.instrument?.currency || symbolLookup?.quote?.currency;
  const lookupSymbol = symbolLookup?.instrument?.symbol || symbolLookup?.quote?.symbol || symbolLookup?.symbol;
  const lookupLastPrice = symbolLookup?.quote?.last_price;
  const orderCurrency = inferCurrency(orderSymbol, lookupCurrency);

  function refreshDashboard() {
    startRefreshTransition(() => {
      router.refresh();
    });
  }

  useEffect(() => {
    const timer = window.setInterval(() => {
      startRefreshTransition(() => {
        router.refresh();
      });
    }, 60_000);

    return () => window.clearInterval(timer);
  }, [router]);

  useEffect(() => {
    if (accounts.length === 0) {
      setOrderAccountId("");
      return;
    }

    if (!orderAccountId || !accounts.some((account) => account.id === orderAccountId)) {
      setOrderAccountId(accounts[0].id);
    }
  }, [accounts, orderAccountId]);

  useEffect(() => {
    const symbol = orderSymbol.trim().toUpperCase();
    if (!symbol) {
      setSymbolLookup(null);
      setSymbolLookupStatus("idle");
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSymbolLookupStatus("loading");
      try {
        const response = await fetch(`/api/market/lookup?broker=auto&symbol=${encodeURIComponent(symbol)}`, {
          signal: controller.signal,
        });
        const payload = (await response.json()) as SymbolLookup;
        setSymbolLookup(payload);
        setSymbolLookupStatus(response.ok ? "found" : "error");
      } catch (error) {
        if (!controller.signal.aborted) {
          setSymbolLookup({
            errors: [error instanceof Error ? error.message : String(error)],
            instrument: null,
            quote: null,
            symbol,
          });
          setSymbolLookupStatus("error");
        }
      }
    }, 450);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [orderSymbol]);

  useEffect(() => {
    if (lookupLastPrice && !priceTouched) {
      setLimitPrice(String(lookupLastPrice));
    }
  }, [lookupLastPrice, priceTouched]);

  function toggleRow(symbol: string) {
    setOpenRows((current) => {
      const next = new Set(current);
      if (next.has(symbol)) {
        next.delete(symbol);
      } else {
        next.add(symbol);
      }
      return next;
    });
  }

  function clearOrderFeedback() {
    setOrderActionStatus("idle");
    setOrderActionLabel("");
    setOrderResult(null);
    setOrderError("");
    setConfirmationText("");
  }

  function buildOrderPayload(): Record<string, unknown> | null {
    const symbol = orderSymbol.trim().toUpperCase();
    const quantity = Number(orderQuantity);
    const price = Number(limitPrice);

    if (!selectedOrderAccount) {
      setOrderError("请先选择一个券商账户。");
      setOrderActionStatus("error");
      return null;
    }

    if (!symbol) {
      setOrderError("请输入标的代码。");
      setOrderActionStatus("error");
      return null;
    }

    if (!Number.isFinite(quantity) || quantity <= 0) {
      setOrderError("请输入大于 0 的数量。");
      setOrderActionStatus("error");
      return null;
    }

    if (orderType === "limit" && (!Number.isFinite(price) || price <= 0)) {
      setOrderError("限价单需要填写大于 0 的限价。");
      setOrderActionStatus("error");
      return null;
    }

    return {
      account_id: selectedOrderAccount.accountId,
      broker: selectedOrderAccount.broker,
      client_memo: "created from BrokerGate web",
      currency: orderCurrency,
      limit_price: orderType === "limit" ? limitPrice : null,
      order_type: orderType,
      quantity: orderQuantity,
      side: orderSide,
      symbol,
    };
  }

  async function submitOrderAction(kind: OrderActionKind) {
    const payload = buildOrderPayload();
    if (!payload) {
      return;
    }

    const label = kind === "preview" ? "预览" : "创建草稿";
    setOrderActionStatus("loading");
    setOrderActionLabel(label);
    setOrderResult(null);
    setOrderError("");

    try {
      const response = await fetch(kind === "preview" ? "/api/orders/preview" : "/api/orders/drafts", {
        body: JSON.stringify(payload),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      const responsePayload = (await response.json()) as Record<string, unknown>;

      if (!response.ok) {
        const detail = responsePayload.detail || responsePayload.error || response.statusText;
        throw new Error(Array.isArray(detail) ? JSON.stringify(detail) : String(detail));
      }

      setOrderResult({ kind, payload: responsePayload });
      setOrderActionStatus("success");
      setOrderActionLabel(label);
      if (kind === "draft") {
        setConfirmationText("");
      }
    } catch (error) {
      setOrderError(error instanceof Error ? error.message : String(error));
      setOrderActionStatus("error");
      setOrderActionLabel(label);
    }
  }

  async function submitConfirmedDraft() {
    if (!orderResult || orderResult.kind !== "draft") {
      setOrderError("请先创建草稿。");
      setOrderActionStatus("error");
      setOrderActionLabel("提交到券商");
      return;
    }

    const draftId = draftIdFrom(orderResult.payload);
    const requiredConfirmation = stringValue(orderResult.payload.required_confirmation);

    if (!draftId) {
      setOrderError("草稿缺少 ID，无法提交。");
      setOrderActionStatus("error");
      setOrderActionLabel("提交到券商");
      return;
    }

    if (confirmationText.trim() !== requiredConfirmation) {
      setOrderError("确认口令不匹配。");
      setOrderActionStatus("error");
      setOrderActionLabel("提交到券商");
      return;
    }

    setOrderActionStatus("loading");
    setOrderActionLabel("提交到券商");
    setOrderError("");

    try {
      const response = await fetch("/api/orders/confirm", {
        body: JSON.stringify({
          confirmed_by: "web-user",
          confirmation_text: confirmationText.trim(),
          draft_id: draftId,
        }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      const responsePayload = (await response.json()) as Record<string, unknown>;

      if (!response.ok) {
        const detail = responsePayload.detail || responsePayload.error || response.statusText;
        throw new Error(Array.isArray(detail) ? JSON.stringify(detail) : String(detail));
      }

      setOrderResult({ kind: "submit", payload: responsePayload });
      setOrderActionStatus("success");
      setOrderActionLabel("提交到券商");
    } catch (error) {
      setOrderError(error instanceof Error ? error.message : String(error));
      setOrderActionStatus("error");
      setOrderActionLabel("提交到券商");
    }
  }

  function navButton(tab: TabId, label: string, icon: ReactNode, count?: number) {
    return (
      <button
        className={activeTab === tab ? "active" : ""}
        type="button"
        onClick={() => setActiveTab(tab)}
      >
        {icon}
        {label}
        {typeof count === "number" ? <span className="count">{count}</span> : null}
      </button>
    );
  }

  return (
    <div className="shell">
      <aside className="side" aria-label="主导航">
        <div className="brand">
          <div className="mark">BG</div>
          <div>
            <strong>BrokerGate</strong>
            <span>统一交易台</span>
          </div>
        </div>

        <nav className="nav">
          {navButton("assets", "资产", <LayoutDashboard />, accounts.length)}
          {navButton("positions", "持仓", <List />, positions.length)}
          {navButton("orders", "下单", <ArrowUpRight />)}
          {navButton("accounts", "账户", <Settings2 />)}
        </nav>

        <div className="sideStatus">
          <div className="statusRow">
            <span>网关</span>
            <span className={`dot ${dataStatus.tone === "error" ? "bad" : ""}`} aria-hidden="true" />
          </div>
          <div className="statusRow">
            <span>模式</span>
            <strong>{dataStatus.brokerMode || "未知"}</strong>
          </div>
          <div className="statusRow">
            <span>最近同步</span>
            <strong>
              {new Date(dataStatus.updatedAt).toLocaleTimeString("zh-CN", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </strong>
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="mobileBrand">
            <div className="mark">BG</div>
            <div>
              <div className="eyebrow">{currentMeta.eyebrow}</div>
              <h1>{currentMeta.title}</h1>
            </div>
          </div>

          <div className="desktopTitle">
            <div className="eyebrow">{currentMeta.eyebrow}</div>
            <h1>{currentMeta.title}</h1>
          </div>

          <div className="topActions">
            <button
              className="iconButton"
              type="button"
              title="刷新"
              onClick={refreshDashboard}
              disabled={isRefreshing}
            >
              <RefreshCw className={isRefreshing ? "spin" : ""} />
            </button>
            <button className="action" type="button" onClick={() => setActiveTab("accounts")}>
              <Plus />
              添加账户
            </button>
            <button className="action primary" type="button" onClick={() => setActiveTab("orders")}>
              <ArrowUpRight />
              新建订单
            </button>
          </div>
        </header>

        <DataStatusBanner
          dataStatus={dataStatus}
          errors={errors}
          isRefreshing={isRefreshing}
          onRefresh={refreshDashboard}
        />

        {activeTab === "assets" ? (
          <div className="workspace assetWorkspace">
            <section className="panel summary" aria-label="资产总览">
              <div className="summaryHead">
                <div className="total">
                  <span className="totalLabel">总资产</span>
                  <strong className="totalValue">{totalAssets}</strong>
                  <div className="totalMeta">
                    {summary.totalMeta.map((item) => (
                      <span className="pill" key={item}>
                        {item}
                      </span>
                    ))}
                    <span className="pill blue">{accounts.length} 个账户</span>
                  </div>
                </div>
                <div className="segmented currencySwitch" aria-label="显示币种">
                  {summary.displayCurrencies.map((currency) => (
                    <button
                      className={selectedCurrency === currency ? "active" : ""}
                      key={currency}
                      type="button"
                      onClick={() => setSelectedCurrency(currency)}
                    >
                      {currency}
                    </button>
                  ))}
                </div>
              </div>

              <div className="accounts" aria-label="券商账户">
                {accounts.length > 0 ? (
                  accounts.map((account) => (
                    <button
                      className={`accountCard ${selectedAccount === account.id ? "active" : ""}`}
                      type="button"
                      data-account={account.id}
                      key={account.id}
                      onClick={() => setSelectedAccount(account.id)}
                    >
                      <div className="accountTop">
                        <div className="broker">
                          <span className={`brokerLogo ${account.color}`}>{account.brokerCode}</span>
                          <span>
                            <span className="brokerName">{account.brokerName}</span>
                            <span className="brokerId">账号 {account.accountId}</span>
                          </span>
                        </div>
                        <span className={statusClass[account.status]}>
                          {account.statusText || statusLabel[account.status]}
                        </span>
                      </div>
                      <span className="accountValueLabel">账户资产</span>
                      <div className="accountValue">
                        {account.valuesByCurrency[selectedCurrency] || account.value}
                      </div>
                      <div className="accountStats">
                        <span>
                          <small>现金</small>
                          <strong>{account.cashByCurrency[selectedCurrency] || account.cash}</strong>
                        </span>
                        <span>
                          <small>可用购买力</small>
                          <strong>
                            {account.buyingPowerByCurrency[selectedCurrency] || account.buyingPower}
                          </strong>
                        </span>
                        <span>
                          <small>连接</small>
                          <strong>{account.statusText || statusLabel[account.status]}</strong>
                        </span>
                      </div>
                      <div className="accountFoot">
                        <span>{account.originalValue}</span>
                        <Sparkline values={account.trend} tone={account.color} />
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="emptyState">
                    <strong>还没有配置账户</strong>
                    <span>在 Web 运行环境里设置 BROKERGATE_WEB_ACCOUNTS 后会显示真实账户。</span>
                  </div>
                )}
              </div>
            </section>

            <aside className="assetRail">
              <section className="panel section" aria-label="汇率">
                {summary.fxRates.length > 0 ? (
                  <div className="fxBoard compactFx">
                    <div className="sectionTitle compact">
                      <h2>汇率</h2>
                      <span>{summary.fxMeta}</span>
                    </div>
                    <div className="fxRates">
                      {summary.fxRates.map((rate) => (
                        <span key={rate}>{rate}</span>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="emptyState">
                    <strong>汇率暂不可用</strong>
                    <span>服务端汇率接口返回后会显示换算参考。</span>
                  </div>
                )}
              </section>
            </aside>
          </div>
        ) : null}

        {activeTab === "positions" ? (
          <section className="panel section widePanel" aria-label="持仓">
            <div className="sectionHead">
              <div className="sectionTitle">
                <h2>持仓</h2>
                <span>{selectedAccount === "all" ? "按标的汇总" : selectedAccountName}</span>
              </div>
              <span className="pill blue">{filteredPositions.length} 项持仓</span>
            </div>

            <div className="toolbar">
              <label className="search">
                <Search />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  type="search"
                  placeholder="搜索代码"
                />
              </label>
              <div className="segmented" aria-label="账户筛选">
                <button
                  className={selectedAccount === "all" ? "active" : ""}
                  type="button"
                  onClick={() => setSelectedAccount("all")}
                >
                  全部
                </button>
                {accounts.slice(0, 2).map((account) => (
                  <button
                    className={selectedAccount === account.id ? "active" : ""}
                    key={account.id}
                    type="button"
                    onClick={() => setSelectedAccount(account.id)}
                  >
                    {account.brokerCode}
                  </button>
                ))}
              </div>
            </div>

            <div className="positionTable">
              <div className="positionRow header">
                <div>标的</div>
                <div className="num">数量</div>
                <div className="money">市值</div>
                <div className="num">账户</div>
                <div />
              </div>

              {filteredPositions.length > 0 ? (
                filteredPositions.map((position) => {
                  const open = openRows.has(position.symbol);

                  return (
                    <div className={`positionRow ${open ? "open" : ""}`} key={position.symbol}>
                      <div className="symbol">
                        <strong>{position.symbol}</strong>
                        <span>{position.name}</span>
                      </div>
                      <div className="num">{position.quantity}</div>
                      <div className="money">
                        {position.marketValueByCurrency[selectedCurrency] || position.marketValue}
                      </div>
                      <div className="accountChips">
                        {position.accounts.map((account) => (
                          <span className="chip" key={account}>
                            {account}
                          </span>
                        ))}
                      </div>
                      <button
                        className="expand"
                        type="button"
                        title={open ? "收起" : "展开"}
                        onClick={() => toggleRow(position.symbol)}
                      >
                        {open ? "-" : "+"}
                      </button>
                      <div className="detail">
                        <div className="lots">
                          {position.lots.map((lot) => (
                            <div className="lot" key={`${position.symbol}-${lot.title}`}>
                              <strong>{lot.title}</strong>
                              <span>{lot.detail}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="tableEmpty">
                  <strong>接口暂未返回持仓</strong>
                  <span>Python API 返回账户持仓后，这里会按标的自动汇总。</span>
                </div>
              )}
            </div>
          </section>
        ) : null}

        {activeTab === "orders" ? (
          <section className="panel drawer orderWorkspace" aria-label="下单草稿">
            <div className="draftHead">
              <div>
                <strong>下单草稿</strong>
                <span>服务端先创建草稿，提交到券商前必须人工确认</span>
              </div>
              <span className="pill green">风控校验</span>
            </div>
            <div className="draftBody">
              <div className="orderGrid">
                <label className="field">
                  <span>账户</span>
                  <select
                    value={orderAccountId || primaryAccountId}
                    disabled={accounts.length === 0}
                    onChange={(event) => {
                      setOrderAccountId(event.target.value);
                      clearOrderFeedback();
                    }}
                  >
                    {accounts.length > 0 ? (
                      accounts.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.brokerName} - {account.accountId}
                        </option>
                      ))
                    ) : (
                      <option value="">暂无账户</option>
                    )}
                  </select>
                </label>
                <label className="field">
                  <span>方向</span>
                  <select
                    value={orderSide}
                    onChange={(event) => {
                      setOrderSide(event.target.value as OrderSide);
                      clearOrderFeedback();
                    }}
                  >
                    <option value="buy">买入</option>
                    <option value="sell">卖出</option>
                  </select>
                </label>
                <label className="field">
                  <span>标的</span>
                  <input
                    value={orderSymbol}
                    onChange={(event) => {
                      setOrderSymbol(event.target.value.toUpperCase());
                      setLimitPrice("");
                      setPriceTouched(false);
                      clearOrderFeedback();
                    }}
                    placeholder="输入代码，如 AAPL / 700.HK"
                    type="search"
                  />
                </label>
                <label className="field">
                  <span>数量</span>
                  <input
                    value={orderQuantity}
                    min="0"
                    onChange={(event) => {
                      setOrderQuantity(event.target.value);
                      clearOrderFeedback();
                    }}
                    placeholder="0"
                    type="number"
                  />
                </label>
                <label className="field">
                  <span>类型</span>
                  <select
                    value={orderType}
                    onChange={(event) => {
                      setOrderType(event.target.value as OrderType);
                      clearOrderFeedback();
                    }}
                  >
                    <option value="limit">限价单</option>
                    <option value="market">市价单</option>
                  </select>
                </label>
                <label className="field">
                  <span>限价</span>
                  <input
                    value={limitPrice}
                    disabled={orderType === "market"}
                    onChange={(event) => {
                      setLimitPrice(event.target.value);
                      setPriceTouched(true);
                      clearOrderFeedback();
                    }}
                    placeholder={lookupLastPrice ? String(lookupLastPrice) : "0.00"}
                    type="number"
                  />
                </label>
              </div>

              {orderSymbol.trim() ? (
                <div className={`symbolLookup ${symbolLookupStatus}`} aria-live="polite">
                  {symbolLookupStatus === "loading" ? (
                    <span>正在查询 {orderSymbol.trim().toUpperCase()}...</span>
                  ) : null}
                  {symbolLookupStatus === "found" ? (
                    <>
                      <strong>{lookupSymbol}</strong>
                      <span>{lookupName || "已找到标的"}</span>
                      {lookupCurrency ? <span>{lookupCurrency}</span> : null}
                      {symbolLookup?.instrument?.market ? <span>{symbolLookup.instrument.market}</span> : null}
                      {lookupLastPrice ? <span>最新价 {lookupLastPrice}</span> : <span>暂无实时价，需手动填写</span>}
                    </>
                  ) : null}
                  {symbolLookupStatus === "error" ? (
                    <>
                      <strong>{orderSymbol.trim().toUpperCase()}</strong>
                      <span>{symbolLookup?.errors[0] || "标的查询失败"}</span>
                    </>
                  ) : null}
                </div>
              ) : null}

              <div className="riskLine">
                <span>
                  {selectedOrderAccount
                    ? `${selectedOrderAccount.brokerName} ${selectedOrderAccount.accountId}`
                    : "请选择账户"}
                </span>
                <span>{orderCurrency} / {buyingPower}</span>
              </div>

              <div className="draftActions">
                <button
                  className="action"
                  type="button"
                  disabled={orderActionStatus === "loading" || accounts.length === 0}
                  onClick={() => submitOrderAction("preview")}
                >
                  {orderActionStatus === "loading" && orderActionLabel === "预览" ? "预览中..." : "预览"}
                </button>
                <button
                  className="action primary"
                  type="button"
                  disabled={orderActionStatus === "loading" || accounts.length === 0}
                  onClick={() => submitOrderAction("draft")}
                >
                  {orderActionStatus === "loading" && orderActionLabel === "创建草稿" ? "创建中..." : "创建草稿"}
                </button>
              </div>

              {orderActionStatus !== "idle" ? (
                <div className={`orderResult ${orderActionStatus}`} aria-live="polite">
                  {orderActionStatus === "loading" ? (
                    <strong>{orderActionLabel}请求已发送，正在等待券商接口返回...</strong>
                  ) : null}

                  {orderActionStatus === "error" ? (
                    <>
                      <strong>{orderActionLabel || "下单请求"}失败</strong>
                      <span>{orderError}</span>
                    </>
                  ) : null}

                  {orderActionStatus === "success" && orderResult ? (
                    <OrderResultPanel
                      brokerMode={dataStatus.brokerMode}
                      confirmationText={confirmationText}
                      currency={orderCurrency}
                      onConfirmationTextChange={setConfirmationText}
                      onSubmitDraft={submitConfirmedDraft}
                      result={orderResult}
                      submitDisabled={false}
                      submitStatus="idle"
                    />
                  ) : null}
                </div>
              ) : null}
            </div>
          </section>
        ) : null}

        {activeTab === "accounts" ? (
          <div className="workspace accountWorkspace">
            <section className="panel section" aria-label="券商连接">
              <div className="sectionHead">
                <div className="sectionTitle">
                  <h2>券商连接</h2>
                  <span>连接状态</span>
                </div>
                <button
                  className="iconButton"
                  type="button"
                  title="刷新连接"
                  onClick={refreshDashboard}
                  disabled={isRefreshing}
                >
                  <RefreshCw className={isRefreshing ? "spin" : ""} />
                </button>
              </div>

              <div className="connectionList">
                {connections.map((connection) => (
                  <div className="connection" key={connection.name}>
                    <div>
                      <strong>{connection.name}</strong>
                      <span>{connection.detail}</span>
                    </div>
                    <span className={statusClass[connection.status]}>{statusLabel[connection.status]}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="panel section" aria-label="账户资产">
              <div className="sectionHead">
                <div className="sectionTitle">
                  <h2>账户资产</h2>
                  <span>{summary.fxMeta}</span>
                </div>
                <div className="segmented currencySwitch compactSwitch" aria-label="显示币种">
                  {summary.displayCurrencies.map((currency) => (
                    <button
                      className={selectedCurrency === currency ? "active" : ""}
                      key={currency}
                      type="button"
                      onClick={() => setSelectedCurrency(currency)}
                    >
                      {currency}
                    </button>
                  ))}
                </div>
              </div>
              <div className="snapshotList">
                {accounts.map((account) => (
                  <div className="snapshotRow large" key={account.id}>
                    <span className="snapshotIdentity">
                      <span>{account.brokerName}</span>
                      <small>{account.accountId}</small>
                    </span>
                    <strong>{account.valuesByCurrency[selectedCurrency] || account.value}</strong>
                  </div>
                ))}
              </div>
              {summary.fxRates.length > 0 ? (
                <div className="fxBoard" aria-label="汇率">
                  <div className="fxRates">
                    {summary.fxRates.map((rate) => (
                      <span key={rate}>{rate}</span>
                    ))}
                  </div>
                </div>
              ) : null}
            </section>
          </div>
        ) : null}
      </main>

      <nav className="bottomNav" aria-label="移动端导航">
        <button
          className={activeTab === "assets" ? "active" : ""}
          type="button"
          onClick={() => setActiveTab("assets")}
        >
          <LayoutDashboard />
          资产
        </button>
        <button
          className={activeTab === "positions" ? "active" : ""}
          type="button"
          onClick={() => setActiveTab("positions")}
        >
          <BarChart3 />
          持仓
        </button>
        <button
          className={activeTab === "orders" ? "active" : ""}
          type="button"
          onClick={() => setActiveTab("orders")}
        >
          <BriefcaseBusiness />
          下单
        </button>
        <button
          className={activeTab === "accounts" ? "active" : ""}
          type="button"
          onClick={() => setActiveTab("accounts")}
        >
          <WalletCards />
          账户
        </button>
      </nav>

      <button className="mobileMenu" type="button" title="菜单">
        <Menu />
      </button>
      <div className="safetyBadge">
        <ShieldCheck />
        服务端 API Key
        <ChevronDown />
      </div>
    </div>
  );
}
