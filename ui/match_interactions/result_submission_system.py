# ui/match_interactions/result_submission_system.py
"""
Result Submission System
"""


import discord
import logging
import json
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ResultSubmissionModal(discord.ui.Modal):
    pass

class SimpleResultView(discord.ui.View):
    
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any], submitting_user: discord.Member):
        super().__init__(timeout=300)
        self.bot = bot
        self.match_id = match_id
        self.submitting_user = submitting_user
        self.supersede_view = None
        
        self.match_data = self._get_real_team_names_from_config(match_data)
        
        
        winner_options = [
            discord.SelectOption(label=self.match_data['team1_name'], value=self.match_data['team1_name']),
            discord.SelectOption(label=self.match_data['team2_name'], value=self.match_data['team2_name'])
        ]
        
        self.winner_select = discord.ui.Select(
            placeholder="Select winning team...",
            options=winner_options,
            custom_id=f"winner_select_{match_id}_{int(datetime.now().timestamp())}"
        )
        self.winner_select.callback = self.winner_selected
        
        
        score_options = [
            discord.SelectOption(label="2-0 (Won 2 rounds, lost 0)", value="2-0"),
            discord.SelectOption(label="2-1 (Won 2 rounds, lost 1)", value="2-1")
        ]
        
        self.score_select = discord.ui.Select(
            placeholder="Select score...",
            options=score_options,
            custom_id=f"score_select_{match_id}_{int(datetime.now().timestamp())}",
            disabled=True
        )
        self.score_select.callback = self.score_selected
        
        self.add_item(self.winner_select)
        self.add_item(self.score_select)
        
        self.selected_winner = None
        self.selected_score = None
        
    def _get_real_team_names_from_config(self, fallback_match_data: Dict[str, Any]) -> Dict[str, Any]:
        
        try:
            
            match_details = self.bot.db.get_match_details(self.match_id)
            if not match_details:
                return fallback_match_data
            
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
                    logger.debug(f"Could not get team names from config: {config_error}")
            
            
            updated_match_data = fallback_match_data.copy()
            updated_match_data['team1_name'] = team1_name
            updated_match_data['team2_name'] = team2_name
            updated_match_data['match_id'] = self.match_id
            
            logger.info(f"Real team names for result submission match {self.match_id}: {team1_name} vs {team2_name}")
            
            return updated_match_data
            
        except Exception as e:
            logger.error(f"Error getting real team names for result submission: {e}")
            return fallback_match_data

    async def winner_selected(self, interaction: discord.Interaction):
        
        self.selected_winner = self.winner_select.values[0]
        
        
        self.score_select.disabled = False
        self.winner_select.disabled = True
        
        await interaction.response.edit_message(view=self)
    
    async def score_selected(self, interaction: discord.Interaction):
        
        self.selected_score = self.score_select.values[0]
        
        try:
            
            if interaction.response.is_done():
                logger.warning("Interaction already responded to, using followup")
                await interaction.followup.send("⚠️ Processing your submission...", ephemeral=True)
                return
            
            
            submitting_team_info = self._get_user_team_info_with_real_names(self.submitting_user)
            if not submitting_team_info:
                await interaction.response.send_message("❌ Could not determine your team!", ephemeral=True)
                return
            
            submitting_team_name, other_team_name, other_team_role_id = submitting_team_info
            
            
            await self._disable_submit_result_button_on_first_submission()
            
            
            result_data = {
                'winner': self.selected_winner,
                'score': self.selected_score,
                'submitted_by_team': submitting_team_name,
                'submitted_by_user': self.submitting_user.id,
                'submitted_at': datetime.now().isoformat()
            }
            
            
            embed = discord.Embed(
                title="📊 Match Result Submission",
                description=f"**{submitting_team_name}** has submitted the following result:",
                color=discord.Color.orange()
            )
            
            embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            embed.add_field(name="🥇 Winner", value=f"**{self.selected_winner}**", inline=True)
            embed.add_field(name="📊 Score", value=f"**{self.selected_score}**", inline=True)
            embed.add_field(name="🗺️ Map", value=self.match_data.get('map_name', 'TBA'), inline=True)
            
            
            for item in self.children:
                item.disabled = True
            
            
            try:
                await interaction.response.edit_message(
                    content="✅ Result submitted successfully!",
                    embed=embed, 
                    view=self
                )
            except discord.NotFound:
                logger.warning("Interaction not found, using followup for result submission")
                await interaction.followup.send(
                    content="✅ Result submitted successfully!",
                    embed=embed,
                    ephemeral=True
                )
            
            
            public_view = ResultSubmissionView(
                self.bot, self.match_id, self.match_data, result_data, 
                submitting_team_name, other_team_name, other_team_role_id
            )
            
            
            other_team_role = interaction.guild.get_role(other_team_role_id)
            mention_text = f"{other_team_role.mention} **{submitting_team_name}** has submitted match results. Please review and confirm:"
            
            public_embed = discord.Embed(
                title="📊 Match Result Submission",
                description=f"**{submitting_team_name}** has submitted the following result:",
                color=discord.Color.orange()
            )
            public_embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            public_embed.add_field(name="🥇 Winner", value=f"**{self.selected_winner}**", inline=True)
            public_embed.add_field(name="📊 Score", value=f"**{self.selected_score}**", inline=True)
            public_embed.add_field(name="🗺️ Map", value=self.match_data.get('map_name', 'TBA'), inline=True)
            
            
            webhook_message = await interaction.followup.send(mention_text, embed=public_embed, view=public_view)
            
            
            try:
                
                if webhook_message and hasattr(webhook_message, 'id'):
                    message_id = webhook_message.id
                    channel_id = interaction.channel.id
                    guild_id = interaction.guild.id
                    
                    
                    public_view.message = webhook_message  
                    public_view.message_id = message_id     
                    public_view.channel_id = channel_id     
                    public_view.guild_id = guild_id         
                    
                    
                    if hasattr(self.bot, 'lazy_persistence'):
                        persistence_data = {
                            'result_data': result_data,
                            'responding_team_role_id': other_team_role_id,
                            'submitting_team': submitting_team_name,
                            'responding_team': other_team_name,
                            'message_id': message_id,      
                            'channel_id': channel_id,      
                            'guild_id': guild_id           
                        }
                        
                        
                        ui_data = {
                            'view_type': 'result_submission',
                            'registered_at': datetime.now().isoformat(),
                            'data': persistence_data
                        }
                        
                        self.bot.db.register_ui_message(
                            message_id, channel_id, guild_id,
                            'result_submission', ui_data, self.match_id
                        )
                        
                        
                        buttons_data = []
                        for item in public_view.children:
                            if hasattr(item, 'custom_id') and item.custom_id:
                                buttons_data.append({
                                    'id': item.custom_id,
                                    'label': item.label,
                                    'disabled': item.disabled,
                                    'style': item.style.name,
                                    'data': {}
                                })
                        
                        if buttons_data:
                            self.bot.db.save_button_states(message_id, buttons_data)
                            logger.info(f"✅ Result submission view registered for persistence with {len(buttons_data)} buttons")
                        
                        
                        self.bot.add_view(public_view)
                        
                        logger.info(f"✅ Result submission registered manually for persistence: {message_id}")
                else:
                    logger.warning(f"Could not get valid webhook message for persistence registration")
                
            except Exception as persistence_error:
                logger.error(f"Could not register result submission for persistence: {persistence_error}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
            
            
            if hasattr(self, 'supersede_view') and self.supersede_view:
                await self._disable_superseded_view()
            
            logger.info(f"Result submitted by {submitting_team_name} for match {self.match_id}: {self.selected_winner} wins {self.selected_score}")
            
        except discord.NotFound as not_found_error:
            logger.error(f"Interaction not found in result submission: {not_found_error}")
            
        except Exception as e:
            logger.error(f"Error in result submission: {e}")
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error processing result submission!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Error processing result submission!", ephemeral=True)
            except discord.NotFound:
                logger.error("Could not send error message - interaction expired")
            except Exception as error_error:
                logger.error(f"Could not send error message: {error_error}")
    
    async def _disable_superseded_view(self):
        
        try:
            if not self.supersede_view:
                return
            
            
            for item in self.supersede_view.children:
                item.disabled = True
            
            
            embed = discord.Embed(
                title="🔄 Counter Result Submitted",
                description=f"**{self.supersede_view.responding_team}** has made a counter result submission. This submission is no longer active.",
                color=discord.Color.orange()
            )
            embed.add_field(name="🥇 Original Winner", value=self.supersede_view.result_data['winner'], inline=True)
            embed.add_field(name="📊 Original Score", value=self.supersede_view.result_data['score'], inline=True)
            embed.add_field(name="ℹ️ Status", value="Superseded by counter submission", inline=True)
            
            
            superseded_message = None
            
            
            if hasattr(self.supersede_view, 'message') and self.supersede_view.message:
                superseded_message = self.supersede_view.message
                logger.info("✅ Using direct message reference for superseded result view")
            
            
            elif (hasattr(self.supersede_view, 'message_id') and self.supersede_view.message_id and
                  hasattr(self.supersede_view, 'channel_id') and self.supersede_view.channel_id and
                  hasattr(self.supersede_view, 'guild_id') and self.supersede_view.guild_id):
                
                try:
                    guild = self.bot.get_guild(self.supersede_view.guild_id)
                    if guild:
                        channel = guild.get_channel(self.supersede_view.channel_id)
                        if channel:
                            superseded_message = await channel.fetch_message(self.supersede_view.message_id)
                            logger.info(f"✅ Retrieved superseded result message from stored IDs: {self.supersede_view.message_id}")
                except Exception as fetch_error:
                    logger.error(f"Could not fetch superseded result message from stored IDs: {fetch_error}")
            
            
            else:
                logger.warning("No message reference or stored IDs - trying database lookup for result submission")
                try:
                    
                    cursor = self.bot.db.conn.cursor()
                    cursor.execute('''
                        SELECT message_id, channel_id, guild_id 
                        FROM ui_messages 
                        WHERE message_type = 'result_submission' 
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
                                    
                                    
                                    if test_message.embeds and not any("Counter Result Submitted" in embed.title for embed in test_message.embeds):
                                        superseded_message = test_message
                                        logger.info(f"✅ Found superseded result message via database: {message_id}")
                                        break
                        except:
                            continue
                            
                except Exception as db_error:
                    logger.error(f"Database lookup for superseded result message failed: {db_error}")
            
            
            if superseded_message:
                await superseded_message.edit(embed=embed, view=self.supersede_view)
                
                
                self.bot.db.complete_ongoing_interaction(superseded_message.id)
                
                logger.info(f"✅ Successfully disabled superseded result submission view: {superseded_message.id}")
            else:
                logger.error(f"❌ Could not find superseded result message to disable for match {self.match_id}")
            
        except Exception as e:
            logger.error(f"Error disabling superseded result view: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
                
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
                
    async def _disable_submit_result_button_on_first_submission(self):
        
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
                        view.result_submission_button.label = "⏳ Result Submission Ongoing"
                        view.result_submission_button.style = discord.ButtonStyle.secondary
                        
                        
                        embed.color = discord.Color.orange()
                        
                        
                        for i, field in enumerate(embed.fields):
                            if "Status" in field.name:
                                embed.set_field_at(i, name=field.name, value="⏳ Result submission ongoing - awaiting team agreement", inline=field.inline)
                                break
                        
                        await message.edit(embed=embed, view=view)
                        logger.info(f"Submit Result button disabled after first submission for match {self.match_id}")
                        break
            
        except Exception as e:
            logger.error(f"Error disabling submit result button on first submission: {e}")
    
class ResultSubmissionView(discord.ui.View):
    
    
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any], result_data: Dict[str, Any],
                 submitting_team: str, responding_team: str, responding_team_role_id: int):
        super().__init__(timeout=None)  
        self.bot = bot
        self.match_id = match_id
        self.match_data = match_data
        self.result_data = result_data
        self.submitting_team = submitting_team
        self.responding_team = responding_team
        self.responding_team_role_id = responding_team_role_id
        
        
        self.message = None          
        self.message_id = None       
        self.channel_id = None       
        self.guild_id = None         
        
        
        timestamp = int(datetime.now().timestamp())
        self.confirm_button.custom_id = f"confirm_result_{match_id}_{timestamp}"
        self.dispute_button.custom_id = f"dispute_result_{match_id}_{timestamp}"
    
    async def _get_message_from_stored_ids(self) -> discord.Message:
        
        try:
            if not self.message_id or not self.channel_id or not self.guild_id:
                logger.error("No stored message/channel/guild IDs available for result submission")
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
                logger.debug(f"Successfully retrieved result submission message {self.message_id}")
                return message
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving result submission message from stored IDs: {e}")
            return None
    
    @discord.ui.button(label='✅ Confirm Result', style=discord.ButtonStyle.success, custom_id='confirm_result')
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        
        if not self._user_in_responding_team(interaction.user):
            await interaction.response.send_message("❌ Only the responding team can confirm this result!", ephemeral=True)
            return
        
        try:
            
            simplified_result = {
                'winner': self.result_data['winner'],
                'score': self.result_data['score'],
                'submitted_by_team': self.result_data['submitted_by_team'],
                'submitted_by_user': self.result_data['submitted_by_user'],
                'submitted_at': self.result_data['submitted_at']
            }
            
            self.bot.db.update_match_result(self.match_id, simplified_result)
            
            
            await self._update_submit_result_button_to_awaiting_orga()
            
            
            embed = discord.Embed(
                title="✅ Result Confirmed by Teams!",
                description=f"Both teams have agreed on the match result. Awaiting Event Orga final confirmation.",
                color=discord.Color.green()
            )
            embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            embed.add_field(name="🥇 Winner", value=f"**{self.result_data['winner']}**", inline=True)
            
            
            embed.add_field(name="📊 Final Score", value=f"**{self.result_data['score']}**", inline=True)
            embed.add_field(name="🗺️ Map", value=self.match_data.get('map_name', 'TBA'), inline=True)
            
            
            embed.add_field(name="📋 Result Details", value=f"Winner: {self.result_data['winner']}\nScore: {self.result_data['score']}", inline=False)
            
            
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            try:
                # Public Embed aktualisieren
                await self.bot.public_updater.update_public_embed_for_match(self.match_id, "result_update")
            except Exception as e:
                logger.error(f"Error updating public embed after result confirmation: {e}")
            
            
            await self._notify_event_orga_with_buttons(interaction.channel)
            
            
            try:
                from ui.streamer_management.streamer_match_manager import StreamerMatchManager
                streamer_manager = StreamerMatchManager(self.bot)
                await streamer_manager.update_all_match_posts_including_private(self.match_id)
                logger.info(f"✅ Streamer embeds updated after team result confirmation for match {self.match_id}")
            except Exception as streamer_error:
                logger.warning(f"Could not update streamer embeds after team confirmation: {streamer_error}")
            
        except Exception as e:
            logger.error(f"Error confirming result: {e}")
            await interaction.response.send_message("❌ Error confirming result!", ephemeral=True)
    
    async def _update_submit_result_button_to_awaiting_orga(self):
        
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
                        view.result_submission_button.label = "⏳ Awaiting Orga Confirmation"
                        view.result_submission_button.style = discord.ButtonStyle.secondary
                        
                        
                        embed.color = discord.Color.orange()
                        
                        
                        for i, field in enumerate(embed.fields):
                            if "Status" in field.name:
                                embed.set_field_at(i, name=field.name, value="⏳ Teams agreed - Awaiting Event Orga confirmation", inline=field.inline)
                                break
                        
                        await message.edit(embed=embed, view=view)
                        logger.info(f"Submit Result button updated to awaiting orga for match {self.match_id}")
                        break
            
        except Exception as e:
            logger.error(f"Error updating submit result button to awaiting orga: {e}")
    
    async def _notify_event_orga_with_buttons(self, channel):
        
        try:
            
            orga_role = channel.guild.get_role(self.bot.EVENT_ORGA_ROLE_ID)
            if not orga_role:
                return
            
            
            embed = discord.Embed(
                title="🚨 Result Awaiting Final Confirmation",
                description=f"Teams have agreed on the result. Please review and confirm:",
                color=discord.Color.gold()
            )
            embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            embed.add_field(name="🥇 Winner", value=f"**{self.result_data['winner']}**", inline=True)
            embed.add_field(name="📊 Score", value=f"**{self.result_data['score']}**", inline=True)
            embed.add_field(name="🆔 Match ID", value=str(self.match_id), inline=True)
            
            
            from ui.match_interactions.orga_result_confirmation import OrgaResultConfirmationView
            view = OrgaResultConfirmationView(self.bot, self.match_id, self.match_data, self.result_data)
            
            webhook_message = await channel.send(f"{orga_role.mention}", embed=embed, view=view)
            
            
            try:
                if webhook_message and hasattr(webhook_message, 'id') and hasattr(self.bot, 'lazy_persistence'):
                    message_id = webhook_message.id
                    channel_id = channel.id
                    guild_id = channel.guild.id
                    
                    
                    view.message_id = message_id
                    view.channel_id = channel_id
                    view.guild_id = guild_id
                    
                    persistence_data = {
                        'result_data': self.result_data,
                        'match_data': self.match_data,
                        'message_id': message_id,  
                        'channel_id': channel_id,  
                        'guild_id': guild_id       
                    }
                    
                    
                    
                    
                    await self.bot.lazy_persistence.register_view(webhook_message, 'orga_result_confirmation', self.match_id, persistence_data)
                    
                    
                    ui_data = {
                        'view_type': 'orga_result_confirmation',
                        'registered_at': datetime.now().isoformat(),
                        'data': persistence_data
                    }
                    
                    self.bot.db.register_ui_message(
                        message_id, channel_id, guild_id,
                        'orga_result_confirmation', ui_data, self.match_id
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
                        self.bot.db.save_button_states(message_id, buttons_data)
                        logger.info(f"✅ Orga result confirmation view registered for Fast Startup with {len(buttons_data)} buttons")
                    
                    
                    self.bot.add_view(view)
                    
                    logger.info(f"✅ Orga result confirmation registered with DUAL persistence: {message_id}")
                
            except Exception as persistence_error:
                logger.warning(f"Could not register orga result confirmation for persistence: {persistence_error}")
                
                self.bot.add_view(view)
            
        except Exception as e:
            logger.error(f"Error notifying Event Orga with buttons: {e}")
    
    @discord.ui.button(label='🔄 Dispute & Counter', style=discord.ButtonStyle.danger, custom_id='dispute_result')
    async def dispute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        
        if not self._user_in_responding_team(interaction.user):
            await interaction.response.send_message("❌ Only the responding team can dispute this result!", ephemeral=True)
            return
        
        
        complete_match_data = self._get_complete_match_data_for_counter()
        
        
        counter_view = SimpleResultView(self.bot, self.match_id, complete_match_data, interaction.user)
        
        
        counter_view.supersede_view = self
        
        counter_embed = discord.Embed(
            title="📊 Submit Counter Result",
            description="Please submit your version of the match result:",
            color=discord.Color.blue()
        )
        counter_embed.add_field(name="🏆 Match", value=f"{complete_match_data['team1_name']} vs {complete_match_data['team2_name']}", inline=False)
        counter_embed.add_field(name="🗺️ Map", value=complete_match_data.get('map_name', 'TBA'), inline=True)
        counter_embed.add_field(name="ℹ️ Instructions", value="1. Select the winning team\n2. Select the final score", inline=False)
        
        await interaction.response.send_message(embed=counter_embed, view=counter_view, ephemeral=True)
        
        logger.info(f"Counter result modal shown to {interaction.user} for match {self.match_id} with complete match data")
    
    def _get_complete_match_data_for_counter(self) -> Dict[str, Any]:
        
        try:
            
            match_details = self.bot.db.get_match_details(self.match_id)
            if not match_details:
                logger.warning(f"Could not get match details for counter - using existing data")
                return self.match_data
            
            
            complete_data = self.match_data.copy()
            
            
            if len(match_details) > 5:
                complete_data['map_name'] = match_details[5]  
            
            
            complete_data['match_date'] = match_details[3] if len(match_details) > 3 else complete_data.get('match_date', 'TBA')
            complete_data['match_time'] = match_details[4] if len(match_details) > 4 else complete_data.get('match_time', 'TBA')
            complete_data['team1_side'] = match_details[6] if len(match_details) > 6 else complete_data.get('team1_side', 'TBA')
            complete_data['team2_side'] = match_details[7] if len(match_details) > 7 else complete_data.get('team2_side', 'TBA')
            complete_data['week'] = match_details[13] if len(match_details) > 13 else complete_data.get('week', 1)
            complete_data['status'] = match_details[10] if len(match_details) > 10 else complete_data.get('status', 'pending')
            
            logger.info(f"✅ Complete match data for counter: Map={complete_data.get('map_name', 'MISSING')}")
            
            return complete_data
            
        except Exception as e:
            logger.error(f"Error getting complete match data for counter: {e}")
            return self.match_data
    
    async def _supersede_this_view_after_counter(self):
        
        try:
            
            for item in self.children:
                item.disabled = True
            
            
            embed = discord.Embed(
                title="🔄 Result Disputed",
                description=f"**{self.responding_team}** has disputed this result and submitted a counter. This submission is no longer active.",
                color=discord.Color.red()
            )
            embed.add_field(name="🥇 Original Winner", value=self.result_data['winner'], inline=True)
            embed.add_field(name="📊 Original Score", value=self.result_data['score'], inline=True)
            embed.add_field(name="ℹ️ Status", value="Superseded by counter submission", inline=True)
            
            
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
                            logger.info(f"✅ Retrieved superseded result message from stored IDs: {self.message_id}")
                except Exception as fetch_error:
                    logger.error(f"Could not fetch superseded result message from stored IDs: {fetch_error}")
            
            
            else:
                logger.warning("No message reference or stored IDs - trying database lookup for result submission")
                try:
                    
                    cursor = self.bot.db.conn.cursor()
                    cursor.execute('''
                        SELECT message_id, channel_id, guild_id 
                        FROM ui_messages 
                        WHERE message_type = 'result_submission' 
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
                                    
                                    
                                    if test_message.embeds and not any("Result Disputed" in embed.title for embed in test_message.embeds):
                                        superseded_message = test_message
                                        logger.info(f"✅ Found superseded result message via database: {message_id}")
                                        break
                        except:
                            continue
                            
                except Exception as db_error:
                    logger.error(f"Database lookup for superseded result message failed: {db_error}")
            
            
            if superseded_message:
                await superseded_message.edit(embed=embed, view=self)
                
                
                self.bot.db.complete_ongoing_interaction(superseded_message.id)
                
                logger.info(f"✅ Successfully disabled superseded result submission view: {superseded_message.id}")
            else:
                logger.error(f"❌ Could not find superseded result message to disable for match {self.match_id}")
                
        except Exception as e:
            logger.error(f"Error superseding result submission view: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
    
    def _user_in_responding_team(self, user: discord.Member) -> bool:
        
        user_role_ids = [role.id for role in user.roles]
        return self.responding_team_role_id in user_role_ids
    
    def restore_from_persistence_data(self, persistence_data: Dict[str, Any]):
        
        try:
            
            submission_data = persistence_data.get('data', {})
            self.message_id = submission_data.get('message_id')      
            self.channel_id = submission_data.get('channel_id')      
            self.guild_id = submission_data.get('guild_id')          
            
            
            if 'result_data' in submission_data:
                self.result_data = submission_data['result_data']
            
            if 'submitting_team' in submission_data:
                self.submitting_team = submission_data['submitting_team']
            
            if 'responding_team' in submission_data:
                self.responding_team = submission_data['responding_team']
            
            if 'responding_team_role_id' in submission_data:
                self.responding_team_role_id = submission_data['responding_team_role_id']
            
            logger.info(f"✅ Restored result submission view with message_id: {self.message_id}, submitting_team: {getattr(self, 'submitting_team', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"Error restoring result submission view from persistence: {e}")
    
    async def on_timeout(self):
        
        for item in self.children:
            item.disabled = True
        
        try:
            
            
            pass
        except:
            pass