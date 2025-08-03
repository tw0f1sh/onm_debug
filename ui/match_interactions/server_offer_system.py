# ui/match_interactions/server_offer_system.py
"""
Server Offer System
"""

import discord
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ServerOfferModal(discord.ui.Modal):
    
    
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any], supersede_view=None):
        super().__init__(title="🖥️ Offer Server", timeout=300)
        self.bot = bot
        self.match_id = match_id
        self.match_data = match_data
        self.supersede_view = supersede_view
        
        self.server_name = discord.ui.TextInput(
            label="Server Name",
            placeholder="Team Alpha Server",
            max_length=100,
            required=True
        )
        
        self.server_password = discord.ui.TextInput(
            label="Server Password",
            placeholder="password123",
            max_length=50,
            required=True
        )
        
        self.add_item(self.server_name)
        self.add_item(self.server_password)
    
    async def on_submit(self, interaction: discord.Interaction):
        
        try:
            server_name = self.server_name.value.strip()
            server_password = self.server_password.value.strip()
            
            
            user_team_info = self._get_user_team_info_with_real_names(interaction.user)
            if not user_team_info:
                await interaction.response.send_message("❌ Could not determine your team!", ephemeral=True)
                return
            
            offering_team_name, other_team_name, other_team_role_id = user_team_info
            
            logger.info(f"✅ FIXED Server offer: {offering_team_name} offers server to {other_team_name}")
            
            
            await self._disable_server_offer_button_after_offer()
            
            
            embed = discord.Embed(
                title="🖥️ Server Offer",
                description=f"**{offering_team_name}** offers the following server:",
                color=discord.Color.purple()
            )
            
            
            embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            embed.add_field(name="🖥️ Server Name", value=f"**{server_name}**", inline=True)
            embed.add_field(name="🔑 Password", value=f"`{server_password}`", inline=True)
            embed.add_field(name="🗺️ Map", value=self.match_data.get('map_name', 'TBA'), inline=True)            
            
            view = ServerOfferView(self.bot, self.match_id, self.match_data, server_name, server_password, offering_team_name, other_team_name, other_team_role_id)
            
            
            other_team_role = interaction.guild.get_role(other_team_role_id)
            mention_text = f"{other_team_role.mention} **{offering_team_name}** has offered a server. Please review and respond:"
            
            message = await interaction.response.send_message(mention_text, embed=embed, view=view)
            
            
            actual_message = await interaction.original_response()
            
            
            view.message = actual_message
            view.message_id = actual_message.id
            view.channel_id = actual_message.channel.id
            view.guild_id = actual_message.guild.id
            
            
            try:
                
                await self.bot.lazy_persistence.register_view(actual_message, 'server_offer', self.match_id, {
                    'server_name': server_name,
                    'server_password': server_password,
                    'offering_team': offering_team_name,  
                    'responding_team': other_team_name,   
                    'responding_team_role_id': other_team_role_id,
                    'match_data': self.match_data,
                    'created_at': datetime.now().isoformat(),
                    'expires_in_hours': 24
                })
                
                
                ui_data = {
                    'view_type': 'server_offer',
                    'registered_at': datetime.now().isoformat(),
                    'data': {
                        'server_name': server_name,
                        'server_password': server_password,
                        'offering_team': offering_team_name,  
                        'responding_team': other_team_name,   
                        'responding_team_role_id': other_team_role_id,
                        'match_data': self.match_data,
                        'message_id': actual_message.id,
                        'channel_id': actual_message.channel.id,
                        'guild_id': actual_message.guild.id
                    }
                }
                
                self.bot.db.register_ui_message(
                    actual_message.id, 
                    actual_message.channel.id, 
                    actual_message.guild.id,
                    'server_offer', 
                    ui_data, 
                    self.match_id
                )
                
                
                buttons_data = []
                for item in view.children:
                    if hasattr(item, 'custom_id') and item.custom_id:
                        buttons_data.append({
                            'id': item.custom_id,
                            'label': item.label,
                            'disabled': item.disabled,
                            'style': item.style.name,
                            'data': {}
                        })
                
                if buttons_data:
                    self.bot.db.save_button_states(actual_message.id, buttons_data)
                    logger.info(f"✅ Server offer view registered for Fast Startup with {len(buttons_data)} buttons")
                
                logger.info(f"✅ Server offer registered with DUAL persistence for match {self.match_id}")
                
            except Exception as persistence_error:
                logger.error(f"Could not register server offer for persistence: {persistence_error}")
            
            
            if self.supersede_view:
                await self._disable_superseded_view()
            
            logger.info(f"✅ Server offer '{server_name}' from {offering_team_name} for match {self.match_id}")
            
        except Exception as e:
            logger.error(f"Error in server offer submission: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error processing server offer!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Error processing server offer!", ephemeral=True)
            except:
                pass
    
    def _get_user_team_info_with_real_names(self, user: discord.Member):
        
        try:
            match_details = self.bot.db.get_match_details(self.match_id)
            if not match_details:
                return None
            
            team1_id = match_details[1]
            team2_id = match_details[2]
            
            
            team1_name = "Team 1"  
            team2_name = "Team 2"  
            
            
            try:
                all_teams = self.bot.get_all_teams()
                for team_tuple in all_teams:
                    team_config_id, name, role_id, members, active = team_tuple
                    
                    if team_config_id == team1_id:
                        team1_name = name
                    elif team_config_id == team2_id:
                        team2_name = name
                        
                logger.info(f"🏆 REAL team names from config: Team1={team1_name}, Team2={team2_name}")
                        
            except Exception as config_error:
                logger.error(f"Could not get team names from config: {config_error}")
                
                if len(match_details) > 16:
                    team1_name = match_details[16] or f"Team {team1_id}"
                if len(match_details) > 17:
                    team2_name = match_details[17] or f"Team {team2_id}"
            
            
            teams = self.bot.db.get_all_teams()
            team1_role_id = None
            team2_role_id = None
            
            for team in teams:
                if team[0] == team1_id:
                    team1_role_id = team[2]
                elif team[0] == team2_id:
                    team2_role_id = team[2]
            
            
            user_role_ids = [role.id for role in user.roles]
            
            if team1_role_id in user_role_ids:
                logger.info(f"✅ User {user} is in team1: {team1_name}")
                return team1_name, team2_name, team2_role_id
            elif team2_role_id in user_role_ids:
                logger.info(f"✅ User {user} is in team2: {team2_name}")
                return team2_name, team1_name, team1_role_id
            
            logger.warning(f"❌ User {user} not found in any team")
            return None
            
        except Exception as e:
            logger.error(f"Error getting user team info with real names: {e}")
            return None
    
    async def _disable_server_offer_button_after_offer(self):
        
        try:
            
            cursor = self.bot.db.conn.cursor()
            cursor.execute('SELECT private_channel_id FROM matches WHERE id = ?', (self.match_id,))
            result = cursor.fetchone()
            
            if not result or not result[0]:
                return
            
            private_channel = self.bot.get_channel(result[0])
            if not private_channel:
                return
            
            
            async for message in private_channel.history(limit=50, oldest_first=True):
                if (message.author == self.bot.user and 
                    message.embeds and 
                    message.components):  
                    
                    embed = message.embeds[0]
                    if (embed.footer and 
                        f"Match ID: {self.match_id}" in embed.footer.text):
                        
                        
                        from ui.match_interactions.private_match_view import PrivateMatchView
                        view = PrivateMatchView(self.bot, self.match_id, self.match_data)
                        
                        
                        view.server_offer_button.disabled = True
                        view.server_offer_button.label = "⏳ Server Offer Ongoing"
                        view.server_offer_button.style = discord.ButtonStyle.secondary
                        
                        await message.edit(embed=embed, view=view)
                        
                        logger.info(f"Server Offer button disabled after offer submission for match {self.match_id}")
                        break
            
        except Exception as e:
            logger.error(f"Error disabling server offer button after offer: {e}")
    
    async def _disable_superseded_view(self):
        
        try:
            
            for item in self.supersede_view.children:
                item.disabled = True
            
            
            embed = discord.Embed(
                title="🔄 Counter Server Offer Made",
                description=f"**{self.supersede_view.responding_team}** has made a counter server offer. This offer is no longer active.",
                color=discord.Color.orange()
            )
            embed.add_field(name="🖥️ Original Server", value=self.supersede_view.server_name, inline=True)
            embed.add_field(name="👥 Offered by", value=self.supersede_view.offering_team, inline=True)
            embed.add_field(name="ℹ️ Status", value="Superseded by counter offer", inline=True)
            
            
            superseded_message = None
            
            
            if hasattr(self.supersede_view, 'message') and self.supersede_view.message:
                superseded_message = self.supersede_view.message
                logger.info("✅ Using direct message reference for superseded server view")
            
            
            elif (hasattr(self.supersede_view, 'message_id') and self.supersede_view.message_id and
                  hasattr(self.supersede_view, 'channel_id') and self.supersede_view.channel_id and
                  hasattr(self.supersede_view, 'guild_id') and self.supersede_view.guild_id):
                
                try:
                    guild = self.bot.get_guild(self.supersede_view.guild_id)
                    if guild:
                        channel = guild.get_channel(self.supersede_view.channel_id)
                        if channel:
                            superseded_message = await channel.fetch_message(self.supersede_view.message_id)
                            logger.info(f"✅ Retrieved superseded server message from stored IDs: {self.supersede_view.message_id}")
                except Exception as fetch_error:
                    logger.error(f"Could not fetch superseded server message from stored IDs: {fetch_error}")
            
            
            else:
                logger.warning("No message reference or stored IDs - trying database lookup for server offer")
                try:
                    
                    cursor = self.bot.db.conn.cursor()
                    cursor.execute('''
                        SELECT message_id, channel_id, guild_id 
                        FROM ui_messages 
                        WHERE message_type = 'server_offer' 
                        AND related_match_id = ? 
                        AND is_active = 1
                        ORDER BY created_at DESC
                        LIMIT 2
                    ''', (self.match_id,))
                    
                    results = cursor.fetchall()
                    
                    
                    for result in results:
                        message_id, channel_id, guild_id = result
                        try:
                            guild = self.bot.get_guild(guild_id)
                            if guild:
                                channel = guild.get_channel(channel_id)
                                if channel:
                                    test_message = await channel.fetch_message(message_id)
                                    
                                    
                                    if test_message.embeds and not any("Counter Server Offer Made" in embed.title for embed in test_message.embeds):
                                        superseded_message = test_message
                                        logger.info(f"✅ Found superseded server message via database: {message_id}")
                                        break
                        except:
                            continue
                            
                except Exception as db_error:
                    logger.error(f"Database lookup for superseded server message failed: {db_error}")
            
            
            if superseded_message:
                await superseded_message.edit(embed=embed, view=self.supersede_view)
                
                
                self.bot.db.complete_ongoing_interaction(superseded_message.id)
                
                logger.info(f"✅ Successfully disabled superseded server offer view: {superseded_message.id}")
            else:
                logger.error(f"❌ Could not find superseded server message to disable for match {self.match_id}")
            
        except Exception as e:
            logger.error(f"Error disabling superseded server view: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")


class ServerOfferView(discord.ui.View):
    
    
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any], 
                 server_name: str, server_password: str, offering_team: str, responding_team: str, responding_team_role_id: int):
        super().__init__(timeout=None)  
        self.bot = bot
        self.match_id = match_id
        self.match_data = match_data
        self.server_name = server_name
        self.server_password = server_password
        self.offering_team = offering_team      
        self.responding_team = responding_team  
        self.responding_team_role_id = responding_team_role_id
        
        
        self.message = None
        self.message_id = None
        self.channel_id = None
        self.guild_id = None
        
        
        timestamp = int(datetime.now().timestamp())
        self.accept_button.custom_id = f"server_accept_{match_id}_{timestamp}"
        self.counter_button.custom_id = f"server_counter_{match_id}_{timestamp}"
    
    async def _get_message_from_stored_ids(self) -> discord.Message:
        
        try:
            if self.message:
                return self.message
            
            if not self.message_id or not self.channel_id or not self.guild_id:
                logger.error("No stored message/channel/guild IDs available")
                return None
            
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                logger.error(f"Guild {self.guild_id} not found")
                return None
            
            channel = guild.get_channel(self.channel_id)
            if not channel:
                logger.error(f"Channel {self.channel_id} not found")
                return None
            
            message = await channel.fetch_message(self.message_id)
            if message:
                self.message = message  
                logger.debug(f"Successfully retrieved server offer message {self.message_id}")
                return message
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving server offer message from stored IDs: {e}")
            return None
    
    @discord.ui.button(label='✅ Accept Server', style=discord.ButtonStyle.success, custom_id='server_accept')
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        
        if not self._user_in_responding_team(interaction.user):
            await interaction.response.send_message("❌ Only the responding team can accept this offer!", ephemeral=True)
            return
        
        try:
            
            server_data = {
                'server_name': self.server_name,
                'server_password': self.server_password,
                'offering_team': self.offering_team,    
                'accepted_at': datetime.now().isoformat()
            }
            
            
            import json
            self.bot.db.set_setting(f'match_{self.match_id}_server', json.dumps(server_data))
            
            
            embed = discord.Embed(
                title="✅ Server Accepted!",
                description=f"Both teams have agreed on the server provided by **{self.offering_team}**",  
                color=discord.Color.green()
            )
            embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            embed.add_field(name="🖥️ Server Name", value=self.server_name, inline=True)
            embed.add_field(name="🔑 Password", value=f"`{self.server_password}`", inline=True)
            embed.add_field(name="🗺️ Map", value=self.match_data.get('map_name', 'TBA'), inline=True)
            embed.set_footer(text="Server accepted")
            
            
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            
            await self._add_only_server_field_to_private_embed_with_real_team()
            
            
            await self._send_server_dm_to_streamer_fixed()
            
            
            await self._mention_both_teams_confirmation_with_real_team(interaction)
         
            message = await self._get_message_from_stored_ids()
            if message:
                self.bot.db.complete_ongoing_interaction(message.id)
            
            logger.info(f"✅ Server '{self.server_name}' accepted for match {self.match_id} - FIXED DM sent to streamer with REAL team name: {self.offering_team}")
            
        except Exception as e:
            logger.error(f"Error accepting server with FIXED DM to streamer: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error accepting server!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Error accepting server!", ephemeral=True)
            except:
                pass
    
    @discord.ui.button(label='🔄 Counter Offer', style=discord.ButtonStyle.primary, custom_id='server_counter')
    async def counter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        
        if not self._user_in_responding_team(interaction.user):
            await interaction.response.send_message("❌ Only the responding team can make a counter offer!", ephemeral=True)
            return
        
        
        modal = ServerOfferModal(self.bot, self.match_id, self.match_data, supersede_view=self)
        await interaction.response.send_modal(modal)
    
    def restore_from_persistence_data(self, persistence_data: Dict[str, Any]):
        
        try:
            offer_data = persistence_data.get('data', {})
            
            
            self.message_id = offer_data.get('message_id')
            self.channel_id = offer_data.get('channel_id')
            self.guild_id = offer_data.get('guild_id')
            
            logger.debug(f"Restored server offer view with message_id: {self.message_id}")
            
        except Exception as e:
            logger.error(f"Error restoring server offer view from persistence: {e}")
    
    def _user_in_responding_team(self, user: discord.Member) -> bool:
        
        user_role_ids = [role.id for role in user.roles]
        return self.responding_team_role_id in user_role_ids
    
    
    
    async def _send_server_dm_to_streamer_fixed(self):
        
        try:
            
            streamers = self.bot.db.get_match_streamers_detailed(self.match_id)
            
            if not streamers or len(streamers) == 0:
                logger.info(f"No streamer registered for match {self.match_id} - no DM sent")
                return
            
            streamer_data = streamers[0]  
            streamer_id = streamer_data['streamer_id']
            
            
            streamer_user = self.bot.get_user(streamer_id)
            if not streamer_user:
                logger.warning(f"Streamer user {streamer_id} not found for DM")
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
            
            
            real_offering_team = self.offering_team  
            
            
            dm_embed = discord.Embed(
                title="🖥️ Server Details - Match Reminder",
                description=f"The server details for your streamed match are now available!",
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
                value=f"**Server Name:** {self.server_name}\n"
                      f"**Password:** `{self.server_password}`\n"
                      f"**Provided by:** {real_offering_team}",  
                inline=False
            )
            
            
            if streamer_data.get('team_side'):
                if streamer_data['team_side'] == 'team1':
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
            
            dm_embed.set_footer(text=f"Match ID: {self.match_id} • Server accepted at {datetime.now().strftime('%H:%M')}")
            
            
            try:
                await streamer_user.send(embed=dm_embed)
                logger.info(f"✅ FIXED Server details DM sent to streamer {streamer_user} for match {self.match_id} - Time: {current_match_time}, Team: {real_offering_team}")
                
                
                try:
                    
                    cursor = self.bot.db.conn.cursor()
                    cursor.execute('SELECT private_channel_id FROM matches WHERE id = ?', (self.match_id,))
                    result = cursor.fetchone()
                    
                    if result and result[0]:
                        private_channel = self.bot.get_channel(result[0])
                        if private_channel:
                            confirmation_embed = discord.Embed(
                                title="📧 Streamer Notified",
                                description=f"Server details have been sent via DM to the registered streamer: {streamer_user.mention}",
                                color=discord.Color.green()
                            )
                            confirmation_embed.add_field(
                                name="📊 Sent Details",
                                value=f"Time: {current_match_time or 'TBA'}\nProvided by: {real_offering_team}",  
                                inline=False
                            )
                            await private_channel.send(embed=confirmation_embed)
                except Exception as log_error:
                    logger.debug(f"Could not log DM confirmation in match channel: {log_error}")
                
            except discord.Forbidden:
                logger.warning(f"Could not send DM to streamer {streamer_user} - DMs disabled")
                
                
                try:
                    cursor = self.bot.db.conn.cursor()
                    cursor.execute('SELECT private_channel_id FROM matches WHERE id = ?', (self.match_id,))
                    result = cursor.fetchone()
                    
                    if result and result[0]:
                        private_channel = self.bot.get_channel(result[0])
                        if private_channel:
                            fallback_embed = discord.Embed(
                                title="⚠️ Streamer DM Failed",
                                description=f"{streamer_user.mention} Server details could not be sent via DM (DMs disabled). Please share server details manually:",
                                color=discord.Color.orange()
                            )
                            fallback_embed.add_field(
                                name="🖥️ Server Details",
                                value=f"**Server:** {self.server_name}\n**Password:** `{self.server_password}`\n**Time:** {current_match_time or 'TBA'}\n**Provided by:** {real_offering_team}",  
                                inline=False
                            )
                            await private_channel.send(embed=fallback_embed)
                            logger.info(f"📢 FIXED Server details shared in private channel as DM fallback for match {self.match_id}")
                except Exception as fallback_error:
                    logger.error(f"Could not send DM fallback notification: {fallback_error}")
            
            except Exception as dm_error:
                logger.error(f"Error sending FIXED server DM to streamer: {dm_error}")
                
        except Exception as e:
            logger.error(f"Error in _send_server_dm_to_streamer_fixed: {e}")
    
    async def _add_only_server_field_to_private_embed_with_real_team(self):
        
        try:
            
            cursor = self.bot.db.conn.cursor()
            cursor.execute('SELECT private_channel_id FROM matches WHERE id = ?', (self.match_id,))
            result = cursor.fetchone()
            
            if not result or not result[0]:
                return
            
            private_channel = self.bot.get_channel(result[0])
            if not private_channel:
                return
            
            
            current_streamers = self.bot.db.get_match_streamers_detailed(self.match_id)
            
            
            async for message in private_channel.history(limit=50, oldest_first=True):
                if (message.author == self.bot.user and 
                    message.embeds and 
                    message.components):  
                    
                    embed = message.embeds[0]
                    if (embed.footer and 
                        f"Match ID: {self.match_id}" in embed.footer.text):
                        
                        
                        existing_view_data = self._extract_current_view_state(message)
                        
                        
                        view = self._create_view_preserving_button_states(existing_view_data)
                        
                        
                        view.server_offer_button.disabled = True
                        view.server_offer_button.label = f"✅ Server Set"
                        view.server_offer_button.style = discord.ButtonStyle.success
                        
                        
                        server_text = f"Server Name: `{self.server_name}`\nPassword: `{self.server_password}`\nProvided by: {self.offering_team}"  
                        
                        
                        insert_index = len(embed.fields)
                        for i, field in enumerate(embed.fields):
                            if "Streamer" in field.name or "📺" in field.name or "Rules" in field.name or "📖" in field.name:
                                insert_index = i
                                break
                        
                        embed.insert_field_at(insert_index, name="🖥️ Server Details", value=server_text, inline=False)
                        
                        
                        if current_streamers and len(current_streamers) > 0:
                            streamer_data = current_streamers[0]
                            stream_url = streamer_data.get('stream_url', '')
                            
                            
                            user = self.bot.get_user(streamer_data['streamer_id'])
                            username = user.display_name if user else f"User {streamer_data['streamer_id']}"
                            
                            
                            if streamer_data['team_side'] == 'team1':
                                team_name = self.match_data['team1_name']
                            else:
                                team_name = self.match_data['team2_name']
                            
                            if stream_url:
                                streamer_text = f"{team_name}: [{username}]({stream_url})"
                            else:
                                streamer_text = f"{team_name}: {username}"
                            
                            
                            steam_id64 = streamer_data.get('steam_id64', '')
                            if steam_id64:
                                streamer_text += f"\nSteamID64: `{steam_id64}`"
                            
                            
                            streamer_field_found = False
                            for i, field in enumerate(embed.fields):
                                if "Streamer" in field.name or "📺" in field.name:
                                    embed.set_field_at(i, name="📺 Streamer", value=streamer_text, inline=False)
                                    streamer_field_found = True
                                    break
                            
                            if not streamer_field_found:
                                
                                rules_index = -1
                                for i, field in enumerate(embed.fields):
                                    if "Rules" in field.name or "📖" in field.name:
                                        rules_index = i
                                        break
                                
                                if rules_index >= 0:
                                    embed.insert_field_at(rules_index, name="📺 Streamer", value=streamer_text, inline=False)
                                else:
                                    embed.add_field(name="📺 Streamer", value=streamer_text, inline=False)
                        
                        await message.edit(embed=embed, view=view)
                        
                        logger.info(f"✅ ONLY server field added to private embed for match {self.match_id} with REAL team name: {self.offering_team}")
                        break
            
        except Exception as e:
            logger.error(f"Error adding only server field to private embed: {e}")
    
    async def _mention_both_teams_confirmation_with_real_team(self, interaction):
        
        try:
            
            match_details = self.bot.db.get_match_details(self.match_id)
            if not match_details:
                return
            
            team1_id = match_details[1]
            team2_id = match_details[2]
            
            
            teams = self.bot.db.get_all_teams()
            team1_role_id = None
            team2_role_id = None
            
            for team in teams:
                if team[0] == team1_id:
                    team1_role_id = team[2]
                elif team[0] == team2_id:
                    team2_role_id = team[2]
            
            if team1_role_id and team2_role_id:
                team1_role = interaction.guild.get_role(team1_role_id)
                team2_role = interaction.guild.get_role(team2_role_id)
                
                if team1_role and team2_role:
                    confirmation_embed = discord.Embed(
                        title="✅ Server Confirmed!",
                        description=f"Both teams have agreed on the server provided by **{self.offering_team}**",  
                        color=discord.Color.green()
                    )
                    confirmation_embed.add_field(name="🖥️ Server Name", value=self.server_name, inline=True)
                    confirmation_embed.add_field(name="🔑 Password", value=f"`{self.server_password}`", inline=True)
                    confirmation_embed.add_field(name="🗺️ Map", value=self.match_data.get('map_name', 'TBA'), inline=True)
                    
                    await interaction.followup.send(
                        f"🖥️ {team1_role.mention} {team2_role.mention} **Server confirmed!**", 
                        embed=confirmation_embed
                    )
            
        except Exception as e:
            logger.error(f"Error mentioning teams for server confirmation: {e}")
    
    def _extract_current_view_state(self, message: discord.Message) -> Dict[str, Any]:
        
        try:
            view_data = {
                'time_offer_disabled': False,
                'time_offer_label': "🕒 Offer Match Time",
                'time_offer_style': 'primary',
                'result_submission_disabled': False,
                'result_submission_label': "📊 Submit Result",
                'result_submission_style': 'secondary',
                'server_offer_disabled': False,
                'server_offer_label': "🖥️ Offer Server",
                'server_offer_style': 'secondary'
            }
            
            if message.components:
                for action_row in message.components:
                    for component in action_row.children:
                        if hasattr(component, 'label') and component.label:
                            label = component.label
                            
                            
                            if "Time" in label or "🕒" in label:
                                view_data['time_offer_disabled'] = component.disabled
                                view_data['time_offer_label'] = label
                                view_data['time_offer_style'] = component.style.name
                            
                            
                            elif "Result" in label or "📊" in label:
                                view_data['result_submission_disabled'] = component.disabled
                                view_data['result_submission_label'] = label
                                view_data['result_submission_style'] = component.style.name
                            
                            
                            elif "Server" in label or "🖥️" in label:
                                view_data['server_offer_disabled'] = component.disabled
                                view_data['server_offer_label'] = label
                                view_data['server_offer_style'] = component.style.name
            
            return view_data
            
        except Exception as e:
            logger.error(f"Error extracting view state: {e}")
            return {}
    
    def _create_view_preserving_button_states(self, view_data: Dict[str, Any]):
        
        try:
            from ui.match_interactions.private_match_view import PrivateMatchView
            view = PrivateMatchView(self.bot, self.match_id, self.match_data)
            
            
            if view_data.get('time_offer_disabled'):
                view.time_offer_button.disabled = True
                view.time_offer_button.label = view_data.get('time_offer_label', "✅ Time Set")
                view.time_offer_button.style = getattr(discord.ButtonStyle, view_data.get('time_offer_style', 'success'), discord.ButtonStyle.success)
            
            
            if view_data.get('result_submission_disabled'):
                view.result_submission_button.disabled = True
                view.result_submission_button.label = view_data.get('result_submission_label', "📊 Result Submitted")
                view.result_submission_button.style = getattr(discord.ButtonStyle, view_data.get('result_submission_style', 'success'), discord.ButtonStyle.success)
            
            return view
            
        except Exception as e:
            logger.error(f"Error creating view with preserved states: {e}")
            from ui.match_interactions.private_match_view import PrivateMatchView
            return PrivateMatchView(self.bot, self.match_id, self.match_data)
    
    async def on_timeout(self):
        
        try:
            for item in self.children:
                item.disabled = True
            
            
            embed = discord.Embed(
                title="⏰ Server Offer Expired",
                description=f"The server offer for **{self.server_name}** has expired.",
                color=discord.Color.orange()
            )
            embed.add_field(name="🖥️ Expired Offer", value=self.server_name, inline=True)
            embed.add_field(name="👥 Offered by", value=self.offering_team, inline=True)  
            embed.add_field(name="ℹ️ Status", value="Expired - can be resubmitted", inline=True)
            
            message = await self._get_message_from_stored_ids()
            if message:
                await message.edit(embed=embed, view=self)
                
                
                self.bot.db.complete_ongoing_interaction(message.id)
            
            
            await self._re_enable_server_offer_button()
            
            logger.info(f"Server offer view timed out for match {self.match_id}")
            
        except Exception as e:
            logger.error(f"Error handling timeout: {e}")
    
    async def _re_enable_server_offer_button(self):
        
        try:
            
            cursor = self.bot.db.conn.cursor()
            cursor.execute('SELECT private_channel_id FROM matches WHERE id = ?', (self.match_id,))
            result = cursor.fetchone()
            
            if not result or not result[0]:
                return
            
            private_channel = self.bot.get_channel(result[0])
            if not private_channel:
                return
            
            
            server_data_json = self.bot.db.get_setting(f'match_{self.match_id}_server')
            if server_data_json:
                try:
                    import json
                    server_data = json.loads(server_data_json)
                    if server_data.get('server_name'):
                        return  
                except:
                    pass
            
            
            async for message in private_channel.history(limit=50, oldest_first=True):
                if (message.author == self.bot.user and 
                    message.embeds and 
                    message.components):  
                    
                    embed = message.embeds[0]
                    if (embed.footer and 
                        f"Match ID: {self.match_id}" in embed.footer.text):
                        
                        
                        from ui.match_interactions.private_match_view import PrivateMatchView
                        view = PrivateMatchView(self.bot, self.match_id, self.match_data)
                        
                        
                        view.server_offer_button.disabled = False
                        view.server_offer_button.label = "🖥️ Offer Server"
                        view.server_offer_button.style = discord.ButtonStyle.secondary
                        
                        await message.edit(embed=embed, view=view)
                        
                        logger.info(f"Server Offer button re-enabled after timeout for match {self.match_id}")
                        break
            
        except Exception as e:
            logger.error(f"Error re-enabling server offer button: {e}")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        
        logger.error(f"Error in ServerOfferView for match {self.match_id}: {error}")
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing the server offer. Please try again or contact an admin.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ An error occurred while processing the server offer. Please try again or contact an admin.",
                    ephemeral=True
                )
                
            
            message = await self._get_message_from_stored_ids()
            if message:
                self.bot.db.complete_ongoing_interaction(message.id)
                
        except:
            pass