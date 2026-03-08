"""Application configuration and user data paths."""

import os
from pathlib import Path


class Config:
    """Application configuration."""
    
    APP_NAME = "Dad's Money"
    APP_VERSION = "0.1.0"
    
    @staticmethod
    def get_user_data_dir() -> Path:
        """Get the user data directory for the application."""
        if os.name == 'nt':  # Windows
            base_dir = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
        elif os.name == 'posix':
            if 'Darwin' in os.uname().sysname:  # macOS
                base_dir = Path.home() / 'Library' / 'Application Support'
            else:  # Linux
                base_dir = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
        else:
            base_dir = Path.home()
        
        app_dir = base_dir / "DadsMoney"
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir
    
    @staticmethod
    def get_database_path() -> Path:
        """Get the default database file path."""
        return Config.get_user_data_dir() / "dadsmoney.db"
    
    @staticmethod
    def get_log_path() -> Path:
        """Get the log file path."""
        return Config.get_user_data_dir() / "dadsmoney.log"
