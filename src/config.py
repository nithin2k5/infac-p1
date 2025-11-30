"""Configuration management for the desktop application."""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

class Config:
    """Configuration manager for the application."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Path to configuration JSON file. If None, uses default locations.
        """
        if config_path is None:
            # Try default locations
            default_paths = [
                os.path.join(os.path.dirname(__file__), "..", "config.json"),
                os.path.expanduser("~/.rpi-monitor-ui/config.json"),
                "/etc/rpi-monitor-ui/config.json",
            ]
            for path in default_paths:
                if os.path.exists(path):
                    config_path = path
                    break
            else:
                # Use project config.json if no system config found
                config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> None:
        """Load configuration from JSON file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self._config = json.load(f)
            else:
                # Use defaults if file doesn't exist
                self._config = self._get_defaults()
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
    
    def _get_defaults(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "database": {
                "type": "mysql",
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "",
                "database": "rpi_monitor"
            },
            "ui": {
                "auto_refresh_interval": 30,
                "default_page_size": 100,
                "show_utc": False,
                "window_width": 1200,
                "window_height": 800
            },
            "default_filters": {
                "input_id": None,
                "start_time": None,
                "end_time": None,
                "event_type": None
            }
        }
    
    def save(self) -> None:
        """Save current configuration to file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            raise IOError(f"Failed to save configuration: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        keys = key.split('.')
        value = self._config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value using dot notation."""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        return self._config.get("database", {})
    
    def get_ui_config(self) -> Dict[str, Any]:
        """Get UI configuration."""
        return self._config.get("ui", {})


