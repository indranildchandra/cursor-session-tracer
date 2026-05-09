# DEMO CURSOR CHAT

## User Request

Refactor all API clients in this codebase to use the new BearerTokenAuth
pattern from demo/auth.py instead of APIKeyAuth. Update demo/main.py,
demo/clients/github.py, and demo/clients/stripe.py. Make sure the
get_current_auth() function also returns the new auth type.

## Cursor Response

Got it. I’ll first inspect the existing auth abstractions (demo/auth.py) and how each client currently wires APIKeyAuth, then update the shared get_current_auth() to return BearerTokenAuth and refactor demo/main.py, demo/clients/github.py, and demo/clients/stripe.py accordingly. Finally I’ll run the test suite to ensure everything still works.

I’ve found the old pattern is still hard-coded in get_current_auth() and both clients construct APIKeyAuth() directly. Next I’ll update get_current_auth() to return BearerTokenAuth, refactor the two clients to use it (or directly use BearerTokenAuth), then adjust demo/main.py imports and run tests to confirm nothing else relies on APIKeyAuth.

Core refactor is in place: get_current_auth() now yields BearerTokenAuth, and both GitHubClient/StripeClient now use that new auth class. Next I’ll run the tests and a quick lint check on the touched files, then close out the trace.

Done
demo/auth.py: get_current_auth() now returns BearerTokenAuth (and its return type annotation is updated accordingly).
demo/clients/github.py: switched from APIKeyAuth to BearerTokenAuth.
demo/clients/stripe.py: switched from APIKeyAuth to BearerTokenAuth.
demo/main.py: removed the unused APIKeyAuth import; validate_auth() now reports the new auth type via get_current_auth().

Verification
Tests: pytest -q passes (54 passed).
