"""ToyScreen configuration: one switch per deliberate weakness.

Every flag is named for the weakness it turns ON. ``True`` means vulnerable,
``False`` means the matching defence is active. Change one flag at a time and
compare attack success rates: that is the controlled experiment Module 08 uses.

FICTIONAL TRAINING SOFTWARE. Never point it at real résumés or real people.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields

# Map each flag to the OWASP Top 10 for LLM Applications (2025) item it exercises.
OWASP_MAP = {
    "unpinned_model": "LLM03 Supply Chain",
    "pass_hidden_text": "LLM01 Prompt Injection (indirect) / LLM08",
    "no_delimiting": "LLM01 Prompt Injection",
    "secrets_in_prompt": "LLM07 System Prompt Leakage / LLM02",
    "unlabelled_vector_store": "LLM08 Vector and Embedding Weaknesses",
    "unapproved_notes": "LLM04 Data and Model Poisoning",
    "llm_score_is_final": "LLM09 Misinformation (and LLM01 impact)",
    "unrestricted_update_stage": "LLM06 Excessive Agency",
    "unrestricted_send_email": "LLM06 Excessive Agency",
    "model_written_sql": "LLM05 Improper Output Handling",
    "raw_html_output": "LLM05 Improper Output Handling",
    "all_candidates_in_chat_context": "LLM02 Sensitive Information Disclosure",
    "no_resource_limits": "LLM10 Unbounded Consumption",
}


@dataclass
class Flags:
    unpinned_model: bool = True
    pass_hidden_text: bool = True
    no_delimiting: bool = True
    secrets_in_prompt: bool = True
    unlabelled_vector_store: bool = True
    unapproved_notes: bool = True
    llm_score_is_final: bool = True
    unrestricted_update_stage: bool = True
    unrestricted_send_email: bool = True
    model_written_sql: bool = True
    raw_html_output: bool = True
    all_candidates_in_chat_context: bool = True
    no_resource_limits: bool = True

    @classmethod
    def vulnerable(cls) -> "Flags":
        return cls()

    @classmethod
    def hardened(cls) -> "Flags":
        return cls(**{f.name: False for f in fields(cls)})

    def with_(self, **changes: bool) -> "Flags":
        d = asdict(self)
        unknown = set(changes) - set(d)
        if unknown:
            raise KeyError(f"unknown flag(s): {sorted(unknown)}")
        d.update(changes)
        return Flags(**d)


@dataclass
class Settings:
    flags: Flags = field(default_factory=Flags.vulnerable)
    # "mock" (seeded, instant), "llamacpp" (Qwen2.5-0.5B-Instruct GGUF on CPU) or
    # "hf" (Qwen2.5-0.5B-Instruct via transformers on CPU).
    backend: str = "mock"
    seed: int = 0
    # Limits used only when no_resource_limits is False.
    max_resume_chars: int = 8000
    max_upload_bytes: int = 2_000_000
    max_output_tokens: int = 512
    max_agent_steps: int = 4
    max_requests_per_user: int = 200
    db_path: str = ":memory:"
    log_path: str = "logs/toyscreen.jsonl"


def load_settings(mode: str | None = None, overrides: dict | None = None) -> Settings:
    """Build settings from a mode ("vulnerable"/"hardened"), a JSON file, or env vars.

    TOYSCREEN_MODE=vulnerable|hardened, TOYSCREEN_FLAGS='{"no_delimiting": false}',
    TOYSCREEN_BACKEND=mock|llamacpp|hf, TOYSCREEN_SEED=0.
    """
    mode = mode or os.environ.get("TOYSCREEN_MODE", "vulnerable")
    flags = Flags.hardened() if mode == "hardened" else Flags.vulnerable()
    env_flags = os.environ.get("TOYSCREEN_FLAGS")
    if env_flags:
        flags = flags.with_(**json.loads(env_flags))
    if overrides:
        flags = flags.with_(**overrides)
    return Settings(
        flags=flags,
        backend=os.environ.get("TOYSCREEN_BACKEND", "mock"),
        seed=int(os.environ.get("TOYSCREEN_SEED", "0")),
    )
