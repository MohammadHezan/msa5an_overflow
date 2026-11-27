/// <reference types="node" />
/** Real HTTP contract check: only operator setup bypasses the phone client. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { api, ApiError, riderFromPlanChanged, type BookingPayload } from '../../src/api';

const [apiUrl, offlineUrl] = process.argv.slice(2);
assert.ok(apiUrl && offlineUrl, 'Run pnpm test:api to start the isolated Flask backend');
const origin: string = apiUrl;

async function operator<T>(path: string, body?: unknown, token?: string): Promise<T> {
  const response = await fetch(`${origin}/api/v1${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  });
  assert.ok(response.ok, `Operator ${path} returned ${response.status}`);
  return response.json() as Promise<T>;
}

function errorWith(code: string, status: number) {
  return (error: unknown): boolean => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.code, code);
    assert.equal(error.status, status);
    assert.equal(error.isNetwork, status === 0);
    return true;
  };
}

test('phone booking, matching, stale confirmation, decline and connection errors', { timeout: 60000 }, async (t) => {
  const batch = await operator<{ id: string; joinCode: string; operatorToken: string }>(
    '/batches', { mode: 'empty' },
  );
  const payload: BookingPayload = {
    name: 'Sara', classEnd: '16:00', stop: 'Dabouq', woman: true, womenOnly: true,
  };
  const session = await api.join(origin, batch.joinCode);
  assert.equal(session.batchId, batch.id);
  assert.equal(session.tokenType, 'Bearer');
  assert.equal(session.matched, false);
  assert.ok(session.token);
  assert.equal((await api.health(origin)).status, 'ok');
  const stops = await api.stops(origin);
  assert.equal(stops.currency, 'JOD');
  const dabouq = stops.corridors.flatMap((corridor) => corridor.stops).find((stop) => stop.name === payload.stop);
  assert.ok(dabouq);
  assert.equal(dabouq.soloFare.currency, 'JOD');
  assert.ok(Number.isInteger(dabouq.soloFare.fils) && dabouq.soloFare.fils > 0);

  const sara = await api.book(origin, session.token, batch.id, payload, 'phone-sara-0001');
  assert.equal(sara.status, 'waiting');
  assert.equal(sara.plan, null);
  assert.equal(sara.batchId, batch.id);
  const retry = await api.book(origin, session.token, batch.id, payload, 'phone-sara-0001');
  assert.deepEqual(retry, sara);
  await assert.rejects(
    api.book(origin, session.token, batch.id, { ...payload, stop: 'Khalda' }, 'phone-sara-0001'),
    errorWith('request_conflict', 409),
  );

  const ramaSession = await api.join(origin, batch.joinCode);
  const hudaSession = await api.join(origin, batch.joinCode);
  await api.book(origin, ramaSession.token, batch.id, {
    ...payload, name: 'Rama', stop: 'Al Bayader', classEnd: '15:55',
  }, 'phone-rama-0001');
  const huda = await api.book(origin, hudaSession.token, batch.id, {
    ...payload, name: 'Huda', stop: 'Wadi As-Seer',
  }, 'phone-huda-0001');
  const detail = await operator<{ riders: { id: number }[] }>(`/batches/${batch.id}`, undefined, batch.operatorToken);
  assert.equal(detail.riders.length, 3, 'Retry and conflict must not create extra riders');
  const matched = await operator<{ ranNow: boolean }>(`/batches/${batch.id}/matching`, {}, batch.operatorToken);
  assert.equal(matched.ranNow, true);
  const review = await api.rider(origin, session.token, sara.id);
  assert.equal(review.status, 'review');
  assert.equal(review.matched, true);
  assert.ok(review.plan?.shared);
  assert.deepEqual([...review.plan.riders].sort(), ['Huda', 'Rama']);
  assert.ok(review.plan.signature);

  await assert.rejects(api.confirm(origin, session.token, sara.id, 'stale-signature'), (error: unknown) => {
    errorWith('plan_changed', 409)(error);
    assert.deepEqual(riderFromPlanChanged(error), review, '409 must include the current rider and plan');
    return true;
  });
  const confirmed = await api.confirm(origin, session.token, sara.id, review.plan.signature);
  assert.equal(confirmed.status, 'confirmed');
  const declined = await api.decline(origin, hudaSession.token, huda.id);
  assert.equal(declined.status, 'declined');
  assert.equal(declined.plan, null);
  assert.deepEqual(await api.decline(origin, hudaSession.token, huda.id), declined);

  const changed = await api.rider(origin, session.token, sara.id);
  assert.equal(changed.status, 'changed');
  assert.ok(changed.plan);
  assert.deepEqual(changed.plan.riders, ['Rama']);
  assert.notEqual(changed.plan.signature, review.plan.signature);
  await assert.rejects(api.confirm(origin, session.token, sara.id, review.plan.signature), (error: unknown) => {
    errorWith('plan_changed', 409)(error);
    assert.deepEqual(riderFromPlanChanged(error), changed);
    return true;
  });
  assert.equal((await api.confirm(origin, session.token, sara.id, changed.plan.signature)).status, 'confirmed');
  t.diagnostic('Join, stops, idempotent booking, conflict, matching, stale confirm, confirm, changed and repeat decline passed');

  await assert.rejects(api.join(origin, 'NOPE99'), errorWith('join_code_invalid', 404));
  await assert.rejects(api.health(offlineUrl), errorWith('offline', 0));
  t.diagnostic('Invalid join code and real connection refusal passed');
});
