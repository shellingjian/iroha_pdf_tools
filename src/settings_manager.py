
import json
import os
import customtkinter as ctk
from config import GlobalConfig

class SettingsManager:
    _instance = None
    SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_settings.json")
    
    DEFAULT_SETTINGS = {
        "appearance_mode": "System",  # System, Light, Dark
        "color_theme": "blue",
        "last_file_directory": os.path.expanduser("~"),
        "window_geometry": GlobalConfig.APP_SIZE
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance.settings = cls._instance.DEFAULT_SETTINGS.copy()
            cls._instance.load_settings()
        return cls._instance

    def load_settings(self):
        """Load settings from JSON file"""
        if os.path.exists(self.SETTINGS_FILE):
            try:
                with open(self.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self.settings.update(saved)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save_settings(self):
        """Save current settings to JSON file"""
        try:
            with open(self.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key):
        return self.settings.get(key, self.DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.settings[key] = value
        self.save_settings()

    def update_last_dir(self, file_path):
        if file_path:
            directory = os.path.dirname(os.path.abspath(file_path))
            self.set("last_file_directory", directory)

    def apply_startup_settings(self):
        """Apply theme settings on app startup"""
        mode = self.get("appearance_mode")
        ctk.set_appearance_mode(mode)
        # Note: set_default_color_theme requires restart usually, or is static in config
        # We only persist Appearance Mode for now dynamic switching
