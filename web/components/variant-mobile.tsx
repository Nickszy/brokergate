import { ArrowUpRight, Bell, ChevronRight, CircleDollarSign, Plus, ShieldCheck } from "lucide-react";
import type { DashboardData } from "@/lib/brokergate-api";
import { changeTone } from "@/lib/format";

function fmt(value: number): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export function MobileVariant({ data }: { data: DashboardData }) {
  const { accounts, positions, aggregates } = data;

  const usdTotal = aggregates.totalByCurrency.find((t) => t.currency === "USD");
  const hkdTotal = aggregates.totalByCurrency.find((t) => t.currency === "HKD");
  const usdCash = aggregates.cashByCurrency.find((t) => t.currency === "USD");

  return (
    <main className="mobileShell">
      <section className="phoneFrame">
        <header className="phoneTop">
          <div>
            <span>BrokerGate</span>
            <h1>All accounts</h1>
          </div>
          <button type="button"><Bell /></button>
        </header>

        <section className="phoneHero">
          <span>Aggregated assets</span>
          <strong>{usdTotal ? `USD ${fmt(usdTotal.value)}` : "—"}</strong>
          <small>{hkdTotal ? `HKD ${fmt(hkdTotal.value)} tracked separately` : ""}</small>
          <div className="phoneHeroActions">
            <button type="button"><Plus /> Account</button>
            <button type="button"><ArrowUpRight /> Order</button>
          </div>
        </section>

        <section className="phoneStrip">
          <div><CircleDollarSign /><span>Cash</span><strong>{usdCash ? fmt(usdCash.value) : "—"}</strong></div>
          <div><ShieldCheck /><span>Risk</span><strong>Scoped</strong></div>
        </section>

        <section className="phoneSection">
          <div className="phoneSectionHead">
            <h2>Accounts</h2>
            <span>{aggregates.connectedCount} connected</span>
          </div>
          {accounts.map((account) => (
            <button className="phoneAccount" type="button" key={account.id}>
              <span>
                <strong>{account.brokerName}</strong>
                <small>{account.status}</small>
              </span>
              <span>
                <strong>{account.value}</strong>
                <small className={changeTone(account.change)}>{account.change || "—"}</small>
              </span>
              <ChevronRight />
            </button>
          ))}
        </section>

        <section className="phoneSection">
          <div className="phoneSectionHead">
            <h2>Holdings</h2>
            <span>Grouped</span>
          </div>
          {positions.map((position) => (
            <button className="phonePosition" type="button" key={position.symbol}>
              <span>
                <strong>{position.symbol}</strong>
                <small>{position.accounts.join(", ")}</small>
              </span>
              <strong>{position.marketValue}</strong>
            </button>
          ))}
        </section>
      </section>

      <aside className="mobileNotes">
        <span className="eyebrow">Direction D</span>
        <h2>Feels like a brokerage app, but neutral.</h2>
        <p>
          This direction optimizes for the first five minutes on a phone: what changed,
          which account is stale, and what can I act on without opening another app.
        </p>
      </aside>
    </main>
  );
}
