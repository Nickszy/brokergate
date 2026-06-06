import { NextResponse } from "next/server";

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

export async function proxyOrderPayload(body: unknown, path: string) {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  const apiKey = process.env.BROKERGATE_API_KEY;
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  let lastNetworkError: unknown;

  for (const baseUrl of fallbackUrls()) {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 30000);
      try {
        const response = await fetch(`${baseUrl}${path}`, {
          body: JSON.stringify(body),
          cache: "no-store",
          headers,
          method: "POST",
          signal: controller.signal,
        });
        const text = await response.text();
        let payload: unknown = {};
        try {
          payload = text ? (JSON.parse(text) as unknown) : {};
        } catch {
          payload = { error: text || response.statusText };
        }

        return NextResponse.json(payload, { status: response.status });
      } catch (error) {
        lastNetworkError = error;
        await new Promise((resolve) => setTimeout(resolve, 180));
      } finally {
        clearTimeout(timeout);
      }
    }
  }

  return NextResponse.json(
    { error: `BrokerGate API 网络错误：${formatError(lastNetworkError)}` },
    { status: 502 },
  );
}

export async function proxyOrderRequest(request: Request, path: string) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "请求体必须是 JSON" }, { status: 400 });
  }

  return proxyOrderPayload(body, path);
}
