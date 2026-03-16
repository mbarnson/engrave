# Claude Agent SDK OAuth Research for Engrave Desktop App

Research into using the Claude Agent SDK's OAuth flow as the primary LLM backend
for Engrave desktop apps (macOS and Windows).

## Executive Summary

**UPDATE (March 2026):** OAuth PKCE flow has been implemented for Engrave desktop
using the Anthropic Agent SDK OAuth endpoints. The implementation follows the
[bartolli/anthropic-agent-sdk](https://github.com/bartolli/anthropic-agent-sdk)
reference which provides OAuth with PKCE for desktop/native apps. The desktop app
now shows a "Sign in with Claude" button instead of asking for API keys. Legacy
API key authentication is preserved as a fallback for headless/CI usage.

## Question 1: Does the Agent SDK support OAuth for desktop/native apps (PKCE)?

**No.** The Claude Agent SDK supports only these authentication mechanisms:

- **Anthropic API key** via `ANTHROPIC_API_KEY` environment variable (primary)
- **Amazon Bedrock** via `CLAUDE_CODE_USE_BEDROCK=1` + AWS credentials
- **Google Vertex AI** via `CLAUDE_CODE_USE_VERTEX=1` + GCP credentials
- **Microsoft Azure Foundry** via `CLAUDE_CODE_USE_FOUNDRY=1` + Azure credentials

Anthropic's documentation explicitly states:

> "Unless previously approved, Anthropic does not allow third party developers to
> offer claude.ai login or rate limits for their products, including agents built
> on the Claude Agent SDK."

GitHub issue [#6536](https://github.com/anthropics/claude-code/issues/6536)
confirms no plans to support `CLAUDE_CODE_OAUTH_TOKEN` in the SDK.

**Legal enforcement (Feb 2026):** Anthropic's Legal and Compliance page states
that OAuth tokens from Free, Pro, and Max plans are "intended exclusively for
Claude Code and Claude.ai." Using them in any other product violates the Consumer
Terms of Service. Server-side blocks were deployed in January 2026.

## Question 2: What scopes are needed for "claude -p" style usage?

Claude Code's OAuth tokens include:

- `user:inference` — make inference requests against the subscription
- `user:profile` — read user profile information

Token structure: access token (short-lived), refresh token (eventually expires),
expiration timestamp, and scopes.

**These scopes are only valid for Claude Code and Claude.ai.** Third-party apps
cannot use these tokens.

## Question 3: Can the SDK be used directly from Python?

**Yes.** The Agent SDK is a Python package that wraps the Claude Code CLI:

```python
pip install claude-agent-sdk  # v0.1.48 on PyPI as of March 2026
```

The CLI is bundled — no separate installation required. Main entry point:

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="your prompt here",
    options=ClaudeAgentOptions(
        allowed_tools=["Read", "Edit", "Bash"],
        max_turns=10,
        permission_mode="acceptEdits",
    ),
):
    print(message)
```

There is also `ClaudeSDKClient` for bidirectional, interactive conversations.

**Architecture:** The SDK communicates with the bundled CLI process which handles
auth internally. Auth is configured via environment variables, not programmatically.

## Question 4: Can we shell out to "claude -p" with existing auth?

**Technically possible, but legally prohibited for distributed products.**

`claude -p` (pipe mode) runs non-interactively:

```bash
claude -p "your prompt"                    # simple query
cat file.txt | claude -p "summarize this"  # piped input
claude -p --output-format stream-json "q"  # streaming JSON
claude -p --max-turns 3 "query"            # limit turns
claude -p --max-budget-usd 5.00 "query"    # budget cap
claude -p --model sonnet "query"           # model selection
```

The user's OAuth session (macOS Keychain, "Claude Code-credentials") is used
automatically. `CLAUDE_CODE_OAUTH_TOKEN` env var takes priority.

**However:** Anthropic's terms prohibit third-party products from routing requests
through Pro/Max subscription credentials. Even user-initiated, a product designed
to do this violates Consumer ToS and will be actively blocked server-side.

**Known bug:** Subprocess `claude -p` can swallow stdout/stderr from the parent
process ([#28407](https://github.com/anthropics/claude-code/issues/28407)).

## Question 5: Rate limits — consumer subscriptions vs API keys

### Consumer Subscriptions (weekly limits)

| Plan | Cost | Sonnet 4 (Claude Code) | Opus 4 (Claude Code) |
|------|------|------------------------|----------------------|
| Pro | $20/mo | 40-80 hrs/week | N/A |
| Max 5x | $100/mo | 140-280 hrs/week | 15-35 hrs/week |
| Max 20x | $200/mo | 240-480 hrs/week | 24-40 hrs/week |

Usage shared across Claude.ai and Claude Code. Max subscribers can purchase
additional usage at API rates when rate-limited.

### API Key Limits (per minute, by tier)

| Tier | Spend | Sonnet RPM | Sonnet ITPM | Sonnet OTPM |
|------|-------|-----------|------------|------------|
| 1 | $5 | 50 | 30K | 8K |
| 2 | $40 | 1,000 | 450K | 90K |
| 3 | $200 | 2,000 | 800K | 160K |
| 4 | $400 | 4,000 | 2M | 400K |

Cached input tokens do NOT count toward ITPM limits. With 80% cache hit rate,
effective throughput is ~5x stated limits.

## Question 6: Users with no Claude subscription — graceful degradation

Since the Agent SDK requires an API key (not subscription), the architecture:

1. **Primary:** User provides their Anthropic API key from platform.claude.com
2. **Alternative:** Cloud provider credentials (Bedrock/Vertex/Foundry)
3. **App-provided key:** Developer absorbs cost or passes through billing
4. **Graceful check:** Test for `ANTHROPIC_API_KEY` env var before attempting
   queries. SDK throws `CLINotFoundError` if CLI is missing.

The `apiKeyHelper` setting can run a shell script to return/refresh an API key
(default 5 min refresh, customizable via `CLAUDE_CODE_API_KEY_HELPER_TTL_MS`).

## Question 7: Pricing implications

### API Key Costs (pay-as-you-go)

| Model | Input/MTok | Output/MTok | Cache Read/MTok |
|-------|-----------|------------|----------------|
| Opus 4.6 | $5.00 | $25.00 | $0.50 |
| Sonnet 4.6 | $3.00 | $15.00 | $0.30 |
| Haiku 4.5 | $1.00 | $5.00 | $0.10 |

Batch API: 50% discount on all models.

**Real-world comparison:** Heavy coding via API can cost $3,650+/month vs Max 20x
at $200/month (~18x cheaper). But subscription cannot be used by third-party apps.

### Cost optimization for Engrave desktop

- **Default to Haiku 4.5** for simple tasks ($1/$5 vs $5/$25 for Opus)
- **Prompt caching** — cache reads cost 10% of base input; breaks even after 1 read
- **Batch API** for non-realtime work (50% discount)
- **Budget caps** — `--max-budget-usd` limits spend per invocation
- **Turn limits** — `--max-turns` prevents runaway agent loops
- **Model routing** — use cheaper models for simpler subtasks

## Recommended Architecture for Engrave

```
┌─────────────────────────────────────┐
│         Engrave Desktop App         │
│                                     │
│  Settings:                          │
│  ┌─────────────────────────────┐    │
│  │ API Key: sk-ant-...        │    │
│  │ Model: haiku-4.5 (default) │    │
│  │ Budget: $5.00/session      │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌──────────────────┐               │
│  │ claude-agent-sdk │               │
│  │ (Python package) │               │
│  │                  │               │
│  │ ANTHROPIC_API_KEY│               │
│  │ set from user's  │               │
│  │ stored key       │               │
│  └────────┬─────────┘               │
│           │                         │
│  ┌────────▼─────────┐               │
│  │ Bundled CLI       │               │
│  │ (included in SDK) │               │
│  └────────┬─────────┘               │
└───────────┼─────────────────────────┘
            │
            ▼
    Anthropic API (direct)
```

### First-run experience

1. App detects no API key configured
2. Shows setup dialog: "Enter your Anthropic API key"
3. Link to platform.claude.com to create account and get key
4. Key stored in OS keychain (macOS Keychain / Windows Credential Manager)
5. Optional: model preference and budget cap settings

### Key decisions for implementation

1. **Use `claude-agent-sdk` Python package** — not raw `claude -p` subprocess
2. **API key only** — no OAuth, no subscription piggybacking
3. **Default to Haiku 4.5** — cheapest, still capable for music notation tasks
4. **Allow model upgrade** — let users pick Sonnet/Opus in settings
5. **Budget caps** — configurable per-session spending limit
6. **Secure key storage** — OS keychain, never plaintext config files

## Sources

- [Agent SDK Overview](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Authentication — Claude Code Docs](https://code.claude.com/docs/en/authentication)
- [Legal and Compliance — Claude Code Docs](https://code.claude.com/docs/en/legal-and-compliance)
- [Rate Limits — Claude API Docs](https://platform.claude.com/docs/en/api/rate-limits)
- [Pricing — Claude API Docs](https://platform.claude.com/docs/en/about-claude/pricing)
- [CLI Reference — Claude Code Docs](https://code.claude.com/docs/en/cli-reference)
- [claude-agent-sdk on PyPI](https://pypi.org/project/claude-agent-sdk/)
- [GitHub Issue #6536: OAuth token support in SDK](https://github.com/anthropics/claude-code/issues/6536)
