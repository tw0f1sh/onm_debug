"""
Orga Embeds
"""

import discord
import json
import logging
from typing import List, Tuple
from datetime import datetime
from .config_helper import ConfigHelper

logger = logging.getLogger(__name__)

class OrgaEmbeds:
    
    
    @staticmethod
    def create_orga_panel_embed(bot) -> discord.Embed:
        
        embed = discord.Embed(
            title="🏆 Tournament Control Panel",
            description=f"**{bot.TOURNAMENT_NAME}** - Event Organisation",
            color=discord.Color.gold()
        )
        
        teams = bot.get_all_teams()
        active_teams = len([t for t in teams if t[4]])
        
        matches_current_week = bot.db.get_matches_by_week(bot.CURRENT_WEEK)
        completed_matches = len([m for m in matches_current_week if m[10] == 'confirmed'])
        
        embed.add_field(
            name="📊 Aktuelle Statistiken",
            value=f"👥 **Teams:** {active_teams} aktiv / {len(teams)} gesamt (aus config.json)\n"
                  f"🏆 **Matches (Woche {bot.CURRENT_WEEK}):** {completed_matches}/{len(matches_current_week)} abgeschlossen\n"
                  f"📅 **Aktuelle Woche:** {bot.CURRENT_WEEK}",
            inline=False
        )
        
        embed.set_footer(text="Nur Event Orga Mitglieder können diese Buttons verwenden")
        embed.timestamp = discord.utils.utcnow()
        
        return embed