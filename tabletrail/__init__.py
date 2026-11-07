"""TableTrail: small, composable tools for inspecting CSV data locally."""

__version__ = "0.1.0"

from .contracts import Contract, load_contract
from .engine import analyze
from .compare import compare

__all__ = ["Contract", "analyze", "compare", "load_contract", "__version__"]
