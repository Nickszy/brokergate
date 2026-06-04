import { proxyOrderRequest } from "../_proxy";

export async function POST(request: Request) {
  return proxyOrderRequest(request, "/v1/orders/drafts");
}
