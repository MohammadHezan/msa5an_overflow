/// <reference types="node" />
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { parseJoinLink } from '../src/joinLink';

test('valid custom scheme', () => {
  assert.equal(parseJoinLink('campus-connect://join?code=ABC123'), 'ABC123');
});
test('lowercase code is normalized', () => {
  assert.equal(parseJoinLink('campus-connect://join?code=abc123'), 'ABC123');
});
test('HTTPS join path', () => {
  assert.equal(parseJoinLink('https://example.test/join?code=ABC123'), 'ABC123');
});
test('wrong path or scheme', () => {
  assert.equal(parseJoinLink('campus-connect://book?code=ABC123'), null);
  assert.equal(parseJoinLink('campus-connect://join/other?code=ABC123'), null);
  assert.equal(parseJoinLink('https://example.test/book?code=ABC123'), null);
  assert.equal(parseJoinLink('http://example.test/join?code=ABC123'), null);
});
test('invalid or ambiguous code', () => {
  assert.equal(parseJoinLink('campus-connect://join?code=ABC12'), null);
  assert.equal(parseJoinLink('campus-connect://join?code=ABC1234'), null);
  assert.equal(parseJoinLink('campus-connect://join?code=ABC-12'), null);
  assert.equal(parseJoinLink('campus-connect://join?code=ABC123&code=DEF456'), null);
  assert.equal(parseJoinLink('campus-connect://join?other=ABC123'), null);
});
test('garbage string', () => {
  assert.equal(parseJoinLink('not a URL'), null);
});
