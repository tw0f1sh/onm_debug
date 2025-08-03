# ui/streamer_management.py
"""
Streamer Management - Import Wrapper für Rückwärtskompatibilität
REFACTORED: Alle Klassen sind jetzt in Untermodule aufgeteilt
"""

from .streamer_management.streamer_match_view import StreamerMatchView
from .streamer_management.team_side_selection_view import TeamSideSelectionView
from .streamer_management.stream_url_modal import StreamURLModal
from .streamer_management.streamer_match_manager import StreamerMatchManager

__all__ = [
    'StreamerMatchView',
    'TeamSideSelectionView',
    'StreamURLModal', 
    'StreamerMatchManager'
]