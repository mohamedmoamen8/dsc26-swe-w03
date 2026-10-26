## Tools
- Kilo (AI coding assistant) – used to scaffold the FastAPI app structure, write SQLAlchemy models, create Alembic migrations, implement the transfer logic with idempotency and token-bucket rate limiting, debug authentication issues, and handle git operations.

## What AI got wrong
- Initially tried to write the idempotency record in a separate transaction after committing the transfer. I had to fix this to account for the fact that if the server crashes between those two transactions, a retry would create a duplicate transfer.
- Forgot to add the WWW-Authenticate: Bearer header to all 401 responses at first. The task explicitly requires it on every 401 for the three endpoints.
- Initially used 	ime.time() for the rate limiter instead of settings.clock. The hidden tests inject their own fake clock, so switching to settings.clock was necessary.
- At first I didn't enforce extra = "forbid" strictly enough in the Pydantic schema. Had to make sure any unknown field in the request body returns 422.
- Overthought the "source not owned" vs "unknown destination" distinction at the beginning. The spec is very specific: source account not owned by caller OR not existing must return 404, but an unknown destination account must return 422.

## In my own words
- **Why does a transfer to someone else's account return 404 and not 403?**  
  To prevent account enumeration. If we returned 403 for "this account exists but isn't yours" and 404 for "this account doesn't exist", an attacker could brute force account IDs and learn which ones are valid. Returning 404 in both cases keeps that information hidden.

- **What would happen to a customer if your idempotency record were written in a separate transaction after the transfer?**  
  If the transfer transaction commits successfully but the server crashes or drops connection before committing the idempotency record, there would be no record of that completed transfer. On retry, the client would send the same Idempotency-Key with the same body, but we'd find nothing in idempotency_records. We'd treat it as a brand new request, debit the sender again, credit the receiver again and create a second Transfer row. That would be a double-spend. By keeping the idempotency record creation and the transfer changes in the same atomic transaction, we avoid this entirely.
