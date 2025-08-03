"""
Enhanced Tournament Cog - WITH TIMEZONE SUPPORT
Speichere als: cogs/tournament_cog.py
"""

import discord
from discord.ext import commands
import json
import logging
from datetime import datetime
from utils.embed_builder import EmbedBuilder
from utils.timezone_helper import TimezoneHelper

logger = logging.getLogger(__name__)

class TournamentCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    def has_orga_role(self, user) -> bool:
        if not self.bot.EVENT_ORGA_ROLE_ID:
            return False
        return any(role.id == self.bot.EVENT_ORGA_ROLE_ID for role in user.roles)

    @commands.command(name='send_orga_panel')
    async def send_orga_panel(self, ctx):
        if not self.has_orga_role(ctx.author):
            await ctx.send("❌ Du benötigst die Event Orga Rolle!")
            return
        
        orga_channel_id = self.bot.config['channels'].get('orga_channel_id')
        
        if orga_channel_id:
            orga_channel = ctx.guild.get_channel(orga_channel_id)
            if not orga_channel:
                await ctx.send("❌ Orga Channel nicht gefunden! Prüfe die config.json")
                return
        else:
            orga_channel = ctx.channel
        
        try:
            existing_panels = self.bot.db.get_ui_messages_by_type('orga_panel')
            for panel_data in existing_panels:
                try:
                    old_channel = ctx.guild.get_channel(panel_data[1])
                    if old_channel:
                        old_message = await old_channel.fetch_message(panel_data[0])
                        await old_message.delete()
                        logger.info(f"🗑️ Old orga panel deleted: {panel_data[0]}")
                except:
                    pass
                
                self.bot.db.deactivate_ui_message(panel_data[0])
            
            self.bot.db.set_setting('orga_panel_message_id', '')
            self.bot.db.set_setting('orga_panel_channel_id', '')
            
            panel_message = await self.bot.send_orga_panel_with_lazy_persistence(orga_channel)
            
            if panel_message:
                teams_stats = self.bot.team_loader.get_team_statistics()
                
                if orga_channel != ctx.channel:
                    response_text += f" in {orga_channel.mention}"
                
                logger.info(f"✅ Orga Panel mit Lazy Persistence gesendet von {ctx.author} in {orga_channel}")
            else:
                await ctx.send("❌ Fehler beim Senden des Orga Panels!")
            
        except Exception as e:
            await ctx.send(f"❌ Fehler beim Senden des Orga Panels: {e}")
            logger.error(f"Fehler beim Orga Panel senden: {e}")

    def _create_match_data_dict(self, match_details):
        try:
            return {
                'match_id': match_details[0],
                'team1_name': match_details[16] if len(match_details) > 16 else f"Team {match_details[1]}",
                'team2_name': match_details[17] if len(match_details) > 17 else f"Team {match_details[2]}",
                'team1_side': match_details[6],
                'team2_side': match_details[7],
                'match_date': match_details[3],
                'match_time': match_details[4],
                'map_name': match_details[5],
                'week': match_details[13],
                'status': match_details[10]
            }
        except (IndexError, TypeError):
            return {}

    def _create_private_embed_with_dynamic_status(self, match_data):
        try:
            formatted_date = self._format_date_display(match_data.get('match_date', 'TBA'))
            
            team1_side_with_icon = self._format_team_side_with_icon(match_data.get('team1_side', 'TBA'))
            team2_side_with_icon = self._format_team_side_with_icon(match_data.get('team2_side', 'TBA'))
            
            # TIMEZONE SUPPORT: Zeit mit Timezone formatieren
            raw_match_time = match_data.get('match_time', '*TBA*')
            if raw_match_time and raw_match_time != '*TBA*':
                formatted_time = TimezoneHelper.format_time_with_timezone(raw_match_time, self.bot)
            else:
                formatted_time = '*TBA*'
            
            # TIMEZONE SUPPORT: Timezone-Info hinzufügen
            timezone_warning = TimezoneHelper.get_timezone_warning_text(self.bot)
            
            embed = discord.Embed(
                title=f"🏆 Week {match_data.get('week', 'N/A')}: {match_data['team1_name']} vs {match_data['team2_name']}",
                color=discord.Color.gold()
            )
            embed.add_field(name="📅 Match Date", value=formatted_date, inline=True)
            embed.add_field(name="🕒 Match Time", value=formatted_time, inline=True)
            embed.add_field(name="🗺️ Map", value=match_data.get('map_name', 'TBA'), inline=True)
            
            embed.add_field(
                name="🔴 Team Sides", 
                value=f"{match_data['team1_name']}: {team1_side_with_icon}\n{match_data['team2_name']}: {team2_side_with_icon}", 
                inline=False
            )
            
            rules_url = self.bot.config.get('rules', {}).get('onm_url', '#')
            embed.add_field(name="📖 Rules", value=f"[ONM]({rules_url})", inline=False)
            
            # TIMEZONE SUPPORT: Timezone-Info hinzufügen
            embed.add_field(name="⏰ Timezone Info", value=timezone_warning, inline=False)
            
            status = match_data.get('status', 'pending')
            if status == 'confirmed':
                embed.add_field(name="ℹ️ Status", value="✅ Match completed and confirmed", inline=False)
            elif status == 'completed':
                embed.add_field(name="ℹ️ Status", value="⏳ Teams agreed - Awaiting Event Orga confirmation", inline=False)
            elif match_data.get('match_time'):
                # TIMEZONE SUPPORT: Zeit im Status mit Timezone
                status_time = TimezoneHelper.format_time_with_timezone(match_data['match_time'], self.bot)
                embed.add_field(name="ℹ️ Status", value=f"⏳ Scheduled for {status_time} - Waiting for results", inline=False)
            else:
                embed.add_field(name="ℹ️ Status", value="Waiting for match time coordination", inline=False)
            
            embed.set_footer(text=f"Match ID: {match_data.get('match_id', 'N/A')}")
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating private embed with dynamic status: {e}")
            return discord.Embed(title="Match Error", color=discord.Color.red())

    def _format_team_side_with_icon(self, team_side: str) -> str:
        try:
            if not team_side or team_side == 'TBA':
                return 'TBA'
            
            team_icons = self.bot.config.get('team_icons', {})
            icon = team_icons.get(team_side.upper(), '')
            
            if icon:
                return f"{team_side} {icon}"
            else:
                return team_side
                
        except Exception as e:
            logger.error(f"Error formatting team side with icon: {e}")
            return team_side

    def _format_date_display(self, date_str: str) -> str:
        if not date_str or date_str == 'TBA':
            return "TBA"
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%d.%m.%Y')
        except:
            return date_str

async def setup(bot):
    await bot.add_cog(TournamentCog(bot))