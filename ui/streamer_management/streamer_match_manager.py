# ui/streamer_management/streamer_match_manager.py
"""
Enhanced Streamer Match Manager with Match Completion Support
"""

import discord
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class StreamerMatchManager:
    
    def __init__(self, bot):
        self.bot = bot
    
    def _get_streamer_display_name(self, streamer_id: int) -> str:
        """Get server nickname or fallback to global name/username"""
        # Versuche Member zu finden (hat Server-Nickname)
        for guild in self.bot.guilds:
            member = guild.get_member(streamer_id)
            if member:
                return member.nick or member.global_name or member.name
        
        # Fallback auf User
        user = self.bot.get_user(streamer_id)
        return user.global_name or user.name if user else f"User {streamer_id}"
    
    async def disable_streamer_buttons_for_completed_match(self, match_id: int):
        """
        Disable streamer buttons when match is submitted to orga for final confirmation
        Replace both register/unregister buttons with single disabled 'Match Completed' button
        """
        try:
            # Find streamer message
            streamer_message_id = self.bot.db.get_match_streamer_message_id(match_id)
            if not streamer_message_id:
                logger.info(f"No streamer message found for match {match_id}")
                return
            
            # Get streamer channel
            streamer_channel_id = self.bot.config['channels'].get('streamer_channel_id')
            if not streamer_channel_id:
                logger.warning("No streamer_channel_id configured in config.json")
                return
            
            streamer_channel = self.bot.get_channel(streamer_channel_id)
            if not streamer_channel:
                logger.warning(f"Streamer channel {streamer_channel_id} not found")
                return
            
            # Get the message
            try:
                message = await streamer_channel.fetch_message(streamer_message_id)
                
                if message.embeds:
                    embed = message.embeds[0]
                    
                    # Update embed title to show completion
                    if "✅" not in embed.title:
                        embed.title = f"✅ {embed.title.replace('📺', '').strip()}"
                    
                    # Change embed color to green
                    embed.color = discord.Color.green()
                    
                    # Update status field
                    for i, field in enumerate(embed.fields):
                        if "Streamer Status" in field.name or "📺" in field.name:
                            current_streamer_info = field.value
                            if "Streamer wanted" in current_streamer_info:
                                embed.set_field_at(i, name="📺 Streamer Status", 
                                                 value="✅ **Match completed** - Results submitted to Event Orga", inline=field.inline)
                            else:
                                # Keep existing streamer info but add completion status
                                embed.set_field_at(i, name="📺 Streamer Status", 
                                                 value=f"{current_streamer_info}\n\n✅ **Match completed** - Results submitted to Event Orga", inline=field.inline)
                            break
                    
                    # Create disabled view with single button
                    from ui.match_interactions.orga_result_confirmation import StreamerMatchViewDisabled
                    disabled_view = StreamerMatchViewDisabled()
                    
                    # Update the message
                    await message.edit(embed=embed, view=disabled_view)
                    
                    # Update button states in database for persistence
                    try:
                        buttons_data = []
                        for item in disabled_view.children:
                            if hasattr(item, 'custom_id') and item.custom_id:
                                buttons_data.append({
                                    'id': item.custom_id,
                                    'label': item.label,
                                    'disabled': item.disabled,
                                    'style': item.style.name,
                                    'data': {}
                                })
                        
                        if buttons_data:
                            self.bot.db.save_button_states(streamer_message_id, buttons_data)
                            logger.info(f"✅ Streamer buttons disabled and persisted for completed match {match_id}")
                    except Exception as persistence_error:
                        logger.error(f"Error updating button persistence: {persistence_error}")
                    
                    logger.info(f"✅ Streamer embed updated to show match completion for match {match_id}")
                    
            except discord.NotFound:
                logger.warning(f"Streamer message {streamer_message_id} not found for match {match_id}")
            except Exception as e:
                logger.error(f"Error updating streamer message: {e}")
                
        except Exception as e:
            logger.error(f"Error disabling streamer buttons for completed match: {e}")
    
    async def update_all_match_posts_including_private(self, match_id: int):
        
        try:
            
            await self._update_first_private_match_embed_with_buttons(match_id)
            
            
            await self._update_public_match_posts(match_id)
            
            
            await self._update_streamer_match_posts(match_id)
            
            logger.info(f"✅ ALL match posts updated with REAL team names for match {match_id} - FIRST private embed targeted")
            
        except Exception as e:
            logger.error(f"Error updating all match posts: {e}")
    
    async def _update_first_private_match_embed_with_buttons(self, match_id: int):
        
        try:
            
            match_details = self.bot.db.get_match_details(match_id)
            if not match_details or not match_details[8]:  
                return
            
            private_channel_id = match_details[8]
            channel = self.bot.get_channel(private_channel_id)
            if not channel:
                return
            
            
            real_team_names = self._get_real_team_names_from_match_details(match_details)
            
            
            server_data_json = self.bot.db.get_setting(f'match_{match_id}_server')
            
            
            target_message = None
            async for message in channel.history(limit=50, oldest_first=True):
                if (message.author == self.bot.user and 
                    message.embeds and 
                    message.components):  
                    
                    embed = message.embeds[0]
                    
                    
                    if (embed.footer and 
                        f"Match ID: {match_id}" in embed.footer.text):
                        
                        target_message = message
                        logger.info(f"🎯 Found FIRST private embed with buttons for match {match_id}: Message ID {message.id}")
                        break
            
            if not target_message:
                logger.warning(f"❌ No private embed with buttons found for match {match_id}")
                return
            
            
            current_streamers = self.bot.db.get_match_streamers_detailed(match_id)
            
            
            embed = target_message.embeds[0]
            
            
            await self._update_main_private_streamer_field(
                embed, current_streamers, match_id, real_team_names, server_data_json
            )
            
            
            await target_message.edit(embed=embed)
            logger.info(f"✅ FIRST private embed (with buttons) updated with REAL team names and SteamID64 for match {match_id}")
                        
        except Exception as e:
            logger.error(f"Error updating FIRST private match embed with buttons: {e}")
    
    async def _update_main_private_streamer_field(self, embed: discord.Embed, streamers: List[Dict], match_id: int, real_team_names: Dict[str, str], server_data_json: str = None):
        
        try:
            
            current_fields = [(field.name, field.value, field.inline) for field in embed.fields]
            
            
            embed.clear_fields()
            
            
            for name, value, inline in current_fields:
                
                if not ("Streamer" in name or "📺" in name or "Server" in name or "🖥️" in name):
                    embed.add_field(name=name, value=value, inline=inline)
            
            
            if server_data_json:
                try:
                    import json
                    server_data = json.loads(server_data_json)
                    if server_data.get('server_name'):
                        server_text = f"Server Name: `{server_data['server_name']}`\nPassword: `{server_data['server_password']}`\nProvided by: {server_data['offering_team']}"
                        
                        
                        rules_index = self._find_field_index(embed, ["Rules", "📖"])
                        if rules_index >= 0:
                            embed.insert_field_at(rules_index, name="🖥️ Server Details", value=server_text, inline=False)
                        else:
                            
                            status_index = self._find_field_index(embed, ["Status", "ℹ️"])
                            if status_index >= 0:
                                embed.insert_field_at(status_index, name="🖥️ Server Details", value=server_text, inline=False)
                            else:
                                embed.add_field(name="🖥️ Server Details", value=server_text, inline=False)
                except Exception as server_error:
                    logger.error(f"Error adding server field: {server_error}")
            
            
            if streamers and len(streamers) > 0:
                streamer_data = streamers[0]
                stream_url = streamer_data.get('stream_url', '')
                steam_id64 = streamer_data.get('steam_id64', '')
                
                
                username = self._get_streamer_display_name(streamer_data['streamer_id'])
                
                
                if streamer_data['team_side'] == 'team1':
                    team_name = real_team_names['team1_name']
                else:
                    team_name = real_team_names['team2_name']
                
                
                if stream_url:
                    streamer_text = f"{team_name}: [{username}]({stream_url})"
                else:
                    streamer_text = f"{team_name}: {username}"
                
                if steam_id64:  
                    streamer_text += f"\nSteamID64: `{steam_id64}`"
                
                
                rules_index = self._find_field_index(embed, ["Rules", "📖"])
                if rules_index >= 0:
                    embed.insert_field_at(rules_index, name="📺 Streamer", value=streamer_text, inline=False)
                else:
                    
                    status_index = self._find_field_index(embed, ["Status", "ℹ️"])
                    if status_index >= 0:
                        embed.insert_field_at(status_index, name="📺 Streamer", value=streamer_text, inline=False)
                    else:
                        embed.add_field(name="📺 Streamer", value=streamer_text, inline=False)
                
                logger.info(f"✅ Streamer field with REAL team name '{team_name}' and SteamID64 added to MAIN private embed for match {match_id}")
            
            else:
                logger.info(f"✅ No streamer registered - no streamer field added to MAIN private embed for match {match_id}")
        
        except Exception as e:
            logger.error(f"Error updating MAIN private streamer field: {e}")
    
    def _find_field_index(self, embed: discord.Embed, search_terms: List[str]) -> int:
        
        for i, field in enumerate(embed.fields):
            for term in search_terms:
                if term in field.name:
                    return i
        return -1
    
    async def _update_public_match_posts(self, match_id: int):
        """
        Update public match posts - FIXED für separate channels
        """
        try:
            # ENTFERNT: Die alte PUBLIC_CATEGORY_ID Logik
            # ERSETZT durch: Direkte Suche nach public match channel
            
            # Channel ID für dieses Match aus Datenbank holen
            stored_channel_id = self.bot.db.get_setting(f'public_match_{match_id}_channel_id')
            if not stored_channel_id:
                logger.info(f"No public match channel found for match {match_id}")
                return
            
            # Channel direkt finden
            public_channel = None
            for guild in self.bot.guilds:
                channel = guild.get_channel(int(stored_channel_id))
                if channel:
                    public_channel = channel
                    break
            
            if not public_channel:
                logger.warning(f"Public match channel {stored_channel_id} not found for match {match_id}")
                return
            
            # Public message ID holen
            public_message_id = self.bot.db.get_setting(f'public_match_{match_id}_message_id')
            if not public_message_id:
                # Fallback: Suche nach der Match Embed Message im Channel
                async for message in public_channel.history(limit=10):
                    if (message.author == self.bot.user and 
                        message.embeds and 
                        message.embeds[0].footer and
                        f"Match ID: {match_id}" in message.embeds[0].footer.text):
                        
                        public_message_id = message.id
                        # Für zukünftige Updates speichern
                        self.bot.db.set_setting(f'public_match_{match_id}_message_id', str(message.id))
                        break
            
            if not public_message_id:
                logger.warning(f"No public message found for match {match_id}")
                return
            
            # Message holen und aktualisieren
            try:
                message = await public_channel.fetch_message(int(public_message_id))
                
                # Real team names holen
                match_details = self.bot.db.get_match_details(match_id)
                if not match_details:
                    return
                
                real_team_names = self._get_real_team_names_from_match_details(match_details)
                
                # Embed aktualisieren
                if message.embeds:
                    embed = message.embeds[0]
                    
                    # Current streamers holen
                    current_streamers = self.bot.db.get_match_streamers_detailed(match_id)
                    
                    # Streamer field aktualisieren
                    await self._update_public_streamer_field_with_real_names(
                        embed, current_streamers, match_id, real_team_names
                    )
                    
                    await message.edit(embed=embed)
                    logger.info(f"✅ Public embed updated with REAL team names for match {match_id}")
                    
            except discord.NotFound:
                logger.warning(f"Public message {public_message_id} not found for match {match_id}")
            except Exception as e:
                logger.error(f"Error updating public message: {e}")
                    
        except Exception as e:
            logger.error(f"Error updating public match posts: {e}")
    
    async def _update_streamer_match_posts(self, match_id: int):
        
        try:
            
            streamer_message_id = self.bot.db.get_match_streamer_message_id(match_id)
            if not streamer_message_id:
                logger.info(f"No streamer message found for match {match_id}")
                return
            
            
            streamer_channel_id = self.bot.config['channels'].get('streamer_channel_id')
            if not streamer_channel_id:
                logger.warning("No streamer_channel_id configured in config.json")
                return
            
            streamer_channel = self.bot.get_channel(streamer_channel_id)
            if not streamer_channel:
                logger.warning(f"Streamer channel {streamer_channel_id} not found")
                return
            
            
            match_details = self.bot.db.get_match_details(match_id)
            if not match_details:
                return
            
            real_team_names = self._get_real_team_names_from_match_details(match_details)
            
            try:
                message = await streamer_channel.fetch_message(streamer_message_id)
                
                
                if message.embeds:
                    embed = message.embeds[0]
                    
                    
                    current_streamers = self.bot.db.get_match_streamers_detailed(match_id)
                    
                    
                    await self._update_public_streamer_field_with_real_names(
                        embed, current_streamers, match_id, real_team_names
                    )
                    
                    
                    view = await self._create_updated_streamer_view(match_id, current_streamers)
                    
                    await message.edit(embed=embed, view=view)
                    
                    
                    if hasattr(self.bot, 'lazy_persistence') and view:
                        await self.bot.lazy_persistence.update_streamer_button_states(streamer_message_id, view)
                    
                    logger.info(f"✅ Streamer embed updated with REAL team names for match {match_id}")
                    
            except discord.NotFound:
                logger.warning(f"Streamer message {streamer_message_id} not found for match {match_id}")
            except Exception as e:
                logger.error(f"Error updating streamer message: {e}")
                
        except Exception as e:
            logger.error(f"Error updating streamer match posts: {e}")
    
    def _get_real_team_names_from_match_details(self, match_details) -> Dict[str, str]:
        
        try:
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
            
            logger.info(f"🏆 REAL team names for match {match_details[0]}: {team1_name} vs {team2_name}")
            
            return {
                'team1_name': team1_name,
                'team2_name': team2_name
            }
            
        except Exception as e:
            logger.error(f"Error getting real team names: {e}")
            return {
                'team1_name': 'Team 1',
                'team2_name': 'Team 2'
            }
    
    async def _update_public_streamer_field_with_real_names(self, embed: discord.Embed, streamers: List[Dict], match_id: int, real_team_names: Dict[str, str]):
        
        try:
            
            fields_to_keep = []
            for field in embed.fields:
                if not ("Streamer" in field.name or "📺" in field.name):
                    fields_to_keep.append((field.name, field.value, field.inline))
            
            
            embed.clear_fields()
            for name, value, inline in fields_to_keep:
                embed.add_field(name=name, value=value, inline=inline)
            
            if streamers and len(streamers) > 0:
                streamer_data = streamers[0]
                stream_url = streamer_data.get('stream_url', '')
                
                
                username = self._get_streamer_display_name(streamer_data['streamer_id'])
                
                
                if streamer_data['team_side'] == 'team1':
                    team_name = real_team_names['team1_name']
                else:
                    team_name = real_team_names['team2_name']
                
                
                if stream_url:
                    streamer_text = f"{team_name}: [{username}]({stream_url})"
                else:
                    streamer_text = f"{team_name}: {username}"
                
                
                rules_index = self._find_field_index(embed, ["Rules", "📖"])
                if rules_index >= 0:
                    embed.insert_field_at(rules_index, name="📺 Streamer", value=streamer_text, inline=False)
                else:
                    embed.add_field(name="📺 Streamer", value=streamer_text, inline=False)
                
                logger.info(f"✅ Streamer field with REAL team name '{team_name}' added to public/streamer embed for match {match_id}")
        
        except Exception as e:
            logger.error(f"Error updating public/streamer streamer field with real names: {e}")
    
    async def _create_updated_streamer_view(self, match_id: int, streamers: List[Dict]):
        
        try:
            match_details = self.bot.db.get_match_details(match_id)
            if not match_details:
                return None
            
            # Check if match is completed/confirmed
            match_status = match_details[10] if len(match_details) > 10 else 'pending'
            if match_status in ['completed', 'confirmed']:
                # Return disabled view for completed matches
                from ui.match_interactions.orga_result_confirmation import StreamerMatchViewDisabled
                return StreamerMatchViewDisabled()
            
            
            real_team_names = self._get_real_team_names_from_match_details(match_details)
            
            match_data = {
                'match_id': match_details[0],
                'team1_name': real_team_names['team1_name'],
                'team2_name': real_team_names['team2_name'],
                'team1_side': match_details[6],
                'team2_side': match_details[7],
                'match_date': match_details[3],
                'match_time': match_details[4],
                'map_name': match_details[5],
                'status': match_details[10]
            }
            
            from ui.streamer_management import StreamerMatchView
            view = StreamerMatchView(match_id, self.bot, match_data)
            
            
            has_streamers = len(streamers) > 0
            
            if has_streamers:
                
                view.register_button.disabled = True
                view.register_button.label = 'Streamer Registered'
                view.register_button.style = discord.ButtonStyle.secondary
                
                view.unregister_button.disabled = False
                view.unregister_button.label = 'Unregister as Streamer'
                view.unregister_button.style = discord.ButtonStyle.danger
            else:
                
                view.register_button.disabled = False
                view.register_button.label = '📺 Register as Streamer'
                view.register_button.style = discord.ButtonStyle.primary
                
                view.unregister_button.disabled = True
                view.unregister_button.label = 'Not Registered'
                view.unregister_button.style = discord.ButtonStyle.danger
            
            return view
            
        except Exception as e:
            logger.error(f"Error creating updated streamer view: {e}")
            return None