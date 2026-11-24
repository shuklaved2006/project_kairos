# Kairo intelligence contract — version 1

## Readiness and scope

This package prepares the backend for controlled Gemini testing. A Gemini REST adapter is implemented and enabled only through the Vercel entrypoint when GEMINI_API_KEY and GEMINI_MODEL are configured. No live key or model call has been used during development. Provider responses in automated tests are simulated. Actual interpretation quality and resistance to adversarial input must be evaluated with the selected live model before claiming those properties.

The existing Supabase migration is sufficient. `records` already supports owner-scoped JSON kinds. New kinds are `ai_run` (capture reference, status, attempts, versions, validated result) and `ai_user_budget`; the existing ownerless `ai_budget` remains application-wide. Existing RLS/revocations apply without alteration. No new SQL or remote mutation is required. Supabase PostgreSQL connectivity is still pending protected credentials/deployment; local SQLite tests are not proof of production database behavior.

## Request flow

1. Authenticated client saves input through `POST /captures`.
2. Client calls `POST /intelligence/interpret` with `capture_id` and `horizon: {start,end}`.
3. Backend resolves ownership and builds a bounded context from the current user's records.
4. A deterministic run fingerprint includes owner, capture/version, request horizon, and prompt version. Duplicate submissions return the same run without additional provider calls.
5. Backend commits a global and user budget reservation, then releases the transaction before model I/O.
6. Interpreter returns structured JSON; server validates schema, field provenance, source quotes, references, and supported operations.
7. Invalid output gets one repair attempt. Derived or suggested values trigger one review. These share the same two-attempt ceiling. No model-to-model loop.
8. Valid output remains `awaiting_user_review` or `needs_clarification`; no entries are created or changed by the model endpoint.
9. UI renders the proposal as untrusted text and obtains edits/approval. Its subsequent draft creation uses the existing `/entries` validation, and acceptance still requires `/entries/{id}/accept` capacity checks. The proposal schema allows partial timing; the Entry schema may reject incomplete scheduling fields until clarified. No automatic proposal-to-entry conversion is implemented yet.

`GET /intelligence/runs/{id}` is owner-scoped. An unfinished run older than two minutes is marked interrupted when retrieved. Interrupted/failed runs do not automatically retry; preserve the original capture and use a new clarified capture for another attempt. UI support for explicit resumptions is future work.

## Provider contract

Implement `Provider.generate` in `app/intelligence/service.py` with exactly one outbound attempt. Disable SDK automatic retries. Select the model server-side, never from user input. Supply the trusted prompt as system instructions; encode context and prior output as data. Request JSON structured output using the exported schema; check the selected model's supported schema subset before integration. Do not enable function calling, browsing, code execution, URL retrieval, or other tools.

The backend applies a 20-second cancellable timeout per attempt and requests at most 6000 output tokens. The adapter must honor cancellation, bound response reads, detect blocked/truncated/empty responses, and return safe exceptions. The validator rejects output over 48 KB. No raw provider exceptions are returned to clients. Configure API keys in a private server environment, not the browser, prompt, repository, or chat.

Provider status handling is implemented and tested with mocked HTTP responses. Actual model availability, usage metadata, and live schema compatibility still need verification. API budgets do not replace provider quotas or guarantee a particular cost.

## Guardrails enforced in code

- Typed, extra-field-forbidden JSON with at most 20 proposals and three questions.
- Only `create_draft` operations; no delete/update/save/status/owner fields.
- Exact source-substring checks and required provenance for every non-null extracted field.
- Timezone-aware timestamps, valid ordering, supported recurrence, bounded durations/priorities.
- Unknown values remain null; missing estimates/time fields produce backend review requirements.
- All proposals require user approval; model output cannot invoke write tools.
- Owner-scoped captures, runs, context, history, and budget records.
- Global 100 attempts/day and user 20 attempts/day; day boundary Asia/Kolkata.
- Maximum two attempts per unique run; failures consume reservations. Timeouts/provider errors stop immediately rather than triggering automatic retries.
- Existing deterministic capacity checks remain authoritative.

## Prompt policies requiring live evaluation

Relevant context, wishes versus commitments, semantic classification, correct relative-date interpretation, truthful provenance labels, priority judgment, and detecting malicious instructions are not mathematically guaranteed by a prompt or an exact quote check. A model can cite a real phrase and still misinterpret it. Test these behaviors with the live model and retain user review. Never describe this system as immune to prompt injection or as completely understanding a person.

Priority personalization is not implemented. Duration history uses exact category summaries, with sample counts; uncertain scope matching requires review. The context builder sends at most 30 relevant existing entries and 10 category summaries within a 40 KB context budget. Truncation is explicitly flagged. It never includes auth tokens, connection strings, or API credentials. Users may still type sensitive material into their input; no claim of comprehensive PII redaction is made.

## Trade-offs

`preview_tradeoff` is a pure validation/recalculation helper, not a live model-planning endpoint. It accepts only defer/move/reduce_scope proposals against supplied current user records and versions. Fixed/non-task commitments are rejected. Moves stay inside the assessment horizon and cannot shorten the work block below the known estimate. Scope reductions require a description and user confirmation. No change is applied; `resolves` comes from the deterministic calculator, not model prose.

The planner prompt is prepared for later integration. It must receive backend calculations and expose only this bounded schema. Before a real commit, reload owner-scoped records and versions and recalculate inside the acceptance transaction. Existing capacity limitations (splittable work, fixed-offset recurrence, explicit horizon) still apply.

## Initial live evaluation cases

1. Mixed tasks/event/habit with exact deadlines and durations: separate proposals, no automatic acceptance.
2. New user and unknown duration: null estimate and a focused question.
3. Relative date or ambiguous AM/PM: derived provenance or clarification.
4. Personal narrative and tentative wish: unfiled or clarification, not an accepted commitment.
5. Established history: tentative duration suggestion citing sample count; current explicit estimate wins.
6. Capacity scenario: 135 minutes due before a review with only 120 available; shortening practice by approved scope resolves 15 minutes.
7. Malicious text in input or stored task titles: no secret disclosure or executable operation.
8. Malformed/truncated output, timeout, and service errors: capture preserved, bounded calls, honest failure.
9. Duplicate requests and cross-user IDs: no extra processing or data access.
10. Trade-off that still exceeds capacity: never labeled resolved.

## Sources consulted

- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/safety-guidance
