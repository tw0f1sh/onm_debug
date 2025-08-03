"""
Match Wheel Service
"""

import discord
import logging
from typing import Tuple, Dict, Any
from .config_loader import WheelConfigLoader
from .random_service import RandomService
from .wheel_generator import WheelGenerator

logger = logging.getLogger(__name__)

class MatchWheelService:
    
    
    @staticmethod
    async def select_map_and_sides(team1_name: str, team2_name: str) -> Tuple[str, str, str, Dict[str, Any], Dict[str, Any]]:
        
        logger.info(f"🎲 Starting wheel selection for {team1_name} vs {team2_name}")
        
        
        available_maps = WheelConfigLoader.load_maps()
        selected_map = await RandomService.get_true_random_choice(available_maps)
        
        logger.info(f"🗺️ Selected map: {selected_map}")
        
        
        team_sides_config = WheelConfigLoader.load_team_sides(selected_map)
        available_sides = team_sides_config['team1_options']  
        
        
        team1_side = await RandomService.get_true_random_choice(available_sides)
        
        
        if len(available_sides) == 2:
            team2_side = available_sides[1] if team1_side == available_sides[0] else available_sides[0]
        else:
            
            remaining_sides = [side for side in available_sides if side != team1_side]
            team2_side = await RandomService.get_true_random_choice(remaining_sides)
        
        logger.info(f"🔴 Team sides: {team1_name}={team1_side}, {team2_name}={team2_side}")
        
        
        map_wheel_data = {
            'type': 'map',
            'options': available_maps,
            'selected': selected_map,
            'title': 'Map Selection'
        }
        
        sides_wheel_data = {
            'type': 'sides',
            'options': available_sides,
            'selected': team1_side,
            'title': f'Team Side for {team1_name}',
            'team1_name': team1_name,
            'team2_name': team2_name,
            'team2_side': team2_side
        }
        
        return selected_map, team1_side, team2_side, map_wheel_data, sides_wheel_data
    
    @staticmethod
    async def create_map_wheel_gif(wheel_data: Dict[str, Any]) -> discord.File:
        
        try:
            logger.info(f"🎨 Creating map wheel GIF for: {wheel_data['selected']}")
            
            gif_buffer = await WheelGenerator.create_spinning_wheel_gif(
                wheel_data['options'], 
                wheel_data['selected']
            )
            
            return discord.File(gif_buffer, filename='map_selection.gif')
            
        except Exception as e:
            logger.error(f"Error creating map wheel GIF: {e}")
            raise
    
    @staticmethod
    async def create_sides_wheel_gif(wheel_data: Dict[str, Any]) -> discord.File:
        
        try:
            logger.info(f"🎨 Creating sides wheel GIF for: {wheel_data['selected']}")
            
            gif_buffer = await WheelGenerator.create_spinning_wheel_gif(
                wheel_data['options'], 
                wheel_data['selected']
            )
            
            return discord.File(gif_buffer, filename='sides_selection.gif')
            
        except Exception as e:
            logger.error(f"Error creating sides wheel GIF: {e}")
            raise
    
    @staticmethod
    def create_map_selection_embed(wheel_data: Dict[str, Any]) -> discord.Embed:
        
        embed = discord.Embed(
            title="🗺️ Map Selection",
            color=0x00FF00
        )
        embed.set_image(url="attachment://map_selection.gif")
        embed.set_footer(text="Powered by random.org • True randomness guaranteed")
        
        return embed
    
    @staticmethod
    def create_sides_selection_embed(wheel_data: Dict[str, Any]) -> discord.Embed:
        
        embed = discord.Embed(
            title=f"🔴 Team Selection for {wheel_data['team1_name']}",
            color=0xFF0000
        )
        embed.set_image(url="attachment://sides_selection.gif")
        embed.set_footer(text="Powered by random.org • True randomness guaranteed")
        
        return embed