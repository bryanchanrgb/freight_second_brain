/** Map raw API / agent errors to short, identifiable desk messages. */
export function friendlyDeskError(raw: string): string {
  const text = raw.trim();
  const lower = text.toLowerCase();

  if (!text) return "Something went wrong. Try again.";

  if (lower.includes("recursion limit") || (lower.includes("maximum of") && lower.includes("steps"))) {
    return "Step limit: the search stopped after too many steps. Try a narrower question.";
  }
  if (lower.includes("oilprice_api_token") || (lower.includes("oilprice") && lower.includes("token"))) {
    return "Market data unavailable: OilPriceAPI is not configured. Dated Baltic prints need a token.";
  }
  if (lower.includes("empty_window")) {
    return "No price history for that window. Baltic series on this feed start in 2026.";
  }
  if (lower.includes("openrouter") && (lower.includes("key") || text.includes("401") || text.includes("403"))) {
    return "Language model unavailable: the OpenRouter key is missing or invalid.";
  }
  if (lower.includes("unknown session")) {
    return "Session expired. Refresh the page to start again.";
  }
  if (lower.includes("unauthorized") || lower.includes('"auth":"required"') || lower.includes('"auth": "required"')) {
    return "This desk is private. Enter the password to continue.";
  }
  if (lower === "internal server error" || text.startsWith("500") || lower.includes("internal server error")) {
    return "Server error: the desk failed on that request. Try again.";
  }

  try {
    const parsed = JSON.parse(text) as { detail?: string; message?: string };
    const detail = parsed.detail || parsed.message;
    if (detail && detail !== text) return friendlyDeskError(detail);
  } catch {
    /* not JSON */
  }

  return text;
}
