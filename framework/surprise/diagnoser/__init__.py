"""Diagnoser agent: turns high-surprise samples into candidate edits of the theory."""

from . import constants
from .diagnoser import Diagnoser

__all__ = ["constants", "Diagnoser"]
