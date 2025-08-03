"""
Orga Panel - Haupt Control Panel
"""

import discord
import logging

logger = logging.getLogger(__name__)

class OrgaControlPanel(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        
        self.create_match.custom_id = "orga_create_match"
        self.refresh_panel.custom_id = "orga_refresh_panel"
        
    @discord.ui.button(label='🆕 Neues Match erstellen', style=discord.ButtonStyle.primary, row=0, custom_id="orga_create_match")
    async def create_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._has_orga_role(interaction.user):
            await interaction.response.send_message("❌ Du benötigst die Event Orga Rolle!", ephemeral=True)
            return
            
        from ui.orga_match_creation import MatchCreationHandler
        handler = MatchCreationHandler(self.bot)
        await handler.start_match_creation(interaction)
    
    @discord.ui.button(label='🔄 Panel aktualisieren', style=discord.ButtonStyle.gray, row=1, custom_id="orga_refresh_panel")
    async def refresh_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._has_orga_role(interaction.user):
            await interaction.response.send_message("❌ Du benötigst die Event Orga Rolle!", ephemeral=True)
            return
            
        from utils.embed_builder import EmbedBuilder
        embed = EmbedBuilder.create_orga_panel_embed(self.bot)
        await interaction.response.edit_message(embed=embed, view=self)
    
    def _has_orga_role(self, user) -> bool:
        if not self.bot.EVENT_ORGA_ROLE_ID:
            return False
        return any(role.id == self.bot.EVENT_ORGA_ROLE_ID for role in user.roles)