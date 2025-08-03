"""
Wheel Config Loader
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

class WheelConfigLoader:
    
    
    @staticmethod
    def load_maps() -> list:
        
        try:
            
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'map_config.json')
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            maps_data = config.get('maps', [])
            if not maps_data:
                logger.warning("No maps found in map_config.json")
                return ["de_dust2", "de_mirage", "de_inferno"]  
            
            
            maps = [map_data['name'] for map_data in maps_data if 'name' in map_data]
            
            if not maps:
                logger.warning("No valid map names found in map_config.json")
                return ["de_dust2", "de_mirage", "de_inferno"]  
                
            logger.info(f"Loaded {len(maps)} maps from map_config.json")
            return maps
            
        except FileNotFoundError:
            logger.error("map_config.json not found in main directory")
            return ["de_dust2", "de_mirage", "de_inferno"]  
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing map_config.json: {e}")
            return ["de_dust2", "de_mirage", "de_inferno"]  
        except Exception as e:
            logger.error(f"Error loading maps: {e}")
            return ["de_dust2", "de_mirage", "de_inferno"]  
    
    @staticmethod
    def load_team_sides(map_name: str = None) -> dict:
        
        try:
            
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'map_config.json')
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            maps_data = config.get('maps', [])
            
            if map_name:
                
                for map_data in maps_data:
                    if map_data['name'] == map_name:
                        teams = map_data.get('teams', ['US', 'GER'])
                        logger.info(f"Found teams for {map_name}: {teams}")
                        return {
                            'team1_options': teams,
                            'team2_options': teams
                        }
                
                
                logger.warning(f"Map {map_name} not found, using default teams")
                return {
                    'team1_options': ['US', 'GER'],
                    'team2_options': ['US', 'GER']
                }
            else:
                
                return {
                    'team1_options': ['CT', 'T'],
                    'team2_options': ['CT', 'T']
                }
                
        except FileNotFoundError:
            logger.error("map_config.json not found")
            return {
                'team1_options': ['CT', 'T'],
                'team2_options': ['CT', 'T']
            }
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing map_config.json: {e}")
            return {
                'team1_options': ['CT', 'T'],
                'team2_options': ['CT', 'T']
            }
        except Exception as e:
            logger.error(f"Error loading team sides: {e}")
            return {
                'team1_options': ['CT', 'T'],
                'team2_options': ['CT', 'T']
            }