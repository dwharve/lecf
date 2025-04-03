"""Base manager class to standardize service implementations."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
from utils import logger, get_env, get_env_int

class BaseManager(ABC):
    """Base class for all service managers."""
    
    def __init__(self, service_name: str):
        """
        Initialize the base manager.
        
        Args:
            service_name: The name of the service
        """
        self.service_name = service_name
        self._setup_interval()
        
        logger.debug(f"{self.service_name} manager initialized", 
                   extra={'interval': self.get_schedule_info()})
    
    @abstractmethod
    def _setup_interval(self) -> None:
        """
        Set up the check interval for this service.
        This must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    def _execute_cycle(self) -> None:
        """
        Execute a single operational cycle.
        This must be implemented by subclasses.
        """
        pass
    
    def run(self) -> None:
        """
        Run a single service cycle.
        """
        logger.info(f"Running {self.service_name} cycle")
        try:
            self._execute_cycle()
            logger.info(f"{self.service_name} cycle completed")
        except Exception as e:
            logger.error(f"Error during {self.service_name} cycle", 
                       extra={'error': str(e), 'error_type': type(e).__name__})
    
    def get_schedule_info(self) -> Tuple[int, str]:
        """
        Get scheduling information for this service.
        
        Returns:
            Tuple of (interval_value, interval_unit)
        """
        return (self.check_interval, self.interval_unit) 