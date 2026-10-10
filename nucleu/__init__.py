"""Nucleul Regatului Partiturilor: încărcare, descriere în cuvinte, Braille, recunoaștere."""
VERSIUNE = '0.1.0'
try:  # la compilarea pe GitHub se scrie aici versiunea exactă (0.1.<numărul build-ului>)
    from ._build import VERSIUNE  # noqa: F401
except ImportError:
    pass
