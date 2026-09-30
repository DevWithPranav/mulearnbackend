# muLearn Dashboard + Backend + Auth Server — Full Production Audit (every API, every page)

| Item | Value |
|---|---|
| Date | 2026-09-30 (second, exhaustive pass, plus a third pass that measures performance; replaces the first report of the same day) |
| Dashboard repo / branch | `DevWithPranav/mulearn-dashboard` @ `dev` (`50c7052`, 2026-09-25) |
| Backend repo / branch | `DevWithPranav/mulearnbackend` @ `pranav-dev` (`ad02b2a`, 2026-09-16) |
| Backend comparison base | `dev` (`c4a8536`). `pranav-dev` is 194 commits ahead: 137 files, +11,525 / −3,752 lines |
| Auth server repo / branch | `DevWithPranav/authserver` @ `dev` (`c749e90`, 2026-07-17). Unmerged branch `feat/new-auth` (`b790491`, 2026-09-24) was checked for fixes only |
| Scope | Full regression + production audit: **every backend endpoint (1,123 unique route + method pairs)**, **every dashboard page (129 pages)**, the auth server, the integration between them, and the **performance of every endpoint and page** |

**How to read this report.** Issue IDs from the first report are kept (C-01…C-09, H-01…H-20, M-01…M-28, L-01…L-09) so earlier discussions still match. Everything found in this second pass continues the numbering: **C-10, H-21…H-35, M-29…M-59, L-10…L-55**. The performance pass adds **H-36…H-40, M-60…M-70, L-56…L-66**. Section 5 and Appendix E list **every endpoint** with its access level, the roles that got through in testing, whether the dashboard uses it, any crash seen, and the issue IDs that apply. Section 7 and Appendix F list **every page** with what happened when it was opened as each role. Section 10, **Appendix I (every endpoint)** and **Appendix J (every page)** give the measured performance.

---

## How this audit was done

**First pass (static + reading the code)**
1. **Backend route map.** Django was loaded and every URL pattern was listed through the real resolver: **733 URL patterns (728 unique) / 1,123 unique route + method pairs**. The per-endpoint table has 1,140 rows because five URL patterns are declared twice in `urls.py` (Appendix B).
2. **Permission scan** of every view method (`permission_classes`, `authentication_classes`, `role_required`, `RoleRequired`, in-body checks), then checked by hand.
3. **Frontend endpoint map.** All **568 endpoint definitions** in `src/api/endpoints.ts` resolved against the backend.
4. **Call-site check.** All **673 API call sites** parsed: **603 OK**, **11 no backend route**, **2 wrong HTTP method**, **57 built from variables** (checked by hand). This pass also found calls that "resolve" only because a literal path is swallowed by a `<str:…>` route (H-33).
5. **Flow tracing, branch diff, auth-server read-through** (as in the first report).

**Second pass (this report) — the code was run**
6. **Static analysis of the whole backend:** `ruff` (undefined names, unused variables, duplicate imports), a check that every view method signature matches its URL parameters, and a check that every `ModelSerializer` builds and that every `source=` path exists on the model.
7. **Dynamic API test harness.** All 136 backend tables were created in SQLite from the models, filled with generated data plus a hand-made scenario (colleges, a company, IGs, events, a learning circle with a live meeting, jobs, tasks, mentor grants). **19 test users**, one per role (anonymous, Student, Admin, Company, Mentor, Campus Lead, Enabler, Lead Enabler, IG Lead, Campus IG Lead, Intern, Intern Lead, Zonal Lead, District Lead, Fellow, Associate, Tech Team, Discord Moderator, Comic Admin), each with a signed JWT. **Every route and method was called as every role** (**21,660 requests**; writes used an empty body and every call was rolled back). Outbound HTTP (auth server, partners) was mocked. Every 500 was traced to a line of code and checked by hand; test-data artefacts were removed.
8. **Targeted live tests** for the most serious findings (for example C-10, H-22, H-23, M-29, M-52) — each one is marked "verified" in its entry.
9. **Browser crawl of the dashboard.** The dashboard was built (`next build` passes) and run against the local backend. **All 129 pages were opened** in headless Chromium as Anonymous, Student and Admin, and every role-specific page as the matching role (**781 page visits**). For each visit the crawl recorded redirects, JavaScript errors, React errors, failed or error API calls, and error text on screen. The first 176 visits ran in development mode, which also logs API schema mismatches.
10. **Schema contract check.** For every dashboard GET call the live backend response was validated against the dashboard's own Zod schema (198 call sites checked).

**Limits.** The backend ran on SQLite, not MySQL (MySQL-only behaviour — for example case-insensitive text matching — is called out where it matters). External services (auth server, partners, Razorpay, e-mail, Redis, Celery broker) were mocked or replaced in memory. Infra (Netlify, reverse proxy rules, upload limits) is not in the repos. Test data was generated, so some page content (names, numbers) is meaningless; only errors that were confirmed in the code are reported.

**Third pass — performance**
11. **Backend performance harness.** Every GET endpoint was called as every role that could use it on a small and a large copy of the test database, with the cache cleared, recording SQL queries (with the line of code behind each repeated query), response size, rows, paging and side work. Every query was checked against the indexes in `schema.sql`. Write handlers were scanned in code for queries in loops, e-mails and outbound calls inside the request (§10.1).
12. **Page performance crawl.** Every page was opened on the production build with mobile throttling (4× CPU, 150 ms round trip, 1.6 Mbps), recording Web Vitals, JavaScript size and unused code, API calls and their order, prefetches, DOM size and memory; search boxes were tested by typing (§10.1).
13. **Code review of the hot spots** found by 11 and 12 (sidebar data, loaders, barrel imports, retries, leaderboards, rank, imports).

---

## 1. Executive summary

The three branches **are not ready for production together.** The second pass ran the backend and the dashboard for real and found many more problems than reading the code alone showed.

**What works.** About 90% of the dashboard's API calls reach the right backend view with the right method. The production build of the dashboard passes (`next build`, typecheck). Most pages open without errors for the roles they are meant for. Recent backend work has good patterns (row locks on approvals, publish policy, denormalised aggregates).

**What blocks a release (in plain words):**

1. **Anyone can become powerful.**
   - A new account can make itself Admin (C-09), and anyone can log in as any user through Apple sign-in (C-08) — both from the first report.
   - **New:** any Intern can give themselves unlimited karma — verified: one request added 999,999 karma (C-10). Interns can also approve their own leave and deactivate the Intern Lead (H-21).
   - **New:** a lead of a single interest group can make anyone a verified platform Mentor (H-24).
   - **New:** any user can make themselves a verified member of any college or company, and a Campus Lead can "move" to another college with one call and manage it (H-23).
2. **Private data is exposed.** **New:** one public endpoint returns the email and phone number of any user from their muID (H-22). Others leak student details or allow account enumeration (L-17, L-23, L-41, L-42).
3. **Karma can be faked in many ways:** intern verification (C-10), event tasks edited after approval (H-25), learning-circle join/leave loops and forced members (H-10, M-43), junk social links (M-30), plus task deletion that silently wipes karma history (M-39).
4. **Pages and APIs are broken today.**
   - **Crash on load (browser crawl):** company Collaborations (H-30), Event Templates (H-31), Feedback & Impact (H-32).
   - **Public pages do not work for visitors:** every shareable page (public profile, muJourney, interest groups, events, search) sends anonymous visitors to the login page (H-34).
   - **Always fails:** invite-link page for learning circles (H-27), Dynamic Type admin page and Discord leaderboard (H-26, a regression from 2026-08-30), company co-admin status (H-33), all public learning-circle report APIs (H-28), Top-100 leaderboard (M-49), campus student list / member lists (M-47), hackathon organisers (M-53), registration with a wrong invite code (M-52).
   - **Wrong numbers:** muJourney progress (M-29), home "open jobs" count (M-58), impact report (H-32).
   - **Role mismatches between the dashboard and the backend** leave whole pages showing "You do not have the required role" for roles the dashboard lets in: intern pages for Intern Lead/Admin (M-54), manage-interns for Associate (M-38), zonal/district for Admin (M-55), career labs for Fellow (M-56), talent pool for non-companies (M-57).
5. **Money records can be duplicated.** **New:** the donation verification endpoint can be replayed to create extra "paid" donations and extra tax receipts (H-29, M-44).
6. **Deployment and data safety.** Missing DB migration scripts (C-06, H-16, first report). **New:** production runs Django's development server and nothing runs Celery beat, so none of the 10 scheduled jobs run — every college and learning circle shows 0 karma and rank 0, and events, jobs, grants and intern statuses never change on schedule (H-35, M-59). Destructive cascades on delete (H-11, M-39, L-38).

7. **Speed and load (third pass, measured).**
   - The profile API behind the sidebar reads the whole wallet table to compute rank and percentile, on every page load of every user (H-36). Public leaderboards run heavy joins and sorts with no cache — the top-100 list alone makes 301 SQL queries per call (H-37). The karma voucher import gets slower with every voucher ever made and sends one e-mail per row inside the request (H-38).
   - 50 GET endpoints repeat the same query for every row (N+1); the worst export makes 847 queries in one call (M-60…M-63). Event, karma-log, wallet and task filters have no index in `schema.sql`, and 68 of 140 tables are not in `schema.sql` at all (M-64). 21 lists return every row with no paging (M-65).
   - On a normal phone with slow 4G, the median dashboard page downloads 713 KB of JavaScript (65% of it unused during load), shows its main content after 7.7 s, and blocks taps for 2,034 ms (H-39). Every page also downloads a 144 KB loader GIF twice and waits for `user/info` before asking for its own data (H-40). Failing calls are sent 4 times (M-68), and the home page pre-renders dozens of other pages (M-67).

### Findings count

| Severity | First report | Second pass | Performance pass | Total |
|---|---|---|---|---|
| Critical | 9 (C-01…C-09) | 1 (C-10) | 0 | **10** |
| High | 19 (H-01…H-20, H-14 merged) | 15 (H-21…H-35) | 5 (H-36…H-40) | **39** |
| Medium | 28 (M-01…M-28) | 31 (M-29…M-59) | 11 (M-60…M-70) | **70** |
| Low | 9 (L-01…L-09) | 46 (L-10…L-55) | 11 (L-56…L-66) | **66** |
| **Total** | **65** | **93** | **27** | **185** |

Plus the per-endpoint tables (1,140 rows covering all 1,123 endpoints: issues in Appendix E, performance in Appendix I) and the per-page tables (129 rows: problems in Appendix F, performance in Appendix J), which point every endpoint and page to its issues.

### Automated results at a glance

| Check | Result |
|---|---|
| Backend endpoints (unique route + method pairs) | 1,123 (1,140 table rows; 5 URL patterns are declared twice) |
| Endpoints the dashboard calls | 542 |
| Endpoints with at least one issue ID | 428 |
| Endpoints reachable with **no login** | 172 (44 of them change data) |
| Endpoints that returned **HTTP 500** for at least one role in testing | 263 (173 are "wrong method on a shared URL" crashes, L-11 / Appendix H; 35 are anonymous calls that should be 401, L-10; 55 are other bugs, Appendix G) |
| Dashboard pages | 129 (120 under `/dashboard`, 9 auth/onboarding/public) |
| Page visits in the browser crawl | 781 (all pages × Anonymous/Student/Admin + each role's own pages) |
| Pages with a crash, 500, role error or schema error for a role that is allowed on the page | 35 (plus 11 public pages that bounce visitors to login, H-34) |
| Dashboard GET calls checked against live responses | 198 → 112 match, 17 schema mismatches (13 real, 4 caused by test data), 44 API errors (most from placeholder ids) |
| `next build` / typecheck / lint / unit tests | ✅ / ✅ / ✅ (50 warnings) / ❌ 14 failing tests |
| Performance, backend (third pass) | 358 GET endpoints measured on small and large data; 50 with N+1 queries; up to 847 queries in one call (§10.2, Appendix I) |
| Performance, frontend (third pass) | 129 pages measured with mobile throttling; median 713 KB JavaScript per dashboard page, LCP 7.7 s, TBT 2,034 ms (§10.2, Appendix J) |

### Top 15 to fix first

| # | ID | What | Where |
|---|---|---|---|
| 1 | C-09 | Only verified roles in tokens; limit self-requested roles | Auth server + Backend |
| 2 | C-08 | Verify Apple identity tokens | Auth server |
| 3 | C-10, H-21 | Remove `Intern` from all manage-interns APIs; cap and block self-awarded karma | Backend |
| 4 | H-18 | Accept only `tokenType == "access"` | Backend |
| 5 | C-01…C-04, H-15, H-22 | Close the unauthenticated admin/PII endpoints | Backend |
| 6 | H-23 | Stop self-verified org links; tie campus roles to their college | Backend |
| 7 | H-24, M-37 | IG leads must not mint Mentors or change IG code/status | Backend |
| 8 | H-25, H-10, M-43 | Karma integrity (event tasks, LC loops, forced members) | Backend |
| 9 | C-06, H-16, H-35, M-59 | Commit and rehearse all DB migration scripts; run a real app server and Celery beat; register every scheduled task | Backend / infra |
| 10 | H-29, M-44 | Make donation verification idempotent | Backend |
| 11 | H-26 | Fix the pagination helper regression | Backend |
| 12 | H-30…H-34 | Fix the broken company pages and the public pages | Dashboard + Backend |
| 13 | H-27, H-28 | LC invite link page; public LC APIs | Backend |
| 14 | C-07, M-38, M-54…M-57 | One shared role list for every page and its APIs | Both |
| 15 | H-17 | Make CI run the test suites in all three repos | All |

**Top 5 performance fixes** (third pass, details in §10): H-36 (sidebar rank query on every page), H-37 (cache the public leaderboards), H-39 (remove charts and Markdown from the shared bundle), H-40 (do not block pages on `user/info`; drop the 144 KB loader GIF), M-68 (stop retrying 500s).

---

## 2. Critical issues (fix before any release)

### C-01 · Anyone can merge and delete any organization (no authentication)

| Field | Detail |
|---|---|
| Severity | **Critical** |
| Category | Security / Business Logic |
| Repository / branch | mulearnbackend @ `pranav-dev` (already present on `dev`) |
| Location | `api/dashboard/organisation/organisation_views.py:836` — `TransferAPI.post`; route `POST /api/v1/dashboard/organisation/transfer/` |
| Related dependency | Dashboard `src/features/organizations/api/transfer.api.ts` (`transferOrganization`). The page `/dashboard/management/organization-transfer` is limited to Admins only in the edge proxy. |

- **Problem.** `TransferAPI` has no `permission_classes`, no `authentication_classes` and no role decorator. DRF's default permission is `AllowAny` (`REST_FRAMEWORK` in `mulearnbackend/settings.py` sets no default). The view moves every `UserOrganizationLink` from `from_id` to `to_id` and then calls `from_org.delete()`.
- **Why it matters.** A person with no account can send one POST and delete any college or company, and move all its members to another org. Org codes are easy to find (they are public in many list APIs).
- **Expected.** Only authenticated Admins can run it. It runs inside a transaction and is logged.
- **Current.** Open to the internet. No transaction, no audit log.
- **Reproduce.** `curl -X POST https://<api>/api/v1/dashboard/organisation/transfer/ -H 'Content-Type: application/json' -d '{"from_id":"<codeA>","to_id":"<codeB>"}'` → `"Organisations transferred successfully"`.
- **Fix.**
  - Add `permission_classes = [CustomizePermission]` and `@role_required([RoleType.ADMIN.value])`.
  - Wrap the work in `transaction.atomic()` and write an audit log entry.
  - Better: remove this endpoint and use the safer merge endpoint (after fixing H-03).
- **Impact.** Permanent data loss for organizations, wrong campus membership, wrong leaderboards.

### C-02 · Achievement admin endpoints have no role checks and accept expired tokens

| Field | Detail |
|---|---|
| Severity | **Critical** |
| Category | Security |
| Repository / branch | mulearnbackend @ `pranav-dev` (present on `dev`; `pranav-dev` added more endpoints) |
| Location | `api/dashboard/achievement/achievement_views.py`: `AchievementCreateAPIView` (L76), `AchievementUpdateAPIView` (L188), `AchievementDeleteAPIView` (L310), `UserAchievementsIssueAPIView` (L385), `AchievementRuleCreateAPIView` (L588), `AchievementRuleDeactivateAPIView` (L736), `AchievementRuleActivateAPIView` (L764), `SimulateRulesAPIView` (L797), `DebugAchievementAPIView` (L854), `ManualIssueAPIView` (L920), `RevokeAchievementAPIView` (L966), `AuditLogAPIView` (L1014), `AchievementIssueBulkAPIView` (L1075) |
| Related dependency | Dashboard `/dashboard/management/manage-achievements` (Admins only in the UI) |

- **Problem.** These views have no `permission_classes` and no role check. They only call `JWTUtils.fetch_user_id(request)`. That helper decodes the JWT signature but **does not check the custom `expiry` claim**, and it throws `IndexError` (HTTP 500) when there is no `Authorization` header. Only `AchievementRuleDetailAPIView.patch` has `RoleRequired([ADMIN])`.
- **Why it matters.**
  - Any learner with a token (even an expired one) can create achievements, give any achievement to anyone (`manual-issue`, `bulk-issue`), revoke other people's achievements, and turn rules on or off.
  - `simulate/<muid>`, `debug/...` and `audit/<muid>` leak other users' data.
- **Expected.** Admin role required. Token checked by `CustomizePermission` (which checks expiry).
- **Current.** Any validly signed token is accepted.
- **Reproduce.** As a normal learner: `POST /api/v1/dashboard/achievement/manual-issue/` with `{"muid":"<self>","achievement_id":"<id>"}` → success.
- **Fix.**
  - Add `permission_classes = [CustomizePermission]` to every achievement view.
  - Add `@role_required([RoleType.ADMIN.value])` to all admin actions.
  - Make `JWTUtils.fetch_user_id` / `fetch_role` also check `expiry`, or only call them after `CustomizePermission`.
- **Impact.** Fake credentials and achievements, damaged trust in verifiable credentials (VC), privacy leak.

### C-03 · Anyone can replace any user's profile picture (no authentication, user id taken from the body)

| Field | Detail |
|---|---|
| Severity | **Critical** |
| Category | Security / API |
| Repository / branch | Backend @ `pranav-dev` + Dashboard @ `dev` |
| Location | Backend `api/dashboard/user/dash_user_views.py:522` — `UserProfilePictureView.post` (route `POST /api/v1/dashboard/user/profile/update/`). Dashboard `src/features/profile/api/profile.api.ts:203` — `updateProfileImage(profilePic, userId)` sends `user_id` in the form. |
| Related dependency | Cross-repo: the dashboard design depends on the unsafe backend contract |

- **Problem.** The view has no auth. It reads `user_id` from the request body and writes `media/user/profile/<user_id>.png`, overwriting the old file. The only file check is the client-supplied `content_type`.
- **Why it matters.** Anyone can replace any user's avatar (defacement, offensive images) if they know the user's UUID. UUIDs are public: `GET /dashboard/user/search/` is public and returns `id` (see M-15).
- **Expected.** Authenticated user. Target user = the JWT `id`. Image checked with `ImageUploadUtils.validate`.
- **Current.** Unauthenticated, any target, weak content check.
- **Reproduce.** `curl -F user_id=<victim uuid> -F profile=@x.png https://<api>/api/v1/dashboard/user/profile/update/`.
- **Fix.**
  - Backend: add `authentication_classes=[CustomizePermission]`, use `JWTUtils.fetch_user_id`, ignore `user_id` in the body, use `ImageUploadUtils`.
  - Dashboard: stop sending `user_id`.
- **Impact.** Abuse at platform scale. Reputation damage.

### C-04 · Launchpad admin endpoints "authenticate" with an email from the request body

| Field | Detail |
|---|---|
| Severity | **Critical** |
| Category | Security |
| Repository / branch | mulearnbackend @ `pranav-dev` (existing code) |
| Location | `api/launchpad/launchpad_views.py:2565` `LaunchPadUser.post/put`, `:2799` `BulkLaunchpadUser.post`, `:2691` `UserProfile.get/put` (identity from `?current_user=` / body). Other Launchpad views also have no permission class, for example `:845` `GetCompanyInfoAPI.post`, which returns any company's POC name, email and phone for a given `company_id`. |
| Related dependency | Not called by the dashboard (the route `/dashboard/management/manage-launchpad` is in the access map but has no page) |

- **Problem.** These views read `current_user` (an email) from the request body and treat the caller as a Launchpad admin if a `LaunchPadUsers` row with that email and role `ADMIN` exists. No token or password is checked.
- **Why it matters.** Anyone who knows or guesses an admin's email can create or modify Launchpad users and college links, including by bulk Excel upload.
- **Expected.** Use the existing `LaunchpadJWTPermission` or `CustomizePermission`, and take identity from the token.
- **Current.** Identity is claimed by the client.
- **Reproduce.** `POST /api/v1/launchpad/user-college-link/` with `{"current_user":"<admin email>", ...}`.
- **Fix.** Add a permission class to all Launchpad views. Remove `current_user` from the body.
- **Impact.** Full takeover of Launchpad data.

### C-05 · Company sign-up never uploads the verification document; it sends a made-up URL

| Field | Detail |
|---|---|
| Severity | **Critical** |
| Category | Business Logic / API / Cross-repo |
| Repository / branch | mulearn-dashboard @ `dev` (backend accepts it) |
| Location | Dashboard `src/app/(auth)/register/register-client.tsx:211-229` (`handleCompanySignup`), `src/features/auth/api/register.api.ts:109` (`uploadVerificationDocument` returns a base64 `data:` URL). Backend `api/dashboard/company/serializers.py:44` (`verification_document_url = URLField(required=True)`), `:361` (verify requires a document URL). |
| Related dependency | Admin company verification (`PATCH /dashboard/company/verify/<id>/`), public company profile (logo, gallery) |

- **Problem.**
  - When the user uploads a file, the dashboard builds `https://mulearn.org/documents/<file name>`. That URL does not exist. The file itself is never sent anywhere.
  - `normalizeUrl` drops every `data:` / `blob:` URL, so uploaded **logo and gallery images are silently discarded**.
  - The backend has no upload endpoint for these files. Its `URLField` rejects `data:` URLs.
- **Why it matters.** The whole company trust model depends on admins checking a legal document. Admins now see a working-looking link to nothing, and the backend check "must have a document before verify" passes with a fake value.
- **Expected.** The file is uploaded (multipart, or a pre-signed URL). The backend stores it, checks it, and exposes it only to admins.
- **Current.** A fake URL is stored. Logo and gallery are lost with no error to the user.
- **Reproduce.** Register as a company and attach a PDF. Then as admin, open the company detail → document link → 404 on mulearn.org.
- **Fix.**
  - Add `POST /dashboard/company/documents/` (multipart; size and type checks; private storage).
  - The dashboard uploads first, then sends the returned URL.
  - Mark existing companies whose document URL starts with `https://mulearn.org/documents/` for re-upload.
- **Impact.** Fake companies can get verified. Wrong data in public profiles.

### C-06 · Required DB migration for the campus co-lead / execom refactor is missing

| Field | Detail |
|---|---|
| Severity | **Critical** (deployment blocker) |
| Category | Regression / Architecture |
| Repository / branch | mulearnbackend @ `pranav-dev` (commit `c83ccda`, 2026-09-08) |
| Location | `db/campus.py` (`CampusIGChapter.co_lead` → column `co_lead_id`; new `CampusExecomRole` table with no org/role FKs), `utils/types.py:53-58` (role title rename). The commit message says *"alter-1.91.sql: creates/migrates campus_execom_role, adds campus_ig_chapter.co_lead_id, renames existing role titles…"*. **That file is not in the repo.** `alter-scripts/` ends at `alter-1.64.py`. |
| Related dependency | All campus pages in the dashboard (`/dashboard/campus/manage`, campus IG chapters, execom) and event permissions |

- **Problem.** The models are `managed = False` and the project uses hand-written alter scripts. The script this refactor needs was never committed.
- **Why it matters.**
  - Every query that loads `CampusIGChapter` selects `co_lead_id`. Without the column, MySQL raises "Unknown column" → **HTTP 500 on campus chapters, campus details, execom and event scoping**.
  - Existing `"{code} CampusLead"` role rows are not renamed, so current campus IG leads silently lose event rights on the backend (the code now checks `" CampusIGLead"`).
- **Expected.** The migration is committed, reviewed, and run before deploy.
- **Current.** Missing.
- **Reproduce.** Deploy `pranav-dev` on a DB that only has migrations up to 1.64 → open the Campus Manage page → 500.
- **Fix.**
  - Commit `alter-1.91` (create table, add column, rename `"% CampusLead"` → `"% CampusIGLead"` for IG-derived roles, move existing execom rows).
  - Add a deploy check that fails if expected columns are missing.
- **Impact.** Campus features go down. Silent loss of permissions.

### C-07 · Dashboard still checks the old dynamic role name; Campus IG Leads lose access (co-leads never get access)

| Field | Detail |
|---|---|
| Severity | **Critical** (after C-06 is fixed, this becomes the visible break) |
| Category | Regression / Cross-repo / RBAC |
| Repository / branch | Dashboard @ `dev` vs Backend @ `pranav-dev` |
| Location | Dashboard `src/lib/auth/roles.ts:54` (`igCampusLeadRole` → `"${code} CampusLead"`), `src/lib/auth/route-access.ts:256-257` (`/dashboard/manage-events` dynamic check `endsWith(" CampusLead")`), `src/lib/auth/permissions.ts:191-200` (`events:manage`, `events:manage_co_owners`, `events:accept_collaboration`, `events:reject_collaboration`). Backend `utils/types.py:53` (`"{code} CampusIGLead"`), `:57` (`"{code} CampusIGCoLead"`), `api/dashboard/events/manage_views.py:61-66` (`_can_create_event` checks `' CampusIGLead'` only). |
| Related dependency | The edge proxy (`src/proxy.ts`) uses these checks to allow or block pages |

- **Problem.** The backend renamed the role and added a co-lead role. The dashboard was not updated. `"WEBDEV CampusIGLead".endsWith(" CampusLead")` is `false`.
- **Why it matters.** Campus IG Leads are sent back to `/dashboard?unauthorized=true` when they open Manage Events, and they lose the co-owner and collaboration actions. Co-leads (`CampusIGCoLead`) get no event rights in either repo, even though the backend assigns the role.
- **Expected.** Both repos use one naming rule, ideally from a shared constant or an API such as `GET /roles/meta`.
- **Current.** Names differ, so users are locked out.
- **Reproduce.** Give a user `"WEBDEV CampusIGLead"` (the new backend flow) → open `/dashboard/manage-events` → redirected as unauthorized.
- **Fix.**
  - Dashboard: accept `" CampusIGLead"` and `" CampusIGCoLead"`, and keep `" CampusLead"` during the migration window.
  - Backend: decide whether co-leads can create or manage events, and add that to `_can_create_event` and `decide_publish_status`.
- **Impact.** Campus IG event work is blocked for all campus chapters.

### C-08 · Apple mobile sign-in does not check the token signature, so anyone can log in as any user

| Field | Detail |
|---|---|
| Severity | **Critical** |
| Category | Security (account takeover) |
| Repository / branch | authserver @ `dev` (fixed on unmerged `feat/new-auth`). Also reachable through the backend proxy on `pranav-dev` |
| Location | Auth server `muauth/views.py:986-1069` — `AppleMobileAuthAPIView.post` (`jwt.decode(identity_token, options={"verify_signature": False})`, then falls back to `request.data.get("email")`); route `POST /api/v1/auth/apple-mobile/`. Same unverified decode in `AppleLoginCallbackAPIView` (L915). Backend `api/auth/auth_views.py` `AppleMobileAuthProxyAPI` forwards `identity_token` and `email` unchanged. |
| Related dependency | Every system that trusts auth-server JWTs: backend, dashboard, mobile apps |

- **Problem.** The view decodes the "Apple" token without checking who signed it, and it does not check `iss`, `aud` or `exp`. If the token has no email, it takes the email from the request body. It then finds the user by email and returns a fresh access token and a 7-day refresh token. `APPLE_CLIENT_ID` is not needed for this path.
- **Why it matters.** A person can forge a JWT with any email (for example an admin's) and receive that user's tokens. This is a full account takeover with no password, OTP or Apple account needed.
- **Expected.** Verify the token with Apple's public keys (`https://appleid.apple.com/auth/keys`), and check `iss = https://appleid.apple.com`, `aud = <our client id>` and `exp`. Take the email only from the verified token.
- **Current.** Any JWT-shaped string is accepted.
- **Reproduce.** `POST /api/v1/auth/apple-mobile/` with `{"identity_token":"<any unsigned JWT>","email":"<victim email>"}` → `accessToken` + `refreshToken` for the victim. (Do not run this against production.)
- **Fix.**
  - Merge the `verify_apple_identity_token` fix from `feat/new-auth` into `dev` and deploy it.
  - Until then, turn off `apple-mobile/` and `apple/login/callback/` on the auth server and the backend proxy.
  - Rotate the JWT secret afterwards if logs show suspicious Apple logins.
- **Impact.** Any account can be taken over, including every Admin.

### C-09 · A new account can make itself Admin: tokens include roles that were never approved

| Field | Detail |
|---|---|
| Severity | **Critical** |
| Category | Security / RBAC / Cross-repo |
| Repository / branch | authserver @ `dev` + Backend @ `pranav-dev` + Dashboard @ `dev` |
| Location | Auth server `utils/views.py:64` `generate_jwt` and `muauth/views.py:564` `GetAccessToken.post` both use `UserRoleLink.objects.filter(user=user)` with **no `verified=True` filter** (the unused `generate_access_token` in `utils/views.py` has the filter; `feat/new-auth` still has the bug). Backend `api/register/serializers.py:302` accepts any role ID at sign-up (`queryset=Role.objects.all()`) and saves it with `verified=False`. `api/register/register_views.py:233` `GET /register/role/list/` publicly lists every role, including "Admins", with its ID. Backend `utils/permission.py` `role_required` trusts JWT roles. Backend `dash_user_serializer.py:80` `get_roles` also returns unapproved roles. |
| Related dependency | Dashboard proxy (JWT roles), `usePermissions` and server `requireRole` (roles from `user/info`) |

- **Problem.** Role requests are stored as unverified `UserRoleLink` rows and wait in the admin verification queue. But the auth server puts every link into the token, so the requested role works at once everywhere.
- **Why it matters.** Anyone can sign up with `role = <Admins id>` (or "Campus Lead", "Enabler", "Mentor", …). On the first login they are a full admin in the backend, in the edge proxy and in the dashboard. This is complete platform takeover by self-service.
- **Expected.** Tokens and `user/info` contain only approved, active roles. Sign-up only allows a small list of self-service roles.
- **Current.** Unapproved roles are treated as real roles.
- **Reproduce.**
  1. `GET /api/v1/register/role/list/` → find the ID of "Admins".
  2. `POST /api/v1/register/` with `user.role = <that id>`.
  3. Log in → decode the access token → `roles` contains `"Admins"`.
  4. Call any `@role_required([ADMIN])` endpoint → it succeeds.
  (Do not run this against production.)
- **Fix.**
  - Auth server: filter `verified=True` in `generate_jwt` and `GetAccessToken` (and skip revoked or inactive links once the auth server model has those columns).
  - Backend: add an allowlist for self-requested roles in `UserSerializer`, and filter `verified=True, is_active=True` in `user/info`.
  - Check for accounts that already have unverified privileged role links and remove them.
- **Impact.** Total loss of access control.

### C-10 · Any Intern can give themselves unlimited karma (verified in a live test)
| Field | Detail |
|---|---|
| Severity / Category | **Critical** · Security / Business Logic (karma integrity) |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/dashboard/manage_interns/tasks/tasks_views.py:160` `ManageInternTaskVerifyAPI.post` (route `POST /api/v1/dashboard/manage-interns/tasks/<task_id>/verify/`). Related: interns can also approve their own timesheets and weekly reviews, which award fixed karma with streak multipliers and milestone bonuses (`manage_interns/reviews/review_views.py:224-300`, `:333-390`) |
| Dependency | Dashboard `/dashboard/management/manage-interns/tasks` (the UI is only shown to Admin / Associate / Intern Lead, but the API is open to every Intern) |

- **Problem.** The view allows the roles `Admin`, `Intern` and `Intern Lead`. It reads `karma_awarded` from the request body and only checks that it is not negative. There is no upper limit and no check that the caller is not verifying their own task. It then writes an approved `KarmaActivityLog` and adds the amount to the intern's `Wallet`.
- **Why it matters.** Karma drives levels, leaderboards, campus rank and rewards. One intern can make themselves (or a friend) number one on every leaderboard in one request.
- **Expected.** Only Intern Lead / Admin can verify. The karma comes from a fixed table (or has a small maximum). Nobody can verify their own task.
- **Current.** Any Intern can verify any task, including their own, with any karma value.
- **Reproduce (done in this audit).** As a plain Intern: create or pick an intern task assigned to yourself, then `POST /api/v1/dashboard/manage-interns/tasks/<id>/verify/` with `{"karma_awarded": 999999}`. Result in the test run: `200 "Task verified successfully"`, wallet **500 → 1,000,499**.
- **Fix.** Change the role list to `[ADMIN, INTERN_LEAD]` on all manage-interns views (see H-21). Add a hard maximum (for example 100) and reject `task.assigned_to_id == caller`. Block self-approval of timesheets and weekly reviews. Add an audit report of all `#intern-task-verified` karma already awarded.
- **Impact.** Leaderboards and levels can be faked; existing karma data may already be polluted.

---

## 3. High-priority issues

### H-01 · Any logged-in user can approve or reject organization requests
| Field | Detail |
|---|---|
| Severity / Category | High · Security / RBAC |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/dashboard/organisation/organisation_views.py:859` `UnverifiedOrganizationsListAPI.get`, `:893` `VerifyOrganizationAPI.post` |
| Dependency | Dashboard Role Verification → "College" tab (`VerifyOrgsView`), Admins only in the proxy |

- **Problem.** Both views only require a valid token. There is no Admin check.
- **Why it matters.** Any learner can list every pending org request (with the submitter's name) and approve it into any real organization. That creates a verified `UserOrganizationLink` for the submitter. Campus membership then controls campus event authority (see `_is_active_campus_member`).
- **Expected / Current.** Admin only / any user.
- **Reproduce.** As a learner: `POST /api/v1/dashboard/organisation/verify/<uorg_id>/` with `{"verified":true,"org_id":"<campus id>"}`.
- **Fix.** Add `@role_required([RoleType.ADMIN.value])` to both views.
- **Impact.** Users can join any campus and gain campus-level power.

### H-02 · Rejecting an organization request always fails
| Field | Detail |
|---|---|
| Severity / Category | High · API / Cross-repo |
| Repo / branch | Dashboard @ `dev` + Backend @ `pranav-dev` |
| Location | Dashboard `src/features/organizations/schemas/verification.schema.ts` (`toVerifyOrgPayload` sends `{verified:false}` with no `org_id`; the comment points to `OrganizationVerifySerializer.validate`). Backend `api/dashboard/organisation/serializers.py:463` (`org_id = PrimaryKeyRelatedField(required=True)`; no `validate()` method exists). |

- **Problem.** The backend requires `org_id` even when rejecting.
- **Expected.** A rejection needs no org.
- **Current.** 400 `"org_id: This field is required."` and a red toast.
- **Reproduce.** Role Verification → College → Reject.
- **Fix.** Backend: `org_id = PrimaryKeyRelatedField(required=False, allow_null=True)`, plus `validate()` that requires `org_id` only when `verified` is true.
- **Impact.** Admins cannot clear bad requests, so the queue keeps growing.

### H-03 · Organization merge preview always fails, so the merge flow is blocked; the preview data is also wrong
| Field | Detail |
|---|---|
| Severity / Category | High · API / Business Logic |
| Repo / branch | Both |
| Location | Dashboard `src/features/organizations/api/transfer.api.ts:21` (`GET ...merge_organizations/<id>/?source_org=<code>`), `components/transfer/transfer-view.tsx:189-207` (step 2 only after preview succeeds). Backend `organisation_views.py:556` (`OrganizationMergerSerializer(destination, data=request.data)` on GET), `serializers.py:280-345` (`get_update_summary`). |

- **Problem.**
  1. On GET the backend reads `source_org` from the request body, which is empty for GET. The dashboard sends a query parameter. So it always returns "source_org is required".
  2. Even when it works, the summary counts rows linked to the **destination**, not the source.
  3. `source_org` is `write_only`, so `previewData.source_org` is undefined in the UI.
- **Expected.** The preview shows what will move from the source.
- **Current.** The admin can never reach the "Execute merge" step.
- **Fix.**
  - GET: read `request.query_params` and compute the summary for `source_org`.
  - Return the `source_org` code.
  - See M-06 for problems in the merge logic itself.
- **Impact.** Admins cannot clean up duplicate colleges. They may fall back to the unsafe C-01 endpoint.

### H-04 · The new notification feed hides all broadcasts and all notification links
| Field | Detail |
|---|---|
| Severity / Category | High · Cross-repo / Regression |
| Repo / branch | Backend @ `pranav-dev` (commit `b87f3b0`) + Dashboard @ `dev` |
| Location | Backend `api/notification/notification_view.py:57` `NotificationListView` (queries `Notification` only), `api/notification/serializers.py:10` `NotificationSerializer` (no `url`, `redirect_url` or `source`). Dashboard `src/features/notification/schemas/notification.schema.ts` (`NotificationItemSchema` requires `source` and `redirect_url`), `components/notification-item.tsx:39` (link from `redirect_url`). |

- **Problem.**
  - The backend has **57 places** that call `NotificationUtils.insert_notification(..., url=...)`. They write the link into the legacy `url` column, which the feed never returns.
  - **13 places** call `BroadcastUtils.create_broadcast(...)`: event published, learning circle created, admin `broadcast/create/`. Those rows are in `broadcast_notification`, which no user endpoint lists any more. The old `GET /notification/list/` (personal + broadcasts) was removed.
- **Expected.** A unified feed with personal and broadcast items and a deep link, as the dashboard schema describes.
- **Current.** No notification has a link. Broadcasts are never shown. Admin "global broadcast" creation does nothing a user can see.
- **Fix.**
  - Serialize `redirect_url = obj.redirect_url or obj.url` and `source`.
  - Merge active broadcasts that match the user's audience (global, campus, IG, event interest) into the feed, or fan them out into `Notification` rows at creation time.
- **Impact.** Users miss event launches and approvals. Admin announcements are invisible.

### H-05 · "Send announcement" (admin) calls an endpoint that does not exist
| Field | Detail |
|---|---|
| Severity / Category | High · API / Missing functionality |
| Repo / branch | Dashboard @ `dev` (commit `e4f5ae9 "Admin broadcast fixed"`) |
| Location | Dashboard `src/features/notification/api/notification.api.ts:112` `dispatchAdminBroadcast` → `POST /api/v1/notification/admin/broadcast/`, used by `components/manage/admin-broadcast-dialog.tsx`. Backend: no route. `ADMIN_BROADCAST` is commented out in `api/notification/types.py:26-48`. |

- **Current.** 404, then the toast "Failed to send announcement".
- **Fix.** Build `NotificationService.dispatch(ADMIN_BROADCAST)` with an Admin check, or hide the dialog until it exists.
- **Impact.** The feature is advertised but broken.

### H-06 · Mentor home "Accept session request" always fails; "Decline" uses an admin-only API
| Field | Detail |
|---|---|
| Severity / Category | High · API / Business Logic |
| Repo / branch | Dashboard @ `dev` |
| Location | `src/features/home/api/home.api.ts:212` `acceptSessionRequest` → `POST /mentor/session/participant/list/<id>/`. That route only has GET (`MentorParticipantListAPI`) → **405**. It also sends `user: <the mentor's own muid>` and `participant_role:"MENTOR"`. `home.api.ts:225` `declineSessionRequest` → `PATCH /mentor/session/admin/verify/<id>/`, which is `@role_required([ADMIN])` → 400 for mentors, and would reject the whole session. Used by `components/mentor/session-requests-card.tsx`. |

- **Expected.** Use `PATCH /mentor/session/student-requests/<session_id>/verify/` (`MentorStudentRequestVerifyAPI`) for both accept and decline.
- **Current.** Both buttons fail for every mentor.
- **Fix.** Change the endpoints and the payload. Invalidate the student-request queries after success.
- **Impact.** Mentors cannot handle requests from their home page.

### H-07 · New unified Role Verification page (PR #527) depends on backend features that don't exist
| Field | Detail |
|---|---|
| Severity / Category | High · Cross-repo / UX |
| Repo / branch | Dashboard @ `dev` (commits `26a537c`, `ecc91c8`) vs Backend @ `pranav-dev` |
| Location | Dashboard `src/features/role-verification/api/role-verification.api.ts` (`?role=Enabler`, `sortBy=created_at`), `lib/role-rows.ts` (client-side filter "added 2026-09-25" on the backend), `lib/sort-contract.test.ts` (claims `created_at` is a backend sort field), `components/role-verification-table.tsx` (column "Requested" = `created_at`; CSV `?role=`). Backend `api/dashboard/user/dash_user_views.py:254` `UserVerificationAPI.get` (no `role` filter; sort fields lack `created_at`), `dash_user_serializer.py:253` (no `created_at`). |

- **Problem.**
  - The backend returns every unverified role link (all roles). The dashboard then filters "Enabler" rows **on the current page only**. Page counts and totals are for all roles, so pages can be empty while "Showing N results" is shown.
  - Sorting by "Requested" does nothing.
  - The "Requested" column is always "—".
  - CSV export contains all roles.
- **Expected.** Server-side `role` filter, `created_at` sort, and a `created_at` field.
- **Fix.**
  - Backend: add `role = request.query_params.get("role")` → `filter(role__title=role)`, add `"created_at": "created_at"` to the sort fields and the serializer, and apply the same to `UserVerificationCSV`.
  - Also refuse (server-side) to verify Mentor or Company links through this endpoint.
- **Impact.** Admins miss requests. Verification is slow.

### H-08 · Uploads larger than 2.5 MB fail even though UI and validators allow 5–10 MB
| Field | Detail |
|---|---|
| Severity / Category | High · Bug / Cross-repo |
| Repo / branch | Backend @ `pranav-dev` + Dashboard @ `dev` |
| Location | Backend `mulearnbackend/middlewares.py:95-98` (`UniversalErrorHandlerMiddleware.__call__` does `_ = request.body` on every request), `settings.py` (no `DATA_UPLOAD_MAX_MEMORY_SIZE`, so Django's default 2.5 MB applies), `utils/utils.py` (`ImageUploadUtils.MAX_SIZE_BYTES = 5 MB`). Dashboard `components/ui/file-upload.tsx` (10 MB), `profile.api.ts` (`COVER_PIC_MAX_BYTES = 5 MB`), `register-role-details.tsx` (10 MB / 5 MB). |

- **Problem.** Reading `request.body` raises `RequestDataTooBig` when `Content-Length > DATA_UPLOAD_MAX_MEMORY_SIZE`, before any view runs. Django turns that into a bare 400.
- **Current.** Any upload between about 2.5 MB and 10 MB fails with a generic error. This covers event banners, cover pictures, IG images, excel imports and bulk issue files.
- **Fix.**
  - Only cache the body for small JSON requests, or catch the exception when logging.
  - Set `DATA_UPLOAD_MAX_MEMORY_SIZE` to match the product limit.
  - Make the dashboard limits match the backend. Check the nginx `client_max_body_size` too.
- **Impact.** Users see failed uploads with no clear reason.

### H-09 · A campus event creator can approve their own event; the campus check uses the wrong field
| Field | Detail |
|---|---|
| Severity / Category | High · Business Logic / RBAC |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/dashboard/events/manage_views.py:1869` `CampusEventApproveAPI.post` |

- **Problem.**
  1. There is no `event.created_by_id == user_id` check. `CompanyEventApproveAPI` has one. An Enabler or Lead Enabler creates a campus event → it goes to `pending_campus_approval` (only Campus Lead / Zonal / District can publish directly) → the **same user** approves it → published.
  2. Membership is checked against `event.scope_org_id`, but ownership and publish use `event.organiser_org_id`. A campus event scoped to another campus (or with scope `global`, where `scope_org` is empty) is either approvable by the wrong campus or by nobody except Admins.
- **Expected.** Different approver; membership of `organiser_org`.
- **Fix.** Add a self-approval guard. Use `organiser_org_id` for CAMPUS events and the chapter's org for CAMPUS_IG events.
- **Impact.** The approval step can be bypassed. Events get stuck.

### H-10 · Learning-circle karma can be farmed
| Field | Detail |
|---|---|
| Severity / Category | High · Business Logic / Security |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/dashboard/learningcircle/learningcircle_views.py:470` `LearningCircleJoinAPI.post` (awards `#lc-meet-join` karma on every join), `:532` `delete` (removes the attendee row and keeps the karma), `:140` `LearningCircleView.post` (awards `#lc-meet-create` on every circle create), `:210` `delete` (no `remove_karma`). `utils/karma.py:8` `add_karma`. |

- **Problem.** During a live meeting, a member with the meet code can repeat POST join → DELETE leave → POST join. Each join adds karma. A user can also create and delete circles in a loop. There is no idempotency key such as "one award per (user, meeting)".
- **Expected.** One award per user per meeting and per circle. Reverse the karma when the action is undone.
- **Fix.** Before awarding, check whether a `KarmaActivityLog` already exists for (user, task, meeting). Store `meet_id` in the log. Call `remove_karma` when leaving or deleting. Add rate limits.
- **Impact.** The leaderboard can be manipulated, and karma loses its meaning.

### H-11 · Deleting an interest group cascades into karma history; any static "IG Lead" can do it
| Field | Detail |
|---|---|
| Severity / Category | High · Business Logic / Data consistency |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/dashboard/ig/dash_ig_view.py:496-527` `InterestGroupAPI.delete` (`@role_required([ADMIN, IG_LEAD])`, `ig.delete()`); cascades: `db/task.py:170` `TaskList.ig CASCADE` → `:258` `KarmaActivityLog.task CASCADE`; also `learning_circle.ig`, `campus_ig_chapter.ig`, `impact_project.ig`, `user_ig_link.ig` |
| Dependency | Dashboard `features/manage-ig/components/manage-ig-table.tsx:174` (delete button) |

- **Problem.**
  - A hard delete removes the IG's tasks and all karma logs for those tasks, but `Wallet.karma` is not recalculated. Learning circles and campus chapters are deleted too.
  - The global "IG Lead" role (not just Admins) is allowed to do this for **any** IG.
  - Role cleanup deletes `CampusIGLead` but not `CampusIGCoLead` (and not the old `CampusLead`).
- **Expected.** Admin-only soft delete (the new `deactivate` endpoint exists) and no loss of karma history.
- **Fix.** Replace delete with deactivate in the UI. Limit hard delete to Admin with an "no tasks / no karma logs" rule. Change the FKs to `PROTECT` or `SET_NULL` where history matters.
- **Impact.** Permanent loss of user achievements. Karma totals no longer match the logs.

### H-12 · Company co-admin invitations cannot be accepted from the dashboard
| Field | Detail |
|---|---|
| Severity / Category | High · Cross-repo / Missing functionality |
| Repo / branch | Dashboard @ `dev` |
| Location | `src/features/company-jobs/components/admin/company-admins-client.tsx:63-77` (shows `pending_invitations` from `useUserCompanyStatus`) is mounted at `/dashboard/company/admin`. `src/lib/auth/route-access.ts:277` limits `/dashboard/company*` to `ROLES.COMPANY`. The backend supports delegates (`company_views.py:19` `is_company_owner_or_admin`, `dash_mentor_helper.py:144`). |

- **Problem.** Invitees and accepted delegates never have the `Company` role (the backend says only the owner gets it). The edge proxy sends them away before the page renders.
- **Expected.** A place any user can reach to accept an invite (profile, notifications), plus a delegate view of the company dashboard.
- **Fix.** Add a dynamic check to `/dashboard/company` (owner OR accepted delegate OR company mentor, from `user-status`). Show invites on `/dashboard`.
- **Impact.** The whole delegate feature cannot be used.

### H-13 · Mentor-created company jobs cannot be approved from the UI
| Field | Detail |
|---|---|
| Severity / Category | High · Missing functionality |
| Repo / branch | Both |
| Location | Backend `api/dashboard/company/job_serializers.py:64-68` (non-owner → `Pending Approval`), `job_views.py:107-111` (notification URL `/dashboard/company/jobs/pending/`). Dashboard: `fetchPendingJobs`, `approveJob`, `rejectJob`, `requestJobChanges` (`features/company-jobs/api/jobs.api.ts:705-756`) and their hooks are **not used by any component**. There is no `/dashboard/company/jobs/pending` page (the path falls into `[jobId]="pending"`). |

- **Current.** Jobs posted by company mentors stay pending forever, and the notification link opens a broken job page.
- **Fix.** Add a "Pending approval" tab on company jobs with approve / reject / request-changes, and fix the notification URL.
- **Impact.** The company-mentor hiring flow does not work.

### H-14 · (Moved to C-09)
This item was first marked "High, needs confirmation", because the auth server was not yet reviewed. The auth server review confirmed that tokens include unapproved roles, so it is now **C-09 (Critical)**.

### H-15 · Unauthenticated integration proxies use server secrets
| Field | Detail |
|---|---|
| Severity / Category | High · Security |
| Repo / branch | Backend @ `pranav-dev` (existing code) |
| Location | `api/integrations/qseverse/qseverse_views.py:19` `IssueVerifiableCredentialView` (POST, adds `api_key` and sends email), `:53` `GetAllConnectedUsersView` (lists connected users with **emails**), `:81`, `:119`. `api/integrations/wadhwani/wadhwani_views.py` `WadhwaniAuthToken.post` (runs the OAuth client-credentials grant with `WADHWANI_CLIENT_SECRET` and **returns the partner access token to the caller**), `WadhwaniCourseDetails` (no auth). |

- **Problem.** No permission class. Anyone can issue verifiable credentials in muLearn's name, read users' emails, and get a live Wadhwani partner access token.
- **Fix.** Admin-only, or a backend API key (`BackendApiKeyPermission`). Add rate limits.
- **Impact.** Fake credentials, privacy leak, API quota abuse.

### H-16 · Most schema changes on `pranav-dev` have no migration script in the repo
| Field | Detail |
|---|---|
| Severity / Category | High · Regression / Architecture |
| Repo / branch | Backend @ `pranav-dev` |
| Location | New or changed columns with `managed=False` models and no script in `alter-scripts/`: `notification` (type, category, context, entity_type, entity_id, actor_id, is_read, read_at, is_archived, dedupe_key, redirect_url, batch_id; title 50→100, description 200→300), `learning_circle.cached_total_karma/cached_rank`, `organization.cached_total_karma/cached_member_count`, `user_lvl_link.grit/last_level_down_at`, new tables `community_partner`, `ig_community_partner_link`, `ig_media_content_link`, `hiring`, `achievement_eligibility_grant`, `campus_execom_role` (C-06). Only `alter-1.63.py` and `alter-1.64.py` (mentor) were added. `schema.sql` is out of date (it has no `campus_ig_chapter`). |

- **Why it matters.** Deploying code without these columns returns 500 on the related endpoints. Ops cannot know what to run.
- **Fix.** Put all DDL in versioned scripts (or move to Django migrations with `managed=True`). Add a CI job that builds a DB from scratch and runs a smoke test.

### H-17 · Dashboard unit tests fail on `dev`; the job form doesn't enforce backend limits; CI runs no tests in either repo
| Field | Detail |
|---|---|
| Severity / Category | High · Regression / Process |
| Repo / branch | Dashboard @ `dev`; Backend @ `pranav-dev` |
| Location | `src/features/company-jobs/schemas/jobs.form.test.ts` (**14 failing tests**) vs `schemas/jobs.schema.ts:983` `JobFormSchema`; empty or non-Vitest test files `src/features/events/lib/events.policy.test.ts` (0 bytes) and `src/features/mujourney/utils/markdown.test.ts` (a standalone script). `.github/workflows/ci.yml` runs only lint and typecheck. The backend workflows only deploy (tests exist under `api/**/tests` but never run). |

- **Problem.** `JobFormSchema` does not check title ≤ 75, location ≤ 75, salary_range ≤ 36, experience ≤ 20, the `job_type` enum, `hourly_rate` Decimal(10,2), duration pairing, or compensation per job type. The backend model enforces these (`db/job.py`).
- **Current.** Users fill in a long multi-step job form and then get a 400 at the end. The test regression was merged unseen.
- **Fix.**
  - Restore the schema rules.
  - Delete or convert the two broken test files.
  - Add `bunx vitest run` to CI.
  - Add `pytest` with a MySQL service to the backend CI.

### H-18 · The backend accepts a refresh token as an access token
| Field | Detail |
|---|---|
| Severity / Category | High · Security / Cross-repo |
| Repo / branch | Backend @ `pranav-dev` + authserver @ `dev` |
| Location | Backend `utils/permission.py` `JWTUtils.is_jwt_authenticated` (checks signature, `id` and `expiry` only; never checks `tokenType`). Auth server `utils/views.py:64` `generate_jwt` signs access and refresh tokens with the same key and the same claims (`id`, `muid`, `roles`, `expiry`), only `tokenType` differs. |

- **Problem.** A refresh token (valid 7 days) works as a Bearer token on every backend endpoint.
- **Why it matters.**
  - The roles inside it are frozen at login time for 7 days, so a revoked admin keeps admin power for a week.
  - Logout does not help: the auth server's global logout only blocks the refresh endpoint, and the backend never checks it.
  - The dashboard keeps the refresh token in a JavaScript-readable cookie (M-23), so any XSS gives a 7-day admin credential.
- **Expected.** The backend accepts only `tokenType == "access"`.
- **Fix.** In `is_jwt_authenticated`, reject tokens where `tokenType != "access"`. Stop putting `roles` into refresh tokens.
- **Impact.** Revocation and logout do not work for anyone holding a refresh token.

### H-19 · Password and OTP guessing is not properly limited; the IEDC login is an open password oracle
| Field | Detail |
|---|---|
| Severity / Category | High · Security |
| Repo / branch | authserver @ `dev` (OTP code unchanged on `feat/new-auth`) |
| Location | `muauth/views.py:25-173` `UserAuthenticationAPI.post`, `:660` `RequestMuidOtp.post`, `:696` `IedcLogin.post` |

- **Problem.**
  1. **IEDC login has no limit and leaks the answer.** `POST /api/v1/auth/iedc-login/` checks the password with no attempt limit and no log. A wrong password returns 400 "Invalid password". A correct password crashes with HTTP 500, because the code reads `user.fullname` (the field is `full_name`). So the status code tells an attacker when a guess is right, with no lockout. It also says "Invalid muid or mails" for unknown users (account enumeration).
  2. **Lockout is per typed identifier.** The main login locks after 5 failures in 30 minutes, keyed on the exact `emailOrMuid` string. Email and muid are separate counters for the same user.
  3. **Weak OTP.** `random.randint(0, 99999)` gives only 100,000 values (the first digit is always 0), from a non-secure random generator. Old OTPs are not deleted when a new one is requested, so several can be valid at once. The check `OtpVerification.objects.filter(otp=otp).first()` looks up by OTP value across **all** users, so two users with the same OTP can block each other.
  4. `request-otp/` has no rate limit (email flooding) and returns "Invalid muid or email" for unknown users (account enumeration).
- **Expected.** One limiter per **user** for every login route, a secure 6-digit OTP (`secrets.randbelow(10**6)`), one active OTP per user, looked up by user and OTP together, and the same response for known and unknown accounts.
- **Fix.**
  - Remove or fix `iedc-login` (use `full_name`, add the same limiter, and return tokens or nothing).
  - Key the limiter on `user.id` after lookup, plus a per-IP limit.
  - Rewrite OTP creation and lookup as above.
  - Rate-limit `request-otp`.
- **Impact.** Accounts with weak passwords can be taken over. Users can be flooded with OTP emails.

### H-20 · Every login waits on a third-party IP lookup with no timeout; a failure breaks login
| Field | Detail |
|---|---|
| Severity / Category | High · Reliability / Privacy |
| Repo / branch | authserver @ `dev` |
| Location | `utils/views.py` `CustomHTTPHandler.get_location` (`requests.get("https://ipinfo.io/<ip>/json")` with no timeout and no error handling) and `get_user_agent` (which may fail when there is no User-Agent header), called by `get_user_info` at the start of password, OTP and Google logins |

- **Problem.**
  - If ipinfo.io is slow, every login hangs. If it is down, rate-limited or returns non-JSON, the exception is not caught and login returns HTTP 500.
  - It uses `REMOTE_ADDR`, which behind the reverse proxy is the proxy's IP. So the saved location is wrong anyway.
  - Each user's IP is sent to a third party.
- **Expected.** Login never depends on analytics.
- **Fix.** Log login attempts without the lookup (or enrich them later in a background job). Use a short timeout and catch all errors. Use the client IP from `X-Forwarded-For`, as `get_client_ip_address` already does.
- **Impact.** An ipinfo.io outage takes down all logins.

### H-21 · A plain "Intern" can use every intern-management API
| Field | Detail |
|---|---|
| Severity / Category | High · Security / RBAC |
| Repo / branch | Backend @ `pranav-dev` |
| Location | All views in `api/dashboard/manage_interns/` — `interns_views.py` (`ManageInternAPI` get/post/patch/delete), `tasks/tasks_views.py`, `reviews/review_views.py`, `leave/leave_views.py:56` (`patch` = approve/reject leave) — use `role_required([ADMIN, INTERN, INTERN_LEAD])` |
| Dependency | Dashboard `/dashboard/management/manage-interns/*` (route-access allows Admin, Associate, Intern Lead — see M-38) |

- **Problem.** The manage-interns APIs accept the normal `Intern` role. In the test run the Intern persona could update and deactivate other interns (`DELETE manage-interns/interns/<id>/` → "Intern deactivated successfully"; this also deletes the target's Intern / Intern Lead role links).
- **Why it matters.** An intern can approve their own leave (the leave review has no "reviewer is not the requester" check), approve their own timesheets and weekly reviews (each approval awards karma), create and verify tasks (C-10), onboard new people as interns, and remove the Intern Lead.
- **Expected / Current.** Admin + Intern Lead (+ Associate if that is the product decision) / every Intern.
- **Reproduce.** Log in as an Intern → `PATCH /api/v1/dashboard/manage-interns/leave/<own_leave_id>/` with `{"action":"approve"}`.
- **Fix.** Remove `RoleType.INTERN.value` from every `role_required` in `api/dashboard/manage_interns/**`. Block self-review (`leave.user_id != caller`). Keep the intern's own APIs under `api/dashboard/intern/**`.
- **Impact.** The whole intern program (attendance, leave, reviews, karma) can be manipulated by interns.

### H-22 · Anyone can read any user's email and phone number (no login needed)
| Field | Detail |
|---|---|
| Severity / Category | High · Security / Privacy (PII leak) |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/register/register_views.py:304` `LearningCircleUserViewAPI.post` (route `POST /api/v1/register/lc/user-validation/`) |
| Dependency | Not used by the dashboard (legacy helper) |

- **Problem.** The view has no authentication. It reads a `muid` from the request **header** and returns the user's `id`, `muid`, full name, **email and phone**.
- **Why it matters.** muIDs are public (leaderboards, profiles, search, LC member lists). Anyone can harvest emails and phone numbers of all users, including admins.
- **Expected / Current.** Not public (or return only a yes/no) / full PII to anonymous callers.
- **Reproduce (done).** `curl -X POST -H "muid: admin@mulearn" https://<api>/api/v1/register/lc/user-validation/` → `200 {"email": "...", "phone": "..."}`.
- **Fix.** Delete the endpoint, or require `CustomizePermission` and return only `{"exists": true}`.
- **Impact.** Mass PII exposure; phishing and SIM-swap risk for users; legal risk (DPDP Act).

### H-23 · Any user can make themselves a verified member of any organization (and a Campus Lead can "move" to any college)
| Field | Detail |
|---|---|
| Severity / Category | High · Security / Business Logic |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/dashboard/user/dash_user_views.py:557` `UserAddOrgAPI.post` + `dash_user_serializer.py:569` `UserOrgLinkSerializer.create` (sets `verified=True` for every org type; non-college orgs get a new duplicate row each call). Same effect through `PATCH /dashboard/college/change-college/` and `PATCH /dashboard/profile/` `communities` (M-31) |
| Dependency | Dashboard onboarding (`features/onboarding/api/onboarding.api.ts:93`), profile "change college" (`features/profile/api/profile.api.ts:419`) |

- **Problem.** The serializer accepts **any** `Organization` id (college, company, community) and stores the link as `verified=True`. The view has no auth class (it calls `JWTUtils` directly, so expired tokens also work, and anonymous calls crash with a 500).
- **Why it matters.** Campus-scoped power is based on the caller's own college link: campus dashboards, campus event approval (`_is_active_campus_member`), student lists, campus IG chapters. Verified test: a Campus Lead called this API once with another college's id and the campus dashboard (`/campus/home-summary/`) immediately showed **the other college**. A learner could also link themselves as a verified member of a company org ("Test Co").
- **Expected.** A college change should go through the same "unverified organization" review as new orgs, or at least keep campus roles tied to the college they were granted for. Company/community links should not be self-verified.
- **Current.** One call, no review, immediately verified.
- **Reproduce.** As a Campus Lead: `POST /api/v1/dashboard/user/organization/` `{"organization":"<other college id>"}` → `GET /api/v1/dashboard/campus/home-summary/` shows the other college.
- **Fix.** Store `verified=False` for self-service links (except the first college at onboarding), and drop/suspend campus roles when the college changes. Only allow org types that make sense for the form (`College`/`School`). Add `authentication_classes = [CustomizePermission]`.
- **Impact.** Campus leads and enablers can manage campuses they do not belong to; campus stats and leaderboards can be polluted.

### H-24 · A per-IG lead can create verified Mentors and break IG roles through the IG edit API
| Field | Detail |
|---|---|
| Severity / Category | High · Security / RBAC |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/dashboard/ig/dash_ig_view.py:634` `InterestGroupGetAPI.patch` (route `PATCH /api/v1/dashboard/ig/get/<pk>/`), mentor side-effect `:741-815`, lead side-effect `:686-739`; serializer `dash_ig_serializer.py:336` `InterestGroupCreateUpdateSerializer` (fields include `code`, `status`, `created_by`) |
| Dependency | Dashboard `/dashboard/edit-ig/[id]` (`features/manage-ig`) — allowed for Admin, "IG Lead" and any "{code} IGLead" |

- **Problem.**
  1. For every muid in the `mentors` list, the view creates a `UserMentor` profile, an active `IG_MENTOR` scope grant, a **verified global "Mentor" role link**, and a mentor IG link. This skips the mentor application and admin approval flow completely. Removing a muid from the list never removes anything.
  2. The same PATCH lets a per-IG lead change `code`, `name`, `status` and `created_by`. Only the PUT path renames the derived roles (`"{code} IGLead"`, `"{code} CampusIGLead"`, co-lead, execom catalog). Changing the code through PATCH orphans all of them, so every lead of that IG (including the caller) loses access.
- **Why it matters.** A per-IG lead (a scoped, lower-trust role) can mint platform-wide Mentors, who then get the mentor dashboard, can create mentorship sessions and mentor tasks for that IG, and pass every `role_required([MENTOR])` check. A mistake in the edit form can also lock out every lead.
- **Expected.** Mentor assignment goes through admin approval (or is limited to the IG scope, without the global role). `code`/`status` are admin-only fields.
- **Reproduce.** As `WEBDEV IGLead`: `PATCH /api/v1/dashboard/ig/get/<webdev id>/` `{"mentors":[{"muid":"friend@mulearn"}]}` → the friend now has a verified "Mentor" role.
- **Fix.** Remove the global Mentor role grant (keep only the IG scope grant, pending approval), revoke grants for removed muids, make `code`/`status`/`created_by` read-only for non-admins, and share the rename logic between PUT and PATCH (or block code changes in PATCH).
- **Impact.** Privilege escalation; broken IG administration.

### H-25 · Event managers can change the karma of an event task after an admin approved it
| Field | Detail |
|---|---|
| Severity / Category | High · Business Logic (karma integrity) |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/dashboard/events/task_views.py:183` `EventTaskDetailAPI.patch`; serializer `api/dashboard/events/serializers.py:232` `EventTaskWriteSerializer` (fields `hashtag, title, description, karma, type, ig, level, org, bonus_time`) |
| Dependency | Dashboard manage-events task tab (`/dashboard/manage-events/[id]`) |

- **Problem.** Creating an event task sets `approval_status='pending'` and `active=False` (admin must approve). Editing does **not** reset the approval. The event creator, co-owners, company admins and company mentors can PATCH an approved, active task and set `karma` to any number (there is no maximum). Company tasks (`company/task_views.py:341-347`) and mentor tasks do reset to pending on edit — events are the exception.
- **Why it matters.** Approve a 10-karma task, then change it to 10,000. Every submission of that hashtag then earns the new value.
- **Expected / Current.** Any change to karma/hashtag/level sends the task back to pending / edit is silently live.
- **Reproduce.** Create an event task, let an admin approve it, then `PATCH /api/v1/dashboard/events/manage/<event_id>/tasks/<task_id>/` `{"karma": 10000}`.
- **Fix.** On PATCH set `approval_status='pending', active=False` when `karma`, `hashtag`, `level`, `ig` or `org` change (same as company tasks); add a max karma validator.
- **Impact.** Karma inflation through events.

### H-26 · A shared pagination change (2026-08-30) broke five list APIs, including two admin pages
| Field | Detail |
|---|---|
| Severity / Category | High · Regression / Bug |
| Repo / branch | Backend @ `pranav-dev` (commit `f9f35ef`, 2026-08-30) |
| Location | `utils/utils.py:100` `CommonUtils.get_paginated_queryset` now reads `queryset._fields`. Callers that pass a Python list crash: `api/dashboard/dynamic_management/dynamic_management_view.py:43` (`DynamicRoleAPI.get`), `:112` (`DynamicUserAPI.get`), `api/dashboard/discord_moderator/discord_mod_views.py:104` (`LeaderBoard.get`), `api/dashboard/mentor/mentor_views.py:230` (`MentorActivityListAPI.get`), `api/launchpad/launchpad_views.py:1167` (`ListLaunchpadStudentsAPI.get`) |
| Dependency | Dashboard `/dashboard/management/dynamic-type` (`features/dynamic-type/api/dynamic-type.api.ts:96,138`), `/dashboard/management/discord-moderation` (`features/discord-moderation/api/discord-moderation.api.ts:95`) |

- **Problem.** `AttributeError: 'list' object has no attribute '_fields'` → HTTP 500 on every call.
- **Why it matters.** The Dynamic Type management page cannot list anything (confirmed in the browser crawl: both list calls return 500), the Discord moderation leaderboard is empty, and the mentor activity feed and Launchpad eligible-students list are down.
- **Expected / Current.** Lists work / 500.
- **Reproduce.** As Admin: `GET /api/v1/dashboard/dynamic-management/dynamic-role/`.
- **Fix.** In `get_paginated_queryset`, use `is_grouped = getattr(queryset, "_fields", None) is not None` and keep a list branch (slice + count) for non-QuerySet inputs; add a unit test with a list input.
- **Impact.** Admin tooling outage since 2026-08-30.

### H-27 · The learning-circle invite link page always says "Invalid or Expired Link"
| Field | Detail |
|---|---|
| Severity / Category | High · API / Cross-repo |
| Repo / branch | Backend @ `pranav-dev` + Dashboard @ `dev` |
| Location | Backend `api/dashboard/learningcircle/learningcircle_views.py:1550` `CircleInviteStatusAPI.get(self, request)` (no `link_id` parameter) mounted on `invite/status/<str:link_id>/`. Dashboard `src/features/learning-circle/api/learning-circle.api.ts:294` `getInviteByLink`, page `src/app/(dashboard)/dashboard/learning-circle/invite/[link_id]` → `InviteLinkView` |
| Dependency | Invite links sent to users |

- **Problem.** The dashboard calls `GET /learningcircle/invite/status/<link_id>/`. Django passes `link_id` to `get()`, which does not accept it → `TypeError` → HTTP 500. The page treats any error as an invalid link.
- **Why it matters.** Nobody can open an invite link. (Accepting from the "Invites" list still works because it uses POST.)
- **Expected / Current.** Page shows the invite with Accept/Reject / page always shows "Invalid or Expired Link".
- **Reproduce.** Open `/dashboard/learning-circle/invite/<any link id>`.
- **Fix.** Add `def get(self, request, link_id=None)` that returns the single invite (only if it belongs to the caller), or change the FE to use the list endpoint and filter.
- **Impact.** Invite-by-link feature is dead.

### H-28 · All public Learning Circle report APIs crash (field `name` no longer exists)
| Field | Detail |
|---|---|
| Severity / Category | High · Bug (also broken on backend `dev`; not a new regression) |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/common/common_views.py:151, 208, 281, 312, 372, 507, 559` (`circle_name=F("circle__name")`), `:181, 189, 237, 245` (`Count("learning_circle_ig")`); `api/common/serializer.py:26, 82, 154, 174, 186` (`LcListSerializer` / `LcDetailsSerializer` use `name`). Model `db/learning_circle.py:18` has `title`, and the IG reverse name is `learning_circle_ig_id` |
| Dependency | Public website (not the dashboard): `GET /api/v1/public/lc-list`, `/public/<circle_id>/lc-details/`, `/public/lc-dashboard/`, `/public/lc-report/`, `/public/lc-report/csv/`, `/public/lc-enrollment/`, `/public/lc-enrollment/csv/` |

- **Problem.** `FieldError: Cannot resolve keyword 'name'` / `ImproperlyConfigured: Field name 'name' is not valid for model 'LearningCircle'` → HTTP 500 for everyone (confirmed for anonymous, learner and admin).
- **Why it matters.** Any public LC listing, LC detail page and the LC enrollment/report exports are down.
- **Fix.** Replace `circle__name` → `circle__title`, `name` → `title` in the two serializers (keep the JSON key `name` with `source="title"` so clients do not break), and `learning_circle_ig` → `learning_circle_ig_id`.
- **Impact.** Public LC pages and reports broken.

### H-29 · Donation payment verification can be replayed (duplicate paid donations and tax receipts)
| Field | Detail |
|---|---|
| Severity / Category | High · Business Logic / Data integrity (payments) |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/donate/views.py:461` `RazorPayVerification.post`, `:694` `RazorPaySubscriptionVerification.post`; model `db/donation.py:13` (`payment_id` has no unique constraint) |
| Dependency | Public donation page (not the dashboard) |

- **Problem.** The view checks the Razorpay signature, then always creates a new `Donation(is_paid=True)`, a **new invoice number**, and e-mails a receipt with PAN and address. Nothing checks whether this `payment_id` was already recorded.
- **Why it matters.** Re-sending the same valid request (browser retry, double click, or on purpose) inflates donation totals and produces several tax receipts with different invoice numbers for one payment. It can also be used to flood the donor's inbox.
- **Expected / Current.** Idempotent: one payment = one record + one receipt / every call creates new ones.
- **Reproduce.** Complete a test payment, then POST the same `{razorpay_order_id, razorpay_payment_id, razorpay_signature}` to `/api/v1/donate/verify/` again.
- **Fix.** Add a unique index on `donation.payment_id`; at the start of the view return the existing record if found; generate the invoice only once; also check `payment_data["status"] == "captured"` (see M-44).
- **Impact.** Wrong financial records and duplicate 80G/tax documents.

### H-30 · Company "Collaborations" page crashes on load
| Field | Detail |
|---|---|
| Severity / Category | High · API contract / Frontend |
| Repo / branch | Dashboard @ `dev` + Backend @ `pranav-dev` |
| Location | Dashboard `src/features/company-jobs/api/jobs.api.ts:909-938` (`fetchCollaborations`, `discoverCollaborations` return `res.response ?? []`), `components/collaborations/company-collaborations-client.tsx:124-127` (`myCollaborations.filter(...)`), schema `schemas/jobs.schema.ts:1499` (`z.array(...)`). Backend `api/dashboard/company/collaboration_views.py:62-75, 190-200` (paginated: `{"data": [...], "pagination": {...}}`) |
| Dependency | Page `/dashboard/company/collaborations` (Company role) |

- **Problem.** The backend returns a paginated object; the dashboard expects a plain array. The schema check fails, the client returns the raw object, and `myCollaborations.filter is not a function` crashes the React tree (seen in the browser crawl, Company role).
- **Expected / Current.** List of collaborations / the page shows the error screen.
- **Reproduce.** Log in as a company → open `/dashboard/company/collaborations`.
- **Fix.** Either read `res.response.data` in both API functions (and use the pagination), or return a plain list from the two backend views. Make the list schemas strict so this fails loudly in tests.
- **Impact.** The whole collaborations feature is unusable.

### H-31 · Company "Event Templates" page crashes (regression from 2026-08-19)
| Field | Detail |
|---|---|
| Severity / Category | High · Regression / Frontend |
| Repo / branch | Dashboard @ `dev` (commit `9246f1f` "redesigned the Task Templates modal", 2026-08-19) |
| Location | `src/features/company-jobs/components/templates/company-templates-client.tsx:228-319` — a `<TabsContent value="event-templates">` is rendered after the parent `<Tabs>` was removed (the unused `Tabs` import at `:46` is one of the lint warnings) |
| Dependency | Page `/dashboard/company/event-templates` |

- **Problem.** Radix throws "`TabsContent` must be used within `Tabs`" on every render → the page crashes (seen in the crawl).
- **Fix.** Remove the `TabsContent` wrapper (render the content directly) or restore the `<Tabs>` root. Add a render test for the page.
- **Impact.** Companies cannot see or create event templates.

### H-32 · Company "Feedback & Impact" page crashes, and the impact report shows empty numbers
| Field | Detail |
|---|---|
| Severity / Category | High · API contract |
| Repo / branch | Dashboard @ `dev` + Backend @ `pranav-dev` |
| Location | Dashboard `src/features/company-jobs/api/jobs.api.ts:880-893` (`fetchCompanyFeedbackList` expects an array; `fetchCompanyImpactReport` expects `{company_id, company_name, total_hires, total_gigs, total_karma_awarded, campuses_engaged, is_published, published_at}` — `schemas/jobs.schema.ts:1471`). Backend `api/dashboard/company/feedback_views.py:148-170` (paginated list) and `:271` `CompanyImpactReportAPI` (returns `{company:{id,name}, reach:{…}, quality_signal:{…}, outcome_signal:{hires, karma_distributed}}`) |
| Dependency | Page `/dashboard/company/feedback` |

- **Problem.** `feedbackList.map is not a function` crashes the page (crawl). Even after that is fixed, every impact-report field the UI reads is `undefined` (7 schema errors), and `is_published` is missing, so the "publish impact report" toggle cannot show the real state.
- **Fix.** Align one contract: update the dashboard schema/UI to the backend's nested shape (or flatten on the backend), and read `response.data` for the paginated list.
- **Impact.** Feedback and the public impact report cannot be managed.

### H-33 · Dashboard calls `/company/user-status/`, which does not exist (the request hits another route)
| Field | Detail |
|---|---|
| Severity / Category | High · Cross-repo / Missing endpoint |
| Repo / branch | Dashboard @ `dev` + Backend @ `pranav-dev` |
| Location | Dashboard `src/api/endpoints.ts:148` (`userStatus: "/api/v1/dashboard/company/user-status/"`), `features/company-jobs/api/jobs.api.ts:688` `fetchUserCompanyStatus`, `components/admin/company-admins-client.tsx:63-77` (shows `pending_invitations`). Backend `api/dashboard/company/urls.py` has no `user-status/` route; the URL matches `path("<str:company_id>/", CompanyDetailAPI)` (Admin-only) instead |
| Dependency | Page `/dashboard/company/admin` (co-admin management). Related: H-12 |

- **Problem.** Because `user-status` is treated as a company id, Company users get `400 "You do not have the required role to access this page."` (crawl). The page never gets `pending_invitations`, so invites are never shown. The earlier call-site check counted this as "OK" because the URL does resolve — to the wrong view.
- **Fix.** Add a real `company/user-status/` view (owner / delegate / pending invites for the caller) **above** the `<str:company_id>/` pattern, or point the dashboard to an existing endpoint. Consider moving `<str:company_id>/` routes under a prefix (for example `detail/<id>/`) so literal paths can never be swallowed.
- **Impact.** Together with H-12, the co-admin feature cannot work.

### H-34 · Every "public" page sends anonymous visitors to the login page (shared profile links do not work)
| Field | Detail |
|---|---|
| Severity / Category | High · Frontend / Cross-repo |
| Repo / branch | Dashboard @ `dev` |
| Location | `src/features/notification/hooks/use-notification.ts:60-68` `useUnreadCount` (no `enabled` guard, polls every interval) used by `components/notification-popover.tsx:53`, rendered by `src/components/dashboard/app-topbar.tsx:102` on every dashboard layout page; `src/api/client.ts` (`isTokenExpired` treats the backend's `statusCode: 1000` as "token expired" → `refreshAccessToken()` → `clearTokens()` + `redirectToLogin()`). Public list: `src/lib/auth/public-routes.ts` (`/dashboard/mujourney`, `/dashboard/search`, `/dashboard/interest-groups`, `/dashboard/events`, `/profile/<muid>`, `/dashboard/profile/<muid>`) |
| Dependency | Backend `GET /api/v1/notification/unread-count/` (login required → 403 `statusCode 1000`); `/profile/<muid>` also calls `GET /dashboard/profile/` (own profile, login required) |

- **Problem.** The edge proxy correctly lets anonymous users into the public routes, but the shared top bar immediately calls an authenticated API. The 403 is treated as an expired session, the client tries to refresh (there is no refresh token), clears cookies and redirects to `/login`.
- **Seen in the crawl.** Anonymous visits to all 11 public pages ended on `/login` (for example `/profile/learner@mulearn`, `/dashboard/mujourney/learner@mulearn`, `/dashboard/search/students`, `/dashboard/interest-groups/<id>`), right after `GET /notification/unread-count/ → 403`.
- **Why it matters.** "Share your profile" links, public muJourney pages and the public IG/event pages cannot be opened by anyone who is not logged in.
- **Expected / Current.** Public pages render for visitors / visitors are forced to log in.
- **Fix.** Add `enabled: authStore.isAuthenticated()` to `useUnreadCount` (and hide the popover for visitors); on `/profile/<muid>` do not call the own-profile endpoint when logged out; in `apiClient`, do not redirect to login when there was never a session.
- **Impact.** Every public, shareable page is broken for new visitors.

### H-35 · Production runs Django's development server, and no scheduled job ever runs (no Celery beat)
| Field | Detail |
|---|---|
| Severity / Category | High · Deployment / Reliability |
| Repo / branch | Backend @ `pranav-dev` (same files on `dev`) |
| Location | `docker-compose.yml:19` and `docker-compose.pod.yml:19` (`entrypoint: python manage.py runserver 0.0.0.0:8000`); `Dockerfile:11` (`# ENTRYPOINT sh entrypoint.sh` — the daphne entrypoint is commented out); both compose files mount `.:/app` over the image; the only Celery service is `celery -A mulearnbackend.celery worker -l info` (no `beat`, no `-B`). Deploy workflows `prod-deploy.yml`, `dev-deploy.yml`, `pod1-roll.yml` use these compose files. `mulearnbackend/settings.py:322-365` defines 10 `CELERY_BEAT_SCHEDULE` jobs |
| Dependency | Every dashboard page; event status, mentor sessions, campus/LC rankings shown in the dashboard |

- **Problem.**
  1. The API is served by `runserver` — Django's development server, which is not built for production traffic, security or stability, and auto-reloads when files change (the bind mount means a `git pull` on the host restarts the server mid-request).
  2. Nothing runs Celery **beat**, so none of the 10 scheduled jobs run: `transition_event_statuses_task` (event status stays "upcoming"/"ongoing" — the first report's M-11 assumed it runs daily), `transition_mentorship_session_statuses`, `expire_stale_jobs`, `expire_stale_applications`, `expire_stale_grants`, `intern_daily_status_cron`, `intern_task_deadline_cron`, `update_alumni_status_cron`, `refresh_org_aggregates`, `refresh_learning_circle_aggregates`.
- **Why it matters.** `organization.cached_total_karma/cached_member_count` and `learning_circle.cached_total_karma/cached_rank` are **only** written by those crons and are read by the org list, campus search, campus rank, LC detail and leaderboards (7 places in `api/`). Without beat they stay at their default `0`, so every college shows 0 karma and LC ranks are 0. Expired jobs, mentor grants and applications never expire; alumni are never flagged; intern status/deadline automation never happens.
- **Expected / Current.** A production ASGI/WSGI server (daphne, as `entrypoint.sh` already defines, or gunicorn + uvicorn workers) and a `celery beat` service / dev server and no beat.
- **Reproduce.** `docker compose -f docker-compose.yml config` → no beat service; check `organization.cached_total_karma` in production.
- **Fix.** Use `entrypoint.sh` (daphne) or gunicorn; remove the `.:/app` mount in production; add a `beat` service (`celery -A mulearnbackend.celery beat -l info`, with a persistent schedule file or `django-celery-beat`); run the two aggregate crons once by hand after deploy. See M-59 for the worker side.
- **Impact.** Unstable API server; wrong karma/rank numbers across the dashboard; business automation silently off.

#### High issues added in the performance pass

### H-36 · The profile API that the sidebar loads on every page reads the whole wallet table (rank and percentile)
| Field | Detail |
|---|---|
| Severity / Category | High · Performance / Scalability |
| Repo / branch | Backend @ `pranav-dev` (same code on `dev`) + Dashboard @ `dev` |
| Location | Backend `api/dashboard/profile/profile_serializer.py:189-198` `UserProfileSerializer.get_percentile` and `:242-279` `get_rank` (route `GET /api/v1/dashboard/profile/user-profile/`, `UserProfileAPI`). Dashboard `src/components/dashboard/app-sidebar.tsx:44` `useUserProfile()` (stale time 5 minutes, `src/features/profile/hooks/use-profile.ts:40`) |
| Dependency | Every dashboard page (the sidebar shows the user's name, picture and karma from this API) |

- **Problem.**
  1. `get_rank` makes a Python list of the user id of **every wallet with karma ≥ the user's karma** (`list(ranks.values_list("user_id", flat=True))`, with a join on roles and `DISTINCT`) and then looks for the user with `list.index`. For a new user (karma 0) this is every wallet in the database.
  2. `get_percentile` counts all wallets with less karma and then counts all users — two more whole-table counts. `wallet.karma` has no index (`schema.sql`).
  3. The API runs 18 queries per call (measured). The browser crawl shows the sidebar calls it on **every** dashboard page load, and again every 5 minutes while the user is active.
- **Why it matters.** This is the most often called heavy query in the system, and its cost grows with the total number of users, not with anything the user did. With 300,000 wallets, a new user's page load moves up to 300,000 ids from MySQL into Python and searches them. It is likely the first thing to slow down under real traffic. The same pattern exists in `UserRankSerializer` (L-24).
- **Expected / Current.** A light "current user" call for the sidebar, and rank from one indexed `COUNT` or a stored value / every page load reads the whole wallet table.
- **Reproduce.** Open any dashboard page with the network tab open → `GET /dashboard/profile/user-profile/`. In the test harness this call makes 18 SQL queries; the rank query has no `LIMIT`.
- **Fix.** (1) Sidebar: use `user/info` (already loaded by the top bar) or a new small `me` endpoint; call `user-profile` only on the profile page. (2) Rank: `Wallet.objects.filter(karma__gt=user_karma).count() + 1` with an index on `wallet(karma)`, or a rank table refreshed by a scheduled job (needs H-35). (3) Percentile: the same count, with the total user count cached.
- **Impact.** Database CPU and memory load on every page view by every user; slow sidebar; with the single-process dev server (H-35) one slow call delays everyone.

### H-37 · Public leaderboards run heavy whole-table queries with no cache (301 queries for the top 100)
| Field | Detail |
|---|---|
| Severity / Category | High · Performance / DoS |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/common/common_views.py:897-907` `BekenAPI` (`GET /api/v1/public/leaderboard/top-100/`); `api/leaderboard/leaderboard_view.py:26-50` `StudentsLeaderboard`, `:69-110` `StudentsMonthlyLeaderboard`, `:127-150` `CollegeLeaderboard`; only `CollegeMonthlyLeaderboard` (`:154`) has a cache (`cache_page(300)`) |
| Dependency | Dashboard home page ("top karma earners" card) and `/dashboard/leaderboard` (`src/features/leaderboard/api/leaderboard.api.ts:29-47`). No login needed |

- **Problem.**
  1. Top 100: one query for the users plus three queries per user (wallet, IG links, org links) = **301 queries per call** (measured), no cache, no login.
  2. Students and colleges: one big query that joins user, org link, organization, role link, role and wallet with `DISTINCT` and sorts by `wallet.karma`. `wallet.karma` has no index, so the database builds and sorts the whole student set on every call. The college board also counts and sums every student of every college.
  3. Students monthly: sums `karma_activity_log.karma` for last month for every student. `karma_activity_log` (the biggest table) has no index on `created_at` (`schema.sql`), so every call reads the karma log. It also checks the file system once per row for a profile picture.
- **Why it matters.** Anyone can call these in a loop without logging in, and each call is a large join and sort. The home page calls one on every load. The results only change when karma changes.
- **Expected / Current.** Cached or pre-computed rankings / computed from scratch on every call.
- **Reproduce.** `GET /api/v1/public/leaderboard/top-100/` with no token → 301 SQL queries in the harness.
- **Fix.** Cache every leaderboard for 5–15 minutes, or have a scheduled job write the top N into a small table. In `BekenAPI` add `select_related("wallet_user")` and prefetch the IG and org links. Add indexes on `wallet(karma)` and `karma_activity_log(created_at)` (or `(user_id, created_at)`). Rate-limit the public endpoints.
- **Impact.** Database load grows with traffic on the most visited pages; an easy target for a denial-of-service attack.

### H-38 · Karma voucher import gets slower with every voucher ever made, and draws an image and sends an e-mail for each row inside the request
| Field | Detail |
|---|---|
| Severity / Category | High · Performance / Reliability |
| Repo / branch | Backend @ `pranav-dev` |
| Location | `api/dashboard/karma_voucher/karma_voucher_view.py:38-236` `ImportVoucherLogAPI.post` (`POST /api/v1/dashboard/karma-voucher/import/`): `:113-114` `existing_codes = set(VoucherLog.objects.values_list('code', flat=True))` inside the per-row loop; `:196-229` `generate_karma_voucher(...)` and `EmailMessage(...).send()` for each voucher. The same image + e-mail in `VoucherLogAPI.post` (`:286-341`) |
| Dependency | Dashboard karma voucher import screen |

- **Problem.** (1) For each valid row the code loads the code of **every voucher ever created**. 500 rows with 50,000 existing vouchers = 25 million values read. (2) For each created voucher it draws an image (PIL) and sends an SMTP e-mail while the HTTP request waits. `EMAIL_TIMEOUT` is not set, so one slow mail server stops the whole import.
- **Why it matters.** A normal import of a few hundred rows takes minutes and hits the proxy timeout. The admin sees an error and retries, while the first run is still sending e-mails → people get duplicate e-mails, and vouchers can be created twice.
- **Expected / Current.** A quick import that queues the images and e-mails / quadratic reads plus N images and N e-mails in one request.
- **Fix.** Load existing codes once before the loop (or let a unique index + retry generate codes); `bulk_create` the vouchers; send one Celery task per voucher for the image and e-mail (`mu_celery.task.send_email` already exists); set `EMAIL_TIMEOUT`.
- **Impact.** Imports fail or time out; duplicate side effects when retried.

### H-39 · Every dashboard page downloads about 713 KB of JavaScript, most of it unused, and is slow on a normal phone
| Field | Detail |
|---|---|
| Severity / Category | High · Performance (frontend) |
| Repo / branch | Dashboard @ `dev` |
| Location | `src/components/dashboard/app-sidebar.tsx:27` imports `useUserProfile` from the `@/features/profile` barrel (`src/features/profile/index.ts` → `components/index.ts` re-exports every profile component, including `karma-distribution.tsx`, which imports `recharts`); `src/components/dashboard/whats-new-popup.tsx:13` imports `MarkdownRenderer` (`react-markdown` + `remark-gfm` + `rehype-sanitize`) directly. Both are part of the dashboard layout (`src/app/(dashboard)/layout.tsx`), so they load on every page |
| Dependency | All 120 dashboard pages |

- **Problem.** Measured on the production build with mobile throttling (4× slower CPU, 150 ms round trip, 1.6 Mbps):
  1. The median dashboard page downloads 40 script files, **713 KB compressed (2,435 KB unzipped)**, and **65%** of that code does not run while the page loads (V8 coverage).
  2. The charts chunk (recharts, about 91 KB compressed / 297 KB unzipped) and the Markdown chunk (about 44 KB compressed / 143 KB unzipped) load on every dashboard page, including pages with no chart and when the "What's new" popup stays closed.
  3. Median LCP (when the main content appears) is **7.7 s**, and median Total Blocking Time is **2,034 ms**. 123 of 129 pages have LCP over 4 s ("poor" in Core Web Vitals), and 123 pages block the main thread for more than 600 ms.
- **Why it matters.** Many learners use phones on mobile data. On such a phone they wait 7–9 s for content, and the page does not respond to taps for about 2 s after it appears.
- **Expected / Current.** Under about 250–300 KB of compressed first-load JavaScript per page, LCP under 2.5–4 s / the numbers above.
- **Reproduce.** Chrome DevTools → Performance, "Slow 4G" + 4× CPU → open `/dashboard/interest-groups` → the chunk containing `recharts-wrapper` and the one containing `micromark` are loaded.
- **Fix.** (1) Import hooks from their own files (`@/features/profile/hooks/use-profile`), not from feature barrels, in shared components; or mark packages side-effect free and use `optimizePackageImports`. (2) Load the What's-new popup with `next/dynamic` only when it will open. (3) Load chart components with `next/dynamic` (zonal, district, campus manage and URL-shortener analytics already do). (4) Add `@next/bundle-analyzer` and a size budget check to CI. (5) For the most visited pages (home, profile, IGs, learning circles), fetch the first data in server components so content does not wait for all the JavaScript.
- **Impact.** A slow first view of every page; poor Core Web Vitals, which also hurts search ranking of public pages.

### H-40 · Every page load shows a 1920×1080 GIF (downloaded twice) and waits for `user/info` before the page asks for its own data
| Field | Detail |
|---|---|
| Severity / Category | High · Performance (frontend + backend load) |
| Repo / branch | Dashboard @ `dev` |
| Location | `src/app/loading.tsx:1-16` (`/images/MuLoader.gif`: 144 KB, 1920×1080, `priority` + `unoptimized`, shown at 400×400); `src/app/(dashboard)/onboarding-guard.tsx:21-68` (renders `<Loader />` until `useUserInfo()` has finished, so the page and its queries are not mounted yet); app-shell calls: `src/components/dashboard/app-topbar.tsx:41` (`user/info`), `app-sidebar.tsx:44` (`profile/user-profile`, H-36), `features/mujourney/components/GameProgressBar.tsx:11` (`profile/user-level-feed`), notification bell (`notification/unread-count`, L-57) |
| Dependency | Every dashboard page |

- **Problem.**
  1. In 101 of 129 pages, the page's own API calls started only **after** `user/info` had finished: one extra full round trip before any page data is requested. The median page has its data at **7.8 s** after navigation.
  2. The loader GIF is 144 KB and was downloaded **twice** per page load (257 downloads in 129 page loads). That is about 288 KB on the critical path, more than all the page's API data, and on slow 4G about 1.5 s of bandwidth taken from the JavaScript.
  3. Every full page load makes 4 app-shell API calls that run about 30 SQL queries (`user/info` 9–11, `user-profile` 17–18, `user-level-feed` 2, `unread-count` 1, depending on the role) before the page's own calls.
- **Why it matters.** Every page is slower than it needs to be, and the backend does the shell work again on every full load and tab.
- **Expected / Current.** Page queries start at the same time as `user/info`; a tiny loader / a sequential wait and a large GIF.
- **Fix.** Render the page while `user/info` loads (redirect from an effect only when needed) so its queries start in parallel; replace the GIF with a CSS spinner or a small SVG/WebP (under 10 KB) and remove `priority`; merge the shell calls into one light `me` endpoint (H-36).
- **Impact.** Slower first view of every page; extra backend load.

---

## 4. Medium and low issues

Format: **ID · Title** — Severity · Category · Repo @ branch · Location — then problem, expected vs current, how to reproduce, fix, impact, dependency.

### Medium

**M-01 · System roles can be renamed or deleted** — Medium · Business Logic/RBAC · Backend @ pranav-dev · `api/dashboard/roles/dash_roles_views.py:61-110` `RoleAPI.patch/delete`.
- *Problem:* RBAC compares role **titles** everywhere (`RoleType`). Renaming "Admins" or "Campus Lead" breaks every check. Deleting a role cascades to all `UserRoleLink` rows.
- *Expected:* Built-in roles are locked. *Current:* Editable.
- *Repro:* PATCH `/dashboard/roles/<Admins id>/` with `{"title":"Admin"}` → every admin is locked out.
- *Fix:* Add an `is_system` flag or a `RoleType` blocklist. Soft delete.
- *Impact:* Platform-wide lockout. *Dependency:* Dashboard `manage-roles`.

**M-02 · Bulk role removal skips the cleanup that single removal does** — Medium · Business Logic · Backend · `dash_roles_views.py:298` `UserRoleLinkManagement.patch` vs `:379` `UserRole.delete`.
- *Problem:* Removing Mentor, Intern or Company in bulk leaves approved mentor applications and active scope grants, active intern guild links, and verified companies.
- *Fix:* Share one `revoke_role(user, role)` service between both paths. Also block special roles in bulk (the same way bulk assign already does).
- *Impact:* Removed mentors or companies keep their powers through grants.

**M-03 · Single role removal crashes on IG-scoped links; "assign" does not verify a pending request** — Medium · Bug · Backend · `dash_roles_views.py:379` (`UserRoleLink.objects.get(role_id, user_id)` → `MultipleObjectsReturned` when IG-scoped rows exist, `UserRoleLink.ig`), `dash_roles_serializer.py:244` (an existing unverified link is returned unchanged).
- *Current:* 500. "Role Added Successfully" but the user still has no active role.
- *Fix:* Filter by `ig=None` or accept an `ig_id`. Set `verified=True, is_active=True` on an existing link.

**M-04 · Roles list is slow and sorting by members creates duplicate rows** — Medium · Performance · Backend · `dash_roles_serializer.py:83` `get_members` (`len(UserRoleLink.objects.filter(...))` loads every row, per role), `dash_roles_views.py:45` (sort `members` → `order_by("userrolelink")` makes a JOIN that duplicates rows).
- *Fix:* `annotate(members=Count('userrolelink', filter=Q(userrolelink__verified=True)))` and sort by the annotation.
- *Impact:* The admin roles page is slow (the Student role has a very large table). Pagination looks wrong.

**M-05 · Org verification: partial writes, duplicate college links, ignored filter, 1000-org dropdown limit** — Medium · Data consistency/UX · Both.
- `serializers.py:469-492` saves `verified=True` before the duplicate-link check can raise, and there is no transaction. A user with an existing college link gets a second one.
- `UnverifiedOrganizationsListAPI` ignores `org_type`.
- The dashboard `verify-action-dialog.tsx:59-66` loads only the first 1000 orgs (`MAX_PAGE_SIZE=1000`), sorted by title, so later orgs cannot be picked.
- The dashboard expects `created_by_muid` / `created_by_email`, which are never returned.
- *Fix:* Use `transaction.atomic`, replace or refuse an existing college link, add the `org_type` filter, use server-side search in the combobox, and return the submitter's muid/email to admins.

**M-06 · Merge logic has correctness gaps** — Medium · Business Logic · Backend · `organisation/serializers.py:347-392` `OrganizationMergerSerializer.update`.
- *Problem:* It picks the *first* FK to `Organization` on each related model (models with two org FKs are handled wrong). It moves `UserOrganizationLink` without removing duplicates (a user in both orgs gets two links). The cached aggregates stay stale until the cron runs.
- *Fix:* Explicit per-model merge rules, dedupe, and recompute aggregates.

**M-07 · Company applicants: `status` filter is ignored** — Medium · API · Backend `api/dashboard/company/job_views.py:535` `JobApplicationAPI.get`; Dashboard `features/company-jobs/components/applicants-section.tsx:105-130`.
- *Current:* The "Selected / Rejected / …" counters (separate calls with `perPage=1&status=`) all show the total. Filtering happens on the client, per page only.
- *Fix:* Add `status` filtering on the backend.

**M-08 · IG request lifecycle gaps** — Medium · Business Logic · Backend `dash_ig_view.py:841-1107`; Dashboard `features/ig-requests/api/ig-requests.api.ts:26`.
- *Problems:*
  - (a) The admin list (no `user_id`) returns **all IGs**, including active IGs that were never requested.
  - (b) `PATCH` allows any→any status ("admin override").
  - (c) Approving a request does not create the IG's member / `IGLead` / `CampusIGLead` roles and does not grant lead roles to the listed leads. `InterestGroupAPI.post` does both.
  - (d) The dashboard sends `sort=`, but the backend reads `sortBy`.
  - (e) The notification link is `/interest-groups/{id}/`, but the dashboard route is `/dashboard/interest-groups/[id]`.
- *Fix:* Filter the list to `created_by` with a Company role or `status in (requested, rejected, cancelled)`. Use a state machine. Reuse the role provisioning from create. Fix the param and the URL.

**M-09 · IG membership counts, cache and join limit** — Medium · Data consistency · Backend `dash_ig_view.py:1181-1310`.
- `members=Count("user_ig_link_ig")` counts inactive and mentor links.
- `cache_page(600)` hides joins and activations for 10 minutes.
- The 3-IG limit is only checked for new links, so reactivating an old link bypasses it.
- *Fix:* `Count(..., filter=Q(is_active=True, assignment_type=LEARNER))`, invalidate the cache on change, and always check the limit.

**M-10 · Events: other approval and permission gaps** — Medium · Business Logic · Backend `manage_views.py`.
- `MentorEventApproveAPI` (L1571) has no self-approval guard.
- Campus-IG event tenancy is not enforced (the docstring at L125-150 admits it). `decide_publish_status` uses `scope_org`, which the wizard leaves empty.
- `CampusIGCoLead` cannot create events.
- *Fix:* Store the chapter or org on campus-IG events, check it, and add the guards.

**M-11 · Event lists are merged on the client and stale** — Medium · Performance/UX · Dashboard `features/events/api/events.api.ts:74-81, 298-380`; Backend `settings.py` `transition-event-statuses` (daily at 00:35).
- The "Pending" tab makes 3 requests of up to 200 items each and paginates them in the browser. Anything past 200 per status is silently cut off.
- "Ongoing/Completed" fall back to loading all published events because statuses change only once a day.
- *Fix:* Backend support for `status__in`, and a status transition every 5–15 minutes, or compute the status from the time on read.

**M-12 · Field-length overflow in notifications after the change is already saved** — Medium · Bug · Backend `db/notification.py` (`url` max 100; broadcast `title` 50, `description` 200), callers such as `manage_views.py:1952` (`f'A new Campus event "{event.title}" is now live!'`).
- *Problem:* Long titles or URLs raise `DataError` on MySQL strict mode **after** `event.save()`, with no atomic block. The user gets a 500 but the event is already approved.
- *Fix:* Truncate in the utils. Wrap the state change and notification in a transaction, or send notifications with `on_commit`.

**M-13 · Backend deep links point to dashboard routes that don't exist** — Medium · Cross-repo · Backend `FR_DOMAIN_NAME` URLs in `api/dashboard/company/*`, `mentor/*`, `events/manage_views.py`, `ig/dash_ig_view.py`, `lc/dash_lc_view.py`.
- *Broken targets:*
  - `/dashboard/admin/companies/{id}/`
  - `/dashboard/company/jobs/pending/`
  - `/dashboard/company/mentor/list/`
  - `/dashboard/mentor/applications/{id}/`, `/dashboard/mentor/list/`, `/dashboard/mentor/status/`
  - `/events/{id}/` (should be `/dashboard/events/{id}`)
  - `/interest-groups/{id}/`
  - `FR_DOMAIN_NAME + /api/v1/dashboard/lc/...` (an API path on the frontend domain)
- *Fix:* One shared route map (for example `utils/frontend_routes.py`) checked against the dashboard's `app` routes in CI.

**M-14 · Auth helper inconsistencies** — Medium · Security/API · Backend `utils/permission.py`.
- `role_required` returns **HTTP 400** (statusCode 400) for "no role". `dynamic_role_required` returns 403.
- `fetch_user_id` and `fetch_role` skip the `expiry` check and raise `IndexError` → 500 when the header is missing.
- Roles come only from the JWT, so grants and revocations take effect only after the token is refreshed (up to 15 minutes). Suspended users keep access until their token expires.
- The dashboard's `isTokenExpired` works because statusCode 1000 is used for token errors.
- *Fix:* Return 403 for role failures. Check expiry in one place. Optionally check `verified` roles against the DB for sensitive actions.

**M-15 · Public user search leaks data** — Medium · Security/Privacy · Backend `dash_user_views.py:618` `UserSearchAPI` (no auth).
- It returns internal `id` (which enables C-03), names, muid, orgs and karma.
- `?role=Admins` lists all admins.
- Private profiles (`UserSettings.is_public`) are not excluded.
- *Fix:* Filter public users, hide `id`, and limit the role filter to authenticated staff.

**M-16 · `user/info` fails when Redis is down; the client guard loops** — Medium · Reliability · Backend `dash_user_views.py:44` (the first `cache.set` has no try/except, unlike the one at L50-54); Dashboard `src/app/(dashboard)/onboarding-guard.tsx:39-42` sends users to `/login` on **any** error.
- *Problem:* The proxy then sends `/login` back to `/dashboard` because the refresh cookie still exists, which creates a redirect loop.
- *Fix:* Guard the cache. On the client, only log out on 401/1000 and show an error state for 5xx.

**M-17 · Karma updates are not atomic** — Medium · Data consistency · Backend `utils/karma.py:8-70`.
- The single-user path does read → `+=` → `save()` (lost updates under concurrency), with no transaction around log + wallet.
- `remove_karma` subtracts from the wallet even when no log was found, so karma can go negative.
- *Fix:* Use `F()` updates in `transaction.atomic()` and only subtract what was deleted.

**M-18 · Legacy notification endpoints removed** — Medium · Regression · Backend `api/notification/urls.py` (diff `dev..pranav-dev`).
- `GET /notification/list/` and `DELETE /notification/delete/id/<id>/` are gone. `list/` now matches `<str:notification_id>/` (`DeleteOneView`) → 405.
- Other clients (mobile, bots) will break.
- The dashboard's legacy hooks `useNotifications`, `useDeleteDirectNotification`, `useDeleteAllDirectNotifications` are now dead code.
- *Fix:* Keep aliases for one release or announce the removal. Delete the dead hooks.

**M-19 · Company verification links org by title; sign-up is two steps and not atomic** — Medium · Business Logic · Backend `company/serializers.py:381-397` (`Organization.objects.filter(title=instance.name, ...)`) + Dashboard `register-client.tsx:189-262`.
- Two companies with the same name get linked to the same org.
- The user account is created first. If company registration then fails, the user is stuck with a pending Company role and cannot sign up again.
- *Fix:* Always create or link by FK. Create user + company in one backend call, or let the company step be retried.

**M-20 · Learning circle delete is allowed only for the original creator** — Medium · Business Logic · Backend `learningcircle_views.py:210-226`.
- After the lead is transferred, the old creator can still delete the circle and the new lead cannot.
- Delete also keeps the creation karma.
- *Fix:* Check the current lead. Soft delete.

**M-21 · Features disabled in the UI because of a "backend conflict"** — Medium · Missing functionality · Dashboard.
- `features/manage-ig/components/ig-form-dialog.tsx:391,590`, `edit-interest-group-form.tsx:259-382` (IG cover/icon upload)
- `ig-detail.tsx:691`, `interest-groups/components/interest-group-detail-client.tsx:677` (Impact Projects)
- `weekly-twitches/components/office-hours-form.tsx:271` (poster upload)
- *Note:* The backend has the endpoints (`ig/<pk>/cover-image/`, `icon-image/`, `ig/<id>/impact-projects/`). Agree on the contract and turn them back on, or remove the unused backend code.

**M-22 · Backend configuration not hardened for production** — Medium · Security · Backend `mulearnbackend/settings.py`, `middlewares.py`, `urls.py`.
- `CORS_ALLOW_ALL_ORIGINS = True`.
- `debug_toolbar` app, middleware and `/api/v1/__debug__/` URLs are always on.
- `UniversalErrorHandlerMiddleware.log_exception` writes the **full request body** (passwords, tokens) to `error.log`.
- The root logger is at DEBUG to files with no rotation.
- `/muback-media/` is served by Django `serve`.
- *Fix:* Use an origin allowlist, only enable debug in dev, redact secrets in logs, use rotating handlers, and serve media from nginx or object storage.

**M-23 · Tokens are stored in cookies that JavaScript can read** — Medium · Security · Dashboard `src/lib/auth/token-store.ts` (js-cookie sets `accessToken` and a 7-day `refreshToken` without HttpOnly).
- Comments in `app-topbar.tsx:49-51` say the refresh token is HttpOnly. It is not.
- `src/api/server.ts:53` sets an HttpOnly 1-day `accessToken` that the client code then cannot read or overwrite, which causes repeated refreshes.
- *Fix:* Move the refresh token to an HttpOnly cookie set by a route handler. Use the same cookie attributes and lifetime everywhere.

**M-24 · Zonal/District dashboards show a "Lead Number" column the backend removed** — Medium · Regression · Backend commit `fa47e8a` removed `lead_number`; Dashboard `features/zonal/components/zonal-view.tsx:143-168`, `schemas/zonal.schema.ts:34`, `features/district/components/district-dashboard.tsx:129`.
- *Current:* The column is always "-" and the schema check fails (it is lenient, so only a log).
- *Fix:* Remove the column (the field was removed for privacy).

**M-25 · Google sign-in: redirect list, missing `state`, no audience check** — Medium · Security/Cross-repo · authserver @ dev · `muauth/views.py:202-207` `ALLOWED_GOOGLE_REDIRECT_URIS`, `:236` `GoogleLoginAPIView`, `:379` `GoogleMobileAuthAPIView`; Dashboard `src/features/auth/api/auth.api.ts:160-190` (redirect URI = `window.location.origin + "/callback/"`).
- *Problems:*
  - The list has `https://app.mulearn.org/`, `https://dev.mulearn.org/`, `http://localhost:3000/` and `https://mulearn-dashboard.vercel.app/`, but **not the staging site `https://staging.app.mulearn.org/`** (named in the dashboard's CONTRIBUTING.md) or Netlify previews. So Google login fails on staging.
  - `localhost` and a `vercel.app` domain are allowed in production. If muLearn does not own that Vercel project, someone else could receive Google login codes.
  - No OAuth `state` value is used, so login CSRF is possible (an attacker can log a victim into the attacker's account).
  - The mobile flow does not check the token's `aud`, so Google ID tokens made for other apps are accepted.
- *Fix:* Keep a separate redirect list per environment, add staging, and remove dev URLs from prod. Add a `state` value and check it in the callback. Check `aud` against muLearn's client IDs.

**M-26 · Logout and refresh-token handling are weak** — Medium · Security · authserver @ dev · `muauth/views.py:500-657` (`GetAccessToken`, `LogoutAPIView`).
- *Problems:*
  - The global-logout check **allows the request when Redis is down**, so logout stops working during a Redis outage.
  - Refresh tokens are never rotated. The same token is returned on every refresh until it expires 7 days after login.
  - Roles are copied into the refresh token (see H-18).
  - The refresh endpoint returns HTTP 400 for every failure. The dashboard only treats 401 or `statusCode 1000` as "session expired". It still logs the user out, because the refresh returns no token, but the error codes (1003/1004) are inconsistent.
- *Fix:* Rotate refresh tokens and store their `jti` in Redis. Fail closed (or use a database fallback) for logout checks. Keep roles out of refresh tokens.

**M-27 · Auth routing depends on hidden infra; two copies of the auth API** — Medium · Architecture/Cross-repo · Dashboard `src/api/refresh.client.ts`, `refresh.server.ts`, `app/api/auth/logout/route.ts`, `src/api/base-url.server.ts`; Backend `api/auth/auth_views.py`; authserver `muauth/urls.py`.
- *Problem:* The dashboard calls `/api/v1/auth/*` on `NEXT_PUBLIC_DJANGO_API_URL` and `BACKEND_URL`. Those routes live on the auth server, not in Django. So it works only if a reverse proxy sends `/api/v1/auth/*` to the auth server. The backend also has its own `auth/*` proxy views on the **same paths**, which that routing rule hides. The backend's `user-authentication/` proxy drops `otp`, so OTP login fails if a request ever reaches Django.
- *Current risk:* `src/api/server.ts` tells ops to point `BACKEND_URL` at an internal (VPC) Django address. If they do, server-side refresh and logout call Django, get 404, and users are logged out on page loads once their 15-minute token expires.
- *Fix:* Add an explicit `AUTH_URL` (public and server-side) to the dashboard and use it for every `/auth/*` call. Delete the backend proxies, or make them the only path and forward every field. Write down the gateway rule.

**M-28 · Auth server hygiene** — Medium · Security/Ops · authserver @ dev · `authserver/settings.py`, `requirements.txt`, `muauth/views.py`.
- `CORS_ALLOW_ALL_ORIGINS = True`, and `CorsMiddleware` sits *after* `CommonMiddleware`, so redirects and errors from earlier middleware miss CORS headers.
- The root logger is at DEBUG and SQL logging goes to files with no rotation.
- `requirements.txt` is saved as UTF-16 and lists `pytz` twice. `gunicorn` is only installed in the Dockerfile.
- The protected-key checks use `==` instead of a constant-time compare (`hmac.compare_digest`).
- There are no tests on `dev`. `feat/new-auth` adds tests and CI.
- A dead branch in `UserAuthenticationAPI` (`flag_register_*` cache key) skips all brute-force protection. Nothing in the backend sets that key today, but it is a hidden bypass. Remove it.
- *Fix:* Same hardening as M-22. Merge the tested `feat/new-auth` work after it gets the C-09 and H-19 fixes.

#### Medium issues added in the second pass

**M-29 · muJourney progress bar shows the karma of only one task** — Medium · Bug · Backend @ `pranav-dev` · `api/dashboard/profile/profile_view.py:834-882` `UserLevelFeedAPI.get` (sum at `:862-872`); Dashboard `src/features/mujourney/components/GameProgressBar.tsx:37-93`.
- *Problem.* `KarmaActivityLog.objects.filter(...).annotate(total_karma=Sum("karma")).values("total_karma").first()` groups by row, so it returns the karma of **one** log, not the total. Verified: 3 logs of 10/20/30 → API returns 10, correct value is 60.
- *Expected / Current.* Level progress = total karma earned for the current level / karma of one random task.
- *Fix.* Use `.aggregate(total=Sum("karma"))["total"] or 0`.
- *Impact.* Every learner sees a wrong progress bar on `/dashboard/mujourney`.

**M-30 · Free karma for typing anything into social-link fields** — Medium · Business Logic · Backend · `api/dashboard/profile/profile_serializer.py:638-699` `LinkSocials.update` (route `PUT /dashboard/profile/socials/edit/`, used by `features/profile/api/profile.api.ts:155`).
- *Problem.* When any of 9 social fields changes from empty to **any string** (no URL or domain check), the code creates an auto-approved `KarmaActivityLog` (+20) and updates the wallet. 9 fields → +180 karma by typing junk. When a link is removed and the matching log is missing (old data), `.first().delete()` raises `AttributeError` → 500, and the user can never clear that link.
- *Fix.* Validate each field as a URL for the right domain (github.com/…, linkedin.com/in/…); award once per platform per user (unique log); handle a missing log; make wallet + log atomic (M-17).
- *Impact.* Cheap karma inflation for every user.

**M-31 · Users can change their login email and phone with no verification; "communities" accepts any org** — Medium · Security · Backend · `api/dashboard/profile/profile_serializer.py:460-546` `UserProfileEditSerializer` (route `PATCH /dashboard/profile/`, used by `features/profile/api/profile.api.ts:195`).
- *Problem.* `email` and `mobile` are plain editable fields. Email is the login id and the password-reset address. `communities` accepts any `Organization` id (not only `Community`) and creates verified links (another path to H-23). A bad id → FK error → 500.
- *Fix.* Change email/mobile only through an OTP/verification flow; validate `communities` against `org_type="Community"`.
- *Impact.* Account recovery goes to unverified addresses; typo = locked-out user; wrong org links.

**M-32 · "Delete my account" API deletes everything at once, with no confirmation** — Medium · Security / Data · Backend · `api/dashboard/profile/profile_view.py:126` `UserProfileEditView.delete` (route `DELETE /dashboard/profile/`).
- *Problem.* Hard `User.delete()` with no password re-check, no confirmation token, no soft-delete. It cascades karma logs, links and history; profile/cover images stay on disk; existing tokens stay valid until expiry. (The dashboard does not call it today, but any holder of a token — for example via XSS, see M-23 — can.)
- *Fix.* Require re-authentication, soft-delete (`suspended_at`), schedule data removal, revoke tokens.

**M-33 · Admin "Edit user" re-creates all role links as approved global roles** — Medium · Business Logic / RBAC · Backend · `api/dashboard/user/dash_user_serializer.py:494-566` `UserDetailsEditSerializer.update` (route `PATCH /dashboard/user/<user_id>/`); Dashboard `features/manage-users/components/form-utils.ts:47` (sends `roles` only when changed).
- *Problem.* When the admin changes the role list, the backend deletes **all** `UserRoleLink` rows and recreates them with `verified=True` and no `ig`. So: (1) pending, unverified role requests that appear in the list get approved without review; (2) IG-scoped role links lose their IG; (3) `is_primary` is lost; (4) the role-specific cleanup that single removal does (mentor grants, intern guild, company — `dash_roles_views.py:379+`) is skipped. Organizations and IG links are also deleted and recreated (join dates lost; one department/graduation year for all orgs).
- *Fix.* Diff the old and new lists: add only new roles, remove only missing ones through the same cleanup path as `UserRole.delete`, keep `ig`, `verified`, dates.

**M-34 · Password reset has no rules and weak token handling** — Medium · Security · Backend · `api/dashboard/user/dash_user_views.py:392-486` (`ForgotPasswordAPI`, `ResetPasswordVerifyTokenAPI`, `ResetPasswordConfirmAPI`); used by `features/auth/api/auth.api.ts:85-113`.
- *Problem.* (1) No password validation: a missing `password` makes `make_password(None)` store an **unusable** password (the user is locked out); any length is accepted. (2) Older reset tokens stay valid until they expire. (3) Sessions/refresh tokens are not revoked after reset. (4) "User not exist" reveals which emails/muIDs are registered. (5) No rate limit; the SMTP send runs inside the request.
- *Fix.* Use Django password validators; reject empty passwords; delete all `ForgotPassword` rows of the user on success; return the same message for unknown accounts; queue the e-mail; rate-limit by IP and account.

**M-35 · Admin CSV exports load every row into memory** — Medium · Performance / Privacy · Backend · `api/dashboard/user/dash_user_views.py:233` `UserManagementCSV.get` (`GET /dashboard/user/csv/`), `:358` `UserVerificationCSV.get`, `organisation_views.py:246` `InstitutionCSVAPI`, `task/dash_task_view.py:687` `TaskListCSV`, `career_lab` `HiringCSVAPI`.
- *Problem.* The whole table (users with email and mobile) is serialized in one request, with no streaming, filter or limit. On a large DB this times out or exhausts worker memory. Exports of PII are not logged.
- *Fix.* Stream with `StreamingHttpResponse` + `iterator()`, or generate in Celery and e-mail a link; log who exported what.

**M-36 · Excel bulk role assignment skips the "special role" guard** — Medium · RBAC · Backend · `api/dashboard/roles/dash_roles_views.py:494` `UserRoleBulkAssignAPI.post` (`POST /dashboard/roles/bulk-assign-excel/`).
- *Problem.* The JSON bulk-assign (`:260`) blocks Mentor / Intern / Company because they need extra records. The Excel path does not, so users get these roles (verified) without a `UserMentor` profile, intern guild link or company — their dashboards then fail. IG-scoped roles are granted as global roles. No file size / row limit.
- *Fix.* Reuse the same guard and the per-role provisioning; cap rows and file size.

**M-37 · Any "IG Lead" can activate an IG that is still only a request** — Medium · Business Logic · Backend · `api/dashboard/ig/dash_ig_view.py:529-575` `InterestGroupActivateAPIView` / `Deactivate…` (`POST /dashboard/ig/<pk>/activate/`).
- *Problem.* The view sets `status=active` for any IG, including `requested`, `rejected` and `cancelled` ones. IG creation requests are supposed to be approved by an Admin (`PATCH /ig/request/<pk>/` is Admin-only). A global IG Lead can bypass that.
- *Fix.* Allow activation only from `inactive`; send `requested` IGs through the request review.

**M-38 · Dashboard and backend disagree on who can manage interns** — Medium · Cross-repo / RBAC · Dashboard `src/lib/auth/route-access.ts:137-141` + `roles.ts:93` vs Backend `api/dashboard/manage_interns/**`, `api/dashboard/intern/minutes`.
- *Problem.* The dashboard lets **Associate** open `/dashboard/management/manage-interns` (and `…/minutes`), but every backend manage-interns API rejects Associate ("You do not have the required role") → the pages load empty with error toasts for Associates. At the same time the backend allows plain **Intern**, which the dashboard hides (H-21).
- *Fix.* Pick one list (Admin, Associate, Intern Lead) and use it on both sides.

**M-39 · Deleting a task wipes the karma history of everyone who did it** — Medium · Data integrity · Backend · `api/dashboard/task/dash_task_view.py:569` `TaskAPI.delete` (Admin / Fellow / Associate); FKs `db/task.py:258, 294, 385` (`on_delete=CASCADE`).
- *Problem.* Task delete is a hard delete that cascades all `KarmaActivityLog`, `MucoinActivityLog` and `VoucherLog` rows of that task. Wallet karma is not reduced, so wallet totals and log-based stats (leaderboards, level feed, profile history) disagree.
- *Fix.* Soft-delete tasks (`active=False`), or block delete when logs exist; if deletion is needed, adjust wallets in the same transaction.

**M-40 · Learning-circle chat WebSocket has no authentication** — Medium · Security · Backend · `api/dashboard/lc/dash_lc_consumers.py` `LcChatConsumer` (ws route `/dashboard/<lc_id>/chat/<room_name>/<user_id>/`, `api/routing.py`).
- *Problem.* The consumer trusts the `user_id` in the URL. User ids are returned by public APIs (for example `GET /learningcircle/members/<id>/`). The chat group is `chat_{room_name}` and is not tied to `lc_id`, so a member of any circle can join any other circle's room. There is no origin check. (The rest of `api/dashboard/lc/` is dead code, but this consumer is live whenever the ASGI server runs.)
- *Fix.* Authenticate the socket with the JWT (query param or cookie) in a custom middleware, derive the user from the token, use `chat_{lc_id}`, add `AllowedHostsOriginValidator` — or remove the route if the chat is not used.

**M-41 · Public "landing stats" WebSocket runs full-table counts on every connection** — Medium · Performance / DoS · Backend · `api/common/common_consumer.py` `GlobalCount.connect`, signal handlers `db_signals` (same file).
- *Problem.* Every anonymous connection runs 6 aggregate queries, including `Sum` + `Count` over the whole `karma_activity_log` table. Opening many connections is a cheap way to load the database. The signal handlers also run `COUNT(*)` + a Redis publish inside every request that creates or deletes a user, LC, IG, role link or organization. The shared `landing_stats.data` dict is mutated from many threads.
- *Fix.* Cache the stats (for example 60 s) and serve them from the cache; move the signal work to Celery; rate-limit connections.

**M-42 · Anyone can create a learning circle under any college (and broadcast to its students)** — Medium · Business Logic / Abuse · Backend · `api/dashboard/learningcircle/learningcircle_serializer.py` `LearningCircleCreateEditSerialzier` (`ig` and `org` accept any id), `learningcircle_views.py:141-172` (`POST /learningcircle/create/`, broadcast at `:156`).
- *Problem.* The org is not checked against the creator's own college and the IG is not checked to be active. Each create sends the broadcast "A new Learning Circle "<title>" has been formed in your campus!" to **every member of that campus**, with a title chosen by the user. Each create also gives karma (H-10). PUT can move a circle to another org/IG later.
- *Fix.* Force `org` = the creator's verified college, require an active IG the user belongs to, rate-limit creation, and escape/limit the title in broadcasts.

**M-43 · A circle lead can add any user as a member without their consent** — Medium · Business Logic · Backend · `api/dashboard/learningcircle/learningcircle_views.py:1418` `CircleMemberAddAPI.post` (`POST /learningcircle/members/add/<circle_id>/`, used by `features/learning-circle/api/learning-circle.api.ts:164`).
- *Problem.* The lead gives a muid; the backend deletes that user's pending invite/request and creates `accepted=True` directly. There is no consent, no college/IG check, no member cap, and a user who rejected an invite gets a second link. With the meeting report flow (minimum 2 attendees, the organizer can approve themselves) this helps karma farming with extra accounts (see H-10).
- *Fix.* Turn "add" into "invite" (user must accept), or limit it to users of the same campus/IG and notify them.

**M-44 · Donation verification ignores its own validation result and the payment status** — Medium · Data integrity · Backend · `api/donate/views.py:516` and `:750` (`if donation_serializer.is_valid(): save()` with no else).
- *Problem.* If validation fails, the payment is **not recorded**, but the API still returns success and e-mails a receipt. The Razorpay payment `status` (`captured`) is never checked.
- *Fix.* Return an error (and alert) when the record cannot be saved; require `captured`; use a Razorpay webhook as the source of truth.

**M-45 · Referral invites can be used to send spam from muLearn's mail server** — Medium · Abuse · Backend · `api/dashboard/referral/referral_view.py` `Referral.post` (`POST /dashboard/referral/send-referral/`).
- *Problem.* Any logged-in user can make the platform send "AN INVITE TO INSPIRE" e-mails to any address, as many times as they want (no rate limit or de-duplication). The only user-controlled text is the sender's full name, which is free text (a URL or a phishing line fits). An unknown `invite_type` returns success without doing anything. The muCoin debit is a read-modify-write (`wallet.coin -= 1`), so two parallel requests can spend the same coin.
- *Fix.* Rate-limit per user/day, de-duplicate per target email, validate `invite_type`, use `F("coin") - 1` with a `coin__gte=1` filter.

**M-46 · Discord moderation task list crashes when any karma log has no user** — Medium · Bug · Backend · `api/dashboard/discord_moderator/serializer.py:7` (`source="user.full_name"`) on nullable `KarmaActivityLog.user` (`db/task.py:259`); page `/dashboard/management/discord-moderation` (`features/discord-moderation/api/discord-moderation.api.ts:54`).
- *Problem.* One log with `user=NULL` (allowed by the model) makes the whole list return 500. The view also lists **all** karma logs in the system with no filter by moderator scope.
- *Fix.* `source="user.full_name", default=None` (or filter `user__isnull=False`), and filter to Discord-channel tasks.

**M-47 · Three campus APIs always crash** — Medium · Bug · Backend · `api/dashboard/campus/campus_views.py:794` (`GET /dashboard/campus/student-list/`: `annotate(full_name=F("full_name"), …)` → "The annotation 'full_name' conflicts with a field on the model"); `api/dashboard/campus/serializers.py:858, 885` (`GET /campus/learning-circles/<id>/members/`, `GET /campus/igs/<id>/members/`: `user.user_lvl_link_user.first()` on a OneToOne relation).
- *Problem.* 500 for every caller (confirmed for Campus Lead, Enabler, Lead Enabler, Mentor). The dashboard does not call these three routes today, but other clients may.
- *Fix.* Remove the self-annotations; use `getattr(obj.user, "user_lvl_link_user", None)`.

**M-48 · `PATCH /dashboard/profile/user-preferences/` always crashes** — Medium · Bug · Backend · `api/dashboard/profile/profile_view.py:941` uses `profile_serializer.UserPreferencesSerializer`, which does not exist → `AttributeError` → 500. (The dashboard uses `/dashboard/user/preferences/` instead, which works.) *Fix.* Remove the method or add the serializer.

**M-49 · Top-100 coders leaderboard always crashes** — Medium · Bug · Backend · `api/top100_coders/top100_view.py:25-74` raw SQL selects `u.profile_pic`, but `profile_pic` is a Python property (`db/user.py:44`), not a column (`schema.sql` user table has none) → `OperationalError` → 500 for everyone on `GET /api/v1/top100/leaderboard/`. *Fix.* Remove the column from the SQL and build the URL in Python.

**M-50 · Launchpad and dashboard tokens are interchangeable** — Medium · Security · Backend · `utils/launchpad_permission.py:88` `LaunchpadJWTUtils.is_jwt_authenticated`, `api/launchpad/launchpad_views.py:90` `generate_launchpad_jwt`; `utils/permission.py:160` `JWTUtils.is_jwt_authenticated`.
- *Problem.* Both systems sign tokens with the same `SECRET_KEY` and check only `id` + `expiry` (never `tokenType` or an audience). A dashboard token is accepted by Launchpad views, which then crash with `KeyError: 'user_type'` (500 on 14 routes: `job/<id>`, `hire-requests`, `accepted-students`, `list-launchpad-students`, `send-job-invitations`, `application-final-decision`, `register-recruiter`, `add-job`, `change-password`, …). A Launchpad token (id = a Launchpad company/recruiter id) is accepted by every dashboard view as a logged-in user with no roles.
- *Fix.* Add `aud` ("dashboard" / "launchpad") and `tokenType` to every token and check them; use a separate key for Launchpad.

**M-51 · Outbound HTTP calls without timeouts (and one public endpoint that calls a third party on every request)** — Medium · Reliability · Backend · 25 `requests.*` calls, only 6 set a timeout: `api/integrations/wadhwani/wadhwani_views.py`, `qseverse/qseverse_views.py`, `kkem/kkem_views.py`, `kkem/kkem_helper.py`, `integrations_helper.py:108-120`, `api/dashboard/profile/profile_view.py:437` (favicon download for QR), `api/common/common_views.py:674` (`GTASANDSHOREAPI`), `utils/utils.py`, `mu_celery/task.py`, `mu_celery/achievement_tasks.py`.
- *Problem.* A slow partner API holds a worker forever (the prod server is the single-process `runserver`, see earlier deployment findings). `GET /api/v1/public/gta-sandshore/` is anonymous, calls `devfolio.vez.social` on every hit, writes `response.json` into the working directory (race between requests) and crashes if the partner is down and the file does not exist.
- *Fix.* Add `timeout=(3, 10)` everywhere (a shared session helper), cache partner responses, remove the file write.

**M-52 · Registration crashes (500) for an unknown invite code** — Medium · Bug · Backend · `api/register/serializers.py:218-224` `ReferralSerializer.validate_invite_code` does `.filter(...).first().user` and only catches `DoesNotExist` → `AttributeError` → 500 on `POST /api/v1/register/` (verified). *Fix.* `obj = …first(); if not obj: raise ValidationError(...)`.

**M-53 · Hackathon "add organiser" always crashes** — Medium · Bug · Backend · `api/hackathon/serializer.py` never imports `User`: `HackathonOrganiserSerializer.validate_muid` (`:378`) → `NameError` on every `POST /api/v1/hackathon/add-organiser/<id>/`; `list-applicants` (`:425-427`) crashes when a submission has `data=NULL` or is missing system fields; `submit-hackathon` without a hackathon → `IntegrityError` 500. Not used by the dashboard. *Fix.* `from db.user import User`; validate inputs.

**M-54 · Intern pages: the dashboard lets Admin and Intern Lead in, the backend only answers Interns** — Medium · Cross-repo / RBAC · Dashboard `src/lib/auth/route-access.ts:81-87` (`/dashboard/intern*`: Admin, Intern, Intern Lead) vs Backend `api/dashboard/intern/**` (`role_required([INTERN])` on overview, tasks, timesheets, reviews, leave, leaderboard; `intern/guilds/` and `intern/tasks/categories/` also reject Intern Lead).
- *Seen in the crawl.* As Intern Lead and as Admin, every call on `/dashboard/intern`, `/intern/leaderboard`, `/intern/leave`, `/intern/minutes`, `/intern/quest-log`, `/intern/tasks`, `/intern/timesheet`, `/intern/weekly-review` returns `400 "You do not have the required role"`. On the manage pages, `GET /dashboard/intern/guilds/` and `/intern/tasks/categories/` fail for Intern Lead, so the guild/category dropdowns on `/dashboard/management/manage-interns/tasks` and `/minutes` are empty.
- *Fix.* Decide who uses each page; either hide intern pages from Admin/Intern Lead, or allow those roles on the read APIs; allow Intern Lead on `guilds` and `tasks/categories`.

**M-55 · Zonal and District dashboards: Admin is let in but rejected; leads need a college link** — Medium · Cross-repo / RBAC · Dashboard `route-access.ts:71-78` (`ZONAL_ROLES`, `DISTRICT_ROLES` include Admin) vs Backend `api/dashboard/zonal/dash_zonal_views.py`, `district/dash_district_views.py` (Admin rejected; scope is taken from the lead's **own college link** → "No college organization linked to this user." for a lead without one).
- *Seen in the crawl.* Admin: 5/5 calls → 400 role error on both pages. Zonal/District lead without a college link: 5/5 calls → 400.
- *Fix.* Store the zone/district on the role assignment (not derived from the college); let Admin pick a zone/district; align the role lists.

**M-56 · Career Labs and Departments admin pages are open to Fellows in the dashboard, but the backend rejects them** — Medium · Cross-repo / RBAC · Dashboard `route-access.ts:122` (`/dashboard/management/homepage` → `MANAGEMENT_ROLES` incl. Fellow) and `route-access.ts:161` (`/dashboard/management/organizations/departments` → `FELLOW_MANAGEMENT_ROLES`) vs Backend `api/dashboard/career_lab/career_lab_views.py:17` (`CAREER_LAB_ADMIN_ROLES = [Admin, Associate]`) and `organisation_views.py:434` `DepartmentAPI` (Admin only). Crawl: Fellow → `GET /dashboard/career-lab/hiring/` 400 and `GET /dashboard/organisation/departments/` 400 ("You do not have the required role"). *Fix.* Align the role lists.

**M-57 · Talent Pool page is visible to everyone but only works for verified companies** — Medium · UX / RBAC · `/dashboard/talent-pool` has no entry in `route-access.ts` (falls back to "any logged-in user"), while `GET /company/mulearners/` and `/shortlist/` require a verified company (crawl: Admin and Student get "Access denied. Verified company profile required."). *Fix.* Add `/dashboard/talent-pool` to the access map (Company) and hide it from other roles.

**M-58 · Home "open jobs" count is always empty** — Medium · API contract · Dashboard `src/features/home/api/home.api.ts:73-79` returns `response.pagination.totalCount`; schema `home.schema.ts:115-121` expects `currentPage/totalCount/previousPage`. Backend pagination (`utils/utils.py` `get_paginated_queryset`) returns `count/totalPages/isNext/isPrev/nextPage`. So `totalCount` is `undefined` on the home quick-action card. *Fix.* Use `pagination.count` and one shared pagination schema that matches the backend.

**M-59 · Even with beat added, 6 of the 10 scheduled jobs are not registered in the worker** — Medium · Deployment / Bug · Backend · `mulearnbackend/celery.py:8-24` (`include=[alumni_cron, org_aggregates_cron, learning_circle_aggregates_cron]` + `app.autodiscover_tasks()`, which only looks for modules named `tasks.py`; the code lives in `mu_celery/task.py`, `event_cron.py`, `mentor_tasks.py`, `company_tasks.py`, `intern_cron.py`, …).
- *Verified.* Loading the worker's app the same way the worker does registers only 9 tasks: `achievement_tasks.*` (3), `alumni_cron`, `learning_circle_aggregates_cron`, `media_content_tasks.fetch_and_attach_poster`, `org_aggregates_cron`, `task.onboard_user`, `task.send_email`. **Not registered:** `event_cron.transition_event_statuses_task`, `mentor_tasks.expire_stale_applications`, `mentor_tasks.expire_stale_grants`, `mentor_tasks.transition_mentorship_session_statuses`, `company_tasks.expire_stale_jobs`, `intern_cron.intern_daily_status_cron`, `intern_cron.intern_task_deadline_cron` — a worker would drop them as "unregistered task".
- *Fix.* List every `mu_celery.*` module in `include=[...]` (or rename them to `tasks.py` inside an installed app) and add a start-up check that every `CELERY_BEAT_SCHEDULE` task is registered.

#### Medium issues added in the performance pass

**M-60 · Interest-group APIs run 5–6 queries per interest group (up to 847 queries for one export)** — Medium · Performance · Backend · `api/dashboard/ig/dash_ig_serializer.py:236` `get_media_content_links`, `:254` `get_community_partners`, `:280` `to_representation` (user lookups); `api/dashboard/ig/impact_project_serializer.py:42` `get_team`, `:46` `get_links`.
- *Evidence (queries: small data → large data).* `GET /dashboard/ig/` 37 → 69 for one 10-row page; `/dashboard/ig/request/` 49 → 83; `/dashboard/ig/list/` 11 → 129 (every IG in one response; used by the home page; cached for 10 minutes, see M-09); `/dashboard/ig/csv/` 185 → 847; `/dashboard/ig/get/<pk>/` and `/public/ig/<pk>/` 13 → 25. Repeated queries: `SELECT … FROM user WHERE id = ?` (18 per page), media-content links and community-partner links (one each per IG), impact-project team and links (one each per project).
- *Fix.* `prefetch_related` the media links (with the date filter in a `Prefetch`), `community_partner_links__community_partner`, and impact projects with their team users and links; fetch all lead/mentor users in one query (the list view already does this in `get_ig_list_context` — reuse it in the other views).
- *Impact.* Slow IG admin pages and exports; slow home page whenever the cache is empty.

**M-61 · Paginated lists run 1–4 extra queries for every row** — Medium · Performance · Backend. Measured on one page of 10 rows (large data); the origin of the repeated query is in brackets:
- `dashboard/roles/` 32 (20 user lookups for `created_by`/`updated_by`; `dash_roles_serializer.py:84` `get_members` does `len(UserRoleLink.objects.filter(...))`, which loads **every member row** of the role to count it — for "Student" that is almost every user, see M-04).
- `dashboard/affiliation/` 32 (`affiliation/serializers.py:20` org count per row), `dashboard/channels/` 22, `dashboard/category/` 22 (user lookups).
- `dashboard/college/` 72 (5 aggregate queries per college, `college/serializer.py:40-75`).
- `dashboard/company/jobs/` 43 (user, company and job rules per job), `company/applications/me/` 33, `company/collaborations/` 23, `company/collaborations/discover/` 12, `company/list/` 12, `company/tasks/` 16 (`task_serializers.py:126` skills per task), `company/jobs/<id>/applications/` 17.
- `dashboard/events/admin/` 12 (`events/serializers.py:287` `get_viewer_interest_status` per event), `events/tasks/` 20, `events/manage/<id>/` 28 and `events/<id>/` 17 (`serializers.py:392` `get_linked_tasks`).
- `dashboard/mentor/opportunities/` 21, `mentor/session/admin/list/` 12, `manage-interns/reviews/` 12, `manage-interns/reviews/timesheets/` 12, `community-partner/` 12, `muComics/comics/` 15 (`comic/serializers.py:69`), `discord-moderator/tasklist/` 22, `career-lab/hiring/` 16, `dashboard/referral/` 13 (`referral_serializer.py:19,23` wallet and level per referred user).
- *Why it matters.* Cost = rows on the page × extra queries, and each query is a round trip to the database. Some screens ask for 1,000 rows (L-58).
- *Fix.* `select_related("created_by", "updated_by", …)` in each list queryset; `annotate(Count(...))` instead of per-row counts; `prefetch_related` for skills, rules and links. Add tests that assert the query count of each list endpoint with 2 and 20 rows (`assertNumQueries`), so it cannot grow back.

**M-62 · Exports run one or more queries per exported row** — Medium · Performance · Backend (adds to M-35). `GET /dashboard/ig/csv/` 185 → 847 queries; `/dashboard/roles/csv/` 106 → 331 (`RoleManagementCSV`: `get_members` + 2 user lookups per role); `/dashboard/karma-voucher/export/` 13 → 113 (`ExportVoucherLogAPI`, 3 lookups per voucher); `/dashboard/career-lab/hiring/csv/` 1 → 51. On top of loading everything into memory (M-35), export time grows with rows × queries per row. *Fix.* The same `select_related`/`prefetch_related` as M-60/M-61; stream with `StreamingHttpResponse` and `.iterator(chunk_size=2000)`; run large exports as a background job that sends a download link.

**M-63 · The company home page recounts the whole talent pool several times per visit, and the shortlist runs 3 queries per learner** — Medium · Performance · Backend · `api/dashboard/company/analytics_views.py:169-200` `_talent_pool_payload` (used by `GET /dashboard/company/home-summary/` 34 → 61 queries and `/dashboard/company/talent-pool/analytics/` 27 → 54); `api/dashboard/company/mulearner_views.py:118-140` `CompanyTalentShortlistAPI.get` (`GET /dashboard/company/mulearners/shortlist/`, 5 → 149 queries for 24 learners).
- *Problem.* The talent-pool summary runs one `COUNT(DISTINCT …)` over all public learners (users + settings + roles) **for each level**, plus an IG aggregate, every time any company opens its home page, with no cache. `MulearnerDirectorySerializer.get_college` (`mulearner_serializers.py:36-44`) has the comment "uses prefetch_related cache — no extra DB hit", but the view never prefetches, so it makes 3 queries per learner. The shortlist is not paginated.
- *Fix.* One grouped query (`values("user_lvl_link_user__level").annotate(Count("id", distinct=True))`); cache the summary for 10–15 minutes (without filters it is the same for every company); `prefetch_related("user__user_organization_link_user__org")` and paginate the shortlist.

**M-64 · Common filters have no database index (checked against `schema.sql`)** — Medium · Performance · Backend / Database. Every SQL query that the GET endpoints ran in the test was compared with the indexes in `schema.sql` (a dump of `mu_dev` from 2026-08-17). Appendix I marks each affected endpoint with "no index".
- `events`: only `id`, `created_by` and `updated_by` are indexed, but every event list and calendar filters on `status`, `deleted_at`, `end_datetime`, `scope`, `scope_org_id`, `organiser_org_id`, `organiser_ig_id` → a full scan of `events` on each call (public events, campus/IG/cluster events, calendars).
- `karma_activity_log` (the biggest table): no index on `created_at`, used by karma trend, weekly karma and the monthly leaderboards (H-37). `campus/weekly-karma/` also filters with `created_at__date=…` (`campus/serializers.py:455`), which wraps the column in a function, so no index could be used even if one existed. Use a range (`created_at >= day_start AND created_at < next_day`).
- `wallet`: no index on `karma` (rank, percentile, leaderboards — H-36/H-37) or `karma_last_updated_at` (campus "active members").
- `task_list`: no index on `hashtag` (intern leaderboard, achievements, launchpad and the voucher import look tasks up by hashtag), `event_id`, `approval_status`, `requested_by`, `submitted_by_company_id`.
- 68 of the 140 tables used by the code are not in `schema.sql` at all (for example `mentor_application`, `company`, `company_jobs`, `user_job_application`, `events_interest`, `events_connection`, `mentorship_session`, `intern_*`, `media_content`, `impact_project*`). Their indexes cannot be checked; this is the missing migration scripts problem (C-06/H-16). When those scripts are written, index at least `mentor_application(user_id, status)` (43 endpoints filter on it), `company(company_user_id, status)`, `company(org_id, status)`, `company_admin_link(user_id, status)`, `company_jobs(company_id, status)`, `user_job_application(job_id, status)`, `events_interest(event_id, user_id)`, `events_connection(event_id, entity_type)`, `mentorship_session(entity_id, session_type, status)`, `impact_project(ig_id)`, `ig_media_content_link(ig_id)` and `ig_community_partner_link(ig_id)`.
- *Fix.* Add composite indexes such as `events(status, deleted_at, end_datetime)`, `events(scope_org_id, status)`, `events(organiser_org_id, status)`, `karma_activity_log(created_at)` and `(user_id, created_at)`, `wallet(karma)`, `task_list(hashtag)`, `task_list(event_id)`; confirm each with `EXPLAIN` on a copy of production data.

**M-65 · 21 list endpoints return every row, with no paging** — Medium · Performance · Backend. These endpoints returned all rows, and the count grew with the data (Appendix I, "returns every row"). The ones that will grow most in production: `dashboard/task/organization/` and `hackathon/list-organisations/` (every organization — thousands of colleges and companies), `public/list/college/`, `register/role/list/` and `dashboard/dynamic-management/roles/` (every role, including all IG roles), `dashboard/achievement/list/` (140 rows = 110 KB in the test), `launchpad/company-list/`, `launchpad/list-jobs/`, `dashboard/task/ig/`, `dashboard/events/manage/<id>/tasks/meta/` (every task), `dashboard/skill/dropdown/`, `notification/broadcast/list/all/`, `dashboard/profile/user-log/` (every karma log of a user — thousands for active users), the company templates and shortlist lists, and `public/career-lab/ongoing/` (also 2 user queries per post). The frontend pays too: the admin achievements list renders every achievement, 5,442 DOM nodes with 140 achievements in the test (Appendix J). *Fix.* Paginate them (the helper already exists), or return only `id` + `name` for dropdowns and add a server-side search box.

**M-66 · Campus and college pages compute everything live on every visit** — Medium · Performance · Backend. `GET /dashboard/campus/campus-details/` 18 queries, `/campus/home-summary/` 17, `/campus/<org_id>/` 16, `/public/campus-details/<college_code>/` 19, `/campus/weekly-karma/` 9 (7 date-function queries on the karma log, M-64), `/dashboard/college/` 5 per college (M-61). `CampusDetailsSerializer` (`campus/serializers.py:246-400`, 9 method fields: lead, level, active members, total karma, rank, karma of the last 7 and 30 days, active IG count, social links) and `CampusDetailsPublicSerializer` (8 method fields) each run their own aggregate over org members and karma logs. The cached columns built for this (`organization.cached_total_karma` and friends) are never refreshed because Celery beat does not run (H-35). *Fix.* After H-35, read the cached values; compute rank and the 7/30-day karma in the scheduled job; merge the rest into one `annotate` query; cache per campus for a few minutes.

**M-67 · The home page asks the server to pre-render dozens of other pages** — Medium · Performance · Dashboard · home cards (`src/features/home/components/interest-groups-card.tsx`, `learning-circles-card.tsx`, `mentor/my-igs-card.tsx`) and `src/components/ui/version-badge.tsx:10-17` (changelog link in the sidebar) use `<Link>` with the default prefetch.
- *Problem.* On load, `/dashboard` requested **46 RSC payloads** for other pages (every IG and learning-circle card, leaderboard, projects, events, changelog). Some were requested twice with different router-state hashes, and the changelog up to 7 times. The median dashboard page makes 13 such requests. Each prefetch of a dynamic page is a server render on the Next.js server (and the layout reads `CHANGELOG.md` each time, L-63).
- *Fix.* `prefetch={false}` on card links and on the version badge (the sidebar menu already does this, `app-sidebar.tsx:113`), or prefetch only on hover.
- *Impact.* Wasted bandwidth on mobile and many extra server renders per home-page view.

**M-68 · A failing API call is sent 4 times and the error appears about 8 s late** — Medium · Performance / UX · Dashboard · `src/app/providers.tsx:22-31` (React Query `retry`: up to 3 retries for every status ≥ 500, with the default 1 s / 2 s / 4 s back-off).
- *Evidence (crawl).* On `/dashboard/learning-circle/[id]` and its meeting page, `learningcircle/info/<id>/` and `learningcircle/meeting/list/<id>/` each ran 4 times (at about 6.9 s, 8.7 s, 10.9 s and 15.0 s). On `/dashboard/learning-circle/invite/[link_id]`, `invite/status/<id>/` ran 4 times (H-27). The error screen came about 8 s after the first failure.
- *Fix.* Retry at most once, and only for network errors and 502/503/504; never for 500.
- *Impact.* Every backend 500 (Appendix G) costs 4× the load, and users wait longer to see what went wrong.

**M-69 · Some search boxes send a request on every key press** — Medium · Performance · Dashboard. 60 pages have a search box. The crawl typed 6 letters into each one, 150 ms apart (normal typing speed):
- *A request on every key press (no debounce).* `/dashboard/management/session-verification` sent **24** requests for 6 letters (it re-fetches 4 lists on each key: pending approval, scheduled, rejected and all sessions); `/dashboard/management/role-verification` and `/dashboard/management/mentor-verification` sent **18** (3 lists on each key: pending mentors, all mentors, change requests; `src/features/mentor/admin/components/mentor-verification-page.tsx`). `/dashboard/campus/manage` (campus leaderboard search, `src/features/campus-manage/components/campus-manage-dashboard.tsx`), `/dashboard/company/jobs/[jobId]` (applicant search), `/dashboard/management/manage-interns/intern-report`, `leave-reviews` and `timesheet-reviews`, and `/dashboard/weekly-twitches` (`src/features/weekly-twitches/components/office-hours-tab.tsx`) each sent 6. Every request is a backend search with `icontains` on several columns (L-61).
- *A server round trip on every key press.* `/dashboard/search/students`, `/search/mentors`, `/search/campuses` and `/dashboard/campus/manage` made **6** Next.js RSC requests for 6 letters, because each key press rewrites the URL with `router.replace` (`src/features/search/components/StudentsSearchClient.tsx:34-39`, `MentorsSearchClient.tsx:34-39`, `CampusesSearchClient.tsx:66-78`). The API call itself on these pages is debounced (800 ms), but the URL update is not.
- The other 47 pages behave well (one request after typing stops, or filtering in the browser). `/dashboard/search` redirects to `/dashboard/search/students` and behaves the same.
- *Fix.* Use the existing `useDebounce` hook (300–500 ms) for every search that calls the API; update the URL from the debounced value (or with `window.history.replaceState`, which does not ask the server); on tabbed pages fetch only the visible tab.
- *Impact.* 6–24 backend searches for one 6-letter word, each a full-table scan (L-61), and a server render per key on the search pages.

**M-70 · E-mails are sent inside the request in 14 places, and SMTP has no timeout** — Medium · Performance / Reliability · Backend · `api/dashboard/lc/dash_lc_view.py:692,753` (LC invites), `api/dashboard/referral/referral_view.py:40,56`, `api/dashboard/user/dash_user_views.py:335` (user verification) and `:422` (forgot password, M-34), `api/donate/views.py:573,813` (donation receipts), `api/integrations/kkem/kkem_views.py:130`, `api/launchpad/launchpad_views.py:155,994,3203`, `api/dashboard/karma_voucher/karma_voucher_view.py:229,340` (H-38) — all through `utils.send_template_mail` or `EmailMessage.send`. Celery already has `mu_celery.task.send_email`, but these views do not use it. Each SMTP round trip (about 0.3–3 s) is added to the request, and because `EMAIL_TIMEOUT` is not set, a stuck mail server hangs the worker (with the single-process server of H-35 that blocks everyone). *Fix.* Use `send_email.delay(...)` everywhere and set `EMAIL_TIMEOUT = 10`.

### Low

**L-01** · Error-log "dismiss" URL has no trailing slash (`src/api/endpoints.ts:1035`). This relies on the APPEND_SLASH 301 redirect for a PATCH (a RuntimeError when DEBUG=True). *Fix:* Add `/`.

**L-02** · `POST /dashboard/profile/userterm-approved/<muid>/` needs no auth (`profile_view.py:678`). Anyone can mark terms as accepted for any user. *Fix:* Require auth and use the JWT user.

**L-03** · Route edge cases that return the wrong result or 500:
- `POST /ig/<pk>/leave/` *joins* (same view as join).
- `DELETE /ig/request/` → TypeError 500.
- `GET /task/<id>/review/` and `PATCH /task/pending/` → TypeError 500 (`AdminTaskApprovalAPI` method signatures).
- `sortBy=-interest_count` → `order_by('--interest_count')` 500 (`admin_views.py:77`, `public_views.py:153`).

**L-04** · Dead code:
- `validateRegistrationData` (calls the missing `/register/validate/`).
- Unused job-approval hooks (see H-13).
- Legacy notification hooks.
- 94 endpoint keys in `endpoints.ts` that are never used (listed in Appendix C).
- Duplicate URL patterns: `roles/` ×2, `roles/<id>/` ×2, `user/<id>/` ×3, `user/verification/<id>/` ×2.

**L-05** · Auth call details:
- `loginWithPassword` / `loginWithOTP` use the authenticated client. A 401 from the auth service would trigger refresh → redirect and hide the error.
- `googleCallback(code)` does not URL-encode `code`.
- `redirectToLogin()` drops the `ruri` return path.

**L-06** · Pagination returns the **last page** for an out-of-range `pageIndex` (`utils/utils.py:118-122`), so the UI can show page N with page M's data.

**L-07** · The mentor "Session Requests" card shows negative "time ago" for future sessions when `created_at` is missing (`session-requests-card.tsx:35-39`).

**L-08** · User-supplied links are put straight into `href` without a scheme check (for example `registration_url`, `meet_link`, `output_link`, impact-project links). React 19 blocks `javascript:` URLs, so the risk is low, but the backend should validate schemes for all clients.

**L-09** · `/dashboard/management/manage-launchpad` and `/dashboard/management/verify-organizations` are in `route-access.ts` but have no page (stale config).

#### Low issues added in the second pass

**L-10** · **Anonymous calls to many views crash with 500 instead of 401.** Views that call `JWTUtils.fetch_role/fetch_user_id` without an auth class do `token[1]` on an empty header → `IndexError` (`utils/permission.py:124/137`). Seen on 15+ `achievement/*` routes, `organisation/affiliation/list/`, `institutes/info|prefill/<code>/`, `college/change-college/`, `user/profile/update/`, `user/organization/`, `wadhwani/user-login/`, `launchpad/delete-company/`. The same views accept **expired** tokens (M-14). *Fix:* add `authentication_classes = [CustomizePermission]` everywhere, and make `fetch_*` return 401 on a missing header.

**L-11** · **173 route/method pairs return 500 instead of 405.** One view class is mounted on several URLs (with and without an id), and a method is reachable on the URL that lacks its parameter (for example `PATCH /dashboard/roles/`, `DELETE /dashboard/ig/`, `GET /dashboard/roles/<id>/`, `POST /dashboard/location/countries/<id>/`) → `TypeError: … missing 1 required positional argument` → 500. Full list in Appendix H. Dead dashboard code hits one of them: `src/features/company-tasks/api/tasks.api.ts:223,231` (`updateTaskType`/`deleteTaskType` call `PUT/DELETE list-task-type/` without an id; the live UI uses `features/tasks` which is correct). *Fix:* split list and detail views, or give the methods `pk=None` and return 405.

**L-12** · **Missing-object and bad-input 500s.** `projects_view.py:36,57` (`Project.objects.get` → 500 for an unknown project on `GET/PUT /projects/<pk>/`); `dash_user_views.py:315,350` (`UserRoleLink.objects.get` on verification PATCH/DELETE with a stale id, reachable from the Role Verification page after another admin acted); `dash_roles_views.py:304` (bulk remove without `users` → `TypeError`); `integrations_helper.py:26` (malformed KKEM token → `DecodeError`); `integrations_helper.py:74-81` (`token_required` raises a plain `CustomException`, which DRF does not handle → 500 instead of 401 for KKEM partner calls); `learningcircle_views.py:753` (report with a list instead of a dict); `campus_views.py:503` `ChangeStudentTypeAPI.patch` (member not in the lead's college → serializer without instance → `NotImplementedError: create() must be implemented` → 500 instead of 404). *Fix:* `get_object_or_404`/`filter().first()` + validation; make `CustomException` an `APIException`.

**L-13** · `GET /dashboard/error-log/graph/` crashes when the log is empty (`log_helper.py:291` `[-1]` on an empty list) or contains a path that does not resolve (`resolve(hit)` raises `Resolver404`, `:275`). Not used by the dashboard.

**L-14** · Institution prefill always returns `affiliation_name: null`: `api/dashboard/organisation/serializers.py:244` uses `source="affiliation.name"`, but `OrgAffiliation` has `title`. DRF hides the error because the field is `allow_null`.

**L-15** · A wrong `?referral_id=` blocks sign-up. The register page always sends `referral: {muid}` (`src/app/(auth)/register/register-client.tsx:197,308`); the backend rejects the whole registration if the muid is unknown, and the UI gives no way to drop it.

**L-16** · `generate_muid` (`api/register/register_helper.py:15`) keeps every character of the full name (`/`, `?`, `#`, `@`, emoji) → muIDs that break `<str:muid>` routes and profile links. The uniqueness check then insert is not atomic → `IntegrityError` 500 on two sign-ups with the same name at the same time.

**L-17** · Account existence is exposed: `POST /register/email-verification/` returns `value: true/false` for any email; `POST /dashboard/user/forgot-password/` says "User not exist". No rate limit on either.

**L-18** · `POST /register/select-domains/` and `select-endgoals/` accept unlimited arbitrary strings (no allow-list, no length/count limit); errors are `print()`ed.

**L-19** · The auth proxy views (`api/auth/auth_views.py`) do not forward the client IP (no `X-Forwarded-For`), so the auth server's IP-based throttling and login geo lookup see the backend server's IP. Error messages include `str(RequestException)` (internal `AUTH_DOMAIN` URL).

**L-20** · `GET /register/connect-discord/` has side effects (queues `onboard_user`) and uses an exception from `is_jwt_authenticated` for control flow (anonymous → 400/500 instead of 401).

**L-21** · Admin user delete (`DELETE /dashboard/user/<id>/`) is a hard delete that cascades karma logs and links with no audit record; `PATCH /dashboard/user/<id>/` uses `User.objects.get` (500 for a bad id) and writes into `request.data` (500 for multipart bodies).

**L-22** · Role verification: approving any role sends the `mentor_verification.html` e-mail template; rejecting is a hard delete of the request with no notification to the user (`dash_user_views.py:309-356`).

**L-23** · Public profile endpoints crash or ignore privacy: `GET /profile/user-profile/<muid>/` uses `.get()` → 500 for an unknown muid; `user_settings` can be `None` → 500 in `UserProfileAPI`, `UserLogAPI`, `UserLevelsAPI`, `GetSocialsAPI`, `ShareUserProfileAPI`, `QrcodeRetrieveAPI`; `rank/<muid>/`, `badges/<muid>`, `permute/<muid>/` do not check `is_public` (private users' karma, rank, role titles, IGs and college are exposed; `rank` also reveals who is an Admin).

**L-24** · `UserRankSerializer.get_rank` (`profile_serializer.py:398`) loads the ids of every wallet with karma ≥ the user's into a Python list on each call (hundreds of thousands of rows for new users). `UserLogAPI` returns all karma logs with no pagination.

**L-25** · `ShareUserProfileAPI`: `GET /profile/share-user-profile/` returns `None` → 500; `GET …/<uuid>/` builds the QR for the **caller**, not the uuid, crashes for anonymous users, downloads the favicon on every call (no timeout) and writes a file each time.

**L-26** · Change password (`POST /profile/change-password/`): no password rules, no session revocation, and users who signed up with Google (NULL password) can never set a password (`check_password` always fails). The dashboard has an endpoint key (`src/api/endpoints.ts:45`) but no screen uses it (missing feature).

**L-27** · Home "top college of last month" (`GET /profile/karma-feed/`, `profile_view.py:790`) is not filtered to `org_type="College"`, so a company or community can be shown as the top college.

**L-28** · `PATCH /profile/ig-edit/` (`UserIgEditSerializer`) lets users join IGs whose status is `requested`, `rejected` or `cancelled` (only existence is checked).

**L-29** · `GET /roles/base-template/` has no role check (any user gets the full role list including internal roles); `PUT /roles/bulk-assign/<id>/` is a read ("users without this role") behind a write verb and runs a heavy `~Q` over all users.

**L-30** · IG rename (`PUT /ig/<pk>/`) is not atomic (IG saved first, then four role renames; a clash → `IntegrityError` after a partial rename). IG delete leaves the `"{code} CampusIGCoLead"` role and campus-execom catalog rows behind; deleting an unknown id returns success ("invalid ig", HTTP 200).

**L-31** · IG join limit can be exceeded: re-activating an old inactive link skips the "max 3 IGs" check (`dash_ig_view.py:1276`); the count is not locked. `POST /ig/<pk>/leave/` actually **joins** (same view as `/join/`).

**L-32** · A lead can invite someone "as lead" (`CircleInviteAPI`, `lead=true`), so a circle can end up with several leads, while the transfer-lead code assumes one. Users who rejected once can never request to join again, but a lead can still force-add them (M-43).

**L-33** · Anonymous users can read learning-circle member lists with user ids (`GET /learningcircle/members/<id>/`) and offline meeting places with GPS coordinates (`GET /learningcircle/meeting/list/<id>/`, `meeting/list-public/`). User ids also make M-40 easier.

**L-34** · Organizer report (`POST /learningcircle/meeting/report/<id>/`) expects `attendees` as an object; a list → `AttributeError` 500 (`learningcircle_views.py:753`).

**L-35** · Donations: `get_or_create_donor(email)` (`api/donate/views.py:405`) overwrites an existing donor's name/phone/PAN/address with whatever the next person typed for that e-mail; order creation has no rate limit; error text echoes exception strings.

**L-36** · `POST /dashboard/coupon/verify-coupon/` is anonymous, not rate-limited, returns a hard-coded 100% discount and a hard-coded ticket id for any existing code, and never marks the coupon as used.

**L-37** · `POST /organisation/karma-type/create/` and `karma-log/create/` have no auth class and no role check (any token, even expired; learners reach validation). On success they call `CustomResponse("…")` with a string as `message` → `TypeError` → 500 **after** the row is saved. `OrgKarmaLog` is not used anywhere else.

**L-38** · Org delete (`DELETE /organisation/institutes/delete/<code>/`) is a hard delete that cascades learning circles (`LearningCircle.org on_delete=CASCADE`) and all member links; the Excel org import matches districts by name only (district names are not unique across states); if one row fails serializer validation, nothing is saved but the response is still "success" with an empty list.

**L-39** · `GET /api/v1/protected/organisation/get-institutes/<district>/` is under "protected" but does not check the protection key (the sibling route does); the key is compared with `==`.

**L-40** · `POST /dashboard/projects/` accepts an empty body (the create path uses the all-optional update serializer) → empty projects; errors are `print()`ed.

**L-41** · The company talent directory (`GET /company/mulearners/`) shows the **e-mail** of every user with a public profile to any verified company; making a profile public is not consent to recruiter contact, and `interested_in_work` is ignored.

**L-42** · Campus analytics for **any** `org_id` are readable by any logged-in user (`campus/<org_id>/`, `/leaderboard/`, `student-level/<org_id>/`, `weekly-karma/<org_id>/`). Leaderboard rows include graduation year, department, alumni flag, join date and last-karma date.

**L-43** · Fellow and Tech Team can download, view and **clear** server error logs (`POST /error-log/clear/<name>/`). Logs may hold request data and secrets (M-22); clearing destroys evidence and has no audit trail.

**L-44** · Dead code with runtime errors: `api/dashboard/lc/*` (URLs commented out in `api/dashboard/urls.py:17`; undefined names `user_circle_link` `dash_lc_serializer.py:137`, `previous_meetings` `:477`), `api/dashboard/task_report/*` (never included in any `urls.py`; `TaskReportSerializer` undefined in `views.py:55,87`). Only the LC chat consumer from `lc/` is still live (M-40). Ruff also reports unused variables that hide logic mistakes (for example intern leaderboard `leaderboard_views.py:63-69,171-177` computes `total_intern_karma`, `completed_count`, `complexity_score` and never uses them).

**L-45** · Dashboard shows the literal text **"TODO"** as the placeholder of two select boxes: `src/app/(dashboard)/dashboard/intern/tasks/components/task-detail-dialog.tsx:197` and `intern-task-client.tsx:246`.

**L-46** · Dashboard lint: 50 Biome warnings (unused imports/variables from features disabled because of "backend conflict", 2 `any`): `features/manage-ig/components/ig-form-dialog.tsx` (30), `ig-detail.tsx`, `interest-group-detail-client.tsx`, `company-templates-client.tsx`, `mentor-roster-tab.tsx`, `session-create-dialog.tsx:65`, `session-edit-sheet.tsx:81`, `tasks-view.tsx:3`, `company-jobs/api/jobs.api.ts:39`.

**L-47** · `POST /company/jobs/<id>/view/` (job view counter, `api/dashboard/company/job_views.py` `TrackJobViewAPIView`) is public and de-duplicates by client IP taken from the **`X-Forwarded-For` header first**. The caller controls that header, so sending a different fake value each time bypasses the one-view-per-hour rule and inflates the view count that feeds company conversion analytics. *Fix:* use the proxy-verified client IP (trusted-proxy setting) and de-duplicate per user for logged-in users.

**L-48** · `/dashboard/search` redirect triggers React error #310 ("rendered more hooks than during the previous render") in the production build (seen in the crawl and reproduced; the target page `/dashboard/search/students` itself is fine). The redirect is a server `redirect()` inside a route that the layout treats as public; the hook-order change happens in a `useMemo` in the shared layout during the redirect. *Fix.* Redirect in `next.config`/proxy instead of the page, and check the layout components for hooks after early returns.

**L-49** · Zod schemas are stricter than the backend for nullable fields, so the client logs a mismatch (development) and returns raw, unvalidated data (production): `events/meta/categories/` (`description: null`), `profile/karma-feed/` (`top_user.full_name/muid`, `top_college.name` are `null` when there was no karma last month), `media-content/salt-mango-tree/` and `grab-your-superpowers/` (`campus: null`), `career-lab/hiring/` (`title: null`), auth feature `UserProfileResponseSchema` expects `karma_distribution` as an array but the backend sends an object (`features/auth/schemas/auth.schema.ts:155`; the profile feature handles the object correctly). *Fix.* Mark these fields `.nullable()`, and fail tests on schema mismatches.

**L-50** · Charts render into zero-size containers (Recharts "width(-1) and height(-1)" warnings) on `/dashboard/campus/manage` and `/dashboard/url-shortener/[id]/analytics`. Give the chart wrappers a fixed min height.

**L-51** · Sidebar: "Interest Groups" and "Weekly Twitches" appear twice for admins (learner page and management page share the same label, `src/lib/nav-config.ts:133,181,363,411`); typo "Url Shortner" (`nav-config.ts`).

**L-52** · The dashboard requests `organisation/institutes/college/` and `…/school/` in lower case (`features/search/api/search.api.ts:80,84`, `events.api.ts:622`, `settings.api.ts:57`, `onboarding.api.ts:44`), while `org_type` values are `College`/`School`. It only works because MySQL's default collation is case-insensitive; a case-sensitive collation or another DB returns empty lists. Use the exact enum value.

**L-53** · `.github/workflows/pod1-roll.yml:71,76,91` run `docker-compose -f docker-compose.pod.yml restart backend` / `exec backend …`, but the service in `docker-compose.pod.yml` is called `mulearnbackend` → "No such service: backend"; the restart and "install requirements" options of the roll-out workflow never work.

**L-54** · `pod1-roll.yml:58-64` syncs code with `rsync -avz --delete` from the CI checkout into the server's project folder. Anything on the server that is not in git and not excluded (for example the bind-mounted `./logs` folder of `docker-compose.pod.yml:13`) is deleted on every sync.

**L-55** · `db/models.py` imports every model module "for the side effect of registering models" (its own docstring says to add new modules there) but misses `db/community_partner.py` and `db/intern.py`. Those models are only registered once something imports them (the URLconf does). Processes that do not load the URLconf (Celery worker, some management commands, schema tools) cannot resolve them early; the audit's schema build failed for exactly this reason (`no such table: community_partner`).

#### Low issues added in the performance pass

**L-56** · `GET /dashboard/profile/get-user-levels/` (muJourney) runs one or two task queries per level. For a user with no completed task it also reloads the karma log once per level: `UserLevelSerializer._get_completed_tasks` (`profile_serializer.py:334-343`) caches the list on the serializer, but `if getattr(self, "completed_tasks", None)` treats an empty list as "not cached" (measured: 41 → 95 queries for such a user). `GET /public/list/levels/` (`common_views.py:800-830`) also runs one task query per level. *Fix.* `if hasattr(self, "completed_tasks")`; one `TaskList` query for all levels, grouped in Python.

**L-57** · The notification bell asks for `GET /notification/unread-count/` every 60 s in every open tab (`src/features/notification/hooks/use-notification.ts:39,60-66`), and the feed also polls while it is open. At 5,000 open tabs that is about 83 requests per second of polling only. The backend already has Channels/WebSockets. *Fix.* Push the count over a WebSocket, or poll every 3–5 minutes and refresh when the tab gets focus.

**L-58** · Dropdowns ask for 1,000 rows at once: task types (`src/features/tasks/components/task-type/task-type-view.tsx:40`), departments (`src/features/organizations/components/departments/departments-view.tsx:40`), organizations in the verify dialog (`src/features/organizations/components/verify/verify-action-dialog.tsx:63`), interns (`src/features/intern/components/onboard-dialog.tsx:79`, `src/app/(dashboard)/dashboard/management/manage-interns/tasks/admin-tasks-client.tsx:150`). The backend endpoints are cheap per row, but the download and render cost grows with the data. *Fix.* Server-side search comboboxes.

**L-59** · Write endpoints that run a query or an insert for every item (static scan; Appendix I marks each with "query inside a loop"): IG update (`dash_ig_view.py:460-471, 718-793`, `get_or_create` per lead and role), intern bulk import (`manage_interns/interns_views.py:330-359`, two lookups and a create per row), achievement bulk issue (`achievement_views.py:1136`), launchpad bulk users (`launchpad_views.py:2845-2856`), LC meeting report and verify (`dash_lc_view.py:1042, 1475-1508`), role removal (`dash_roles_views.py:411-423`), mentor unassign (`mentor_views.py:1186-1199`), project images, links and skills (`projects_view.py:69, 115, 126, 224`), comic chapter pages (`chapter_views.py:779`), task skill links (`company/task_views.py:32-33`, `mentor/task_views.py:26-27`). *Fix.* Fetch all lookups in one query before the loop; use `bulk_create`/`bulk_update`.

**L-60** · Scheduled jobs update rows one at a time: `mu_celery/company_tasks.py:28`, `mentor_tasks.py:41,84`, `intern_cron.py:96-138,155`, `achievement_cron.py:64-142`, `achievement_tasks.py:107-119`, `api/management/commands/transition_mentorship_session_statuses.py:33`. This does not matter today because the jobs never run (H-35, M-59), but once beat runs they will be slow on large tables. *Fix.* `queryset.update(...)` or `bulk_update` in batches.

**L-61** · Search on list endpoints uses `icontains` on several columns joined with OR (`utils/utils.py:85-90`). `LIKE '%text%'` cannot use an index, so every search reads the whole table, and the page count reads it again. The main search pages wait 800 ms after typing before searching, but some tables do not (Appendix J). *Fix.* A MySQL FULLTEXT index, or prefix search (`istartswith`) on the main columns (user name, muid, email, org title).

**L-62** · Server settings that cost time on every request: no response compression in Django (no `GZipMiddleware`; JSON such as `ig/list` at 37 KB or `achievement/list` at 110 KB is sent uncompressed unless the proxy compresses it, and the proxy config is not in the repo); `CONN_MAX_AGE = 0` opens a new MySQL connection for every request; the `debug_toolbar` app and middleware are in the production settings, and `INTERNAL_IPS` includes the Docker gateway, so if `DEBUG` is ever on, every request is instrumented. `UniversalErrorHandlerMiddleware` also reads every request body into memory (H-08). *Fix.* gzip/brotli at the proxy (or `GZipMiddleware`); persistent connections with a pool; remove the debug toolbar from production settings.

**L-63** · The dashboard layout reads and parses `CHANGELOG.md` from disk on every request (`src/lib/whats-new.ts:72-84`, called from `src/app/(dashboard)/layout.tsx:31-34`), including every prefetch of every dashboard page (M-67). *Fix.* Read it once at build time or at module level, or wrap it in `unstable_cache`.

**L-64** · `public/favicon.ico` is 98 KB (a normal favicon is 1–15 KB), and every first visit downloads it. 16 `<img>` tags skip `next/image` (no resizing, no lazy loading): `src/components/ui/markdown-renderer.tsx`, `src/features/projects/components/project-wizard.tsx` and `project-detail-modal.tsx`, `src/features/manage-ig/components/impact-projects/*` and `edit-interest-group-form.tsx`, `src/features/courses/components/CourseCard.tsx`, `src/features/achievements/components/achievement-form-dialog.tsx`, `src/features/company-jobs/components/public-job-card.tsx` and `application-row.tsx`. *Fix.* Shrink the favicon; use `next/image` (or at least `loading="lazy"` with a width and height).

**L-65** · Some pages fetch the same API twice while loading: `/dashboard/mujourney` loads `profile/user-profile/` twice — once for the sidebar (`useUserProfile`) and once in `src/features/mujourney/hooks/useInterestGroups.ts:14`, which calls `getUserProfile()` under a different query key only to read the interest groups (so the heavy H-36 query runs twice); `/dashboard/manage-events` loads `events/meta/event-type-scope/` twice; `/dashboard/manage-events/[id]` loads `user/info` twice. *Fix.* Reuse the same query key (or `select` from the cached profile) so React Query shares one request.

**L-66** · The browser calls outside services at run time: the Courses page reads the Wadhwani course list from a Google Sheet through `opensheet.elk.sh`, a free public proxy (`src/api/endpoints.ts:958-959`, `src/features/courses/api/courses.api.ts:48`), and share-profile QR codes come from `quickchart.io` (`src/api/endpoints.ts:1002`). Each adds a connection to a third-party host with no service guarantee, and sends the user's IP address to it; if the service is slow or down, the feature breaks. *Fix.* Serve the sheet data from the backend with a cache, and draw QR codes in the browser (`react-qr-code` is already a dependency).

---

## 5. Complete API wiring audit

### 5.1 Method

The full chain for every endpoint is: **UI → API function → URL → Django route → auth → role → serializer → DB → response → UI**. Sections 5.2–5.3 are machine-checked. Section 5.4 is the result of reading each flow by hand.

### 5.2 Automated results

| Check | Result |
|---|---|
| Endpoint definitions in `endpoints.ts` | 568 |
| Definitions with no backend route | 16 (6 are external auth-service paths; 2 are third-party URLs) |
| API call sites parsed | 673 |
| Calls that hit a route with the right method | 603 |
| Calls with no backend route | 11 (after resolving template URLs; see 5.3) |
| Calls with the wrong HTTP method | 2 |
| Calls built from variables (checked by hand for key flows) | 57 |
| Backend route+method pairs with **no authentication at all** | 208 (≈70 of them change data; see Appendix A) |

### 5.3 Every endpoint mismatch found

| Dashboard call | Method | Backend result | Verdict |
|---|---|---|---|
| `auth.login` `/api/v1/auth/user-authentication/` | POST | Auth server ✅ (password + OTP). Django also has a proxy on the same path that drops `otp` | Works when the gateway sends `/api/v1/auth/*` to the auth server (M-27) |
| `auth.requestOTP` `/auth/request-otp/` | POST | Auth server ✅ | Needs the gateway rule; no rate limit, enumeration (H-19) |
| `auth.refreshToken` `/auth/get-access-token/` (client + server refresh) | POST | Auth server ✅ (Django has a `/auth/refresh-token/` proxy) | Needs the gateway rule; **breaks if `BACKEND_URL` points straight at Django** (M-27) |
| `auth.logout` `/auth/logout/` (route handler) | POST | Auth server ✅ (global logout by `iat`) | Same routing risk. The route handler swallows errors, so a failed logout is silent. The backend still accepts the old refresh token as a Bearer token (H-18) |
| `auth.signinWithGoogle`, `auth.googleCallback` | GET | Auth server ✅ | Redirect list has no staging domain; no `state` (M-25) |
| `register.validate` `/register/validate/` | PUT | No route | Dead code (L-04) |
| `notifications.list` `/notification/list/` | GET | Matches `DeleteOneView` (DELETE only) → 405 | Dead legacy hook (M-18) |
| `notifications.deleteOne` `/notification/delete/id/<id>/` | DELETE | Removed | Dead legacy hook (M-18) |
| `notifications.adminBroadcast` `/notification/admin/broadcast/` | POST | No route | **H-05** |
| `mentor.sessionParticipantList` (accept request) | POST | GET only → 405 | **H-06** |
| `admin.errorLog.dismiss` `/error-log/patch/<id>` | PATCH | Works only through the slash redirect | L-01 |
| `integrations.openGrad.*` | POST | No route (backend has `wadhwani/*`) | The OpenGrad section of the Courses page is commented out, so these are dead API functions. Add routes before turning it back on |
| `achievements.auditLogsAll` `/achievement/audit/` | – | No route (only `audit/<muid>/`) | Unused key |
| `integrations.wadhwani.sheet`, `utils.qrCode` | GET | External third-party URLs | OK by design |

### 5.4 Module wiring matrix (checked by hand)

Legend: ✅ correct · ⚠️ works with a gap · ❌ broken

| Module / flow | Route + method | Auth | Role / ownership | Payload / params | Response handling | Mutation → UI refresh | Verdict |
|---|---|---|---|---|---|---|---|
| Login / session (auth server) | ✅ on auth server | ❌ Apple token unverified | ❌ unapproved roles in JWT | ⚠️ OTP via Django proxy | ✅ envelope | ✅ | ❌ (C-08, C-09, H-18, H-19, M-27) |
| User info | ✅ `GET user/info/` | ✅ | ❌ returns unverified roles | ✅ | ✅ | ✅ | ❌ (C-09, M-16) |
| Profile picture | ✅ `POST user/profile/update/` | ❌ none | ❌ user from body | ❌ `user_id` | ✅ | ✅ | ❌ (C-03) |
| Role management | ✅ | ✅ | ✅ Admin | ✅ | ✅ both paginated and array shapes | ✅ | ⚠️ (M-01…M-04) |
| Role verification (new) | ✅ `GET/PATCH/DELETE user/verification/` | ✅ | ✅ Admin | ❌ `role`, `created_at` ignored | ⚠️ missing `created_at` | ✅ | ❌ (H-07) |
| Org requests verify | ✅ | ✅ | ❌ no Admin check | ❌ reject payload | ✅ | ✅ | ❌ (H-01, H-02) |
| Org transfer | ✅ | ❌ none | ❌ | ✅ | ✅ | ✅ | ❌ (C-01) |
| Org merge | ✅ | ✅ | ✅ Admin | ❌ GET param vs body | ❌ summary for wrong org | – | ❌ (H-03) |
| Departments / affiliation | ✅ | ✅ | ✅ Admin | ✅ | ✅ | ✅ | ✅ |
| Company register | ✅ | ✅ | ✅ | ❌ fake doc URL; logo/gallery dropped | ✅ | ✅ | ❌ (C-05) |
| Company verify (admin) | ✅ | ✅ | ✅ Admin | ✅ | ✅ | ✅ | ⚠️ (M-19) |
| Company jobs CRUD | ✅ | ✅ | ✅ owner/delegate/mentor | ⚠️ form doesn't enforce limits | ✅ | ✅ | ⚠️ (H-17) |
| Company job approval | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ no UI | ❌ (H-13) |
| Company applicants | ✅ | ✅ | ✅ | ❌ `status` ignored | ⚠️ client filter | ✅ | ⚠️ (M-07) |
| Company co-admin | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ page unreachable | ❌ (H-12) |
| Events manage / publish | ✅ | ✅ | ⚠️ role-name mismatch | ✅ | ✅ | ✅ | ❌ (C-07) |
| Event approvals | ✅ admin/mentor/campus/company | ✅ | ⚠️ self-approval | ✅ | ✅ | ✅ | ⚠️ (H-09, M-10) |
| Event lists | ✅ | ✅ | ✅ | ⚠️ multi-status not supported | ⚠️ client merge (200 cap) | – | ⚠️ (M-11) |
| IG CRUD | ✅ | ✅ | ⚠️ static IG Lead can edit or delete any IG | ✅ | ✅ | ✅ | ⚠️ (H-11) |
| IG requests | ✅ | ✅ | ✅ Admin/Company | ⚠️ `sort` vs `sortBy` | ⚠️ admin sees all IGs | ✅ | ⚠️ (M-08) |
| IG join / leave | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ 10-minute cache | ⚠️ (M-09) |
| Campus manage / execom | ✅ | ✅ | ✅ campus staff | ✅ (dashboard updated to new rules) | ✅ | ✅ | ⚠️ needs C-06 migration |
| Tasks + task approval | ✅ | ✅ | ✅ Admin | ✅ | ✅ | ✅ | ✅ |
| Karma voucher | ✅ | ✅ | ✅ Admin | ✅ | ✅ | ✅ | ✅ |
| Achievements admin | ✅ | ❌ signature only | ❌ none | ✅ | ✅ | ✅ | ❌ (C-02) |
| Learning circles | ✅ | ✅ | ✅ member/lead | ✅ | ✅ | ✅ | ⚠️ (H-10, M-20) |
| Mentor admin / verification | ✅ | ✅ | ✅ Admin | ✅ | ✅ | ✅ | ✅ |
| Mentor home requests | ❌ | ✅ | ❌ admin endpoint | ❌ | – | – | ❌ (H-06) |
| Notifications feed | ✅ | ✅ | ✅ | ✅ | ❌ no `source`/`redirect_url`, no broadcasts | ✅ | ❌ (H-04) |
| Notifications admin | ⚠️ legacy CRUD works; dispatch missing | ✅ | ✅ Admin | ✅ | ✅ | ⚠️ | ❌ (H-05) |
| Uploads (all) | ✅ | ✅ | ✅ | ❌ > 2.5 MB fails | ✅ | – | ❌ (H-08) |
| Zonal / District | ✅ | ✅ | ✅ | ✅ | ⚠️ `lead_number` gone | – | ⚠️ (M-24) |

### 5.5 Dynamic test of every endpoint (second pass)

Every one of the **1,123 unique route + method pairs** was called as each of the 19 test users (see "How this audit was done"). Results:

| Result | Count |
|---|---|
| Route + method pairs tested | 1,123 (1,140 rows including duplicate URL patterns) |
| Reachable with no login (anonymous got a normal answer) | 172, of which **44 change data** (see Appendix A) |
| Returned HTTP 500 for at least one role | 263 |
| — "wrong method on a shared URL" (`TypeError … unexpected keyword` / `missing … argument`) | 173 (L-11, Appendix H) |
| — anonymous caller hits `JWTUtils` with no header (`IndexError`) | 35 (L-10) |
| — other crashes (Appendix G; 5 of them are test-data artefacts and are marked as such) | 55 |
| Writes accepted with an **empty body** by a role that should not reach them | see C-02, C-10, H-21, L-37 |

How to read the per-endpoint table (Appendix E):
- **Login** — `Login` = anonymous gets 403; `**Public**` = anonymous reaches the view; `Login (anon→500)` = login is needed but anonymous crashes instead of getting 401 (L-10).
- **Roles that got through** — the test roles that were *not* rejected by a role check (writes were sent with an empty body, so "got through" means the role check passed and validation ran). `any logged-in` = no role restriction was seen.
- **Used by dashboard** — the dashboard file and line that calls it.
- **500 seen** — the exception and the roles that triggered it.
- **Issues** — IDs in this report.

### 5.6 Live schema contract check (second pass)

For each of the 198 dashboard GET calls whose Zod schema could be loaded, the live response was validated against that schema:

| Outcome | Count | Notes |
|---|---|---|
| Response matches the dashboard schema | 112 | |
| Schema mismatch | 17 | 13 real (H-30, H-32, M-58, L-49 and the `karma_distribution` shape), 4 caused by generated test ids that are not UUIDs (not reported) |
| API error for the chosen role/placeholder id | 44 | Mostly "not found" from placeholder ids; the real ones are H-26, H-27, H-33, M-46, L-12 |
| Schema could not be loaded by the checker | 25 | Calls without a schema argument (blob/CSV downloads) or re-exported schemas |

The dashboard hides these mismatches in production: `apiClient` logs them only in development and then returns the raw, unvalidated object. That is why three company pages crash with `x.map is not a function` instead of showing a clear error (H-30, H-32).

### 5.7 Literal paths swallowed by parameter routes (second pass)

A call can "resolve" and still hit the wrong view when a literal path segment matches a `<str:…>` pattern. All dashboard calls were checked for this:

| Dashboard call | Resolves to | Result |
|---|---|---|
| `GET /dashboard/company/user-status/` (`jobs.api.ts:688`) | `company/<str:company_id>/` (`CompanyDetailAPI`, Admin-only) | **Broken** — H-33 |
| `GET /dashboard/organisation/institutes/college/` and `/school/` (5 call sites) | `institutes/<str:org_type>/` | Works on MySQL only because of case-insensitive collation — L-52 |
| `GET /dashboard/organisation/institutes/Company/` (`manageUsers.api.ts:270`) | same | OK |

### 5.8 Per-endpoint table

The full table with all endpoints (1,140 rows) is in **Appendix E** (grouped by module).

---

## 6. Business-logic audit

**Users and roles**
- Role requests at sign-up are not limited, and the auth server puts unapproved roles into tokens, so any new account can become Admin (C-09).
- System roles can be edited or deleted (M-01).
- Bulk and single role removal behave differently (M-02).
- Roles are trusted from the JWT for up to 15 minutes after a change (M-14).
- `user/info` mixes pending and active roles (C-09).
- Company role is granted only on company verification. That is correct, but delegates never get a UI (H-12).

**Organizations**
- Verification is open to any user (H-01).
- Rejection is impossible (H-02).
- Merge cannot start (H-03) and moves data unsafely (M-06).
- There is an unauthenticated destructive transfer (C-01).
- A user can end up in two colleges (M-05).
- Company ↔ org linking is by title (M-19).

**Companies**
- The trust document is never stored (C-05).
- Mentor-created jobs have no approval UI (H-13).
- Applicant filtering is client-side (M-07).
- The job form accepts values the DB rejects (H-17).
- The approval rules themselves are sound: an owner cannot approve their own job, and there is a pending-job cap per mentor.

**Events**
- The publish policy is well structured (`publish_policy.py`).
- Approvers can self-approve campus events (H-09) and mentor events (M-10).
- Campus-IG events have no owning campus stored (M-10).
- Co-leads are unsupported (C-07).
- Status transitions run once a day (M-11).

**Interest groups**
- Hard delete loses karma history (H-11).
- The request → approval flow does not set up roles or leads (M-08).
- Member counts are wrong (M-09).
- Any static "IG Lead" can edit every IG. This is documented as intended, but it is broad for a production role.

**Learning circles**
- Karma can be farmed (H-10).
- Delete rights stay with the creator instead of the current lead (M-20).
- Lead transfer and member removal are now atomic, which is good.

**Karma / achievements**
- Admin endpoints are open (C-02).
- Wallet updates are not atomic (M-17).
- Karma history cascades on IG or task deletion (H-11).

**Notifications**
- Personal links and broadcasts are lost (H-04).
- Admin dispatch is missing (H-05).
- Notification writes happen after state changes without a transaction (M-12).
- Deep links are broken (M-13).

**Mentors**
- The admin flows line up well.
- Mentor home request handling is broken (H-06).
- Mentor removal in bulk skips cleanup (M-02).

**Added in the second pass**

**Users, roles and organizations**
- Any user can self-verify into any organization; campus roles follow the user's current college (H-23).
- Admin "Edit user" silently approves pending role requests and drops IG scope (M-33).
- Excel bulk role assignment skips the special-role rules (M-36).
- Email and phone can be changed without verification (M-31); self-delete is immediate and total (M-32).
- Password reset: no rules, unusable-password bug, no session revocation (M-34).

**Karma**
- Interns can award themselves unlimited karma (C-10).
- Event task karma can be raised after approval (H-25).
- Social links give free karma for any text (M-30).
- Task delete wipes karma history without adjusting wallets (M-39).
- muJourney shows the wrong karma progress (M-29).

**Interest groups**
- Per-IG leads can mint Mentors and change IG code/status (H-24); IG Leads can activate IGs that are only requests (M-37).

**Learning circles**
- Anyone can create a circle in any college and broadcast to its students (M-42).
- Leads can add members without consent (M-43); several leads per circle are possible (L-32).
- Invite links never open (H-27); public LC reports are down (H-28).

**Interns**
- The whole management API is open to interns (H-21); roles differ between the dashboard and the backend (M-38, M-54).

**Companies**
- Collaborations, event templates and feedback pages crash (H-30, H-31, H-32); the co-admin status endpoint does not exist (H-33); talent directory shows student emails (L-41); job view counter can be inflated (L-47).

**Payments**
- Donation verification can be replayed (H-29) and ignores its own validation (M-44).

---

## 7. Frontend audit (mulearn-dashboard @ dev)

**Strengths**
- One endpoint registry (`src/api/endpoints.ts`).
- Zod schemas for responses.
- One refresh-token flow with de-duplication (`refresh.client.ts`).
- Edge proxy + client guard + server `requireRole` + backend checks (four layers).
- A strict `ruri` sanitizer.
- React Query with sensible retries (no retry on 4xx).
- Typecheck is clean.

**Issues**
1. **Contract drift is hidden.** Schemas are lenient by default (`strictSchema` is off and mismatches are only logged in development). Many mismatches in this report (H-04, H-07, M-24) fail silently in production. Suggestion: send schema-mismatch events to monitoring in production, and turn on `strictSchema` for critical flows (auth, roles, payments).
2. **RBAC data source.** The UI uses DB roles from `user/info` (including pending ones), the proxy uses JWT roles, and the backend uses JWT roles. These three sources can disagree (C-09, M-14).
3. **Role-name constants are copied by hand from the backend** (C-07). Suggestion: generate them from an API or a shared JSON file.
4. **Client-side "fallbacks" hide backend gaps:**
   - event status merging (M-11)
   - applicant filters (M-07)
   - role filter (H-07)
   - Discord moderation search
   Each fallback makes counts and pagination wrong. Prefer fixing the backend.
5. **Fake success paths:** company document URL (C-05), logo/gallery dropped silently (C-05).
6. **Unreachable pages because of route gating:** company co-admin (H-12). Stale access entries (L-09).
7. **Error handling:**
   - `onboarding-guard` treats any error as "logged out" (M-16).
   - `redirectToLogin` loses the return path (L-05).
   - Upload errors show a generic message for 413/400 (H-08).
8. **Security:**
   - JS-readable refresh token (M-23).
   - HttpOnly mismatch between server and client cookie setters (M-23).
   - Links not scheme-checked (L-08; React 19 helps).
9. **Tests and CI:** 14 failing tests, 2 invalid test files, and CI does not run tests (H-17).
10. **Dead code:** 94 unused endpoint keys, legacy notification hooks, the unused `validateRegistrationData`, and job approval hooks with no UI (L-04, H-13).

### 7.1 Browser crawl of every page (second pass)

The production build was served locally against the backend with test data, and every page was opened in headless Chromium: all **129 pages** as Anonymous, Student and Admin, plus each role-specific page as its role (Company, Mentor, Campus Lead, Enabler, Lead Enabler, IG Lead, Campus IG Lead, Intern, Intern Lead, Zonal, District, Fellow, Associate, Tech Team, Discord Moderator, Comic Admin) — **781 page visits** in total.

| What the crawl saw | Pages | Issues |
|---|---|---|
| Page crashes on load (React error / `x.map is not a function`) | 4 — `/dashboard/company/collaborations`, `/company/event-templates`, `/company/feedback`, `/dashboard/search` (redirect) | H-30, H-31, H-32, L-48 |
| API returns 500 while the page loads | 3 — LC invite link, Discord moderation, Dynamic Type | H-27, H-26, M-46 |
| Page opens for a role but its APIs reply "You do not have the required role" (or "Verified company profile required") | 22 — 8 intern pages, 8 manage-interns pages, zonal, district, career labs, departments, talent pool, company admin | M-38, M-54, M-55, M-56, M-57, H-33 |
| Public page sends visitors to `/login` | 11 — every route in `public-routes.ts` | H-34 |
| Schema mismatch logged (development-mode visits) | 6 | H-30, H-32, L-49 |
| Charts rendered at size −1 | 2 | L-50 |
| Access control of the edge proxy | Protected pages sent Anonymous to `/login?ruri=…` and wrong roles to `/dashboard` as designed. No page leaked another role's data on screen. | — |

The full page-by-page result (component file, roles that could open it, roles redirected, number of API calls on load, every problem seen, issue IDs) is in **Appendix F**.

### 7.2 Frontend issues added in the second pass

- **Pages that crash:** H-30, H-31, H-32 (company), L-48 (search redirect).
- **Public pages unusable without login:** H-34.
- **Contract drift hidden by lenient schemas:** H-30, H-32, M-58, L-49 (see §5.6). Recommendation from the first report is now proven: turn on `strictSchema` in tests, and report schema mismatches from production to monitoring.
- **Role maps that differ from the backend:** M-38, M-54, M-55, M-56, M-57 (plus C-07 and H-12 from the first pass).
- **Missing backend endpoint shadowed by a parameter route:** H-33.
- **UI polish:** placeholder text "TODO" in intern task selects (L-45), duplicate sidebar labels and a typo (L-51), charts with no size (L-50), lowercase enum values in URLs (L-52), lint warnings from disabled features (L-46), dead API functions with wrong URLs (L-11).
- **Build:** `next build` passes (123 static pages); typecheck passes; unit tests still fail (H-17).

### 7.3 Frontend performance (third pass, measured)

- **JavaScript weight:** H-39 — charts and Markdown libraries on every page through a barrel import and the What's-new popup; median 713 KB compressed per page, 65% unused during load.
- **Loading sequence:** H-40 — the full-screen GIF loader (144 KB, downloaded twice) and the wait for `user/info` before the page's own requests.
- **Network behaviour:** M-67 (dozens of prefetches from the home page), M-68 (failed calls sent 4 times), M-69 (search boxes that send a request per key), L-57 (notification polling), L-58 (1,000-row dropdowns).
- **Assets and extra calls:** L-64 (98 KB favicon, `<img>` without lazy loading), L-65 (the same API loaded twice on some pages), L-66 (third-party services called from the browser).
- **Per page:** Appendix J lists every page with its JavaScript, unused code, API calls, sequential rounds, data-ready time, FCP/LCP, blocking time, CLS, DOM size, heap and prefetches.

---

## 8. Backend audit (mulearnbackend @ pranav-dev)

**Strengths**
- Consistent `CustomResponse` envelope.
- A page-size ceiling (`MAX_PAGE_SIZE=1000`).
- A stable-ordering fix in pagination.
- Good use of `select_for_update` in recent code (job approval, task approval, LC transfer).
- Denormalized aggregates with a cron (org and LC karma).
- A test-covered publish policy.
- Schema docs through drf-spectacular.

**Issues**
1. **Default-open permission model.** There is no `DEFAULT_PERMISSION_CLASSES`, so every view is public unless it opts in. 208 route/method pairs have no auth. Several mutate data (C-01, C-02, C-03, C-04, H-15, L-02). *Fix:* set `DEFAULT_PERMISSION_CLASSES = [CustomizePermission-like IsAuthenticated]` and mark public views explicitly with `AllowAny`.
2. **Role checks are mixed.** Decorators (`role_required`, `RoleRequired`, `dynamic_role_required`, `campus_staff_required`) and in-body checks are both used. Results differ (400 vs 403). Several business actions have no ownership checks (H-01, H-09).
3. **Transactions.** Many multi-step writes have no `transaction.atomic` (org verify, org transfer, company verify, add_karma, event approve + notify).
4. **Schema management.** `managed=False` everywhere plus hand-written scripts that are missing for most changes (C-06, H-16). `schema.sql` is out of date.
5. **Error handling.** `Model.objects.get()` is used without catching `DoesNotExist` in many admin views, which gives 500 instead of 404. View signatures that don't match their URL kwargs give 500 (L-03).
6. **Notifications.** Two systems live side by side (legacy `insert_notification` with `url`, and the new `dispatch` for LC only). The feed only reads the new fields (H-04).
7. **Logging.** Full request bodies are written to logs on errors (M-22). Root logger at DEBUG with no rotation. `print()` in middleware.
8. **Tests.** Test modules exist (events, LC, projects), but no CI runs them.

**Module-by-module results of the second pass** (every module under `api/` was read and every one of its endpoints was called as every role)

| Module | Endpoints | New issues |
|---|---|---|
| `auth` (proxies) | 4 | L-19 |
| `register` | 22 | H-22, M-52, L-15, L-16, L-17, L-18, L-20 |
| `dashboard/user` | 34 | H-23, M-33, M-34, M-35, L-10, L-12, L-21, L-22 |
| `dashboard/profile` | 32 | M-29, M-30, M-31, M-32, M-48, L-23…L-28 |
| `dashboard/roles` | 30 | M-36, L-29 |
| `dashboard/organisation`, `college`, `location`, `affiliation` | 102 | L-14, L-37, L-38, L-39 (plus C-01, H-01…H-03, M-05, M-06 from the first pass) |
| `dashboard/ig` | 36 | H-24, M-37, L-28, L-30, L-31 |
| `dashboard/learningcircle` | 61 | H-27, M-42, M-43, L-32, L-33, L-34 (plus H-10, M-20) |
| `dashboard/lc` (unmounted) + websocket | 0 HTTP + 1 websocket | M-40, L-44 |
| `common` (`/public/…`) + websocket | 30 + 1 websocket | H-28, M-41, M-51 |
| `dashboard/task`, `task_report` (unmounted) | 29 | M-39, L-44 |
| `dashboard/events` | 51 | H-25 (plus H-09, M-10, M-11) |
| `dashboard/company` | 80 | H-30…H-33, L-41, L-47 (plus C-05, H-12, H-13, M-07, M-19) |
| `dashboard/mentor` | 71 | H-26 (activity), (plus H-06) |
| `dashboard/campus` | 57 | M-47, L-12, L-42 (plus C-06, C-07) |
| `dashboard/intern`, `manage_interns` | 80 | C-10, H-21, M-38, M-54 |
| `dashboard/zonal`, `district` | 14 | M-55 (plus M-24) |
| `dashboard/career_lab` | 7 | M-56 |
| `dashboard/dynamic_management` | 34 | H-26 |
| `dashboard/discord_moderator` | 3 | H-26, M-46 |
| `dashboard/error_log` | 9 | L-13, L-43 |
| `dashboard/referral`, `coupon`, `projects` | 25 | M-45, L-36, L-40, L-12 |
| `donate` | 5 | H-29, M-44, L-35 |
| `hackathon` | 42 | M-53 |
| `launchpad` | 52 | M-50 (plus C-04) |
| `integrations` (kkem, wadhwani, qseverse) | 20 | L-12, M-51 (plus H-15) |
| `top100_coders`, `leaderboard` | 10 | M-49 |
| `protected` | 2 | L-39 |
| `notification` | 13 | (H-04, H-05, M-12, M-18 from the first pass) |
| `achievement` | 24 | L-10 (plus C-02) |
| `muComics`, `calendar`, `media_content`, `skill`, `channels`, `category`, `community_partner`, `home`, `feature`, `url_shortener`, `karma_voucher`, `enabler` | 160 | no new High/Critical; lows in Appendix E (for example L-49 for media content) |

**Cross-cutting backend issues found in this pass**
- `get_paginated_queryset` regression (H-26).
- 173 route + method pairs crash with `TypeError` because one view class serves URLs with and without a parameter (L-11, Appendix H).
- 35 views crash for anonymous callers instead of returning 401 (L-10).
- Missing-object handling (`.get()` without a 404) across modules (L-12).
- Outbound HTTP without timeouts (M-51).
- WebSockets without authentication or rate limits (M-40, M-41).
- Static analysis: undefined names in dead modules, unused variables that hide logic mistakes (L-44).

**Backend performance (third pass, measured)**
- Whole-table work on hot paths: H-36 (rank on every page load), H-37 (public leaderboards), M-63 (company talent pool), M-66 (campus pages).
- Queries per row (N+1): M-60 (interest groups), M-61 (25 paginated lists), M-62 (exports), L-56 (levels).
- Missing indexes and unknown schema: M-64. Unbounded lists: M-65.
- Work inside the request that belongs in a background job: H-38 (voucher import), M-70 (e-mails), L-59 (loops in bulk writes), L-60 (row-by-row scheduled jobs).
- Server settings: L-62 (no compression, a new DB connection per request, debug toolbar in production settings).
- Every endpoint's numbers are in Appendix I.

### 8b. Auth server audit (authserver @ dev)

**What it does.** A small Django service (about 1,800 lines) that shares the `user`, `role` and `user_role_link` tables and the `SECRET_KEY` with the backend. It issues HS256 JWTs: access tokens (15 minutes) and refresh tokens (7 days). It handles password login, OTP login, Google (web + mobile), Apple (web + mobile), refresh, global logout, and an internal token issue for Google sign-up.

**Strengths**
- Suspended users cannot log in or refresh (`ActiveUserManager`).
- Google web sign-in checks `redirect_uri` against a list.
- The Google sign-up temp token is short-lived, single-use (`jti` + `cache.add`) and checked with a protected key.
- Global logout by `iat` is a sensible, cheap design.

**Issues**
1. Unapproved roles in tokens (C-09).
2. Apple tokens not verified (C-08). Fixed only on the unmerged `feat/new-auth`.
3. Refresh and access tokens carry the same claims and key; the backend does not tell them apart (H-18).
4. Brute-force and OTP weaknesses, including the IEDC oracle (H-19).
5. Login depends on ipinfo.io (H-20).
6. Google OAuth gaps (M-25). Refresh/logout weaknesses (M-26). Routing and duplicate proxies (M-27). Config and hygiene (M-28).
7. `dev` was last changed on 2026-07-17. `feat/new-auth` (2026-09-24, 80 files, +6,677 lines) adds OIDC, tests and the Apple fix, but still has C-09 and the weak OTP. Review it and merge it with those fixes, instead of patching `dev` twice.

---

## 9. Security audit

| ID | Issue | Severity |
|---|---|---|
| C-01 | Unauthenticated org transfer + delete | Critical |
| C-02 | Achievement admin with no role check; expired tokens accepted | Critical |
| C-03 | Unauthenticated profile picture overwrite | Critical |
| C-04 | Launchpad identity taken from the request body | Critical |
| C-08 | Apple mobile sign-in accepts unsigned tokens (take over any account) | Critical |
| C-09 | Self-requested privileged roles become real roles in the JWT (self-service Admin) | Critical |
| C-10 | Any Intern can award unlimited karma to themselves (verified) | Critical |
| H-01 | Org request approval by any user | High |
| H-10 | Karma farming | High |
| H-15 | Unauthenticated VC issuance and connected-user email listing | High |
| H-18 | Refresh token accepted as an access token for 7 days; bypasses logout and role changes | High |
| H-19 | Weak brute-force protection; IEDC login is an unlimited password oracle; weak OTP; OTP email flooding | High |
| H-21 | Interns can use all intern-management APIs (own leave approval, deactivate the Intern Lead) | High |
| H-22 | Anonymous lookup of any user's email and phone by muID (verified) | High |
| H-23 | Self-verified membership in any organization; campus scope hijack (verified) | High |
| H-24 | Per-IG lead can mint verified Mentors and rewrite IG leads/code/status | High |
| H-25 | Event task karma editable after approval | High |
| H-29 | Replayable donation verification (duplicate paid records and tax receipts) | High |
| M-14 | JWT helpers skip the expiry check; role staleness; suspended users | Medium |
| M-15 | Public user search: IDs, admin enumeration, private users | Medium |
| M-22 | CORS `*`, debug toolbar, secrets in logs, Django serving media | Medium |
| M-23 | Refresh token readable by JavaScript | Medium |
| M-25 | Google OAuth: no `state`, no `aud` check, dev/vercel redirect URIs in prod | Medium |
| M-26 | Logout fails open when Redis is down; refresh tokens never rotated | Medium |
| M-31 | Login email/phone changeable without verification | Medium |
| M-32 | Immediate hard account deletion with no re-authentication | Medium |
| M-33 | Admin edit auto-approves pending role requests | Medium |
| M-34 | Password reset weaknesses (unusable password, no revocation, enumeration) | Medium |
| M-36 | Excel bulk role assign bypasses special-role checks | Medium |
| M-37 | IG Lead can activate unapproved IG requests | Medium |
| M-40 | LC chat WebSocket trusts the user id in the URL | Medium |
| M-41 | Public WebSocket runs full-table aggregates per connection (DoS) | Medium |
| M-42 | Broadcast spam to any campus by creating a circle there | Medium |
| M-45 | Referral e-mails usable for spam/phishing | Medium |
| M-50 | Launchpad and dashboard tokens interchangeable | Medium |
| L-02 | Unauthenticated terms approval | Low |
| L-08 | Unchecked link schemes | Low |
| L-17 | Account enumeration (email check, forgot password) | Low |
| L-23 | Private profile data exposed through rank/badges/permute | Low |
| L-36 | Coupon oracle | Low |
| L-39 | "Protected" endpoint without key check | Low |
| L-41 | Company talent directory shows student emails | Low |
| L-42 | Campus analytics for any college readable by any user | Low |
| L-43 | Error logs can be cleared by Fellow/Tech Team | Low |
| L-47 | Spoofable `X-Forwarded-For` used for rate limiting | Low |

Other notes:
- `OrganizationKarmaTypeGetPostPatchDeleteAPI` and `OrganizationKarmaLogGetPostPatchDeleteAPI` (`POST /organisation/karma-type/create/`, `/karma-log/create/`) only need a signed token and no role. Any user can add org karma logs. Add an Admin check.
- `CollegeChangeAPI` (PATCH `college/change-college/`) has no permission class. It relies on `fetch_user_id` (signature only, no expiry check).
- The OpenAPI schema at `/api/schema/` uses `IsAdminUser` only while `ENABLE_SWAGGER` is off. When it is on, the schema and docs are `AllowAny`. Make sure `ENABLE_SWAGGER` is off in production.

Other notes added in the second pass:
- The org karma endpoints above are tracked as L-37; `college/change-college/` and `user/organization/` as H-23.

---

## 10. Performance and scalability

### 10.1 How performance was measured (third pass)

- **Backend, every GET endpoint.** All 506 GET routes were called as every role that could use them, on two copies of the test database: *small* (the functional-test data: about 3 rows per table plus the scenario) and *large* (plus 40 complete student profiles in one college and interest group, 10 more colleges, 6 more interest groups, about 25 more rows in every table, and 30 karma logs and notifications for one student). For each call the harness recorded the SQL queries (count, repeated query shapes and the line of code that ran them), response size, rows, paging, outbound HTTP, e-mails and cache use. The cache was cleared before every call, so the numbers are for a cold cache, and the role with the most queries is reported. 358 routes gave a successful response and were measured; the others need data or ids the test database does not have ("not measured" in Appendix I). A query count that grows with the data means one query per row (N+1). Every query was also checked against the indexes in `schema.sql`.
- **Backend, write endpoints (629 route/method pairs).** These need real request bodies, so they were not load-tested. The code of every handler was scanned for queries inside loops, e-mails, outbound HTTP and file building inside the request.
- **Frontend, every page.** All 129 pages were opened once on the production build (`next build` + `next start`) with a cold cache, as the role each page is for, with Lighthouse-style mobile throttling: CPU 4× slower, 150 ms round trip, 1.6 Mbps down / 750 kbps up. Recorded: FCP, LCP, CLS, long tasks (→ Total Blocking Time), JavaScript downloaded and unused (V8 coverage), API calls during load (duplicates, sequential rounds, time until the data is ready), Next.js prefetches, DOM size, JS heap, and API calls repeated after the page settled. Pages with a search box were also tested by typing 6 letters.
- **Limits.** SQLite, not MySQL: query counts and shapes are exact, but backend timings are not production timings, so this section uses counts, sizes and index checks, not backend milliseconds. Browser timings come from a local server and a simulated network: use them to compare pages and to find the causes, not as field data.

### 10.2 Results at a glance

| Check | Result |
|---|---|
| GET endpoints measured | 358 of 506 |
| SQL queries per GET call (large data) | median 2, 90th percentile 17, maximum 847 (`dashboard/ig/csv/`) |
| Endpoints with the same query repeated ≥ 5 times in one call (N+1) | 50 |
| Endpoints whose query count grew by ≥ 10 on the large data | 32 |
| Endpoints with ≥ 50 queries on the large data | 15 |
| Lists that return every row (no paging) | 21 (M-65) |
| Endpoint rows that filter on a column with no index | 53 (M-64) |
| Tables with unknown indexes (not in `schema.sql`) | 68 of 140 (M-64, C-06/H-16) |
| Write handlers with a query/insert inside a loop | 23 route/method rows (L-59) |
| Handlers that send e-mail inside the request | 17 route/method rows (M-70) |
| Dashboard pages measured | 120 (+ 9 auth/public pages) |
| JavaScript per dashboard page (median) | 40 files, 713 KB compressed (2,435 KB unzipped); 65% not run during load (H-39) |
| FCP / LCP (median, mobile throttling) | 1.6 s / 7.7 s; 123 pages have LCP over 4 s (H-39, H-40) |
| Total Blocking Time (median) | 2,034 ms; 123 pages over 600 ms (H-39) |
| API calls during load (median) | 6 calls in 2 sequential rounds; data ready at 7.8 s |
| Pages whose own data waits for `user/info` | 101 (H-40) |
| Next.js prefetches on load (median) | 13 (home page: 46) (M-67) |
| Pages where a failing call was retried 3 more times | 5 (M-68) |

### 10.3 The 20 GET endpoints with the most SQL queries (large data)

| Endpoint | Queries (small → large data) | Most repeated query | Rows | Issue |
|---|---|---|---|---|
| `dashboard/ig/csv/` | 185 → 847 | 180× `user` | — | M-60, M-62 |
| `dashboard/roles/csv/` | 106 → 331 | 220× `user` | — | M-61, M-62 |
| `public/leaderboard/top-100/` | 301 → 301 | 100× `wallet` | 100 | H-37 |
| `dashboard/company/mulearners/shortlist/` | 5 → 149 | 72× `user_organization_link` | 24 | M-63 |
| `dashboard/ig/list/` | 11 → 129 | 51× `user` | 7 | M-60 |
| `dashboard/karma-voucher/export/` | 13 → 113 | 84× `user` | — | M-62 |
| `dashboard/profile/get-user-levels/` | 41 → 95 | 47× `karma_activity_log` | 47 | L-56 |
| `dashboard/ig/request/` | 49 → 83 | 18× `user` | 10 (paged) | M-60 |
| `dashboard/college/` | 23 → 72 | 10× `user_organization_link` | 10 (paged) | M-61, M-66 |
| `dashboard/ig/` | 37 → 69 | 18× `user` | 10 (paged) | M-60 |
| `dashboard/company/home-summary/` | 34 → 61 | 47× `user` | 47 | M-63 |
| `dashboard/company/talent-pool/analytics/` | 27 → 54 | 47× `user` | 47 | M-63 |
| `dashboard/profile/get-user-levels/<str:muid>/` | 43 → 51 | 26× `task_list` | 47 | L-56 |
| `dashboard/career-lab/hiring/csv/` | 1 → 51 | 50× `user` | — | M-62 |
| `public/career-lab/ongoing/` | 1 → 51 | 50× `user` | 28 | M-65 |
| `public/list/levels/` | 21 → 48 | 47× `task_list` | 47 | L-56 |
| `dashboard/company/jobs/` | 6 → 43 | 20× `user` | 10 (paged) | M-61 |
| `dashboard/company/applications/me/` | 1 → 33 | 10× `company_jobs` | 10 (paged) | M-61 |
| `dashboard/roles/` | 32 → 32 | 20× `user` | 10 (paged) | M-61 |
| `dashboard/affiliation/` | 11 → 32 | 20× `user` | 10 (paged) | M-61 |

### 10.4 The 10 slowest dashboard pages (largest contentful paint, mobile throttling)

| Page | LCP | TBT | JS (compressed) | API calls on load | Sequential API rounds | Data ready at |
|---|---|---|---|---|---|---|
| `/dashboard/mentor` | 9.0 s | 2464 ms | 832 KB | 9 | 2 | 9.0 s |
| `/dashboard/mentor/opportunities` | 8.9 s | 2219 ms | 832 KB | 9 | 2 | 8.7 s |
| `/dashboard/profile` | 8.9 s | 2359 ms | 780 KB | 12 | 3 | 9.3 s |
| `/dashboard` | 8.4 s | 2067 ms | 832 KB | 9 | 2 | 8.7 s |
| `/dashboard/management/manage-interest-groups` | 8.2 s | 2356 ms | 763 KB | 6 | 2 | 8.3 s |
| `/dashboard/management/manage-interns/tasks` | 8.1 s | 2490 ms | 722 KB | 8 | 2 | 8.3 s |
| `/dashboard/management/organizations/affiliation` | 8.1 s | 2297 ms | 717 KB | 5 | 2 | 8.0 s |
| `/dashboard/mentor/sessions` | 8.1 s | 2285 ms | 713 KB | 8 | 2 | 8.0 s |
| `/dashboard/campus/manage` | 8.1 s | 2933 ms | 751 KB | 15 | 3 | 9.0 s |
| `/dashboard/management/tasks/create` | 8.1 s | 3394 ms | 715 KB | 11 | 2 | 8.6 s |

### 10.5 The 10 dashboard pages with the most main-thread blocking

| Page | TBT | JS (compressed) | JS unused on load | DOM nodes |
|---|---|---|---|---|
| `/dashboard/management/tasks/create` | 3394 ms | 715 KB | 64% | 1114 |
| `/dashboard/management/manage-achievements/list` | 3072 ms | 696 KB | 65% | 5442 |
| `/dashboard/campus/manage` | 2933 ms | 751 KB | 60% | 1293 |
| `/dashboard/management/manage-achievements/logs` | 2526 ms | 699 KB | 65% | 3813 |
| `/dashboard/management/manage-interns/tasks` | 2490 ms | 722 KB | 65% | 1158 |
| `/dashboard/talent-pool` | 2473 ms | 742 KB | 66% | 1390 |
| `/dashboard/mentor` | 2464 ms | 832 KB | 68% | 851 |
| `/dashboard/company/jobs/[jobId]` | 2444 ms | 740 KB | 66% | 1203 |
| `/dashboard/management/organizations/verify` | 2427 ms | 788 KB | 67% | 836 |
| `/dashboard/management/session-verification` | 2378 ms | 706 KB | 64% | 870 |

Every endpoint is in Appendix I and every page in Appendix J. The performance issues are H-36…H-40 (§3), M-60…M-70 (§4) and L-56…L-66 (§4).

### 10.6 Earlier findings (first and second pass)

| Area | Problem | Suggestion |
|---|---|---|
| Roles list | `len(queryset)` per role; members sort JOIN (M-04, M-61) | `annotate(Count)` |
| Mentor list | Loads every pending application into Python to find change requests | Use `Exists()` / a subquery |
| Events | The dashboard fetches 3×200 events per "Pending" view and all published events for "Ongoing/Completed" (M-11) | Server `status__in`, time-based status |
| Uploads | The middleware reads every request body into memory (H-08) | Drop it; stream uploads |
| IG list | `cache_page(600)` with no invalidation (M-09) | Key-based cache with invalidation |
| Notifications | `count()` + offset pagination; fine now, but fan-out for broadcasts is needed (H-04) | Batch insert with `dedupe_key` (already designed) |
| Role verification | Client filter over server pages (H-07) | Server filter |
| Org dropdowns | `perPage=1000` loads (verify dialog, departments, interns, task types) | Server-side search combobox |
| DB connections | `CONN_MAX_AGE=0` under ASGI (documented choice) means a connection per request | Add a pooler (ProxySQL / pgbouncer-like) |
| Logging | DEBUG root logger to disk, no rotation | Rotate; INFO level |
| Public WebSocket | 6 full-table aggregates per anonymous connection; signal handlers run `COUNT(*)` inside requests (M-41) | Cache stats; move work to Celery |
| CSV exports | Whole tables serialized in one request (M-35) | Stream or generate in the background |
| Profile rank | Loads every wallet id above the user's karma into Python (L-24; the same pattern runs on every page load through the sidebar — H-36) | Window function or cached rank |
| Outbound calls | 19 of 25 `requests` calls have no timeout (M-51) | Shared session with timeouts |
| Dev server in production | `runserver` + no timeouts = slow partner calls block users (H-35) | daphne/gunicorn with workers and timeouts |
| Cached aggregates | Org/LC karma and rank columns are never refreshed because beat does not run (H-35, M-59) | Run beat; refresh once after deploy |
| Karma logs | `UserLogAPI` returns all logs unpaginated (L-24) | Paginate |

---

## 11. Regression risks (`dev` → `pranav-dev`, and recent dashboard `dev`)

| Change | Commit(s) | Risk |
|---|---|---|
| Role rename `CampusLead` → `CampusIGLead`, new `CampusIGCoLead` | `c83ccda`, `55dd963`, `dcc3e04` | Dashboard checks the old name (C-07); DB rows need a rename (C-06) |
| `campus_execom_role` restructure, `co_lead_id` column | `c83ccda` | Migration missing (C-06) |
| Notification model v2 + URL rewrite | `b87f3b0` | Legacy routes removed (M-18); feed contract (H-04); columns without a script (H-16) |
| Mentor model restructure (`MentorApplication`, `UserMentor.hours` → choices; deactivation fields removed) | `f21db2e`, `344a13d`, `e0a60e3` | Only covered by `alter-1.63/1.64`. Check data migration on prod. The admin deactivate/reactivate route param changed (`mentor_id` → user_mentor id) and the dashboard already uses `userMentorId` |
| Student detail serializers drop `user_id`, `lead_number` | `fa47e8a` | Dashboard zonal/district columns (M-24) |
| Public event list pagination + masked links | `483f536`, `debfc76` | Dashboard handles `data/pagination`; check the public event page for masked `registration_url` (it shows "—" for anonymous users) |
| Admin event list exclusion of past pending events | `c064a40` → reverted by `4cd2d21` | **Resolved**, no action |
| `UserRoleLinkManagement` now paginated | `9e13efd` | The dashboard handles both shapes (`extractUserArray`) ✅ |
| Denormalized org/LC aggregates + crons | `6505686`, `5dd14fa` | Columns need scripts (H-16); rankings lag up to 15 minutes |
| muComics create is admin-only, with `creator_muid` | `abb85c2` | Contract change for other clients (not used by the dashboard) |
| Dashboard job form refactor | `96ae3a7` | Lost backend limits; tests red (H-17) |
| Dashboard notification + broadcast work | `c4e2b89`…`4ac6876` | Built against endpoints and fields the backend does not provide (H-04, H-05) |
| Dashboard unified Role Verification | `26a537c`, `ecc91c8` | Depends on an unmerged backend change (H-07) |
| Auth server `feat/new-auth` (unmerged) | latest `b790491` | Large rewrite (OIDC, account API, internal API). It fixes C-08 and adds tests, but still has C-09 and weak OTP. Merging it changes URL layout (`muauth/urls/*`), so check every dashboard and backend auth call again before release |
| Pagination helper now requires a QuerySet | `f9f35ef` (2026-08-30) | Five list APIs return 500, including two admin pages (H-26) — **not on `dev`** |
| Task Templates modal redesign removed the `<Tabs>` root | dashboard `9246f1f` (2026-08-19) | Event Templates page crashes for every company (H-31) |
| Company list APIs paginated, dashboard still expects arrays | backend `c4a8536` / `a91791e` (2026-07/08), dashboard company schemas | Collaborations and Feedback pages crash (H-30, H-32) — also true on backend `dev` |
| `CircleInviteStatusAPI.get` never took `link_id` | present on `dev` and `pranav-dev` | Invite-link page never worked (H-27) |
| `LearningCircle.name` → `title` | before `dev` | Public LC APIs broken on both branches (H-28) |
| Intern module role lists (manage APIs open to `Intern`) | on both `dev` and `pranav-dev` (merged 2026-07-08, `abb34b1`) | C-10, H-21 — not new on `pranav-dev`, but live wherever the intern module is deployed |

---

## 12. Cross-repository integration issues

These are cases where each repo looks fine alone but the pair is broken.

1. **Dynamic role names** — C-07.
2. **Notification contract** — H-04 / H-05 / M-18.
3. **Org verification / merge contracts** — H-02 / H-03.
4. **Role verification filters** — H-07.
5. **Mentor session requests** — H-06.
6. **Upload size** — H-08 (dashboard 5–10 MB vs backend 2.5 MB effective).
7. **Company document upload** — C-05 (the dashboard has no endpoint to call).
8. **Company delegates** — H-12 (the backend supports them; the dashboard's gating blocks them).
9. **Auth routing depends on infra** — M-27.
   - The auth routes the dashboard calls (`request-otp`, `get-access-token`, `logout`, `signin-with-google`, `google/login/callback`, `user-authentication`) all exist on the **auth server**. Django serves none of them, except its own proxies for `user-authentication/`, `refresh-token/` and the mobile routes.
   - So login works only if a reverse proxy sends `/api/v1/auth/*` to the auth server. That rule also hides the Django proxies on the same paths.
   - The server-side refresh (`refresh.server.ts`) and logout (`app/api/auth/logout/route.ts`) use `BACKEND_URL`. `src/api/server.ts` recommends pointing that at an internal VPC endpoint. **If that endpoint is Django, every server refresh fails and users are logged out on page loads once their 15-minute token expires.** The logout route swallows the error.
   - `loginWithOTP` sends `otp`. The auth server supports it, but the Django proxy only forwards `password`.
   - *Fix:* Add an explicit auth base URL to the dashboard for all `/auth/*` calls, write down the gateway rule, and add a health check.
10. **Deep links from the backend** — M-13.
11. **Role data sources** — C-09 / M-14 (DB roles in the UI vs JWT roles in proxy and backend; the auth server includes unapproved roles).
12. **Disabled features** — M-21 (the backend has the endpoints; the dashboard turned them off).
13. **Removed fields** — M-24.
14. **Token types** — H-18 (the auth server marks tokens with `tokenType`, but the backend never checks it, so refresh tokens work as access tokens).
15. **Google redirect list** — M-25 (the dashboard builds the redirect URI from its own origin; the auth server's list has no staging domain).
16. **Apple sign-in through the backend** — C-08 (the backend's `apple-mobile/` proxy forwards unsigned tokens to the vulnerable auth-server route).
17. **Company list contracts** — H-30, H-32 (backend paginates, dashboard expects arrays; impact report shape differs).
18. **Missing `company/user-status/` endpoint shadowed by `<company_id>/`** — H-33.
19. **Role lists differ page by page** — M-38 (manage-interns), M-54 (intern pages), M-55 (zonal/district), M-56 (career labs), M-57 (talent pool). Suggestion: generate one role map (page → roles → API roles) from a shared JSON file and test it in both repos.
20. **Pagination keys** — M-58 (`totalCount/currentPage/previousPage` in the dashboard vs `count/totalPages/isNext/isPrev/nextPage` in the backend).
21. **Case of enum values in URLs** — L-52.
22. **Nullable fields** — L-49 (the dashboard marks fields as required strings that the backend sends as `null`).
23. **Public pages vs authenticated layout APIs** — H-34 (the proxy lets visitors in, the shared top bar calls a login-only API, and the client then forces a login).

---

## 13. Missing or incomplete functionality

| Feature | Where it is incomplete |
|---|---|
| Admin announcement dispatch | Backend endpoint missing (H-05) |
| Broadcast notifications to users | Backend feed does not include them (H-04) |
| Company verification document storage | No upload endpoint; dashboard fakes the URL (C-05) |
| Company logo / gallery at sign-up | Dropped by the dashboard (C-05) |
| Company co-admin accept / delegate dashboard | No reachable UI (H-12) |
| Mentor-created job approval | No UI (H-13) |
| Mentor home accept/decline | Wrong endpoints (H-06) |
| Org request rejection / merge | Backend contract (H-02, H-03) |
| Campus IG co-lead event rights | Neither repo (C-07, M-10) |
| IG cover/icon images, Impact Projects, weekly-twitch posters | Dashboard disabled (M-21) |
| OpenGrad courses | UI section commented out; its API functions call `integrations/OpenGrad/*`, which the backend does not have (5.3) |
| Registration pre-validation | `/register/validate/` missing (L-04) |
| Role verification server filters | Backend (H-07) |
| Event multi-status and real-time status | Backend (M-11) |
| LC invite link page | Backend `get` has no `link_id` (H-27) |
| Company collaborations / event templates / feedback | Pages crash (H-30, H-31, H-32) |
| Company co-admin status | Endpoint missing (H-33) |
| Public profile / muJourney / IG / events / search for visitors | Pages bounce to login (H-34) |
| Scheduled jobs (event/session status, expiry of jobs/grants/applications, intern crons, alumni, org/LC aggregates) | Never run in the provided deployment (H-35, M-59) |
| Change password in the dashboard | Endpoint exists, no screen (L-26) |
| Intern pages for Intern Lead / Admin | Backend rejects them (M-54) |
| Zonal/District dashboards for Admin | Backend rejects Admin; scope tied to college (M-55) |
| User preferences PATCH (profile) | Serializer missing (M-48) |
| Hackathon organisers | Always crashes (M-53) |
| Top-100 leaderboard | Always crashes (M-49) |
| Campus student list / member lists | Always crash (M-47) |

---

## 14. Recommended fixes and priorities

**P0 — before any deploy (1–2 days)**
1. **Auth server, today:** only verified roles in tokens (C-09). Turn off or fix Apple sign-in (C-08; the fix already exists on `feat/new-auth`). Remove the IEDC password oracle and fix the login limiter and OTP (H-19).
2. **Backend, today:** accept only `tokenType == "access"` (H-18). Allow only a short list of self-requested roles at sign-up, and return only verified, active roles from `user/info` (C-09). Remove unverified privileged role links that already exist. Rotate `SECRET_KEY` (this logs everyone out) if logs show abuse.
3. Lock down open endpoints: C-01, C-02, C-03, C-04, H-01, H-15, the org karma endpoints, L-02. Also set `DEFAULT_PERMISSION_CLASSES` so new views are closed by default.
4. Commit and dry-run the missing DB scripts (C-06, H-16). Block deploy on a schema check.
5. Update the dashboard role suffixes for `CampusIGLead` / `CampusIGCoLead` (C-07).
6. Remove the `request.body` read in the middleware or raise the limits (H-08).

**P1 — this sprint**
1. Company document upload (C-05) and re-verify affected companies.
2. Notification feed contract + broadcasts + admin dispatch (H-04, H-05, M-12, M-13).
3. Org verify reject + merge preview + merge safety (H-02, H-03, M-05, M-06).
4. Role verification filters (H-07).
5. Mentor home requests (H-06). Company delegates (H-12). Pending job approvals (H-13).
6. Event self-approval + campus checks (H-09, M-10).
7. Karma farming + atomic wallet updates (H-10, M-17).
8. IG delete → deactivate; protect karma history (H-11).
9. Restore job form rules. Add tests to CI in both repos (H-17).

**P2 — next sprint**
- Auth server: login must not depend on ipinfo.io (H-20); Google OAuth `state`, `aud` and redirect lists (M-25); refresh rotation and fail-closed logout (M-26); explicit auth base URL in the dashboard (M-27); auth server hygiene (M-28).
- Role safety (M-01…M-04).
- IG request lifecycle (M-08, M-09).
- Event list performance (M-11).
- Public search privacy (M-15).
- Guard / redirect loop (M-16).
- Legacy route aliases (M-18).
- Company org linking (M-19).
- LC delete rights (M-20).
- Re-enable disabled features (M-21).
- Config hardening (M-22).
- HttpOnly refresh token (M-23).
- Zonal/district column (M-24).

**P3 — clean-up**
- Low items L-01…L-09.
- Dead code.
- A shared "contract" package (role names, routes, enums) used by both repos.
- Production schema-mismatch telemetry in the dashboard.

**Second-pass additions to the plan**

**P0 — before any deploy**
- C-10 and H-21: remove `Intern` from every `manage_interns` role list today; cap `karma_awarded`; block self-verification; audit karma already awarded through `#intern-task-verified` and review bonuses.
- H-22: delete or lock `register/lc/user-validation/`.
- H-23: stop self-verified org links; suspend campus roles on college change.
- H-24: remove the global Mentor grant from the IG PATCH; make `code`/`status` admin-only.
- H-29: unique `payment_id` + idempotent verify.
- H-35, M-59: production app server (daphne/gunicorn), no code bind-mount, Celery beat service, every scheduled task registered; then run the aggregate crons once.

**P1 — this sprint**
- H-25, M-30, M-39, M-43, M-42 (karma and circle abuse).
- H-26 (pagination helper), H-27, H-28 (LC), H-30…H-33 (company pages), H-34 (public pages), M-29, M-58 (wrong numbers).
- M-33, M-34, M-36, M-37 (role and account safety).
- M-38, M-54…M-57: one role map for pages and APIs.
- M-40, M-41 (WebSockets), M-50 (token audience), M-51 (timeouts).

**P2 — next sprint**
- M-31, M-32, M-35, M-44…M-49, M-52, M-53.
- L-10 (401 instead of 500), L-11 (405 instead of 500), L-12 (404 instead of 500).

**P3 — clean-up**
- L-13…L-52, dead code (L-44), lint (L-46).
- Add contract tests: for each dashboard API function, validate a recorded backend response against its Zod schema in CI (the checker used for §5.6 can be reused).
- Add the browser crawl used for §7 to CI as a smoke test (open every page as each role and fail on page errors or 5xx).

**Performance additions to the plan (third pass)**

**P1 — this sprint (biggest load and speed wins)**
- H-36: stop calling `profile/user-profile/` from the sidebar; compute rank with one indexed count (or a stored rank); add `wallet(karma)` index.
- H-37: cache all leaderboards (or pre-compute them in a job) and prefetch in `BekenAPI`; rate-limit public endpoints.
- H-38: move voucher images and e-mails to Celery; load existing codes once.
- H-39: remove the profile barrel import from the sidebar and load the What's-new Markdown renderer and charts with `next/dynamic`; add a bundle-size budget to CI.
- H-40: render pages while `user/info` loads; replace the 144 KB GIF with a CSS/SVG spinner.
- M-68: stop retrying 500 responses.

**P2 — next sprint**
- M-60…M-63, M-66: `select_related`/`prefetch_related`/`annotate` on the listed endpoints, plus `assertNumQueries` tests for every list endpoint.
- M-64: add the listed indexes and write index-bearing migration scripts for the 68 tables missing from `schema.sql` (with C-06/H-16).
- M-65: paginate the 21 unbounded lists; M-67: turn off default prefetch on card links; M-69: debounce search and stop rewriting the URL on each key; M-70: e-mails through Celery with `EMAIL_TIMEOUT`.

**P3 — clean-up**
- L-56…L-66.
- Keep the performance harness (§10.1) in CI: fail a build when an endpoint's query count grows between the small and the large test data, or when a page's first-load JavaScript grows over the budget.

---

## 15. Final production-readiness assessment

**Verdict: NOT production-ready.**

| Area | Status |
|---|---|
| Authentication (auth server) | ❌ Any account can become Admin (C-09); any account can be taken over through Apple sign-in (C-08); weak brute-force protection (H-19); refresh tokens work as access tokens (H-18) |
| Security (backend) | ❌ Several unauthenticated or unauthorized write endpoints (C-01…C-04, H-01, H-15) |
| Data integrity | ❌ Missing migrations (C-06, H-16); destructive cascades (H-11); non-atomic karma (M-17) |
| Core business rules | ❌ Fake document verification (C-05); karma farming (H-10); self-approval (H-09) |
| Integration | ❌ At least 10 cross-repo breaks (§12) |
| Frontend quality | ⚠️ Typecheck and lint pass; unit tests fail; CI does not run tests |
| Backend quality | ⚠️ Good recent patterns, but default-open permissions and no CI tests |
| Observability | ⚠️ Schema drift is invisible in production; logs hold secrets |

**Release gate.** Ship only when all of these are true:
1. All Critical and High items are fixed or have an accepted, documented risk.
2. The DB migration set is committed and rehearsed on a copy of production.
3. The dashboard `vitest`, backend `pytest` and auth-server test suites run in CI and pass.
4. A security test shows that a new account with a requested privileged role gets **no** extra rights, that forged Apple tokens are rejected, and that a refresh token is rejected as a Bearer token.
5. A smoke test covers: login (password, OTP, Google) / refresh / logout through the real gateway, org verify/reject/merge, company sign-up with a real document, event create → approve → publish for each organiser type, role verification per tab, notification feed with links and broadcasts, and uploads at 4–5 MB.

**Second-pass update.** The verdict stays **NOT production-ready**, and the list of blockers is longer:

| Area | Status after the second pass |
|---|---|
| Authorization inside the backend | ❌ Low-privilege roles can reach high-privilege actions (C-10, H-21, H-23, H-24, M-36, M-37) |
| Privacy | ❌ Anonymous PII lookup (H-22); smaller leaks (L-17, L-23, L-41, L-42) |
| Karma integrity | ❌ At least six independent ways to inflate or lose karma (C-10, H-10, H-25, M-30, M-39, M-43) |
| Payments | ❌ Replayable verification (H-29, M-44) |
| Frontend | ❌ Three company pages crash on load; one LC page never works; all public pages bounce visitors to login; many role mismatches show error screens (H-27, H-30…H-34, M-38, M-54…M-57) |
| API robustness | ⚠️ 263 route + method pairs return 500 for some input (most are 404/405/401 cases, Appendix G/H) |
| Build | ✅ `next build` and typecheck pass; ❌ unit tests fail; no CI tests |
| Deployment | ❌ Development server in production; no Celery beat; 6 scheduled tasks unregistered; broken roll-out workflow (H-35, M-59, L-53, L-54) |

Add to the release gate: the browser crawl (§7) shows **no page errors and no 5xx** for any role on the pages that role can open, and the schema contract check (§5.6) shows **no mismatches**.

**Third-pass update (performance).** The measured performance adds these release blockers:

| Area | Status after the third pass |
|---|---|
| Backend load per page view | ❌ Every page load runs a whole-table rank query (H-36) and about 30 SQL queries for the app shell (H-40) |
| Public endpoints | ❌ Uncached heavy leaderboards, 301 queries for the top-100 list, no rate limit (H-37) |
| Query efficiency | ⚠️ 50 endpoints with N+1 queries; exports up to 847 queries (M-60…M-63) |
| Database indexes | ❌ Missing for events, karma-log dates, wallet karma, task hashtags; unknown for 68 tables (M-64) |
| Frontend speed (mid-range phone, slow 4G) | ❌ Median LCP 7.7 s, TBT 2,034 ms; 713 KB JavaScript per page, 65% unused (H-39, H-40) |

Add to the release gate: no list endpoint grows its query count with more data (§10.1 harness in CI), every public endpoint is cached or rate-limited, and on a mid-range phone profile (4× CPU, slow 4G) the home, profile, interest-group and learning-circle pages have LCP under 4 s and TBT under 600 ms.

---

## Appendix A — Backend routes that change data and have no authentication

These come from the automated scan and were confirmed by reading the code. Some are public on purpose (registration, password reset, donations, OAuth proxies). The ones marked ❗ should not be public.

| Route | Method | View | Note |
|---|---|---|---|
| `/dashboard/organisation/transfer/` | POST | `TransferAPI` | ❗ C-01 |
| `/dashboard/achievement/create/`, `update/<id>/`, `delete/<id>/` | POST/PUT/DELETE | Achievement* | ❗ C-02 (signature only, no role) |
| `/dashboard/achievement/manual-issue/`, `revoke/`, `bulk-issue/`, `issue-vc/` | POST | Achievement* | ❗ C-02 |
| `/dashboard/achievement/rules/create/`, `rules/<id>/activate/`, `deactivate/` | POST | Rule* | ❗ C-02 (`rules/<id>/` PATCH does have `RoleRequired`) |
| `/dashboard/achievement/claim/<id>/` | POST | `ClaimAchievementAPIView` | Signature only (no expiry check) |
| `/dashboard/user/profile/update/` | POST/PATCH | `UserProfilePictureView` | ❗ C-03 |
| `/dashboard/organisation/karma-type/create/`, `karma-log/create/` | POST | Org karma | ❗ no role |
| `/dashboard/profile/userterm-approved/<muid>/` | POST | `UsertermAPI` | ❗ L-02 |
| `/dashboard/college/change-college/` | PATCH | `CollegeChangeAPI` | Signature only |
| `/dashboard/user/organization/` | POST | `UserAddOrgAPI` | Signature only |
| `/dashboard/coupon/verify-coupon/` | POST | `CouponApi` | Check that this is intended |
| `/dashboard/company/jobs/<id>/view/` | POST | `TrackJobViewAPIView` | View counter can be inflated; add rate limits |
| `/integrations/qseverse/issue-vc/` | POST | Qseverse | ❗ H-15 |
| `/integrations/wadhwani/*` | POST | Wadhwani | Some use the JWT inside; check |
| `/integrations/kkem/*` | POST/PATCH | KKEM | Token-based decorator on some |
| `/launchpad/*` (user-college-link, bulk-user-college-link, user-profile, company-info, recruiter-info …) | POST/PUT | Launchpad | ❗ C-04 |
| `/register/*`, `/dashboard/user/forgot-password/`, `reset-password/*`, `/donate/*`, `/auth/*` proxies | POST | – | Public by design (add rate limits) |
| `/dashboard/profile/userterm-approved/<muid>/` | POST | `UsertermAPI` | ❗ L-02 |
| `/register/lc/user-validation/` | POST | `LearningCircleUserViewAPI` | ❗ H-22 (returns email + phone) |
| `/dashboard/organisation/karma-type/create/`, `karma-log/create/` | POST | Org karma | ❗ L-37 (500 after saving) |
| `/integrations/kkem/login/` | POST | `KKEMIntegrationLogin` | Proxies password login to the auth server; add rate limits |
| `/donate/verify/`, `/donate/subscription/verify/` | POST | Razorpay | ❗ H-29 replayable |

## Appendix B — Automated scan counts

- Backend URL patterns: 733 (728 unique). Unique route/method pairs: **1,123** (1140 rows including duplicate patterns).
- Reachable without login: 172 (of which 44 change data). Used by the dashboard: 542. With at least one issue ID: 428.
- Returned HTTP 500 for at least one role in the dynamic test: 263 route/method pairs (173 signature mismatches — Appendix H; 35 anonymous `IndexError` — L-10; the rest in Appendix G).
- Requests sent by the dynamic harness: 21,660 (19 roles × every route and method).
- Duplicate URL patterns: `dashboard/roles/`, `dashboard/roles/<roles_id>/`, `dashboard/user/<user_id>/` (×3), `dashboard/user/verification/<link_id>/`.
- Routes removed from `dev` → `pranav-dev`: `notification/list/`, `notification/delete/id/<id>/`, `mentor/admin/deactivate|reactivate/<mentor_id>/` (param renamed). Method change: `learningcircle/meeting/rsvp/<id>/` added DELETE.

## Appendix C — Unused dashboard endpoint keys (94)

`auth.refreshToken`, `auth.verifyToken`, `password.change`, `register.lcUserValidation`, `register.userCountry`, `register.userState`, `register.userZone`, `onboarding.areasOfInterest`, `onboarding.location`, `location.collegesInDistrict`, `location.schools`, `company.publicJobsBySlug`, `company.myJobs`, `company.jobsAll`, `company.jobsPending`, `company.jobApplications`, `company.myApplications`, `company.analyticsCampusTrend`, `company.homeSummary`, `company.mulearners`, `company.talentPoolAnalytics`, `mentor.activity`, `mentor.list`, `mentor.roster`, `mentor.changeRequests`, `mentor.adminRevoke`, `mentor.opportunities*` (9 keys), `user.delete`, `projects.create`, `projects.update`, `dashboard.events`, `events.featured`, `events.public.base`, `events.public.featured`, `events.mentor`, `campus.sessionsList`, `campusManage.publicCampusDetail`, `campusManage.studentLevelByOrg`, `campusManage.studentDetails`, `campusManage.studentDetailsCsv`, `campusManage.leaderboard`, `campusManage.weeklyKarmaByOrg`, `campusManage.karmaByCluster`, `campusManage.execomSearch`, `campusManage.events`, `leaderboard.students`, `leaderboard.studentsMonthly`, `leaderboard.college`, `leaderboard.collegeMonthly`, `calendar.dashboard`, `interestGroups.detail`, `interestGroups.requestList`, `college.list`, `achievements.auditLogs`, `achievements.auditLogsAll`, `achievements.bulkClaim`, `learningCircle.list`, `learningCircle.userCircles`, `learningCircle.meetingListPublic`, `learningCircle.meetingListUser`, `learningCircle.meetingReportExport`, `mujourney.taskList`, `search.students`, `search.mentors`, `admin.roleVerification.csv`, `admin.tasks.*` (12 keys), `admin.interestGroups.detail`, `manageUsers.csv`, `discordModeration.pendingCounts`, `manageRoles.userRoleSearch`, `careerLab.hiring.detail`, `zonal.studentList`, `zonal.collegeList`, `campusDashboard.recentActivity`, `organizations.detail`.

Some of these are used through variables (for example `admin.tasks.*` inside `useCsvDownload` paths). Check before deleting.

## Appendix D — Dashboard checks run on `dev`

| Check | Result |
|---|---|
| `bun run typecheck` | ✅ pass |
| `bun run lint` (Biome) | ✅ pass, 50 warnings (mostly unused imports) |
| `bunx vitest run` | ❌ 3 files failed / 36 passed; **14 tests failed** / 253 passed (all in `jobs.form.test.ts`); `events.policy.test.ts` is empty; `mujourney/utils/markdown.test.ts` is not a Vitest suite |
| `next build` (production, Turbopack) | ✅ pass (123 static pages generated) |
| Browser crawl (second pass) | 608+ page visits, see §7 and Appendix F |

## Appendix E — Every backend endpoint (1,123 unique route + method pairs; 1,140 rows)

Columns are explained in §5.5. `—` means nothing was seen. Issue IDs point to sections 2–4.
#### `api` (1 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/schema/` | SpectacularAPIView | Login | none observed | — | — | — |

#### `auth` (4 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/auth/user-authentication/` | UserAuthenticationProxyAPI | **Public** | any logged-in | features/auth/api/auth.api.ts:43, features/auth/api/auth.api.ts:58 | — | L-19 |
| POST | `/api/v1/auth/google-mobile/` | GoogleMobileAuthProxyAPI | **Public** | any logged-in | — | — | L-19 |
| POST | `/api/v1/auth/apple-mobile/` | AppleMobileAuthProxyAPI | **Public** | any logged-in | — | — | C-08, L-19 |
| POST | `/api/v1/auth/refresh-token/` | RefreshTokenProxyAPI | **Public** | any logged-in | — | — | L-19 |

#### `calendar` (7 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/calendar/ig-mentor/<str:ig_id>/sessions/` | IGMentorSessionCalendar | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/calendar/campus-mentor/<str:campus_id>/sessions/` | CampusMentorSessionCalendar | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/calendar/company/<str:company_org_id>/sessions/` | CompanySessionCalendar | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/calendar/events/` | EventCalendar | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/calendar/ig/<str:ig_id>/events/` | IGEventCalendar | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/calendar/campus/<str:campus_id>/events/` | CampusEventCalendar | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/calendar/company/<str:company_id>/events/` | CompanyEventCalendar | **Public** | any logged-in | — | — | — |

#### `dashboard/achievement` (24 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/achievement/list/` | AchievementListAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:349, features/achievements/api/achievements.api.ts:44 | IndexError: list index out of range (anon) | L-10 |
| GET | `/api/v1/dashboard/achievement/eligible/` | EligibleAchievementsAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:363 | IndexError: list index out of range (anon) | L-10 |
| POST | `/api/v1/dashboard/achievement/claim/<str:achievement_id>/` | ClaimAchievementAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:383 | IndexError: list index out of range (anon) | L-10 |
| GET | `/api/v1/dashboard/achievement/list/user/<str:muid>/` | UserAchievementsListAPIView | **Public** | any logged-in | features/achievements/api/achievements.api.ts:333, features/profile/api/profile.api.ts:456 | — | L-10 |
| GET | `/api/v1/dashboard/achievement/progress/` | UserProgressAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:373 | IndexError: list index out of range (anon) | L-10 |
| POST | `/api/v1/dashboard/achievement/create/` | AchievementCreateAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:55 | IndexError: list index out of range (anon) | C-02, L-10 |
| PUT | `/api/v1/dashboard/achievement/update/<str:achievement_id>/` | AchievementUpdateAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:68 | IndexError: list index out of range (anon) | C-02, L-10 |
| DELETE | `/api/v1/dashboard/achievement/delete/<str:achievement_id>/` | AchievementDeleteAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:77 | IndexError: list index out of range (anon) | C-02, L-10 |
| GET | `/api/v1/dashboard/achievement/rules/` | AchievementRuleListAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:100 | IndexError: list index out of range (anon) | L-10 |
| POST | `/api/v1/dashboard/achievement/rules/create/` | AchievementRuleCreateAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:110 | IndexError: list index out of range (anon) | C-02, L-10 |
| GET | `/api/v1/dashboard/achievement/rules/<str:rule_id>/` | AchievementRuleDetailAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:156 | IndexError: list index out of range (anon) | L-10 |
| PATCH | `/api/v1/dashboard/achievement/rules/<str:rule_id>/` | AchievementRuleDetailAPIView | Login (anon→500) | Admin | features/achievements/api/achievements.api.ts:126 | IndexError: list index out of range (anon) | L-10 |
| POST | `/api/v1/dashboard/achievement/rules/<str:rule_id>/deactivate/` | AchievementRuleDeactivateAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:134 | IndexError: list index out of range (anon) | C-02, L-10 |
| POST | `/api/v1/dashboard/achievement/rules/<str:rule_id>/activate/` | AchievementRuleActivateAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:142 | IndexError: list index out of range (anon) | C-02, L-10 |
| GET | `/api/v1/dashboard/achievement/simulate/<str:muid>/` | SimulateRulesAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:170 | IndexError: list index out of range (anon) | L-10 |
| GET | `/api/v1/dashboard/achievement/debug/<str:muid>/<str:achievement_id>/` | DebugAchievementAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:181 | IndexError: list index out of range (anon) | L-10 |
| POST | `/api/v1/dashboard/achievement/manual-issue/` | ManualIssueAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:193 | IndexError: list index out of range (anon) | C-02, L-10 |
| POST | `/api/v1/dashboard/achievement/revoke/` | RevokeAchievementAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:201 | IndexError: list index out of range (anon) | C-02, L-10 |
| GET | `/api/v1/dashboard/achievement/audit/<str:muid>/` | AuditLogAPIView | Login (anon→500) | any logged-in | — | IndexError: list index out of range (anon) | L-10 |
| POST | `/api/v1/dashboard/achievement/issue-vc/` | UserAchievementsIssueAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:228, features/profile/api/profile.api.ts:497 | IndexError: list index out of range (anon) | C-02, L-10 |
| POST | `/api/v1/dashboard/achievement/bulk-issue/` | AchievementIssueBulkAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:215 | IndexError: list index out of range (anon) | C-02, L-10 |
| GET | `/api/v1/dashboard/achievement/bulk-issue/template/` | AchievementBulkImportTemplateAPIView | **Public** | any logged-in | features/achievements/api/achievements.api.ts:236 | — | L-10 |
| GET | `/api/v1/dashboard/achievement/issued-log/` | AchievementLogListAPIView | Login (anon→500) | any logged-in | features/achievements/api/achievements.api.ts:275 | IndexError: list index out of range (anon) | L-10 |
| POST | `/api/v1/dashboard/achievement/bulk-claim/` | BulkClaimTaskAchievementAPIView | Login | none observed | — | — | L-10 |

#### `dashboard/affiliation` (8 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/affiliation/` | AffiliationCRUDAPI | Login | any logged-in | features/organizations/api/affiliation.api.ts:29 | — | — |
| POST | `/api/v1/dashboard/affiliation/` | AffiliationCRUDAPI | Login | Admin | features/organizations/api/affiliation.api.ts:41 | — | — |
| PUT | `/api/v1/dashboard/affiliation/` | AffiliationCRUDAPI | Login | none observed | — | TypeError: AffiliationCRUDAPI.put() missing 1 required positional argu (admin) | — |
| DELETE | `/api/v1/dashboard/affiliation/` | AffiliationCRUDAPI | Login | none observed | — | TypeError: AffiliationCRUDAPI.delete() missing 1 required positional a (admin) | — |
| GET | `/api/v1/dashboard/affiliation/<str:affiliation_id>/` | AffiliationCRUDAPI | Login | ? (500) | — | TypeError: AffiliationCRUDAPI.get() got an unexpected keyword argument (admin,associate,campusiglead,campuslead,) | — |
| POST | `/api/v1/dashboard/affiliation/<str:affiliation_id>/` | AffiliationCRUDAPI | Login | none observed | — | TypeError: AffiliationCRUDAPI.post() got an unexpected keyword argumen (admin) | — |
| PUT | `/api/v1/dashboard/affiliation/<str:affiliation_id>/` | AffiliationCRUDAPI | Login | Admin | features/organizations/api/affiliation.api.ts:54 | — | — |
| DELETE | `/api/v1/dashboard/affiliation/<str:affiliation_id>/` | AffiliationCRUDAPI | Login | Admin | features/organizations/api/affiliation.api.ts:64 | — | — |

#### `dashboard/calendar` (1 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/calendar/events/` | DashboardCalendarAPI | **Public** | any logged-in | — | — | — |

#### `dashboard/campus` (57 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/campus/home-summary/` | CampusDashboardSummaryAPIView | Login | any logged-in | features/home/api/home.api.ts:172 | — | — |
| GET | `/api/v1/dashboard/campus/member-funnel/` | CampusMemberFunnelAPIView | Login | any logged-in | features/home/api/home.api.ts:181 | — | — |
| GET | `/api/v1/dashboard/campus/circle-health/` | CampusCircleHealthAPIView | Login | any logged-in | features/home/api/home.api.ts:190 | — | — |
| GET | `/api/v1/dashboard/campus/recent-activity/` | CampusRecentActivityAPIView | Login | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/campus/campus-list/` | CampusListAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/campus/campus-details/` | CampusDetailsAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | features/campus-manage/api/campus-manage.api.ts:139 | — | — |
| GET | `/api/v1/dashboard/campus/student-level/` | CampusStudentInEachLevelAPI | Login | any logged-in | features/campus-manage/api/campus-manage.api.ts:495 | — | — |
| GET | `/api/v1/dashboard/campus/student-level/<str:org_id>/` | CampusStudentInEachLevelAPI | Login | any logged-in | — | — | L-42 |
| GET | `/api/v1/dashboard/campus/student-details/` | CampusStudentDetailsAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | — | — | — |
| GET | `/api/v1/dashboard/campus/student-details/csv/` | CampusStudentDetailsCSVAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | — | — | — |
| GET | `/api/v1/dashboard/campus/weekly-karma/` | WeeklyKarmaAPI | Login | any logged-in | features/campus-manage/api/campus-manage.api.ts:140 | — | — |
| GET | `/api/v1/dashboard/campus/weekly-karma/<str:org_id>/` | WeeklyKarmaAPI | Login | any logged-in | features/campus/api/campus.api.ts:18 | — | L-42 |
| PATCH | `/api/v1/dashboard/campus/change-student-type/<str:member_id>/` | ChangeStudentTypeAPI | Login | none observed | features/campus-manage/api/campus-manage.api.ts:687 | NotImplementedError: `create()` must be implemented. (campuslead,leadenabler) | L-12 |
| POST | `/api/v1/dashboard/campus/transfer-lead-role/` | TransferLeadRoleAPI | Login | Campus Lead, Lead Enabler | features/campus-manage/api/campus-manage.api.ts:608 | — | — |
| POST | `/api/v1/dashboard/campus/transfer-enabler-role/` | TransferEnablerRoleAPI | Login | Campus Lead, Lead Enabler | features/campus-manage/api/campus-manage.api.ts:614 | — | — |
| GET | `/api/v1/dashboard/campus/transfer-ig-role/` | TransferIGRoleAPI | Login | Campus Lead, Lead Enabler | features/campus-manage/api/campus-manage.api.ts:620 | — | — |
| POST | `/api/v1/dashboard/campus/transfer-ig-role/` | TransferIGRoleAPI | Login | Campus Lead, Lead Enabler | features/campus-manage/api/campus-manage.api.ts:677 | — | — |
| GET | `/api/v1/dashboard/campus/events/` | CampusEventsAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | — | — | — |
| GET | `/api/v1/dashboard/campus/events/distribution/` | CampusEventDistributionAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | features/campus-manage/api/campus-manage.api.ts:390 | — | — |
| GET | `/api/v1/dashboard/campus/execom/` | CampusExecomAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | features/campus-manage/api/campus-manage.api.ts:508 | — | C-06 |
| POST | `/api/v1/dashboard/campus/execom/` | CampusExecomAPI | Login | Campus Lead, Lead Enabler | features/campus-manage/api/campus-manage.api.ts:595 | — | C-06 |
| DELETE | `/api/v1/dashboard/campus/execom/` | CampusExecomAPI | Login | Campus Lead, Lead Enabler | — | — | C-06 |
| GET | `/api/v1/dashboard/campus/execom/roles/` | CampusExecomRoleAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | features/campus-manage/api/campus-manage.api.ts:553 | — | C-06 |
| POST | `/api/v1/dashboard/campus/execom/roles/` | CampusExecomRoleAPI | Login | Campus Lead, Lead Enabler | features/campus-manage/api/campus-manage.api.ts:577 | — | C-06 |
| GET | `/api/v1/dashboard/campus/execom/search/` | CampusUserSearchAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | — | — | C-06 |
| GET | `/api/v1/dashboard/campus/execom/<str:member_id>/` | CampusExecomAPI | Login | none observed | — | TypeError: CampusExecomAPI.get() got an unexpected keyword argument 'm (campuslead,enabler,leadenabler,mentor) | C-06 |
| POST | `/api/v1/dashboard/campus/execom/<str:member_id>/` | CampusExecomAPI | Login | none observed | — | TypeError: CampusExecomAPI.post() got an unexpected keyword argument ' (campuslead,leadenabler) | C-06 |
| DELETE | `/api/v1/dashboard/campus/execom/<str:member_id>/` | CampusExecomAPI | Login | Campus Lead, Lead Enabler | features/campus-manage/api/campus-manage.api.ts:602 | — | C-06 |
| GET | `/api/v1/dashboard/campus/ig-chapters/` | CampusIGChapterAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | features/notification/api/notification.api.ts:152 | — | — |
| POST | `/api/v1/dashboard/campus/ig-chapters/` | CampusIGChapterAPI | Login | Campus Lead, Lead Enabler | features/campus-manage/api/campus-manage.api.ts:735 | — | — |
| PATCH | `/api/v1/dashboard/campus/ig-chapters/` | CampusIGChapterAPI | Login | none observed | — | TypeError: CampusIGChapterAPI.patch() missing 1 required positional ar (campuslead,leadenabler) | — |
| DELETE | `/api/v1/dashboard/campus/ig-chapters/` | CampusIGChapterAPI | Login | none observed | — | TypeError: CampusIGChapterAPI.delete() missing 1 required positional a (campuslead,leadenabler) | — |
| GET | `/api/v1/dashboard/campus/ig-chapters/<str:chapter_id>/` | CampusIGChapterAPI | Login | none observed | — | TypeError: CampusIGChapterAPI.get() got an unexpected keyword argument (campuslead,enabler,leadenabler,mentor) | — |
| POST | `/api/v1/dashboard/campus/ig-chapters/<str:chapter_id>/` | CampusIGChapterAPI | Login | none observed | — | TypeError: CampusIGChapterAPI.post() got an unexpected keyword argumen (campuslead,leadenabler) | — |
| PATCH | `/api/v1/dashboard/campus/ig-chapters/<str:chapter_id>/` | CampusIGChapterAPI | Login | Campus Lead, Lead Enabler | features/campus-manage/api/campus-manage.api.ts:747 | — | — |
| DELETE | `/api/v1/dashboard/campus/ig-chapters/<str:chapter_id>/` | CampusIGChapterAPI | Login | Campus Lead, Lead Enabler | features/campus-manage/api/campus-manage.api.ts:754 | — | — |
| POST | `/api/v1/dashboard/campus/ig-chapters/<str:chapter_id>/join/` | CampusIGChapterJoinAPI | Login | Admin, Campus IG Lead, Campus Lead, Enabler, Lead Enabler, Mentor, Student | — | — | — |
| DELETE | `/api/v1/dashboard/campus/ig-chapters/<str:chapter_id>/leave/` | CampusIGChapterLeaveAPI | Login | Associate, Comic Admin, Company, Discord Mod, District Lead, Fellow, IG Lead, Intern, Intern Lead, Student, Tech Team, Zonal Lead | — | — | — |
| PUT | `/api/v1/dashboard/campus/social-links/` | CampusSocialLinkAPI | Login | Campus Lead, Lead Enabler | features/campus-manage/api/campus-manage.api.ts:758 | — | — |
| DELETE | `/api/v1/dashboard/campus/social-links/` | CampusSocialLinkAPI | Login | none observed | — | TypeError: CampusSocialLinkAPI.delete() missing 1 required positional  (campuslead,leadenabler) | — |
| PUT | `/api/v1/dashboard/campus/social-links/<str:link_id>/` | CampusSocialLinkAPI | Login | none observed | — | TypeError: CampusSocialLinkAPI.put() got an unexpected keyword argumen (campuslead,leadenabler) | — |
| DELETE | `/api/v1/dashboard/campus/social-links/<str:link_id>/` | CampusSocialLinkAPI | Login | Campus Lead, Lead Enabler | features/campus-manage/api/campus-manage.api.ts:762 | — | — |
| GET | `/api/v1/dashboard/campus/student-list/` | CampusStudentListAPI | Login | none observed | — | ValueError: The annotation 'full_name' conflicts with a field on the m (campuslead,enabler,leadenabler,mentor) | M-47 |
| GET | `/api/v1/dashboard/campus/students/<str:muid>/activity/` | CampusStudentActivityAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | — | — | — |
| GET | `/api/v1/dashboard/campus/igs/` | CampusIGsAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | — | — | — |
| GET | `/api/v1/dashboard/campus/igs/<str:ig_id>/members/` | CampusIGMembersAPI | Login | none observed | — | AttributeError: 'UserLvlLink' object has no attribute 'first' (campuslead,enabler,leadenabler,mentor) | M-47 |
| GET | `/api/v1/dashboard/campus/learning-circles/` | CampusLearningCirclesAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | — | — | — |
| GET | `/api/v1/dashboard/campus/learning-circles/<str:circle_id>/members/` | CampusLCMembersAPI | Login | none observed | — | AttributeError: 'UserLvlLink' object has no attribute 'first' (campuslead,enabler,leadenabler,mentor) | M-47 |
| GET | `/api/v1/dashboard/campus/analytics/karma-trend/` | CampusKarmaTrendAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | — | — | — |
| GET | `/api/v1/dashboard/campus/analytics/growth/` | CampusGrowthAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | — | — | — |
| GET | `/api/v1/dashboard/campus/showcase/` | CampusShowcaseAPI | Login | Campus Lead, Enabler, Lead Enabler, Mentor | — | — | — |
| PATCH | `/api/v1/dashboard/campus/showcase/` | CampusShowcaseAPI | Login | Campus Lead, Lead Enabler | — | — | — |
| POST | `/api/v1/dashboard/campus/assign-mentor/` | AssignCampusMentorAPI | Login | Campus Lead, Lead Enabler | features/campus/api/campus.api.ts:25 | — | — |
| GET | `/api/v1/dashboard/campus/sessions/list/` | CampusSessionListAPI | Login | Admin, Campus IG Lead, Campus Lead, Enabler, Lead Enabler, Mentor, Student | — | — | — |
| GET | `/api/v1/dashboard/campus/<str:org_id>/` | CampusDetailsPublicAPI | Login | any logged-in | features/campus/api/campus.api.ts:15 | — | L-42 |
| GET | `/api/v1/dashboard/campus/<str:org_id>/leaderboard/` | CampusStudentLeaderboardAPI | Login | any logged-in | — | — | L-42 |
| GET | `/api/v1/dashboard/campus/<str:org_id>/karma-by-cluster/` | CampusKarmaByClusterAPI | Login | any logged-in | — | — | L-42 |

#### `dashboard/career-lab` (7 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/career-lab/hiring/` | HiringAPI | Login | Admin, Associate | features/career-labs/api/career-labs.api.ts:36 | — | — |
| POST | `/api/v1/dashboard/career-lab/hiring/` | HiringAPI | Login | Admin, Associate | features/career-labs/api/career-labs.api.ts:44 | — | — |
| GET | `/api/v1/dashboard/career-lab/hiring/csv/` | HiringCSVAPI | Login | Admin, Associate | features/career-labs/api/career-labs.api.ts:72 | — | — |
| POST | `/api/v1/dashboard/career-lab/hiring/csv/` | HiringCSVAPI | Login | Admin, Associate | features/career-labs/api/career-labs.api.ts:91 | — | — |
| GET | `/api/v1/dashboard/career-lab/hiring/<str:hiring_id>/` | HiringDetailAPI | Login | Admin, Associate | — | — | — |
| PUT | `/api/v1/dashboard/career-lab/hiring/<str:hiring_id>/` | HiringDetailAPI | Login | Admin, Associate | features/career-labs/api/career-labs.api.ts:55 | — | — |
| DELETE | `/api/v1/dashboard/career-lab/hiring/<str:hiring_id>/` | HiringDetailAPI | Login | Admin, Associate | features/career-labs/api/career-labs.api.ts:63 | — | — |

#### `dashboard/category` (10 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/category/` | CategoryAPI | Login | any logged-in | — | — | — |
| POST | `/api/v1/dashboard/category/` | CategoryAPI | Login | Admin | — | — | — |
| PUT | `/api/v1/dashboard/category/` | CategoryAPI | Login | none observed | — | TypeError: CategoryAPI.put() missing 1 required positional argument: ' (admin) | — |
| PATCH | `/api/v1/dashboard/category/` | CategoryAPI | Login | none observed | — | TypeError: CategoryAPI.patch() missing 1 required positional argument: (admin) | — |
| DELETE | `/api/v1/dashboard/category/` | CategoryAPI | Login | none observed | — | TypeError: CategoryAPI.delete() missing 1 required positional argument (admin) | — |
| GET | `/api/v1/dashboard/category/<str:category_id>/` | CategoryAPI | Login | any logged-in | — | — | — |
| POST | `/api/v1/dashboard/category/<str:category_id>/` | CategoryAPI | Login | none observed | — | TypeError: CategoryAPI.post() got an unexpected keyword argument 'cate (admin) | — |
| PUT | `/api/v1/dashboard/category/<str:category_id>/` | CategoryAPI | Login | Admin | — | — | — |
| PATCH | `/api/v1/dashboard/category/<str:category_id>/` | CategoryAPI | Login | Admin | — | — | — |
| DELETE | `/api/v1/dashboard/category/<str:category_id>/` | CategoryAPI | Login | Admin | — | — | — |

#### `dashboard/channels` (8 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/channels/` | ChannelCRUDAPI | Login | any logged-in | features/channels/api/channels.api.ts:36 | — | — |
| POST | `/api/v1/dashboard/channels/` | ChannelCRUDAPI | Login | Admin | features/channels/api/channels.api.ts:59 | — | — |
| PUT | `/api/v1/dashboard/channels/` | ChannelCRUDAPI | Login | none observed | — | TypeError: ChannelCRUDAPI.put() missing 1 required positional argument (admin) | — |
| DELETE | `/api/v1/dashboard/channels/` | ChannelCRUDAPI | Login | none observed | — | TypeError: ChannelCRUDAPI.delete() missing 1 required positional argum (admin) | — |
| GET | `/api/v1/dashboard/channels/<str:channel_id>/` | ChannelCRUDAPI | Login | ? (500) | — | TypeError: ChannelCRUDAPI.get() got an unexpected keyword argument 'ch (admin,associate,campusiglead,campuslead,) | — |
| POST | `/api/v1/dashboard/channels/<str:channel_id>/` | ChannelCRUDAPI | Login | none observed | — | TypeError: ChannelCRUDAPI.post() got an unexpected keyword argument 'c (admin) | — |
| PUT | `/api/v1/dashboard/channels/<str:channel_id>/` | ChannelCRUDAPI | Login | Admin | features/channels/api/channels.api.ts:65 | — | — |
| DELETE | `/api/v1/dashboard/channels/<str:channel_id>/` | ChannelCRUDAPI | Login | Admin | features/channels/api/channels.api.ts:53 | — | — |

#### `dashboard/college` (3 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/college/` | CollegeApi | **Public** | any logged-in | features/college-levels/api/college.api.ts:26 | — | — |
| PATCH | `/api/v1/dashboard/college/change-college/` | CollegeChangeAPI | Login (anon→500) | any logged-in | features/profile/api/profile.api.ts:419 | IndexError: list index out of range (anon) | H-23, L-10 |
| GET | `/api/v1/dashboard/college/<str:college_code>/` | CollegeApi | **Public** | any logged-in | — | — | — |

#### `dashboard/community-partner` (5 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/community-partner/` | CommunityPartnerListCreateAPI | **Public** | any logged-in | — | — | — |
| POST | `/api/v1/dashboard/community-partner/` | CommunityPartnerListCreateAPI | Login | Admin, Associate, IG Lead | features/manage-ig/api/community-partner.api.ts:57 | — | — |
| GET | `/api/v1/dashboard/community-partner/<str:partner_id>/` | CommunityPartnerDetailAPI | **Public** | any logged-in | features/manage-ig/api/community-partner.api.ts:70 | — | — |
| PATCH | `/api/v1/dashboard/community-partner/<str:partner_id>/` | CommunityPartnerDetailAPI | Login | Admin, Associate, IG Lead | features/manage-ig/api/community-partner.api.ts:83 | — | — |
| DELETE | `/api/v1/dashboard/community-partner/<str:partner_id>/` | CommunityPartnerDetailAPI | Login | Admin, Associate, IG Lead | features/manage-ig/api/community-partner.api.ts:93 | — | — |

#### `dashboard/company` (80 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/dashboard/company/register/` | CompanyRegistrationAPI | Login | any logged-in | features/auth/api/register.api.ts:50 | — | C-05, M-19 |
| PATCH | `/api/v1/dashboard/company/register/` | CompanyRegistrationAPI | Login | any logged-in | features/auth/api/register.api.ts:71 | — | C-05, M-19 |
| GET | `/api/v1/dashboard/company/summary/` | CompanyAdminSummaryAPI | Login | Admin | features/company-jobs/api/jobs.api.ts:631 | — | — |
| GET | `/api/v1/dashboard/company/home-summary/` | CompanyDashboardSummaryAPIView | Login | Company, Mentor | — | — | — |
| GET | `/api/v1/dashboard/company/status/` | CompanyStatusAPI | Login | any logged-in | features/auth/api/auth.api.ts:152 | — | — |
| GET | `/api/v1/dashboard/company/profile/` | CompanyProfileAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:114 | — | — |
| PATCH | `/api/v1/dashboard/company/profile/` | CompanyProfileAPI | Login | Company | features/company-jobs/api/jobs.api.ts:136, features/company-profile/api/company-profile.api.ts:35 | — | — |
| GET | `/api/v1/dashboard/company/profile/public/<str:slug>/` | PublicCompanyProfileAPI | **Public** | any logged-in | features/company-jobs/api/jobs.api.ts:320 | — | — |
| GET | `/api/v1/dashboard/company/profile/public/<str:slug>/jobs/` | PublicCompanyJobListAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/company/list/` | CompanyListAPI | Login | Admin | features/manage-companies/api/manage-companies.api.ts:44 | — | — |
| GET | `/api/v1/dashboard/company/jobs/` | CompanyJobAPI | Login | Company, Mentor | — | — | — |
| POST | `/api/v1/dashboard/company/jobs/` | CompanyJobAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:204 | — | — |
| GET | `/api/v1/dashboard/company/jobs/pending/` | CompanyPendingJobListAPI | Login | Company | — | — | — |
| GET | `/api/v1/dashboard/company/jobs/all/` | PublicJobAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/company/jobs/<str:job_id>/` | CompanyJobDetailAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:183 | — | — |
| PATCH | `/api/v1/dashboard/company/jobs/<str:job_id>/` | CompanyJobDetailAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:216 | — | — |
| DELETE | `/api/v1/dashboard/company/jobs/<str:job_id>/` | CompanyJobDetailAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:225 | — | — |
| POST | `/api/v1/dashboard/company/jobs/<str:job_id>/approve/` | CompanyJobApproveAPI | Login | Company | features/company-jobs/api/jobs.api.ts:731 | — | H-13 |
| POST | `/api/v1/dashboard/company/jobs/<str:job_id>/reject/` | CompanyJobRejectAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:739 | — | — |
| POST | `/api/v1/dashboard/company/jobs/<str:job_id>/request-changes/` | CompanyJobRequestChangesAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:750 | — | — |
| POST | `/api/v1/dashboard/company/jobs/<str:job_id>/view/` | TrackJobViewAPIView | **Public** | any logged-in | features/company-jobs/api/jobs.api.ts:579 | — | L-47 |
| GET | `/api/v1/dashboard/company/jobs/<str:job_id>/analytics/` | CompanyJobEngagementAnalyticsAPIView | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:597 | — | — |
| GET | `/api/v1/dashboard/company/jobs/<str:job_id>/apply/` | JobApplicationAPI | Login | Company, Mentor | — | — | — |
| POST | `/api/v1/dashboard/company/jobs/<str:job_id>/apply/` | JobApplicationAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:412 | — | — |
| GET | `/api/v1/dashboard/company/jobs/<str:job_id>/applications/` | JobApplicationAPI | Login | Company, Mentor | — | — | M-07 |
| POST | `/api/v1/dashboard/company/jobs/<str:job_id>/applications/` | JobApplicationAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/company/applications/me/` | UserAppliedJobsAPI | Login | any logged-in | — | — | — |
| PATCH | `/api/v1/dashboard/company/applications/<str:app_id>/status/` | ApplicationStatusAPI | Login | none observed | features/company-jobs/api/jobs.api.ts:481 | — | — |
| DELETE | `/api/v1/dashboard/company/applications/<str:app_id>/withdraw/` | UserApplicationWithdrawAPI | Login | none observed | features/company-jobs/api/jobs.api.ts:420 | — | — |
| PATCH | `/api/v1/dashboard/company/applications/<str:app_id>/resubmit/` | UserApplicationResubmitAPI | Login | none observed | features/company-jobs/api/jobs.api.ts:431 | — | — |
| GET | `/api/v1/dashboard/company/mulearners/` | CompanyMulearnerDirectoryAPI | Login | Company, Mentor | — | — | L-41 |
| GET | `/api/v1/dashboard/company/mulearners/shortlist/` | CompanyTalentShortlistAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:798 | — | — |
| POST | `/api/v1/dashboard/company/mulearners/shortlist/` | CompanyTalentShortlistAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:811 | — | — |
| DELETE | `/api/v1/dashboard/company/mulearners/shortlist/` | CompanyTalentShortlistAPI | Login | ? (500) | — | TypeError: CompanyTalentShortlistAPI.delete() missing 1 required posit (admin,associate,campusiglead,campuslead,) | — |
| GET | `/api/v1/dashboard/company/mulearners/shortlist/<str:user_id>/` | CompanyTalentShortlistAPI | Login | ? (500) | — | TypeError: CompanyTalentShortlistAPI.get() got an unexpected keyword a (admin,associate,campusiglead,campuslead,) | — |
| POST | `/api/v1/dashboard/company/mulearners/shortlist/<str:user_id>/` | CompanyTalentShortlistAPI | Login | ? (500) | — | TypeError: CompanyTalentShortlistAPI.post() got an unexpected keyword  (admin,associate,campusiglead,campuslead,) | — |
| DELETE | `/api/v1/dashboard/company/mulearners/shortlist/<str:user_id>/` | CompanyTalentShortlistAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:821 | — | — |
| GET | `/api/v1/dashboard/company/analytics/gigs/` | CompanyGigAnalyticsAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:535 | — | — |
| GET | `/api/v1/dashboard/company/analytics/tasks/` | CompanyTaskAnalyticsAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:786 | — | — |
| GET | `/api/v1/dashboard/company/talent-pool/analytics/` | CompanyTalentPoolAnalyticsAPIView | Login | Company, Mentor | — | — | — |
| GET | `/api/v1/dashboard/company/analytics/campus/trend/` | CompanyCampusTrendAPIView | Login | Company, Mentor | — | — | — |
| GET | `/api/v1/dashboard/company/analytics/campus/` | CompanyCampusAnalyticsAPIView | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:760 | — | — |
| GET | `/api/v1/dashboard/company/talent-pool/insights/` | CompanyTalentPoolInsightsAPIView | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:848 | — | — |
| POST | `/api/v1/dashboard/company/feedback/` | CompanyFeedbackAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:872 | — | — |
| GET | `/api/v1/dashboard/company/feedback/list/` | CompanyFeedbackListAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:881 | — | — |
| GET | `/api/v1/dashboard/company/impact-report/` | CompanyImpactReportAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:889 | — | — |
| PATCH | `/api/v1/dashboard/company/impact-report/publish/` | CompanyImpactReportPublishAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:899 | — | — |
| GET | `/api/v1/dashboard/company/collaborations/` | CompanyCollaborationListCreateAPI | Login | Company | features/company-jobs/api/jobs.api.ts:910 | — | — |
| POST | `/api/v1/dashboard/company/collaborations/` | CompanyCollaborationListCreateAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:923 | — | — |
| GET | `/api/v1/dashboard/company/collaborations/discover/` | CompanyCollaborationDiscoverAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:934 | — | — |
| POST | `/api/v1/dashboard/company/collaborations/<str:collaboration_id>/respond/` | CompanyCollaborationRespondAPI | Login | none observed | features/company-jobs/api/jobs.api.ts:945 | — | — |
| DELETE | `/api/v1/dashboard/company/collaborations/<str:collaboration_id>/` | CompanyCollaborationWithdrawAPI | Login | none observed | features/company-jobs/api/jobs.api.ts:954 | — | — |
| POST | `/api/v1/dashboard/company/ig-sponsorship/<str:ig_id>/` | IgSponsorshipRequestAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:964 | — | — |
| PATCH | `/api/v1/dashboard/company/ig-sponsorship/<str:ig_id>/review/` | IgSponsorshipReviewAPI | Login | Admin | features/company-jobs/api/jobs.api.ts:975 | — | — |
| GET | `/api/v1/dashboard/company/ig-sponsorship/<str:ig_id>/metrics/` | IgSponsorshipMetricsAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:985 | — | — |
| GET | `/api/v1/dashboard/company/events/templates/` | CompanyEventTemplateListCreateAPI | Login | Company, Mentor | features/company-jobs/api/jobs.api.ts:995 | — | — |
| POST | `/api/v1/dashboard/company/events/templates/` | CompanyEventTemplateListCreateAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:1021 | — | — |
| DELETE | `/api/v1/dashboard/company/events/templates/<str:template_id>/` | CompanyEventTemplateDetailAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:1033 | — | — |
| POST | `/api/v1/dashboard/company/admin-link/` | CompanyAdminLinkCreateAPI | Login | Company | features/company-jobs/api/jobs.api.ts:643 | — | — |
| GET | `/api/v1/dashboard/company/admin-link/list/` | CompanyAdminLinkListAPI | Login | Company | features/company-jobs/api/jobs.api.ts:680 | — | — |
| POST | `/api/v1/dashboard/company/admin-link/<str:link_id>/respond/` | CompanyAdminLinkAcceptAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:655 | — | H-12 |
| DELETE | `/api/v1/dashboard/company/admin-link/<str:link_id>/leave/` | CompanyAdminLinkLeaveAPI | Login | any logged-in | features/company-jobs/api/jobs.api.ts:672 | — | — |
| DELETE | `/api/v1/dashboard/company/admin-link/<str:link_id>/` | CompanyAdminLinkRevokeAPI | Login | Company | features/company-jobs/api/jobs.api.ts:664 | — | — |
| POST | `/api/v1/dashboard/company/mentor/nominate/` | CompanyMentorNominateAPI | Login | any logged-in | features/company-jobs/api/company-mentor.api.ts:117 | — | — |
| POST | `/api/v1/dashboard/company/mentor/apply/` | CompanyMentorApplyAPI | Login | any logged-in | features/company-jobs/api/company-mentor.api.ts:138 | — | — |
| GET | `/api/v1/dashboard/company/mentor/list/` | CompanyMentorListAPI | Login | any logged-in | features/company-jobs/api/company-mentor.api.ts:156 | — | — |
| GET | `/api/v1/dashboard/company/tasks/` | CompanyTaskListCreateAPI | Login | Company, Mentor | — | — | — |
| POST | `/api/v1/dashboard/company/tasks/` | CompanyTaskListCreateAPI | Login | Company, Mentor | features/company-jobs/api/company-tasks.api.ts:68, features/company-tasks/api/tasks.api.ts:118 | — | — |
| GET | `/api/v1/dashboard/company/tasks/templates/` | CompanyTaskTemplateListCreateAPI | Login | Company, Mentor | features/company-tasks/api/tasks.api.ts:153 | — | — |
| POST | `/api/v1/dashboard/company/tasks/templates/` | CompanyTaskTemplateListCreateAPI | Login | any logged-in | features/company-tasks/api/tasks.api.ts:175 | — | — |
| DELETE | `/api/v1/dashboard/company/tasks/templates/<str:template_id>/` | CompanyTaskTemplateDetailAPI | Login | any logged-in | features/company-tasks/api/tasks.api.ts:187 | — | — |
| GET | `/api/v1/dashboard/company/tasks/<str:task_id>/` | CompanyTaskDetailAPI | Login | Company, Mentor | features/company-jobs/api/company-tasks.api.ts:80, features/company-tasks/api/tasks.api.ts:124 | — | — |
| PUT | `/api/v1/dashboard/company/tasks/<str:task_id>/` | CompanyTaskDetailAPI | Login | any logged-in | features/company-jobs/api/company-tasks.api.ts:95 | — | — |
| PATCH | `/api/v1/dashboard/company/tasks/<str:task_id>/` | CompanyTaskDetailAPI | Login | any logged-in | features/company-tasks/api/tasks.api.ts:141 | — | — |
| DELETE | `/api/v1/dashboard/company/tasks/<str:task_id>/` | CompanyTaskDetailAPI | Login | any logged-in | features/company-jobs/api/company-tasks.api.ts:106, features/company-tasks/api/tasks.api.ts:149 | — | — |
| POST | `/api/v1/dashboard/company/deactivate/` | CompanyDeactivateAPI | Login | Company | features/company-jobs/api/jobs.api.ts:696 | — | — |
| POST | `/api/v1/dashboard/company/<str:company_id>/deactivate/` | CompanyAdminDeactivateAPI | Login | Admin | features/manage-companies/api/manage-companies.api.ts:105 | — | — |
| POST | `/api/v1/dashboard/company/<str:company_id>/reactivate/` | CompanyReactivateAPI | Login | Admin | features/manage-companies/api/manage-companies.api.ts:117 | — | — |
| GET | `/api/v1/dashboard/company/<str:company_id>/` | CompanyDetailAPI | Login | Admin | features/company-jobs/api/jobs.api.ts:688, features/manage-companies/api/manage-companies.api.ts:82 | — | — |
| PATCH | `/api/v1/dashboard/company/verify/<str:company_id>/` | CompanyVerifyAPI | Login | Admin | features/manage-companies/api/manage-companies.api.ts:67 | — | — |

#### `dashboard/coupon` (1 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/dashboard/coupon/verify-coupon/` | CouponApi | **Public** | any logged-in | — | — | L-36 |

#### `dashboard/discord-moderator` (3 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/discord-moderator/tasklist/` | TaskList | Login | ? (500) | features/discord-moderation/api/discord-moderation.api.ts:54 | AttributeError: Got AttributeError when attempting to get a value for  (admin,associate,campusiglead,campuslead,) | M-46 |
| GET | `/api/v1/dashboard/discord-moderator/pendingcounts/` | PendingTasks | Login | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/discord-moderator/leaderboard/` | LeaderBoard | Login | ? (500) | features/discord-moderation/api/discord-moderation.api.ts:95 | AttributeError: 'list' object has no attribute '_fields' (admin,associate,campusiglead,campuslead,) | H-26 |

#### `dashboard/district` (7 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/district/district-details/` | DistrictDetailAPI | Login | District Lead | features/district/api/district.api.ts:21 | — | M-24 |
| GET | `/api/v1/dashboard/district/top-campus/` | DistrictTopThreeCampusAPI | Login | District Lead | features/district/api/district.api.ts:31 | — | M-24 |
| GET | `/api/v1/dashboard/district/student-level/` | DistrictStudentLevelStatusAPI | Login | District Lead | features/district/api/district.api.ts:41 | — | M-24 |
| GET | `/api/v1/dashboard/district/student-details/` | DistrictStudentDetailsAPI | Login | District Lead | features/district/api/district.api.ts:75 | — | M-24 |
| GET | `/api/v1/dashboard/district/student-details/csv/` | DistrictStudentDetailsCSVAPI | Login | District Lead | features/district/api/district.api.ts:84 | — | M-24 |
| GET | `/api/v1/dashboard/district/college-details/` | DistrictsCollageDetailsAPI | Login | District Lead | features/district/api/district.api.ts:116 | — | M-24 |
| GET | `/api/v1/dashboard/district/college-details/csv/` | DistrictsCollageDetailsCSVAPI | Login | District Lead | features/district/api/district.api.ts:125 | — | M-24 |

#### `dashboard/dynamic-management` (34 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/dynamic-management/dynamic-role/` | DynamicRoleAPI | Login | none observed | features/dynamic-type/api/dynamic-type.api.ts:96 | AttributeError: 'list' object has no attribute '_fields' (admin) | H-26 |
| POST | `/api/v1/dashboard/dynamic-management/dynamic-role/` | DynamicRoleAPI | Login | Admin | — | — | — |
| PATCH | `/api/v1/dashboard/dynamic-management/dynamic-role/` | DynamicRoleAPI | Login | none observed | — | TypeError: DynamicRoleAPI.patch() missing 1 required positional argume (admin) | — |
| DELETE | `/api/v1/dashboard/dynamic-management/dynamic-role/` | DynamicRoleAPI | Login | none observed | — | TypeError: DynamicRoleAPI.delete() missing 1 required positional argum (admin) | — |
| GET | `/api/v1/dashboard/dynamic-management/dynamic-role/create/` | DynamicRoleAPI | Login | none observed | — | AttributeError: 'list' object has no attribute '_fields' (admin) | — |
| POST | `/api/v1/dashboard/dynamic-management/dynamic-role/create/` | DynamicRoleAPI | Login | Admin | features/dynamic-type/api/dynamic-type.api.ts:105 | — | — |
| PATCH | `/api/v1/dashboard/dynamic-management/dynamic-role/create/` | DynamicRoleAPI | Login | none observed | — | TypeError: DynamicRoleAPI.patch() missing 1 required positional argume (admin) | — |
| DELETE | `/api/v1/dashboard/dynamic-management/dynamic-role/create/` | DynamicRoleAPI | Login | none observed | — | TypeError: DynamicRoleAPI.delete() missing 1 required positional argum (admin) | — |
| GET | `/api/v1/dashboard/dynamic-management/dynamic-role/delete/<str:type_id>/` | DynamicRoleAPI | Login | none observed | — | TypeError: DynamicRoleAPI.get() got an unexpected keyword argument 'ty (admin) | — |
| POST | `/api/v1/dashboard/dynamic-management/dynamic-role/delete/<str:type_id>/` | DynamicRoleAPI | Login | none observed | — | TypeError: DynamicRoleAPI.post() got an unexpected keyword argument 't (admin) | — |
| PATCH | `/api/v1/dashboard/dynamic-management/dynamic-role/delete/<str:type_id>/` | DynamicRoleAPI | Login | Admin | — | — | — |
| DELETE | `/api/v1/dashboard/dynamic-management/dynamic-role/delete/<str:type_id>/` | DynamicRoleAPI | Login | Admin | features/dynamic-type/api/dynamic-type.api.ts:126 | — | — |
| GET | `/api/v1/dashboard/dynamic-management/dynamic-role/update/<str:type_id>/` | DynamicRoleAPI | Login | none observed | — | TypeError: DynamicRoleAPI.get() got an unexpected keyword argument 'ty (admin) | — |
| POST | `/api/v1/dashboard/dynamic-management/dynamic-role/update/<str:type_id>/` | DynamicRoleAPI | Login | none observed | — | TypeError: DynamicRoleAPI.post() got an unexpected keyword argument 't (admin) | — |
| PATCH | `/api/v1/dashboard/dynamic-management/dynamic-role/update/<str:type_id>/` | DynamicRoleAPI | Login | Admin | features/dynamic-type/api/dynamic-type.api.ts:117 | — | — |
| DELETE | `/api/v1/dashboard/dynamic-management/dynamic-role/update/<str:type_id>/` | DynamicRoleAPI | Login | Admin | — | — | — |
| GET | `/api/v1/dashboard/dynamic-management/dynamic-user/` | DynamicUserAPI | Login | none observed | features/dynamic-type/api/dynamic-type.api.ts:138 | AttributeError: 'list' object has no attribute '_fields' (admin) | H-26 |
| POST | `/api/v1/dashboard/dynamic-management/dynamic-user/` | DynamicUserAPI | Login | Admin | — | — | — |
| PATCH | `/api/v1/dashboard/dynamic-management/dynamic-user/` | DynamicUserAPI | Login | none observed | — | TypeError: DynamicUserAPI.patch() missing 1 required positional argume (admin) | — |
| DELETE | `/api/v1/dashboard/dynamic-management/dynamic-user/` | DynamicUserAPI | Login | none observed | — | TypeError: DynamicUserAPI.delete() missing 1 required positional argum (admin) | — |
| GET | `/api/v1/dashboard/dynamic-management/dynamic-user/create/` | DynamicUserAPI | Login | none observed | — | AttributeError: 'list' object has no attribute '_fields' (admin) | — |
| POST | `/api/v1/dashboard/dynamic-management/dynamic-user/create/` | DynamicUserAPI | Login | Admin | features/dynamic-type/api/dynamic-type.api.ts:147 | — | — |
| PATCH | `/api/v1/dashboard/dynamic-management/dynamic-user/create/` | DynamicUserAPI | Login | none observed | — | TypeError: DynamicUserAPI.patch() missing 1 required positional argume (admin) | — |
| DELETE | `/api/v1/dashboard/dynamic-management/dynamic-user/create/` | DynamicUserAPI | Login | none observed | — | TypeError: DynamicUserAPI.delete() missing 1 required positional argum (admin) | — |
| GET | `/api/v1/dashboard/dynamic-management/dynamic-user/delete/<str:type_id>/` | DynamicUserAPI | Login | none observed | — | TypeError: DynamicUserAPI.get() got an unexpected keyword argument 'ty (admin) | — |
| POST | `/api/v1/dashboard/dynamic-management/dynamic-user/delete/<str:type_id>/` | DynamicUserAPI | Login | none observed | — | TypeError: DynamicUserAPI.post() got an unexpected keyword argument 't (admin) | — |
| PATCH | `/api/v1/dashboard/dynamic-management/dynamic-user/delete/<str:type_id>/` | DynamicUserAPI | Login | Admin | — | — | — |
| DELETE | `/api/v1/dashboard/dynamic-management/dynamic-user/delete/<str:type_id>/` | DynamicUserAPI | Login | Admin | features/dynamic-type/api/dynamic-type.api.ts:168 | — | — |
| GET | `/api/v1/dashboard/dynamic-management/dynamic-user/update/<str:type_id>/` | DynamicUserAPI | Login | none observed | — | TypeError: DynamicUserAPI.get() got an unexpected keyword argument 'ty (admin) | — |
| POST | `/api/v1/dashboard/dynamic-management/dynamic-user/update/<str:type_id>/` | DynamicUserAPI | Login | none observed | — | TypeError: DynamicUserAPI.post() got an unexpected keyword argument 't (admin) | — |
| PATCH | `/api/v1/dashboard/dynamic-management/dynamic-user/update/<str:type_id>/` | DynamicUserAPI | Login | Admin | features/dynamic-type/api/dynamic-type.api.ts:159 | — | — |
| DELETE | `/api/v1/dashboard/dynamic-management/dynamic-user/update/<str:type_id>/` | DynamicUserAPI | Login | Admin | — | — | — |
| GET | `/api/v1/dashboard/dynamic-management/types/` | DynamicTypeDropDownAPI | Login | any logged-in | features/dynamic-type/api/dynamic-type.api.ts:86 | — | — |
| GET | `/api/v1/dashboard/dynamic-management/roles/` | RoleDropDownAPI | Login | any logged-in | features/dynamic-type/api/dynamic-type.api.ts:80 | — | — |

#### `dashboard/enabler` (8 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/enabler/home-summary/` | EnablerHomeSummaryAPI | Login | Enabler, Lead Enabler | — | — | — |
| GET | `/api/v1/dashboard/enabler/campuses/` | EnablerCampusListAPI | Login | Enabler, Lead Enabler | — | — | — |
| GET | `/api/v1/dashboard/enabler/campuses/<str:campus_id>/review/` | EnablerCampusReviewAPI | Login | Enabler, Lead Enabler | — | — | — |
| GET | `/api/v1/dashboard/enabler/campuses/<str:campus_id>/notes/` | EnablerCampusNoteAPI | Login | Enabler, Lead Enabler | — | — | — |
| POST | `/api/v1/dashboard/enabler/campuses/<str:campus_id>/notes/` | EnablerCampusNoteAPI | Login | Enabler, Lead Enabler | — | — | — |
| PATCH | `/api/v1/dashboard/enabler/campuses/<str:campus_id>/notes/` | EnablerCampusNoteAPI | Login | Enabler, Lead Enabler | — | — | — |
| DELETE | `/api/v1/dashboard/enabler/campuses/<str:campus_id>/notes/` | EnablerCampusNoteAPI | Login | Enabler, Lead Enabler | — | — | — |
| GET | `/api/v1/dashboard/enabler/reports/` | EnablerReportsAPI | Login | Enabler, Lead Enabler | — | — | — |

#### `dashboard/error-log` (9 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/error-log/` | LoggerAPI | Login | Admin, Fellow, Tech Team | features/error-log/api/error-log.api.ts:75 | — | — |
| PATCH | `/api/v1/dashboard/error-log/` | LoggerAPI | Login | none observed | — | TypeError: LoggerAPI.patch() missing 1 required positional argument: ' (admin,fellow,techteam) | — |
| GET | `/api/v1/dashboard/error-log/graph/` | ErrorGraphAPI | Login | Admin | — | IndexError: list index out of range (fellow,techteam) | L-13 |
| GET | `/api/v1/dashboard/error-log/tab/` | ErrorTabAPI | Login | Admin, Fellow, Tech Team | — | — | — |
| GET | `/api/v1/dashboard/error-log/patch/<str:error_id>/` | LoggerAPI | Login | none observed | — | TypeError: LoggerAPI.get() got an unexpected keyword argument 'error_i (admin,fellow,techteam) | L-01 |
| PATCH | `/api/v1/dashboard/error-log/patch/<str:error_id>/` | LoggerAPI | Login | Admin, Fellow, Tech Team | — | — | L-01 |
| GET | `/api/v1/dashboard/error-log/<str:log_name>/` | DownloadErrorLogAPI | Login | Admin, Fellow, Tech Team | features/error-log/api/error-log.api.ts:89 | — | L-43 |
| GET | `/api/v1/dashboard/error-log/view/<str:log_name>/` | ViewErrorLogAPI | Login | Admin, Fellow, Tech Team | — | — | L-43 |
| POST | `/api/v1/dashboard/error-log/clear/<str:log_name>/` | ClearErrorLogAPI | Login | Admin, Fellow, Tech Team | features/error-log/api/error-log.api.ts:101 | — | L-43 |

#### `dashboard/events` (51 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/events/meta/categories/` | EventCategoriesAPI | **Public** | any logged-in | features/events/api/events.api.ts:743 | — | — |
| GET | `/api/v1/dashboard/events/meta/organizer-options/` | OrganizerOptionsAPI | Login | any logged-in | features/events/api/events.api.ts:735 | — | — |
| GET | `/api/v1/dashboard/events/meta/collaboration-targets/` | CollaborationTargetsAPI | Login | any logged-in | features/events/api/events.api.ts:606 | — | — |
| GET | `/api/v1/dashboard/events/meta/event-type-scope/` | EventTypesScopesAPI | **Public** | any logged-in | features/events/api/events.api.ts:751 | — | — |
| GET | `/api/v1/dashboard/events/meta/linkable-events/` | LinkableEventsAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/events/ig/cluster/<str:cluster>/` | ClusterEventListAPI | Login | any logged-in | features/events/api/events.api.ts:652 | — | — |
| GET | `/api/v1/dashboard/events/ig/<str:ig_id>/` | IGEventListAPI | Login | any logged-in | features/events/api/events.api.ts:644 | — | — |
| GET | `/api/v1/dashboard/events/campus/<str:campus_id>/` | CampusEventListAPI | Login | any logged-in | features/events/api/events.api.ts:662 | — | — |
| GET | `/api/v1/dashboard/events/campus-ig/<str:campus_ig_id>/` | CampusIGEventListAPI | Login | any logged-in | features/events/api/events.api.ts:672 | — | — |
| GET | `/api/v1/dashboard/events/company/<str:company_id>/` | CompanyEventListAPI | Login | any logged-in | features/events/api/events.api.ts:682 | — | — |
| GET | `/api/v1/dashboard/events/admin/` | AdminEventListAPI | Login | Admin | features/notification/api/notification.api.ts:167 | — | — |
| POST | `/api/v1/dashboard/events/admin/<str:event_id>/approve/` | AdminEventApproveAPI | Login | Admin | — | — | — |
| POST | `/api/v1/dashboard/events/admin/<str:event_id>/reject/` | AdminEventRejectAPI | Login | Admin | — | — | — |
| PATCH | `/api/v1/dashboard/events/admin/<str:event_id>/feature/` | AdminEventFeatureAPI | Login | Admin | features/events/api/events.api.ts:725 | — | — |
| POST | `/api/v1/dashboard/events/mentor/<str:event_id>/approve/` | MentorEventApproveAPI | Login | Mentor | — | — | — |
| POST | `/api/v1/dashboard/events/mentor/<str:event_id>/reject/` | MentorEventRejectAPI | Login | Mentor | — | — | — |
| POST | `/api/v1/dashboard/events/campus/<str:event_id>/approve/` | CampusEventApproveAPI | Login | Admin, Campus Lead, Enabler, Lead Enabler | — | — | H-09 |
| POST | `/api/v1/dashboard/events/campus/<str:event_id>/reject/` | CampusEventRejectAPI | Login | Admin, Campus Lead, Enabler, Lead Enabler | — | — | — |
| POST | `/api/v1/dashboard/events/company/<str:event_id>/approve/` | CompanyEventApproveAPI | Login | any logged-in | — | — | — |
| POST | `/api/v1/dashboard/events/company/<str:event_id>/reject/` | CompanyEventRejectAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/events/manage/` | ManageEventListCreateAPI | Login | any logged-in | — | — | M-10 |
| POST | `/api/v1/dashboard/events/manage/` | ManageEventListCreateAPI | Login | Admin, Campus IG Lead, Campus Lead, Company, District Lead, Enabler, IG Lead, Lead Enabler, Zonal Lead | features/events/api/events.api.ts:459 | — | M-10 |
| POST | `/api/v1/dashboard/events/manage/<str:event_id>/publish/` | ManageEventPublishAPI | Login | Admin, Enabler | features/events/api/events.api.ts:507 | — | M-10 |
| GET | `/api/v1/dashboard/events/manage/<str:event_id>/co-owners/` | ManageEventCoOwnerAPI | Login | any logged-in | features/events/api/events.api.ts:516 | — | M-10 |
| POST | `/api/v1/dashboard/events/manage/<str:event_id>/co-owners/` | ManageEventCoOwnerAPI | Login | any logged-in | features/events/api/events.api.ts:525 | — | M-10 |
| DELETE | `/api/v1/dashboard/events/manage/<str:event_id>/co-owners/<str:co_owner_id>/` | ManageEventCoOwnerRemoveAPI | Login | any logged-in | features/events/api/events.api.ts:535 | — | M-10 |
| GET | `/api/v1/dashboard/events/manage/<str:event_id>/collaborators/` | ManageEventCollaboratorAPI | Login | any logged-in | features/events/api/events.api.ts:546 | — | M-10 |
| POST | `/api/v1/dashboard/events/manage/<str:event_id>/collaborators/` | ManageEventCollaboratorAPI | Login | any logged-in | features/events/api/events.api.ts:555 | — | M-10 |
| POST | `/api/v1/dashboard/events/manage/<str:event_id>/collaborators/<str:collaborator_id>/accept/` | ManageEventCollaboratorAcceptAPI | Login | any logged-in | features/events/api/events.api.ts:565 | — | M-10 |
| POST | `/api/v1/dashboard/events/manage/<str:event_id>/collaborators/<str:collaborator_id>/reject/` | ManageEventCollaboratorRejectAPI | Login | any logged-in | features/events/api/events.api.ts:576 | — | M-10 |
| DELETE | `/api/v1/dashboard/events/manage/<str:event_id>/collaborators/<str:collaborator_id>/` | ManageEventCollaboratorRemoveAPI | Login | any logged-in | features/events/api/events.api.ts:586 | — | M-10 |
| GET | `/api/v1/dashboard/events/manage/<str:event_id>/tasks/meta/` | EventTaskMetaAPI | Login | Admin, Enabler | — | — | M-10, H-25 |
| GET | `/api/v1/dashboard/events/manage/<str:event_id>/tasks/<str:task_id>/` | EventTaskDetailAPI | Login | Admin, Enabler | — | — | M-10, H-25 |
| PATCH | `/api/v1/dashboard/events/manage/<str:event_id>/tasks/<str:task_id>/` | EventTaskDetailAPI | Login | Admin, Enabler | — | — | M-10, H-25 |
| DELETE | `/api/v1/dashboard/events/manage/<str:event_id>/tasks/<str:task_id>/` | EventTaskDetailAPI | Login | Admin, Enabler | — | — | M-10, H-25 |
| GET | `/api/v1/dashboard/events/manage/<str:event_id>/tasks/` | EventTaskListCreateAPI | Login | Admin, Enabler | — | — | M-10, H-25 |
| POST | `/api/v1/dashboard/events/manage/<str:event_id>/tasks/` | EventTaskListCreateAPI | Login | Admin, Enabler | — | — | M-10, H-25 |
| GET | `/api/v1/dashboard/events/manage/<str:event_id>/analytics/` | EventAnalyticsAPI | Login | Admin, Enabler | — | — | M-10 |
| GET | `/api/v1/dashboard/events/manage/<str:event_id>/` | ManageEventDetailAPI | Login | Admin, Enabler | features/events/api/events.api.ts:469 | — | M-10 |
| PUT | `/api/v1/dashboard/events/manage/<str:event_id>/` | ManageEventDetailAPI | Login | Admin, Enabler | features/events/api/events.api.ts:479 | — | M-10 |
| PATCH | `/api/v1/dashboard/events/manage/<str:event_id>/` | ManageEventDetailAPI | Login | Admin, Enabler | features/events/api/events.api.ts:491 | — | M-10 |
| DELETE | `/api/v1/dashboard/events/manage/<str:event_id>/` | ManageEventDetailAPI | Login | Admin, Enabler | features/events/api/events.api.ts:501 | — | M-10 |
| GET | `/api/v1/dashboard/events/my-invites/` | MyEventInvitesAPI | Login | any logged-in | features/events/api/events.api.ts:542 | — | — |
| GET | `/api/v1/dashboard/events/calendar/` | EventCalendarAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/events/featured/` | EventFeaturedAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/events/is-featured/` | EventFeaturedAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/events/tasks/` | EventTaskPublicListAPI | Login | any logged-in | — | — | — |
| POST | `/api/v1/dashboard/events/<str:event_id>/interest/` | EventInterestAPI | Login | any logged-in | features/events/api/events.api.ts:438 | — | — |
| DELETE | `/api/v1/dashboard/events/<str:event_id>/interest/` | EventInterestAPI | Login | any logged-in | features/events/api/events.api.ts:445 | — | — |
| GET | `/api/v1/dashboard/events/<str:event_id>/` | EventDetailAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/events/` | EventListAPI | Login | any logged-in | — | — | M-11 |

#### `dashboard/feature` (2 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/feature/grit-meter/` | GritMeterToggleAPI | Login | any logged-in | features/grit-meter/api/grit-meter.api.ts:12 | — | — |
| POST | `/api/v1/dashboard/feature/grit-meter/` | GritMeterToggleAPI | Login | Admin | features/grit-meter/api/grit-meter.api.ts:21 | — | — |

#### `dashboard/home` (2 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/home/learner/summary/` | LearnerDashboardSummaryAPIView | Login | any logged-in | features/home/api/home.api.ts:87 | — | — |
| GET | `/api/v1/dashboard/home/learner/streak/` | LearnerStreakAPIView | Login | any logged-in | features/home/api/home.api.ts:160 | — | — |

#### `dashboard/ig` (36 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/ig/` | InterestGroupAPI | Login | any logged-in | features/manage-ig/api/manage-ig.api.ts:70 | — | — |
| POST | `/api/v1/dashboard/ig/` | InterestGroupAPI | Login | Admin, IG Lead | features/manage-ig/api/manage-ig.api.ts:87, features/manage-ig/api/manage-ig.api.ts:93 | — | — |
| PUT | `/api/v1/dashboard/ig/` | InterestGroupAPI | Login | none observed | — | TypeError: InterestGroupAPI.put() missing 1 required positional argume (admin,iglead) | — |
| DELETE | `/api/v1/dashboard/ig/` | InterestGroupAPI | Login | none observed | — | TypeError: InterestGroupAPI.delete() missing 1 required positional arg (admin,iglead) | — |
| GET | `/api/v1/dashboard/ig/request/` | InterestGroupRequestAPI | Login | Admin, Company | features/manage-ig/api/manage-ig.api.ts:149 | — | M-08 |
| POST | `/api/v1/dashboard/ig/request/` | InterestGroupRequestAPI | Login | Admin, Company | features/ig-requests/api/ig-requests.api.ts:62, features/manage-ig/api/manage-ig.api.ts:179 (+1) | — | M-08 |
| PATCH | `/api/v1/dashboard/ig/request/` | InterestGroupRequestAPI | Login | none observed | — | TypeError: InterestGroupRequestAPI.patch() missing 1 required position (admin) | M-08 |
| DELETE | `/api/v1/dashboard/ig/request/` | InterestGroupRequestAPI | Login | none observed | — | TypeError: InterestGroupRequestAPI.delete() missing 1 required positio (admin,company) | M-08 |
| GET | `/api/v1/dashboard/ig/request/<str:pk>/` | InterestGroupRequestAPI | Login | none observed | — | TypeError: InterestGroupRequestAPI.get() got an unexpected keyword arg (admin,company) | M-08 |
| POST | `/api/v1/dashboard/ig/request/<str:pk>/` | InterestGroupRequestAPI | Login | none observed | — | TypeError: InterestGroupRequestAPI.post() got an unexpected keyword ar (admin,company) | M-08 |
| PATCH | `/api/v1/dashboard/ig/request/<str:pk>/` | InterestGroupRequestAPI | Login | Admin | features/ig-requests/api/ig-requests.api.ts:74, features/manage-ig/api/manage-ig.api.ts:160 | — | M-08 |
| DELETE | `/api/v1/dashboard/ig/request/<str:pk>/` | InterestGroupRequestAPI | Login | Admin, Company | features/ig-requests/api/ig-requests.api.ts:82 | — | M-08 |
| GET | `/api/v1/dashboard/ig/list/` | InterestGroupListApi | **Public** | any logged-in | features/campus-manage/api/campus-manage.api.ts:650, features/events/api/events.api.ts:629 (+5) | — | — |
| GET | `/api/v1/dashboard/ig/csv/` | InterestGroupCSV | Login | Admin | features/manage-ig/api/manage-ig.api.ts:131 | — | — |
| GET | `/api/v1/dashboard/ig/impact-projects/public/` | PublicImpactProjectListAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/ig/<str:ig_id>/impact-projects/` | ImpactProjectListCreateAPI | Login | any logged-in | features/manage-ig/api/impact-projects.api.ts:18 | — | — |
| POST | `/api/v1/dashboard/ig/<str:ig_id>/impact-projects/` | ImpactProjectListCreateAPI | Login | Admin, IG Lead | features/manage-ig/api/impact-projects.api.ts:29 | — | — |
| PATCH | `/api/v1/dashboard/ig/<str:ig_id>/impact-projects/<str:project_id>/` | ImpactProjectDetailAPI | Login | Admin, IG Lead | features/manage-ig/api/impact-projects.api.ts:42 | — | — |
| DELETE | `/api/v1/dashboard/ig/<str:ig_id>/impact-projects/<str:project_id>/` | ImpactProjectDetailAPI | Login | Admin, IG Lead | features/manage-ig/api/impact-projects.api.ts:54 | — | — |
| POST | `/api/v1/dashboard/ig/<str:ig_id>/impact-projects/<str:project_id>/image/` | ImpactProjectImageAPI | Login | Admin, IG Lead | — | — | — |
| POST | `/api/v1/dashboard/ig/<str:pk>/cover-image/` | InterestGroupImageAPI | Login | Admin, IG Lead | features/manage-ig/api/manage-ig.api.ts:202 | — | — |
| DELETE | `/api/v1/dashboard/ig/<str:pk>/cover-image/` | InterestGroupImageAPI | Login | Admin, IG Lead | features/manage-ig/api/manage-ig.api.ts:212 | — | — |
| POST | `/api/v1/dashboard/ig/<str:pk>/icon-image/` | InterestGroupImageAPI | Login | Admin, IG Lead | features/manage-ig/api/manage-ig.api.ts:222 | — | — |
| DELETE | `/api/v1/dashboard/ig/<str:pk>/icon-image/` | InterestGroupImageAPI | Login | Admin, IG Lead | features/manage-ig/api/manage-ig.api.ts:232 | — | — |
| GET | `/api/v1/dashboard/ig/<str:pk>/` | InterestGroupAPI | Login | ? (500) | — | TypeError: InterestGroupAPI.get() got an unexpected keyword argument ' (admin,associate,campusiglead,campuslead,) | — |
| POST | `/api/v1/dashboard/ig/<str:pk>/` | InterestGroupAPI | Login | none observed | — | TypeError: InterestGroupAPI.post() got an unexpected keyword argument  (admin,iglead) | — |
| PUT | `/api/v1/dashboard/ig/<str:pk>/` | InterestGroupAPI | Login | Admin, IG Lead | features/manage-ig/api/manage-ig.api.ts:105 | — | L-30 |
| DELETE | `/api/v1/dashboard/ig/<str:pk>/` | InterestGroupAPI | Login | Admin, IG Lead | features/manage-ig/api/manage-ig.api.ts:119 | — | H-11, L-30 |
| POST | `/api/v1/dashboard/ig/<str:pk>/activate/` | InterestGroupActivateAPIView | Login | Admin, IG Lead | features/manage-ig/api/manage-ig.api.ts:123 | — | M-37 |
| POST | `/api/v1/dashboard/ig/<str:pk>/deactivate/` | InterestGroupDeactivateAPIView | Login | Admin, IG Lead | features/manage-ig/api/manage-ig.api.ts:127 | — | — |
| GET | `/api/v1/dashboard/ig/get/<str:pk>/` | InterestGroupGetAPI | Login | Admin, IG Lead | — | — | — |
| PATCH | `/api/v1/dashboard/ig/get/<str:pk>/` | InterestGroupGetAPI | Login | Admin, IG Lead | features/manage-ig/api/manage-ig.api.ts:112 | — | H-24 |
| POST | `/api/v1/dashboard/ig/<str:pk>/join/` | InterestGroupMembershipAPI | Login | any logged-in | — | — | M-09, L-31 |
| DELETE | `/api/v1/dashboard/ig/<str:pk>/join/` | InterestGroupMembershipAPI | Login | any logged-in | — | — | M-09, L-31 |
| POST | `/api/v1/dashboard/ig/<str:pk>/leave/` | InterestGroupMembershipAPI | Login | any logged-in | — | — | M-09, L-31 |
| DELETE | `/api/v1/dashboard/ig/<str:pk>/leave/` | InterestGroupMembershipAPI | Login | any logged-in | — | — | M-09, L-31 |

#### `dashboard/intern` (49 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/intern/timesheets/` | InternTimesheetAPI | Login | Intern | features/intern/api/intern.api.ts:85 | — | — |
| POST | `/api/v1/dashboard/intern/timesheets/` | InternTimesheetAPI | Login | Intern | features/intern/api/intern.api.ts:111 | — | — |
| PATCH | `/api/v1/dashboard/intern/timesheets/` | InternTimesheetAPI | Login | none observed | — | TypeError: InternTimesheetAPI.patch() missing 1 required positional ar (intern) | — |
| GET | `/api/v1/dashboard/intern/timesheets/prefill/` | InternTimesheetPrefillAPI | Login | Intern | features/intern/api/intern.api.ts:107 | — | — |
| GET | `/api/v1/dashboard/intern/timesheets/today/` | InternTimesheetTodayAPI | Login | Intern | features/intern/api/intern.api.ts:122 | — | — |
| GET | `/api/v1/dashboard/intern/timesheets/history/` | InternTimesheetHistoryAPI | Login | Intern | features/intern/api/intern.api.ts:129 | — | — |
| GET | `/api/v1/dashboard/intern/timesheets/summary/` | InternTimesheetSummaryAPI | Login | Intern | features/intern/api/intern.api.ts:135 | — | — |
| GET | `/api/v1/dashboard/intern/timesheets/<str:timesheet_id>/` | InternTimesheetAPI | Login | Intern | features/intern/api/intern.api.ts:91 | — | — |
| POST | `/api/v1/dashboard/intern/timesheets/<str:timesheet_id>/` | InternTimesheetAPI | Login | none observed | — | TypeError: InternTimesheetAPI.post() got an unexpected keyword argumen (intern) | — |
| PATCH | `/api/v1/dashboard/intern/timesheets/<str:timesheet_id>/` | InternTimesheetAPI | Login | Intern | features/intern/api/intern.api.ts:118 | — | — |
| GET | `/api/v1/dashboard/intern/reviews/` | InternWeeklyReviewAPI | Login | Intern | features/intern/api/intern.api.ts:143 | — | — |
| POST | `/api/v1/dashboard/intern/reviews/` | InternWeeklyReviewAPI | Login | Intern | features/intern/api/intern.api.ts:173 | — | — |
| PATCH | `/api/v1/dashboard/intern/reviews/` | InternWeeklyReviewAPI | Login | none observed | — | TypeError: InternWeeklyReviewAPI.patch() missing 1 required positional (intern) | — |
| GET | `/api/v1/dashboard/intern/reviews/prefill/` | InternWeeklyReviewPrefillAPI | Login | Intern | features/intern/api/intern.api.ts:167 | — | — |
| GET | `/api/v1/dashboard/intern/reviews/current/` | InternWeeklyReviewCurrentAPI | Login | Intern | features/intern/api/intern.api.ts:184 | — | — |
| GET | `/api/v1/dashboard/intern/reviews/history/` | InternWeeklyReviewHistoryAPI | Login | Intern | features/intern/api/intern.api.ts:191 | — | — |
| GET | `/api/v1/dashboard/intern/reviews/<str:review_id>/` | InternWeeklyReviewAPI | Login | Intern | features/intern/api/intern.api.ts:149 | — | — |
| POST | `/api/v1/dashboard/intern/reviews/<str:review_id>/` | InternWeeklyReviewAPI | Login | none observed | — | TypeError: InternWeeklyReviewAPI.post() got an unexpected keyword argu (intern) | — |
| PATCH | `/api/v1/dashboard/intern/reviews/<str:review_id>/` | InternWeeklyReviewAPI | Login | Intern | features/intern/api/intern.api.ts:180 | — | — |
| GET | `/api/v1/dashboard/intern/overview/status/` | InternOverviewStatusAPI | Login | Intern | features/intern/api/intern.api.ts:62 | — | — |
| GET | `/api/v1/dashboard/intern/overview/activity/` | InternOverviewActivityAPI | Login | Intern | features/intern/api/intern.api.ts:71 | — | — |
| GET | `/api/v1/dashboard/intern/overview/leaderboard/top/` | InternOverviewLeaderboardTopAPI | Login | Intern | features/intern/api/intern.api.ts:77 | — | — |
| GET | `/api/v1/dashboard/intern/leaderboard/` | InternLeaderboardAPI | Login | Admin, Intern | features/intern/api/intern.api.ts:269 | — | — |
| GET | `/api/v1/dashboard/intern/leaderboard/me/` | InternLeaderboardMeAPI | Login | Intern | features/intern/api/intern.api.ts:276 | — | — |
| GET | `/api/v1/dashboard/intern/tasks/categories/` | InternTaskCategoryAPI | Login | Admin, Intern | features/intern/api/intern.api.ts:218 | — | — |
| GET | `/api/v1/dashboard/intern/tasks/mine/` | InternTaskMineAPI | Login | Intern | features/intern/api/intern.api.ts:201 | — | — |
| PATCH | `/api/v1/dashboard/intern/tasks/<str:task_id>/` | InternTaskSubmitAPI | Login | Intern | features/intern/api/intern.api.ts:211 | — | — |
| PATCH | `/api/v1/dashboard/intern/tasks/<str:task_id>/submit/` | InternTaskSubmitAPI | Login | Intern | — | — | — |
| GET | `/api/v1/dashboard/intern/tasks/<str:task_id>/detail/` | InternTaskDetailAPI | Login | Intern | features/intern/api/intern.api.ts:224 | — | — |
| GET | `/api/v1/dashboard/intern/leave/` | InternLeaveRequestAPI | Login | Intern | features/intern/api/intern.api.ts:232 | — | — |
| POST | `/api/v1/dashboard/intern/leave/` | InternLeaveRequestAPI | Login | Intern | features/intern/api/intern.api.ts:242 | — | — |
| PATCH | `/api/v1/dashboard/intern/leave/` | InternLeaveRequestAPI | Login | Intern | — | — | — |
| GET | `/api/v1/dashboard/intern/leave/history/` | InternLeaveHistoryAPI | Login | Intern | features/intern/api/intern.api.ts:255 | — | — |
| GET | `/api/v1/dashboard/intern/leave/balance/` | InternLeaveBalanceAPI | Login | Intern | features/intern/api/intern.api.ts:261 | — | — |
| GET | `/api/v1/dashboard/intern/leave/<str:leave_id>/` | InternLeaveRequestAPI | Login | Intern | features/intern/api/intern.api.ts:238 | — | — |
| POST | `/api/v1/dashboard/intern/leave/<str:leave_id>/` | InternLeaveRequestAPI | Login | none observed | — | TypeError: InternLeaveRequestAPI.post() got an unexpected keyword argu (intern) | — |
| PATCH | `/api/v1/dashboard/intern/leave/<str:leave_id>/` | InternLeaveRequestAPI | Login | Intern | features/intern/api/intern.api.ts:246 | — | — |
| GET | `/api/v1/dashboard/intern/leave/<str:leave_id>/cancel/` | InternLeaveRequestAPI | Login | Intern | — | — | — |
| POST | `/api/v1/dashboard/intern/leave/<str:leave_id>/cancel/` | InternLeaveRequestAPI | Login | none observed | — | TypeError: InternLeaveRequestAPI.post() got an unexpected keyword argu (intern) | — |
| PATCH | `/api/v1/dashboard/intern/leave/<str:leave_id>/cancel/` | InternLeaveRequestAPI | Login | Intern | — | — | — |
| GET | `/api/v1/dashboard/intern/guilds/` | InternGuildsAPI | Login | Admin, Intern | features/intern/api/intern.api.ts:289 | — | — |
| GET | `/api/v1/dashboard/intern/minutes/` | InternGuildMinuteAPI | Login | Admin, Intern, Intern Lead | features/intern/api/intern.api.ts:308, features/intern/api/manage-interns.api.ts:212 | — | M-38 |
| POST | `/api/v1/dashboard/intern/minutes/` | InternGuildMinuteAPI | Login | Admin, Intern Lead | features/intern/api/intern.api.ts:294 | — | M-38 |
| PUT | `/api/v1/dashboard/intern/minutes/` | InternGuildMinuteAPI | Login | none observed | — | TypeError: InternGuildMinuteAPI.put() missing 1 required positional ar (admin,internlead) | M-38 |
| DELETE | `/api/v1/dashboard/intern/minutes/` | InternGuildMinuteAPI | Login | none observed | — | TypeError: InternGuildMinuteAPI.delete() missing 1 required positional (admin,internlead) | M-38 |
| GET | `/api/v1/dashboard/intern/minutes/<str:minute_id>/` | InternGuildMinuteAPI | Login | Admin, Intern, Intern Lead | — | — | M-38 |
| POST | `/api/v1/dashboard/intern/minutes/<str:minute_id>/` | InternGuildMinuteAPI | Login | none observed | — | TypeError: InternGuildMinuteAPI.post() got an unexpected keyword argum (admin,internlead) | M-38 |
| PUT | `/api/v1/dashboard/intern/minutes/<str:minute_id>/` | InternGuildMinuteAPI | Login | Admin, Intern Lead | features/intern/api/intern.api.ts:301 | — | M-38 |
| DELETE | `/api/v1/dashboard/intern/minutes/<str:minute_id>/` | InternGuildMinuteAPI | Login | Admin, Intern Lead | — | — | M-38 |

#### `dashboard/karma-voucher` (19 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/karma-voucher/` | VoucherLogAPI | Login | Admin, Associate, Fellow | features/karma-voucher/api/karma-voucher.api.ts:43 | — | — |
| POST | `/api/v1/dashboard/karma-voucher/` | VoucherLogAPI | Login | Admin, Associate, Fellow | — | — | — |
| PATCH | `/api/v1/dashboard/karma-voucher/` | VoucherLogAPI | Login | none observed | — | TypeError: VoucherLogAPI.patch() missing 1 required positional argumen (admin,associate,fellow) | — |
| DELETE | `/api/v1/dashboard/karma-voucher/` | VoucherLogAPI | Login | none observed | — | TypeError: VoucherLogAPI.delete() missing 1 required positional argume (admin,associate,fellow) | — |
| POST | `/api/v1/dashboard/karma-voucher/import/` | ImportVoucherLogAPI | Login | Admin, Associate, Fellow | features/karma-voucher/api/karma-voucher.api.ts:97 | — | — |
| GET | `/api/v1/dashboard/karma-voucher/export/` | ExportVoucherLogAPI | Login | Admin, Associate, Fellow | features/karma-voucher/api/karma-voucher.api.ts:136 | — | — |
| GET | `/api/v1/dashboard/karma-voucher/create/` | VoucherLogAPI | Login | Admin, Associate, Fellow | — | — | — |
| POST | `/api/v1/dashboard/karma-voucher/create/` | VoucherLogAPI | Login | Admin, Associate, Fellow | features/karma-voucher/api/karma-voucher.api.ts:62 | — | — |
| PATCH | `/api/v1/dashboard/karma-voucher/create/` | VoucherLogAPI | Login | none observed | — | TypeError: VoucherLogAPI.patch() missing 1 required positional argumen (admin,associate,fellow) | — |
| DELETE | `/api/v1/dashboard/karma-voucher/create/` | VoucherLogAPI | Login | none observed | — | TypeError: VoucherLogAPI.delete() missing 1 required positional argume (admin,associate,fellow) | — |
| GET | `/api/v1/dashboard/karma-voucher/update/<str:voucher_id>/` | VoucherLogAPI | Login | none observed | — | TypeError: VoucherLogAPI.get() got an unexpected keyword argument 'vou (admin,associate,fellow) | — |
| POST | `/api/v1/dashboard/karma-voucher/update/<str:voucher_id>/` | VoucherLogAPI | Login | none observed | — | TypeError: VoucherLogAPI.post() got an unexpected keyword argument 'vo (admin,associate,fellow) | — |
| PATCH | `/api/v1/dashboard/karma-voucher/update/<str:voucher_id>/` | VoucherLogAPI | Login | Admin, Associate, Fellow | features/karma-voucher/api/karma-voucher.api.ts:81 | — | — |
| DELETE | `/api/v1/dashboard/karma-voucher/update/<str:voucher_id>/` | VoucherLogAPI | Login | Admin, Associate, Fellow | — | — | — |
| GET | `/api/v1/dashboard/karma-voucher/delete/<str:voucher_id>/` | VoucherLogAPI | Login | none observed | — | TypeError: VoucherLogAPI.get() got an unexpected keyword argument 'vou (admin,associate,fellow) | — |
| POST | `/api/v1/dashboard/karma-voucher/delete/<str:voucher_id>/` | VoucherLogAPI | Login | none observed | — | TypeError: VoucherLogAPI.post() got an unexpected keyword argument 'vo (admin,associate,fellow) | — |
| PATCH | `/api/v1/dashboard/karma-voucher/delete/<str:voucher_id>/` | VoucherLogAPI | Login | Admin, Associate, Fellow | — | — | — |
| DELETE | `/api/v1/dashboard/karma-voucher/delete/<str:voucher_id>/` | VoucherLogAPI | Login | Admin, Associate, Fellow | features/karma-voucher/api/karma-voucher.api.ts:87 | — | — |
| GET | `/api/v1/dashboard/karma-voucher/base-template/` | VoucherBaseTemplateAPI | Login | ? (500) | features/karma-voucher/api/karma-voucher.api.ts:146 | FileNotFoundError: [Errno 2] No such file or directory: './excel-templ (admin,associate,campusiglead,campuslead,) | — |

#### `dashboard/learningcircle` (61 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/learningcircle/create/` | LearningCircleView | Login | any logged-in | — | — | H-10 |
| POST | `/api/v1/dashboard/learningcircle/create/` | LearningCircleView | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:127 | — | H-10, M-42 |
| PUT | `/api/v1/dashboard/learningcircle/create/` | LearningCircleView | Login | ? (500) | — | TypeError: LearningCircleView.put() missing 1 required positional argu (admin,associate,campusiglead,campuslead,) | H-10 |
| DELETE | `/api/v1/dashboard/learningcircle/create/` | LearningCircleView | Login | ? (500) | — | TypeError: LearningCircleView.delete() missing 1 required positional a (admin,associate,campusiglead,campuslead,) | H-10 |
| GET | `/api/v1/dashboard/learningcircle/list/` | LearningCircleView | Login | any logged-in | — | — | H-10 |
| POST | `/api/v1/dashboard/learningcircle/list/` | LearningCircleView | Login | any logged-in | — | — | H-10, M-42 |
| PUT | `/api/v1/dashboard/learningcircle/list/` | LearningCircleView | Login | ? (500) | — | TypeError: LearningCircleView.put() missing 1 required positional argu (admin,associate,campusiglead,campuslead,) | H-10 |
| DELETE | `/api/v1/dashboard/learningcircle/list/` | LearningCircleView | Login | ? (500) | — | TypeError: LearningCircleView.delete() missing 1 required positional a (admin,associate,campusiglead,campuslead,) | H-10 |
| GET | `/api/v1/dashboard/learningcircle/info/<str:circle_id>/` | LearningCircleView | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:107 | — | — |
| POST | `/api/v1/dashboard/learningcircle/info/<str:circle_id>/` | LearningCircleView | Login | ? (500) | — | TypeError: LearningCircleView.post() got an unexpected keyword argumen (admin,associate,campusiglead,campuslead,) | — |
| PUT | `/api/v1/dashboard/learningcircle/info/<str:circle_id>/` | LearningCircleView | Login | Student | — | — | M-42 |
| DELETE | `/api/v1/dashboard/learningcircle/info/<str:circle_id>/` | LearningCircleView | Login | Student | — | — | M-20 |
| GET | `/api/v1/dashboard/learningcircle/members/<str:circle_id>/` | LearningCircleMemberDetailsView | **Public** | any logged-in | features/learning-circle/api/learning-circle.api.ts:118 | — | L-33 |
| GET | `/api/v1/dashboard/learningcircle/edit/<str:circle_id>/` | LearningCircleView | Login | any logged-in | — | — | — |
| POST | `/api/v1/dashboard/learningcircle/edit/<str:circle_id>/` | LearningCircleView | Login | ? (500) | — | TypeError: LearningCircleView.post() got an unexpected keyword argumen (admin,associate,campusiglead,campuslead,) | — |
| PUT | `/api/v1/dashboard/learningcircle/edit/<str:circle_id>/` | LearningCircleView | Login | Student | features/learning-circle/api/learning-circle.api.ts:140 | — | M-42 |
| DELETE | `/api/v1/dashboard/learningcircle/edit/<str:circle_id>/` | LearningCircleView | Login | Student | — | — | M-20 |
| GET | `/api/v1/dashboard/learningcircle/delete/<str:circle_id>/` | LearningCircleView | Login | any logged-in | — | — | — |
| POST | `/api/v1/dashboard/learningcircle/delete/<str:circle_id>/` | LearningCircleView | Login | ? (500) | — | TypeError: LearningCircleView.post() got an unexpected keyword argumen (admin,associate,campusiglead,campuslead,) | — |
| PUT | `/api/v1/dashboard/learningcircle/delete/<str:circle_id>/` | LearningCircleView | Login | Student | — | — | M-42 |
| DELETE | `/api/v1/dashboard/learningcircle/delete/<str:circle_id>/` | LearningCircleView | Login | Student | features/learning-circle/api/learning-circle.api.ts:149 | — | M-20 |
| POST | `/api/v1/dashboard/learningcircle/meeting/create/<str:circle_id>/` | LearningCircleMeetingView | Login | Student | features/learning-circle/api/learning-circle.api.ts:387 | — | — |
| PUT | `/api/v1/dashboard/learningcircle/meeting/create/<str:circle_id>/` | LearningCircleMeetingView | Login | ? (500) | — | TypeError: LearningCircleMeetingView.put() got an unexpected keyword a (admin,associate,campusiglead,campuslead,) | — |
| DELETE | `/api/v1/dashboard/learningcircle/meeting/create/<str:circle_id>/` | LearningCircleMeetingView | Login | ? (500) | — | TypeError: LearningCircleMeetingView.delete() got an unexpected keywor (admin,associate,campusiglead,campuslead,) | — |
| GET | `/api/v1/dashboard/learningcircle/meeting/list-public/` | LearningCircleMeetingPublicListView | Public? (anon→500) | ? (500) | — | OverflowError: date value out of range (admin,anon,associate,campusiglead,campus) | L-33 |
| GET | `/api/v1/dashboard/learningcircle/meeting/list/` | LearningCircleMeetingListAPI | Login | ? (500) | — | OverflowError: date value out of range (admin,associate,campusiglead,campuslead,) | L-33 |
| GET | `/api/v1/dashboard/learningcircle/meeting/list/<str:circle_id>/` | LearningCircleMeetingListView | **Public** | any logged-in | features/learning-circle/api/learning-circle.api.ts:319 | — | L-33 |
| POST | `/api/v1/dashboard/learningcircle/meeting/edit/<str:meet_id>/` | LearningCircleMeetingView | Login | ? (500) | — | TypeError: LearningCircleMeetingView.post() got an unexpected keyword  (admin,associate,campusiglead,campuslead,) | — |
| PUT | `/api/v1/dashboard/learningcircle/meeting/edit/<str:meet_id>/` | LearningCircleMeetingView | Login | Student | features/learning-circle/api/learning-circle.api.ts:408 | — | — |
| DELETE | `/api/v1/dashboard/learningcircle/meeting/edit/<str:meet_id>/` | LearningCircleMeetingView | Login | Student | — | — | — |
| GET | `/api/v1/dashboard/learningcircle/meeting/info/<str:meet_id>/` | LearningCircleMeetingInfoAPI | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:364 | — | — |
| POST | `/api/v1/dashboard/learningcircle/meeting/delete/<str:meet_id>/` | LearningCircleMeetingView | Login | ? (500) | — | TypeError: LearningCircleMeetingView.post() got an unexpected keyword  (admin,associate,campusiglead,campuslead,) | — |
| PUT | `/api/v1/dashboard/learningcircle/meeting/delete/<str:meet_id>/` | LearningCircleMeetingView | Login | Student | — | — | — |
| DELETE | `/api/v1/dashboard/learningcircle/meeting/delete/<str:meet_id>/` | LearningCircleMeetingView | Login | Student | features/learning-circle/api/learning-circle.api.ts:417 | — | — |
| POST | `/api/v1/dashboard/learningcircle/meeting/join/<str:meet_id>/` | LearningCircleJoinAPI | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:449 | — | H-10 |
| DELETE | `/api/v1/dashboard/learningcircle/meeting/join/<str:meet_id>/` | LearningCircleJoinAPI | Login | any logged-in | — | — | H-10 |
| POST | `/api/v1/dashboard/learningcircle/meeting/rsvp/<str:meet_id>/` | LearningCircleRSVPAPI | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:429 | — | — |
| DELETE | `/api/v1/dashboard/learningcircle/meeting/rsvp/<str:meet_id>/` | LearningCircleRSVPAPI | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:438 | — | — |
| POST | `/api/v1/dashboard/learningcircle/meeting/leave/<str:meet_id>/` | LearningCircleJoinAPI | Login | any logged-in | — | — | — |
| DELETE | `/api/v1/dashboard/learningcircle/meeting/leave/<str:meet_id>/` | LearningCircleJoinAPI | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:458 | — | — |
| GET | `/api/v1/dashboard/learningcircle/meeting/attendee-report/<str:meet_id>/` | LearningCircleAttendeeReportAPI | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:482 | — | H-10 |
| POST | `/api/v1/dashboard/learningcircle/meeting/attendee-report/<str:meet_id>/` | LearningCircleAttendeeReportAPI | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:473 | — | H-10 |
| DELETE | `/api/v1/dashboard/learningcircle/meeting/attendee-report/<str:meet_id>/` | LearningCircleAttendeeReportAPI | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:491 | — | H-10 |
| GET | `/api/v1/dashboard/learningcircle/meeting/report/<str:meet_id>/` | LearningCircleReportAPI | Login | Student | features/learning-circle/api/learning-circle.api.ts:511 | — | H-10 |
| POST | `/api/v1/dashboard/learningcircle/meeting/report/<str:meet_id>/` | LearningCircleReportAPI | Login | Student | features/learning-circle/api/learning-circle.api.ts:502 | — | H-10, L-34 |
| DELETE | `/api/v1/dashboard/learningcircle/meeting/report/<str:meet_id>/` | LearningCircleReportAPI | Login | Student | features/learning-circle/api/learning-circle.api.ts:520 | — | H-10 |
| GET | `/api/v1/dashboard/learningcircle/meeting/report/export/<str:meet_id>/` | LearningCircleReportExportAPI | Login | Student | — | — | H-10 |
| GET | `/api/v1/dashboard/learningcircle/user-circles/` | UserCircleListAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/learningcircle/join/<str:circle_id>/` | CircleJoinAPI | Login | Student | features/learning-circle/api/learning-circle.api.ts:221 | — | — |
| POST | `/api/v1/dashboard/learningcircle/join/<str:circle_id>/` | CircleJoinAPI | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:210 | — | — |
| PATCH | `/api/v1/dashboard/learningcircle/join/<str:circle_id>/` | CircleJoinAPI | Login | Student | features/learning-circle/api/learning-circle.api.ts:233 | — | — |
| POST | `/api/v1/dashboard/learningcircle/members/add/<str:circle_id>/` | CircleMemberAddAPI | Login | Student | features/learning-circle/api/learning-circle.api.ts:164 | — | M-43 |
| DELETE | `/api/v1/dashboard/learningcircle/members/remove/<str:circle_id>/` | CircleMemberRemoveAPI | Login | Student | features/learning-circle/api/learning-circle.api.ts:188 | — | — |
| DELETE | `/api/v1/dashboard/learningcircle/leave/<str:circle_id>/` | CircleLeaveAPI | Login | Student | features/learning-circle/api/learning-circle.api.ts:197 | — | — |
| GET | `/api/v1/dashboard/learningcircle/invite/status/` | CircleInviteStatusAPI | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:274 | — | — |
| POST | `/api/v1/dashboard/learningcircle/invite/status/` | CircleInviteStatusAPI | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:285 | — | — |
| GET | `/api/v1/dashboard/learningcircle/invite/status/<str:link_id>/` | CircleInviteStatusAPI | Login | ? (500) | features/learning-circle/api/learning-circle.api.ts:294 | TypeError: CircleInviteStatusAPI.get() got an unexpected keyword argum (admin,associate,campusiglead,campuslead,) | H-27 |
| POST | `/api/v1/dashboard/learningcircle/invite/status/<str:link_id>/` | CircleInviteStatusAPI | Login | any logged-in | features/learning-circle/api/learning-circle.api.ts:306 | — | — |
| GET | `/api/v1/dashboard/learningcircle/invite/sent/<str:circle_id>/` | CircleSentInvitesAPI | Login | Student | features/learning-circle/api/learning-circle.api.ts:254 | — | — |
| POST | `/api/v1/dashboard/learningcircle/invite/<str:circle_id>/` | CircleInviteAPI | Login | Student | features/learning-circle/api/learning-circle.api.ts:245 | — | L-32 |
| POST | `/api/v1/dashboard/learningcircle/transfer-lead/<str:circle_id>/` | CircleTransferLeadAPI | Login | Student | features/learning-circle/api/learning-circle.api.ts:176 | — | — |

#### `dashboard/location` (35 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/location/countries/` | CountryDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:76 | — | — |
| POST | `/api/v1/dashboard/location/countries/` | CountryDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:84 | — | — |
| PATCH | `/api/v1/dashboard/location/countries/` | CountryDataAPI | Login | none observed | — | TypeError: CountryDataAPI.patch() missing 1 required positional argume (admin) | — |
| DELETE | `/api/v1/dashboard/location/countries/` | CountryDataAPI | Login | none observed | — | TypeError: CountryDataAPI.delete() missing 1 required positional argum (admin) | — |
| GET | `/api/v1/dashboard/location/countries/list/` | CountryListApi | **Public** | any logged-in | features/manage-locations/api/locations.api.ts:106, features/organizations/api/organizations.api.ts:140 | — | — |
| GET | `/api/v1/dashboard/location/countries/<str:country_id>/` | CountryDataAPI | Login | Admin | — | — | — |
| POST | `/api/v1/dashboard/location/countries/<str:country_id>/` | CountryDataAPI | Login | none observed | — | TypeError: CountryDataAPI.post() got an unexpected keyword argument 'c (admin) | — |
| PATCH | `/api/v1/dashboard/location/countries/<str:country_id>/` | CountryDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:94 | — | — |
| DELETE | `/api/v1/dashboard/location/countries/<str:country_id>/` | CountryDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:102 | — | — |
| GET | `/api/v1/dashboard/location/states/` | StateDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:118 | — | — |
| POST | `/api/v1/dashboard/location/states/` | StateDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:126 | — | — |
| PATCH | `/api/v1/dashboard/location/states/` | StateDataAPI | Login | none observed | — | TypeError: StateDataAPI.patch() missing 1 required positional argument (admin) | — |
| DELETE | `/api/v1/dashboard/location/states/` | StateDataAPI | Login | none observed | — | TypeError: StateDataAPI.delete() missing 1 required positional argumen (admin) | — |
| GET | `/api/v1/dashboard/location/states/list/` | StateListApi | **Public** | any logged-in | features/manage-locations/api/locations.api.ts:143, features/organizations/api/organizations.api.ts:147 | — | — |
| GET | `/api/v1/dashboard/location/states/<str:state_id>/` | StateDataAPI | Login | Admin | — | — | — |
| POST | `/api/v1/dashboard/location/states/<str:state_id>/` | StateDataAPI | Login | none observed | — | TypeError: StateDataAPI.post() got an unexpected keyword argument 'sta (admin) | — |
| PATCH | `/api/v1/dashboard/location/states/<str:state_id>/` | StateDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:132 | — | — |
| DELETE | `/api/v1/dashboard/location/states/<str:state_id>/` | StateDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:140 | — | — |
| GET | `/api/v1/dashboard/location/zones/` | ZoneDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:154 | — | — |
| POST | `/api/v1/dashboard/location/zones/` | ZoneDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:162 | — | — |
| PATCH | `/api/v1/dashboard/location/zones/` | ZoneDataAPI | Login | none observed | — | TypeError: ZoneDataAPI.patch() missing 1 required positional argument: (admin) | — |
| DELETE | `/api/v1/dashboard/location/zones/` | ZoneDataAPI | Login | none observed | — | TypeError: ZoneDataAPI.delete() missing 1 required positional argument (admin) | — |
| GET | `/api/v1/dashboard/location/zones/list/` | ZoneListApi | **Public** | any logged-in | features/manage-locations/api/locations.api.ts:180 | — | — |
| GET | `/api/v1/dashboard/location/zones/<str:zone_id>/` | ZoneDataAPI | Login | Admin | — | — | — |
| POST | `/api/v1/dashboard/location/zones/<str:zone_id>/` | ZoneDataAPI | Login | none observed | — | TypeError: ZoneDataAPI.post() got an unexpected keyword argument 'zone (admin) | — |
| PATCH | `/api/v1/dashboard/location/zones/<str:zone_id>/` | ZoneDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:168 | — | — |
| DELETE | `/api/v1/dashboard/location/zones/<str:zone_id>/` | ZoneDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:176 | — | — |
| GET | `/api/v1/dashboard/location/districts/` | DistrictDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:192 | — | — |
| POST | `/api/v1/dashboard/location/districts/` | DistrictDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:200 | — | — |
| PATCH | `/api/v1/dashboard/location/districts/` | DistrictDataAPI | Login | none observed | — | TypeError: DistrictDataAPI.patch() missing 1 required positional argum (admin) | — |
| DELETE | `/api/v1/dashboard/location/districts/` | DistrictDataAPI | Login | none observed | — | TypeError: DistrictDataAPI.delete() missing 1 required positional argu (admin) | — |
| GET | `/api/v1/dashboard/location/districts/<str:district_id>/` | DistrictDataAPI | Login | Admin | — | — | — |
| POST | `/api/v1/dashboard/location/districts/<str:district_id>/` | DistrictDataAPI | Login | none observed | — | TypeError: DistrictDataAPI.post() got an unexpected keyword argument ' (admin) | — |
| PATCH | `/api/v1/dashboard/location/districts/<str:district_id>/` | DistrictDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:210 | — | — |
| DELETE | `/api/v1/dashboard/location/districts/<str:district_id>/` | DistrictDataAPI | Login | Admin | features/manage-locations/api/locations.api.ts:218 | — | — |

#### `dashboard/manage-interns` (31 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/manage-interns/reviews/timesheets/<str:timesheet_id>/review/` | InternTimesheetReviewAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:166 | — | C-10, H-21, M-38 |
| PATCH | `/api/v1/dashboard/manage-interns/reviews/timesheets/<str:timesheet_id>/review/` | InternTimesheetReviewAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:175 | — | C-10, H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/reviews/reviews/<str:review_id>/review/` | InternWeeklyReviewReviewAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:192 | — | C-10, H-21, M-38 |
| PATCH | `/api/v1/dashboard/manage-interns/reviews/reviews/<str:review_id>/review/` | InternWeeklyReviewReviewAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:201 | — | C-10, H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/reviews/timesheets/` | InternTimesheetListAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:160 | — | C-10, H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/reviews/` | InternWeeklyReviewListAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:186 | — | C-10, H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/tasks/` | ManageInternTaskAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:91 | — | H-21, M-38 |
| POST | `/api/v1/dashboard/manage-interns/tasks/` | ManageInternTaskAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:101 | — | H-21, M-38 |
| PATCH | `/api/v1/dashboard/manage-interns/tasks/` | ManageInternTaskAPI | Login | none observed | — | TypeError: ManageInternTaskAPI.patch() missing 1 required positional a (admin,intern,internlead) | H-21, M-38 |
| DELETE | `/api/v1/dashboard/manage-interns/tasks/` | ManageInternTaskAPI | Login | none observed | — | TypeError: ManageInternTaskAPI.delete() missing 1 required positional  (admin,intern,internlead) | H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/tasks/by-intern/<str:muid>/` | ManageInternTasksByInternAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:127 | — | H-21, M-38 |
| POST | `/api/v1/dashboard/manage-interns/tasks/<str:task_id>/verify/` | ManageInternTaskVerifyAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:119 | — | C-10, H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/tasks/<str:task_id>/` | ManageInternTaskAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:97 | — | H-21, M-38 |
| POST | `/api/v1/dashboard/manage-interns/tasks/<str:task_id>/` | ManageInternTaskAPI | Login | none observed | — | TypeError: ManageInternTaskAPI.post() got an unexpected keyword argume (admin,intern,internlead) | H-21, M-38 |
| PATCH | `/api/v1/dashboard/manage-interns/tasks/<str:task_id>/` | ManageInternTaskAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:108 | — | H-21, M-38 |
| DELETE | `/api/v1/dashboard/manage-interns/tasks/<str:task_id>/` | ManageInternTaskAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:112 | — | H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/leave/` | ManageInternLeaveAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:137 | — | H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/leave/<str:leave_id>/` | ManageInternLeaveAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:143 | — | H-21, M-38 |
| PATCH | `/api/v1/dashboard/manage-interns/leave/<str:leave_id>/review/` | ManageInternLeaveReviewAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:152 | — | H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/status/` | ManageInternStatusAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:75 | — | H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/interns/export/` | ManageInternExportAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:81 | — | H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/interns/import/template/` | ManageInternBulkImportTemplateAPIView | Login | Admin | features/intern/api/manage-interns.api.ts:218 | — | H-21, M-38 |
| POST | `/api/v1/dashboard/manage-interns/interns/import/` | ManageInternBulkImportAPI | Login | Admin | features/intern/api/manage-interns.api.ts:228 | — | H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/interns/` | ManageInternAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:48 | — | H-21, M-38 |
| POST | `/api/v1/dashboard/manage-interns/interns/` | ManageInternAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:60 | — | H-21, M-38 |
| PATCH | `/api/v1/dashboard/manage-interns/interns/` | ManageInternAPI | Login | none observed | — | TypeError: ManageInternAPI.patch() missing 1 required positional argum (admin,intern,internlead) | H-21, M-38 |
| DELETE | `/api/v1/dashboard/manage-interns/interns/` | ManageInternAPI | Login | none observed | — | TypeError: ManageInternAPI.delete() missing 1 required positional argu (admin,intern,internlead) | H-21, M-38 |
| GET | `/api/v1/dashboard/manage-interns/interns/<str:intern_id>/` | ManageInternAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:54 | — | H-21, M-38 |
| POST | `/api/v1/dashboard/manage-interns/interns/<str:intern_id>/` | ManageInternAPI | Login | none observed | — | TypeError: ManageInternAPI.post() got an unexpected keyword argument ' (admin,intern,internlead) | H-21, M-38 |
| PATCH | `/api/v1/dashboard/manage-interns/interns/<str:intern_id>/` | ManageInternAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:67 | — | H-21, M-38 |
| DELETE | `/api/v1/dashboard/manage-interns/interns/<str:intern_id>/` | ManageInternAPI | Login | Admin, Intern, Intern Lead | features/intern/api/manage-interns.api.ts:71 | — | H-21, M-38 |

#### `dashboard/media-content` (22 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/media-content/office-hours/` | OfficeHoursListCreateAPI | **Public** | any logged-in | features/weekly-twitches/api/weekly-twitches.api.ts:62 | — | — |
| POST | `/api/v1/dashboard/media-content/office-hours/` | OfficeHoursListCreateAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | features/weekly-twitches/api/weekly-twitches.api.ts:108, features/weekly-twitches/api/weekly-twitches.api.ts:116 | — | — |
| GET | `/api/v1/dashboard/media-content/office-hours/<str:record_id>/` | OfficeHoursDetailAPI | **Public** | any logged-in | features/weekly-twitches/api/weekly-twitches.api.ts:72 | — | — |
| PATCH | `/api/v1/dashboard/media-content/office-hours/<str:record_id>/` | OfficeHoursDetailAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | features/weekly-twitches/api/weekly-twitches.api.ts:135, features/weekly-twitches/api/weekly-twitches.api.ts:143 | — | — |
| DELETE | `/api/v1/dashboard/media-content/office-hours/<str:record_id>/` | OfficeHoursDetailAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | features/weekly-twitches/api/weekly-twitches.api.ts:157 | — | — |
| GET | `/api/v1/dashboard/media-content/salt-mango-tree/` | SaltMangoTreeListCreateAPI | **Public** | any logged-in | features/weekly-twitches/api/weekly-twitches.api.ts:169 | — | — |
| POST | `/api/v1/dashboard/media-content/salt-mango-tree/` | SaltMangoTreeListCreateAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | features/weekly-twitches/api/weekly-twitches.api.ts:185 | — | — |
| GET | `/api/v1/dashboard/media-content/salt-mango-tree/<str:record_id>/` | SaltMangoTreeDetailAPI | **Public** | any logged-in | features/weekly-twitches/api/weekly-twitches.api.ts:177 | — | — |
| PATCH | `/api/v1/dashboard/media-content/salt-mango-tree/<str:record_id>/` | SaltMangoTreeDetailAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | features/weekly-twitches/api/weekly-twitches.api.ts:196 | — | — |
| DELETE | `/api/v1/dashboard/media-content/salt-mango-tree/<str:record_id>/` | SaltMangoTreeDetailAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | features/weekly-twitches/api/weekly-twitches.api.ts:204 | — | — |
| GET | `/api/v1/dashboard/media-content/inspiration-station/` | InspirationStationListCreateAPI | **Public** | any logged-in | features/weekly-twitches/api/weekly-twitches.api.ts:216 | — | — |
| POST | `/api/v1/dashboard/media-content/inspiration-station/` | InspirationStationListCreateAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | features/weekly-twitches/api/weekly-twitches.api.ts:232 | — | — |
| GET | `/api/v1/dashboard/media-content/inspiration-station/<str:record_id>/` | InspirationStationDetailAPI | **Public** | any logged-in | features/weekly-twitches/api/weekly-twitches.api.ts:224 | — | — |
| PATCH | `/api/v1/dashboard/media-content/inspiration-station/<str:record_id>/` | InspirationStationDetailAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | features/weekly-twitches/api/weekly-twitches.api.ts:243 | — | — |
| DELETE | `/api/v1/dashboard/media-content/inspiration-station/<str:record_id>/` | InspirationStationDetailAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | features/weekly-twitches/api/weekly-twitches.api.ts:251 | — | — |
| GET | `/api/v1/dashboard/media-content/grab-your-superpowers/` | GrabYourSuperpowersListCreateAPI | **Public** | any logged-in | features/weekly-twitches/api/weekly-twitches.api.ts:261 | — | — |
| POST | `/api/v1/dashboard/media-content/grab-your-superpowers/` | GrabYourSuperpowersListCreateAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | features/weekly-twitches/api/weekly-twitches.api.ts:277 | — | — |
| GET | `/api/v1/dashboard/media-content/grab-your-superpowers/<str:record_id>/` | GrabYourSuperpowersDetailAPI | **Public** | any logged-in | features/weekly-twitches/api/weekly-twitches.api.ts:269 | — | — |
| PATCH | `/api/v1/dashboard/media-content/grab-your-superpowers/<str:record_id>/` | GrabYourSuperpowersDetailAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | features/weekly-twitches/api/weekly-twitches.api.ts:294 | — | — |
| DELETE | `/api/v1/dashboard/media-content/grab-your-superpowers/<str:record_id>/` | GrabYourSuperpowersDetailAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | features/weekly-twitches/api/weekly-twitches.api.ts:308 | — | — |
| POST | `/api/v1/dashboard/media-content/bulk/import/` | MediaContentBulkImportAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | — | — | — |
| GET | `/api/v1/dashboard/media-content/bulk/export/<str:content_type>/` | MediaContentBulkExportAPI | Login | Admin, Associate, District Lead, IG Lead, Zonal Lead | — | — | — |

#### `dashboard/mentor` (71 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/mentor/opportunities/` | IgOpportunityListCreateAPI | Login | Mentor | — | — | — |
| POST | `/api/v1/dashboard/mentor/opportunities/` | IgOpportunityListCreateAPI | Login | Mentor | — | — | — |
| GET | `/api/v1/dashboard/mentor/opportunities/public/` | PublicIgOpportunityListAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/mentor/opportunities/<str:opportunity_id>/` | IgOpportunityDetailAPI | Login | Mentor | — | — | — |
| PATCH | `/api/v1/dashboard/mentor/opportunities/<str:opportunity_id>/` | IgOpportunityDetailAPI | Login | Mentor | — | — | — |
| DELETE | `/api/v1/dashboard/mentor/opportunities/<str:opportunity_id>/` | IgOpportunityDetailAPI | Login | Mentor | — | — | — |
| POST | `/api/v1/dashboard/mentor/opportunities/<str:opportunity_id>/publish/` | IgOpportunityPublishAPI | Login | Mentor | — | — | — |
| POST | `/api/v1/dashboard/mentor/opportunities/<str:opportunity_id>/close/` | IgOpportunityCloseAPI | Login | Mentor | — | — | — |
| GET | `/api/v1/dashboard/mentor/public/profile/<str:mentor_id>/` | MentorPublicProfileAPI | Login | any logged-in | features/mentor/public/api/public-mentor.api.ts:20 | — | — |
| GET | `/api/v1/dashboard/mentor/public/availability/<str:mentor_id>/` | MentorPublicAvailabilityAPI | Login | any logged-in | features/mentor/public/api/public-mentor.api.ts:35 | — | — |
| GET | `/api/v1/dashboard/mentor/overview/` | MentorOverviewAPI | Login | any logged-in | features/home/api/home.api.ts:48, features/mentor/api/mentor.api.ts:229 | — | — |
| GET | `/api/v1/dashboard/mentor/persona/current/` | PersonaCurrentAPI | Login | any logged-in | features/mentor/api/mentor.api.ts:268 | — | — |
| POST | `/api/v1/dashboard/mentor/register/` | MentorRegistrationAPI | Login | any logged-in | features/mentor/onboarding/api/onboarding.api.ts:27 | — | — |
| PATCH | `/api/v1/dashboard/mentor/register/` | MentorRegistrationAPI | Login | any logged-in | features/mentor/onboarding/api/onboarding.api.ts:41 | — | — |
| GET | `/api/v1/dashboard/mentor/status/` | MentorStatusAPI | Login | any logged-in | features/mentor/onboarding/api/onboarding.api.ts:14 | — | — |
| GET | `/api/v1/dashboard/mentor/profile/` | MentorProfileAPI | Login | Mentor | features/mentor/onboarding/api/onboarding.api.ts:53 | — | — |
| PATCH | `/api/v1/dashboard/mentor/profile/` | MentorProfileAPI | Login | Mentor | features/mentor/onboarding/api/onboarding.api.ts:66 | — | — |
| GET | `/api/v1/dashboard/mentor/activity/` | MentorActivityListAPI | Login | none observed | — | AttributeError: 'list' object has no attribute '_fields' (campuslead,leadenabler,mentor) | H-26 |
| GET | `/api/v1/dashboard/mentor/analytics/personal/` | MentorPersonalAnalyticsAPI | Login | Mentor | features/mentor/api/mentor.api.ts:410 | — | — |
| GET | `/api/v1/dashboard/mentor/profile/completion/` | MentorProfileCompletionAPI | Login | Mentor | features/mentor/api/mentor.api.ts:339 | — | — |
| GET | `/api/v1/dashboard/mentor/list/` | MentorListAPI | Login | Admin | — | — | — |
| GET | `/api/v1/dashboard/mentor/roster/` | MentorRosterAPI | Login | Admin | — | — | — |
| GET | `/api/v1/dashboard/mentor/change-requests/` | MentorChangeRequestListAPI | Login | Admin | — | — | — |
| PATCH | `/api/v1/dashboard/mentor/verify/<str:mentor_id>/` | MentorVerifyAPI | Login | Admin, IG Lead, Mentor | features/mentor/admin/api/mentor-verify.api.ts:149 | — | — |
| GET | `/api/v1/dashboard/mentor/detail/<str:mentor_id>/` | MentorDetailAPI | Login | Admin | features/mentor/admin/api/mentor-verify.api.ts:136 | — | — |
| POST | `/api/v1/dashboard/mentor/session/create/` | MentorSessionCreateAPI | Login | Mentor | features/mentor/sessions/api/sessions.api.ts:158 | — | — |
| GET | `/api/v1/dashboard/mentor/session/list/` | MentorSessionListAPI | Login | Mentor | features/mentor/sessions/api/sessions.api.ts:182 | — | — |
| GET | `/api/v1/dashboard/mentor/session/list/<str:session_id>/` | MentorSessionListAPI | Login | Mentor | features/mentor/sessions/api/sessions.api.ts:196 | — | — |
| PATCH | `/api/v1/dashboard/mentor/session/update/<str:session_id>/` | MentorSessionUpdateAPI | Login | Mentor | features/mentor/sessions/api/sessions.api.ts:209 | — | — |
| DELETE | `/api/v1/dashboard/mentor/session/update/<str:session_id>/` | MentorSessionUpdateAPI | Login | Mentor | features/mentor/sessions/api/sessions.api.ts:219 | — | — |
| POST | `/api/v1/dashboard/mentor/session/complete/<str:session_id>/` | MentorSessionCompleteAPI | Login | Mentor | features/mentor/sessions/api/sessions.api.ts:229 | — | — |
| GET | `/api/v1/dashboard/mentor/session/available/` | AvailableSessionListAPI | Login | any logged-in | features/mentor/sessions/api/sessions.api.ts:247 | — | — |
| GET | `/api/v1/dashboard/mentor/session/admin/list/` | AdminSessionListAPI | Login | Admin | features/mentor/sessions/api/sessions.api.ts:278 | — | — |
| PATCH | `/api/v1/dashboard/mentor/session/admin/verify/<str:session_id>/` | AdminSessionVerifyAPI | Login | Admin | features/home/api/home.api.ts:231, features/mentor/sessions/api/sessions.api.ts:301 | — | — |
| GET | `/api/v1/dashboard/mentor/availability/` | MentorAvailabilitySlotAPI | Login | Mentor | features/mentor/api/mentor.api.ts:102, features/mentor/api/mentor.api.ts:130 (+1) | — | — |
| POST | `/api/v1/dashboard/mentor/availability/` | MentorAvailabilitySlotAPI | Login | Mentor | features/mentor/api/mentor.api.ts:175, features/mentor/api/mentor.api.ts:203 | — | — |
| PATCH | `/api/v1/dashboard/mentor/availability/` | MentorAvailabilitySlotAPI | Login | none observed | — | TypeError: MentorAvailabilitySlotAPI.patch() missing 1 required positi (mentor) | — |
| DELETE | `/api/v1/dashboard/mentor/availability/` | MentorAvailabilitySlotAPI | Login | none observed | — | TypeError: MentorAvailabilitySlotAPI.delete() missing 1 required posit (mentor) | — |
| GET | `/api/v1/dashboard/mentor/availability/<str:slot_id>/` | MentorAvailabilitySlotAPI | Login | Mentor | — | — | — |
| POST | `/api/v1/dashboard/mentor/availability/<str:slot_id>/` | MentorAvailabilitySlotAPI | Login | none observed | — | TypeError: MentorAvailabilitySlotAPI.post() got an unexpected keyword  (mentor) | — |
| PATCH | `/api/v1/dashboard/mentor/availability/<str:slot_id>/` | MentorAvailabilitySlotAPI | Login | Mentor | — | — | — |
| DELETE | `/api/v1/dashboard/mentor/availability/<str:slot_id>/` | MentorAvailabilitySlotAPI | Login | Mentor | features/mentor/api/mentor.api.ts:153 | — | — |
| POST | `/api/v1/dashboard/mentor/session/participation/join/<str:session_id>/` | SessionJoinAPI | Login | any logged-in | features/mentor/mentees/api/mentees.api.ts:122, features/mentor/sessions/api/sessions.api.ts:313 | — | — |
| GET | `/api/v1/dashboard/mentor/session/participant/history/` | UserSessionHistoryAPI | Login | any logged-in | features/mentor/mentees/api/mentees.api.ts:25, features/mentor/mentees/api/mentees.api.ts:78 (+1) | — | — |
| POST | `/api/v1/dashboard/mentor/session/participant/add/<str:session_id>/` | MentorAddParticipantAPI | Login | Mentor | features/mentor/sessions/api/sessions.api.ts:371 | — | — |
| GET | `/api/v1/dashboard/mentor/session/participant/list/<str:session_id>/` | MentorParticipantListAPI | Login | none observed | features/mentor/mentees/api/mentees.api.ts:91, features/mentor/sessions/api/sessions.api.ts:356 | — | — |
| PATCH | `/api/v1/dashboard/mentor/session/participant/update/<str:link_id>/` | MentorParticipantUpdateAPI | Login | Mentor | features/mentor/mentees/api/mentees.api.ts:107, features/mentor/sessions/api/sessions.api.ts:384 | — | — |
| PATCH | `/api/v1/dashboard/mentor/session/participant/feedback/<str:session_id>/` | ParticipantFeedbackAPI | Login | none observed | features/mentor/mentees/api/mentees.api.ts:66, features/mentor/sessions/api/sessions.api.ts:397 | — | — |
| GET | `/api/v1/dashboard/mentor/tasks/ig-dropdown/` | MentorIGDropdownAPI | Login | Mentor | features/mentor/tasks/api/mentor-tasks.api.ts:42 | — | — |
| GET | `/api/v1/dashboard/mentor/tasks/` | MentorTaskListCreateAPI | Login | Mentor | — | — | — |
| POST | `/api/v1/dashboard/mentor/tasks/` | MentorTaskListCreateAPI | Login | Mentor | features/mentor/tasks/api/mentor-tasks.api.ts:96 | — | — |
| GET | `/api/v1/dashboard/mentor/tasks/<str:task_id>/` | MentorTaskDetailAPI | Login | Mentor | features/mentor/tasks/api/mentor-tasks.api.ts:106 | — | — |
| PUT | `/api/v1/dashboard/mentor/tasks/<str:task_id>/` | MentorTaskDetailAPI | Login | Mentor | features/mentor/tasks/api/mentor-tasks.api.ts:120 | — | — |
| DELETE | `/api/v1/dashboard/mentor/tasks/<str:task_id>/` | MentorTaskDetailAPI | Login | Mentor | features/mentor/tasks/api/mentor-tasks.api.ts:130 | — | — |
| POST | `/api/v1/dashboard/mentor/admin/assign/` | AdminAssignMentorAPI | Login | Admin | features/mentor/admin/api/mentor-assign.api.ts:21 | — | — |
| DELETE | `/api/v1/dashboard/mentor/admin/assign/` | AdminAssignMentorAPI | Login | none observed | — | TypeError: AdminAssignMentorAPI.delete() missing 1 required positional (admin) | — |
| POST | `/api/v1/dashboard/mentor/admin/assign/<str:user_muid>/` | AdminAssignMentorAPI | Login | none observed | — | TypeError: AdminAssignMentorAPI.post() got an unexpected keyword argum (admin) | — |
| DELETE | `/api/v1/dashboard/mentor/admin/assign/<str:user_muid>/` | AdminAssignMentorAPI | Login | Admin | — | — | — |
| POST | `/api/v1/dashboard/mentor/admin/deactivate/<str:user_mentor_id>/` | MentorDeactivationAPI | Login | Admin | features/mentor/admin/api/mentor-assign.api.ts:50 | — | — |
| POST | `/api/v1/dashboard/mentor/admin/reactivate/<str:user_mentor_id>/` | MentorReactivationAPI | Login | Admin | features/mentor/admin/api/mentor-assign.api.ts:60 | — | — |
| GET | `/api/v1/dashboard/mentor/<str:mentor_id>/preferred-igs/` | MentorPreferredIgAPI | Login | Mentor | — | — | — |
| PATCH | `/api/v1/dashboard/mentor/<str:mentor_id>/preferred-igs/` | MentorPreferredIgAPI | Login | Mentor | — | — | — |
| GET | `/api/v1/dashboard/mentor/<str:mentor_id>/grants/` | MentorScopeGrantListAPI | Login | Admin | features/mentor/admin/api/mentor-grants.api.ts:12 | — | — |
| DELETE | `/api/v1/dashboard/mentor/<str:mentor_id>/grants/<str:grant_id>/` | MentorScopeGrantRevokeAPI | Login | Admin | features/mentor/admin/api/mentor-grants.api.ts:25 | — | — |
| POST | `/api/v1/dashboard/mentor/change-company/` | MentorChangeCompanyAPI | Login | Mentor | features/mentor/api/mentor.api.ts:304 | — | — |
| POST | `/api/v1/dashboard/mentor/session/student/request/` | StudentSessionRequestAPI | Login | any logged-in | features/mentor/sessions/api/student-requests.api.ts:52 | — | — |
| GET | `/api/v1/dashboard/mentor/session/student/my-requests/` | StudentSessionRequestListAPI | Login | any logged-in | features/mentor/sessions/api/student-requests.api.ts:74 | — | — |
| GET | `/api/v1/dashboard/mentor/session/student-requests/` | MentorStudentRequestListAPI | Login | Mentor | features/mentor/sessions/api/student-requests.api.ts:97 | — | H-06 |
| PATCH | `/api/v1/dashboard/mentor/session/student-requests/<str:session_id>/verify/` | MentorStudentRequestVerifyAPI | Login | Mentor | features/mentor/sessions/api/student-requests.api.ts:113 | — | H-06 |
| GET | `/api/v1/dashboard/mentor/persona/status/` | PersonaStatusAPI | Login | Mentor | features/mentor/api/mentor.api.ts:278 | — | — |
| POST | `/api/v1/dashboard/mentor/persona/switch/` | PersonaSwitchAPI | Login | Mentor | features/mentor/api/mentor.api.ts:290 | — | — |

#### `dashboard/organisation` (56 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/dashboard/organisation/institutes/create/` | InstitutionPostUpdateDeleteAPI | Login | Admin | features/organizations/api/organizations.api.ts:56 | — | — |
| PUT | `/api/v1/dashboard/organisation/institutes/create/` | InstitutionPostUpdateDeleteAPI | Login | none observed | — | TypeError: InstitutionPostUpdateDeleteAPI.put() missing 1 required pos (admin) | — |
| DELETE | `/api/v1/dashboard/organisation/institutes/create/` | InstitutionPostUpdateDeleteAPI | Login | none observed | — | TypeError: InstitutionPostUpdateDeleteAPI.delete() missing 1 required  (admin) | — |
| POST | `/api/v1/dashboard/organisation/institutes/edit/<str:org_code>/` | InstitutionPostUpdateDeleteAPI | Login | none observed | — | TypeError: InstitutionPostUpdateDeleteAPI.post() got an unexpected key (admin) | — |
| PUT | `/api/v1/dashboard/organisation/institutes/edit/<str:org_code>/` | InstitutionPostUpdateDeleteAPI | Login | Admin | features/organizations/api/organizations.api.ts:75 | — | — |
| DELETE | `/api/v1/dashboard/organisation/institutes/edit/<str:org_code>/` | InstitutionPostUpdateDeleteAPI | Login | Admin | — | — | — |
| POST | `/api/v1/dashboard/organisation/institutes/delete/<str:org_code>/` | InstitutionPostUpdateDeleteAPI | Login | none observed | — | TypeError: InstitutionPostUpdateDeleteAPI.post() got an unexpected key (admin) | L-38 |
| PUT | `/api/v1/dashboard/organisation/institutes/delete/<str:org_code>/` | InstitutionPostUpdateDeleteAPI | Login | Admin | — | — | L-38 |
| DELETE | `/api/v1/dashboard/organisation/institutes/delete/<str:org_code>/` | InstitutionPostUpdateDeleteAPI | Login | Admin | features/organizations/api/organizations.api.ts:85 | — | L-38 |
| GET | `/api/v1/dashboard/organisation/institutes/<str:org_type>/csv/` | InstitutionCSVAPI | Login | Admin | features/organizations/api/organizations.api.ts:95 | — | — |
| GET | `/api/v1/dashboard/organisation/institutes/info/<str:org_code>/` | InstitutionDetailsAPI | Login (anon→500) | Admin | — | IndexError: list index out of range (anon) | L-10 |
| GET | `/api/v1/dashboard/organisation/institutes/prefill/<str:org_code>/` | InstitutionPrefillAPI | Login (anon→500) | Admin | — | IndexError: list index out of range (anon) | L-14, L-10 |
| GET | `/api/v1/dashboard/organisation/institutes/<str:org_type>/` | InstitutionAPI | **Public** | any logged-in | features/events/api/events.api.ts:622, features/manage-users/api/manageUsers.api.ts:270 (+5) | — | — |
| GET | `/api/v1/dashboard/organisation/institutes/<str:org_type>/<str:district_id>/` | InstitutionAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/organisation/institutes/org/affiliation/show/` | AffiliationGetPostUpdateDeleteAPI | Login | Admin | — | — | — |
| POST | `/api/v1/dashboard/organisation/institutes/org/affiliation/show/` | AffiliationGetPostUpdateDeleteAPI | Login | Admin | — | — | — |
| PUT | `/api/v1/dashboard/organisation/institutes/org/affiliation/show/` | AffiliationGetPostUpdateDeleteAPI | Login | none observed | — | TypeError: AffiliationGetPostUpdateDeleteAPI.put() missing 1 required  (admin) | — |
| DELETE | `/api/v1/dashboard/organisation/institutes/org/affiliation/show/` | AffiliationGetPostUpdateDeleteAPI | Login | none observed | — | TypeError: AffiliationGetPostUpdateDeleteAPI.delete() missing 1 requir (admin) | — |
| GET | `/api/v1/dashboard/organisation/institutes/org/affiliation/create/` | AffiliationGetPostUpdateDeleteAPI | Login | Admin | — | — | — |
| POST | `/api/v1/dashboard/organisation/institutes/org/affiliation/create/` | AffiliationGetPostUpdateDeleteAPI | Login | Admin | — | — | — |
| PUT | `/api/v1/dashboard/organisation/institutes/org/affiliation/create/` | AffiliationGetPostUpdateDeleteAPI | Login | none observed | — | TypeError: AffiliationGetPostUpdateDeleteAPI.put() missing 1 required  (admin) | — |
| DELETE | `/api/v1/dashboard/organisation/institutes/org/affiliation/create/` | AffiliationGetPostUpdateDeleteAPI | Login | none observed | — | TypeError: AffiliationGetPostUpdateDeleteAPI.delete() missing 1 requir (admin) | — |
| GET | `/api/v1/dashboard/organisation/institutes/org/affiliation/edit/<str:affiliation_id>/` | AffiliationGetPostUpdateDeleteAPI | Login | none observed | — | TypeError: AffiliationGetPostUpdateDeleteAPI.get() got an unexpected k (admin) | — |
| POST | `/api/v1/dashboard/organisation/institutes/org/affiliation/edit/<str:affiliation_id>/` | AffiliationGetPostUpdateDeleteAPI | Login | none observed | — | TypeError: AffiliationGetPostUpdateDeleteAPI.post() got an unexpected  (admin) | — |
| PUT | `/api/v1/dashboard/organisation/institutes/org/affiliation/edit/<str:affiliation_id>/` | AffiliationGetPostUpdateDeleteAPI | Login | Admin | — | — | — |
| DELETE | `/api/v1/dashboard/organisation/institutes/org/affiliation/edit/<str:affiliation_id>/` | AffiliationGetPostUpdateDeleteAPI | Login | Admin | — | — | — |
| GET | `/api/v1/dashboard/organisation/institutes/org/affiliation/delete/<str:affiliation_id>/` | AffiliationGetPostUpdateDeleteAPI | Login | none observed | — | TypeError: AffiliationGetPostUpdateDeleteAPI.get() got an unexpected k (admin) | — |
| POST | `/api/v1/dashboard/organisation/institutes/org/affiliation/delete/<str:affiliation_id>/` | AffiliationGetPostUpdateDeleteAPI | Login | none observed | — | TypeError: AffiliationGetPostUpdateDeleteAPI.post() got an unexpected  (admin) | — |
| PUT | `/api/v1/dashboard/organisation/institutes/org/affiliation/delete/<str:affiliation_id>/` | AffiliationGetPostUpdateDeleteAPI | Login | Admin | — | — | — |
| DELETE | `/api/v1/dashboard/organisation/institutes/org/affiliation/delete/<str:affiliation_id>/` | AffiliationGetPostUpdateDeleteAPI | Login | Admin | — | — | — |
| GET | `/api/v1/dashboard/organisation/departments/` | DepartmentAPI | Login | Admin | features/organizations/api/departments.api.ts:39 | — | — |
| POST | `/api/v1/dashboard/organisation/departments/` | DepartmentAPI | Login | Admin | — | — | — |
| PUT | `/api/v1/dashboard/organisation/departments/` | DepartmentAPI | Login | none observed | — | TypeError: DepartmentAPI.put() missing 1 required positional argument: (admin) | — |
| DELETE | `/api/v1/dashboard/organisation/departments/` | DepartmentAPI | Login | none observed | — | TypeError: DepartmentAPI.delete() missing 1 required positional argume (admin) | — |
| GET | `/api/v1/dashboard/organisation/departments/create/` | DepartmentAPI | Login | Admin | — | — | — |
| POST | `/api/v1/dashboard/organisation/departments/create/` | DepartmentAPI | Login | Admin | features/organizations/api/departments.api.ts:56 | — | — |
| PUT | `/api/v1/dashboard/organisation/departments/create/` | DepartmentAPI | Login | none observed | — | TypeError: DepartmentAPI.put() missing 1 required positional argument: (admin) | — |
| DELETE | `/api/v1/dashboard/organisation/departments/create/` | DepartmentAPI | Login | none observed | — | TypeError: DepartmentAPI.delete() missing 1 required positional argume (admin) | — |
| GET | `/api/v1/dashboard/organisation/departments/edit/<str:department_id>/` | DepartmentAPI | Login | none observed | — | TypeError: DepartmentAPI.get() got an unexpected keyword argument 'dep (admin) | — |
| POST | `/api/v1/dashboard/organisation/departments/edit/<str:department_id>/` | DepartmentAPI | Login | none observed | — | TypeError: DepartmentAPI.post() got an unexpected keyword argument 'de (admin) | — |
| PUT | `/api/v1/dashboard/organisation/departments/edit/<str:department_id>/` | DepartmentAPI | Login | Admin | features/organizations/api/departments.api.ts:67 | — | — |
| DELETE | `/api/v1/dashboard/organisation/departments/edit/<str:department_id>/` | DepartmentAPI | Login | Admin | — | — | — |
| GET | `/api/v1/dashboard/organisation/departments/delete/<str:department_id>/` | DepartmentAPI | Login | none observed | — | TypeError: DepartmentAPI.get() got an unexpected keyword argument 'dep (admin) | — |
| POST | `/api/v1/dashboard/organisation/departments/delete/<str:department_id>/` | DepartmentAPI | Login | none observed | — | TypeError: DepartmentAPI.post() got an unexpected keyword argument 'de (admin) | — |
| PUT | `/api/v1/dashboard/organisation/departments/delete/<str:department_id>/` | DepartmentAPI | Login | Admin | — | — | — |
| DELETE | `/api/v1/dashboard/organisation/departments/delete/<str:department_id>/` | DepartmentAPI | Login | Admin | features/organizations/api/departments.api.ts:75 | — | — |
| GET | `/api/v1/dashboard/organisation/affiliation/list/` | AffiliationListAPI | Login (anon→500) | Admin | features/organizations/api/organizations.api.ts:116 | IndexError: list index out of range (anon) | L-10 |
| GET | `/api/v1/dashboard/organisation/merge_organizations/<str:organisation_id>/` | OrganizationMergerView | Login | Admin | features/organizations/api/transfer.api.ts:25 | — | H-03, M-06 |
| PATCH | `/api/v1/dashboard/organisation/merge_organizations/<str:organisation_id>/` | OrganizationMergerView | Login | Admin | features/organizations/api/transfer.api.ts:38 | — | H-03, M-06 |
| POST | `/api/v1/dashboard/organisation/karma-type/create/` | OrganizationKarmaTypeGetPostPatchDeleteAPI | Login (anon→500) | any logged-in | — | IndexError: list index out of range (anon) | L-37 |
| POST | `/api/v1/dashboard/organisation/karma-log/create/` | OrganizationKarmaLogGetPostPatchDeleteAPI | Login (anon→500) | any logged-in | — | IndexError: list index out of range (anon) | L-37 |
| GET | `/api/v1/dashboard/organisation/base-template/` | OrganisationBaseTemplateAPI | Login | ? (500) | — | FileNotFoundError: [Errno 2] No such file or directory: './excel-templ (admin,associate,campusiglead,campuslead,) | — |
| POST | `/api/v1/dashboard/organisation/import/` | OrganisationImportAPI | Login | Admin | — | — | L-38 |
| POST | `/api/v1/dashboard/organisation/transfer/` | TransferAPI | **Public** | any logged-in | features/organizations/api/transfer.api.ts:14 | — | C-01 |
| GET | `/api/v1/dashboard/organisation/verify/list/` | UnverifiedOrganizationsListAPI | Login | any logged-in | features/organizations/api/verification.api.ts:28 | — | H-01, H-02, M-05 |
| POST | `/api/v1/dashboard/organisation/verify/<str:uorg_id>/` | VerifyOrganizationAPI | Login | any logged-in | features/organizations/api/verification.api.ts:39 | — | H-01, H-02, M-05 |

#### `dashboard/profile` (32 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/profile/` | UserProfileEditView | Login | any logged-in | features/profile/api/profile.api.ts:69 | — | — |
| PATCH | `/api/v1/dashboard/profile/` | UserProfileEditView | Login | any logged-in | features/profile/api/profile.api.ts:195 | — | M-31 |
| DELETE | `/api/v1/dashboard/profile/` | UserProfileEditView | Login | any logged-in | — | — | M-32 |
| GET | `/api/v1/dashboard/profile/badges/<str:muid>` | BadgesAPI | **Public** | any logged-in | features/profile/api/badges.api.ts:15 | — | L-23 |
| GET | `/api/v1/dashboard/profile/user-profile/` | UserProfileAPI | Login | any logged-in | features/profile/api/profile.api.ts:60 | — | L-23 |
| GET | `/api/v1/dashboard/profile/ig-edit/` | UserIgEditView | Login | any logged-in | — | — | L-28 |
| PATCH | `/api/v1/dashboard/profile/ig-edit/` | UserIgEditView | Login | any logged-in | features/profile/api/profile.api.ts:441 | — | L-28 |
| GET | `/api/v1/dashboard/profile/user-profile/<str:muid>/` | UserProfileAPI | **Public** | any logged-in | features/auth/api/auth.api.ts:141, features/campus-manage/api/campus-manage.api.ts:542 (+1) | — | L-23 |
| GET | `/api/v1/dashboard/profile/user-log/` | UserLogAPI | Login | any logged-in | features/profile/api/profile.api.ts:91 | — | L-23 |
| GET | `/api/v1/dashboard/profile/user-log/<str:muid>/` | UserLogAPI | **Public** | any logged-in | features/profile/api/profile.api.ts:100 | — | L-23 |
| GET | `/api/v1/dashboard/profile/share-user-profile/` | ShareUserProfileAPI | Login | ? (500) | — | AssertionError: Expected a `Response`, `HttpResponse` or `HttpStreamin (admin,associate,campusiglead,campuslead,) | L-25 |
| PUT | `/api/v1/dashboard/profile/share-user-profile/` | ShareUserProfileAPI | Login | any logged-in | features/profile/api/profile.api.ts:166 | — | — |
| GET | `/api/v1/dashboard/profile/share-user-profile/<str:uuid>/` | ShareUserProfileAPI | Login | any logged-in | — | — | L-25 |
| PUT | `/api/v1/dashboard/profile/share-user-profile/<str:uuid>/` | ShareUserProfileAPI | Login | ? (500) | — | TypeError: ShareUserProfileAPI.put() got an unexpected keyword argumen (admin,associate,campusiglead,campuslead,) | — |
| GET | `/api/v1/dashboard/profile/rank/<str:muid>/` | UserRankAPI | **Public** | any logged-in | — | — | L-23, L-24 |
| GET | `/api/v1/dashboard/profile/get-user-levels/` | UserLevelsAPI | Login | any logged-in | features/profile/api/profile.api.ts:113 | — | L-23 |
| GET | `/api/v1/dashboard/profile/get-user-levels/<str:muid>/` | UserLevelsAPI | **Public** | any logged-in | features/mujourney/api/mujourney.api.ts:49, features/profile/api/profile.api.ts:124 | — | L-23 |
| PUT | `/api/v1/dashboard/profile/socials/edit/` | SocialsAPI | Login | any logged-in | features/profile/api/profile.api.ts:155 | — | M-30 |
| GET | `/api/v1/dashboard/profile/socials/` | GetSocialsAPI | Login | any logged-in | features/profile/api/profile.api.ts:137 | — | L-23 |
| GET | `/api/v1/dashboard/profile/socials/<str:muid>/` | GetSocialsAPI | **Public** | any logged-in | features/profile/api/profile.api.ts:146 | — | L-23 |
| GET | `/api/v1/dashboard/profile/qrcode-get/<str:uuid>/` | QrcodeRetrieveAPI | **Public** | any logged-in | — | — | L-23 |
| POST | `/api/v1/dashboard/profile/change-password/` | ResetPasswordAPI | Login | any logged-in | — | — | L-26 |
| GET | `/api/v1/dashboard/profile/userterm-approved/<str:muid>/` | UsertermAPI | **Public** | any logged-in | — | — | L-02 |
| POST | `/api/v1/dashboard/profile/userterm-approved/<str:muid>/` | UsertermAPI | **Public** | any logged-in | — | — | L-02 |
| GET | `/api/v1/dashboard/profile/karma-feed/` | KarmaFeedAPI | **Public** | any logged-in | features/home/api/home.api.ts:36 | — | L-27 |
| GET | `/api/v1/dashboard/profile/user-level-feed/` | UserLevelFeedAPI | Login | any logged-in | features/mujourney/api/mujourney.api.ts:63 | — | M-29 |
| GET | `/api/v1/dashboard/profile/cover-pic/` | UserProfileCoverView | Login | any logged-in | features/profile/api/profile.api.ts:246 | — | — |
| POST | `/api/v1/dashboard/profile/cover-pic/` | UserProfileCoverView | Login | any logged-in | — | — | — |
| DELETE | `/api/v1/dashboard/profile/cover-pic/` | UserProfileCoverView | Login | any logged-in | features/profile/api/profile.api.ts:297 | — | — |
| GET | `/api/v1/dashboard/profile/user-preferences/` | UserPreferencesAPI | Login | any logged-in | — | — | — |
| PATCH | `/api/v1/dashboard/profile/user-preferences/` | UserPreferencesAPI | Login | ? (500) | — | AttributeError: module 'api.dashboard.profile.profile_serializer' has  (admin,associate,campusiglead,campuslead,) | M-48 |
| GET | `/api/v1/dashboard/profile/permute/<str:muid>/` | UserPermuteAPI | **Public** | any logged-in | — | — | L-23 |

#### `dashboard/projects` (22 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/projects/` | ProjectsAPIView | Login | any logged-in | features/projects/api/projects.api.ts:35, features/projects/api/projects.api.ts:57 | — | — |
| POST | `/api/v1/dashboard/projects/` | ProjectsAPIView | Login | any logged-in | — | — | L-40 |
| GET | `/api/v1/dashboard/projects/<uuid:pk>/` | ProjectDetailAPIView | Login | ? (500) | features/projects/api/projects.api.ts:74 | DoesNotExist: Project matching query does not exist. (admin,associate,campusiglead,campuslead,) | L-12 |
| PUT | `/api/v1/dashboard/projects/<uuid:pk>/` | ProjectDetailAPIView | Login | ? (500) | — | DoesNotExist: Project matching query does not exist. (admin,associate,campusiglead,campuslead,) | L-12 |
| DELETE | `/api/v1/dashboard/projects/<uuid:pk>/` | ProjectDetailAPIView | Login | any logged-in | features/projects/api/projects.api.ts:149 | — | L-12 |
| PATCH | `/api/v1/dashboard/projects/<uuid:pk>/status/` | ProjectStatusAPI | Login | any logged-in | features/projects/api/projects.api.ts:160 | — | — |
| GET | `/api/v1/dashboard/projects/<uuid:project_id>/members/` | ProjectMemberAPI | Login | any logged-in | features/projects/api/projects.api.ts:169 | — | — |
| POST | `/api/v1/dashboard/projects/<uuid:project_id>/members/` | ProjectMemberAPI | Login | none observed | features/projects/api/projects.api.ts:180 | — | — |
| DELETE | `/api/v1/dashboard/projects/<uuid:project_id>/members/` | ProjectMemberAPI | Login | ? (500) | — | TypeError: ProjectMemberAPI.delete() missing 1 required positional arg (admin,associate,campusiglead,campuslead,) | — |
| GET | `/api/v1/dashboard/projects/<uuid:project_id>/members/<uuid:pk>/` | ProjectMemberAPI | Login | ? (500) | — | TypeError: ProjectMemberAPI.get() got an unexpected keyword argument ' (admin,associate,campusiglead,campuslead,) | — |
| POST | `/api/v1/dashboard/projects/<uuid:project_id>/members/<uuid:pk>/` | ProjectMemberAPI | Login | ? (500) | — | TypeError: ProjectMemberAPI.post() got an unexpected keyword argument  (admin,associate,campusiglead,campuslead,) | — |
| DELETE | `/api/v1/dashboard/projects/<uuid:project_id>/members/<uuid:pk>/` | ProjectMemberAPI | Login | none observed | features/projects/api/projects.api.ts:192 | — | — |
| POST | `/api/v1/dashboard/projects/vote/` | ProjectVoteAPI | Login | any logged-in | features/projects/api/projects.api.ts:203 | — | — |
| DELETE | `/api/v1/dashboard/projects/vote/` | ProjectVoteAPI | Login | ? (500) | — | TypeError: ProjectVoteAPI.delete() missing 1 required positional argum (admin,associate,campusiglead,campuslead,) | — |
| POST | `/api/v1/dashboard/projects/vote/<uuid:pk>/` | ProjectVoteAPI | Login | ? (500) | — | TypeError: ProjectVoteAPI.post() got an unexpected keyword argument 'p (admin,associate,campusiglead,campuslead,) | — |
| DELETE | `/api/v1/dashboard/projects/vote/<uuid:pk>/` | ProjectVoteAPI | Login | any logged-in | features/projects/api/projects.api.ts:212 | — | — |
| POST | `/api/v1/dashboard/projects/comment/` | ProjectCommentAPI | Login | any logged-in | features/projects/api/projects.api.ts:220 | — | — |
| PUT | `/api/v1/dashboard/projects/comment/` | ProjectCommentAPI | Login | ? (500) | — | TypeError: ProjectCommentAPI.put() missing 1 required positional argum (admin,associate,campusiglead,campuslead,) | — |
| DELETE | `/api/v1/dashboard/projects/comment/` | ProjectCommentAPI | Login | ? (500) | — | TypeError: ProjectCommentAPI.delete() missing 1 required positional ar (admin,associate,campusiglead,campuslead,) | — |
| POST | `/api/v1/dashboard/projects/comment/<uuid:pk>/` | ProjectCommentAPI | Login | ? (500) | — | TypeError: ProjectCommentAPI.post() got an unexpected keyword argument (admin,associate,campusiglead,campuslead,) | — |
| PUT | `/api/v1/dashboard/projects/comment/<uuid:pk>/` | ProjectCommentAPI | Login | any logged-in | — | — | — |
| DELETE | `/api/v1/dashboard/projects/comment/<uuid:pk>/` | ProjectCommentAPI | Login | any logged-in | features/projects/api/projects.api.ts:229 | — | — |

#### `dashboard/referral` (2 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/referral/` | ReferralListAPI | Login | any logged-in | — | — | — |
| POST | `/api/v1/dashboard/referral/send-referral/` | Referral | Login | any logged-in | — | — | M-45 |

#### `dashboard/roles` (30 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/roles/user-role/<str:role_id>/` | UserRoleSearchAPI | Login | Admin | — | — | M-02, M-03 |
| GET | `/api/v1/dashboard/roles/base-template/` | RoleBaseTemplateAPI | Login | ? (500) | features/manage-roles/api/manage-roles.api.ts:222 | FileNotFoundError: [Errno 2] No such file or directory: './excel-templ (admin,associate,campusiglead,campuslead,) | L-29 |
| GET | `/api/v1/dashboard/roles/bulk-assign/` | UserRoleLinkManagement | Login | none observed | — | TypeError: UserRoleLinkManagement.get() missing 1 required positional  (admin) | — |
| POST | `/api/v1/dashboard/roles/bulk-assign/` | UserRoleLinkManagement | Login | none observed | — | TypeError: UserRoleLinkManagement.post() missing 1 required positional (admin) | — |
| PUT | `/api/v1/dashboard/roles/bulk-assign/` | UserRoleLinkManagement | Login | none observed | — | TypeError: UserRoleLinkManagement.put() missing 1 required positional  (admin) | — |
| PATCH | `/api/v1/dashboard/roles/bulk-assign/` | UserRoleLinkManagement | Login | none observed | — | TypeError: UserRoleLinkManagement.patch() missing 1 required positiona (admin) | — |
| GET | `/api/v1/dashboard/roles/bulk-assign/<str:role_id>/` | UserRoleLinkManagement | Login | Admin | features/manage-roles/api/manage-roles.api.ts:167 | — | — |
| POST | `/api/v1/dashboard/roles/bulk-assign/<str:role_id>/` | UserRoleLinkManagement | Login | Admin | features/manage-roles/api/manage-roles.api.ts:201 | — | — |
| PUT | `/api/v1/dashboard/roles/bulk-assign/<str:role_id>/` | UserRoleLinkManagement | Login | Admin | features/manage-roles/api/manage-roles.api.ts:181 | — | — |
| PATCH | `/api/v1/dashboard/roles/bulk-assign/<str:role_id>/` | UserRoleLinkManagement | Login | none observed | features/manage-roles/api/manage-roles.api.ts:212 | TypeError: 'NoneType' object is not iterable (admin) | M-02, L-29 |
| POST | `/api/v1/dashboard/roles/bulk-assign-excel/` | UserRoleBulkAssignAPI | Login | Admin | features/manage-roles/api/manage-roles.api.ts:243 | — | M-36 |
| POST | `/api/v1/dashboard/roles/user-role/` | UserRole | Login | Admin | features/manage-roles/api/manage-roles.api.ts:122, features/manage-users/api/manageUsers.api.ts:132 (+1) | — | M-02, M-03 |
| DELETE | `/api/v1/dashboard/roles/user-role/` | UserRole | Login | Admin | features/manage-roles/api/manage-roles.api.ts:137 | — | M-02, M-03 |
| GET | `/api/v1/dashboard/roles/` | RoleAPI | Login | Admin | features/manage-roles/api/manage-roles.api.ts:35 | — | M-04 |
| POST | `/api/v1/dashboard/roles/` | RoleAPI | Login | Admin | features/manage-roles/api/manage-roles.api.ts:43 | — | — |
| PATCH | `/api/v1/dashboard/roles/` | RoleAPI | Login | none observed | — | TypeError: RoleAPI.patch() missing 1 required positional argument: 'ro (admin) | — |
| DELETE | `/api/v1/dashboard/roles/` | RoleAPI | Login | none observed | — | TypeError: RoleAPI.delete() missing 1 required positional argument: 'r (admin) | — |
| GET | `/api/v1/dashboard/roles/` | RoleAPI | Login | Admin | features/manage-roles/api/manage-roles.api.ts:35 | — | M-04 |
| POST | `/api/v1/dashboard/roles/` | RoleAPI | Login | Admin | features/manage-roles/api/manage-roles.api.ts:43 | — | — |
| PATCH | `/api/v1/dashboard/roles/` | RoleAPI | Login | none observed | — | TypeError: RoleAPI.patch() missing 1 required positional argument: 'ro (admin) | — |
| DELETE | `/api/v1/dashboard/roles/` | RoleAPI | Login | none observed | — | TypeError: RoleAPI.delete() missing 1 required positional argument: 'r (admin) | — |
| GET | `/api/v1/dashboard/roles/csv/` | RoleManagementCSV | Login | Admin | features/manage-roles/api/manage-roles.api.ts:71 | — | — |
| GET | `/api/v1/dashboard/roles/<str:roles_id>/` | RoleAPI | Login | none observed | — | TypeError: RoleAPI.get() got an unexpected keyword argument 'roles_id' (admin) | M-01 |
| POST | `/api/v1/dashboard/roles/<str:roles_id>/` | RoleAPI | Login | none observed | — | TypeError: RoleAPI.post() got an unexpected keyword argument 'roles_id (admin) | M-01 |
| PATCH | `/api/v1/dashboard/roles/<str:roles_id>/` | RoleAPI | Login | Admin | features/manage-roles/api/manage-roles.api.ts:54 | — | M-01 |
| DELETE | `/api/v1/dashboard/roles/<str:roles_id>/` | RoleAPI | Login | Admin | features/manage-roles/api/manage-roles.api.ts:62 | — | M-01 |
| GET | `/api/v1/dashboard/roles/<str:roles_id>/` | RoleAPI | Login | none observed | — | TypeError: RoleAPI.get() got an unexpected keyword argument 'roles_id' (admin) | M-01 |
| POST | `/api/v1/dashboard/roles/<str:roles_id>/` | RoleAPI | Login | none observed | — | TypeError: RoleAPI.post() got an unexpected keyword argument 'roles_id (admin) | M-01 |
| PATCH | `/api/v1/dashboard/roles/<str:roles_id>/` | RoleAPI | Login | Admin | features/manage-roles/api/manage-roles.api.ts:54 | — | M-01 |
| DELETE | `/api/v1/dashboard/roles/<str:roles_id>/` | RoleAPI | Login | Admin | features/manage-roles/api/manage-roles.api.ts:62 | — | M-01 |

#### `dashboard/skill` (7 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/skill/` | SkillListAPI | Login | any logged-in | features/projects/components/project-skill-picker.tsx:44 | — | — |
| POST | `/api/v1/dashboard/skill/create/` | SkillCreateAPI | Login | Admin | — | — | — |
| GET | `/api/v1/dashboard/skill/dropdown/` | SkillDropdownAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/dashboard/skill/<str:skill_id>/` | SkillDetailAPI | Login | any logged-in | — | — | — |
| PUT | `/api/v1/dashboard/skill/<str:skill_id>/` | SkillDetailAPI | Login | Admin | — | — | — |
| DELETE | `/api/v1/dashboard/skill/<str:skill_id>/` | SkillDetailAPI | Login | Admin | — | — | — |
| GET | `/api/v1/dashboard/skill/<str:skill_id>/tasks/` | SkillTasksAPI | Login | any logged-in | — | — | — |

#### `dashboard/task` (29 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/task/list-task-type/` | TaskTypeCrudAPI | Login | Admin, Company, Mentor | features/company-tasks/api/tasks.api.ts:207, features/mentor/tasks/api/mentor-tasks.api.ts:52 (+1) | — | — |
| POST | `/api/v1/dashboard/task/list-task-type/` | TaskTypeCrudAPI | Login | Admin | features/company-tasks/api/tasks.api.ts:215, features/tasks/api/task-type.api.ts:58 | — | — |
| PUT | `/api/v1/dashboard/task/list-task-type/` | TaskTypeCrudAPI | Login | none observed | features/company-tasks/api/tasks.api.ts:223 | TypeError: TaskTypeCrudAPI.put() missing 1 required positional argumen (admin) | — |
| DELETE | `/api/v1/dashboard/task/list-task-type/` | TaskTypeCrudAPI | Login | none observed | features/company-tasks/api/tasks.api.ts:231 | TypeError: TaskTypeCrudAPI.delete() missing 1 required positional argu (admin) | — |
| GET | `/api/v1/dashboard/task/task-type/<str:task_type_id>/` | TaskTypeCrudAPI | Login | none observed | — | TypeError: TaskTypeCrudAPI.get() got an unexpected keyword argument 't (admin,company,mentor) | — |
| POST | `/api/v1/dashboard/task/task-type/<str:task_type_id>/` | TaskTypeCrudAPI | Login | none observed | — | TypeError: TaskTypeCrudAPI.post() got an unexpected keyword argument ' (admin) | — |
| PUT | `/api/v1/dashboard/task/task-type/<str:task_type_id>/` | TaskTypeCrudAPI | Login | Admin | features/tasks/api/task-type.api.ts:69 | — | — |
| DELETE | `/api/v1/dashboard/task/task-type/<str:task_type_id>/` | TaskTypeCrudAPI | Login | Admin | features/tasks/api/task-type.api.ts:77 | — | — |
| GET | `/api/v1/dashboard/task/channel/` | ChannelDropdownAPI | Login | Admin, Associate, Company, Fellow, Mentor | — | — | — |
| GET | `/api/v1/dashboard/task/ig/` | IGDropdownAPI | Login | Admin, Associate, Company, Fellow, Mentor | — | — | — |
| GET | `/api/v1/dashboard/task/organization/` | OrganizationDropdownAPI | Login | Admin, Associate, Company, Fellow, Mentor | — | — | — |
| GET | `/api/v1/dashboard/task/level/` | LevelDropdownAPI | Login | Admin, Associate, Company, Fellow, Mentor | features/company-jobs/api/eligibility-refs.api.ts:36, features/company-tasks/api/tasks.api.ts:241 (+1) | — | — |
| GET | `/api/v1/dashboard/task/task-types/` | TaskTypesDropDownAPI | Login | Admin, Associate, Company, Fellow, Mentor | — | — | — |
| GET | `/api/v1/dashboard/task/` | TaskListAPI | Login | Admin, Associate, Fellow | — | — | — |
| POST | `/api/v1/dashboard/task/` | TaskListAPI | Login | Admin, Associate, Fellow | features/tasks/api/tasks.api.ts:134 | — | — |
| GET | `/api/v1/dashboard/task/active/` | TaskActiveListAPI | Login | Admin, Associate, Fellow | — | — | — |
| GET | `/api/v1/dashboard/task/inactive/` | TaskInactiveListAPI | Login | Admin, Associate, Fellow | — | — | — |
| GET | `/api/v1/dashboard/task/list/` | TaskPublicListAPI | **Public** | any logged-in | features/company-tasks/api/tasks.api.ts:199, features/tasks/api/tasks.api.ts:102 | — | — |
| GET | `/api/v1/dashboard/task/csv/` | TaskListCSV | Login | Admin, Associate, Fellow | — | — | — |
| POST | `/api/v1/dashboard/task/import/` | ImportTaskListCSV | Login | Admin, Associate, Fellow | features/tasks/api/tasks.api.ts:169 | — | — |
| GET | `/api/v1/dashboard/task/base-template/` | TaskBaseTemplateAPI | Login | none observed | — | FileNotFoundError: [Errno 2] No such file or directory: './excel-templ (admin,associate,fellow) | — |
| GET | `/api/v1/dashboard/task/events/` | EventDropDownApi | Login | Admin | — | — | — |
| GET | `/api/v1/dashboard/task/pending/` | AdminTaskApprovalAPI | Login | Admin | — | — | — |
| PATCH | `/api/v1/dashboard/task/pending/` | AdminTaskApprovalAPI | Login | none observed | — | TypeError: AdminTaskApprovalAPI.patch() missing 1 required positional  (admin) | — |
| GET | `/api/v1/dashboard/task/<str:task_id>/review/` | AdminTaskApprovalAPI | Login | none observed | — | TypeError: AdminTaskApprovalAPI.get() got an unexpected keyword argume (admin) | — |
| PATCH | `/api/v1/dashboard/task/<str:task_id>/review/` | AdminTaskApprovalAPI | Login | Admin | features/tasks/api/task-verification.api.ts:59 | — | — |
| GET | `/api/v1/dashboard/task/<str:task_id>/` | TaskAPI | Login | Admin, Associate, Fellow | features/tasks/api/tasks.api.ts:118 | — | — |
| PUT | `/api/v1/dashboard/task/<str:task_id>/` | TaskAPI | Login | Admin, Associate, Fellow | features/tasks/api/tasks.api.ts:148 | — | — |
| DELETE | `/api/v1/dashboard/task/<str:task_id>/` | TaskAPI | Login | Admin, Associate, Fellow | features/tasks/api/tasks.api.ts:159 | — | M-39 |

#### `dashboard/user` (34 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/user/preferences/` | UserPreferencesAPI | Login | any logged-in | features/profile/api/profile.api.ts:171 | — | — |
| PATCH | `/api/v1/dashboard/user/preferences/` | UserPreferencesAPI | Login | any logged-in | features/profile/api/profile.api.ts:182 | — | — |
| GET | `/api/v1/dashboard/user/search/` | UserSearchAPI | **Public** | any logged-in | features/events/api/events.api.ts:613, features/projects/components/project-member-picker.tsx:40 (+2) | — | M-15 |
| GET | `/api/v1/dashboard/user/verification/` | UserVerificationAPI | Login | Admin | features/role-verification/api/role-verification.api.ts:39 | — | H-07, L-12, L-22 |
| PATCH | `/api/v1/dashboard/user/verification/` | UserVerificationAPI | Login | none observed | — | TypeError: UserVerificationAPI.patch() missing 1 required positional a (admin) | H-07, L-12, L-22 |
| DELETE | `/api/v1/dashboard/user/verification/` | UserVerificationAPI | Login | none observed | — | TypeError: UserVerificationAPI.delete() missing 1 required positional  (admin) | H-07, L-12, L-22 |
| GET | `/api/v1/dashboard/user/verification/csv/` | UserVerificationCSV | Login | Admin | — | — | H-07, L-12, L-22, M-35 |
| GET | `/api/v1/dashboard/user/verification/<str:link_id>/` | UserVerificationAPI | Login | none observed | — | TypeError: UserVerificationAPI.get() got an unexpected keyword argumen (admin) | H-07, L-12, L-22 |
| PATCH | `/api/v1/dashboard/user/verification/<str:link_id>/` | UserVerificationAPI | Login | none observed | features/role-verification/api/role-verification.api.ts:51 | DoesNotExist: UserRoleLink matching query does not exist. (admin) | H-07, L-12, L-22 |
| DELETE | `/api/v1/dashboard/user/verification/<str:link_id>/` | UserVerificationAPI | Login | none observed | features/role-verification/api/role-verification.api.ts:59 | DoesNotExist: UserRoleLink matching query does not exist. (admin) | H-07, L-12, L-22 |
| GET | `/api/v1/dashboard/user/verification/<str:link_id>/` | UserVerificationAPI | Login | none observed | — | TypeError: UserVerificationAPI.get() got an unexpected keyword argumen (admin) | H-07, L-12, L-22 |
| PATCH | `/api/v1/dashboard/user/verification/<str:link_id>/` | UserVerificationAPI | Login | none observed | features/role-verification/api/role-verification.api.ts:51 | DoesNotExist: UserRoleLink matching query does not exist. (admin) | H-07, L-12, L-22 |
| DELETE | `/api/v1/dashboard/user/verification/<str:link_id>/` | UserVerificationAPI | Login | none observed | features/role-verification/api/role-verification.api.ts:59 | DoesNotExist: UserRoleLink matching query does not exist. (admin) | H-07, L-12, L-22 |
| GET | `/api/v1/dashboard/user/organization/` | UserAddOrgAPI | Login (anon→500) | any logged-in | — | IndexError: list index out of range (anon) | H-23, L-10 |
| POST | `/api/v1/dashboard/user/organization/` | UserAddOrgAPI | Login (anon→500) | any logged-in | features/onboarding/api/onboarding.api.ts:93 | IndexError: list index out of range (anon) | H-23, L-10 |
| GET | `/api/v1/dashboard/user/organization/list/` | UserAddOrgAPI | Login (anon→500) | any logged-in | — | IndexError: list index out of range (anon) | H-23, L-10 |
| POST | `/api/v1/dashboard/user/organization/list/` | UserAddOrgAPI | Login (anon→500) | any logged-in | — | IndexError: list index out of range (anon) | H-23, L-10 |
| GET | `/api/v1/dashboard/user/info/` | UserInfoAPI | Login | any logged-in | features/auth/api/auth.api.ts:128, features/events/components/manage-event-detail-view.tsx:172 (+1) | — | M-16 |
| POST | `/api/v1/dashboard/user/forgot-password/` | ForgotPasswordAPI | **Public** | any logged-in | features/auth/api/auth.api.ts:85 | — | M-34, L-17 |
| POST | `/api/v1/dashboard/user/reset-password/verify-token/<str:token>/` | ResetPasswordVerifyTokenAPI | **Public** | any logged-in | features/auth/api/auth.api.ts:98 | — | M-34, L-17 |
| POST | `/api/v1/dashboard/user/reset-password/<str:token>/` | ResetPasswordConfirmAPI | **Public** | any logged-in | features/auth/api/auth.api.ts:113 | — | M-34, L-17 |
| POST | `/api/v1/dashboard/user/profile/update/` | UserProfilePictureView | **Public** | any logged-in | — | — | C-03, L-10 |
| PATCH | `/api/v1/dashboard/user/profile/update/` | UserProfilePictureView | Login (anon→500) | any logged-in | features/profile/api/profile.api.ts:230 | IndexError: list index out of range (anon) | L-10 |
| GET | `/api/v1/dashboard/user/csv/` | UserManagementCSV | Login | Admin | — | — | M-35 |
| GET | `/api/v1/dashboard/user/` | UserAPI | Login | Admin | features/manage-users/api/manageUsers.api.ts:64 | — | — |
| GET | `/api/v1/dashboard/user/<str:user_id>/` | UserGetPatchDeleteAPI | Login | Admin | features/manage-users/api/manageUsers.api.ts:81 | — | — |
| PATCH | `/api/v1/dashboard/user/<str:user_id>/` | UserGetPatchDeleteAPI | Login | Admin | features/manage-users/api/manageUsers.api.ts:99 | — | M-33 |
| DELETE | `/api/v1/dashboard/user/<str:user_id>/` | UserGetPatchDeleteAPI | Login | Admin | features/manage-users/api/manageUsers.api.ts:107 | — | L-21 |
| GET | `/api/v1/dashboard/user/<str:user_id>/` | UserGetPatchDeleteAPI | Login | Admin | features/manage-users/api/manageUsers.api.ts:81 | — | — |
| PATCH | `/api/v1/dashboard/user/<str:user_id>/` | UserGetPatchDeleteAPI | Login | Admin | features/manage-users/api/manageUsers.api.ts:99 | — | M-33 |
| DELETE | `/api/v1/dashboard/user/<str:user_id>/` | UserGetPatchDeleteAPI | Login | Admin | features/manage-users/api/manageUsers.api.ts:107 | — | L-21 |
| GET | `/api/v1/dashboard/user/<str:user_id>/` | UserGetPatchDeleteAPI | Login | Admin | features/manage-users/api/manageUsers.api.ts:81 | — | — |
| PATCH | `/api/v1/dashboard/user/<str:user_id>/` | UserGetPatchDeleteAPI | Login | Admin | features/manage-users/api/manageUsers.api.ts:99 | — | M-33 |
| DELETE | `/api/v1/dashboard/user/<str:user_id>/` | UserGetPatchDeleteAPI | Login | Admin | features/manage-users/api/manageUsers.api.ts:107 | — | L-21 |

#### `dashboard/zonal` (7 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/dashboard/zonal/zonal-details/` | ZonalDetailsAPI | Login | Zonal Lead | features/zonal/api/zonal.api.ts:25 | — | M-24 |
| GET | `/api/v1/dashboard/zonal/top-districts/` | ZonalTopThreeDistrictAPI | Login | Zonal Lead | features/zonal/api/zonal.api.ts:30 | — | M-24 |
| GET | `/api/v1/dashboard/zonal/student-level/` | ZonalStudentLevelStatusAPI | Login | Zonal Lead | features/zonal/api/zonal.api.ts:35 | — | M-24 |
| GET | `/api/v1/dashboard/zonal/student-details/` | ZonalStudentDetailsAPI | Login | Zonal Lead | — | — | M-24 |
| GET | `/api/v1/dashboard/zonal/student-details/csv/` | ZonalStudentDetailsCSVAPI | Login | Zonal Lead | features/zonal/api/zonal.api.ts:49 | — | M-24 |
| GET | `/api/v1/dashboard/zonal/college-details/` | ZonalCollegeDetailsAPI | Login | Zonal Lead | — | — | M-24 |
| GET | `/api/v1/dashboard/zonal/college-details/csv/` | ZonalCollegeDetailsCSVAPI | Login | Zonal Lead | features/zonal/api/zonal.api.ts:67 | — | M-24 |

#### `donate` (5 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/donate/order/` | RazorPayOrderAPI | **Public** | any logged-in | — | — | L-35 |
| POST | `/api/v1/donate/verify/` | RazorPayVerification | **Public** | any logged-in | — | — | H-29, M-44, L-35 |
| POST | `/api/v1/donate/subscription/create/` | RazorPaySubscriptionAPI | **Public** | any logged-in | — | — | L-35 |
| POST | `/api/v1/donate/subscription/verify/` | RazorPaySubscriptionVerification | **Public** | any logged-in | — | — | H-29, M-44, L-35 |
| POST | `/api/v1/donate/bank-transfer/` | BankTransferAPI | **Public** | any logged-in | — | — | L-35 |

#### `hackathon` (42 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/hackathon/list-hackathons/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| POST | `/api/v1/hackathon/list-hackathons/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| PUT | `/api/v1/hackathon/list-hackathons/` | HackathonManagementAPI | Login | none observed | — | TypeError: HackathonManagementAPI.put() missing 1 required positional  (admin) | M-53 |
| DELETE | `/api/v1/hackathon/list-hackathons/` | HackathonManagementAPI | Login | none observed | — | TypeError: HackathonManagementAPI.delete() missing 1 required position (admin) | M-53 |
| GET | `/api/v1/hackathon/list-hackathons/upcoming/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| POST | `/api/v1/hackathon/list-hackathons/upcoming/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| PUT | `/api/v1/hackathon/list-hackathons/upcoming/` | HackathonManagementAPI | Login | none observed | — | TypeError: HackathonManagementAPI.put() missing 1 required positional  (admin) | M-53 |
| DELETE | `/api/v1/hackathon/list-hackathons/upcoming/` | HackathonManagementAPI | Login | none observed | — | TypeError: HackathonManagementAPI.delete() missing 1 required position (admin) | M-53 |
| GET | `/api/v1/hackathon/list-hackathons/<str:hackathon_id>/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| POST | `/api/v1/hackathon/list-hackathons/<str:hackathon_id>/` | HackathonManagementAPI | Login | none observed | — | TypeError: HackathonManagementAPI.post() got an unexpected keyword arg (admin) | M-53 |
| PUT | `/api/v1/hackathon/list-hackathons/<str:hackathon_id>/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| DELETE | `/api/v1/hackathon/list-hackathons/<str:hackathon_id>/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| GET | `/api/v1/hackathon/info/<str:hackathon_id>/` | HackathonInfoAPI | Login | Admin | — | — | M-53 |
| GET | `/api/v1/hackathon/create-hackathon/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| POST | `/api/v1/hackathon/create-hackathon/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| PUT | `/api/v1/hackathon/create-hackathon/` | HackathonManagementAPI | Login | none observed | — | TypeError: HackathonManagementAPI.put() missing 1 required positional  (admin) | M-53 |
| DELETE | `/api/v1/hackathon/create-hackathon/` | HackathonManagementAPI | Login | none observed | — | TypeError: HackathonManagementAPI.delete() missing 1 required position (admin) | M-53 |
| GET | `/api/v1/hackathon/edit-hackathon/<str:hackathon_id>/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| POST | `/api/v1/hackathon/edit-hackathon/<str:hackathon_id>/` | HackathonManagementAPI | Login | none observed | — | TypeError: HackathonManagementAPI.post() got an unexpected keyword arg (admin) | M-53 |
| PUT | `/api/v1/hackathon/edit-hackathon/<str:hackathon_id>/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| DELETE | `/api/v1/hackathon/edit-hackathon/<str:hackathon_id>/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| GET | `/api/v1/hackathon/delete-hackathon/<str:hackathon_id>/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| POST | `/api/v1/hackathon/delete-hackathon/<str:hackathon_id>/` | HackathonManagementAPI | Login | none observed | — | TypeError: HackathonManagementAPI.post() got an unexpected keyword arg (admin) | M-53 |
| PUT | `/api/v1/hackathon/delete-hackathon/<str:hackathon_id>/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| DELETE | `/api/v1/hackathon/delete-hackathon/<str:hackathon_id>/` | HackathonManagementAPI | Login | Admin | — | — | M-53 |
| PUT | `/api/v1/hackathon/publish-hackathon/<str:hackathon_id>/` | HackathonPublishingAPI | Login | Admin | — | — | M-53 |
| POST | `/api/v1/hackathon/submit-hackathon/` | HackathonSubmissionAPI | Login | none observed | — | IntegrityError: NOT NULL constraint failed: hackathon_submission.hacka (admin) | M-53 |
| GET | `/api/v1/hackathon/list-organiser-hackathons/<str:hackathon_id>/` | HackathonOrganiserAPI | Login | Admin | — | — | M-53 |
| POST | `/api/v1/hackathon/list-organiser-hackathons/<str:hackathon_id>/` | HackathonOrganiserAPI | Login | none observed | — | KeyError: 'muid' (admin) | M-53 |
| DELETE | `/api/v1/hackathon/list-organiser-hackathons/<str:hackathon_id>/` | HackathonOrganiserAPI | Login | none observed | — | TypeError: HackathonOrganiserAPI.delete() got an unexpected keyword ar (admin) | M-53 |
| GET | `/api/v1/hackathon/add-organiser/<str:hackathon_id>/` | HackathonOrganiserAPI | Login | Admin | — | — | M-53 |
| POST | `/api/v1/hackathon/add-organiser/<str:hackathon_id>/` | HackathonOrganiserAPI | Login | none observed | — | KeyError: 'muid' (admin) | M-53 |
| DELETE | `/api/v1/hackathon/add-organiser/<str:hackathon_id>/` | HackathonOrganiserAPI | Login | none observed | — | TypeError: HackathonOrganiserAPI.delete() got an unexpected keyword ar (admin) | M-53 |
| GET | `/api/v1/hackathon/delete-organiser/<str:organiser_link_id>/` | HackathonOrganiserAPI | Login | none observed | — | TypeError: HackathonOrganiserAPI.get() got an unexpected keyword argum (admin) | M-53 |
| POST | `/api/v1/hackathon/delete-organiser/<str:organiser_link_id>/` | HackathonOrganiserAPI | Login | none observed | — | TypeError: HackathonOrganiserAPI.post() got an unexpected keyword argu (admin) | M-53 |
| DELETE | `/api/v1/hackathon/delete-organiser/<str:organiser_link_id>/` | HackathonOrganiserAPI | Login | Admin | — | — | M-53 |
| GET | `/api/v1/hackathon/list-applicants/` | ListApplicantsAPI | Login | none observed | — | AttributeError: 'NoneType' object has no attribute 'get' (admin) | M-53 |
| GET | `/api/v1/hackathon/list-applicants/<str:hackathon_id>/` | ListApplicantsAPI | Login | none observed | — | AttributeError: 'NoneType' object has no attribute 'get' (admin) | M-53 |
| GET | `/api/v1/hackathon/list-form/<str:hackathon_id>/` | ListHackathonFormAPI | Login | Admin | — | — | M-53 |
| GET | `/api/v1/hackathon/list-organisations/` | ListOrganisations | Login | Admin | — | — | M-53 |
| GET | `/api/v1/hackathon/list-districts/` | ListDistricts | Login | Admin | — | — | M-53 |
| GET | `/api/v1/hackathon/list-default-form-fields/` | GetDefaultFieldsAPI | Login | Admin | — | — | M-53 |

#### `integrations` (20 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/integrations/kkem/login/` | KKEMIntegrationLogin | **Public** | any logged-in | — | — | L-12 |
| POST | `/api/v1/integrations/kkem/authorization/` | KKEMAuthorizationAPI | **Public** | any logged-in | — | — | L-12 |
| PATCH | `/api/v1/integrations/kkem/authorization/` | KKEMAuthorizationAPI | Public? (anon→500) | ? (500) | — | TypeError: KKEMAuthorizationAPI.patch() missing 1 required positional  (admin,anon,associate,campusiglead,campus) | L-12 |
| POST | `/api/v1/integrations/kkem/authorization/<str:token>/` | KKEMAuthorizationAPI | Public? (anon→500) | ? (500) | — | TypeError: KKEMAuthorizationAPI.post() got an unexpected keyword argum (admin,anon,associate,campusiglead,campus) | L-12 |
| PATCH | `/api/v1/integrations/kkem/authorization/<str:token>/` | KKEMAuthorizationAPI | Public? (anon→500) | ? (500) | — | DecodeError: Not enough segments (admin,anon,associate,campusiglead,campus) | L-12 |
| GET | `/api/v1/integrations/kkem/user/status/<str:encrypted_data>/` | KKEMUserStatusAPI | **Public** | any logged-in | — | — | L-12 |
| GET | `/api/v1/integrations/kkem/user/<str:encrypted_data>/` | KKEMdetailsFetchAPI | **Public** | any logged-in | — | — | L-12 |
| GET | `/api/v1/integrations/kkem/users/` | KKEMBulkKarmaAPI | Public? (anon→500) | ? (500) | — | CustomException: Invalid Authorization header (admin,anon,associate,campusiglead,campus) | L-12 |
| GET | `/api/v1/integrations/kkem/users/<str:muid>/` | KKEMIndividualKarmaAPI | Public? (anon→500) | ? (500) | — | CustomException: Invalid Authorization header (admin,anon,associate,campusiglead,campus) | L-12 |
| GET | `/api/v1/integrations/kkem/hackathon-stats/` | HackathonStatsAPI | Public? (anon→500) | ? (500) | — | CustomException: Invalid Authorization header (admin,anon,associate,campusiglead,campus) | L-12 |
| POST | `/api/v1/integrations/wadhwani/auth-token/` | WadhwaniAuthToken | **Public** | any logged-in | features/courses/api/courses.api.ts:19 | — | H-15 |
| POST | `/api/v1/integrations/wadhwani/user-login/` | WadhwaniUserLogin | Login (anon→500) | any logged-in | features/courses/api/courses.api.ts:38 | IndexError: list index out of range (anon) | H-15, L-10 |
| POST | `/api/v1/integrations/wadhwani/course-details/` | WadhwaniCourseDetails | **Public** | any logged-in | features/courses/api/courses.api.ts:27 | — | H-15 |
| POST | `/api/v1/integrations/wadhwani/course-enroll-status/` | WadhwaniCourseEnrollStatus | Login (anon→500) | any logged-in | — | IndexError: list index out of range (anon) | H-15 |
| POST | `/api/v1/integrations/wadhwani/course-quiz-data/` | WadhwaniCourseQuizData | **Public** | any logged-in | — | — | H-15 |
| POST | `/api/v1/integrations/qseverse/issue-vc/` | IssueVerifiableCredentialView | **Public** | any logged-in | features/profile/api/profile.api.ts:480 | — | H-15 |
| GET | `/api/v1/integrations/qseverse/connected-users/` | GetAllConnectedUsersView | **Public** | any logged-in | — | — | H-15 |
| GET | `/api/v1/integrations/qseverse/connected-users/search` | GetConnectedUserView | **Public** | any logged-in | features/connect/api/connect.api.ts:11, features/profile/api/profile.api.ts:467 | — | H-15 |
| GET | `/api/v1/integrations/qseverse/qs-credentials/` | GetQSCredentialsView | **Public** | any logged-in | features/achievements/api/achievements.api.ts:88 | — | H-15 |
| GET | `/api/v1/integrations/mufifa/verify-task/` | ExternalTaskVerificationAPI | **Public** | any logged-in | — | — | — |

#### `launchpad` (52 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/launchpad/register-company/` | RegisterCompanyAPI | **Public** | any logged-in | — | — | M-50 |
| POST | `/api/v1/launchpad/register-recruiter/` | RegisterRecruiterAPI | Login | ? (500) | — | KeyError: 'user_type' (admin,associate,campusiglead,campuslead,) | M-50 |
| GET | `/api/v1/launchpad/company-list/` | CompanyListAPI | Login | Admin | — | — | M-50 |
| GET | `/api/v1/launchpad/company-list-verified/` | CompanyListVerifiedAPI | **Public** | any logged-in | — | — | M-50 |
| POST | `/api/v1/launchpad/login-company/` | LoginCompanyAPI | **Public** | any logged-in | — | — | M-50 |
| POST | `/api/v1/launchpad/login-recruiter/` | LoginRecruiterAPI | **Public** | any logged-in | — | — | M-50 |
| POST | `/api/v1/launchpad/refresh-token/` | RefreshTokenAPI | **Public** | any logged-in | — | — | M-50 |
| POST | `/api/v1/launchpad/add-job/` | AddJobAPI | Login | ? (500) | — | KeyError: 'user_type' (admin,associate,campusiglead,campuslead,) | M-50 |
| GET | `/api/v1/launchpad/job/<str:job_id>/` | JobAPI | Login | ? (500) | — | KeyError: 'user_type' (admin,associate,campusiglead,campuslead,) | M-50 |
| PUT | `/api/v1/launchpad/job/<str:job_id>/` | JobAPI | Login | ? (500) | — | KeyError: 'user_type' (admin,associate,campusiglead,campuslead,) | M-50 |
| DELETE | `/api/v1/launchpad/job/<str:job_id>/` | JobAPI | Login | ? (500) | — | KeyError: 'user_type' (admin,associate,campusiglead,campuslead,) | M-50 |
| POST | `/api/v1/launchpad/company-info/` | GetCompanyInfoAPI | **Public** | any logged-in | — | — | C-04, M-50 |
| POST | `/api/v1/launchpad/recruiter-info/` | GetRecruiterInfoAPI | **Public** | any logged-in | — | — | C-04, M-50 |
| POST | `/api/v1/launchpad/company-verify/` | CompanyVerifyAPI | Login | Admin | — | — | M-50 |
| GET | `/api/v1/launchpad/list-jobs/` | ListJobsAPI | Login | any logged-in | — | — | M-50 |
| POST | `/api/v1/launchpad/verify-task/` | VerifyTaskAPI | Login | Admin | — | — | M-50 |
| GET | `/api/v1/launchpad/list-launchpad-students/<str:job_id>/` | ListLaunchpadStudentsAPI | Login | ? (500) | — | KeyError: 'user_type' (admin,associate,campusiglead,campuslead,) | M-50, H-26 |
| GET | `/api/v1/launchpad/hire-requests/` | HireRequestsAPI | Login | ? (500) | — | KeyError: 'user_type' (admin,associate,campusiglead,campuslead,) | M-50 |
| POST | `/api/v1/launchpad/send-job-invitations/` | SendJobInvitationsAPI | Login | ? (500) | — | KeyError: 'user_type' (admin,associate,campusiglead,campuslead,) | M-50 |
| GET | `/api/v1/launchpad/student/job-invitations/` | StudentJobInvitationsAPI | Login | any logged-in | — | — | M-50 |
| POST | `/api/v1/launchpad/student/apply-to-job/` | StudentApplyToJobAPI | Login | any logged-in | — | — | M-50 |
| GET | `/api/v1/launchpad/accepted-students/` | AcceptedStudentsAPI | Login | ? (500) | — | KeyError: 'user_type' (admin,associate,campusiglead,campuslead,) | M-50 |
| GET | `/api/v1/launchpad/accepted-students/<str:job_id>/` | AcceptedStudentsAPI | Login | ? (500) | — | KeyError: 'user_type' (admin,associate,campusiglead,campuslead,) | M-50 |
| POST | `/api/v1/launchpad/schedule-interview/` | ScheduleInterviewAPI | Login | any logged-in | — | — | M-50 |
| POST | `/api/v1/launchpad/application-final-decision/` | ApplicationFinalDecisionAPI | Login | ? (500) | — | KeyError: 'user_type' (admin,associate,campusiglead,campuslead,) | M-50 |
| PATCH | `/api/v1/launchpad/delete-company/` | DeleteCompanyAPI | Login (anon→500) | Admin | — | IndexError: list index out of range (anon) | C-04, M-50 |
| GET | `/api/v1/launchpad/leaderboard/` | Leaderboard | **Public** | any logged-in | — | — | M-50 |
| GET | `/api/v1/launchpad/task-completed-leaderboard/` | TaskCompletedLeaderboard | **Public** | any logged-in | — | — | M-50 |
| GET | `/api/v1/launchpad/list-participants/` | ListParticipantsAPI | **Public** | any logged-in | — | — | M-50 |
| GET | `/api/v1/launchpad/launchpad-details/` | LaunchpadDetailsCount | **Public** | any logged-in | — | — | M-50 |
| GET | `/api/v1/launchpad/college-data/` | CollegeData | **Public** | any logged-in | — | — | M-50 |
| GET | `/api/v1/launchpad/user-college-link/` | LaunchPadUser | Login | none observed | — | — | C-04, M-50 |
| POST | `/api/v1/launchpad/user-college-link/` | LaunchPadUser | Login | none observed | — | — | C-04, M-50 |
| PUT | `/api/v1/launchpad/user-college-link/` | LaunchPadUser | Public? (anon→500) | ? (500) | — | TypeError: LaunchPadUser.put() missing 1 required positional argument: (admin,anon,associate,campusiglead,campus) | C-04, M-50 |
| GET | `/api/v1/launchpad/user-college-link/<str:email>` | LaunchPadUser | Public? (anon→500) | ? (500) | — | TypeError: LaunchPadUser.get() got an unexpected keyword argument 'ema (admin,anon,associate,campusiglead,campus) | C-04, M-50 |
| POST | `/api/v1/launchpad/user-college-link/<str:email>` | LaunchPadUser | Public? (anon→500) | ? (500) | — | TypeError: LaunchPadUser.post() got an unexpected keyword argument 'em (admin,anon,associate,campusiglead,campus) | C-04, M-50 |
| PUT | `/api/v1/launchpad/user-college-link/<str:email>` | LaunchPadUser | Login | none observed | — | — | C-04, M-50 |
| GET | `/api/v1/launchpad/user-college-link-public/<str:email>` | LaunchPadUserPublic | **Public** | any logged-in | — | — | C-04, M-50 |
| GET | `/api/v1/launchpad/user-profile/` | UserProfile | Login | none observed | — | — | C-04, M-50 |
| PUT | `/api/v1/launchpad/user-profile/` | UserProfile | Login | none observed | — | — | C-04, M-50 |
| GET | `/api/v1/launchpad/user-college-data/` | UserBasedCollegeData | Login | none observed | — | — | M-50 |
| POST | `/api/v1/launchpad/bulk-user-college-link/` | BulkLaunchpadUser | Login | none observed | — | — | C-04, M-50 |
| GET | `/api/v1/launchpad/list-participants-admin/` | LaunchPadListAdmin | Login | none observed | — | — | M-50 |
| GET | `/api/v1/launchpad/user-details/<str:launchpad_id>/` | UserProfileAPI | Login | none observed | — | — | M-50 |
| GET | `/api/v1/launchpad/socials/<str:launchpad_id>/` | GetSocialsAPI | Login | none observed | — | — | M-50 |
| GET | `/api/v1/launchpad/user-log/<str:launchpad_id>/` | UserLogAPI | Login | none observed | — | — | M-50 |
| GET | `/api/v1/launchpad/get-user-levels/<str:launchpad_id>/` | UserLevelsAPI | Login | none observed | — | — | M-50 |
| GET | `/api/v1/launchpad/ig-leaderboard/` | IGLeaderboardView | **Public** | any logged-in | — | — | M-50 |
| POST | `/api/v1/launchpad/forgot-password/` | ForgotPasswordAPI | **Public** | any logged-in | — | — | M-50 |
| POST | `/api/v1/launchpad/reset-password/` | ResetPasswordAPI | **Public** | any logged-in | — | — | M-50 |
| POST | `/api/v1/launchpad/verify-reset-token/` | VerifyResetTokenAPI | **Public** | any logged-in | — | — | M-50 |
| POST | `/api/v1/launchpad/change-password/` | ChangePasswordAPI | Login | ? (500) | — | KeyError: 'user_type' (admin,associate,campusiglead,campuslead,) | M-50 |

#### `leaderboard` (9 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/leaderboard/students/` | StudentsLeaderboard | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/leaderboard/students-monthly/` | StudentsMonthlyLeaderboard | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/leaderboard/college/` | CollegeLeaderboard | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/leaderboard/college-monthly/` | CollegeMonthlyLeaderboard | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/leaderboard/wadhwani-college/` | WadhwaniCollegeLeaderboard | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/leaderboard/wadhwani-zonal/` | WadhwaniZonalLeaderboard | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/leaderboard/ig-mentor/<str:ig_id>/` | IGMentorLeaderboard | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/leaderboard/campus-mentor/<str:campus_id>/` | CampusMentorLeaderboard | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/leaderboard/company-mentor/<str:company_id>/` | CompanyMentorLeaderboard | **Public** | any logged-in | — | — | — |

#### `muComics` (52 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/muComics/comics/genres/` | GenreListCreateView | **Public** | any logged-in | — | — | — |
| POST | `/api/v1/muComics/comics/genres/` | GenreListCreateView | Login | Admin | — | — | — |
| GET | `/api/v1/muComics/comics/genres/<str:genre_id>/` | GenreDetailView | **Public** | any logged-in | — | — | — |
| PATCH | `/api/v1/muComics/comics/genres/<str:genre_id>/` | GenreDetailView | Login | Admin | — | — | — |
| DELETE | `/api/v1/muComics/comics/genres/<str:genre_id>/` | GenreDetailView | Login | Admin | — | — | — |
| POST | `/api/v1/muComics/comics/genres/<str:genre_id>/reinstate/` | GenreReinstateView | Login | Admin | — | — | — |
| GET | `/api/v1/muComics/comics/` | ComicListCreateView | **Public** | any logged-in | — | — | — |
| POST | `/api/v1/muComics/comics/` | ComicListCreateView | Login | Admin | — | — | — |
| GET | `/api/v1/muComics/comics/<str:comic_id>/` | ComicDetailView | **Public** | any logged-in | — | — | — |
| PATCH | `/api/v1/muComics/comics/<str:comic_id>/` | ComicDetailView | Login | none observed | — | — | — |
| DELETE | `/api/v1/muComics/comics/<str:comic_id>/` | ComicDetailView | Login | none observed | — | — | — |
| POST | `/api/v1/muComics/comics/<str:comic_id>/publish/` | ComicPublishView | Login | none observed | — | — | — |
| POST | `/api/v1/muComics/comics/<str:comic_id>/archive/` | ComicArchiveView | Login | none observed | — | — | — |
| POST | `/api/v1/muComics/comics/<str:comic_id>/unarchive/` | ComicUnarchiveView | Login | none observed | — | — | — |
| GET | `/api/v1/muComics/comics/<str:comic_id>/contributors/` | ComicContributorListView | **Public** | any logged-in | — | — | — |
| POST | `/api/v1/muComics/comics/<str:comic_id>/contributors/` | ComicContributorListView | Login | Admin | — | — | — |
| PATCH | `/api/v1/muComics/comics/<str:comic_id>/contributors/<str:contributor_id>/` | ComicContributorDetailView | Login | Admin | — | — | — |
| DELETE | `/api/v1/muComics/comics/<str:comic_id>/contributors/<str:contributor_id>/` | ComicContributorDetailView | Login | Admin | — | — | — |
| POST | `/api/v1/muComics/comics/<str:comic_id>/genres/` | ComicGenreListView | Login | Admin | — | — | — |
| DELETE | `/api/v1/muComics/comics/<str:comic_id>/genres/<str:link_id>/` | ComicGenreDetailView | Login | Admin | — | — | — |
| GET | `/api/v1/muComics/comments/comic/<str:comic_id>/list/` | ComicCommentListAPI | **Public** | any logged-in | — | — | — |
| POST | `/api/v1/muComics/comments/comic/<str:comic_id>/create/` | ComicCommentCreateAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/muComics/comments/chapter/<str:chapter_id>/list/` | ChapterCommentListAPI | **Public** | any logged-in | — | — | — |
| POST | `/api/v1/muComics/comments/chapter/<str:chapter_id>/create/` | ChapterCommentCreateAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/muComics/comments/admin/` | AdminCommentListAPI | Login | Comic Admin | — | — | — |
| DELETE | `/api/v1/muComics/comments/admin/<str:comment_id>/` | AdminCommentDeleteAPI | Login | Comic Admin | — | — | — |
| PATCH | `/api/v1/muComics/comments/<str:comment_id>/` | CommentDetailAPI | Login | any logged-in | — | — | — |
| DELETE | `/api/v1/muComics/comments/<str:comment_id>/` | CommentDetailAPI | Login | any logged-in | — | — | — |
| POST | `/api/v1/muComics/chapters/upload-url/` | ChapterUploadURLAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/muComics/chapters/` | ChapterListCreateView | Login | any logged-in | — | — | — |
| POST | `/api/v1/muComics/chapters/` | ChapterListCreateView | Login | any logged-in | — | — | — |
| GET | `/api/v1/muComics/chapters/<str:chapter_id>/` | ChapterDetailView | Login | any logged-in | — | — | — |
| PATCH | `/api/v1/muComics/chapters/<str:chapter_id>/` | ChapterDetailView | Login | any logged-in | — | — | — |
| DELETE | `/api/v1/muComics/chapters/<str:chapter_id>/` | ChapterDetailView | Login | any logged-in | — | — | — |
| POST | `/api/v1/muComics/chapters/<str:chapter_id>/publish/` | ChapterPublishView | Login | any logged-in | — | — | — |
| POST | `/api/v1/muComics/chapters/<str:chapter_id>/archive/` | ChapterArchiveView | Login | any logged-in | — | — | — |
| GET | `/api/v1/muComics/chapters/<str:chapter_id>/pages/` | ChapterPageListCreateAPI | Login | any logged-in | — | — | — |
| POST | `/api/v1/muComics/chapters/<str:chapter_id>/pages/` | ChapterPageListCreateAPI | Login | any logged-in | — | — | — |
| POST | `/api/v1/muComics/chapters/<str:chapter_id>/pages/reorder/` | ChapterPageReorderAPI | Login | any logged-in | — | — | — |
| POST | `/api/v1/muComics/chapters/<str:chapter_id>/pages/register/` | ChapterRegisterImagesAPI | Login | any logged-in | — | — | — |
| PATCH | `/api/v1/muComics/chapters/pages/<str:page_id>/` | ChapterPageDetailAPI | Login | none observed | — | — | — |
| DELETE | `/api/v1/muComics/chapters/pages/<str:page_id>/` | ChapterPageDetailAPI | Login | none observed | — | — | — |
| GET | `/api/v1/muComics/reader/me/` | ReaderDashboardAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/muComics/reader/me/bookmarks/` | MyBookmarksAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/muComics/reader/me/progress/` | MyReadingProgressAPI | Login | any logged-in | — | — | — |
| POST | `/api/v1/muComics/reader/comics/<str:comic_id>/likes/` | LikeComicAPI | Login | any logged-in | — | — | — |
| DELETE | `/api/v1/muComics/reader/comics/<str:comic_id>/likes/` | LikeComicAPI | Login | any logged-in | — | — | — |
| POST | `/api/v1/muComics/reader/comics/<str:comic_id>/bookmarks/` | BookmarkComicAPI | Login | any logged-in | — | — | — |
| DELETE | `/api/v1/muComics/reader/comics/<str:comic_id>/bookmarks/` | BookmarkComicAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/muComics/reader/comics/<str:comic_id>/interaction-status/` | InteractionStatusAPI | Login | any logged-in | — | — | — |
| GET | `/api/v1/muComics/reader/comics/<str:comic_id>/progress/` | ReadingProgressAPI | Login | any logged-in | — | — | — |
| PUT | `/api/v1/muComics/reader/comics/<str:comic_id>/progress/` | ReadingProgressAPI | Login | any logged-in | — | — | — |

#### `notification` (13 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/notification/` | NotificationListView | Login | any logged-in | features/notification/api/notification.api.ts:70 | — | H-04, M-12, M-18 |
| GET | `/api/v1/notification/unread-count/` | UnreadCountView | Login | any logged-in | features/notification/api/notification.api.ts:79 | — | M-12, M-18 |
| PATCH | `/api/v1/notification/read-all/` | MarkAllReadView | Login | any logged-in | features/notification/api/notification.api.ts:93 | — | M-12, M-18 |
| PATCH | `/api/v1/notification/read/` | MarkReadBulkView | Login | none observed | features/notification/api/notification.api.ts:98 | — | M-12, M-18 |
| PATCH | `/api/v1/notification/<str:notification_id>/read/` | MarkReadView | Login | any logged-in | features/notification/api/notification.api.ts:88 | — | M-12, M-18 |
| PATCH | `/api/v1/notification/<str:notification_id>/archive/` | ArchiveView | Login | any logged-in | — | — | M-12, M-18 |
| DELETE | `/api/v1/notification/<str:notification_id>/` | DeleteOneView | Login | any logged-in | features/notification/api/notification.api.ts:103 | — | M-12, M-18 |
| DELETE | `/api/v1/notification/delete/all/` | DeleteAllView | Login | any logged-in | features/notification/api/notification.api.ts:25 | — | M-12, M-18 |
| DELETE | `/api/v1/notification/broadcast/delete/id/<str:broadcast_id>/` | BroadcastNotificationDeleteAPI | Login | Admin | features/notification/api/notification.api.ts:54 | — | M-12, M-18 |
| DELETE | `/api/v1/notification/broadcast/delete/all/` | BroadcastNotificationDeleteAllAPI | Login | Admin | features/notification/api/notification.api.ts:58 | — | M-12, M-18 |
| GET | `/api/v1/notification/broadcast/list/all/` | BroadcastNotificationListAPI | Login | Admin | features/notification/api/notification.api.ts:29 | — | M-12, M-18 |
| POST | `/api/v1/notification/broadcast/create/` | BroadcastNotificationCreateAPI | Login | Admin | features/notification/api/notification.api.ts:37 | — | M-12, M-18 |
| PATCH | `/api/v1/notification/broadcast/update/id/<str:broadcast_id>/` | BroadcastNotificationUpdateAPI | Login | Admin | features/notification/api/notification.api.ts:47 | — | M-12, M-18 |

#### `protected` (2 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/protected/organisation/institutes/<str:organisation_type>/<str:district_name>/` | GetInstitutionsAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/protected/organisation/get-institutes/<str:district_name>/` | RetrieveInstitutesAPI | **Public** | any logged-in | — | — | L-39 |

#### `public` (30 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/public/campus-details/<str:college_code>/` | CollegeDetailsAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/lc-list` | LcListAPI | Public? (anon→500) | ? (500) | — | ImproperlyConfigured: Field name `name` is not valid for model `Learni (admin,anon,associate,campusiglead,campus) | H-28 |
| GET | `/api/v1/public/<str:circle_id>/lc-details/` | LcDetailsAPI | Public? (anon→500) | ? (500) | — | ImproperlyConfigured: Field name `name` is not valid for model `Learni (admin,anon,associate,campusiglead,campus) | H-28 |
| GET | `/api/v1/public/lc-dashboard/` | LcDashboardAPI | Public? (anon→500) | ? (500) | — | FieldError: Cannot resolve keyword 'name' into field. Choices are: cac (admin,anon,associate,campusiglead,campus) | H-28 |
| GET | `/api/v1/public/lc-report/` | LcReportAPI | Public? (anon→500) | ? (500) | — | FieldError: Cannot resolve keyword 'name' into field. Choices are: cac (admin,anon,associate,campusiglead,campus) | H-28 |
| GET | `/api/v1/public/college-wise-lc-report/` | CollegeWiseLcReport | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/college-wise-lc-report/csv/` | CollegeWiseLcReportCSV | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/lc-report/csv/` | LcReportDownloadAPI | Public? (anon→500) | ? (500) | — | FieldError: Cannot resolve keyword 'name' into field. Choices are: cac (admin,anon,associate,campusiglead,campus) | H-28 |
| GET | `/api/v1/public/lc-enrollment/` | LearningCircleEnrollment | Public? (anon→500) | ? (500) | — | FieldError: Cannot resolve keyword 'name' into field. Choices are: cac (admin,anon,associate,campusiglead,campus) | H-28 |
| GET | `/api/v1/public/lc-enrollment/csv/` | LearningCircleEnrollmentCSV | Public? (anon→500) | ? (500) | — | FieldError: Cannot resolve keyword 'name' into field. Choices are: cac (admin,anon,associate,campusiglead,campus) | H-28 |
| GET | `/api/v1/public/global-count/` | GlobalCountAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/gta-sandshore/` | GTASANDSHOREAPI | Public? (anon→500) | ? (500) | — | TypeError: int() argument must be a string, a bytes-like object or a r (admin,anon,associate,campusiglead,campus) | M-51 |
| GET | `/api/v1/public/profile-pic/<str:muid>/` | UserProfilePicAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/list-ig/` | ListIGAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/list-ig-top100/` | ListTopIgUsersAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/list/levels/` | ListAllLevelInfo | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/leaderboard/top-100/` | BekenAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/list/college/` | LcCollegeAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/list/district/` | LcDistrictAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/list/state/` | LcStateAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/list/country/` | LcCountryAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/external/user/` | ExternalUserDetailsAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/jobs/` | PublicJobAPI | Login | any logged-in | features/home/api/home.api.ts:74 | — | — |
| GET | `/api/v1/public/ig/list/` | PublicInterestGroupListApi | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/ig/<str:pk>/` | IGDetailAPI | **Public** | any logged-in | features/interest-groups/api/interest-groups.api.ts:64 | — | — |
| GET | `/api/v1/public/career-lab/ongoing/` | PublicOngoingHiringAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/career-lab/previous/` | PublicPreviousHiringAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/events/` | PublicEventListAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/events/featured/` | PublicEventFeaturedAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/public/events/<str:event_id>/` | PublicEventDetailAPI | **Public** | any logged-in | — | — | — |

#### `register` (22 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/register/` | RegisterDataAPI | **Public** | any logged-in | features/auth/api/register.api.ts:27 | — | C-09, M-52, L-15 |
| GET | `/api/v1/register/role/list/` | RoleAPI | **Public** | any logged-in | features/manage-users/api/manageUsers.api.ts:123, features/onboarding/api/onboarding.api.ts:82 | — | C-09 |
| GET | `/api/v1/register/colleges/` | CollegesAPI | **Public** | any logged-in | features/notification/api/notification.api.ts:130, features/onboarding/api/onboarding.api.ts:36 | — | — |
| GET | `/api/v1/register/department/list/` | DepartmentAPI | **Public** | any logged-in | features/onboarding/api/onboarding.api.ts:54, features/onboarding/api/onboarding.api.ts:65 (+1) | — | — |
| GET | `/api/v1/register/location/` | LocationSearchView | **Public** | any logged-in | features/manage-users/api/manageUsers.api.ts:151 | — | — |
| GET | `/api/v1/register/country/list/` | CountryAPI | **Public** | any logged-in | features/manage-users/api/manageUsers.api.ts:165, features/onboarding/api/onboarding.api.ts:124 (+1) | — | — |
| POST | `/api/v1/register/state/list/` | StateAPI | **Public** | any logged-in | features/manage-users/api/manageUsers.api.ts:180, features/onboarding/api/onboarding.api.ts:132 (+1) | — | — |
| POST | `/api/v1/register/district/list/` | DistrictAPI | **Public** | any logged-in | features/manage-users/api/manageUsers.api.ts:197, features/onboarding/api/onboarding.api.ts:144 (+2) | — | — |
| POST | `/api/v1/register/college/list/` | CollegeAPI | **Public** | any logged-in | features/manage-users/api/manageUsers.api.ts:216, features/profile/api/profile.api.ts:379 | — | — |
| GET | `/api/v1/register/company/list/` | CompanyAPI | **Public** | any logged-in | features/onboarding/api/onboarding.api.ts:75 | — | — |
| GET | `/api/v1/register/community/list/` | CommunityAPI | **Public** | any logged-in | features/manage-users/api/manageUsers.api.ts:114, features/profile/api/profile.api.ts:317 | — | — |
| POST | `/api/v1/register/schools/list/` | SchoolAPI | **Public** | any logged-in | features/manage-users/api/manageUsers.api.ts:221, features/profile/api/profile.api.ts:384 | — | — |
| GET | `/api/v1/register/area-of-interest/list/` | AreaOfInterestAPI | **Public** | any logged-in | features/manage-users/api/manageUsers.api.ts:142 | — | — |
| POST | `/api/v1/register/lc/user-validation/` | LearningCircleUserViewAPI | **Public** | any logged-in | — | — | H-22 |
| POST | `/api/v1/register/email-verification/` | UserEmailVerificationAPI | **Public** | any logged-in | features/auth/api/register.api.ts:83 | — | L-17 |
| GET | `/api/v1/register/user-country/` | UserCountryAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/register/user-state/` | UserStateAPI | **Public** | any logged-in | — | — | — |
| GET | `/api/v1/register/user-zone/` | UserZoneAPI | **Public** | any logged-in | — | — | — |
| POST | `/api/v1/register/select-domains/` | UserDomainSelectionAPI | Login | any logged-in | features/onboarding/api/onboarding.api.ts:159 | — | L-18 |
| POST | `/api/v1/register/select-endgoals/` | UserEndgoalSelectionAPI | Login | any logged-in | features/onboarding/api/onboarding.api.ts:170 | — | L-18 |
| GET | `/api/v1/register/connect-discord/` | ConnectDiscordAPI | Login | any logged-in | features/connect/api/connect.api.ts:24 | — | L-20 |
| POST | `/api/v1/register/organization/create/` | UnverifiedOrganizationCreateView | Login | any logged-in | features/onboarding/api/onboarding.api.ts:109 | — | — |

#### `top100` (1 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/top100/leaderboard/` | Leaderboard | Public? (anon→500) | ? (500) | — | OperationalError: no such column: u.profile_pic (admin,anon,associate,campusiglead,campus) | M-49 |

#### `url-shortener` (17 endpoints)

| Method | Path | View | Login | Roles that got through (tested) | Used by dashboard | 500 seen (persona) | Issues |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/url-shortener/create/` | UrlShortenerAPI | Login | Admin, Associate, Fellow | — | — | — |
| POST | `/api/v1/url-shortener/create/` | UrlShortenerAPI | Login | Admin, Associate, Fellow | features/url-shortener/api/shortener.api.ts:52 | — | — |
| PUT | `/api/v1/url-shortener/create/` | UrlShortenerAPI | Login | none observed | — | TypeError: UrlShortenerAPI.put() missing 1 required positional argumen (admin,associate,fellow) | — |
| DELETE | `/api/v1/url-shortener/create/` | UrlShortenerAPI | Login | none observed | — | TypeError: UrlShortenerAPI.delete() missing 1 required positional argu (admin,associate,fellow) | — |
| GET | `/api/v1/url-shortener/edit/<str:url_id>/` | UrlShortenerAPI | Login | none observed | — | TypeError: UrlShortenerAPI.get() got an unexpected keyword argument 'u (admin,associate,fellow) | — |
| POST | `/api/v1/url-shortener/edit/<str:url_id>/` | UrlShortenerAPI | Login | none observed | — | TypeError: UrlShortenerAPI.post() got an unexpected keyword argument ' (admin,associate,fellow) | — |
| PUT | `/api/v1/url-shortener/edit/<str:url_id>/` | UrlShortenerAPI | Login | Admin, Associate, Fellow | features/url-shortener/api/shortener.api.ts:63 | — | — |
| DELETE | `/api/v1/url-shortener/edit/<str:url_id>/` | UrlShortenerAPI | Login | Admin, Associate, Fellow | — | — | — |
| GET | `/api/v1/url-shortener/list/` | UrlShortenerAPI | Login | Admin, Associate, Fellow | features/url-shortener/api/shortener.api.ts:35 | — | — |
| POST | `/api/v1/url-shortener/list/` | UrlShortenerAPI | Login | Admin, Associate, Fellow | — | — | — |
| PUT | `/api/v1/url-shortener/list/` | UrlShortenerAPI | Login | none observed | — | TypeError: UrlShortenerAPI.put() missing 1 required positional argumen (admin,associate,fellow) | — |
| DELETE | `/api/v1/url-shortener/list/` | UrlShortenerAPI | Login | none observed | — | TypeError: UrlShortenerAPI.delete() missing 1 required positional argu (admin,associate,fellow) | — |
| GET | `/api/v1/url-shortener/delete/<str:url_id>/` | UrlShortenerAPI | Login | none observed | — | TypeError: UrlShortenerAPI.get() got an unexpected keyword argument 'u (admin,associate,fellow) | — |
| POST | `/api/v1/url-shortener/delete/<str:url_id>/` | UrlShortenerAPI | Login | none observed | — | TypeError: UrlShortenerAPI.post() got an unexpected keyword argument ' (admin,associate,fellow) | — |
| PUT | `/api/v1/url-shortener/delete/<str:url_id>/` | UrlShortenerAPI | Login | Admin, Associate, Fellow | — | — | — |
| DELETE | `/api/v1/url-shortener/delete/<str:url_id>/` | UrlShortenerAPI | Login | Admin, Associate, Fellow | features/url-shortener/api/shortener.api.ts:71 | — | — |
| GET | `/api/v1/url-shortener/get-analytics/<str:url_id>/` | UrlAnalyticsAPI | Login | Admin, Associate, Fellow | features/url-shortener/api/shortener.api.ts:81 | — | — |

## Appendix F — Every dashboard page (browser crawl)

"Opened OK as" lists the tested roles that stayed on the page; "Redirected" lists roles the edge proxy or guard sent elsewhere (usually correct). "Problems" are what the browser saw for roles that were allowed on the page.

| # | Page | Page file → main component | Opened OK as (tested roles) | Redirected | API calls on load | Problems seen in the crawl | Issues |
|---|---|---|---|---|---|---|---|
| 1 | `/` | `src/app/page.tsx` | — | Admin → /dashboard; Anonymous → /login; Student → /dashboard | 9 | none | — |
| 2 | `/callback` | `src/app/(auth)/callback/page.tsx`<br>→ `./callback-page-client` | Admin, Anonymous, Student | — | 0 | none | M-25 |
| 3 | `/dashboard` | `src/app/(dashboard)/dashboard/page.tsx`<br>→ `@/features/home` | Admin, Associate, Campus IG Lead, Campus Lead, Comic Admin, Company, Discord Mod, District Lead, Enabler, Fellow, IG Lead, Intern, Intern Lead, Lead Enabler, Mentor, Student, Tech Team, Zonal Lead | Anonymous → /login | 24 | none | M-58, L-27, M-16, M-29 |
| 4 | `/dashboard/campus/[id]` | `src/app/(dashboard)/dashboard/campus/[id]/page.tsx`<br>→ `@/features/campus` | Admin, Campus IG Lead, Campus Lead, Enabler, Lead Enabler, Student | Anonymous → /login | 6 | none | L-42, H-35 |
| 5 | `/dashboard/campus/manage` | `src/app/(dashboard)/dashboard/campus/manage/page.tsx` | Campus Lead, Enabler, Lead Enabler | Admin → /dashboard; Anonymous → /login; Campus IG Lead → /dashboard; Student → /dashboard | 20 | none | C-06, C-07, H-23, L-50 |
| 6 | `/dashboard/changelog` | `src/app/(dashboard)/dashboard/changelog/page.tsx`<br>→ `@/components/ui/button` | Admin, Student | Anonymous → /login | 4 | none | — |
| 7 | `/dashboard/company` | `src/app/(dashboard)/dashboard/company/page.tsx`<br>→ `@/components/ui/card` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 16 | none | — |
| 8 | `/dashboard/company/admin` | `src/app/(dashboard)/dashboard/company/admin/page.tsx`<br>→ `@/features/company-jobs/components/admin/company-admins-client` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 18 | API GET /api/v1/dashboard/company/user-status/ → 400 {"general":["You do not have the required role to access this page."]} [Company] | H-12, H-33 |
| 9 | `/dashboard/company/analytics` | `src/app/(dashboard)/dashboard/company/analytics/page.tsx`<br>→ `./company-analytics-client` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 17 | none | — |
| 10 | `/dashboard/company/collaborations` | `src/app/(dashboard)/dashboard/company/collaborations/page.tsx`<br>→ `@/features/company-jobs/components/collaborations/company-collaborations-client` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 18 | Console: error: %o %s TypeError: myCollaborations.filter is not a function at CompanyCollaborationsPageClient (http://localhost:3000/_next/static/chunks/src_06pr377._.js<br>Console: error: TypeError: myCollaborations.filter is not a function at CompanyCollaborationsPageClient (http://localhost:3000/_next/static/chunks/src_06pr377._.js:206:4<br>Schema mismatch: /api/v1/dashboard/company/collaborations/<br>Schema mismatch: /api/v1/dashboard/company/collaborations/discover/ | H-30 |
| 11 | `/dashboard/company/event-templates` | `src/app/(dashboard)/dashboard/company/event-templates/page.tsx`<br>→ `@/features/company-jobs/components/templates/company-templates-client` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 16 | Console: error: %o %s Error: `TabsContent` must be used within `Tabs` at useContext2 (http://localhost:3000/_next/static/chunks/node_modules_%40radix-ui_0vyhvjv._.js:432<br>Console: error: Error: `TabsContent` must be used within `Tabs` at useContext2 (http://localhost:3000/_next/static/chunks/node_modules_%40radix-ui_0vyhvjv._.js:432:19) a | H-31 |
| 12 | `/dashboard/company/feedback` | `src/app/(dashboard)/dashboard/company/feedback/page.tsx`<br>→ `@/features/company-jobs/components/feedback/company-feedback-client` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 18 | Console: error: %o %s TypeError: feedbackList.map is not a function at CompanyFeedbackPageClient (http://localhost:3000/_next/static/chunks/src_0dsohvp._.js:1316:56) at <br>Console: error: TypeError: feedbackList.map is not a function at CompanyFeedbackPageClient (http://localhost:3000/_next/static/chunks/src_0dsohvp._.js:1316:56) at Object<br>Schema mismatch: /api/v1/dashboard/company/feedback/list/<br>Schema mismatch: /api/v1/dashboard/company/impact-report/ | H-32 |
| 13 | `/dashboard/company/ig-requests` | `src/app/(dashboard)/dashboard/company/ig-requests/page.tsx`<br>→ `@/features/ig-requests` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 17 | none | — |
| 14 | `/dashboard/company/ig-sponsorship` | `src/app/(dashboard)/dashboard/company/ig-sponsorship/page.tsx`<br>→ `@/features/company-jobs/components/sponsorship/company-sponsorship-client` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 17 | API GET /api/v1/dashboard/company/ig-sponsorship/<id>/metrics/ → 400 {"general":["This Interest Group is not sponsored by your company."]} [Company] | M-08 |
| 15 | `/dashboard/company/jobs` | `src/app/(dashboard)/dashboard/company/jobs/page.tsx`<br>→ `./company-jobs-client` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 17 | none | M-07, H-13, L-47, H-17 |
| 16 | `/dashboard/company/jobs/[jobId]` | `src/app/(dashboard)/dashboard/company/jobs/[jobId]/page.tsx`<br>→ `./job-detail-client` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 18 | none | M-07, H-13, L-47, H-17 |
| 17 | `/dashboard/company/jobs/[jobId]/edit` | `src/app/(dashboard)/dashboard/company/jobs/[jobId]/edit/page.tsx`<br>→ `./job-edit-client` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 17 | none | M-07, H-13, L-47, H-17 |
| 18 | `/dashboard/company/jobs/create` | `src/app/(dashboard)/dashboard/company/jobs/create/page.tsx`<br>→ `./jobs-create-client` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 16 | none | M-07, H-13, L-47, H-17 |
| 19 | `/dashboard/company/mentors` | `src/app/(dashboard)/dashboard/company/mentors/page.tsx`<br>→ `@/features/company-mentors/components/mentors-page` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 17 | none | — |
| 20 | `/dashboard/company/profile/edit` | `src/app/(dashboard)/dashboard/company/profile/edit/page.tsx`<br>→ `./profile-edit-client` | Company | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 16 | none | M-19 |
| 21 | `/dashboard/company/tasks` | `src/app/(dashboard)/dashboard/company/tasks/page.tsx`<br>→ `@/features/company-tasks/components/tasks-page` | Company | Admin → /dashboard; Anonymous timeout/goto error; Mentor → /dashboard; Student → /dashboard | 20 | none | L-11 |
| 22 | `/dashboard/connect-discord` | `src/app/(dashboard)/dashboard/connect-discord/page.tsx`<br>→ `@/components/ui/spinner` | Admin, Student | Anonymous → /login | 4 | none | L-20 |
| 23 | `/dashboard/courses` | `src/app/(dashboard)/dashboard/courses/page.tsx`<br>→ `./courses-client` | Admin | Anonymous → /login; Student timeout/goto error | 5 | Schema mismatch: /api/v1/integrations/wadhwani/auth-token/ | H-15 |
| 24 | `/dashboard/district` | `src/app/(dashboard)/dashboard/district/page.tsx` | Admin, District Lead | Anonymous → /login; Student → /dashboard | 14 | API GET /api/v1/dashboard/district/district-details/ → 400 {"general":["You do not have the required role to access this page."]} [Admin]<br>API GET /api/v1/dashboard/district/student-level/ → 400 {"general":["You do not have the required role to access this page."]} [Admin]<br>API GET /api/v1/dashboard/district/top-campus/ → 400 {"general":["You do not have the required role to access this page."]} [Admin]<br>API GET /api/v1/dashboard/district/student-details/ → 400 {"general":["You do not have the required role to access this page."]} [Admin]<br>API GET /api/v1/dashboard/district/college-details/ → 400 {"general":["You do not have the required role to access this page."]} [Admin]<br>API GET /api/v1/dashboard/district/district-details/ → 400 {"general":["No college organization linked to this user."]} [District Lead]<br>API GET /api/v1/dashboard/district/student-level/ → 400 {"general":["No college organization linked to this user."]} [District Lead]<br>API GET /api/v1/dashboard/district/top-campus/ → 400 {"general":["No college organization linked to this user."]} [District Lead]<br>(+2 more) | M-24, M-55 |
| 25 | `/dashboard/edit-ig` | `src/app/(dashboard)/dashboard/edit-ig/page.tsx`<br>→ `@/features/manage-ig` | Admin | Anonymous → /login; Campus IG Lead → /dashboard; IG Lead timeout/goto error; Student → /dashboard | 9 | none | H-24, H-11, M-37, L-30, M-21 |
| 26 | `/dashboard/edit-ig/[id]` | `src/app/(dashboard)/dashboard/edit-ig/[id]/page.tsx`<br>→ `@/features/manage-ig` | Admin, IG Lead | Anonymous → /login; Campus IG Lead → /dashboard; Student → /dashboard | 13 | none | H-24, H-11, M-37, L-30, M-21 |
| 27 | `/dashboard/events` | `src/app/(dashboard)/dashboard/events/page.tsx`<br>→ `./events-client` | Admin, Student | Anonymous → /login | 7 | none | M-11, H-34 |
| 28 | `/dashboard/events/[id]` | `src/app/(dashboard)/dashboard/events/[id]/page.tsx`<br>→ `@/features/events` | Admin, Student | Anonymous → /login | 5 | none | M-11, H-34 |
| 29 | `/dashboard/interest-groups` | `src/app/(dashboard)/dashboard/interest-groups/page.tsx`<br>→ `@/features/interest-groups` | Admin, IG Lead, Student | Anonymous → /login | 5 | none | M-08, M-09, L-31, M-21, H-34 |
| 30 | `/dashboard/interest-groups/[id]` | `src/app/(dashboard)/dashboard/interest-groups/[id]/page.tsx`<br>→ `@/features/interest-groups` | Admin, IG Lead, Student | Anonymous → /login | 5 | none | M-08, M-09, L-31, M-21, H-34 |
| 31 | `/dashboard/intern` | `src/app/(dashboard)/dashboard/intern/page.tsx`<br>→ `./intern-client` | Admin, Intern, Intern Lead | Anonymous → /login; Student → /dashboard | 15 | API GET /api/v1/dashboard/intern/overview/status/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/leaderboard/me/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/timesheets/history/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/overview/leaderboard/top/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/tasks/mine/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/reviews/history/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/leaderboard/me/ → 400 {"general":["Not found in leaderboard."]} [Intern]<br>API GET /api/v1/dashboard/intern/overview/status/ → 400 {"general":["Not an intern."]} [Intern] | M-54 |
| 32 | `/dashboard/intern/leaderboard` | `src/app/(dashboard)/dashboard/intern/leaderboard/page.tsx`<br>→ `./intern-leaderboard-client` | Admin, Intern, Intern Lead | Anonymous → /login; Student → /dashboard | 11 | API GET /api/v1/dashboard/intern/leaderboard/me/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/leaderboard/me/ → 400 {"general":["Not found in leaderboard."]} [Intern]<br>API GET /api/v1/dashboard/intern/leaderboard/ → 400 {"general":["You do not have the required role to access this page."]} [Intern Lead] | M-54 |
| 33 | `/dashboard/intern/leave` | `src/app/(dashboard)/dashboard/intern/leave/page.tsx`<br>→ `./intern-leave-client` | Admin, Intern, Intern Lead | Anonymous → /login; Student → /dashboard | 11 | API GET /api/v1/dashboard/intern/leave/balance/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/leave/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead] | M-54 |
| 34 | `/dashboard/intern/minutes` | `src/app/(dashboard)/dashboard/intern/minutes/page.tsx`<br>→ `@/components/ui/badge` | Admin, Intern, Intern Lead | Anonymous → /login; Student → /dashboard | 10 | API GET /api/v1/dashboard/intern/overview/status/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/overview/status/ → 400 {"general":["Not an intern."]} [Intern] | M-54 |
| 35 | `/dashboard/intern/quest-log` | `src/app/(dashboard)/dashboard/intern/quest-log/page.tsx`<br>→ `@/features/intern` | Admin, Intern, Intern Lead | Anonymous → /login; Student → /dashboard | 12 | API GET /api/v1/dashboard/intern/timesheets/history/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/reviews/history/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/tasks/mine/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead] | M-54 |
| 36 | `/dashboard/intern/tasks` | `src/app/(dashboard)/dashboard/intern/tasks/page.tsx`<br>→ `./intern-task-client` | Admin, Intern, Intern Lead | Anonymous → /login; Student → /dashboard | 10 | API GET /api/v1/dashboard/intern/tasks/mine/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead] | M-54, L-45 |
| 37 | `/dashboard/intern/timesheet` | `src/app/(dashboard)/dashboard/intern/timesheet/page.tsx`<br>→ `./intern-timesheet-client` | Admin, Intern, Intern Lead | Anonymous → /login; Student → /dashboard | 14 | API GET /api/v1/dashboard/intern/timesheets/history/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/overview/status/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/timesheets/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/timesheets/today/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/tasks/mine/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/timesheets/today/ → 400 {"general":["No timesheet submitted for today."]} [Intern]<br>API GET /api/v1/dashboard/intern/overview/status/ → 400 {"general":["Not an intern."]} [Intern] | M-54 |
| 38 | `/dashboard/intern/weekly-review` | `src/app/(dashboard)/dashboard/intern/weekly-review/page.tsx`<br>→ `./weekly-review-client` | Admin, Intern, Intern Lead | Anonymous → /login; Student → /dashboard | 11 | API GET /api/v1/dashboard/intern/overview/status/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/reviews/current/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Intern Lead]<br>API GET /api/v1/dashboard/intern/overview/status/ → 400 {"general":["Not an intern."]} [Intern]<br>API GET /api/v1/dashboard/intern/reviews/current/ → 400 {"general":["No review submitted for the current week."]} [Intern] | M-54 |
| 39 | `/dashboard/jobs` | `src/app/(dashboard)/dashboard/jobs/page.tsx`<br>→ `./jobs-page-client` | Admin, Student | Anonymous → /login; Company → /dashboard; Mentor → /dashboard | 17 | none | L-47 |
| 40 | `/dashboard/leaderboard` | `src/app/(dashboard)/dashboard/leaderboard/page.tsx`<br>→ `@/features/leaderboard` | Admin, Student | Anonymous → /login | 5 | none | H-35 |
| 41 | `/dashboard/learning-circle` | `src/app/(dashboard)/dashboard/learning-circle/page.tsx`<br>→ `@/components/ui/page-header` | Admin, Student | Anonymous → /login | 8 | none | H-10, M-42, L-33 |
| 42 | `/dashboard/learning-circle/[id]` | `src/app/(dashboard)/dashboard/learning-circle/[id]/page.tsx`<br>→ `@/features/learning-circle` | Admin, Student | Anonymous → /login | 10 | none | H-10, M-43, M-20, L-32, H-35 |
| 43 | `/dashboard/learning-circle/[id]/meeting/[meet_id]` | `src/app/(dashboard)/dashboard/learning-circle/[id]/meeting/[meet_id]/page.tsx`<br>→ `@/features/learning-circle` | Student | Admin timeout/goto error; Anonymous → /login | 8 | none | H-10, L-34 |
| 44 | `/dashboard/learning-circle/invite/[link_id]` | `src/app/(dashboard)/dashboard/learning-circle/invite/[link_id]/page.tsx`<br>→ `@/features/learning-circle` | Admin, Student | Anonymous → /login | 5 | API GET /api/v1/dashboard/learningcircle/invite/status/<id>/ → 500  [Admin,Student] | H-27 |
| 45 | `/dashboard/learning-circle/invites` | `src/app/(dashboard)/dashboard/learning-circle/invites/page.tsx`<br>→ `@/features/learning-circle` | Admin, Student | Anonymous → /login | 6 | none | L-32 |
| 46 | `/dashboard/manage-events` | `src/app/(dashboard)/dashboard/manage-events/page.tsx`<br>→ `@/features/events` | Admin, Campus Lead, Company, Enabler, IG Lead, Mentor | Anonymous → /login; Campus IG Lead → /dashboard; Student → /dashboard | 18 | Schema mismatch: /api/v1/dashboard/events/meta/categories/ | H-09, M-10, H-25 |
| 47 | `/dashboard/manage-events/[id]` | `src/app/(dashboard)/dashboard/manage-events/[id]/page.tsx`<br>→ `@/features/events` | Admin, Campus Lead, Company, Enabler, IG Lead, Mentor | Anonymous → /login; Campus IG Lead → /dashboard; Student → /dashboard | 13 | API GET /api/v1/dashboard/events/manage/<id>/ → 400 {"general":["You do not have permission to manage this event."]} [Campus Lead,Company,IG Lead,Mentor] | H-09, M-10, H-25 |
| 48 | `/dashboard/management` | `src/app/(dashboard)/dashboard/management/page.tsx` | Admin, Associate, Discord Mod, Fellow, Tech Team | Anonymous → /login; Comic Admin → /dashboard; Student → /dashboard | 9 | none | — |
| 49 | `/dashboard/management/channels` | `src/app/(dashboard)/dashboard/management/channels/page.tsx`<br>→ `@/features/channels/components/channel-page` | Admin, Associate, Fellow | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | Schema mismatch: /api/v1/dashboard/channels/?pageIndex=1&perPage=10 | L-11 |
| 50 | `/dashboard/management/college-levels` | `src/app/(dashboard)/dashboard/management/college-levels/page.tsx`<br>→ `@/features/college-levels/components/CollegeLevelsPage` | Admin, Fellow | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | — |
| 51 | `/dashboard/management/community` | `src/app/(dashboard)/dashboard/management/community/page.tsx` | Admin, Associate, Discord Mod, Fellow | Anonymous → /login; Comic Admin → /dashboard; Student → /dashboard; Tech Team → /dashboard | 9 | none | — |
| 52 | `/dashboard/management/discord-moderation` | `src/app/(dashboard)/dashboard/management/discord-moderation/page.tsx`<br>→ `@/features/discord-moderation` | Admin, Discord Mod | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | API GET /api/v1/dashboard/discord-moderator/leaderboard/ → 500  [Admin,Discord Mod] | H-26, M-46 |
| 53 | `/dashboard/management/dynamic-type` | `src/app/(dashboard)/dashboard/management/dynamic-type/page.tsx`<br>→ `@/features/dynamic-type` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | API GET /api/v1/dashboard/dynamic-management/dynamic-role/ → 500  [Admin] | H-26 |
| 54 | `/dashboard/management/error-log` | `src/app/(dashboard)/dashboard/management/error-log/page.tsx`<br>→ `@/features/error-log` | Admin, Tech Team | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard | 10 | none | L-01, L-43 |
| 55 | `/dashboard/management/homepage` | `src/app/(dashboard)/dashboard/management/homepage/page.tsx` | Associate, Fellow | Admin timeout/goto error; Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Student → /dashboard; Tech Team → /dashboard | 9 | none | — |
| 56 | `/dashboard/management/homepage/career-labs` | `src/app/(dashboard)/dashboard/management/homepage/career-labs/page.tsx`<br>→ `@/features/career-labs` | Admin, Associate, Fellow | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | API GET /api/v1/dashboard/career-lab/hiring/ → 400 {"general":["You do not have the required role to access this page."]} [Fellow] | M-56 |
| 57 | `/dashboard/management/karma-voucher` | `src/app/(dashboard)/dashboard/management/karma-voucher/page.tsx`<br>→ `@/features/karma-voucher` | Admin, Fellow | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | — |
| 58 | `/dashboard/management/manage-achievements` | `src/app/(dashboard)/dashboard/management/manage-achievements/page.tsx`<br>→ `@/features/achievements` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 9 | none | C-02 |
| 59 | `/dashboard/management/manage-achievements/bulk-issue` | `src/app/(dashboard)/dashboard/management/manage-achievements/bulk-issue/page.tsx`<br>→ `@/features/achievements` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | C-02 |
| 60 | `/dashboard/management/manage-achievements/issue` | `src/app/(dashboard)/dashboard/management/manage-achievements/issue/page.tsx`<br>→ `@/features/achievements` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 9 | none | C-02 |
| 61 | `/dashboard/management/manage-achievements/list` | `src/app/(dashboard)/dashboard/management/manage-achievements/list/page.tsx`<br>→ `@/features/achievements` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 11 | none | C-02 |
| 62 | `/dashboard/management/manage-achievements/logs` | `src/app/(dashboard)/dashboard/management/manage-achievements/logs/page.tsx`<br>→ `@/components/ui/tabs` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | C-02 |
| 63 | `/dashboard/management/manage-achievements/rules` | `src/app/(dashboard)/dashboard/management/manage-achievements/rules/page.tsx`<br>→ `@/features/achievements` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 11 | none | C-02 |
| 64 | `/dashboard/management/manage-achievements/simulate` | `src/app/(dashboard)/dashboard/management/manage-achievements/simulate/page.tsx`<br>→ `@/features/achievements` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 9 | none | C-02 |
| 65 | `/dashboard/management/manage-companies` | `src/app/(dashboard)/dashboard/management/manage-companies/page.tsx`<br>→ `@/features/role-verification` | — | Admin → /dashboard/management/role-verification; Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team →  | 10 | none | — |
| 66 | `/dashboard/management/manage-interest-groups` | `src/app/(dashboard)/dashboard/management/manage-interest-groups/page.tsx`<br>→ `./manage-interest-groups-client` | Admin, Fellow | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Student → /dashboard; Tech Team → /dashboard | 11 | none | H-11, M-08, M-37 |
| 67 | `/dashboard/management/manage-interns` | `src/app/(dashboard)/dashboard/management/manage-interns/page.tsx`<br>→ `./manage-interns-client` | Admin, Associate, Intern Lead | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Intern → /dashboard; Student → /dashboard; Tech Team → /dashboard | 12 | API GET /api/v1/dashboard/intern/guilds/ → 400 {"general":["You do not have the required role to access this page."]} [Associate,Intern Lead]<br>API GET /api/v1/dashboard/manage-interns/interns/ → 400 {"general":["You do not have the required role to access this page."]} [Associate]<br>API GET /api/v1/dashboard/manage-interns/status/ → 400 {"general":["You do not have the required role to access this page."]} [Associate] | C-10, H-21, M-38, M-54 |
| 68 | `/dashboard/management/manage-interns/intern-report` | `src/app/(dashboard)/dashboard/management/manage-interns/intern-report/page.tsx`<br>→ `./intern-report-client` | Admin, Associate, Intern Lead | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Intern → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | API GET /api/v1/dashboard/manage-interns/reviews/ → 400 {"general":["You do not have the required role to access this page."]} [Associate] | C-10, H-21, M-38, M-54 |
| 69 | `/dashboard/management/manage-interns/intern-report/individual` | `src/app/(dashboard)/dashboard/management/manage-interns/intern-report/individual/page.tsx`<br>→ `./individual-report-client` | Admin, Associate, Intern Lead | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Intern → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | API GET /api/v1/dashboard/manage-interns/reviews/ → 400 {"general":["You do not have the required role to access this page."]} [Associate] | C-10, H-21, M-38, M-54 |
| 70 | `/dashboard/management/manage-interns/intern-report/team` | `src/app/(dashboard)/dashboard/management/manage-interns/intern-report/team/page.tsx`<br>→ `./team-report-client` | Admin, Associate, Intern Lead | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Intern → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | API GET /api/v1/dashboard/manage-interns/reviews/ → 400 {"general":["You do not have the required role to access this page."]} [Associate] | C-10, H-21, M-38, M-54 |
| 71 | `/dashboard/management/manage-interns/leave-reviews` | `src/app/(dashboard)/dashboard/management/manage-interns/leave-reviews/page.tsx`<br>→ `./leave-reviews-client` | Admin, Associate, Intern Lead | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Intern → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | API GET /api/v1/dashboard/manage-interns/leave/ → 400 {"general":["You do not have the required role to access this page."]} [Associate] | C-10, H-21, M-38, M-54 |
| 72 | `/dashboard/management/manage-interns/minutes` | `src/app/(dashboard)/dashboard/management/manage-interns/minutes/page.tsx`<br>→ `./manage-minutes-client` | Admin, Associate, Intern Lead | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Intern → /dashboard; Student → /dashboard; Tech Team → /dashboard | 12 | API GET /api/v1/dashboard/intern/overview/status/ → 400 {"general":["You do not have the required role to access this page."]} [Admin,Associate,Intern Lead]<br>API GET /api/v1/dashboard/intern/guilds/ → 400 {"general":["You do not have the required role to access this page."]} [Associate,Intern Lead]<br>API GET /api/v1/dashboard/intern/minutes/ → 400 {"general":["You do not have the required role to access this page."]} [Associate] | C-10, H-21, M-38, M-54 |
| 73 | `/dashboard/management/manage-interns/tasks` | `src/app/(dashboard)/dashboard/management/manage-interns/tasks/page.tsx`<br>→ `./admin-tasks-client` | Admin, Associate, Intern Lead | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Intern → /dashboard; Student → /dashboard; Tech Team → /dashboard | 13 | API GET /api/v1/dashboard/manage-interns/interns/ → 400 {"general":["You do not have the required role to access this page."]} [Associate]<br>API GET /api/v1/dashboard/intern/guilds/ → 400 {"general":["You do not have the required role to access this page."]} [Associate,Intern Lead]<br>API GET /api/v1/dashboard/manage-interns/tasks/ → 400 {"general":["You do not have the required role to access this page."]} [Associate]<br>API GET /api/v1/dashboard/intern/tasks/categories/ → 400 {"general":["You do not have the required role to access this page."]} [Associate,Intern Lead] | C-10, H-21, M-38, M-54 |
| 74 | `/dashboard/management/manage-interns/timesheet-reviews` | `src/app/(dashboard)/dashboard/management/manage-interns/timesheet-reviews/page.tsx`<br>→ `./timesheet-reviews-client` | Admin, Associate, Intern Lead | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Intern → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | API GET /api/v1/dashboard/manage-interns/reviews/timesheets/ → 400 {"general":["You do not have the required role to access this page."]} [Associate] | C-10, H-21, M-38, M-54 |
| 75 | `/dashboard/management/manage-locations` | `src/app/(dashboard)/dashboard/management/manage-locations/page.tsx`<br>→ `@/features/manage-locations` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | L-11 |
| 76 | `/dashboard/management/manage-roles` | `src/app/(dashboard)/dashboard/management/manage-roles/page.tsx`<br>→ `@/features/manage-roles/components/roles-table` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | M-01, M-02, M-03, M-04, M-36, L-29 |
| 77 | `/dashboard/management/manage-users` | `src/app/(dashboard)/dashboard/management/manage-users/page.tsx`<br>→ `@/features/manage-users/components/manage-user-page` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | M-33, M-35, L-21 |
| 78 | `/dashboard/management/mentor-verification` | `src/app/(dashboard)/dashboard/management/mentor-verification/page.tsx`<br>→ `@/features/role-verification` | — | Admin → /dashboard/management/role-verification; Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team →  | 12 | none | H-24 |
| 79 | `/dashboard/management/notifications` | `src/app/(dashboard)/dashboard/management/notifications/page.tsx`<br>→ `@/features/notification/components/manage/notification-manage-card` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | H-04, H-05, M-12 |
| 80 | `/dashboard/management/organizations` | `src/app/(dashboard)/dashboard/management/organizations/page.tsx`<br>→ `@/features/role-verification` | Admin, Associate, Fellow | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Student → /dashboard; Tech Team → /dashboard | 9 | none | M-05 |
| 81 | `/dashboard/management/organizations/affiliation` | `src/app/(dashboard)/dashboard/management/organizations/affiliation/page.tsx`<br>→ `@/features/organizations` | Admin, Associate, Fellow | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | — |
| 82 | `/dashboard/management/organizations/departments` | `src/app/(dashboard)/dashboard/management/organizations/departments/page.tsx`<br>→ `@/features/organizations` | Admin, Fellow | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | API GET /api/v1/dashboard/organisation/departments/ → 400 {"general":["You do not have the required role to access this page."]} [Fellow] | M-56 |
| 83 | `/dashboard/management/organizations/list` | `src/app/(dashboard)/dashboard/management/organizations/list/page.tsx`<br>→ `@/features/organizations` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | M-05, L-38, L-14, H-35 |
| 84 | `/dashboard/management/organizations/transfer` | `src/app/(dashboard)/dashboard/management/organizations/transfer/page.tsx`<br>→ `@/features/organizations` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 9 | none | C-01, H-03, M-06 |
| 85 | `/dashboard/management/organizations/verify` | `src/app/(dashboard)/dashboard/management/organizations/verify/page.tsx`<br>→ `@/features/role-verification` | — | Admin → /dashboard/management/role-verification; Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team →  | 10 | none | H-01, H-02, M-05 |
| 86 | `/dashboard/management/role-verification` | `src/app/(dashboard)/dashboard/management/role-verification/page.tsx`<br>→ `./role-verification-client` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 12 | none | H-07, L-12, L-22 |
| 87 | `/dashboard/management/session-verification` | `src/app/(dashboard)/dashboard/management/session-verification/page.tsx`<br>→ `@/features/mentor/sessions/components/admin-session-verification-page` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | H-06 |
| 88 | `/dashboard/management/system` | `src/app/(dashboard)/dashboard/management/system/page.tsx` | Admin, Associate, Fellow, Tech Team | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Student → /dashboard | 9 | none | — |
| 89 | `/dashboard/management/system/features` | `src/app/(dashboard)/dashboard/management/system/features/page.tsx`<br>→ `@/features/grit-meter/components/grit-meter-item` | Admin, Associate, Fellow | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | — |
| 90 | `/dashboard/management/tasks` | `src/app/(dashboard)/dashboard/management/tasks/page.tsx` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 9 | none | M-39, L-11 |
| 91 | `/dashboard/management/tasks/bulk-import` | `src/app/(dashboard)/dashboard/management/tasks/bulk-import/page.tsx`<br>→ `@/features/tasks` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 9 | none | M-39, L-11 |
| 92 | `/dashboard/management/tasks/create` | `src/app/(dashboard)/dashboard/management/tasks/create/page.tsx`<br>→ `@/features/tasks` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 16 | none | M-39, L-11 |
| 93 | `/dashboard/management/tasks/list` | `src/app/(dashboard)/dashboard/management/tasks/list/page.tsx`<br>→ `@/features/tasks` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | M-39, L-11 |
| 94 | `/dashboard/management/tasks/task-type` | `src/app/(dashboard)/dashboard/management/tasks/task-type/page.tsx`<br>→ `@/features/tasks` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | M-39, L-11 |
| 95 | `/dashboard/management/tasks/task-verification` | `src/app/(dashboard)/dashboard/management/tasks/task-verification/page.tsx`<br>→ `@/features/tasks` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | M-39, L-11 |
| 96 | `/dashboard/management/user-management` | `src/app/(dashboard)/dashboard/management/user-management/page.tsx`<br>→ `@/features/role-verification` | Admin, Associate | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard/management; Student → /dashboard; Tech Team → /dashboard | 9 | none | — |
| 97 | `/dashboard/management/verification` | `src/app/(dashboard)/dashboard/management/verification/page.tsx` | Admin | Anonymous → /login; Associate → /dashboard; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 9 | none | H-07 |
| 98 | `/dashboard/management/weekly-twitches` | `src/app/(dashboard)/dashboard/management/weekly-twitches/page.tsx`<br>→ `@/features/weekly-twitches` | Admin, Associate | Anonymous → /login; Comic Admin → /dashboard; Discord Mod → /dashboard; Fellow → /dashboard; Student → /dashboard; Tech Team → /dashboard | 10 | none | L-49, M-21 |
| 99 | `/dashboard/mentor` | `src/app/(dashboard)/dashboard/mentor/page.tsx` | — | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 14 | none | H-06, H-13 |
| 100 | `/dashboard/mentor/mentees` | `src/app/(dashboard)/dashboard/mentor/mentees/page.tsx`<br>→ `@/features/mentor/mentees/components/mentees-page` | Mentor | Admin → /dashboard; Anonymous → /login; Student → /dashboard | 11 | none | H-06, H-13 |
| 101 | `/dashboard/mentor/opportunities` | `src/app/(dashboard)/dashboard/mentor/opportunities/page.tsx` | — | Admin → /dashboard; Anonymous → /login; Mentor → /dashboard; Student → /dashboard | 14 | none | H-06, H-13 |
| 102 | `/dashboard/mentor/sessions` | `src/app/(dashboard)/dashboard/mentor/sessions/page.tsx`<br>→ `@/features/mentor/sessions/components/sessions-page` | Mentor | Admin → /dashboard; Anonymous → /login; Student → /dashboard | 12 | none | H-06, H-13 |
| 103 | `/dashboard/mentor/task-requests` | `src/app/(dashboard)/dashboard/mentor/task-requests/page.tsx`<br>→ `@/features/mentor/task-requests/components/task-requests-page` | Mentor | Admin → /dashboard; Anonymous → /login; Student → /dashboard | 14 | none | H-06, H-13 |
| 104 | `/dashboard/mujourney` | `src/app/(dashboard)/dashboard/mujourney/page.tsx` | Admin, Student | Anonymous → /login | 5 | none | M-29, H-34 |
| 105 | `/dashboard/mujourney/[muid]` | `src/app/(dashboard)/dashboard/mujourney/[muid]/page.tsx`<br>→ `./mujourney-client` | Admin, Student | Anonymous → /login | 5 | none | M-29, H-34 |
| 106 | `/dashboard/muverse` | `src/app/(dashboard)/dashboard/muverse/page.tsx`<br>→ `./muverse-client` | Admin, Comic Admin, Student | Anonymous → /login | 4 | none | — |
| 107 | `/dashboard/profile` | `src/app/(dashboard)/dashboard/profile/page.tsx`<br>→ `./profile-client` | Admin, Associate, Campus IG Lead, Campus Lead, Comic Admin, Company, Discord Mod, District Lead, Enabler, Fellow, IG Lead, Intern, Intern Lead, Lead Enabler, Mentor, Student, Tech Team, Zonal Lead | Anonymous → /login | 19 | none | C-03, M-30, M-31, H-23, L-23 |
| 108 | `/dashboard/projects` | `src/app/(dashboard)/dashboard/projects/page.tsx`<br>→ `@/features/projects` | Admin, Student | Anonymous → /login | 5 | none | L-40, L-12 |
| 109 | `/dashboard/reports` | `src/app/(dashboard)/dashboard/reports/page.tsx`<br>→ `./event-report-client` | Admin, Student | Anonymous → /login | 4 | none | — |
| 110 | `/dashboard/search` | `src/app/(dashboard)/dashboard/search/page.tsx` | — | Admin → /dashboard/search/students; Anonymous → /login; Student → /dashboard/search/students | 5 | JS error: Error: Minified React error #310; visit https://react.dev/errors/310 for the full message or use the non-minified dev environment for full errors and additional | M-15, L-48, H-34, H-35 |
| 111 | `/dashboard/search/campuses` | `src/app/(dashboard)/dashboard/search/campuses/page.tsx`<br>→ `@/features/search` | Admin, Student | Anonymous → /login | 6 | none | M-15, L-48, H-34, H-35 |
| 112 | `/dashboard/search/mentors` | `src/app/(dashboard)/dashboard/search/mentors/page.tsx`<br>→ `@/features/search` | Admin, Student | Anonymous → /login | 5 | API GET /api/v1/notification/unread-count/ → 403  [Anonymous] | M-15, L-48, H-34, H-35 |
| 113 | `/dashboard/search/students` | `src/app/(dashboard)/dashboard/search/students/page.tsx`<br>→ `@/features/search` | Admin, Student | Anonymous → /login | 5 | none | M-15, L-48, H-34, H-35 |
| 114 | `/dashboard/sessions` | `src/app/(dashboard)/dashboard/sessions/page.tsx`<br>→ `@/features/mentor/sessions/components/student-sessions-page` | Admin, Mentor, Student | Anonymous → /login | 7 | none | — |
| 115 | `/dashboard/settings` | `src/app/(dashboard)/dashboard/settings/page.tsx`<br>→ `@/components/auth/role-gate` | Admin, Student | Anonymous → /login | 4 | none | — |
| 116 | `/dashboard/settings/account` | `src/app/(dashboard)/dashboard/settings/account/page.tsx`<br>→ `./change-password-form` | Admin, Student | Anonymous → /login | 4 | none | M-31, L-26 |
| 117 | `/dashboard/settings/organization` | `src/app/(dashboard)/dashboard/settings/organization/page.tsx`<br>→ `./organization-settings-client` | Admin, Campus Lead, Enabler, Lead Enabler, Student | Anonymous → /login | 6 | none | H-23 |
| 118 | `/dashboard/talent-pool` | `src/app/(dashboard)/dashboard/talent-pool/page.tsx`<br>→ `./talent-pool-client` | Admin, Company, Student | Anonymous → /login | 10 | API GET /api/v1/dashboard/company/mulearners/ → 400 {"general":["Access denied. Verified company profile required."]} [Admin,Student]<br>API GET /api/v1/dashboard/company/mulearners/shortlist/ → 400 {"general":["Access denied. Verified company profile required."]} [Admin,Student]<br>Schema mismatch: /api/v1/dashboard/achievement/list/ | M-57, L-41 |
| 119 | `/dashboard/url-shortener` | `src/app/(dashboard)/dashboard/url-shortener/page.tsx`<br>→ `@/features/url-shortener/components/url-shortener-view` | Admin, Associate, Fellow | Anonymous → /login; Student → /dashboard | 10 | none | L-50 |
| 120 | `/dashboard/url-shortener/[id]/analytics` | `src/app/(dashboard)/dashboard/url-shortener/[id]/analytics/page.tsx`<br>→ `@/features/url-shortener` | Admin, Associate, Fellow | Anonymous → /login; Student → /dashboard | 10 | none | L-50 |
| 121 | `/dashboard/weekly-twitches` | `src/app/(dashboard)/dashboard/weekly-twitches/page.tsx`<br>→ `@/features/weekly-twitches` | Admin, Student | Anonymous → /login | 5 | none | L-49 |
| 122 | `/dashboard/zonal` | `src/app/(dashboard)/dashboard/zonal/page.tsx` | Admin, Zonal Lead | Anonymous → /login; Student → /dashboard | 14 | API GET /api/v1/dashboard/zonal/top-districts/ → 400 {"general":["You do not have the required role to access this page."]} [Admin]<br>API GET /api/v1/dashboard/zonal/student-level/ → 400 {"general":["You do not have the required role to access this page."]} [Admin]<br>API GET /api/v1/dashboard/zonal/student-details/ → 400 {"general":["You do not have the required role to access this page."]} [Admin]<br>API GET /api/v1/dashboard/zonal/zonal-details/ → 400 {"general":["You do not have the required role to access this page."]} [Admin]<br>API GET /api/v1/dashboard/zonal/college-details/ → 400 {"general":["You do not have the required role to access this page."]} [Admin]<br>API GET /api/v1/dashboard/zonal/top-districts/ → 400 {"general":["No college organization linked to this user."]} [Zonal Lead]<br>API GET /api/v1/dashboard/zonal/student-details/ → 400 {"general":["No college organization linked to this user."]} [Zonal Lead]<br>API GET /api/v1/dashboard/zonal/student-level/ → 400 {"general":["No college organization linked to this user."]} [Zonal Lead]<br>(+2 more) | M-24, M-55 |
| 123 | `/forgot-password` | `src/app/(auth)/forgot-password/page.tsx`<br>→ `./forgot-password-client` | Anonymous | Admin → /dashboard; Student → /dashboard | 9 | none | M-34, L-17 |
| 124 | `/login` | `src/app/(auth)/login/page.tsx`<br>→ `./login-client` | Anonymous | Admin → /dashboard; Student → /dashboard | 9 | none | H-18, H-19, H-20, M-23, M-25, M-26 |
| 125 | `/onboarding/interests` | `src/app/(onboarding)/onboarding/interests/page.tsx`<br>→ `./interests-client` | — | Admin → /dashboard/management; Anonymous → /login; Student → /dashboard | 9 | none | L-18 |
| 126 | `/onboarding/organization` | `src/app/(onboarding)/onboarding/organization/page.tsx`<br>→ `./organization-client` | Admin, Student | Anonymous → /login | 3 | none | H-23 |
| 127 | `/profile/[muid]` | `src/app/(dashboard)/profile/[muid]/page.tsx`<br>→ `./publicprofile-client` | Admin, Student | Anonymous → /login | 12 | none | L-23, M-15, H-34 |
| 128 | `/register` | `src/app/(auth)/register/page.tsx`<br>→ `./register-client` | Anonymous | Admin → /dashboard; Student → /dashboard | 13 | none | C-09, C-05, M-52, L-15, L-16, M-19 |
| 129 | `/reset-password` | `src/app/(auth)/reset-password/page.tsx`<br>→ `./reset-password-client` | Anonymous | Admin → /dashboard; Student → /dashboard | 9 | none | M-34, L-17 |

## Appendix G — Every HTTP 500 seen in the dynamic test (except signature mismatches)

| Location | Exception | Endpoints | Roles that hit it | Issues |
|---|---|---|---|---|
| `api/common/common_views.py:110` | ImproperlyConfigured: Field name `name` is not valid for model `LearningCircle`. | GET `/api/v1/public/lc-list` | 19 roles | H-28 |
| `api/common/common_views.py:204` | FieldError: Cannot resolve keyword 'name' into field. Choices are: cached_rank, cached_total_karma, circle_meeting_log_circle_id, created_at | GET `/api/v1/public/lc-dashboard/` | 19 roles | H-28 |
| `api/common/common_views.py:309` | FieldError: Cannot resolve keyword 'name' into field. Choices are: cached_rank, cached_total_karma, circle_meeting_log_circle_id, created_at | GET `/api/v1/public/lc-report/` | 19 roles | H-28 |
| `api/common/common_views.py:369` | FieldError: Cannot resolve keyword 'name' into field. Choices are: cached_rank, cached_total_karma, circle_meeting_log_circle_id, created_at | GET `/api/v1/public/lc-report/csv/` | 19 roles | H-28 |
| `api/common/common_views.py:503` | FieldError: Cannot resolve keyword 'name' into field. Choices are: cached_rank, cached_total_karma, circle_meeting_log_circle_id, created_at | GET `/api/v1/public/lc-enrollment/` | 19 roles | H-28 |
| `api/common/common_views.py:555` | FieldError: Cannot resolve keyword 'name' into field. Choices are: cached_rank, cached_total_karma, circle_meeting_log_circle_id, created_at | GET `/api/v1/public/lc-enrollment/csv/` | 19 roles | H-28 |
| `api/common/common_views.py:57` | ImproperlyConfigured: Field name `name` is not valid for model `LearningCircle`. | GET `/api/v1/public/<str:circle_id>/lc-details/` | 19 roles | H-28 |
| `api/common/common_views.py:698` | TypeError: int() argument must be a string, a bytes-like object or a real number, not 'dict' | GET `/api/v1/public/gta-sandshore/` | 19 roles | M-51 (crash here was caused by the mocked reply; the real risks are listed in M-51) |
| `api/dashboard/campus/campus_views.py:503` | NotImplementedError: `create()` must be implemented. | PATCH `/api/v1/dashboard/campus/change-student-type/<str:member_id>/` | campuslead, leadenabler | L-12 |
| `api/dashboard/campus/campus_views.py:794` | ValueError: The annotation 'full_name' conflicts with a field on the model. | GET `/api/v1/dashboard/campus/student-list/` | campuslead, enabler, leadenabler, mentor | M-47 |
| `api/dashboard/campus/serializers.py:858` | AttributeError: 'UserLvlLink' object has no attribute 'first' | GET `/api/v1/dashboard/campus/learning-circles/<str:circle_id>/members/` | campuslead, enabler, leadenabler, mentor | M-47 |
| `api/dashboard/campus/serializers.py:885` | AttributeError: 'UserLvlLink' object has no attribute 'first' | GET `/api/v1/dashboard/campus/igs/<str:ig_id>/members/` | campuslead, enabler, leadenabler, mentor | M-47 |
| `api/dashboard/discord_moderator/discord_mod_views.py:37` | AttributeError: Got AttributeError when attempting to get a value for field `full_name` on serializer `KarmaActivityLogSerializer`. | GET `/api/v1/dashboard/discord-moderator/tasklist/` | 18 roles | M-46 |
| `api/dashboard/error_log/log_helper.py:291` | IndexError: list index out of range | GET `/api/v1/dashboard/error-log/graph/` | fellow, techteam | L-13 |
| `api/dashboard/karma_voucher/karma_voucher_view.py:416` | FileNotFoundError: [Errno 2] No such file or directory: './excel-templates/voucher_base_template.xlsx' | GET `/api/v1/dashboard/karma-voucher/base-template/` | 18 roles | test artefact — not a bug (template path depends on the working directory / generated dates / mocked partner reply) |
| `api/dashboard/learningcircle/learningcircle_serializer.py:27` | OverflowError: date value out of range | GET `/api/v1/dashboard/learningcircle/meeting/list-public/`<br>GET `/api/v1/dashboard/learningcircle/meeting/list/` | 19 roles | test artefact — not a bug (template path depends on the working directory / generated dates / mocked partner reply) |
| `api/dashboard/organisation/organisation_views.py:650` | FileNotFoundError: [Errno 2] No such file or directory: './excel-templates/organisation_base_template.xlsx' | GET `/api/v1/dashboard/organisation/base-template/` | 18 roles | test artefact — not a bug (template path depends on the working directory / generated dates / mocked partner reply) |
| `api/dashboard/profile/profile_view.py:941` | AttributeError: module 'api.dashboard.profile.profile_serializer' has no attribute 'UserPreferencesSerializer' | PATCH `/api/v1/dashboard/profile/user-preferences/` | 18 roles | M-48 |
| `api/dashboard/projects/projects_view.py:36` | DoesNotExist: Project matching query does not exist. | GET `/api/v1/dashboard/projects/<uuid:pk>/` | 18 roles | L-12 |
| `api/dashboard/projects/projects_view.py:57` | DoesNotExist: Project matching query does not exist. | PUT `/api/v1/dashboard/projects/<uuid:pk>/` | 18 roles | L-12 |
| `api/dashboard/roles/dash_roles_views.py:304` | TypeError: 'NoneType' object is not iterable | PATCH `/api/v1/dashboard/roles/bulk-assign/<str:role_id>/` | admin | M-02, L-29 |
| `api/dashboard/roles/dash_roles_views.py:470` | FileNotFoundError: [Errno 2] No such file or directory: './excel-templates/role_base_template.xlsx' | GET `/api/v1/dashboard/roles/base-template/` | 18 roles | test artefact — not a bug (template path depends on the working directory / generated dates / mocked partner reply) |
| `api/dashboard/task/dash_task_view.py:1158` | FileNotFoundError: [Errno 2] No such file or directory: './excel-templates/task_base_template.xlsx' | GET `/api/v1/dashboard/task/base-template/` | admin, associate, fellow | test artefact — not a bug (template path depends on the working directory / generated dates / mocked partner reply) |
| `api/dashboard/user/dash_user_views.py:315` | DoesNotExist: UserRoleLink matching query does not exist. | PATCH `/api/v1/dashboard/user/verification/<str:link_id>/` | admin | H-07, L-12, L-22 |
| `api/dashboard/user/dash_user_views.py:350` | DoesNotExist: UserRoleLink matching query does not exist. | DELETE `/api/v1/dashboard/user/verification/<str:link_id>/` | admin | H-07, L-12, L-22 |
| `api/hackathon/serializer.py:366` | IntegrityError: NOT NULL constraint failed: hackathon_submission.hackathon_id | POST `/api/v1/hackathon/submit-hackathon/` | admin | M-53 |
| `api/hackathon/serializer.py:398` | KeyError: 'muid' | POST `/api/v1/hackathon/add-organiser/<str:hackathon_id>/`<br>POST `/api/v1/hackathon/list-organiser-hackathons/<str:hackathon_id>/` | admin | M-53 |
| `api/hackathon/serializer.py:425` | AttributeError: 'NoneType' object has no attribute 'get' | GET `/api/v1/hackathon/list-applicants/`<br>GET `/api/v1/hackathon/list-applicants/<str:hackathon_id>/` | admin | M-53 |
| `api/integrations/integrations_helper.py:26` | DecodeError: Not enough segments | PATCH `/api/v1/integrations/kkem/authorization/<str:token>/` | 19 roles | L-12 |
| `api/integrations/integrations_helper.py:74` | CustomException: Invalid Authorization header | GET `/api/v1/integrations/kkem/hackathon-stats/`<br>GET `/api/v1/integrations/kkem/users/`<br>GET `/api/v1/integrations/kkem/users/<str:muid>/` | anon | L-12 |
| `api/integrations/integrations_helper.py:81` | CustomException: Invalid Authorization header | GET `/api/v1/integrations/kkem/hackathon-stats/`<br>GET `/api/v1/integrations/kkem/users/`<br>GET `/api/v1/integrations/kkem/users/<str:muid>/` | 18 roles | L-12 |
| `api/launchpad/launchpad_views.py:1024` | KeyError: 'user_type' | GET `/api/v1/launchpad/list-launchpad-students/<str:job_id>/` | 18 roles | M-50, H-26 |
| `api/launchpad/launchpad_views.py:1216` | KeyError: 'user_type' | GET `/api/v1/launchpad/hire-requests/` | 18 roles | M-50 |
| `api/launchpad/launchpad_views.py:1500` | KeyError: 'user_type' | POST `/api/v1/launchpad/send-job-invitations/` | 18 roles | M-50 |
| `api/launchpad/launchpad_views.py:1771` | KeyError: 'user_type' | GET `/api/v1/launchpad/accepted-students/`<br>GET `/api/v1/launchpad/accepted-students/<str:job_id>/` | 18 roles | M-50 |
| `api/launchpad/launchpad_views.py:1994` | KeyError: 'user_type' | POST `/api/v1/launchpad/application-final-decision/` | 18 roles | M-50 |
| `api/launchpad/launchpad_views.py:251` | KeyError: 'user_type' | POST `/api/v1/launchpad/register-recruiter/` | 18 roles | M-50 |
| `api/launchpad/launchpad_views.py:311` | KeyError: 'user_type' | POST `/api/v1/launchpad/add-job/` | 18 roles | M-50 |
| `api/launchpad/launchpad_views.py:3315` | KeyError: 'user_type' | POST `/api/v1/launchpad/change-password/` | 18 roles | M-50 |
| `api/launchpad/launchpad_views.py:426` | KeyError: 'user_type' | GET `/api/v1/launchpad/job/<str:job_id>/` | 18 roles | M-50 |
| `api/launchpad/launchpad_views.py:484` | KeyError: 'user_type' | PUT `/api/v1/launchpad/job/<str:job_id>/` | 18 roles | M-50 |
| `api/launchpad/launchpad_views.py:565` | KeyError: 'user_type' | DELETE `/api/v1/launchpad/job/<str:job_id>/` | 18 roles | M-50 |
| `api/top100_coders/top100_view.py:74` | OperationalError: no such column: u.profile_pic | GET `/api/v1/top100/leaderboard/` | 19 roles | M-49 |
| `mulearnbackend/middlewares.py:156` | AssertionError: Expected a `Response`, `HttpResponse` or `HttpStreamingResponse` to be returned from the view, but received a `<class 'NoneT | GET `/api/v1/dashboard/profile/share-user-profile/` | 18 roles | L-25 |
| `utils/permission.py:124` | IndexError: list index out of range | GET `/api/v1/dashboard/organisation/affiliation/list/`<br>GET `/api/v1/dashboard/organisation/institutes/info/<str:org_code>/`<br>GET `/api/v1/dashboard/organisation/institutes/prefill/<str:org_code>/`<br>PATCH `/api/v1/dashboard/achievement/rules/<str:rule_id>/`<br>PATCH `/api/v1/launchpad/delete-company/` | anon | L-10, L-14, C-04, M-50 |
| `utils/permission.py:137` | IndexError: list index out of range | DELETE `/api/v1/dashboard/achievement/delete/<str:achievement_id>/`<br>GET `/api/v1/dashboard/achievement/audit/<str:muid>/`<br>GET `/api/v1/dashboard/achievement/debug/<str:muid>/<str:achievement_id>/`<br>GET `/api/v1/dashboard/achievement/eligible/`<br>GET `/api/v1/dashboard/achievement/issued-log/`<br>GET `/api/v1/dashboard/achievement/list/`<br>(+24 more) | anon | C-02, L-10, H-23, L-37, H-15 |
| `utils/utils.py:100` | AttributeError: 'list' object has no attribute '_fields' | GET `/api/v1/dashboard/discord-moderator/leaderboard/`<br>GET `/api/v1/dashboard/dynamic-management/dynamic-role/`<br>GET `/api/v1/dashboard/dynamic-management/dynamic-role/create/`<br>GET `/api/v1/dashboard/dynamic-management/dynamic-user/`<br>GET `/api/v1/dashboard/dynamic-management/dynamic-user/create/`<br>GET `/api/v1/dashboard/mentor/activity/` | 18 roles | H-26 |

## Appendix H — Route/method pairs that crash because the view signature does not match the URL (L-11)

These return 500 instead of 405. Most are never called by the dashboard; they show how the shared-view pattern breaks.

| Method | Path | Error |
|---|---|---|
| DELETE | `/api/v1/dashboard/affiliation/` | TypeError: AffiliationCRUDAPI.delete() missing 1 required positional argument: 'affiliation_id' |
| PUT | `/api/v1/dashboard/affiliation/` | TypeError: AffiliationCRUDAPI.put() missing 1 required positional argument: 'affiliation_id' |
| GET | `/api/v1/dashboard/affiliation/<str:affiliation_id>/` | TypeError: AffiliationCRUDAPI.get() got an unexpected keyword argument 'affiliation_id' |
| POST | `/api/v1/dashboard/affiliation/<str:affiliation_id>/` | TypeError: AffiliationCRUDAPI.post() got an unexpected keyword argument 'affiliation_id' |
| GET | `/api/v1/dashboard/campus/execom/<str:member_id>/` | TypeError: CampusExecomAPI.get() got an unexpected keyword argument 'member_id' |
| POST | `/api/v1/dashboard/campus/execom/<str:member_id>/` | TypeError: CampusExecomAPI.post() got an unexpected keyword argument 'member_id' |
| DELETE | `/api/v1/dashboard/campus/ig-chapters/` | TypeError: CampusIGChapterAPI.delete() missing 1 required positional argument: 'chapter_id' |
| PATCH | `/api/v1/dashboard/campus/ig-chapters/` | TypeError: CampusIGChapterAPI.patch() missing 1 required positional argument: 'chapter_id' |
| GET | `/api/v1/dashboard/campus/ig-chapters/<str:chapter_id>/` | TypeError: CampusIGChapterAPI.get() got an unexpected keyword argument 'chapter_id' |
| POST | `/api/v1/dashboard/campus/ig-chapters/<str:chapter_id>/` | TypeError: CampusIGChapterAPI.post() got an unexpected keyword argument 'chapter_id' |
| DELETE | `/api/v1/dashboard/campus/social-links/` | TypeError: CampusSocialLinkAPI.delete() missing 1 required positional argument: 'link_id' |
| PUT | `/api/v1/dashboard/campus/social-links/<str:link_id>/` | TypeError: CampusSocialLinkAPI.put() got an unexpected keyword argument 'link_id' |
| DELETE | `/api/v1/dashboard/category/` | TypeError: CategoryAPI.delete() missing 1 required positional argument: 'category_id' |
| PATCH | `/api/v1/dashboard/category/` | TypeError: CategoryAPI.patch() missing 1 required positional argument: 'category_id' |
| PUT | `/api/v1/dashboard/category/` | TypeError: CategoryAPI.put() missing 1 required positional argument: 'category_id' |
| POST | `/api/v1/dashboard/category/<str:category_id>/` | TypeError: CategoryAPI.post() got an unexpected keyword argument 'category_id' |
| DELETE | `/api/v1/dashboard/channels/` | TypeError: ChannelCRUDAPI.delete() missing 1 required positional argument: 'channel_id' |
| PUT | `/api/v1/dashboard/channels/` | TypeError: ChannelCRUDAPI.put() missing 1 required positional argument: 'channel_id' |
| GET | `/api/v1/dashboard/channels/<str:channel_id>/` | TypeError: ChannelCRUDAPI.get() got an unexpected keyword argument 'channel_id' |
| POST | `/api/v1/dashboard/channels/<str:channel_id>/` | TypeError: ChannelCRUDAPI.post() got an unexpected keyword argument 'channel_id' |
| DELETE | `/api/v1/dashboard/company/mulearners/shortlist/` | TypeError: CompanyTalentShortlistAPI.delete() missing 1 required positional argument: 'user_id' |
| GET | `/api/v1/dashboard/company/mulearners/shortlist/<str:user_id>/` | TypeError: CompanyTalentShortlistAPI.get() got an unexpected keyword argument 'user_id' |
| POST | `/api/v1/dashboard/company/mulearners/shortlist/<str:user_id>/` | TypeError: CompanyTalentShortlistAPI.post() got an unexpected keyword argument 'user_id' |
| DELETE | `/api/v1/dashboard/dynamic-management/dynamic-role/` | TypeError: DynamicRoleAPI.delete() missing 1 required positional argument: 'type_id' |
| PATCH | `/api/v1/dashboard/dynamic-management/dynamic-role/` | TypeError: DynamicRoleAPI.patch() missing 1 required positional argument: 'type_id' |
| DELETE | `/api/v1/dashboard/dynamic-management/dynamic-role/create/` | TypeError: DynamicRoleAPI.delete() missing 1 required positional argument: 'type_id' |
| PATCH | `/api/v1/dashboard/dynamic-management/dynamic-role/create/` | TypeError: DynamicRoleAPI.patch() missing 1 required positional argument: 'type_id' |
| GET | `/api/v1/dashboard/dynamic-management/dynamic-role/delete/<str:type_id>/` | TypeError: DynamicRoleAPI.get() got an unexpected keyword argument 'type_id' |
| POST | `/api/v1/dashboard/dynamic-management/dynamic-role/delete/<str:type_id>/` | TypeError: DynamicRoleAPI.post() got an unexpected keyword argument 'type_id' |
| GET | `/api/v1/dashboard/dynamic-management/dynamic-role/update/<str:type_id>/` | TypeError: DynamicRoleAPI.get() got an unexpected keyword argument 'type_id' |
| POST | `/api/v1/dashboard/dynamic-management/dynamic-role/update/<str:type_id>/` | TypeError: DynamicRoleAPI.post() got an unexpected keyword argument 'type_id' |
| DELETE | `/api/v1/dashboard/dynamic-management/dynamic-user/` | TypeError: DynamicUserAPI.delete() missing 1 required positional argument: 'type_id' |
| PATCH | `/api/v1/dashboard/dynamic-management/dynamic-user/` | TypeError: DynamicUserAPI.patch() missing 1 required positional argument: 'type_id' |
| DELETE | `/api/v1/dashboard/dynamic-management/dynamic-user/create/` | TypeError: DynamicUserAPI.delete() missing 1 required positional argument: 'type_id' |
| PATCH | `/api/v1/dashboard/dynamic-management/dynamic-user/create/` | TypeError: DynamicUserAPI.patch() missing 1 required positional argument: 'type_id' |
| GET | `/api/v1/dashboard/dynamic-management/dynamic-user/delete/<str:type_id>/` | TypeError: DynamicUserAPI.get() got an unexpected keyword argument 'type_id' |
| POST | `/api/v1/dashboard/dynamic-management/dynamic-user/delete/<str:type_id>/` | TypeError: DynamicUserAPI.post() got an unexpected keyword argument 'type_id' |
| GET | `/api/v1/dashboard/dynamic-management/dynamic-user/update/<str:type_id>/` | TypeError: DynamicUserAPI.get() got an unexpected keyword argument 'type_id' |
| POST | `/api/v1/dashboard/dynamic-management/dynamic-user/update/<str:type_id>/` | TypeError: DynamicUserAPI.post() got an unexpected keyword argument 'type_id' |
| PATCH | `/api/v1/dashboard/error-log/` | TypeError: LoggerAPI.patch() missing 1 required positional argument: 'error_id' |
| GET | `/api/v1/dashboard/error-log/patch/<str:error_id>/` | TypeError: LoggerAPI.get() got an unexpected keyword argument 'error_id' |
| DELETE | `/api/v1/dashboard/ig/` | TypeError: InterestGroupAPI.delete() missing 1 required positional argument: 'pk' |
| PUT | `/api/v1/dashboard/ig/` | TypeError: InterestGroupAPI.put() missing 1 required positional argument: 'pk' |
| GET | `/api/v1/dashboard/ig/<str:pk>/` | TypeError: InterestGroupAPI.get() got an unexpected keyword argument 'pk' |
| POST | `/api/v1/dashboard/ig/<str:pk>/` | TypeError: InterestGroupAPI.post() got an unexpected keyword argument 'pk' |
| DELETE | `/api/v1/dashboard/ig/request/` | TypeError: InterestGroupRequestAPI.delete() missing 1 required positional argument: 'pk' |
| PATCH | `/api/v1/dashboard/ig/request/` | TypeError: InterestGroupRequestAPI.patch() missing 1 required positional argument: 'pk' |
| GET | `/api/v1/dashboard/ig/request/<str:pk>/` | TypeError: InterestGroupRequestAPI.get() got an unexpected keyword argument 'pk' |
| POST | `/api/v1/dashboard/ig/request/<str:pk>/` | TypeError: InterestGroupRequestAPI.post() got an unexpected keyword argument 'pk' |
| POST | `/api/v1/dashboard/intern/leave/<str:leave_id>/` | TypeError: InternLeaveRequestAPI.post() got an unexpected keyword argument 'leave_id' |
| POST | `/api/v1/dashboard/intern/leave/<str:leave_id>/cancel/` | TypeError: InternLeaveRequestAPI.post() got an unexpected keyword argument 'leave_id' |
| DELETE | `/api/v1/dashboard/intern/minutes/` | TypeError: InternGuildMinuteAPI.delete() missing 1 required positional argument: 'minute_id' |
| PUT | `/api/v1/dashboard/intern/minutes/` | TypeError: InternGuildMinuteAPI.put() missing 1 required positional argument: 'minute_id' |
| POST | `/api/v1/dashboard/intern/minutes/<str:minute_id>/` | TypeError: InternGuildMinuteAPI.post() got an unexpected keyword argument 'minute_id' |
| PATCH | `/api/v1/dashboard/intern/reviews/` | TypeError: InternWeeklyReviewAPI.patch() missing 1 required positional argument: 'review_id' |
| POST | `/api/v1/dashboard/intern/reviews/<str:review_id>/` | TypeError: InternWeeklyReviewAPI.post() got an unexpected keyword argument 'review_id' |
| PATCH | `/api/v1/dashboard/intern/timesheets/` | TypeError: InternTimesheetAPI.patch() missing 1 required positional argument: 'timesheet_id' |
| POST | `/api/v1/dashboard/intern/timesheets/<str:timesheet_id>/` | TypeError: InternTimesheetAPI.post() got an unexpected keyword argument 'timesheet_id' |
| DELETE | `/api/v1/dashboard/karma-voucher/` | TypeError: VoucherLogAPI.delete() missing 1 required positional argument: 'voucher_id' |
| PATCH | `/api/v1/dashboard/karma-voucher/` | TypeError: VoucherLogAPI.patch() missing 1 required positional argument: 'voucher_id' |
| DELETE | `/api/v1/dashboard/karma-voucher/create/` | TypeError: VoucherLogAPI.delete() missing 1 required positional argument: 'voucher_id' |
| PATCH | `/api/v1/dashboard/karma-voucher/create/` | TypeError: VoucherLogAPI.patch() missing 1 required positional argument: 'voucher_id' |
| GET | `/api/v1/dashboard/karma-voucher/delete/<str:voucher_id>/` | TypeError: VoucherLogAPI.get() got an unexpected keyword argument 'voucher_id' |
| POST | `/api/v1/dashboard/karma-voucher/delete/<str:voucher_id>/` | TypeError: VoucherLogAPI.post() got an unexpected keyword argument 'voucher_id' |
| GET | `/api/v1/dashboard/karma-voucher/update/<str:voucher_id>/` | TypeError: VoucherLogAPI.get() got an unexpected keyword argument 'voucher_id' |
| POST | `/api/v1/dashboard/karma-voucher/update/<str:voucher_id>/` | TypeError: VoucherLogAPI.post() got an unexpected keyword argument 'voucher_id' |
| DELETE | `/api/v1/dashboard/learningcircle/create/` | TypeError: LearningCircleView.delete() missing 1 required positional argument: 'circle_id' |
| PUT | `/api/v1/dashboard/learningcircle/create/` | TypeError: LearningCircleView.put() missing 1 required positional argument: 'circle_id' |
| POST | `/api/v1/dashboard/learningcircle/delete/<str:circle_id>/` | TypeError: LearningCircleView.post() got an unexpected keyword argument 'circle_id' |
| POST | `/api/v1/dashboard/learningcircle/edit/<str:circle_id>/` | TypeError: LearningCircleView.post() got an unexpected keyword argument 'circle_id' |
| POST | `/api/v1/dashboard/learningcircle/info/<str:circle_id>/` | TypeError: LearningCircleView.post() got an unexpected keyword argument 'circle_id' |
| GET | `/api/v1/dashboard/learningcircle/invite/status/<str:link_id>/` | TypeError: CircleInviteStatusAPI.get() got an unexpected keyword argument 'link_id' |
| DELETE | `/api/v1/dashboard/learningcircle/list/` | TypeError: LearningCircleView.delete() missing 1 required positional argument: 'circle_id' |
| PUT | `/api/v1/dashboard/learningcircle/list/` | TypeError: LearningCircleView.put() missing 1 required positional argument: 'circle_id' |
| DELETE | `/api/v1/dashboard/learningcircle/meeting/create/<str:circle_id>/` | TypeError: LearningCircleMeetingView.delete() got an unexpected keyword argument 'circle_id' |
| PUT | `/api/v1/dashboard/learningcircle/meeting/create/<str:circle_id>/` | TypeError: LearningCircleMeetingView.put() got an unexpected keyword argument 'circle_id' |
| POST | `/api/v1/dashboard/learningcircle/meeting/delete/<str:meet_id>/` | TypeError: LearningCircleMeetingView.post() got an unexpected keyword argument 'meet_id' |
| POST | `/api/v1/dashboard/learningcircle/meeting/edit/<str:meet_id>/` | TypeError: LearningCircleMeetingView.post() got an unexpected keyword argument 'meet_id' |
| DELETE | `/api/v1/dashboard/location/countries/` | TypeError: CountryDataAPI.delete() missing 1 required positional argument: 'country_id' |
| PATCH | `/api/v1/dashboard/location/countries/` | TypeError: CountryDataAPI.patch() missing 1 required positional argument: 'country_id' |
| POST | `/api/v1/dashboard/location/countries/<str:country_id>/` | TypeError: CountryDataAPI.post() got an unexpected keyword argument 'country_id' |
| DELETE | `/api/v1/dashboard/location/districts/` | TypeError: DistrictDataAPI.delete() missing 1 required positional argument: 'district_id' |
| PATCH | `/api/v1/dashboard/location/districts/` | TypeError: DistrictDataAPI.patch() missing 1 required positional argument: 'district_id' |
| POST | `/api/v1/dashboard/location/districts/<str:district_id>/` | TypeError: DistrictDataAPI.post() got an unexpected keyword argument 'district_id' |
| DELETE | `/api/v1/dashboard/location/states/` | TypeError: StateDataAPI.delete() missing 1 required positional argument: 'state_id' |
| PATCH | `/api/v1/dashboard/location/states/` | TypeError: StateDataAPI.patch() missing 1 required positional argument: 'state_id' |
| POST | `/api/v1/dashboard/location/states/<str:state_id>/` | TypeError: StateDataAPI.post() got an unexpected keyword argument 'state_id' |
| DELETE | `/api/v1/dashboard/location/zones/` | TypeError: ZoneDataAPI.delete() missing 1 required positional argument: 'zone_id' |
| PATCH | `/api/v1/dashboard/location/zones/` | TypeError: ZoneDataAPI.patch() missing 1 required positional argument: 'zone_id' |
| POST | `/api/v1/dashboard/location/zones/<str:zone_id>/` | TypeError: ZoneDataAPI.post() got an unexpected keyword argument 'zone_id' |
| DELETE | `/api/v1/dashboard/manage-interns/interns/` | TypeError: ManageInternAPI.delete() missing 1 required positional argument: 'intern_id' |
| PATCH | `/api/v1/dashboard/manage-interns/interns/` | TypeError: ManageInternAPI.patch() missing 1 required positional argument: 'intern_id' |
| POST | `/api/v1/dashboard/manage-interns/interns/<str:intern_id>/` | TypeError: ManageInternAPI.post() got an unexpected keyword argument 'intern_id' |
| DELETE | `/api/v1/dashboard/manage-interns/tasks/` | TypeError: ManageInternTaskAPI.delete() missing 1 required positional argument: 'task_id' |
| PATCH | `/api/v1/dashboard/manage-interns/tasks/` | TypeError: ManageInternTaskAPI.patch() missing 1 required positional argument: 'task_id' |
| POST | `/api/v1/dashboard/manage-interns/tasks/<str:task_id>/` | TypeError: ManageInternTaskAPI.post() got an unexpected keyword argument 'task_id' |
| DELETE | `/api/v1/dashboard/mentor/admin/assign/` | TypeError: AdminAssignMentorAPI.delete() missing 1 required positional argument: 'user_muid' |
| POST | `/api/v1/dashboard/mentor/admin/assign/<str:user_muid>/` | TypeError: AdminAssignMentorAPI.post() got an unexpected keyword argument 'user_muid' |
| DELETE | `/api/v1/dashboard/mentor/availability/` | TypeError: MentorAvailabilitySlotAPI.delete() missing 1 required positional argument: 'slot_id' |
| PATCH | `/api/v1/dashboard/mentor/availability/` | TypeError: MentorAvailabilitySlotAPI.patch() missing 1 required positional argument: 'slot_id' |
| POST | `/api/v1/dashboard/mentor/availability/<str:slot_id>/` | TypeError: MentorAvailabilitySlotAPI.post() got an unexpected keyword argument 'slot_id' |
| DELETE | `/api/v1/dashboard/organisation/departments/` | TypeError: DepartmentAPI.delete() missing 1 required positional argument: 'department_id' |
| PUT | `/api/v1/dashboard/organisation/departments/` | TypeError: DepartmentAPI.put() missing 1 required positional argument: 'department_id' |
| DELETE | `/api/v1/dashboard/organisation/departments/create/` | TypeError: DepartmentAPI.delete() missing 1 required positional argument: 'department_id' |
| PUT | `/api/v1/dashboard/organisation/departments/create/` | TypeError: DepartmentAPI.put() missing 1 required positional argument: 'department_id' |
| GET | `/api/v1/dashboard/organisation/departments/delete/<str:department_id>/` | TypeError: DepartmentAPI.get() got an unexpected keyword argument 'department_id' |
| POST | `/api/v1/dashboard/organisation/departments/delete/<str:department_id>/` | TypeError: DepartmentAPI.post() got an unexpected keyword argument 'department_id' |
| GET | `/api/v1/dashboard/organisation/departments/edit/<str:department_id>/` | TypeError: DepartmentAPI.get() got an unexpected keyword argument 'department_id' |
| POST | `/api/v1/dashboard/organisation/departments/edit/<str:department_id>/` | TypeError: DepartmentAPI.post() got an unexpected keyword argument 'department_id' |
| DELETE | `/api/v1/dashboard/organisation/institutes/create/` | TypeError: InstitutionPostUpdateDeleteAPI.delete() missing 1 required positional argument: 'org_code' |
| PUT | `/api/v1/dashboard/organisation/institutes/create/` | TypeError: InstitutionPostUpdateDeleteAPI.put() missing 1 required positional argument: 'org_code' |
| POST | `/api/v1/dashboard/organisation/institutes/delete/<str:org_code>/` | TypeError: InstitutionPostUpdateDeleteAPI.post() got an unexpected keyword argument 'org_code' |
| POST | `/api/v1/dashboard/organisation/institutes/edit/<str:org_code>/` | TypeError: InstitutionPostUpdateDeleteAPI.post() got an unexpected keyword argument 'org_code' |
| DELETE | `/api/v1/dashboard/organisation/institutes/org/affiliation/create/` | TypeError: AffiliationGetPostUpdateDeleteAPI.delete() missing 1 required positional argument: 'affiliation_id' |
| PUT | `/api/v1/dashboard/organisation/institutes/org/affiliation/create/` | TypeError: AffiliationGetPostUpdateDeleteAPI.put() missing 1 required positional argument: 'affiliation_id' |
| GET | `/api/v1/dashboard/organisation/institutes/org/affiliation/delete/<str:affiliation_id>/` | TypeError: AffiliationGetPostUpdateDeleteAPI.get() got an unexpected keyword argument 'affiliation_id' |
| POST | `/api/v1/dashboard/organisation/institutes/org/affiliation/delete/<str:affiliation_id>/` | TypeError: AffiliationGetPostUpdateDeleteAPI.post() got an unexpected keyword argument 'affiliation_id' |
| GET | `/api/v1/dashboard/organisation/institutes/org/affiliation/edit/<str:affiliation_id>/` | TypeError: AffiliationGetPostUpdateDeleteAPI.get() got an unexpected keyword argument 'affiliation_id' |
| POST | `/api/v1/dashboard/organisation/institutes/org/affiliation/edit/<str:affiliation_id>/` | TypeError: AffiliationGetPostUpdateDeleteAPI.post() got an unexpected keyword argument 'affiliation_id' |
| DELETE | `/api/v1/dashboard/organisation/institutes/org/affiliation/show/` | TypeError: AffiliationGetPostUpdateDeleteAPI.delete() missing 1 required positional argument: 'affiliation_id' |
| PUT | `/api/v1/dashboard/organisation/institutes/org/affiliation/show/` | TypeError: AffiliationGetPostUpdateDeleteAPI.put() missing 1 required positional argument: 'affiliation_id' |
| PUT | `/api/v1/dashboard/profile/share-user-profile/<str:uuid>/` | TypeError: ShareUserProfileAPI.put() got an unexpected keyword argument 'uuid' |
| DELETE | `/api/v1/dashboard/projects/<uuid:project_id>/members/` | TypeError: ProjectMemberAPI.delete() missing 1 required positional argument: 'pk' |
| GET | `/api/v1/dashboard/projects/<uuid:project_id>/members/<uuid:pk>/` | TypeError: ProjectMemberAPI.get() got an unexpected keyword argument 'pk' |
| POST | `/api/v1/dashboard/projects/<uuid:project_id>/members/<uuid:pk>/` | TypeError: ProjectMemberAPI.post() got an unexpected keyword argument 'pk' |
| DELETE | `/api/v1/dashboard/projects/comment/` | TypeError: ProjectCommentAPI.delete() missing 1 required positional argument: 'pk' |
| PUT | `/api/v1/dashboard/projects/comment/` | TypeError: ProjectCommentAPI.put() missing 1 required positional argument: 'pk' |
| POST | `/api/v1/dashboard/projects/comment/<uuid:pk>/` | TypeError: ProjectCommentAPI.post() got an unexpected keyword argument 'pk' |
| DELETE | `/api/v1/dashboard/projects/vote/` | TypeError: ProjectVoteAPI.delete() missing 1 required positional argument: 'pk' |
| POST | `/api/v1/dashboard/projects/vote/<uuid:pk>/` | TypeError: ProjectVoteAPI.post() got an unexpected keyword argument 'pk' |
| DELETE | `/api/v1/dashboard/roles/` | TypeError: RoleAPI.delete() missing 1 required positional argument: 'roles_id' |
| PATCH | `/api/v1/dashboard/roles/` | TypeError: RoleAPI.patch() missing 1 required positional argument: 'roles_id' |
| GET | `/api/v1/dashboard/roles/<str:roles_id>/` | TypeError: RoleAPI.get() got an unexpected keyword argument 'roles_id' |
| POST | `/api/v1/dashboard/roles/<str:roles_id>/` | TypeError: RoleAPI.post() got an unexpected keyword argument 'roles_id' |
| GET | `/api/v1/dashboard/roles/bulk-assign/` | TypeError: UserRoleLinkManagement.get() missing 1 required positional argument: 'role_id' |
| PATCH | `/api/v1/dashboard/roles/bulk-assign/` | TypeError: UserRoleLinkManagement.patch() missing 1 required positional argument: 'role_id' |
| POST | `/api/v1/dashboard/roles/bulk-assign/` | TypeError: UserRoleLinkManagement.post() missing 1 required positional argument: 'role_id' |
| PUT | `/api/v1/dashboard/roles/bulk-assign/` | TypeError: UserRoleLinkManagement.put() missing 1 required positional argument: 'role_id' |
| GET | `/api/v1/dashboard/task/<str:task_id>/review/` | TypeError: AdminTaskApprovalAPI.get() got an unexpected keyword argument 'task_id' |
| DELETE | `/api/v1/dashboard/task/list-task-type/` | TypeError: TaskTypeCrudAPI.delete() missing 1 required positional argument: 'task_type_id' |
| PUT | `/api/v1/dashboard/task/list-task-type/` | TypeError: TaskTypeCrudAPI.put() missing 1 required positional argument: 'task_type_id' |
| PATCH | `/api/v1/dashboard/task/pending/` | TypeError: AdminTaskApprovalAPI.patch() missing 1 required positional argument: 'task_id' |
| GET | `/api/v1/dashboard/task/task-type/<str:task_type_id>/` | TypeError: TaskTypeCrudAPI.get() got an unexpected keyword argument 'task_type_id' |
| POST | `/api/v1/dashboard/task/task-type/<str:task_type_id>/` | TypeError: TaskTypeCrudAPI.post() got an unexpected keyword argument 'task_type_id' |
| DELETE | `/api/v1/dashboard/user/verification/` | TypeError: UserVerificationAPI.delete() missing 1 required positional argument: 'link_id' |
| PATCH | `/api/v1/dashboard/user/verification/` | TypeError: UserVerificationAPI.patch() missing 1 required positional argument: 'link_id' |
| GET | `/api/v1/dashboard/user/verification/<str:link_id>/` | TypeError: UserVerificationAPI.get() got an unexpected keyword argument 'link_id' |
| DELETE | `/api/v1/hackathon/add-organiser/<str:hackathon_id>/` | TypeError: HackathonOrganiserAPI.delete() got an unexpected keyword argument 'hackathon_id' |
| DELETE | `/api/v1/hackathon/create-hackathon/` | TypeError: HackathonManagementAPI.delete() missing 1 required positional argument: 'hackathon_id' |
| PUT | `/api/v1/hackathon/create-hackathon/` | TypeError: HackathonManagementAPI.put() missing 1 required positional argument: 'hackathon_id' |
| POST | `/api/v1/hackathon/delete-hackathon/<str:hackathon_id>/` | TypeError: HackathonManagementAPI.post() got an unexpected keyword argument 'hackathon_id' |
| GET | `/api/v1/hackathon/delete-organiser/<str:organiser_link_id>/` | TypeError: HackathonOrganiserAPI.get() got an unexpected keyword argument 'organiser_link_id' |
| POST | `/api/v1/hackathon/delete-organiser/<str:organiser_link_id>/` | TypeError: HackathonOrganiserAPI.post() got an unexpected keyword argument 'organiser_link_id' |
| POST | `/api/v1/hackathon/edit-hackathon/<str:hackathon_id>/` | TypeError: HackathonManagementAPI.post() got an unexpected keyword argument 'hackathon_id' |
| DELETE | `/api/v1/hackathon/list-hackathons/` | TypeError: HackathonManagementAPI.delete() missing 1 required positional argument: 'hackathon_id' |
| PUT | `/api/v1/hackathon/list-hackathons/` | TypeError: HackathonManagementAPI.put() missing 1 required positional argument: 'hackathon_id' |
| POST | `/api/v1/hackathon/list-hackathons/<str:hackathon_id>/` | TypeError: HackathonManagementAPI.post() got an unexpected keyword argument 'hackathon_id' |
| DELETE | `/api/v1/hackathon/list-hackathons/upcoming/` | TypeError: HackathonManagementAPI.delete() missing 1 required positional argument: 'hackathon_id' |
| PUT | `/api/v1/hackathon/list-hackathons/upcoming/` | TypeError: HackathonManagementAPI.put() missing 1 required positional argument: 'hackathon_id' |
| DELETE | `/api/v1/hackathon/list-organiser-hackathons/<str:hackathon_id>/` | TypeError: HackathonOrganiserAPI.delete() got an unexpected keyword argument 'hackathon_id' |
| PATCH | `/api/v1/integrations/kkem/authorization/` | TypeError: KKEMAuthorizationAPI.patch() missing 1 required positional argument: 'token' |
| POST | `/api/v1/integrations/kkem/authorization/<str:token>/` | TypeError: KKEMAuthorizationAPI.post() got an unexpected keyword argument 'token' |
| PUT | `/api/v1/launchpad/user-college-link/` | TypeError: LaunchPadUser.put() missing 1 required positional argument: 'email' |
| GET | `/api/v1/launchpad/user-college-link/<str:email>` | TypeError: LaunchPadUser.get() got an unexpected keyword argument 'email' |
| POST | `/api/v1/launchpad/user-college-link/<str:email>` | TypeError: LaunchPadUser.post() got an unexpected keyword argument 'email' |
| DELETE | `/api/v1/url-shortener/create/` | TypeError: UrlShortenerAPI.delete() missing 1 required positional argument: 'url_id' |
| PUT | `/api/v1/url-shortener/create/` | TypeError: UrlShortenerAPI.put() missing 1 required positional argument: 'url_id' |
| GET | `/api/v1/url-shortener/delete/<str:url_id>/` | TypeError: UrlShortenerAPI.get() got an unexpected keyword argument 'url_id' |
| POST | `/api/v1/url-shortener/delete/<str:url_id>/` | TypeError: UrlShortenerAPI.post() got an unexpected keyword argument 'url_id' |
| GET | `/api/v1/url-shortener/edit/<str:url_id>/` | TypeError: UrlShortenerAPI.get() got an unexpected keyword argument 'url_id' |
| POST | `/api/v1/url-shortener/edit/<str:url_id>/` | TypeError: UrlShortenerAPI.post() got an unexpected keyword argument 'url_id' |
| DELETE | `/api/v1/url-shortener/list/` | TypeError: UrlShortenerAPI.delete() missing 1 required positional argument: 'url_id' |
| PUT | `/api/v1/url-shortener/list/` | TypeError: UrlShortenerAPI.put() missing 1 required positional argument: 'url_id' |

## Appendix I — Performance of every backend endpoint (1,140 rows)

How to read it:
- **SQL queries (small → large data):** SQL queries for one call on the small and on the large test database (§10.1), for the role that made the most queries. A big jump means one or more queries per row (N+1).
- **Most repeated query:** how many times the same query shape ran in one call, and on which table (shown when 3 or more).
- **Rows:** the longest list in the response on the large data ("paged" = the response has pagination).
- **Other performance notes:** measured findings (no index, returns every row, outbound HTTP, cached response) and the static code scan (query inside a loop, e-mail in the request, spreadsheet building, and SerializerMethodFields that run a query per row). For write methods the static scan is the only data.
- **Not measured:** no role got a successful response with the test data (usually no matching object for the id in the URL, or a crash listed in Appendix G/H).

| # | Method | Endpoint (`/api/v1/` prefix removed) | Measured as | SQL queries (small → large data) | Most repeated query | Rows (large data) | Size (large data) | Other performance notes | Issues |
|---|---|---|---|---|---|---|---|---|---|
| 1 | POST | `auth/user-authentication/` | — | write (not load-tested) | — | — | — | outbound HTTP in the request (api/auth/auth_views.py:152) | — |
| 2 | POST | `auth/google-mobile/` | — | write (not load-tested) | — | — | — | outbound HTTP in the request (api/auth/auth_views.py:38) | — |
| 3 | POST | `auth/apple-mobile/` | — | write (not load-tested) | — | — | — | outbound HTTP in the request (api/auth/auth_views.py:97) | — |
| 4 | POST | `auth/refresh-token/` | — | write (not load-tested) | — | — | — | outbound HTTP in the request (api/auth/auth_views.py:206) | — |
| 5 | POST | `register/` | — | write (not load-tested) | — | — | — | — | — |
| 6 | GET | `register/role/list/` | Admin | 1 → 1 | — | 110 | 12.6 KB | response cached; returns every row (no paging) | M-65 |
| 7 | GET | `register/colleges/` | Admin | 1 → 1 | — | 11 | 0.8 KB | response cached | — |
| 8 | GET | `register/department/list/` | Admin | 1 → 1 | — | 28 | 4.4 KB | response cached | — |
| 9 | GET | `register/location/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 10 | GET | `register/country/list/` | Admin | 1 → 1 | — | 245 | 31.4 KB | response cached | — |
| 11 | POST | `register/state/list/` | — | write (not load-tested) | — | — | — | — | — |
| 12 | POST | `register/district/list/` | — | write (not load-tested) | — | — | — | — | — |
| 13 | POST | `register/college/list/` | — | write (not load-tested) | — | — | — | — | — |
| 14 | GET | `register/company/list/` | Admin | 1 → 1 | — | 1 | 0.1 KB | response cached | — |
| 15 | GET | `register/community/list/` | Admin | 1 → 1 | — | 0 | 0.1 KB | response cached | — |
| 16 | POST | `register/schools/list/` | — | write (not load-tested) | — | — | — | — | — |
| 17 | GET | `register/area-of-interest/list/` | Admin | 1 → 1 | — | 7 | 0.6 KB | response cached | — |
| 18 | POST | `register/lc/user-validation/` | — | write (not load-tested) | — | — | — | — | — |
| 19 | POST | `register/email-verification/` | — | write (not load-tested) | — | — | — | — | — |
| 20 | GET | `register/user-country/` | Admin | 1 → 1 | — | 245 | 22.8 KB | response cached | — |
| 21 | GET | `register/user-state/` | Admin | 1 → 1 | — | — | 0.1 KB | — | — |
| 22 | GET | `register/user-zone/` | Admin | 1 → 1 | — | — | 0.1 KB | — | — |
| 23 | POST | `register/select-domains/` | — | write (not load-tested) | — | — | — | — | — |
| 24 | POST | `register/select-endgoals/` | — | write (not load-tested) | — | — | — | — | — |
| 25 | GET | `register/connect-discord/` | — | not measured (no successful response in test data; 400) | — | — | — | outbound HTTP in the request (api/register/register_views.py:54) | — |
| 26 | POST | `register/organization/create/` | — | write (not load-tested) | — | — | — | — | — |
| 27 | GET | `leaderboard/students/` | Anonymous | 1 → 2 | — | 20 | 2.3 KB | — | H-37 |
| 28 | GET | `leaderboard/students-monthly/` | Anonymous | 1 → 1 | — | 20 | 2.4 KB | — | H-37 |
| 29 | GET | `leaderboard/college/` | Anonymous | 1 → 1 | — | 11 | 1.4 KB | — | H-37 |
| 30 | GET | `leaderboard/college-monthly/` | Anonymous | 1 → 1 | — | 11 | 1.1 KB | response cached; no index: karma_activity_log(created_at) | H-37, M-64 |
| 31 | GET | `leaderboard/wadhwani-college/` | Anonymous | 1 → 1 | — | 0 | 0.1 KB | no index: task_list(hashtag) | M-64 |
| 32 | GET | `leaderboard/wadhwani-zonal/` | Anonymous | 1 → 1 | — | 0 | 0.1 KB | no index: task_list(hashtag) | M-64 |
| 33 | GET | `leaderboard/ig-mentor/<str:ig_id>/` | Admin | 2 → 2 | — | 1 | 0.2 KB | — | — |
| 34 | GET | `leaderboard/campus-mentor/<str:campus_id>/` | Admin | 2 → 2 | — | 1 | 0.2 KB | — | — |
| 35 | GET | `leaderboard/company-mentor/<str:company_id>/` | Admin | 2 → 2 | — | 1 | 0.2 KB | — | — |
| 36 | GET | `dashboard/calendar/events/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 37 | GET | `dashboard/home/learner/summary/` | Discord Mod | 8 → 8 | — | — | 0.3 KB | no index: circle_meeting_log(meet_time); no index: wallet(karma) | M-64 |
| 38 | GET | `dashboard/home/learner/streak/` | Discord Mod | 2 → 2 | — | 1 | 0.2 KB | — | — |
| 39 | GET | `dashboard/user/preferences/` | Admin | 1 → 1 | — | — | 0.1 KB | — | — |
| 40 | PATCH | `dashboard/user/preferences/` | — | write (not load-tested) | — | — | — | — | — |
| 41 | GET | `dashboard/user/search/` | Admin | 5 → 5 | — | 10 (paged) | 4.4 KB | — | — |
| 42 | GET | `dashboard/user/verification/` | Admin | 6 → 9 | — | 10 (paged) | 11.3 KB | per-row method fields: UserVerificationSerializer: role_profile | — |
| 43 | PATCH | `dashboard/user/verification/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/dashboard/user/dash_user_views.py:335) | M-70 |
| 44 | DELETE | `dashboard/user/verification/` | — | write (not load-tested) | — | — | — | — | — |
| 45 | GET | `dashboard/user/verification/csv/` | Admin | 5 → 8 | — | — | 5.5 KB | per-row method fields: UserVerificationSerializer: role_profile | — |
| 46 | GET | `dashboard/user/verification/<str:link_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: UserVerificationSerializer: role_profile | — |
| 47 | PATCH | `dashboard/user/verification/<str:link_id>/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/dashboard/user/dash_user_views.py:335) | M-70 |
| 48 | DELETE | `dashboard/user/verification/<str:link_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 49 | GET | `dashboard/user/verification/<str:link_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: UserVerificationSerializer: role_profile | — |
| 50 | PATCH | `dashboard/user/verification/<str:link_id>/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/dashboard/user/dash_user_views.py:335) | M-70 |
| 51 | DELETE | `dashboard/user/verification/<str:link_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 52 | GET | `dashboard/user/organization/` | Admin | 2 → 2 | — | 1 | 0.2 KB | — | — |
| 53 | POST | `dashboard/user/organization/` | — | write (not load-tested) | — | — | — | — | — |
| 54 | GET | `dashboard/user/organization/list/` | Admin | 2 → 2 | — | 1 | 0.2 KB | — | — |
| 55 | POST | `dashboard/user/organization/list/` | — | write (not load-tested) | — | — | — | — | — |
| 56 | GET | `dashboard/user/info/` | Company | 11 → 11 | — | 1 | 0.4 KB | — | H-40 |
| 57 | POST | `dashboard/user/forgot-password/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/dashboard/user/dash_user_views.py:422) | M-70 |
| 58 | POST | `dashboard/user/reset-password/verify-token/<str:token>/` | — | write (not load-tested) | — | — | — | — | — |
| 59 | POST | `dashboard/user/reset-password/<str:token>/` | — | write (not load-tested) | — | — | — | — | — |
| 60 | POST | `dashboard/user/profile/update/` | — | write (not load-tested) | — | — | — | — | — |
| 61 | PATCH | `dashboard/user/profile/update/` | — | write (not load-tested) | — | — | — | — | — |
| 62 | GET | `dashboard/user/csv/` | Admin | 1 → 1 | — | — | 1173.2 KB | — | — |
| 63 | GET | `dashboard/user/` | Admin | 2 → 2 | — | 10 (paged) | 4.6 KB | — | — |
| 64 | GET | `dashboard/user/<str:user_id>/` | Admin | 6 → 6 | — | 1 | 0.6 KB | — | — |
| 65 | PATCH | `dashboard/user/<str:user_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 66 | DELETE | `dashboard/user/<str:user_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 67 | GET | `dashboard/user/<str:user_id>/` | Admin | 6 → 6 | — | 1 | 0.6 KB | — | — |
| 68 | PATCH | `dashboard/user/<str:user_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 69 | DELETE | `dashboard/user/<str:user_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 70 | GET | `dashboard/user/<str:user_id>/` | Admin | 6 → 6 | — | 1 | 0.6 KB | — | — |
| 71 | PATCH | `dashboard/user/<str:user_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 72 | DELETE | `dashboard/user/<str:user_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 73 | GET | `dashboard/zonal/zonal-details/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: ZonalDetailsSerializer: rank, karma, total_members, active_members | — |
| 74 | GET | `dashboard/zonal/top-districts/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 75 | GET | `dashboard/zonal/student-level/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: ZonalStudentLevelStatusSerializer: students_count | — |
| 76 | GET | `dashboard/zonal/student-details/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 77 | GET | `dashboard/zonal/student-details/csv/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 78 | GET | `dashboard/zonal/college-details/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 79 | GET | `dashboard/zonal/college-details/csv/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 80 | GET | `dashboard/district/district-details/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: DistrictDetailsSerializer: rank, district_lead, karma, total_members | — |
| 81 | GET | `dashboard/district/top-campus/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 82 | GET | `dashboard/district/student-level/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: DistrictStudentLevelStatusSerializer: students_count | — |
| 83 | GET | `dashboard/district/student-details/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 84 | GET | `dashboard/district/student-details/csv/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 85 | GET | `dashboard/district/college-details/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 86 | GET | `dashboard/district/college-details/csv/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 87 | GET | `dashboard/campus/home-summary/` | Admin | 17 → 17 | — | 5 | 1.8 KB | no index: karma_activity_log(created_at); no index: wallet(karma_last_updated_at) | M-66, M-64 |
| 88 | GET | `dashboard/campus/member-funnel/` | Admin | 7 → 7 | — | 5 | 0.5 KB | no index: wallet(karma_last_updated_at) | M-66, M-64 |
| 89 | GET | `dashboard/campus/circle-health/` | Admin | 5 → 5 | — | 1 | 0.4 KB | — | — |
| 90 | GET | `dashboard/campus/recent-activity/` | Admin | 3 → 3 | — | 1 | 0.5 KB | — | — |
| 91 | GET | `dashboard/campus/campus-list/` | Admin | 2 → 2 | — | 10 (paged) | 1.0 KB | — | — |
| 92 | GET | `dashboard/campus/campus-details/` | Mentor | 18 → 18 | — | 2 | 0.8 KB | per-row method fields: CampusDetailsSerializer: lead, campus_level, active_members, total_karma | M-66 |
| 93 | GET | `dashboard/campus/student-level/` | Admin | 3 → 3 | — | 47 | 1.6 KB | — | M-66 |
| 94 | GET | `dashboard/campus/student-level/<str:org_id>/` | Admin | 2 → 2 | — | 47 | 1.6 KB | — | M-66 |
| 95 | GET | `dashboard/campus/student-details/` | Mentor | 8 → 8 | — | 10 (paged) | 2.9 KB | — | — |
| 96 | GET | `dashboard/campus/student-details/csv/` | Mentor | 7 → 7 | — | — | 1.6 KB | — | — |
| 97 | GET | `dashboard/campus/weekly-karma/` | Admin | 9 → 9 | 7× `karma_activity_log` | — | 0.2 KB | index unusable: karma_activity_log(django_datetime_cast_date(created_at)) | M-66, M-64 |
| 98 | GET | `dashboard/campus/weekly-karma/<str:org_id>/` | Admin | 8 → 8 | 7× `karma_activity_log` | — | 0.2 KB | index unusable: karma_activity_log(django_datetime_cast_date(created_at)) | M-66, M-64 |
| 99 | PATCH | `dashboard/campus/change-student-type/<str:member_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 100 | POST | `dashboard/campus/transfer-lead-role/` | — | write (not load-tested) | — | — | — | — | — |
| 101 | POST | `dashboard/campus/transfer-enabler-role/` | — | write (not load-tested) | — | — | — | — | — |
| 102 | GET | `dashboard/campus/transfer-ig-role/` | Campus Lead | 3 → 3 | — | 1 | 0.1 KB | — | — |
| 103 | POST | `dashboard/campus/transfer-ig-role/` | — | write (not load-tested) | — | — | — | — | — |
| 104 | GET | `dashboard/campus/events/` | Mentor | 7 → 7 | — | 1 (paged) | 0.5 KB | no index: events(deleted_at,scope,scope_org_id,status) | M-64 |
| 105 | GET | `dashboard/campus/events/distribution/` | Mentor | 6 → 6 | — | 0 | 0.1 KB | no index: events(deleted_at,scope,scope_org_id) | M-64 |
| 106 | GET | `dashboard/campus/execom/` | Mentor | 6 → 6 | — | 0 | 0.1 KB | — | — |
| 107 | POST | `dashboard/campus/execom/` | — | write (not load-tested) | — | — | — | — | — |
| 108 | DELETE | `dashboard/campus/execom/` | — | write (not load-tested) | — | — | — | — | — |
| 109 | GET | `dashboard/campus/execom/roles/` | Mentor | 7 → 7 | — | 32 | 2.3 KB | — | — |
| 110 | POST | `dashboard/campus/execom/roles/` | — | write (not load-tested) | — | — | — | — | — |
| 111 | GET | `dashboard/campus/execom/search/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 112 | GET | `dashboard/campus/execom/<str:member_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 113 | POST | `dashboard/campus/execom/<str:member_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 114 | DELETE | `dashboard/campus/execom/<str:member_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 115 | GET | `dashboard/campus/ig-chapters/` | Mentor | 8 → 12 | 5× `organization` | 3 | 1.0 KB | per-row method fields: CampusIGChapterListSerializer: campus_ig_member_count | — |
| 116 | POST | `dashboard/campus/ig-chapters/` | — | write (not load-tested) | — | — | — | — | — |
| 117 | PATCH | `dashboard/campus/ig-chapters/` | — | write (not load-tested) | — | — | — | — | — |
| 118 | DELETE | `dashboard/campus/ig-chapters/` | — | write (not load-tested) | — | — | — | — | — |
| 119 | GET | `dashboard/campus/ig-chapters/<str:chapter_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: CampusIGChapterListSerializer: campus_ig_member_count | — |
| 120 | POST | `dashboard/campus/ig-chapters/<str:chapter_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 121 | PATCH | `dashboard/campus/ig-chapters/<str:chapter_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 122 | DELETE | `dashboard/campus/ig-chapters/<str:chapter_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 123 | POST | `dashboard/campus/ig-chapters/<str:chapter_id>/join/` | — | write (not load-tested) | — | — | — | — | — |
| 124 | DELETE | `dashboard/campus/ig-chapters/<str:chapter_id>/leave/` | — | write (not load-tested) | — | — | — | — | — |
| 125 | PUT | `dashboard/campus/social-links/` | — | write (not load-tested) | — | — | — | — | — |
| 126 | DELETE | `dashboard/campus/social-links/` | — | write (not load-tested) | — | — | — | — | — |
| 127 | PUT | `dashboard/campus/social-links/<str:link_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 128 | DELETE | `dashboard/campus/social-links/<str:link_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 129 | GET | `dashboard/campus/student-list/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 130 | GET | `dashboard/campus/students/<str:muid>/activity/` | Mentor | 7 → 8 | — | 10 (paged) | 2.3 KB | — | — |
| 131 | GET | `dashboard/campus/igs/` | Mentor | 7 → 7 | — | 7 (paged) | 1.2 KB | no index: user_ig_link(assignment_type) | M-64 |
| 132 | GET | `dashboard/campus/igs/<str:ig_id>/members/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 133 | GET | `dashboard/campus/learning-circles/` | Mentor | 8 → 8 | — | 1 (paged) | 0.3 KB | — | — |
| 134 | GET | `dashboard/campus/learning-circles/<str:circle_id>/members/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 135 | GET | `dashboard/campus/analytics/karma-trend/` | Mentor | 6 → 6 | — | 1 | 0.1 KB | response cached; no index: karma_activity_log(created_at) | M-66, M-64 |
| 136 | GET | `dashboard/campus/analytics/growth/` | Mentor | 9 → 9 | — | 2 | 0.3 KB | response cached | — |
| 137 | GET | `dashboard/campus/showcase/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 138 | PATCH | `dashboard/campus/showcase/` | — | write (not load-tested) | — | — | — | — | — |
| 139 | POST | `dashboard/campus/assign-mentor/` | — | write (not load-tested) | — | — | — | — | — |
| 140 | GET | `dashboard/campus/sessions/list/` | Campus IG Lead | 4 → 4 | — | 0 (paged) | 0.2 KB | per-row method fields: SessionListSerializer: entity_name | — |
| 141 | GET | `dashboard/campus/<str:org_id>/` | Admin | 14 → 16 | 3× `user_ig_link` | 10 | 2.6 KB | no index: wallet(karma_last_updated_at); per-row method fields: CampusDetailsPublicSerializer: total_karma, rank, social_links, campus_lead | M-66, M-64 |
| 142 | GET | `dashboard/campus/<str:org_id>/leaderboard/` | Admin | 4 → 4 | — | 10 (paged) | 3.2 KB | — | — |
| 143 | GET | `dashboard/campus/<str:org_id>/karma-by-cluster/` | Admin | 2 → 2 | — | — | 0.2 KB | — | — |
| 144 | GET | `dashboard/enabler/home-summary/` | Enabler | 3 → 3 | — | — | 0.1 KB | — | — |
| 145 | GET | `dashboard/enabler/campuses/` | Enabler | 4 → 4 | — | 1 (paged) | 0.4 KB | — | — |
| 146 | GET | `dashboard/enabler/campuses/<str:campus_id>/review/` | Enabler | 4 → 4 | — | — | 0.3 KB | — | — |
| 147 | GET | `dashboard/enabler/campuses/<str:campus_id>/notes/` | Enabler | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 148 | POST | `dashboard/enabler/campuses/<str:campus_id>/notes/` | — | write (not load-tested) | — | — | — | — | — |
| 149 | PATCH | `dashboard/enabler/campuses/<str:campus_id>/notes/` | — | write (not load-tested) | — | — | — | — | — |
| 150 | DELETE | `dashboard/enabler/campuses/<str:campus_id>/notes/` | — | write (not load-tested) | — | — | — | — | — |
| 151 | GET | `dashboard/enabler/reports/` | Enabler | 4 → 4 | — | 1 | 0.3 KB | — | — |
| 152 | GET | `dashboard/roles/user-role/<str:role_id>/` | Admin | 2 → 2 | — | 10 (paged) | 0.8 KB | — | — |
| 153 | GET | `dashboard/roles/base-template/` | — | not measured (no successful response in test data; 500) | — | — | — | builds a spreadsheet/CSV in the request (api/dashboard/roles/dash_roles_views.py:470) | — |
| 154 | GET | `dashboard/roles/bulk-assign/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 155 | POST | `dashboard/roles/bulk-assign/` | — | write (not load-tested) | — | — | — | — | — |
| 156 | PUT | `dashboard/roles/bulk-assign/` | — | write (not load-tested) | — | — | — | — | — |
| 157 | PATCH | `dashboard/roles/bulk-assign/` | — | write (not load-tested) | — | — | — | — | — |
| 158 | GET | `dashboard/roles/bulk-assign/<str:role_id>/` | Admin | 2 → 2 | — | 10 (paged) | 0.9 KB | — | — |
| 159 | POST | `dashboard/roles/bulk-assign/<str:role_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 160 | PUT | `dashboard/roles/bulk-assign/<str:role_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 161 | PATCH | `dashboard/roles/bulk-assign/<str:role_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 162 | POST | `dashboard/roles/bulk-assign-excel/` | — | write (not load-tested) | — | — | — | — | — |
| 163 | POST | `dashboard/roles/user-role/` | — | write (not load-tested) | — | — | — | — | — |
| 164 | DELETE | `dashboard/roles/user-role/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/dashboard/roles/dash_roles_views.py:411,423); query inside a loop (api/dashboard/roles/dash_roles_views.py:423) | L-59 |
| 165 | GET | `dashboard/roles/` | Admin | 32 → 32 | 20× `user` | 10 (paged) | 2.8 KB | per-row method fields: RoleDashboardSerializer: members | M-61 |
| 166 | POST | `dashboard/roles/` | — | write (not load-tested) | — | — | — | — | — |
| 167 | PATCH | `dashboard/roles/` | — | write (not load-tested) | — | — | — | — | — |
| 168 | DELETE | `dashboard/roles/` | — | write (not load-tested) | — | — | — | — | — |
| 169 | GET | `dashboard/roles/` | Admin | 32 → 32 | 20× `user` | 10 (paged) | 2.8 KB | per-row method fields: RoleDashboardSerializer: members | M-61 |
| 170 | POST | `dashboard/roles/` | — | write (not load-tested) | — | — | — | — | — |
| 171 | PATCH | `dashboard/roles/` | — | write (not load-tested) | — | — | — | — | — |
| 172 | DELETE | `dashboard/roles/` | — | write (not load-tested) | — | — | — | — | — |
| 173 | GET | `dashboard/roles/csv/` | Admin | 106 → 331 | 220× `user` | — | 22.5 KB | per-row method fields: RoleDashboardSerializer: members | M-62 |
| 174 | GET | `dashboard/roles/<str:roles_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: RoleDashboardSerializer: members | — |
| 175 | POST | `dashboard/roles/<str:roles_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 176 | PATCH | `dashboard/roles/<str:roles_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 177 | DELETE | `dashboard/roles/<str:roles_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 178 | GET | `dashboard/roles/<str:roles_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: RoleDashboardSerializer: members | — |
| 179 | POST | `dashboard/roles/<str:roles_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 180 | PATCH | `dashboard/roles/<str:roles_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 181 | DELETE | `dashboard/roles/<str:roles_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 182 | GET | `dashboard/ig/` | Admin | 37 → 69 | 18× `user` | 10 (paged) | 21.2 KB | — | M-60 |
| 183 | POST | `dashboard/ig/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/dashboard/ig/dash_ig_view.py:343) | L-59 |
| 184 | PUT | `dashboard/ig/` | — | write (not load-tested) | — | — | — | query inside a loop (api/dashboard/ig/dash_ig_view.py:460,460,463); insert/update inside a loop (api/dashboard/ig/dash_ig_view.py:467,471) | L-59 |
| 185 | DELETE | `dashboard/ig/` | — | write (not load-tested) | — | — | — | — | — |
| 186 | GET | `dashboard/ig/request/` | Admin | 49 → 83 | 18× `user` | 10 (paged) | 23.8 KB | — | M-60 |
| 187 | POST | `dashboard/ig/request/` | — | write (not load-tested) | — | — | — | — | — |
| 188 | PATCH | `dashboard/ig/request/` | — | write (not load-tested) | — | — | — | — | — |
| 189 | DELETE | `dashboard/ig/request/` | — | write (not load-tested) | — | — | — | — | — |
| 190 | GET | `dashboard/ig/request/<str:pk>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 191 | POST | `dashboard/ig/request/<str:pk>/` | — | write (not load-tested) | — | — | — | — | — |
| 192 | PATCH | `dashboard/ig/request/<str:pk>/` | — | write (not load-tested) | — | — | — | — | — |
| 193 | DELETE | `dashboard/ig/request/<str:pk>/` | — | write (not load-tested) | — | — | — | — | — |
| 194 | GET | `dashboard/ig/list/` | Admin | 11 → 129 | 51× `user` | 7 | 36.5 KB | response cached | M-60 |
| 195 | GET | `dashboard/ig/csv/` | Admin | 185 → 847 | 180× `user` | — | 113.2 KB | — | M-60, M-62 |
| 196 | GET | `dashboard/ig/impact-projects/public/` | Admin | 14 → 15 | 10× `interest_group` | 10 (paged) | 11.6 KB | — | — |
| 197 | GET | `dashboard/ig/<str:ig_id>/impact-projects/` | Admin | 2 → 8 | 3× `interest_group` | 3 (paged) | 2.5 KB | — | — |
| 198 | POST | `dashboard/ig/<str:ig_id>/impact-projects/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/dashboard/ig/impact_project_view.py:135) | L-59 |
| 199 | PATCH | `dashboard/ig/<str:ig_id>/impact-projects/<str:project_id>/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/dashboard/ig/impact_project_view.py:215) | L-59 |
| 200 | DELETE | `dashboard/ig/<str:ig_id>/impact-projects/<str:project_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 201 | POST | `dashboard/ig/<str:ig_id>/impact-projects/<str:project_id>/image/` | — | write (not load-tested) | — | — | — | — | — |
| 202 | POST | `dashboard/ig/<str:pk>/cover-image/` | — | write (not load-tested) | — | — | — | — | — |
| 203 | DELETE | `dashboard/ig/<str:pk>/cover-image/` | — | write (not load-tested) | — | — | — | — | — |
| 204 | POST | `dashboard/ig/<str:pk>/icon-image/` | — | write (not load-tested) | — | — | — | — | — |
| 205 | DELETE | `dashboard/ig/<str:pk>/icon-image/` | — | write (not load-tested) | — | — | — | — | — |
| 206 | GET | `dashboard/ig/<str:pk>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 207 | POST | `dashboard/ig/<str:pk>/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/dashboard/ig/dash_ig_view.py:343) | L-59 |
| 208 | PUT | `dashboard/ig/<str:pk>/` | — | write (not load-tested) | — | — | — | query inside a loop (api/dashboard/ig/dash_ig_view.py:460,460,463); insert/update inside a loop (api/dashboard/ig/dash_ig_view.py:467,471) | L-59 |
| 209 | DELETE | `dashboard/ig/<str:pk>/` | — | write (not load-tested) | — | — | — | — | — |
| 210 | POST | `dashboard/ig/<str:pk>/activate/` | — | write (not load-tested) | — | — | — | — | — |
| 211 | POST | `dashboard/ig/<str:pk>/deactivate/` | — | write (not load-tested) | — | — | — | — | — |
| 212 | GET | `dashboard/ig/get/<str:pk>/` | Admin | 13 → 25 | 9× `user` | 5 | 5.8 KB | — | M-60 |
| 213 | PATCH | `dashboard/ig/get/<str:pk>/` | — | write (not load-tested) | — | — | — | query inside a loop (api/dashboard/ig/dash_ig_view.py:718,718,729); insert/update inside a loop (api/dashboard/ig/dash_ig_view.py:722,767,779) | L-59 |
| 214 | POST | `dashboard/ig/<str:pk>/join/` | — | write (not load-tested) | — | — | — | — | — |
| 215 | DELETE | `dashboard/ig/<str:pk>/join/` | — | write (not load-tested) | — | — | — | — | — |
| 216 | POST | `dashboard/ig/<str:pk>/leave/` | — | write (not load-tested) | — | — | — | — | — |
| 217 | DELETE | `dashboard/ig/<str:pk>/leave/` | — | write (not load-tested) | — | — | — | — | — |
| 218 | GET | `dashboard/task/list-task-type/` | Admin | 2 → 2 | — | 10 (paged) | 5.0 KB | — | L-58 |
| 219 | POST | `dashboard/task/list-task-type/` | — | write (not load-tested) | — | — | — | — | — |
| 220 | PUT | `dashboard/task/list-task-type/` | — | write (not load-tested) | — | — | — | — | — |
| 221 | DELETE | `dashboard/task/list-task-type/` | — | write (not load-tested) | — | — | — | — | — |
| 222 | GET | `dashboard/task/task-type/<str:task_type_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 223 | POST | `dashboard/task/task-type/<str:task_type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 224 | PUT | `dashboard/task/task-type/<str:task_type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 225 | DELETE | `dashboard/task/task-type/<str:task_type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 226 | GET | `dashboard/task/channel/` | Admin | 1 → 1 | — | 28 | 3.7 KB | — | — |
| 227 | GET | `dashboard/task/ig/` | Admin | 1 → 1 | — | 161 | 20.2 KB | returns every row (no paging) | M-65 |
| 228 | GET | `dashboard/task/organization/` | Admin | 1 → 1 | — | 145 | 21.2 KB | returns every row (no paging) | M-65 |
| 229 | GET | `dashboard/task/level/` | Admin | 1 → 1 | — | 47 | 4.9 KB | — | — |
| 230 | GET | `dashboard/task/task-types/` | Admin | 1 → 1 | — | 79 | 10.2 KB | — | — |
| 231 | GET | `dashboard/task/` | Admin | 4 → 4 | — | 10 (paged) | 11.6 KB | — | — |
| 232 | POST | `dashboard/task/` | — | write (not load-tested) | — | — | — | — | — |
| 233 | GET | `dashboard/task/active/` | Admin | 4 → 4 | — | 10 (paged) | 9.4 KB | — | — |
| 234 | GET | `dashboard/task/inactive/` | Admin | 3 → 4 | — | 18 (paged) | 3.5 KB | — | — |
| 235 | GET | `dashboard/task/list/` | Mentor | 9 → 9 | — | 25 | 16.4 KB | no index: events(deleted_at,scope,scope_org_id,status); no index: task_list(event_id); no index: task_list(event_id,requested_by) | M-64 |
| 236 | GET | `dashboard/task/csv/` | Admin | 4 → 4 | — | — | 18.1 KB | — | — |
| 237 | POST | `dashboard/task/import/` | — | write (not load-tested) | — | — | — | — | — |
| 238 | GET | `dashboard/task/base-template/` | — | not measured (no successful response in test data; 500) | — | — | — | builds a spreadsheet/CSV in the request (api/dashboard/task/dash_task_view.py:1158) | — |
| 239 | GET | `dashboard/task/events/` | Admin | 0 → 0 | — | 2 | 0.1 KB | — | — |
| 240 | GET | `dashboard/task/pending/` | Admin | 2 → 2 | — | 1 (paged) | 0.5 KB | no index: task_list(approval_status) | M-64 |
| 241 | PATCH | `dashboard/task/pending/` | — | write (not load-tested) | — | — | — | — | — |
| 242 | GET | `dashboard/task/<str:task_id>/review/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 243 | PATCH | `dashboard/task/<str:task_id>/review/` | — | write (not load-tested) | — | — | — | — | — |
| 244 | GET | `dashboard/task/<str:task_id>/` | Admin | 1 → 1 | — | — | 0.4 KB | — | — |
| 245 | PUT | `dashboard/task/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 246 | DELETE | `dashboard/task/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 247 | GET | `dashboard/profile/` | Campus IG Lead | 4 → 4 | — | 0 | 0.6 KB | — | — |
| 248 | PATCH | `dashboard/profile/` | — | write (not load-tested) | — | — | — | — | — |
| 249 | DELETE | `dashboard/profile/` | — | write (not load-tested) | — | — | — | — | — |
| 250 | GET | `dashboard/profile/badges/<str:muid>` | Admin | 4 → 4 | 3× `karma_activity_log` | 0 | 0.1 KB | no index: task_list(hashtag); query inside a loop (api/dashboard/profile/profile_view.py:667,667) | M-64 |
| 251 | GET | `dashboard/profile/user-profile/` | Student | 18 → 18 | — | 8 | 2.5 KB | no index: wallet(karma); per-row method fields: UserProfileSerializer: percentile, rank, interest_groups | H-36, H-40, M-64 |
| 252 | GET | `dashboard/profile/ig-edit/` | Student | 1 → 1 | — | 1 | 0.1 KB | — | — |
| 253 | PATCH | `dashboard/profile/ig-edit/` | — | write (not load-tested) | — | — | — | — | — |
| 254 | GET | `dashboard/profile/user-profile/<str:muid>/` | Admin | 19 → 19 | — | 8 | 2.5 KB | no index: wallet(karma); per-row method fields: UserProfileSerializer: percentile, rank, interest_groups | M-64 |
| 255 | GET | `dashboard/profile/user-log/` | Student | 1 → 1 | — | 30 | 4.5 KB | returns every row (no paging) | M-65 |
| 256 | GET | `dashboard/profile/user-log/<str:muid>/` | Admin | 3 → 3 | — | 30 | 4.5 KB | returns every row (no paging) | M-65 |
| 257 | GET | `dashboard/profile/share-user-profile/` | — | not measured (no successful response in test data; 500) | — | — | — | outbound HTTP in the request (api/dashboard/profile/profile_view.py:437) | — |
| 258 | PUT | `dashboard/profile/share-user-profile/` | — | write (not load-tested) | — | — | — | — | — |
| 259 | GET | `dashboard/profile/share-user-profile/<str:uuid>/` | — | not measured (no successful response in test data; 400) | — | — | — | outbound HTTP in the request (api/dashboard/profile/profile_view.py:437) | — |
| 260 | PUT | `dashboard/profile/share-user-profile/<str:uuid>/` | — | write (not load-tested) | — | — | — | — | — |
| 261 | GET | `dashboard/profile/rank/<str:muid>/` | Admin | 7 → 7 | — | 1 | 0.2 KB | no index: wallet(karma); per-row method fields: UserRankSerializer: rank, interest_groups | M-64 |
| 262 | GET | `dashboard/profile/get-user-levels/` | Mentor | 41 → 95 | 47× `karma_activity_log` | 47 | 10.6 KB | per-row method fields: UserLevelSerializer: tasks | L-56 |
| 263 | GET | `dashboard/profile/get-user-levels/<str:muid>/` | Admin | 43 → 51 | 26× `task_list` | 47 | 10.6 KB | per-row method fields: UserLevelSerializer: tasks | L-56 |
| 264 | PUT | `dashboard/profile/socials/edit/` | — | write (not load-tested) | — | — | — | — | — |
| 265 | GET | `dashboard/profile/socials/` | Admin | 1 → 1 | — | — | 0.2 KB | — | — |
| 266 | GET | `dashboard/profile/socials/<str:muid>/` | Admin | 3 → 3 | — | — | 0.2 KB | — | — |
| 267 | GET | `dashboard/profile/qrcode-get/<str:uuid>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 268 | POST | `dashboard/profile/change-password/` | — | write (not load-tested) | — | — | — | — | — |
| 269 | GET | `dashboard/profile/userterm-approved/<str:muid>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 270 | POST | `dashboard/profile/userterm-approved/<str:muid>/` | — | write (not load-tested) | — | — | — | — | — |
| 271 | GET | `dashboard/profile/karma-feed/` | Admin | 2 → 2 | — | — | 0.2 KB | response cached; index unusable: karma_activity_log(django_datetime_cast_date(created_at)) | M-64 |
| 272 | GET | `dashboard/profile/user-level-feed/` | Admin | 2 → 2 | — | — | 0.2 KB | — | H-40 |
| 273 | GET | `dashboard/profile/cover-pic/` | Admin | 1 → 1 | — | — | 0.1 KB | — | — |
| 274 | POST | `dashboard/profile/cover-pic/` | — | write (not load-tested) | — | — | — | — | — |
| 275 | DELETE | `dashboard/profile/cover-pic/` | — | write (not load-tested) | — | — | — | — | — |
| 276 | GET | `dashboard/profile/user-preferences/` | Lead Enabler | 3 → 3 | — | 2 | 0.3 KB | — | — |
| 277 | PATCH | `dashboard/profile/user-preferences/` | — | write (not load-tested) | — | — | — | — | — |
| 278 | GET | `dashboard/profile/permute/<str:muid>/` | Admin | 7 → 7 | — | 2 | 0.2 KB | — | — |
| 279 | GET | `dashboard/learningcircle/create/` | Admin | 4 → 4 | — | 10 (paged) | 3.4 KB | per-row method fields: LearningCircleListMinSerializer: is_joined | — |
| 280 | POST | `dashboard/learningcircle/create/` | — | write (not load-tested) | — | — | — | — | — |
| 281 | PUT | `dashboard/learningcircle/create/` | — | write (not load-tested) | — | — | — | — | — |
| 282 | DELETE | `dashboard/learningcircle/create/` | — | write (not load-tested) | — | — | — | — | — |
| 283 | GET | `dashboard/learningcircle/list/` | Admin | 4 → 4 | — | 10 (paged) | 3.4 KB | per-row method fields: LearningCircleListMinSerializer: is_joined | — |
| 284 | POST | `dashboard/learningcircle/list/` | — | write (not load-tested) | — | — | — | — | — |
| 285 | PUT | `dashboard/learningcircle/list/` | — | write (not load-tested) | — | — | — | — | — |
| 286 | DELETE | `dashboard/learningcircle/list/` | — | write (not load-tested) | — | — | — | — | — |
| 287 | GET | `dashboard/learningcircle/info/<str:circle_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: LearningCircleListMinSerializer: is_joined | — |
| 288 | POST | `dashboard/learningcircle/info/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 289 | PUT | `dashboard/learningcircle/info/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 290 | DELETE | `dashboard/learningcircle/info/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 291 | GET | `dashboard/learningcircle/members/<str:circle_id>/` | Admin | 3 → 3 | — | 13 | 1.7 KB | — | — |
| 292 | GET | `dashboard/learningcircle/edit/<str:circle_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: LearningCircleListMinSerializer: is_joined | — |
| 293 | POST | `dashboard/learningcircle/edit/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 294 | PUT | `dashboard/learningcircle/edit/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 295 | DELETE | `dashboard/learningcircle/edit/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 296 | GET | `dashboard/learningcircle/delete/<str:circle_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: LearningCircleListMinSerializer: is_joined | — |
| 297 | POST | `dashboard/learningcircle/delete/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 298 | PUT | `dashboard/learningcircle/delete/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 299 | DELETE | `dashboard/learningcircle/delete/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 300 | POST | `dashboard/learningcircle/meeting/create/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 301 | PUT | `dashboard/learningcircle/meeting/create/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 302 | DELETE | `dashboard/learningcircle/meeting/create/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 303 | GET | `dashboard/learningcircle/meeting/list-public/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 304 | GET | `dashboard/learningcircle/meeting/list/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 305 | GET | `dashboard/learningcircle/meeting/list/<str:circle_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 306 | POST | `dashboard/learningcircle/meeting/edit/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 307 | PUT | `dashboard/learningcircle/meeting/edit/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 308 | DELETE | `dashboard/learningcircle/meeting/edit/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 309 | GET | `dashboard/learningcircle/meeting/info/<str:meet_id>/` | Admin | 4 → 4 | — | 0 | 0.5 KB | per-row method fields: CircleMeetupInfoSerializer: is_member, attendees | — |
| 310 | POST | `dashboard/learningcircle/meeting/delete/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 311 | PUT | `dashboard/learningcircle/meeting/delete/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 312 | DELETE | `dashboard/learningcircle/meeting/delete/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 313 | POST | `dashboard/learningcircle/meeting/join/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 314 | DELETE | `dashboard/learningcircle/meeting/join/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 315 | POST | `dashboard/learningcircle/meeting/rsvp/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 316 | DELETE | `dashboard/learningcircle/meeting/rsvp/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 317 | POST | `dashboard/learningcircle/meeting/leave/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 318 | DELETE | `dashboard/learningcircle/meeting/leave/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 319 | GET | `dashboard/learningcircle/meeting/attendee-report/<str:meet_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 320 | POST | `dashboard/learningcircle/meeting/attendee-report/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 321 | DELETE | `dashboard/learningcircle/meeting/attendee-report/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 322 | GET | `dashboard/learningcircle/meeting/report/<str:meet_id>/` | Student | 3 → 3 | — | 0 | 0.2 KB | — | — |
| 323 | POST | `dashboard/learningcircle/meeting/report/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 324 | DELETE | `dashboard/learningcircle/meeting/report/<str:meet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 325 | GET | `dashboard/learningcircle/meeting/report/export/<str:meet_id>/` | Student | 4 → 4 | — | — | 0.2 KB | builds a spreadsheet/CSV in the request (api/dashboard/learningcircle/learningcircle_views.py:889) | — |
| 326 | GET | `dashboard/learningcircle/user-circles/` | Student | 3 → 3 | — | 1 (paged) | 0.3 KB | per-row method fields: UserCircleListSerializer: total_members | — |
| 327 | GET | `dashboard/learningcircle/join/<str:circle_id>/` | Student | 2 → 2 | — | 25 | 4.5 KB | — | — |
| 328 | POST | `dashboard/learningcircle/join/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 329 | PATCH | `dashboard/learningcircle/join/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 330 | POST | `dashboard/learningcircle/members/add/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 331 | DELETE | `dashboard/learningcircle/members/remove/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 332 | DELETE | `dashboard/learningcircle/leave/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 333 | GET | `dashboard/learningcircle/invite/status/` | Fellow | 1 → 1 | — | 1 | 0.4 KB | — | — |
| 334 | POST | `dashboard/learningcircle/invite/status/` | — | write (not load-tested) | — | — | — | — | — |
| 335 | GET | `dashboard/learningcircle/invite/status/<str:link_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 336 | POST | `dashboard/learningcircle/invite/status/<str:link_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 337 | GET | `dashboard/learningcircle/invite/sent/<str:circle_id>/` | Student | 2 → 2 | — | 1 | 0.3 KB | — | — |
| 338 | POST | `dashboard/learningcircle/invite/<str:circle_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 339 | POST | `dashboard/learningcircle/transfer-lead/<str:circle_id>/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/dashboard/learningcircle/learningcircle_views.py:1722) | L-59 |
| 340 | GET | `dashboard/referral/` | Student | 1 → 13 | 3× `user` | 3 | 0.4 KB | per-row method fields: ReferralListSerializer: karma, level | M-61 |
| 341 | POST | `dashboard/referral/send-referral/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/dashboard/referral/referral_view.py:40,56) | M-70 |
| 342 | GET | `dashboard/college/` | Admin | 23 → 72 | 10× `user_organization_link` | 10 (paged) | 4.0 KB | per-row method fields: CollegeListSerializer: no_of_lc, total_karma | M-61, M-66 |
| 343 | PATCH | `dashboard/college/change-college/` | — | write (not load-tested) | — | — | — | — | — |
| 344 | GET | `dashboard/college/<str:college_code>/` | Admin | 1 → 1 | — | 0 (paged) | 0.2 KB | per-row method fields: CollegeListSerializer: no_of_lc, total_karma | — |
| 345 | GET | `dashboard/karma-voucher/` | Admin | 2 → 2 | — | 10 (paged) | 6.4 KB | — | — |
| 346 | POST | `dashboard/karma-voucher/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/dashboard/karma_voucher/karma_voucher_view.py:325,340) | H-38, M-70 |
| 347 | PATCH | `dashboard/karma-voucher/` | — | write (not load-tested) | — | — | — | — | — |
| 348 | DELETE | `dashboard/karma-voucher/` | — | write (not load-tested) | — | — | — | — | — |
| 349 | POST | `dashboard/karma-voucher/import/` | — | write (not load-tested) | — | — | — | query inside a loop (api/dashboard/karma_voucher/karma_voucher_view.py:114); sends e-mail in the request (api/dashboard/karma_voucher/karma_voucher_view.py:214,229) | H-38, L-59, M-70 |
| 350 | GET | `dashboard/karma-voucher/export/` | Admin | 13 → 113 | 84× `user` | — | 8.9 KB | — | M-62 |
| 351 | GET | `dashboard/karma-voucher/create/` | Admin | 2 → 2 | — | 10 (paged) | 6.4 KB | — | — |
| 352 | POST | `dashboard/karma-voucher/create/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/dashboard/karma_voucher/karma_voucher_view.py:325,340) | H-38, M-70 |
| 353 | PATCH | `dashboard/karma-voucher/create/` | — | write (not load-tested) | — | — | — | — | — |
| 354 | DELETE | `dashboard/karma-voucher/create/` | — | write (not load-tested) | — | — | — | — | — |
| 355 | GET | `dashboard/karma-voucher/update/<str:voucher_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 356 | POST | `dashboard/karma-voucher/update/<str:voucher_id>/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/dashboard/karma_voucher/karma_voucher_view.py:325,340) | M-70 |
| 357 | PATCH | `dashboard/karma-voucher/update/<str:voucher_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 358 | DELETE | `dashboard/karma-voucher/update/<str:voucher_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 359 | GET | `dashboard/karma-voucher/delete/<str:voucher_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 360 | POST | `dashboard/karma-voucher/delete/<str:voucher_id>/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/dashboard/karma_voucher/karma_voucher_view.py:325,340) | M-70 |
| 361 | PATCH | `dashboard/karma-voucher/delete/<str:voucher_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 362 | DELETE | `dashboard/karma-voucher/delete/<str:voucher_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 363 | GET | `dashboard/karma-voucher/base-template/` | — | not measured (no successful response in test data; 500) | — | — | — | builds a spreadsheet/CSV in the request (api/dashboard/karma_voucher/karma_voucher_view.py:416) | — |
| 364 | GET | `dashboard/location/countries/` | Admin | 2 → 2 | — | 10 (paged) | 5.3 KB | — | — |
| 365 | POST | `dashboard/location/countries/` | — | write (not load-tested) | — | — | — | — | — |
| 366 | PATCH | `dashboard/location/countries/` | — | write (not load-tested) | — | — | — | — | — |
| 367 | DELETE | `dashboard/location/countries/` | — | write (not load-tested) | — | — | — | — | — |
| 368 | GET | `dashboard/location/countries/list/` | Admin | 1 → 1 | — | 245 | 31.4 KB | response cached | — |
| 369 | GET | `dashboard/location/countries/<str:country_id>/` | Admin | 1 → 1 | — | 1 (paged) | 0.7 KB | — | — |
| 370 | POST | `dashboard/location/countries/<str:country_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 371 | PATCH | `dashboard/location/countries/<str:country_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 372 | DELETE | `dashboard/location/countries/<str:country_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 373 | GET | `dashboard/location/states/` | Admin | 2 → 2 | — | 10 (paged) | 6.2 KB | — | — |
| 374 | POST | `dashboard/location/states/` | — | write (not load-tested) | — | — | — | — | — |
| 375 | PATCH | `dashboard/location/states/` | — | write (not load-tested) | — | — | — | — | — |
| 376 | DELETE | `dashboard/location/states/` | — | write (not load-tested) | — | — | — | — | — |
| 377 | GET | `dashboard/location/states/list/` | Admin | 1 → 1 | — | 217 | 27.8 KB | response cached | — |
| 378 | GET | `dashboard/location/states/<str:state_id>/` | Admin | 1 → 1 | — | 1 (paged) | 0.8 KB | — | — |
| 379 | POST | `dashboard/location/states/<str:state_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 380 | PATCH | `dashboard/location/states/<str:state_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 381 | DELETE | `dashboard/location/states/<str:state_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 382 | GET | `dashboard/location/zones/` | Admin | 2 → 2 | — | 10 (paged) | 6.4 KB | — | — |
| 383 | POST | `dashboard/location/zones/` | — | write (not load-tested) | — | — | — | — | — |
| 384 | PATCH | `dashboard/location/zones/` | — | write (not load-tested) | — | — | — | — | — |
| 385 | DELETE | `dashboard/location/zones/` | — | write (not load-tested) | — | — | — | — | — |
| 386 | GET | `dashboard/location/zones/list/` | Admin | 1 → 1 | — | 189 | 24.2 KB | response cached | — |
| 387 | GET | `dashboard/location/zones/<str:zone_id>/` | Admin | 1 → 1 | — | 1 (paged) | 0.6 KB | — | — |
| 388 | POST | `dashboard/location/zones/<str:zone_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 389 | PATCH | `dashboard/location/zones/<str:zone_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 390 | DELETE | `dashboard/location/zones/<str:zone_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 391 | GET | `dashboard/location/districts/` | Admin | 2 → 2 | — | 10 (paged) | 6.7 KB | — | — |
| 392 | POST | `dashboard/location/districts/` | — | write (not load-tested) | — | — | — | — | — |
| 393 | PATCH | `dashboard/location/districts/` | — | write (not load-tested) | — | — | — | — | — |
| 394 | DELETE | `dashboard/location/districts/` | — | write (not load-tested) | — | — | — | — | — |
| 395 | GET | `dashboard/location/districts/<str:district_id>/` | Admin | 1 → 1 | — | 1 (paged) | 0.7 KB | — | — |
| 396 | POST | `dashboard/location/districts/<str:district_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 397 | PATCH | `dashboard/location/districts/<str:district_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 398 | DELETE | `dashboard/location/districts/<str:district_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 399 | POST | `dashboard/organisation/institutes/create/` | — | write (not load-tested) | — | — | — | — | — |
| 400 | PUT | `dashboard/organisation/institutes/create/` | — | write (not load-tested) | — | — | — | — | — |
| 401 | DELETE | `dashboard/organisation/institutes/create/` | — | write (not load-tested) | — | — | — | — | — |
| 402 | POST | `dashboard/organisation/institutes/edit/<str:org_code>/` | — | write (not load-tested) | — | — | — | — | — |
| 403 | PUT | `dashboard/organisation/institutes/edit/<str:org_code>/` | — | write (not load-tested) | — | — | — | — | — |
| 404 | DELETE | `dashboard/organisation/institutes/edit/<str:org_code>/` | — | write (not load-tested) | — | — | — | — | — |
| 405 | POST | `dashboard/organisation/institutes/delete/<str:org_code>/` | — | write (not load-tested) | — | — | — | — | — |
| 406 | PUT | `dashboard/organisation/institutes/delete/<str:org_code>/` | — | write (not load-tested) | — | — | — | — | — |
| 407 | DELETE | `dashboard/organisation/institutes/delete/<str:org_code>/` | — | write (not load-tested) | — | — | — | — | — |
| 408 | GET | `dashboard/organisation/institutes/<str:org_type>/csv/` | Admin | 1 → 1 | — | — | 0.7 KB | — | — |
| 409 | GET | `dashboard/organisation/institutes/info/<str:org_code>/` | Admin | 1 → 1 | — | 1 | 0.8 KB | — | — |
| 410 | GET | `dashboard/organisation/institutes/prefill/<str:org_code>/` | Admin | 1 → 1 | — | — | 0.8 KB | — | — |
| 411 | GET | `dashboard/organisation/institutes/<str:org_type>/` | Admin | 2 → 2 | — | 10 (paged) | 4.7 KB | — | L-58 |
| 412 | GET | `dashboard/organisation/institutes/<str:org_type>/<str:district_id>/` | Admin | 2 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 413 | GET | `dashboard/organisation/institutes/org/affiliation/show/` | Admin | 2 → 2 | — | 10 (paged) | 1.5 KB | — | — |
| 414 | POST | `dashboard/organisation/institutes/org/affiliation/show/` | — | write (not load-tested) | — | — | — | — | — |
| 415 | PUT | `dashboard/organisation/institutes/org/affiliation/show/` | — | write (not load-tested) | — | — | — | — | — |
| 416 | DELETE | `dashboard/organisation/institutes/org/affiliation/show/` | — | write (not load-tested) | — | — | — | — | — |
| 417 | GET | `dashboard/organisation/institutes/org/affiliation/create/` | Admin | 2 → 2 | — | 10 (paged) | 1.5 KB | — | — |
| 418 | POST | `dashboard/organisation/institutes/org/affiliation/create/` | — | write (not load-tested) | — | — | — | — | — |
| 419 | PUT | `dashboard/organisation/institutes/org/affiliation/create/` | — | write (not load-tested) | — | — | — | — | — |
| 420 | DELETE | `dashboard/organisation/institutes/org/affiliation/create/` | — | write (not load-tested) | — | — | — | — | — |
| 421 | GET | `dashboard/organisation/institutes/org/affiliation/edit/<str:affiliation_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 422 | POST | `dashboard/organisation/institutes/org/affiliation/edit/<str:affiliation_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 423 | PUT | `dashboard/organisation/institutes/org/affiliation/edit/<str:affiliation_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 424 | DELETE | `dashboard/organisation/institutes/org/affiliation/edit/<str:affiliation_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 425 | GET | `dashboard/organisation/institutes/org/affiliation/delete/<str:affiliation_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 426 | POST | `dashboard/organisation/institutes/org/affiliation/delete/<str:affiliation_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 427 | PUT | `dashboard/organisation/institutes/org/affiliation/delete/<str:affiliation_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 428 | DELETE | `dashboard/organisation/institutes/org/affiliation/delete/<str:affiliation_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 429 | GET | `dashboard/organisation/departments/` | Admin | 2 → 2 | — | 10 (paged) | 1.7 KB | — | L-58 |
| 430 | POST | `dashboard/organisation/departments/` | — | write (not load-tested) | — | — | — | — | — |
| 431 | PUT | `dashboard/organisation/departments/` | — | write (not load-tested) | — | — | — | — | — |
| 432 | DELETE | `dashboard/organisation/departments/` | — | write (not load-tested) | — | — | — | — | — |
| 433 | GET | `dashboard/organisation/departments/create/` | Admin | 2 → 2 | — | 10 (paged) | 1.7 KB | — | — |
| 434 | POST | `dashboard/organisation/departments/create/` | — | write (not load-tested) | — | — | — | — | — |
| 435 | PUT | `dashboard/organisation/departments/create/` | — | write (not load-tested) | — | — | — | — | — |
| 436 | DELETE | `dashboard/organisation/departments/create/` | — | write (not load-tested) | — | — | — | — | — |
| 437 | GET | `dashboard/organisation/departments/edit/<str:department_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 438 | POST | `dashboard/organisation/departments/edit/<str:department_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 439 | PUT | `dashboard/organisation/departments/edit/<str:department_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 440 | DELETE | `dashboard/organisation/departments/edit/<str:department_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 441 | GET | `dashboard/organisation/departments/delete/<str:department_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 442 | POST | `dashboard/organisation/departments/delete/<str:department_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 443 | PUT | `dashboard/organisation/departments/delete/<str:department_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 444 | DELETE | `dashboard/organisation/departments/delete/<str:department_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 445 | GET | `dashboard/organisation/affiliation/list/` | Admin | 1 → 1 | — | 28 | 3.7 KB | — | — |
| 446 | GET | `dashboard/organisation/merge_organizations/<str:organisation_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: OrganizationMergerSerializer: update_summary | — |
| 447 | PATCH | `dashboard/organisation/merge_organizations/<str:organisation_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 448 | POST | `dashboard/organisation/karma-type/create/` | — | write (not load-tested) | — | — | — | — | — |
| 449 | POST | `dashboard/organisation/karma-log/create/` | — | write (not load-tested) | — | — | — | — | — |
| 450 | GET | `dashboard/organisation/base-template/` | — | not measured (no successful response in test data; 500) | — | — | — | builds a spreadsheet/CSV in the request (api/dashboard/organisation/organisation_views.py:650) | — |
| 451 | POST | `dashboard/organisation/import/` | — | write (not load-tested) | — | — | — | — | — |
| 452 | POST | `dashboard/organisation/transfer/` | — | write (not load-tested) | — | — | — | — | — |
| 453 | GET | `dashboard/organisation/verify/list/` | Admin | 2 → 2 | — | 10 (paged) | 3.0 KB | — | — |
| 454 | POST | `dashboard/organisation/verify/<str:uorg_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 455 | GET | `dashboard/dynamic-management/dynamic-role/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: DynamicRoleListSerializer: roles | — |
| 456 | POST | `dashboard/dynamic-management/dynamic-role/` | — | write (not load-tested) | — | — | — | — | — |
| 457 | PATCH | `dashboard/dynamic-management/dynamic-role/` | — | write (not load-tested) | — | — | — | — | — |
| 458 | DELETE | `dashboard/dynamic-management/dynamic-role/` | — | write (not load-tested) | — | — | — | — | — |
| 459 | GET | `dashboard/dynamic-management/dynamic-role/create/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: DynamicRoleListSerializer: roles | — |
| 460 | POST | `dashboard/dynamic-management/dynamic-role/create/` | — | write (not load-tested) | — | — | — | — | — |
| 461 | PATCH | `dashboard/dynamic-management/dynamic-role/create/` | — | write (not load-tested) | — | — | — | — | — |
| 462 | DELETE | `dashboard/dynamic-management/dynamic-role/create/` | — | write (not load-tested) | — | — | — | — | — |
| 463 | GET | `dashboard/dynamic-management/dynamic-role/delete/<str:type_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: DynamicRoleListSerializer: roles | — |
| 464 | POST | `dashboard/dynamic-management/dynamic-role/delete/<str:type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 465 | PATCH | `dashboard/dynamic-management/dynamic-role/delete/<str:type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 466 | DELETE | `dashboard/dynamic-management/dynamic-role/delete/<str:type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 467 | GET | `dashboard/dynamic-management/dynamic-role/update/<str:type_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: DynamicRoleListSerializer: roles | — |
| 468 | POST | `dashboard/dynamic-management/dynamic-role/update/<str:type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 469 | PATCH | `dashboard/dynamic-management/dynamic-role/update/<str:type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 470 | DELETE | `dashboard/dynamic-management/dynamic-role/update/<str:type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 471 | GET | `dashboard/dynamic-management/dynamic-user/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: DynamicUserListSerializer: users | — |
| 472 | POST | `dashboard/dynamic-management/dynamic-user/` | — | write (not load-tested) | — | — | — | — | — |
| 473 | PATCH | `dashboard/dynamic-management/dynamic-user/` | — | write (not load-tested) | — | — | — | — | — |
| 474 | DELETE | `dashboard/dynamic-management/dynamic-user/` | — | write (not load-tested) | — | — | — | — | — |
| 475 | GET | `dashboard/dynamic-management/dynamic-user/create/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: DynamicUserListSerializer: users | — |
| 476 | POST | `dashboard/dynamic-management/dynamic-user/create/` | — | write (not load-tested) | — | — | — | — | — |
| 477 | PATCH | `dashboard/dynamic-management/dynamic-user/create/` | — | write (not load-tested) | — | — | — | — | — |
| 478 | DELETE | `dashboard/dynamic-management/dynamic-user/create/` | — | write (not load-tested) | — | — | — | — | — |
| 479 | GET | `dashboard/dynamic-management/dynamic-user/delete/<str:type_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: DynamicUserListSerializer: users | — |
| 480 | POST | `dashboard/dynamic-management/dynamic-user/delete/<str:type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 481 | PATCH | `dashboard/dynamic-management/dynamic-user/delete/<str:type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 482 | DELETE | `dashboard/dynamic-management/dynamic-user/delete/<str:type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 483 | GET | `dashboard/dynamic-management/dynamic-user/update/<str:type_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: DynamicUserListSerializer: users | — |
| 484 | POST | `dashboard/dynamic-management/dynamic-user/update/<str:type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 485 | PATCH | `dashboard/dynamic-management/dynamic-user/update/<str:type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 486 | DELETE | `dashboard/dynamic-management/dynamic-user/update/<str:type_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 487 | GET | `dashboard/dynamic-management/types/` | Admin | 0 → 0 | — | 15 | 0.3 KB | — | — |
| 488 | GET | `dashboard/dynamic-management/roles/` | Admin | 1 → 1 | — | 110 | 12.6 KB | returns every row (no paging) | M-65 |
| 489 | GET | `dashboard/error-log/` | Admin | 0 → 0 | — | 0 | 0.1 KB | — | — |
| 490 | PATCH | `dashboard/error-log/` | — | write (not load-tested) | — | — | — | — | — |
| 491 | GET | `dashboard/error-log/graph/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 492 | GET | `dashboard/error-log/tab/` | Admin | 0 → 0 | — | 0 | 0.1 KB | — | — |
| 493 | GET | `dashboard/error-log/patch/<str:error_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 494 | PATCH | `dashboard/error-log/patch/<str:error_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 495 | GET | `dashboard/error-log/<str:log_name>/` | Admin | 0 → 0 | — | — | 0.0 KB | — | — |
| 496 | GET | `dashboard/error-log/view/<str:log_name>/` | Admin | 0 → 0 | — | — | 0.1 KB | — | — |
| 497 | POST | `dashboard/error-log/clear/<str:log_name>/` | — | write (not load-tested) | — | — | — | — | — |
| 498 | GET | `dashboard/affiliation/` | Admin | 11 → 32 | 20× `user` | 10 (paged) | 3.6 KB | — | M-61 |
| 499 | POST | `dashboard/affiliation/` | — | write (not load-tested) | — | — | — | — | — |
| 500 | PUT | `dashboard/affiliation/` | — | write (not load-tested) | — | — | — | — | — |
| 501 | DELETE | `dashboard/affiliation/` | — | write (not load-tested) | — | — | — | — | — |
| 502 | GET | `dashboard/affiliation/<str:affiliation_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 503 | POST | `dashboard/affiliation/<str:affiliation_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 504 | PUT | `dashboard/affiliation/<str:affiliation_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 505 | DELETE | `dashboard/affiliation/<str:affiliation_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 506 | GET | `dashboard/channels/` | Admin | 8 → 22 | 20× `user` | 10 (paged) | 3.3 KB | — | M-61 |
| 507 | POST | `dashboard/channels/` | — | write (not load-tested) | — | — | — | — | — |
| 508 | PUT | `dashboard/channels/` | — | write (not load-tested) | — | — | — | — | — |
| 509 | DELETE | `dashboard/channels/` | — | write (not load-tested) | — | — | — | — | — |
| 510 | GET | `dashboard/channels/<str:channel_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 511 | POST | `dashboard/channels/<str:channel_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 512 | PUT | `dashboard/channels/<str:channel_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 513 | DELETE | `dashboard/channels/<str:channel_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 514 | GET | `dashboard/discord-moderator/tasklist/` | Admin | ? → 22 | 10× `user` | 10 (paged) | 1.6 KB | — | M-61 |
| 515 | GET | `dashboard/discord-moderator/pendingcounts/` | Admin | 2 → 2 | — | — | 0.1 KB | — | — |
| 516 | GET | `dashboard/discord-moderator/leaderboard/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 517 | GET | `dashboard/events/meta/categories/` | Admin | 1 → 1 | — | 28 | 9.1 KB | — | — |
| 518 | GET | `dashboard/events/meta/organizer-options/` | Mentor | 10 → 10 | 4× `mentor_scope_grant` | 1 | 0.6 KB | — | — |
| 519 | GET | `dashboard/events/meta/collaboration-targets/` | Admin | 4 → 4 | — | 20 | 7.5 KB | — | — |
| 520 | GET | `dashboard/events/meta/event-type-scope/` | Admin | 0 → 0 | — | 16 | 0.9 KB | — | — |
| 521 | GET | `dashboard/events/meta/linkable-events/` | Admin | 3 → 3 | — | 1 | 0.2 KB | no index: events(deleted_at,end_datetime,scope,scope_org_id,status) | M-64 |
| 522 | GET | `dashboard/events/ig/cluster/<str:cluster>/` | Admin | 2 → 2 | — | 0 (paged) | 0.2 KB | no index: events(deleted_at,end_datetime,organiser_ig_id,status); per-row method fields: EventListItemSerializer: viewer_interest_status | M-64 |
| 523 | GET | `dashboard/events/ig/<str:ig_id>/` | Admin | 2 → 2 | — | 0 (paged) | 0.2 KB | no index: events(deleted_at,end_datetime,organiser_ig_id,scope_ig_id,status); per-row method fields: EventListItemSerializer: viewer_interest_status | M-64 |
| 524 | GET | `dashboard/events/campus/<str:campus_id>/` | Admin | 2 → 2 | — | 0 (paged) | 0.2 KB | no index: events(deleted_at,end_datetime,organiser_org_id,scope_org_id,status); per-row method fields: EventListItemSerializer: viewer_interest_status | M-64 |
| 525 | GET | `dashboard/events/campus-ig/<str:campus_ig_id>/` | Admin | 1 → 1 | — | 0 (paged) | 0.2 KB | no index: events(deleted_at,end_datetime,organiser_ci_id,status); per-row method fields: EventListItemSerializer: viewer_interest_status | M-64 |
| 526 | GET | `dashboard/events/company/<str:company_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: EventListItemSerializer: viewer_interest_status | — |
| 527 | GET | `dashboard/events/admin/` | Admin | 12 → 12 | 10× `events_interest` | 10 (paged) | 11.2 KB | per-row method fields: EventListItemSerializer: viewer_interest_status | M-61 |
| 528 | POST | `dashboard/events/admin/<str:event_id>/approve/` | — | write (not load-tested) | — | — | — | — | — |
| 529 | POST | `dashboard/events/admin/<str:event_id>/reject/` | — | write (not load-tested) | — | — | — | — | — |
| 530 | PATCH | `dashboard/events/admin/<str:event_id>/feature/` | — | write (not load-tested) | — | — | — | — | — |
| 531 | POST | `dashboard/events/mentor/<str:event_id>/approve/` | — | write (not load-tested) | — | — | — | — | — |
| 532 | POST | `dashboard/events/mentor/<str:event_id>/reject/` | — | write (not load-tested) | — | — | — | — | — |
| 533 | POST | `dashboard/events/campus/<str:event_id>/approve/` | — | write (not load-tested) | — | — | — | — | — |
| 534 | POST | `dashboard/events/campus/<str:event_id>/reject/` | — | write (not load-tested) | — | — | — | — | — |
| 535 | POST | `dashboard/events/company/<str:event_id>/approve/` | — | write (not load-tested) | — | — | — | — | — |
| 536 | POST | `dashboard/events/company/<str:event_id>/reject/` | — | write (not load-tested) | — | — | — | — | — |
| 537 | GET | `dashboard/events/manage/` | Mentor | 4 → 6 | — | 1 (paged) | 1.3 KB | per-row method fields: EventListItemSerializer: viewer_interest_status | — |
| 538 | POST | `dashboard/events/manage/` | — | write (not load-tested) | — | — | — | — | — |
| 539 | POST | `dashboard/events/manage/<str:event_id>/publish/` | — | write (not load-tested) | — | — | — | — | — |
| 540 | GET | `dashboard/events/manage/<str:event_id>/co-owners/` | Admin | 2 → 3 | — | 1 | 0.3 KB | per-row method fields: EventCoOwnerSerializer: user | — |
| 541 | POST | `dashboard/events/manage/<str:event_id>/co-owners/` | — | write (not load-tested) | — | — | — | — | — |
| 542 | DELETE | `dashboard/events/manage/<str:event_id>/co-owners/<str:co_owner_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 543 | GET | `dashboard/events/manage/<str:event_id>/collaborators/` | Admin | 2 → 2 | — | 3 | 1.1 KB | per-row method fields: EventCollaboratorSerializer: entity_detail | — |
| 544 | POST | `dashboard/events/manage/<str:event_id>/collaborators/` | — | write (not load-tested) | — | — | — | — | — |
| 545 | POST | `dashboard/events/manage/<str:event_id>/collaborators/<str:collaborator_id>/accept/` | — | write (not load-tested) | — | — | — | — | — |
| 546 | POST | `dashboard/events/manage/<str:event_id>/collaborators/<str:collaborator_id>/reject/` | — | write (not load-tested) | — | — | — | — | — |
| 547 | DELETE | `dashboard/events/manage/<str:event_id>/collaborators/<str:collaborator_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 548 | GET | `dashboard/events/manage/<str:event_id>/tasks/meta/` | Admin | 6 → 6 | — | 161 | 58.9 KB | returns every row (no paging) | M-65 |
| 549 | GET | `dashboard/events/manage/<str:event_id>/tasks/<str:task_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 550 | PATCH | `dashboard/events/manage/<str:event_id>/tasks/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 551 | DELETE | `dashboard/events/manage/<str:event_id>/tasks/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 552 | GET | `dashboard/events/manage/<str:event_id>/tasks/` | Admin | 2 → 3 | — | 6 (paged) | 5.6 KB | no index: task_list(event_id) | M-64 |
| 553 | POST | `dashboard/events/manage/<str:event_id>/tasks/` | — | write (not load-tested) | — | — | — | — | — |
| 554 | GET | `dashboard/events/manage/<str:event_id>/analytics/` | Admin | 11 → 14 | — | 6 | 2.2 KB | no index: task_list(approval_status,event_id); no index: task_list(event_id) | M-64 |
| 555 | GET | `dashboard/events/manage/<str:event_id>/` | Admin | 11 → 28 | 12× `user` | 10 | 7.8 KB | no index: task_list(event_id); per-row method fields: EventDetailSerializer: collaborators, co_owners, linked_tasks, viewer_interest_status | M-61, M-64 |
| 556 | PUT | `dashboard/events/manage/<str:event_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 557 | PATCH | `dashboard/events/manage/<str:event_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 558 | DELETE | `dashboard/events/manage/<str:event_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 559 | GET | `dashboard/events/my-invites/` | Campus IG Lead | 2 → 2 | — | 0 | 0.1 KB | — | — |
| 560 | GET | `dashboard/events/calendar/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 561 | GET | `dashboard/events/featured/` | Admin | 3 → 3 | — | 0 (paged) | 0.2 KB | no index: events(deleted_at,end_datetime,scope,scope_org_id,status); per-row method fields: EventListItemSerializer: viewer_interest_status | M-64 |
| 562 | GET | `dashboard/events/is-featured/` | Admin | 3 → 3 | — | 0 (paged) | 0.2 KB | no index: events(deleted_at,end_datetime,scope,scope_org_id,status); per-row method fields: EventListItemSerializer: viewer_interest_status | M-64 |
| 563 | GET | `dashboard/events/tasks/` | Admin | 3 → 20 | 8× `user` | 8 (paged) | 4.4 KB | no index: events(deleted_at,end_datetime,scope,scope_org_id,status); no index: task_list(event_id) | M-61, M-64 |
| 564 | POST | `dashboard/events/<str:event_id>/interest/` | — | write (not load-tested) | — | — | — | — | — |
| 565 | DELETE | `dashboard/events/<str:event_id>/interest/` | — | write (not load-tested) | — | — | — | — | — |
| 566 | GET | `dashboard/events/<str:event_id>/` | Admin | 10 → 17 | 6× `interest_group` | 6 | 4.3 KB | no index: task_list(event_id); per-row method fields: EventDetailSerializer: collaborators, co_owners, linked_tasks, viewer_interest_status | M-61, M-64 |
| 567 | GET | `dashboard/events/` | Admin | 4 → 4 | — | 1 (paged) | 0.9 KB | no index: events(deleted_at,end_datetime,scope,scope_org_id,status); per-row method fields: EventListItemSerializer: viewer_interest_status | M-64 |
| 568 | POST | `dashboard/coupon/verify-coupon/` | — | write (not load-tested) | — | — | — | — | — |
| 569 | GET | `dashboard/projects/` | Admin | 15 → 8 | — | 10 (paged) | 8.7 KB | — | — |
| 570 | POST | `dashboard/projects/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/dashboard/projects/projects_view.py:224) | L-59 |
| 571 | GET | `dashboard/projects/<uuid:pk>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 572 | PUT | `dashboard/projects/<uuid:pk>/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/dashboard/projects/projects_view.py:69) | L-59 |
| 573 | DELETE | `dashboard/projects/<uuid:pk>/` | — | write (not load-tested) | — | — | — | — | — |
| 574 | PATCH | `dashboard/projects/<uuid:pk>/status/` | — | write (not load-tested) | — | — | — | — | — |
| 575 | GET | `dashboard/projects/<uuid:project_id>/members/` | Admin | 1 → 1 | — | 0 | 0.1 KB | — | — |
| 576 | POST | `dashboard/projects/<uuid:project_id>/members/` | — | write (not load-tested) | — | — | — | — | — |
| 577 | DELETE | `dashboard/projects/<uuid:project_id>/members/` | — | write (not load-tested) | — | — | — | — | — |
| 578 | GET | `dashboard/projects/<uuid:project_id>/members/<uuid:pk>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 579 | POST | `dashboard/projects/<uuid:project_id>/members/<uuid:pk>/` | — | write (not load-tested) | — | — | — | — | — |
| 580 | DELETE | `dashboard/projects/<uuid:project_id>/members/<uuid:pk>/` | — | write (not load-tested) | — | — | — | — | — |
| 581 | POST | `dashboard/projects/vote/` | — | write (not load-tested) | — | — | — | — | — |
| 582 | DELETE | `dashboard/projects/vote/` | — | write (not load-tested) | — | — | — | — | — |
| 583 | POST | `dashboard/projects/vote/<uuid:pk>/` | — | write (not load-tested) | — | — | — | — | — |
| 584 | DELETE | `dashboard/projects/vote/<uuid:pk>/` | — | write (not load-tested) | — | — | — | — | — |
| 585 | POST | `dashboard/projects/comment/` | — | write (not load-tested) | — | — | — | — | — |
| 586 | PUT | `dashboard/projects/comment/` | — | write (not load-tested) | — | — | — | — | — |
| 587 | DELETE | `dashboard/projects/comment/` | — | write (not load-tested) | — | — | — | — | — |
| 588 | POST | `dashboard/projects/comment/<uuid:pk>/` | — | write (not load-tested) | — | — | — | — | — |
| 589 | PUT | `dashboard/projects/comment/<uuid:pk>/` | — | write (not load-tested) | — | — | — | — | — |
| 590 | DELETE | `dashboard/projects/comment/<uuid:pk>/` | — | write (not load-tested) | — | — | — | — | — |
| 591 | GET | `dashboard/achievement/list/` | Admin | 2 → 2 | — | 140 | 107.6 KB | returns every row (no paging) | M-65 |
| 592 | GET | `dashboard/achievement/eligible/` | Student | 5 → 14 | 7× `karma_activity_log` | 28 | 7.7 KB | no index: task_list(event); returns every row (no paging) | M-65, M-64 |
| 593 | POST | `dashboard/achievement/claim/<str:achievement_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 594 | GET | `dashboard/achievement/list/user/<str:muid>/` | Admin | 2 → 2 | — | 0 | 0.1 KB | — | — |
| 595 | GET | `dashboard/achievement/progress/` | Campus IG Lead | 5 → 14 | 7× `karma_activity_log` | 29 | 8.3 KB | no index: task_list(event); returns every row (no paging) | M-65, M-64 |
| 596 | POST | `dashboard/achievement/create/` | — | write (not load-tested) | — | — | — | — | — |
| 597 | PUT | `dashboard/achievement/update/<str:achievement_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 598 | DELETE | `dashboard/achievement/delete/<str:achievement_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 599 | GET | `dashboard/achievement/rules/` | Admin | 1 → 1 | — | 28 | 8.7 KB | returns every row (no paging) | M-65 |
| 600 | POST | `dashboard/achievement/rules/create/` | — | write (not load-tested) | — | — | — | — | — |
| 601 | GET | `dashboard/achievement/rules/<str:rule_id>/` | Admin | 1 → 1 | — | — | 0.4 KB | — | — |
| 602 | PATCH | `dashboard/achievement/rules/<str:rule_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 603 | POST | `dashboard/achievement/rules/<str:rule_id>/deactivate/` | — | write (not load-tested) | — | — | — | — | — |
| 604 | POST | `dashboard/achievement/rules/<str:rule_id>/activate/` | — | write (not load-tested) | — | — | — | — | — |
| 605 | GET | `dashboard/achievement/simulate/<str:muid>/` | Admin | 6 → 15 | 7× `karma_activity_log` | 28 | 8.1 KB | no index: task_list(event); returns every row (no paging) | M-65, M-64 |
| 606 | GET | `dashboard/achievement/debug/<str:muid>/<str:achievement_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 607 | POST | `dashboard/achievement/manual-issue/` | — | write (not load-tested) | — | — | — | — | — |
| 608 | POST | `dashboard/achievement/revoke/` | — | write (not load-tested) | — | — | — | — | — |
| 609 | GET | `dashboard/achievement/audit/<str:muid>/` | Admin | 2 → 2 | — | 0 | 0.1 KB | — | — |
| 610 | POST | `dashboard/achievement/issue-vc/` | — | write (not load-tested) | — | — | — | — | — |
| 611 | POST | `dashboard/achievement/bulk-issue/` | — | write (not load-tested) | — | — | — | builds a spreadsheet/CSV in the request (api/dashboard/achievement/achievement_views.py:1096); query inside a loop (api/dashboard/achievement/achievement_views.py:1136,1136) | L-59 |
| 612 | GET | `dashboard/achievement/bulk-issue/template/` | Admin | 0 → 0 | — | — | 4.7 KB | builds a spreadsheet/CSV in the request (api/dashboard/achievement/achievement_views.py:1186) | — |
| 613 | GET | `dashboard/achievement/issued-log/` | Admin | 2 → 2 | — | 10 (paged) | 2.9 KB | — | — |
| 614 | POST | `dashboard/achievement/bulk-claim/` | — | write (not load-tested) | — | — | — | — | — |
| 615 | GET | `dashboard/skill/` | Admin | 2 → 2 | — | 10 (paged) | 3.0 KB | — | — |
| 616 | POST | `dashboard/skill/create/` | — | write (not load-tested) | — | — | — | — | — |
| 617 | GET | `dashboard/skill/dropdown/` | Admin | 1 → 1 | — | 84 | 13.3 KB | returns every row (no paging) | M-65 |
| 618 | GET | `dashboard/skill/<str:skill_id>/` | Admin | 2 → 2 | — | — | 0.4 KB | — | — |
| 619 | PUT | `dashboard/skill/<str:skill_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 620 | DELETE | `dashboard/skill/<str:skill_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 621 | GET | `dashboard/skill/<str:skill_id>/tasks/` | Admin | 2 → 2 | — | 0 | 0.4 KB | — | — |
| 622 | GET | `dashboard/media-content/office-hours/` | Admin | 2 → 2 | — | 10 (paged) | 6.1 KB | per-row method fields: OfficeHoursReadSerializer: interest_groups | — |
| 623 | POST | `dashboard/media-content/office-hours/` | — | write (not load-tested) | — | — | — | — | — |
| 624 | GET | `dashboard/media-content/office-hours/<str:record_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: OfficeHoursReadSerializer: interest_groups | — |
| 625 | PATCH | `dashboard/media-content/office-hours/<str:record_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 626 | DELETE | `dashboard/media-content/office-hours/<str:record_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 627 | GET | `dashboard/media-content/salt-mango-tree/` | Admin | 2 → 2 | — | 10 (paged) | 5.5 KB | — | — |
| 628 | POST | `dashboard/media-content/salt-mango-tree/` | — | write (not load-tested) | — | — | — | — | — |
| 629 | GET | `dashboard/media-content/salt-mango-tree/<str:record_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 630 | PATCH | `dashboard/media-content/salt-mango-tree/<str:record_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 631 | DELETE | `dashboard/media-content/salt-mango-tree/<str:record_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 632 | GET | `dashboard/media-content/inspiration-station/` | Admin | 1 → 2 | — | 10 (paged) | 5.5 KB | — | — |
| 633 | POST | `dashboard/media-content/inspiration-station/` | — | write (not load-tested) | — | — | — | — | — |
| 634 | GET | `dashboard/media-content/inspiration-station/<str:record_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 635 | PATCH | `dashboard/media-content/inspiration-station/<str:record_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 636 | DELETE | `dashboard/media-content/inspiration-station/<str:record_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 637 | GET | `dashboard/media-content/grab-your-superpowers/` | Admin | 2 → 2 | — | 10 (paged) | 5.8 KB | — | — |
| 638 | POST | `dashboard/media-content/grab-your-superpowers/` | — | write (not load-tested) | — | — | — | — | — |
| 639 | GET | `dashboard/media-content/grab-your-superpowers/<str:record_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 640 | PATCH | `dashboard/media-content/grab-your-superpowers/<str:record_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 641 | DELETE | `dashboard/media-content/grab-your-superpowers/<str:record_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 642 | POST | `dashboard/media-content/bulk/import/` | — | write (not load-tested) | — | — | — | — | — |
| 643 | GET | `dashboard/media-content/bulk/export/<str:content_type>/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: OfficeHoursReadSerializer: interest_groups | — |
| 644 | GET | `dashboard/community-partner/` | Admin | 8 → 12 | 10× `ig_community_partner_link` | 10 (paged) | 5.0 KB | per-row method fields: CommunityPartnerReadSerializer: interest_groups | M-61 |
| 645 | POST | `dashboard/community-partner/` | — | write (not load-tested) | — | — | — | — | — |
| 646 | GET | `dashboard/community-partner/<str:partner_id>/` | Admin | 2 → 2 | — | 1 | 0.6 KB | per-row method fields: CommunityPartnerReadSerializer: interest_groups | — |
| 647 | PATCH | `dashboard/community-partner/<str:partner_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 648 | DELETE | `dashboard/community-partner/<str:partner_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 649 | GET | `dashboard/category/` | Admin | 8 → 22 | 20× `user` | 10 (paged) | 5.4 KB | — | M-61 |
| 650 | POST | `dashboard/category/` | — | write (not load-tested) | — | — | — | — | — |
| 651 | PUT | `dashboard/category/` | — | write (not load-tested) | — | — | — | — | — |
| 652 | PATCH | `dashboard/category/` | — | write (not load-tested) | — | — | — | — | — |
| 653 | DELETE | `dashboard/category/` | — | write (not load-tested) | — | — | — | — | — |
| 654 | GET | `dashboard/category/<str:category_id>/` | Admin | 3 → 3 | — | — | 0.6 KB | — | — |
| 655 | POST | `dashboard/category/<str:category_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 656 | PUT | `dashboard/category/<str:category_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 657 | PATCH | `dashboard/category/<str:category_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 658 | DELETE | `dashboard/category/<str:category_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 659 | GET | `dashboard/mentor/opportunities/` | Mentor | 2 → 21 | 6× `interest_group` | 6 (paged) | 5.4 KB | — | M-61 |
| 660 | POST | `dashboard/mentor/opportunities/` | — | write (not load-tested) | — | — | — | — | — |
| 661 | GET | `dashboard/mentor/opportunities/public/` | Admin | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 662 | GET | `dashboard/mentor/opportunities/<str:opportunity_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 663 | PATCH | `dashboard/mentor/opportunities/<str:opportunity_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 664 | DELETE | `dashboard/mentor/opportunities/<str:opportunity_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 665 | POST | `dashboard/mentor/opportunities/<str:opportunity_id>/publish/` | — | write (not load-tested) | — | — | — | — | — |
| 666 | POST | `dashboard/mentor/opportunities/<str:opportunity_id>/close/` | — | write (not load-tested) | — | — | — | — | — |
| 667 | GET | `dashboard/mentor/public/profile/<str:mentor_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 668 | GET | `dashboard/mentor/public/availability/<str:mentor_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 669 | GET | `dashboard/mentor/overview/` | Mentor | 10 → 10 | — | 1 | 0.4 KB | response cached; no index: karma_activity_log(mentor_review_status); no index: wallet(karma_last_updated_at) | M-64 |
| 670 | GET | `dashboard/mentor/persona/current/` | Mentor | 2 → 2 | — | 3 | 0.4 KB | — | — |
| 671 | POST | `dashboard/mentor/register/` | — | write (not load-tested) | — | — | — | — | — |
| 672 | PATCH | `dashboard/mentor/register/` | — | write (not load-tested) | — | — | — | — | — |
| 673 | GET | `dashboard/mentor/status/` | Mentor | 5 → 5 | — | 1 | 0.3 KB | — | — |
| 674 | GET | `dashboard/mentor/profile/` | Mentor | 6 → 6 | — | 1 | 0.8 KB | — | — |
| 675 | PATCH | `dashboard/mentor/profile/` | — | write (not load-tested) | — | — | — | — | — |
| 676 | GET | `dashboard/mentor/activity/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 677 | GET | `dashboard/mentor/analytics/personal/` | Mentor | 9 → 9 | 3× `mentorship_session` | 0 | 0.2 KB | — | — |
| 678 | GET | `dashboard/mentor/profile/completion/` | Mentor | 3 → 3 | — | — | 0.2 KB | — | — |
| 679 | GET | `dashboard/mentor/list/` | Admin | 4 → 4 | — | 10 (paged) | 5.5 KB | — | — |
| 680 | GET | `dashboard/mentor/roster/` | Admin | 6 → 6 | — | 1 (paged) | 0.8 KB | — | — |
| 681 | GET | `dashboard/mentor/change-requests/` | Admin | 2 → 2 | — | 0 (paged) | 0.2 KB | — | — |
| 682 | PATCH | `dashboard/mentor/verify/<str:mentor_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 683 | GET | `dashboard/mentor/detail/<str:mentor_id>/` | Admin | 2 → 2 | — | 1 | 0.5 KB | — | — |
| 684 | POST | `dashboard/mentor/session/create/` | — | write (not load-tested) | — | — | — | — | — |
| 685 | GET | `dashboard/mentor/session/list/` | Mentor | 1 → 1 | — | 0 (paged) | 0.2 KB | per-row method fields: SessionListSerializer: entity_name | — |
| 686 | GET | `dashboard/mentor/session/list/<str:session_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: SessionListSerializer: entity_name | — |
| 687 | PATCH | `dashboard/mentor/session/update/<str:session_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 688 | DELETE | `dashboard/mentor/session/update/<str:session_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 689 | POST | `dashboard/mentor/session/complete/<str:session_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 690 | GET | `dashboard/mentor/session/available/` | Admin | 1 → 1 | — | 0 (paged) | 0.2 KB | per-row method fields: SessionListSerializer: entity_name | — |
| 691 | GET | `dashboard/mentor/session/admin/list/` | Admin | 11 → 12 | 10× `user` | 10 (paged) | 8.0 KB | per-row method fields: SessionListSerializer: entity_name | M-61 |
| 692 | PATCH | `dashboard/mentor/session/admin/verify/<str:session_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 693 | GET | `dashboard/mentor/availability/` | Mentor | 1 → 3 | — | 1 (paged) | 0.5 KB | — | — |
| 694 | POST | `dashboard/mentor/availability/` | — | write (not load-tested) | — | — | — | — | — |
| 695 | PATCH | `dashboard/mentor/availability/` | — | write (not load-tested) | — | — | — | — | — |
| 696 | DELETE | `dashboard/mentor/availability/` | — | write (not load-tested) | — | — | — | — | — |
| 697 | GET | `dashboard/mentor/availability/<str:slot_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 698 | POST | `dashboard/mentor/availability/<str:slot_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 699 | PATCH | `dashboard/mentor/availability/<str:slot_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 700 | DELETE | `dashboard/mentor/availability/<str:slot_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 701 | POST | `dashboard/mentor/session/participation/join/<str:session_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 702 | GET | `dashboard/mentor/session/participant/history/` | Lead Enabler | 1 → 2 | — | 1 (paged) | 0.9 KB | per-row method fields: ParticipantListSerializer: session_entity_name | — |
| 703 | POST | `dashboard/mentor/session/participant/add/<str:session_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 704 | GET | `dashboard/mentor/session/participant/list/<str:session_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: ParticipantListSerializer: session_entity_name | — |
| 705 | PATCH | `dashboard/mentor/session/participant/update/<str:link_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 706 | PATCH | `dashboard/mentor/session/participant/feedback/<str:session_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 707 | GET | `dashboard/mentor/tasks/ig-dropdown/` | Mentor | 1 → 1 | — | 1 | 0.1 KB | — | — |
| 708 | GET | `dashboard/mentor/tasks/` | Mentor | 3 → 4 | — | 18 (paged) | 4.3 KB | no index: task_list(requested_by); per-row method fields: MentorTaskListSerializer: skills | M-64 |
| 709 | POST | `dashboard/mentor/tasks/` | — | write (not load-tested) | — | — | — | — | — |
| 710 | GET | `dashboard/mentor/tasks/<str:task_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: MentorTaskListSerializer: skills | — |
| 711 | PUT | `dashboard/mentor/tasks/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 712 | DELETE | `dashboard/mentor/tasks/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 713 | POST | `dashboard/mentor/admin/assign/` | — | write (not load-tested) | — | — | — | — | — |
| 714 | DELETE | `dashboard/mentor/admin/assign/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/dashboard/mentor/mentor_views.py:1186,1199); query inside a loop (api/dashboard/mentor/mentor_views.py:1199) | L-59 |
| 715 | POST | `dashboard/mentor/admin/assign/<str:user_muid>/` | — | write (not load-tested) | — | — | — | — | — |
| 716 | DELETE | `dashboard/mentor/admin/assign/<str:user_muid>/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/dashboard/mentor/mentor_views.py:1186,1199); query inside a loop (api/dashboard/mentor/mentor_views.py:1199) | L-59 |
| 717 | POST | `dashboard/mentor/admin/deactivate/<str:user_mentor_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 718 | POST | `dashboard/mentor/admin/reactivate/<str:user_mentor_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 719 | GET | `dashboard/mentor/<str:mentor_id>/preferred-igs/` | Mentor | 2 → 2 | — | 1 | 0.5 KB | — | — |
| 720 | PATCH | `dashboard/mentor/<str:mentor_id>/preferred-igs/` | — | write (not load-tested) | — | — | — | — | — |
| 721 | GET | `dashboard/mentor/<str:mentor_id>/grants/` | Admin | 5 → 5 | 3× `user` | 3 | 0.8 KB | — | — |
| 722 | DELETE | `dashboard/mentor/<str:mentor_id>/grants/<str:grant_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 723 | POST | `dashboard/mentor/change-company/` | — | write (not load-tested) | — | — | — | — | — |
| 724 | POST | `dashboard/mentor/session/student/request/` | — | write (not load-tested) | — | — | — | — | — |
| 725 | GET | `dashboard/mentor/session/student/my-requests/` | Mentor | 1 → 6 | — | 2 (paged) | 1.4 KB | per-row method fields: StudentSessionRequestListSerializer: entity_name | — |
| 726 | GET | `dashboard/mentor/session/student-requests/` | Mentor | 3 → 3 | — | 0 (paged) | 0.2 KB | per-row method fields: StudentSessionRequestListSerializer: entity_name | — |
| 727 | PATCH | `dashboard/mentor/session/student-requests/<str:session_id>/verify/` | — | write (not load-tested) | — | — | — | — | — |
| 728 | GET | `dashboard/mentor/persona/status/` | Mentor | 1 → 1 | — | — | 0.2 KB | — | — |
| 729 | POST | `dashboard/mentor/persona/switch/` | — | write (not load-tested) | — | — | — | — | — |
| 730 | GET | `dashboard/intern/timesheets/` | Intern | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 731 | POST | `dashboard/intern/timesheets/` | — | write (not load-tested) | — | — | — | — | — |
| 732 | PATCH | `dashboard/intern/timesheets/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/dashboard/intern/timesheet/timesheet_views.py:205); query inside a loop (api/dashboard/intern/timesheet/timesheet_views.py:205) | L-59 |
| 733 | GET | `dashboard/intern/timesheets/prefill/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 734 | GET | `dashboard/intern/timesheets/today/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 735 | GET | `dashboard/intern/timesheets/history/` | Intern | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 736 | GET | `dashboard/intern/timesheets/summary/` | Intern | 1 → 1 | — | — | 0.1 KB | — | — |
| 737 | GET | `dashboard/intern/timesheets/<str:timesheet_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 738 | POST | `dashboard/intern/timesheets/<str:timesheet_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 739 | PATCH | `dashboard/intern/timesheets/<str:timesheet_id>/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/dashboard/intern/timesheet/timesheet_views.py:205); query inside a loop (api/dashboard/intern/timesheet/timesheet_views.py:205) | L-59 |
| 740 | GET | `dashboard/intern/reviews/` | Intern | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 741 | POST | `dashboard/intern/reviews/` | — | write (not load-tested) | — | — | — | — | — |
| 742 | PATCH | `dashboard/intern/reviews/` | — | write (not load-tested) | — | — | — | — | — |
| 743 | GET | `dashboard/intern/reviews/prefill/` | Intern | 1 → 1 | — | 0 | 0.2 KB | — | — |
| 744 | GET | `dashboard/intern/reviews/current/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 745 | GET | `dashboard/intern/reviews/history/` | Intern | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 746 | GET | `dashboard/intern/reviews/<str:review_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 747 | POST | `dashboard/intern/reviews/<str:review_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 748 | PATCH | `dashboard/intern/reviews/<str:review_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 749 | GET | `dashboard/intern/overview/status/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 750 | GET | `dashboard/intern/overview/activity/` | Intern | 1 → 1 | — | 0 (paged) | 0.2 KB | no index: task_list(hashtag) | M-64 |
| 751 | GET | `dashboard/intern/overview/leaderboard/top/` | Intern | 4 → 4 | — | 3 | 1.0 KB | — | — |
| 752 | GET | `dashboard/intern/leaderboard/` | Admin | 7 → 7 | — | 10 (paged) | 3.6 KB | no index: task_list(hashtag) | M-64 |
| 753 | GET | `dashboard/intern/leaderboard/me/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 754 | GET | `dashboard/intern/tasks/categories/` | Admin | 0 → 0 | — | 6 | 0.3 KB | — | — |
| 755 | GET | `dashboard/intern/tasks/mine/` | Intern | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 756 | PATCH | `dashboard/intern/tasks/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 757 | PATCH | `dashboard/intern/tasks/<str:task_id>/submit/` | — | write (not load-tested) | — | — | — | — | — |
| 758 | GET | `dashboard/intern/tasks/<str:task_id>/detail/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 759 | GET | `dashboard/intern/leave/` | Intern | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 760 | POST | `dashboard/intern/leave/` | — | write (not load-tested) | — | — | — | — | — |
| 761 | PATCH | `dashboard/intern/leave/` | — | write (not load-tested) | — | — | — | — | — |
| 762 | GET | `dashboard/intern/leave/history/` | Intern | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 763 | GET | `dashboard/intern/leave/balance/` | Intern | 4 → 4 | 4× `intern_leave_request` | — | 0.1 KB | — | — |
| 764 | GET | `dashboard/intern/leave/<str:leave_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 765 | POST | `dashboard/intern/leave/<str:leave_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 766 | PATCH | `dashboard/intern/leave/<str:leave_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 767 | GET | `dashboard/intern/leave/<str:leave_id>/cancel/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 768 | POST | `dashboard/intern/leave/<str:leave_id>/cancel/` | — | write (not load-tested) | — | — | — | — | — |
| 769 | PATCH | `dashboard/intern/leave/<str:leave_id>/cancel/` | — | write (not load-tested) | — | — | — | — | — |
| 770 | GET | `dashboard/intern/guilds/` | Admin | 0 → 0 | — | 4 | 0.1 KB | — | — |
| 771 | GET | `dashboard/intern/minutes/` | Admin | 2 → 2 | — | 10 (paged) | 8.0 KB | — | — |
| 772 | POST | `dashboard/intern/minutes/` | — | write (not load-tested) | — | — | — | — | — |
| 773 | PUT | `dashboard/intern/minutes/` | — | write (not load-tested) | — | — | — | — | — |
| 774 | DELETE | `dashboard/intern/minutes/` | — | write (not load-tested) | — | — | — | — | — |
| 775 | GET | `dashboard/intern/minutes/<str:minute_id>/` | Admin | 2 → 2 | — | — | 0.8 KB | — | — |
| 776 | POST | `dashboard/intern/minutes/<str:minute_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 777 | PUT | `dashboard/intern/minutes/<str:minute_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 778 | DELETE | `dashboard/intern/minutes/<str:minute_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 779 | GET | `dashboard/manage-interns/reviews/timesheets/<str:timesheet_id>/review/` | Admin | 2 → 2 | — | — | 0.7 KB | — | — |
| 780 | PATCH | `dashboard/manage-interns/reviews/timesheets/<str:timesheet_id>/review/` | — | write (not load-tested) | — | — | — | — | — |
| 781 | GET | `dashboard/manage-interns/reviews/reviews/<str:review_id>/review/` | Admin | 2 → 2 | — | — | 0.9 KB | — | — |
| 782 | PATCH | `dashboard/manage-interns/reviews/reviews/<str:review_id>/review/` | — | write (not load-tested) | — | — | — | — | — |
| 783 | GET | `dashboard/manage-interns/reviews/timesheets/` | Admin | 5 → 12 | 10× `user` | 10 (paged) | 6.2 KB | — | M-61 |
| 784 | GET | `dashboard/manage-interns/reviews/` | Admin | 5 → 12 | 10× `user` | 10 (paged) | 8.7 KB | — | M-61 |
| 785 | GET | `dashboard/manage-interns/tasks/` | Admin | 2 → 2 | — | 10 (paged) | 10.0 KB | — | — |
| 786 | POST | `dashboard/manage-interns/tasks/` | — | write (not load-tested) | — | — | — | — | — |
| 787 | PATCH | `dashboard/manage-interns/tasks/` | — | write (not load-tested) | — | — | — | — | — |
| 788 | DELETE | `dashboard/manage-interns/tasks/` | — | write (not load-tested) | — | — | — | — | — |
| 789 | GET | `dashboard/manage-interns/tasks/by-intern/<str:muid>/` | Admin | 2 → 2 | — | 0 (paged) | 0.2 KB | — | — |
| 790 | POST | `dashboard/manage-interns/tasks/<str:task_id>/verify/` | — | write (not load-tested) | — | — | — | — | — |
| 791 | GET | `dashboard/manage-interns/tasks/<str:task_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 792 | POST | `dashboard/manage-interns/tasks/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 793 | PATCH | `dashboard/manage-interns/tasks/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 794 | DELETE | `dashboard/manage-interns/tasks/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 795 | GET | `dashboard/manage-interns/leave/` | Admin | 2 → 2 | — | 10 (paged) | 5.9 KB | — | — |
| 796 | GET | `dashboard/manage-interns/leave/<str:leave_id>/` | Admin | 2 → 2 | — | — | 0.6 KB | — | — |
| 797 | PATCH | `dashboard/manage-interns/leave/<str:leave_id>/review/` | — | write (not load-tested) | — | — | — | — | — |
| 798 | GET | `dashboard/manage-interns/status/` | Admin | 2 → 2 | — | — | 0.1 KB | — | — |
| 799 | GET | `dashboard/manage-interns/interns/export/` | Admin | 1 → 1 | — | — | 9.8 KB | builds a spreadsheet/CSV in the request (api/dashboard/manage_interns/interns_views.py:188) | — |
| 800 | GET | `dashboard/manage-interns/interns/import/template/` | Admin | 0 → 0 | — | — | 4.7 KB | builds a spreadsheet/CSV in the request (api/dashboard/manage_interns/interns_views.py:213) | — |
| 801 | POST | `dashboard/manage-interns/interns/import/` | — | write (not load-tested) | — | — | — | builds a spreadsheet/CSV in the request (api/dashboard/manage_interns/interns_views.py:260); query inside a loop (api/dashboard/manage_interns/interns_views.py:330,330,340); insert/update inside a loop (api/dashboard/manage_interns/interns_views.py:349,359) | L-59 |
| 802 | GET | `dashboard/manage-interns/interns/` | Admin | 3 → 3 | — | 10 (paged) | 5.4 KB | — | L-58 |
| 803 | POST | `dashboard/manage-interns/interns/` | — | write (not load-tested) | — | — | — | — | — |
| 804 | PATCH | `dashboard/manage-interns/interns/` | — | write (not load-tested) | — | — | — | — | — |
| 805 | DELETE | `dashboard/manage-interns/interns/` | — | write (not load-tested) | — | — | — | — | — |
| 806 | GET | `dashboard/manage-interns/interns/<str:intern_id>/` | Admin | 2 → 2 | — | 0 | 0.6 KB | — | — |
| 807 | POST | `dashboard/manage-interns/interns/<str:intern_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 808 | PATCH | `dashboard/manage-interns/interns/<str:intern_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 809 | DELETE | `dashboard/manage-interns/interns/<str:intern_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 810 | POST | `dashboard/company/register/` | — | write (not load-tested) | — | — | — | — | — |
| 811 | PATCH | `dashboard/company/register/` | — | write (not load-tested) | — | — | — | — | — |
| 812 | GET | `dashboard/company/summary/` | Admin | 7 → 7 | 4× `company` | — | 0.2 KB | no index: task_list(submitted_by_company_id) | M-64 |
| 813 | GET | `dashboard/company/home-summary/` | Mentor | 34 → 61 | 47× `user` | 47 | 8.0 KB | — | M-63 |
| 814 | GET | `dashboard/company/status/` | Company | 2 → 2 | — | 0 | 1.1 KB | — | — |
| 815 | GET | `dashboard/company/profile/` | Mentor | 5 → 5 | — | 0 | 1.1 KB | — | — |
| 816 | PATCH | `dashboard/company/profile/` | — | write (not load-tested) | — | — | — | — | — |
| 817 | GET | `dashboard/company/profile/public/<str:slug>/` | Admin | 4 → 4 | — | 0 | 0.6 KB | per-row method fields: PublicCompanyProfileSerializer: collaboration_summary | — |
| 818 | GET | `dashboard/company/profile/public/<str:slug>/jobs/` | Admin | 6 → 6 | — | 25 (paged) | 7.5 KB | — | — |
| 819 | GET | `dashboard/company/list/` | Admin | 12 → 12 | 10× `user` | 10 (paged) | 6.7 KB | — | M-61 |
| 820 | GET | `dashboard/company/jobs/` | Company | 6 → 43 | 20× `user` | 10 (paged) | 6.3 KB | — | M-61 |
| 821 | POST | `dashboard/company/jobs/` | — | write (not load-tested) | — | — | — | — | — |
| 822 | GET | `dashboard/company/jobs/pending/` | Company | 2 → 2 | — | 0 (paged) | 0.2 KB | — | — |
| 823 | GET | `dashboard/company/jobs/all/` | Admin | 9 → 9 | — | 25 (paged) | 13.8 KB | — | — |
| 824 | GET | `dashboard/company/jobs/<str:job_id>/` | Mentor | 8 → 8 | — | 25 | 7.4 KB | — | — |
| 825 | PATCH | `dashboard/company/jobs/<str:job_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 826 | DELETE | `dashboard/company/jobs/<str:job_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 827 | POST | `dashboard/company/jobs/<str:job_id>/approve/` | — | write (not load-tested) | — | — | — | — | — |
| 828 | POST | `dashboard/company/jobs/<str:job_id>/reject/` | — | write (not load-tested) | — | — | — | — | — |
| 829 | POST | `dashboard/company/jobs/<str:job_id>/request-changes/` | — | write (not load-tested) | — | — | — | — | — |
| 830 | POST | `dashboard/company/jobs/<str:job_id>/view/` | — | write (not load-tested) | — | — | — | — | — |
| 831 | GET | `dashboard/company/jobs/<str:job_id>/analytics/` | Mentor | 7 → 7 | — | — | 0.3 KB | — | — |
| 832 | GET | `dashboard/company/jobs/<str:job_id>/apply/` | Mentor | 6 → 17 | 10× `user` | 10 (paged) | 2.9 KB | — | M-61 |
| 833 | POST | `dashboard/company/jobs/<str:job_id>/apply/` | — | write (not load-tested) | — | — | — | — | — |
| 834 | GET | `dashboard/company/jobs/<str:job_id>/applications/` | Mentor | 6 → 17 | 10× `user` | 10 (paged) | 2.9 KB | — | M-61 |
| 835 | POST | `dashboard/company/jobs/<str:job_id>/applications/` | — | write (not load-tested) | — | — | — | — | — |
| 836 | GET | `dashboard/company/applications/me/` | Student | 1 → 33 | 10× `company_jobs` | 10 (paged) | 15.2 KB | — | M-61 |
| 837 | PATCH | `dashboard/company/applications/<str:app_id>/status/` | — | write (not load-tested) | — | — | — | — | — |
| 838 | DELETE | `dashboard/company/applications/<str:app_id>/withdraw/` | — | write (not load-tested) | — | — | — | — | — |
| 839 | PATCH | `dashboard/company/applications/<str:app_id>/resubmit/` | — | write (not load-tested) | — | — | — | — | — |
| 840 | GET | `dashboard/company/mulearners/` | Mentor | 8 → 8 | — | 10 (paged) | 1.9 KB | — | — |
| 841 | GET | `dashboard/company/mulearners/shortlist/` | Mentor | 5 → 149 | 72× `user_organization_link` | 24 | 5.0 KB | — | M-63, M-65 |
| 842 | POST | `dashboard/company/mulearners/shortlist/` | — | write (not load-tested) | — | — | — | — | — |
| 843 | DELETE | `dashboard/company/mulearners/shortlist/` | — | write (not load-tested) | — | — | — | — | — |
| 844 | GET | `dashboard/company/mulearners/shortlist/<str:user_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 845 | POST | `dashboard/company/mulearners/shortlist/<str:user_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 846 | DELETE | `dashboard/company/mulearners/shortlist/<str:user_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 847 | GET | `dashboard/company/analytics/gigs/` | Mentor | 10 → 10 | — | — | 0.3 KB | — | — |
| 848 | GET | `dashboard/company/analytics/tasks/` | Mentor | 9 → 9 | — | — | 0.3 KB | no index: task_list(submitted_by_company_id) | M-64 |
| 849 | GET | `dashboard/company/talent-pool/analytics/` | Mentor | 27 → 54 | 47× `user` | 47 | 7.4 KB | — | M-63 |
| 850 | GET | `dashboard/company/analytics/campus/trend/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 851 | GET | `dashboard/company/analytics/campus/` | Mentor | 7 → 7 | — | 7 | 0.9 KB | no index: events(organiser_org_id,organiser_type); no index: task_list(submitted_by_company_id) | M-64 |
| 852 | GET | `dashboard/company/talent-pool/insights/` | Mentor | 7 → 8 | — | 10 | 2.3 KB | builds a spreadsheet/CSV in the request (api/dashboard/company/analytics_views.py:447) | — |
| 853 | POST | `dashboard/company/feedback/` | — | write (not load-tested) | — | — | — | — | — |
| 854 | GET | `dashboard/company/feedback/list/` | Mentor | 5 → 6 | — | 10 (paged) | 2.4 KB | — | — |
| 855 | GET | `dashboard/company/impact-report/` | Mentor | 11 → 11 | — | — | 0.5 KB | no index: events(organiser_org_id,organiser_type); no index: task_list(submitted_by_company_id) | M-64 |
| 856 | PATCH | `dashboard/company/impact-report/publish/` | — | write (not load-tested) | — | — | — | — | — |
| 857 | GET | `dashboard/company/collaborations/` | Company | 2 → 23 | 10× `company` | 10 (paged) | 5.8 KB | — | M-61 |
| 858 | POST | `dashboard/company/collaborations/` | — | write (not load-tested) | — | — | — | — | — |
| 859 | GET | `dashboard/company/collaborations/discover/` | Admin | 2 → 12 | 10× `user` | 10 (paged) | 5.8 KB | — | M-61 |
| 860 | POST | `dashboard/company/collaborations/<str:collaboration_id>/respond/` | — | write (not load-tested) | — | — | — | — | — |
| 861 | DELETE | `dashboard/company/collaborations/<str:collaboration_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 862 | POST | `dashboard/company/ig-sponsorship/<str:ig_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 863 | PATCH | `dashboard/company/ig-sponsorship/<str:ig_id>/review/` | — | write (not load-tested) | — | — | — | — | — |
| 864 | GET | `dashboard/company/ig-sponsorship/<str:ig_id>/metrics/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 865 | GET | `dashboard/company/events/templates/` | Mentor | 5 → 5 | — | 25 | 8.0 KB | returns every row (no paging) | M-65 |
| 866 | POST | `dashboard/company/events/templates/` | — | write (not load-tested) | — | — | — | — | — |
| 867 | DELETE | `dashboard/company/events/templates/<str:template_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 868 | POST | `dashboard/company/admin-link/` | — | write (not load-tested) | — | — | — | — | — |
| 869 | GET | `dashboard/company/admin-link/list/` | Company | 2 → 2 | — | 19 | 4.9 KB | — | — |
| 870 | POST | `dashboard/company/admin-link/<str:link_id>/respond/` | — | write (not load-tested) | — | — | — | — | — |
| 871 | DELETE | `dashboard/company/admin-link/<str:link_id>/leave/` | — | write (not load-tested) | — | — | — | — | — |
| 872 | DELETE | `dashboard/company/admin-link/<str:link_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 873 | POST | `dashboard/company/mentor/nominate/` | — | write (not load-tested) | — | — | — | — | — |
| 874 | POST | `dashboard/company/mentor/apply/` | — | write (not load-tested) | — | — | — | — | — |
| 875 | GET | `dashboard/company/mentor/list/` | Company | 3 → 3 | — | 0 | 0.1 KB | — | — |
| 876 | GET | `dashboard/company/tasks/` | Mentor | 5 → 16 | 10× `task_skill_link` | 10 (paged) | 7.8 KB | no index: task_list(submitted_by_company_id); per-row method fields: CompanyTaskListSerializer: skills | M-61, M-64 |
| 877 | POST | `dashboard/company/tasks/` | — | write (not load-tested) | — | — | — | — | — |
| 878 | GET | `dashboard/company/tasks/templates/` | Mentor | 5 → 5 | — | 25 | 5.4 KB | returns every row (no paging) | M-65 |
| 879 | POST | `dashboard/company/tasks/templates/` | — | write (not load-tested) | — | — | — | — | — |
| 880 | DELETE | `dashboard/company/tasks/templates/<str:template_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 881 | GET | `dashboard/company/tasks/<str:task_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: CompanyTaskListSerializer: skills | — |
| 882 | PUT | `dashboard/company/tasks/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 883 | PATCH | `dashboard/company/tasks/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 884 | DELETE | `dashboard/company/tasks/<str:task_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 885 | POST | `dashboard/company/deactivate/` | — | write (not load-tested) | — | — | — | — | — |
| 886 | POST | `dashboard/company/<str:company_id>/deactivate/` | — | write (not load-tested) | — | — | — | — | — |
| 887 | POST | `dashboard/company/<str:company_id>/reactivate/` | — | write (not load-tested) | — | — | — | — | — |
| 888 | GET | `dashboard/company/<str:company_id>/` | Admin | 2 → 2 | — | 0 | 1.1 KB | — | — |
| 889 | PATCH | `dashboard/company/verify/<str:company_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 890 | GET | `dashboard/feature/grit-meter/` | Admin | 1 → 1 | — | — | 0.1 KB | — | — |
| 891 | POST | `dashboard/feature/grit-meter/` | — | write (not load-tested) | — | — | — | — | — |
| 892 | GET | `dashboard/career-lab/hiring/` | Admin | 2 → 16 | 14× `user` | 10 (paged) | 8.8 KB | — | M-61 |
| 893 | POST | `dashboard/career-lab/hiring/` | — | write (not load-tested) | — | — | — | — | — |
| 894 | GET | `dashboard/career-lab/hiring/csv/` | Admin | 1 → 51 | 50× `user` | — | 12.0 KB | — | M-62 |
| 895 | POST | `dashboard/career-lab/hiring/csv/` | — | write (not load-tested) | — | — | — | — | — |
| 896 | GET | `dashboard/career-lab/hiring/<str:hiring_id>/` | Admin | 1 → 3 | — | — | 1.0 KB | — | — |
| 897 | PUT | `dashboard/career-lab/hiring/<str:hiring_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 898 | DELETE | `dashboard/career-lab/hiring/<str:hiring_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 899 | POST | `integrations/kkem/login/` | — | write (not load-tested) | — | — | — | — | — |
| 900 | POST | `integrations/kkem/authorization/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/integrations/kkem/kkem_views.py:130) | M-70 |
| 901 | PATCH | `integrations/kkem/authorization/` | — | write (not load-tested) | — | — | — | — | — |
| 902 | POST | `integrations/kkem/authorization/<str:token>/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/integrations/kkem/kkem_views.py:130) | M-70 |
| 903 | PATCH | `integrations/kkem/authorization/<str:token>/` | — | write (not load-tested) | — | — | — | — | — |
| 904 | GET | `integrations/kkem/user/status/<str:encrypted_data>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 905 | GET | `integrations/kkem/user/<str:encrypted_data>/` | — | not measured (no successful response in test data; 400) | — | — | — | outbound HTTP in the request (api/integrations/kkem/kkem_views.py:247) | — |
| 906 | GET | `integrations/kkem/users/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 907 | GET | `integrations/kkem/users/<str:muid>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 908 | GET | `integrations/kkem/hackathon-stats/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 909 | POST | `integrations/wadhwani/auth-token/` | — | write (not load-tested) | — | — | — | outbound HTTP in the request (api/integrations/wadhwani/wadhwani_views.py:35) | — |
| 910 | POST | `integrations/wadhwani/user-login/` | — | write (not load-tested) | — | — | — | outbound HTTP in the request (api/integrations/wadhwani/wadhwani_views.py:90) | — |
| 911 | POST | `integrations/wadhwani/course-details/` | — | write (not load-tested) | — | — | — | outbound HTTP in the request (api/integrations/wadhwani/wadhwani_views.py:133) | — |
| 912 | POST | `integrations/wadhwani/course-enroll-status/` | — | write (not load-tested) | — | — | — | outbound HTTP in the request (api/integrations/wadhwani/wadhwani_views.py:174) | — |
| 913 | POST | `integrations/wadhwani/course-quiz-data/` | — | write (not load-tested) | — | — | — | outbound HTTP in the request (api/integrations/wadhwani/wadhwani_views.py:224) | — |
| 914 | POST | `integrations/qseverse/issue-vc/` | — | write (not load-tested) | — | — | — | outbound HTTP in the request (api/integrations/qseverse/qseverse_views.py:35) | — |
| 915 | GET | `integrations/qseverse/connected-users/` | Admin | 0 → 0 | — | 0 | 0.1 KB | 1 outbound HTTP call(s); outbound HTTP in the request (api/integrations/qseverse/qseverse_views.py:67) | — |
| 916 | GET | `integrations/qseverse/connected-users/search` | — | not measured (no successful response in test data; 400) | — | — | — | outbound HTTP in the request (api/integrations/qseverse/qseverse_views.py:100) | — |
| 917 | GET | `integrations/qseverse/qs-credentials/` | Admin | 0 → 0 | — | 0 | 0.1 KB | 1 outbound HTTP call(s); outbound HTTP in the request (api/integrations/qseverse/qseverse_views.py:135) | — |
| 918 | GET | `integrations/mufifa/verify-task/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 919 | GET | `url-shortener/create/` | Admin | 3 → 3 | — | 10 (paged) | 10.6 KB | — | — |
| 920 | POST | `url-shortener/create/` | — | write (not load-tested) | — | — | — | — | — |
| 921 | PUT | `url-shortener/create/` | — | write (not load-tested) | — | — | — | — | — |
| 922 | DELETE | `url-shortener/create/` | — | write (not load-tested) | — | — | — | — | — |
| 923 | GET | `url-shortener/edit/<str:url_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 924 | POST | `url-shortener/edit/<str:url_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 925 | PUT | `url-shortener/edit/<str:url_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 926 | DELETE | `url-shortener/edit/<str:url_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 927 | GET | `url-shortener/list/` | Admin | 3 → 3 | — | 10 (paged) | 10.6 KB | — | — |
| 928 | POST | `url-shortener/list/` | — | write (not load-tested) | — | — | — | — | — |
| 929 | PUT | `url-shortener/list/` | — | write (not load-tested) | — | — | — | — | — |
| 930 | DELETE | `url-shortener/list/` | — | write (not load-tested) | — | — | — | — | — |
| 931 | GET | `url-shortener/delete/<str:url_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 932 | POST | `url-shortener/delete/<str:url_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 933 | PUT | `url-shortener/delete/<str:url_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 934 | DELETE | `url-shortener/delete/<str:url_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 935 | GET | `url-shortener/get-analytics/<str:url_id>/` | Admin | 4 → 4 | — | 0 | 1.1 KB | — | — |
| 936 | GET | `protected/organisation/institutes/<str:organisation_type>/<str:district_name>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 937 | GET | `protected/organisation/get-institutes/<str:district_name>/` | Admin | 2 → 2 | — | 0 | 0.1 KB | — | — |
| 938 | GET | `hackathon/list-hackathons/` | Admin | 1 → 1 | — | 0 | 0.1 KB | per-row method fields: HackathonRetrievalSerializer: editable, is_applied | — |
| 939 | POST | `hackathon/list-hackathons/` | — | write (not load-tested) | — | — | — | — | — |
| 940 | PUT | `hackathon/list-hackathons/` | — | write (not load-tested) | — | — | — | — | — |
| 941 | DELETE | `hackathon/list-hackathons/` | — | write (not load-tested) | — | — | — | — | — |
| 942 | GET | `hackathon/list-hackathons/upcoming/` | Admin | 1 → 1 | — | 0 | 0.1 KB | per-row method fields: HackathonRetrievalSerializer: editable, is_applied | — |
| 943 | POST | `hackathon/list-hackathons/upcoming/` | — | write (not load-tested) | — | — | — | — | — |
| 944 | PUT | `hackathon/list-hackathons/upcoming/` | — | write (not load-tested) | — | — | — | — | — |
| 945 | DELETE | `hackathon/list-hackathons/upcoming/` | — | write (not load-tested) | — | — | — | — | — |
| 946 | GET | `hackathon/list-hackathons/<str:hackathon_id>/` | Admin | 3 → 3 | — | — | 0.6 KB | per-row method fields: HackathonRetrievalSerializer: editable, is_applied | — |
| 947 | POST | `hackathon/list-hackathons/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 948 | PUT | `hackathon/list-hackathons/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 949 | DELETE | `hackathon/list-hackathons/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 950 | GET | `hackathon/info/<str:hackathon_id>/` | Admin | 3 → 3 | — | 1 | 0.8 KB | per-row method fields: HackathonInfoSerializer: form_fields, is_applied | — |
| 951 | GET | `hackathon/create-hackathon/` | Admin | 1 → 1 | — | 0 | 0.1 KB | per-row method fields: HackathonRetrievalSerializer: editable, is_applied | — |
| 952 | POST | `hackathon/create-hackathon/` | — | write (not load-tested) | — | — | — | — | — |
| 953 | PUT | `hackathon/create-hackathon/` | — | write (not load-tested) | — | — | — | — | — |
| 954 | DELETE | `hackathon/create-hackathon/` | — | write (not load-tested) | — | — | — | — | — |
| 955 | GET | `hackathon/edit-hackathon/<str:hackathon_id>/` | Admin | 3 → 3 | — | — | 0.6 KB | per-row method fields: HackathonRetrievalSerializer: editable, is_applied | — |
| 956 | POST | `hackathon/edit-hackathon/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 957 | PUT | `hackathon/edit-hackathon/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 958 | DELETE | `hackathon/edit-hackathon/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 959 | GET | `hackathon/delete-hackathon/<str:hackathon_id>/` | Admin | 3 → 3 | — | — | 0.6 KB | per-row method fields: HackathonRetrievalSerializer: editable, is_applied | — |
| 960 | POST | `hackathon/delete-hackathon/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 961 | PUT | `hackathon/delete-hackathon/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 962 | DELETE | `hackathon/delete-hackathon/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 963 | PUT | `hackathon/publish-hackathon/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 964 | POST | `hackathon/submit-hackathon/` | — | write (not load-tested) | — | — | — | — | — |
| 965 | GET | `hackathon/list-organiser-hackathons/<str:hackathon_id>/` | Admin | 1 → 1 | — | 0 | 0.1 KB | — | — |
| 966 | POST | `hackathon/list-organiser-hackathons/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 967 | DELETE | `hackathon/list-organiser-hackathons/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 968 | GET | `hackathon/add-organiser/<str:hackathon_id>/` | Admin | 1 → 1 | — | 0 | 0.1 KB | — | — |
| 969 | POST | `hackathon/add-organiser/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 970 | DELETE | `hackathon/add-organiser/<str:hackathon_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 971 | GET | `hackathon/delete-organiser/<str:organiser_link_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 972 | POST | `hackathon/delete-organiser/<str:organiser_link_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 973 | DELETE | `hackathon/delete-organiser/<str:organiser_link_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 974 | GET | `hackathon/list-applicants/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: ListApplicantsSerializer: data | — |
| 975 | GET | `hackathon/list-applicants/<str:hackathon_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: ListApplicantsSerializer: data | — |
| 976 | GET | `hackathon/list-form/<str:hackathon_id>/` | Admin | 2 → 2 | — | 1 | 0.4 KB | — | — |
| 977 | GET | `hackathon/list-organisations/` | Admin | 1 → 1 | — | 145 | 21.2 KB | returns every row (no paging) | M-65 |
| 978 | GET | `hackathon/list-districts/` | Admin | 1 → 1 | — | 161 | 20.7 KB | — | — |
| 979 | GET | `hackathon/list-default-form-fields/` | Admin | 0 → 0 | — | — | 0.2 KB | — | — |
| 980 | GET | `notification/` | Student | 2 → 2 | — | 20 | 12.9 KB | — | L-57 |
| 981 | GET | `notification/unread-count/` | Student | 1 → 1 | — | — | 0.1 KB | — | H-40, L-57 |
| 982 | PATCH | `notification/read-all/` | — | write (not load-tested) | — | — | — | — | — |
| 983 | PATCH | `notification/read/` | — | write (not load-tested) | — | — | — | — | — |
| 984 | PATCH | `notification/<str:notification_id>/read/` | — | write (not load-tested) | — | — | — | — | — |
| 985 | PATCH | `notification/<str:notification_id>/archive/` | — | write (not load-tested) | — | — | — | — | — |
| 986 | DELETE | `notification/<str:notification_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 987 | DELETE | `notification/delete/all/` | — | write (not load-tested) | — | — | — | — | — |
| 988 | DELETE | `notification/broadcast/delete/id/<str:broadcast_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 989 | DELETE | `notification/broadcast/delete/all/` | — | write (not load-tested) | — | — | — | — | — |
| 990 | GET | `notification/broadcast/list/all/` | Admin | 1 → 1 | — | 28 | 17.2 KB | returns every row (no paging); per-row method fields: BroadcastNotificationAdminSerializer: target_details | M-65 |
| 991 | POST | `notification/broadcast/create/` | — | write (not load-tested) | — | — | — | — | — |
| 992 | PATCH | `notification/broadcast/update/id/<str:broadcast_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 993 | GET | `public/campus-details/<str:college_code>/` | Admin | 17 → 19 | 3× `user_ig_link` | 20 | 4.9 KB | response cached; no index: wallet(karma_last_updated_at); per-row method fields: CampusDetailsPublicSerializer: total_karma, rank, social_links, campus_lead | M-66, M-64 |
| 994 | GET | `public/lc-list` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: LcListSerializer: karma | — |
| 995 | GET | `public/<str:circle_id>/lc-details/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: LcDetailsSerializer: total_karma, rank | — |
| 996 | GET | `public/lc-dashboard/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 997 | GET | `public/lc-report/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 998 | GET | `public/college-wise-lc-report/` | Admin | 2 → 2 | — | 10 (paged) | 0.9 KB | — | — |
| 999 | GET | `public/college-wise-lc-report/csv/` | Admin | 1 → 1 | — | — | 0.1 KB | — | — |
| 1000 | GET | `public/lc-report/csv/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 1001 | GET | `public/lc-enrollment/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 1002 | GET | `public/lc-enrollment/csv/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 1003 | GET | `public/global-count/` | Admin | 5 → 5 | — | 2 | 0.3 KB | — | — |
| 1004 | GET | `public/gta-sandshore/` | — | not measured (no successful response in test data; 500) | — | — | — | outbound HTTP in the request (api/common/common_views.py:674) | — |
| 1005 | GET | `public/profile-pic/<str:muid>/` | Admin | 1 → 1 | — | — | 0.1 KB | — | — |
| 1006 | GET | `public/list-ig/` | Admin | 1 → 1 | — | 7 | 0.3 KB | — | — |
| 1007 | GET | `public/list-ig-top100/` | Admin | 0 → 0 | — | 0 | 0.1 KB | — | — |
| 1008 | GET | `public/list/levels/` | Admin | 21 → 48 | 47× `task_list` | 47 | 13.1 KB | query inside a loop (api/common/common_views.py:805,805) | L-56 |
| 1009 | GET | `public/leaderboard/top-100/` | Admin | 301 → 301 | 100× `wallet` | 100 | 15.8 KB | — | H-37 |
| 1010 | GET | `public/list/college/` | Admin | 2 → 2 | — | 28 | 4.4 KB | returns every row (no paging) | M-65 |
| 1011 | GET | `public/list/district/` | Admin | 1 → 1 | — | 0 | 0.1 KB | — | — |
| 1012 | GET | `public/list/state/` | Admin | 1 → 1 | — | 0 | 0.1 KB | — | — |
| 1013 | GET | `public/list/country/` | Admin | 1 → 1 | — | 245 | 31.4 KB | — | — |
| 1014 | GET | `public/external/user/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 1015 | GET | `public/jobs/` | Admin | 9 → 9 | — | 25 (paged) | 13.8 KB | — | — |
| 1016 | GET | `public/ig/list/` | Admin | 9 → 11 | — | 7 | 20.7 KB | response cached | M-60 |
| 1017 | GET | `public/ig/<str:pk>/` | Admin | 13 → 25 | 10× `user` | 5 | 5.8 KB | — | M-60 |
| 1018 | GET | `public/career-lab/ongoing/` | Admin | 1 → 51 | 50× `user` | 28 | 24.0 KB | returns every row (no paging) | M-65 |
| 1019 | GET | `public/career-lab/previous/` | Admin | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 1020 | GET | `public/events/` | Admin | 2 → 2 | — | 1 (paged) | 0.9 KB | no index: events(deleted_at,end_datetime,status); per-row method fields: EventListItemSerializer: viewer_interest_status | M-64 |
| 1021 | GET | `public/events/featured/` | Admin | 1 → 1 | — | 0 (paged) | 0.2 KB | no index: events(deleted_at,end_datetime,status); per-row method fields: EventListItemSerializer: viewer_interest_status | M-64 |
| 1022 | GET | `public/events/<str:event_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 1023 | GET | `top100/leaderboard/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 1024 | POST | `launchpad/register-company/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/launchpad/launchpad_views.py:155) | M-70 |
| 1025 | POST | `launchpad/register-recruiter/` | — | write (not load-tested) | — | — | — | — | — |
| 1026 | GET | `launchpad/company-list/` | Admin | 1 → 1 | — | 168 | 80.3 KB | returns every row (no paging) | M-65 |
| 1027 | GET | `launchpad/company-list-verified/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 1028 | POST | `launchpad/login-company/` | — | write (not load-tested) | — | — | — | — | — |
| 1029 | POST | `launchpad/login-recruiter/` | — | write (not load-tested) | — | — | — | — | — |
| 1030 | POST | `launchpad/refresh-token/` | — | write (not load-tested) | — | — | — | — | — |
| 1031 | POST | `launchpad/add-job/` | — | write (not load-tested) | — | — | — | — | — |
| 1032 | GET | `launchpad/job/<str:job_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 1033 | PUT | `launchpad/job/<str:job_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1034 | DELETE | `launchpad/job/<str:job_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1035 | POST | `launchpad/company-info/` | — | write (not load-tested) | — | — | — | — | — |
| 1036 | POST | `launchpad/recruiter-info/` | — | write (not load-tested) | — | — | — | — | — |
| 1037 | POST | `launchpad/company-verify/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/launchpad/launchpad_views.py:994) | M-70 |
| 1038 | GET | `launchpad/list-jobs/` | Campus IG Lead | 2 → 2 | — | 56 | 70.6 KB | returns every row (no paging) | M-65 |
| 1039 | POST | `launchpad/verify-task/` | — | write (not load-tested) | — | — | — | — | — |
| 1040 | GET | `launchpad/list-launchpad-students/<str:job_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: EligibleStudentSerializer: candidate_links, karma_distribution | — |
| 1041 | GET | `launchpad/hire-requests/` | — | not measured (no successful response in test data; 500) | — | — | — | query inside a loop (api/launchpad/launchpad_views.py:1312,1312,1312) | — |
| 1042 | POST | `launchpad/send-job-invitations/` | — | write (not load-tested) | — | — | — | query inside a loop (api/launchpad/launchpad_views.py:1544,1544) | L-59 |
| 1043 | GET | `launchpad/student/job-invitations/` | Comic Admin | 1 → 2 | — | 2 (paged) | 2.4 KB | — | — |
| 1044 | POST | `launchpad/student/apply-to-job/` | — | write (not load-tested) | — | — | — | — | — |
| 1045 | GET | `launchpad/accepted-students/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 1046 | GET | `launchpad/accepted-students/<str:job_id>/` | — | not measured (no successful response in test data; 500) | — | — | — | — | — |
| 1047 | POST | `launchpad/schedule-interview/` | — | write (not load-tested) | — | — | — | — | — |
| 1048 | POST | `launchpad/application-final-decision/` | — | write (not load-tested) | — | — | — | — | — |
| 1049 | PATCH | `launchpad/delete-company/` | — | write (not load-tested) | — | — | — | — | — |
| 1050 | GET | `launchpad/leaderboard/` | Admin | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 1051 | GET | `launchpad/task-completed-leaderboard/` | Admin | 2 → 2 | — | 0 (paged) | 0.2 KB | no index: task_list(event) | M-64 |
| 1052 | GET | `launchpad/list-participants/` | Admin | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 1053 | GET | `launchpad/launchpad-details/` | Admin | 5 → 5 | 4× `user_organization_link` | — | 0.1 KB | no index: task_list(event,hashtag) | M-64 |
| 1054 | GET | `launchpad/college-data/` | Admin | 1 → 1 | — | 0 (paged) | 0.2 KB | — | — |
| 1055 | GET | `launchpad/user-college-link/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: LaunchpadUserListSerializer: colleges | — |
| 1056 | POST | `launchpad/user-college-link/` | — | write (not load-tested) | — | — | — | query inside a loop (api/launchpad/launchpad_views.py:2593,2593,2596); insert/update inside a loop (api/launchpad/launchpad_views.py:2599,2601) | L-59 |
| 1057 | PUT | `launchpad/user-college-link/` | — | write (not load-tested) | — | — | — | — | — |
| 1058 | GET | `launchpad/user-college-link/<str:email>` | — | not measured (no successful response in test data; 500) | — | — | — | per-row method fields: LaunchpadUserListSerializer: colleges | — |
| 1059 | POST | `launchpad/user-college-link/<str:email>` | — | write (not load-tested) | — | — | — | query inside a loop (api/launchpad/launchpad_views.py:2593,2593,2596); insert/update inside a loop (api/launchpad/launchpad_views.py:2599,2601) | L-59 |
| 1060 | PUT | `launchpad/user-college-link/<str:email>` | — | write (not load-tested) | — | — | — | — | — |
| 1061 | GET | `launchpad/user-college-link-public/<str:email>` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: LaunchpadUserListSerializer: colleges | — |
| 1062 | GET | `launchpad/user-profile/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: LaunchpadUserListSerializer: colleges | — |
| 1063 | PUT | `launchpad/user-profile/` | — | write (not load-tested) | — | — | — | — | — |
| 1064 | GET | `launchpad/user-college-data/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 1065 | POST | `launchpad/bulk-user-college-link/` | — | write (not load-tested) | — | — | — | query inside a loop (api/launchpad/launchpad_views.py:2845,2845,2851); insert/update inside a loop (api/launchpad/launchpad_views.py:2854,2856) | L-59 |
| 1066 | GET | `launchpad/list-participants-admin/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 1067 | GET | `launchpad/user-details/<str:launchpad_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: UserProfileSerializer: percentile, rank, interest_groups | — |
| 1068 | GET | `launchpad/socials/<str:launchpad_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 1069 | GET | `launchpad/user-log/<str:launchpad_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 1070 | GET | `launchpad/get-user-levels/<str:launchpad_id>/` | — | not measured (no successful response in test data; 400) | — | — | — | per-row method fields: UserLevelSerializer: tasks | — |
| 1071 | GET | `launchpad/ig-leaderboard/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 1072 | POST | `launchpad/forgot-password/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/launchpad/launchpad_views.py:3203) | M-70 |
| 1073 | POST | `launchpad/reset-password/` | — | write (not load-tested) | — | — | — | — | — |
| 1074 | POST | `launchpad/verify-reset-token/` | — | write (not load-tested) | — | — | — | — | — |
| 1075 | POST | `launchpad/change-password/` | — | write (not load-tested) | — | — | — | — | — |
| 1076 | POST | `donate/order/` | — | write (not load-tested) | — | — | — | — | — |
| 1077 | POST | `donate/verify/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/donate/views.py:573) | M-70 |
| 1078 | POST | `donate/subscription/create/` | — | write (not load-tested) | — | — | — | — | — |
| 1079 | POST | `donate/subscription/verify/` | — | write (not load-tested) | — | — | — | sends e-mail in the request (api/donate/views.py:813) | M-70 |
| 1080 | POST | `donate/bank-transfer/` | — | write (not load-tested) | — | — | — | — | — |
| 1081 | GET | `calendar/ig-mentor/<str:ig_id>/sessions/` | Admin | 2 → 2 | — | 0 | 0.1 KB | — | — |
| 1082 | GET | `calendar/campus-mentor/<str:campus_id>/sessions/` | Admin | 2 → 2 | — | 0 | 0.1 KB | — | — |
| 1083 | GET | `calendar/company/<str:company_org_id>/sessions/` | Admin | 2 → 2 | — | 0 | 0.1 KB | — | — |
| 1084 | GET | `calendar/events/` | Admin | 1 → 1 | — | 1 | 0.4 KB | no index: events(deleted_at,status) | M-64 |
| 1085 | GET | `calendar/ig/<str:ig_id>/events/` | Admin | 2 → 2 | — | 0 | 0.1 KB | no index: events(deleted_at,organiser_ig_id,scope_ig_id,status) | M-64 |
| 1086 | GET | `calendar/campus/<str:campus_id>/events/` | Admin | 2 → 2 | — | 0 | 0.1 KB | no index: events(deleted_at,organiser_org_id,scope_org_id,status) | M-64 |
| 1087 | GET | `calendar/company/<str:company_id>/events/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 1088 | GET | `muComics/comics/genres/` | Admin | 2 → 2 | — | 10 (paged) | 3.3 KB | — | — |
| 1089 | POST | `muComics/comics/genres/` | — | write (not load-tested) | — | — | — | — | — |
| 1090 | GET | `muComics/comics/genres/<str:genre_id>/` | Admin | 1 → 1 | — | — | 0.5 KB | — | — |
| 1091 | PATCH | `muComics/comics/genres/<str:genre_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1092 | DELETE | `muComics/comics/genres/<str:genre_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1093 | POST | `muComics/comics/genres/<str:genre_id>/reinstate/` | — | write (not load-tested) | — | — | — | — | — |
| 1094 | GET | `muComics/comics/` | Admin | 16 → 15 | 10× `comic_contributor_link` | 10 (paged) | 8.5 KB | — | M-61 |
| 1095 | POST | `muComics/comics/` | — | write (not load-tested) | — | — | — | — | — |
| 1096 | GET | `muComics/comics/<str:comic_id>/` | Admin | 5 → 5 | — | 1 | 1.6 KB | — | — |
| 1097 | PATCH | `muComics/comics/<str:comic_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1098 | DELETE | `muComics/comics/<str:comic_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1099 | POST | `muComics/comics/<str:comic_id>/publish/` | — | write (not load-tested) | — | — | — | — | — |
| 1100 | POST | `muComics/comics/<str:comic_id>/archive/` | — | write (not load-tested) | — | — | — | — | — |
| 1101 | POST | `muComics/comics/<str:comic_id>/unarchive/` | — | write (not load-tested) | — | — | — | — | — |
| 1102 | GET | `muComics/comics/<str:comic_id>/contributors/` | Admin | 2 → 2 | — | 0 (paged) | 0.2 KB | — | — |
| 1103 | POST | `muComics/comics/<str:comic_id>/contributors/` | — | write (not load-tested) | — | — | — | — | — |
| 1104 | PATCH | `muComics/comics/<str:comic_id>/contributors/<str:contributor_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1105 | DELETE | `muComics/comics/<str:comic_id>/contributors/<str:contributor_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1106 | POST | `muComics/comics/<str:comic_id>/genres/` | — | write (not load-tested) | — | — | — | — | — |
| 1107 | DELETE | `muComics/comics/<str:comic_id>/genres/<str:link_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1108 | GET | `muComics/comments/comic/<str:comic_id>/list/` | Admin | 4 → 2 | — | 0 (paged) | 0.2 KB | — | — |
| 1109 | POST | `muComics/comments/comic/<str:comic_id>/create/` | — | write (not load-tested) | — | — | — | — | — |
| 1110 | GET | `muComics/comments/chapter/<str:chapter_id>/list/` | — | not measured (no successful response in test data; 404) | — | — | — | — | — |
| 1111 | POST | `muComics/comments/chapter/<str:chapter_id>/create/` | — | write (not load-tested) | — | — | — | — | — |
| 1112 | GET | `muComics/comments/admin/` | Comic Admin | 3 → 3 | — | 10 (paged) | 9.6 KB | — | — |
| 1113 | DELETE | `muComics/comments/admin/<str:comment_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1114 | PATCH | `muComics/comments/<str:comment_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1115 | DELETE | `muComics/comments/<str:comment_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1116 | POST | `muComics/chapters/upload-url/` | — | write (not load-tested) | — | — | — | — | — |
| 1117 | GET | `muComics/chapters/` | — | not measured (no successful response in test data; 400) | — | — | — | — | — |
| 1118 | POST | `muComics/chapters/` | — | write (not load-tested) | — | — | — | — | — |
| 1119 | GET | `muComics/chapters/<str:chapter_id>/` | — | not measured (no successful response in test data; 404) | — | — | — | — | — |
| 1120 | PATCH | `muComics/chapters/<str:chapter_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1121 | DELETE | `muComics/chapters/<str:chapter_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1122 | POST | `muComics/chapters/<str:chapter_id>/publish/` | — | write (not load-tested) | — | — | — | — | — |
| 1123 | POST | `muComics/chapters/<str:chapter_id>/archive/` | — | write (not load-tested) | — | — | — | — | — |
| 1124 | GET | `muComics/chapters/<str:chapter_id>/pages/` | — | not measured (no successful response in test data; 404) | — | — | — | — | — |
| 1125 | POST | `muComics/chapters/<str:chapter_id>/pages/` | — | write (not load-tested) | — | — | — | — | — |
| 1126 | POST | `muComics/chapters/<str:chapter_id>/pages/reorder/` | — | write (not load-tested) | — | — | — | — | — |
| 1127 | POST | `muComics/chapters/<str:chapter_id>/pages/register/` | — | write (not load-tested) | — | — | — | insert/update inside a loop (api/muComics/chapter/chapter_views.py:779) | L-59 |
| 1128 | PATCH | `muComics/chapters/pages/<str:page_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1129 | DELETE | `muComics/chapters/pages/<str:page_id>/` | — | write (not load-tested) | — | — | — | — | — |
| 1130 | GET | `muComics/reader/me/` | Campus IG Lead | 4 → 4 | — | — | 0.2 KB | — | — |
| 1131 | GET | `muComics/reader/me/bookmarks/` | Campus Lead | 1 → 2 | — | 2 (paged) | 1.0 KB | — | — |
| 1132 | GET | `muComics/reader/me/progress/` | Admin | 1 → 2 | — | 1 (paged) | 0.6 KB | — | — |
| 1133 | POST | `muComics/reader/comics/<str:comic_id>/likes/` | — | write (not load-tested) | — | — | — | — | — |
| 1134 | DELETE | `muComics/reader/comics/<str:comic_id>/likes/` | — | write (not load-tested) | — | — | — | — | — |
| 1135 | POST | `muComics/reader/comics/<str:comic_id>/bookmarks/` | — | write (not load-tested) | — | — | — | — | — |
| 1136 | DELETE | `muComics/reader/comics/<str:comic_id>/bookmarks/` | — | write (not load-tested) | — | — | — | — | — |
| 1137 | GET | `muComics/reader/comics/<str:comic_id>/interaction-status/` | Admin | 2 → 2 | — | — | 0.1 KB | — | — |
| 1138 | GET | `muComics/reader/comics/<str:comic_id>/progress/` | Admin | 1 → 1 | — | — | 0.1 KB | — | — |
| 1139 | PUT | `muComics/reader/comics/<str:comic_id>/progress/` | — | write (not load-tested) | — | — | — | — | — |
| 1140 | GET | `api/schema/` | — | not measured (no successful response in test data; 403) | — | — | — | — | — |

## Appendix J — Performance of every dashboard page (129 rows)

Each page was opened once with a cold cache, as the role in "Tested as", on the production build, with mobile throttling (4× slower CPU, 150 ms round trip, 1.6 Mbps down).
- **JS downloaded:** script files / compressed KB. **JS unused on load:** the share of the downloaded JavaScript that did not run before the page settled (V8 coverage), with its unzipped size.
- **API calls on load:** calls to the backend until the page settled (compressed KB). **Sequential API rounds:** the longest chain of calls where each one started after the one before it had finished. **Data ready at:** when the last of those calls finished, counted from the start of navigation.
- **FCP / LCP:** first and largest contentful paint. **TBT:** Total Blocking Time — the sum of main-thread long-task time over 50 ms after FCP. **CLS:** layout shift. **Prefetches:** Next.js RSC requests for other pages made during load.
- "Other notes" lists redirects, the wait for `user/info` (H-40), duplicate or failed calls, calls repeated after load (polling), large images, and the result of typing 6 letters into the page's search box.

| # | Page | Tested as | JS downloaded (files / KB) | JS unused on load | API calls on load (KB) | Sequential API rounds | Data ready at | FCP / LCP | Blocking time (TBT) | CLS | DOM nodes / JS heap | Prefetches (RSC) | Other notes | Issues |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `/` | Admin | 45 / 832 | 69% (2907 KB unzipped) | 9 (45) | 2 | 8.8 s | 1.8 s / 8.8 s | 2245 ms | 0.006 | 851 / 36.7 MB | 46 | redirected to `/dashboard`; page requests start only after `user/info` returns; images 293 KB | H-40, H-36, M-64, H-37, M-60, M-67 |
| 2 | `/callback` | Student | 51 / 882 | 87% (3012 KB unzipped) | 0 (0) | 0 | — | 1.5 s / 4.3 s | 441 ms | 0.002 | 119 / 13.8 MB | 1 | — | — |
| 3 | `/dashboard` | Student | 45 / 832 | 69% (2907 KB unzipped) | 9 (47) | 2 | 8.7 s | 1.6 s / 8.4 s | 2067 ms | 0.007 | 799 / 37.0 MB | 46 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, H-37, M-60, M-67 |
| 4 | `/dashboard/campus/[id]` | Campus Lead | 39 / 702 | 65% (2383 KB unzipped) | 6 (6) | 2 | 7.3 s | 1.6 s / 7.4 s | 1657 ms | 0.015 | 775 / 37.8 MB | 13 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, M-66 |
| 5 | `/dashboard/campus/manage` | Campus Lead | 42 / 751 | 60% (2561 KB unzipped) | 15 (19) | 3 | 9.0 s | 1.6 s / 8.1 s | 2933 ms | 0.007 | 1293 / 49.6 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 6 API call(s), 6 server round trip(s) | H-39, H-40, H-36, M-64, M-66, M-69 |
| 6 | `/dashboard/changelog` | Student | 38 / 694 | 64% (2404 KB unzipped) | 4 (4) | 2 | 7.4 s | 1.6 s / 7.3 s | 1904 ms | 0.001 | 744 / 37.5 MB | 15 | images 293 KB | H-39, H-40, H-36, M-64 |
| 7 | `/dashboard/company` | Company | 39 / 696 | 65% (2386 KB unzipped) | 6 (5) | 3 | 8.0 s | 1.6 s / 7.9 s | 2249 ms | 0.001 | 648 / 32.2 MB | 36 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, M-67 |
| 8 | `/dashboard/company/admin` | Company | 40 / 701 | 65% (2381 KB unzipped) | 8 (11) | 3 | 7.9 s | 1.6 s / 7.7 s | 2001 ms | 0.114 | 904 / 40.6 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 9 | `/dashboard/company/analytics` | Company | 41 / 708 | 65% (2416 KB unzipped) | 7 (13) | 3 | 7.9 s | 1.6 s / 7.8 s | 2030 ms | 0.001 | 605 / 41.1 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, M-63 |
| 10 | `/dashboard/company/collaborations` | Company | 40 / 703 | 65% (2387 KB unzipped) | 8 (17) | 3 | 8.0 s | 1.6 s / 7.8 s | 2320 ms | 0.001 | 526 / 32.9 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, M-61 |
| 11 | `/dashboard/company/event-templates` | Company | 40 / 701 | 65% (2379 KB unzipped) | 6 (5) | 3 | 7.9 s | 1.6 s / 7.9 s | 2117 ms | 0.001 | 526 / 43.4 MB | 13 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 12 | `/dashboard/company/feedback` | Company | 40 / 703 | 64% (2388 KB unzipped) | 8 (9) | 3 | 7.8 s | 1.6 s / 7.5 s | 2031 ms | 0.012 | 526 / 31.8 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 13 | `/dashboard/company/ig-requests` | Company | 40 / 703 | 64% (2386 KB unzipped) | 7 (7) | 3 | 8.1 s | 1.6 s / 7.9 s | 2225 ms | 0.001 | 643 / 32.4 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-60 |
| 14 | `/dashboard/company/ig-sponsorship` | Company | 40 / 700 | 65% (2375 KB unzipped) | 8 (42) | 4 | 8.2 s | 1.6 s / 7.5 s | 2198 ms | 0.001 | 545 / 41.7 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, M-60 |
| 15 | `/dashboard/company/jobs` | Company | 42 / 740 | 66% (2549 KB unzipped) | 7 (12) | 3 | 8.1 s | 1.6 s / 7.9 s | 2172 ms | 0.001 | 870 / 33.9 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-61 |
| 16 | `/dashboard/company/jobs/[jobId]` | Company | 42 / 740 | 66% (2549 KB unzipped) | 15 (39) | 4 | 8.8 s | 1.6 s / 7.9 s | 2444 ms | 0.001 | 1203 / 43.3 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 6 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-61, M-69 |
| 17 | `/dashboard/company/jobs/[jobId]/edit` | Company | 42 / 741 | 66% (2551 KB unzipped) | 7 (13) | 3 | 8.0 s | 1.6 s / 7.8 s | 2195 ms | 0.001 | 606 / 32.4 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 18 | `/dashboard/company/jobs/create` | Company | 42 / 741 | 66% (2549 KB unzipped) | 6 (5) | 3 | 8.0 s | 1.6 s / 7.8 s | 2195 ms | 0.001 | 604 / 38.4 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 19 | `/dashboard/company/mentors` | Company | 40 / 702 | 65% (2382 KB unzipped) | 7 (5) | 3 | 8.0 s | 1.6 s / 7.8 s | 2183 ms | 0.001 | 525 / 40.0 MB | 11 | page requests start only after `user/info` returns; images 305 KB | H-39, H-40, H-36, M-64 |
| 20 | `/dashboard/company/profile/edit` | Company | 40 / 704 | 65% (2392 KB unzipped) | 6 (5) | 3 | 7.7 s | 1.6 s / 7.6 s | 1924 ms | 0.001 | 601 / 39.9 MB | 14 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 21 | `/dashboard/company/tasks` | Company | 44 / 766 | 67% (2641 KB unzipped) | 15 (47) | 4 | 8.6 s | 1.6 s / 8.0 s | 2168 ms | 0.001 | 744 / 34.2 MB | 14 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, M-61, L-58, M-65 |
| 22 | `/dashboard/connect-discord` | Student | 39 / 698 | 66% (2375 KB unzipped) | 4 (4) | 2 | 7.4 s | 1.6 s / 7.7 s | 1978 ms | 0.001 | 493 / 36.8 MB | 13 | images 293 KB | H-39, H-40, H-36, M-64 |
| 23 | `/dashboard/courses` | Admin | 39 / 700 | 66% (2379 KB unzipped) | 5 (3) | 2 | 7.4 s | 1.6 s / 7.6 s | 1806 ms | 0.002 | 512 / 38.1 MB | 13 | page requests start only after `user/info` returns; images 293 KB; third-party: opensheet.elk.sh | H-39, H-40, L-66, H-36, M-64 |
| 24 | `/dashboard/district` | District Lead | 41 / 725 | 65% (2462 KB unzipped) | 9 (5) | 2 | 7.9 s | 1.6 s / 7.9 s | 2113 ms | 0.12 | 648 / 31.9 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 25 | `/dashboard/edit-ig` | Admin | 42 / 761 | 69% (2642 KB unzipped) | 5 (39) | 2 | 8.1 s | 1.6 s / 7.8 s | 2147 ms | 0.001 | 611 / 37.2 MB | 27 | page requests start only after `user/info` returns; images 437 KB; typing 6 letters in search: 0 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-60, M-67 |
| 26 | `/dashboard/edit-ig/[id]` | IG Lead | 42 / 761 | 67% (2643 KB unzipped) | 8 (41) | 3 | 8.4 s | 1.6 s / 7.9 s | 2203 ms | 0.001 | 535 / 43.1 MB | 15 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, M-60, M-61 |
| 27 | `/dashboard/events` | Student | 41 / 744 | 66% (2547 KB unzipped) | 7 (7) | 2 | 7.9 s | 1.6 s / 7.2 s | 1572 ms | 0.014 | 502 / 41.2 MB | 13 | page requests start only after `user/info` returns; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 28 | `/dashboard/events/[id]` | Student | 41 / 742 | 67% (2544 KB unzipped) | 5 (9) | 2 | 7.6 s | 1.6 s / 7.1 s | 1326 ms | 0.001 | 597 / 38.2 MB | 13 | page requests start only after `user/info` returns | H-39, H-40, H-36, M-64, M-61 |
| 29 | `/dashboard/interest-groups` | Student | 38 / 694 | 65% (2362 KB unzipped) | 5 (41) | 2 | 7.7 s | 1.7 s / 7.0 s | 1449 ms | 0.001 | 562 / 35.7 MB | 13 | page requests start only after `user/info` returns; typing 6 letters in search: 0 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-60 |
| 30 | `/dashboard/interest-groups/[id]` | Student | 38 / 694 | 65% (2362 KB unzipped) | 5 (10) | 2 | 7.6 s | 1.6 s / 7.1 s | 1596 ms | 0 | 534 / 31.1 MB | 17 | page requests start only after `user/info` returns | H-39, H-40, H-36, M-64, M-60 |
| 31 | `/dashboard/intern` | Intern | 40 / 717 | 65% (2462 KB unzipped) | 10 (6) | 2 | 7.8 s | 1.6 s / 7.7 s | 2003 ms | 0.058 | 653 / 38.9 MB | 29 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, M-67 |
| 32 | `/dashboard/intern/leaderboard` | Intern | 40 / 715 | 65% (2452 KB unzipped) | 7 (11) | 2 | 7.6 s | 1.6 s / 7.6 s | 2040 ms | 0.001 | 722 / 38.8 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 33 | `/dashboard/intern/leave` | Intern | 40 / 717 | 65% (2459 KB unzipped) | 6 (3) | 2 | 7.5 s | 1.6 s / 7.6 s | 1964 ms | 0.001 | 555 / 38.3 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 34 | `/dashboard/intern/minutes` | Intern | 40 / 718 | 66% (2461 KB unzipped) | 5 (3) | 2 | 7.7 s | 1.6 s / 7.8 s | 2019 ms | 0.001 | 475 / 38.9 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 0 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 35 | `/dashboard/intern/quest-log` | Intern | 40 / 712 | 66% (2441 KB unzipped) | 7 (4) | 2 | 7.6 s | 1.6 s / 7.6 s | 2002 ms | 0.001 | 482 / 38.5 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 0 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 36 | `/dashboard/intern/tasks` | Intern | 40 / 715 | 66% (2455 KB unzipped) | 5 (3) | 2 | 7.7 s | 1.6 s / 7.8 s | 2021 ms | 0.001 | 467 / 38.6 MB | 13 | page requests start only after `user/info` returns; images 315 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 37 | `/dashboard/intern/timesheet` | Intern | 40 / 716 | 65% (2457 KB unzipped) | 9 (5) | 2 | 7.7 s | 1.6 s / 7.7 s | 2115 ms | 0.001 | 600 / 40.5 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 38 | `/dashboard/intern/weekly-review` | Intern | 40 / 713 | 65% (2443 KB unzipped) | 6 (3) | 2 | 7.5 s | 1.6 s / 7.6 s | 2033 ms | 0.001 | 550 / 39.2 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 39 | `/dashboard/jobs` | Student | 41 / 740 | 67% (2550 KB unzipped) | 7 (49) | 2 | 8.2 s | 1.6 s / 8.0 s | 2108 ms | 0.002 | 479 / 35.1 MB | 11 | page requests start only after `user/info` returns; images 449 KB; typing 6 letters in search: 2 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-61 |
| 40 | `/dashboard/leaderboard` | Student | 39 / 700 | 65% (2380 KB unzipped) | 5 (5) | 2 | 7.4 s | 1.6 s / 7.5 s | 1820 ms | 0.001 | 484 / 37.1 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, H-37 |
| 41 | `/dashboard/learning-circle` | Student | 41 / 743 | 65% (2553 KB unzipped) | 8 (46) | 2 | 8.0 s | 1.6 s / 7.7 s | 1991 ms | 0.002 | 912 / 34.6 MB | 37 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-60, M-67 |
| 42 | `/dashboard/learning-circle/[id]` | Student | 41 / 743 | 67% (2550 KB unzipped) | 12 (10) | 4 | 11.1 s | 1.6 s / 7.8 s | 1924 ms | 0.001 | 442 / 42.8 MB | 13 | page requests start only after `user/info` returns; duplicate calls: api/v1/dashboard/learningcircle/info/ef9baa6d-7f6a-481b-8d63-231a7cc6cf80/ ×3; api/v1/dashboard/learningcircle/meeting/list/ef9baa6d-7f6a-481b-8d63-231a7cc6cf80/ ×3; 6 call(s) failed with 5xx; 2 call(s) repeated after load: api/v1/dashboard/learningcircle/info/ef9baa6d-7f6a-481b-8d63-231a7cc6cf80/, api/v1/dashboard/learningcircle/meeting/list/ef9baa6d-7f6a-481b-8d63-231a7cc6cf80/; images 293 KB | H-39, H-40, H-36, M-64, M-68 |
| 43 | `/dashboard/learning-circle/[id]/meeting/[meet_id]` | Student | 41 / 743 | 66% (2551 KB unzipped) | 12 (10) | 6 | 11.2 s | 1.6 s / 7.6 s | 1780 ms | 0.001 | 550 / 40.3 MB | 15 | page requests start only after `user/info` returns; duplicate calls: api/v1/dashboard/learningcircle/info/ef9baa6d-7f6a-481b-8d63-231a7cc6cf80/ ×3; api/v1/dashboard/learningcircle/meeting/list/ef9baa6d-7f6a-481b-8d63-231a7cc6cf80/ ×3; 6 call(s) failed with 5xx; 2 call(s) repeated after load: api/v1/dashboard/learningcircle/info/ef9baa6d-7f6a-481b-8d63-231a7cc6cf80/, api/v1/dashboard/learningcircle/meeting/list/ef9baa6d-7f6a-481b-8d63-231a7cc6cf80/; images 293 KB | H-39, H-40, H-36, M-64, M-68 |
| 44 | `/dashboard/learning-circle/invite/[link_id]` | Student | 41 / 743 | 67% (2550 KB unzipped) | 7 (6) | 4 | 10.9 s | 1.6 s / 7.6 s | 1800 ms | 0.001 | 447 / 38.6 MB | 13 | page requests start only after `user/info` returns; duplicate calls: api/v1/dashboard/learningcircle/invite/status/03d235b0-914e-44c2-aab2-cec0e1ae9212/ ×3; 3 call(s) failed with 5xx; 1 call(s) repeated after load: api/v1/dashboard/learningcircle/invite/status/03d235b0-914e-44c2-aab2-cec0e1ae9212/; images 293 KB | H-39, H-40, H-36, M-64, M-68 |
| 45 | `/dashboard/learning-circle/invites` | Student | 41 / 743 | 67% (2549 KB unzipped) | 6 (5) | 2 | 7.7 s | 1.6 s / 7.8 s | 1850 ms | 0.051 | 450 / 40.4 MB | 15 | page requests start only after `user/info` returns; images 315 KB | H-39, H-40, H-36, M-64 |
| 46 | `/dashboard/manage-events` | Campus Lead | 42 / 744 | 66% (2547 KB unzipped) | 19 (24) | 3 | 8.4 s | 1.6 s / 8.0 s | 2157 ms | 0.007 | 533 / 35.9 MB | 11 | page requests start only after `user/info` returns; duplicate calls: api/v1/dashboard/events/meta/event-type-scope/ ×2; images 298 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, L-65, H-36, M-64, M-61 |
| 47 | `/dashboard/manage-events/[id]` | Campus Lead | 42 / 744 | 67% (2548 KB unzipped) | 6 (4) | 2 | 7.7 s | 1.6 s / 7.8 s | 1937 ms | 0.001 | 460 / 40.8 MB | 11 | page requests start only after `user/info` returns; duplicate calls: api/v1/dashboard/user/info/ ×2; images 293 KB | H-39, H-40, L-65, H-36, M-64, M-61 |
| 48 | `/dashboard/management` | Admin | 39 / 696 | 65% (2384 KB unzipped) | 4 (2) | 2 | 7.4 s | 1.6 s / 7.4 s | 1911 ms | 0.001 | 649 / 37.9 MB | 34 | images 293 KB | H-39, H-40, H-36, M-64, M-67 |
| 49 | `/dashboard/management/channels` | Admin | 40 / 701 | 65% (2378 KB unzipped) | 5 (6) | 2 | 7.4 s | 1.6 s / 7.4 s | 1994 ms | 0.001 | 697 / 39.0 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-61 |
| 50 | `/dashboard/management/college-levels` | Admin | 40 / 698 | 65% (2369 KB unzipped) | 5 (10) | 2 | 7.5 s | 1.6 s / 7.5 s | 1917 ms | 0.001 | 825 / 38.9 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-61, M-66 |
| 51 | `/dashboard/management/community` | Admin | 39 / 696 | 65% (2376 KB unzipped) | 4 (2) | 2 | 7.3 s | 1.6 s / 7.5 s | 1824 ms | 0.001 | 567 / 37.6 MB | 28 | images 293 KB | H-39, H-40, H-36, M-64, M-67 |
| 52 | `/dashboard/management/discord-moderation` | Discord Mod | 41 / 709 | 65% (2400 KB unzipped) | 7 (4) | 4 | 11.0 s | 1.6 s / 7.7 s | 2012 ms | 0.001 | 474 / 37.5 MB | 13 | page requests start only after `user/info` returns; duplicate calls: api/v1/dashboard/discord-moderator/leaderboard/?option=peer&perPage=10&pageIndex=1 ×3; 3 call(s) failed with 5xx; 1 call(s) repeated after load: api/v1/dashboard/discord-moderator/leaderboard/?option=peer&perPage=10&pageIndex=1; images 293 KB | H-39, H-40, H-36, M-64, M-68 |
| 53 | `/dashboard/management/dynamic-type` | Admin | 40 / 702 | 65% (2386 KB unzipped) | 7 (4) | 4 | 11.1 s | 1.6 s / 7.8 s | 2116 ms | 0.001 | 554 / 39.2 MB | 13 | page requests start only after `user/info` returns; duplicate calls: api/v1/dashboard/dynamic-management/dynamic-role/ ×3; 3 call(s) failed with 5xx; 1 call(s) repeated after load: api/v1/dashboard/dynamic-management/dynamic-role/; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-68 |
| 54 | `/dashboard/management/error-log` | Tech Team | 41 / 704 | 65% (2381 KB unzipped) | 5 (3) | 2 | 7.5 s | 1.6 s / 7.5 s | 1932 ms | 0.001 | 567 / 37.6 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 0 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 55 | `/dashboard/management/homepage` | Associate | 39 / 696 | 66% (2367 KB unzipped) | 4 (2) | 2 | 7.4 s | 1.6 s / 7.5 s | 1897 ms | 0.001 | 482 / 37.0 MB | 20 | images 293 KB | H-39, H-40, H-36, M-64, M-67 |
| 56 | `/dashboard/management/homepage/career-labs` | Admin | 40 / 703 | 64% (2389 KB unzipped) | 5 (20) | 2 | 7.9 s | 1.6 s / 7.8 s | 2337 ms | 0.001 | 1201 / 42.6 MB | 14 | page requests start only after `user/info` returns; images 437 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-61 |
| 57 | `/dashboard/management/karma-voucher` | Admin | 40 / 706 | 64% (2395 KB unzipped) | 5 (17) | 2 | 7.9 s | 1.6 s / 7.8 s | 2257 ms | 0.001 | 1058 / 41.9 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 58 | `/dashboard/management/manage-achievements` | Admin | 39 / 696 | 66% (2365 KB unzipped) | 4 (2) | 2 | 7.6 s | 1.6 s / 7.6 s | 2067 ms | 0.001 | 577 / 37.9 MB | 28 | images 293 KB | H-39, H-40, H-36, M-64, M-67 |
| 59 | `/dashboard/management/manage-achievements/bulk-issue` | Admin | 39 / 696 | 65% (2365 KB unzipped) | 5 (110) | 2 | 8.1 s | 1.6 s / 7.5 s | 1917 ms | 0.001 | 539 / 38.2 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 0 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-65 |
| 60 | `/dashboard/management/manage-achievements/issue` | Admin | 39 / 696 | 65% (2365 KB unzipped) | 4 (2) | 2 | 7.5 s | 1.6 s / 7.6 s | 1960 ms | 0.001 | 507 / 30.8 MB | 11 | images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 61 | `/dashboard/management/manage-achievements/list` | Admin | 39 / 696 | 65% (2365 KB unzipped) | 6 (116) | 2 | 8.6 s | 1.6 s / 7.7 s | 3072 ms | 0.001 | 5442 / 52.3 MB | 11 | page requests start only after `user/info` returns; images 437 KB; typing 6 letters in search: 0 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-65 |
| 62 | `/dashboard/management/manage-achievements/logs` | Admin | 40 / 699 | 65% (2378 KB unzipped) | 5 (110) | 2 | 8.3 s | 1.6 s / 7.8 s | 2526 ms | 0.001 | 3813 / 31.8 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 0 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-65 |
| 63 | `/dashboard/management/manage-achievements/rules` | Admin | 39 / 696 | 65% (2365 KB unzipped) | 7 (156) | 2 | 9.0 s | 1.6 s / 7.6 s | 2274 ms | 0.001 | 1430 / 33.6 MB | 11 | page requests start only after `user/info` returns; images 437 KB; typing 6 letters in search: 0 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-65, M-60 |
| 64 | `/dashboard/management/manage-achievements/simulate` | Admin | 39 / 696 | 66% (2365 KB unzipped) | 4 (2) | 2 | 7.5 s | 1.6 s / 7.6 s | 1981 ms | 0.001 | 509 / 37.0 MB | 11 | images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 65 | `/dashboard/management/manage-companies` | Admin | 47 / 788 | 67% (2676 KB unzipped) | 5 (16) | 3 | 9.2 s | 1.6 s / 7.7 s | 2355 ms | 0.001 | 1198 / 39.1 MB | 16 | redirected to `/dashboard/management/role-verification?`; page requests start only after `user/info` returns; images 437 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-61 |
| 66 | `/dashboard/management/manage-interest-groups` | Admin | 43 / 763 | 65% (2646 KB unzipped) | 6 (29) | 2 | 8.3 s | 1.6 s / 8.2 s | 2356 ms | 0.001 | 1006 / 39.0 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-60, M-61 |
| 67 | `/dashboard/management/manage-interns` | Intern Lead | 45 / 753 | 66% (2601 KB unzipped) | 8 (24) | 2 | 8.2 s | 1.6 s / 7.9 s | 2241 ms | 0.007 | 942 / 33.5 MB | 26 | page requests start only after `user/info` returns; images 437 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, L-58, M-67 |
| 68 | `/dashboard/management/manage-interns/intern-report` | Intern Lead | 41 / 717 | 65% (2458 KB unzipped) | 5 (11) | 2 | 7.7 s | 1.6 s / 7.6 s | 2065 ms | 0.001 | 793 / 30.9 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 6 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-61, M-69 |
| 69 | `/dashboard/management/manage-interns/intern-report/individual` | Intern Lead | 41 / 715 | 66% (2452 KB unzipped) | 5 (27) | 2 | 7.6 s | 1.6 s / 7.5 s | 1999 ms | 0.078 | 1339 / 38.5 MB | 14 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, M-61 |
| 70 | `/dashboard/management/manage-interns/intern-report/team` | Intern Lead | 41 / 715 | 66% (2450 KB unzipped) | 5 (27) | 2 | 7.8 s | 1.6 s / 7.7 s | 1953 ms | 0.021 | 553 / 38.4 MB | 17 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, M-61 |
| 71 | `/dashboard/management/manage-interns/leave-reviews` | Intern Lead | 41 / 717 | 66% (2460 KB unzipped) | 5 (9) | 2 | 7.8 s | 1.6 s / 7.8 s | 2099 ms | 0.001 | 794 / 40.2 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 6 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-69 |
| 72 | `/dashboard/management/manage-interns/minutes` | Intern Lead | 41 / 718 | 66% (2458 KB unzipped) | 7 (20) | 2 | 7.8 s | 1.6 s / 7.7 s | 2093 ms | 0.001 | 1038 / 39.1 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 73 | `/dashboard/management/manage-interns/tasks` | Intern Lead | 42 / 722 | 65% (2480 KB unzipped) | 8 (34) | 2 | 8.3 s | 1.6 s / 8.1 s | 2490 ms | 0.001 | 1158 / 34.8 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, L-58 |
| 74 | `/dashboard/management/manage-interns/timesheet-reviews` | Intern Lead | 41 / 718 | 66% (2469 KB unzipped) | 5 (9) | 2 | 7.8 s | 1.6 s / 7.8 s | 2165 ms | 0.001 | 750 / 41.2 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 6 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-61, M-69 |
| 75 | `/dashboard/management/manage-locations` | Admin | 40 / 703 | 64% (2389 KB unzipped) | 5 (8) | 2 | 7.8 s | 1.6 s / 7.8 s | 2165 ms | 0.001 | 718 / 41.2 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 76 | `/dashboard/management/manage-roles` | Admin | 43 / 742 | 66% (2550 KB unzipped) | 5 (9) | 2 | 8.0 s | 1.6 s / 8.1 s | 2268 ms | 0.001 | 1226 / 36.2 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-61 |
| 77 | `/dashboard/management/manage-users` | Admin | 41 / 709 | 65% (2415 KB unzipped) | 5 (12) | 2 | 7.9 s | 1.6 s / 7.8 s | 2297 ms | 0.001 | 1075 / 33.4 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 78 | `/dashboard/management/mentor-verification` | Admin | 47 / 788 | 67% (2676 KB unzipped) | 8 (16) | 3 | 8.9 s | 1.6 s / 7.6 s | 2194 ms | 0.002 | 975 / 37.1 MB | 16 | redirected to `/dashboard/management/role-verification?`; page requests start only after `user/info` returns; images 437 KB; typing 6 letters in search: 18 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-69 |
| 79 | `/dashboard/management/notifications` | Admin | 39 / 696 | 65% (2365 KB unzipped) | 5 (20) | 2 | 7.5 s | 1.6 s / 7.5 s | 1883 ms | 0.004 | 1144 / 38.8 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, M-65 |
| 80 | `/dashboard/management/organizations` | Admin | 40 / 701 | 66% (2393 KB unzipped) | 4 (2) | 2 | 7.4 s | 1.6 s / 7.5 s | 1880 ms | 0.001 | 579 / 37.7 MB | 29 | images 293 KB | H-39, H-40, H-36, M-64, M-67 |
| 81 | `/dashboard/management/organizations/affiliation` | Admin | 41 / 717 | 65% (2441 KB unzipped) | 5 (9) | 2 | 8.0 s | 1.6 s / 8.1 s | 2297 ms | 0.001 | 994 / 36.2 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-61 |
| 82 | `/dashboard/management/organizations/departments` | Admin | 41 / 717 | 65% (2441 KB unzipped) | 5 (4) | 2 | 7.8 s | 1.6 s / 7.9 s | 2034 ms | 0.001 | 724 / 42.3 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, L-58 |
| 83 | `/dashboard/management/organizations/list` | Admin | 41 / 717 | 65% (2441 KB unzipped) | 5 (3) | 2 | 7.8 s | 1.6 s / 7.9 s | 2105 ms | 0.001 | 608 / 44.1 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, L-58 |
| 84 | `/dashboard/management/organizations/transfer` | Admin | 41 / 717 | 66% (2441 KB unzipped) | 4 (2) | 2 | 7.6 s | 1.6 s / 7.7 s | 1941 ms | 0.001 | 532 / 38.7 MB | 13 | images 293 KB | H-39, H-40, H-36, M-64 |
| 85 | `/dashboard/management/organizations/verify` | Admin | 47 / 788 | 67% (2676 KB unzipped) | 5 (6) | 3 | 9.0 s | 1.6 s / 7.7 s | 2427 ms | 0.001 | 836 / 36.4 MB | 16 | redirected to `/dashboard/management/role-verification?`; page requests start only after `user/info` returns; images 437 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 86 | `/dashboard/management/role-verification` | Admin | 43 / 742 | 65% (2521 KB unzipped) | 8 (16) | 2 | 7.8 s | 1.6 s / 7.8 s | 2137 ms | 0.002 | 970 / 36.4 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 18 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-69 |
| 87 | `/dashboard/management/session-verification` | Admin | 40 / 706 | 64% (2401 KB unzipped) | 8 (35) | 2 | 8.1 s | 1.6 s / 7.9 s | 2378 ms | 0.002 | 870 / 33.9 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 24 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-61, M-69 |
| 88 | `/dashboard/management/system` | Admin | 39 / 696 | 65% (2373 KB unzipped) | 4 (2) | 2 | 7.3 s | 1.6 s / 7.4 s | 1801 ms | 0.001 | 556 / 37.5 MB | 26 | images 293 KB | H-39, H-40, H-36, M-64, M-67 |
| 89 | `/dashboard/management/system/features` | Admin | 40 / 698 | 65% (2371 KB unzipped) | 5 (3) | 2 | 7.5 s | 1.6 s / 7.6 s | 1961 ms | 0.001 | 528 / 37.2 MB | 17 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 90 | `/dashboard/management/tasks` | Admin | 39 / 696 | 65% (2376 KB unzipped) | 4 (2) | 2 | 7.2 s | 1.6 s / 7.4 s | 1748 ms | 0.001 | 574 / 37.4 MB | 28 | images 293 KB | H-39, H-40, H-36, M-64, M-67 |
| 91 | `/dashboard/management/tasks/bulk-import` | Admin | 41 / 715 | 66% (2435 KB unzipped) | 4 (2) | 2 | 7.8 s | 1.6 s / 7.9 s | 2104 ms | 0.001 | 517 / 35.4 MB | 11 | images 293 KB | H-39, H-40, H-36, M-64 |
| 92 | `/dashboard/management/tasks/create` | Admin | 41 / 715 | 64% (2435 KB unzipped) | 11 (78) | 2 | 8.6 s | 1.6 s / 8.1 s | 3394 ms | 0.009 | 1114 / 44.9 MB | 13 | page requests start only after `user/info` returns; images 437 KB | H-39, H-40, H-36, M-64, M-65 |
| 93 | `/dashboard/management/tasks/list` | Admin | 41 / 715 | 65% (2435 KB unzipped) | 5 (20) | 2 | 8.0 s | 1.6 s / 7.9 s | 2287 ms | 0.001 | 1381 / 33.7 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 94 | `/dashboard/management/tasks/task-type` | Admin | 41 / 715 | 65% (2435 KB unzipped) | 5 (12) | 2 | 7.9 s | 1.6 s / 7.8 s | 2129 ms | 0.001 | 1010 / 44.2 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, L-58 |
| 95 | `/dashboard/management/tasks/task-verification` | Admin | 41 / 715 | 65% (2435 KB unzipped) | 5 (3) | 2 | 7.7 s | 1.6 s / 7.8 s | 2018 ms | 0.001 | 620 / 43.6 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 96 | `/dashboard/management/user-management` | Admin | 40 / 701 | 66% (2390 KB unzipped) | 4 (2) | 2 | 7.6 s | 1.6 s / 7.6 s | 2059 ms | 0.001 | 553 / 37.6 MB | 27 | images 293 KB | H-39, H-40, H-36, M-64, M-67 |
| 97 | `/dashboard/management/verification` | Admin | 39 / 696 | 66% (2371 KB unzipped) | 4 (2) | 2 | 7.5 s | 1.6 s / 7.6 s | 2023 ms | 0.001 | 542 / 37.5 MB | 24 | images 293 KB | H-39, H-40, H-36, M-64, M-67 |
| 98 | `/dashboard/management/weekly-twitches` | Admin | 43 / 736 | 65% (2529 KB unzipped) | 6 (46) | 2 | 8.2 s | 1.6 s / 8.0 s | 2220 ms | 0.001 | 879 / 38.0 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-60 |
| 99 | `/dashboard/mentor` | Admin | 45 / 832 | 68% (2907 KB unzipped) | 9 (45) | 2 | 9.0 s | 1.8 s / 9.0 s | 2464 ms | 0.006 | 851 / 38.5 MB | 49 | redirected to `/dashboard`; page requests start only after `user/info` returns; images 437 KB | H-39, H-40, H-36, M-64, H-37, M-60, M-67 |
| 100 | `/dashboard/mentor/mentees` | Mentor | 39 / 700 | 65% (2381 KB unzipped) | 6 (4) | 2 | 7.5 s | 1.6 s / 7.5 s | 1929 ms | 0.006 | 500 / 37.9 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 0 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 101 | `/dashboard/mentor/opportunities` | Admin | 45 / 832 | 68% (2907 KB unzipped) | 9 (45) | 2 | 8.7 s | 1.7 s / 8.9 s | 2219 ms | 0.007 | 851 / 37.2 MB | 49 | redirected to `/dashboard`; page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, H-37, M-60, M-67 |
| 102 | `/dashboard/mentor/sessions` | Mentor | 40 / 713 | 65% (2439 KB unzipped) | 8 (4) | 2 | 8.0 s | 1.6 s / 8.1 s | 2285 ms | 0.003 | 507 / 34.9 MB | 13 | page requests start only after `user/info` returns; images 305 KB | H-39, H-40, H-36, M-64 |
| 103 | `/dashboard/mentor/task-requests` | Mentor | 39 / 701 | 65% (2386 KB unzipped) | 12 (24) | 2 | 7.8 s | 1.6 s / 7.7 s | 2051 ms | 0.002 | 561 / 39.5 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64, L-58 |
| 104 | `/dashboard/mujourney` | Student | 40 / 703 | 65% (2390 KB unzipped) | 6 (24) | 2 | 7.7 s | 1.6 s / 7.1 s | 1727 ms | 0 | 1008 / 46.3 MB | 15 | page requests start only after `user/info` returns; duplicate calls: api/v1/dashboard/profile/user-profile/ ×2; typing 6 letters in search: 0 API call(s), 0 server round trip(s) | H-39, H-40, L-65, H-36, M-64 |
| 105 | `/dashboard/mujourney/[muid]` | Student | 40 / 703 | 65% (2390 KB unzipped) | 5 (15) | 2 | 7.6 s | 1.6 s / 7.1 s | 1497 ms | 0.001 | 973 / 36.1 MB | 15 | page requests start only after `user/info` returns | H-39, H-40, H-36, M-64, L-56 |
| 106 | `/dashboard/muverse` | Comic Admin | 39 / 696 | 66% (2364 KB unzipped) | 4 (2) | 2 | 7.4 s | 1.6 s / 7.6 s | 1909 ms | 0.001 | 444 / 36.6 MB | 13 | images 293 KB | H-39, H-40, H-36, M-64 |
| 107 | `/dashboard/profile` | Student | 44 / 780 | 64% (2693 KB unzipped) | 12 (91) | 3 | 9.3 s | 1.6 s / 8.9 s | 2359 ms | 0.001 | 1206 / 42.8 MB | 14 | page requests start only after `user/info` returns; images 571 KB; third-party: quickchart.io | H-39, H-40, H-36, M-64, M-65, L-56, M-60 |
| 108 | `/dashboard/projects` | Student | 40 / 715 | 65% (2432 KB unzipped) | 5 (16) | 2 | 7.8 s | 1.6 s / 7.7 s | 1975 ms | 0.004 | 834 / 40.8 MB | 14 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 1 server round trip(s) | H-39, H-40, H-36, M-64 |
| 109 | `/dashboard/reports` | Student | 39 / 697 | 65% (2366 KB unzipped) | 4 (4) | 2 | 7.5 s | 1.6 s / 7.6 s | 1941 ms | 0.001 | 477 / 36.8 MB | 13 | images 293 KB | H-39, H-40, H-36, M-64 |
| 110 | `/dashboard/search` | Admin | 78 / 1402 | 67% (4775 KB unzipped) | 4 (2) | 1 | 7.4 s | 1.6 s / 2.0 s | 1348 ms | 0 | 459 / 72.0 MB | 5 | redirected to `/dashboard/search/students`; 4 call(s) repeated after load: api/v1/dashboard/profile/user-level-feed/, api/v1/dashboard/profile/user-profile/, api/v1/dashboard/user/info/; images 294 KB; typing 6 letters in search: 1 API call(s), 6 server round trip(s) | H-39, H-40, H-36, M-64, M-69 |
| 111 | `/dashboard/search/campuses` | Student | 40 / 707 | 64% (2414 KB unzipped) | 6 (5) | 2 | 7.9 s | 1.6 s / 7.2 s | 1749 ms | 0.001 | 488 / 40.0 MB | 18 | page requests start only after `user/info` returns; typing 6 letters in search: 2 API call(s), 6 server round trip(s) | H-39, H-40, H-36, M-64, L-58, M-69 |
| 112 | `/dashboard/search/mentors` | Student | 40 / 707 | 66% (2414 KB unzipped) | 5 (5) | 2 | 7.6 s | 1.6 s / 7.0 s | 1527 ms | 0.001 | 462 / 33.1 MB | 18 | page requests start only after `user/info` returns; typing 6 letters in search: 1 API call(s), 6 server round trip(s) | H-39, H-40, H-36, M-64, M-69 |
| 113 | `/dashboard/search/students` | Student | 40 / 707 | 65% (2414 KB unzipped) | 5 (17) | 2 | 7.9 s | 1.6 s / 7.2 s | 1755 ms | 0 | 1017 / 40.9 MB | 42 | page requests start only after `user/info` returns; typing 6 letters in search: 1 API call(s), 6 server round trip(s) | H-39, H-40, H-36, M-64, M-67, M-69 |
| 114 | `/dashboard/sessions` | Mentor | 39 / 708 | 65% (2416 KB unzipped) | 7 (5) | 2 | 7.5 s | 1.6 s / 7.6 s | 1965 ms | 0.002 | 511 / 39.4 MB | 11 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 115 | `/dashboard/settings` | Student | 38 / 694 | 65% (2368 KB unzipped) | 4 (4) | 2 | 7.4 s | 1.6 s / 7.5 s | 1874 ms | 0.001 | 472 / 37.0 MB | 20 | images 293 KB | H-39, H-40, H-36, M-64, M-67 |
| 116 | `/dashboard/settings/account` | Student | 39 / 697 | 65% (2370 KB unzipped) | 4 (4) | 2 | 7.5 s | 1.6 s / 7.6 s | 2010 ms | 0.001 | 468 / 37.3 MB | 13 | images 293 KB | H-39, H-40, H-36, M-64 |
| 117 | `/dashboard/settings/organization` | Campus Lead | 39 / 697 | 65% (2369 KB unzipped) | 6 (8) | 2 | 7.5 s | 1.6 s / 7.5 s | 1966 ms | 0.001 | 477 / 37.4 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, L-58 |
| 118 | `/dashboard/talent-pool` | Company | 41 / 742 | 66% (2560 KB unzipped) | 10 (160) | 3 | 9.4 s | 1.6 s / 8.0 s | 2473 ms | 0.004 | 1390 / 40.7 MB | 23 | page requests start only after `user/info` returns; images 437 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-60, M-65, M-63, M-67 |
| 119 | `/dashboard/url-shortener` | Admin | 39 / 699 | 64% (2373 KB unzipped) | 5 (22) | 2 | 7.8 s | 1.6 s / 7.8 s | 2206 ms | 0.001 | 1199 / 40.9 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 120 | `/dashboard/url-shortener/[id]/analytics` | Admin | 44 / 735 | 63% (2493 KB unzipped) | 5 (4) | 2 | 7.7 s | 1.6 s / 7.8 s | 2245 ms | 0.043 | 693 / 43.3 MB | 13 | page requests start only after `user/info` returns; images 293 KB | H-39, H-40, H-36, M-64 |
| 121 | `/dashboard/weekly-twitches` | Student | 42 / 735 | 66% (2526 KB unzipped) | 5 (12) | 2 | 7.9 s | 1.6 s / 7.9 s | 1984 ms | 0.001 | 684 / 32.6 MB | 11 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 6 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64, M-69 |
| 122 | `/dashboard/zonal` | Zonal Lead | 41 / 726 | 65% (2463 KB unzipped) | 9 (5) | 2 | 7.9 s | 1.6 s / 7.8 s | 2064 ms | 0.098 | 640 / 31.9 MB | 13 | page requests start only after `user/info` returns; images 293 KB; typing 6 letters in search: 1 API call(s), 0 server round trip(s) | H-39, H-40, H-36, M-64 |
| 123 | `/forgot-password` | Anonymous | 22 / 357 | 68% (1211 KB unzipped) | 0 (0) | 0 | — | 1.5 s / 1.5 s | 447 ms | 0 | 98 / 12.7 MB | 4 | — | — |
| 124 | `/login` | Anonymous | 24 / 375 | 68% (1257 KB unzipped) | 0 (0) | 0 | — | 1.6 s / 1.6 s | 413 ms | 0 | 120 / 13.3 MB | 10 | — | — |
| 125 | `/onboarding/interests` | Admin | 72 / 1262 | 81% (4258 KB unzipped) | 1 (0) | 1 | 4.4 s | 1.6 s / 10.8 s | 1979 ms | 0.01 | 663 / 41.6 MB | 33 | redirected to `/dashboard/management`; 3 call(s) repeated after load: api/v1/dashboard/profile/user-level-feed/, api/v1/dashboard/profile/user-profile/, api/v1/notification/unread-count/; images 443 KB | H-40, M-67 |
| 126 | `/onboarding/organization` | Student | 52 / 884 | 87% (3009 KB unzipped) | 3 (5) | 1 | 4.0 s | 1.6 s / 1.6 s | 346 ms | 0 | 126 / 12.5 MB | 1 | — | L-58 |
| 127 | `/profile/[muid]` | Student | 42 / 756 | 65% (2606 KB unzipped) | 11 (62) | 2 | 8.6 s | 1.6 s / 8.8 s | 2047 ms | 0.001 | 1190 / 44.3 MB | 11 | images 427 KB | H-40, H-36, M-64, M-65, L-56, M-60 |
| 128 | `/register` | Anonymous | 24 / 385 | 67% (1287 KB unzipped) | 4 (18) | 1 | 4.6 s | 1.6 s / 1.6 s | 443 ms | 0 | 130 / 11.8 MB | 4 | — | L-58, M-65 |
| 129 | `/reset-password` | Anonymous | 24 / 375 | 69% (1258 KB unzipped) | 0 (0) | 0 | — | 1.6 s / 1.6 s | 590 ms | 0 | 94 / 12.9 MB | 8 | — | — |
