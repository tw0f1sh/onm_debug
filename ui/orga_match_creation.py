"""
Enhanced Orga Match Creation - Updated für separate Public Match Channels
Speichere als: ui/orga_match_creation.py
"""

import discord
import logging
from datetime import datetime
from typing import List, Tuple

logger = logging.getLogger(__name__)

class MatchCreationHandler:
    def __init__(self, bot):
        self.bot = bot
    
    async def start_match_creation(self, interaction: discord.Interaction):
        teams = self.bot.get_active_teams()
        if len(teams) < 2:
            await interaction.response.send_message(
                "❌ Mindestens 2 aktive Teams müssen in der config.json konfiguriert sein!\n"
                "Prüfe die 'teams' Sektion in deiner config.json", 
                ephemeral=True
            )
            return
            
        modal = MatchCreationModal(self.bot, teams)
        await interaction.response.send_modal(modal)

class MatchCreationModal(discord.ui.Modal):
    def __init__(self, bot, teams: List[Tuple]):
        super().__init__(title="🆕 Neues Match erstellen", timeout=300)
        self.bot = bot
        self.teams = teams
        
        self.team_options = [(team[1], team[0]) for team in teams if team[4]]
        
        today = datetime.now().strftime('%d.%m.%Y')
        self.match_date = discord.ui.TextInput(
            label="Match Datum (DD.MM.YYYY)",
            placeholder="DD.MM.YYYY",
            default=today,
            max_length=10,
            required=True
        )
        
        self.week_number = discord.ui.TextInput(
            label="Woche",
            placeholder=str(bot.CURRENT_WEEK),
            default=str(bot.CURRENT_WEEK),
            max_length=2,
            required=True
        )
        
        self.channel_prefix = discord.ui.TextInput(
            label="Channel Prefix (optional)",
            placeholder="g1, playoffs, finale, etc.",
            default="",
            max_length=10,
            required=False
        )
        
        self.add_item(self.match_date)
        self.add_item(self.week_number)
        self.add_item(self.channel_prefix)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            date_input = self.match_date.value.strip()
            week = int(self.week_number.value.strip())
            prefix = self.channel_prefix.value.strip()
            
            try:
                date_obj = datetime.strptime(date_input, '%d.%m.%Y')
                date_str = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                await interaction.response.send_message("❌ Ungültiges Datumsformat! Verwende DD.MM.YYYY (z.B. 15.03.2024)", ephemeral=True)
                return
            
            view = TeamSelectionView(self.bot, self.team_options, date_str, week, prefix)
            embed = discord.Embed(
                title="👥 Team Auswahl",
                description="Wähle die beiden Teams für das Match:\n\n🎲 **Map und Team-Seiten werden automatisch per Wheel ausgewählt!**",
                color=discord.Color.blue()
            )
            embed.add_field(name="📅 Datum", value=date_input, inline=True)
            embed.add_field(name="📅 Woche", value=str(week), inline=True)
            
            if prefix:
                embed.add_field(name="🏷️ Channel Prefix", value=f"`{prefix}`", inline=True)
            
            embed.add_field(name="🎪 Automatic Selection", value="Map and team sides will be randomly selected using spinning wheels!", inline=False)
            
            team_names = [team[0] for team in self.team_options]
            embed.add_field(name="🏆 Available Teams", value=f"{len(team_names)} teams: {', '.join(team_names[:5])}" + ("..." if len(team_names) > 5 else ""), inline=False)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except ValueError as e:
            if "invalid literal for int()" in str(e):
                await interaction.response.send_message("❌ Woche muss eine Zahl sein!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Ungültige Eingabe! Prüfe alle Felder.", ephemeral=True)
        except Exception as e:
            logger.error(f"Fehler beim Match erstellen: {e}")
            await interaction.response.send_message("❌ Ein Fehler ist aufgetreten!", ephemeral=True)

class TeamSelectionView(discord.ui.View):
    def __init__(self, bot, team_options: List[Tuple], date_str: str, week: int, prefix: str = ""):
        super().__init__(timeout=300)
        self.bot = bot
        self.team_options = team_options
        self.date_str = date_str
        self.week = week
        self.prefix = prefix
        
        team1_options = [discord.SelectOption(label=name, value=str(team_id)) for name, team_id in team_options]
        self.team1_select = discord.ui.Select(
            placeholder="Wähle Team 1...",
            options=team1_options[:25],
            custom_id="team1_select"
        )
        self.team1_select.callback = self.team1_selected
        
        team2_options = [discord.SelectOption(label=name, value=str(team_id)) for name, team_id in team_options]
        self.team2_select = discord.ui.Select(
            placeholder="Wähle Team 2...",
            options=team2_options[:25],
            custom_id="team2_select",
            disabled=True
        )
        self.team2_select.callback = self.team2_selected
        
        self.add_item(self.team1_select)
        self.add_item(self.team2_select)
        
        self.selected_team1 = None
        self.selected_team2 = None
    
    async def team1_selected(self, interaction: discord.Interaction):
        self.selected_team1 = int(self.team1_select.values[0])
        
        team2_options = [
            discord.SelectOption(label=name, value=str(team_id)) 
            for name, team_id in self.team_options 
            if team_id != self.selected_team1
        ]
        
        self.team2_select.options = team2_options[:25]
        self.team2_select.disabled = False
        self.team1_select.disabled = True
        
        await interaction.response.edit_message(view=self)
    
    async def team2_selected(self, interaction: discord.Interaction):
        self.selected_team2 = int(self.team2_select.values[0])
        
        try:
            all_teams = self.bot.get_all_teams()
            team1_data = next((team for team in all_teams if team[0] == self.selected_team1), None)
            team2_data = next((team for team in all_teams if team[0] == self.selected_team2), None)
            
            if not team1_data or not team2_data:
                await interaction.response.send_message("❌ Teams nicht in Config gefunden!", ephemeral=True)
                return
            
            team1_role = interaction.guild.get_role(team1_data[2])
            team2_role = interaction.guild.get_role(team2_data[2])
            
            if not team1_role or not team2_role:
                await interaction.response.send_message(
                    f"❌ Team-Rollen nicht gefunden!\n"
                    f"Team 1: {team1_data[1]} (Rolle ID: {team1_data[2]})\n"
                    f"Team 2: {team2_data[1]} (Rolle ID: {team2_data[2]})\n"
                    f"Prüfe die role_id Werte in deiner config.json", 
                    ephemeral=True
                )
                return
            
            await interaction.response.send_message("🎲 Spinning wheels for map and team sides...", ephemeral=True)
            
            from wheel.match_wheel_service import MatchWheelService
            
            selected_map, team1_side, team2_side, map_wheel_data, sides_wheel_data = await MatchWheelService.select_map_and_sides(
                team1_data[1], team2_data[1]
            )
            
            logger.info(f"🎲 Wheel results: Map={selected_map}, {team1_data[1]}={team1_side}, {team2_data[1]}={team2_side}")
            
            db_team1_id = self.bot.create_legacy_team_in_db(team1_data)
            db_team2_id = self.bot.create_legacy_team_in_db(team2_data)
            
            if not db_team1_id or not db_team2_id:
                await interaction.followup.send("❌ Fehler beim Synchronisieren der Teams mit der Datenbank!", ephemeral=True)
                return
            
            private_channel = await self._create_match_channel_with_roles(
                interaction.guild, team1_data[1], team2_data[1], team1_role, team2_role, self.week, self.prefix
            )
            
            match_id = self.bot.db.create_match(
                db_team1_id, db_team2_id, self.date_str, selected_map,
                team1_side, team2_side, private_channel.id, self.week
            )
            
            match_data = {
                'match_id': match_id,
                'team1_name': team1_data[1],
                'team2_name': team2_data[1],
                'team1_side': team1_side,
                'team2_side': team2_side,
                'match_date': self.date_str,
                'match_time': None,
                'map_name': selected_map,
                'week': self.week,
                'status': 'pending'
            }
            
            private_message = await self.bot.send_private_match_with_lazy_persistence_with_icons(
                private_channel, match_id, match_data, team1_role, team2_role
            )
            
            await self._send_wheel_gifs_to_channel(private_channel, match_id, map_wheel_data, sides_wheel_data)
            
            public_message = await self.bot.send_public_match_with_lazy_persistence(
                interaction.guild, match_id, match_data, self.prefix
            )
          
            await self._create_and_send_streamer_post_with_lazy_persistence(match_id, match_data)
            
            try:
                date_obj = datetime.strptime(self.date_str, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d.%m.%Y')
            except:
                formatted_date = self.date_str
            
            team1_side_with_icon = self._format_team_side_with_icon(team1_side)
            team2_side_with_icon = self._format_team_side_with_icon(team2_side)
            
            embed = discord.Embed(
                title="✅ Match erfolgreich erstellt!",
                description=f"**{team1_data[1]}** vs **{team2_data[1]}**",
                color=discord.Color.green()
            )
            embed.add_field(name="📅 Datum", value=formatted_date, inline=True)
            embed.add_field(name="🗺️ Map", value=f"🎲 {selected_map} (wheel selected)", inline=True)
            embed.add_field(name="🆔 Match ID", value=str(match_id), inline=True)
            embed.add_field(name="🔴 Team Sides", value=f"{team1_data[1]}: {team1_side_with_icon}\n{team2_data[1]}: {team2_side_with_icon}", inline=False)
            embed.add_field(name="💬 Private Channel", value=private_channel.mention, inline=False)
            embed.add_field(name="👥 Teams", value=f"{team1_role.mention} vs {team2_role.mention}", inline=False)
            
            if self.prefix:
                embed.add_field(name="🏷️ Channel Prefix", value=f"`{self.prefix}` wurde verwendet", inline=False)
            
            if public_message:
                public_channel_id = self.bot.db.get_setting(f'public_match_{match_id}_channel_id')
                if public_channel_id:
                    public_channel = interaction.guild.get_channel(int(public_channel_id))
                    if public_channel:
                        embed.add_field(name="🌐 Public Channel", value=public_channel.mention, inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            logger.info(f"✅ Match {match_id} erstellt: {team1_data[1]} vs {team2_data[1]}, Map: {selected_map}")
            
        except Exception as e:
            logger.error(f"Fehler beim Match erstellen: {e}")
            await interaction.response.send_message("❌ Fehler beim Erstellen des Matches!", ephemeral=True)
    
    def _format_team_side_with_icon(self, team_side: str) -> str:
        try:
            team_icons = self.bot.config.get('team_icons', {})
            icon = team_icons.get(team_side.upper(), '')
            
            if icon:
                return f"{team_side} {icon}"
            else:
                return team_side
                
        except Exception as e:
            logger.error(f"Error formatting team side with icon: {e}")
            return team_side

    async def _create_match_channel_with_roles(self, guild: discord.Guild, team1_name: str, team2_name: str, team1_role: discord.Role, team2_role: discord.Role, week: int, prefix: str = "") -> discord.TextChannel:
        try:
            match_category = guild.get_channel(self.bot.MATCH_CATEGORY_ID)
            if not match_category:
                raise Exception(f"Match category {self.bot.MATCH_CATEGORY_ID} not found")
            
            if prefix:
                clean_prefix = self.bot._sanitize_channel_name(prefix)
                channel_name = f"{clean_prefix}-w{week}-{team1_name.lower()}-vs-{team2_name.lower()}"
            else:
                channel_name = f"w{week}-{team1_name.lower()}-vs-{team2_name.lower()}"
            
            channel_name = self.bot._sanitize_channel_name(channel_name)
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                team1_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                team2_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            if self.bot.EVENT_ORGA_ROLE_ID:
                orga_role = guild.get_role(self.bot.EVENT_ORGA_ROLE_ID)
                if orga_role:
                    overwrites[orga_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
            
            # NEUE ERGÄNZUNG: Zusätzliche Rollen aus Config hinzufügen
            additional_role_ids = self.bot.config.get('additional_match_role_ids', [])
            for role_id in additional_role_ids:
                if role_id:
                    additional_role = guild.get_role(role_id)
                    if additional_role:
                        overwrites[additional_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                        logger.info(f"✅ Added read/write access for role: {additional_role.name}")
                    else:
                        logger.warning(f"⚠️ Additional match role not found: ID {role_id}")
            
            channel = await guild.create_text_channel(
                name=channel_name,
                category=match_category,
                overwrites=overwrites,
                topic=f"Private match channel for {team1_name} vs {team2_name} - Week {week}" + (f" - {prefix}" if prefix else "")
            )
            
            logger.info(f"✅ Private match channel created: {channel.name}" + (f" with prefix '{prefix}'" if prefix else ""))
            return channel
            
        except Exception as e:
            logger.error(f"Error creating match channel: {e}")
            raise

    async def _send_wheel_gifs_to_channel(self, channel: discord.TextChannel, match_id: int, map_wheel_data: dict, sides_wheel_data: dict):
        try:
            from wheel.match_wheel_service import MatchWheelService
            
            try:
                map_gif = await MatchWheelService.create_map_wheel_gif(map_wheel_data)
                map_embed = MatchWheelService.create_map_selection_embed(map_wheel_data)
                
                await channel.send(embed=map_embed, file=map_gif)
                logger.info(f"✅ Map wheel GIF sent for match {match_id}")
                
            except Exception as map_error:
                logger.error(f"Error sending map wheel GIF: {map_error}")
                await channel.send(f"🗺️ **Map Selected:** {map_wheel_data['selected']}")
            
            try:
                sides_gif = await MatchWheelService.create_sides_wheel_gif(sides_wheel_data)
                sides_embed = MatchWheelService.create_sides_selection_embed(sides_wheel_data)
                
                await channel.send(embed=sides_embed, file=sides_gif)
                logger.info(f"✅ Sides wheel GIF sent for match {match_id}")
                
            except Exception as sides_error:
                logger.error(f"Error sending sides wheel GIF: {sides_error}")
                await channel.send(f"🔴 **Team Sides:** {sides_wheel_data['team1_name']}: {sides_wheel_data['selected']}, {sides_wheel_data['team2_name']}: {sides_wheel_data['team2_side']}")
            
        except Exception as e:
            logger.error(f"Error sending wheel GIFs: {e}")

    async def _create_and_send_streamer_post_with_lazy_persistence(self, match_id: int, match_data: dict):
        try:
            streamer_channel_id = self.bot.config['channels'].get('streamer_channel_id')
            if not streamer_channel_id:
                logger.info("No streamer channel configured")
                return
            
            streamer_channel = None
            for guild in self.bot.guilds:
                channel = guild.get_channel(streamer_channel_id)
                if channel:
                    streamer_channel = channel
                    break
            
            if not streamer_channel:
                logger.warning(f"Streamer channel {streamer_channel_id} not found")
                return
            
            streamer_message = await self.bot.send_streamer_match_with_lazy_persistence(
                streamer_channel, match_id, match_data
            )
            
            logger.info(f"✅ Streamer post created for match {match_id}")
            
        except Exception as e:
            logger.error(f"Error creating streamer post: {e}")