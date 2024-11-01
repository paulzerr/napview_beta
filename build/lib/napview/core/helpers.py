import os
import logging
import json 
from pathlib import Path
import threading 

def configure_logger(base_path):
    logger = logging.getLogger('napview_logger')
    if not logger.handlers:  # Avoid adding multiple handlers
        try:
            logger.setLevel(logging.DEBUG)
            base_path = Path(base_path) if not isinstance(base_path, Path) else base_path
            base_path.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(base_path / 'napview_log.log', mode='a')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(processName)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        except Exception as e:
            print(f"Error configuring logger: {e}")
    return logger


class ConfigManager:
    def __init__(self, base_path, config_defaults=None):
        self.logger = logging.getLogger('napview_logger')
        self.config_path = os.path.join(base_path, "config.json")
        self.config_lock = threading.RLock()  # Add reentrant lock

        if config_defaults:
            self.config = config_defaults
            try:
                self.save_config()
            except Exception as e:
                self.logger.error(f"Error saving config during initialization: {e}", exc_info=True)
        else:
            try:
                self.load_config()
            except Exception as e:
                self.logger.error(f"Error loading config during initialization: {e}", exc_info=True)

    def load_config(self, instance=None):
        with self.config_lock:
            try:
                if os.path.exists(self.config_path):
                    with open(self.config_path, 'r') as config_file:
                        self.config = json.load(config_file)
                else:
                    self.config = {}
                if instance is not None:
                    for key, value in self.config.items():
                        setattr(instance, key, value)
                    setattr(instance, 'config', self.config)
            except Exception as e:
                self.logger.error(f"Error loading config: {e}", exc_info=True)
                self.config = {}
            return self.config

    def save_config(self, config_dict=None):
        with self.config_lock:
            try:
                if config_dict:
                    self.config.update(config_dict)
                with open(self.config_path, 'w') as config_file:
                    json.dump(self.config, config_file, indent=4)
            except Exception as e:
                self.logger.error(f"Error saving config: {e}", exc_info=True)

