import { fetchDashboardData } from "@/lib/brokergate-api";
import { CommandVariant } from "@/components/variant-command";

export const revalidate = 30;

export default async function Page() {
  const data = await fetchDashboardData();
  return <CommandVariant data={data} />;
}
