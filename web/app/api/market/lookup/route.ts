import { NextResponse } from "next/server";

type LookupPayload = {
  errors: string[];
  instrument: Record<string, unknown> | null;
  quote: Record<string, unknown> | null;
  symbol: string;
};

function getBaseUrl(): string {
  return (process.env.BROKERGATE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
}

function fallbackUrls(): string[] {
  const baseUrl = getBaseUrl();
  const fallbackBaseUrl = baseUrl.includes("127.0.0.1")
    ? baseUrl.replace("127.0.0.1", "localhost")
    : baseUrl.includes("localhost")
      ? baseUrl.replace("localhost", "127.0.0.1")
      : "";

  return [baseUrl, fallbackBaseUrl].filter(Boolean);
}

function formatError(error: unknown): string {
  if (error instanceof Error) {
    const cause = "cause" in error ? (error as Error & { cause?: unknown }).cause : undefined;
    return cause instanceof Error ? `${error.message}; cause: ${cause.message}` : error.message;
  }

  return String(error);
}

async function brokerGateFetch<T>(path: string): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const apiKey = process.env.BROKERGATE_API_KEY;
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  let lastNetworkError: unknown;

  for (const baseUrl of fallbackUrls()) {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 12000);

      try {
        const response = await fetch(`${baseUrl}${path}`, {
          cache: "no-store",
          headers,
          signal: controller.signal,
        });

        if (!response.ok) {
          const body = await response.text().catch(() => "");
          throw new Error(
            `BrokerGate ${response.status}${body ? `: ${body.slice(0, 180)}` : ""}`,
          );
        }

        return response.json() as Promise<T>;
      } catch (error) {
        lastNetworkError = error;
        await new Promise((resolve) => setTimeout(resolve, 180));
      } finally {
        clearTimeout(timeout);
      }
    }
  }

  throw new Error(`BrokerGate API 网络错误：${formatError(lastNetworkError)}`);
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const symbol = (url.searchParams.get("symbol") || "").trim().toUpperCase();
  const broker = (url.searchParams.get("broker") || "auto").trim() || "auto";

  if (!symbol) {
    return NextResponse.json({ error: "缺少标的代码" }, { status: 400 });
  }

  const instrumentPath = `/v1/market/instruments/${encodeURIComponent(symbol)}?broker=${encodeURIComponent(
    broker,
  )}&fallback=true`;
  const quotePath = `/v1/market/quotes?broker=${encodeURIComponent(
    broker,
  )}&fallback=true&symbols=${encodeURIComponent(symbol)}`;

  const [instrumentResult, quoteResult] = await Promise.allSettled([
    brokerGateFetch<Record<string, unknown>>(instrumentPath),
    brokerGateFetch<{ quotes?: Record<string, unknown>[] }>(quotePath),
  ]);

  const errors: string[] = [];
  const instrument =
    instrumentResult.status === "fulfilled" ? instrumentResult.value : null;
  const quote =
    quoteResult.status === "fulfilled" ? quoteResult.value.quotes?.[0] || null : null;

  if (instrumentResult.status === "rejected") {
    errors.push(`标的信息查询失败：${formatError(instrumentResult.reason)}`);
  }
  if (quoteResult.status === "rejected") {
    errors.push(`行情查询失败：${formatError(quoteResult.reason)}`);
  }

  const payload: LookupPayload = {
    errors,
    instrument,
    quote,
    symbol,
  };

  return NextResponse.json(payload, {
    status: instrument || quote ? 200 : 502,
  });
}
