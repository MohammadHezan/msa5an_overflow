/** The join code in a scanned QR link (campus-connect://join?code=ABC123 or https://…/join?code=…), or null. */
export function parseJoinLink(url: string): string | null {
  // Normalize the custom scheme first: URL only parses hosts reliably for http(s).
  const normalized = url.replace(/^campus-connect:\/\/join(?=\?)/, 'https://join.invalid/join');
  if (!/^https:\/\/[^/?#\s]+\/join\?/.test(normalized)) return null;
  try {
    const parsed = new URL(normalized);
    if (parsed.pathname !== '/join') return null;
    const codes = parsed.searchParams.getAll('code');
    const code = codes[0];
    return codes.length === 1 && code?.length === 6 && /^[A-Za-z0-9]+$/.test(code) ? code.toUpperCase() : null;
  } catch {
    return null;
  }
}
