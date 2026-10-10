"""Hand-written harness fixture, not an LLM translation."""
from pathlib import Path

Path("report.dat").write_bytes(b"HELLO\n")
