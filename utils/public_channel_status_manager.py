# utils/public_channel_status_manager.py
"""
Public Match Channel Status Manager - FIXED: Emoji-Erhaltung beim Status-Update
"""

import discord
import logging
from typing import Optional
import re

logger = logging.getLogger(__name__)

class PublicChannelStatusManager:
    
    STATUS_ICONS = {
        'created': '📝',           # :pencil: - Neu erstellt
        'scheduled': '⏳',         # :hourglass_flowing_sand: - Zeit vereinbart
        'completed': '✅'          # :white_check_mark: - Archiviert
    }
    
    def __init__(self, bot):
        self.bot = bot
    
    def _sanitize_channel_name_with_emojis(self, name: str) -> str:
        """
        Bereinigt Channel Namen für Discord - Behält Emojis bei (FIXED)
        """
        try:
            # Status-Icons explizit erhalten
            status_icons = ['📝', '⏳', '✅']
            leading_status_icon = ""
            
            # Prüfen ob der Name mit einem Status-Icon beginnt
            for icon in status_icons:
                if name.startswith(icon):
                    leading_status_icon = icon
                    name_without_icon = name[len(icon):]
                    break
            else:
                name_without_icon = name
            
            logger.debug(f"🔍 Sanitization debug: leading_icon='{leading_status_icon}', name_without='{name_without_icon}'")
            
            # Emojis aus dem Rest extrahieren und temporär ersetzen
            emoji_placeholders = {}
            emoji_counter = 0
            
            # Erweiterte Unicode Emoji Bereiche
            emoji_pattern = re.compile(
                "["
                "\U0001F600-\U0001F64F"  # emoticons
                "\U0001F300-\U0001F5FF"  # symbols & pictographs
                "\U0001F680-\U0001F6FF"  # transport & map symbols
                "\U0001F1E0-\U0001F1FF"  # flags (iOS)
                "\U00002702-\U000027B0"  # dingbats
                "\U000024C2-\U0001F251"  # enclosed characters
                "\U00002600-\U000026FF"  # miscellaneous symbols
                "\U0000FE0F"             # variation selector
                "]+",
                flags=re.UNICODE
            )
            
            def replace_emoji(match):
                nonlocal emoji_counter
                emoji = match.group(0)
                placeholder = f"__EMOJI_{emoji_counter}__"
                emoji_placeholders[placeholder] = emoji
                emoji_counter += 1
                return placeholder
            
            # Emojis im Namen (ohne führendes Status-Icon) durch Platzhalter ersetzen
            temp_name = emoji_pattern.sub(replace_emoji, name_without_icon)
            
            # Nur erlaubte Zeichen: a-z, 0-9, - und _ (plus unsere Emoji-Platzhalter)
            sanitized = re.sub(r'[^a-z0-9\-_]', '-', temp_name.lower())
            
            # Mehrfache Bindestriche entfernen
            sanitized = re.sub(r'-+', '-', sanitized)
            
            # Bindestriche am Anfang/Ende entfernen
            sanitized = sanitized.strip('-')
            
            # Emojis wieder einsetzen (case-insensitive)
            for placeholder, emoji in emoji_placeholders.items():
                sanitized = sanitized.replace(placeholder.lower(), emoji)
            
            # Status-Icon wieder hinzufügen
            if leading_status_icon:
                final_name = f"{leading_status_icon}-{sanitized}" if sanitized else leading_status_icon
            else:
                final_name = sanitized
            
            # Maximale Länge 100 Zeichen
            result = final_name[:100]
            
            logger.debug(f"🔍 Sanitization result: '{name}' -> '{result}'")
            return result
            
        except Exception as e:
            logger.error(f"Error in emoji-safe sanitization: {e}")
            return name[:100]  # Fallback
    
    async def update_channel_status(self, match_id: int, new_status: str) -> bool:
        """
        Aktualisiert den Status-Icon im Public Match Channel Namen
        """
        try:
            # Channel für dieses Match finden
            channel = await self._find_public_match_channel(match_id)
            if not channel:
                logger.warning(f"No public match channel found for match {match_id}")
                return False
            
            # FIXED: Neuen Channel Namen erstellen ohne Sanitization zu früh
            new_name = await self._create_channel_name_with_status_fixed(match_id, new_status, channel.name)
            if not new_name:
                logger.error(f"Could not create new channel name for match {match_id}")
                return False
            
            # Nur umbenennen wenn der Name sich ändert
            if channel.name == new_name:
                logger.info(f"Channel name already correct for match {match_id}")
                return True
            
            # DEBUG: Namen vor und nach dem Update loggen
            logger.info(f"🔄 Renaming channel: '{channel.name}' -> '{new_name}'")
            
            # Channel umbenennen
            await channel.edit(name=new_name, reason=f"Status update to {new_status}")
            
            logger.info(f"✅ Updated channel status for match {match_id}: {new_status} -> {new_name}")
            return True
            
        except discord.Forbidden:
            logger.error(f"❌ No permission to rename channel for match {match_id}")
            return False
        except discord.HTTPException as e:
            logger.error(f"❌ Discord error renaming channel for match {match_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error updating channel status for match {match_id}: {e}")
            return False
    
    async def _find_public_match_channel(self, match_id: int) -> Optional[discord.TextChannel]:
        """
        Findet den Public Match Channel für eine Match ID
        """
        try:
            # Channel ID aus Datenbank holen
            stored_channel_id = self.bot.db.get_setting(f'public_match_{match_id}_channel_id')
            if not stored_channel_id:
                return None
            
            # Channel finden
            for guild in self.bot.guilds:
                channel = guild.get_channel(int(stored_channel_id))
                if channel:
                    return channel
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding public match channel for {match_id}: {e}")
            return None
    
    async def _create_channel_name_with_status_fixed(self, match_id: int, status: str, current_name: str) -> Optional[str]:
        """
        FIXED: Erstellt einen neuen Channel Namen mit dem entsprechenden Status-Icon
        """
        try:
            # Status-Icon holen
            status_icon = self.STATUS_ICONS.get(status, '📝')
            
            # Aktuelles Icon entfernen (falls vorhanden)
            cleaned_name = current_name
            for icon in self.STATUS_ICONS.values():
                if cleaned_name.startswith(icon + '-'):
                    cleaned_name = cleaned_name[len(icon + '-'):]
                    break
            
            # Neuen Namen mit Status-Icon erstellen
            new_name = f"{status_icon}-{cleaned_name}"
            
            # FIXED: Sanitization nur einmal am Ende ausführen
            final_name = self._sanitize_channel_name_with_emojis(new_name)
            
            logger.info(f"🔧 Channel name creation: '{current_name}' -> '{cleaned_name}' -> '{new_name}' -> '{final_name}'")
            
            return final_name
            
        except Exception as e:
            logger.error(f"Error creating channel name with status: {e}")
            return None
    
    async def _create_channel_name_with_status(self, match_id: int, status: str) -> Optional[str]:
        """
        LEGACY: Erstellt einen neuen Channel Namen mit dem entsprechenden Status-Icon
        Diese Methode wird nicht mehr verwendet - siehe _create_channel_name_with_status_fixed
        """
        try:
            # Match Details holen
            match_details = self.bot.db.get_match_details(match_id)
            if not match_details:
                return None
            
            # Team Namen extrahieren
            team1_name, team2_name = self._get_team_names_from_match(match_details)
            
            # Week und Prefix holen
            week = match_details[13] if len(match_details) > 13 else 1
            
            # Originalen Prefix aus Channel Namen extrahieren (falls vorhanden)
            current_channel = await self._find_public_match_channel(match_id)
            original_prefix = ""
            
            if current_channel:
                original_prefix = self._extract_original_prefix(current_channel.name, week, team1_name, team2_name)
            
            # Status-Icon holen
            status_icon = self.STATUS_ICONS.get(status, '📝')
            
            # Neuen Namen erstellen
            if original_prefix:
                # Format: 📝-prefix-w1-team1-vs-team2
                channel_name = f"{status_icon}-{original_prefix}-w{week}-{team1_name.lower()}-vs-{team2_name.lower()}"
            else:
                # Format: 📝-w1-team1-vs-team2
                channel_name = f"{status_icon}-w{week}-{team1_name.lower()}-vs-{team2_name.lower()}"
            
            # Channel Namen für Discord bereinigen (mit Emoji-Erhaltung)
            channel_name = self._sanitize_channel_name_with_emojis(channel_name)
            
            return channel_name
            
        except Exception as e:
            logger.error(f"Error creating channel name with status: {e}")
            return None
    
    def _extract_original_prefix(self, current_name: str, week: int, team1_name: str, team2_name: str) -> str:
        """
        Extrahiert den originalen Prefix aus dem aktuellen Channel Namen
        """
        try:
            # Status-Icon entfernen (falls vorhanden)
            for icon in self.STATUS_ICONS.values():
                if current_name.startswith(icon + '-'):
                    current_name = current_name[len(icon + '-'):]
                    break
            
            # Expected suffix erstellen
            expected_suffix = f"w{week}-{team1_name.lower()}-vs-{team2_name.lower()}"
            expected_suffix = self._sanitize_channel_name_with_emojis(expected_suffix)
            
            # Wenn der Name mit dem erwarteten Suffix endet, extrahiere Prefix
            if current_name.endswith(expected_suffix):
                prefix_part = current_name[:-len(expected_suffix)]
                # Trailing dash entfernen
                if prefix_part.endswith('-'):
                    prefix_part = prefix_part[:-1]
                return prefix_part
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting original prefix: {e}")
            return ""
    
    def _get_team_names_from_match(self, match_details: tuple) -> tuple:
        """
        Holt die echten Team Namen aus den Match Details
        """
        try:
            team1_id = match_details[1]
            team2_id = match_details[2]
            
            # Standard Namen aus DB
            team1_name = "team1"
            team2_name = "team2"
            
            # Aus Match Details wenn verfügbar
            if len(match_details) > 16:
                team1_name = match_details[16] or f"team{team1_id}"
            if len(match_details) > 17:
                team2_name = match_details[17] or f"team{team2_id}"
            
            # Aus Config wenn noch generisch
            if team1_name.startswith("team") or team2_name.startswith("team"):
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
            
            return team1_name, team2_name
            
        except Exception as e:
            logger.error(f"Error getting team names from match: {e}")
            return "team1", "team2"
    
    async def get_current_status_from_match(self, match_id: int) -> str:
        """
        Bestimmt den aktuellen Status basierend auf Match-Daten
        """
        try:
            match_details = self.bot.db.get_match_details(match_id)
            if not match_details:
                return 'created'
            
            # Status basierend auf Match-Zustand
            match_status = match_details[10] if len(match_details) > 10 else 'pending'
            match_time = match_details[4] if len(match_details) > 4 else None
            
            if match_status == 'confirmed':
                return 'completed'
            elif match_time and match_time != 'TBA':
                return 'scheduled'
            else:
                return 'created'
                
        except Exception as e:
            logger.error(f"Error getting current status for match {match_id}: {e}")
            return 'created'