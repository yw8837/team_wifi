# ModuYuga community completion specification

Baseline: `756869d64c6376d65e46a9b21eb8c6363f8e872f`. Date: 2026-11-06 KST.

## Source authority and scope

The current acceptance authority is the workbook modified on 2026-11-06 16:06:44 KST: `artifacts/requirements-live-20261106/requirements.xlsx` (SHA-256 `20bb64c8a1538cd11eb6499209b1e8afa1940e4445c247d50baa69846a66acb7`). Its two tabs contain 47 distinct IDs: 21 detailed definitions and 26 overview-only IDs. Preserve shared overview descriptions without inventing an individual allocation among IDs. The current direction is a parenting groupbuy-information community; preserve current brand/design, existing accounts/content/API links. The older 128-ID workbook, 346 designed screen states and original 101-item audit remain historical sources, not the latest acceptance baseline. Designed states are not implemented screens.

Every current ID must receive an explicit disposition with source row and acceptance evidence in `docs/plans/latest-requirements-20261106.{json,md}`. Historical 128-ID dispositions remain separate; they do not replace the latest 47-ID baseline or add missing detailed definitions. Later community/design decisions supersede the old commerce flow and exact older palette, without claiming the old conditions were implemented. Real purchases, PG refunds, settlement, shipping and merchant certification require business identities/contracts/real inventory not supplied. Keep these original conditions as external commercial dependencies; never invent working checkout, discounts, certifications, or sales. Do not delete dormant original code merely to improve completion counts.

Split each commercial row into applicable community behavior, existing software verification, external business activation prerequisites, and presentation superseded by the later direction. A payment contract does not excuse missing implementable validation/access checks: file type/size/count limits, file ownership, private inquiry isolation and preservation after invalid submission must be evaluated independently, including dormant paths if retained.

Current source: `artifacts/requirements-live-20261106/requirements.xlsx`, with derived `workbook.json` and `source-mapping.json`. Historical reference sources: `artifacts/drive-reference-20261103/requirements.xlsx`, `requirements.csv`, `screen-design.xlsx`, `screen-design-text.json`, `board-text.txt`; `docs/plans/2026-11-05-community-feedback.md`; `docs/plans/2026-11-04-community-rag-opik.md`; data report and actual evaluation artifacts under `ai-pipeline/artifacts/`. Private originals stay out of Git.

## Community

- Root is the ongoing groupbuy-information feed. `/demands` retains the demand/community feed and `/offers` the official-reference catalog. The five bottom navigation items are **공구 찾기 · 공구 수요 · 단가 비교 · 저장 · 마이**, with a separate assistant button. Guests may browse and ask assistant questions; ownership actions require login.
- Post types `question`, `experience`, `information`, `demand`; retain `release_demand` storage and existing `/demands/*` routes. Historical missing type defaults to demand. Old edit requests MUST preserve stored type when absent.
- Feed search, type/category filtering and pagination in URL; clear loading/error/empty state, honest counts. No fabricated popular posts.
- Only demand posts have demand-interest semantics. All types have author-owned edit/delete, replies, report/block behavior and creation/update timestamps. Preserve revision conflict handling and children/counts.
- Authenticated my activity shows own posts/comments/interests with current parent visibility and account isolation.
- Feed/activity/moderation history supports optional Korea-date start/end (inclusive) based on creation/action time, separate updated time, invalid range rejection, URL query persistence, page reset on filter changes and filter retention on pagination. Editing does not change creation-based period membership. Default is all dates. Query failure preserves the previous valid list and clearly marks it stale. Counts/ranges are after visibility filters.
- Moderation actions require a reason and preserve the exact target type/ID and actor/action time. Hidden-content notices must not repeat private removed text. Affected members see the action notice on next authenticated entry and can acknowledge it; duplicate acknowledgements are safe. Suspended members receive a non-enumerating login restriction message, with no authenticated content disclosure.
- Report forms show the exact post/comment target and safe current preview before reason entry. Admin review preserves report ID/target and recorded receive/action times, never invents a completed timestamp for an open report. Explain and separate hide/remove, no-action and account suspension. Authorized admin evidence review is distinct from public visibility.
- Interest onboarding supports multiple existing categories and an explicit skip choice; previously saved choices are not overwritten when skipped.
- The latest overview rows 28–29 require operator functions on both Android/app and web. Operator authentication and authorized management must work on both; do not restore the older blanket mobile/operator denial. Keep server role authorization, fresh authentication, mandatory reasons, audit history and request limits. Client/platform signals are informational, not device attestation or a replacement for authorization.
- Preserve no-login browsing, return-to after login, no automatic posting/interest. Explicit keep-signed-in preference may use a secured design after review; 30-day expiry and revocation remain. Never claim browser restart persistence from sessionStorage alone.
- Retain semantic controls, keyboard focus, 48px touch targets, responsive wrapping, safe areas, reduced motion, form drafts and meaningful errors. Existing visual tokens win over unsuitable generated palettes.
- Policy and support links remain accessible on my page/footer without collision with fixed navigation. Unknown company/address/business registration information is not fabricated.

## Assistant and live data

- Dedicated `/chat` with genuine local open-model inference when available; existing `/advisor` remains a condition form. No template response labelled as a generated LLM answer.
- Approved public corpus: catalog comparison notes, verified service guides and reviewed data-analysis summaries. Chunk ID, source URL/type, revision/hash and checked-at retained. No raw retail CSV as parenting medical knowledge.
- Deterministic authorized tools: current visible community search, own saved items, own choices and existing privacy-threshold companions. Server chooses identity and allowlisted operations; no model-written SQL, URL fetches or writes.
- Inference receives only approved public material initially. Current account/private results are assembled by the server and never sent to a third-party model or analytics system. Community content is untrusted evidence, never instructions.
- Separate inference process, loopback binding, bounded input/context/output, queue/concurrency/deadlines. Do not hold SQL transactions during generation. Fresh DB session reauthenticates and revalidates evidence revision/visibility before responding.
- Explicit saved conversation option for signed-in accounts (off until chosen), bounded history, retention of 30 days from last successful saved activity, resume across sessions, confirmed end/clear/delete. Expired history is immediately excluded and removed on access plus scheduled cleanup. End/delete/opt-out clears text; atomic revision/status checks prevent late inference from recreating closed history. Save/delete failure is reported and retryable, not shown as success. Anonymous and non-opted-in conversation is temporary; UI explicitly explains it will not resume after a new login. Clear current UI and pending responses on account change/logout. Account erasure deletes saved chats. Previous answers are not current factual evidence.
- Source cards, checked-at, relevant links, actual generation status, unsupported/medical/price/certification abstention, differentiated no-evidence/service-failure states. Citation existence alone is insufficient: assess support.

## Measurement and operations

- Genuine Opik SDK integration to a verified self-hosted or explicitly authorized free endpoint; input/output capture disabled for members. Allowlisted random trace IDs, public document versions, stage latency/errors/metrics only. SDK failure cannot break user actions. Offline results must not be called a running Opik deployment.
- Freeze synthetic evaluation cases before tuning, including retrieval gold, live changes, private isolation, injection, unknown prices and errors. Retain failures. Measure retrieval Recall@5 on applicable cases, groundedness review, citation validity, leakage, fresh state, warm/cold p50/p95 and timeout rate. Targets are not results.
- Verify shared account data across independent sessions, revoked tokens, durable quotas, real PostgreSQL concurrency and recovery on an isolated DB. Do not seed production statistics or expose private backups.
- Existing Elice only. External HTTPS ownership gap, Google quota, Neon explicit permission, actual phone availability and Play submission restrictions are external gates; pursue useful independent work. Preserve working Render until verified cutover.

## Completion

For each applicable acceptance item: implementation + tests/build + actual UI/API observation where possible + deployment/package provenance. Then independent functionality/spec, security and code-quality reviews must have no unresolved blocking findings. Current community release completion is distinct from all original commerce requirements and measured long-term user/business outcomes. Never manufacture users, CTR lift, search-engine citations or human study evidence.
