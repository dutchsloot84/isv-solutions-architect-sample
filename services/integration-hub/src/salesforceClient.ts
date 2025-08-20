import fetch from "node-fetch";
import { SALESFORCE_BASE_URL } from "./config";

export async function upsert(order: any, correlationId?: string) {
  const res = await fetch(`${SALESFORCE_BASE_URL}/upsert`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Correlation-ID": correlationId || "",
    },
    body: JSON.stringify(order),
  });
  if (!res.ok) {
    throw new Error("salesforce error");
  }
  return res.json();
}
