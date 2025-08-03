# ui/streamer_management/team_side_selection_view.py
"""
Team Side Selection View
"""


import discord
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class TeamSideSelectionView(discord.ui.View):
    
    
    def __init__(self, match_id: int, bot, match_data: Dict, existing_streamers: List[Dict]):
        super().__init__(timeout=300)
        self.match_id = match_id
        self.bot = bot
        self.match_data = match_data
        self.existing_streamers = existing_streamers
        
        
        team1_button = discord.ui.Button(
            label=f"{match_data['team1_name']} ({match_data['team1_side']})",
            style=discord.ButtonStyle.primary,
            emoji="📺",
            custom_id="team1_selection"
        )
        team1_button.callback = lambda i: self.select_team_side(i, 'team1')
        
        
        team2_button = discord.ui.Button(
            label=f"{match_data['team2_name']} ({match_data['team2_side']})",
            style=discord.ButtonStyle.primary,
            emoji="📺",
            custom_id="team2_selection"
        )
        team2_button.callback = lambda i: self.select_team_side(i, 'team2')
        
        self.add_item(team1_button)
        self.add_item(team2_button)
    
    async def select_team_side(self, interaction: discord.Interaction, team_side: str):
        
        
        existing_streamers = self.bot.db.get_match_streamers_detailed(self.match_id)
        
        for streamer_data in existing_streamers:
            if streamer_data['streamer_id'] == interaction.user.id:
                try:
                    await interaction.response.send_message(
                        "❌ You are already registered for this match! Please use 'Unregister as Streamer' first if you want to change your team selection.", 
                        ephemeral=True
                    )
                except:
                    pass
                return
        
        
        team_name = self.match_data['team1_name'] if team_side == 'team1' else self.match_data['team2_name']
        
        from .stream_url_modal import StreamURLModal
        modal = StreamURLModal(self.match_id, self.bot, self.match_data, team_side, team_name)
        
        try:
            await interaction.response.send_modal(modal)
        except discord.HTTPException as e:
            logger.error(f"Error showing stream URL modal: {e}")