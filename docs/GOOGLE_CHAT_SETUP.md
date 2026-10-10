# GOOGLE_CHAT_SETUP.md: Connect ORBIT to Google Chat

This takes you from nothing to a working bot. Test it locally first with the simulator (section 1); you do not need Google for that.

## 0. What ORBIT does in Chat

| You type | ORBIT does |
|---|---|
| `Create a high priority task for Rahul to test the API by Friday` | Creates it, replies with a task card |
| `/tasks` or `Show my pending tasks` | Replies with a card listing your tasks, each with a **Done** button |
| `/plan` or `What should I focus on today?` | Ranked plan with reasons |
| `/overdue`, `/insights`, `/help` | Overdue list, workload insights, command help |
| `/new Fix the login bug` | Creates a task titled "Fix the login bug" |
| `Make it critical` | Updates the task you just discussed (memory is per person per thread) |
| `Delete the old login task` | Managers get a **Confirm / Cancel** card; employees are told only managers can delete |

Proactively, ORBIT sends a 9:00 morning briefing, an 18:00 overdue alert, and a notification when someone assigns you a task or completes one you created (all opt-out per user on the dashboard Profile page).

Each person has their own conversation per thread, so in a shared room "it" never refers to a colleague's task.

## 1. Try it locally without Google

```bash
# backend running on :8001 with seeded users (README Quick start)
cd backend
python -m scripts.simulate_chat --email john@orbit.dev
```

At the `you>` prompt:

```
you> /tasks
you> done 1            # presses the Done button on item 1 of the last card
you> Create a task to review the PR
you> quit
```

Log in as a manager (`--email sarah@orbit.dev`) and say `Delete the Review the PR task`, then type `confirm` or `cancel` to press the card button. For one-shot use: `--say "Plan my day"`.

Notes:
- Requires `GOOGLE_CHAT_VERIFY_AUTH=false` (the development default). If `GOOGLE_CHAT_WEBHOOK_SECRET` is set the simulator signs requests with it (pass `--secret` or export the variable).
- On Git Bash for Windows, an argument starting with `/` is rewritten into a file path. Type slash commands at the interactive prompt, or prefix the command with `MSYS_NO_PATHCONV=1`.

## 2. Google Cloud setup

1. **Project and API**: in [Google Cloud Console](https://console.cloud.google.com) select or create a project and enable the **Google Chat API**. Note the **project number** (Dashboard, Project info).
2. **Service account** (lets ORBIT send proactive messages): IAM, Service accounts, create one, then Keys, Add key, JSON. Save it as `credentials/service-account.json` (git-ignored) or paste the JSON into `GOOGLE_SERVICE_ACCOUNT_JSON`. Never commit it.
3. **Public HTTPS URL** for the webhook. Easiest on a dev machine: `cd backend && python -m scripts.dev_tunnel` (needs `cloudflared`; on Windows `winget install Cloudflare.cloudflared`). It starts a free tunnel, prints the exact endpoint URL, copies it to your clipboard and sends a test event through it. Keep it running, and paste the new URL into Google Cloud after every restart (quick-tunnel URLs change). Alternatives: Local development: `ngrok http 8001`, which gives `https://abc123.ngrok-free.app`. Production: your API's HTTPS address.
4. **Chat app configuration** (Google Chat API, Configuration):
   - App name `ORBIT`, an avatar URL, description "Multi-agent task management".
   - Enable **Receive 1:1 messages** and **Join spaces and group conversations**.
   - Connection settings: **HTTP endpoint URL** = `https://<your-host>/api/chat/webhook`.
   - **Authentication audience**: choose one and mirror it in `.env` (see section 3):
     - *HTTP endpoint URL* (simplest): audience is the endpoint URL itself.
     - *Project number*: audience is the project number.
   - **Commands**: add these slash commands (the command **ID** matters, ORBIT maps the number to the action):

     | ID | Name | Description |
     |---|---|---|
     | 1 | `/help` | Show what ORBIT can do |
     | 2 | `/tasks` | Show my pending tasks |
     | 3 | `/plan` | Plan my day |
     | 4 | `/overdue` | Show overdue tasks |
     | 5 | `/new` | Create a task (`/new Fix the login bug`) |
     | 6 | `/insights` | Workload recommendations |

     Typed names work even without the IDs.
   - Visibility: yourself and specific people while testing; widen later.
5. Save the configuration. The app now appears in Google Chat when you search for `ORBIT`.

## 3. ORBIT configuration

```env
# Production values
ENVIRONMENT=production
GOOGLE_CHAT_VERIFY_AUTH=true
GOOGLE_CHAT_AUDIENCE=https://<your-host>/api/chat/webhook   # or the project number, matching step 4
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service-account.json
# Optional extra layer: requests must also carry a valid X-Goog-Signature HMAC
GOOGLE_CHAT_WEBHOOK_SECRET=
# Optional: a space that receives the weekly summary broadcast
GOOGLE_CHAT_SPACE_ID=spaces/AAAA...
```

Local development with ngrok can leave `GOOGLE_CHAT_VERIFY_AUTH=false`; never do that on a public deployment (anyone could then post events as any user). In production the app refuses to start with verification off, or on without an audience.

## 4. Accounts

First message from a new person creates an `employee` account from their Google identity. If that email already belongs to a password account, the Chat identity attaches to it. Promote people to manager or admin on the dashboard (Admin, Users). The first direct message also records that person's DM space so ORBIT can message them proactively later.

## 5. Verification checklist

- [ ] In Google Chat, message ORBIT `help`; you get the command list.
- [ ] `/tasks` returns a card; pressing **Done** completes the task and the dashboard board updates within 15 seconds.
- [ ] As a manager, `Delete the <task>` shows Confirm and Cancel; Confirm deletes (audit trail records "via Google Chat"), Cancel does not.
- [ ] As an employee, the same delete request is refused politely.
- [ ] Assign a task to someone else on the dashboard; they receive a DM, and Admin, Notifications shows `sent`.
- [ ] Admin, Scheduler, run "Morning briefing"; recipients get a DM, people with no linked Google account show `skipped` rather than `sent`.
- [ ] Send the same message twice quickly (or use the simulator to replay an event): only one task is created.
- [ ] With `GOOGLE_CHAT_VERIFY_AUTH=true`, `curl -X POST https://<host>/api/chat/webhook -d '{}'` returns 401.

## 6. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Chat shows "ORBIT not responding" | Nothing is answering the endpoint URL. Most often the tunnel stopped (its URL changes when restarted) or the backend is down. Run `python -m scripts.dev_tunnel`, paste the new URL, and check the backend log for `[WEBHOOK INCOMING]` |
| 401 in the log, "Invalid or missing Google Chat authentication token" | Verification is on and the audience in `.env` does not match the Chat app's Authentication audience (project number vs endpoint URL) |
| 403 "Invalid Google Chat webhook signature" | `GOOGLE_CHAT_WEBHOOK_SECRET` is set; every request must be HMAC-signed, which Google does not do by itself. Leave the secret empty when relying on Google token verification |
| Replies work but proactive DMs say `failed` | The service account is not permitted in that space, or the user never added the app; read the reason in Admin, Notifications |
| DMs `skipped` | That user has not messaged ORBIT or signed in with Google yet |
| Slash command does nothing | Command IDs in the Chat console must be 1 to 6 as in the table (typed `/tasks` works regardless) |
| A Chat user does not match their dashboard account | Google did not include an email in the event, so ORBIT created `<id>@orbit.chat`. Ensure the Chat app can read user emails (Workspace users in your domain normally can). There is no UI to merge accounts after the fact |
| Message processed twice | Should not happen: events are de-duplicated by message id; if you see it, check `chat_event_ledger` and the log for `[WEBHOOK DEDUP]` |
| "Something went wrong (ref abc123)" | Search the backend log for that reference id for the stack trace |

## Keeping the endpoint stable

A quick tunnel (`python -m scripts.dev_tunnel`) is for testing: its address changes every time it restarts, and Chat shows "not responding" until you paste the new URL into the Chat API configuration. For anything longer-lived use one of:

1. **A named Cloudflare tunnel** (free, needs a domain on Cloudflare): `cloudflared tunnel login`, `cloudflared tunnel create orbit`, route a hostname such as `orbit.example.com` to it with `cloudflared tunnel route dns orbit orbit.example.com`, then run `cloudflared tunnel run --url http://localhost:8001 orbit`. Install it as a service (`cloudflared service install`) so it survives reboots. The URL never changes.
2. **Deploy the backend** to a host with a fixed HTTPS address (Render, Fly.io, Railway, a VM behind Caddy) and set `ENVIRONMENT=production`, `GOOGLE_CHAT_VERIFY_AUTH=true` and `GOOGLE_CHAT_AUDIENCE`.

Either way, the endpoint to register is `https://<your-host>/api/chat/webhook`.
