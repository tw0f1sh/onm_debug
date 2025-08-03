"""
Orga Team Management - DEPRECATED - Teams werden via config.json verwaltet
"""

import logging

logger = logging.getLogger(__name__)

class TeamManagementHandler:
    def __init__(self, bot):
        self.bot = bot
        logger.warning("TeamManagementHandler is deprecated - use config.json for team management")
    
    async def start_team_management(self, interaction):
        await interaction.response.send_message(
            "❌ Team Management über UI ist deaktiviert!\n"
            "Teams werden jetzt über die config.json verwaltet.\n"
            "Verwende `!validate_teams` um die Konfiguration zu prüfen.",
            ephemeral=True
        )

class TeamManagementView: pass
class TeamRegistrationModal: pass
class TeamSelectionForEditView: pass
class TeamEditModal: pass
class TeamSelectionForDeleteView: pass
class DeleteConfirmationView: pass
class TeamSelectionForToggleView: pass