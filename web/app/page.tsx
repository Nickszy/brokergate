import { fetchDashboardData } from "@/lib/brokergate-api";
import { Dashboard } from "@/components/dashboard";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function Page() {
  const data = await fetchDashboardData();
  return (
    <Dashboard
      accounts={data.accounts}
      positions={data.positions}
      connections={data.connections}
      summary={data.summary}
      dataStatus={data.dataStatus}
      errors={data.errors}
    />
  );
}
