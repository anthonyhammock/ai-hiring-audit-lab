# Security policy

## What this repository is

Teaching labs for an AI red-teaming course. They contain **intentionally vulnerable** software (ToyScreen, the MCP agent, the HR helper, the OIDC lab) and run security tools (garak, PyRIT, promptfoo, gitleaks) against small models you run yourself and against those lab targets. All data is synthetic and every secret is fake. Nothing here should be pointed at a system you do not own or have written permission to test.

## Reporting a vulnerability

If you find a security problem in this repository itself (for example a dependency pin with a known vulnerability, or a notebook that could leak a secret), please report it privately through GitHub's "Report a vulnerability" button on the Security tab of this repository, rather than in a public issue.

Please include the file, the problem, and how to reproduce it. We aim to acknowledge reports within 5 business days.

## Out of scope

- Findings in the deliberately weak lab targets (`toyscreen/`, `m15-mcp-agent/`, `m16-audit-validation/`, `m17-identity/oidc-lab/`) or the toy targets inside the notebooks: they are meant to fail. Do report a weakness that escapes the lab, for example code that would send real email or reach the network when it should not.
- Vulnerabilities in garak, PyRIT or other upstream tools: report those to their own projects.
