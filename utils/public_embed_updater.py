# utils/public_embed_updater.py
"""
Public Embed Update System - WITH TIMEZONE SUPPORT
"""

import discord
import logging
from typing import Dict, Any, Optional
from utils.timezone_helper import TimezoneHelper

logger = logging.getLogger(__name__)

class PublicEmbedUpdater:
    
    def __init__(self, bot):
        self.bot = bot
    
    async def update_public_embed_for_match(self, match_id: int, update_type: str = "general"):
        """
        Updated das Public Embed für ein Match nach Änderungen
        """
        try:
            # Public Match Channel für dieses Match finden
            public_channel, public_message = await self._find_public_match_channel_and_message(match_id)
            
            if not public_channel or not public_message:
                logger.warning(f"No public channel/message found for match {match_id}")
                return False
            
            # Match Details aus Datenbank holen
            match_details = self.bot.db.get_match_details(match_id)
            if not match_details:
                logger.warning(f"No match details found for match {match_id}")
                return False
            
            # Aktuelle Streamer-Informationen holen
            current_streamers = self.bot.db.get_match_streamers_detailed(match_id)
            
            # Public Embed aktualisieren
            await self._update_public_embed_with_current_data(
                public_message, match_details, current_streamers, update_type
            )
            
            logger.info(f"✅ Public embed updated for match {match_id} ({update_type})")
            return True
            
        except Exception as e:
            logger.error(f"Error updating public embed for match {match_id}: {e}")
            return False
    
    async def _find_public_match_channel_and_message(self, match_id: int):
        """
        Findet den Public Match Channel und die entsprechende Message
        """
        try:
            # Channel ID aus Datenbank holen
            stored_channel_id = self.bot.db.get_setting(f'public_match_{match_id}_channel_id')
            if not stored_channel_id:
                return None, None
            
            # Channel finden
            channel = None
            for guild in self.bot.guilds:
                channel = guild.get_channel(int(stored_channel_id))
                if channel:
                    break
            
            if not channel:
                return None, None
            
            # Public Message ID holen
            public_message_id = self.bot.db.get_setting(f'public_match_{match_id}_message_id')
            if not public_message_id:
                # Fallback: Suche nach der Match Embed Message
                async for message in channel.history(limit=10):
                    if (message.author == self.bot.user and 
                        message.embeds and 
                        message.embeds[0].footer and
                        f"Match ID: {match_id}" in message.embeds[0].footer.text):
                        
                        # Message ID für zukünftige Updates speichern
                        self.bot.db.set_setting(f'public_match_{match_id}_message_id', str(message.id))
                        return channel, message
                return channel, None
            
            # Message direkt holen
            try:
                message = await channel.fetch_message(int(public_message_id))
                return channel, message
            except discord.NotFound:
                # Message wurde gelöscht, entferne ID aus DB
                self.bot.db.set_setting(f'public_match_{match_id}_message_id', '')
                return channel, None
            
        except Exception as e:
            logger.error(f"Error finding public channel/message for match {match_id}: {e}")
            return None, None
    
    async def _update_public_embed_with_current_data(self, message: discord.Message, match_details: tuple, streamers: list, update_type: str):
        """
        Aktualisiert das Public Embed mit aktuellen Daten - WITH TIMEZONE SUPPORT
        """
        try:
            if not message.embeds:
                return
            
            embed = message.embeds[0]
            
            # Grundlegende Match-Daten aktualisieren
            formatted_date = self._format_date_display(match_details[3])
            
            # TIMEZONE SUPPORT: Zeit mit Timezone formatieren
            raw_match_time = match_details[4]
            if raw_match_time and raw_match_time != "*TBA*":
                formatted_match_time = TimezoneHelper.format_time_with_timezone(raw_match_time, self.bot)
            else:
                formatted_match_time = "*TBA*"
            
            # Felder aktualisieren
            for i, field in enumerate(embed.fields):
                if "Match Date" in field.name or "📅" in field.name:
                    embed.set_field_at(i, name=field.name, value=formatted_date, inline=field.inline)
                elif "Match Time" in field.name or "🕒" in field.name:
                    embed.set_field_at(i, name=field.name, value=formatted_match_time, inline=field.inline)
                elif "Map" in field.name or "🗺️" in field.name:
                    embed.set_field_at(i, name=field.name, value=match_details[5], inline=field.inline)
                # TIMEZONE SUPPORT: Timezone-Info Feld aktualisieren
                elif "Timezone Info" in field.name or "⏰" in field.name:
                    timezone_warning = TimezoneHelper.get_timezone_warning_text(self.bot)
                    embed.set_field_at(i, name=field.name, value=timezone_warning, inline=field.inline)
            
            # Streamer-Informationen aktualisieren
            await self._update_streamer_field_in_public_embed(embed, streamers, match_details)
            
            # Result-Feld aktualisieren (falls Match abgeschlossen)
            await self._update_result_field_if_completed(embed, match_details)
            
            # Embed-Farbe basierend auf Status
            if match_details[10] == 'confirmed':
                embed.color = discord.Color.green()
            elif match_details[10] == 'completed':
                embed.color = discord.Color.orange()
            else:
                embed.color = discord.Color.blue()
            
            # Message aktualisieren
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error updating public embed content: {e}")
    
    async def _update_streamer_field_in_public_embed(self, embed: discord.Embed, streamers: list, match_details: tuple):
        """
        Aktualisiert oder fügt Streamer-Feld hinzu
        """
        try:
            # Bestehende Streamer-Felder entfernen
            fields_to_keep = []
            for field in embed.fields:
                if not ("Streamer" in field.name or "📺" in field.name):
                    fields_to_keep.append((field.name, field.value, field.inline))
            
            # Embed neu aufbauen
            embed.clear_fields()
            for name, value, inline in fields_to_keep:
                embed.add_field(name=name, value=value, inline=inline)
            
            # Streamer-Feld hinzufügen, falls vorhanden
            if streamers and len(streamers) > 0:
                streamer_data = streamers[0]
                stream_url = streamer_data.get('stream_url', '')
                
                # Server-Nickname verwenden (FIXED)
                username = self._get_streamer_display_name(streamer_data['streamer_id'])
                
                # Team-Namen aus Match Details holen
                team1_name = match_details[16] if len(match_details) > 16 else f"Team {match_details[1]}"
                team2_name = match_details[17] if len(match_details) > 17 else f"Team {match_details[2]}"
                
                # Falls Team-Namen noch generisch sind, aus Config laden
                if team1_name.startswith("Team ") or team2_name.startswith("Team "):
                    try:
                        all_teams = self.bot.get_all_teams()
                        for team_tuple in all_teams:
                            team_config_id, name, role_id, members, active = team_tuple
                            if team_config_id == match_details[1]:
                                team1_name = name
                            elif team_config_id == match_details[2]:
                                team2_name = name
                    except:
                        pass
                
                # Richtigen Team-Namen basierend auf Streamer-Seite wählen
                if streamer_data['team_side'] == 'team1':
                    team_name = team1_name
                else:
                    team_name = team2_name
                
                if stream_url:
                    streamer_text = f"{team_name}: [{username}]({stream_url})"
                else:
                    streamer_text = f"{team_name}: {username}"
                
                # Streamer-Feld vor Rules-Feld einfügen
                rules_index = -1
                for i, field in enumerate(embed.fields):
                    if "Rules" in field.name or "📖" in field.name:
                        rules_index = i
                        break
                
                if rules_index >= 0:
                    embed.insert_field_at(rules_index, name="📺 Streamer", value=streamer_text, inline=False)
                else:
                    embed.add_field(name="📺 Streamer", value=streamer_text, inline=False)
            
        except Exception as e:
            logger.error(f"Error updating streamer field in public embed: {e}")
    
    def _get_streamer_display_name(self, streamer_id: int) -> str:
        """
        Holt den Server-Nickname oder fällt auf Display-Name zurück (FIXED)
        """
        try:
            # Versuche Member zu finden (hat Server-Nickname)
            for guild in self.bot.guilds:
                member = guild.get_member(streamer_id)
                if member:
                    # Priorität: Server-Nickname > Global Display Name > Username
                    return member.nick or member.global_name or member.name
            
            # Fallback auf User
            user = self.bot.get_user(streamer_id)
            return user.global_name or user.name if user else f"User {streamer_id}"
            
        except Exception as e:
            logger.error(f"Error getting streamer display name: {e}")
            return f"User {streamer_id}"
    
    async def _update_result_field_if_completed(self, embed: discord.Embed, match_details: tuple):
        """
        Aktualisiert Result-Feld falls Match abgeschlossen
        """
        try:
            if match_details[11] and match_details[10] == 'confirmed':
                import json
                try:
                    result_data = json.loads(match_details[11])
                    result_text = f"||**{result_data['winner']}** wins with **{result_data['score']}**||"
                    
                    # Result-Feld aktualisieren oder hinzufügen
                    result_field_found = False
                    for i, field in enumerate(embed.fields):
                        if "Result" in field.name or "📊" in field.name:
                            embed.set_field_at(i, name=field.name, value=result_text, inline=field.inline)
                            result_field_found = True
                            break
                    
                    if not result_field_found:
                        embed.add_field(name="📊 Result", value=result_text, inline=False)
                        
                except (json.JSONDecodeError, KeyError):
                    pass
            elif match_details[11] and match_details[10] == 'completed':
                # Result eingereicht, aber noch nicht bestätigt
                result_field_found = False
                for i, field in enumerate(embed.fields):
                    if "Result" in field.name or "📊" in field.name:
                        embed.set_field_at(i, name=field.name, value="||*Awaiting confirmation*||", inline=field.inline)
                        result_field_found = True
                        break
                
                if not result_field_found:
                    embed.add_field(name="📊 Result", value="||*Awaiting confirmation*||", inline=False)
        
        except Exception as e:
            logger.error(f"Error updating result field: {e}")
    
    def _format_date_display(self, date_str: str) -> str:
        """
        Formatiert Datum für Anzeige
        """
        if not date_str or date_str == 'TBA':
            return "TBA"
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%d.%m.%Y')
        except:
            return date_str