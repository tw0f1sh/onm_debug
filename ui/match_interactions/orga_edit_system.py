# ui/match_interactions/orga_edit_system.py
"""
Enhanced Orga Edit System - ERWEITERT mit Result Edit und vollständigen Embed Updates
WITH TIMEZONE SUPPORT
"""

import discord
import logging
import json
import random
import asyncio
from datetime import datetime
from typing import Dict, Any
from utils.timezone_helper import TimezoneHelper

logger = logging.getLogger(__name__)

class OrgaEditModal(discord.ui.Modal):
    
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any], current_details: Dict[str, Any]):
        # TIMEZONE SUPPORT: Dynamischer Titel mit Timezone
        timezone_display = TimezoneHelper.get_timezone_display(bot)
        super().__init__(title=f"⚙️ Orga Edit Match ({timezone_display})", timeout=300)
        
        self.bot = bot
        self.match_id = match_id
        self.match_data = match_data
        
        current_date = current_details.get('match_date', '')
        current_time = current_details.get('match_time', '')
        current_map = current_details.get('map_name', '')
        
        display_date = current_date
        if current_date and current_date != 'TBA':
            try:
                date_obj = datetime.strptime(current_date, '%Y-%m-%d')
                display_date = date_obj.strftime('%d.%m.%Y')
            except:
                display_date = current_date
        
        self.match_date = discord.ui.TextInput(
            label="Match Date (DD.MM.YYYY)",
            placeholder="15.03.2024",
            default=display_date,
            max_length=10,
            required=True
        )
        
        # TIMEZONE SUPPORT: Zeit-Label mit Timezone
        time_label = TimezoneHelper.get_time_input_label(bot)
        time_placeholder = TimezoneHelper.get_time_input_placeholder(bot)
        
        self.match_time = discord.ui.TextInput(
            label=time_label,
            placeholder=time_placeholder,
            default=current_time or '',
            max_length=5,
            required=False
        )
        
        self.map_name = discord.ui.TextInput(
            label="Map Name",
            placeholder="de_dust2",
            default=current_map,
            max_length=50,
            required=True
        )
        
        self.add_item(self.match_date)
        self.add_item(self.match_time)
        self.add_item(self.map_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            date_input = self.match_date.value.strip()
            try:
                date_obj = datetime.strptime(date_input, '%d.%m.%Y')
                date_str = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                await interaction.response.send_message("❌ Invalid date format! Use DD.MM.YYYY (e.g. 15.03.2024)", ephemeral=True)
                return
            
            time_str = self.match_time.value.strip() if self.match_time.value else None
            map_name = self.map_name.value.strip()
            
            # TIMEZONE SUPPORT: Zeit-Validierung mit Timezone-Info
            if time_str:
                if not TimezoneHelper.validate_time_format(time_str):
                    timezone_info = TimezoneHelper.get_timezone_info(self.bot)
                    await interaction.response.send_message(
                        f"❌ Invalid time format! Please use HH:MM format.\n"
                        f"⏰ {timezone_info}", 
                        ephemeral=True
                    )
                    return
            
            cursor = self.bot.db.conn.cursor()
            
            cursor.execute('''
                UPDATE matches 
                SET match_date = ?, match_time = ?, map_name = ?
                WHERE id = ?
            ''', (date_str, time_str, map_name, self.match_id))
            
            self.bot.db.conn.commit()
            
            # TIMEZONE SUPPORT: Zeit mit Timezone formatieren für Bestätigung
            formatted_time = TimezoneHelper.format_time_with_timezone(time_str, self.bot) if time_str else "TBA"
            
            embed = discord.Embed(
                title="✅ Match Updated by Event Orga!",
                description=f"Match details have been updated:",
                color=discord.Color.green()
            )
            embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            embed.add_field(name="📅 Date", value=date_input, inline=True)
            embed.add_field(name="🕒 Time", value=formatted_time, inline=True)
            embed.add_field(name="🗺️ Map", value=map_name, inline=True)
            embed.add_field(name="👤 Updated by", value=interaction.user.mention, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # FIXED: Vollständige Embed-Updates für alle Kanäle
            await self._update_all_match_embeds_complete()
            
            logger.info(f"Match {self.match_id} updated by Orga {interaction.user}: Date={date_str}, Time={time_str}, Map={map_name}")
            
        except Exception as e:
            logger.error(f"Error in orga edit submission: {e}")
            await interaction.response.send_message("❌ Error updating match details!", ephemeral=True)
    
    async def _update_all_match_embeds_complete(self):
        """
        FIXED: Komplette Embed-Updates für alle Kanäle nach Orga-Änderungen
        """
        try:
            match_details = self.bot.db.get_match_details(self.match_id)
            if not match_details:
                logger.error(f"No match details found for match {self.match_id}")
                return
            
            logger.info(f"🔄 Starting complete embed updates for match {self.match_id}")
            
            # 1. Private Channel Embed aktualisieren
            await self._update_private_embed_complete(match_details)
            
            # 2. Public Channel Embed aktualisieren
            await self._update_public_embed_complete(match_details)
            
            # 3. Streamer Channel Embed aktualisieren
            await self._update_streamer_embed_complete(match_details)
            
            # 4. FIXED: Status-Icon nur aktualisieren wenn Match NICHT abgeschlossen ist
            match_status = match_details[10] if len(match_details) > 10 else 'pending'
            if match_status not in ['completed', 'confirmed']:
                # Nur bei aktiven Matches Status aktualisieren
                if match_details[4]:  # match_time
                    try:
                        await self.bot.status_manager.update_channel_status(self.match_id, 'scheduled')
                        logger.info(f"✅ Channel status updated to 'scheduled' for match {self.match_id}")
                    except Exception as status_error:
                        logger.error(f"Error updating channel status: {status_error}")
            else:
                logger.info(f"ℹ️ Match {self.match_id} is {match_status} - keeping completed status icon")
            
            logger.info(f"✅ Complete embed updates finished for match {self.match_id}")
            
        except Exception as e:
            logger.error(f"Error in complete embed updates: {e}")
    
    async def _update_private_embed_complete(self, match_details):
        """Aktualisiert das Private Match Embed vollständig"""
        try:
            private_channel_id = match_details[8]
            if not private_channel_id:
                return
            
            private_channel = self.bot.get_channel(private_channel_id)
            if not private_channel:
                return
            
            # Erste Message mit Buttons finden
            async for message in private_channel.history(limit=50, oldest_first=True):
                if (message.author == self.bot.user and 
                    message.embeds and 
                    message.components):
                    
                    embed = message.embeds[0]
                    if (embed.footer and 
                        f"Match ID: {self.match_id}" in embed.footer.text):
                        
                        # Embed-Felder aktualisieren mit Timezone-Support
                        formatted_date = self._format_date_display(match_details[3])
                        
                        # TIMEZONE SUPPORT: Zeit mit Timezone formatieren
                        formatted_time = TimezoneHelper.format_time_with_timezone(
                            match_details[4], self.bot
                        ) if match_details[4] else '*TBA*'
                        
                        for i, field in enumerate(embed.fields):
                            if "Match Date" in field.name or "📅" in field.name:
                                embed.set_field_at(i, name=field.name, value=formatted_date, inline=field.inline)
                            elif "Match Time" in field.name or "🕒" in field.name:
                                embed.set_field_at(i, name=field.name, value=formatted_time, inline=field.inline)
                            elif "Map" in field.name or "🗺️" in field.name:
                                embed.set_field_at(i, name=field.name, value=match_details[5], inline=field.inline)
                        
                        await message.edit(embed=embed)
                        logger.info(f"✅ Private embed updated for match {self.match_id}")
                        break
            
        except Exception as e:
            logger.error(f"Error updating private embed: {e}")
    
    async def _update_public_embed_complete(self, match_details):
        """Aktualisiert das Public Match Embed vollständig"""
        try:
            # Public Channel und Message finden
            stored_channel_id = self.bot.db.get_setting(f'public_match_{self.match_id}_channel_id')
            if not stored_channel_id:
                logger.warning(f"No public match channel found for match {self.match_id}")
                return
            
            channel = None
            for guild in self.bot.guilds:
                channel = guild.get_channel(int(stored_channel_id))
                if channel:
                    break
            
            if not channel:
                logger.warning(f"Public match channel {stored_channel_id} not found")
                return
            
            # Public Message ID holen
            public_message_id = self.bot.db.get_setting(f'public_match_{self.match_id}_message_id')
            if not public_message_id:
                # Fallback: Suche nach der Match Embed Message
                async for message in channel.history(limit=10):
                    if (message.author == self.bot.user and 
                        message.embeds and 
                        message.embeds[0].footer and
                        f"Match ID: {self.match_id}" in message.embeds[0].footer.text):
                        
                        public_message_id = message.id
                        self.bot.db.set_setting(f'public_match_{self.match_id}_message_id', str(message.id))
                        break
            
            if not public_message_id:
                return
            
            # Message aktualisieren
            try:
                message = await channel.fetch_message(int(public_message_id))
                
                if message.embeds:
                    embed = message.embeds[0]
                    formatted_date = self._format_date_display(match_details[3])
                    
                    # TIMEZONE SUPPORT: Zeit mit Timezone formatieren
                    formatted_time = TimezoneHelper.format_time_with_timezone(
                        match_details[4], self.bot
                    ) if match_details[4] else "*TBA*"
                    
                    for i, field in enumerate(embed.fields):
                        if "Match Date" in field.name or "📅" in field.name:
                            embed.set_field_at(i, name=field.name, value=formatted_date, inline=field.inline)
                        elif "Match Time" in field.name or "🕒" in field.name:
                            embed.set_field_at(i, name=field.name, value=formatted_time, inline=field.inline)
                        elif "Map" in field.name or "🗺️" in field.name:
                            embed.set_field_at(i, name=field.name, value=match_details[5], inline=field.inline)
                    
                    await message.edit(embed=embed)
                    logger.info(f"✅ Public embed updated for match {self.match_id}")
                    
            except discord.NotFound:
                logger.warning(f"Public message {public_message_id} not found")
                
        except Exception as e:
            logger.error(f"Error updating public embed: {e}")
    
    async def _update_streamer_embed_complete(self, match_details):
        """Aktualisiert das Streamer Match Embed vollständig"""
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
                            formatted_date = self._format_date_display(match_details[3])
                            
                            # TIMEZONE SUPPORT: Zeit mit Timezone formatieren
                            formatted_time = TimezoneHelper.format_time_with_timezone(
                                match_details[4], self.bot
                            ) if match_details[4] else "TBA"
                            
                            for i, field in enumerate(embed.fields):
                                if "Match Date" in field.name or "📅" in field.name:
                                    embed.set_field_at(i, name=field.name, value=formatted_date, inline=field.inline)
                                elif "Match Time" in field.name or "🕒" in field.name:
                                    embed.set_field_at(i, name=field.name, value=formatted_time, inline=field.inline)
                                elif "Map" in field.name or "🗺️" in field.name:
                                    embed.set_field_at(i, name=field.name, value=match_details[5], inline=field.inline)
                            
                            await message.edit(embed=embed)
                            logger.info(f"✅ Streamer embed updated for match {self.match_id}")
                        return
                        
                    except discord.NotFound:
                        continue
            
        except Exception as e:
            logger.error(f"Error updating streamer embed: {e}")
    
    def _format_date_display(self, date_str: str) -> str:
        if not date_str or date_str == 'TBA':
            return "TBA"
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%d.%m.%Y')
        except:
            return date_str


class OrgaResultEditView(discord.ui.View):
    """
    NEUE Klasse: Event Orga Result Editor
    """
    
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any], submitting_user):
        super().__init__(timeout=300)
        self.bot = bot
        self.match_id = match_id
        self.match_data = match_data
        self.submitting_user = submitting_user
        
        # Winner Selection
        winner_options = [
            discord.SelectOption(label=match_data['team1_name'], value=match_data['team1_name']),
            discord.SelectOption(label=match_data['team2_name'], value=match_data['team2_name'])
        ]
        
        timestamp = int(datetime.now().timestamp())
        self.winner_select = discord.ui.Select(
            placeholder="Select winning team...",
            options=winner_options,
            custom_id=f"orga_result_winner_select_{match_id}_{timestamp}"
        )
        self.winner_select.callback = self.winner_selected
        
        # Score Selection
        score_options = [
            discord.SelectOption(label="2-0 (Won 2 rounds, lost 0)", value="2-0"),
            discord.SelectOption(label="2-1 (Won 2 rounds, lost 1)", value="2-1")
        ]
        
        self.score_select = discord.ui.Select(
            placeholder="Select score...",
            options=score_options,
            custom_id=f"orga_result_score_select_{match_id}_{timestamp}",
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
            # Result Data erstellen
            new_result = {
                'winner': self.selected_winner,
                'score': self.selected_score,
                'submitted_by_team': 'Event Orga (Override)',
                'submitted_by_user': self.submitting_user.id,
                'submitted_at': datetime.now().isoformat(),
                'orga_edited': True
            }
            
            # Result in Datenbank speichern
            self.bot.db.update_match_result(self.match_id, new_result)
            
            # Match Status auf 'confirmed' setzen (da Orga das direkt bestätigt)
            self.bot.db.confirm_match_result(self.match_id)
            
            # Buttons deaktivieren
            for item in self.children:
                item.disabled = True
            
            embed = discord.Embed(
                title="✅ Result Set by Event Orga!",
                description="Event Orga has set the match result:",
                color=discord.Color.green()
            )
            embed.add_field(name="🏆 Match", value=f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}", inline=False)
            embed.add_field(name="🥇 Winner", value=f"**{self.selected_winner}**", inline=True)
            embed.add_field(name="📊 Score", value=f"**{self.selected_score}**", inline=True)
            embed.add_field(name="👤 Set by", value=self.submitting_user.mention, inline=True)
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            # ALLE Embeds aktualisieren
            await self._update_all_embeds_with_result()
            
            # Channel Status aktualisieren
            try:
                await self.bot.status_manager.update_channel_status(self.match_id, 'completed')
                logger.info(f"✅ Status updated to 'completed' for match {self.match_id}")
            except Exception as status_error:
                logger.error(f"Error updating status: {status_error}")
            
            # Match archivieren
            await self._archive_match_after_orga_result()
            
            logger.info(f"✅ Orga set result for match {self.match_id}: {self.selected_winner} wins {self.selected_score}")
            
        except Exception as e:
            logger.error(f"Error in orga result setting: {e}")
            try:
                await interaction.response.send_message("❌ Error setting result!", ephemeral=True)
            except:
                try:
                    await interaction.followup.send("❌ Error setting result!", ephemeral=True)
                except:
                    pass
    
    async def _update_all_embeds_with_result(self):
        """Aktualisiert alle Embeds mit dem neuen Result"""
        try:
            logger.info(f"🔄 Updating all embeds with orga result for match {self.match_id}")
            
            # 1. Private Embed aktualisieren
            await self._update_private_embed_with_result()
            
            # 2. Public Embed aktualisieren
            await self._update_public_embed_with_result()
            
            # 3. Streamer Embed aktualisieren
            await self._update_streamer_embed_with_result()
            
            # 4. Private Match View Buttons deaktivieren
            await self._disable_private_match_buttons()
            
            logger.info(f"✅ All embeds updated with orga result for match {self.match_id}")
            
        except Exception as e:
            logger.error(f"Error updating all embeds with result: {e}")
    
    async def _update_private_embed_with_result(self):
        """Aktualisiert Private Embed mit Result"""
        try:
            match_details = self.bot.db.get_match_details(self.match_id)
            if not match_details or not match_details[8]:
                return
            
            private_channel = self.bot.get_channel(match_details[8])
            if not private_channel:
                return
            
            async for message in private_channel.history(limit=50, oldest_first=True):
                if (message.author == self.bot.user and 
                    message.embeds and 
                    message.components):
                    
                    embed = message.embeds[0]
                    if (embed.footer and 
                        f"Match ID: {self.match_id}" in embed.footer.text):
                        
                        # Status Field aktualisieren
                        for i, field in enumerate(embed.fields):
                            if "Status" in field.name or "ℹ️" in field.name:
                                embed.set_field_at(i, name=field.name, value="✅ Match completed and confirmed by Event Orga", inline=field.inline)
                                break
                        
                        embed.color = discord.Color.green()
                        await message.edit(embed=embed)
                        break
            
        except Exception as e:
            logger.error(f"Error updating private embed with result: {e}")
    
    async def _update_public_embed_with_result(self):
        """Aktualisiert Public Embed mit Result"""
        try:
            stored_channel_id = self.bot.db.get_setting(f'public_match_{self.match_id}_channel_id')
            if not stored_channel_id:
                return
            
            channel = None
            for guild in self.bot.guilds:
                channel = guild.get_channel(int(stored_channel_id))
                if channel:
                    break
            
            if not channel:
                return
            
            public_message_id = self.bot.db.get_setting(f'public_match_{self.match_id}_message_id')
            if not public_message_id:
                return
            
            try:
                message = await channel.fetch_message(int(public_message_id))
                
                if message.embeds:
                    embed = message.embeds[0]
                    
                    # Result Field aktualisieren
                    result_text = f"||**{self.selected_winner}** wins ({self.selected_score})||"
                    
                    result_field_found = False
                    for i, field in enumerate(embed.fields):
                        if "Result" in field.name or "📊" in field.name:
                            embed.set_field_at(i, name=field.name, value=result_text, inline=field.inline)
                            result_field_found = True
                            break
                    
                    if not result_field_found:
                        embed.add_field(name="📊 Result", value=result_text, inline=False)
                    
                    embed.color = discord.Color.green()
                    await message.edit(embed=embed)
                    
            except discord.NotFound:
                pass
                
        except Exception as e:
            logger.error(f"Error updating public embed with result: {e}")
    
    async def _update_streamer_embed_with_result(self):
        """Aktualisiert Streamer Embed mit Result"""
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
                            
                            # Title aktualisieren
                            if "✅" not in embed.title:
                                embed.title = f"✅ {embed.title.replace('📺', '').strip()}"
                            
                            # Status Field aktualisieren
                            result_text = f"**{self.selected_winner}** wins ({self.selected_score})"
                            
                            for i, field in enumerate(embed.fields):
                                if "Status" in field.name or "Final Result" in field.name or "📺" in field.name:
                                    embed.set_field_at(i, name="📺 Final Result", value=f"✅ **COMPLETED by Event Orga**\n{result_text}", inline=field.inline)
                                    break
                            
                            embed.color = discord.Color.green()
                            
                            # Disabled View erstellen
                            from ui.match_interactions.orga_result_confirmation import StreamerMatchViewDisabled
                            disabled_view = StreamerMatchViewDisabled()
                            
                            await message.edit(embed=embed, view=disabled_view)
                        return
                        
                    except discord.NotFound:
                        continue
            
        except Exception as e:
            logger.error(f"Error updating streamer embed with result: {e}")
    
    async def _disable_private_match_buttons(self):
        """Deaktiviert alle Buttons im Private Match"""
        try:
            match_details = self.bot.db.get_match_details(self.match_id)
            if not match_details or not match_details[8]:
                return
            
            private_channel = self.bot.get_channel(match_details[8])
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
                        
                        # Alle Buttons deaktivieren
                        view.result_submission_button.disabled = True
                        view.result_submission_button.label = "✅ Results Set by Orga"
                        view.result_submission_button.style = discord.ButtonStyle.success
                        
                        await message.edit(embed=embed, view=view)
                        break
            
        except Exception as e:
            logger.error(f"Error disabling private match buttons: {e}")
    
    async def _archive_match_after_orga_result(self):
        """
        FIXED: Archiviert den PRIVATE Channel nach Orga-Result, Public Channel bleibt
        """
        try:
            # FIXED: Nur PRIVATE Channel archivieren, nicht Public Channel
            archive_category_id = self.bot.config['categories'].get('archive_category_id')
            if not archive_category_id:
                logger.warning("No archive category configured in config.json")
                return
            
            # Archive Kategorie finden
            archive_category = None
            for guild in self.bot.guilds:
                category = guild.get_channel(archive_category_id)
                if category:
                    archive_category = category
                    break
            
            if not archive_category:
                logger.warning(f"Archive category {archive_category_id} not found")
                return
            
            # PRIVATE Channel archivieren
            match_details = self.bot.db.get_match_details(self.match_id)
            if not match_details or not match_details[8]:
                logger.info(f"No private channel to archive for match {self.match_id}")
                return
            
            private_channel = None
            for guild in self.bot.guilds:
                channel = guild.get_channel(match_details[8])
                if channel:
                    private_channel = channel
                    break
            
            if not private_channel:
                logger.warning(f"Private channel {match_details[8]} not found")
                return
            
            # Server-Details für Archive-Message erhalten
            server_data_json = self.bot.db.get_setting(f'match_{self.match_id}_server')
            server_details = None
            if server_data_json:
                try:
                    import json
                    server_details = json.loads(server_data_json)
                except:
                    pass
            
            # Team-Rollen aus Private Channel entfernen
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
                team1_role = private_channel.guild.get_role(team1_role_id)
                if team1_role and team1_role in overwrites:
                    del overwrites[team1_role]
            
            if team2_role_id:
                team2_role = private_channel.guild.get_role(team2_role_id)
                if team2_role and team2_role in overwrites:
                    del overwrites[team2_role]
            
            # Private Channel archivieren
            await private_channel.edit(
                category=archive_category,
                overwrites=overwrites,
                name=f"archived-{private_channel.name}",
                reason=f"Match {self.match_id} completed by Event Orga"
            )
            
            # Archive-Message im Private Channel senden
            archive_embed = discord.Embed(
                title="📁 Match Archived by Event Orga",
                description="This match has been completed and archived by Event Orga.",
                color=discord.Color.green()
            )
            archive_embed.add_field(
                name="🏆 Final Result", 
                value=f"**{self.selected_winner}** wins {self.selected_score}", 
                inline=False
            )
            archive_embed.add_field(
                name="👤 Set by", 
                value=self.submitting_user.mention, 
                inline=True
            )
            
            if server_details:
                server_text = f"**{server_details['server_name']}**\nPassword: `{server_details['server_password']}`\nProvided by: {server_details['offering_team']}"
                archive_embed.add_field(name="🖥️ Server Details", value=server_text, inline=False)
            
            await private_channel.send(embed=archive_embed)
            
            logger.info(f"✅ PRIVATE channel archived for match {self.match_id} after orga result - PUBLIC channel remains active")
            
        except Exception as e:
            logger.error(f"Error archiving private channel after orga result: {e}")


class MatchDeleteConfirmationModal(discord.ui.Modal):
    """Modal zur Bestätigung der Match-Löschung mit 4-stelliger Zufallszahl"""
    
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any], confirmation_code: str):
        super().__init__(title="🗑️ DELETE MATCH - FINAL CONFIRMATION", timeout=300)
        self.bot = bot
        self.match_id = match_id
        self.match_data = match_data
        self.confirmation_code = confirmation_code
        
        self.code_input = discord.ui.TextInput(
            label=f"Enter confirmation code: {confirmation_code}",
            placeholder="Enter the 4-digit code above",
            min_length=4,
            max_length=4,
            required=True
        )
        
        self.add_item(self.code_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            entered_code = self.code_input.value.strip()
            
            if entered_code != self.confirmation_code:
                await interaction.response.send_message("❌ Incorrect confirmation code! Match deletion cancelled.", ephemeral=True)
                return
            
            # Bestätigung erhalten - Match vollständig löschen
            await interaction.response.defer(ephemeral=True)
            
            delete_result = await self._delete_match_completely()
            
            if delete_result['success']:
                embed = discord.Embed(
                    title="🗑️ Match Completely Deleted!",
                    description=f"Match **{self.match_data['team1_name']} vs {self.match_data['team2_name']}** has been permanently deleted.",
                    color=discord.Color.red()
                )
                embed.add_field(name="🆔 Match ID", value=str(self.match_id), inline=True)
                embed.add_field(name="👤 Deleted by", value=interaction.user.mention, inline=True)
                embed.add_field(name="🕒 Deleted at", value=datetime.now().strftime('%d.%m.%Y %H:%M'), inline=True)
                
                deletion_summary = []
                if delete_result.get('private_channel_deleted'):
                    deletion_summary.append("✅ Private channel deleted")
                if delete_result.get('public_channel_deleted'):
                    deletion_summary.append("✅ Public channel deleted")
                if delete_result.get('streamer_message_deleted'):
                    deletion_summary.append("✅ Streamer message deleted")
                if delete_result.get('database_cleaned'):
                    deletion_summary.append("✅ Database entries removed")
                if delete_result.get('persistence_cleaned'):
                    deletion_summary.append("✅ UI persistence cleaned")
                
                embed.add_field(name="📋 Deletion Summary", value="\n".join(deletion_summary), inline=False)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                logger.warning(f"🗑️ MATCH DELETED: ID {self.match_id} ({self.match_data['team1_name']} vs {self.match_data['team2_name']}) by {interaction.user}")
                
            else:
                error_embed = discord.Embed(
                    title="❌ Match Deletion Failed",
                    description="Some errors occurred during match deletion.",
                    color=discord.Color.orange()
                )
                error_embed.add_field(name="🔍 Details", value=delete_result.get('error', 'Unknown error'), inline=False)
                
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in match deletion confirmation: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error during match deletion!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Error during match deletion!", ephemeral=True)
            except:
                pass
    
    async def _delete_match_completely(self) -> Dict[str, Any]:
        """Löscht das Match komplett mit allen zugehörigen Ressourcen - SEQUENZIELL"""
        result = {
            'success': False,
            'private_channel_deleted': False,
            'public_channel_deleted': False,
            'streamer_message_deleted': False,
            'database_cleaned': False,
            'persistence_cleaned': False,
            'error': None
        }
        
        try:
            # 1. Match Details aus DB holen (VOR jeder Löschung!)
            match_details = self.bot.db.get_match_details(self.match_id)
            if not match_details:
                result['error'] = "Match not found in database"
                return result
            
            logger.info(f"🗑️ Starting sequential deletion for match {self.match_id}")
            
            # SCHRITT 1: Public Channel löschen und warten
            logger.info(f"🗑️ Step 1: Deleting public channel...")
            try:
                stored_channel_id = self.bot.db.get_setting(f'public_match_{self.match_id}_channel_id')
                if stored_channel_id:
                    public_channel = None
                    for guild in self.bot.guilds:
                        channel = guild.get_channel(int(stored_channel_id))
                        if channel:
                            public_channel = channel
                            break
                    
                    if public_channel:
                        await public_channel.delete(reason=f"Match {self.match_id} deleted by Orga")
                        result['public_channel_deleted'] = True
                        logger.info(f"✅ Step 1 COMPLETE: Public channel {stored_channel_id} deleted")
                        
                        # WARTEN nach Public Channel Löschung
                        await asyncio.sleep(2)
                    else:
                        logger.warning(f"Public channel {stored_channel_id} not found")
                else:
                    logger.info(f"No public channel found for match {self.match_id}")
            except Exception as e:
                logger.error(f"❌ Step 1 FAILED: Error deleting public channel: {e}")
            
            # SCHRITT 2: Streamer Message löschen und warten
            logger.info(f"🗑️ Step 2: Deleting streamer message...")
            try:
                streamer_message_id = self.bot.db.get_match_streamer_message_id(self.match_id)
                if streamer_message_id:
                    streamer_channel_id = self.bot.config['channels'].get('streamer_channel_id')
                    if streamer_channel_id:
                        streamer_channel = None
                        for guild in self.bot.guilds:
                            channel = guild.get_channel(streamer_channel_id)
                            if channel:
                                streamer_channel = channel
                                break
                        
                        if streamer_channel:
                            try:
                                message = await streamer_channel.fetch_message(streamer_message_id)
                                await message.delete()
                                result['streamer_message_deleted'] = True
                                logger.info(f"✅ Step 2 COMPLETE: Streamer message {streamer_message_id} deleted")
                                
                                # WARTEN nach Streamer Message Löschung
                                await asyncio.sleep(1)
                            except discord.NotFound:
                                logger.warning(f"Streamer message {streamer_message_id} not found")
                            except discord.Forbidden:
                                logger.warning(f"No permission to delete streamer message {streamer_message_id}")
                        else:
                            logger.warning(f"Streamer channel {streamer_channel_id} not found")
                    else:
                        logger.warning(f"No streamer_channel_id configured in config.json")
                else:
                    logger.info(f"No streamer message found for match {self.match_id}")
            except Exception as e:
                logger.error(f"❌ Step 2 FAILED: Error deleting streamer message: {e}")
            
            # SCHRITT 3: Private Channel löschen und warten
            logger.info(f"🗑️ Step 3: Deleting private channel...")
            try:
                private_channel_id = match_details[8]
                if private_channel_id:
                    private_channel = self.bot.get_channel(private_channel_id)
                    if private_channel:
                        await private_channel.delete(reason=f"Match {self.match_id} deleted by Orga")
                        result['private_channel_deleted'] = True
                        logger.info(f"✅ Step 3 COMPLETE: Private channel {private_channel_id} deleted")
                        
                        # WARTEN nach Private Channel Löschung
                        await asyncio.sleep(2)
                    else:
                        logger.warning(f"Private channel {private_channel_id} not found")
                else:
                    logger.info(f"No private channel found for match {self.match_id}")
            except Exception as e:
                logger.error(f"❌ Step 3 FAILED: Error deleting private channel: {e}")
            
            # SCHRITT 4: Notification Messages löschen und warten
            logger.info(f"🗑️ Step 4: Deleting notification messages...")
            try:
                notification_channel_id = self.bot.config['channels'].get('streamer_notification_channel_id')
                if notification_channel_id:
                    notification_channel = None
                    for guild in self.bot.guilds:
                        channel = guild.get_channel(notification_channel_id)
                        if channel:
                            notification_channel = channel
                            break
                    
                    if notification_channel:
                        deleted_count = 0
                        async for message in notification_channel.history(limit=50):
                            if (message.author == self.bot.user and 
                                message.embeds and 
                                len(message.embeds) > 0 and
                                message.embeds[0].description and
                                f"{self.match_data['team1_name']} vs {self.match_data['team2_name']}" in message.embeds[0].description):
                                try:
                                    await message.delete()
                                    deleted_count += 1
                                    logger.info(f"✅ Notification message deleted for match {self.match_id}")
                                    # WARTEN zwischen Message Löschungen
                                    await asyncio.sleep(0.5)
                                except discord.NotFound:
                                    logger.debug(f"Notification message already deleted")
                                except discord.Forbidden:
                                    logger.warning(f"No permission to delete notification message")
                                except Exception as msg_error:
                                    logger.warning(f"Error deleting notification message: {msg_error}")
                        
                        logger.info(f"✅ Step 4 COMPLETE: {deleted_count} notification messages deleted")
                    else:
                        logger.warning(f"Notification channel {notification_channel_id} not found")
                else:
                    logger.info(f"No streamer_notification_channel_id configured")
            except Exception as e:
                logger.error(f"❌ Step 4 FAILED: Error deleting notification messages: {e}")
            
            # SCHRITT 5: UI Persistence aufräumen (VOR Database!)
            logger.info(f"🗑️ Step 5: Cleaning UI persistence...")
            try:
                # Lazy Persistence aufräumen
                if hasattr(self.bot, 'lazy_persistence') and hasattr(self.bot.lazy_persistence, 'active_views'):
                    views_to_remove = []
                    for msg_id, view_data in self.bot.lazy_persistence.active_views.items():
                        if view_data.get('data', {}).get('match_id') == self.match_id:
                            views_to_remove.append(msg_id)
                    
                    for msg_id in views_to_remove:
                        del self.bot.lazy_persistence.active_views[msg_id]
                    
                    logger.info(f"Cleaned {len(views_to_remove)} lazy persistence views")
                
                # Fast Startup Persistence aufräumen
                if hasattr(self.bot, 'fast_startup') and hasattr(self.bot.fast_startup, 'restored_views'):
                    views_to_remove = []
                    for msg_id, view_data in self.bot.fast_startup.restored_views.items():
                        if view_data.get('data', {}).get('match_id') == self.match_id:
                            views_to_remove.append(msg_id)
                    
                    for msg_id in views_to_remove:
                        del self.bot.fast_startup.restored_views[msg_id]
                    
                    logger.info(f"Cleaned {len(views_to_remove)} fast startup persistence views")
                
                result['persistence_cleaned'] = True
                logger.info(f"✅ Step 5 COMPLETE: UI persistence cleaned")
                
                # WARTEN nach Persistence Cleanup
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Step 5 FAILED: Error cleaning persistence: {e}")
            
            # SCHRITT 6: Database Einträge löschen (GANZ AM ENDE!)
            logger.info(f"🗑️ Step 6: Cleaning database (FINAL STEP)...")
            try:
                cursor = self.bot.db.conn.cursor()
                
                # Match Streamers löschen
                cursor.execute('DELETE FROM match_streamers WHERE match_id = ?', (self.match_id,))
                streamers_deleted = cursor.rowcount
                
                # Match Streamer Messages löschen
                cursor.execute('DELETE FROM match_streamer_messages WHERE match_id = ?', (self.match_id,))
                streamer_messages_deleted = cursor.rowcount
                
                # UI Messages löschen
                cursor.execute('DELETE FROM ui_messages WHERE related_match_id = ?', (self.match_id,))
                ui_messages_deleted = cursor.rowcount
                
                # Ongoing Interactions löschen
                cursor.execute('DELETE FROM ongoing_interactions WHERE match_id = ?', (self.match_id,))
                interactions_deleted = cursor.rowcount
                
                # Settings für dieses Match löschen
                cursor.execute("DELETE FROM tournament_settings WHERE key LIKE ?", (f'%match_{self.match_id}%',))
                match_settings_deleted = cursor.rowcount
                
                cursor.execute("DELETE FROM tournament_settings WHERE key LIKE ?", (f'%public_match_{self.match_id}%',))
                public_settings_deleted = cursor.rowcount
                
                # Match selbst löschen
                cursor.execute('DELETE FROM matches WHERE id = ?', (self.match_id,))
                match_deleted = cursor.rowcount
                
                # COMMIT am Ende
                self.bot.db.conn.commit()
                
                result['database_cleaned'] = True
                logger.info(f"✅ Step 6 COMPLETE: Database cleaned - "
                           f"Streamers: {streamers_deleted}, "
                           f"Streamer Messages: {streamer_messages_deleted}, "
                           f"UI Messages: {ui_messages_deleted}, "
                           f"Interactions: {interactions_deleted}, "
                           f"Match Settings: {match_settings_deleted}, "
                           f"Public Settings: {public_settings_deleted}, "
                           f"Match: {match_deleted}")
                
            except Exception as e:
                logger.error(f"❌ Step 6 FAILED: Error cleaning database: {e}")
                result['error'] = f"Database cleanup failed: {e}"
                # Rollback bei DB-Fehler
                try:
                    self.bot.db.conn.rollback()
                    logger.info("Database rollback completed")
                except:
                    pass
            
            # Erfolg bewerten
            result['success'] = result['database_cleaned']  # Mindestens DB muss erfolgreich sein
            
            logger.info(f"🗑️ SEQUENTIAL DELETION COMPLETE for match {self.match_id}: "
                       f"Success={result['success']}, "
                       f"Public={result['public_channel_deleted']}, "
                       f"Streamer={result['streamer_message_deleted']}, "
                       f"Private={result['private_channel_deleted']}, "
                       f"DB={result['database_cleaned']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Critical error in match deletion: {e}")
            result['error'] = str(e)
            return result


class OrgaEditView(discord.ui.View):
    
    def __init__(self, bot, match_id: int, match_data: Dict[str, Any]):
        super().__init__(timeout=300)
        self.bot = bot
        self.match_id = match_id
        self.match_data = match_data
    
    @discord.ui.button(label='✏️ Edit Match Details', style=discord.ButtonStyle.primary)
    async def edit_match_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == self.bot.EVENT_ORGA_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("❌ Only Event Orga can edit match details!", ephemeral=True)
            return
        
        current_details = self.bot.db.get_match_details(self.match_id)
        if not current_details:
            await interaction.response.send_message("❌ Match not found!", ephemeral=True)
            return
        
        current_dict = {
            'match_date': current_details[3],
            'match_time': current_details[4],
            'map_name': current_details[5]
        }
        
        modal = OrgaEditModal(self.bot, self.match_id, self.match_data, current_dict)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='📊 Edit Result', style=discord.ButtonStyle.success)
    async def edit_result(self, interaction: discord.Interaction, button: discord.ui.Button):
        """NEUER Button: Event Orga Result Editor"""
        if not any(role.id == self.bot.EVENT_ORGA_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("❌ Only Event Orga can edit results!", ephemeral=True)
            return
        
        # Real team names holen
        real_match_data = self._get_real_team_names_from_config()
        
        # Result Edit View erstellen
        edit_view = OrgaResultEditView(self.bot, self.match_id, real_match_data, interaction.user)
        
        embed = discord.Embed(
            title="📊 Set/Edit Match Result",
            description="Set or edit the match result (Event Orga override):",
            color=discord.Color.green()
        )
        embed.add_field(name="🏆 Match", value=f"{real_match_data['team1_name']} vs {real_match_data['team2_name']}", inline=False)
        embed.add_field(name="ℹ️ Instructions", value="1. Select the winning team\n2. Select the final score\n\n⚠️ **This will set the result directly and mark the match as confirmed!**", inline=False)
        
        await interaction.response.send_message(embed=embed, view=edit_view, ephemeral=True)
    
    @discord.ui.button(label='🔄 Reset Server', style=discord.ButtonStyle.secondary)
    async def reset_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == self.bot.EVENT_ORGA_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("❌ Only Event Orga can reset server details!", ephemeral=True)
            return
        
        try:
            self.bot.db.set_setting(f'match_{self.match_id}_server', '')
            
            await self._update_all_embeds_remove_server()
            
            embed = discord.Embed(
                title="✅ Server Details Reset!",
                description=f"Server details have been cleared for this match.",
                color=discord.Color.orange()
            )
            embed.add_field(name="👤 Reset by", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            
            logger.info(f"Server details reset for match {self.match_id} by {interaction.user}")
            
        except Exception as e:
            logger.error(f"Error resetting server: {e}")
            await interaction.response.send_message("❌ Error resetting server details!", ephemeral=True)
    
    @discord.ui.button(label='🗑️ DELETE MATCH', style=discord.ButtonStyle.danger)
    async def delete_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button zum vollständigen Löschen eines Matches"""
        if not any(role.id == self.bot.EVENT_ORGA_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("❌ Only Event Orga can delete matches!", ephemeral=True)
            return
        
        # 4-stellige Zufallszahl generieren
        confirmation_code = f"{random.randint(1000, 9999)}"
        
        # Warnung-Embed
        warning_embed = discord.Embed(
            title="⚠️ DANGER: PERMANENT MATCH DELETION",
            description="You are about to **PERMANENTLY DELETE** this entire match!",
            color=discord.Color.red()
        )
        warning_embed.add_field(
            name="🗑️ What will be deleted:",
            value="• **Private match channel** (completely removed)\n"
                  "• **Public match channel** (completely removed)\n" 
                  "• **Streamer embed** (deleted from streamer channel)\n"
                  "• **All database entries** (match, streamers, settings)\n"
                  "• **All UI persistence** (buttons, views, interactions)",
            inline=False
        )
        warning_embed.add_field(
            name="🆔 Match Details:",
            value=f"**ID:** {self.match_id}\n**Match:** {self.match_data['team1_name']} vs {self.match_data['team2_name']}\n**Map:** {self.match_data.get('map_name', 'TBA')}",
            inline=False
        )
        warning_embed.add_field(
            name="🔢 Confirmation Required:",
            value=f"**Enter this code: `{confirmation_code}`**",
            inline=False
        )
        warning_embed.add_field(
            name="❌ This action is IRREVERSIBLE!",
            value="The match and all associated data will be permanently lost.",
            inline=False
        )
        
        # Modal zeigen
        modal = MatchDeleteConfirmationModal(self.bot, self.match_id, self.match_data, confirmation_code)
        
        await interaction.response.send_message(embed=warning_embed, ephemeral=True)
        await interaction.followup.send("Enter confirmation code:", view=DeleteConfirmationView(modal), ephemeral=True)
    
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
    
    async def _update_all_embeds_remove_server(self):
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
                        
                        fields_to_keep = []
                        for field in embed.fields:
                            if "Server" not in field.name and "🖥️" not in field.name:
                                fields_to_keep.append((field.name, field.value, field.inline))
                        
                        new_embed = discord.Embed(
                            title=embed.title,
                            color=embed.color
                        )
                        
                        for name, value, inline in fields_to_keep:
                            new_embed.add_field(name=name, value=value, inline=inline)
                        
                        new_embed.set_footer(text=embed.footer.text if embed.footer else None)
                        
                        from ui.match_interactions.private_match_view import PrivateMatchView
                        view = PrivateMatchView(self.bot, self.match_id, self.match_data)
                        
                        view.server_offer_button.disabled = False
                        view.server_offer_button.label = "🖥️ Offer Server"
                        view.server_offer_button.style = discord.ButtonStyle.secondary
                        
                        await message.edit(embed=new_embed, view=view)
                        logger.info(f"Server details removed from private embed for match {self.match_id}")
                        break
            
        except Exception as e:
            logger.error(f"Error removing server from embeds: {e}")
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class DeleteConfirmationView(discord.ui.View):
    """Helper View mit Button zum Öffnen des Confirmation Modals"""
    
    def __init__(self, modal: MatchDeleteConfirmationModal):
        super().__init__(timeout=300)
        self.modal = modal
    
    @discord.ui.button(label='Enter Confirmation Code', style=discord.ButtonStyle.danger, emoji='🔢')
    async def open_confirmation_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self.modal)