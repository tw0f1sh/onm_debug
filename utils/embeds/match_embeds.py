"""
Match Embeds - WITH TIMEZONE SUPPORT
"""

import discord
import json
import logging
from typing import Tuple
from .config_helper import ConfigHelper
from utils.timezone_helper import TimezoneHelper

logger = logging.getLogger(__name__)

class MatchEmbeds:
    
    
    @staticmethod
    def create_private_match_embed_with_roles(match_id: int, team1_name: str, team2_name: str,
                                 match_date: str, map_name: str, team1_side: str, 
                                 team2_side: str, team1_role, team2_role, week: int, bot=None) -> discord.Embed:
        
        formatted_date = ConfigHelper.format_date_to_display(match_date)
        
        team1_side_with_icon = ConfigHelper.format_team_side_with_icon(team1_side, bot)
        team2_side_with_icon = ConfigHelper.format_team_side_with_icon(team2_side, bot)
        
        # TIMEZONE SUPPORT: Timezone-Info hinzufügen
        timezone_warning = TimezoneHelper.get_timezone_warning_text(bot)
        
        embed = discord.Embed(
            title=f"🏆 Week {week}: {team1_name} vs {team2_name}",
            color=discord.Color.gold()
        )
        embed.add_field(name="📅 Match Date", value=formatted_date, inline=True)
        embed.add_field(name="🕒 Match Time", value="*TBA*", inline=True)
        embed.add_field(name="🗺️ Map", value=map_name, inline=True)
        embed.add_field(
            name="🔴 Team Sides", 
            value=f"{team1_name}: {team1_side_with_icon}\n{team2_name}: {team2_side_with_icon}", 
            inline=False
        )
        embed.add_field(name="👥 Teams", value=f"{team1_role.mention} vs {team2_role.mention}", inline=False)
        embed.add_field(name="📖 Rules", value=f"[ONM]({ConfigHelper.get_rules_url(bot)})", inline=False)
        
        # TIMEZONE SUPPORT: Timezone-Info hinzufügen
        embed.add_field(name="⏰ Timezone Info", value=timezone_warning, inline=False)
        
        embed.add_field(name="ℹ️ Status", value="Waiting for match time", inline=False)
        embed.set_footer(text=f"Match ID: {match_id}")
        
        return embed
    
    @staticmethod
    def create_public_match_embed_with_week(match_id: int, team1_name: str, team2_name: str,
                                match_date: str, map_name: str, team1_side: str, 
                                team2_side: str, week: int, bot=None) -> discord.Embed:
        """
        TIMEZONE SUPPORT: Tournament Phase entfernt, Timezone-Info hinzugefügt
        """
        formatted_date = ConfigHelper.format_date_to_display(match_date)
        
        team1_side_with_icon = ConfigHelper.format_team_side_with_icon(team1_side, bot)
        team2_side_with_icon = ConfigHelper.format_team_side_with_icon(team2_side, bot)
        
        # TIMEZONE SUPPORT: Timezone-Info hinzufügen
        timezone_warning = TimezoneHelper.get_timezone_warning_text(bot)
        
        embed = discord.Embed(
            title=f"🏆 Week {week}: {team1_name} vs {team2_name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="📅 Match Date", value=formatted_date, inline=True)
        embed.add_field(name="🕒 Match Time", value="*TBA*", inline=True)
        embed.add_field(name="🗺️ Map", value=map_name, inline=True)
        embed.add_field(
            name="🔴 Team Sides", 
            value=f"{team1_name}: {team1_side_with_icon}\n{team2_name}: {team2_side_with_icon}", 
            inline=False
        )
        embed.add_field(name="📖 Rules", value=f"[ONM]({ConfigHelper.get_rules_url(bot)})", inline=False)
        
        # TIMEZONE SUPPORT: Timezone-Info hinzufügen
        embed.add_field(name="⏰ Timezone Info", value=timezone_warning, inline=False)
        
        embed.add_field(name="📊 Result", value="||*Match not played yet*||", inline=False)
        embed.set_footer(text=f"Match ID: {match_id}")
        
        return embed
    
    @staticmethod
    def create_public_match_embed(match_id: int, team1_name: str, team2_name: str,
                                match_date: str, map_name: str, team1_side: str, 
                                team2_side: str, week: int, bot=None) -> discord.Embed:
        
        return MatchEmbeds.create_public_match_embed_with_week(
            match_id, team1_name, team2_name, match_date, map_name, 
            team1_side, team2_side, week, bot
        )
    
    @staticmethod
    def create_updated_private_match_embed(match_data: Tuple, bot=None) -> discord.Embed:
        
        formatted_date = ConfigHelper.format_date_to_display(match_data[3])
        team1_name, team2_name = ConfigHelper.safe_get_team_names(match_data)
        
        team1_side_with_icon = ConfigHelper.format_team_side_with_icon(match_data[6], bot)
        team2_side_with_icon = ConfigHelper.format_team_side_with_icon(match_data[7], bot)
        
        week = match_data[13] if len(match_data) > 13 else "N/A"
        
        # TIMEZONE SUPPORT: Match time mit Timezone formatieren
        raw_match_time = match_data[4] if len(match_data) > 4 else None
        if raw_match_time and raw_match_time != "*TBA*":
            formatted_match_time = TimezoneHelper.format_time_with_timezone(raw_match_time, bot)
        else:
            formatted_match_time = "*TBA*"
        
        # TIMEZONE SUPPORT: Timezone-Info hinzufügen
        timezone_warning = TimezoneHelper.get_timezone_warning_text(bot)
        
        embed = discord.Embed(
            title=f"🏆 Week {week}: {team1_name} vs {team2_name}",
            color=discord.Color.gold()
        )
        embed.add_field(name="📅 Match Date", value=formatted_date, inline=True)
        embed.add_field(name="🕒 Match Time", value=formatted_match_time, inline=True)
        embed.add_field(name="🗺️ Map", value=match_data[5], inline=True)
        embed.add_field(
            name="🔴 Team Sides", 
            value=f"{team1_name}: {team1_side_with_icon}\n{team2_name}: {team2_side_with_icon}", 
            inline=False
        )
        embed.add_field(name="📖 Rules", value=f"[ONM]({ConfigHelper.get_rules_url(bot)})", inline=False)
        
        # TIMEZONE SUPPORT: Timezone-Info hinzufügen
        embed.add_field(name="⏰ Timezone Info", value=timezone_warning, inline=False)
        
        if match_data[11]:
            try:
                result_data = json.loads(match_data[11])
                embed.add_field(name="🏆 Result", value=f"**{result_data['winner']}** wins!\nScore: {result_data['score']}", inline=False)
                embed.add_field(name="📊 Status", value="✅ Confirmed" if match_data[10] == 'confirmed' else "⏳ Waiting for confirmation", inline=False)
            except (json.JSONDecodeError, KeyError):
                embed.add_field(name="🏆 Result", value="Result available", inline=False)
        
        embed.set_footer(text=f"Match ID: {match_data[0]}")
        
        return embed
    
    @staticmethod
    def create_updated_public_match_embed(match_data: Tuple, bot=None) -> discord.Embed:
        """
        TIMEZONE SUPPORT: Tournament Phase entfernt, Timezone-Support hinzugefügt
        """
        formatted_date = ConfigHelper.format_date_to_display(match_data[3])
        team1_name, team2_name = ConfigHelper.safe_get_team_names(match_data)
        
        team1_side_with_icon = ConfigHelper.format_team_side_with_icon(match_data[6], bot)
        team2_side_with_icon = ConfigHelper.format_team_side_with_icon(match_data[7], bot)
        
        week = match_data[13] if len(match_data) > 13 else "N/A"
        
        # TIMEZONE SUPPORT: Match time mit Timezone formatieren
        raw_match_time = match_data[4] if len(match_data) > 4 else None
        if raw_match_time and raw_match_time != "*TBA*":
            formatted_match_time = TimezoneHelper.format_time_with_timezone(raw_match_time, bot)
        else:
            formatted_match_time = "*TBA*"
        
        # TIMEZONE SUPPORT: Timezone-Info hinzufügen
        timezone_warning = TimezoneHelper.get_timezone_warning_text(bot)
        
        embed = discord.Embed(
            title=f"🏆 Week {week}: {team1_name} vs {team2_name}",
            color=discord.Color.green() if match_data[10] == 'confirmed' else discord.Color.blue()
        )
        embed.add_field(name="📅 Match Date", value=formatted_date, inline=True)
        embed.add_field(name="🕒 Match Time", value=formatted_match_time, inline=True)
        embed.add_field(name="🗺️ Map", value=match_data[5], inline=True)
        embed.add_field(
            name="🔴 Team Sides", 
            value=f"{team1_name}: {team1_side_with_icon}\n{team2_name}: {team2_side_with_icon}", 
            inline=False
        )
        embed.add_field(name="📖 Rules", value=f"[ONM]({ConfigHelper.get_rules_url(bot)})", inline=False)
        
        # TIMEZONE SUPPORT: Timezone-Info hinzufügen
        embed.add_field(name="⏰ Timezone Info", value=timezone_warning, inline=False)
        
        if match_data[11] and match_data[10] == 'confirmed':
            try:
                result_data = json.loads(match_data[11])
                result_text = f"||**{result_data['winner']}** wins with **{result_data['score']}**||"
                if match_data[12]:
                    result_text += f"\n[📺 Watch Replay]({match_data[12]})"
                embed.add_field(name="📊 Result", value=result_text, inline=False)
            except (json.JSONDecodeError, KeyError):
                embed.add_field(name="📊 Result", value="||*Result available*||", inline=False)
        elif match_data[11] and match_data[10] == 'completed':
            embed.add_field(name="📊 Result", value="||*Awaiting confirmation*||", inline=False)
        else:
            embed.add_field(name="📊 Result", value="||*Match not played yet*||", inline=False)
        
        embed.set_footer(text=f"Match ID: {match_data[0]}")
        
        return embed