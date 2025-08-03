"""
Orga View - Legacy Compatibility File
"""

from .orga_panel import OrgaControlPanel
from .orga_match_creation import (
    MatchCreationHandler, 
    MatchCreationModal, 
    TeamSelectionView
)
from .orga_team_management import TeamManagementHandler
from .orga_settings import (
    SettingsView,
    MatchOverviewView
)

__all__ = [
    'OrgaControlPanel',
    'MatchCreationHandler',
    'MatchCreationModal', 
    'TeamSelectionView',
    'TeamManagementHandler',
    'SettingsView',
    'MatchOverviewView'
]