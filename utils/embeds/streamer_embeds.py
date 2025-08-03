"""
Streamer Embeds
"""

import discord
import logging
from typing import List
from .config_helper import ConfigHelper

logger = logging.getLogger(__name__)

class StreamerEmbeds:
    
    @staticmethod
    def _get_streamer_display_name(bot, streamer_id: int) -> str:
        """Get server nickname or fallback to global name/username"""
        # Versuche Member zu finden (hat Server-Nickname)
        for guild in bot.guilds:
            member = guild.get_member(streamer_id)
            if member:
                return member.nick or member.global_name or member.name
        
        # Fallback auf User
        user = bot.get_user(streamer_id)
        return user.global_name or user.name if user else f"User {streamer_id}"
    
    @staticmethod
    def create_streamer_match_embed(match_data: dict, streamers: List[dict] = None, bot=None) -> discord.Embed:
        
        formatted_date = ConfigHelper.format_date_to_display(match_data.get('match_date', 'TBA'))
        
        
        team1_side_with_icon = ConfigHelper.format_team_side_with_icon(match_data['team1_side'], bot)
        team2_side_with_icon = ConfigHelper.format_team_side_with_icon(match_data['team2_side'], bot)
        
        
        week = match_data.get('week', 'N/A')
        title = f"📺 Week {week} - Streamer wanted!"
        
        embed = discord.Embed(
            title=title,
            description=f"**{match_data['team1_name']} vs {match_data['team2_name']}**",
            color=discord.Color.purple()
        )
        
        embed.add_field(name="📅 Match Date", value=formatted_date, inline=True)
        embed.add_field(name="🕒 Match Time", value=match_data.get('match_time', 'TBA'), inline=True)
        embed.add_field(name="🗺️ Map", value=match_data.get('map_name', 'TBA'), inline=True)
        
        
        embed.add_field(
            name="🔴 Team Sides",
            value=f"**{match_data['team1_name']}:** {team1_side_with_icon}\n"
                  f"**{match_data['team2_name']}:** {team2_side_with_icon}",
            inline=False
        )
        
        
        embed.add_field(name="📖 Rules", value=f"[ONM]({ConfigHelper.get_rules_url(bot)})", inline=False)
        
        
        if streamers and len(streamers) > 0:
            streamer_data = streamers[0]  
            stream_url = streamer_data.get('stream_url', '')
            
            
            if bot:
                username = StreamerEmbeds._get_streamer_display_name(bot, streamer_data['streamer_id'])
            else:
                username = f"User {streamer_data['streamer_id']}"
            
            
            if streamer_data['team_side'] == 'team1':
                team_name = match_data['team1_name']
            else:
                team_name = match_data['team2_name']
            
            if stream_url:
                streamer_text = f"{team_name}: [{username}]({stream_url})"
            else:
                streamer_text = f"{team_name}: {username}"
            
            embed.add_field(name="📺 Streamer Status", value=streamer_text, inline=False)
        else:
            embed.add_field(
                name="📺 Streamer Status", 
                value="🔍 **Streamer wanted!**", 
                inline=False
            )
        
        embed.add_field(
            name="ℹ️ Information",
            value="• **Maximum 1 streamer** per match\n"
                  "• **Stream URL required**\n"
                  "• **SteamID64 required**\n"
                  "• **Registration possible anytime**",
            inline=False
        )
        
        embed.set_footer(text=f"Match ID: {match_data.get('match_id', 'N/A')}")
        
        return embed
    
    @staticmethod
    def create_public_embed_with_streamers(match_data: dict, streamers: List[dict], bot=None) -> discord.Embed:
        
        formatted_date = ConfigHelper.format_date_to_display(match_data.get('match_date', 'TBA'))
        
        
        team1_side_with_icon = ConfigHelper.format_team_side_with_icon(match_data['team1_side'], bot)
        team2_side_with_icon = ConfigHelper.format_team_side_with_icon(match_data['team2_side'], bot)
        
        
        week = match_data.get('week', 'N/A')
        title = f"🏆 Week {week}: {match_data['team1_name']} vs {match_data['team2_name']}"
        
        embed = discord.Embed(
            title=title,
            color=discord.Color.blue()
        )
        embed.add_field(name="📅 Match Date", value=formatted_date, inline=True)
        embed.add_field(name="🕒 Match Time", value=match_data['match_time'] or "*TBA*", inline=True)
        embed.add_field(name="🗺️ Map", value=match_data['map_name'], inline=True)
        embed.add_field(
            name="🔴 Team Sides", 
            value=f"{match_data['team1_name']}: {team1_side_with_icon}\n{match_data['team2_name']}: {team2_side_with_icon}", 
            inline=False
        )
        embed.add_field(name="📖 Rules", value=f"[ONM]({ConfigHelper.get_rules_url(bot)})", inline=False)
        
        
        if streamers and len(streamers) > 0:
            streamer_data = streamers[0]  
            stream_url = streamer_data.get('stream_url', '')
            
            
            if bot:
                username = StreamerEmbeds._get_streamer_display_name(bot, streamer_data['streamer_id'])
            else:
                username = f"User {streamer_data['streamer_id']}"
            
            if stream_url:
                streamer_text = f"📺 [{username}]({stream_url})"
            else:
                streamer_text = f"📺 {username}"
            
            embed.add_field(name="📺 Streamer", value=streamer_text, inline=False)
        
        embed.add_field(name="📊 Result", value="||*Match not played yet*||", inline=False)
        embed.set_footer(text=f"Match ID: {match_data['match_id']}")
        
        return embed
    
    @staticmethod
    def create_private_embed_with_streamers(match_data: dict, streamers: List[dict], bot=None) -> discord.Embed:
        
        formatted_date = ConfigHelper.format_date_to_display(match_data.get('match_date', 'TBA'))
        
        
        team1_side_with_icon = ConfigHelper.format_team_side_with_icon(match_data['team1_side'], bot)
        team2_side_with_icon = ConfigHelper.format_team_side_with_icon(match_data['team2_side'], bot)
        
        
        week = match_data.get('week', 'N/A')
        title = f"🏆 Week {week}: {match_data['team1_name']} vs {match_data['team2_name']}"
        
        embed = discord.Embed(
            title=title,
            color=discord.Color.gold()
        )
        embed.add_field(name="📅 Match Date", value=formatted_date, inline=True)
        embed.add_field(name="🕒 Match Time", value=match_data['match_time'] or "*TBA*", inline=True)
        embed.add_field(name="🗺️ Map", value=match_data['map_name'], inline=True)
        embed.add_field(
            name="🔴 Team Sides", 
            value=f"{match_data['team1_name']}: {team1_side_with_icon}\n{match_data['team2_name']}: {team2_side_with_icon}", 
            inline=False
        )
        embed.add_field(name="📖 Rules", value=f"[ONM]({ConfigHelper.get_rules_url(bot)})", inline=False)
        
        
        if streamers and len(streamers) > 0:
            streamer_data = streamers[0]  
            stream_url = streamer_data.get('stream_url', '')
            
            
            if bot:
                username = StreamerEmbeds._get_streamer_display_name(bot, streamer_data['streamer_id'])
            else:
                username = f"User {streamer_data['streamer_id']}"
            
            
            if streamer_data['team_side'] == 'team1':
                team_name = match_data['team1_name']
            else:
                team_name = match_data['team2_name']
            
            if stream_url:
                streamer_text = f"{team_name}: [{username}]({stream_url})"
            else:
                streamer_text = f"{team_name}: {username}"
            
            embed.add_field(name="📺 Streamer", value=streamer_text, inline=False)
        
        embed.add_field(name="ℹ️ Status", value="Waiting for match time", inline=False)
        embed.set_footer(text=f"Match ID: {match_data['match_id']}")
        
        return embed