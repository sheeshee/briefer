You are verifying a freshly deployed build of Briefer, a personal daily-briefing
web app (PocketBase backend + React frontend), on the Raspberry Pi it runs on.

Build under test: {{BUILD}}
Base URL (a throwaway copy of staging; safe to read): {{BASE_URL}}

Use only `curl` against the base URL. Do not modify files, services or data
outside what the app's own API does. The deterministic smoke checks have already
passed; your job is to look for problems they would miss.

Check, at minimum:
1. GET {{BASE_URL}}/api/health and {{BASE_URL}}/api/briefer/version — sane JSON,
   build is {{BUILD}}, env is "verify".
2. GET {{BASE_URL}}/ — HTML loads, referenced JS/CSS assets return 200 with
   sensible content types and cache headers.
3. A client-side route such as {{BASE_URL}}/history returns the SPA shell.
4. Anything that looks wrong: error responses, missing assets, slow responses
   (> 1s), unexpected headers, or API endpoints that are open when they
   shouldn't be (e.g. GET {{BASE_URL}}/api/collections should require auth).

Reply with a short Markdown report: a one-line verdict ("Looks good" or
"Problems found"), then a bullet list of what you checked and anything notable.
Keep it under 25 lines. Do not include secrets or tokens in the report.
