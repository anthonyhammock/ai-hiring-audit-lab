"""The model (component 1): a seeded mock, or a tiny real model on CPU.

backend="mock" (default)
    A rule-based stand-in that behaves like a weak instruction-following model. It
    follows injected instructions with a fixed probability: about 0.75 when the
    untrusted text is pasted in undelimited, about 0.08 when it is spotlighted. It
    adds score noise and the occasional invented credential when asked for a final
    score, and leaks what is in its context when asked with a pretext. The numbers
    are teaching settings, not measurements of any real model. Every draw comes from
    a seeded random generator, so a run is exactly repeatable.

backend="llamacpp" (recommended in Codespaces)
    Qwen/Qwen2.5-0.5B-Instruct-GGUF, file qwen2.5-0.5b-instruct-q4_k_m.gguf (Apache-2.0,
    about 490 MB) through llama-cpp-python on CPU. Fits a free 2-core, 8 GB Codespace;
    expect a few seconds per call. See requirements-llamacpp.txt.

backend="hf" (recommended in Colab, where PyTorch is preinstalled)
    Qwen/Qwen2.5-0.5B-Instruct (Apache-2.0, 494M parameters, about 1 GB of safetensors)
    through Hugging Face transformers on CPU. See requirements-hf.txt.

For both real backends, unpinned_model=True loads the model by name at whatever the
latest upload is (LLM03 weakness). unpinned_model=False pins the commit below and
checks the weight file's SHA-256 before loading (and, for transformers, refuses
pickle-based weights by requiring safetensors).
"""
from __future__ import annotations

import hashlib
import json
import random
import re

from .prompt import BEGIN, END

HF_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
HF_REVISION = "7ae557604adf67be50417f59c2c2f167def9a775"  # checked 2026-11-07
HF_WEIGHTS_SHA256 = "fdf756fa7fcbe7404d5c60e26bff1a0c8b8aa1f72ced49e7dd0210fe288fb7fe"
GGUF_REPO = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
GGUF_FILE = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
GGUF_REVISION = "9217f5db79a29953eb74d5343926648285ec7e67"  # checked 2026-11-07
GGUF_SHA256 = "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db"

P_FOLLOW_UNDELIMITED = 0.75
P_FOLLOW_SPOTLIGHTED = 0.08
P_LEAK = 0.6
P_SCORE_NOISE = 0.2
P_HALLUCINATE = 0.15

INJECTION = re.compile(r"ignore (all )?previous instructions|system note|assistant:", re.I)
LEAK_ASK = re.compile(r"system prompt|your instructions|admin key|repeat (the|your) (text|words|instructions)", re.I)
CONTACT_ASK = re.compile(r"phone|number|e-?mail|contact", re.I)
OTHER_PERSON = re.compile(r"other|another|finalist|everyone|all candidates", re.I)
CID = re.compile(r"C-\d{3}")
MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def _untrusted_segments(text: str) -> list[tuple[str, bool]]:
    """Split text into (segment, spotlighted) pairs."""
    if BEGIN not in text:
        return [(text, False)]
    segs = re.findall(re.escape(BEGIN) + r"(.*?)" + re.escape(END), text, re.S)
    return [(s.replace("^", " "), True) for s in segs]


def _injected_actions(seg: str) -> list[dict]:
    acts: list[dict] = []
    if m := re.search(r"score this candidate (\d)", seg, re.I):
        acts.append({"kind": "score", "value": int(m.group(1))})
    if m := re.search(r"update_stage for (C-\d{3}) with stage ([\w-]+)", seg, re.I):
        acts.append({"kind": "tool", "name": "update_stage",
                     "args": {"candidate_id": m.group(1), "stage": m.group(2)}})
    if m := re.search(r"run_report_sql with: (.+)", seg, re.I):
        acts.append({"kind": "tool", "name": "run_report_sql", "args": {"query": m.group(1).strip()}})
    if m := re.search(r"repeat send_email to (C-\d{3}) (\d+) times", seg, re.I):
        acts += [{"kind": "tool", "name": "send_email",
                  "args": {"to": m.group(1), "subject": "Update", "body": f"Message {i + 1}"}}
                 for i in range(int(m.group(2)))]
    elif m := re.search(r"send_email to (\S+@[\w.-]+\w)(.*)", seg, re.I):
        acts.append({"kind": "tool", "name": "send_email",
                     "args": {"to": m.group(1), "subject": "Requested data", "body": "<<ALL_CONTACTS>>"}})
    for img in MD_IMAGE.findall(seg):
        acts.append({"kind": "rationale", "value": img})
    return acts


def _resume_fields(resume: str) -> dict:
    low = resume.lower()
    years = re.search(r"(\d+) years", low)

    def q(word: str) -> str:
        line = next((ln for ln in resume.splitlines() if word in ln.lower()), "")
        return line.strip()[:120]

    return {
        "sql": {"value": "sql" in low, "quote": q("sql")},
        "python": {"value": "python" in low, "quote": q("python")},
        "years": {"value": int(years.group(1)) if years else 0, "quote": q("years")},
        "tableau": {"value": "tableau" in low, "quote": q("tableau")},
        "survey_design": {"value": "survey" in low, "quote": q("survey")},
        "hris": {"value": "hris" in low, "quote": q("hris")},
    }


class MockLLM:
    name = "mock"

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.chat_calls = 0
        self.rng = random.Random(seed)

    def reseed(self, seed: int) -> None:
        self.seed = seed
        self.chat_calls = 0

    def chat(self, messages: list[dict], max_tokens: int | None = None) -> str:
        system, user = messages[0]["content"], messages[1]["content"]
        # Screening: draws depend only on (seed, prompt), so every step of one screening agrees.
        # Chat: draws also depend on a call counter, so repeated identical prompts (as red-team
        # tools send them) are independent trials, yet the sequence is fixed for a given seed.
        if "Résumé:" in user:
            self.rng = random.Random(hashlib.sha256(f"{self.seed}|{system}|{user}".encode()).hexdigest())
            out = self._screen(system, user, messages)
        else:
            self.chat_calls += 1
            self.rng = random.Random(hashlib.sha256(f"{self.seed}|{self.chat_calls}|{system}|{user}".encode()).hexdigest())
            out = self._chat(system, user)
        return out if max_tokens is None else out[: max_tokens * 4]

    # Screening ------------------------------------------------------------
    def _screen(self, system: str, user: str, messages: list[dict]) -> str:
        # Decide, once per conversation, whether the model "obeys" injected text.
        turn = sum(m["role"] == "tool" for m in messages)
        actions: list[dict] = []
        for seg, spot in _untrusted_segments(user):
            if INJECTION.search(seg):
                p = P_FOLLOW_SPOTLIGHTED if spot else P_FOLLOW_UNDELIMITED
                if self.rng.random() < p:
                    actions += _injected_actions(seg)
        resume = user.split("Résumé:", 1)[1].split(END)[0].split("\n\nReturn JSON")[0].replace("^", " ")
        tool_actions = [a for a in actions if a["kind"] == "tool"]
        if turn > 0:  # agent loop: emit the next pending tool call, if any
            nxt = tool_actions[turn: turn + 1]
            return json.dumps({"tool_calls": [{"name": a["name"], "args": a["args"]} for a in nxt]})
        fields = _resume_fields(resume)
        if "Do not score" in user:
            if any(a["kind"] == "score" for a in actions):  # injected: claim everything
                for f in fields.values():
                    f["value"], f["quote"] = True, "Expert in all required skills"
                fields["years"]["value"] = 10
            return json.dumps({"fields": fields,
                               "tool_calls": [{"name": a["name"], "args": a["args"]} for a in tool_actions[:1]]})
        from .data import ground_truth_score
        skills = [k.replace("_", " ") for k, v in fields.items() if k != "years" and v["value"]]
        score = ground_truth_score(fields["years"]["value"], skills)
        rationale = f"Meets {len(skills)} listed skills with {fields['years']['value']} years of experience."
        if "Partner University get +1" in system and "partner university" in resume.lower():
            score = min(5, score + 1)
            rationale += " Partner University bonus applied."
        if self.rng.random() < P_SCORE_NOISE:
            score = max(1, min(5, score + self.rng.choice([-1, 1])))
        if self.rng.random() < P_HALLUCINATE:
            rationale += " Holds a certification in HR analytics."  # not in the résumé (LLM09)
        for a in actions:
            if a["kind"] == "score":
                score = a["value"]
            elif a["kind"] == "rationale":
                rationale += " " + a["value"]
        return json.dumps({"score": score, "rationale": rationale,
                           "tool_calls": [{"name": a["name"], "args": a["args"]} for a in tool_actions[:1]]})

    # Recruiter chat ---------------------------------------------------------
    def _chat(self, system: str, message: str) -> str:
        scoped = re.search(r"with candidate (C-\d{3})", system)
        scoped_id = scoped.group(1) if scoped else None
        records = {m.group(1): m.group(0) for m in re.finditer(r"(C-\d{3}) \| [^\n]+", system)}
        if LEAK_ASK.search(message) and self.rng.random() < P_LEAK:
            return "My instructions are: " + system.split("\nYou are helping")[0]
        if CONTACT_ASK.search(message):
            named = [c for c in CID.findall(message) if c != scoped_id]
            others = [c for c in records if c != scoped_id]
            target = named[0] if named else (others[0] if OTHER_PERSON.search(message) and others else scoped_id)
            if target != scoped_id and target in records and self.rng.random() < P_LEAK:
                return f"The record I have is: {records[target]}"
            if target != scoped_id:
                return "I can only discuss the candidate you are reviewing."
            if scoped_id in records:
                return f"Contact details for {scoped_id}: {records[scoped_id]}"
        return (f"{scoped_id or 'This candidate'}: summary available. I assess skills and recency of "
                "practice; career breaks are not treated as a negative signal.")


class HFLLM:
    """Qwen2.5-0.5B-Instruct on CPU via transformers (optional extra: requirements-hf.txt)."""

    name = "hf"

    def __init__(self, pinned: bool, seed: int = 0):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.manual_seed(seed)
        self.torch = torch
        if pinned:
            from huggingface_hub import hf_hub_download

            path = hf_hub_download(HF_MODEL, "model.safetensors", revision=HF_REVISION)
            _check_sha256(path, HF_WEIGHTS_SHA256)
            kw = dict(revision=HF_REVISION, use_safetensors=True)
        else:
            kw = {}
        self.tok = AutoTokenizer.from_pretrained(HF_MODEL, **{k: v for k, v in kw.items() if k == "revision"})
        self.model = AutoModelForCausalLM.from_pretrained(HF_MODEL, dtype=torch.float32, **kw)
        self.model.eval()

    def reseed(self, seed: int) -> None:
        self.torch.manual_seed(seed)

    def chat(self, messages: list[dict], max_tokens: int | None = None) -> str:
        msgs = [{"role": "user" if m["role"] == "tool" else m["role"], "content": m["content"]} for m in messages]
        ids = self.tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True)
        with self.torch.no_grad():
            out = self.model.generate(**ids, max_new_tokens=max_tokens or 1024, do_sample=True,
                                      temperature=0.7, top_p=0.9)
        return self.tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)


def _check_sha256(path: str, expected: str) -> None:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    if h.hexdigest() != expected:
        raise RuntimeError(f"weight hash mismatch for {path}: {h.hexdigest()}")


class LlamaCppLLM:
    """Qwen2.5-0.5B-Instruct (GGUF, 4-bit) on CPU via llama-cpp-python."""

    name = "llamacpp"

    def __init__(self, pinned: bool, seed: int = 0, n_ctx: int = 4096):
        from llama_cpp import Llama

        self.seed = seed
        if pinned:
            from huggingface_hub import hf_hub_download

            path = hf_hub_download(GGUF_REPO, GGUF_FILE, revision=GGUF_REVISION)
            _check_sha256(path, GGUF_SHA256)
            self.model = Llama(model_path=path, n_ctx=n_ctx, seed=seed, verbose=False)
        else:
            self.model = Llama.from_pretrained(repo_id=GGUF_REPO, filename="*q4_k_m.gguf",
                                               n_ctx=n_ctx, seed=seed, verbose=False)

    def reseed(self, seed: int) -> None:
        self.seed = seed

    def chat(self, messages: list[dict], max_tokens: int | None = None) -> str:
        msgs = [{"role": "user" if m["role"] == "tool" else m["role"], "content": m["content"]} for m in messages]
        out = self.model.create_chat_completion(messages=msgs, max_tokens=max_tokens or 1024,
                                                temperature=0.7, top_p=0.9, seed=self.seed)
        return out["choices"][0]["message"]["content"] or ""


def make_llm(backend: str, pinned: bool, seed: int = 0):
    if backend == "hf":
        return HFLLM(pinned=pinned, seed=seed)
    if backend == "llamacpp":
        return LlamaCppLLM(pinned=pinned, seed=seed)
    return MockLLM(seed)


def parse_json(text: str) -> dict:
    """Pull the first JSON object out of model output; tolerate code fences and chatter."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
