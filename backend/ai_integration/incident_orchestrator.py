import logging
from typing import Dict, Any, Optional

from ai_integration.alert_service import AlertService
from ai_integration.ticket_service import TicketService
from ai_integration.providers import PredictionResponse

logger = logging.getLogger("rakshak.ai_integration.orchestrator")


class IncidentOrchestrator:
    """
    Orchestrates the creation of alerts and tickets based on AI predictions.
    
    This layer decouples the incident creation business logic from the
    journey simulation logic, preventing direct dependency of JourneyService
    on AlertService and TicketService.
    """

    def __init__(self):
        self._alert_service = AlertService()
        self._ticket_service = TicketService()

    def process_prediction(
        self, 
        response: PredictionResponse, 
        track_section_id: Optional[int],
        auto_alert: bool = True,
        auto_ticket: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluate a PredictionResponse and create alerts/tickets if necessary.
        
        Args:
            response: The standardized AI PredictionResponse.
            track_section_id: The ID of the track section to tie the incident to.
            auto_alert: Whether to create alerts automatically.
            auto_ticket: Whether to create tickets automatically.
            
        Returns:
            Dict containing creation flags, IDs, and any errors encountered.
        """
        result = {
            "alert_created": False,
            "alert_id": None,
            "ticket_created": False,
            "ticket_id": None,
            "errors": []
        }

        if not response or not track_section_id:
            return result

        # Create alert if anomaly detected
        if auto_alert and response.is_anomaly:
            try:
                alert_pk = self._alert_service.create_anomaly_alert(
                    response=response,
                    track_section_id=track_section_id,
                )
                if alert_pk:
                    result["alert_created"] = True
                    result["alert_id"] = alert_pk
            except Exception as e:
                logger.error(f"IncidentOrchestrator: Alert creation failed: {e}")
                result["errors"].append(f"Alert creation failed: {e}")

        # Also check for predictive alert
        if auto_alert and response.needs_alert:
            try:
                self._alert_service.create_predictive_alert(
                    response=response,
                    track_section_id=track_section_id,
                )
            except Exception as e:
                logger.error(f"IncidentOrchestrator: Predictive alert creation failed: {e}")
                result["errors"].append(f"Predictive alert creation failed: {e}")

        # Create ticket if critical/needs alert
        if auto_ticket and response.needs_alert:
            try:
                ticket_pk = self._ticket_service.create_ticket_from_prediction(
                    response=response,
                    track_section_id=track_section_id,
                )
                if ticket_pk:
                    result["ticket_created"] = True
                    result["ticket_id"] = ticket_pk
            except Exception as e:
                logger.error(f"IncidentOrchestrator: Ticket creation failed: {e}")
                result["errors"].append(f"Ticket creation failed: {e}")

        return result
