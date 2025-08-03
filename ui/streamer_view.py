"""
Streamer View - Legacy/Placeholder Datei
Das alte System wurde durch streamer_management.py ersetzt
"""

import discord
import logging

logger = logging.getLogger(__name__)

class LegacyStreamerSignupView(discord.ui.View):

    def __init__(self, match_id: int, bot):
        super().__init__(timeout=None)
        self.match_id = match_id
        self.bot = bot

StreamerSignupView = LegacyStreamerSignupView
StreamerManagementView = LegacyStreamerSignupView