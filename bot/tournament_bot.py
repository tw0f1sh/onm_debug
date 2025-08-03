# bot/tournament_bot.py

import discord
from discord.ext import commands
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from database.db_manager import DatabaseManager
from utils.lazy_persistence_service import LazyPersistenceService
from utils.fast_startup_persistence import FastStartupPersistence
from utils.team_config_loader import TeamConfigLoader
from utils.public_channel_status_manager import PublicChannelStatusManager

logger = logging.getLogger(__name__)

class TournamentBot(commands.Bot):
    def __init__(self, config):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.members = True  
        super().__init__(command_prefix=config['bot']['prefix'], intents=intents)
        
        self.config = config
        self.db = DatabaseManager()
        self.lazy_persistence = LazyPersistenceService(self)
        self.fast_startup = FastStartupPersistence(self)
        self.team_loader = TeamConfigLoader(self)
        
        # Public Embed Updater hinzufügen
        from utils.public_embed_updater import PublicEmbedUpdater
        self.public_updater = PublicEmbedUpdater(self)
        
        self.status_manager = PublicChannelStatusManager(self)
        
        self.STREAMER_ROLE_ID = config['roles'].get('streamer_role_id')
        self.EVENT_ORGA_ROLE_ID = config['roles'].get('event_orga_role_id')
        self.MATCH_CATEGORY_ID = config['categories'].get('match_category_id')
        # Neue Kategorie für einzelne Public Match Channels
        self.PUBLIC_MATCHES_CATEGORY_ID = config['categories'].get('public_matches_category_id')
        self.TOURNAMENT_NAME = config['tournament'].get('name', 'Tournament')
        self.CURRENT_WEEK = config['tournament'].get('current_week', 1)
        
        self.restoration_complete = False
        self.startup_tasks = []
    
    async def create_public_match_channel(self, guild: discord.Guild, match_id: int, team1_name: str, team2_name: str, week: int, prefix: str = "") -> Optional[discord.TextChannel]:
        """
        Erstellt einen eigenen Channel für ein Public Match mit Status-Icon und optionalem Prefix
        """
        try:
            if not self.PUBLIC_MATCHES_CATEGORY_ID:
                logger.warning("❌ PUBLIC_MATCHES_CATEGORY_ID nicht in config.json konfiguriert!")
                return None
            
            # Kategorie finden
            public_matches_category = guild.get_channel(self.PUBLIC_MATCHES_CATEGORY_ID)
            if not public_matches_category:
                logger.error(f"❌ Public Matches Kategorie {self.PUBLIC_MATCHES_CATEGORY_ID} nicht gefunden!")
                return None
            
            # Status-Icon für neuen Channel (created)
            status_icon = '📝'
            
            # Channel Namen erstellen mit Status-Icon und optionalem Prefix
            if prefix:
                # Prefix bereinigen
                clean_prefix = self._sanitize_channel_name(prefix)
                channel_name = f"{status_icon}-{clean_prefix}-w{week}-{team1_name.lower()}-vs-{team2_name.lower()}"
            else:
                channel_name = f"{status_icon}-w{week}-{team1_name.lower()}-vs-{team2_name.lower()}"
            
            # Discord Channel Namen bereinigen
            channel_name = self._sanitize_channel_name(channel_name)
            
            # Channel erstellen
            channel = await guild.create_text_channel(
                name=channel_name,
                category=public_matches_category,
                topic=f"Week {week}: {team1_name} vs {team2_name} - Match ID: {match_id}" + (f" - {prefix}" if prefix else ""),
                reason=f"Automatisch erstellter Public Match Channel für Match {match_id}" + (f" mit Prefix '{prefix}'" if prefix else "")
            )
            
            # Channel ID in Datenbank speichern
            self.db.set_setting(f'public_match_{match_id}_channel_id', str(channel.id))
            
            logger.info(f"✅ Public Match Channel erstellt: {channel.name} (ID: {channel.id}) für Match {match_id}" + (f" mit Prefix '{prefix}'" if prefix else ""))
            return channel
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Erstellen des Public Match Channels: {e}")
            return None
    
    def _sanitize_channel_name(self, name: str) -> str:
        """
        Bereinigt Channel Namen für Discord - FIXED: Behält Emojis bei
        """
        import re
        import unicodedata
        
        # GEÄNDERT: Emojis explizit beibehalten
        # Zuerst alle Emojis extrahieren und temporär ersetzen
        emoji_placeholders = {}
        emoji_counter = 0
        
        # Unicode Emoji Bereiche
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"  # enclosed characters
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
        
        # Emojis temporär durch Platzhalter ersetzen
        temp_name = emoji_pattern.sub(replace_emoji, name)
        
        # Nur erlaubte Zeichen: a-z, 0-9, - und _ (plus unsere Emoji-Platzhalter)
        sanitized = re.sub(r'[^a-z0-9\-_]', '-', temp_name.lower())
        
        # Mehrfache Bindestriche entfernen
        sanitized = re.sub(r'-+', '-', sanitized)
        
        # Bindestriche am Anfang/Ende entfernen
        sanitized = sanitized.strip('-')
        
        # Emojis wieder einsetzen
        for placeholder, emoji in emoji_placeholders.items():
            sanitized = sanitized.replace(placeholder.lower(), emoji)
        
        # Maximale Länge 100 Zeichen
        result = sanitized[:100]
        
        return result
    
    async def get_or_create_public_match_channel(self, guild: discord.Guild, match_id: int, team1_name: str, team2_name: str, week: int, prefix: str = "") -> Optional[discord.TextChannel]:
        """
        Holt einen existierenden Public Match Channel oder erstellt einen neuen mit optionalem Prefix
        """
        try:
            # Prüfen ob Channel bereits existiert
            stored_channel_id = self.db.get_setting(f'public_match_{match_id}_channel_id')
            if stored_channel_id:
                try:
                    channel = guild.get_channel(int(stored_channel_id))
                    if channel:
                        logger.info(f"✅ Existierender Public Match Channel gefunden: {channel.name}")
                        return channel
                    else:
                        logger.warning(f"⚠️ Gespeicherter Channel {stored_channel_id} nicht mehr vorhanden, erstelle neuen")
                except ValueError:
                    logger.warning(f"⚠️ Ungültige Channel ID gespeichert: {stored_channel_id}")
            
            # Neuen Channel erstellen
            return await self.create_public_match_channel(guild, match_id, team1_name, team2_name, week, prefix)
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen/Erstellen des Public Match Channels: {e}")
            return None
    
    async def archive_public_match_channel(self, match_id: int, result_data: dict = None):
        """
        Archiviert einen Public Match Channel nach Abschluss des Matches
        """
        try:
            # Channel ID aus Datenbank holen
            stored_channel_id = self.db.get_setting(f'public_match_{match_id}_channel_id')
            if not stored_channel_id:
                logger.info(f"ℹ️ Kein Public Match Channel für Match {match_id} gefunden")
                return
            
            # Channel finden
            channel = None
            for guild in self.guilds:
                channel = guild.get_channel(int(stored_channel_id))
                if channel:
                    break
            
            if not channel:
                logger.warning(f"⚠️ Public Match Channel {stored_channel_id} nicht gefunden")
                return
            
            # Archive Kategorie finden
            archive_category_id = self.config['categories'].get('archive_category_id')
            if archive_category_id:
                archive_category = channel.guild.get_channel(archive_category_id)
                if archive_category:
                    # Channel zur Archive Kategorie verschieben
                    await channel.edit(
                        category=archive_category,
                        name=f"archived-{channel.name}",
                        reason=f"Match {match_id} abgeschlossen"
                    )
                    
                    # Archiv-Nachricht senden
                    if result_data:
                        archive_embed = discord.Embed(
                            title="📁 Match Archived",
                            description="This match has been completed and archived.",
                            color=discord.Color.green()
                        )
                        archive_embed.add_field(
                            name="🏆 Final Result", 
                            value=f"**{result_data['winner']}** wins {result_data['score']}", 
                            inline=False
                        )
                        archive_embed.set_footer(text=f"Match ID: {match_id}")
                        
                        await channel.send(embed=archive_embed)
                    
                    logger.info(f"✅ Public Match Channel {channel.name} erfolgreich archiviert")
                else:
                    logger.warning(f"⚠️ Archive Kategorie {archive_category_id} nicht gefunden")
            else:
                logger.warning("⚠️ Keine Archive Kategorie konfiguriert")
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Archivieren des Public Match Channels: {e}")

    async def send_private_match_with_lazy_persistence_with_icons(self, channel, match_id: int, match_data: Dict[str, Any], team1_role, team2_role):
        try:
            from ui.match_interactions.private_match_view import PrivateMatchView
            view = PrivateMatchView(self, match_id, match_data)
            
            try:
                from cogs.tournament_cog import TournamentCog
                cog = self.get_cog('TournamentCog')
                if cog:
                    embed = cog._create_private_embed_with_dynamic_status(match_data)
                else:
                    from utils.embed_builder import EmbedBuilder
                    embed = EmbedBuilder.create_private_match_embed_with_roles(
                        match_id, match_data['team1_name'], match_data['team2_name'],
                        match_data['match_date'], match_data['map_name'],
                        match_data['team1_side'], match_data['team2_side'],
                        team1_role, team2_role, match_data['week'], self
                    )
            except Exception as embed_error:
                logger.error(f"Error creating embed: {embed_error}")
                formatted_date = self._format_date_display(match_data.get('match_date', 'TBA'))
                team1_side_with_icon = self._format_team_side_with_icon(match_data['team1_side'])
                team2_side_with_icon = self._format_team_side_with_icon(match_data['team2_side'])
                
                embed = discord.Embed(
                    title=f"🏆 Week {match_data.get('week', 'N/A')}: {match_data['team1_name']} vs {match_data['team2_name']}",
                    color=discord.Color.gold()
                )
                embed.add_field(name="📅 Match Date", value=formatted_date, inline=True)
                embed.add_field(name="🕒 Match Time", value=match_data.get('match_time', '*TBA*'), inline=True)
                embed.add_field(name="🗺️ Map", value=match_data.get('map_name', 'TBA'), inline=True)
                embed.add_field(
                    name="🔴 Team Sides", 
                    value=f"{match_data['team1_name']}: {team1_side_with_icon}\n{match_data['team2_name']}: {team2_side_with_icon}", 
                    inline=False
                )
                embed.add_field(name="👥 Teams", value=f"{team1_role.mention} vs {team2_role.mention}", inline=False)
                
                rules_url = self.config.get('rules', {}).get('onm_url', '#')
                embed.add_field(name="📖 Rules", value=f"[ONM]({rules_url})", inline=False)
                embed.add_field(name="ℹ️ Status", value="Waiting for match time coordination", inline=False)
                embed.set_footer(text=f"Match ID: {match_id}")
            
            message = await channel.send(embed=embed, view=view)
            
            await self.lazy_persistence.register_view(message, 'private_match', match_id, match_data)
            
            logger.info(f"✅ Private match message sent WITH ICONS and lazy persistence: {match_id}")
            return message
            
        except Exception as e:
            logger.error(f"Error sending private match with icons and lazy persistence: {e}")
            return None

    def _format_date_display(self, date_str: str) -> str:
        if not date_str or date_str == 'TBA':
            return "TBA"
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%d.%m.%Y')
        except:
            return date_str

    def _format_team_side_with_icon(self, team_side: str) -> str:
        try:
            if not team_side or team_side == 'TBA':
                return 'TBA'
            
            team_icons = self.config.get('team_icons', {})
            icon = team_icons.get(team_side.upper(), '')
            
            if icon:
                return f"{team_side} {icon}"
            else:
                return team_side
                
        except Exception as e:
            logger.error(f"Error formatting team side with icon: {e}")
            return team_side
        
    async def on_ready(self):
        logger.info(f'{self.user} ist online!')
        logger.info(f'Tournament: {self.TOURNAMENT_NAME}')
        logger.info(f'Aktuelle Woche: {self.CURRENT_WEEK}')
        
        self._check_configuration()
        self._validate_teams_configuration()
        
        logger.info("🚀 Starting FAST startup (NO MESSAGE EDITS)...")
        
        await self.fast_startup.fast_restore_all_components()
        
        self.restoration_complete = True
        
        stats = self.fast_startup.get_restoration_stats()
        logger.info(f"📊 FAST startup stats: {stats}")
        
        await self._start_background_tasks()
        
        logger.info("✅ Bot startup complete with FAST RESTORATION!")

        asyncio.create_task(self._sync_slash_commands_async())
    
    async def _sync_slash_commands_async(self):
        try:
            logger.info("🔄 Syncing slash commands in background...")
            
            synced = await asyncio.wait_for(self.tree.sync(), timeout=30.0)
            logger.info(f"✅ Synced {len(synced)} slash command(s)")
            
        except asyncio.TimeoutError:
            logger.warning("⏰ Slash command sync timed out after 30s - continuing without sync")
        except Exception as e:
            logger.error(f"❌ Failed to sync slash commands: {e}")
            logger.info("📝 Bot will work normally, only slash commands may not be available")
    
    def _validate_teams_configuration(self):
        try:
            validation_result = self.team_loader.validate_teams_config()
            
            if validation_result['valid']:
                logger.info(f"✅ Valid teams loaded: {', '.join(validation_result['valid'])}")
            
            if validation_result['warnings']:
                for warning in validation_result['warnings']:
                    logger.warning(f"⚠️ Team config warning: {warning}")
            
            if validation_result['invalid']:
                for invalid in validation_result['invalid']:
                    logger.error(f"❌ Invalid team config: {invalid}")
            
            stats = self.team_loader.get_team_statistics()
            logger.info(f"📊 Teams loaded: {stats['active_teams']} active, {stats['inactive_teams']} inactive, {stats['total_teams']} total")
            
        except Exception as e:
            logger.error(f"Error validating teams configuration: {e}")
    
    def get_all_teams(self):
        return self.team_loader.get_all_teams()
    
    def get_active_teams(self):
        return self.team_loader.get_active_teams()
    
    def team_exists(self, name: str) -> bool:
        return self.team_loader.team_exists(name)
    
    def get_team_by_role_id(self, role_id: int):
        return self.team_loader.get_team_by_role_id(role_id)
    
    def get_team_by_name(self, name: str):
        return self.team_loader.get_team_by_name(name)
    
    def create_legacy_team_in_db(self, team_config_tuple):
        try:
            team_id, name, role_id, members, active = team_config_tuple
            
            cursor = self.db.conn.cursor()
            cursor.execute('SELECT id FROM teams WHERE captain_id = ?', (role_id,))
            existing = cursor.fetchone()
            
            if not existing:
                db_team_id = self.db.create_team(name, role_id)
                logger.info(f"Created legacy database entry for team {name}")
                return db_team_id
            else:
                return existing[0]
                
        except Exception as e:
            logger.error(f"Error creating legacy team entry: {e}")
            return None
    
    def sync_config_teams_to_database(self):
        try:
            config_teams = self.get_all_teams()
            synced_count = 0
            
            for team_tuple in config_teams:
                if self.create_legacy_team_in_db(team_tuple):
                    synced_count += 1
            
            logger.info(f"✅ Synced {synced_count} teams from config to database")
            
        except Exception as e:
            logger.error(f"Error syncing config teams to database: {e}")
    
    async def _start_background_tasks(self):
        try:
            self.sync_config_teams_to_database()
            
            cleanup_task = asyncio.create_task(self._periodic_cleanup())
            self.startup_tasks.append(cleanup_task)
            
            stats_task = asyncio.create_task(self._periodic_stats_logging())
            self.startup_tasks.append(stats_task)
            
            logger.info("✅ Background tasks started")
            
        except Exception as e:
            logger.error(f"Error starting background tasks: {e}")
    
    async def _periodic_cleanup(self):
        while not self.is_closed():
            try:
                await asyncio.sleep(3600)
                
                logger.info("🧹 Running periodic cleanup...")
                
                self.db.cleanup_expired_data()
                await self.lazy_persistence.cleanup_orphaned_messages()
                self.sync_config_teams_to_database()
                
                logger.info("✅ Periodic cleanup complete")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(300)
    
    def get_fast_persistence_stats(self) -> Dict[str, Any]:
        try:
            return self.fast_startup.get_restoration_stats()
        except Exception as e:
            logger.error(f"Error getting fast persistence stats: {e}")
            return {'startup_method': 'FAST_NO_EDITS', 'active_views': 0}
    
    async def _periodic_stats_logging(self):
        while not self.is_closed():
            try:
                await asyncio.sleep(21600)
                
                stats = self.get_fast_persistence_stats()
                logger.info(f"📊 Periodic FAST stats: {stats}")
                
                team_stats = self.team_loader.get_team_statistics()
                logger.info(f"👥 Team stats: {team_stats}")
                
                active_guilds = len(self.guilds)
                total_members = sum(guild.member_count for guild in self.guilds)
                
                logger.info(f"🤖 Bot stats: {active_guilds} guilds, ~{total_members} members")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic stats: {e}")
                await asyncio.sleep(300)
    
    def _check_configuration(self):
        missing_config = []
        
        if not self.STREAMER_ROLE_ID:
            missing_config.append("Streamer Role ID")
        if not self.EVENT_ORGA_ROLE_ID:
            missing_config.append("Event Orga Role ID")
        if not self.MATCH_CATEGORY_ID:
            missing_config.append("Match Category ID")
        if not self.PUBLIC_MATCHES_CATEGORY_ID:
            missing_config.append("Public Matches Category ID")
            
        teams_config = self.config.get('teams', {})
        if not teams_config:
            missing_config.append("Teams Configuration")
        
        if missing_config:
            logger.warning(f"Fehlende Konfiguration: {', '.join(missing_config)}")
        else:
            logger.info("✅ Alle Konfigurationen gesetzt!")
    
    async def send_private_match_with_lazy_persistence(self, channel, match_id: int, match_data: Dict[str, Any]):
        try:
            from ui.match_interactions.private_match_view import PrivateMatchView
            view = PrivateMatchView(self, match_id, match_data)
            
            try:
                from cogs.tournament_cog import TournamentCog
                cog = self.get_cog('TournamentCog')
                if cog:
                    embed = cog._create_private_embed_with_dynamic_status(match_data)
                else:
                    from utils.embed_builder import EmbedBuilder
                    embed = EmbedBuilder.create_private_match_embed_with_roles(
                        match_id, match_data['team1_name'], match_data['team2_name'],
                        match_data['match_date'], match_data['map_name'],
                        match_data['team1_side'], match_data['team2_side'],
                        None, None, match_data['week'], self
                    )
            except Exception as embed_error:
                logger.error(f"Error creating embed: {embed_error}")
                embed = discord.Embed(
                    title=f"Week {match_data.get('week', 'N/A')}: {match_data['team1_name']} vs {match_data['team2_name']}",
                    color=discord.Color.gold()
                )
                embed.add_field(name="Match Date", value=match_data.get('match_date', 'TBA'), inline=True)
                embed.add_field(name="Match Time", value=match_data.get('match_time', '*TBA*'), inline=True)
                embed.add_field(name="Map", value=match_data.get('map_name', 'TBA'), inline=True)
                embed.set_footer(text=f"Match ID: {match_id}")
            
            message = await channel.send(embed=embed, view=view)
            
            await self.lazy_persistence.register_view(message, 'private_match', match_id, match_data)
            
            logger.info(f"✅ Private match message sent with lazy persistence: {match_id}")
            return message
            
        except Exception as e:
            logger.error(f"Error sending private match with lazy persistence: {e}")
            return None
    
    async def send_streamer_match_with_lazy_persistence(self, channel, match_id: int, match_data: Dict[str, Any]):
        try:
            from ui.streamer_management.streamer_match_view import StreamerMatchView
            view = StreamerMatchView(match_id, self, match_data)
            
            from utils.embed_builder import EmbedBuilder
            embed = EmbedBuilder.create_streamer_match_embed(match_data, [], self)
            
            message = await channel.send(embed=embed, view=view)
            
            await self.lazy_persistence.register_view(message, 'streamer_match', match_id, match_data)
            
            self.db.set_match_streamer_message_id(match_id, message.id)
            
            logger.info(f"✅ Streamer match message sent with lazy persistence: {match_id}")
            return message
            
        except Exception as e:
            logger.error(f"Error sending streamer match with lazy persistence: {e}")
            return None
    
    async def send_public_match_with_lazy_persistence(self, guild: discord.Guild, match_id: int, match_data: Dict[str, Any], prefix: str = ""):
        """
        NEUE Methode: Erstellt einen eigenen Channel und sendet das Public Match Embed mit optionalem Prefix
        """
        try:
            # Channel für dieses Match erstellen/finden mit Prefix
            public_channel = await self.get_or_create_public_match_channel(
                guild, match_id, match_data['team1_name'], match_data['team2_name'], match_data['week'], prefix
            )
            
            if not public_channel:
                logger.error(f"❌ Konnte keinen Public Match Channel für Match {match_id} erstellen")
                return None
            
            # Embed erstellen
            from utils.embed_builder import EmbedBuilder
            embed = EmbedBuilder.create_public_match_embed_with_week(
                match_id, match_data['team1_name'], match_data['team2_name'],
                match_data['match_date'], match_data['map_name'],
                match_data['team1_side'], match_data['team2_side'],
                match_data['week'], self
            )

            # Message senden
            message = await public_channel.send(embed=embed)
            
            # Lazy Persistence registrieren
            await self.lazy_persistence.register_view(message, 'public_match', match_id, match_data)
            
            # Message ID in Datenbank speichern
            self.db.update_public_message_id(match_id, message.id)
            
            # Public Message ID auch für Update-System speichern
            self.db.set_setting(f'public_match_{match_id}_message_id', str(message.id))
            
            logger.info(f"✅ Public match message sent in dedicated channel {public_channel.name}: {match_id}" + (f" with prefix '{prefix}'" if prefix else ""))
            return message
            
        except Exception as e:
            logger.error(f"Error sending public match with lazy persistence: {e}")
            return None
    
    async def send_orga_panel_with_lazy_persistence(self, channel):
        try:
            from utils.embed_builder import EmbedBuilder
            from ui.orga_panel import OrgaControlPanel
            
            logger.info("Creating orga panel embed...")
            embed = EmbedBuilder.create_orga_panel_embed(self)
            
            logger.info("Creating orga panel view...")
            view = OrgaControlPanel(self)
            
            logger.info("Sending orga panel message...")
            message = await channel.send(embed=embed, view=view)
            
            if not message:
                logger.error("❌ Failed to send orga panel message - message is None")
                return None
            
            logger.info("Setting database entries...")
            self.db.set_setting('orga_panel_message_id', str(message.id))
            self.db.set_setting('orga_panel_channel_id', str(channel.id))

            try:
                if hasattr(self, 'lazy_persistence'):
                    persistence_data = {
                        'orga_panel_data': {},
                        'message_id': message.id,
                        'channel_id': message.channel.id,
                        'guild_id': message.guild.id if message.guild else None
                    }
                    
                    await self.lazy_persistence.register_view(message, 'orga_panel', None, persistence_data)
                    logger.info(f"✅ Orga panel registered with lazy persistence: {message.id}")
            except Exception as lazy_persistence_error:
                logger.error(f"Error with lazy persistence registration: {lazy_persistence_error}")
            
            try:
                ui_data = {
                    'view_type': 'orga_panel',
                    'registered_at': datetime.now().isoformat(),
                    'data': {
                        'orga_panel_data': {},
                        'message_id': message.id,
                        'channel_id': message.channel.id,
                        'guild_id': message.guild.id if message.guild else None
                    }
                }
                
                self.db.register_ui_message(
                    message.id, message.channel.id, message.guild.id if message.guild else None,
                    'orga_panel', ui_data, None
                )
                
                buttons_data = []
                for item in view.children:
                    if hasattr(item, 'custom_id') and item.custom_id:
                        buttons_data.append({
                            'id': item.custom_id,
                            'label': item.label,
                            'disabled': item.disabled,
                            'style': item.style.name,
                            'data': {}
                        })
                
                if buttons_data:
                    self.db.save_button_states(message.id, buttons_data)
                    logger.info(f"✅ Orga panel registered for Fast Startup with {len(buttons_data)} buttons")
                
                self.add_view(view)
                
                logger.info(f"✅ Orga panel registered with DUAL persistence: {message.id}")
                
            except Exception as db_registration_error:
                logger.error(f"Error with database registration: {db_registration_error}")
                self.add_view(view)
            
            logger.info(f"✅ Orga panel sent with lazy persistence: {message.id}")
            return message
            
        except Exception as e:
            import traceback
            logger.error(f"Error sending orga panel with lazy persistence: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None

    async def wait_for_restoration(self, timeout: int = 30):
        start_time = asyncio.get_event_loop().time()
        
        while not self.restoration_complete:
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.warning("⚠️ FAST restoration timeout reached")
                break
            await asyncio.sleep(0.5)
    
    async def on_message_delete(self, message):
        try:
            if message.author == self.user:
                self.db.deactivate_ui_message(message.id)
                logger.info(f"🗑️ Deactivated persistence for deleted message {message.id}")
                
        except Exception as e:
            logger.error(f"Error handling message deletion: {e}")
    
    async def on_guild_channel_delete(self, channel):
        try:
            cursor = self.db.conn.cursor()
            cursor.execute('SELECT message_id FROM ui_messages WHERE channel_id = ?', (channel.id,))
            message_ids = cursor.fetchall()
            
            for (message_id,) in message_ids:
                self.db.deactivate_ui_message(message_id)
            
            logger.info(f"🗑️ Deactivated {len(message_ids)} messages due to channel deletion")
            
        except Exception as e:
            logger.error(f"Error handling channel deletion: {e}")
    
    async def close(self):
        logger.info("Bot wird heruntergefahren...")
        
        for task in self.startup_tasks:
            if not task.done():
                task.cancel()
        
        if self.startup_tasks:
            await asyncio.gather(*self.startup_tasks, return_exceptions=True)
        
        if hasattr(self, 'db'):
            self.db.close()
            
        await super().close()
    def _get_streamer_display_name(self, streamer_id: int) -> str:
        """
        Holt den Server-Nickname oder fällt auf Display-Name zurück (FIXED)
        """
        try:
            # Versuche Member zu finden (hat Server-Nickname)
            for guild in self.guilds:
                member = guild.get_member(streamer_id)
                if member:
                    # Priorität: Server-Nickname > Global Display Name > Username
                    return member.nick or member.global_name or member.name
            
            # Fallback auf User
            user = self.get_user(streamer_id)
            return user.global_name or user.name if user else f"User {streamer_id}"
            
        except Exception as e:
            logger.error(f"Error getting streamer display name: {e}")
            return f"User {streamer_id}"
        
        logger.info("✅ Bot shutdown complete")