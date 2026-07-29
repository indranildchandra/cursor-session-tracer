# ADR-0001: Migrate all API clients from APIKeyAuth to BearerTokenAuth

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Indranil Chandra + review-council (4 personas)
- **Review record:** `docs/design-review.md` (2026-05-09 06:40:00 entry)
- **Implemented by trace:** `pending` (linked at `start_trace` time via `adr_id="ADR-0001"`)

## Context

The demo service authenticates its GitHub and Stripe clients with `APIKeyAuth`,
which sends the credential as a static `X-API-Key` header. The upstream APIs are
moving to short-lived bearer tokens, and our own gateway now expects
`Authorization: Bearer <token>`. `APIKeyAuth` has no `.headers` property shaped
for that, and every client constructs its own header inline, so the auth contract
is duplicated across the codebase with no single seam to change.

This is a small surface (one auth module, two clients, one accessor) but a
cross-cutting one: get it wrong and every outbound call fails identically, which
is exactly the kind of change that looks trivial in a diff and is painful to debug
48 hours later.

## Decision

We will introduce `BearerTokenAuth` in `demo/auth.py` exposing a `.headers`
property that returns `{"Authorization": "Bearer <token>"}`, make
`get_current_auth()` return it, and update every client to construct its request
headers from `auth.headers` rather than building an `X-API-Key` header inline.

## Scope (files)

- `demo/auth.py`
- `demo/main.py`
- `demo/clients/github.py`
- `demo/clients/stripe.py`

## Alternatives Considered

- **Add BearerTokenAuth but keep APIKeyAuth as a fallback (dual-auth)** — rejected:
  keeps the duplicated header logic we are trying to remove and doubles the test
  matrix for no current consumer.
- **Have each client read the raw token and build its own Bearer header** — rejected:
  re-duplicates the contract the `.headers` seam is meant to centralise; the next
  auth change would again touch every client.

## Consequences

- **Positive:** one seam (`auth.headers`) now owns header construction; a future
  auth change touches `auth.py` only. The clients become auth-agnostic.
- **Trade-offs:** a hard cutover — there is no window where both auth types work,
  so the four files must land together.
- **Risks flagged by council:** `staff-engineer` flagged that any client left on
  the old inline header would fail silently at call time, not import time.
  Mitigation: the accessor `get_current_auth()` is the single source of the auth
  object, and the post-refactor test asserts every client's header key.

## Council Verdict

**Proceed as-is** — adversarial review by 4 personas (staff-engineer,
appsec-architect, senior-backend-engineer, lead-sdet). Converged concern: the
cutover must be atomic across all four files (see Trade-offs). No blockers. No
human overrides.
