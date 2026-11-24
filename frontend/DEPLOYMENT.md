# Kairo frontend: Overview slides

The exported design is preserved. Only Overview navigation changed: five existing sections now appear one at a time, with Previous/Next buttons, a slide selector, keyboard navigation, and a final Watch demo button. Small screens may scroll within a content-heavy slide; scrolling no longer moves through the entire presentation. The app screens, video placeholder, mascot slots, and backend integrations remain as exported.

## Vercel setup

Use a separate Vercel frontend project; do not replace the existing FastAPI project.

- Import the same GitHub repository with this source in its `frontend` directory.
- Root Directory: `frontend`
- Framework: Vite
- Install command: `npm ci`
- Build command: `npm run build`
- Output directory: `dist`
- Node: 24.x
- Browser variables: `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (use your existing publishable key for the latter; the exported code uses this variable name).
- Never add GEMINI_API_KEY or DATABASE_URL as VITE variables.

The frontend calls the existing backend directly. Live cross-origin requests need a backend CORS allowlist or same-origin proxy; that remains for the next integration pass. Sample mode is suitable for reviewing appearance now. Do not claim full API integration is verified.

After deployment, add the frontend URL to Supabase Authentication URL settings for any confirmation/redirect flows. Send the frontend deployment URL for checks and final touches. Demo video and mascot integration are deferred per your latest instruction.
