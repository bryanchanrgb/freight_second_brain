/** Map raw API / agent errors to short, actionable desk messages. */
export function friendlyDeskError(raw: string): string {
  const text = raw.trim();
  const lower = text.toLowerCase();

  if (!text) return "Something went wrong. Try again or reset the session.";

  if (lower.includes("recursion limit") || lower.includes("maximum of") && lower.includes("steps")) {
    return "The agent hit its step limit. Try a narrower question.";
  }
  if (lower.includes("oilprice_api_token") || (lower.includes("oilprice") && lower.includes("token"))) {
    return "OilPriceAPI token is not set. Add OILPRICE_API_TOKEN to .env for dated prints.";
  }
  if (lower.includes("empty_window")) {
    return "No price history for that window. Baltic series on this feed start in 2026.";
  }
  if (lower.includes("openrouter") && (lower.includes("key") || text.includes("401") || text.includes("403"))) {
    return "OpenRouter API key missing or invalid. Check OPENROUTER_API_KEY in .env.";
  }
  if (lower.includes("unknown session")) {
    return "Session expired. Refresh the page to start again.";
  }
  if (lower.includes("unauthorized") || lower.includes('"auth":"required"') || lower.includes('"auth": "required"')) {
    return "This desk is locked. Enter the access token to continue.";
  }
  if (lower === "internal server error" || text.startsWith("500")) {
    return "Server error. Check the terminal running freight-sb ui for details.";
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
