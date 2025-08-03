"""
Embed Builder - Main Entry Point
"""

import discord
import json
import logging
from typing import List, Tuple
from datetime import datetime


from .embeds.orga_embeds import OrgaEmbeds
from .embeds.match_embeds import MatchEmbeds
from .embeds.streamer_embeds import StreamerEmbeds
from .embeds.config_helper import ConfigHelper

logger = logging.getLogger(__name__)

class EmbedBuilder:
    
    
    
    @staticmethod
    def get_rules_url(bot=None) -> str:
        
        return ConfigHelper.get_rules_url(bot)
    
    
    @staticmethod
    def create_orga_panel_embed(bot) -> discord.Embed:
        return OrgaEmbeds.create_orga_panel_embed(bot)
    
    @staticmethod
    def create_private_match_embed_with_roles(match_id: int, team1_name: str, team2_name: str,
                                 match_date: str, map_name: str, team1_side: str, 
                                 team2_side: str, team1_role, team2_role, week: int, bot=None) -> discord.Embed:
        return MatchEmbeds.create_private_match_embed_with_roles(
            match_id, team1_name, team2_name, match_date, map_name, 
            team1_side, team2_side, team1_role, team2_role, week, bot
        )
    
    @staticmethod
    def create_public_match_embed_with_week(match_id: int, team1_name: str, team2_name: str,
                                match_date: str, map_name: str, team1_side: str, 
                                team2_side: str, week: int, bot=None) -> discord.Embed:
        return MatchEmbeds.create_public_match_embed_with_week(
            match_id, team1_name, team2_name, match_date, map_name,
            team1_side, team2_side, week, bot
        )
    
    @staticmethod
    def create_public_match_embed(match_id: int, team1_name: str, team2_name: str,
                                match_date: str, map_name: str, team1_side: str, 
                                team2_side: str, week: int, bot=None) -> discord.Embed:
        return MatchEmbeds.create_public_match_embed(
            match_id, team1_name, team2_name, match_date, map_name,
            team1_side, team2_side, week, bot
        )
    
    @staticmethod
    def create_updated_private_match_embed(match_data: Tuple, bot=None) -> discord.Embed:
        return MatchEmbeds.create_updated_private_match_embed(match_data, bot)
    
    @staticmethod
    def create_updated_public_match_embed(match_data: Tuple, bot=None) -> discord.Embed:
        return MatchEmbeds.create_updated_public_match_embed(match_data, bot)
    
    
    @staticmethod
    def create_streamer_match_embed(match_data: dict, streamers: List[dict] = None, bot=None) -> discord.Embed:
        return StreamerEmbeds.create_streamer_match_embed(match_data, streamers, bot)
    
    @staticmethod
    def create_public_embed_with_streamers(match_data: dict, streamers: List[dict], bot=None) -> discord.Embed:
        return StreamerEmbeds.create_public_embed_with_streamers(match_data, streamers, bot)
    
    @staticmethod
    def create_private_embed_with_streamers(match_data: dict, streamers: List[dict], bot=None) -> discord.Embed:
        return StreamerEmbeds.create_private_embed_with_streamers(match_data, streamers, bot)