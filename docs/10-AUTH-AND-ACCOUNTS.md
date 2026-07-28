# Auth & Account Management

Design for login, sessions, RBAC, and account/API-key management. Design-only pass — no backend
or frontend code lands with this doc, matching how `00-08` preceded the architecture and
`09-LIFE-INSURANCE-SLICE.md` preceded its code. This doc, `02-DATABASE-ERD.md`, and
`03-API-SPEC.md` are the contract a future implementation slice builds against.

## Why custom JWT + direct Entra OIDC, not a hosted IdaaS

A WorkOS-style hosted-auth vendor was evaluated first: free password/social login, but
**enterprise SSO connections (including Microsoft Entra ID) are billed per connection** — not
viable at this stage, and specifically the thing PolicyIQ needs for broker/enterprise users. The
alternative isn't "no SSO," it's talking to Microsoft directly: an Entra app registration is free
on Microsoft's side, and OIDC (authorization-code flow + PKCE) is a standard, well-supported
protocol — no vendor lock-in, no recurring per-connection fee. This also happens to be exactly
what `01-ARCHITECTURE.md` already specified before the hosted-vendor detour, so this doc mostly
fills in detail rather than changing direction.

## Password login flow

1. `POST /auth/register` — email + password. Password hashed with **argon2id** (memory-hard,
   current OWASP recommendation over bcrypt for new systems). Role defaults to `consumer`;
   `broker`/`admin` are assigned by a PolicyIQ admin after registration (audit-logged), never
   self-selected at signup.
2. `POST /auth/login` — verifies password, issues:
   - **Access token**: JWT, ~15 minute TTL, carries `sub` (user id), `role`, `exp`.
   - **Refresh token**: opaque random value, ~30 day TTL, **stored server-side hashed** (in
     Redis — the same instance `03-API-SPEC.md` already requires for rate limiting, no new
     dependency) so it's revocable. Rotates on every use: using a refresh token issues a new one
     and invalidates the old, so a stolen-and-reused refresh token is detectable (reuse of an
     already-rotated token revokes the whole chain).
3. `POST /auth/refresh` — exchanges a valid refresh token for a new access/refresh pair.
4. `POST /auth/logout` — deletes the refresh token's server-side record.

## Microsoft Entra SSO flow

1. `GET /auth/sso/entra/login` — builds the Microsoft authorization URL (`ENTRA_TENANT_ID`,
   `ENTRA_CLIENT_ID`, PKCE code challenge) and redirects.
2. User authenticates with Microsoft (their own MFA/conditional-access policy applies — we don't
   reimplement any of that).
3. `GET /auth/sso/entra/callback?code=...` — exchanges the code for tokens, validates the ID
   token's signature against Microsoft's published JWKS and its `aud`/`iss`/`exp` claims, then:
   - Looks up `USER` by `sso_subject = id_token.oid`.
   - If none exists, JIT-provisions a new `USER` row (`role = consumer`, `sso_provider = "entra"`,
     `sso_subject = oid`, `password_hash = null`).
   - Issues a **PolicyIQ** access/refresh pair exactly like the password flow — from this point on,
     an Entra-authenticated session is indistinguishable from a password-authenticated one to the
     rest of the API. This is deliberate: `Depends(get_current_user)` has exactly one code path to
     validate, not one per login method.

RBAC stays entirely PolicyIQ-owned: Entra's own group/role claims are never read for
authorization decisions. A user showing up via SSO always starts as `consumer`; getting to
`broker` is a PolicyIQ-admin action, audit-logged like any other role change. This avoids trusting
an external directory's group structure to map cleanly onto PolicyIQ's three roles.

## Session transport

httpOnly, `Secure`, `SameSite=Strict` cookies for both the access and refresh token. Chosen over
bearer-token-in-localStorage because the frontend is (and will remain, per `01-ARCHITECTURE.md`)
a same-origin SPA served alongside the API in Phase 1 — cookies avoid XSS-exfiltration risk that
localStorage tokens carry, at the cost of needing CSRF protection on state-changing routes
(standard double-submit or `SameSite=Strict` alone, since there's no cross-site form-post use
case for this app). If a native mobile client or third-party integration needs stateless
verification later, that's a `Depends` variant that reads an `Authorization: Bearer` header
instead — API keys already cover the non-browser case (below), so this isn't urgent.

## Account / Settings screen

- **Profile card**: name (editable), email (editable for password users, read-only "managed by
  your Microsoft account" for SSO users), role badge, organization/firm name (editable — the
  minimal broker-identifying field for Phase 1; FSP/adviser-register-number-level detail is
  deferred to the Phase-2 broker portal per `07-ROADMAP.md`, not designed here).
- **Security card**: auth method (password vs. "Microsoft Entra SSO"), password-change form
  (password users only), no session-list/device-management UI in this pass (out of scope, cheap
  to add later against the same refresh-token-in-Redis record).
- **API Keys card**: list (label, key prefix, created, last used, revoked/active), "Generate new
  key" flow that shows the raw key exactly once with a copy button and an explicit "store this
  now, it won't be shown again" warning, and a revoke action per key.

## API keys vs. browser sessions

Different mechanism, different threat model: API keys are long-lived, presented via a header
(not a cookie — no browser involved), verified against `key_hash` with no refresh/rotation
dance. They're the intended path for the previously-discussed "API option" (B2B/broker
programmatic access) and for scripts/integrations that can't do an interactive redirect login.
Revocation is immediate (`revoked_at` set, checked on every request) rather than TTL-based expiry.

## Config (new environment variables)

Cross-referenced into `06-DEPLOYMENT-PLAN.md`'s secrets section:

| Variable | Purpose |
|---|---|
| `JWT_SECRET_KEY` | Signs/verifies PolicyIQ-issued access tokens |
| `JWT_ACCESS_TTL` | Access token lifetime (default ~15 min) |
| `JWT_REFRESH_TTL` | Refresh token lifetime (default ~30 days) |
| `ENTRA_TENANT_ID` | Microsoft tenant to authenticate against |
| `ENTRA_CLIENT_ID` | PolicyIQ's Entra app registration client ID |
| `ENTRA_CLIENT_SECRET` | Entra app registration secret (confidential client) |
| `ENTRA_REDIRECT_URI` | Must match the callback URL registered with Entra |

None of these are hardcoded anywhere — see `.env.example` for placeholders.
