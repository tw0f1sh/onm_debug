"""
Lazy Persistence Service
"""

import discord
import logging
import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class LazyPersistenceService:
    
    
    def __init__(self, bot):
        self.bot = bot
        self.active_views = {}
        self.interaction_callbacks = {}
        
    async def update_and_disable_old_buttons(self, message_id: int, view_type: str, new_button_states: Dict = None):
        
        try:
            
            if message_id not in self.active_views:
                logger.warning(f"Message {message_id} not found in active views")
                return False
            
            view_data = self.active_views[message_id]
            view = view_data.get('view')
            
            if not view:
                logger.warning(f"No view found for message {message_id}")
                return False
            
            
            message = await self._get_message_from_id(message_id, view_data.get('data', {}))
            if not message:
                logger.warning(f"Could not retrieve Discord message {message_id}")
                return False
            
            
            if new_button_states:
                await self._apply_button_states_to_view(view, new_button_states)
            
            
            try:
                await message.edit(view=view)
                logger.info(f"✅ Updated buttons for message {message_id}")
                
                
                buttons_data = []
                for item in view.children:
                    if hasattr(item, 'custom_id') and item.custom_id:
                        buttons_data.append({
                            'id': item.custom_id,
                            'label': getattr(item, 'label', ''),
                            'disabled': getattr(item, 'disabled', False),
                            'style': getattr(item, 'style', discord.ButtonStyle.primary).name,
                            'data': {}
                        })
                
                if buttons_data:
                    self.bot.db.save_button_states(message_id, buttons_data)
                
                return True
                
            except discord.NotFound:
                logger.warning(f"Message {message_id} was deleted, removing from active views")
                self.bot.db.deactivate_ui_message(message_id)
                if message_id in self.active_views:
                    del self.active_views[message_id]
                return False
                
            except Exception as edit_error:
                logger.error(f"Error editing message {message_id}: {edit_error}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating buttons for message {message_id}: {e}")
            return False

    async def _get_message_from_id(self, message_id: int, view_data: Dict) -> Optional[discord.Message]:
        
        try:
            
            channel_id = view_data.get('channel_id')
            guild_id = view_data.get('guild_id')
            
            if not channel_id:
                
                cursor = self.bot.db.conn.cursor()
                cursor.execute('SELECT channel_id, guild_id FROM ui_messages WHERE message_id = ?', (message_id,))
                result = cursor.fetchone()
                if result:
                    channel_id, guild_id = result
            
            if not channel_id:
                return None
            
            
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return None
            
            
            message = await channel.fetch_message(message_id)
            return message
            
        except discord.NotFound:
            return None
        except Exception as e:
            logger.error(f"Error retrieving message {message_id}: {e}")
            return None

    async def _apply_button_states_to_view(self, view, button_states: Dict):
        
        try:
            for item in view.children:
                if hasattr(item, 'custom_id') and item.custom_id:
                    button_id = item.custom_id
                    
                    
                    for state_key, state_data in button_states.items():
                        if state_key in button_id or button_id.endswith(state_key):
                            if isinstance(state_data, dict):
                                if 'disabled' in state_data:
                                    item.disabled = state_data['disabled']
                                if 'label' in state_data:
                                    item.label = state_data['label']
                                if 'style' in state_data:
                                    style_map = {
                                        'primary': discord.ButtonStyle.primary,
                                        'secondary': discord.ButtonStyle.secondary,
                                        'success': discord.ButtonStyle.success,
                                        'danger': discord.ButtonStyle.danger
                                    }
                                    item.style = style_map.get(state_data['style'], item.style)
                            break
                            
        except Exception as e:
            logger.error(f"Error applying button states: {e}")

    async def disable_all_buttons_for_message(self, message_id: int, disabled_label: str = "Completed"):
        
        try:
            button_states = {
                'register_button': {'disabled': True, 'label': disabled_label, 'style': 'secondary'},
                'unregister_button': {'disabled': True, 'label': disabled_label, 'style': 'secondary'},
                'time_offer': {'disabled': True, 'label': disabled_label, 'style': 'secondary'},
                'server_offer': {'disabled': True, 'label': disabled_label, 'style': 'secondary'},
                'result_submit': {'disabled': True, 'label': disabled_label, 'style': 'secondary'},
                'confirm_result': {'disabled': True, 'label': disabled_label, 'style': 'secondary'},
                'dispute_result': {'disabled': True, 'label': disabled_label, 'style': 'secondary'}
            }
            
            return await self.update_and_disable_old_buttons(message_id, None, button_states)
            
        except Exception as e:
            logger.error(f"Error disabling all buttons for message {message_id}: {e}")
            return False
        
    async def restore_all_components(self) -> Dict[str, int]:
        
        try:
            logger.info("🔄 Starting FAST lazy UI restoration...")
            
            
            await self._cleanup_invalid_ui_messages()
            
            persistent_data = self.bot.db.get_all_persistent_messages()
            
            stats = {
                'total': len(persistent_data),
                'restored': 0,
                'failed': 0,
                'by_type': {},
                'skipped': 0
            }
            
            logger.info(f"📊 Processing {len(persistent_data)} messages with timeout...")
            
            
            for i, message_data in enumerate(persistent_data):
                try:
                    
                    if i % 5 == 0:
                        logger.info(f"📈 Progress: {i}/{len(persistent_data)} ({i*100//len(persistent_data) if len(persistent_data) > 0 else 0}%)")
                    
                    
                    success = await asyncio.wait_for(
                        self._restore_component_fast(message_data), 
                        timeout=2.0  
                    )
                    
                    message_type = message_data.get('message_type', 'unknown')
                    if message_type not in stats['by_type']:
                        stats['by_type'][message_type] = {'restored': 0, 'failed': 0, 'skipped': 0}
                    
                    if success:
                        stats['restored'] += 1
                        stats['by_type'][message_type]['restored'] += 1
                    else:
                        stats['failed'] += 1
                        stats['by_type'][message_type]['failed'] += 1
                        
                        
                        message_id = message_data.get('message_id')
                        if message_id:
                            self.bot.db.deactivate_ui_message(message_id)
                
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ Timeout restoring message {message_data.get('message_id')} - skipping")
                    stats['skipped'] += 1
                    message_type = message_data.get('message_type', 'unknown')
                    if message_type not in stats['by_type']:
                        stats['by_type'][message_type] = {'restored': 0, 'failed': 0, 'skipped': 0}
                    stats['by_type'][message_type]['skipped'] += 1
                    
                except Exception as e:
                    logger.error(f"❌ Error restoring {message_data.get('message_type')}: {e}")
                    stats['failed'] += 1
                
                
                if i % 10 == 0:
                    await asyncio.sleep(0.1)
            
            
            try:
                ongoing_stats = await asyncio.wait_for(
                    self._restore_ongoing_interactions_fast(), 
                    timeout=10.0
                )
                stats['ongoing_interactions'] = ongoing_stats
            except asyncio.TimeoutError:
                logger.warning("⏰ Timeout restoring ongoing interactions - skipping")
                stats['ongoing_interactions'] = {'total': 0, 'restored': 0, 'failed': 0}
            
            logger.info(f"✅ FAST restoration complete: {stats['restored']} restored, {stats['failed']} failed, {stats['skipped']} skipped")
            return stats
            
        except Exception as e:
            logger.error(f"Error in FAST restoration: {e}")
            return {'total': 0, 'restored': 0, 'failed': 0}
    
    async def _restore_component_fast(self, message_data: Dict[str, Any]) -> bool:
        
        try:
            message_type = message_data.get('message_type')
            message_id = message_data.get('message_id')
            
            if not message_type or not message_id:
                return False
            
            
            original_button_states = self.bot.db.get_button_states(message_id)
            
            
            view = await self._create_view_fast(message_type, message_data, original_button_states)
            if not view:
                return False
            
            
            self.active_views[message_id] = {
                'view': view,
                'message_type': message_type,
                'data': message_data
            }
            
            
            self.bot.add_view(view)
            
            return True
            
        except Exception as e:
            logger.error(f"Error in fast restore: {e}")
            return False
    
    async def _create_view_fast(self, message_type: str, message_data: Dict[str, Any], button_states: List[Dict]) -> Optional[discord.ui.View]:
        
        try:
            match_id = message_data.get('match_id')
            
            if message_type == 'private_match':
                return self._create_private_match_view_fast(match_id, message_data, button_states)
            elif message_type == 'streamer_match':
                return self._create_streamer_match_view_fast(match_id, message_data, button_states)
            elif message_type == 'orga_panel':
                return self._create_orga_panel_view_fast(button_states)
            elif message_type == 'result_submission':
                return self._create_result_submission_view_fast(match_id, message_data, button_states)
            elif message_type == 'orga_result_confirmation':  
                return self._create_orga_result_confirmation_view_fast(match_id, message_data, button_states)
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating fast view for {message_type}: {e}")
            return None
    
    def _create_orga_result_confirmation_view_fast(self, match_id: int, message_data: Dict[str, Any], button_states: List[Dict]) -> Optional[discord.ui.View]:
        
        try:
            ui_data = message_data.get('ui_data', {})
            result_data = ui_data.get('data', {}).get('result_data', {})
            
            if not result_data:
                return None
            
            match_details = self.bot.db.get_match_details(match_id)
            if not match_details:
                logger.debug(f"No match details found for orga result confirmation {match_id}")
                return None
            
            match_dict = self._create_match_data_dict(match_details)
            
            from ui.match_interactions.orga_result_confirmation import OrgaResultConfirmationView
            
            view = OrgaResultConfirmationView(self.bot, match_id, match_dict, result_data)
            view.timeout = None
            
            
            submission_data = ui_data.get('data', {})
            view.message_id = submission_data.get('message_id')
            view.channel_id = submission_data.get('channel_id')
            view.guild_id = submission_data.get('guild_id')
            
            
            if not view.message_id:
                view.message_id = message_data.get('message_id')
            if not view.channel_id:
                view.channel_id = message_data.get('channel_id')
            if not view.guild_id:
                view.guild_id = message_data.get('guild_id')
            
            
            if button_states:
                for button_state in button_states:
                    button_id = button_state.get('id', '')
                    if 'orga_confirm_result' in button_id:
                        self._restore_button_state_fast(view.confirm_button, button_state, button_id)
                    elif 'orga_edit_result' in button_id:
                        self._restore_button_state_fast(view.edit_button, button_state, button_id)
            
            logger.debug(f"Orga result confirmation view restored with message_id: {view.message_id}")
            
            return view
            
        except Exception as e:
            logger.error(f"Error creating fast orga result confirmation view: {e}")
            return None
    
    def _create_private_match_view_fast(self, match_id: int, message_data: Dict[str, Any], button_states: List[Dict]) -> Optional[discord.ui.View]:
        
        try:
            match_details = self.bot.db.get_match_details(match_id)
            if not match_details:
                return None
            
            match_dict = self._create_match_data_dict(match_details)
            
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
            logger.error(f"Error creating fast private match view: {e}")
            return None
    
    def _create_streamer_match_view_fast(self, match_id: int, message_data: Dict[str, Any], button_states: List[Dict]) -> Optional[discord.ui.View]:
        
        try:
            match_details = self.bot.db.get_match_details(match_id)
            if not match_details:
                return None
            
            match_dict = self._create_match_data_dict(match_details)
            
            from ui.streamer_management import StreamerMatchView
            view = StreamerMatchView(match_id, self.bot, match_dict)
            view.timeout = None
            
            
            if button_states:
                for button_state in button_states:
                    button_id = button_state.get('id', '')
                    if 'register_streamer' in button_id and 'unregister' not in button_id:
                        self._restore_button_state_fast(view.register_button, button_state, button_id)
                    elif 'unregister_streamer' in button_id:
                        self._restore_button_state_fast(view.unregister_button, button_state, button_id)
            
            
            existing_streamers = self.bot.db.get_match_streamers_detailed(match_id)
            has_streamers = len(existing_streamers) > 0
            
            if has_streamers:
                view.register_button.disabled = True
                view.register_button.label = 'Streamer Registered'
                view.register_button.style = discord.ButtonStyle.secondary
                
                view.unregister_button.disabled = False
                view.unregister_button.label = 'Unregister as Streamer'
                view.unregister_button.style = discord.ButtonStyle.danger
            else:
                view.register_button.disabled = False
                view.register_button.label = '📺 Register as Streamer'
                view.register_button.style = discord.ButtonStyle.primary
                
                view.unregister_button.disabled = True
                view.unregister_button.label = 'Not Registered'
                view.unregister_button.style = discord.ButtonStyle.danger
            
            return view
            
        except Exception as e:
            logger.error(f"Error creating streamer match view: {e}")
            return None
    
    def _create_orga_panel_view_fast(self, button_states: List[Dict]) -> Optional[discord.ui.View]:
        
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
            logger.error(f"Error creating fast orga panel view: {e}")
            return None
    
    def _create_result_submission_view_fast(self, match_id: int, message_data: Dict[str, Any], button_states: List[Dict]) -> Optional[discord.ui.View]:
        
        try:
            ui_data = message_data.get('ui_data', {})
            submission_data = ui_data.get('data', {})
            result_data = submission_data.get('result_data', {})
            
            if not result_data:
                logger.debug(f"No result data found for result submission {match_id}")
                return None
            
            match_details = self.bot.db.get_match_details(match_id)
            if not match_details:
                logger.debug(f"No match details found for result submission {match_id}")
                return None
            
            match_dict = self._create_match_data_dict(match_details)
            
            from ui.match_interactions.result_submission_system import ResultSubmissionView
            
            
            submitting_team = submission_data.get('submitting_team', 'Unknown')
            responding_team = submission_data.get('responding_team', 'Team2')
            responding_team_role_id = submission_data.get('responding_team_role_id', 0)
            
            view = ResultSubmissionView(
                self.bot, match_id, match_dict, result_data,
                submitting_team, responding_team, responding_team_role_id
            )
            view.timeout = None
            
            
            view.message_id = submission_data.get('message_id')
            view.channel_id = submission_data.get('channel_id')
            view.guild_id = submission_data.get('guild_id')
            
            
            if not view.message_id:
                view.message_id = message_data.get('message_id')
            if not view.channel_id:
                view.channel_id = message_data.get('channel_id')
            if not view.guild_id:
                view.guild_id = message_data.get('guild_id')
            
            
            if button_states:
                for button_state in button_states:
                    button_id = button_state.get('id', '')
                    if 'confirm_result' in button_id:
                        self._restore_button_state_fast(view.confirm_button, button_state, button_id)
                    elif 'dispute_result' in button_id:
                        self._restore_button_state_fast(view.dispute_button, button_state, button_id)
            
            logger.debug(f"Result submission view restored with message_id: {view.message_id}")
            
            return view
            
        except Exception as e:
            logger.error(f"Error creating fast result submission view: {e}")
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
    
    async def _restore_ongoing_interactions_fast(self) -> Dict[str, int]:
        
        try:
            stats = {'total': 0, 'restored': 0, 'failed': 0}
            
            cursor = self.bot.db.conn.cursor()
            cursor.execute('''
                SELECT id, match_id, interaction_type, message_id, data, expires_at
                FROM ongoing_interactions 
                WHERE is_active = 1
                AND (expires_at IS NULL OR expires_at > ?)
                LIMIT 50
            ''', (datetime.now().isoformat(),))
            
            ongoing = cursor.fetchall()
            stats['total'] = len(ongoing)
            
            for interaction_row in ongoing:
                try:
                    interaction_id, match_id, interaction_type, message_id, data_json, expires_at = interaction_row
                    
                    if not data_json:
                        continue
                    
                    interaction_data = json.loads(data_json)
                    button_states = self.bot.db.get_button_states(message_id)
                    
                    view = self._create_ongoing_interaction_view_fast(interaction_type, match_id, interaction_data, button_states)
                    
                    if view:
                        self.bot.add_view(view)
                        self.active_views[message_id] = {
                            'view': view,
                            'message_type': interaction_type,
                            'data': interaction_data
                        }
                        stats['restored'] += 1
                    else:
                        stats['failed'] += 1
                        
                except Exception:
                    stats['failed'] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error in fast ongoing interactions: {e}")
            return {'total': 0, 'restored': 0, 'failed': 0}
    
    def _create_ongoing_interaction_view_fast(self, interaction_type: str, match_id: int, interaction_data: Dict, button_states: List[Dict]) -> Optional[discord.ui.View]:
        
        try:
            if interaction_type == 'time_offer':
                from ui.match_interactions.time_offer_system import TimeOfferView
                
                view = TimeOfferView(
                    self.bot, match_id, interaction_data.get('match_data', {}),
                    interaction_data.get('offered_time', ''), interaction_data.get('offering_team', ''),
                    interaction_data.get('responding_team', ''), interaction_data.get('responding_team_role_id', 0)
                )
                view.timeout = None
                
                
                view.message_id = interaction_data.get('message_id')
                view.channel_id = interaction_data.get('channel_id')
                view.guild_id = interaction_data.get('guild_id')
                
                
                if button_states:
                    for button_state in button_states:
                        button_id = button_state.get('id', '')
                        if 'time_accept' in button_id:
                            self._restore_button_state_fast(view.accept_button, button_state, button_id)
                        elif 'time_counter' in button_id:
                            self._restore_button_state_fast(view.counter_button, button_state, button_id)
                
                return view
                
            elif interaction_type == 'server_offer':
                from ui.match_interactions.server_offer_system import ServerOfferView
                
                view = ServerOfferView(
                    self.bot, match_id, interaction_data.get('match_data', {}),
                    interaction_data.get('server_name', ''), interaction_data.get('server_password', ''),
                    interaction_data.get('offering_team', ''), interaction_data.get('responding_team', ''),
                    interaction_data.get('responding_team_role_id', 0)
                )
                view.timeout = None
                
                
                view.message_id = interaction_data.get('message_id')
                view.channel_id = interaction_data.get('channel_id')
                view.guild_id = interaction_data.get('guild_id')
                
                
                if button_states:
                    for button_state in button_states:
                        button_id = button_state.get('id', '')
                        if 'server_accept' in button_id:
                            self._restore_button_state_fast(view.accept_button, button_state, button_id)
                        elif 'server_counter' in button_id:
                            self._restore_button_state_fast(view.counter_button, button_state, button_id)
                
                return view
                
            elif interaction_type == 'result_submission':
                from ui.match_interactions.result_submission_system import ResultSubmissionView
                
                result_data = interaction_data.get('result_data', {})
                if not result_data:
                    return None
                
                match_dict = {'match_id': match_id, 'team1_name': 'Team 1', 'team2_name': 'Team 2'}
                
                view = ResultSubmissionView(
                    self.bot, match_id, match_dict, result_data,
                    interaction_data.get('submitting_team', 'Unknown'),
                    interaction_data.get('responding_team', 'Team2'),
                    interaction_data.get('responding_team_role_id', 0)
                )
                view.timeout = None
                
                
                view.message_id = interaction_data.get('message_id')
                view.channel_id = interaction_data.get('channel_id')
                view.guild_id = interaction_data.get('guild_id')
                
                
                if button_states:
                    for button_state in button_states:
                        button_id = button_state.get('id', '')
                        if 'confirm_result' in button_id:
                            self._restore_button_state_fast(view.confirm_button, button_state, button_id)
                        elif 'dispute_result' in button_id:
                            self._restore_button_state_fast(view.dispute_button, button_state, button_id)
                
                return view
                
            elif interaction_type == 'orga_result_confirmation':  
                from ui.match_interactions.orga_result_confirmation import OrgaResultConfirmationView
                
                result_data = interaction_data.get('result_data', {})
                if not result_data:
                    return None
                
                match_dict = {'match_id': match_id, 'team1_name': 'Team 1', 'team2_name': 'Team 2'}
                
                view = OrgaResultConfirmationView(
                    self.bot, match_id, match_dict, result_data
                )
                view.timeout = None
                
                
                view.message_id = interaction_data.get('message_id')
                view.channel_id = interaction_data.get('channel_id')
                view.guild_id = interaction_data.get('guild_id')
                
                
                if button_states:
                    for button_state in button_states:
                        button_id = button_state.get('id', '')
                        if 'orga_confirm_result' in button_id:
                            self._restore_button_state_fast(view.confirm_button, button_state, button_id)
                        elif 'orga_edit_result' in button_id:
                            self._restore_button_state_fast(view.edit_button, button_state, button_id)
                
                return view
            
            return None
            
        except Exception:
            return None
    
    def _create_match_data_dict(self, match_details: tuple) -> Dict[str, Any]:
        
        try:
            return {
                'match_id': match_details[0],
                'team1_name': match_details[16] if len(match_details) > 16 else f"Team {match_details[1]}",
                'team2_name': match_details[17] if len(match_details) > 17 else f"Team {match_details[2]}",
                'team1_side': match_details[6],
                'team2_side': match_details[7],
                'match_date': match_details[3],
                'match_time': match_details[4],
                'map_name': match_details[5],
                'week': match_details[13],
                'status': match_details[10]
            }
        except (IndexError, TypeError):
            return {}
    
    async def register_view(self, message: discord.Message, view_type: str, match_id: int = None, data: Dict = None):
        
        try:
            
            if not message or not hasattr(message, 'id'):
                logger.error("❌ Cannot register view: invalid message object")
                return
            
            ui_data = {
                'view_type': view_type,
                'registered_at': datetime.now().isoformat(),
                'data': data or {}
            }
            
            
            message_id = message.id
            channel_id = message.channel.id if message.channel else None
            guild_id = message.guild.id if message.guild else None  
            
            if not channel_id:
                logger.error("❌ Cannot register view: no valid channel_id")
                return
            
            
            logger.debug(f"Registering view: message_id={message_id}, channel_id={channel_id}, guild_id={guild_id}")
                
            self.bot.db.register_ui_message(
                message_id, channel_id, guild_id,  
                view_type, ui_data, match_id
            )
            
            
            try:
                if hasattr(message, 'components') and message.components:
                    buttons_data = []
                    for action_row in message.components:
                        if hasattr(action_row, 'children'):
                            for component in action_row.children:
                                if hasattr(component, 'custom_id') and component.custom_id:
                                    buttons_data.append({
                                        'id': component.custom_id,
                                        'label': getattr(component, 'label', ''),
                                        'disabled': getattr(component, 'disabled', False),
                                        'style': getattr(component, 'style', discord.ButtonStyle.primary).name,
                                        'data': {}
                                    })
                    
                    if buttons_data:
                        self.bot.db.save_button_states(message_id, buttons_data)
                
            except Exception as button_error:
                logger.warning(f"Could not save button states: {button_error}")
            
            logger.debug(f"✅ View registered for persistence: {view_type} (Message ID: {message_id})")
            
        except Exception as e:
            logger.error(f"Error registering view: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
    
    async def update_streamer_button_states(self, message_id: int, view: discord.ui.View):
        
        try:
            if not hasattr(view, 'register_button') or not hasattr(view, 'unregister_button'):
                return
            
            
            new_button_states = [
                {
                    'id': view.register_button.custom_id,
                    'label': view.register_button.label,
                    'disabled': view.register_button.disabled,
                    'style': view.register_button.style.name,
                    'data': {}
                },
                {
                    'id': view.unregister_button.custom_id,
                    'label': view.unregister_button.label,
                    'disabled': view.unregister_button.disabled,
                    'style': view.unregister_button.style.name,
                    'data': {}
                }
            ]
            
            
            self.bot.db.save_button_states(message_id, new_button_states)
            
        except Exception as e:
            logger.error(f"Error updating streamer button states: {e}")
    
    async def cleanup_orphaned_messages(self):
        
        try:
            logger.info("🧹 Starting cleanup...")
            
            stats = {'cleaned': 0}
            
            
            cursor = self.bot.db.conn.cursor()
            cursor.execute('''
                UPDATE ongoing_interactions 
                SET is_active = 0 
                WHERE expires_at < ? AND is_active = 1
            ''', (datetime.now().isoformat(),))
            
            expired = cursor.rowcount
            if expired > 0:
                stats['cleaned'] += expired
                logger.info(f"🗑️ Cleaned {expired} expired interactions")
            
            
            seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor.execute('''
                UPDATE ui_messages 
                SET is_active = 0 
                WHERE message_type IN ('result_submission', 'orga_result_confirmation')
                AND created_at < ? 
                AND is_active = 1
            ''', (seven_days_ago,))
            
            old_messages = cursor.rowcount
            if old_messages > 0:
                stats['cleaned'] += old_messages
                logger.info(f"🗑️ Cleaned {old_messages} old messages")
            
            self.bot.db.conn.commit()
            
            if stats['cleaned'] > 0:
                logger.info(f"✅ Cleanup complete: {stats['cleaned']} items")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
            return {'cleaned': 0}
    
    async def _cleanup_invalid_ui_messages(self):
        
        try:
            cursor = self.bot.db.conn.cursor()
            
            
            cursor.execute('''
                UPDATE ui_messages 
                SET is_active = 0 
                WHERE related_match_id IS NOT NULL 
                AND related_match_id NOT IN (SELECT id FROM matches)
                AND is_active = 1
            ''')
            
            invalid_matches = cursor.rowcount
            
            
            thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
            cursor.execute('''
                UPDATE ui_messages 
                SET is_active = 0 
                WHERE created_at < ? AND is_active = 1
            ''', (thirty_days_ago,))
            
            old_messages = cursor.rowcount
            
            self.bot.db.conn.commit()
            
            total = invalid_matches + old_messages
            if total > 0:
                logger.info(f"🗑️ Pre-cleanup: {total} invalid messages removed")
            
        except Exception as e:
            logger.error(f"Error in pre-cleanup: {e}")
    
    def get_restoration_stats(self) -> Dict[str, Any]:
        
        return {
            'active_views': len(self.active_views),
            'cache_stats': {'active_views': len(self.active_views)}
        }