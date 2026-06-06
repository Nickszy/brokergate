import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  CircleDollarSign,
  RefreshCw,
  ShieldCheck,
  TerminalSquare,
  WalletCards,
} from "lucide-react";
import type { DashboardData } from "@/lib/brokergate-api";
import { changeTone } from "@/lib/format";

function fmt(value: number): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export function CommandVariant({ data }: { data: DashboardData }) {
  const { accounts, positions, connections, aggregates } = data;

  const usdTotal = aggregates.totalByCurrency.find((t) => t.currency === "USD");
  const hkdTotal = aggregates.totalByCurrency.find((t) => t.currency === "HKD");
  const usdCash = aggregates.cashByCurrency.find((t) => t.currency === "USD");
  const hkdCash = aggregates.cashByCurrency.find((t) => t.currency === "HKD");

  return (
    <main className="commandShell">
      <header className="commandTop">
        <div>
          <span className="commandKicker">BrokerGate / Command Desk</span>
          <h1>All brokerage accounts, one operating picture.</h1>
        </div>
        <div className="commandActions">
          <button type="button"><RefreshCw /> Sync</button>
          <button className="hot" type="button"><ArrowUpRight /> New order</button>
        </div>
      </header>

      <section className="commandStats" aria-label="Asset summary">
        <div className="commandStat primary">
          <span>Aggregated assets</span>
          <strong>{usdTotal ? `USD ${fmt(usdTotal.value)}` : "—"}</strong>
          <small>{hkdTotal ? `HKD ${fmt(hkdTotal.value)} tracked separately` : ""}</small>
        </div>
        <div className="commandStat">
          <span>Cash</span>
          <strong>{usdCash ? `USD ${fmt(usdCash.value)}` : "—"}</strong>
          <small>{hkdCash ? `HKD ${fmt(hkdCash.value)}` : ""}</small>
        </div>
        <div className="commandStat">
          <span>Connections</span>
          <strong>{aggregates.connectedCount} / {aggregates.totalBrokers}</strong>
          <small>{aggregates.connectedCount < aggregates.totalBrokers ? "Some connections stale or planned" : "All connected"}</small>
        </div>
        <div className="commandStat">
          <span>Risk boundary</span>
          <strong>Account scoped</strong>
          <small>No pooled buying power</small>
        </div>
      </section>

      <div className="commandGrid">
        <section className="commandPanel">
          <div className="commandPanelHead">
            <h2><WalletCards /> Accounts</h2>
            <span>Connection and asset deltas</span>
          </div>
          <div className="commandAccountList">
            {accounts.map((account) => (
              <div className="commandAccount" key={account.id}>
                <div>
                  <strong>{account.brokerName}</strong>
                  <span>{account.accountSuffix}</span>
                </div>
                <div>
                  <strong>{account.value}</strong>
                  <span className={changeTone(account.change)}>{account.change}</span>
                </div>
                <span className={account.status === "ready" ? "commandBadge good" : "commandBadge warn"}>
                  {account.status === "ready" ? <CheckCircle2 /> : <AlertTriangle />}
                  {account.status}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="commandPanel positionsPanel">
          <div className="commandPanelHead">
            <h2><TerminalSquare /> Positions</h2>
            <span>Grouped by symbol</span>
          </div>
          <div className="commandRows">
            {positions.map((position) => (
              <div className="commandRow" key={position.symbol}>
                <div><strong>{position.symbol}</strong><span>{position.name}</span></div>
                <span>{position.quantity}</span>
                <strong>{position.marketValue}</strong>
                <span>{position.accounts.join(", ")}</span>
              </div>
            ))}
          </div>
        </section>

        <aside className="commandRisk">
          <ShieldCheck />
          <h2>Execution stays boring.</h2>
          <p>Every order is drafted against one selected account, checked against that account snapshot, then confirmed by exact server text.</p>
          <div className="riskTicks">
            <span><CircleDollarSign /> Buying power checked</span>
            <span><ArrowDownRight /> Sell quantity checked</span>
            <span><ShieldCheck /> Human confirmation required</span>
          </div>
        </aside>
      </div>
    </main>
  );
}
