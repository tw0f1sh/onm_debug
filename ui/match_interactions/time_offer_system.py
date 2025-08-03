"""
Enhanced Time Offer System - WITH TIMEZONE SUPPORT
Speichere als: ui/match_interactions/time_offer_system.py
"""

import discord
import logging
import re
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from utils.timezone_helper import TimezoneHelper

logger = logging.getLogger(__name__)

class TimeOfferModal(discord.ui.Modal):
    
    
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any], supersede_view=None):
        # TIMEZONE SUPPORT: Dynamischer Titel mit Timezone
        timezone_display = TimezoneHelper.get_timezone_display(bot)
        super().__init__(title=f"🕒 Offer Match Time ({timezone_display})", timeout=300)
        
        self.bot = bot
        self.match_id = match_id
        self.match_data = match_data
        self.supersede_view = supersede_view
        
        # TIMEZONE SUPPORT: Label und Placeholder mit Timezone-Info
        time_label = TimezoneHelper.get_time_input_label(bot)
        time_placeholder = TimezoneHelper.get_time_input_placeholder(bot)
        
        self.time_input = discord.ui.TextInput(
            label=time_label,
            placeholder=time_placeholder,
            max_length=5,
            required=True
        )
        
        self.add_item(self.time_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        
        try:
            time_str = self.time_input.value.strip()
            
            # TIMEZONE SUPPORT: Erweiterte Validierung mit Timezone-Info
            if not TimezoneHelper.validate_time_format(time_str):
                timezone_info = TimezoneHelper.get_timezone_info(self.bot)
                await interaction.response.send_message(
                    f"❌ Invalid time format! Please use HH:MM format.\n"
                    f"⏰ {timezone_info}", 
                    ephemeral=True
                )
                return
            
            
            user_team_info = self._get_user_team_info_with_real_names(interaction.user)
            if not user_team_info:
                await interaction.response.send_message("❌ Could not determine your team!", ephemeral=True)
                return
            
            offering_team_name, other_team_name, other_team_role_id = user_team_info
            
            logger.info(f"✅ TIMEZONE: Time offer {time_str} from {offering_team_name} to {other_team_name}")
            
            
            await self._disable_time_offer_button_after_offer()
            
            # TIMEZONE SUPPORT: Embed mit Timezone-formatierter Zeit
            formatted_time = TimezoneHelper.format_time_with_timezone(time_str, self.bot)
            timezone_warning = TimezoneHelper.get_timezone_warning_text(self.bot)
            
            embed = discord.Embed(
                title="🕒 Match Time Offer",
                description=f"**{offering_team_name}** proposes the following match time:",
                color=discord.Color.blue()
            )
            
            
            embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            embed.add_field(name="📅 Date", value=self.match_data.get('match_date', 'TBA'), inline=True)
            embed.add_field(name="🕒 Proposed Time", value=f"**{formatted_time}**", inline=True)
            embed.add_field(name="🗺️ Map", value=self.match_data.get('map_name', 'TBA'), inline=True)
            
            # TIMEZONE SUPPORT: Timezone-Warnung hinzufügen
            embed.add_field(name="⏰ Timezone Info", value=timezone_warning, inline=False)
         
            view = TimeOfferView(self.bot, self.match_id, self.match_data, time_str, offering_team_name, other_team_name, other_team_role_id)
            
            
            other_team_role = interaction.guild.get_role(other_team_role_id)
            mention_text = f"{other_team_role.mention} **{offering_team_name}** has proposed a match time. Please review and respond:"
            
            message = await interaction.response.send_message(mention_text, embed=embed, view=view)
            
            
            actual_message = await interaction.original_response()
            
            
            view.message = actual_message
            view.message_id = actual_message.id
            view.channel_id = actual_message.channel.id
            view.guild_id = actual_message.guild.id
            
            
            try:
                
                await self.bot.lazy_persistence.register_view(actual_message, 'time_offer', self.match_id, {
                    'offered_time': time_str,
                    'offering_team': offering_team_name,  
                    'responding_team': other_team_name,   
                    'responding_team_role_id': other_team_role_id,
                    'match_data': self.match_data,
                    'created_at': datetime.now().isoformat(),
                    'expires_in_hours': 24
                })
                
                
                ui_data = {
                    'view_type': 'time_offer',
                    'registered_at': datetime.now().isoformat(),
                    'data': {
                        'offered_time': time_str,
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
                    'time_offer', 
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
                    logger.info(f"✅ Time offer view registered for Fast Startup with {len(buttons_data)} buttons")
                
                logger.info(f"✅ Time offer registered with DUAL persistence for match {self.match_id}")
                
            except Exception as persistence_error:
                logger.error(f"Could not register time offer for persistence: {persistence_error}")
            
            
            if self.supersede_view:
                await self._disable_superseded_view()
            
            logger.info(f"✅ TIMEZONE: Time offer {time_str} from {offering_team_name} for match {self.match_id} WITH TIMEZONE SUPPORT")
            
        except Exception as e:
            logger.error(f"Error in time offer submission with TIMEZONE support: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error processing time offer!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Error processing time offer!", ephemeral=True)
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
    
    async def _disable_time_offer_button_after_offer(self):
        
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
                        
                        
                        view.time_offer_button.disabled = True
                        view.time_offer_button.label = "⏳ Time Offer Ongoing"
                        view.time_offer_button.style = discord.ButtonStyle.secondary
                        
                        await message.edit(embed=embed, view=view)
                        
                        logger.info(f"Time Offer button disabled after offer submission for match {self.match_id}")
                        break
            
        except Exception as e:
            logger.error(f"Error disabling time offer button after offer: {e}")
    
    async def _disable_superseded_view(self):
        
        try:
            
            for item in self.supersede_view.children:
                item.disabled = True
            
            
            embed = discord.Embed(
                title="🔄 Counter Offer Made",
                description=f"**{self.supersede_view.responding_team}** has made a counter offer. This offer is no longer active.",
                color=discord.Color.orange()
            )
            embed.add_field(name="🕒 Original Offer", value=self.supersede_view.offered_time, inline=True)
            embed.add_field(name="👥 Offered by", value=self.supersede_view.offering_team, inline=True)
            embed.add_field(name="ℹ️ Status", value="Superseded by counter offer", inline=True)
            
            
            superseded_message = None
            
            
            if hasattr(self.supersede_view, 'message') and self.supersede_view.message:
                superseded_message = self.supersede_view.message
                logger.info("✅ Using direct message reference for superseded view")
            
            
            elif (hasattr(self.supersede_view, 'message_id') and self.supersede_view.message_id and
                  hasattr(self.supersede_view, 'channel_id') and self.supersede_view.channel_id and
                  hasattr(self.supersede_view, 'guild_id') and self.supersede_view.guild_id):
                
                try:
                    guild = self.bot.get_guild(self.supersede_view.guild_id)
                    if guild:
                        channel = guild.get_channel(self.supersede_view.channel_id)
                        if channel:
                            superseded_message = await channel.fetch_message(self.supersede_view.message_id)
                            logger.info(f"✅ Retrieved superseded message from stored IDs: {self.supersede_view.message_id}")
                except Exception as fetch_error:
                    logger.error(f"Could not fetch superseded message from stored IDs: {fetch_error}")
            
            
            else:
                logger.warning("No message reference or stored IDs - trying database lookup")
                try:
                    
                    cursor = self.bot.db.conn.cursor()
                    cursor.execute('''
                        SELECT message_id, channel_id, guild_id 
                        FROM ui_messages 
                        WHERE message_type = 'time_offer' 
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
                                    
                                    
                                    if test_message.embeds and not any("Counter Offer Made" in embed.title for embed in test_message.embeds):
                                        superseded_message = test_message
                                        logger.info(f"✅ Found superseded message via database: {message_id}")
                                        break
                        except:
                            continue
                            
                except Exception as db_error:
                    logger.error(f"Database lookup for superseded message failed: {db_error}")
            
            
            if superseded_message:
                await superseded_message.edit(embed=embed, view=self.supersede_view)
                
                
                self.bot.db.complete_ongoing_interaction(superseded_message.id)
                
                logger.info(f"✅ Successfully disabled superseded time offer view: {superseded_message.id}")
            else:
                logger.error(f"❌ Could not find superseded message to disable for match {self.match_id}")
            
        except Exception as e:
            logger.error(f"Error disabling superseded view: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")


class TimeOfferView(discord.ui.View):
    
    
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any], 
                 offered_time: str, offering_team: str, responding_team: str, responding_team_role_id: int):
        super().__init__(timeout=None)  
        self.bot = bot
        self.match_id = match_id
        self.match_data = match_data
        self.offered_time = offered_time
        self.offering_team = offering_team      
        self.responding_team = responding_team  
        self.responding_team_role_id = responding_team_role_id
        
        
        self.message = None  
        self.message_id = None  
        self.channel_id = None  
        self.guild_id = None  
        
        
        timestamp = int(datetime.now().timestamp())
        self.accept_button.custom_id = f"time_accept_{match_id}_{timestamp}"
        self.counter_button.custom_id = f"time_counter_{match_id}_{timestamp}"
    
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
                logger.debug(f"Successfully retrieved message {self.message_id}")
                return message
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving message from stored IDs: {e}")
            return None
    
    @discord.ui.button(label='✅ Accept Time', style=discord.ButtonStyle.success, custom_id='time_accept')
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        
        if not self._user_in_responding_team(interaction.user):
            await interaction.response.send_message("❌ Only the responding team can accept this offer!", ephemeral=True)
            return
        
        try:
            
            self.bot.db.update_match_time(self.match_id, self.offered_time)
            
            # TIMEZONE SUPPORT: Zeit mit Timezone formatieren
            formatted_time = TimezoneHelper.format_time_with_timezone(self.offered_time, self.bot)
            timezone_warning = TimezoneHelper.get_timezone_warning_text(self.bot)
            
            
            embed = discord.Embed(
                title="✅ Match Time Confirmed!",
                description=f"Both teams have agreed on the match time: **{formatted_time}**",
                color=discord.Color.green()
            )
            embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            embed.add_field(name="📅 Date", value=self.match_data.get('match_date', 'TBA'), inline=True)
            embed.add_field(name="🕒 Time", value=formatted_time, inline=True)
            embed.add_field(name="🗺️ Map", value=self.match_data.get('map_name', 'TBA'), inline=True)
            
            # TIMEZONE SUPPORT: Timezone-Info hinzufügen
            embed.add_field(name="⏰ Timezone Info", value=timezone_warning, inline=False)
            embed.set_footer(text="Time accepted")
            
            
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            
            await self._update_only_time_field_in_private_embed()
            
            
            await self._update_only_time_field_in_public_embed()
            
            
            await self._update_only_time_field_in_streamer_embed()
            
            try:
                # Public Embed aktualisieren
                await self.bot.public_updater.update_public_embed_for_match(self.match_id, "time_update")
            except Exception as e:
                logger.error(f"Error updating public embed after time acceptance: {e}")
            
            # Status-Icon auf 'scheduled' aktualisieren - MIT DEBUG
            try:
                logger.info(f"🔄 DEBUGGING: About to update status for match {self.match_id} to 'scheduled'")
                
                # Channel vor Update finden
                stored_channel_id = self.bot.db.get_setting(f'public_match_{self.match_id}_channel_id')
                if stored_channel_id:
                    for guild in self.bot.guilds:
                        channel = guild.get_channel(int(stored_channel_id))
                        if channel:
                            logger.info(f"🔍 BEFORE status update - Channel name: {channel.name}")
                            break
                
                await self.bot.status_manager.update_channel_status(self.match_id, 'scheduled')
                
                # Channel nach Update prüfen
                if stored_channel_id:
                    for guild in self.bot.guilds:
                        channel = guild.get_channel(int(stored_channel_id))
                        if channel:
                            logger.info(f"✅ AFTER status update - Channel name: {channel.name}")
                            break
                
                logger.info(f"✅ Status updated to 'scheduled' for match {self.match_id}")
            except Exception as status_error:
                logger.error(f"Error updating status to scheduled for match {self.match_id}: {status_error}")
                import traceback
                logger.error(f"Status update traceback: {traceback.format_exc()}")
            
            # Mention both teams confirmation
            await self._mention_both_teams_confirmation_with_real_names(interaction)
            
            
            await self._notify_streamer()
            
            message = await self._get_message_from_stored_ids()
            if message:
                self.bot.db.complete_ongoing_interaction(message.id)
            
            logger.info(f"✅ TIMEZONE: Time {self.offered_time} accepted for match {self.match_id} WITH TIMEZONE DISPLAY")

        except Exception as e:
            logger.error(f"Error accepting time with TIMEZONE support: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error accepting time!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Error accepting time!", ephemeral=True)
            except:
                pass
    
    @discord.ui.button(label='🔄 Counter Offer', style=discord.ButtonStyle.primary, custom_id='time_counter')
    async def counter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        
        if not self._user_in_responding_team(interaction.user):
            await interaction.response.send_message("❌ Only the responding team can make a counter offer!", ephemeral=True)
            return
        
        
        modal = TimeOfferModal(self.bot, self.match_id, self.match_data, supersede_view=self)
        await interaction.response.send_modal(modal)
    
    def restore_from_persistence_data(self, persistence_data: Dict[str, Any]):
        
        try:
            offer_data = persistence_data.get('data', {})
            
            
            self.message_id = offer_data.get('message_id')
            self.channel_id = offer_data.get('channel_id')
            self.guild_id = offer_data.get('guild_id')
            
            logger.debug(f"Restored time offer view with message_id: {self.message_id}")
            
        except Exception as e:
            logger.error(f"Error restoring time offer view from persistence: {e}")
    
    async def _mention_both_teams_confirmation_with_real_names(self, interaction):
        
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
                    # TIMEZONE SUPPORT: Zeit mit Timezone formatieren
                    formatted_time = TimezoneHelper.format_time_with_timezone(self.offered_time, self.bot)
                    timezone_warning = TimezoneHelper.get_timezone_warning_text(self.bot)
                    
                    confirmation_embed = discord.Embed(
                        title="✅ Match Time Confirmed!",
                        description=f"Both teams have agreed on **{formatted_time}**",
                        color=discord.Color.green()
                    )
                    confirmation_embed.add_field(name="📅 Date", value=self.match_data.get('match_date', 'TBA'), inline=True)
                    confirmation_embed.add_field(name="🕒 Time", value=formatted_time, inline=True)
                    confirmation_embed.add_field(name="🗺️ Map", value=self.match_data.get('map_name', 'TBA'), inline=True)
                    
                    # TIMEZONE SUPPORT: Timezone-Info hinzufügen
                    confirmation_embed.add_field(name="⏰ Timezone Info", value=timezone_warning, inline=False)
                 
                    await interaction.followup.send(
                        f"🕒 {team1_role.mention} {team2_role.mention} **Match time confirmed!**", 
                        embed=confirmation_embed
                    )
            
        except Exception as e:
            logger.error(f"Error mentioning teams for confirmation: {e}")
    
    def _user_in_responding_team(self, user: discord.Member) -> bool:
        
        user_role_ids = [role.id for role in user.roles]
        return self.responding_team_role_id in user_role_ids
    
    
    
    async def _update_only_time_field_in_private_embed(self):
        
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
                        
                        
                        existing_view_data = self._extract_current_view_state(message)
                        
                        
                        view = self._create_view_preserving_button_states(existing_view_data)
                        
                        
                        # TIMEZONE SUPPORT: Zeit mit Timezone formatieren
                        formatted_time = TimezoneHelper.format_time_with_timezone(self.offered_time, self.bot)
                        view.time_offer_button.disabled = True
                        view.time_offer_button.label = f"✅ Time Set: {formatted_time}"
                        view.time_offer_button.style = discord.ButtonStyle.success
                        
                        
                        self._update_only_time_field_in_embed(embed, formatted_time)
                        
                        
                        for i, field in enumerate(embed.fields):
                            if "Status" in field.name:
                                embed.set_field_at(i, name=field.name, value=f"⏳ Scheduled for {formatted_time} - Waiting for results", inline=field.inline)
                                break
                        
                        
                        embed.color = discord.Color.blue()
                        
                        
                        await message.edit(embed=embed, view=view)
                        
                        logger.info(f"✅ TIMEZONE: ONLY time field updated in private embed for match {self.match_id}")
                        break
            
        except Exception as e:
            logger.error(f"Error updating only time field in private embed: {e}")
    
    def _extract_current_view_state(self, message: discord.Message) -> Dict[str, Any]:
        
        try:
            view_data = {
                'server_offer_disabled': False,
                'server_offer_label': "🖥️ Offer Server",
                'server_offer_style': 'secondary',
                'result_submission_disabled': False,
                'result_submission_label': "📊 Submit Result",
                'result_submission_style': 'primary',
                'time_offer_disabled': False,
                'time_offer_label': "🕒 Offer Time",
                'time_offer_style': 'secondary'
            }
            
            if message.components:
                for action_row in message.components:
                    for component in action_row.children:
                        if hasattr(component, 'label') and component.label:
                            label = component.label
                            
                            
                            if "Server" in label or "🖥️" in label:
                                view_data['server_offer_disabled'] = component.disabled
                                view_data['server_offer_label'] = label
                                view_data['server_offer_style'] = component.style.name
                            
                            
                            elif "Result" in label or "📊" in label:
                                view_data['result_submission_disabled'] = component.disabled
                                view_data['result_submission_label'] = label
                                view_data['result_submission_style'] = component.style.name
                            
                            
                            elif "Time" in label or "🕒" in label:
                                view_data['time_offer_disabled'] = component.disabled
                                view_data['time_offer_label'] = label
                                view_data['time_offer_style'] = component.style.name
            
            return view_data
            
        except Exception as e:
            logger.error(f"Error extracting view state: {e}")
            return {}
    
    def _create_view_preserving_button_states(self, view_data: Dict[str, Any]):
        
        try:
            from ui.match_interactions.private_match_view import PrivateMatchView
            view = PrivateMatchView(self.bot, self.match_id, self.match_data)
            
            
            if view_data.get('server_offer_disabled'):
                view.server_offer_button.disabled = True
                view.server_offer_button.label = view_data.get('server_offer_label', "🖥️ Server Set")
                view.server_offer_button.style = getattr(discord.ButtonStyle, view_data.get('server_offer_style', 'success'), discord.ButtonStyle.success)
            
            
            if view_data.get('result_submission_disabled'):
                view.result_submission_button.disabled = True
                view.result_submission_button.label = view_data.get('result_submission_label', "📊 Result Submitted")
                view.result_submission_button.style = getattr(discord.ButtonStyle, view_data.get('result_submission_style', 'success'), discord.ButtonStyle.success)
            
            return view
            
        except Exception as e:
            logger.error(f"Error creating view with preserved states: {e}")
            from ui.match_interactions.private_match_view import PrivateMatchView
            return PrivateMatchView(self.bot, self.match_id, self.match_data)
    
    def _update_only_time_field_in_embed(self, embed: discord.Embed, time_value: str):
        
        try:
            
            time_field_updated = False
            for i, field in enumerate(embed.fields):
                if "Match Time" in field.name or "🕒" in field.name:
                    embed.set_field_at(i, name=field.name, value=time_value, inline=field.inline)
                    time_field_updated = True
                    break
            
            if not time_field_updated:
                
                
                insert_index = 1  
                for i, field in enumerate(embed.fields):
                    if "Date" in field.name or "📅" in field.name:
                        insert_index = i + 1
                        break
                
                embed.insert_field_at(insert_index, name="🕒 Match Time", value=time_value, inline=True)
            
        except Exception as e:
            logger.error(f"Error updating only time field: {e}")
    
    async def _update_only_time_field_in_public_embed(self):
        """
        TIMEZONE SUPPORT: Update time field in separate public match channel
        """
        try:
            # Channel ID für dieses Match aus Datenbank holen
            stored_channel_id = self.bot.db.get_setting(f'public_match_{self.match_id}_channel_id')
            if not stored_channel_id:
                logger.info(f"No public match channel found for match {self.match_id}")
                return
            
            # Channel direkt finden
            public_channel = None
            for guild in self.bot.guilds:
                channel = guild.get_channel(int(stored_channel_id))
                if channel:
                    public_channel = channel
                    break
            
            if not public_channel:
                logger.warning(f"Public match channel {stored_channel_id} not found for match {self.match_id}")
                return
            
            # Public message ID holen
            public_message_id = self.bot.db.get_setting(f'public_match_{self.match_id}_message_id')
            if not public_message_id:
                # Fallback: Suche nach der Match Embed Message im Channel
                async for message in public_channel.history(limit=10):
                    if (message.author == self.bot.user and 
                        message.embeds and 
                        message.embeds[0].footer and
                        f"Match ID: {self.match_id}" in message.embeds[0].footer.text):
                        
                        public_message_id = message.id
                        # Für zukünftige Updates speichern
                        self.bot.db.set_setting(f'public_match_{self.match_id}_message_id', str(message.id))
                        break
            
            if not public_message_id:
                logger.warning(f"No public message found for match {self.match_id}")
                return
            
            # Message holen und time field aktualisieren
            try:
                message = await public_channel.fetch_message(int(public_message_id))
                
                if message.embeds:
                    embed = message.embeds[0]
                    
                    # TIMEZONE SUPPORT: Zeit mit Timezone formatieren
                    formatted_time = TimezoneHelper.format_time_with_timezone(self.offered_time, self.bot)
                    
                    # Nur time field aktualisieren
                    for i, field in enumerate(embed.fields):
                        if "Match Time" in field.name or "🕒" in field.name:
                            embed.set_field_at(i, name=field.name, value=formatted_time, inline=field.inline)
                            break
                    
                    await message.edit(embed=embed)
                    logger.info(f"✅ TIMEZONE: ONLY time field updated in public embed for match {self.match_id}")
                    
            except discord.NotFound:
                logger.warning(f"Public message {public_message_id} not found for match {self.match_id}")
            except Exception as e:
                logger.error(f"Error updating public message: {e}")
                
        except Exception as e:
            logger.error(f"Error updating only time field in public embed: {e}")
    
    async def _update_only_time_field_in_streamer_embed(self):
        
        try:
            
            streamer_message_id = self.bot.db.get_match_streamer_message_id(self.match_id)
            if not streamer_message_id:
                return
            
            
            streamer_channel_id = self.bot.config['channels'].get('streamer_channel_id')
            if not streamer_channel_id:
                return
            
            for guild in self.bot.guilds:
                channel = guild.get_channel(streamer_channel_id)
                if channel:
                    try:
                        message = await channel.fetch_message(streamer_message_id)
                        
                        if message.embeds:
                            embed = message.embeds[0]
                            
                            # TIMEZONE SUPPORT: Zeit mit Timezone formatieren
                            formatted_time = TimezoneHelper.format_time_with_timezone(self.offered_time, self.bot)
                            
                            
                            for i, field in enumerate(embed.fields):
                                if "Match Time" in field.name or "🕒" in field.name:
                                    embed.set_field_at(i, name=field.name, value=formatted_time, inline=field.inline)
                                    break
                            
                            
                            await message.edit(embed=embed)
                            logger.info(f"✅ TIMEZONE: ONLY time field updated in streamer embed for match {self.match_id}")
                        return
                        
                    except discord.NotFound:
                        continue
            
        except Exception as e:
            logger.error(f"Error updating only time field in streamer embed: {e}")
    
    async def _notify_streamer(self):
        
        try:
            streamers = self.bot.db.get_match_streamers_detailed(self.match_id)
            if not streamers:
                return
            
            streamer_data = streamers[0]
            streamer_id = streamer_data['streamer_id']
            
            
            streamer_notification_channel_id = self.bot.config['channels'].get('streamer_notification_channel_id')
            if not streamer_notification_channel_id:
                logger.warning("No streamer notification channel configured")
                return
            
            streamer_notification_channel = None
            for guild in self.bot.guilds:
                channel = guild.get_channel(streamer_notification_channel_id)
                if channel:
                    streamer_notification_channel = channel
                    break
            
            if not streamer_notification_channel:
                logger.warning(f"Streamer notification channel {streamer_notification_channel_id} not found")
                return
            
            
            streamer_user = self.bot.get_user(streamer_id)
            if not streamer_user:
                return
            
            # TIMEZONE SUPPORT: Zeit mit Timezone formatieren
            formatted_time = TimezoneHelper.format_time_with_timezone(self.offered_time, self.bot)
            timezone_warning = TimezoneHelper.get_timezone_warning_text(self.bot)
            
            
            embed = discord.Embed(
                title="🕒 Match Time Set!",
                description=f"The match you're streaming has been scheduled!",
                color=discord.Color.blue()
            )
            embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            embed.add_field(name="📅 Date", value=self.match_data.get('match_date', 'TBA'), inline=True)
            embed.add_field(name="🕒 Time", value=formatted_time, inline=True)
            embed.add_field(name="🗺️ Map", value=self.match_data.get('map_name', 'TBA'), inline=True)
            
            # TIMEZONE SUPPORT: Timezone-Info hinzufügen
            embed.add_field(name="⏰ Timezone Info", value=timezone_warning, inline=False)
   
            await streamer_notification_channel.send(f"{streamer_user.mention}", embed=embed, delete_after=60)
            
            logger.info(f"TIMEZONE: Streamer {streamer_user} notified about match time {formatted_time} in notification channel")
            
        except Exception as e:
            logger.error(f"Error notifying streamer: {e}")
    
    async def on_timeout(self):
        
        try:
            for item in self.children:
                item.disabled = True
            
            # TIMEZONE SUPPORT: Zeit mit Timezone formatieren für Timeout-Message
            formatted_time = TimezoneHelper.format_time_with_timezone(self.offered_time, self.bot)
            
            
            embed = discord.Embed(
                title="⏰ Time Offer Expired",
                description=f"The time offer for **{formatted_time}** has expired.",
                color=discord.Color.orange()
            )
            embed.add_field(name="🕒 Expired Offer", value=formatted_time, inline=True)
            embed.add_field(name="👥 Offered by", value=self.offering_team, inline=True)  
            embed.add_field(name="ℹ️ Status", value="Expired - can be resubmitted", inline=True)
            
            message = await self._get_message_from_stored_ids()
            if message:
                await message.edit(embed=embed, view=self)
                
                
                self.bot.db.complete_ongoing_interaction(message.id)
            
            
            await self._re_enable_time_offer_button()
            
            logger.info(f"Time offer view timed out for match {self.match_id}")
            
        except Exception as e:
            logger.error(f"Error handling timeout: {e}")
    
    async def _re_enable_time_offer_button(self):
        
        try:
            
            cursor = self.bot.db.conn.cursor()
            cursor.execute('SELECT private_channel_id FROM matches WHERE id = ?', (self.match_id,))
            result = cursor.fetchone()
            
            if not result or not result[0]:
                return
            
            private_channel = self.bot.get_channel(result[0])
            if not private_channel:
                return
            
            
            current_match_data = self.bot.db.get_match_details(self.match_id)
            if current_match_data and current_match_data[4]:  
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
                        
                        
                        view.time_offer_button.disabled = False
                        view.time_offer_button.label = "🕒 Offer Match Time"
                        view.time_offer_button.style = discord.ButtonStyle.primary
                        
                        await message.edit(embed=embed, view=view)
                        
                        logger.info(f"Time Offer button re-enabled after timeout for match {self.match_id}")
                        break
            
        except Exception as e:
            logger.error(f"Error re-enabling time offer button: {e}")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        
        logger.error(f"Error in TimeOfferView for match {self.match_id}: {error}")
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing the time offer. Please try again or contact an admin.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ An error occurred while processing the time offer. Please try again or contact an admin.",
                    ephemeral=True
                )
                
            
            message = await self._get_message_from_stored_ids()
            if message:
                self.bot.db.complete_ongoing_interaction(message.id)
                
        except:
            pass