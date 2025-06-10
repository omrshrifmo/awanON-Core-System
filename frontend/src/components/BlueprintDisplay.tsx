import React from 'react'

interface AIEmployeeRole {
  role_title: string
  responsibilities: string[];
  reports_to?: string | null; // Match BlueprintSuccess
}

// Updated Blueprint interface to match BlueprintSuccess structure from App.tsx
interface Blueprint {
  company_name_suggestion?: string;
  specialization?: string;
  mission_statement_draft?: string;
  key_ai_employee_roles?: AIEmployeeRole[]; // Array is optional
  initial_sop_ideas?: string[]; // Array is optional
  estimated_time_to_operational_setup_days?: number | null;
  summary?: string;
  vision?: string;
  values?: string[];
  target_audience?: string;
  marketing_channels?: string[];
  key_features_and_services?: string[];
  operational_workflow_overview?: string;
  ethical_considerations?: string;
  [key: string]: any; // Keep if present in BlueprintSuccess for flexibility
}

interface BlueprintDisplayProps {
  blueprint: Blueprint; // Uses the updated local Blueprint interface
}

const BlueprintDisplay: React.FC<BlueprintDisplayProps> = ({ blueprint }) => {
  if (!blueprint || Object.keys(blueprint).length === 0) { // Added check for empty object
    return (
      <div style={{ 
        padding: '20px', 
        backgroundColor: '#f8f9fa', 
        borderRadius: '8px',
        textAlign: 'center',
        color: '#6c757d'
      }}>
        <p>No blueprint data available</p>
      </div>
    )
  }

  return (
    <div style={{ 
      backgroundColor: 'white', 
      padding: '30px', 
      borderRadius: '12px', 
      border: '1px solid #e9ecef',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.05)',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      {/* Company Header */}
      <div style={{ 
        marginBottom: '30px', 
        paddingBottom: '20px', 
        borderBottom: '2px solid #007bff' 
      }}>
        <h2 style={{ 
          color: '#007bff', 
          fontSize: '28px', 
          fontWeight: 'bold', 
          margin: '0 0 10px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>
          🏢 {blueprint.company_name_suggestion || 'N/A'}
        </h2>
        <p style={{ 
          color: '#6c757d', 
          fontSize: '16px', 
          margin: '0',
          fontStyle: 'italic'
        }}>
          {blueprint.specialization || 'N/A'}
        </p>
      </div>

      {/* Mission Statement */}
      {blueprint.mission_statement_draft && (
        <div style={{ marginBottom: '30px' }}>
          <h3 style={{
            color: '#495057',
            fontSize: '20px',
            fontWeight: 'bold',
            margin: '0 0 15px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            🎯 Mission Statement
          </h3>
          <div style={{
            backgroundColor: '#f8f9fa',
            padding: '20px',
            borderRadius: '8px',
            borderLeft: '4px solid #007bff'
          }}>
            <p style={{
              fontSize: '16px',
              lineHeight: '1.6',
              margin: '0',
              color: '#495057'
            }}>
              "{blueprint.mission_statement_draft}"
            </p>
          </div>
        </div>
      )}

      {/* Setup Timeline */}
      {blueprint.estimated_time_to_operational_setup_days !== undefined && blueprint.estimated_time_to_operational_setup_days !== null && (
        <div style={{ marginBottom: '30px' }}>
          <h3 style={{
            color: '#495057',
            fontSize: '20px',
            fontWeight: 'bold', 
            margin: '0 0 15px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            ⏱️ Setup Timeline
          </h3>
          <div style={{
            backgroundColor: '#e3f2fd',
            padding: '15px 20px',
            borderRadius: '8px',
            display: 'inline-block'
          }}>
            <span style={{
              fontSize: '24px',
              fontWeight: 'bold',
              color: '#1565c0'
            }}>
              {blueprint.estimated_time_to_operational_setup_days}
            </span>
            <span style={{
              fontSize: '16px',
              color: '#1976d2',
              marginLeft: '8px'
            }}>
              days to operational setup
            </span>
          </div>
        </div>
      )}

      {/* AI Employee Roles */}
      {(blueprint.key_ai_employee_roles || []).length > 0 && (
        <div style={{ marginBottom: '30px' }}>
          <h3 style={{
            color: '#495057',
            fontSize: '20px',
            fontWeight: 'bold',
            margin: '0 0 20px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            👥 Key AI Employee Roles
          </h3>
          <div style={{
            display: 'grid',
            gap: '20px',
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))'
          }}>
            {(blueprint.key_ai_employee_roles || []).map((role, index) => (
              <div key={index} style={{
                backgroundColor: '#f8f9fa',
                padding: '20px',
              borderRadius: '8px',
              border: '1px solid #dee2e6'
            }}>
              <h4 style={{ 
                color: '#007bff', 
                fontSize: '18px', 
                fontWeight: 'bold', 
                margin: '0 0 10px 0' 
              }}>
                {role.role_title}
              </h4>
              
              {role.reports_to && (
                <p style={{ 
                  color: '#6c757d', 
                  fontSize: '14px', 
                  margin: '0 0 15px 0',
                  fontStyle: 'italic'
                }}>
                  Reports to: <strong>{role.reports_to}</strong>
                </p>
              )}
              
              <div>
                <h5 style={{ 
                  color: '#495057', 
                  fontSize: '14px', 
                  fontWeight: 'bold', 
                  margin: '0 0 10px 0',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px'
                }}>
                  Responsibilities:
                </h5>
                <ul style={{ 
                  margin: '0', 
                  paddingLeft: '20px',
                  color: '#495057'
                }}>
                  {(role.responsibilities || []).map((responsibility, respIndex) => (
                    <li key={respIndex} style={{ 
                      marginBottom: '8px',
                      lineHeight: '1.5',
                      fontSize: '14px'
                    }}>
                      {responsibility}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            ))}
          </div>
        </div>
      )}

      {/* Initial SOP Ideas */}
      {(blueprint.initial_sop_ideas || []).length > 0 && (
        <div style={{ marginBottom: '0' }}>
          <h3 style={{
            color: '#495057',
            fontSize: '20px',
            fontWeight: 'bold',
            margin: '0 0 20px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            📋 Initial SOP Ideas
          </h3>
          <div style={{
            backgroundColor: '#fff3cd',
            padding: '20px',
            borderRadius: '8px',
            border: '1px solid #ffeaa7'
          }}>
            <ol style={{
              margin: '0',
              paddingLeft: '20px',
              color: '#856404'
            }}>
              {(blueprint.initial_sop_ideas || []).map((sop, index) => (
                <li key={index} style={{
                  marginBottom: '12px',
                  lineHeight: '1.6',
                  fontSize: '15px'
                }}>
                  {sop}
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
      {/* TODO: Add rendering for other new fields from BlueprintSuccess if desired */}
      {/* e.g., summary, vision, values etc. */}
    </div>
  )
}

export default BlueprintDisplay