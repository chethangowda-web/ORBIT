# Deploying the ORBIT backend to Render

This puts the API, the Google Chat webhook and the scheduler on a fixed public HTTPS address, so the bot works without your PC. It uses `render.yaml` in the repository root, which creates a web service, a Postgres database and a Redis (Key Value) instance.

## What it costs and what to expect

| Piece | Plan in `render.yaml` | Notes |
|---|---|---|
| Web service | `free` | 512 MB RAM (the backend idles at about 360 MB, so there is little headroom). A free service **sleeps after 15 minutes without traffic**, and a sleeping service cannot answer Google Chat inside its 30 second limit or run the scheduler, so set up the keep-alive below. For a service that stays awake on its own change `plan` to `starter` (paid, roughly $7 per month). |
| Postgres | `free` | Deleted after 30 days. Upgrade the plan in the Render dashboard before then; data is kept. |
| Redis (Key Value) | `free` | Holds conversation memory and scheduler jobs. |

Check current prices on Render's pricing page before confirming.

Not included: the dashboard (it still runs on your PC) and file attachments persistence (Render's disk needs a paid plan; without it uploaded files are lost on each deploy).

## Before you start

- The code must be on GitHub, on the branch you will deploy. Merge `feature/v2-rebuild` into `master` first, or choose `feature/v2-rebuild` in step 2.
- Have these ready, but **never paste secrets into chat or commit them**:
  - the Google service-account JSON (the file behind `GOOGLE_SERVICE_ACCOUNT_FILE`),
  - your Google Cloud project number (for a Workspace add-on Chat app),
  - a seed password of 12 or more characters,
  - optionally a Gemini API key.

## Steps

1. Create a Render account at render.com and connect your GitHub account.
2. **New > Blueprint**, select the ORBIT repository and the branch, then **Apply**.
3. Render asks for the variables marked `sync: false`:
   - `GOOGLE_CHAT_ADDON_PROJECT_NUMBER`: your project number.
   - `GOOGLE_SERVICE_ACCOUNT_JSON`: open the service-account file, copy its entire contents, paste them here.
   - `SEED_PASSWORD`: the password for the demo accounts (`admin@orbit.dev`, `sarah@orbit.dev`, `john@orbit.dev`).
   - `GOOGLE_CHAT_AUDIENCE`: type any placeholder for now; you fix it in step 5.
   - Leave the optional ones blank if unused.
4. Wait for the first deploy. The container applies the database migrations on start. When the service shows **Live**, open `https://<service-name>.onrender.com/health`: you should see `{"status":"healthy",...}`.
5. In the service's **Environment** tab, set `GOOGLE_CHAT_AUDIENCE` to `https://<service-name>.onrender.com/api/chat/webhook` and save. Render redeploys.
6. In Google Cloud Console, Chat API, Configuration:
   - HTTP endpoint URL: `https://<service-name>.onrender.com/api/chat/webhook`
   - Authentication audience: **HTTP endpoint URL**
   - Save.
7. Send "hi" to the bot. If it does not answer, open the service **Logs** and look for `verification failed`; the line says why (see `docs/GOOGLE_CHAT_SETUP.md`, Troubleshooting).
8. **Turn the local copy off** so two backends do not both run the scheduler and message people twice: stop the ngrok service, remove the scheduled task and stop the local containers.

   ```powershell
   Unregister-ScheduledTask -TaskName "ORBIT keep running" -Confirm:$false
   docker compose stop backend
   ```
   (Stopping the ngrok Windows service needs an Administrator PowerShell: `ngrok service stop`.)

## Keep the free service awake

1. Create a free account at uptimerobot.com.
2. **Add New Monitor**: type **HTTP(s)**, URL `https://<service-name>.onrender.com/health`, interval **5 minutes**.
3. Done. The regular visits stop the 15 minute idle sleep. A free service has about 750 running hours per month, enough for one service all month.

If the service ever restarts or redeploys, the first Chat message can still be slow (a cold start takes up to a minute). The monitor also emails you when the service is down.

## If sign-in says "Invalid email or password"

The demo accounts get `SEED_PASSWORD` on the first deploy. If that value had a stray space or newline when it was pasted, the stored password is wrong. To reset it:

1. In Render, **Environment**: re-type `SEED_PASSWORD` (12 or more characters) and add `SEED_RESET_PASSWORDS` = `true`.
2. Save and wait for the redeploy to show **Live**. The log prints `Reset the password of 3 demo account(s)`.
3. Sign in with `admin@orbit.dev` and the new password.
4. **Delete `SEED_RESET_PASSWORDS`** so the passwords are not reset on every start.

## Demo credentials on the login page

For a demo, set `NEXT_PUBLIC_DEMO_PASSWORD` in Vercel (Settings, Environment Variables) to the same value as `SEED_PASSWORD` in Render, then redeploy the dashboard. The login page then lists the three demo accounts with one-click sign-in buttons. The value is public to anyone who opens the page and `admin@orbit.dev` is an administrator, so use a password you do not use anywhere else and remove the variable (and reset the passwords) when the demo is over. Leave it unset for real use.

## Afterwards

- The Render database starts empty. Chat users are created when they first message the bot; the seeded accounts let you sign in to a dashboard.
- **Vercel gives every deployment its own address** (for example `orbit-abc123-team.vercel.app`) besides your main one. The browser blocks sign-in from any address that is not allowed, and the login shows "Cannot reach the ORBIT server". Always share the main address. To allow all of your team's deployment addresses, set `CORS_ORIGIN_REGEX` in Render to a pattern that matches the whole address, for example `https://orbit-[a-z0-9-]+-chethann1328-7757s-projects\.vercel\.app`. Patterns that match every website are refused in production.
- To point your local dashboard at Render, rebuild it with `NEXT_PUBLIC_API_URL=https://<service-name>.onrender.com/api` and add the dashboard address to `CORS_ORIGINS` in Render (a JSON list, for example `["http://localhost:3000"]`).
- Logs, metrics and restarts are in the Render dashboard. The service restarts itself if it crashes, and Render health-checks `/health`.
- Rotate secrets that have been shared anywhere (service-account key, ngrok and Cloudflare tokens).
