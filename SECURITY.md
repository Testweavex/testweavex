# Security Policy

## Supported versions

TestWeaveX is pre-1.0. Only the latest release receives security fixes.

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
| < 0.1   | No        |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through
[GitHub Security Advisories](https://github.com/Testweavex/testweavex/security/advisories/new),
or email **pankaj.shiwotia@gmail.com** if you cannot use that form.

Please include:

- What the issue is and why it is a security problem
- Steps to reproduce, or a proof-of-concept
- Affected version or commit
- Any suggested fix

You can expect an acknowledgement within 5 working days and a status update at
least every 10 working days until the report is resolved. If the report is
accepted, we will agree a disclosure timeline with you and credit you in the
advisory unless you prefer otherwise.

## Handling secrets

TestWeaveX handles credentials in three places. Understanding them helps when
assessing whether something is a vulnerability.

**LLM API keys.** Set in `testweavex.config.yaml` under `llm.api_key`. Prefer
`${ENV_VAR}` interpolation over literal keys so nothing sensitive is committed:

```yaml
llm:
  api_key: ${ANTHROPIC_API_KEY}
```

**Result server tokens.** Passed via `--token` or `TESTWEAVEX_TOKEN`. Prefer the
environment variable — CLI arguments are visible to other processes on the same
host and are commonly captured in CI logs.

**External TCM credentials.** TestRail and Xray credentials live in the `tcm`
block of the config file. Use `${ENV_VAR}` interpolation for these too.

Add `.testweavex/` and `testweavex.config.yaml` to `.gitignore` if your config
contains literal credentials. The local results database at
`.testweavex/results.db` stores test case content and run history; treat it with
the same sensitivity as your test suite.

## Scope

In scope: authentication and authorisation flaws in the result server, injection
or path-traversal issues in generation and step-definition writing, credential
leakage in logs or storage, and vulnerabilities in the bundled web UI.

Out of scope: vulnerabilities in third-party LLM providers, findings that
require an already-compromised developer machine, and issues in dependencies
that have no exploitable path through TestWeaveX. Report those upstream.
