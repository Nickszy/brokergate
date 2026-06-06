import { NextResponse } from "next/server";
import { proxyOrderPayload } from "../_proxy";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "请求体必须是 JSON" }, { status: 400 });
  }

  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return NextResponse.json({ error: "请求体必须是对象" }, { status: 400 });
  }

  const payload = body as Record<string, unknown>;
  const draftId = String(payload.draft_id || "").trim();
  const confirmationText = String(payload.confirmation_text || "").trim();
  const confirmedBy = String(payload.confirmed_by || "web-user").trim();

  if (!draftId) {
    return NextResponse.json({ error: "缺少草稿 ID" }, { status: 400 });
  }

  if (!confirmationText) {
    return NextResponse.json({ error: "缺少确认口令" }, { status: 400 });
  }

  return proxyOrderPayload(
    {
      confirmation_text: confirmationText,
      confirmed_by: confirmedBy || "web-user",
    },
    `/v1/orders/${encodeURIComponent(draftId)}/confirm`,
  );
}
