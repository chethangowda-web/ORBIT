/**
 * Selectable IANA zones. Browsers list canonical names (for example Asia/Calcutta), so a
 * stored value such as Asia/Kolkata may be missing from the list. The current value is
 * always included, otherwise a <select> would silently display the first option instead.
 */
export function timezoneOptions(current?: string): string[] {
  let zones: string[];
  try {
    zones = (Intl as unknown as { supportedValuesOf: (key: string) => string[] }).supportedValuesOf("timeZone");
  } catch {
    zones = ["UTC", "Asia/Kolkata", "Europe/London", "America/New_York", "America/Los_Angeles"];
  }
  const set = new Set(zones);
  if (current) set.add(current);
  set.add("UTC");
  return Array.from(set).sort();
}
