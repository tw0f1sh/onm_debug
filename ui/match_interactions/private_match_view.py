"""
Enhanced Private Match View - WITH LAZY PERSISTENCE
"""

import discord
import logging
import json
from typing import Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PrivateMatchView(discord.ui.View):
    
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any]):
        super().__init__(timeout=None)
        self.bot = bot
        self.match_id = match_id
        self.match_data = match_data
        
        self.time_offer_button.custom_id = f"time_offer_{match_id}"
        self.server_offer_button.custom_id = f"server_offer_{match_id}"
        self.result_submission_button.custom_id = f"result_submit_{match_id}"
        self.orga_edit_button.custom_id = f"orga_edit_{match_id}"
        
        if match_data.get('match_time'):
            self.time_offer_button.disabled = True
            self.time_offer_button.label = f"✅ Time Set: {match_data['match_time']}"
            self.time_offer_button.style = discord.ButtonStyle.success
        else:
            self._check_for_ongoing_time_offer()
        
        server_data_json = self.bot.db.get_setting(f'match_{match_id}_server')
        if server_data_json:
            try:
                server_data = json.loads(server_data_json)
                if server_data.get('server_name'):
                    self.server_offer_button.disabled = True
                    self.server_offer_button.label = "✅ Server Set"
                    self.server_offer_button.style = discord.ButtonStyle.success
            except:
                pass
        
        if match_data.get('status') == 'confirmed':
            self.result_submission_button.disabled = True
            self.result_submission_button.label = "✅ Results Confirmed"
            self.result_submission_button.style = discord.ButtonStyle.success
        elif match_data.get('status') == 'completed':
            self.result_submission_button.disabled = True
            self.result_submission_button.label = "⏳ Awaiting Orga Confirmation"
            self.result_submission_button.style = discord.ButtonStyle.secondary
    
    def _check_for_ongoing_time_offer(self):
        try:
            ongoing_offers = self.bot.db.get_ongoing_interactions(
                match_id=self.match_id, 
                interaction_type='time_offer'
            )
            
            if ongoing_offers:
                self.time_offer_button.disabled = True
                self.time_offer_button.label = "⏳ Time Offer Ongoing"
                self.time_offer_button.style = discord.ButtonStyle.secondary
                
        except Exception as e:
            logger.error(f"Error checking ongoing time offer: {e}")
    
    @discord.ui.button(label='🕒 Offer Match Time', style=discord.ButtonStyle.primary, row=0, custom_id='time_offer_btn')
    async def time_offer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._user_in_match_teams(interaction.user):
            await interaction.response.send_message("❌ Only team members can offer match times!", ephemeral=True)
            return
            
        current_match_data = self.bot.db.get_match_details(self.match_id)
        if current_match_data and current_match_data[4]:
            await interaction.response.send_message("❌ Match time is already set!", ephemeral=True)
            return
        
        ongoing_offers = self.bot.db.get_ongoing_interactions(
            match_id=self.match_id, 
            interaction_type='time_offer'
        )
        
        if ongoing_offers:
            await interaction.response.send_message("❌ There's already an ongoing time offer! Please wait for it to be resolved.", ephemeral=True)
            return
        
        from ui.match_interactions.time_offer_system import TimeOfferModal
        modal = TimeOfferModal(self.bot, self.match_id, self.match_data)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='🖥️ Offer Server', style=discord.ButtonStyle.secondary, row=0, custom_id='server_offer_btn')
    async def server_offer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._user_in_match_teams(interaction.user):
            await interaction.response.send_message("❌ Only team members can offer servers!", ephemeral=True)
            return
        
        server_data_json = self.bot.db.get_setting(f'match_{self.match_id}_server')
        if server_data_json:
            try:
                server_data = json.loads(server_data_json)
                if server_data.get('server_name'):
                    await interaction.response.send_message("❌ Server is already set!", ephemeral=True)
                    return
            except:
                pass
        
        ongoing_offers = self.bot.db.get_ongoing_interactions(
            match_id=self.match_id, 
            interaction_type='server_offer'
        )
        
        if ongoing_offers:
            await interaction.response.send_message("❌ There's already an ongoing server offer! Please wait for it to be resolved.", ephemeral=True)
            return
        
        from ui.match_interactions.server_offer_system import ServerOfferModal
        modal = ServerOfferModal(self.bot, self.match_id, self.match_data)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='📊 Submit Result', style=discord.ButtonStyle.secondary, row=0, custom_id='result_submit_btn')
    async def result_submission_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._user_in_match_teams(interaction.user):
            await interaction.response.send_message("❌ Only team members can submit results!", ephemeral=True)
            return
        
        current_match_data = self.bot.db.get_match_details(self.match_id)
        if not current_match_data or not current_match_data[4]:
            await interaction.response.send_message("❌ Please set a match time first before submitting results!", ephemeral=True)
            return
        
        if current_match_data[10] == 'confirmed':
            await interaction.response.send_message("❌ Match result is already confirmed!", ephemeral=True)
            return
        
        ongoing_submissions = self.bot.db.get_ongoing_interactions(
            match_id=self.match_id, 
            interaction_type='result_submission'
        )
        
        if ongoing_submissions:
            await interaction.response.send_message("❌ There's already an ongoing result submission! Please wait for it to be resolved.", ephemeral=True)
            return
        
        from ui.match_interactions.result_submission_system import SimpleResultView
        
        view = SimpleResultView(self.bot, self.match_id, self.match_data, interaction.user)
        
        embed = discord.Embed(
            title="📊 Submit Match Result",
            description="Please submit the match result:",
            color=discord.Color.blue()
        )
        embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
        embed.add_field(name="ℹ️ Instructions", value="1. Select the winning team\n2. Select the final score (2-0 or 2-1)", inline=False)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label='⚙️ Orga Edit', style=discord.ButtonStyle.danger, row=1, custom_id='orga_edit_btn')
    async def orga_edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == self.bot.EVENT_ORGA_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("❌ Only Event Orga can edit match details!", ephemeral=True)
            return
        
        from ui.match_interactions.orga_edit_system import OrgaEditView
        
        view = OrgaEditView(self.bot, self.match_id, self.match_data)
        
        embed = discord.Embed(
            title="⚙️ Event Orga - Match Editor",
            description="Edit match details and settings:",
            color=discord.Color.red()
        )
        embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
        embed.add_field(name="ℹ️ Available Actions", value="• **Edit Match Details** - Date, time, map\n• **Reset Server** - Clear server details", inline=False)
        embed.add_field(name="⚠️ Warning", value="Changes will update all embeds (private, public, streamer)", inline=False)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    def _user_in_match_teams(self, user: discord.Member) -> bool:
        try:
            match_details = self.bot.db.get_match_details(self.match_id)
            if not match_details:
                return False
            
            team1_id = match_details[1]
            team2_id = match_details[2] 
            
            teams = self.bot.get_all_teams()
            team1_role_id = None
            team2_role_id = None
            
            for team in teams:
                if team[0] == team1_id:
                    team1_role_id = team[2]
                elif team[0] == team2_id:
                    team2_role_id = team[2]
            
            user_role_ids = [role.id for role in user.roles]
            return team1_role_id in user_role_ids or team2_role_id in user_role_ids
            
        except Exception as e:
            logger.error(f"Error checking user team membership: {e}")
            return False
    
    @classmethod
    def restore_from_persistence_data(cls, bot, persistence_data: Dict[str, Any]):
        try:
            match_id = persistence_data.get('match_id')
            match_data = persistence_data.get('match_data', {})
            
            view = cls(bot, match_id, match_data)
            
            button_states = persistence_data.get('button_states', {})
            
            if 'time_offer' in button_states:
                state = button_states['time_offer']
                view.time_offer_button.disabled = state.get('disabled', False)
                view.time_offer_button.label = state.get('label', '🕒 Offer Match Time')
                style_map = {
                    'primary': discord.ButtonStyle.primary,
                    'secondary': discord.ButtonStyle.secondary,
                    'success': discord.ButtonStyle.success,
                    'danger': discord.ButtonStyle.danger
                }
                view.time_offer_button.style = style_map.get(state.get('style', 'primary'), discord.ButtonStyle.primary)
            
            if 'server_offer' in button_states:
                state = button_states['server_offer']
                view.server_offer_button.disabled = state.get('disabled', False)
                view.server_offer_button.label = state.get('label', '🖥️ Offer Server')
                style_map = {
                    'primary': discord.ButtonStyle.primary,
                    'secondary': discord.ButtonStyle.secondary,
                    'success': discord.ButtonStyle.success,
                    'danger': discord.ButtonStyle.danger
                }
                view.server_offer_button.style = style_map.get(state.get('style', 'secondary'), discord.ButtonStyle.secondary)
            
            if 'result_submission' in button_states:
                state = button_states['result_submission']
                view.result_submission_button.disabled = state.get('disabled', False)
                view.result_submission_button.label = state.get('label', '📊 Submit Result')
                style_map = {
                    'primary': discord.ButtonStyle.primary,
                    'secondary': discord.ButtonStyle.secondary,
                    'success': discord.ButtonStyle.success,
                    'danger': discord.ButtonStyle.danger
                }
                view.result_submission_button.style = style_map.get(state.get('style', 'secondary'), discord.ButtonStyle.secondary)
            
            if 'orga_edit' in button_states:
                state = button_states['orga_edit']
                view.orga_edit_button.disabled = state.get('disabled', False)
                view.orga_edit_button.label = state.get('label', '⚙️ Orga Edit')
                style_map = {
                    'primary': discord.ButtonStyle.primary,
                    'secondary': discord.ButtonStyle.secondary,
                    'success': discord.ButtonStyle.success,
                    'danger': discord.ButtonStyle.danger
                }
                view.orga_edit_button.style = style_map.get(state.get('style', 'danger'), discord.ButtonStyle.danger)
            
            logger.info(f"✅ PrivateMatchView restored from persistence for match {match_id}")
            return view
            
        except Exception as e:
            logger.error(f"Error restoring PrivateMatchView from persistence: {e}")
            return cls(bot, persistence_data.get('match_id', 0), persistence_data.get('match_data', {}))
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        logger.error(f"Error in PrivateMatchView for match {self.match_id}: {error}")
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing your request. Please try again or contact an admin.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ An error occurred while processing your request. Please try again or contact an admin.",
                    ephemeral=True
                )
        except:
            pass