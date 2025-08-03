#!/usr/bin/env python3
"""
Tournament Bot - Hauptdatei mit farbigem Logging
Startet den Bot und lädt alle Komponenten
"""

import json
import logging
from bot.tournament_bot import TournamentBot
from cogs.tournament_cog import TournamentCog

from utils.colored_logger import setup_colored_logging

setup_colored_logging(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ config.json nicht gefunden!")
        print("Erstelle eine config.json basierend auf dem Beispiel.")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Fehler beim Laden der config.json: {e}")
        exit(1)
        
def load_token():
    try:
        with open('token.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ token.json nicht gefunden!")
        print("Erstelle eine token.json basierend auf dem Beispiel.")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Fehler beim Laden der token.json: {e}")
        exit(1)

async def setup_bot(bot):
    await bot.add_cog(TournamentCog(bot))
    logger.info("Tournament Cog geladen!")

def main():
    config = load_config()
    Token = load_token()
    
    bot = TournamentBot(config)
    
    bot.setup_hook = lambda: setup_bot(bot)
    
    TOKEN = Token['token']
    if not TOKEN or TOKEN == "DEIN_DISCORD_BOT_TOKEN_HIER":
        print("❌ Bitte setze deinen Discord Bot Token in der config.json!")
        exit(1)
    
    logger.info("Starte Tournament Bot...")
    bot.run(TOKEN)

if __name__ == "__main__":
    main()