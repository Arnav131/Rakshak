# backend/ai_integration/journey_service.py
"""
Rakshak AI Integration — Journey Service
============================================
Orchestrates simulated train journeys for the hackathon demo.

Generates mock sensor readings, feeds them through PredictionService,
and creates alerts/tickets when anomalies are detected.

ARCHITECTURE POSITION:
    Journey API View
        ↓
    JourneyService  ← YOU ARE HERE
        ↓
    MockSensorGenerator (generates readings)
        ↓
    PredictionService (runs inference)
        ↓
    AlertService / TicketService (creates DB records if anomaly)

AI TEAM NOTE:
    Purpose:     Simulate end-to-end train journeys for hackathon demo.
    How it works: Generates a window of sequential sensor readings for a
                  scenario, feeds each reading to PredictionService (which
                  internally buffers inside the provider), then processes
                  the final prediction for alert/ticket creation.
    Why introduced: Demo requires journey simulation without real sensors.
    Future LLM compatibility: JourneyService calls PredictionService only.
                              Swapping the AI provider (pickle → LLM → cloud)
                              requires ZERO changes here.

CHANGE SUMMARY:
    Reason: Hackathon journey simulation feature.
    Architecture impact: New service module. Depends on PredictionService,
                         AlertService, TicketService, MockSensorGenerator.
                         Does NOT depend on any AI model or provider directly.
    Future migration notes: Replace MockSensorGenerator with real sensor
                            ingestion when hardware is available.
    Backward compatibility: N/A — new module.

# ---------------------------------------------------------------------------
# DATABASE MIGRATION NOTE
#
# This module reads from:
#   - rakshak_station (via Station.objects.get)
#   - rakshak_track_section (via TrackSection.objects.filter)
#
# This module writes to DB indirectly via AlertService and TicketService.
#
# Current DB: PostgreSQL
# Future DB: None
# Whether this code is PostgreSQL compatible: YES
# Whether teammate needs to modify anything: NO
# Migration required: NO
# ---------------------------------------------------------------------------
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ai_integration.incident_orchestrator import IncidentOrchestrator
from ai_integration.sensor_source import get_sensor_source
from ai_integration.prediction_service import PredictionService
from ai_integration.providers import PredictionResponse

logger = logging.getLogger("rakshak.ai_integration.journey")


@dataclass
class JourneyResult:
    """
    Result of a simulated journey.

    Contains the final prediction, alert/ticket creation status,
    and all intermediate readings for debugging.
    """

    start_station_name: str = ""
    end_station_name: str = ""
    scenario: str = "healthy"
    sensor_id: str = "SIM-001"
    readings_sent: int = 0
    prediction: Optional[PredictionResponse] = None
    alert_created: bool = False
    alert_id: Optional[int] = None
    ticket_created: bool = False
    ticket_id: Optional[int] = None
    track_section_id: Optional[int] = None
    buffering_responses: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for API response."""
        result = {
            "start_station": self.start_station_name,
            "end_station": self.end_station_name,
            "scenario": self.scenario,
            "sensor_id": self.sensor_id,
            "readings_sent": self.readings_sent,
            "prediction": self.prediction.to_dict() if self.prediction else None,
            "alert_created": self.alert_created,
            "alert_id": self.alert_id,
            "ticket_created": self.ticket_created,
            "ticket_id": self.ticket_id,
            "buffering_responses": self.buffering_responses,
        }
        if self.errors:
            result["errors"] = self.errors
        return result


class JourneyService:
    """
    Orchestrates simulated train journeys.

    Usage:
        service = JourneyService()
        result = service.start_journey(
            start_station_id=1,
            end_station_id=5,
            scenario="gauge_widening",
        )

        if result.alert_created:
            print(f"Alert created: {result.alert_id}")
    """

    def __init__(self):
        self._prediction_service = PredictionService()
        self._incident_orchestrator = IncidentOrchestrator()
        self._sensor_source = get_sensor_source()

    def start_journey(
        self,
        start_station_id: int,
        end_station_id: int,
        scenario: str = "healthy",
        sensor_id: str = "SIM-001",
        seed: Optional[int] = None,
    ) -> JourneyResult:
        """
        Execute a simulated journey between two stations.

        Steps:
            1. Resolve station names and find connecting track section
            2. Generate mock sensor readings for the scenario
            3. Feed each reading through PredictionService
            4. Create alert if anomaly detected
            5. Create ticket if critical prediction

        Args:
            start_station_id: PK of the boarding station.
            end_station_id:   PK of the destination station.
            scenario:         Simulation scenario key.
            sensor_id:        Simulated sensor identifier.
            seed:             Optional random seed for reproducibility.

        Returns:
            JourneyResult — always. Never raises exceptions.
        """
        result = JourneyResult(scenario=scenario, sensor_id=sensor_id)

        # --- Step 1: Resolve stations and track section ---
        try:
            from railway.models import Station, TrackSection
            from django.db.models import Q

            start_station = Station.objects.get(pk=start_station_id)
            end_station = Station.objects.get(pk=end_station_id)
            result.start_station_name = start_station.station_name
            result.end_station_name = end_station.station_name

            # Find a track section connecting these stations (either direction)
            track_section = TrackSection.objects.filter(
                Q(start_station=start_station, end_station=end_station)
                | Q(start_station=end_station, end_station=start_station)
            ).first()

            if track_section:
                result.track_section_id = track_section.pk
            else:
                # No direct track section — use start station's first section
                track_section = TrackSection.objects.filter(
                    Q(start_station=start_station) | Q(end_station=start_station)
                ).first()
                if track_section:
                    result.track_section_id = track_section.pk
                else:
                    result.errors.append(
                        f"No track section found for stations "
                        f"{start_station_id} → {end_station_id}"
                    )

        except Station.DoesNotExist:
            result.errors.append(
                f"Station not found: start={start_station_id}, end={end_station_id}"
            )
            return result
        except Exception as e:
            result.errors.append(f"Station lookup failed: {e}")
            return result

        # --- Step 2: Generate sensor readings ---
        try:
            provider_meta = self._prediction_service.get_provider_metadata()
            window_size = provider_meta.get("window_size", 16)
            readings = self._sensor_source.get_readings(
                scenario=scenario,
                window_size=window_size,
                seed=seed,
            )
        except ValueError as e:
            result.errors.append(str(e))
            return result

        # --- Step 3: Feed readings through PredictionService ---
        last_response = None

        for reading in readings:
            response = self._prediction_service.predict_for_sensor(
                sensor_id=sensor_id,
                ambient_temp=reading["ambient_temp"],
                humidity=reading["humidity"],
                vibration_rms=reading["vibration_rms"],
                gauge_width=reading["gauge_width"],
                track_section_id=result.track_section_id,
            )
            result.readings_sent += 1

            # Check if still buffering
            if response.metadata.get("status") == "buffering":
                result.buffering_responses += 1
            else:
                last_response = response

        result.prediction = last_response

        # --- Step 4 & 5: Create alert / ticket if necessary ---
        if last_response and result.track_section_id:
            incident_result = self._incident_orchestrator.process_prediction(
                response=last_response,
                track_section_id=result.track_section_id
            )
            result.alert_created = incident_result.get("alert_created", False)
            result.alert_id = incident_result.get("alert_id")
            result.ticket_created = incident_result.get("ticket_created", False)
            result.ticket_id = incident_result.get("ticket_id")
            result.errors.extend(incident_result.get("errors", []))

        logger.info(
            f"JourneyService: Journey complete — "
            f"{result.start_station_name} → {result.end_station_name}, "
            f"scenario={scenario}, readings={result.readings_sent}, "
            f"anomaly={last_response.is_anomaly if last_response else 'N/A'}"
        )

        return result

    @staticmethod
    def get_scenarios() -> List[Dict[str, str]]:
        """Return available simulation scenarios."""
        # Now depends on mock_sensor_generator just for listing, or we can import it locally
        from ai_integration.mock_sensor_generator import list_scenarios
        return list_scenarios()
