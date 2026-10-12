# ORBIT: demo script (about 4 minutes)

Written to be said out loud in simple words. Text in *italics* is what to do on screen.

## Before you start (1 minute, off camera)
- Open the dashboard: https://orbit-lyart-tau-78.vercel.app and sign in as **Manager** (one click).
- Open Google Chat with ORBIT in another window.
- Wake the backend by opening https://orbit-backend-mq67.onrender.com/health once.
- Have two or three tasks on the board so it does not look empty.

## 1. What it is (20 seconds)
"ORBIT is a task manager you can talk to. Teams already live in Google Chat, so you just write what you need, like *move my late tasks to Friday*, and a small team of AI helpers does it. There is also a dashboard for the board, the week and the history."

## 2. Chat: simple requests (50 seconds)
*In Google Chat:*
- Type **show my tasks**. "I get my tasks as a card. Each one has buttons: Done, Start, Due tomorrow and Undo."
- Press **Start** on one task. "One tap, and it moves to In progress."
- Type **create a task review the pricing page by Friday, high priority**. "It understood the title, the priority and the date, and shows what it set."
- Type the same sentence again. "It will not add the same task twice. It tells me the task already exists, and I can say *create it anyway*."
- Type **undo that**. "Changed my mind. One word reverses it. If a teammate changed the task since, ORBIT leaves it alone, so it never overwrites someone else's work."

## 3. Chat: the clever part (50 seconds)
*Type:* **move all my overdue tasks to Friday and make them high priority**
"This is more than one step. ORBIT works out the plan by itself: find the late tasks, then change each one. It can only use a fixed set of safe tools, it stops after a few steps, and it cannot delete anything. If two people have the same name, it asks me instead of guessing."

*Type:* **plan my week**
"Planning is not left to the AI. It is a small program: late work first, then the nearest deadline, spread across five days, with a warning when a deadline cannot be met. So it is instant, always the same answer, and it works even if the AI is down."

*Type (as manager):* **who should take this?**
"It counts open and late tasks per person and suggests who has the most room, with the reason."

## 4. Safety and control (30 seconds)
*Type:* **delete the old brochure task**
"For anything destructive, ORBIT asks first and waits for my yes. Employees cannot delete at all. Questions never change data, and every change is saved in a history."

## 5. Dashboard (60 seconds)
*Switch to the dashboard.*
- **Board:** "The same tasks, live. Anything I did in Chat appears here without refreshing."
- **My week:** "The same week plan, as a calendar."
- **ORBIT activity:** "This shows how every request was handled: who understood it, which helper did it, what changed and how long it took. The map in the middle is the team: the Coordinator in the centre sends each request to the right helper."
- **Admin (manager):** "Connections to Google Chat, reminders, users."

## 6. It works on its own (20 seconds)
"ORBIT does not wait to be asked. It sends a morning briefing, reminds people about tasks due soon, nudges tasks that went quiet, and tells managers about the late ones, in Chat and by email."

## 7. How it is built (30 seconds)
"A supervisor reads each message and sends it to one of five helpers: task, planner, advisor, reviewer, or the multi-step helper. Simple requests skip the AI entirely, so the free AI limit lasts. If the AI is slow or out of quota, ORBIT falls back to other models and finally to plain rules, so it keeps answering. Data is in Postgres, short-term memory in Redis. It is deployed on Render and Vercel."

## 8. Close (10 seconds)
"So: you talk to it, it acts, it asks before risky things, you can undo, and you can always see what it did."

---

## If something goes wrong
- **Chat is slow the first time:** the free server was asleep. Say "it wakes up on the first request" and send again.
- **The AI says it is busy:** "That is the free AI limit. This is exactly why the simple requests do not use the AI, and why there are fallback models." Then use a simple request such as *show my tasks*.
- **A button does nothing:** it is from an old card. Ask for a fresh card with *show my tasks*.

## Submission checklist
- [ ] Dashboard link opens and Manager sign-in works
- [ ] Chat answers, Done and Undo work on a fresh card
- [ ] Health monitor is running
- [ ] Architecture document section 8 is filled in
- [ ] Repository access given to reviewers
- [ ] Keys rotated after the demo (Gemini, Cloudflare, ngrok)
