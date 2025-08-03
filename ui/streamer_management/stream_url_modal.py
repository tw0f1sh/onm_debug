# ui/streamer_management/stream_url_modal.py
"""
ENHANCED: Stream URL Modal
"""

import discord
import logging
import json
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class StreamURLModal(discord.ui.Modal):
    
    
    def __init__(self, match_id: int, bot, match_data: Dict, team_side: str, team_name: str):
        
        real_team_name = StreamURLModal._get_real_team_name_for_side(bot, match_id, team_side, team_name)
        
        super().__init__(title=f"📺 Stream Registration for {real_team_name}", timeout=300)
        self.match_id = match_id
        self.bot = bot
        self.match_data = match_data
        self.team_side = team_side
        self.team_name = real_team_name  
        
        self.stream_url = discord.ui.TextInput(
            label="Stream/Channel URL",
            placeholder="https://twitch.tv/your_channel or https://youtube.com/@your_channel",
            max_length=200,
            required=True
        )
        
        
        self.steam_id64 = discord.ui.TextInput(
            label="SteamID64 (Required)",
            placeholder="76561198000000000 (17-digit Steam ID)",
            min_length=17,
            max_length=17,
            required=True
        )
        
        self.add_item(self.stream_url)
        self.add_item(self.steam_id64)
    
    @staticmethod
    def _get_real_team_name_for_side(bot, match_id: int, team_side: str, fallback_team_name: str) -> str:
        
        try:
            
            match_details = bot.db.get_match_details(match_id)
            if not match_details:
                logger.warning(f"No match details found for match {match_id}")
                return fallback_team_name
            
            team1_id = match_details[1]
            team2_id = match_details[2]
            
            
            team1_name = "Team 1"  
            team2_name = "Team 2"  
            
            
            if len(match_details) > 16:
                team1_name = match_details[16] or f"Team {team1_id}"
            if len(match_details) > 17:
                team2_name = match_details[17] or f"Team {team2_id}"
            
            
            if team1_name.startswith("Team ") or team2_name.startswith("Team "):
                try:
                    all_teams = bot.get_all_teams()
                    for team_tuple in all_teams:
                        team_config_id, name, role_id, members, active = team_tuple
                        
                        
                        if team_config_id == team1_id:
                            team1_name = name
                        elif team_config_id == team2_id:
                            team2_name = name
                except Exception as config_error:
                    logger.debug(f"Could not get team names from config: {config_error}")
            
            
            if team_side == 'team1':
                real_team_name = team1_name
            else:
                real_team_name = team2_name
            
            logger.info(f"🏆 REAL team name for {team_side}: {real_team_name}")
            return real_team_name
            
        except Exception as e:
            logger.error(f"Error getting real team name for side: {e}")
            return fallback_team_name
    
    async def on_submit(self, interaction: discord.Interaction):
        
        try:
            
            existing_streamers = self.bot.db.get_match_streamers_detailed(self.match_id)
            
            for streamer_data in existing_streamers:
                if streamer_data['streamer_id'] == interaction.user.id:
                    await interaction.response.send_message(
                        "❌ You are already registered for this match! Please use 'Unregister as Streamer' first if you want to change your selection.", 
                        ephemeral=True
                    )
                    return
            
            stream_url = self.stream_url.value.strip()
            steam_id64 = self.steam_id64.value.strip()
            
            
            if not steam_id64.isdigit() or len(steam_id64) != 17:
                await interaction.response.send_message(
                    "❌ Invalid SteamID64! Please enter a valid 17-digit SteamID64 (e.g., 76561198000000000)",
                    ephemeral=True
                )
                return
            
            
            if not (stream_url.startswith('http://') or stream_url.startswith('https://')):
                if not stream_url.startswith('www.'):
                    stream_url = 'https://' + stream_url
                else:
                    stream_url = 'https://' + stream_url
            
            
            self.bot.db.add_match_streamer_with_side_url_and_steamid(
                self.match_id, 
                interaction.user.id, 
                self.team_side,
                stream_url,
                steam_id64
            )
            
            
            team_side_name = self._get_real_team_side_name(self.team_side)
            
            
            embed = discord.Embed(
                title="✅ Streamer Registration Successful!",
                description=f"You are streaming for **{self.team_name}** ({team_side_name})",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📊 Match",
                value=f"**{self.match_data['team1_name']} vs {self.match_data['team2_name']}**",
                inline=False
            )
            
            
            match_date = self.match_data.get('match_date', 'TBA')
            if match_date != 'TBA':
                try:
                    date_obj = datetime.strptime(match_date, '%Y-%m-%d')
                    formatted_date = date_obj.strftime('%d.%m.%Y')
                except:
                    formatted_date = match_date
            else:
                formatted_date = match_date
            
            embed.add_field(name="📅 Date", value=formatted_date, inline=True)
            embed.add_field(name="🕒 Time", value=self.match_data.get('match_time', 'TBA'), inline=True)
            embed.add_field(name="🗺️ Map", value=self.match_data.get('map_name', 'TBA'), inline=True)
            embed.add_field(name="📺 Stream URL", value=stream_url, inline=False)
            embed.add_field(name="🎮 SteamID64", value=f"`{steam_id64}`", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            
            await self._check_and_send_existing_server_details(interaction.user)
            
            
            from .streamer_match_manager import StreamerMatchManager
            streamer_manager = StreamerMatchManager(self.bot)
            await streamer_manager.update_all_match_posts_including_private(self.match_id)
            
            try:
                # Public Embed aktualisieren
                await self.bot.public_updater.update_public_embed_for_match(self.match_id, "streamer_update")
            except Exception as e:
                logger.error(f"Error updating public embed after streamer registration: {e}")
            
            logger.info(f"Streamer {interaction.user} registered for Match {self.match_id}, Team: {self.team_name}, URL: {stream_url}, SteamID64: {steam_id64}")
            
        except Exception as e:
            logger.error(f"Error in enhanced streamer registration: {e}")
            try:
                await interaction.response.send_message("❌ Error during registration!", ephemeral=True)
            except:
                pass
    
    async def _check_and_send_existing_server_details(self, streamer_user: discord.User):
        
        try:
            
            server_data_json = self.bot.db.get_setting(f'match_{self.match_id}_server')
            
            if not server_data_json:
                logger.info(f"No existing server details for match {self.match_id} - no DM sent")
                return
            
            try:
                server_data = json.loads(server_data_json)
                server_name = server_data.get('server_name')
                server_password = server_data.get('server_password')
                offering_team = server_data.get('offering_team')
                
                if not server_name or not server_password:
                    logger.info(f"Incomplete server data for match {self.match_id} - no DM sent")
                    return
                
            except json.JSONDecodeError:
                logger.error(f"Invalid server data JSON for match {self.match_id}")
                return
            
            
            current_match_details = self.bot.db.get_match_details(self.match_id)
            if not current_match_details:
                logger.error(f"Could not get current match details for match {self.match_id}")
                return
            
            
            current_match_date = current_match_details[3]  
            current_match_time = current_match_details[4]  
            current_map_name = current_match_details[5]    
            
            
            team1_id = current_match_details[1]
            team2_id = current_match_details[2]
            
            
            team1_name = "Team 1"  
            team2_name = "Team 2"  
            
            
            if len(current_match_details) > 16:
                team1_name = current_match_details[16] or f"Team {team1_id}"
            if len(current_match_details) > 17:
                team2_name = current_match_details[17] or f"Team {team2_id}"
            
            
            if team1_name.startswith("Team ") or team2_name.startswith("Team "):
                try:
                    all_teams = self.bot.get_all_teams()
                    for team_tuple in all_teams:
                        team_config_id, name, role_id, members, active = team_tuple
                        
                        if team_config_id == team1_id:
                            team1_name = name
                        elif team_config_id == team2_id:
                            team2_name = name
                except Exception as config_error:
                    logger.debug(f"Could not get team names from config: {config_error}")
            
            
            if current_match_date != 'TBA' and current_match_date:
                try:
                    date_obj = datetime.strptime(current_match_date, '%Y-%m-%d')
                    formatted_date = date_obj.strftime('%d.%m.%Y')
                except:
                    formatted_date = current_match_date
            else:
                formatted_date = current_match_date or 'TBA'
            
            
            dm_embed = discord.Embed(
                title="🖥️ Server Details Available - Match Reminder",
                description=f"The server details for your streamed match are already available!",
                color=discord.Color.blue()
            )
            
            dm_embed.add_field(
                name="📊 Match Info",
                value=f"**{team1_name} vs {team2_name}**\n"
                      f"📅 Date: {formatted_date}\n"
                      f"🕒 Time: {current_match_time or 'TBA'}\n"
                      f"🗺️ Map: {current_map_name or 'TBA'}",
                inline=False
            )
            
            dm_embed.add_field(
                name="🖥️ Server Access",
                value=f"**Server Name:** {server_name}\n"
                      f"**Password:** `{server_password}`\n"
                      f"**Provided by:** {offering_team}",
                inline=False
            )
            
            
            if self.team_side:
                if self.team_side == 'team1':
                    streaming_team = team1_name
                else:
                    streaming_team = team2_name
                
                dm_embed.add_field(
                    name="📺 Your Stream",
                    value=f"You are streaming for: **{streaming_team}**",
                    inline=False
                )
            
            dm_embed.add_field(
                name="ℹ️ Important",
                value="• Save these server details for the match\n"
                      "• Join the server when the match starts\n"
                      "• Contact teams if you have connection issues",
                inline=False
            )
            
            dm_embed.set_footer(text=f"Match ID: {self.match_id} • Server was already configured before your registration")
            
            
            try:
                await streamer_user.send(embed=dm_embed)
                logger.info(f"✅ EXISTING server details DM sent to new streamer {streamer_user} for match {self.match_id}")
                
                
                try:
                    
                    cursor = self.bot.db.conn.cursor()
                    cursor.execute('SELECT private_channel_id FROM matches WHERE id = ?', (self.match_id,))
                    result = cursor.fetchone()
                    
                    if result and result[0]:
                        private_channel = self.bot.get_channel(result[0])
                        if private_channel:
                            confirmation_embed = discord.Embed(
                                title="📧 Streamer Notified (Existing Server)",
                                description=f"Existing server details have been sent via DM to the newly registered streamer: {streamer_user.mention}",
                                color=discord.Color.green()
                            )
                            confirmation_embed.add_field(
                                name="📊 Sent Details",
                                value=f"Server: {server_name}\nTime: {current_match_time or 'TBA'}\nProvided by: {offering_team}",
                                inline=False
                            )
                            await private_channel.send(embed=confirmation_embed)
                            
                except Exception as log_error:
                    logger.debug(f"Could not log DM confirmation in match channel: {log_error}")
                
            except discord.Forbidden:
                logger.warning(f"Could not send existing server DM to streamer {streamer_user} - DMs disabled")
                
                
                try:
                    cursor = self.bot.db.conn.cursor()
                    cursor.execute('SELECT private_channel_id FROM matches WHERE id = ?', (self.match_id,))
                    result = cursor.fetchone()
                    
                    if result and result[0]:
                        private_channel = self.bot.get_channel(result[0])
                        if private_channel:
                            fallback_embed = discord.Embed(
                                title="⚠️ Streamer DM Failed (Existing Server)",
                                description=f"{streamer_user.mention} Could not send existing server details via DM (DMs disabled). Please share server details manually:",
                                color=discord.Color.orange()
                            )
                            fallback_embed.add_field(
                                name="🖥️ Server Details",
                                value=f"**Server:** {server_name}\n**Password:** `{server_password}`\n**Time:** {current_match_time or 'TBA'}\n**Provided by:** {offering_team}",
                                inline=False
                            )
                            await private_channel.send(embed=fallback_embed)
                            logger.info(f"📢 Existing server details shared in private channel as DM fallback for match {self.match_id}")
                            
                except Exception as fallback_error:
                    logger.error(f"Could not send existing server DM fallback notification: {fallback_error}")
            
            except Exception as dm_error:
                logger.error(f"Error sending existing server DM to streamer: {dm_error}")
                
        except Exception as e:
            logger.error(f"Error in _check_and_send_existing_server_details: {e}")
    
    def _get_real_team_side_name(self, team_side: str) -> str:
        
        try:
            
            if team_side == 'team1':
                side_name = self.match_data.get('team1_side', 'TBA')
            else:
                side_name = self.match_data.get('team2_side', 'TBA')
            
            
            team_icons = self.bot.config.get('team_icons', {})
            icon = team_icons.get(side_name.upper(), '')
            
            if icon:
                return f"{side_name} {icon}"
            else:
                return side_name
                
        except Exception as e:
            logger.error(f"Error formatting team side with icon: {e}")
            return 'TBA'