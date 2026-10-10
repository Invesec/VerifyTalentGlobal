# VerifyTalent Global (Flask)

Find. Verify. Match.

Flask + SQLAlchemy + Jinja. **Milestone 1:** project structure, database connection, `/health`, landing page.
**Milestone 7:** email verification with a 6-digit code, free permanent database (Neon) and data backups, interactive features (step-by-step sign-up forms, live admin search, progress trackers, notifications, copy/share buttons).
**Milestone 6:** forgot/reset password, account settings, talent profile editing, public pages (About, How it works, Find talent, For companies, Categories, Contact, Privacy, Terms), production hardening for Render.
**Milestone 5:** job requests, rule-based matching with scores, admin review (shortlist, present, interview, placement), talent opportunities page.
**Milestone 4:** company registration, company review and approval, client agreement (send, view, accept), activation with the official Client ID, client dashboard.
**Milestone 3:** admin dashboard, status changes with emails, manual $60 payment confirmation, Talent ID and ID card, public verification page, demo data.
**Milestone 2:** database tables, talent registration with category-specific questions, login and logout, talent dashboard, audit log, Brevo "Application Received" email.

Locally the app uses a SQLite file (no setup). On Render it uses PostgreSQL through `DATABASE_URL`.

## Run on Termux

```bash
pkg update && pkg upgrade -y
pkg install python git unzip -y
termux-setup-storage            # tap Allow when asked
cd ~
unzip ~/storage/downloads/verifytalent-global-flask.zip
cd verifytalent-global-flask
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python wsgi.py
```

Open `http://localhost:5000` in your phone browser. Stop the server with CTRL + C.

Next time, only run: `cd ~/verifytalent-global-flask && source .venv/bin/activate && python wsgi.py`

If `pip install` fails on `SQLAlchemy` or `greenlet`, run `pkg install clang make -y` and try again.

## Email through Gmail (free)

1. Use a Gmail account for the platform (it appears as the sender). In Google Account, open **Security** and turn on **2-Step Verification**.
2. Open **Security**, then **2-Step Verification**, then **App passwords**. Create one named `VerifyTalent` and copy the 16 letters (spaces do not matter).
3. In Render, set `SMTP_USER` to the Gmail address and `SMTP_PASSWORD` to the app password. Leave `SMTP_HOST` and `SMTP_PORT` empty (they default to Gmail).
4. If you still have `BREVO_API_KEY` set, you can delete it. Redeploy happens automatically.
5. Register a test account and check that the code email arrives (also check spam).

Gmail limits how many emails an account can send per day, which is fine for getting started. If you later outgrow it, set the same variables for Mailjet, SMTP2GO, or Resend (their SMTP details) with no code change. Never share the app password. If it leaks, delete it in your Google Account and make a new one.

## Email verification

Talents and companies must confirm their email with a 6-digit code before they can use their dashboard. Codes expire after 15 minutes, allow 5 wrong tries, and can be re-sent once a minute. Admins are exempt. Finishing a password reset also verifies the email. In `/admin`, open a talent or company to see whether their email is verified, and use **Mark email as verified** if someone cannot receive the code.

- **Locally without email settings:** the code is printed in the Termux window on a line starting `DEV ONLY verification code`.
- **On Render:** verification turns on only when an email provider is set (`SMTP_USER` and `SMTP_PASSWORD` for Gmail, or the Brevo pair), so a missing email setup can never lock everyone out. Run `flask --app wsgi check-config` to see whether it is on.
- Anyone who registered before this update will be asked to verify the next time they open their dashboard.

## Update to Milestone 7

```bash
cd ~
unzip -o ~/storage/downloads/verifytalent-global-flask-m7.zip
cd verifytalent-global-flask
source .venv/bin/activate
python wsgi.py
```

No new packages are needed.

## Test Milestone 7

1. Register a new test talent. After the form you land on **Verify your email**. Find the code in the Termux window and enter it.
2. The sign-up form now runs step by step with a progress bar. Check Next, Back, and the password show/hide button.
3. Log in as admin, open **Talent**, and type in the search box. The list should update as you type.
4. Open a talent dashboard to see the progress tracker and the Copy buttons. Open **Notifications**.
5. In `/admin`, open **Backup** and download the ZIP.

## Update to Milestone 6

```bash
cd ~
unzip -o ~/storage/downloads/verifytalent-global-flask-m6.zip
cd verifytalent-global-flask
source .venv/bin/activate
python wsgi.py
```

No new packages are needed.

## Test Milestone 6

1. Open `/about`, `/how-it-works`, `/privacy`, and `/terms`, and check the footer links.
2. Log out, open `/login`, tap **Forgot your password?**, and enter your email. Without email settings, look in the Termux window for a line starting `DEV ONLY reset link`. Open that link in your browser and choose a new password.
3. Log in as a talent, open **Edit profile** on the dashboard, change something, and save.
4. Open **Account** in the menu and change your password.

## Update to Milestone 5

```bash
cd ~
unzip -o ~/storage/downloads/verifytalent-global-flask-m5.zip
cd verifytalent-global-flask
source .venv/bin/activate
python wsgi.py
```

No new packages are needed. The new tables are created automatically on start.

## Test Milestone 5 (fastest way, using demo data)

1. Log in as admin and open `/admin`. If demo data already exists, tap **Delete demo data** first, then **Add demo talents**. This adds a verified demo developer (Kemi) and an active demo company with one demo job request.
2. Open **Jobs**, open the demo job, and tap **Run matching**. Kemi should appear with a Match Score.
3. Tap **Shortlist**, then **Present to client**, then fill in **Schedule interview** (a future date and a meeting link), then **Mark placed**. The job becomes Filled.
4. To see the real emails and both sides, use your own test accounts: a verified talent (Milestone 3 steps) and an active company (Milestone 4 steps). Post a job as the company, run matching as admin, and log in as the talent to answer on the **Opportunities** page.

Matching only considers verified talent whose ID card is active. Scoring: skills 40, experience 20, profession 20, location 10, availability 10. Timezone is not scored yet because talent profiles do not collect one.

## Update to Milestone 4

```bash
cd ~
unzip -o ~/storage/downloads/verifytalent-global-flask-m4.zip
cd verifytalent-global-flask
source .venv/bin/activate
python wsgi.py
```

No new packages are needed. The new tables are created automatically on start.

## Test Milestone 4

1. Log out, open `/register/company`, and register a test company (use a different email from your admin and talent test accounts).
2. Log in as admin, open **Companies**, and open the test company. Tap **Approve company**.
3. In **Client agreement**, enter a document link or reference (any text or link works while testing) and tap **Send to client**.
4. Log in as the company and open **Agreements**. Type your name, tick the box, and accept.
5. Log back in as admin and tap **Activate client**. The company now has a Client ID such as `VTG-CL-000001`.

Agreements are legal documents. Have a qualified lawyer review your agreement text before using it commercially.

## Update to Milestone 3

```bash
cd ~
unzip -o ~/storage/downloads/verifytalent-global-flask-m3.zip
cd verifytalent-global-flask
source .venv/bin/activate
pip install -r requirements.txt      # adds the QR code package
python wsgi.py
```

Create your admin account once (the password is typed hidden and is never saved in `.env`):

```bash
flask --app wsgi create-admin --email you@example.com
```

Then log in at `/login`. Admins land on `/admin`.

## Test Milestone 3

1. In `/admin`, tap **Add demo talents** (labelled [DEMO], cannot log in, never emailed).
2. Open a demo talent, choose **Approve application**.
3. Open the same talent: enter a payment reference, choose a method, tap **Confirm payment**.
4. The talent now has a Talent ID such as `VTG-TL-000001`. Open `/verify/talent/VTG-TL-000001` to see the public page.
5. To see the talent side, register a real test account at `/register`, approve it as admin, then log in as that talent and open Onboarding and ID Card.
6. When finished, tap **Delete demo data**.

## Update from Milestone 1

Your `.venv` and `.env` stay as they are. From your home folder:

```bash
unzip -o ~/storage/downloads/verifytalent-global-flask-m2.zip
cd verifytalent-global-flask
source .venv/bin/activate
python wsgi.py
```

The new tables are created automatically on start. If you already ran the old version, nothing needs migrating.

## Test Milestone 2

1. Open `/register`, pick **Translator** and watch the language questions appear. Pick **Software Developer** and they change.
2. Submit the form. You land on your dashboard with an Application ID such as `VTG-APP-000001`.
3. Without email settings, the terminal prints `Email NOT sent (no email provider configured)`. That is expected. Add `SMTP_USER` and `SMTP_PASSWORD` to `.env` to send for real (see the Gmail section).
4. Log out, then log in again at `/login`.

## Test

| What | Address | Expected |
|---|---|---|
| Landing page | `/` | Branded home page |
| Health check | `/health` | `{"status":"ok"}` |
| Database check | `/health/db` | `connected` or `unavailable` |

## Push to GitHub

Create an empty repository on GitHub first, then:

```bash
git init
git add .
git commit -m "Initial VerifyTalent Global MVP"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY
git push -u origin main
```

Run `git status` before pushing and confirm `.env` is not listed.

## Free database that does not expire (Neon)

Render's free PostgreSQL database is deleted after 30 days. Use a free **Neon** database instead and keep Render only for the web service. The app only needs one connection string, so nothing in the code changes.

1. Sign up at neon.com (no card needed) and create a project. Pick the region closest to your users.
2. Copy the **connection string** (it starts with `postgresql://` and ends with `sslmode=require`). Treat it like a password: never post it in chat or commit it to GitHub.
3. Do **not** create a Render PostgreSQL database. In your Render web service, set `DATABASE_URL` to the Neon connection string.
4. Deploy. The tables are created automatically on first start.

Neon's free plan includes 0.5 GB of storage and 100 compute-hours a month, with no expiry. The database goes to sleep after 5 minutes without use and wakes on the next request. If you ever reach a monthly limit, Neon pauses compute until the next month rather than charging you. Check neon.com/pricing for current limits. Half a gigabyte holds a lot of text records, but watch the usage page in Neon's dashboard.

For testing, create a **second** Neon project and use it locally, so test data never mixes with real data.

### Backups (do this regularly)

Free plans have a short restore window, so keep your own copies.

- **Easy:** in `/admin`, open **Backup** and tap **Download backup**. You get a ZIP of spreadsheet (CSV) files. Password hashes are left out. Keep it somewhere private.
- **Full database copy (can be restored):** in Termux run `pkg install postgresql`, then
  ```bash
  pg_dump "YOUR_NEON_CONNECTION_STRING" -Fc -f backup-$(date +%F).dump
  ```
  To restore into an empty database:
  ```bash
  pg_restore --clean --if-exists --no-owner -d "NEW_CONNECTION_STRING" backup-2026-10-10.dump
  ```
  If `pg_dump` complains about a version mismatch, run `pkg upgrade` and try again.

## Deploy on Render

1. Push the project to GitHub (see above). Check `git status` first: `.env` must not be listed.
2. Create your Neon database (see above) and copy its connection string.
3. On Render, create a **Web Service** from your GitHub repo.
   - Build command: `pip install -r requirements-prod.txt`
   - Start command: `gunicorn wsgi:app --workers 1 --threads 4 --timeout 60`
   - Health check path: `/health`
4. Add these environment variables:

| Name | Notes |
|---|---|
| `DATABASE_URL` | the Neon connection string |
| `SESSION_SECRET` | **required**. The app will not start in production without it |
| `SMTP_USER`, `SMTP_PASSWORD` | Gmail address and its **App Password**, for real emails. Email verification only turns on when an email provider is set |
| `SMTP_HOST`, `SMTP_PORT` | optional. Default to `smtp.gmail.com` and `587` |
| `BREVO_API_KEY`, `BREVO_SENDER_EMAIL` | optional backup provider, used only if Gmail fails |
| `COMPANY_EMAIL`, `TELEGRAM_USERNAME` | shown on the Onboarding and Contact pages |
| `ADMIN_EMAIL`, `ADMIN_INITIAL_PASSWORD` | creates your first admin on startup (12+ characters). **Delete `ADMIN_INITIAL_PASSWORD` after you can log in** |

Generate a session secret with: `python -c "import secrets; print(secrets.token_hex(32))"`

5. Deploy, then open `/health` (expect `{"status":"ok"}`), log in at `/login`, and open `/admin`.

Use one worker (as in the start command). The rate limiter keeps its counts in memory, which only works correctly with one worker.

### Before you go live

- Run `flask --app wsgi check-config` locally or in a Render shell. It lists what is set and what is missing, without printing any secrets.
- Send a real test email (register a test account) and check the inbox and spam folder.
- Replace the demo data: in `/admin`, tap **Delete demo data**.
- Have a qualified lawyer review the **Privacy Policy**, **Terms of Use**, and your **client agreement** before commercial use. The pages describe how the app behaves, but they are not legal advice and do not cover your company's legal details or local data-protection law.
- Test the full flow once on the live site with test accounts: register, approve, payment, ID card, company, agreement, job, matching.

## Password reset

Reset links work once and for one hour. If no email provider is set up while you develop locally, the link is printed in the terminal (development only, never in production).

## Structure

```
wsgi.py                 entry point (gunicorn wsgi:app)
config.py               environment config
app/__init__.py         app factory, security headers, error pages
app/extensions.py       database object
app/models.py           users, talent_applications, audit_logs
app/validators.py       registration validation
app/security.py         CSRF, login_required, rate limiting, password hashing
app/services/           email service (Gmail/SMTP, Brevo backup), audit log, matching rules, email verification, backup
app/routes/             health, pages, auth, account, talent, client, admin, admin_clients, admin_jobs, public verify
app/cli.py              create-admin, seed-demo, reset-demo commands
app/templates/          Jinja pages
app/static/             css, js, logo images
```
