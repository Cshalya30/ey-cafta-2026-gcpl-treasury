# 9. Postgres for the deployment, SQLite for the demo

**Status** Accepted · **Date** 20 October 2026 · **Supersedes the hosting half of** [0007](0007-one-origin-and-two-content-security-policies.md)

## Context

Decision 0007 put the application in one container on one origin, and that was
right. What it got wrong was the hosting economics.

A free container that sleeps is not a demo. The deployment sat behind a free
instance that spins down after fifteen minutes idle and takes thirty to sixty
seconds to wake. For a link a judging panel opens at a time nobody controls,
that is the difference between a product and a blank tab. Keeping it warm by
pinging it does work, but it consumes the capped monthly instance hours at the
same rate as running continuously, so the service would suspend partway through
the judging window instead of merely being slow.

Every alternative that keeps a container always-on costs money or requires a
card on file. The ones that do not — serverless platforms — were ruled out in
0007 for a good reason: SQLite on an ephemeral, per-instance filesystem means
two clicks can land on different instances, and the audit chain forks. The
product's own verifier would then correctly report it broken.

That reason was sound, and it was also the wrong thing to conclude from. The
obstacle was never serverless. It was SQLite on serverless.

## Decision

The database is chosen by `DATABASE_URL`. Set, it is Postgres. Unset, it is the
SQLite file.

Both are real deployments. The local demo and the whole test suite keep SQLite,
so `python scripts/generate_data.py && uvicorn` still needs no database server
and the two-command workflow in the README is unchanged. The serverless
deployment uses hosted Postgres, where every instance sees one database and one
audit chain.

The ORM did not need changing. Every column is `String`, `Float`, `Integer` or
`Date`; there is not one `Boolean` in the schema, and no query uses an integer
as a condition. The coupling was six places, and only one of them was
dangerous:

```sql
-- SQLite scores the comparison as 1 or 0. Postgres returns a boolean and
-- refuses to sum it.
SELECT CAST(SUM(feed_status = 'live') AS REAL) / COUNT(*) FROM account
```

That line computes INV-3, the cash visibility headline. `CASE WHEN … THEN 1
ELSE 0 END` is accepted by both.

Connections use `NullPool` with `pool_pre_ping`. A pool held inside an instance
that may be frozen between requests hands back connections the server has
already closed, and the provider's pooler is doing the pooling anyway.

### Moving the database was not sufficient

One durable database stops instances from holding *different* chains. It does
not stop them from corrupting the same one.

`audit.append` reads the tail row and inserts an event linked to it. That is
read-then-insert, and at READ COMMITTED two transactions read the same tail and
both chain to it. The result is a forked chain, and `/audit/verify` would
report it broken — in the product whose argument is that the chain is
verifiable. The proposal router had the same shape: an id derived from
`count(*)`, which two concurrent creates turn into a primary key collision and
a 500.

Neither had ever been seen, because SQLite has one writer and that hid both.
Moving to Postgres would have exposed them on the first pair of simultaneous
clicks.

Both sections now take a transaction-scoped advisory lock, released on commit
or rollback, and a no-op on SQLite. This is the part of the migration that a
passing test suite would not have caught: the suite runs on the dialect that
hides the bug.

`create_all` no longer runs at startup against Postgres. The generator has
already created and seeded the schema, and the call would spend a reflection
round trip on every cold start to discover that. The application refuses to
boot if it finds itself serverless with no `DATABASE_URL`, rather than opening
a private SQLite file per instance and serving inconsistent answers quietly.

The static mount stays exactly as 0007 left it. On this platform a top-level
middleware keeps static files in the function rather than promoting them to the
CDN — which is the behaviour we need, because CDN-served files bypass
middleware, and the two content security policies live in middleware.

## Consequences

The suite runs on SQLite and the deployment runs on Postgres, so the tests do
not exercise the database that serves judges. That asymmetry is the real cost
of this decision and it is the one worth watching: a SQLite-only idiom passes
every test and fails in production.

`api/tests/test_portability.py` narrows it without a server. It compiles all
thirty tables and every index against both dialects, asserts the schema
declares no `Boolean`, greps the source for `SUM(x = y)`, and checks that the
two dependency lists agree. Compilation is not execution and this is not proof;
it catches the class of error that actually occurred rather than standing in
for an integration test.

The suite also refuses to reach a configured server database. `DATABASE_URL`
takes precedence over the SQLite path and is read from the environment on every
call, so seeding a deployment and then running pytest in the same shell would
have sent tests that tamper with `audit_event` and update a deposit rate at the
live demo. An autouse fixture removes the variable for every test.

Connection strings are normalised on the way in. `postgres://` has not been a
valid SQLAlchemy URL since 1.4 and a bare `postgresql://` selects a driver this
project does not install, so a string pasted from a provider's dashboard works
unedited. The likeliest way for this to fail was someone retyping a URL.

The container and `render.yaml` still work and are still correct. Nothing here
removes the option of running this as one image on a host that does not sleep;
it removes the requirement to pay for one.
