---
name: ship-milestone
description: Completes one PRD milestone — lint, test, verify the UI, audit invariants, commit.
disable-model-invocation: true
---

Complete one milestone. Stop at the first failure rather than carrying it
forward.

1. **Regenerate and verify the dataset.**

   ```
   python scripts/generate_data.py --seed 42
   ```

   All five invariants must print OK. Confirm reproducibility by running it
   twice and comparing the SHA-256 of `data/gcpl.db`.

2. **Run every suite.** Fix failures before continuing; do not skip a test.

   ```
   python -m pytest
   cd web && npx tsc -b --noEmit && npm test && npm run e2e
   ```

3. **Verify the UI.** Ensure both servers are running, then use the
   `ui-verifier` subagent on each route this milestone touched. Fix any FAIL in
   this session, not the next one.

4. **Audit.** Run the `invariant-auditor` subagent. Any finding blocks the
   commit.

5. **Review the diff.** Show `git status` and a short diff summary. Confirm no
   generated artefact, `.env`, database file or `node_modules` is staged.

6. **Commit this milestone alone.** Never bundle two.

   ```
   git add <only this milestone's files>
   git commit -m "feat(<area>): <milestone>"
   ```

7. **Report** what passed, what failed, and which PRD acceptance criteria for
   this milestone remain open. If a criterion could not be verified, say so
   plainly rather than marking it done.
