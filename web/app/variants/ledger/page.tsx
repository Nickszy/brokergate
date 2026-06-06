import { fetchDashboardData } from "@/lib/brokergate-api";
import { LedgerVariant } from "@/components/variant-ledger";

export const revalidate = 30;

export default async function Page() {
  const data = await fetchDashboardData();
  return <LedgerVariant data={data} />;
}
