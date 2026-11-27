import assert from 'node:assert/strict';
import { test } from 'node:test';

import { ApiError } from '../src/api';
import { cleanCode, formatCountdown, looksLikeEmail, needsNewCode, secondsUntil, verificationErrorTitle } from '../src/verification';

test('countdowns use whole seconds and stop at zero', () => {
  const now = Date.parse('2026-11-27T10:00:00+02:00');
  assert.equal(secondsUntil('2026-11-27T10:04:32+02:00', now), 272);
  assert.equal(secondsUntil('2026-11-27T08:04:31.200Z', now), 272, 'offsets are respected and partial seconds round up');
  assert.equal(secondsUntil('2026-11-27T09:59:00+02:00', now), 0);
  assert.equal(secondsUntil('not a date', now), 0);
  assert.equal(formatCountdown(272), '04:32');
  assert.equal(formatCountdown(0), '00:00');
  assert.equal(formatCountdown(-5), '00:00');
});

test('code and email input are cleaned before sending', () => {
  assert.equal(cleanCode(' 12-34 567 '), '123456');
  assert.equal(looksLikeEmail(' sara.a@bau.edu.jo '), true);
  assert.equal(looksLikeEmail('sara@bau'), false);
  assert.equal(looksLikeEmail('sara bau.edu.jo'), false);
});

test('verification errors get plain titles and say when a new code is needed', () => {
  const error = (code: string) => new ApiError(code, 'm', 400);
  assert.equal(verificationErrorTitle(error('verification_code_invalid')), 'That code is incorrect');
  assert.equal(verificationErrorTitle(error('email_not_university')), 'Use your university email');
  assert.equal(verificationErrorTitle(error('something_else')), "Couldn't verify");
  assert.equal(needsNewCode(error('verification_code_expired')), true);
  assert.equal(needsNewCode(error('verification_locked')), true);
  assert.equal(needsNewCode(error('verification_code_invalid')), false);
});
