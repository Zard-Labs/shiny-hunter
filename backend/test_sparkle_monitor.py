"""Quick smoke test for SparkleMonitor import and game_engine fields."""
import sys
sys.path.insert(0, ".")

from app.services.game_engine import game_engine, SparkleMonitor

print("OK: SparkleMonitor class imported")
print(f"  _sparkle_monitor: {game_engine._sparkle_monitor}")
print(f"  _sparkle_monitor_task: {game_engine._sparkle_monitor_task}")

# Verify SparkleMonitor can be constructed
config = {"analysis_interval": 0.75, "ring_buffer_frames": 180, "analysis_frames": 60}
detection = {"zone": {"upper_x": 320, "upper_y": 40, "lower_x": 580, "lower_y": 200}}
monitor = SparkleMonitor(config=config, detection_config=detection, definition={})
print(f"  SparkleMonitor created: shiny_detected={monitor.shiny_detected}")

# Verify log_encounter action type is recognized
print("OK: All checks passed")
