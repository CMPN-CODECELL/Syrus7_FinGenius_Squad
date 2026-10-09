import json
import os
import re
import sqlite3
import base64
import secrets
import html as html_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).resolve().parent.parent / "skillsync.db"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GMAIL_REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI", "http://127.0.0.1:8000/api/gmail/callback").strip()
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
GMAIL_OAUTH_STATES = {}  # local POC only; short-lived state-to-user mapping

app = FastAPI(title="SkillSync AI POC API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": ["string", "null"]},
        "organization": {"type": ["string", "null"]},
        "type": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
        "location": {"type": ["string", "null"]},
        "format": {"type": ["string", "null"]},
        "deadline": {"type": ["string", "null"]},
        "start_date": {"type": ["string", "null"]},
        "end_date": {"type": ["string", "null"]},
        "fee": {"type": ["string", "null"]},
        "payment_type": {"type": ["string", "null"]},
        "monetary_benefit": {"type": ["string", "null"]},
        "currency": {"type": ["string", "null"]},
        "team_size": {"type": ["string", "null"]},
        "skills": {"type": "array", "items": {"type": "string"}},
        "education": {"type": "array", "items": {"type": "string"}},
        "experience": {"type": ["string", "null"]},
        "impact_lens": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "application_url": {"type": ["string", "null"]},
        "source_post_url": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title", "organization", "type", "description", "location", "format",
        "deadline", "start_date", "end_date", "fee", "currency", "payment_type", "monetary_benefit", "team_size",
        "skills", "education", "experience", "impact_lens", "tags", "application_url", "source_post_url",
        "confidence", "missing_fields"
    ],
    "additionalProperties": False,
}

class OpportunityIn(BaseModel):
    source: str
    title: str
    organization: str = ""
    type: str = "opportunity"
    description: str = ""
    location: str = ""
    format: str = ""
    deadline: str = ""
    start_date: str = ""
    end_date: str = ""
    fee: str = ""
    currency: str = ""
    payment_type: str = ""
    monetary_benefit: str = ""
    team_size: str = ""
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    experience: str = ""
    impact_lens: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    application_url: str = ""
    source_post_url: str = ""
    contact_name: str = ""
    contact_email: str = ""
    contact_info: str = ""
    raw_text: str = ""

class UnstructuredIn(BaseModel):
    source: str
    subject: str = ""
    sender: str = ""
    body: str
    source_post_url: str = ""

class ProfileIn(BaseModel):
    name: str = ""
    university: str = ""
    skills: list[str] = Field(default_factory=list)
    skill_levels: dict[str, int] = Field(default_factory=dict)
    interests: list[str] = Field(default_factory=list)
    budget: str = ""
    availability: str = ""
    sustainability: str = "Yes"
    privacy: str = "discoverable"
    github: str = ""
    linkedin: str = ""
    unstop: str = ""
    mail: str = ""
    age: str = ""
    date_of_birth: str = ""
    skills_text: str = ""


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS raw_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source TEXT NOT NULL,
      source_item_id TEXT,
      subject TEXT,
      raw_text TEXT NOT NULL,
      ai_extracted TEXT,
      processed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS opportunities (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source TEXT NOT NULL,
      source_item_id TEXT,
      title TEXT NOT NULL,
      organization TEXT,
      type TEXT,
      description TEXT,
      location TEXT,
      format TEXT,
      deadline TEXT,
      start_date TEXT,
      end_date TEXT,
      fee TEXT,
      currency TEXT,
      payment_type TEXT DEFAULT '',
      monetary_benefit TEXT DEFAULT '',
      team_size TEXT,
      skills TEXT,
      education TEXT,
      experience TEXT,
      impact_lens TEXT,
      tags TEXT,
      application_url TEXT,
      source_post_url TEXT DEFAULT '',
      contact_name TEXT DEFAULT '', contact_email TEXT DEFAULT '', contact_info TEXT DEFAULT '',
      verified INTEGER DEFAULT 1,
      ai_confidence REAL DEFAULT 1.0,
      missing_fields TEXT DEFAULT '[]',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS profiles (
      id INTEGER PRIMARY KEY CHECK(id=1), name TEXT, university TEXT, skills TEXT,
      skill_levels TEXT DEFAULT '{}', interests TEXT, budget TEXT, availability TEXT, sustainability TEXT,
      privacy TEXT, github TEXT DEFAULT '', linkedin TEXT DEFAULT '', unstop TEXT DEFAULT '', mail TEXT DEFAULT '', age TEXT DEFAULT '', date_of_birth TEXT DEFAULT '', skills_text TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS user_profiles (email TEXT PRIMARY KEY, name TEXT DEFAULT '', university TEXT DEFAULT '', skills TEXT DEFAULT '[]', skill_levels TEXT DEFAULT '{}', interests TEXT DEFAULT '[]', budget TEXT DEFAULT '', availability TEXT DEFAULT '', sustainability TEXT DEFAULT 'Yes', privacy TEXT DEFAULT 'discoverable', github TEXT DEFAULT '', linkedin TEXT DEFAULT '', unstop TEXT DEFAULT '', mail TEXT DEFAULT '', age TEXT DEFAULT '', date_of_birth TEXT DEFAULT '', skills_text TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS gmail_connections (user_email TEXT PRIMARY KEY, token_json TEXT NOT NULL, connected_at TEXT NOT NULL, last_sync TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS gmail_imported_messages (user_email TEXT NOT NULL, message_id TEXT NOT NULL, imported_at TEXT NOT NULL, PRIMARY KEY(user_email,message_id));
    CREATE TABLE IF NOT EXISTS tracked (opportunity_id INTEGER NOT NULL, user_email TEXT NOT NULL DEFAULT 'guest', tracked_at TEXT NOT NULL, PRIMARY KEY(opportunity_id,user_email));
    CREATE TABLE IF NOT EXISTS registrations (
      opportunity_id INTEGER NOT NULL, user_email TEXT NOT NULL, registered_at TEXT NOT NULL,
      PRIMARY KEY(opportunity_id,user_email)
    );
    CREATE TABLE IF NOT EXISTS team_invites (id INTEGER PRIMARY KEY AUTOINCREMENT, sender_email TEXT NOT NULL, recipient_email TEXT NOT NULL, opportunity_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS opportunity_updates (
      id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER NOT NULL, source TEXT NOT NULL,
      updated_at TEXT NOT NULL, summary TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS opportunity_sources (
      opportunity_id INTEGER NOT NULL, channel TEXT NOT NULL, first_seen_at TEXT NOT NULL,
      last_seen_at TEXT NOT NULL, PRIMARY KEY(opportunity_id,channel)
    );
    """)
    opp_cols = {row[1] for row in c.execute("PRAGMA table_info(opportunities)").fetchall()}
    if "source_post_url" not in opp_cols:
        c.execute("ALTER TABLE opportunities ADD COLUMN source_post_url TEXT DEFAULT ''")
    for col in ("contact_name", "contact_email", "contact_info"):
        if col not in opp_cols: c.execute(f"ALTER TABLE opportunities ADD COLUMN {col} TEXT DEFAULT ''")
    tracked_cols = {row[1] for row in c.execute("PRAGMA table_info(tracked)").fetchall()}
    if "user_email" not in tracked_cols:
        c.execute("ALTER TABLE tracked RENAME TO tracked_legacy")
        c.execute("CREATE TABLE tracked (opportunity_id INTEGER NOT NULL, user_email TEXT NOT NULL DEFAULT 'guest', tracked_at TEXT NOT NULL, PRIMARY KEY(opportunity_id,user_email))")
        c.execute("INSERT OR IGNORE INTO tracked SELECT opportunity_id,'guest',tracked_at FROM tracked_legacy")
        c.execute("DROP TABLE tracked_legacy")
    profile_cols = {row[1] for row in c.execute("PRAGMA table_info(profiles)").fetchall()}
    if "skill_levels" not in profile_cols:
        c.execute("ALTER TABLE profiles ADD COLUMN skill_levels TEXT DEFAULT '{}'")
    for col in ["github", "linkedin", "unstop", "mail", "age", "date_of_birth", "skills_text"]:
        if col not in profile_cols:
            c.execute(f"ALTER TABLE profiles ADD COLUMN {col} TEXT DEFAULT ''")
    if c.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0:
        c.execute("INSERT INTO profiles (id,name,university,skills,skill_levels,interests,budget,availability,sustainability,privacy) VALUES (1,?,?,?,?,?,?,?,?,?)", ("", "", json.dumps([]), json.dumps({"React":90,"Python":85,"UI/UX":65}), json.dumps([]), "", "", "Yes", "discoverable"))
    # The POC starts with an empty opportunity feed. Remove only the demo seed rows
    # from older databases so existing user-ingested opportunities are preserved.
    c.execute("DELETE FROM tracked WHERE opportunity_id IN (SELECT id FROM opportunities WHERE source_item_id LIKE 'seed-%')")
    c.execute("DELETE FROM opportunities WHERE source_item_id LIKE 'seed-%'")
    c.commit(); c.close()


def insert_opportunity(c, data: dict, source_item_id: str | None, confidence: float, missing: list[str]):
    now = datetime.now(timezone.utc).isoformat()
    c.execute("""INSERT INTO opportunities
    (source,source_item_id,title,organization,type,description,location,format,deadline,start_date,end_date,fee,currency,payment_type,monetary_benefit,team_size,skills,education,experience,impact_lens,tags,application_url,source_post_url,contact_name,contact_email,contact_info,verified,ai_confidence,missing_fields,created_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        data.get("source", ""), source_item_id, data.get("title", "Untitled"), data.get("organization", ""),
        data.get("type", "opportunity"), data.get("description", ""), data.get("location", ""), data.get("format", ""),
        data.get("deadline", ""), data.get("start_date", ""), data.get("end_date", ""), data.get("fee", ""), data.get("currency", ""), data.get("payment_type", ""), data.get("monetary_benefit", ""),
        data.get("team_size", ""), json.dumps(data.get("skills", [])), json.dumps(data.get("education", [])), data.get("experience", ""),
        json.dumps(data.get("impact_lens", [])), json.dumps(data.get("tags", [])), data.get("application_url", ""), data.get("source_post_url", ""), data.get("contact_name", ""), data.get("contact_email", ""), data.get("contact_info", ""), 1,
        confidence, json.dumps(missing), now
    ))
    return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def normalize(raw: dict, source: str):
    out = dict(raw)
    for key, value in list(out.items()):
        if isinstance(value, str):
            out[key] = value.replace("\\\\n", "\n").replace("\\\\r", "\n").strip()
    out["source"] = source
    # Keep the original source URL available in the opportunity description as well as
    # the dedicated field, so students can open it for further information.
    url = (out.get("application_url") or "").strip()
    source_url = (out.get("source_post_url") or "").strip()
    description = (out.get("description") or "").strip()
    if url and url not in description:
        description = (description + "\n\nFurther information / application: " + url).strip()
    if source_url and source_url not in description:
        description = (description + "\n\nOriginal source post: " + source_url).strip()
    if source.lower().startswith("mail"):
        description = concise_description(description)
    out["description"] = description
    # A short, explicit list of critical fields to verify after extraction.
    critical = ["title", "organization", "deadline", "application_url", "format"]
    missing = out.get("missing_fields", [])
    if not isinstance(missing, list):
        missing = []
    for key in critical:
        value = out.get(key)
        if (value is None or (isinstance(value, str) and not value.strip())) and key not in missing:
            missing.append(key)
    out["missing_fields"] = missing
    for k in ["skills","education","impact_lens","tags"]:
        value = out.get(k, [])
        if isinstance(value, str):
            out[k] = [x.strip() for x in re.split(r",|;|\n", value) if x.strip()]
        elif not isinstance(value, list):
            out[k] = []
    return out


def fallback_extract(text: str):
    def grab(patterns):
        for p in patterns:
            m = re.search(p, text, re.I | re.M)
            if m: return m.group(1).strip()
        return ""
    title = grab([r"(?:subject|title)\s*:\s*(.+)", r"^(.{5,100})$"])
    org = grab([r"(?:organization|company|from)\s*:\s*(.+)"])
    deadline = grab([r"(?:deadline|closes|applications close)\s*[:\-]\s*(.+)"])
    location = grab([r"(?:location|where)\s*[:\-]\s*(.+)"])
    fee = grab([r"(?:fee|cost)\s*[:\-]\s*(.+)"])
    skills = grab([r"skills?\s*[:\-]\s*(.+)"])
    return {
        "title": title or "Untitled opportunity", "organization": org, "type": "opportunity", "description": text.strip(),
        "location": location, "format": "", "deadline": deadline, "start_date": "", "end_date": "", "fee": fee,
        "currency": "", "team_size": "", "skills": [x.strip() for x in re.split(r",|;", skills) if x.strip()],
        "education": [], "experience": "", "impact_lens": [], "tags": [], "application_url": "", "source_post_url": "",
        "confidence": 0.25, "missing_fields": ["organization", "deadline", "format", "skills"]
    }


def groq_extract(text: str):
    if not GROQ_API_KEY:
        return None
    from openai import OpenAI
    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
    system = """You are the SkillSync opportunity extraction agent. Extract facts from an unstructured email, announcement, or listing into the supplied schema. Never invent missing facts; use null or empty arrays for unknown values and never make up a URL. Return a concise, student-facing description of at most 2-4 short sentences describing what the opportunity is, who can apply, and the key action. Do not copy email headers, forwarded-message separators, To/Cc recipient lists, email addresses, signatures, disclaimers, tracking text, or repeated boilerplate into the description. Prefer the opportunity's actual title over an email subject prefixed with Fwd/FW/Invitation. Normalize obvious values but preserve meaning. confidence is 0-1. missing_fields lists important fields not confidently extracted. Flag absent title, organization, deadline, application_url, or format."""
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0,
        messages=[{"role":"system","content":system},{"role":"user","content":text}],
        response_format={"type":"json_schema","json_schema":{"name":"skillsync_opportunity","strict":True,"schema":SCHEMA}},
    )
    return json.loads(resp.choices[0].message.content)




def parse_event_date(value):
    if not value: return None
    value=str(value).strip()
    for fmt in ("%Y-%m-%d","%d/%m/%Y","%d/%m/%y","%m/%d/%Y","%d-%m-%Y","%d-%m-%y","%B %d, %Y","%b %d, %Y"):
        try: return datetime.strptime(value,fmt).date()
        except Exception: pass
    try: return datetime.fromisoformat(value.replace("Z","+00:00")).date()
    except Exception: return None

def duration_months(start, end):
    a,b=parse_event_date(start),parse_event_date(end)
    if not a or not b or b<a: return None
    return max(0.1, round(((b-a).days+1)/30.4375, 1))


def row_to_dict(r):
    d = dict(r)
    for k in ["skills","education","impact_lens","tags","missing_fields"]:
        try: d[k] = json.loads(d[k] or "[]")
        except Exception: d[k] = []
    d["verified"] = bool(d.get("verified"))
    d["tracked"] = False
    d["duration_months"] = duration_months(d.get("start_date"), d.get("end_date"))
    return d


def current_email(request):
    email=(request.headers.get("x-user-email") or "guest").strip().lower()
    return email[:254] if email else "guest"

def profile(email="guest"):
    c=conn()
    if email == "guest": r=c.execute("SELECT * FROM profiles WHERE id=1").fetchone()
    else:
        c.execute("INSERT OR IGNORE INTO user_profiles(email) VALUES(?)",(email,)); c.commit()
        r=c.execute("SELECT * FROM user_profiles WHERE email=?",(email,)).fetchone()
    c.close(); d=dict(r) if r else {}
    for k in ["skills","interests"]:
        try: d[k]=json.loads(d.get(k) or "[]")
        except Exception: d[k]=[]
    try: d["skill_levels"]=json.loads(d.get("skill_levels") or "{}")
    except Exception: d["skill_levels"]={}
    return d


def score(opp, email="guest"):
    """Generous relevance scoring: surface remotely related opportunities, but keep direct matches ranked higher."""
    p = profile(email)
    levels = p.get("skill_levels") or {}
    profile_terms = []
    profile_terms.extend(p.get("skills") or [])
    profile_terms.extend(p.get("interests") or [])
    profile_terms.extend(x.strip() for x in re.split(r"[,;\\n]", p.get("skills_text") or "") if x.strip())
    profile_terms.extend(k for k, v in levels.items() if int(v or 0) >= 15)
    if not profile_terms:
        return 0, 0

    opp_terms = list(opp.get("skills") or []) + list(opp.get("tags") or [])
    opp_text = " ".join([
        str(opp.get("title") or ""), str(opp.get("description") or ""),
        str(opp.get("type") or ""), str(opp.get("organization") or ""),
        " ".join(str(x) for x in (opp.get("impact_lens") or [])),
        " ".join(str(x) for x in opp_terms)
    ]).lower()
    normalize = lambda x: re.sub(r"[^a-z0-9+#./ -]", "", str(x).lower()).strip()
    normalized = {normalize(x) for x in profile_terms if normalize(x)}
    matched = []
    for term in normalized:
        if any(normalize(x) == term for x in opp_terms) or term in opp_text:
            matched.append(term)

    # Lightweight concept groups intentionally broaden matches beyond exact words.
    concept_groups = [
        {"software", "coding", "programming", "developer", "development", "technology", "tech", "computer science", "ai", "machine learning", "data science"},
        {"design", "ui", "ux", "ui/ux", "product design", "creative", "visual design"},
        {"business", "entrepreneurship", "startup", "management", "marketing", "finance", "consulting"},
        {"research", "science", "engineering", "innovation", "laboratory"},
        {"environment", "environmental", "sustainability", "climate", "green", "social impact", "community"},
        {"leadership", "teamwork", "communication", "volunteering", "organizing", "events"},
        {"writing", "content", "journalism", "media", "storytelling"},
        {"education", "teaching", "learning", "mentoring", "training"},
    ]
    broad_hits = []
    for term in normalized:
        for group in concept_groups:
            if term in group and any(word in opp_text for word in group if len(word) > 2):
                broad_hits.append(term)
                break

    # Direct matches score strongly; broad/conceptual matches score modestly but remain visible.
    direct_count = len(set(matched))
    broad_count = len(set(broad_hits) - set(matched))
    if direct_count == 0 and broad_count == 0:
        # If a user has supplied interests/profile text, keep a low-confidence discovery tier
        # rather than hiding every event due to sparse extraction metadata.
        score_value = 30
        overlap = 1
    else:
        total = max(1, len(normalized))
        score_value = min(98, 58 + round(24 * direct_count / total) + min(16, broad_count * 5))
        overlap = direct_count + broad_count
    if p.get("sustainability") == "Yes" and any(str(x).lower() in {"environmental", "social", "community", "sustainability"} for x in (opp.get("impact_lens") or []) + (opp.get("tags") or [])):
        score_value = min(100, score_value + 4)
    return max(30, min(100, score_value)), overlap


@app.on_event("startup")
def startup(): init_db()

@app.get("/api/health")
def health(): return {"ok": True, "groq_configured": bool(GROQ_API_KEY), "model": GROQ_MODEL}

@app.post("/api/auth/google")
def google_sign_in(data: dict):
    """Verify a Google Identity Services ID token and provision the local SkillSync profile."""
    credential = str(data.get("credential") or "").strip()
    if not credential:
        raise HTTPException(status_code=400, detail="Missing Google credential.")
    client_id = os.getenv("GOOGLE_CLIENT_ID", "113605544241-cgpch2vhnk375ap7f524j5f4rl5mdj52.apps.googleusercontent.com").strip()
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        claims = google_id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
    except ImportError:
        raise HTTPException(status_code=503, detail="Google sign-in dependency is missing. Run backend/install_dependencies.bat.")
    except Exception:
        raise HTTPException(status_code=401, detail="Google credential is invalid or expired. Please try again.")
    email = str(claims.get("email") or "").strip().lower()
    if not email or not claims.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google must provide a verified email address.")
    name = str(claims.get("name") or claims.get("given_name") or email.split("@")[0]).strip()
    c = conn()
    c.execute("INSERT OR IGNORE INTO user_profiles(email,name) VALUES(?,?)", (email, name))
    c.execute("UPDATE user_profiles SET name=CASE WHEN name IS NULL OR name='' THEN ? ELSE name END WHERE email=?", (name, email))
    c.commit(); c.close()
    return {"ok": True, "email": email, "name": name}


def gmail_credentials_from_json(token_json: str):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    creds = Credentials.from_authorized_user_info(json.loads(token_json), GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
    return creds


@app.get("/api/gmail/status")
def gmail_status(request: Request):
    email = current_email(request)
    if email == "guest": raise HTTPException(status_code=401, detail="Please sign in to SkillSync first.")
    c = conn(); row = c.execute("SELECT connected_at,last_sync FROM gmail_connections WHERE lower(user_email)=lower(?)", (email,)).fetchone(); c.close()
    return {"connected": bool(row), "connected_at": row["connected_at"] if row else None, "last_sync": row["last_sync"] if row else None}


@app.get("/api/gmail/connect")
def gmail_connect(request: Request):
    email = current_email(request)
    if email == "guest": raise HTTPException(status_code=401, detail="Please sign in to SkillSync first.")
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Gmail OAuth isn't configured yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env, and register the callback URL.")
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise HTTPException(status_code=503, detail="Gmail packages are missing. Run: python -m pip install google-auth-oauthlib google-api-python-client google-auth-httplib2")
    state = secrets.token_urlsafe(32)
    flow = Flow.from_client_config({"web": {"client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": [GMAIL_REDIRECT_URI]}}, scopes=GMAIL_SCOPES, state=state)
    flow.redirect_uri = GMAIL_REDIRECT_URI
    url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    # PKCE verifier must be retained and supplied to the token exchange.
    GMAIL_OAUTH_STATES[state] = {"email": email, "code_verifier": flow.code_verifier}
    return {"url": url}


@app.get("/api/gmail/callback")
def gmail_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    auth_state = GMAIL_OAUTH_STATES.pop(state, None)
    email = auth_state.get("email") if isinstance(auth_state, dict) else None
    code_verifier = auth_state.get("code_verifier") if isinstance(auth_state, dict) else None
    frontend = "http://127.0.0.1:5173/index.html"
    if error or not code or not email:
        # Log only boolean indicators; never log OAuth codes, state values, or tokens.
        print(
            "Gmail OAuth callback incomplete: "
            f"error_present={bool(error)}, code_present={bool(code)}, "
            f"state_matched={bool(email)}"
        )
        return RedirectResponse(frontend + "?gmail=error", status_code=303)

    c = None
    try:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [GMAIL_REDIRECT_URI],
                }
            },
            scopes=GMAIL_SCOPES,
            state=state,
            code_verifier=code_verifier,
        )
        flow.redirect_uri = GMAIL_REDIRECT_URI
        flow.fetch_token(code=code)
        token_json = flow.credentials.to_json()

        c = conn()
        now = datetime.now(timezone.utc).isoformat()
        c.execute(
            """INSERT INTO gmail_connections
               (user_email, token_json, connected_at, last_sync)
               VALUES (?, ?, ?, '')
               ON CONFLICT(user_email) DO UPDATE SET
               token_json=excluded.token_json,
               connected_at=excluded.connected_at""",
            (email, token_json, now),
        )
        c.commit()
        print("Gmail OAuth callback succeeded: connection saved.")
        return RedirectResponse(frontend + "?gmail=connected", status_code=303)
    except Exception as exc:
        # Print exception type/message to the local backend terminal for diagnosis.
        # Do not print request URLs, authorization codes, state, or token contents.
        print(f"Gmail OAuth callback failed: {type(exc).__name__}: {exc}")
        return RedirectResponse(frontend + "?gmail=error", status_code=303)
    finally:
        if c is not None:
            c.close()


def clean_gmail_body(text: str) -> str:
    """Remove markup and mail-routing/forwarding noise before AI extraction."""
    text = html_lib.unescape(str(text or ""))
    text = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</p\s*>|</div\s*>|</li\s*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    # Strip forwarded metadata header block but keep the forwarded message body.
    forward = re.search(r"(?im)^\s*-{2,}\s*Forwarded message\s*-{2,}\s*$", text)
    if forward:
        tail = text[forward.end():]
        # Gmail-style forwarded headers end at the first blank line.
        lines = tail.splitlines()
        cut = None
        for i, line in enumerate(lines):
            if not line.strip():
                cut = i + 1
                break
        if cut is not None:
            text = "\n".join(lines[cut:])
    # Remove common routing/header lines and their wrapped continuation lines.
    lines = text.splitlines()
    cleaned, skipping_recipients = [], False
    for line in lines:
        stripped = line.strip()
        if re.match(r"(?i)^(from|to|cc|bcc|date|sent|subject|reply-to):", stripped):
            skipping_recipients = bool(re.match(r"(?i)^(to|cc|bcc):", stripped))
            continue
        if skipping_recipients and stripped and (
            "@" in stripped or re.search(r"(?i)\b(?:etc|cmpn|extc|inft|ai_and_ds|au_and_ro)\b", stripped)
            or stripped.startswith(("<", ">", ","))
        ):
            continue
        skipping_recipients = False
        if re.match(r"(?i)^-{3,}\s*(original message|forwarded message)\s*-{0,}$", stripped):
            continue
        cleaned.append(line)
    text = "\n".join(cleaned)
    text = re.sub(r"(?im)^\s*(unsubscribe|this email and any attachments|confidentiality notice).*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def concise_description(value: str, max_chars: int = 1100) -> str:
    value = clean_gmail_body(value)
    # Keep only useful leading content; trim excessive repeated email material.
    value = re.sub(r"(?im)^\s*(original source post url|source post url)\s*:.*$", "", value)
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    if len(value) > max_chars:
        value = value[:max_chars].rsplit(" ", 1)[0].rstrip() + "…"
    return value


def _gmail_decode_part(part):
    data = (part.get("body") or {}).get("data")
    if data:
        try: return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
        except Exception: return ""
    out = []
    for child in part.get("parts") or []: out.append(_gmail_decode_part(child))
    return "\n".join(x for x in out if x)


@app.post("/api/gmail/sync")
def gmail_sync(request: Request):
    email = current_email(request)
    if email == "guest": raise HTTPException(status_code=401, detail="Please sign in to SkillSync first.")
    c = conn(); row = c.execute("SELECT token_json FROM gmail_connections WHERE lower(user_email)=lower(?)", (email,)).fetchone(); c.close()
    if not row: raise HTTPException(status_code=400, detail="Connect Gmail first.")
    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        creds = gmail_credentials_from_json(row["token_json"])
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        # Only scan recent messages likely to contain student opportunities; never send or modify mail.
        query = 'newer_than:90d {hackathon internship scholarship fellowship competition workshop "student opportunity"}'
        listed = service.users().messages().list(userId="me", q=query, maxResults=40).execute()
        messages = listed.get("messages", [])
    except ImportError:
        raise HTTPException(status_code=503, detail="Gmail packages are missing. Run: python -m pip install google-auth-oauthlib google-api-python-client google-auth-httplib2")
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Gmail could not be read. Reconnect Gmail and check OAuth configuration.")
    imported = 0; skipped = 0; errors = 0
    for item in messages:
        mid = item.get("id") or ""
        c = conn()
        if c.execute("SELECT 1 FROM gmail_imported_messages WHERE user_email=? AND message_id=?", (email, mid)).fetchone():
            c.close(); skipped += 1; continue
        try:
            msg = service.users().messages().get(userId="me", id=mid, format="full").execute()
            payload = msg.get("payload") or {}
            headers = {h.get("name", "").lower(): h.get("value", "") for h in payload.get("headers", [])}
            subject = headers.get("subject", "Opportunity email")
            sender = headers.get("from", "")
            body = clean_gmail_body(_gmail_decode_part(payload))
            if not body.strip(): body = clean_gmail_body(subject)
            # Subject is kept as a hint, but sender routing metadata and forwarded
            # recipient dumps are excluded from the text sent to the extraction model.
            clean_subject = re.sub(r"(?i)^(?:fwd?|fw|invitation)\s*:\s*", "", subject).strip()
            raw = f"Subject: {clean_subject}\n\n{body}".strip()
            try:
                extracted = groq_extract(raw)
                if not extracted: raise ValueError("AI extraction unavailable; using fallback parser")
                ai_used = True
            except Exception as exc:
                extracted = fallback_extract(raw); extracted["ai_error"] = str(exc); ai_used = False
            extracted = normalize(extracted, "Mail")
            source_id = "gmail:" + mid
            oid, status, changed = merge_or_insert_opportunity(c, extracted, "Mail-" + source_id, float(extracted.get("confidence") or 0), extracted.get("missing_fields", []))
            c.execute("INSERT INTO raw_items(source,source_item_id,subject,raw_text,ai_extracted,processed_at) VALUES(?,?,?,?,?,?)", ("Mail", source_id, subject, raw, json.dumps(extracted, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
            c.execute("INSERT OR IGNORE INTO gmail_imported_messages(user_email,message_id,imported_at) VALUES(?,?,?)", (email, mid, datetime.now(timezone.utc).isoformat()))
            c.commit(); imported += 1
        except Exception:
            errors += 1
        finally:
            c.close()
    c = conn(); c.execute("UPDATE gmail_connections SET token_json=?,last_sync=? WHERE lower(user_email)=lower(?)", (creds.to_json(), datetime.now(timezone.utc).isoformat(), email)); c.commit(); c.close()
    return {"ok": True, "scanned": len(messages), "imported": imported, "already_seen": skipped, "errors": errors, "message": f"Gmail sync complete: imported {imported} email(s), skipped {skipped} already processed."}


@app.get("/api/opportunities")
def opportunities(request: Request, source: Optional[str]=None):
    email=current_email(request)
    c=conn()
    today=datetime.now().date()
    for row in c.execute("SELECT id,end_date,deadline FROM opportunities").fetchall():
        oid=row["id"]; event_end=parse_event_date(row["end_date"]); deadline=parse_event_date(row["deadline"])
        registered=bool(c.execute("SELECT 1 FROM registrations WHERE opportunity_id=? AND user_email=?",(oid,email)).fetchone())
        if (event_end and event_end < today) or (deadline and deadline < today and not registered):
            c.execute("DELETE FROM opportunities WHERE id=?",(oid,))
            c.execute("DELETE FROM opportunity_sources WHERE opportunity_id=?",(oid,))
            c.execute("DELETE FROM opportunity_updates WHERE opportunity_id=?",(oid,))
            c.execute("DELETE FROM tracked WHERE opportunity_id=?",(oid,))
            c.execute("DELETE FROM registrations WHERE opportunity_id=?",(oid,))
    c.commit()
    rows=c.execute("SELECT * FROM opportunities ORDER BY id DESC").fetchall(); tracked={r[0] for r in c.execute("SELECT opportunity_id FROM tracked WHERE user_email=?",(email,)).fetchall()}; source_counts={r[0]:r[1] for r in c.execute("SELECT opportunity_id,COUNT(*) FROM opportunity_sources GROUP BY opportunity_id").fetchall()}; c.close()
    c2=conn()
    registered={r[0] for r in c2.execute("SELECT opportunity_id FROM registrations WHERE user_email=?",(email,)).fetchall()}
    c2.close()
    out=[]
    for r in rows:
        d=row_to_dict(r)
        d["registered"]=d["id"] in registered
        d["hitScore"]=source_counts.get(d["id"], max(1,len([x for x in str(d.get("source") or "").split(",") if x.strip()])))
        if source and d["source"] != source: continue
        d["tracked"]=d["id"] in tracked
        s, overlap=score(d,email); d["matchScore"]=s; d["whyFit"]=f"{overlap} profile skill/interest overlaps detected." if overlap else "No direct profile overlap detected yet."
        out.append(d)
    return out

@app.get("/api/profile")
def get_profile(request: Request): return profile(current_email(request))

@app.put("/api/profile")
def put_profile(data: ProfileIn, request: Request):
    email=current_email(request); levels={k:max(0,min(100,int(v))) for k,v in data.skill_levels.items()}
    vals=(data.name,data.university,json.dumps(data.skills),json.dumps(levels),json.dumps(data.interests),data.budget,data.availability,data.sustainability,data.privacy,data.github,data.linkedin,data.unstop,data.mail,data.age,data.date_of_birth,data.skills_text)
    c=conn()
    if email == "guest": c.execute("UPDATE profiles SET name=?, university=?, skills=?, skill_levels=?, interests=?, budget=?, availability=?, sustainability=?, privacy=?, github=?, linkedin=?, unstop=?, mail=?, age=?, date_of_birth=?, skills_text=? WHERE id=1",vals)
    else: c.execute("INSERT INTO user_profiles(email,name,university,skills,skill_levels,interests,budget,availability,sustainability,privacy,github,linkedin,unstop,mail,age,date_of_birth,skills_text) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET name=excluded.name,university=excluded.university,skills=excluded.skills,skill_levels=excluded.skill_levels,interests=excluded.interests,budget=excluded.budget,availability=excluded.availability,sustainability=excluded.sustainability,privacy=excluded.privacy,github=excluded.github,linkedin=excluded.linkedin,unstop=excluded.unstop,mail=excluded.mail,age=excluded.age,date_of_birth=excluded.date_of_birth,skills_text=excluded.skills_text",(email,*vals))
    c.commit(); c.close(); return profile(email)



def merge_or_insert_opportunity(c, payload, source_tag, confidence, missing):
    title=(payload.get("title") or "").strip(); org=(payload.get("organization") or "").strip()
    channel=(source_tag.split("-")[0] or "unknown").lower()
    def norm(s): return re.sub(r"[^a-z0-9]+", " ",(s or "").lower()).strip()
    def tokens(s):
        stop={"the","a","an","for","and","of","in","2026","2027","updated","applications","application","open"}
        return {t for t in norm(s).split() if t not in stop and len(t)>1}
    def similarity(a,b):
        ta,tb=tokens(a),tokens(b)
        return len(ta & tb)/max(1,len(ta | tb))
    candidate=None
    new_url=norm(payload.get("application_url") or "")
    for row in c.execute("SELECT * FROM opportunities").fetchall():
        rd=dict(row); oo,no=norm(rd.get("organization")),norm(org)
        same_org=bool(oo and no and oo==no)
        old_url=norm(rd.get("application_url") or "")
        same_url=bool(new_url and old_url and new_url==old_url)
        sim=similarity(rd.get("title"),title)
        # Treat identical application links or semantically similar titles as the same event.
        if same_url or (sim >= 0.55 and (same_org or not oo or not no or sim >= 0.72)):
            candidate=rd; break
    now=datetime.now(timezone.utc).isoformat()
    if not candidate:
        oid=insert_opportunity(c,payload,source_tag,confidence,missing)
        c.execute("INSERT OR IGNORE INTO opportunity_sources(opportunity_id,channel,first_seen_at,last_seen_at) VALUES(?,?,?,?)",(oid,channel,now,now))
        return oid,"created",False
    oid=candidate["id"]
    conflict_fields=[]
    for key in ("start_date","end_date","deadline","location","format","fee","payment_type","monetary_benefit"):
        old_value=str(candidate.get(key) or "").strip()
        new_value=str(payload.get(key) or "").strip()
        if old_value and new_value and old_value.lower()!=new_value.lower():
            conflict_fields.append(key.replace("_"," "))
    fields=["source_item_id","title","organization","type","description","location","format","deadline","start_date","end_date","fee","currency","payment_type","monetary_benefit","team_size","skills","education","experience","impact_lens","tags","application_url","source_post_url","contact_name","contact_email","contact_info","missing_fields"]
    updates={}
    for key in fields:
        nv=payload.get(key); ov=candidate.get(key)
        if key in {"skills","education","impact_lens","tags","missing_fields"}:
            oldlist=json.loads(ov or "[]") if isinstance(ov,str) else (ov or [])
            newlist=nv if isinstance(nv,list) else []
            nv=(json.dumps(list(dict.fromkeys(oldlist+newlist)),ensure_ascii=False) if key!="missing_fields" and newlist else json.dumps(newlist,ensure_ascii=False) if key=="missing_fields" and newlist else ov)
        if nv not in (None,"",[],{}) and nv!=ov: updates[key]=nv
    if conflict_fields:
        desc=str(payload.get("description") or candidate.get("description") or "")
        clause="\n\nCoordinator confirmation required: updated sources contain conflicting information for "+", ".join(conflict_fields)+". Please confirm the latest details with the event coordinator."
        if "Coordinator confirmation required:" not in desc:
            updates["description"]=(desc+clause).strip()
    old_sources={r[0] for r in c.execute("SELECT channel FROM opportunity_sources WHERE opportunity_id=?",(oid,)).fetchall()}
    if not old_sources:
        old_sources={x.strip().split("-")[0].lower() for x in str(candidate.get("source") or "").split(",") if x.strip()}
        for old in old_sources:
            c.execute("INSERT OR IGNORE INTO opportunity_sources(opportunity_id,channel,first_seen_at,last_seen_at) VALUES(?,?,?,?)",(oid,old,now,now))
    c.execute("INSERT INTO opportunity_sources(opportunity_id,channel,first_seen_at,last_seen_at) VALUES(?,?,?,?) ON CONFLICT(opportunity_id,channel) DO UPDATE SET last_seen_at=excluded.last_seen_at",(oid,channel,now,now))
    updates["source"]=", ".join(sorted(old_sources|{channel}))
    changed=[k for k,v in updates.items() if k!="source" and v!=candidate.get(k)]
    c.execute("UPDATE opportunities SET "+",".join(f"{k}=?" for k in updates)+",created_at=? WHERE id=?",(*updates.values(),now,oid))
    if changed:
        c.execute("INSERT INTO opportunity_updates(opportunity_id,source,updated_at,summary) VALUES(?,?,?,?)",(oid,channel,now,"Updated fields: "+", ".join(changed)))
        return oid,"updated",True
    if channel not in old_sources:
        c.execute("INSERT INTO opportunity_updates(opportunity_id,source,updated_at,summary) VALUES(?,?,?,?)",(oid,channel,now,"Additional source found: "+channel))
        return oid,"updated",True
    return oid,"duplicate",False

@app.post("/api/ingest/structured")
def ingest_structured(data: OpportunityIn):
    payload=normalize(data.model_dump(),data.source)
    c=conn()
    oid,status,changed=merge_or_insert_opportunity(c,payload,data.source+"-manual",1.0,payload.get("missing_fields",[]))
    if not payload.get("source_post_url"):
        c.execute("UPDATE opportunities SET source_post_url=COALESCE(NULLIF(source_post_url,''),?) WHERE id=?", (f"http://127.0.0.1:5173/terminal.html?source={data.source}&item={oid}", oid))
    raw=json.dumps(payload, ensure_ascii=False)
    c.execute("INSERT INTO raw_items(source,source_item_id,subject,raw_text,ai_extracted,processed_at) VALUES(?,?,?,?,?,?)",(data.source,data.source+"-manual",payload["title"],raw,raw,datetime.now(timezone.utc).isoformat()))
    c.commit(); c.close()
    return {"status":status,"opportunity_id":oid,"ai_used":False,"updated":changed,"extracted":payload}

@app.post("/api/ingest/unstructured")
def ingest_unstructured(data: UnstructuredIn):
    raw=f"Subject: {data.subject}\\nFrom: {data.sender}\\nOriginal source post URL: {data.source_post_url}\\n\\n{data.body}".strip()
    try:
        extracted=groq_extract(raw); ai_used=True
    except Exception as e:
        extracted=fallback_extract(raw); extracted["ai_error"]=str(e); ai_used=False
    extracted["source_post_url"]=data.source_post_url or extracted.get("source_post_url","")
    extracted=normalize(extracted,data.source)
    c=conn()
    oid,status,changed=merge_or_insert_opportunity(c,extracted,data.source+"-ai",float(extracted.get("confidence") or 0),extracted.get("missing_fields",[]))
    if not extracted.get("source_post_url"):
        c.execute("UPDATE opportunities SET source_post_url=COALESCE(NULLIF(source_post_url,''),?) WHERE id=?", (f"http://127.0.0.1:5173/terminal.html?source={data.source}&item={oid}", oid))
    c.execute("INSERT INTO raw_items(source,source_item_id,subject,raw_text,ai_extracted,processed_at) VALUES(?,?,?,?,?,?)",(data.source,data.source+"-ai",data.subject,raw,json.dumps(extracted,ensure_ascii=False),datetime.now(timezone.utc).isoformat()))
    c.commit(); c.close()
    return {"status":status,"opportunity_id":oid,"extracted":extracted,"ai_used":ai_used,"updated":changed}

@app.get("/api/opportunities/{oid}")
def get_opportunity(oid:int):
    c=conn(); r=c.execute("SELECT * FROM opportunities WHERE id=?",(oid,)).fetchone(); c.close()
    if not r: raise HTTPException(404,"Opportunity not found")
    return row_to_dict(r)

@app.post("/api/opportunities/{oid}/track")
def track(oid:int, request: Request):
    email=current_email(request)
    c=conn(); exists=c.execute("SELECT id FROM opportunities WHERE id=?",(oid,)).fetchone()
    if not exists: c.close(); raise HTTPException(404,"Opportunity not found")
    c.execute("INSERT OR REPLACE INTO tracked(opportunity_id,user_email,tracked_at) VALUES (?,?,?)",(oid,email,datetime.now(timezone.utc).isoformat())); c.commit(); c.close(); return {"ok":True}

@app.delete("/api/opportunities/{oid}/track")
def untrack(oid:int, request: Request):
    email=current_email(request)
    c=conn(); c.execute("DELETE FROM tracked WHERE opportunity_id=? AND user_email=?",(oid,email)); c.commit(); c.close(); return {"ok":True}

@app.post("/api/opportunities/{oid}/register")
def register_opportunity(oid:int, request: Request):
    email=current_email(request)
    c=conn()
    if not c.execute("SELECT id FROM opportunities WHERE id=?",(oid,)).fetchone():
        c.close(); raise HTTPException(404,"Opportunity not found")
    c.execute("INSERT OR REPLACE INTO registrations(opportunity_id,user_email,registered_at) VALUES(?,?,?)",(oid,email,datetime.now(timezone.utc).isoformat()))
    c.commit(); c.close(); return {"ok":True}

@app.delete("/api/opportunities/{oid}/register")
def unregister_opportunity(oid:int, request: Request):
    email=current_email(request); c=conn()
    c.execute("DELETE FROM registrations WHERE opportunity_id=? AND user_email=?",(oid,email))
    c.commit(); c.close(); return {"ok":True}

@app.get("/api/notifications")
def notifications(request: Request):
    email=current_email(request); today=datetime.now().date()
    c=conn()
    rows=c.execute("SELECT o.* FROM opportunities o ORDER BY o.id DESC").fetchall()
    registered={r[0] for r in c.execute("SELECT opportunity_id FROM registrations WHERE user_email=?",(email,)).fetchall()}
    updates=c.execute("SELECT u.*,o.title FROM opportunity_updates u JOIN opportunities o ON o.id=u.opportunity_id ORDER BY u.id DESC LIMIT 50").fetchall()
    c.close()
    result=[]
    for row in rows:
        o=row_to_dict(row); oid=o["id"]
        for field,label in (("start_date","starts"),("deadline","deadline")):
            raw=o.get(field)
            if not raw or (field=="deadline" and oid in registered): continue
            value=str(raw).strip()
            parsed=None
            for fmt in ("%Y-%m-%d","%d/%m/%y","%d/%m/%Y","%m/%d/%y","%m/%d/%Y","%d-%m-%Y","%d-%m-%y","%B %d, %Y","%b %d, %Y"):
                try: parsed=datetime.strptime(value,fmt).date(); break
                except Exception: pass
            if parsed is None:
                try: parsed=datetime.fromisoformat(value.replace("Z","+00:00")).date()
                except Exception: continue
            days=(parsed-today).days
            if field=="start_date" and 0 <= days <= 5:
                result.append({"id":f"start-{oid}","opportunity_id":oid,"title":o.get("title"),"message":f"{o.get('title')} starts in {days} day(s).","kind":"start"})
            if field=="deadline" and days==0 and oid not in registered:
                result.append({"id":f"deadline-{oid}","opportunity_id":oid,"title":o.get("title"),"message":f"Registration deadline is today for {o.get('title')}. Mark Registered if you've signed up.","kind":"deadline"})
    for u in updates:
        result.append({"id":f"update-{u['id']}","opportunity_id":u["opportunity_id"],"title":u["title"],"message":f"{u['title']} was updated from {u['source']}: {u['summary']}","kind":"update"})
    c=conn()
    invites=c.execute("SELECT i.id,i.sender_email,i.opportunity_id,i.created_at,o.title,p.name FROM team_invites i JOIN opportunities o ON o.id=i.opportunity_id LEFT JOIN user_profiles p ON p.email=i.sender_email WHERE lower(i.recipient_email)=lower(?) AND i.status='pending' ORDER BY i.id DESC",(email,)).fetchall()
    c.close()
    for i in invites:
        result.insert(0,{"id":f"invite-{i['id']}","kind":"team_invite","message":f"{i['name'] or i['sender_email']} asks: Do you want to team up for {i['title']}?","invite_id":i['id'],"opportunity_id":i['opportunity_id'],"sender_email":i['sender_email']})
    # Also surface sent-invitation status to the sender so the action is verifiable.
    c=conn()
    sent=c.execute("SELECT i.id,i.status,i.created_at,o.title,p.name FROM team_invites i JOIN opportunities o ON o.id=i.opportunity_id LEFT JOIN user_profiles p ON p.email=i.recipient_email WHERE i.sender_email=? ORDER BY i.id DESC LIMIT 20",(email,)).fetchall()
    c.close()
    for i in sent:
        result.append({"id":f"sent-invite-{i['id']}","kind":"team_invite_status","message":f"Invitation to {i['name'] or 'your teammate'} for {i['title']}: {i['status']}.","invite_id":i['id'],"status":i['status'],"opportunity_title":i['title']})
    return result

@app.get("/api/peers")
def peers(request: Request, search: str = "", opportunity_id: int | None = None):
    email=current_email(request); c=conn()
    me=profile(email)
    query="SELECT * FROM user_profiles WHERE email<>? AND (privacy='public' OR privacy='discoverable' OR privacy='teams')" if opportunity_id is not None else "SELECT * FROM user_profiles WHERE email<>? AND (privacy='public' OR privacy='discoverable')"
    args=[email]
    if search.strip(): query += " AND lower(name) LIKE ?"; args.append("%"+search.strip().lower()+"%")
    rows=c.execute(query,args).fetchall(); result=[]
    for row in rows:
        d=dict(row)
        if opportunity_id is not None:
            if d.get('privacy') not in ('public','discoverable','teams'): continue
            if not c.execute("SELECT 1 FROM tracked WHERE opportunity_id=? AND user_email=?",(opportunity_id,d['email'])).fetchone(): continue
        skills=json.loads(d.get('skills') or '[]')
        try: skills += [x.strip() for x in re.split(r'[,;\n]',d.get('skills_text') or '') if x.strip()]
        except Exception: pass
        result.append({"email":d['email'],"name":d.get('name') or d['email'].split('@')[0],"university":d.get('university') or '',"skills":list(dict.fromkeys(skills)),"avatar":''.join(x[0] for x in (d.get('name') or '?').split()[:2]).upper(),"privacy":d.get('privacy'),"synergy":"Potential teammate"})
    c.close(); return result

@app.post("/api/team-invites")
def create_team_invite(data: dict, request: Request):
    sender=current_email(request); recipient=str(data.get('recipient_email') or '').strip().lower(); oid=int(data.get('opportunity_id') or 0)
    if sender=='guest': raise HTTPException(401,'Please log in first')
    if not recipient or recipient==sender: raise HTTPException(400,'Choose another user')
    c=conn(); peer=c.execute("SELECT privacy FROM user_profiles WHERE lower(email)=lower(?)",(recipient,)).fetchone()
    if not peer or peer['privacy'] not in ('public','discoverable','teams'): c.close(); raise HTTPException(404,'Peer profile is not available')
    if not c.execute("SELECT 1 FROM tracked WHERE opportunity_id=? AND user_email=?",(oid,sender)).fetchone(): c.close(); raise HTTPException(400,'Track the hackathon before inviting a teammate')
    if not c.execute("SELECT 1 FROM tracked WHERE opportunity_id=? AND user_email=?",(oid,recipient)).fetchone(): c.close(); raise HTTPException(400,'This user has not tracked the same hackathon')
    existing=c.execute("SELECT id FROM team_invites WHERE lower(sender_email)=lower(?) AND lower(recipient_email)=lower(?) AND opportunity_id=? AND status='pending'",(sender,recipient,oid)).fetchone()
    if existing: invite_id=existing['id']
    else:
        cur=c.execute("INSERT INTO team_invites(sender_email,recipient_email,opportunity_id,status,created_at) VALUES(?,?,?,'pending',?)",(sender,recipient,oid,datetime.now(timezone.utc).isoformat())); invite_id=cur.lastrowid
    c.commit(); c.close(); return {"ok":True,"invite_id":invite_id,"status":"pending","recipient_email":recipient,"opportunity_id":oid}

@app.post("/api/team-invites/{invite_id}/{decision}")
def respond_team_invite(invite_id:int, decision:str, request:Request):
    if decision not in ('accept','decline'): raise HTTPException(400,'Invalid decision')
    email=current_email(request); c=conn(); cur=c.execute("UPDATE team_invites SET status=? WHERE id=? AND recipient_email=? AND status='pending'",(decision+'ed' if decision=='accept' else 'declined',invite_id,email)); c.commit(); changed=cur.rowcount; c.close()
    if not changed: raise HTTPException(404,'Invitation not found')
    return {"ok":True}


@app.get("/api/peers/{peer_email}")
def view_peer_profile(peer_email: str, request: Request):
    viewer=current_email(request)
    if viewer == 'guest': raise HTTPException(401, 'Please log in first')
    c=conn(); row=c.execute("SELECT * FROM user_profiles WHERE lower(email)=lower(?)",(peer_email,)).fetchone()
    if not row: c.close(); raise HTTPException(404, 'Profile not found')
    d=dict(row)
    # Public profiles are viewable from search; team-formation profiles only to people
    # who share at least one tracked hackathon or have an invitation relationship.
    allowed=d.get('privacy') in ('public','discoverable')
    if not allowed and d.get('privacy') == 'teams':
        allowed=bool(c.execute("SELECT 1 FROM tracked a JOIN tracked b ON a.opportunity_id=b.opportunity_id WHERE a.user_email=? AND b.user_email=? LIMIT 1",(viewer,peer_email)).fetchone())
        if not allowed: allowed=bool(c.execute("SELECT 1 FROM team_invites WHERE (sender_email=? AND recipient_email=?) OR (sender_email=? AND recipient_email=?) LIMIT 1",(viewer,peer_email,peer_email,viewer)).fetchone())
    if not allowed: c.close(); raise HTTPException(403, 'This profile is private')
    c.close()
    skills=json.loads(d.get('skills') or '[]')
    skills += [x.strip() for x in re.split(r'[,;\n]',d.get('skills_text') or '') if x.strip()]
    return {"email":d['email'],"name":d.get('name') or d['email'].split('@')[0],"university":d.get('university') or '',"skills":list(dict.fromkeys(skills)),"interests":json.loads(d.get('interests') or '[]'),"privacy":d.get('privacy'),"github":d.get('github') or '',"linkedin":d.get('linkedin') or '',"unstop":d.get('unstop') or ''}

@app.get("/api/teams")
def formed_teams(request: Request):
    email=current_email(request)
    if email == 'guest': raise HTTPException(401, 'Please log in first')
    c=conn()
    rows=c.execute("SELECT DISTINCT i.opportunity_id,o.title,i.sender_email,i.recipient_email FROM team_invites i JOIN opportunities o ON o.id=i.opportunity_id WHERE i.status='accepted' AND (i.sender_email=? OR i.recipient_email=?) ORDER BY i.opportunity_id",(email,email)).fetchall()
    grouped={}
    for r in rows:
        oid=r['opportunity_id']; group=grouped.setdefault(oid,{"opportunity_id":oid,"hackathon":r['title'],"members":[]})
        for member in (r['sender_email'],r['recipient_email']):
            if member not in group['members']: group['members'].append(member)
    for group in grouped.values():
        for idx,member in enumerate(group['members']):
            prof=c.execute("SELECT name FROM user_profiles WHERE email=?",(member,)).fetchone()
            group['members'][idx]={"email":member,"name":(prof['name'] if prof and prof['name'] else member.split('@')[0])}
    c.close(); return list(grouped.values())


class AgentQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=500)

@app.post("/api/agent/ask")
def ask_agent(payload: AgentQuestion, request: Request):
    """Answer only questions grounded in current opportunity records; reject other topics."""
    q = re.sub(r"\s+", " ", payload.question).strip().lower()
    terms = ("opportunit", "event", "hackathon", "workshop", "deadline", "registration", "register", "stipend", "prize", "fee", "cost", "free", "paid", "location", "where", "when", "date", "start", "end", "duration", "skill", "eligib", "team size", "team", "organizer", "organization", "apply", "application", "link", "tracked", "available", "list", "which", "what events", "what hackathons")
    if not any(t in q for t in terms):
        return {"accepted": False, "answer": "I can only answer questions about the opportunities currently listed in SkillSync, such as their deadlines, dates, fees, locations, skills, organizers, or application links."}
    c = conn()
    rows = c.execute("SELECT * FROM opportunities ORDER BY id DESC").fetchall()
    c.close()
    if not rows:
        return {"accepted": True, "answer": "There are no opportunities currently listed in SkillSync."}
    items = [row_to_dict(r) for r in rows]
    # Find event-specific references by title/organizer tokens; broad listing questions use all items.
    matches = []
    for item in items:
        title = str(item.get("title") or "")
        org = str(item.get("organization") or "")
        tokens = [x for x in re.findall(r"[a-z0-9]+", title + " " + org.lower()) if len(x) > 3]
        if any(t in q for t in tokens): matches.append(item)
    broad = any(t in q for t in ("list", "all", "available", "which", "what events", "what hackathons", "opportunities", "events", "hackathons", "workshops"))
    chosen = matches if matches else (items if broad else [])
    if not chosen:
        return {"accepted": True, "answer": "I couldn't match that question to a listed opportunity. Try mentioning an event title or ask about the listed deadlines, dates, fees, locations, skills, or application links."}
    def val(x, *keys):
        for key in keys:
            v=x.get(key)
            if v and str(v).strip() and str(v).lower() not in ("none", "null", "not specified"):
                return str(v).replace("\\n", " ").replace("\n", " ").strip()
        return "Not specified"
    fields = []
    if any(t in q for t in ("deadline", "registration", "when apply")): fields=[("registration deadline",("deadline",))]
    elif any(t in q for t in ("location", "where")): fields=[("location",("location",)),("format",("format",))]
    elif any(t in q for t in ("fee", "cost", "free", "paid", "stipend", "prize")): fields=[("fee",("fee",)),("payment/benefit",("payment_type","monetary_benefit"))]
    elif any(t in q for t in ("skill", "eligib")): fields=[("skills",("skills",)),("eligibility",("education","experience"))]
    elif any(t in q for t in ("date", "start", "end", "duration", "when")): fields=[("start date",("start_date",)),("end date",("end_date",)),("deadline",("deadline",))]
    elif any(t in q for t in ("link", "apply", "application")): fields=[("application link",("application_url",))]
    elif any(t in q for t in ("team size", "team")): fields=[("team size",("team_size",))]
    elif any(t in q for t in ("organizer", "organization")): fields=[("organizer",("organization",))]
    else: fields=[("organizer",("organization",)),("type",("type",)),("deadline",("deadline",)),("location",("location",)),("format",("format",))]
    chunks=[]
    for item in chosen:
        parts=[str(item.get("title") or "Untitled opportunity")]
        for label, keys in fields:
            value = val(item,*keys)
            if isinstance(item.get(keys[0]), list): value = ", ".join(map(str,item.get(keys[0]) or [])) or "Not specified"
            parts.append(f"{label.title()}: {value}")
        chunks.append("\n".join(parts))
    return {"accepted": True, "answer": "\n\n".join(chunks)}

@app.get("/api/stats")
def stats():
    c=conn(); total=c.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]; raw=c.execute("SELECT COUNT(*) FROM raw_items").fetchone()[0]; tracked=c.execute("SELECT COUNT(*) FROM tracked").fetchone()[0]; c.close(); return {"opportunities":total,"raw_items":raw,"tracked":tracked}
