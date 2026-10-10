# Final update notes

This package is based on the uploaded `skillsync-ai-poc-google-auth-gmail-v23` project.

## Updates
- Gmail import cleans HTML, forwarded-message headers, recipient dumps, and common email boilerplate before AI extraction.
- AI extraction instructions now request concise, student-facing descriptions and discourage copying routing metadata/signatures.
- Mail descriptions are normalized and capped to keep opportunity cards readable.
- Profile removes React and UI/UX percentage sliders and the free-text skills field; Python/AI proficiency remains.
- Profile has individual interest entry, add confirmation via toast, persistent interest bubbles, and remove controls.
- Existing project pages, Gmail read-only sync, profile fields, opportunities, peers, teams, and agent console are retained.

## Local setup
Use the existing README and `backend/.env.example`. Create your own `backend/.env` locally and set your own Groq and Google OAuth credentials. Real `.env` files, local SQLite databases, Python virtual environments, and `node_modules` are intentionally excluded from this distributable ZIP.
