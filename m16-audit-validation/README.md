# Module 16, Lesson 04: validating the audit itself

> **INTENTIONALLY VULNERABLE TRAINING SOFTWARE. FICTIONAL DATA ONLY.**
> The "HR helper" agent below has defects planted on purpose so you can measure how well *your audit procedure* finds them. Every employee, salary and address is invented; `send_email` only appends to an in-memory outbox. Run it only in your own Codespace or Colab runtime.

**Course map:** Module 16 (Measurement science for AI evaluation), Lesson 04, Lab steps 1–8. It reuses the MCP pattern from Module 15 and the statistics from Module 16 Lesson 03.

## What is here

| File | Purpose | Lesson step |
|---|---|---|
| `hr_helper.py` | The HR helper: an MCP server (official MCP Python SDK, `mcp==2.3.0`) with `read_policy(doc_id)`, `lookup_employee(name, caller_role)` and `send_email(to, body)`, plus a small host and a seeded mock model | 1 |
| `harness.py` | Runs your test cases against a variant; writes transcripts | 2, 5 |
| `examples/starter_tests.json` | Two starter test cases that show the format. They are deliberately **not** a complete audit: writing the rest is the exercise | 2 |
| `variants.py build` | Variant builder: 12 variants (3 defect classes × 3 trigger conditions, plus 3 clean controls) | 3 |
| `variants.py` blind labels | `build` shuffles the variants with a cryptographic RNG, labels them V01–V12 and seals the key in `.blind/key.json` (git-ignored) | 4 |
| `variants.py unblind findings.csv` | Sensitivity per class and overall, and specificity, each with a Wilson 95% interval | 6 |
| `stats.py kappa labels.csv` | Cohen's kappa and the confusion matrix for judge calibration | 7 |

The three defect classes are the ones the lesson names: the email tool runs without confirmation; `read_policy` output is placed into the instruction channel; `lookup_employee` ignores the caller's role. Within each class the three variants differ in *when* the defect fires, so some are much harder to find than others. Policy IDs to try include `HR-001` to `HR-003`, `OPS-104` and `OPS-220`; employees are listed in `hr_helper.py`.

There is no answer key in this repository. The mapping from V01–V12 to defects exists only in the `.blind/key.json` file that `build` creates in your own environment.

## Open it

**Codespaces:** open the repository in a Codespace ([link](https://codespaces.new/anthonyhammock/ai-hiring-audit-lab?quickstart=1)), then:

```bash
cd m16-audit-validation
pip install -r requirements.txt
python harness.py try examples/starter_tests.json   # practice on a clean configuration
```

**Colab:** open [`M16-Audit-Validation.ipynb`](https://colab.research.google.com/github/anthonyhammock/ai-hiring-audit-lab/blob/main/m16-audit-validation/M16-Audit-Validation.ipynb).

## The lab, step by step

1. **Write your procedure** (step 2): a checklist plus test cases in a JSON file such as `my_tests.json`, using the format in `harness.py`'s docstring. Add a `"class"` field to each test naming the defect class it targets. Freeze it (commit it) before step 3.
2. **Build and blind** (steps 3–4): ask a colleague to run `python variants.py build` in your Codespace, or run it yourself and do not open `.blind/`.
3. **Audit** (step 5): `python harness.py run V01 my_tests.json` for each variant, adding manual probes as your checklist says, or `python harness.py run-all my_tests.json` to produce `findings_auto.csv`. Record your final judgement per variant in `findings.csv` (`variant,defect_reported,class_reported`).
4. **Unblind** (step 6): `python variants.py unblind findings.csv`.
5. **Calibrate your judge** (step 7): sample 40 transcripts from `transcripts/`, label each by hand (`human`), copy the harness's `auto_finding` as `auto`, and run `python stats.py kappa labels.csv`.
6. **Write up** (step 8): methods and limitations, including what the seeded defects can and cannot tell you about real defects (the extrapolation problem in the lesson).

Module 11's tools can also be used: the HR helper is a plain Python function (`hr_helper.run_request`), so you can wrap it as a PyRIT or promptfoo target if you prefer.
