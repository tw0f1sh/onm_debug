"""
Team Config Loader
"""

import logging
from typing import List, Tuple, Optional, Dict

logger = logging.getLogger(__name__)

class TeamConfigLoader:
    
    
    def __init__(self, bot):
        self.bot = bot
        self._teams_cache = None
    
    def get_all_teams(self) -> List[Tuple]:
        
        try:
            if not hasattr(self.bot, 'config') or not self.bot.config:
                logger.error("Bot config not available")
                return []
            
            teams_config = self.bot.config.get('teams', {})
            if not teams_config:
                logger.warning("No teams section found in config.json")
                return []
            
            teams_list = []
            team_id = 1  
            
            for team_key, team_data in teams_config.items():
                if not isinstance(team_data, dict):
                    logger.warning(f"Invalid team data for {team_key}")
                    continue
                
                
                display_name = team_data.get('display_name', team_key)
                role_id = team_data.get('role_id')
                active = team_data.get('active', True)
                
                if not role_id:
                    logger.warning(f"No role_id specified for team {team_key}")
                    continue
                
                
                
                team_tuple = (
                    team_id,           
                    display_name,      
                    role_id,          
                    "[]",             
                    active            
                )
                
                teams_list.append(team_tuple)
                team_id += 1
            
            logger.debug(f"Loaded {len(teams_list)} teams from config.json")
            return teams_list
            
        except Exception as e:
            logger.error(f"Error loading teams from config: {e}")
            return []
    
    def get_active_teams(self) -> List[Tuple]:
        
        all_teams = self.get_all_teams()
        return [team for team in all_teams if team[4]]  
    
    def get_team_by_role_id(self, role_id: int) -> Optional[Tuple]:
        
        all_teams = self.get_all_teams()
        for team in all_teams:
            if team[2] == role_id:  
                return team
        return None
    
    def get_team_by_name(self, name: str) -> Optional[Tuple]:
        
        all_teams = self.get_all_teams()
        for team in all_teams:
            if team[1].lower() == name.lower():  
                return team
        return None
    
    def team_exists(self, name: str) -> bool:
        
        return self.get_team_by_name(name) is not None
    
    def validate_teams_config(self) -> Dict[str, List[str]]:
        
        result = {'valid': [], 'invalid': [], 'warnings': []}
        
        try:
            teams_config = self.bot.config.get('teams', {})
            
            for team_key, team_data in teams_config.items():
                if not isinstance(team_data, dict):
                    result['invalid'].append(f"{team_key}: Invalid configuration format")
                    continue
                
                
                if 'role_id' not in team_data:
                    result['invalid'].append(f"{team_key}: Missing role_id")
                    continue
                
                
                role_id = team_data['role_id']
                for guild in self.bot.guilds:
                    role = guild.get_role(role_id)
                    if role:
                        result['valid'].append(team_key)
                        break
                else:
                    result['warnings'].append(f"{team_key}: Role ID {role_id} not found on any server")
                    result['valid'].append(team_key)  
            
            return result
            
        except Exception as e:
            logger.error(f"Error validating teams config: {e}")
            result['invalid'].append(f"Configuration error: {e}")
            return result
   
    def get_team_statistics(self) -> Dict[str, int]:
        
        try:
            all_teams = self.get_all_teams()
            active_teams = self.get_active_teams()
            
            return {
                'total_teams': len(all_teams),
                'active_teams': len(active_teams),
                'inactive_teams': len(all_teams) - len(active_teams)
            }
            
        except Exception as e:
            logger.error(f"Error getting team statistics: {e}")
            return {'total_teams': 0, 'active_teams': 0, 'inactive_teams': 0}