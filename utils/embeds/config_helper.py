"""
Config Helper
"""

import logging

logger = logging.getLogger(__name__)

class ConfigHelper:
    
    @staticmethod
    def get_rules_url(bot=None) -> str:
        try:
            if bot and hasattr(bot, 'config') and bot.config:
                return bot.config.get('rules', {}).get('onm_url', '#')
            return '#'
        except Exception as e:
            logger.warning(f"Fehler beim Laden der Rules URL: {e}")
            return '#'
    
    @staticmethod
    def get_team_icon(team_side: str, bot=None) -> str:
        try:
            if bot and hasattr(bot, 'config') and bot.config:
                team_icons = bot.config.get('team_icons', {})
                icon = team_icons.get(team_side.upper(), '')
                if icon:
                    logger.debug(f"Team Icon für {team_side}: {icon}")
                    return icon
            
            logger.debug(f"Kein Icon für Team {team_side} gefunden")
            return ''
        except Exception as e:
            logger.warning(f"Fehler beim Laden des Team Icons für {team_side}: {e}")
            return ''
            
    @staticmethod
    def format_team_side_with_icon(team_side: str, bot=None) -> str:
        icon = ConfigHelper.get_team_icon(team_side, bot)
        if icon:
            return f"{team_side} {icon}"
        return team_side
    
    @staticmethod
    def format_date_to_display(date_str: str) -> str:
        if not date_str:
            return "TBA"
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%d.%m.%Y')
        except:
            return date_str
    
    @staticmethod
    def get_status_emoji(status: str) -> str:
        status_emojis = {
            "pending": "⏳",
            "completed": "✅", 
            "confirmed": "🏆"
        }
        return status_emojis.get(status, '❓')
    
    @staticmethod
    def safe_get_team_names(match_data, fallback_prefix="Team") -> tuple:
        try:
            if len(match_data) >= 18:
                return match_data[16], match_data[17]
            else:
                return f"{fallback_prefix} {match_data[1]}", f"{fallback_prefix} {match_data[2]}"
        except (IndexError, TypeError):
            return "Team 1", "Team 2"