# Module 11: garak, PyRIT and promptfoo on a free CPU

> **RED-TEAM TOOLS AGAINST YOUR OWN, INTENTIONALLY VULNERABLE LAB TARGET ONLY. FICTIONAL DATA.**
> Every config here points at `127.0.0.1`: ToyScreen (the Module 08 starter, `../toyscreen`) or a tiny model you run yourself. Do not point these tools at any system you do not own or have written permission to test, and do not use a commercial API without reading its usage policy.

**Course map:** Module 11, Lesson 02 (garak), Lesson 03 (PyRIT), Lesson 04 (promptfoo and CI), Lesson 05 (measuring ASR), and the module assignment.

**Why not llama3 70B?** It needs a large GPU. These configs run on a free 2-core Codespace or Colab CPU by using (a) ToyScreen with its seeded mock model, which answers instantly, or (b) Qwen2.5-0.5B-Instruct (Apache-2.0) served locally by llama.cpp. The lesson's Ollama examples work the same way if you have Ollama; just change the target.

## Versions (checked against the installed tools)

| Tool | Version | What was run here |
|---|---|---|
| garak | 0.17.1 | `-t test.Repeat` plumbing run; `--config garak/toyscreen_rest.yaml` full scan against ToyScreen over REST |
| PyRIT | 1.1.0 | `pyrit/attack_toyscreen.py` (`OpenAIChatTarget` → ToyScreen's OpenAI-compatible endpoint, `SubStringScorer`, `PromptSendingAttack`); `pyrit_scan --help` |
| promptfoo | 0.125.1 (Node.js ≥ 22.22) | `eval` of both configs; regression suite with `--repeat 10` (exit 100 against vulnerable ToyScreen, exit 0 against hardened); `validate` on all three configs |
| llama-cpp-python | 0.3.36 | built and imported; the Qwen GGUF download could not be tested in the authoring sandbox, so `scripts/start_local_model.sh` is untested end to end |

## Files

| Path | Lesson | Purpose |
|---|---|---|
| `scripts/start_lab_assistant.sh`, `scripts/stop_lab_assistant.sh` | 02–05 | Start/stop ToyScreen's chat endpoint on `127.0.0.1:8080` (`TOYSCREEN_MODE=vulnerable|hardened`, `TOYSCREEN_BACKEND=mock|llamacpp`) |
| `scripts/start_local_model.sh` | 02–04 | Serve Qwen2.5-0.5B-Instruct on `127.0.0.1:8081/v1` (OpenAI-compatible) with llama.cpp |
| `garak/toyscreen_rest.yaml` | 02 | garak `RestGenerator` config for your own app's endpoint (the lesson's faded example, filled in) |
| `pyrit/attack_toyscreen.py` | 03 | PyRIT single-turn attacks with a ground-truth scorer and Wilson intervals |
| `promptfoo/promptfooconfig.yaml` | 04 | promptfoo as an evaluation harness, deterministic assertions only |
| `promptfoo/redteam/regression.yaml` | 04 | Confirmed-attack regression suite (REG-014 and friends) |
| `promptfoo/redteam/promptfooconfig.redteam.yaml` | 04 | promptfoo red-team generation using the local model, not promptfoo's cloud |
| `../.github/workflows/llm-redteam-regression.yml` | 04 | The CI example, working: it starts ToyScreen on the runner and runs the regression suite |

## Open it

**Codespaces** ([open](https://codespaces.new/anthonyhammock/ai-hiring-audit-lab?quickstart=1)). The dev container already installs garak 0.17.1 and PyRIT 1.1.0, and Node.js is needed for promptfoo (`npx` downloads it on first use). From the repository root:

```bash
pip install -r toyscreen/requirements.txt
cd m11-redteam-tools
bash scripts/start_lab_assistant.sh
```

**Colab:** open [`M11-Red-Team-Tools.ipynb`](https://colab.research.google.com/github/anthonyhammock/ai-hiring-audit-lab/blob/main/m11-redteam-tools/M11-Red-Team-Tools.ipynb). It runs ToyScreen in the background inside the runtime and drives garak and PyRIT from cells. Colab has Node.js, so the promptfoo cells work too.

## Lesson 02: garak

```bash
# 1. Plumbing, no model at all
python -m garak -t test.Repeat -S probes.encoding.InjectBase64 -g 1
# 2. Your own app through its endpoint (ToyScreen must be running)
python -m garak --config garak/toyscreen_rest.yaml --report_prefix toyscreen_baseline
# 3. A small model directly (Colab, where PyTorch is preinstalled)
python -m garak --target_type huggingface --target_name Qwen/Qwen2.5-0.5B-Instruct \
  --spec probes.promptinject.HijackHateHumans --generations 2 --seed 42
```

garak writes reports to `~/.local/share/garak/garak_runs/`. Expect the mock model to **pass** garak's generic probes: it only fails in the hiring-specific ways ToyScreen was built to show. That is a useful lesson about coverage: a generic scanner is not a test of your application's own risks. Run step 2 with `TOYSCREEN_BACKEND=llamacpp` (after `bash scripts/start_local_model.sh` has downloaded the model, or `pip install -r ../toyscreen/requirements-llamacpp.txt`) to see a real model's behaviour.

## Lesson 03: PyRIT

```bash
export OPENAI_CHAT_ENDPOINT="http://127.0.0.1:8080/v1"   # ToyScreen's OpenAI-compatible endpoint
export OPENAI_CHAT_KEY="not-needed"
export OPENAI_CHAT_MODEL="toyscreen"
python pyrit/attack_toyscreen.py --repeats 10
```

To use the local Qwen model as the target instead (for example for multi-turn attacks that need a model to talk to), set `OPENAI_CHAT_ENDPOINT=http://127.0.0.1:8081/v1` and `OPENAI_CHAT_MODEL=qwen2.5-0.5b-instruct`. A 0.5B model makes a weak adversarial model and judge; keep scorers ground-truth where you can.

## Lesson 04: promptfoo and CI

```bash
npx -y promptfoo@0.125.1 eval -c promptfoo/promptfooconfig.yaml --no-cache
PROMPTFOO_PASS_RATE_THRESHOLD=100 npx -y promptfoo@0.125.1 eval \
  -c promptfoo/redteam/regression.yaml --repeat 10 --no-cache -o results.json; echo "exit code $?"
```

Against vulnerable ToyScreen the regression suite fails (exit code 100); restart it hardened (`bash scripts/stop_lab_assistant.sh; TOYSCREEN_MODE=hardened bash scripts/start_lab_assistant.sh`) and it passes (exit code 0). The GitHub Actions workflow does exactly this on every pull request that touches `toyscreen/` or this folder. For red-team generation with a local model, follow the comments at the top of `promptfoo/redteam/promptfooconfig.redteam.yaml`.

## Lesson 05: measuring ASR

Every script prints counts and Wilson intervals; promptfoo's `--repeat` summary prints its own interval. ToyScreen's `python -m toyscreen asr ...` (see `../toyscreen/README.md`) gives attack and matched-control rates for the indirect-injection attacks.
