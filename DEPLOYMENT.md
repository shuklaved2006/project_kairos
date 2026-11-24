# Deploy Kairo's backend to Vercel

Repository root is the backend root. No frontend exists yet.

1. Import `shuklaved2006/project_kairos` into Vercel.
2. Root Directory: `.` (leave unchanged). Use the detected FastAPI framework; no frontend output directory or custom build command is needed. Entrypoint: `index.py`. Python 3.12 is requested by `.python-version`.
3. Add server-only environment variables before deployment:
   - `SUPABASE_URL`: project URL.
   - `SUPABASE_PUBLISHABLE_KEY`: project publishable key.
   - `DATABASE_URL`: Supabase transaction-pooler URL with NEW percent-encoded password; use `postgresql+psycopg://`.
   - `GEMINI_API_KEY`: enter privately in Vercel. Optional for first health/database check.
   - `GEMINI_MODEL`: exact model identifier supported by your Google project and the generateContent structured-output API. No default or automatic paid fallback is configured. Verify availability and free-tier quota in AI Studio before selection.
4. Deploy. Missing database/auth configuration intentionally fails startup. No migration runs at startup; your existing Supabase migration must be present.
5. Visit `/health` to check database connectivity, then `/docs` for the API contract. Health does not prove Gemini or sign-in works.
6. Sign in with the demo account through Supabase Auth to obtain a user access token; never use the publishable key as a bearer session token. Test `/auth/me`, then capture and interpret using that session. A private test helper/UI is still needed to make this convenient.

The Gemini adapter uses HTTPS generateContent, trusted system instructions, JSON schema, bounded responses, a 20-second orchestration timeout, and no transport retries or tools. Malformed/derived output may consume the second permitted attempt. Provider rate-limit, credential, blocked and truncated-output errors return sanitized codes. No API key is present in the repository.

Grouped extraction now preserves quantity, per-item vs total effort, and approximate/minimum qualifiers. Grouped proposals remain review-only; they are not automatically expanded into accepted entries. The capacity engine uses numeric estimates and cannot promise completion from lower bounds.

No cloud deployment or live Gemini test has been performed by the local test suite. All Gemini tests mock HTTP responses. Model-specific schema compatibility and hosted PostgreSQL/auth must be checked after deployment.

References:
- https://vercel.com/docs/frameworks/backend/fastapi
- https://ai.google.dev/api/generate-content
