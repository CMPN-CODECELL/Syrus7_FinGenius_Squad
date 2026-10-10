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
WHY_FIT_CACHE = {}  # in-process cache to avoid repeated AI calls on every feed refresh

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
    CREATE TABLE IF NOT EXISTS liked_opportunities (
      opportunity_id INTEGER NOT NULL, user_email TEXT NOT NULL, liked_at TEXT NOT NULL,
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


def infer_opportunity_category(raw: dict) -> str:
    """Use extracted title, description, and tags to assign a useful filter category."""
    existing = str(raw.get("type") or "").strip()
    text = " ".join(str(raw.get(k) or "") for k in ("title", "description", "organization")) + " " + " ".join(str(x) for x in (raw.get("tags") or []) if x)
    t = text.lower()
    # Specific event types first to avoid generic 'opportunity' labels.
    rules = [
        ("Hackathon", ("hackathon", "buildathon", "code-a-thon", "coding marathon")),
        ("Internship", ("internship", "intern position", "summer intern")),
        ("Scholarship", ("scholarship", "tuition award", "financial aid")),
        ("Fellowship", ("fellowship", "fellow programme", "fellow program")),
        ("Workshop", ("workshop", "bootcamp", "hands-on training", "training session")),
        ("Competition", ("competition", "contest", "challenge", "poster presentation", "case competition", "pitch competition", "quiz contest", "olympiad")),
        ("Research", ("research program", "research programme", "research opportunity", "research internship", "research assistant", "research poster")),
        ("Grant", ("grant", "seed funding", "funding call")),
        ("Conference", ("conference", "symposium", "summit")),
        ("Course", ("course", "certification", "mooc")),
    ]
    for label, terms in rules:
        if any(term in t for term in terms):
            # Research poster presentation is commonly a competition when the listing explicitly says competition.
            if label == "Competition" and "research internship" in t:
                return "Internship"
            return label
    if existing and existing.lower() not in {"opportunity", "other", "event", "unknown", "none"}:
        return existing[:40]
    return "Opportunity"


def normalize(raw: dict, source: str):
    out = dict(raw)
    for key, value in list(out.items()):
        if isinstance(value, str):
            out[key] = value.replace("\\\\n", "\n").replace("\\\\r", "\n").strip()
    out["source"] = source
    out["type"] = infer_opportunity_category(out)
    # URLs are stored in their dedicated database fields, not appended to ticker text.
    description = (out.get("description") or "").strip()
    if source.lower().startswith("mail"):
        description = concise_description(description, 240)
        # Avoid the common extraction failure where a greeting/opening fragment is
        # displayed instead of a meaningful summary. Prefer the whole cleaned email.
        weak_opening = bool(re.match(r"(?i)^(dear\\b|hello\\b|hi\\b|greetings\\b|hey\\b|to whom it may concern)", description.strip()))
        if weak_opening or len(description.split()) < 7:
            body_for_summary = clean_gmail_body(str(out.get("_raw_email_body") or out.get("raw_text") or ""))
            if body_for_summary:
                description = concise_description(body_for_summary, 240)
        # Display one sentence only.
        parts = re.split(r"(?<=[.!?])\\s+", description.strip())
        description = (parts[0] if parts else description).strip()
    out["description"] = description
    # Recover explicit payment signals deterministically if the model missed them.
    payment_evidence = " ".join(str(out.get(k) or "") for k in (
        "title", "description", "fee", "payment_type", "monetary_benefit", "raw_text"
    )).lower()
    title_and_desc = " ".join(str(out.get(k) or "") for k in ("title", "description")).lower()
    if not out.get("payment_type"):
        if re.search(r"\\b(unpaid|without pay|non[- ]paid|volunteer position)\\b", payment_evidence):
            out["payment_type"] = "Unpaid"
        elif re.search(r"\\b(paid|stipend|salary|remuneration|cash prize|prize money|₹\\s*[\\d,]+|inr\\s*[\\d,]+)\\b", payment_evidence):
            out["payment_type"] = "Paid / monetary benefit stated"
        elif re.search(r"\\b(free registration|no registration fee|free to attend|no fee|without any fee)\\b", payment_evidence):
            out["payment_type"] = "Free participation"
    if not out.get("fee") and re.search(r"\\b(free registration|no registration fee|free to attend|no fee|without any fee)\\b", payment_evidence):
        out["fee"] = "Free"
    if not out.get("monetary_benefit"):
        benefit_match = re.search(r"(?i)(₹\\s?[\\d,]+(?:\\s?(?:per month|/month|per annum|cash prize|prize money))?|INR\\s?[\\d,]+(?:\\s?(?:per month|/month|per annum|cash prize|prize money))?|\\b(?:stipend|salary|prize money|cash prize)\\s*(?:of|up to|upto)?\\s*₹?\\s?[\\d,]+)", payment_evidence)
        if benefit_match:
            out["monetary_benefit"] = benefit_match.group(0).strip()
    if re.search(r"(?i)\\bpaid\\b", title_and_desc) and not out.get("payment_type"):
        out["payment_type"] = "Paid"
    if out.get("payment_type") or out.get("fee") or out.get("monetary_benefit"):
        if "payment_type" in (out.get("missing_fields") or []): out["missing_fields"].remove("payment_type")
        if "fee" in (out.get("missing_fields") or []) and out.get("fee"): out["missing_fields"].remove("fee")
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
        "title": title or "Untitled opportunity", "organization": org, "type": "opportunity", "description": concise_description(text, 300),
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
    system =     system = """You are the SkillSync opportunity extraction agent. Read the ENTIRE supplied email body and all relevant forwarded/quoted listing content before extracting. Do not decide from the subject or opening paragraph alone. Extract only supported facts and never invent missing facts or URLs. Return exactly ONE complete, polished, student-facing sentence of at most 240 characters summarizing the opportunity. Do not return a greeting or fragment. The description is a compact ticker; the other fields must retain the detailed facts.

THOROUGHLY extract all fields wherever stated, including:
- specific category/type (Hackathon, Competition, Internship, Scholarship, Fellowship, Workshop, Research, Grant, Conference, Course, Job, etc.);
- organizer; target audience and education/eligibility; required skills and experience;
- application deadline, event/start/end dates, registration closing dates, time zones if stated;
- location and online/hybrid/in-person format;
- fee/cost and whether paid, unpaid, stipend-based, prize-based, or free; preserve the distinction between participation fee and money paid to participants;
- monetary benefit, prize, salary, stipend, currency, team size, application/registration URL;
- tags and missing_fields for important details genuinely absent or unclear.
Inspect the full body, tables/bullets and later paragraphs. Treat the title, subject, body, tables, bullets and forwarded content as evidence. A title containing "Paid", "Unpaid", "Free", "Stipend", "Prize", "Salary", "Bootcamp" or a category is a meaningful signal even if the body is brief. Never leave payment_type as unknown when an explicit paid/unpaid/free signal appears. Distinguish money paid TO the participant (salary/stipend/prize) from a fee paid BY the participant (registration/course fee); do not infer either from the word "paid" alone beyond marking the opportunity as paid when clearly stated. If the email contains an explicit phrase like free/no fee, unpaid, paid internship, stipend, prize or registration fee, capture it in fee/payment_type/monetary_benefit appropriately. Set type to the most specific useful category based on the full content. For example, poster presentation can be Competition if explicitly framed as a competition; do not classify everything as generic Opportunity. Never copy email headers, recipient lists, signatures, disclaimers, tracking text or repeated boilerplate into description. Prefer the actual event title over a Fwd/Invitation subject. confidence is 0-1. Flag absent title, organization, deadline, application_url, or format in missing_fields."""
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0,
        messages=[{"role":"system","content":system},{"role":"user","content":text[:50000]}],
        response_format={"type":"json_schema","json_schema":{"name":"skillsync_opportunity","strict":True,"schema":SCHEMA}},
    )
    return json.loads(resp.choices[0].message.content)





def groq_text(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str:
    """Generate a concise answer using the configured Groq-compatible OpenAI endpoint."""
    if not GROQ_API_KEY:
        raise RuntimeError("AI is not configured. Add GROQ_API_KEY to backend/.env.")
    from openai import OpenAI
    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=0.25,
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()


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
    """Rank opportunities in the requested tiers: discovery, one interest, multiple interests, liked-event affinity."""
    p = profile(email)
    # Keep non-learning/non-career messages permanently below 15, even if their
    # wording accidentally overlaps a profile term or a liked event.
    relevance_text = " ".join(str(opp.get(k) or "") for k in ("title", "description", "type", "organization", "tags"))
    relevance_text = relevance_text.lower()
    relevant_terms = (
        "hackathon", "competition", "contest", "internship", "job", "career", "scholarship",
        "fellowship", "workshop", "research", "conference", "course", "training", "bootcamp",
        "volunteer", "grant", "grant", "challenge", "student", "eligibility", "apply", "application",
        "stipend", "salary", "prize", "certification", "mentorship", "placement", "project",
        "poster presentation", "skill", "learning", "startup", "innovation"
    )
    non_opportunity_signals = ("order shipped", "delivery update", "otp", "one-time password",
        "password reset", "verify your account", "bank statement", "transaction alert",
        "payment successful", "bill generated", "flight ticket", "hotel booking", "shopping receipt",
        "promotional offer", "sale ends", "your subscription", "meeting reminder")
    if any(term in relevance_text for term in non_opportunity_signals) and not any(term in relevance_text for term in relevant_terms):
        return 5, 0
    if not any(term in relevance_text for term in relevant_terms):
        # Unclear/personal mail is discovery-only and cannot enter match tiers.
        return 10, 0
    profile_terms = []
    profile_terms.extend(p.get("skills") or [])
    profile_terms.extend(p.get("interests") or [])
    profile_terms.extend(x.strip() for x in re.split(r"[,;\n]", p.get("skills_text") or "") if x.strip())
    normalized = {re.sub(r"[^a-z0-9+#./ -]", "", str(x).lower()).strip() for x in profile_terms}
    normalized = {x for x in normalized if x}
    opp_terms = list(opp.get("skills") or []) + list(opp.get("tags") or [])
    opp_text = " ".join([
        str(opp.get("title") or ""), str(opp.get("description") or ""),
        str(opp.get("type") or ""), str(opp.get("organization") or ""),
        " ".join(str(x) for x in (opp.get("impact_lens") or [])),
        " ".join(str(x) for x in opp_terms)
    ]).lower()
    # Match against every useful field, especially extracted skill/tag chips.
    # Normalize list-like fields defensively in case a database driver returns JSON strings.
    def as_items(value):
        if isinstance(value, list):
            return [str(x) for x in value if str(x).strip()]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed if str(x).strip()]
            except Exception:
                pass
            return [x.strip() for x in re.split(r"[,;|]", value) if x.strip()]
        return []
    opp_terms = as_items(opp.get("skills")) + as_items(opp.get("tags"))
    opportunity_phrases = [str(opp.get(k) or "") for k in ("title","description","type","organization","format","impact_lens")]
    opportunity_phrases += opp_terms + as_items(opp.get("education")) + as_items(opp.get("experience"))
    opp_text = " ".join(opportunity_phrases).lower()
    opp_words = set(re.findall(r"[a-z0-9+#]{3,}", opp_text))
    stop_words = {"the","and","for","with","from","that","this","your","you","are","not","into","event","mail","dear","students","opportunity","workshop","any","all","can","who"}
    opp_words -= stop_words
    matched = set()
    for term in normalized:
        clean_term = term.strip().lower()
        term_words = set(re.findall(r"[a-z0-9+#]{3,}", clean_term)) - stop_words
        # Exact phrase is strongest; meaningful word overlap catches "research" in
        # "AI research" and "programming" in "any programming".
        phrase_match = bool(clean_term and re.search(r"(?<![a-z0-9])" + re.escape(clean_term) + r"(?![a-z0-9])", opp_text))
        token_match = bool(term_words and term_words & opp_words)
        if phrase_match or token_match:
            matched.add(term)
    # Use the number of meaningful profile overlaps to calculate the score,
    # rather than relying on a hard-coded default match.
    # A previously liked event boosts similar opportunities for this account only.
    liked_affinity = False
    if email != "guest":
        c = conn()
        liked_rows = c.execute("SELECT o.id,o.title,o.type,o.description,o.skills,o.tags FROM liked_opportunities l JOIN opportunities o ON o.id=l.opportunity_id WHERE l.user_email=?", (email,)).fetchall()
        c.close()
        # A directly liked opportunity always belongs in Tier 1.
        try:
            current_id = int(opp.get("id") or 0)
        except (TypeError, ValueError):
            current_id = 0
        if current_id and any(int(row["id"]) == current_id for row in liked_rows):
            liked_affinity = True
        current_words = set(re.findall(r"[a-z0-9+#]{3,}", opp_text))
        stop = {"the","and","for","with","from","that","this","your","you","are","not","into","opportunity","event","mail","dear","students"}
        current_words -= stop
        interest_terms = {re.sub(r"[^a-z0-9+# ]", "", str(x).lower()).strip()
                          for x in (p.get("interests") or [])}
        interest_terms = {x for x in interest_terms if x}
        current_interest_hits = {term for term in interest_terms if term in opp_text}
        for row in liked_rows:
            liked_text = " ".join(str(row[k] or "") for k in ("title","type","description","skills","tags")).lower()
            liked_words = set(re.findall(r"[a-z0-9+#]{3,}", liked_text)) - stop
            shared_interest = any(term in liked_text and term in opp_text for term in interest_terms)
            # A liked event trains the ranking toward its topic/interest, even when
            # exact event titles differ; avoid unrelated generic word-only boosts.
            if shared_interest or (current_words and liked_words and len(current_words & liked_words) >= 3):
                liked_affinity = True
                break
    count = len(matched)
    if liked_affinity:
        # Liked-event affinity is the highest tier; increase with interest overlap.
        value = min(100, 76 + min(24, count * 6))
    elif count >= 2:
        # Multiple genuine profile overlaps always remain in the 50–75 tier.
        value = min(75, 50 + min(25, (count - 1) * 8))
    elif count == 1:
        value = 25 + min(25, 13)
    else:
        # Any listed opportunity gets a low discovery score, even without a profile match.
        value = 15
    return int(value), count


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


def concise_description(value: str, max_chars: int = 420) -> str:
    value = clean_gmail_body(value)
    # Keep the ticker description focused on the opportunity, not the whole email.
    value = re.sub(r"(?im)^\s*(original source post url|source post url)\s*:.*$", "", value)
    value = re.sub(r"(?im)^\s*(best regards|kind regards|regards|sincerely|unsubscribe|confidentiality notice)\b.*$", "", value)
    value = re.sub(r"(?im)^\s*(from|to|cc|bcc|sent|date|subject|reply-to)\s*:\s*.*$", "", value)
    value = re.sub(r"https?://\S+", "", value)
    value = re.sub(r"(?im)^\s*[-_=]{3,}\s*(original message|forwarded message).*?$", "", value)
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    # Prefer a compact first couple of meaningful sentences.
    sentences = re.split(r"(?<=[.!?])\s+|\n+", value)
    sentences = [re.sub(r"\s+", " ", part).strip(" •-*\t") for part in sentences]
    sentences = [part for part in sentences if part and not re.match(r"(?i)^(click here|view in browser|unsubscribe|this email and any attachments)", part)]
    value = " ".join(sentences[:2]).strip()
    if len(value) > max_chars:
        value = value[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
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
        # Broad, read-only scan: keyword-only queries miss invitations whose subject
        # doesn't contain obvious opportunity terms. Pagination is bounded per run.
        query = 'newer_than:180d -in:spam -in:trash'
        messages = []
        page_token = None
        max_scan = 200
        while len(messages) < max_scan:
            page = service.users().messages().list(
                userId="me", q=query, maxResults=min(100, max_scan-len(messages)),
                pageToken=page_token
            ).execute()
            messages.extend(page.get("messages", []))
            page_token = page.get("nextPageToken")
            if not page_token:
                break
    except ImportError:
        raise HTTPException(status_code=503, detail="Gmail packages are missing. Run: python -m pip install google-auth-oauthlib google-api-python-client google-auth-httplib2")
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Gmail could not be read. Reconnect Gmail and check OAuth configuration.")
    # Gmail returns newest messages first. Reverse the batch so semantic duplicates
    # are merged chronologically and the newest message wins the final record fields.
    messages.reverse()
    imported = 0; skipped = 0; errors = 0
    for item in messages:
        mid = item.get("id") or ""
        c = conn()
        seen = c.execute("SELECT 1 FROM gmail_imported_messages WHERE lower(user_email)=lower(?) AND message_id=?", (email, mid)).fetchone()
        source_id = "gmail:" + mid
        linked = c.execute("SELECT 1 FROM raw_items WHERE source_item_id IN (?,?) LIMIT 1", ("Mail-" + source_id, "Mail-gmail:" + mid)).fetchone()
        if seen and linked:
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
            extracted["_raw_email_body"] = body
            extracted = normalize(extracted, "Mail")
            extracted.pop("_raw_email_body", None)
            source_id = "gmail:" + mid
            oid, status, changed = merge_or_insert_opportunity(c, extracted, "Mail-" + source_id, float(extracted.get("confidence") or 0), extracted.get("missing_fields", []))
            c.execute("INSERT INTO raw_items(source,source_item_id,subject,raw_text,ai_extracted,processed_at) VALUES(?,?,?,?,?,?)", ("Mail", source_id, subject, raw, json.dumps(extracted, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
            c.execute("INSERT OR IGNORE INTO gmail_imported_messages(user_email,message_id,imported_at) VALUES(?,?,?)", (email, mid, datetime.now(timezone.utc).isoformat()))
            c.commit(); imported += 1
        except Exception as exc:
            errors += 1
            print(f"Gmail message import failed for message {mid}: {type(exc).__name__}: {exc}")
        finally:
            c.close()
    c = conn(); c.execute("UPDATE gmail_connections SET token_json=?,last_sync=? WHERE lower(user_email)=lower(?)", (creds.to_json(), datetime.now(timezone.utc).isoformat(), email)); c.commit(); c.close()
    return {"ok": True, "scanned": len(messages), "imported": imported, "already_seen": skipped, "errors": errors, "message": f"Gmail sync complete: imported {imported} email(s), skipped {skipped} already processed."}


@app.get("/api/opportunities")
def opportunities(request: Request, source: Optional[str]=None):
    email=current_email(request)
    c=conn()
    # User requested that opportunities with passed application deadlines leave the feed.
    # Only delete when the deadline is confidently parseable; unknown dates are retained.
    all_rows=c.execute("SELECT id,deadline FROM opportunities").fetchall()
    today=datetime.now().date()
    expired_ids=[]
    for row in all_rows:
        parsed=parse_event_date(row["deadline"])
        if parsed and parsed < today:
            expired_ids.append(row["id"])
    if expired_ids:
        marks=",".join("?" for _ in expired_ids)
        c.execute(f"DELETE FROM opportunities WHERE id IN ({marks})", expired_ids)
        c.execute(f"DELETE FROM opportunity_sources WHERE opportunity_id IN ({marks})", expired_ids)
        c.execute(f"DELETE FROM tracked WHERE opportunity_id IN ({marks})", expired_ids)
        c.execute(f"DELETE FROM liked_opportunities WHERE opportunity_id IN ({marks})", expired_ids)
        c.commit()
    rows=c.execute("SELECT * FROM opportunities ORDER BY id DESC").fetchall(); tracked={r[0] for r in c.execute("SELECT opportunity_id FROM tracked WHERE user_email=?",(email,)).fetchall()}; liked={r[0] for r in c.execute("SELECT opportunity_id FROM liked_opportunities WHERE user_email=?",(email,)).fetchall()}; source_counts={r[0]:r[1] for r in c.execute("SELECT opportunity_id,COUNT(*) FROM opportunity_sources GROUP BY opportunity_id").fetchall()}; c.close()
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
        d["liked"]=d["id"] in liked
        s, overlap=score(d,email); d["matchScore"]=s
        p=profile(email)
        profile_terms=[str(x).strip() for x in (p.get("skills") or [])+(p.get("interests") or []) if str(x).strip()]
        opp_text=" ".join([str(d.get("title") or ""),str(d.get("description") or ""),str(d.get("type") or ""), " ".join(d.get("skills") or []), " ".join(d.get("tags") or [])]).lower()
        opportunity_words=set(re.findall(r"[a-z0-9+#]{3,}", opp_text))
        matched_terms=[]
        for term in profile_terms:
            tw=set(re.findall(r"[a-z0-9+#]{3,}", term.lower()))
            if term.lower() in opp_text or (tw and tw & opportunity_words):
                matched_terms.append(term)
        profile_context={"skills":p.get("skills") or [],"interests":p.get("interests") or [],"university":p.get("university") or ""}
        opportunity_context={"title":d.get("title"),"type":d.get("type"),"description":str(d.get("description") or "")[:1800],"skills":d.get("skills") or [],"tags":d.get("tags") or [],"eligibility":d.get("education") or [],"experience":d.get("experience") or "","missing_fields":d.get("missing_fields") or []}
        if profile_terms and GROQ_API_KEY:
            cache_key = (email, d.get("id"), json.dumps(profile_context, sort_keys=True, ensure_ascii=False), json.dumps(opportunity_context, sort_keys=True, ensure_ascii=False))
            if cache_key in WHY_FIT_CACHE:
                d["whyFit"] = WHY_FIT_CACHE[cache_key]
            else:
                try:
                    d["whyFit"] = groq_text(
                        "You are SkillSync's personalized opportunity matching assistant. Write 1-2 concise sentences. Start by naming the exact profile skills/interests that overlap with the opportunity, using only the provided matched profile terms. Explain the concrete connection to the title, description, skill chips or tags. If there are no direct overlaps, say that honestly. Mention an eligibility gap only if explicitly supported. Never invent requirements or give a generic template.",
                        "Student profile JSON: " + json.dumps(profile_context, ensure_ascii=False) + "\nOpportunity JSON: " + json.dumps(opportunity_context, ensure_ascii=False),
                        180,
                    )
                    WHY_FIT_CACHE[cache_key] = d["whyFit"]
                    if len(WHY_FIT_CACHE) > 1000:
                        WHY_FIT_CACHE.clear()
                except Exception:
                    d["whyFit"] = "Your profile includes " + (", ".join(matched_terms[:3]) if matched_terms else ", ".join(profile_terms[:3])) + ". Compare these with the opportunity details; eligibility is not confirmed by profile overlap alone."
        elif matched_terms:
            d["whyFit"]="Your profile lists "+", ".join(matched_terms[:4])+", which relates to this opportunity. Eligibility is not confirmed by profile overlap alone."
        elif overlap:
            d["whyFit"]=f"Your profile has {overlap} broader skill or interest connection(s) to this opportunity. Review the listed requirements to confirm fit."
        else:
            d["whyFit"]="No clear direct overlap with your saved skills or interests was found yet. You can still review the opportunity and add relevant experience or interests to your profile."
        out.append(d)
    return out

class InterestVerifyIn(BaseModel):
    value: str = Field(min_length=1, max_length=80)
    kind: str = Field(default="interest", pattern="^(interest|skill)$")

@app.post("/api/profile/verify-entry")
def verify_profile_entry(payload: InterestVerifyIn, request: Request):
    email = current_email(request)
    if email == "guest":
        raise HTTPException(status_code=401, detail="Please sign in first.")
    value = re.sub(r"\s+", " ", payload.value).strip()
    # Fast reject for empty/punctuation/repeated-character gibberish before spending an AI call.
    if len(value) < 2 or not re.search(r"[A-Za-z0-9]", value) or re.fullmatch(r"(.)\1{4,}", value):
        return {"valid": False, "message": "That doesn't look like a valid skill or interest. Try a meaningful phrase, such as data analysis or climate research."}
    if not GROQ_API_KEY:
        # Conservative local fallback when AI is not configured.
        if len(re.findall(r"[A-Za-z0-9+#.-]+", value)) >= 1 and not re.search(r"[^A-Za-z0-9+#.&/()' -]", value):
            return {"valid": True, "message": "Looks valid. (AI verification is unavailable until GROQ_API_KEY is configured.)", "normalized": value}
        return {"valid": False, "message": "Please enter a meaningful skill or interest using ordinary words."}
    try:
        result = groq_text(
            "You are a VERY PERMISSIVE validator for a student's skill or interest field. Accept any understandable word or phrase that could reasonably be a hobby, subject, activity, art, career area, technology, academic topic, personal interest, or skill. IMPORTANT: 'Writing' is valid; so are reading, music, gaming, art, cooking, history, research, sports, fashion, films, animals, and niche or uncommon topics. Do not require the entry to sound technical or career-focused. Reject ONLY clear nonsense such as random keyboard mashing, repeated random characters, or text with no interpretable meaning. If uncertain, ACCEPT. Return ONLY JSON with keys valid (boolean), normalized (string), reason (short string).",
            json.dumps({"kind": payload.kind, "entry": value}, ensure_ascii=False), 100)
        match = re.search(r"\{.*\}", result, re.S)
        data = json.loads(match.group(0)) if match else {}
        normalized = re.sub(r"\s+", " ", str(data.get("normalized") or value)).strip()[:80]
        # Prevent an over-strict model verdict from rejecting ordinary, interpretable short entries.
        # Obvious nonsense is caught by the fast checks above; plain words/phrases should pass.
        ordinary_phrase = bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9+#.&/()' -]{0,79}", value)) and bool(re.search(r"[aeiouyAEIOUY]", value))
        valid = bool(data.get("valid")) or ordinary_phrase
        message = "Entry accepted." if valid else str(data.get("reason") or "That looks like random text. Please enter a real skill or interest.")
        return {"valid": valid, "normalized": normalized, "message": message[:240]}
    except Exception as exc:
        # AI outages must not block ordinary interests like "Writing". Fall back to
        # conservative local heuristics; only obvious gibberish is rejected.
        words = re.findall(r"[A-Za-z0-9+#.-]+", value)
        looks_like_gibberish = (
            not words or
            re.search(r"[^A-Za-z0-9+#.&/()' -]", value) is not None or
            (len(value) >= 8 and len(set(value.lower())) <= 2) or
            bool(re.search(r"(.)\1{4,}", value)) or
            (len(words) == 1 and len(words[0]) >= 10 and not re.search(r"[aeiouy]", words[0], re.I))
        )
        if not looks_like_gibberish:
            return {"valid": True, "message": "Accepted using local validation because AI verification is temporarily unavailable.", "normalized": value}
        return {"valid": False, "message": "That entry looks like random text. Please enter a recognizable skill or interest."}

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
        likely_duplicate = same_url or (sim >= 0.55 and (same_org or not oo or not no or sim >= 0.72))
        # For borderline title matches, ask the configured model whether the two records
        # describe the same real-world opportunity. Keep heuristic fallback if AI is absent.
        if not likely_duplicate and GROQ_API_KEY and sim >= 0.30:
            try:
                verdict = groq_text(
                    "You are a conservative duplicate detector for event/opportunity listings. Reply with exactly YES if both records describe the same real-world opportunity/event despite different wording or email formatting. Reply NO if they are different events. Consider event title, organizer, dates, and core purpose. Do not mark two unrelated events as duplicates.",
                    "EXISTING: " + json.dumps({"title": rd.get("title"), "organization": rd.get("organization"), "description": rd.get("description"), "deadline": rd.get("deadline")}, ensure_ascii=False) +
                    "\\nNEW: " + json.dumps({"title": title, "organization": org, "description": payload.get("description"), "deadline": payload.get("deadline")}, ensure_ascii=False),
                    max_tokens=5
                )
                likely_duplicate = verdict.strip().upper().startswith("YES")
            except Exception:
                pass
        if likely_duplicate:
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

@app.post("/api/opportunities/{oid}/like")
def like_opportunity(oid:int, request: Request):
    email=current_email(request)
    if email == "guest": raise HTTPException(status_code=401, detail="Please sign in to like an opportunity.")
    c=conn()
    if not c.execute("SELECT id FROM opportunities WHERE id=?",(oid,)).fetchone():
        c.close(); raise HTTPException(status_code=404, detail="Opportunity not found")
    c.execute("INSERT OR REPLACE INTO liked_opportunities(opportunity_id,user_email,liked_at) VALUES(?,?,?)",(oid,email,datetime.now(timezone.utc).isoformat()))
    c.commit(); c.close(); return {"ok":True,"liked":True}

@app.delete("/api/opportunities/{oid}/like")
def unlike_opportunity(oid:int, request: Request):
    email=current_email(request)
    if email == "guest": raise HTTPException(status_code=401, detail="Please sign in to update liked opportunities.")
    c=conn(); c.execute("DELETE FROM liked_opportunities WHERE opportunity_id=? AND user_email=?",(oid,email)); c.commit(); c.close()
    return {"ok":True,"liked":False}

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
    opportunity_id: int | None = None

@app.post("/api/agent/ask")
def ask_agent(payload: AgentQuestion, request: Request):
    """Answer opportunity and preparation questions grounded in listings and profile context."""
    email = current_email(request)
    q = re.sub(r"\s+", " ", payload.question).strip()
    c = conn()
    if payload.opportunity_id is not None:
        rows = c.execute("SELECT * FROM opportunities WHERE id=?", (payload.opportunity_id,)).fetchall()
    else:
        rows = c.execute("SELECT * FROM opportunities ORDER BY id DESC").fetchall()
    c.close()
    items = [row_to_dict(r) for r in rows]
    if payload.opportunity_id is not None and not items:
        raise HTTPException(status_code=404, detail="That opportunity could not be found.")
    if not items:
        return {"accepted": True, "answer": "There are no opportunities listed yet. Sync Gmail or add an opportunity, then ask me about preparation, deadlines, eligibility, or next steps."}
    p = profile(email)
    # Keep prompt context bounded; the model can answer preparation questions even if they don't
    # contain exact database keywords. The answer must distinguish listed facts from advice.
    context = []
    for item in items[:20]:
        context.append({k: item.get(k) for k in ["title","organization","type","description","deadline","start_date","end_date","location","format","fee","payment_type","monetary_benefit","team_size","skills","education","experience","tags","application_url","missing_fields"]})
    if GROQ_API_KEY:
        try:
            answer = groq_text(
                "You are SkillSync's helpful opportunity and preparation assistant. " + ("The user opened a dedicated console for this single opportunity. Discuss ONLY this opportunity and do not mention or recommend other listings. " if payload.opportunity_id is not None else "") + "Answer questions about listed opportunities, summarizing their source details and making reasonable, clearly labeled deductions. Preparation, planning, project ideas, skill-building, application strategy, and 'how should I prepare?' are in scope even if phrased broadly. Use only the supplied listings for factual claims; label advice as 'Suggested preparation' or 'Inference', and explicitly say when eligibility/deadlines/details are not provided. If the user asks something unrelated to opportunities or preparing for them, gently redirect. Be practical, concise, and specific. Prefer short headings and 3-5 bullet points. Do not dump raw records, JSON, missing_fields arrays, or every opportunity unless asked. For a question about one named opportunity, focus on that opportunity; for preparation questions, summarize its content and give a concrete preparation plan. Never claim inferred advice is an official requirement.",
                "Student profile: " + json.dumps({"skills":p.get("skills") or [],"interests":p.get("interests") or [],"university":p.get("university") or ""}, ensure_ascii=False) +
                "\nUser question: " + q + "\nCurrent opportunity records (JSON): " + json.dumps(context, ensure_ascii=False, default=str),
                700)
            return {"accepted": True, "answer": answer or "I couldn't form a useful answer from the current listings. Try naming an opportunity."}
        except Exception:
            # Fall through to deterministic, database-grounded answers when AI is unavailable.
            pass
    ql = q.lower()
    prep = any(t in ql for t in ("prepare", "preparation", "how should i", "get ready", "improve", "strategy", "plan", "what should i learn", "project idea", "resume", "portfolio"))
    terms = [x for x in re.findall(r"[a-z0-9]+", ql) if len(x) > 3]
    matched = [item for item in items if any(t in str(item.get("title") or "").lower() or t in str(item.get("organization") or "").lower() for t in terms)]
    chosen = matched or items[:8]
    def value(item, key):
        v = item.get(key)
        if isinstance(v, list): return ", ".join(str(x) for x in v) or "Not specified"
        return str(v).strip() if v not in (None, "", "null") else "Not specified"
    if prep:
        chunks=[]
        for item in chosen[:3]:
            chunks.append(f"{value(item,'title')}\nWhat is listed: {value(item,'description')[:500]}\nSuggested preparation (inference, not an official requirement): review the stated skills and eligibility, prepare a concise project/research summary relevant to the theme, collect any required documents, and verify the deadline and application instructions from the original source.")
        return {"accepted": True, "answer": "\n\n".join(chunks)}
    chunks=[]
    for item in chosen[:8]:
        chunks.append(f"{value(item,'title')} · {value(item,'organization')}\nDeadline: {value(item,'deadline')} · Location: {value(item,'location')}\nSkills: {value(item,'skills')}")
    return {"accepted": True, "answer": "\n".join(chunks)}

@app.get("/api/stats")
def stats():
    c=conn(); total=c.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]; raw=c.execute("SELECT COUNT(*) FROM raw_items").fetchone()[0]; tracked=c.execute("SELECT COUNT(*) FROM tracked").fetchone()[0]; c.close(); return {"opportunities":total,"raw_items":raw,"tracked":tracked}
