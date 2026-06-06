import { ArrowUpRight, Check, Clock, Plus, RefreshCw } from "lucide-react";
import type { DashboardData } from "@/lib/brokergate-api";
import { changeTone } from "@/lib/format";

const LEDGER_TONE_CLASS = { up: "positive", down: "negative", flat: "flat" } as const;

function fmt(value: number): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export function LedgerVariant({ data }: { data: DashboardData }) {
  const { accounts, positions, aggregates } = data;

  const usdTotal = aggregates.totalByCurrency.find((t) => t.currency === "USD");
  const hkdTotal = aggregates.totalByCurrency.find((t) => t.currency === "HKD");
  const usdCash = aggregates.cashByCurrency.find((t) => t.currency === "USD");
  const hkdCash = aggregates.cashByCurrency.find((t) => t.currency === "HKD");

  return (
    <main className="ledgerShell">
      <header className="ledgerHeader">
        <div>
          <span>BrokerGate Ledger Sheet</span>
          <h1>Assets first. Orders second. No hidden pooling.</h1>
        </div>
        <div className="ledgerButtons">
          <button type="button"><RefreshCw /> Refresh</button>
          <button type="button"><Plus /> Add account</button>
          <button className="dark" type="button"><ArrowUpRight /> New order</button>
        </div>
      </header>

      <section className="ledgerSummary">
        <div>
          <span>Total USD assets</span>
          <strong>{usdTotal ? fmt(usdTotal.value) : "—"}</strong>
          <small>Shown without FX conversion</small>
        </div>
        <div>
          <span>Total HKD assets</span>
          <strong>{hkdTotal ? fmt(hkdTotal.value) : "—"}</strong>
          <small>Shown without FX conversion</small>
        </div>
        <div>
          <span>Accounts</span>
          <strong>{aggregates.totalBrokers}</strong>
          <small>{aggregates.connectedCount} connected, {aggregates.totalBrokers - aggregates.connectedCount} planned</small>
        </div>
      </section>

      <section className="ledgerTableBlock">
        <div className="ledgerTitle">
          <h2>Account register</h2>
          <p>Every balance stays attached to its broker account.</p>
        </div>
        <table className="ledgerTable">
          <thead>
            <tr><th>Account</th><th>Currency</th><th>Assets</th><th>Cash</th><th>Change</th><th>Status</th></tr>
          </thead>
          <tbody>
            {accounts.map((account) => {
              const currency = account.value.split(" ")[0] || "";
              const assets = account.value.replace(/^[A-Z]{3}\s+/, "");
              return (
                <tr key={account.id}>
                  <td>{account.brokerName}</td>
                  <td>{currency}</td>
                  <td>{assets}</td>
                  <td>—</td>
                  <td className={LEDGER_TONE_CLASS[changeTone(account.change)]}>{account.change || "—"}</td>
                  <td>{account.status === "ready" ? <Check /> : <Clock />} {account.status}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="ledgerTableBlock">
        <div className="ledgerTitle">
          <h2>Consolidated holdings</h2>
          <p>Grouped view for scanning, account detail preserved for action.</p>
        </div>
        <table className="ledgerTable">
          <thead>
            <tr><th>Symbol</th><th>Name</th><th>Currency</th><th>Qty</th><th>Market value</th><th>Held in</th></tr>
          </thead>
          <tbody>
            {positions.map((position) => {
              const currency = position.marketValue.split(" ")[0] || "";
              const value = position.marketValue.replace(/^[A-Z]{3}\s+/, "");
              return (
                <tr key={position.symbol}>
                  <td><strong>{position.symbol}</strong></td>
                  <td>{position.name}</td>
                  <td>{currency}</td>
                  <td>{position.quantity}</td>
                  <td>{value}</td>
                  <td>{position.accounts.join(", ")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </main>
  );
}
