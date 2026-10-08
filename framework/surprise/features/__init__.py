"""Feature layer beside theory: the shared description of a query and the data it runs on."""

from .phi import Phi, make_phi
from .registry import Registry, default_registry
from .spec import SpecCheck, check_spec
from .units import unit_of, unit_parts
from .vocabulary import FeatureDef

__all__ = [
    "FeatureDef",
    "Phi",
    "Registry",
    "SpecCheck",
    "check_spec",
    "default_registry",
    "make_phi",
    "unit_of",
    "unit_parts",
]
