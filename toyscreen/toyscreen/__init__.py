"""ToyScreen: a deliberately vulnerable LLM résumé screener for the Module 08 lab.

INTENTIONALLY VULNERABLE TRAINING SOFTWARE. FICTIONAL DATA ONLY.
Run it only in your own Codespace or Colab runtime. Never expose it to the internet
and never feed it real résumés.
"""
from .config import OWASP_MAP, Flags, Settings, load_settings
from .pipeline import LimitExceeded, ToyScreen

__all__ = ["Flags", "Settings", "load_settings", "ToyScreen", "LimitExceeded", "OWASP_MAP"]
