"""Abstract DNA — structural matching that bypasses the semantic gap.

Zero dependency, pure stdlib. ~11ms per query. Zero hallucination.

Usage:
    from abstract_dna import pipeline
    
    result = pipeline("帮我装个nginx")
    print(result['signals'])   # {'action:setup': 0.3, ...}
"""

from .pipeline import pipeline, RuleChannel, DnaChannel
from .normalizer import normalize

__version__ = "1.0.0"
__all__ = ["pipeline", "RuleChannel", "DnaChannel", "normalize"]
