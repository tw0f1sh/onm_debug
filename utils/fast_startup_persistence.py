"""
Fast Startup Persistence
Speichere als: utils/fast_startup_persistence.py
"""

import discord
import logging
import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class FastStartupPersistence:
    
    
    def __init__(self, bot):
        self.bot = bot
        self.restored_views = {}
        
    async def fast_restore_all_components(self) -> Dict[str, int]:
        
        try:
            logger.info("🚀 Starting FAST startup restoration (NO EDITS)...")
            
            
            await self._quick_cleanup_invalid_data()
            
            persistent_data = self.bot.db.get_all_persistent_messages()
            
            stats = {
                'total': len(persistent_data),
                'restored': 0,
                'failed': 0,
                'by_type': {},
                'skipped': 0
            }
            
            logger.info(f"📊 Processing {len(persistent_data)} messages WITHOUT edits...")
            
            
            batch_size = 50
            for i in range(0, len(persistent_data), batch_size):
                batch = persistent_data[i:i + batch_size]
                
                
                for message_data in batch:
                    try:
                        success = await self._fast_restore_component_no_edit(message_data)
                        
                        message_type = message_data.get('message_type', 'unknown')
                        if message_type not in stats['by_type']:
                            stats['by_type'][message_type] = {'restored': 0, 'failed': 0}
                        
                        if success:
                            stats['restored'] += 1
                            stats['by_type'][message_type]['restored'] += 1
                        else:
                            stats['failed'] += 1
                            stats['by_type'][message_type]['failed'] += 1
                            
                    except Exception as e:
                        logger.error(f"❌ Error restoring {message_data.get('message_type')}: {e}")
                        stats['failed'] += 1
                
                
                await asyncio.sleep(0.1)
                
                
                progress = ((i + batch_size) * 100) // len(persistent_data)
                if i % (batch_size * 4) == 0:  
                    logger.info(f"📈 Progress: {progress}% ({stats['restored']} restored)")
            
            logger.info(f"✅ FAST restoration complete: {stats['restored']} restored, {stats['failed']} failed in ~{len(persistent_data)/50:.1f} seconds")
            return stats
            
        except Exception as e:
            logger.error(f"Error in FAST restoration: {e}")
            return {'total': 0, 'restored': 0, 'failed': 0}
    
    async def _fast_restore_component_no_edit(self, message_data: Dict[str, Any]) -> bool:
        
        try:
            message_type = message_data.get('message_type')
            message_id = message_data.get('message_id')
            
            if not message_type or not message_id:
                logger.warning(f"❌ Missing data: type={message_type}, id={message_id}")  # HINZUFÜGEN
                return False
            
            button_states = self.bot.db.get_button_states(message_id)
            
            view = await self._create_view_fast_no_validation(message_type, message_data, button_states)
            
            #debuggin für: utils.fast_startup_persistence - INFO - ✅ FAST restoration complete: 29 restored, 198 failed in ~4.5 seconds
            #logger.warning(f"🔍 DEBUG: type={message_type}, view={type(view)}, view_value={view}")
            
            if view == "SUCCESS":
                return True
            if not view:
                return False
            
            self.bot.add_view(view)
                   
            self.restored_views[message_id] = {
                'view': view,
                'message_type': message_type,
                'data': message_data
            }
            
            return True
            
        except Exception as e:
            logger.debug(f"Error in fast restore (no edit): {e}")
            logger.warning(f"❌ Failed restore: {message_data.get('message_type')} ID:{message_data.get('message_id')} - {e}")  # HINZUFÜGEN
            return False
    
    async def _create_view_fast_no_validation(self, message_type: str, message_data: Dict[str, Any], button_states: List[Dict]) -> Optional[discord.ui.View]:
        try:
            match_id = message_data.get('match_id')
            
            if message_type == 'private_match':
                return self._create_private_match_view_fast_no_validation(match_id, message_data, button_states)
            elif message_type == 'streamer_match':
                return self._create_streamer_match_view_fast_no_validation(match_id, message_data, button_states)
            elif message_type == 'orga_panel':
                return self._create_orga_panel_view_fast_no_validation(button_states)
            elif message_type == 'result_submission':
                return self._create_result_submission_view_fast_no_validation(match_id, message_data, button_states)
            elif message_type == 'orga_result_confirmation':
                return self._create_orga_result_confirmation_view_fast_no_validation(match_id, message_data, button_states)
            elif message_type == 'time_offer':
                return self._create_time_offer_view_fast_no_validation(match_id, message_data, button_states)
            elif message_type == 'server_offer':
                return self._create_server_offer_view_fast_no_validation(match_id, message_data, button_states)
            elif message_type == 'public_match':
                # Public matches haben keine Views - das ist OK
                return "SUCCESS"  # Spezial-Marker für Erfolg ohne View
            else:
                logger.warning(f"❌ Unknown message_type: {message_type}")
                return None
                
        except Exception as e:
            logger.debug(f"Error creating fast view for {message_type}: {e}")
            return None
    
    def _create_orga_result_confirmation_view_fast_no_validation(self, match_id: int, message_data: Dict[str, Any], button_states: List[Dict]) -> Optional[discord.ui.View]:
        
        try:
            ui_data = message_data.get('ui_data', {})
            result_data = ui_data.get('data', {}).get('result_data', {})
            
            if not result_data:
                return None
            
            
            stored_message_id = message_data.get('message_id')
            stored_channel_id = message_data.get('channel_id') 
            stored_guild_id = message_data.get('guild_id')
            
            
            submission_data = ui_data.get('data', {})
            if not stored_message_id:
                stored_message_id = submission_data.get('message_id')
            if not stored_channel_id:
                stored_channel_id = submission_data.get('channel_id')
            if not stored_guild_id:
                stored_guild_id = submission_data.get('guild_id')
            
            
            real_match_data = self._get_real_team_names_for_orga_view(match_id)
            
            from ui.match_interactions.orga_result_confirmation import OrgaResultConfirmationView
            
            view = OrgaResultConfirmationView(self.bot, match_id, real_match_data, result_data)
            view.timeout = None
            
            
            view.message_id = stored_message_id
            view.channel_id = stored_channel_id
            view.guild_id = stored_guild_id
            
            
            if button_states:
                for button_state in button_states:
                    button_id = button_state.get('id', '')
                    if 'orga_confirm_result' in button_id:
                        self._restore_button_state_fast(view.confirm_button, button_state, button_id)
                    elif 'orga_edit_result' in button_id:
                        self._restore_button_state_fast(view.edit_button, button_state, button_id)
            
            logger.debug(f"Orga result confirmation view restored with message_id: {stored_message_id}")
            
            return view
            
        except Exception as e:
            logger.debug(f"Error creating fast orga result confirmation view: {e}")
            return None
    
    def _create_private_match_view_fast_no_validation(self, match_id: int, message_data: Dict[str, Any], button_states: List[Dict]) -> Optional[discord.ui.View]:
        
        try:
            
            ui_data = message_data.get('ui_data', {})
            match_dict = ui_data.get('data', {})
            
            
            if not match_dict:
                match_dict = {
                    'match_id': match_id,
                    'team1_name': 'Team 1',
                    'team2_name': 'Team 2',
                    'status': 'pending'
                }
            
            from ui.match_interactions.private_match_view import PrivateMatchView
            view = PrivateMatchView(self.bot, match_id, match_dict)
            view.timeout = None
            
            
            if button_states:
                for button_state in button_states:
                    button_id = button_state.get('id', '')
                    if 'time_offer' in button_id:
                        self._restore_button_state_fast(view.time_offer_button, button_state, button_id)
                    elif 'server_offer' in button_id:
                        self._restore_button_state_fast(view.server_offer_button, button_state, button_id)
                    elif 'result_submit' in button_id:
                        self._restore_button_state_fast(view.result_submission_button, button_state, button_id)
                    elif 'orga_edit' in button_id:
                        self._restore_button_state_fast(view.orga_edit_button, button_state, button_id)
            
            return view
            
        except Exception as e:
            logger.debug(f"Error creating fast private match view: {e}")
            return None
    
    def _create_streamer_match_view_fast_no_validation(self, match_id: int, message_data: Dict[str, Any], button_states: List[Dict]) -> Optional[discord.ui.View]:
        """
        Create streamer match view with proper handling for completed matches
        """
        try:
            # Get match status to determine correct view type
            match_details = self.bot.db.get_match_details(match_id)
            if match_details:
                match_status = match_details[10] if len(match_details) > 10 else 'pending'
                
                # If match is completed/confirmed, return disabled view
                if match_status in ['completed', 'confirmed']:
                    from ui.match_interactions.orga_result_confirmation import StreamerMatchViewDisabled
                    return StreamerMatchViewDisabled()
            
            # Get UI data for match info
            ui_data = message_data.get('ui_data', {})
            match_dict = ui_data.get('data', {})
            
            # Fallback match data if not available
            if not match_dict:
                match_dict = {
                    'match_id': match_id,
                    'team1_name': 'Team 1',
                    'team2_name': 'Team 2',
                    'status': match_status if match_details else 'pending'
                }
            else:
                # Ensure status is current
                match_dict['status'] = match_status if match_details else match_dict.get('status', 'pending')
            
            from ui.streamer_management.streamer_match_view import StreamerMatchView
            view = StreamerMatchView(match_id, self.bot, match_dict)
            view.timeout = None
            view._restored_from_persistence = True
            
            # Apply button states from persistence
            if button_states:
                # Check if we have a completed button state
                completed_button_found = False
                for button_state in button_states:
                    button_id = button_state.get('id', '')
                    if 'match_completed' in button_id:
                        completed_button_found = True
                        break
                
                if completed_button_found:
                    # Replace view with disabled view for completed matches
                    from ui.match_interactions.orga_result_confirmation import StreamerMatchViewDisabled
                    disabled_view = StreamerMatchViewDisabled()
                    
                    # Apply the completed button state
                    for button_state in button_states:
                        if 'match_completed' in button_state.get('id', ''):
                            for item in disabled_view.children:
                                if hasattr(item, 'custom_id'):
                                    self._restore_button_state_fast(item, button_state, button_state['id'])
                                    break
                    
                    return disabled_view
                else:
                    # Normal button state restoration
                    for button_state in button_states:
                        button_id = button_state.get('id', '')
                        if 'register_streamer' in button_id and 'unregister' not in button_id:
                            self._restore_button_state_fast(view.register_button, button_state, button_id)
                        elif 'unregister_streamer' in button_id:
                            self._restore_button_state_fast(view.unregister_button, button_state, button_id)
            
            return view
        
        except Exception as e:
            logger.debug(f"Error creating fast streamer match view: {e}")
            return None
    
    def _create_orga_panel_view_fast_no_validation(self, button_states: List[Dict]) -> Optional[discord.ui.View]:
        
        try:
            from ui.orga_panel import OrgaControlPanel
            view = OrgaControlPanel(self.bot)
            view.timeout = None
            
            
            if button_states:
                for button_state in button_states:
                    button_id = button_state.get('id', '')
                    if 'orga_create_match' in button_id:
                        self._restore_button_state_fast(view.create_match, button_state, button_id)
                    elif 'orga_refresh_panel' in button_id:
                        self._restore_button_state_fast(view.refresh_panel, button_state, button_id)
            
            return view
            
        except Exception as e:
            logger.debug(f"Error creating fast orga panel view: {e}")
            return None
    
    def _create_result_submission_view_fast_no_validation(self, match_id: int, message_data: Dict[str, Any], button_states: List[Dict]) -> Optional[discord.ui.View]:
        
        try:
            ui_data = message_data.get('ui_data', {})
            submission_data = ui_data.get('data', {})
            result_data = submission_data.get('result_data', {})
            
            if not result_data:
                logger.debug(f"No result data found for result submission {match_id}")
                return None
            
            
            stored_message_id = message_data.get('message_id')
            stored_channel_id = message_data.get('channel_id')
            stored_guild_id = message_data.get('guild_id')
            
            
            if not stored_message_id:
                stored_message_id = submission_data.get('message_id')
            if not stored_channel_id:
                stored_channel_id = submission_data.get('channel_id')
            if not stored_guild_id:
                stored_guild_id = submission_data.get('guild_id')
            
            
            submitting_team = submission_data.get('submitting_team', 'Team1')
            responding_team = submission_data.get('responding_team', 'Team2')
            responding_team_role_id = submission_data.get('responding_team_role_id', 0)
            
            
            match_dict = submission_data.get('match_data', {
                'match_id': match_id,
                'team1_name': 'Team 1',
                'team2_name': 'Team 2'
            })
            
            from ui.match_interactions.result_submission_system import ResultSubmissionView
            
            view = ResultSubmissionView(
                self.bot, match_id, match_dict, result_data,
                submitting_team, responding_team, responding_team_role_id
            )
            view.timeout = None
            
            
            view.message_id = stored_message_id
            view.channel_id = stored_channel_id
            view.guild_id = stored_guild_id
            
            
            if button_states:
                for button_state in button_states:
                    button_id = button_state.get('id', '')
                    if 'confirm_result' in button_id:
                        self._restore_button_state_fast(view.confirm_button, button_state, button_id)
                    elif 'dispute_result' in button_id:
                        self._restore_button_state_fast(view.dispute_button, button_state, button_id)
            
            logger.debug(f"Result submission view restored with message_id: {stored_message_id}")
            
            return view
            
        except Exception as e:
            logger.debug(f"Error creating fast result submission view: {e}")
            return None
    
    def _get_real_team_names_for_orga_view(self, match_id: int) -> Dict[str, Any]:
        
        try:
            
            match_details = self.bot.db.get_match_details(match_id)
            if not match_details:
                return {
                    'match_id': match_id,
                    'team1_name': 'Team 1',
                    'team2_name': 'Team 2',
                    'status': 'pending'
                }
            
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
                    logger.debug(f"Could not get team names from config: {config_error}")
            
            return {
                'match_id': match_id,
                'team1_name': team1_name,
                'team2_name': team2_name,
                'status': match_details[10] if len(match_details) > 10 else 'pending'
            }
            
        except Exception as e:
            logger.error(f"Error getting real team names for orga view: {e}")
            return {
                'match_id': match_id,
                'team1_name': 'Team 1',
                'team2_name': 'Team 2',
                'status': 'pending'
            }
    
    def _create_time_offer_view_fast_no_validation(self, match_id: int, message_data: Dict[str, Any], button_states: List[Dict]) -> Optional[discord.ui.View]:
        
        try:
            ui_data = message_data.get('ui_data', {})
            offer_data = ui_data.get('data', {})
            
            if not offer_data:
                return None
            
            
            offered_time = offer_data.get('offered_time', '20:00')
            offering_team = offer_data.get('offering_team', 'Team1')
            responding_team = offer_data.get('responding_team', 'Team2')
            responding_team_role_id = offer_data.get('responding_team_role_id', 0)
            match_data = offer_data.get('match_data', {})
            
            
            stored_message_id = offer_data.get('message_id')
            stored_channel_id = offer_data.get('channel_id')
            stored_guild_id = offer_data.get('guild_id')
            
            
            if not match_data:
                match_data = {
                    'match_id': match_id,
                    'team1_name': 'Team 1',
                    'team2_name': 'Team 2',
                    'status': 'pending'
                }
            
            from ui.match_interactions.time_offer_system import TimeOfferView
            
            view = TimeOfferView(
                self.bot, match_id, match_data, offered_time,
                offering_team, responding_team, responding_team_role_id
            )
            view.timeout = None
            
            
            view.message_id = stored_message_id
            view.channel_id = stored_channel_id
            view.guild_id = stored_guild_id
            
            
            if button_states:
                for button_state in button_states:
                    button_id = button_state.get('id', '')
                    if 'time_accept' in button_id:
                        self._restore_button_state_fast(view.accept_button, button_state, button_id)
                    elif 'time_counter' in button_id:
                        self._restore_button_state_fast(view.counter_button, button_state, button_id)
            
            logger.debug(f"Time offer view restored with message_id: {stored_message_id}")
            
            return view
            
        except Exception as e:
            logger.debug(f"Error creating fast time offer view: {e}")
            return None
    
    def _create_server_offer_view_fast_no_validation(self, match_id: int, message_data: Dict[str, Any], button_states: List[Dict]) -> Optional[discord.ui.View]:
        
        try:
            ui_data = message_data.get('ui_data', {})
            offer_data = ui_data.get('data', {})
            
            if not offer_data:
                return None
            
            
            server_name = offer_data.get('server_name', 'Server')
            server_password = offer_data.get('server_password', 'password')
            offering_team = offer_data.get('offering_team', 'Team1')
            responding_team = offer_data.get('responding_team', 'Team2')
            responding_team_role_id = offer_data.get('responding_team_role_id', 0)
            match_data = offer_data.get('match_data', {})
            
            
            stored_message_id = offer_data.get('message_id')
            stored_channel_id = offer_data.get('channel_id')
            stored_guild_id = offer_data.get('guild_id')
            
            
            if not match_data:
                match_data = {
                    'match_id': match_id,
                    'team1_name': 'Team 1',
                    'team2_name': 'Team 2',
                    'status': 'pending'
                }
            
            from ui.match_interactions.server_offer_system import ServerOfferView
            
            view = ServerOfferView(
                self.bot, match_id, match_data, server_name, server_password,
                offering_team, responding_team, responding_team_role_id
            )
            view.timeout = None
            
            
            view.message_id = stored_message_id
            view.channel_id = stored_channel_id
            view.guild_id = stored_guild_id
            
            
            if button_states:
                for button_state in button_states:
                    button_id = button_state.get('id', '')
                    if 'server_accept' in button_id:
                        self._restore_button_state_fast(view.accept_button, button_state, button_id)
                    elif 'server_counter' in button_id:
                        self._restore_button_state_fast(view.counter_button, button_state, button_id)
            
            logger.debug(f"Server offer view restored with message_id: {stored_message_id}")
            
            return view
            
        except Exception as e:
            logger.debug(f"Error creating fast server offer view: {e}")
            return None
    
    def _restore_button_state_fast(self, button, button_state: Dict, button_id: str):
        
        try:
            button.custom_id = button_id
            if 'disabled' in button_state:
                button.disabled = button_state['disabled']
            if 'label' in button_state and button_state['label']:
                button.label = button_state['label']
            if 'style' in button_state and button_state['style'] in ['primary', 'secondary', 'success', 'danger']:
                style_map = {
                    'primary': discord.ButtonStyle.primary,
                    'secondary': discord.ButtonStyle.secondary,
                    'success': discord.ButtonStyle.success,
                    'danger': discord.ButtonStyle.danger
                }
                button.style = style_map[button_state['style']]
        except:
            
            try:
                button.custom_id = button_id
            except:
                pass
    
    async def _quick_cleanup_invalid_data(self):
        
        try:
            cursor = self.bot.db.conn.cursor()
            
            
            thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
            cursor.execute('''
                UPDATE ui_messages 
                SET is_active = 0 
                WHERE created_at < ? AND is_active = 1
            ''', (thirty_days_ago,))
            
            cleaned = cursor.rowcount
            self.bot.db.conn.commit()
            
            if cleaned > 0:
                logger.info(f"🗑️ Quick cleanup: {cleaned} old messages removed")
            
        except Exception as e:
            logger.error(f"Error in quick cleanup: {e}")
    
    def get_restoration_stats(self) -> Dict[str, Any]:
        
        return {
            'active_views': len(self.restored_views),
            'startup_method': 'FAST_NO_EDITS'
        }