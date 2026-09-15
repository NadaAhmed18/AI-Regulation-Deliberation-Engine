from src.controllers.analytics_controller import AnalyticsController
from src.controllers.simulation_controller import SimulationController


def get_simulation_controller() -> SimulationController:
    """Provides the singleton SimulationController encapsulating database operations."""
    return SimulationController()


def get_analytics_controller() -> AnalyticsController:
    """Provides the singleton AnalyticsController with caching and replay capabilities."""
    return AnalyticsController()