# BrokerGate Web

Next.js App Router dashboard for the BrokerGate multi-broker, multi-account asset cockpit.

## Local Development

```bash
npm install
npm run dev
```

The dashboard does not talk to broker APIs directly from the browser. The Next.js
server fetches BrokerGate Python API data and sends the normalized dashboard state
to the client.

Create `web/.env.local` for local API-backed data:

```env
BROKERGATE_API_BASE_URL=http://127.0.0.1:8000
BROKERGATE_API_KEY=change-me
BROKERGATE_WEB_ACCOUNTS=[{"broker":"tiger","account_id":"paper-account","display_name":"Tiger Paper"},{"broker":"longbridge","account_id":"paper-longbridge-account","display_name":"Longbridge Paper"}]
BROKERGATE_WEB_DISPLAY_CURRENCIES=USD,HKD,CNY
```

Use real broker account ids in `BROKERGATE_WEB_ACCOUNTS` after the Python API is
running with those broker credentials. Keep these variables server-side; do not
rename them to `NEXT_PUBLIC_*`.

Currency normalization is also done server-side. If `BROKERGATE_WEB_FX_RATES` is
not set, the Next.js server fetches Frankfurter/ECB reference rates and sends
only normalized dashboard values to the browser. For controlled environments,
set manual rates as JSON:

```env
BROKERGATE_WEB_FX_BASE=USD
BROKERGATE_WEB_FX_RATES={"USD":1,"HKD":7.8,"CNY":7.2}
```

## Vercel Deployment

The GitHub Actions workflow deploys this `web/` subdirectory with Vercel CLI.
If these secrets are not configured yet, the workflow skips the deploy step and
keeps the PR build check usable. Real preview and production deployments require
all three secrets below.

Required GitHub repository secrets:

- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

Where to get them:

1. `VERCEL_TOKEN`: open Vercel account settings, go to Tokens, create a token,
   then save it as a GitHub repository secret.
2. `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID`: run the Vercel CLI from this
   directory after logging in:

   ```bash
   cd web
   vercel login
   vercel link
   ```

   The link command creates `web/.vercel/project.json`. Copy `orgId` into
   `VERCEL_ORG_ID` and `projectId` into `VERCEL_PROJECT_ID`.
3. Add the secrets in GitHub under repository Settings -> Secrets and variables
   -> Actions -> New repository secret.

In the Vercel dashboard, set the project root directory to `web` if using Vercel Git integration directly. The GitHub Actions workflow uses `--cwd web`, so it can deploy from a repository root checkout.

The Vercel project also needs the runtime variables above in Project Settings ->
Environment Variables. For production, point `BROKERGATE_API_BASE_URL` at an
authenticated BrokerGate API endpoint that Vercel can reach.
