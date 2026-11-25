# Implementation and verification plan

**Latest scope:** [2026-11-06 user supplied workbook](latest-requirements-20261106.md) supersedes conflicting historical assumptions below. It defines 47 referenced IDs, 21 detailed rows, public group-buy sharing with external seller transactions, five specified navigation tabs, and operator support on both app and web.

Baseline `756869d64c6376d65e46a9b21eb8c6363f8e872f`. Native Codex goal active. Ultragoal plan `community-completion-20261106`; generated state under `.omc/Team_Wifi-4cc2684b36b31f8c/ultragoal/plans/`.

## Phase 0 / 1

1. Requirements analyst completed read-only source audit: 128 IDs complete/unique; screenboard346; historical101 separate. Backend architect and UX explorer completed integration audits.
2. Critic validates `.omc/autopilot/spec.md` and this plan before execution. Record discrepancies and revisions; no implementation success claims yet.

## Phase 2 ownership

- Community backend worker: `backend/app/release.py`, new community helper module if needed, `backend/tests/test_community*.py`. Own post-type compatibility, filtered feed and my activity API. Coordinate DTO contract with frontend.
- Frontend worker: community/chat UI modules, routes/navigation, type/route policies, relevant frontend tests and CSS within existing tokens. Preserve old deep links and private-cache identity isolation. API helper and auth/session changes require main coordination.
- Assistant backend worker: new knowledge/tool/generation/chat/trace modules and assistant tests. Main integrates router/security quotas/dependencies/legal policy; worker sends exact required changes. Own fixed retrieval/live read contract, saved conversation lifecycle, final fresh-session checks.
- Main: source acceptance matrix, orchestration, model/Opik runtime, auth/session design, security/router integration, operational QA, deployment, real UI verification and provenance.

Main also owns original acceptance details not covered by UI renaming: Korea-date history filters and stale-list feedback, reasoned target-correct moderation notices/acknowledgement, skip-safe interest onboarding, and app/web operator access with server role checks. Assign narrow file ownership after inspecting shared authentication/moderation modules; preserve prior role checks and old-client compatibility.

Workers are not alone and must not revert others' changes. No broad staging, no commits from workers, no secret/config dumps or production test data. Existing weekly tracker/PDF untouched.

## Agreed contract before implementation

Community `GET /release/demands` additive `post_type`, `start_date`, `end_date` (YYYY-MM-DD Korea-date) filters; existing create/edit adds field, missing edit preserves existing. DTO adds `post_type`. `GET /release/activity?tab=posts|comments|interests&q=&start_date=&end_date=&limit=&offset=` authenticated returns `{tab,items,has_more}` with `post` DTO for posts/interests and `{comment,post_id,post_title}` for comments. Counts truthful and page after visibility filter. Feed remains old array shape; activity uses explicit has_more. Invalid range is 422, no client query replacement until validated.

Assistant under `/release/assistant`: `GET /status`, `POST /ask`, authenticated `GET /conversations`, `GET/DELETE /conversations/{id}` and `POST /conversations/{id}/end`. Ask input `{question,conversation_id?,remember:false,history?:[{role,content}]}` bounded. Response `{answer,citations,actions,basis,live_checked_at,generation,conversation_id?,request_id}`; optional fields explicitly typed. Main and frontend agree details with worker before call binding. Writes/quota precharge and request transaction closure must be integrated explicitly. No direct client-selected member IDs/tool URLs/models.

## QA cycles / acceptance

Targeted regressions first, then complete backend/frontend/public build, real disposable PostgreSQL harness. Browser uses CUA only; local QA server must retain auth and rate limits (do not retry previous rejected disabled-guard fixture). Use disposable isolated local accounts/data, not production member mutations. Capture mobile widths320/375/768/1440, landscape, keyboard, reduced motion, large text and screenshots. Actual Android device only if available; no emulator.

Run model on synthetic/public prompts, pin provenance, evaluate frozen/holdout cases and improve failures. Run actual Opik traces/experiment if runtime available; describe concrete resource/permission failure if unavailable after bounded diagnostic attempts. Verify DB backup restoration in isolated destination, not destructive production restore.

Deploy compatible API first, then web, then signed Android package. CI must pass on exact product commit. Keep old API and OAuth paths functional. No Play upload or main merge. Avoid repeated unrelated whole-suite runs after clean results unless a change/failure justifies them.

## Phase 4 / 5

Review against spec and standards separately using `$code-review`, plus security/functionality review. Remove dead/duplicated code and unjustified abstractions. Fix blocking findings then re-run affected and final gates. Update 128-row traceability with evidence, feedback records, operations/runbook and meeting-ready summary. Targeted commit/push and Draft PR update. Clear temporary state only after all achievable stories and final review pass; durable ledger and evidence remain.
