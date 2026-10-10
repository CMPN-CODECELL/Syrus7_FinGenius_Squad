# SkillSync AI POC — Integrated Source → AI → Database → App

This version connects the three dummy source terminals to the supplied SkillSync login/application UI and adds a server-side Groq extraction step.

## Flow

The source gateway is a **separate simulator**, not part of the SkillSync login/app flow.

Source Gateway → LinkedIn / Unstop / Mail terminal → FastAPI ingestion → `raw_items` → Groq structured extraction (when configured) → validation/missing-field reporting → `opportunities` → SkillSync database

Separately: Login → SkillSync application → Opportunities / Peer Hub / Profile / Agent Console

The source gateway can be opened directly for demonstrations; it is not the post-login destination.

The main application reads opportunities from the backend rather than the hard-coded demo dataset.

## Important: Groq API key

The key is intentionally **not included**. Put it only in `backend/.env`:

```env
GROQ_API_KEY=YOUR_KEY_HERE
GROQ_MODEL=openai/gpt-oss-20b
```

The frontend never receives the key. The backend calls Groq through its OpenAI-compatible endpoint. The extraction request uses a JSON schema so the AI returns the standardized opportunity fields. See the official Groq documentation linked below.

## Windows setup

### Terminal 1 — backend

```cmd
cd "C:\path\to\skillsync-ai-poc\backend"
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Open `backend/.env` and add your Groq key. The backend explicitly loads this file from the backend directory.

Then:

```cmd
uvicorn app.main:app --reload --port 8000
```

Leave this terminal open.

### Terminal 2 — frontend

```cmd
cd "C:\path\to\skillsync-ai-poc\frontend"
npm install
npm run dev
```

Open the URL Vite prints, normally `http://127.0.0.1:5173/`.

## Demo sequence

1. Open `login.html` through Vite.
2. Log in with any valid-looking email and a password of 6+ characters. This is demo auth only; login goes directly to the SkillSync application.
3. Open `gateway.html` separately when you want to simulate LinkedIn, Unstop, or Mail source traffic.
4. Mail now uses a free-form email composer for long pasted messages and forwarded threads; LinkedIn and Unstop have source-specific listing forms with optional additional details. The pipeline flags missing critical details after submission.
5. Submit it to the backend; the normalized opportunity is stored in the SkillSync database.
6. Return to the SkillSync application and open Opportunities to see the new record.
7. Open **My Profile** to edit the real profile fields; the name, university, skill slider values, privacy mode, and stored preferences are persisted in SQLite.
8. Open **Agent Console** to see database counts and Groq status.
9. Open `backend/skillsync.db` in DB Browser for SQLite to watch `raw_items`, `opportunities`, and `profiles` change.

## AI behavior

When `GROQ_API_KEY` is configured, `/api/ingest/unstructured` uses Groq structured output to extract:
- title
- organization
- type
- description
- location / format
- deadline / dates
- fee / currency
- team size
- skills
- education / experience
- impact lens / tags
- application URL
- confidence
- missing fields

If the key is not configured, the POC uses a small deterministic fallback extractor so the rest of the pipeline can still be demonstrated. The response clearly reports that AI was not used.

## Database

SQLite is created automatically at:

`backend/skillsync.db`

Tables:
- `raw_items` — original source text plus AI extraction output
- `opportunities` — normalized records consumed by the SkillSync app
- `profiles` — current student profile, skill proficiency levels, and matching preferences
- `tracked` — saved/tracked opportunities

## API

- `GET /api/health`
- `GET /api/opportunities`
- `GET /api/opportunities?source=mail`
- `POST /api/ingest/structured`
- `POST /api/ingest/unstructured`
- `GET /api/profile`
- `PUT /api/profile`
- `GET /api/peers`
- `POST /api/opportunities/{id}/track`
- `DELETE /api/opportunities/{id}/track`
- `GET /api/stats`

## Security note

This is a local POC. The login is demo-only and does not authenticate against a real identity provider. Before production, add real authentication, authorization, CSRF/CORS policy, secrets management, rate limits, audit logging, and a production database.

## Official Groq references

- https://console.groq.com/docs/openai
- https://console.groq.com/docs/structured-outputs


## Source channel UX in this iteration

- Gateway styling uses the supplied `index.html` / `styles.css` design language, with working LinkedIn, Unstop, and Mail cards.
- LinkedIn uses blue accents, Mail uses red accents and a large free-form message body, and Unstop uses the green baseline with warm orange accents.
- Source terminals no longer include an “Open SkillSync app” shortcut. Open SkillSync separately at `index.html`.
- Application/information URLs are retained in the opportunity description and are also rendered as clickable links in SkillSync.
- Missing critical fields are flagged in the extraction result for review.


## Iteration 3 updates
- Source forms include clear-text actions and a Clear all fields reset.
- Channel submit actions use the label “Send”.
- LinkedIn and Unstop listing forms expose event start/end dates.
- Source channels accept an original source-post URL separately from the application/information URL; SkillSync stores and displays both when provided. For a dummy source, enter that dummy website post URL in the “Original post URL” field.
- Profile fields include GitHub, LinkedIn, Unstop, contact email, age, date of birth, and free-text skills; values persist in SQLite.
- Existing SQLite databases are migrated automatically to add the new fields.


## Gmail opportunity sync (local POC)

1. In Google Auth Platform → Clients, open the Web OAuth client used for SkillSync. Add this exact Authorized redirect URI: `http://127.0.0.1:8000/api/gmail/callback`.
2. Copy that Web client’s **client secret** into `backend/.env` as `GOOGLE_CLIENT_SECRET=...`. Also ensure `GOOGLE_CLIENT_ID` is the same client ID and set `GMAIL_REDIRECT_URI=http://127.0.0.1:8000/api/gmail/callback`. Never commit or share `.env`.
3. In the active backend virtual environment, run `python -m pip install -r requirements.txt`, then restart Uvicorn.
4. Sign in to SkillSync, open My Profile, click **Connect Gmail**, consent to read-only Gmail access, then click **Sync emails now**.

The importer checks recent (90-day) messages matching opportunity-related terms, imports each message once, and uses the existing extraction pipeline. This is a local proof of concept, not production-ready token storage; Gmail `gmail.readonly` is a restricted scope and public release may require Google's verification/security assessment. See Google's [web-server OAuth guide](https://developers.google.com/identity/protocols/oauth2/web-server) and [Gmail scope guidance](https://developers.google.com/workspace/gmail/api/auth/scopes).
\n\n## AI email opportunity extraction\n\nGmail sync stores the original cleaned email in `raw_items` and the extracted structured opportunity in the SQLite database. The opportunity ticker uses a short 1–2 sentence description; dates, eligibility, skills, format, benefit/fee, and application/source URLs are stored in dedicated fields when available. Missing important fields are recorded in `missing_fields` rather than invented.\n\nConfigure `GROQ_API_KEY` and `GROQ_MODEL` in `backend/.env` for local runs (or in your hosting provider's environment settings). Never commit real keys or OAuth secrets. If Groq is unavailable, the app uses a conservative fallback extractor; verify the logs/configuration if summaries do not look AI-generated.\n

## v28 improvements
- Infer specific opportunity categories from extracted email/listing content for better filtering, with AI extraction instructed to classify more precisely.
- Simplify Agent Console output, add a visual source-to-summary-to-next-steps flow, move suggested prompt bubbles to the bottom, and render questions/answers as compact chat cards.


## v29 fixes
- Gmail sync searches recent mail broadly and paginates up to 200 messages per run.
- Retries imported markers that do not have a linked opportunity.
- Opportunity feed reads no longer delete expired opportunities.
- Profile entry verification accepts meaningful entries if the AI service is unavailable, while rejecting obvious gibberish.
