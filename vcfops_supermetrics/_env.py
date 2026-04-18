"""Backwards-compat re-export. The canonical implementation lives in
vcfops_common._env. All new code should import from there directly.
"""
from vcfops_common._env import load_dotenv, _parse_into_environ  # noqa: F401

__all__ = ["load_dotenv"]
