import { fetchDashboardData } from "@/lib/brokergate-api";
import { MobileVariant } from "@/components/variant-mobile";

export const revalidate = 30;

export default async function Page() {
  const data = await fetchDashboardData();
  return <MobileVariant data={data} />;
}
