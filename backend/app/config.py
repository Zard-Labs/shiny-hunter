"""Configuration management for the application."""
import yaml
from pathlib import Path
from typing import Dict, Any, List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from config.yaml."""
    
    # Hardware settings
    esp32_ip: str = "192.168.4.1"
    esp32_port: int = 80
    esp32_websocket_port: int = 81
    communication_mode: str = "wifi"
    serial_port: str = "COM6"
    baud_rate: int = 115200
    camera_index: int = 0
    connection_retry_timeout: int = 15
    
    # Automation settings
    button_hold_duration: float = 0.1
    button_release_delay: float = 0.1
    soft_reset_hold: float = 0.5
    soft_reset_wait: float = 3.0
    
    # Detection settings
    shiny_zone: Dict[str, int] = Field(default_factory=dict)
    gender_zone: Dict[str, int] = Field(default_factory=dict)
    nature_text_zone: Dict[str, int] = Field(default_factory=dict)
    yellow_star_threshold: int = 20
    blue_gender_threshold: int = 10
    red_gender_threshold: int = 10
    template_thresholds: Dict[str, float] = Field(default_factory=dict)
    
    # Logging settings
    log_level: str = "INFO"
    log_file: str = "bot_history.log"
    screenshot_directory: str = "encounters"
    save_all_encounters: bool = True
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    websocket_heartbeat: int = 5
    
    class Config:
        env_file = ".env"


def load_config() -> Settings:
    """Load configuration from config.yaml file."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    
    if not config_path.exists():
        print(f"Warning: config.yaml not found at {config_path}, using defaults")
        return Settings()
    
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    # Flatten nested structure for Pydantic
    flat_config = {}
    
    # Hardware
    if 'hardware' in config_data:
        hw = config_data['hardware']
        flat_config['esp32_ip'] = hw.get('esp32_ip', '192.168.4.1')
        flat_config['esp32_port'] = hw.get('esp32_port', 80)
        flat_config['esp32_websocket_port'] = hw.get('esp32_websocket_port', 81)
        flat_config['communication_mode'] = hw.get('communication_mode', 'wifi')
        flat_config['serial_port'] = hw.get('serial_port', 'COM6')
        flat_config['baud_rate'] = hw.get('baud_rate', 115200)
        flat_config['camera_index'] = hw.get('camera_index', 0)
        flat_config['connection_retry_timeout'] = hw.get('connection_retry_timeout', 15)
    
    # Automation
    if 'automation' in config_data:
        auto = config_data['automation']
        flat_config['button_hold_duration'] = auto.get('button_hold_duration', 0.1)
        flat_config['button_release_delay'] = auto.get('button_release_delay', 0.1)
        flat_config['soft_reset_hold'] = auto.get('soft_reset_hold', 0.5)
        flat_config['soft_reset_wait'] = auto.get('soft_reset_wait', 3.0)
    
    # Detection
    if 'detection' in config_data:
        detect = config_data['detection']
        flat_config['shiny_zone'] = detect.get('shiny_zone', {})
        flat_config['gender_zone'] = detect.get('gender_zone', {})
        flat_config['nature_text_zone'] = detect.get('nature_text_zone', {})
        flat_config['yellow_star_threshold'] = detect.get('yellow_star_threshold', 20)
        flat_config['blue_gender_threshold'] = detect.get('blue_gender_threshold', 10)
        flat_config['red_gender_threshold'] = detect.get('red_gender_threshold', 10)
        flat_config['template_thresholds'] = detect.get('template_thresholds', {})
    
    # Logging
    if 'logging' in config_data:
        log = config_data['logging']
        flat_config['log_level'] = log.get('level', 'INFO')
        flat_config['log_file'] = log.get('log_file', 'bot_history.log')
        flat_config['screenshot_directory'] = log.get('screenshot_directory', 'encounters')
        flat_config['save_all_encounters'] = log.get('save_all_encounters', True)
    
    # Server
    if 'server' in config_data:
        srv = config_data['server']
        flat_config['host'] = srv.get('host', '0.0.0.0')
        flat_config['port'] = srv.get('port', 8000)
        flat_config['cors_origins'] = srv.get('cors_origins', ['http://localhost:3000'])
        flat_config['websocket_heartbeat'] = srv.get('websocket_heartbeat', 5)
    
    return Settings(**flat_config)


# Global settings instance
settings = load_config()
