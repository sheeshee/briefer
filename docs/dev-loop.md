# Development loop

How Briefer moves from a milestone branch to the Raspberry Pi: what gets
tested where, how you review, and how a merge reaches production. This file is
the shared instructions for everyone working on the repo, including the cloud
Claude session that writes the code and the Claude Code instance on the Pi.

## Environments

| | Production | Staging |
|---|---|---|
| URL | `https://briefer.<domain>` | `https://staging.briefer.<domain>` |
| Runs | The last merged (approved) build | The latest push on the open milestone PR |
| systemd user unit / port | `briefer@prod` on :8090 | `briefer@staging` on :8091 |
| Data | `/var/lib/briefer/prod`, snapshotted before every promote | `/var/lib/briefer/staging`, refreshed from prod on every deploy |
| Todoist (from M3) | your real projects | the `briefer-test` sandbox project |
| Look | normal | orange `STAGING · <build>` banner, `[staging]` title prefix |

A third, throwaway instance, `briefer@verify` on :8092, runs only during
`briefer-verify`. It uses a copy of staging's build and data, so automated
checks never disturb what you are testing.

Both hostnames resolve to the Pi's NetBird IP. Caddy terminates TLS with Let's
Encrypt certificates obtained through the DNS-01 challenge, so the Pi is never
exposed to the internet. Separate subdomains mean prod and staging get separate
service workers, caches and IndexedDB, so a broken staging build cannot affect
the installed prod app.

## The loop

```
 milestone PR push
      |
      v
 CI (GitHub-hosted)                       app: typecheck, Vitest, hook tests,
  app / deploy-scripts / django  ------>  Playwright against real PocketBase
      |                                   deploy-scripts: shellcheck + bats
      v
 release: build arm64 bundle, publish pre-release  build-<tree-id>
      |
      v
 staging job: join NetBird -> ssh briefer@pi "deploy <id> <sha256>"
      |        (Pi downloads the release, checks the sha256, refreshes
      |         staging data from prod, switches, smoke-tests; reverts on failure)
      v
          ssh briefer@pi "verify <id>"
      |        (throwaway copy: smoke checks + advisory `claude -p` report)
      v
 report posted as a PR comment  --->  you test staging on your phone,
                                      comment; Claude fixes and pushes
      |
      v
 you merge  --->  promote.yml: ssh "promote <id>"
                  (snapshot prod data, switch, smoke-test,
                   automatic restore on failure; report on the merged PR)
      |
      v
 Claude starts the next milestone from main
```

### Build ids, and why merge = promote is safe

A bundle's id is the first 12 hex characters of the commit's **git tree
hash**, not its commit hash. A merge or squash of a branch that is up to date
with `main` produces exactly the PR head's tree, so `promote.yml` can find the
bundle staging tested by computing the tree hash of the new `main` commit. If
`main` differs at all from what staging tested, no bundle with that id exists
and promotion fails without touching prod.

This depends on the branch protection rule **"Require branches to be up to
date before merging"** (see setup below).

### What blocks and what doesn't

- **Blocking:** CI tests, `briefer-smoke`, which is deterministic (health,
  build id, env, frontend, SPA fallback, memory, public HTTPS), and the deploy
  itself.
- **Advisory:** the Claude verify pass. It can fail for reasons unrelated to
  the build, like an expired login or rate limits, so a failure is reported
  but never blocks.

## Testing layers

| Layer | Tool | Runs where | Covers |
|---|---|---|---|
| Hook logic | `node --test pb/tests/*.test.js` | CI, local | Pure CommonJS modules in `pb/pb_hooks/lib/`, with no PocketBase globals |
| Frontend units | Vitest + Testing Library (`web/src/**/*.test.tsx`) | CI, local | Components, and from M5 the offline queue |
| End to end | Playwright (`web/e2e/`) via `scripts/e2e.sh` | CI, local | Real PocketBase serving the real bundle; from M5 also network loss |
| Deploy scripts | bats (`deploy/tests/`) | CI, local | Deploy, verify, promote and rollback against real PocketBase processes, using a fake `systemctl` |
| On-device | `briefer-smoke`, `claude -p` | Pi | The real install: arm64 binary, systemd, Caddy and TLS, memory |
| Human | Checklist in each PR | Your phone | Feel, correctness, anything automation can't judge |

Red-green still applies (see CLAUDE.md). Keep hook files thin and put the
logic in `pb_hooks/lib/` so it can be unit-tested without a server.

## Local commands

```bash
scripts/dev.sh                      # PocketBase :8090 (hooks hot-reload) + Vite :5173
(cd web && npm test)                # frontend unit tests
(cd web && npm run typecheck)
node --test 'pb/tests/*.test.js'    # hook logic
scripts/e2e.sh                      # build amd64 bundle, run PocketBase, Playwright
npx --yes bats@1.13.0 deploy/tests  # deploy-script tests (needs Go + Node)
scripts/build-release.sh --arch arm64   # what CI ships
```

Dependencies: Go (the version in `pb/go.mod`; `GOTOOLCHAIN=auto` fetches it),
Node 22, and npm 11 when you change `web/package-lock.json`. npm 10.9 crashes
resolving vitest 4.1's optional peers, but `npm ci` on 10.x works.

PocketBase is built from the pinned Go module in `pb/go.mod`, never downloaded
as a prebuilt binary. Upgrading PocketBase means `go get
github.com/pocketbase/pocketbase@vX && go mod tidy` in `pb/`, in its own PR.

## Operating prod

Every operation goes through `briefer-entry` on the Pi. From GitHub, use
**Actions → Pi operations → Run workflow**:

- `status`: which build each environment runs, plus recent promotions
- `rollback`: undo the most recent promote. This restores the prod data
  snapshot taken just before it, so data written since then is discarded. A
  snapshot of the discarded state is kept first. Repeatable.
- `promote <id>`: re-promote a specific build that passed staging, e.g. to
  roll forward again after a rollback

On the Pi itself, as the `briefer` user, the same scripts are in
`/opt/briefer/bin/`. Logs: `journalctl --user -u briefer@prod`.

Snapshots are in `/var/lib/briefer/snapshots/`, and the newest 10 are kept.
They contain your real data.

## One-time setup

### 1. Pi (Raspberry Pi OS 64-bit, Pi 5)

1. Install NetBird and join your network. Note the Pi's NetBird IP.
2. At your DNS provider, create A records for `briefer.<domain>` and
   `staging.briefer.<domain>` pointing at that NetBird IP (100.x). Create an API
   token that can edit the zone's TXT records.
3. Generate a dedicated CI deploy key on your laptop:
   `ssh-keygen -t ed25519 -f briefer_ci -C briefer-ci -N ''`
4. Clone this repo on the Pi and run:
   ```bash
   sudo deploy/bootstrap.sh --domain briefer.<domain> --acme-email you@example.com \
        --dns-provider cloudflare --ci-pubkey briefer_ci.pub
   ```
   This installs the deploy key in root-owned `authorized_keys`, restricted to
   the `briefer-entry` forced command. The key can't open a shell.
5. Put the DNS token in `/etc/caddy/caddy.env`, then run `sudo systemctl
   restart caddy`.
6. Fill in `/etc/briefer/common.env` (NewsAPI and Todoist keys) and
   `TODOIST_PROJECT_ID` in `staging.env` and `verify.env` (needed from M3).
7. Claude verify pass: run `sudo -iu briefer claude setup-token` and paste the
   token into `/etc/briefer/claude.env`, or log in once interactively with
   `sudo -iu briefer claude`.
8. To update the deploy scripts later, `git pull` and re-run bootstrap. CI
   cannot change them, by design.

### 2. NetBird

- Create a **reusable, ephemeral** setup key for CI, with an auto-assigned
  group such as `ci`. Ephemeral peers are removed shortly after each run.
- Add an access policy: group `ci` → the Pi, TCP 22 only.

### 3. GitHub

- **Secrets:**
  - `NETBIRD_SETUP_KEY`
  - `PI_SSH_KEY` (the private `briefer_ci` key)
  - `PI_HOST` (the Pi's NetBird IP)
  - `PI_KNOWN_HOSTS`: `<netbird-ip> ssh-ed25519 AAAA...`. Bootstrap prints the
    host key.
- **Variables:**
  - `PI_ENABLED=true`. Until this is set, the staging and promote jobs are
    skipped and CI stays green.
  - `STAGING_URL` and `PROD_URL`
  - `NETBIRD_MANAGEMENT_URL`, only for self-hosted NetBird
- **Branch protection on `main`:**
  - require a pull request
  - require the status checks *Frontend + PocketBase*, *Deploy scripts* and
    *Deploy to staging + verify on the Pi*
  - **require branches to be up to date before merging**

### 4. First run

Once the M0 PR is merged with Pi access configured, prod runs the
placeholder. Then create the PocketBase superuser:

```bash
sudo -u briefer /opt/briefer/envs/prod/current/pocketbase superuser upsert you@example.com '<password>' --dir /var/lib/briefer/prod
```

Staging inherits it on the next deploy, because staging data is copied from
prod.

## Milestones

| # | PR | Your phone check |
|---|---|---|
| M0 | Pipeline: CI, release, Pi scripts, bootstrap, Caddy, verify, placeholder page | Placeholder loads over HTTPS on both hostnames; verify report shows up on the PR; merge promotes |
| M1 | Schema, migrations, item state rules, API rules | Collections look right in the admin UI |
| M2 | HN, NewsAPI and fake fetchers, cron, manual fetch route | Items appear on schedule and on demand |
| M3 | Todoist hook → `action_errors`, with retry | Tasks land in the sandbox project; failures are recorded |
| M4 | React card stack: swipe, radial menu, counters, fetch and reset | The swipe UI feels at least as good as today's |
| M5 | Offline: service worker, IndexedDB swipe queue, instant swipes, retry | Swipe with Wi-Fi off, turn it back on, and the swipes sync |
| M6 | History and errors pages, remove Django, docs | Feature parity; the old code is gone |

One PR per milestone. The next one starts from `main` after the merge.

## For the Claude Code instance on the Pi

You are invoked non-interactively by `briefer-verify` with a prompt from
`/opt/briefer/bin/verify-prompt.md`, restricted to `curl`. Your output is
posted to the PR as an advisory report. If the person asks you to debug
something interactively:

- Use the scripts in `/opt/briefer/bin/` rather than hand-editing symlinks or
  data.
- Never edit files under `/opt/briefer/builds/`. Fixes go through a PR.
- Prod data and snapshots are real personal data. Don't copy them off the Pi.

## Known limitations

- `bootstrap.sh` and the GitHub → NetBird → SSH path can only be tested on the
  real Pi. The M0 PR is where they are proven.
- Caddy with a DNS plugin comes from Caddy's build service and has no
  published checksum. Pin it by keeping the binary, since bootstrap only
  downloads it when the module is missing.
- Pre-releases accumulate, one per tested tree. Prune old `build-*` releases
  occasionally; the Pi keeps its own copies of the last 10 builds.
- Staging and prod both run cron from M2, so staging's schedule is set less
  often to stay inside NewsAPI's free quota.
