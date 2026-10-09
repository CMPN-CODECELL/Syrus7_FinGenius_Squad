# POC Architecture

```text
SOURCE GATEWAY / SOURCE TERMINALS (separate simulator)
        /          |          \
       v           v           v
  LinkedIn       Unstop       Mail
   terminal      terminal    terminal
       \           |           /
        \          |          /
         v         v         v
       Structured form OR unstructured source text
                     |
                     v
              FastAPI ingestion
                     |
              +------+------+
              |             |
              v             v
          raw_items      Groq AI
              |             |
              +------<------+
                     |
                     v
          normalized opportunity
                     |
               validation +
             missing-field flags
                     |
                     v
              SQLite database
                /         \
               v           v
        SkillSync app    Profile data
               |
               v
       match / discovery / peers / agent

SEPARATE USER FLOW
Login -> SkillSync application

The source gateway is not the post-login destination. It is only a local source simulator that sends records/prompts into the ingestion pipeline.
```

The source terminals are intentionally dummy/local. They do not scrape LinkedIn, Unstop, or real mail accounts.


## Dashboard initialization
The student dashboard starts with an empty opportunity feed. Opportunities appear only after a source terminal sends structured or unstructured data through the ingestion API. The source gateway is independent from the student login/app flow.
