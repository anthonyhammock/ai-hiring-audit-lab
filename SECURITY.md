# Security policy

## What this repository is

Teaching notebooks for an AI red-teaming course. They run security tools (garak, PyRIT) against small models you run yourself and against toy targets defined in the notebooks. All data is synthetic. Nothing here should be pointed at a system you do not own or have written permission to test.

## Reporting a vulnerability

If you find a security problem in this repository itself (for example a dependency pin with a known vulnerability, or a notebook that could leak a secret), please report it privately through GitHub's "Report a vulnerability" button on the Security tab of this repository, rather than in a public issue.

Please include the file, the problem, and how to reproduce it. We aim to acknowledge reports within 5 business days.

## Out of scope

- Findings in the deliberately weak toy targets inside the notebooks: they are meant to fail.
- Vulnerabilities in garak, PyRIT or other upstream tools: report those to their own projects.
