# Runtime Contract

## Development hook lifecycle

The local transport uses the GitHub CLI extension:

```text
gh extension install cli/gh-webhook
gh webhook forward --repo=OWNER/REPO --events=EVENTS --secret=SECRET --url=LOCAL_URL
```

Lifecycle verification on 2026-07-21 used `platevault/platevault`:

| State | Command | Result |
|---|---|---|
| Before start | `gh api repos/platevault/platevault/hooks` | No records |
| Forwarding | `gh webhook forward --repo=platevault/platevault --events=ping` | Active `cli` hook `655110579` at `https://webhook-forwarder.github.com/hook` |
| After Ctrl-C | `gh api repos/platevault/platevault/hooks` | No records |

The development hook exists only while the forwarder runs. Stop the process with SIGINT or SIGTERM so the extension removes it.

## Local state

The runtime stores a 32-byte random webhook secret with mode `0600`. It installs `cli/gh-webhook` under an isolated XDG data directory beside that secret. GitHub CLI authentication remains in the caller's configured credentials directory.

`cli/gh-webhook` v0.2.0 accepts the signing secret only through `--secret`. The secret is therefore visible in the forwarding child's argument list to the same user and privileged process inspection while the process runs. This local development transport is supported only on a trusted single-user machine and session; do not run it on a shared or multi-user host.

The default state directory is:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/release-queue-watch/OWNER--REPO
```

## Event and reconciliation boundary

`@octokit/webhooks` verifies `X-Hub-Signature-256` before queue mutation. Pull-request events update queue identity immediately. Check, status, and workflow events request a debounced Octokit REST reconciliation.

The runtime emits a `dispatch` record only when a PR is non-draft, has a clean GitHub merge state, and has passing observed checks. It does not mutate GitHub.
