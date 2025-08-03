# ui/match_interactions/orga_result_confirmation.py
"""
COMPLETE FIXED Orga Result Confirmation - Updated für separate Public Match Channels
Speichere als: ui/match_interactions/orga_result_confirmation.py
"""

import discord
import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

class OrgaResultConfirmationView(discord.ui.View):
 
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any], result_data: Dict[str, Any]):
        super().__init__(timeout=None)
        self.bot = bot
        self.match_id = match_id
        self.match_data = match_data
        self.result_data = result_data
        
        self.message = None
        self.message_id = None
        self.channel_id = None
        self.guild_id = None
        self.supersede_view = None
        
        timestamp = int(datetime.now().timestamp())
        self.confirm_button.custom_id = f"orga_confirm_result_{match_id}_{timestamp}"
        self.edit_button.custom_id = f"orga_edit_result_{match_id}_{timestamp}"
    
    async def _get_message_from_stored_ids(self) -> discord.Message:
        try:
            if not self.message_id or not self.channel_id or not self.guild_id:
                logger.error("No stored message/channel/guild IDs available for orga confirmation")
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
                logger.debug(f"Successfully retrieved orga confirmation message {self.message_id}")
                return message
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving orga confirmation message from stored IDs: {e}")
            return None
    
    def restore_from_persistence_data(self, persistence_data: Dict[str, Any]):
        try:
            submission_data = persistence_data.get('data', {})
            self.message_id = submission_data.get('message_id')
            self.channel_id = submission_data.get('channel_id')  
            self.guild_id = submission_data.get('guild_id')
            
            if 'result_data' in submission_data:
                self.result_data = submission_data['result_data']
            
            if 'match_data' in submission_data:
                self.match_data = submission_data['match_data']
            
            logger.debug(f"✅ Restored orga result confirmation view with message_id: {self.message_id}")
            
        except Exception as e:
            logger.error(f"Error restoring orga result confirmation view from persistence: {e}")
    
    @discord.ui.button(label='✅ Confirm Result', style=discord.ButtonStyle.success, custom_id='orga_confirm_result')
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == self.bot.EVENT_ORGA_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("❌ Only Event Orga can confirm results!", ephemeral=True)
            return
        
        try:
            await interaction.response.defer()
            
            self.bot.db.confirm_match_result(self.match_id)
            
            match_details = self.bot.db.get_match_details(self.match_id)
            
            # GEÄNDERT: Update Public Match in separatem Channel
            if match_details:
                await self._update_public_match_in_separate_channel(match_details)
            
            await self._disable_submit_result_button()
            
            await self._update_private_embed_with_streamer_info()
            
            await self._archive_match_channel_preserve_server(interaction)
            
            await self._update_streamer_embeds_final_with_persistence()
            
            try:
                await self.bot.status_manager.update_channel_status(self.match_id, 'completed')
                logger.info(f"✅ Status updated to 'completed' for match {self.match_id}")
            except Exception as status_error:
                logger.error(f"Error updating status to completed for match {self.match_id}: {status_error}")
            
            # FIXED: Embed erst nach allen Operationen erstellen
            embed = discord.Embed(
                title="✅ Result Confirmed!",
                description=f"Match result has been officially confirmed and archived.",
                color=discord.Color.green()
            )
            embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            embed.add_field(name="🥇 Winner", value=f"**{self.result_data['winner']}**", inline=True)
            embed.add_field(name="📊 Score", value=f"**{self.result_data['score']}**", inline=True)
            embed.add_field(name="👤 Confirmed by", value=interaction.user.mention, inline=True)
            embed.add_field(name="ℹ️ Status", value="✅ Public embed updated\n✅ Private channel archived\n✅ Private button disabled\n✅ Streamer embeds updated\n✅ Server details preserved\n✅ Persistence synchronized", inline=False)
            
            for item in self.children:
                item.disabled = True
            
            await interaction.edit_original_response(embed=embed, view=self)
            
            if hasattr(self, 'supersede_view') and self.supersede_view:
                await self._disable_superseded_view_after_confirmation()
            
            logger.info(f"Match {self.match_id} result confirmed by {interaction.user} - COMPLETE WITH PUBLIC EMBED UPDATE")
            
        except Exception as e:
            import traceback
            logger.error(f"❌ ERROR in result confirmation: {e}")
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            
            # FIXED: Fallback-Embed für Fehlerfall
            try:
                error_embed = discord.Embed(
                    title="❌ Error Confirming Result",
                    description="An error occurred while confirming the match result. Please try again or contact an admin.",
                    color=discord.Color.red()
                )
                error_embed.add_field(name="🆔 Match ID", value=str(self.match_id), inline=True)
                error_embed.add_field(name="❌ Error", value=str(e)[:1000], inline=False)
                
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
            except Exception as fallback_error:
                logger.error(f"❌ Could not send error message: {fallback_error}")
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message("❌ Error confirming result!", ephemeral=True)
                    else:
                        await interaction.followup.send("❌ Error confirming result!", ephemeral=True)
                except:
                    pass
    
    async def _update_public_match_in_separate_channel(self, match_details):
        """
        NEUE Methode: Update Public Match Embed in separatem Channel
        """
        try:
            # Channel ID für dieses Match aus Datenbank holen
            stored_channel_id = self.bot.db.get_setting(f'public_match_{self.match_id}_channel_id')
            if not stored_channel_id:
                logger.warning(f"No public match channel found for match {self.match_id}")
                return
            
            # Channel finden
            channel = None
            for guild in self.bot.guilds:
                channel = guild.get_channel(int(stored_channel_id))
                if channel:
                    break
            
            if not channel:
                logger.warning(f"Public match channel {stored_channel_id} not found for match {self.match_id}")
                return
            
            # Letzte Message in diesem Channel finden (sollte das Match Embed sein)
            async for message in channel.history(limit=10):
                if (message.author == self.bot.user and 
                    message.embeds and 
                    message.embeds[0].footer and
                    f"Match ID: {self.match_id}" in message.embeds[0].footer.text):
                    
                    embed = message.embeds[0]
                    
                    # Result hinzufügen
                    result_text = f"||**{self.result_data['winner']}** wins ({self.result_data['score']})||"
                    
                    result_field_found = False
                    for i, field in enumerate(embed.fields):
                        if "Result" in field.name or "📊" in field.name or "result" in field.name.lower():
                            embed.set_field_at(i, name=field.name, value=result_text, inline=field.inline)
                            result_field_found = True
                            break
                    
                    if not result_field_found:
                        embed.add_field(name="📊 Result", value=result_text, inline=False)
                    
                    embed.color = discord.Color.green()
                    
                    await message.edit(embed=embed)
                    logger.info(f"✅ Public match embed updated in separate channel for match {self.match_id}")
                    break
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Error updating public match in separate channel: {e}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
    
    async def _disable_superseded_view_after_confirmation(self):
        try:
            if not self.supersede_view:
                return
            
            for item in self.supersede_view.children:
                item.disabled = True
            
            embed = discord.Embed(
                title="✅ Result Confirmed by Event Orga",
                description=f"Event Orga has confirmed the final result. This confirmation request is no longer active.",
                color=discord.Color.green()
            )
            embed.add_field(name="🥇 Final Winner", value=self.result_data['winner'], inline=True)
            embed.add_field(name="📊 Final Score", value=self.result_data['score'], inline=True)
            embed.add_field(name="ℹ️ Status", value="Confirmed and archived by Event Orga", inline=True)
            
            superseded_message = None
            
            if hasattr(self.supersede_view, 'message') and self.supersede_view.message:
                superseded_message = self.supersede_view.message
                logger.info("✅ Using direct message reference for superseded orga view")
            
            elif (hasattr(self.supersede_view, 'message_id') and self.supersede_view.message_id and
                  hasattr(self.supersede_view, 'channel_id') and self.supersede_view.channel_id and
                  hasattr(self.supersede_view, 'guild_id') and self.supersede_view.guild_id):
                
                try:
                    guild = self.bot.get_guild(self.supersede_view.guild_id)
                    if guild:
                        channel = guild.get_channel(self.supersede_view.channel_id)
                        if channel:
                            superseded_message = await channel.fetch_message(self.supersede_view.message_id)
                            logger.info(f"✅ Retrieved superseded orga message from stored IDs: {self.supersede_view.message_id}")
                except Exception as fetch_error:
                    logger.error(f"Could not fetch superseded orga message from stored IDs: {fetch_error}")
            
            else:
                logger.warning("No message reference or stored IDs - trying database lookup for orga confirmation")
                try:
                    cursor = self.bot.db.conn.cursor()
                    cursor.execute('''
                        SELECT message_id, channel_id, guild_id 
                        FROM ui_messages 
                        WHERE message_type = 'orga_result_confirmation' 
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
                                    
                                    if test_message.embeds and not any("Result Confirmed by Event Orga" in embed.title for embed in test_message.embeds):
                                        superseded_message = test_message
                                        logger.info(f"✅ Found superseded orga message via database: {message_id}")
                                        break
                        except:
                            continue
                            
                except Exception as db_error:
                    logger.error(f"Database lookup for superseded orga message failed: {db_error}")
            
            if superseded_message:
                await superseded_message.edit(embed=embed, view=self.supersede_view)
                
                self.bot.db.complete_ongoing_interaction(superseded_message.id)
                
                logger.info(f"✅ Successfully disabled superseded orga confirmation view: {superseded_message.id}")
            else:
                logger.error(f"❌ Could not find superseded orga message to disable for match {self.match_id}")
            
        except Exception as e:
            logger.error(f"Error disabling superseded orga view: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
    
    async def _update_streamer_embeds_final_with_persistence(self):
        try:
            message, channel = await self._find_streamer_message()
            
            if not message or not channel:
                logger.info(f"No streamer message found for match {self.match_id}")
                return
            
            if not message.embeds:
                return
            
            embed = message.embeds[0]
            
            if "✅" not in embed.title:
                embed.title = f"✅ {embed.title.replace('📺', '').strip()}"
            
            embed.color = discord.Color.green()
            
            result_text = f"**{self.result_data['winner']}** wins ({self.result_data['score']})"
            
            result_field_found = False
            for i, field in enumerate(embed.fields):
                if "Status" in field.name or ("📺" in field.name and "Status" in field.name):
                    embed.set_field_at(i, name="📺 Final Result", value=f"✅ **COMPLETED**\n{result_text}", inline=field.inline)
                    result_field_found = True
                    break
            
            if not result_field_found:
                embed.add_field(name="📺 Final Result", value=f"✅ **COMPLETED**\n{result_text}", inline=False)
            
            await message.edit(embed=embed)
            
            logger.info(f"✅ Streamer embed updated WITHOUT changing buttons for match {self.match_id}")
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Error updating streamer embed: {e}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
    
    async def _find_streamer_message(self):
        try:
            streamer_message_id = self.bot.db.get_match_streamer_message_id(self.match_id)
            if not streamer_message_id:
                return None, None
            
            streamer_channel_id = self.bot.config['channels'].get('streamer_channel_id')
            if not streamer_channel_id:
                return None, None
            
            for guild in self.bot.guilds:
                channel = guild.get_channel(streamer_channel_id)
                if channel:
                    try:
                        message = await channel.fetch_message(streamer_message_id)
                        return message, channel
                    except discord.NotFound:
                        pass
                    except Exception as e:
                        pass
            
            return None, None
            
        except Exception as e:
            return None, None
    
    async def _disable_submit_result_button(self):
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
                        
                        view.result_submission_button.disabled = True
                        view.result_submission_button.label = "✅ Results Confirmed"
                        view.result_submission_button.style = discord.ButtonStyle.success
                        
                        embed.color = discord.Color.green()
                        
                        for i, field in enumerate(embed.fields):
                            if "Status" in field.name:
                                embed.set_field_at(i, name=field.name, value="✅ Match completed and confirmed", inline=field.inline)
                                break
                        
                        await message.edit(embed=embed, view=view)
                        logger.info(f"Submit Result button disabled for match {self.match_id}")
                        break
            
        except Exception as e:
            logger.error(f"Error disabling submit result button: {e}")
    
    async def _update_private_embed_with_streamer_info(self):
        try:
            cursor = self.bot.db.conn.cursor()
            cursor.execute('SELECT private_channel_id FROM matches WHERE id = ?', (self.match_id,))
            result = cursor.fetchone()
            
            if not result or not result[0]:
                return
            
            private_channel = self.bot.get_channel(result[0])
            if not private_channel:
                return
            
            streamers = self.bot.db.get_match_streamers_detailed(self.match_id)
            
            async for message in private_channel.history(limit=50, oldest_first=True):
                if (message.author == self.bot.user and 
                    message.embeds and 
                    message.embeds[0].footer and 
                    f"Match ID: {self.match_id}" in message.embeds[0].footer.text):
                    
                    embed = message.embeds[0]
                    
                    if streamers and len(streamers) > 0:
                        streamer_data = streamers[0]
                        stream_url = streamer_data.get('stream_url', '')
                        
                        if self.bot:
                            user = self.bot.get_user(streamer_data['streamer_id'])
                            username = user.display_name if user else f"User {streamer_data['streamer_id']}"
                        else:
                            username = f"User {streamer_data['streamer_id']}"
                        
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
                    
                    await message.edit(embed=embed)
                    logger.info(f"Private embed updated with streamer info for match {self.match_id}")
                    break
            
        except Exception as e:
            logger.error(f"Error updating private embed with streamer info: {e}")
    
    async def _archive_match_channel_preserve_server(self, interaction):
        try:
            archive_category_id = self.bot.config['categories'].get('archive_category_id')
            if not archive_category_id:
                logger.warning("No archive category configured in config.json")
                return
            
            archive_category = interaction.guild.get_channel(archive_category_id)
            if not archive_category:
                logger.warning(f"Archive category {archive_category_id} not found")
                return
            
            cursor = self.bot.db.conn.cursor()
            cursor.execute('SELECT private_channel_id FROM matches WHERE id = ?', (self.match_id,))
            result = cursor.fetchone()
            
            if not result or not result[0]:
                return
            
            private_channel = interaction.guild.get_channel(result[0])
            if not private_channel:
                return
            
            server_data_json = self.bot.db.get_setting(f'match_{self.match_id}_server')
            server_details = None
            if server_data_json:
                try:
                    server_details = json.loads(server_data_json)
                except:
                    pass
            
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
            
            overwrites = private_channel.overwrites
            
            if team1_role_id:
                team1_role = interaction.guild.get_role(team1_role_id)
                if team1_role and team1_role in overwrites:
                    del overwrites[team1_role]
            
            if team2_role_id:
                team2_role = interaction.guild.get_role(team2_role_id)
                if team2_role and team2_role in overwrites:
                    del overwrites[team2_role]
            
            await private_channel.edit(
                category=archive_category,
                overwrites=overwrites,
                name=f"archived-{private_channel.name}"
            )
            
            archive_embed = discord.Embed(
                title="📁 Match Archived",
                description="This match has been completed and archived.",
                color=discord.Color.dark_grey()
            )
            archive_embed.add_field(name="🏆 Final Result", value=f"**{self.result_data['winner']}** wins {self.result_data['score']}", inline=False)
            archive_embed.add_field(name="👤 Confirmed by", value=interaction.user.mention, inline=True)
            
            if server_details:
                server_text = f"**{server_details['server_name']}**\nPassword: `{server_details['server_password']}`\nProvided by: {server_details['offering_team']}"
                archive_embed.add_field(name="🖥️ Server Details", value=server_text, inline=False)
            
            await private_channel.send(embed=archive_embed)
            
            logger.info(f"Match {self.match_id} channel archived successfully with server preservation")
            
        except Exception as e:
            logger.error(f"Error archiving match channel: {e}")
    
    @discord.ui.button(label='✏️ Edit Result', style=discord.ButtonStyle.secondary, custom_id='orga_edit_result')
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == self.bot.EVENT_ORGA_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("❌ Only Event Orga can edit results!", ephemeral=True)
            return
        
        real_match_data = self._get_real_team_names_from_config()
        
        edit_view = OrgaResultEditView(self.bot, self.match_id, real_match_data, interaction.user)
        
        edit_view.supersede_view = self
        
        embed = discord.Embed(
            title="✏️ Edit Match Result",
            description="Please correct the match result:",
            color=discord.Color.orange()
        )
        embed.add_field(name="🏆 Match", value=f"{real_match_data['team1_name']} vs {real_match_data['team2_name']}", inline=False)
        embed.add_field(name="ℹ️ Instructions", value="1. Select the correct winning team\n2. Select the correct final score", inline=False)
        
        await interaction.response.send_message(embed=embed, view=edit_view, ephemeral=True)

    async def disable_this_view_as_superseded(self, superseding_message_info: str = ""):
        try:
            for item in self.children:
                item.disabled = True
            
            embed = discord.Embed(
                title="🔄 Superseded by New Confirmation",
                description=f"A new result confirmation has been created. This confirmation is no longer active.",
                color=discord.Color.orange()
            )
            embed.add_field(name="🥇 Original Winner", value=self.result_data.get('winner', 'Unknown'), inline=True)
            embed.add_field(name="📊 Original Score", value=self.result_data.get('score', 'Unknown'), inline=True)
            embed.add_field(name="ℹ️ Status", value=f"Superseded by new confirmation{superseding_message_info}", inline=True)
            
            superseded_message = None
            
            if (hasattr(self, 'message_id') and self.message_id and
                hasattr(self, 'channel_id') and self.channel_id and
                hasattr(self, 'guild_id') and self.guild_id):
                
                try:
                    guild = self.bot.get_guild(self.guild_id)
                    if guild:
                        channel = guild.get_channel(self.channel_id)
                        if channel:
                            superseded_message = await channel.fetch_message(self.message_id)
                            logger.info(f"✅ Retrieved orga confirmation message for superseding: {self.message_id}")
                except Exception as fetch_error:
                    logger.error(f"Could not fetch orga confirmation message for superseding: {fetch_error}")
            
            if superseded_message:
                await superseded_message.edit(embed=embed, view=self)
                
                self.bot.db.complete_ongoing_interaction(superseded_message.id)
                
                logger.info(f"✅ Successfully disabled superseded orga confirmation view: {superseded_message.id}")
                return True
            else:
                logger.error(f"❌ Could not find orga confirmation message to disable for match {self.match_id}")
                return False
            
        except Exception as e:
            logger.error(f"Error disabling superseded orga confirmation view: {e}")
            return False
    
    def _get_real_team_names_from_config(self) -> Dict[str, Any]:
        try:
            match_details = self.bot.db.get_match_details(self.match_id)
            if not match_details:
                return self.match_data
            
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
                    all_teams = self.bot.get_all_teams()
                    for team_tuple in all_teams:
                        team_config_id, name, role_id, members, active = team_tuple
                        
                        if team_config_id == team1_id:
                            team1_name = name
                        elif team_config_id == team2_id:
                            team2_name = name
                except Exception as config_error:
                    logger.error(f"Could not get team names from config: {config_error}")
            
            updated_match_data = self.match_data.copy()
            updated_match_data['team1_name'] = team1_name
            updated_match_data['team2_name'] = team2_name
            updated_match_data['match_id'] = self.match_id
            
            logger.info(f"Real team names for match {self.match_id}: {team1_name} vs {team2_name}")
            
            return updated_match_data
            
        except Exception as e:
            logger.error(f"Error getting real team names: {e}")
            return self.match_data


class StreamerMatchViewDisabled(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        
        completed_button = discord.ui.Button(
            label='✅ Match Completed', 
            style=discord.ButtonStyle.success,
            disabled=True,
            emoji='🏆',
            custom_id=f"match_completed_{int(datetime.now().timestamp())}"
        )
        
        self.add_item(completed_button)
        
        logger.debug("Created disabled streamer view with 'Match Completed' button")

class OrgaResultEditView(discord.ui.View):
    
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any], submitting_user):
        super().__init__(timeout=None)
        self.bot = bot
        self.match_id = match_id
        self.match_data = match_data
        self.submitting_user = submitting_user
        self.supersede_view = None
        
        winner_options = [
            discord.SelectOption(label=match_data['team1_name'], value=match_data['team1_name']),
            discord.SelectOption(label=match_data['team2_name'], value=match_data['team2_name'])
        ]
        
        timestamp = int(datetime.now().timestamp())
        self.winner_select = discord.ui.Select(
            placeholder="Select winning team...",
            options=winner_options,
            custom_id=f"orga_winner_select_{match_id}_{timestamp}"
        )
        self.winner_select.callback = self.winner_selected
        
        score_options = [
            discord.SelectOption(label="2-0 (Won 2 rounds, lost 0)", value="2-0"),
            discord.SelectOption(label="2-1 (Won 2 rounds, lost 1)", value="2-1")
        ]
        
        self.score_select = discord.ui.Select(
            placeholder="Select score...",
            options=score_options,
            custom_id=f"orga_score_select_{match_id}_{timestamp}",
            disabled=True
        )
        self.score_select.callback = self.score_selected
        
        self.add_item(self.winner_select)
        self.add_item(self.score_select)
        
        self.selected_winner = None
        self.selected_score = None
    
    async def winner_selected(self, interaction: discord.Interaction):
        self.selected_winner = self.winner_select.values[0]
        
        self.score_select.disabled = False
        self.winner_select.disabled = True
        
        await interaction.response.edit_message(view=self)
    
    async def score_selected(self, interaction: discord.Interaction):
        self.selected_score = self.score_select.values[0]
        
        try:
            corrected_result = {
                'winner': self.selected_winner,
                'score': self.selected_score,
                'submitted_by_team': 'Event Orga',
                'submitted_by_user': self.submitting_user.id,
                'submitted_at': datetime.now().isoformat()
            }
            
            self.bot.db.update_match_result(self.match_id, corrected_result)
            
            for item in self.children:
                item.disabled = True
            
            embed = discord.Embed(
                title="✅ Result Corrected!",
                description="Event Orga has corrected the match result:",
                color=discord.Color.green()
            )
            embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            embed.add_field(name="🥇 Winner", value=f"**{self.selected_winner}**", inline=True)
            embed.add_field(name="📊 Score", value=f"**{self.selected_score}**", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            try:
                from ui.streamer_management.streamer_match_manager import StreamerMatchManager
                streamer_manager = StreamerMatchManager(self.bot)
                await streamer_manager.update_all_match_posts_including_private(self.match_id)
                logger.info(f"✅ Streamer embeds updated after orga result correction for match {self.match_id}")
            except Exception as streamer_error:
                logger.warning(f"Could not update streamer embeds after orga correction: {streamer_error}")
            
            final_view = OrgaResultConfirmationView(self.bot, self.match_id, self.match_data, corrected_result)
            
            final_view.supersede_view = self.supersede_view
            
            final_embed = discord.Embed(
                title="🚨 Corrected Result - Final Confirmation",
                description="Result has been corrected. Please confirm to finalize:",
                color=discord.Color.gold()
            )
            final_embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            final_embed.add_field(name="🥇 Winner", value=f"**{self.selected_winner}**", inline=True)
            final_embed.add_field(name="📊 Score", value=f"**{self.selected_score}**", inline=True)
            
            channel_message = await interaction.followup.send(
                embed=final_embed, 
                view=final_view, 
                ephemeral=False
            )
            
            try:
                if channel_message and hasattr(channel_message, 'id'):
                    actual_message_id = channel_message.id
                    channel_id = interaction.channel.id
                    guild_id = interaction.guild.id
                    
                    final_view.message = channel_message
                    final_view.message_id = actual_message_id
                    final_view.channel_id = channel_id
                    final_view.guild_id = guild_id
                    
                    try:
                        if hasattr(self.bot, 'lazy_persistence'):
                            persistence_data = {
                                'result_data': corrected_result,
                                'match_data': self.match_data,
                                'message_id': actual_message_id,
                                'channel_id': channel_id,
                                'guild_id': guild_id
                            }
                            
                            await self.bot.lazy_persistence.register_view(channel_message, 'orga_result_confirmation', self.match_id, persistence_data)
                            logger.info(f"✅ Orga result edit final confirmation registered with lazy persistence: {actual_message_id}")
                    except Exception as lazy_persistence_error:
                        logger.error(f"Error with lazy persistence registration: {lazy_persistence_error}")
                    
                    try:
                        ui_data = {
                            'view_type': 'orga_result_confirmation',
                            'registered_at': datetime.now().isoformat(),
                            'data': {
                                'result_data': corrected_result,
                                'match_data': self.match_data,
                                'message_id': actual_message_id,
                                'channel_id': channel_id,
                                'guild_id': guild_id
                            }
                        }
                        
                        self.bot.db.register_ui_message(
                            actual_message_id, channel_id, guild_id,
                            'orga_result_confirmation', ui_data, self.match_id
                        )
                        
                        buttons_data = []
                        for item in final_view.children:
                            if hasattr(item, 'custom_id') and item.custom_id:
                                buttons_data.append({
                                    'id': item.custom_id,
                                    'label': item.label,
                                    'disabled': item.disabled,
                                    'style': item.style.name,
                                    'data': {}
                                })
                        
                        if buttons_data:
                            self.bot.db.save_button_states(actual_message_id, buttons_data)
                            logger.info(f"✅ Orga result edit final confirmation registered for Fast Startup with {len(buttons_data)} buttons")
                    except Exception as db_registration_error:
                        logger.error(f"Error with database registration: {db_registration_error}")
                    
                    self.bot.add_view(final_view)
                    
                    logger.info(f"✅ Orga result edit final confirmation registered with persistence: {actual_message_id}")
                else:
                    logger.error("No valid message returned from followup.send")
                    self.bot.add_view(final_view)
                    
            except Exception as message_handling_error:
                logger.error(f"Error handling message for persistence registration: {message_handling_error}")
                self.bot.add_view(final_view)
            
        except Exception as e:
            logger.error(f"Error in orga edit score selection: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            try:
                await interaction.response.send_message("❌ Error correcting result!", ephemeral=True)
            except:
                try:
                    await interaction.followup.send("❌ Error correcting result!", ephemeral=True)
                except:
                    pass