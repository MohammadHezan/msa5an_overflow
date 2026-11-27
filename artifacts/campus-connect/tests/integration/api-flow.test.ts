/// <reference types="node" />
/** Real HTTP contract check: only operator setup bypasses the phone client. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { api, ApiError, isSessionLost, onlyPreference, riderFromPlanChanged, type BookingPayload, type Rider } from '../../src/api';
import { isDefiniteRejection } from '../../src/booking';

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

/** Test-only hook served by scripts/check_mobile_api.py: deletes a batch as expiry cleanup would. */
async function deleteBatch(batchId: string): Promise<void> {
  const response = await fetch(`${origin}/__harness__/batches/${encodeURIComponent(batchId)}/delete`, {
    method: 'POST', signal: AbortSignal.timeout(15000),
  });
  assert.equal(response.status, 204, `Harness could not delete batch ${batchId}`);
}

/** Test-only hook served by scripts/check_mobile_api.py: marks a session as a verified student. */
/** The demo students who are women; everyone else gets a man's profile. Gender comes from the profile, never the form. */
const DEMO_WOMEN = new Set(['Sara', 'Rama', 'Huda', 'Lina', 'Noor']);

async function verifySession(token: string, firstName: string): Promise<void> {
  const gender = DEMO_WOMEN.has(firstName) ? 'woman' : 'man';
  const response = await fetch(`${origin}/__harness__/sessions/verify?firstName=${encodeURIComponent(firstName)}&gender=${gender}`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(15000),
  });
  assert.equal(response.status, 204, `Harness could not verify ${firstName}`);
}

/** A phone that joined the batch and finished student verification. */
async function verifiedJoin(joinCode: string, firstName: string) {
  const session = await api.join(origin, joinCode);
  await verifySession(session.token, firstName);
  return session;
}

/** The rejection a phone must treat as "this session is over, offer Join with a new code". */
function sessionLostWith(code: string, status: number) {
  return (error: unknown): boolean => {
    errorWith(code, status)(error);
    assert.equal(isSessionLost(error), true, `${code} must offer rejoin on the plan screen`);
    assert.equal(isDefiniteRejection(error as ApiError), true, `${code} proves a booking was not saved`);
    return true;
  };
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
  // Sent with the older woman/womenOnly flags: older app versions keep working.
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

  // Only a verified student may book; the rejection proves nothing was saved.
  await assert.rejects(api.book(origin, session.token, batch.id, payload, 'phone-sara-0001'), (error: unknown) => {
    errorWith('verification_required', 403)(error);
    assert.equal(isDefiniteRejection(error as ApiError), true, 'verification_required proves a booking was not saved');
    assert.equal(isSessionLost(error), false, 'An unverified phone should verify, not rejoin');
    return true;
  });
  await verifySession(session.token, 'Sara');

  const sara = await api.book(origin, session.token, batch.id, payload, 'phone-sara-0001');
  assert.equal(sara.status, 'waiting');
  assert.equal(sara.name, 'Sara');
  assert.equal(sara.plan, null);
  assert.equal(sara.batchId, batch.id);
  const retry = await api.book(origin, session.token, batch.id, payload, 'phone-sara-0001');
  assert.deepEqual(retry, sara);
  await assert.rejects(
    api.book(origin, session.token, batch.id, { ...payload, stop: 'Khalda' }, 'phone-sara-0001'),
    errorWith('request_conflict', 409),
  );

  const ramaSession = await verifiedJoin(batch.joinCode, 'Rama');
  const hudaSession = await verifiedJoin(batch.joinCode, 'Huda');
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

test('a phone cannot use a bad token or act for another rider', { timeout: 60000 }, async (t) => {
  const batch = await operator<{ id: string; joinCode: string; operatorToken: string }>(
    '/batches', { mode: 'empty' },
  );
  const base: BookingPayload = { name: 'Sara', classEnd: '16:00', stop: 'Dabouq', woman: true, womenOnly: true };
  const saraSession = await verifiedJoin(batch.joinCode, 'Sara');
  const ramaSession = await verifiedJoin(batch.joinCode, 'Rama');
  const sara = await api.book(origin, saraSession.token, batch.id, base, 'auth-sara-0001');
  const rama = await api.book(origin, ramaSession.token, batch.id, {
    ...base, name: 'Rama', stop: 'Al Bayader', classEnd: '15:55',
  }, 'auth-rama-0001');
  await api.book(origin, (await verifiedJoin(batch.joinCode, 'Huda')).token, batch.id, {
    ...base, name: 'Huda', stop: 'Wadi As-Seer',
  }, 'auth-huda-0001');
  assert.equal((await operator<{ ranNow: boolean }>(`/batches/${batch.id}/matching`, {}, batch.operatorToken)).ranNow, true);
  const ramaBefore = await api.rider(origin, ramaSession.token, rama.id);
  assert.equal(ramaBefore.status, 'review');
  assert.ok(ramaBefore.plan);
  const riders = async () => (await operator<{ riders: { id: number; status: string }[] }>(
    `/batches/${batch.id}`, undefined, batch.operatorToken,
  )).riders.map(({ id, status }) => ({ id, status }));
  const before = await riders();

  // An unknown, empty or operator-only token is rejected without touching anyone.
  for (const token of ['not-a-token', '', batch.operatorToken.slice(0, -2) + 'xx']) {
    await assert.rejects(api.rider(origin, token, sara.id), sessionLostWith('unauthorized', 401));
    await assert.rejects(api.confirm(origin, token, sara.id, ramaBefore.plan.signature), sessionLostWith('unauthorized', 401));
    await assert.rejects(api.decline(origin, token, sara.id), sessionLostWith('unauthorized', 401));
    await assert.rejects(
      api.book(origin, token, batch.id, { ...base, name: 'Intruder' }, 'auth-intruder-0001'),
      sessionLostWith('unauthorized', 401),
    );
  }
  t.diagnostic('Invalid, empty and tampered tokens return unauthorized 401 and offer rejoin');

  // Sara's valid session must not read, confirm or decline Rama, even with Rama's real signature.
  await assert.rejects(api.rider(origin, saraSession.token, rama.id), sessionLostWith('forbidden', 403));
  await assert.rejects(
    api.confirm(origin, saraSession.token, rama.id, ramaBefore.plan.signature),
    (error: unknown) => {
      sessionLostWith('forbidden', 403)(error);
      assert.equal(riderFromPlanChanged(error), null, 'A forbidden answer must not leak the other rider');
      assert.equal(JSON.stringify((error as ApiError).body).includes('Al Bayader'), false);
      return true;
    },
  );
  await assert.rejects(api.decline(origin, saraSession.token, rama.id), sessionLostWith('forbidden', 403));
  // Nor can it book into a batch it did not join.
  await assert.rejects(
    api.book(origin, saraSession.token, 'another-batch', base, 'auth-sara-0001'),
    sessionLostWith('forbidden', 403),
  );
  assert.deepEqual(await riders(), before, 'Rejected requests must not create or change any rider');
  assert.deepEqual(await api.rider(origin, ramaSession.token, rama.id), ramaBefore, "Rama's plan is untouched");
  const saraNow: Rider = await api.rider(origin, saraSession.token, sara.id);
  assert.equal(saraNow.status, 'review', "Sara's own rider is untouched too");
  t.diagnostic('Another student cannot read, confirm or decline a rider; nothing changed');

  // Each phone can still act for its own rider afterwards.
  assert.equal((await api.confirm(origin, ramaSession.token, rama.id, ramaBefore.plan.signature)).status, 'confirmed');
});

test('a session whose batch was deleted is told to rejoin', { timeout: 60000 }, async (t) => {
  const batch = await operator<{ id: string; joinCode: string; operatorToken: string }>(
    '/batches', { mode: 'empty' },
  );
  const booked = await verifiedJoin(batch.joinCode, 'Lina');
  const unbooked = await verifiedJoin(batch.joinCode, 'Noor');
  const payload: BookingPayload = { name: 'Lina', classEnd: '16:00', stop: 'Dabouq', woman: true, womenOnly: false };
  const lina = await api.book(origin, booked.token, batch.id, payload, 'gone-lina-0001');
  assert.equal((await api.rider(origin, booked.token, lina.id)).status, 'waiting');

  await deleteBatch(batch.id);

  await assert.rejects(api.rider(origin, booked.token, lina.id), sessionLostWith('unauthorized', 401));
  await assert.rejects(api.confirm(origin, booked.token, lina.id, 'any-signature'), sessionLostWith('unauthorized', 401));
  await assert.rejects(api.decline(origin, booked.token, lina.id), sessionLostWith('unauthorized', 401));
  // A retry of the original booking and a first booking both fail definitely, so the phone rejoins.
  await assert.rejects(api.book(origin, booked.token, batch.id, payload, 'gone-lina-0001'), sessionLostWith('unauthorized', 401));
  await assert.rejects(
    api.book(origin, unbooked.token, batch.id, { ...payload, name: 'Noor' }, 'gone-noor-0001'),
    sessionLostWith('unauthorized', 401),
  );
  await assert.rejects(api.join(origin, batch.joinCode), errorWith('join_code_invalid', 404));
  t.diagnostic('Deleted batch: read, confirm, decline and book return unauthorized 401 and offer rejoin');

  // Other batches keep working after the deletion.
  const fresh = await operator<{ id: string; joinCode: string }>('/batches', { mode: 'empty' });
  const again = await verifiedJoin(fresh.joinCode, 'Lina');
  assert.equal((await api.book(origin, again.token, fresh.id, payload, 'gone-lina-0002')).status, 'waiting');
});

test('a phone searches campuses, verifies a university email and asks about unavailable campuses', { timeout: 60000 }, async (t) => {
  const batch = await operator<{ id: string; joinCode: string }>('/batches', { mode: 'empty' });
  const joined = await api.join(origin, batch.joinCode);
  assert.equal(joined.verified, false);
  assert.equal(joined.student, null);

  const all = await api.universities(origin, joined.token);
  assert.deepEqual(all.map((u) => [u.name, u.available]), [
    ['Al-Balqa Applied University', true],
    ['University of Jordan', false],
    ['Yarmouk University', false],
  ]);
  const irbid = await api.universities(origin, joined.token, 'irbid');
  assert.deepEqual(irbid.map((u) => u.name), ['Yarmouk University']);
  assert.deepEqual(await api.universities(origin, joined.token, 'nowhere'), []);
  const [balqa, jordan] = all;

  // Unavailable campus: no code, but a notify-me request with the toast text.
  await assert.rejects(api.startVerification(origin, joined.token, jordan.id, 'sara@ju.edu.jo'), errorWith('campus_unavailable', 409));
  const notified = await api.notifyUniversity(origin, joined.token, jordan.id);
  assert.equal(notified.notificationRequested, true);
  assert.equal(notified.message, "We'll keep you posted");
  assert.deepEqual(await api.notifyUniversity(origin, joined.token, jordan.id), notified, 'Notify me is idempotent');
  await assert.rejects(api.notifyUniversity(origin, joined.token, balqa.id), errorWith('campus_available', 409));
  t.diagnostic('Search, availability and notify-me passed');

  await assert.rejects(api.startVerification(origin, joined.token, balqa.id, 'sara@gmail.com'), errorWith('email_not_university', 400));
  await assert.rejects(api.resendVerification(origin, joined.token), errorWith('verification_not_started', 409));
  const started = await api.startVerification(origin, joined.token, balqa.id, 'sara.a@bau.edu.jo');
  assert.ok(!('alreadyVerified' in started));
  assert.equal(started.maskedEmail, 's***@bau.edu.jo');
  assert.equal(started.delivery, 'console_demo');
  assert.ok(Date.parse(started.expiresAt) > Date.parse(started.resendAvailableAt));
  await assert.rejects(api.resendVerification(origin, joined.token), errorWith('verification_resend_too_soon', 429));
  await assert.rejects(api.confirmVerification(origin, joined.token, '000000'), errorWith('verification_code_invalid', 400));
  assert.equal((await api.me(origin, joined.token)).verified, false);

  const confirmed = await api.confirmVerification(origin, joined.token, '123456');
  assert.equal(confirmed.tokenType, 'Bearer');
  assert.equal(confirmed.student.firstName, 'Sara');
  assert.equal(confirmed.student.verified, true);
  assert.equal(confirmed.student.university.id, balqa.id);
  assert.ok(!JSON.stringify(confirmed).includes('sara.a@'), 'The verified profile never returns the email');
  const me = await api.me(origin, confirmed.token);
  assert.equal(me.verified, true);
  assert.equal(me.student?.firstName, 'Sara');

  const again = await api.startVerification(origin, confirmed.token, balqa.id, 'sara.a@bau.edu.jo');
  assert.ok('alreadyVerified' in again && again.alreadyVerified);
  t.diagnostic('Masked email, cooldown, wrong code, confirm and already-verified passed');
});

test('friends start and join a group, ride in one car, and men-only follows the profile', { timeout: 60000 }, async (t) => {
  const batch = await operator<{ id: string; joinCode: string; operatorToken: string }>('/batches', { mode: 'empty' });
  const omarSession = await verifiedJoin(batch.joinCode, 'Omar');
  const profile = (await api.me(origin, omarSession.token)).student;
  assert.equal(profile?.gender, 'man', 'The demo profile is a man');
  const only = onlyPreference(profile.gender);
  assert.equal(only, 'men');

  // A man may not ask for a women-only car.
  const base: BookingPayload = { name: 'Omar', classEnd: '16:00', stop: 'Dabouq', gender: profile.gender, preference: only };
  await assert.rejects(
    api.book(origin, omarSession.token, batch.id, { ...base, preference: 'women' }, 'friends-omar-0000'),
    (error: unknown) => errorWith('invalid_input', 400)(error) && isDefiniteRejection(error as ApiError),
  );

  const start: BookingPayload = { ...base, friends: { mode: 'start', open: true } };
  const omar = await api.book(origin, omarSession.token, batch.id, start, 'friends-omar-0001');
  const code = omar.request.friendGroup;
  assert.ok(code && /^GR-\d\d$/.test(code), `group code, got ${code}`);
  assert.equal(omar.request.preference, 'men');
  assert.equal(omar.request.groupOpen, true);
  assert.deepEqual(await api.book(origin, omarSession.token, batch.id, start, 'friends-omar-0001'), omar, 'retry returns the same rider');
  await assert.rejects(
    api.book(origin, omarSession.token, batch.id, { ...start, friends: { mode: 'start', open: false } }, 'friends-omar-0001'),
    errorWith('request_conflict', 409),
  );

  const join = (name: string, extra: Partial<BookingPayload> = {}, groupCode = code) =>
    verifiedJoin(batch.joinCode, name).then((s) =>
      api.book(origin, s.token, batch.id, { ...base, name, preference: 'mixed', friends: { mode: 'join', code: groupCode }, ...extra }, `friends-${name.toLowerCase()}-0001`),
    );
  await assert.rejects(join('Ali', {}, 'GR-00'), (error: unknown) => {
    errorWith('group_not_found', 404)(error);
    assert.equal(isSessionLost(error), false, 'An unknown group code is not a lost session');
    return isDefiniteRejection(error as ApiError);
  });
  await assert.rejects(join('Badr', { stop: 'Marka' }), (error: unknown) => errorWith('group_mismatch', 409)(error) && isDefiniteRejection(error as ApiError));
  await assert.rejects(join('Fadi', { classEnd: '16:30' }), errorWith('group_mismatch', 409));

  const zaid = await join('Zaid', { stop: 'Wadi As-Seer', classEnd: '16:05' });
  assert.equal(zaid.request.friendGroup, code);
  await join('Karim', { stop: 'Khalda' });
  await join('Majd', { stop: 'Al Bayader' });
  await assert.rejects(join('Rami'), (error: unknown) => errorWith('group_full', 409)(error) && isDefiniteRejection(error as ApiError));

  const matched = await operator<{ ranNow: boolean }>(`/batches/${batch.id}/matching`, {}, batch.operatorToken);
  assert.equal(matched.ranNow, true);
  const plan = (await api.rider(origin, omarSession.token, omar.id)).plan;
  assert.ok(plan?.shared);
  assert.deepEqual([...plan.riders].sort(), ['Karim', 'Majd', 'Zaid'], 'the whole group shares one car');
  assert.equal(plan.friendGroup, code);
  assert.equal(plan.only, 'men');
  assert.equal(plan.womenOnly, false);

  const late = await verifiedJoin(batch.joinCode, 'Tariq');
  // Brief 05: after matching, a new friends group waits in a lobby for its own car instead of being refused.
  const tariq = await api.book(origin, late.token, batch.id, { ...base, name: 'Tariq', friends: { mode: 'start', open: true } }, 'friends-tariq-0001');
  assert.equal(tariq.status, 'lobby');
  assert.equal(tariq.group?.status, 'lobby');
  t.diagnostic('Profile gender, men-only, start, join, retry, group errors, one car after matching and a late group lobby passed');
});
