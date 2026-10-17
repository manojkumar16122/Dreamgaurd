"""DreamGuard: reversible memory compilation for AI agents."""
from .engine import MemoryEngine
from .compiler import HeuristicCompressor, GroqCompressor, get_compressor

__version__ = "0.1.0"
__all__ = ["MemoryEngine", "HeuristicCompressor", "GroqCompressor", "get_compressor"]
