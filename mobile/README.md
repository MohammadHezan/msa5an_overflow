# Campus Connect student app moved

The existing Expo app now lives in [`artifacts/campus-connect/`](../artifacts/campus-connect/).
Its screens, assets, session handling and regression tests moved together; there is no second app to maintain here.

**On Replit:** click **Run**, select **Campus Connect**, then scan the **Expo Go** QR code from the preview's URL-bar menu. No local Metro server or `.env` setup is needed.

See the [student app README](../artifacts/campus-connect/README.md) for backend configuration, troubleshooting, optional local development and test commands.

## Repeatable regression checks

From the repository root, install the Python dependencies in `requirements.txt`
and run `pnpm install --frozen-lockfile` once. Then run:

```sh
pnpm --dir artifacts/campus-connect typecheck
pnpm --dir artifacts/campus-connect test
pnpm --dir artifacts/campus-connect test:api
```

The registered validation steps remain `mobile-typecheck`, `mobile-unit`, and
`mobile-api`, alongside the backend `test` step. No phone, Expo server, preview,
join code, or `EXPO_PUBLIC_API_URL` setting is needed for these checks.

`test:api` runs `scripts/check_mobile_api.py`, which starts Flask on a free
loopback port with a temporary SQLite database and runs
`artifacts/campus-connect/tests/integration/api-flow.test.ts` through the real
`src/api.ts` client. Only batch creation and operator matching use direct HTTP setup calls.
It covers health, join, stops, booking retries without duplicates, conflicting
requests, matching, stale confirms, updated plans, confirm/decline/reconfirm,
invalid codes and offline failures. The runner removes its temporary database
and shuts down its server even on failure; it never uses the running demo's database.
