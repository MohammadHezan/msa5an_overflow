/**
 * Client for the Yalla Ride /api/v1 backend (see api.py and document.md "As built (B1)").
 * Every failure becomes an ApiError with a stable `code`, including `offline` and `timeout`
 * for requests that never got a response.
 */

let requestTimeoutMs = 15000;

/** Change the per-request deadline (headers and body). Used by tests. */
export function setRequestTimeout(ms: number): void {
  requestTimeoutMs = ms;
}

export type Money = { fils: number; currency: 'JOD' };

export type RiderStatus =
  | 'waiting'
  | 'review'
  | 'no_match'
  | 'confirmed'
  | 'solo_confirmed'
  | 'changed'
  | 'declined';

export type DropOff = { order: number; stop: string; rider: string; you: boolean };

export type Plan = {
  shared: boolean;
  womenOnly: boolean;
  corridor: string;
  gate: string;
  pickupTime: string;
  pickupAt: string;
  riders: string[];
  dropOffs: DropOff[];
  share: Money;
  soloFare: Money;
  saving: Money;
  signature: string;
};

export type Rider = {
  id: number;
  name: string;
  status: RiderStatus;
  batchId: string;
  tripDate: string;
  timezone: string;
  matched: boolean;
  request: { classEnd: string; stop: string; woman: boolean; womenOnly: boolean };
  soloFare: Money;
  plan: Plan | null;
};

export type Stop = { name: string; km: number; soloFare: Money; sampleShare: Money };
export type Corridor = { name: string; gate: string; stops: Stop[] };
export type StopsResponse = {
  currency: 'JOD';
  corridors: Corridor[];
  rules: {
    seatsPerCar: number;
    maxClassEndGapMinutes: number;
    walkToGateMinutes: number;
    classEndEarliest: string;
    classEndLatest: string;
    sampleShareRiders: number;
  };
};

export type JoinResponse = {
  token: string;
  tokenType: 'Bearer';
  batchId: string;
  tripDate: string;
  timezone: string;
  matched: boolean;
};

export type BookingPayload = {
  name: string;
  classEnd: string;
  stop: string;
  woman: boolean;
  womenOnly: boolean;
};

export class ApiError extends Error {
  code: string;
  status: number;
  body: unknown;

  constructor(code: string, message: string, status: number, body: unknown = null) {
    super(message);
    this.code = code;
    this.status = status;
    this.body = body;
  }

  /** True when the request may not have reached the server, so the same request can be retried. */
  get isNetwork(): boolean {
    return this.code === 'offline' || this.code === 'timeout';
  }
}

/** Explicit origin wins; Replit's managed preview supplies the backend domain. */
export function configuredApiUrl(): string | null {
  const raw = (process.env.EXPO_PUBLIC_API_URL ?? '').trim().replace(/\/+$/, '');
  if (raw) return raw;
  const domain = (process.env.EXPO_PUBLIC_DOMAIN ?? '').trim();
  return domain ? `https://${domain}` : null;
}

type RequestOptions = { method?: 'GET' | 'POST'; token?: string | null; body?: unknown };

async function request<T>(apiUrl: string, path: string, options: RequestOptions = {}): Promise<{ status: number; data: T }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (options.token) headers.Authorization = `Bearer ${options.token}`;

  const networkError = () => {
    const timedOut = controller.signal.aborted;
    return new ApiError(
      timedOut ? 'timeout' : 'offline',
      timedOut
        ? 'The server is taking too long to answer. Check your connection and try again.'
        : "Can't reach Yalla Ride. Check your connection and try again.",
      0,
    );
  };

  // The deadline covers both the headers and the body, so a stalled body still times out.
  let response: Response;
  let data: unknown = null;
  try {
    response = await fetch(`${apiUrl}/api/v1${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });
    const raw = await response.text();
    try {
      data = raw ? JSON.parse(raw) : null;
    } catch {
      data = null;
    }
  } catch {
    throw networkError();
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    const error = (data as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiError(
      error?.code ?? (response.status >= 500 ? 'server_error' : 'http_error'),
      error?.message ?? `The server answered with status ${response.status}.`,
      response.status,
      data,
    );
  }
  return { status: response.status, data: data as T };
}

export const api = {
  health: (apiUrl: string) => request<{ status: string; time: string }>(apiUrl, '/health').then((r) => r.data),

  join: (apiUrl: string, joinCode: string) =>
    request<JoinResponse>(apiUrl, '/demo-sessions/join', { method: 'POST', body: { joinCode } }).then((r) => r.data),

  stops: (apiUrl: string) => request<StopsResponse>(apiUrl, '/stops').then((r) => r.data),

  book: (apiUrl: string, token: string, batchId: string, payload: BookingPayload, clientRequestId: string) =>
    request<Rider>(apiUrl, `/batches/${encodeURIComponent(batchId)}/riders`, {
      method: 'POST',
      token,
      body: { ...payload, clientRequestId },
    }).then((r) => r.data),

  rider: (apiUrl: string, token: string, riderId: number) =>
    request<Rider>(apiUrl, `/riders/${riderId}`, { token }).then((r) => r.data),

  confirm: (apiUrl: string, token: string, riderId: number, signature: string) =>
    request<Rider>(apiUrl, `/riders/${riderId}/confirm`, { method: 'POST', token, body: { signature } }).then((r) => r.data),

  decline: (apiUrl: string, token: string, riderId: number) =>
    request<Rider>(apiUrl, `/riders/${riderId}/decline`, { method: 'POST', token, body: {} }).then((r) => r.data),
};

/**
 * True when this phone's session can no longer reach its rider: the token is unknown or expired
 * (`unauthorized`, which is also what a deleted batch returns), belongs to someone else
 * (`forbidden`), or points at something that is gone (`not_found`). The phone then offers
 * "Join with a new code" instead of retrying.
 */
export function isSessionLost(error: unknown): boolean {
  return error instanceof ApiError && (error.code === 'unauthorized' || error.code === 'forbidden' || error.code === 'not_found');
}

/** The current plan the server sent with a 409 plan_changed, if any. */
export function riderFromPlanChanged(error: unknown): Rider | null {
  if (error instanceof ApiError && error.code === 'plan_changed') {
    const rider = (error.body as { rider?: Rider } | null)?.rider;
    return rider ?? null;
  }
  return null;
}

export function formatJod(money: Money | null | undefined): string {
  if (!money) return '—';
  return `JOD ${(money.fils / 1000).toFixed(2)}`;
}

/** A clientRequestId the API accepts: 8–64 letters, digits, `-` or `_`. Not security-sensitive. */
export function newClientRequestId(): string {
  const random = Array.from({ length: 16 }, () => Math.floor(Math.random() * 36).toString(36)).join('');
  return `cc-${Date.now().toString(36)}-${random}`;
}

export function samePayload(a: BookingPayload, b: BookingPayload): boolean {
  return (
    a.name.trim().replace(/\s+/g, ' ') === b.name.trim().replace(/\s+/g, ' ') &&
    a.classEnd === b.classEnd &&
    a.stop === b.stop &&
    a.woman === b.woman &&
    a.womenOnly === b.womenOnly
  );
}
