/**
 * Convert a snake_case / kebab-case enum value into Sentence case for display,
 * e.g. "home_contents" -> "Home contents", "income_protection" -> "Income protection".
 * Raw values stay untouched in the data layer - this is presentation only.
 */
export function formatLabel(value: string | null | undefined): string {
  if (!value) return '—'
  const words = String(value).replace(/[_-]+/g, ' ').trim().toLowerCase()
  if (!words) return '—'
  return words.charAt(0).toUpperCase() + words.slice(1)
}
