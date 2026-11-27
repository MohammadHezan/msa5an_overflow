import { ApiError, BookingPayload, Rider } from './api';

/**
 * Booking with an uncertain outcome must be resolved before different details are sent.
 *
 * Every booking in a session uses the same clientRequestId. If a send gets no answer, the
 * server may or may not hold those details, so they are kept as `sentPayload` and every later
 * send repeats exactly them until the server gives a definite answer:
 * - success: the server returns the rider (the original one on a retry), and the phone stores its id;
 * - a definite rejection (invalid input, duplicate name, closed batch...): nothing was saved, so
 *   the student may edit and send different details.
 * Sending different details while one is unresolved could save the new details while the phone
 * still remembers the old ones, leaving no way back to the rider.
 */

/** Answers that prove these details were not saved. Anything else (5xx, gateway errors, unknown codes) may have committed. */
const DEFINITE_REJECTIONS = new Set([
  'invalid_input', 'duplicate_name', 'batch_matched', 'batch_full', 'already_booked', 'unauthorized', 'forbidden',
  'group_not_found', 'group_full', 'group_mismatch', 'group_placed',
]);

export function isDefiniteRejection(error: ApiError): boolean {
  return error.status >= 400 && error.status < 500 && DEFINITE_REJECTIONS.has(error.code);
}

export type BookingStore = {
  sentPayload: BookingPayload | null;
  setSentPayload: (payload: BookingPayload | null) => Promise<void>;
  setRider: (riderId: number) => Promise<void>;
};

export type BookingResult = { ok: true; rider: Rider } | { ok: false; error: ApiError; unresolved: boolean };

/** The details the next send must use: the unresolved ones if any, otherwise the form's. */
export function detailsToSend(sentPayload: BookingPayload | null, form: BookingPayload): BookingPayload {
  return sentPayload ?? form;
}

export async function submitBooking(
  store: BookingStore,
  form: BookingPayload,
  book: (payload: BookingPayload) => Promise<Rider>,
): Promise<BookingResult> {
  const details = detailsToSend(store.sentPayload, form);
  // Persist before sending so a crash or relaunch mid-request still knows what may be on the server.
  await store.setSentPayload(details);
  try {
    const rider = await book(details);
    await store.setRider(rider.id);
    return { ok: true, rider };
  } catch (e) {
    const error = e instanceof ApiError ? e : new ApiError('offline', String(e), 0);
    if (!isDefiniteRejection(error)) return { ok: false, error, unresolved: true };
    // A definite answer: these details were not saved, so the form is free to change.
    await store.setSentPayload(null);
    return { ok: false, error, unresolved: false };
  }
}
