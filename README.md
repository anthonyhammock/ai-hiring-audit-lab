# AI Hiring Audit Lab: online notebooks

Companion notebooks for BlissPoint Analytics' course *Offensive Security and AI Red Teaming for People Systems*. Everything runs in your browser on a hosted runtime: nothing is installed on your own computer.

The course's practicum apps (resume screener, chatbot interviewer, ML scorer) and the module 15–17 labs are hosted inside the course itself. This repository holds the parts that need a real Python tool: garak, PyRIT, and statistics notebooks.

All data here is synthetic. Use these tools only against models and apps you own or the toy targets defined in the notebooks.

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

The dev container (`.devcontainer/devcontainer.json`) uses Python 3.11 and installs garak 0.17.1, PyRIT 1.1.0, scikit-learn, SciPy and JupyterLab. Open a notebook in the Codespace's editor, or run tools from its terminal, for example:

```bash
python -m garak --target_type huggingface --target_name gpt2 --probes encoding --generations 2
```

Stop the Codespace when you finish; GitHub bills or counts usage by the hour against your account's quota.

## Versions

Pinned and tested on 2026-11-07: garak 0.17.1, PyRIT 1.1.0 (Python 3.11). Newer releases may change command-line flags or APIs.

## Licence

Code: MIT. Documentation and notebook prose: CC BY 4.0. See `LICENSE`.
