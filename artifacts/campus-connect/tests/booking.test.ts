/// <reference types="node" />
/**
 * Booking retries across lost responses, edited details and an app relaunch.
 * The fake server follows api.py's booking rules for one student token.
 */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { ApiError, BookingPayload, Rider, samePayload } from '../src/api';
import { BookingStore, submitBooking } from '../src/booking';

const A: BookingPayload = { name: 'Sara K', classEnd: '16:00', stop: 'Dabouq', woman: true, womenOnly: true };
const B: BookingPayload = { name: 'Sara K', classEnd: '16:10', stop: 'Khalda', woman: true, womenOnly: false };

/** One student token on the server: books once, returns the same rider for the same details. */
function fakeServer() {
  const state = { saved: null as BookingPayload | null, riders: 0, nextId: 41 };
  const rider = (payload: BookingPayload): Rider => ({
    id: state.nextId,
    name: payload.name,
    status: 'waiting',
    batchId: 'b1',
    tripDate: '2026-11-28',
    timezone: 'Asia/Amman',
    matched: false,
    request: { classEnd: payload.classEnd, stop: payload.stop, woman: payload.woman, womenOnly: payload.womenOnly },
    soloFare: { fils: 4500, currency: 'JOD' },
    plan: null,
  });
  const book = (payload: BookingPayload): Rider => {
    if (state.saved) {
      if (!samePayload(state.saved, payload)) throw new ApiError('request_conflict', 'different details', 409);
      return rider(state.saved);
    }
    state.saved = payload;
    state.riders += 1;
    return rider(payload);
  };
  return { state, book };
}

/** Device storage that survives a relaunch, and a store view as the app builds it on each launch. */
function device() {
  const disk = { sentPayload: null as BookingPayload | null, riderId: null as number | null };
  const launch = (): BookingStore => ({
    sentPayload: disk.sentPayload,
    setSentPayload: async (payload) => {
      disk.sentPayload = payload;
    },
    setRider: async (riderId) => {
      disk.riderId = riderId;
      disk.sentPayload = null;
    },
  });
  return { disk, launch };
}

type Network = 'down' | 'up' | 'lose-response';

function transport(server: ReturnType<typeof fakeServer>, mode: () => Network) {
  const sent: BookingPayload[] = [];
  const book = async (payload: BookingPayload): Promise<Rider> => {
    sent.push(payload);
    const m = mode();
    if (m === 'down') throw new ApiError('offline', 'offline', 0);
    const result = server.book(payload);
    if (m === 'lose-response') throw new ApiError('timeout', 'timeout', 0);
    return result;
  };
  return { sent, book };
}

test('edited details after an offline attempt resend the first details, and recovery after relaunch returns the original rider', async () => {
  const server = fakeServer();
  const phone = device();
  let network: Network = 'down';
  const net = transport(server, () => network);

  // 1. Details A while offline: never reaches the server, kept as unresolved.
  let result = await submitBooking(phone.launch(), A, net.book);
  assert.equal(result.ok, false);
  assert.deepEqual(phone.disk.sentPayload, A);

  // 2. The student edits to B and submits; the server saves what was sent, but the response is lost.
  network = 'lose-response';
  result = await submitBooking(phone.launch(), B, net.book);
  assert.equal(result.ok, false);
  assert.deepEqual(net.sent[1], A, 'unresolved details A are resent instead of B');
  assert.deepEqual(server.state.saved, A);
  assert.deepEqual(phone.disk.sentPayload, A);

  // 3. Relaunch with a working network: the retry resolves to the same rider, with no duplicate.
  network = 'up';
  result = await submitBooking(phone.launch(), A, net.book);
  assert.equal(result.ok, true);
  assert.equal(phone.disk.riderId, 41);
  assert.equal(phone.disk.sentPayload, null);
  assert.equal(server.state.riders, 1);
});

test('a definite rejection clears the unresolved details so the student can change them', async () => {
  const phone = device();
  const reject = async (): Promise<Rider> => {
    throw new ApiError('duplicate_name', 'taken', 409);
  };
  const result = await submitBooking(phone.launch(), A, reject);
  assert.equal(result.ok, false);
  if (!result.ok) assert.equal(result.unresolved, false);
  assert.equal(phone.disk.sentPayload, null);

  const server = fakeServer();
  const ok = await submitBooking(phone.launch(), B, transport(server, () => 'up').book);
  assert.equal(ok.ok, true);
  assert.deepEqual(server.state.saved, B);
});

test('a lost response on the first attempt is retried with the same details and books once', async () => {
  const server = fakeServer();
  const phone = device();
  let network: Network = 'lose-response';
  const net = transport(server, () => network);
  await submitBooking(phone.launch(), A, net.book);
  network = 'up';
  const result = await submitBooking(phone.launch(), A, net.book);
  assert.equal(result.ok, true);
  assert.equal(server.state.riders, 1);
});

test('a server error after the booking was saved keeps the details, so the retry finds the same rider', async () => {
  const server = fakeServer();
  const phone = device();
  let failAfterSave = true;
  const book = async (payload: BookingPayload): Promise<Rider> => {
    const saved = server.book(payload);
    if (failAfterSave) throw new ApiError('server_error', 'Bad gateway', 502);
    return saved;
  };
  const first = await submitBooking(phone.launch(), A, book);
  assert.equal(first.ok, false);
  if (!first.ok) assert.equal(first.unresolved, true);
  assert.deepEqual(phone.disk.sentPayload, A);

  failAfterSave = false;
  const retry = await submitBooking(phone.launch(), B, book); // edited form is ignored until resolved
  assert.equal(retry.ok, true);
  assert.equal(phone.disk.riderId, 41);
  assert.equal(server.state.riders, 1);
});

test('a relaunch with no drop-off data can still resend the stored booking', async () => {
  // The Book screen allows sending whenever stored details exist; booking needs nothing from /stops.
  const server = fakeServer();
  const phone = device();
  phone.disk.sentPayload = A;
  const empty: BookingPayload = { name: '', classEnd: '16:00', stop: '', woman: false, womenOnly: false };
  const result = await submitBooking(phone.launch(), empty, transport(server, () => 'up').book);
  assert.equal(result.ok, true);
  assert.deepEqual(server.state.saved, A);
});
