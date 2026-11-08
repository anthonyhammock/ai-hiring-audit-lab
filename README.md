# AI Hiring Audit Lab

> **INTENTIONALLY VULNERABLE TRAINING CODE. SYNTHETIC DATA ONLY.**
> This repository contains deliberately weak software (a résumé screener, an MCP agent, an HR helper agent, an OAuth/OIDC lab) built for teaching. Run it only in your own GitHub Codespace or Colab runtime. Never expose it to the internet, never put real personal data into it, and never use these techniques or tools against any system you do not own or have written permission to test. Every person, email address, phone number, salary and secret in it is invented.

Companion labs for BlissPoint Analytics' course *Offensive Security and AI Red Teaming for People Systems*. Everything runs in your browser on a hosted runtime (GitHub Codespaces or Google Colab): nothing is installed on your own computer. The course also hosts browser-only versions of several labs; this repository is the "run it yourself" route the lessons point to.

## Lab index

| Folder | Module and lesson | What it is |
|---|---|---|
| [`toyscreen/`](toyscreen/) | **Module 08**, Lesson 01 (lab foundation) and Lessons 02–12; target for Module 11 | ToyScreen starter: a deliberately vulnerable LLM résumé screener with one on/off flag per OWASP LLM 2025 weakness, a seeded mock model or Qwen2.5-0.5B on CPU, synthetic PDFs with hidden text, and an ASR command line |
| [`m11-redteam-tools/`](m11-redteam-tools/) | **Module 11**, Lessons 02 (garak), 03 (PyRIT), 04 (promptfoo and CI), 05 (ASR) | Working garak, PyRIT and promptfoo configs against ToyScreen or a tiny local model, plus [`.github/workflows/llm-redteam-regression.yml`](.github/workflows/llm-redteam-regression.yml), a CI gate that really starts the target |
| [`m15-mcp-agent/`](m15-mcp-agent/) | **Module 15**, Lessons 01–03 and assignment Part D | An MCP tool server on the official MCP Python SDK (`mcp` 2.3.0, protocol revision 2026-07-28), an agent host with host policies, a JSON-RPC message inspector and a human-approval drill |
| [`m16-audit-validation/`](m16-audit-validation/) | **Module 16**, Lesson 04 | The "HR helper" agent with seeded defects, a variant builder with blind mode, a test harness, and sensitivity/specificity/kappa tools |
| [`m17-identity/oidc-lab/`](m17-identity/oidc-lab/) | **Module 17**, Lesson 02 and assignment Part B | The IdP-plus-client template: a small OpenID Connect provider and client with switchable weaknesses and a flow trace |
| [`m17-identity/secrets-scanning/`](m17-identity/secrets-scanning/) | **Module 17**, Lesson 03 step 1 and assignment Part C | Plant, find and remove fake secrets with gitleaks in a public fork you own |
| [`m21-fairness-dataset/`](m21-fairness-dataset/) | **Module 21** assignment (and Lessons 02–04) | The synthetic applicant dataset (CSV, vendor summary, benchmark) with a data dictionary |
| [`notebooks/`](notebooks/) | Modules 11, 13, 09 and 16 | The original Colab notebooks listed below |

Each folder has its own README with Codespaces and Colab steps.

## Open in Google Colab

| Notebook | Open |
|---|---|
| garak against a model you run | [Open in Colab](https://colab.research.google.com/github/anthonyhammock/ai-hiring-audit-lab/blob/main/notebooks/01-garak-own-model.ipynb) |
| PyRIT against a toy target | [Open in Colab](https://colab.research.google.com/github/anthonyhammock/ai-hiring-audit-lab/blob/main/notebooks/02-pyrit-own-target.ipynb) |
| Adverse impact and power | [Open in Colab](https://colab.research.google.com/github/anthonyhammock/ai-hiring-audit-lab/blob/main/notebooks/03-adverse-impact-and-power.ipynb) |
| Membership inference (toy) | [Open in Colab](https://colab.research.google.com/github/anthonyhammock/ai-hiring-audit-lab/blob/main/notebooks/04-membership-inference-toy.ipynb) |
| Measurement reliability | [Open in Colab](https://colab.research.google.com/github/anthonyhammock/ai-hiring-audit-lab/blob/main/notebooks/05-measurement-reliability.ipynb) |

Colab asks you to sign in with a Google account. The free runtime is enough for every notebook (garak with `gpt2` runs on CPU).

## Open in GitHub Codespaces

[Open in GitHub Codespaces](https://codespaces.new/anthonyhammock/ai-hiring-audit-lab?quickstart=1)

The dev container (`.devcontainer/devcontainer.json`) uses Python 3.11 and Node.js 22, and installs garak 0.17.1, PyRIT 1.1.0, the MCP Python SDK 2.3.0, PyJWT, pandas, statsmodels, scikit-learn, SciPy and JupyterLab. Lab servers bind to `127.0.0.1`; if you open one through the **Ports** tab, keep its visibility **Private**. Open a notebook in the Codespace's editor, or run tools from its terminal, for example:

```bash
python -m garak --target_type huggingface --target_name gpt2 --probes encoding --generations 2
```

Stop the Codespace when you finish; GitHub bills or counts usage by the hour against your account's quota.

## Versions

Pinned and tested on 2026-11-07/08 (Python 3.11): garak 0.17.1, PyRIT 1.1.0, promptfoo 0.125.1, MCP Python SDK 2.3.0, PyJWT 2.15.1, gitleaks 8.30.1, pypdf 7.0.0. Newer releases may change command-line flags or APIs. Each folder's README says exactly what was run.

## Licence

Code: MIT. Documentation and notebook prose: CC BY 4.0. See `LICENSE`.
