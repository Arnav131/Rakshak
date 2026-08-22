import importlib
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from django.conf import settings

from ai_integration.mock_sensor_generator import generate_sequence

class SensorSource(ABC):
    """
    Abstract base class for all sensor sources.
    
    This interface decouples the JourneyService from the mechanism
    that generates or ingests sensor data.
    """
    @abstractmethod
    def get_readings(
        self, 
        scenario: str = "healthy", 
        window_size: int = 16, 
        seed: Optional[int] = None
    ) -> List[Dict[str, float]]:
        """
        Get a sequence of sensor readings.
        """
        pass

class MockSensorSource(SensorSource):
    """
    Sensor source that generates mock data based on predefined scenarios.
    Used for hackathon demos and isolated testing.
    """
    def get_readings(
        self, 
        scenario: str = "healthy", 
        window_size: int = 16, 
        seed: Optional[int] = None
    ) -> List[Dict[str, float]]:
        return generate_sequence(scenario=scenario, window_size=window_size, seed=seed)

class ProductionSensorSource(SensorSource):
    """
    Placeholder for future production sensor ingestion.
    """
    def get_readings(
        self, 
        scenario: str = "healthy", 
        window_size: int = 16, 
        seed: Optional[int] = None
    ) -> List[Dict[str, float]]:
        raise NotImplementedError("Production sensor source is not implemented yet.")

def get_sensor_source() -> SensorSource:
    """
    Factory function to get the configured SensorSource instance.
    Reads SENSOR_SOURCE_CLASS from settings, defaulting to MockSensorSource.
    """
    class_path = getattr(settings, 'SENSOR_SOURCE_CLASS', 'ai_integration.sensor_source.MockSensorSource')
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        source_class = getattr(module, class_name)
        return source_class()
    except Exception as e:
        import logging
        logger = logging.getLogger("rakshak.ai_integration.sensor_source")
        logger.error(f"Failed to instantiate SensorSource {class_path}: {e}")
        # Fallback to MockSensorSource if config is invalid
        return MockSensorSource()
