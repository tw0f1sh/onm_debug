# utils/timezone_helper.py
"""
Timezone Helper - Vereinfachte Server-Timezone Lösung
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TimezoneHelper:
    """
    Einfache Timezone-Behandlung mit Server-weiter Einstellung
    """
    
    @staticmethod
    def get_server_timezone(bot=None) -> str:
        """
        Holt die Server-Timezone aus der Config
        """
        try:
            if bot and hasattr(bot, 'config') and bot.config:
                server_config = bot.config.get('server', {})
                return server_config.get('timezone', 'UTC')
            return 'UTC'
        except Exception as e:
            logger.warning(f"Error getting server timezone: {e}")
            return 'UTC'
    
    @staticmethod
    def get_timezone_display(bot=None) -> str:
        """
        Holt die detaillierte Timezone-Anzeige
        """
        try:
            if bot and hasattr(bot, 'config') and bot.config:
                server_config = bot.config.get('server', {})
                return server_config.get('timezone_display', 'UTC')
            return 'UTC'
        except Exception as e:
            logger.warning(f"Error getting timezone display: {e}")
            return 'UTC'
    
    @staticmethod
    def get_timezone_info(bot=None) -> str:
        """
        Holt die Timezone-Info für Benutzer-Hinweise
        """
        try:
            if bot and hasattr(bot, 'config') and bot.config:
                server_config = bot.config.get('server', {})
                return server_config.get('timezone_info', 'All times are in UTC')
            return 'All times are in UTC'
        except Exception as e:
            logger.warning(f"Error getting timezone info: {e}")
            return 'All times are in UTC'
    
    @staticmethod
    def format_time_with_timezone(time_str: str, bot=None) -> str:
        """
        Formatiert eine Zeit mit Timezone-Anzeige
        
        Args:
            time_str: Zeit als String (z.B. "20:30" oder "TBA")
            bot: Bot-Instanz für Config-Zugriff
            
        Returns:
            Formatierte Zeit mit Timezone (z.B. "20:30 CET" oder "TBA")
        """
        try:
            if not time_str or time_str == 'TBA' or time_str == '*TBA*':
                return "TBA"
            
            timezone_short = TimezoneHelper.get_server_timezone(bot)
            return f"{time_str} {timezone_short}"
            
        except Exception as e:
            logger.error(f"Error formatting time with timezone: {e}")
            return time_str or "TBA"
    
    @staticmethod
    def format_time_with_full_timezone(time_str: str, bot=None) -> str:
        """
        Formatiert eine Zeit mit vollständiger Timezone-Anzeige
        
        Args:
            time_str: Zeit als String (z.B. "20:30" oder "TBA")
            bot: Bot-Instanz für Config-Zugriff
            
        Returns:
            Formatierte Zeit mit vollständiger Timezone (z.B. "20:30 CET (UTC+1)" oder "TBA")
        """
        try:
            if not time_str or time_str == 'TBA' or time_str == '*TBA*':
                return "TBA"
            
            timezone_display = TimezoneHelper.get_timezone_display(bot)
            return f"{time_str} {timezone_display}"
            
        except Exception as e:
            logger.error(f"Error formatting time with full timezone: {e}")
            return time_str or "TBA"
    
    @staticmethod
    def get_time_input_placeholder(bot=None) -> str:
        """
        Gibt einen Platzhalter-Text für Zeit-Eingaben zurück
        """
        try:
            timezone_short = TimezoneHelper.get_server_timezone(bot)
            return f"20:30 ({timezone_short})"
        except Exception as e:
            logger.error(f"Error getting time input placeholder: {e}")
            return "20:30"
    
    @staticmethod
    def get_time_input_label(bot=None) -> str:
        """
        Gibt einen Label-Text für Zeit-Eingaben zurück
        """
        try:
            timezone_display = TimezoneHelper.get_timezone_display(bot)
            return f"Match Time ({timezone_display})"
        except Exception as e:
            logger.error(f"Error getting time input label: {e}")
            return "Match Time"
    
    @staticmethod
    def validate_time_format(time_str: str) -> bool:
        """
        Validiert das Zeit-Format (HH:MM)
        """
        try:
            if not time_str or time_str.strip() == '':
                return False
            
            import re
            # Validiert HH:MM Format (00:00 - 23:59)
            pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
            return bool(re.match(pattern, time_str.strip()))
            
        except Exception as e:
            logger.error(f"Error validating time format: {e}")
            return False
    
    @staticmethod
    def get_timezone_warning_text(bot=None) -> str:
        """
        Gibt einen Warntext für Timezone-Bewusstsein zurück
        """
        try:
            timezone_info = TimezoneHelper.get_timezone_info(bot)
            return f"⏰ **{timezone_info}**"
        except Exception as e:
            logger.error(f"Error getting timezone warning text: {e}")
            return "⏰ **Please check server timezone settings**"