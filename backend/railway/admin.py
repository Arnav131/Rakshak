from django.contrib import admin

from .models import (
    Zone, Division, Station, TrackSection, Asset,
    SensorType, Sensor, SensorCalibration, SensorReading,
    Alert, AlertEscalation, MaintenanceTeam, Ticket, TicketStatusLog,
    MLModel, MLModelRun, AnomalyPrediction, AuditLog,
)


# Register Zone model in Django admin interface
# The @admin.register decorator automatically registers the model with the admin site
@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    # list_display: Defines which fields appear as columns in the admin list view
    # Users will see code, name, headquarters, and whether the zone is active
    list_display = ('code', 'name', 'headquarters', 'is_active')
    
    # list_filter: Adds a sidebar filter for the is_active field
    # Allows filtering zones by active/inactive status
    list_filter = ('is_active',)
    
    # search_fields: Enables search functionality on code and name fields
    # Users can search for zones by typing partial codes or names
    search_fields = ('code', 'name')


# Register Division model
@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    # Shows division details including its parent zone in the list view
    list_display = ('code', 'name', 'zone', 'headquarters', 'is_active')
    
    # Filter by parent zone or active status
    # zone filter shows a dropdown of all zones to filter divisions by
    list_filter = ('zone', 'is_active')
    
    # Search by division code or name
    search_fields = ('code', 'name')


# Register Station model
@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    # Displays station code, name, parent division, junction status, and active status
    # is_junction indicates if multiple lines meet at this station
    list_display = ('station_code', 'station_name', 'division', 'is_junction', 'is_active')
    
    # Filter stations by division, junction status, or active status
    list_filter = ('division', 'is_junction', 'is_active')
    
    # Search by station code or name
    search_fields = ('station_code', 'station_name')


# Register TrackSection model
@admin.register(TrackSection)
class TrackSectionAdmin(admin.ModelAdmin):
    # Shows section code, start/end stations, direction (up/down), track type, and operational status
    list_display = ('section_code', 'start_station', 'end_station', 'direction', 'track_type', 'status')
    
    # Filter by track type (main line, loop line, etc.) or status
    list_filter = ('track_type', 'status')
    
    # Search by section code
    search_fields = ('section_code',)


# Register Asset model
@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    # Displays asset code, its track section location, type (signal, switch, etc.), and status
    list_display = ('asset_code', 'track_section', 'asset_type', 'status')
    
    # Filter assets by type or operational status
    list_filter = ('asset_type', 'status')
    
    # Search by asset code
    search_fields = ('asset_code',)


# Register SensorType model (defines different types of sensors)
@admin.register(SensorType)
class SensorTypeAdmin(admin.ModelAdmin):
    # Shows sensor type name, measurement unit (e.g., °C, mm), normal min/max values
    # normal_min and normal_max define the expected operational range
    list_display = ('name', 'measurement_unit', 'normal_min', 'normal_max')
    
    # Search by sensor type name
    search_fields = ('name',)


# Register Sensor model
@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    # Displays sensor code, type, associated asset, health status, and active status
    # health_status indicates if sensor is functioning properly
    list_display = ('sensor_code', 'sensor_type', 'asset', 'health_status', 'is_active')
    
    # Filter by health status, sensor type, or active status
    list_filter = ('health_status', 'sensor_type', 'is_active')
    
    # Search by sensor code or unique identifier
    search_fields = ('sensor_code', 'sensor_uid')


# Register SensorCalibration model (tracks when sensors are calibrated)
@admin.register(SensorCalibration)
class SensorCalibrationAdmin(admin.ModelAdmin):
    # Shows which sensor was calibrated, when, by whom, and next due date
    # Helps maintain calibration schedule for accurate readings
    list_display = ('sensor', 'calibrated_at', 'calibrated_by', 'next_calibration_due')
    
    # Filter calibrations by sensor
    list_filter = ('sensor',)


# Register SensorReading model (stores actual sensor measurements)
@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    # Displays sensor, timestamp, raw/processed values, and anomaly flag
    # processed_value may be calibrated/corrected; anomaly_flag indicates suspicious reading
    list_display = ('sensor', 'recorded_at', 'raw_value', 'processed_value', 'anomaly_flag')
    
    # Filter readings by anomaly status or sensor
    list_filter = ('anomaly_flag', 'sensor')
    
    # Make these fields read-only to prevent manual modification of sensor data
    # Ensures data integrity by preventing accidental edits to historical readings
    readonly_fields = ('sensor', 'recorded_at', 'raw_value')


# Register Alert model (system-generated alerts for anomalies or issues)
@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    # Shows alert code, severity level, status, affected track section, and generation time
    list_display = ('alert_code', 'severity', 'status', 'track_section', 'generated_at')
    
    # Filter alerts by severity (critical, warning, info), status, or alert type
    list_filter = ('severity', 'status', 'alert_type')
    
    # Search by alert code or title
    search_fields = ('alert_code', 'title')


# Register AlertEscalation model (tracks when alerts are escalated in severity)
@admin.register(AlertEscalation)
class AlertEscalationAdmin(admin.ModelAdmin):
    # Shows which alert was escalated, when, by whom, and severity change
    # from_severity → to_severity shows how severity increased
    list_display = ('alert', 'escalated_at', 'escalated_by', 'from_severity', 'to_severity')


# Register MaintenanceTeam model
@admin.register(MaintenanceTeam)
class MaintenanceTeamAdmin(admin.ModelAdmin):
    # Shows team code, name, division assignment, specialization, and active status
    # specialization indicates what type of maintenance they handle (signals, tracks, etc.)
    list_display = ('team_code', 'team_name', 'division', 'specialization', 'is_active')
    
    # Search by team code or name
    search_fields = ('team_code', 'team_name')


# Register Ticket model (maintenance work orders)
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    # Shows ticket code, title, priority level, status, affected track section, assigned team
    list_display = ('ticket_code', 'title', 'priority', 'status', 'track_section', 'assigned_team')
    
    # Filter tickets by priority or status
    list_filter = ('priority', 'status')
    
    # Search by ticket code or title
    search_fields = ('ticket_code', 'title')


# Register TicketStatusLog model (audit trail of ticket status changes)
@admin.register(TicketStatusLog)
class TicketStatusLogAdmin(admin.ModelAdmin):
    # Shows which ticket changed status, previous/new status, who changed it, and when
    # Provides complete audit trail of ticket lifecycle
    list_display = ('ticket', 'from_status', 'to_status', 'changed_by', 'changed_at')
    
    # Filter by the new status after change
    list_filter = ('to_status',)


# Register MLModel (machine learning model configurations)
@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    # Shows model name, version, type of ML model, and active status
    list_display = ('model_name', 'model_version', 'model_type', 'is_active')
    
    # Search by model name
    search_fields = ('model_name',)


# Register MLModelRun (tracks when ML models were executed)
@admin.register(MLModelRun)
class MLModelRunAdmin(admin.ModelAdmin):
    # Shows which model ran, on which track section, when it started, and run status
    list_display = ('model', 'track_section', 'run_started_at', 'status')
    
    # Filter by run status (running, completed, failed)
    list_filter = ('status',)


# Register AnomalyPrediction (ML model predictions of anomalies)
@admin.register(AnomalyPrediction)
class AnomalyPredictionAdmin(admin.ModelAdmin):
    # Shows model run, associated sensor reading, anomaly score, classification, predicted fault
    # anomaly_score indicates confidence; is_anomaly is the binary classification result
    list_display = ('model_run', 'sensor_reading', 'anomaly_score', 'is_anomaly', 'predicted_fault_type')


# Register AuditLog model (immutable audit trail for the entire system)
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only view of the append-only audit trail."""
    
    # Shows when event occurred, type of event, affected entity type/ID, and actor info
    list_display = ('occurred_at', 'event_type', 'entity_type', 'entity_id',
                    'actor_type', 'actor_identifier')
    
    # Filter audit logs by event type or actor type
    list_filter = ('event_type', 'actor_type')
    
    # Search for specific actors, entity types, or descriptions
    search_fields = ('actor_identifier', 'entity_type', 'description')

    # CRITICAL SECURITY: Prevents any user from adding audit log entries manually
    # Audit logs should only be created by the system, never by users
    def has_add_permission(self, request):
        return False

    # CRITICAL SECURITY: Prevents modification of existing audit log entries
    # Ensures audit trail integrity - logs cannot be altered after creation
    def has_change_permission(self, request, obj=None):
        return False

    # CRITICAL SECURITY: Prevents deletion of audit log entries
    # Ensures complete audit trail - no log entries can be removed
    def has_delete_permission(self, request, obj=None):
        return False