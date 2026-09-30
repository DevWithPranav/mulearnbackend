# muLearn Dashboard + Backend — Production Audit Report

| Item | Value |
|---|---|
| Date | 2026-09-30 |
| Dashboard repo / branch | `DevWithPranav/mulearn-dashboard` @ `dev` (`50c7052`, 2026-09-25) |
| Backend repo / branch | `DevWithPranav/mulearnbackend` @ `pranav-dev` (`ad02b2a`, 2026-09-16) |
| Backend comparison base | `dev` (`c4a8536`). `pranav-dev` is 194 commits ahead: 137 files, +11,525 / −3,752 lines |
| Scope | Full regression + production audit, with focus on the dashboard ⇄ backend integration |

---

## How this audit was done

1. **Backend route map.** Django was loaded with dummy settings and every URL pattern was listed through the real URL resolver: **733 URL patterns / 1,123 route + method pairs**.
2. **Permission scan.** For every view and method, the scan recorded `permission_classes`, `authentication_classes` and any `role_required` / `RoleRequired` decorator. Results were then checked by hand, because many views check roles inside the method body.
3. **Frontend endpoint map.** All **568 endpoint definitions** in `src/api/endpoints.ts` were run with placeholder values and resolved against the backend resolver.
4. **Call-site check.** All **673 API call sites** (`apiClient` / `publicApiClient` / `serverApiClient` / `authedFetch`) were parsed. The HTTP method and URL of each call were checked against the resolved backend view. Result: **603 OK**, **11 no backend route**, **2 wrong HTTP method**, **57 built from variables** (checked by hand for the flows below).
5. **Flow tracing.** Every important flow was read end to end: UI → API function → URL → backend view → auth/role → serializer → DB → response → UI handling.
6. **Branch diff.** The `dev..pranav-dev` diff, the commit log and the backend route list of both branches were compared.
7. **Dashboard checks run:** `typecheck` passes. `lint` passes (50 warnings). **Unit tests fail: 14 failed / 253 passed, 3 failing files** (see H-17).

**Limits.** The backend was not run against a real MySQL database. The external auth service (`AUTH_DOMAIN`, which issues the JWTs) is not in either repo, so any claim about what it puts in the token is marked "needs confirmation". Infra (Netlify, reverse proxy, nginx limits) is not in the repos. Where a finding depends on infra, the report says so.

---

## 1. Executive summary

The two branches **are not ready for production together**.

Most of the day-to-day wiring is correct: about 90% of the dashboard's API calls (603 of 673) reach an existing backend route with the right HTTP method, and the response envelope (`hasError / statusCode / message / response`) is handled the same way everywhere. Recent work added good things too: company-owner job approval, event publish policy, atomic learning-circle lead transfer, and URL-scheme checks on events.

But the audit found problems in four areas that block a safe release:

1. **Open admin actions on the backend (Security).** Some endpoints that change important data have no login check or no role check:
   - Anyone on the internet can merge and **delete any organization** (`/organisation/transfer/`) and can **replace any user's profile picture**.
   - Any logged-in learner can **create, grant and revoke achievements**, and can **approve organization requests**.
   - The Launchpad admin API trusts an email address typed into the request body.
2. **Broken cross-repo contracts.** Several flows look finished in the UI but cannot work against this backend:
   - The admin announcement endpoint does not exist.
   - Notification links and broadcasts are dropped by the new notification feed.
   - Rejecting an org request always fails, and the org merge preview always fails.
   - The mentor "accept session" button calls a GET-only endpoint with POST.
   - The new Role Verification page sends filters the backend ignores.
   - Company co-admin invites cannot be accepted, and mentor-created company jobs cannot be approved from the UI.
3. **Deployment / regression risk on `pranav-dev`:**
   - The campus co-lead refactor needs a DB migration (`alter-1.91.sql`) that is named in the commit message but **is not in the repo**.
   - It also renames dynamic roles (`"{code} CampusLead"` → `"{code} CampusIGLead"`), which **the dashboard still checks under the old name**.
   - Many other model changes (for example 12 new notification columns) have no migration scripts.
4. **Business rules that can be abused or that lose data:**
   - Learning-circle karma can be farmed with a join/leave loop.
   - A campus event creator can approve their own event.
   - Deleting an interest group cascades into karma history.
   - The company sign-up flow **never uploads the verification document**. It sends a made-up URL instead, so admins verify companies against a document that does not exist.

### Findings count

| Severity | Count |
|---|---|
| Critical | 7 |
| High | 17 |
| Medium | 24 |
| Low | 9 |

### Top 10 to fix first

| # | ID | Fix |
|---|---|---|
| 1 | C-01 | Add auth + Admin role to `organisation/transfer/` (or remove it) |
| 2 | C-03 | Profile picture upload: require auth, use the user id from the JWT |
| 3 | C-02 | Add Admin role checks to all achievement admin endpoints |
| 4 | C-04 | Launchpad: stop trusting `current_user` from the request body |
| 5 | C-06 / C-07 | Commit and run the missing migration; update dashboard role suffix checks |
| 6 | C-05 | Build a real file upload for company verification documents |
| 7 | H-01 / H-14 | Role checks on org verification; restrict self-assignable roles; return only verified, active roles in `user/info` |
| 8 | H-04 / H-05 | Fix the notification feed contract (links, source, broadcasts) and add or remove the admin broadcast endpoint |
| 9 | H-08 | Remove the `request.body` read in the middleware, or raise the upload limits to match the product |
| 10 | H-10 / H-09 | Stop karma farming; block self-approval of events |

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

### H-14 · Anyone can request any role at sign-up; `user/info` returns unverified roles as real roles
| Field | Detail |
|---|---|
| Severity / Category | High · Security / RBAC (Critical if the auth service puts unverified roles in the JWT — **needs confirmation**) |
| Repo / branch | Backend @ `pranav-dev` + Dashboard @ `dev` |
| Location | Backend `api/register/serializers.py:302` (`role = PrimaryKeyRelatedField(queryset=Role.objects.all())`), `register_views.py:233` (`GET /register/role/list/` lists every role, including "Admins", with IDs), `api/dashboard/user/dash_user_serializer.py:80` `UserSerializer.get_roles` (all links; ignores `verified`, `is_active`, `revoked_at`). Dashboard `src/hooks/use-permissions.ts:81-84` (roles from `user/info`), `src/lib/auth/server.ts` `requireRole` (used by 43 server pages). |

- **Problem.**
  - A user can register with `role=<Admins id>`. A link with `verified=False` is created and shows up in the admin verification queue.
  - `user/info` returns `"Admins"` in `roles`, so the dashboard shows management nav, and **server-side `requireRole` lets the user in** (only the edge proxy, which reads JWT roles, may stop them).
- **Expected.** Only a short allowlist can be self-requested (Student, Mentor, Enabler, Company …). `user/info` returns only verified, active roles (and optionally a separate `pending_roles`).
- **Fix.** Add an allowlist in the register serializer. Filter `verified=True, is_active=True` in `get_roles`. Confirm the auth service filters the same way.
- **Impact.** Privilege-escalation risk. Admin UI can leak to unverified users.

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
| Backend route+method pairs with **no authentication at all** | 208 (≈70 of them change data; see Appendix B) |

### 5.3 Every endpoint mismatch found

| Dashboard call | Method | Backend result | Verdict |
|---|---|---|---|
| `auth.login` `/api/v1/auth/user-authentication/` | POST | Django proxy exists but only forwards `emailOrMuid`+`password` | OTP login works only if the gateway routes to the auth service (M-14 / §12) |
| `auth.requestOTP` `/auth/request-otp/` | POST | No Django route | Needs gateway → auth service |
| `auth.refreshToken` `/auth/get-access-token/` (client + server refresh) | POST | No Django route (Django has `/auth/refresh-token/` proxy) | Needs gateway; **breaks if `BACKEND_URL` points straight at Django** (§12) |
| `auth.logout` `/auth/logout/` (route handler) | POST | No Django route | Same as above; errors are swallowed, so the refresh token is never revoked |
| `auth.signinWithGoogle`, `auth.googleCallback` | GET | No Django route | Same as above |
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
| Login / session | gateway paths | ✅ | n/a | ⚠️ OTP via Django proxy | ✅ envelope | ✅ | ⚠️ (§12) |
| User info | ✅ `GET user/info/` | ✅ | ⚠️ returns unverified roles | ✅ | ✅ | ✅ | ⚠️ (H-14, M-16) |
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

---

## 6. Business-logic audit

**Users and roles**
- Role requests at sign-up are not limited (H-14).
- System roles can be edited or deleted (M-01).
- Bulk and single role removal behave differently (M-02).
- Roles are trusted from the JWT for up to 15 minutes after a change (M-14).
- `user/info` mixes pending and active roles (H-14).
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
2. **RBAC data source.** The UI uses DB roles from `user/info` (including pending ones), the proxy uses JWT roles, and the backend uses JWT roles. These three sources can disagree (H-14, M-14).
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

---

## 9. Security audit

| ID | Issue | Severity |
|---|---|---|
| C-01 | Unauthenticated org transfer + delete | Critical |
| C-02 | Achievement admin with no role check; expired tokens accepted | Critical |
| C-03 | Unauthenticated profile picture overwrite | Critical |
| C-04 | Launchpad identity taken from the request body | Critical |
| H-01 | Org request approval by any user | High |
| H-14 | Self-requested privileged roles; unverified roles returned as active | High (Critical if the JWT includes them) |
| H-15 | Unauthenticated VC issuance and connected-user email listing | High |
| H-10 | Karma farming | High |
| M-14 | JWT helpers skip the expiry check; role staleness; suspended users | Medium |
| M-15 | Public user search: IDs, admin enumeration, private users | Medium |
| M-22 | CORS `*`, debug toolbar, secrets in logs, Django serving media | Medium |
| M-23 | Refresh token readable by JavaScript | Medium |
| L-02 | Unauthenticated terms approval | Low |
| L-08 | Unchecked link schemes | Low |

Other notes:
- `OrganizationKarmaTypeGetPostPatchDeleteAPI` and `OrganizationKarmaLogGetPostPatchDeleteAPI` (`POST /organisation/karma-type/create/`, `/karma-log/create/`) only need a signed token and no role. Any user can add org karma logs. Add an Admin check.
- `CollegeChangeAPI` (PATCH `college/change-college/`) has no permission class. It relies on `fetch_user_id` (signature only, no expiry check).
- The OpenAPI schema at `/api/schema/` uses `IsAdminUser` only while `ENABLE_SWAGGER` is off. When it is on, the schema and docs are `AllowAny`. Make sure `ENABLE_SWAGGER` is off in production.

---

## 10. Performance and scalability

| Area | Problem | Suggestion |
|---|---|---|
| Roles list | `len(queryset)` per role; members sort JOIN (M-04) | `annotate(Count)` |
| Mentor list | Loads every pending application into Python to find change requests | Use `Exists()` / a subquery |
| Events | The dashboard fetches 3×200 events per "Pending" view and all published events for "Ongoing/Completed" (M-11) | Server `status__in`, time-based status |
| Uploads | The middleware reads every request body into memory (H-08) | Drop it; stream uploads |
| IG list | `cache_page(600)` with no invalidation (M-09) | Key-based cache with invalidation |
| Notifications | `count()` + offset pagination; fine now, but fan-out for broadcasts is needed (H-04) | Batch insert with `dedupe_key` (already designed) |
| Role verification | Client filter over server pages (H-07) | Server filter |
| Org dropdowns | `perPage=1000` loads (verify dialog, departments, interns, task types) | Server-side search combobox |
| DB connections | `CONN_MAX_AGE=0` under ASGI (documented choice) means a connection per request | Add a pooler (ProxySQL / pgbouncer-like) |
| Logging | DEBUG root logger to disk, no rotation | Rotate; INFO level |

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
9. **Auth routing depends on infra.**
   - The dashboard calls `/api/v1/auth/{request-otp, get-access-token, logout, token-verification, signin-with-google, google/login/callback}` on `NEXT_PUBLIC_DJANGO_API_URL`. Django serves none of these. It has `user-authentication/`, `refresh-token/`, and the mobile proxies.
   - This only works if a reverse proxy sends `/api/v1/auth/*` to the auth service. If it does, the Django `auth/*` proxies are shadowed.
   - The server-side refresh (`refresh.server.ts`) and logout (`app/api/auth/logout/route.ts`) use `BACKEND_URL`. `src/api/server.ts` recommends pointing that at an internal VPC endpoint. **If that endpoint is Django, every server refresh fails and users are logged out every 15 minutes.** The logout route swallows the error, so refresh tokens are never revoked.
   - `loginWithOTP` sends `otp`, but the Django proxy only forwards `password`.
   - *Fix:* Write down the routing. Point both refresh paths at the same working endpoint (the Django `refresh-token/` proxy or the auth service directly). Add a health check.
10. **Deep links from the backend** — M-13.
11. **Role data sources** — H-14 / M-14 (DB roles in the UI vs JWT roles in proxy and backend).
12. **Disabled features** — M-21 (the backend has the endpoints; the dashboard turned them off).
13. **Removed fields** — M-24.

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

---

## 14. Recommended fixes and priorities

**P0 — before any deploy (1–2 days)**
1. Lock down open endpoints: C-01, C-02, C-03, C-04, H-01, H-15, the org karma endpoints, L-02. Also set `DEFAULT_PERMISSION_CLASSES` so new views are closed by default.
2. Commit and dry-run the missing DB scripts (C-06, H-16). Block deploy on a schema check.
3. Update the dashboard role suffixes for `CampusIGLead` / `CampusIGCoLead` (C-07).
4. Remove the `request.body` read in the middleware or raise the limits (H-08).
5. Restrict self-assignable roles. Return only verified, active roles from `user/info` (H-14).

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

---

## 15. Final production-readiness assessment

**Verdict: NOT production-ready.**

| Area | Status |
|---|---|
| Security | ❌ Several unauthenticated or unauthorized write endpoints (C-01…C-04, H-01, H-15) |
| Data integrity | ❌ Missing migrations (C-06, H-16); destructive cascades (H-11); non-atomic karma (M-17) |
| Core business rules | ❌ Fake document verification (C-05); karma farming (H-10); self-approval (H-09) |
| Integration | ❌ At least 10 cross-repo breaks (§12) |
| Frontend quality | ⚠️ Typecheck and lint pass; unit tests fail; CI does not run tests |
| Backend quality | ⚠️ Good recent patterns, but default-open permissions and no CI tests |
| Observability | ⚠️ Schema drift is invisible in production; logs hold secrets |

**Release gate.** Ship only when all of these are true:
1. All Critical and High items are fixed or have an accepted, documented risk.
2. The DB migration set is committed and rehearsed on a copy of production.
3. The dashboard `vitest` and backend `pytest` suites run in CI and pass.
4. A smoke test covers: login/refresh/logout through the real gateway, org verify/reject/merge, company sign-up with a real document, event create → approve → publish for each organiser type, role verification per tab, notification feed with links and broadcasts, and uploads at 4–5 MB.

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

## Appendix B — Automated scan counts

- Backend URL patterns: 733. Route/method pairs: 1,123 (901 authenticated, 14 optional auth, 208 no auth).
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
