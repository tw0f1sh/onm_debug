# ui/streamer_management/streamer_match_view.py
"""
Streamer Match View
"""

import discord
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class StreamerMatchView(discord.ui.View):
    
    def __init__(self, match_id: int, bot, match_data: Dict):
        super().__init__(timeout=None)  
        self.match_id = match_id
        self.bot = bot
        self.match_data = match_data
        self._message_id = None
        
        # Only set custom_id if not restored from persistence
        if not hasattr(self, '_restored_from_persistence'):
            timestamp = int(datetime.now().timestamp())
            self.register_button.custom_id = f"register_streamer_{match_id}_{timestamp}"
            self.unregister_button.custom_id = f"unregister_streamer_{match_id}_{timestamp}"
        
        self._initialize_button_states()
        
    def _initialize_button_states(self):
        """
        Initialize button states based on match status and existing streamers
        """
        try:
            # Check if match is completed or confirmed
            match_status = self.match_data.get('status', 'pending')
            if match_status in ['completed', 'confirmed']:
                # Match is done - replace both buttons with single disabled success button
                self.clear_items()
                
                completed_button = discord.ui.Button(
                    label='✅ Match Completed', 
                    style=discord.ButtonStyle.success,
                    disabled=True,
                    emoji='🏆',
                    custom_id=f"match_completed_{self.match_id}_{int(datetime.now().timestamp())}"
                )
                self.add_item(completed_button)
                
                logger.info(f"Match {self.match_id} is {match_status} - showing completed button")
                return
            
            # Normal flow for active matches
            existing_streamers = self.bot.db.get_match_streamers_detailed(self.match_id)
            
            if existing_streamers:
                # Streamer is registered
                self.register_button.disabled = True
                self.register_button.label = 'Streamer Registered'
                self.register_button.style = discord.ButtonStyle.secondary
                
                self.unregister_button.disabled = False
                self.unregister_button.label = 'Unregister as Streamer'
                self.unregister_button.style = discord.ButtonStyle.danger
            else:
                # No streamer registered
                self.register_button.disabled = False
                self.register_button.label = '📺 Register as Streamer'
                self.register_button.style = discord.ButtonStyle.primary
                
                self.unregister_button.disabled = True
                self.unregister_button.label = 'Not Registered'
                self.unregister_button.style = discord.ButtonStyle.danger
                
        except Exception as e:
            logger.error(f"Error initializing streamer button states: {e}")
            # Fallback to safe state
            self.register_button.disabled = True
            self.register_button.label = 'Error'
            self.register_button.style = discord.ButtonStyle.secondary
            
            self.unregister_button.disabled = True
            self.unregister_button.label = 'Error'
            self.unregister_button.style = discord.ButtonStyle.secondary
    
    @discord.ui.button(label='📺 Register as Streamer', style=discord.ButtonStyle.primary, 
                      custom_id='register_streamer')
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        try:
            
            if not any(role.id == self.bot.STREAMER_ROLE_ID for role in interaction.user.roles):
                await self._safe_response(interaction, "❌ You need the Streamer role!", ephemeral=True)
                return
            
            
            existing_streamers = self.bot.db.get_match_streamers_detailed(self.match_id)
            
            
            for streamer_data in existing_streamers:
                if streamer_data['streamer_id'] == interaction.user.id:
                    await self._safe_response(interaction, "❌ You are already registered for this match! Please use 'Unregister as Streamer' first if you want to change your selection.", ephemeral=True)
                    return
            
            
            if existing_streamers:
                await self._safe_response(interaction, "❌ A streamer is already registered for this match!", ephemeral=True)
                return
            
            
            from .team_side_selection_view import TeamSideSelectionView
            view = TeamSideSelectionView(self.match_id, self.bot, self.match_data, existing_streamers)
            embed = discord.Embed(
                title="📺 Choose Streaming Side",
                description=f"**{self.match_data['team1_name']} vs {self.match_data['team2_name']}**\n\nChoose which team side you want to stream:",
                color=discord.Color.purple()
            )
            
            await self._safe_response(interaction, embed=embed, view=view, ephemeral=True)
            
            
            await self._save_button_state_change(interaction, button, {'action': 'registration_started'})
            
        except Exception as e:
            logger.error(f"Error in streamer registration: {e}")
            await self._safe_response(interaction, "❌ Error during registration!", ephemeral=True)
    
    @discord.ui.button(label='Unregister as Streamer', style=discord.ButtonStyle.danger, 
                      emoji='🚫', custom_id='unregister_streamer')
    async def unregister_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        try:
            
            existing_streamers = self.bot.db.get_match_streamers_detailed(self.match_id)
            user_registration = None
            
            for streamer_data in existing_streamers:
                if streamer_data['streamer_id'] == interaction.user.id:
                    user_registration = streamer_data
                    break
            
            if not user_registration:
                await interaction.response.send_message("❌ You are not registered as a streamer for this match!", ephemeral=True)
                return
            
            
            self.bot.db.remove_match_streamer(self.match_id, interaction.user.id)
            
            try:
                # Public Embed aktualisieren
                await self.bot.public_updater.update_public_embed_for_match(self.match_id, "streamer_update")
            except Exception as e:
                logger.error(f"Error updating public embed after streamer unregistration: {e}")
            
            
            await interaction.response.send_message("✅ Successfully unregistered as streamer!", ephemeral=True)
            
            
            from .streamer_match_manager import StreamerMatchManager
            streamer_manager = StreamerMatchManager(self.bot)
            await streamer_manager.update_all_match_posts_including_private(self.match_id)
            
            logger.info(f"Streamer {interaction.user} unregistered from Match {self.match_id} WITH persistence sync")
            
        except Exception as e:
            logger.error(f"Error in streamer unregistration: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error during unregistration!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Error during unregistration!", ephemeral=True)
            except:
                pass
    
    async def _safe_response(self, interaction: discord.Interaction, *args, **kwargs):
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(*args, **kwargs)
            else:
                await interaction.response.send_message(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in safe response: {e}")
    
    async def _save_button_state_change(self, interaction: discord.Interaction, button: discord.ui.Button, data: Dict):
        
        try:
            if hasattr(self.bot, 'lazy_persistence') and interaction.message:
                
                await self.bot.lazy_persistence.update_streamer_button_states(interaction.message.id, self)
                
        except Exception as e:
            logger.error(f"Error saving button state change: {e}")
    
    @classmethod
    def restore_from_persistence_data(cls, bot, persistence_data: Dict[str, Any]):
        
        try:
            match_id = persistence_data.get('match_id')
            match_data = persistence_data.get('match_data', {})
            
            
            view = cls(match_id, bot, match_data)
            
            
            view._restored_from_persistence = True
            
            
            button_states = persistence_data.get('button_states', {})
            
            if 'register_button' in button_states:
                state = button_states['register_button']
                view.register_button.disabled = state.get('disabled', False)
                view.register_button.label = state.get('label', '📺 Register as Streamer')
                style_map = {
                    'primary': discord.ButtonStyle.primary,
                    'secondary': discord.ButtonStyle.secondary,
                    'success': discord.ButtonStyle.success,
                    'danger': discord.ButtonStyle.danger
                }
                view.register_button.style = style_map.get(state.get('style', 'primary'), discord.ButtonStyle.primary)
            
            if 'unregister_button' in button_states:
                state = button_states['unregister_button']
                view.unregister_button.disabled = state.get('disabled', True)
                view.unregister_button.label = state.get('label', 'Not Registered')
                style_map = {
                    'primary': discord.ButtonStyle.primary,
                    'secondary': discord.ButtonStyle.secondary,
                    'success': discord.ButtonStyle.success,
                    'danger': discord.ButtonStyle.danger
                }
                view.unregister_button.style = style_map.get(state.get('style', 'danger'), discord.ButtonStyle.danger)
            
            
            try:
                existing_streamers = bot.db.get_match_streamers_detailed(match_id)
                has_streamers = len(existing_streamers) > 0
                
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
            except Exception as e:
                logger.error(f"Error checking database state during restoration: {e}")
            
            return view
            
        except Exception as e:
            logger.error(f"Error restoring StreamerMatchView from persistence: {e}")
            return None