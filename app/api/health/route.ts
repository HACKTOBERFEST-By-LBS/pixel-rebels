import { NextResponse } from "next/server";
export const runtime = "nodejs";
export async function GET() {
  return NextResponse.json({ status: "online", application: "Vioum", configured: Boolean(process.env.GEMINI_API_KEY), model: process.env.GEMINI_MODEL || "gemma-4-26b-a4b-it" });
}
