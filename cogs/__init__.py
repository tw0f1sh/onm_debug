# cogs/__init__.py

try:
    from .tournament_cog import TournamentCog
    __all__ = ['TournamentCog']
except ImportError as e:
    print(f"Warning: Could not import TournamentCog: {e}")
    __all__ = []