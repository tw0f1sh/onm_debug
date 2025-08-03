#!/usr/bin/env python3
"""
Colored Logger
"""

import logging
import sys
import os
from typing import Dict


if os.name == 'nt':  
    try:
        import colorama
        colorama.init(autoreset=True)
    except ImportError:
        
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except:
            pass

class ColoredFormatter(logging.Formatter):
    
    
    
    COLORS: Dict[str, str] = {
        'DEBUG': '\033[95m',      
        'INFO': '\033[94m',       
        'WARNING': '\033[93m',    
        'ERROR': '\033[91m',      
        'CRITICAL': '\033[95m'    
    }
    
    RESET = '\033[0m'  
    
    def __init__(self, fmt=None, datefmt=None):
        if fmt is None:
            
            fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        super().__init__(fmt, datefmt)
    
    def format(self, record):
        
        
        log_message = super().format(record)
        
        
        if not self._supports_color():
            return log_message
        
        
        level_name = record.levelname
        color = self.COLORS.get(level_name, '')
        
        if color:
            
            colored_message = f"{color}{log_message}{self.RESET}"
            return colored_message
        
        return log_message
    
    def _supports_color(self):
        
        
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False
        
        
        if os.name == 'nt':
            
            return True
        
        
        term = os.environ.get('TERM', '')
        return term != 'dumb' and term != ''


def setup_colored_logging(level=logging.INFO):
    
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    
    colored_formatter = ColoredFormatter()
    console_handler.setFormatter(colored_formatter)
    
    
    root_logger.addHandler(console_handler)
    
    return root_logger
    
if __name__ == "__main__":
    
    test_colors()