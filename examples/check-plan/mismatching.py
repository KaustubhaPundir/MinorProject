"""Intentional one-byte mismatch for harness verification."""
from pathlib import Path

Path("report.dat").write_bytes(b"HALLO\n")
