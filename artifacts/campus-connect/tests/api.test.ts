/// <reference types="node" />
/** The request deadline must also cover reading the response body. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { api, ApiError, setRequestTimeout } from '../src/api';

test('headers arrive but the body stalls: the request times out', async () => {
  setRequestTimeout(50);
  const realFetch = globalThis.fetch;
  globalThis.fetch = (async (_url: unknown, init?: { signal?: AbortSignal }) => ({
    ok: true,
    status: 200,
    text: () =>
      new Promise<string>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new Error('aborted')));
      }),
  })) as unknown as typeof fetch;
  try {
    await assert.rejects(api.health('https://example.test'), (e: unknown) => e instanceof ApiError && e.code === 'timeout');
  } finally {
    globalThis.fetch = realFetch;
    setRequestTimeout(15000);
  }
});

test('an error body is parsed into its stable code', async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = (async () => ({
    ok: false,
    status: 409,
    text: async () => JSON.stringify({ error: { code: 'plan_changed', message: 'changed' }, rider: { id: 1 } }),
  })) as unknown as typeof fetch;
  try {
    await assert.rejects(api.confirm('https://example.test', 't', 1, 'sig'), (e: unknown) => e instanceof ApiError && e.code === 'plan_changed' && e.status === 409);
  } finally {
    globalThis.fetch = realFetch;
  }
});
