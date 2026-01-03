import { useState, useEffect } from "react";
import "./ClinicalVisualizations.css";

const API_URL = "http://127.0.0.1:8000";

export default function ClinicalVisualizations() {
  const [clinicalData, setClinicalData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadClinicalData();
  }, []);

  async function loadClinicalData() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/clinical-data`);
      const data = await res.json();
      setClinicalData(data);
    } catch (e) {
      setError("Failed to load clinical data");
      console.error("Error loading clinical data:", e);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return <div className="clinical-loading">Loading clinical data...</div>;
  }

  if (error) {
    return <div className="clinical-error">{error}</div>;
  }

  if (!clinicalData || !clinicalData.events || clinicalData.events.length === 0) {
    return (
      <div className="clinical-empty">
        <p>No clinical data available. Upload medical files to see visualizations.</p>
        <button onClick={loadClinicalData}>Refresh</button>
      </div>
    );
  }

  return (
    <div className="clinical-visualizations">
      <div className="clinical-header">
        <h2>Clinical Patient Dashboard</h2>
        <button onClick={loadClinicalData} className="refresh-btn">Refresh Data</button>
      </div>

      {/* Red Flags */}
      {clinicalData.red_flags && clinicalData.red_flags.length > 0 && (
        <RedFlagsPanel redFlags={clinicalData.red_flags} />
      )}

      {/* Section Completeness */}
      <SectionCompleteness sections={clinicalData.sections} />

      {/* Patient Event Timeline */}
      <EventTimeline events={clinicalData.events} />

      {/* Abnormal Labs Panel */}
      <AbnormalLabsPanel labs={clinicalData.labs} />

      {/* Medication Timeline */}
      <MedicationTimeline medications={clinicalData.medications} />

      {/* Summary */}
      {clinicalData.summary && (
        <div className="clinical-summary">
          <h3>Summary</h3>
          <div className="summary-grid">
            <div className="summary-item">
              <span className="summary-label">Total Events:</span>
              <span className="summary-value">{clinicalData.summary.total_events}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Lab Results:</span>
              <span className="summary-value">{clinicalData.summary.total_labs}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Abnormal Labs:</span>
              <span className={`summary-value ${clinicalData.summary.abnormal_labs > 0 ? 'abnormal' : ''}`}>
                {clinicalData.summary.abnormal_labs}
              </span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Medications:</span>
              <span className="summary-value">{clinicalData.summary.total_medications}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Red Flags:</span>
              <span className={`summary-value ${clinicalData.summary.total_red_flags > 0 ? 'alert' : ''}`}>
                {clinicalData.summary.total_red_flags}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Red Flags Panel
function RedFlagsPanel({ redFlags }) {
  return (
    <div className="red-flags-panel">
      <h3>
        <span className="icon-alert">⚠️</span> Red Flags
      </h3>
      <div className="red-flags-grid">
        {redFlags.map((flag, idx) => (
          <div key={idx} className={`red-flag-card severity-${flag.severity || 'medium'}`}>
            <div className="flag-header">
              <span className="flag-type">{flag.type}</span>
              <span className="flag-severity">{flag.severity || 'medium'}</span>
            </div>
            <div className="flag-description">{flag.description}</div>
            <div className="flag-source">Source: {flag.source_file}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Section Completeness Indicators
function SectionCompleteness({ sections }) {
  const sectionLabels = {
    demographics: "Demographics",
    chief_complaint: "Chief Complaint",
    history_of_present_illness: "History of Present Illness",
    past_medical_history: "Past Medical History",
    medications: "Medications",
    allergies: "Allergies",
    vital_signs: "Vital Signs",
    physical_examination: "Physical Examination",
    laboratory_results: "Laboratory Results",
    assessment: "Assessment",
    plan: "Plan"
  };

  const getStatusColor = (status) => {
    switch (status) {
      case "present":
        return "#10b981"; // green
      case "partial":
        return "#f59e0b"; // amber
      case "not_mentioned":
        return "#ef4444"; // red
      default:
        return "#6b7280"; // gray
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case "present":
        return "Present";
      case "partial":
        return "Partial";
      case "not_mentioned":
        return "Not Mentioned";
      default:
        return "Unknown";
    }
  };

  // Combine all sections from all files
  const allSections = {};
  if (sections && typeof sections === 'object') {
    Object.entries(sections).forEach(([filename, fileSections]) => {
      Object.entries(fileSections).forEach(([section, status]) => {
        if (!allSections[section]) {
          allSections[section] = status;
        } else if (status === 'present' && allSections[section] !== 'present') {
          allSections[section] = status;
        } else if (status === 'partial' && allSections[section] === 'not_mentioned') {
          allSections[section] = status;
        }
      });
    });
  }

  return (
    <div className="section-completeness">
      <h3>Section Completeness</h3>
      <div className="sections-grid">
        {Object.entries(sectionLabels).map(([key, label]) => {
          const status = allSections[key] || "not_mentioned";
          return (
            <div key={key} className="section-item">
              <div className="section-label">{label}</div>
              <div className="section-status">
                <span
                  className="status-dot"
                  style={{ backgroundColor: getStatusColor(status) }}
                ></span>
                <span className="status-text">{getStatusLabel(status)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Patient Event Timeline
function EventTimeline({ events }) {
  if (!events || events.length === 0) {
    return (
      <div className="event-timeline">
        <h3>Patient Event Timeline</h3>
        <div className="timeline-empty">No events documented in records</div>
      </div>
    );
  }

  const getEventIcon = (type) => {
    switch (type?.toLowerCase()) {
      case "admission":
        return "🏥";
      case "procedure":
        return "⚕️";
      case "lab":
        return "🧪";
      case "visit":
        return "👤";
      default:
        return "📅";
    }
  };

  const getEventColor = (type) => {
    switch (type?.toLowerCase()) {
      case "admission":
        return "#3b82f6";
      case "procedure":
        return "#8b5cf6";
      case "lab":
        return "#10b981";
      case "visit":
        return "#f59e0b";
      default:
        return "#6b7280";
    }
  };

  return (
    <div className="event-timeline">
      <h3>Patient Event Timeline</h3>
      <div className="timeline-container">
        {events.map((event, idx) => (
          <div key={idx} className="timeline-item">
            <div
              className="timeline-marker"
              style={{ backgroundColor: getEventColor(event.type) }}
            >
              {getEventIcon(event.type)}
            </div>
            <div className="timeline-content">
              <div className="timeline-header">
                <span className="timeline-type">{event.type || "Event"}</span>
                <span className="timeline-date">{event.date || "Date not specified"}</span>
              </div>
              <div className="timeline-description">{event.description || event.source_text}</div>
              <div className="timeline-source">Source: {event.source_file}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Abnormal Labs Panel
function AbnormalLabsPanel({ labs }) {
  if (!labs || labs.length === 0) {
    return (
      <div className="labs-panel">
        <h3>Laboratory Results</h3>
        <div className="labs-empty">No laboratory results documented in records</div>
      </div>
    );
  }

  const abnormalLabs = labs.filter((lab) => lab.is_abnormal);
  const normalLabs = labs.filter((lab) => !lab.is_abnormal);

  return (
    <div className="labs-panel">
      <h3>Laboratory Results</h3>
      
      {abnormalLabs.length > 0 && (
        <div className="abnormal-labs-section">
          <h4 className="abnormal-labs-header">
            <span className="icon-alert">⚠️</span> Abnormal Results ({abnormalLabs.length})
          </h4>
          <div className="labs-grid">
            {abnormalLabs.map((lab, idx) => (
              <div key={idx} className="lab-card abnormal">
                <div className="lab-header">
                  <span className="lab-name">{lab.test_name || "Unknown Test"}</span>
                  <span className="lab-status-badge abnormal">ABNORMAL</span>
                </div>
                <div className="lab-value">
                  <span className="value">{lab.value || "N/A"}</span>
                  {lab.units && <span className="units">{lab.units}</span>}
                </div>
                <div className="lab-reference">
                  Reference: {lab.reference_range || "Not specified"}
                </div>
                <div className="lab-source">Source: {lab.source_file}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {normalLabs.length > 0 && (
        <div className="normal-labs-section">
          <h4>Normal Results ({normalLabs.length})</h4>
          <div className="labs-grid">
            {normalLabs.map((lab, idx) => (
              <div key={idx} className="lab-card normal">
                <div className="lab-header">
                  <span className="lab-name">{lab.test_name || "Unknown Test"}</span>
                  <span className="lab-status-badge normal">NORMAL</span>
                </div>
                <div className="lab-value">
                  <span className="value">{lab.value || "N/A"}</span>
                  {lab.units && <span className="units">{lab.units}</span>}
                </div>
                <div className="lab-reference">
                  Reference: {lab.reference_range || "Not specified"}
                </div>
                <div className="lab-source">Source: {lab.source_file}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Medication Timeline
function MedicationTimeline({ medications }) {
  if (!medications || medications.length === 0) {
    return (
      <div className="medication-timeline">
        <h3>Medications</h3>
        <div className="meds-empty">No medications documented in records</div>
      </div>
    );
  }

  return (
    <div className="medication-timeline">
      <h3>Medications</h3>
      <div className="meds-container">
        {medications.map((med, idx) => (
          <div key={idx} className="med-card">
            <div className="med-name">{med.name || "Unknown Medication"}</div>
            <div className="med-dates">
              <div className="med-date">
                <span className="date-label">Start:</span>
                <span className="date-value">{med.start_date || "Not specified"}</span>
              </div>
              <div className="med-date">
                <span className="date-label">End:</span>
                <span className="date-value">{med.end_date || "Not specified"}</span>
              </div>
            </div>
            <div className="med-source">Source: {med.source_file}</div>
          </div>
        ))}
      </div>
    </div>
  );
}


