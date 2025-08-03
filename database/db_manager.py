# database/db_manager.py
"""
Enhanced Database Manager
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = 'tournament.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.setup_database()
        logger.info(f"Datenbank initialisiert: {db_path}")
        
    def migrate_ui_messages_table(self):
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("PRAGMA table_info(ui_messages)")
            columns = cursor.fetchall()
            
            guild_id_column = None
            for column in columns:
                if column[1] == 'guild_id':
                    guild_id_column = column
                    break
            
            if guild_id_column and guild_id_column[3] == 1:
                logger.info("🔄 Migrating ui_messages table to allow NULL guild_id...")
                
                cursor.execute('''
                    CREATE TABLE ui_messages_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id INTEGER UNIQUE NOT NULL,
                        channel_id INTEGER NOT NULL,
                        guild_id INTEGER,
                        message_type TEXT NOT NULL,
                        related_match_id INTEGER,
                        data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')
                
                cursor.execute('''
                    INSERT INTO ui_messages_new 
                    SELECT * FROM ui_messages
                ''')
                
                cursor.execute('DROP TABLE ui_messages')
                
                cursor.execute('ALTER TABLE ui_messages_new RENAME TO ui_messages')
                
                self.conn.commit()
                logger.info("✅ ui_messages table migration completed")
            else:
                logger.info("ℹ️ ui_messages table migration not needed")
                
        except Exception as e:
            logger.error(f"Error migrating ui_messages table: {e}")
            self.conn.rollback()
    
    def setup_database(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                captain_id INTEGER NOT NULL,
                members TEXT,
                active BOOLEAN DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team1_id INTEGER,
                team2_id INTEGER,
                match_date TEXT,
                match_time TEXT,
                map_name TEXT,
                team1_side TEXT,
                team2_side TEXT,
                private_channel_id INTEGER,
                public_message_id INTEGER,
                status TEXT DEFAULT 'pending',
                result TEXT,
                replay_url TEXT,
                week_number INTEGER,
                FOREIGN KEY (team1_id) REFERENCES teams (id),
                FOREIGN KEY (team2_id) REFERENCES teams (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_streamers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                streamer_id INTEGER,
                team_side TEXT,
                stream_url TEXT,
                steam_id64 TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches (id),
                UNIQUE(match_id, team_side)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_streamer_messages (
                match_id INTEGER PRIMARY KEY,
                streamer_message_id INTEGER,
                FOREIGN KEY (match_id) REFERENCES matches (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tournament_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ui_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER UNIQUE NOT NULL,
                channel_id INTEGER NOT NULL,
                guild_id INTEGER,
                message_type TEXT NOT NULL,
                related_match_id INTEGER,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                view_type TEXT NOT NULL,
                view_data TEXT,
                match_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (message_id) REFERENCES ui_messages (message_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_embeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                embed_data TEXT NOT NULL,
                embed_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES ui_messages (message_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ongoing_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                interaction_type TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (match_id) REFERENCES matches (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS button_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                button_id TEXT NOT NULL,
                button_label TEXT,
                is_disabled BOOLEAN DEFAULT 0,
                button_style TEXT,
                button_data TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES ui_messages (message_id)
            )
        ''')
        
        self._add_missing_columns()
        
        self.migrate_ui_messages_table()
        
        self.conn.commit()
        logger.info("✅ Database setup complete with persistence tables")
    
    def _add_missing_columns(self):
        cursor = self.conn.cursor()
        
        cursor.execute("PRAGMA table_info(match_streamers)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'stream_url' not in columns:
            cursor.execute('ALTER TABLE match_streamers ADD COLUMN stream_url TEXT')
            logger.info("Stream URL Spalte zur match_streamers Tabelle hinzugefügt")
        
        if 'steam_id64' not in columns:
            cursor.execute('ALTER TABLE match_streamers ADD COLUMN steam_id64 TEXT')
            logger.info("SteamID64 Spalte zur match_streamers Tabelle hinzugefügt")
    
    def register_ui_message(self, message_id: int, channel_id: int, guild_id: int, 
                           message_type: str, data: Dict, match_id: int = None) -> int:
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO ui_messages 
            (message_id, channel_id, guild_id, message_type, related_match_id, data, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, channel_id, guild_id, message_type, match_id, 
              json.dumps(data), datetime.now().isoformat()))
        
        self.conn.commit()
        
        ui_id = cursor.lastrowid
        logger.info(f"✅ UI Message registriert: {message_type} (ID: {ui_id}, Message: {message_id})")
        return ui_id
    
    def save_button_states(self, message_id: int, buttons: List[Dict]):
        cursor = self.conn.cursor()
        
        cursor.execute('DELETE FROM button_states WHERE message_id = ?', (message_id,))
        
        for button in buttons:
            cursor.execute('''
                INSERT INTO button_states 
                (message_id, button_id, button_label, is_disabled, button_style, button_data)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (message_id, button['id'], button.get('label'), 
                  button.get('disabled', False), button.get('style'), 
                  json.dumps(button.get('data', {}))))
        
        self.conn.commit()
        logger.debug(f"✅ Button states gespeichert für Message {message_id}: {len(buttons)} buttons")
    
    def get_button_states(self, message_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT button_id, button_label, is_disabled, button_style, button_data
            FROM button_states 
            WHERE message_id = ?
        ''', (message_id,))
        
        results = cursor.fetchall()
        buttons = []
        for row in results:
            buttons.append({
                'id': row[0],
                'label': row[1],
                'disabled': bool(row[2]),
                'style': row[3],
                'data': json.loads(row[4]) if row[4] else {}
            })
        return buttons
    
    def get_all_persistent_messages(self) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT ui.message_id, ui.channel_id, ui.guild_id, ui.message_type, 
                   ui.related_match_id, ui.data,
                   av.view_type, av.view_data,
                   me.embed_data, me.embed_type
            FROM ui_messages ui
            LEFT JOIN active_views av ON ui.message_id = av.message_id AND av.is_active = 1
            LEFT JOIN message_embeds me ON ui.message_id = me.message_id
            WHERE ui.is_active = 1
            ORDER BY ui.updated_at DESC
        ''', ())
        
        results = cursor.fetchall()
        messages = []
        
        for row in results:
            message_data = {
                'message_id': row[0],
                'channel_id': row[1],
                'guild_id': row[2],
                'message_type': row[3],
                'match_id': row[4],
                'ui_data': json.loads(row[5]) if row[5] else {},
                'view_type': row[6],
                'view_data': json.loads(row[7]) if row[7] else {},
                'embed_data': json.loads(row[8]) if row[8] else {},
                'embed_type': row[9]
            }
            
            message_data['button_states'] = self.get_button_states(row[0])
            
            messages.append(message_data)
        
        return messages
    
    def get_ui_messages_by_type(self, message_type: str, is_active: bool = True) -> List[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT message_id, channel_id, guild_id, related_match_id, data 
            FROM ui_messages 
            WHERE message_type = ? AND is_active = ?
        ''', (message_type, is_active))
        return cursor.fetchall()
    
    def get_ongoing_interactions(self, match_id: int = None, interaction_type: str = None) -> List[Tuple]:

        cursor = self.conn.cursor()
        base_query = '''
            SELECT id, match_id, interaction_type, message_id, data, expires_at
            FROM ongoing_interactions 
            WHERE is_active = 1
            AND (expires_at IS NULL OR expires_at > ?)
        '''
        params = [datetime.now().isoformat()]
        
        if match_id:
            base_query += ' AND match_id = ?'
            params.append(match_id)
        
        if interaction_type:
            base_query += ' AND interaction_type = ?'
            params.append(interaction_type)
        
        cursor.execute(base_query, params)
        return cursor.fetchall()
    
    def deactivate_ui_message(self, message_id: int):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE ui_messages SET is_active = 0 WHERE message_id = ?', (message_id,))
        cursor.execute('UPDATE active_views SET is_active = 0 WHERE message_id = ?', (message_id,))
        self.conn.commit()
        logger.info(f"✅ UI Message {message_id} deaktiviert")
    
    def complete_ongoing_interaction(self, interaction_id: int):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE ongoing_interactions SET is_active = 0 WHERE id = ?', (interaction_id,))
        self.conn.commit()
        logger.info(f"✅ Ongoing Interaction {interaction_id} abgeschlossen")
    
    def cleanup_expired_data(self):
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        cursor.execute('UPDATE active_views SET is_active = 0 WHERE expires_at < ?', (now,))
        
        cursor.execute('UPDATE ongoing_interactions SET is_active = 0 WHERE expires_at < ?', (now,))
        
        self.conn.commit()
        logger.info("✅ Expired data cleaned up")
    
    def create_team(self, name: str, captain_id: int, members: List[int] = None) -> int:
        if members is None:
            members = []
        
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO teams (name, captain_id, members) VALUES (?, ?, ?)',
            (name, captain_id, json.dumps(members))
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def get_all_teams(self) -> List[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM teams WHERE active = 1 ORDER BY name')
        return cursor.fetchall()
    
    def team_exists(self, name: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM teams WHERE name = ? AND active = 1', (name,))
        return cursor.fetchone() is not None
    
    def get_team_by_name(self, name: str) -> Optional[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM teams WHERE name = ? AND active = 1', (name,))
        return cursor.fetchone()
    
    def create_match(self, team1_id: int, team2_id: int, match_date: str, 
                    map_name: str, team1_side: str, team2_side: str, 
                    private_channel_id: int, week_number: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO matches (team1_id, team2_id, match_date, map_name, 
                               team1_side, team2_side, private_channel_id, week_number) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (team1_id, team2_id, match_date, map_name, team1_side, team2_side, 
              private_channel_id, week_number))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_match_details(self, match_id: int) -> Optional[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT m.*, t1.name as team1_name, t2.name as team2_name
            FROM matches m
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            WHERE m.id = ?
        ''', (match_id,))
        return cursor.fetchone()
    
    def get_matches_by_week(self, week_number: int) -> List[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT m.*, t1.name as team1_name, t2.name as team2_name
            FROM matches m
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            WHERE m.week_number = ?
            ORDER BY m.match_date, m.match_time
        ''', (week_number,))
        return cursor.fetchall()
    
    def update_match_result(self, match_id: int, result_data: Dict, replay_url: str = None):
        cursor = self.conn.cursor()
        cursor.execute(
            'UPDATE matches SET result = ?, replay_url = ?, status = ? WHERE id = ?',
            (json.dumps(result_data), replay_url, 'completed', match_id)
        )
        self.conn.commit()
    
    def confirm_match_result(self, match_id: int):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE matches SET status = ? WHERE id = ?', ('confirmed', match_id))
        self.conn.commit()
    
    def update_public_message_id(self, match_id: int, message_id: int):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE matches SET public_message_id = ? WHERE id = ?', (message_id, match_id))
        self.conn.commit()
    
    def update_match_time(self, match_id: int, match_time: str):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE matches SET match_time = ? WHERE id = ?', (match_time, match_id))
        self.conn.commit()
        logger.info(f"✅ Match time updated for match {match_id}: {match_time}")
    
    def add_match_streamer_with_side_url_and_steamid(self, match_id: int, streamer_id: int, team_side: str, stream_url: str, steam_id64: str):
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO match_streamers (match_id, streamer_id, team_side, stream_url, steam_id64) VALUES (?, ?, ?, ?, ?)',
            (match_id, streamer_id, team_side, stream_url, steam_id64)
        )
        self.conn.commit()
    
    def remove_match_streamer(self, match_id: int, streamer_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            'DELETE FROM match_streamers WHERE match_id = ? AND streamer_id = ?',
            (match_id, streamer_id)
        )
        self.conn.commit()
    
    def get_match_streamers_detailed(self, match_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT streamer_id, team_side, stream_url, steam_id64, registered_at FROM match_streamers WHERE match_id = ?',
            (match_id,)
        )
        results = cursor.fetchall()
        
        return [
            {
                'streamer_id': row[0],
                'team_side': row[1] if row[1] else '',
                'stream_url': row[2] if row[2] else '',
                'steam_id64': row[3] if row[3] else '',
                'registered_at': row[4]
            }
            for row in results
        ]
    
    def set_match_streamer_message_id(self, match_id: int, message_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO match_streamer_messages (match_id, streamer_message_id) VALUES (?, ?)',
            (match_id, message_id)
        )
        self.conn.commit()
    
    def get_match_streamer_message_id(self, match_id: int) -> Optional[int]:
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT streamer_message_id FROM match_streamer_messages WHERE match_id = ?',
            (match_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else None
    
    def set_setting(self, key: str, value: str):
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO tournament_settings (key, value) VALUES (?, ?)',
            (key, value)
        )
        self.conn.commit()
    
    def get_setting(self, key: str) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM tournament_settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def backup_database(self, backup_path: str):
        backup_conn = sqlite3.connect(backup_path)
        self.conn.backup(backup_conn)
        backup_conn.close()
        logger.info(f"Datenbank-Backup erstellt: {backup_path}")
    
    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Datenbankverbindung geschlossen")
    
    def __del__(self):
        self.close()