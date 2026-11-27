import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { configuredApiUrl } from '../src/api';

const originalApi = process.env.EXPO_PUBLIC_API_URL;
const originalDomain = process.env.EXPO_PUBLIC_DOMAIN;

afterEach(() => {
  if (originalApi === undefined) delete process.env.EXPO_PUBLIC_API_URL;
  else process.env.EXPO_PUBLIC_API_URL = originalApi;
  if (originalDomain === undefined) delete process.env.EXPO_PUBLIC_DOMAIN;
  else process.env.EXPO_PUBLIC_DOMAIN = originalDomain;
});

test('Replit preview automatically uses the public backend HTTPS origin', () => {
  delete process.env.EXPO_PUBLIC_API_URL;
  process.env.EXPO_PUBLIC_DOMAIN = 'campus.example.test';
  assert.equal(configuredApiUrl(), 'https://campus.example.test');
});

test('an explicit backend origin overrides the Replit preview', () => {
  process.env.EXPO_PUBLIC_API_URL = ' https://backend.example.test/// ';
  process.env.EXPO_PUBLIC_DOMAIN = 'campus.example.test';
  assert.equal(configuredApiUrl(), 'https://backend.example.test');
});

test('local use without configuration remains explicitly unconfigured', () => {
  delete process.env.EXPO_PUBLIC_API_URL;
  delete process.env.EXPO_PUBLIC_DOMAIN;
  assert.equal(configuredApiUrl(), null);
});
