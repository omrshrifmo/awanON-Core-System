import { useState } from 'react'
import './App.css'
import { submitNewTask, getTaskStatus, parseBlueprint, TaskSubmissionResponse, TaskStatusResponse, TaskResult } from './apiService'

function App() {
  const [taskDetails, setTaskDetails] = useState('')
  const [submittedTaskId, setSubmittedTaskId] = useState<string | null>(null)
  const [taskResult, setTaskResult] = useState<TaskStatusResponse | null>(null)
  const [parsedBlueprint, setParsedBlueprint] = useState<TaskResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!taskDetails.trim()) {
      setError('Please enter task details')
      return
    }

    setIsLoading(true)
    setError(null)
    setTaskResult(null)
    setParsedBlueprint(null)
    setSubmittedTaskId(null)

    try {
      const data: TaskSubmissionResponse = await submitNewTask(taskDetails)
      setSubmittedTaskId(data.task_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred')
    } finally {
      setIsLoading(false)
    }
  }

  const handleCheckStatus = async () => {
    if (!submittedTaskId) return

    setIsLoading(true)
    setError(null)
    setTaskResult(null)
    setParsedBlueprint(null)

    try {
      const data = await getTaskStatus(submittedTaskId)
      setTaskResult(data)
      
      if (data?.task?.details) {
        const blueprint = parseBlueprint(data.task.details)
        setParsedBlueprint(blueprint)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred')
    } finally {
      setIsLoading(false)
    }
  }

  const formatStatus = (status: string) => {
    switch (status) {
      case 'completed_langgraph_blueprint':
        return '✅ Completed - Blueprint Generated'
      case 'DISPATCHED':
        return '🔄 Processing...'
      case 'PENDING':
        return '⏳ Pending'
      default:
        return status
    }
  }

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px' }}>
      <h1>🤖 awanON AI Task Submission</h1>
      <p>Submit a task to generate an AI-powered company blueprint</p>

      <form onSubmit={handleSubmit} style={{ marginBottom: '30px' }}>
        <div style={{ marginBottom: '15px' }}>
          <label htmlFor="taskDetails" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            Task Details:
          </label>
          <textarea 
            id="taskDetails"
            value={taskDetails} 
            onChange={(e) => setTaskDetails(e.target.value)} 
            placeholder="Enter your task details here... (e.g., 'Generate a detailed company blueprint for an AI-powered company specializing in personalized music generation for content creators.')"
            rows={5}
            style={{ 
              width: '100%', 
              padding: '10px', 
              border: '1px solid #ccc', 
              borderRadius: '4px',
              fontSize: '14px',
              fontFamily: 'inherit'
            }}
            required 
          />
        </div>
        <button 
          type="submit" 
          disabled={isLoading}
          style={{
            padding: '10px 20px',
            backgroundColor: isLoading ? '#ccc' : '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isLoading ? 'not-allowed' : 'pointer',
            fontSize: '16px'
          }}
        >
          {isLoading ? 'Submitting...' : 'Submit Task'}
        </button>
      </form>

      {submittedTaskId && (
        <div style={{ 
          backgroundColor: '#f8f9fa', 
          padding: '15px', 
          borderRadius: '4px', 
          marginBottom: '20px',
          border: '1px solid #dee2e6'
        }}>
          <h3>✅ Task Submitted Successfully!</h3>
          <p><strong>Task ID:</strong> <code>{submittedTaskId}</code></p>
          <button 
            onClick={handleCheckStatus} 
            disabled={isLoading}
            style={{
              padding: '8px 16px',
              backgroundColor: isLoading ? '#ccc' : '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: isLoading ? 'not-allowed' : 'pointer'
            }}
          >
            {isLoading ? 'Checking...' : 'Check Status'}
          </button>
        </div>
      )}

      {error && (
        <div style={{ 
          backgroundColor: '#f8d7da', 
          color: '#721c24', 
          padding: '15px', 
          borderRadius: '4px', 
          marginBottom: '20px',
          border: '1px solid #f5c6cb'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {taskResult && (
        <div style={{ 
          backgroundColor: '#d4edda', 
          padding: '20px', 
          borderRadius: '4px', 
          marginBottom: '20px',
          border: '1px solid #c3e6cb'
        }}>
          <h2>📊 Task Result</h2>
          <div style={{ marginBottom: '15px' }}>
            <p><strong>Status:</strong> {formatStatus(taskResult.task.status)}</p>
            <p><strong>Company:</strong> {taskResult.task.target_company_name}</p>
            <p><strong>Created:</strong> {new Date(taskResult.task.created_at).toLocaleString()}</p>
            <p><strong>Updated:</strong> {new Date(taskResult.task.updated_at).toLocaleString()}</p>
          </div>

          {parsedBlueprint?.blueprint && (
            <div style={{ marginTop: '20px' }}>
              <h3>🏢 Generated Company Blueprint</h3>
              <div style={{ 
                backgroundColor: 'white', 
                padding: '15px', 
                borderRadius: '4px', 
                border: '1px solid #ccc'
              }}>
                <h4>📝 Company Overview</h4>
                <p><strong>Company Name:</strong> {parsedBlueprint.blueprint.company_name_suggestion}</p>
                <p><strong>Specialization:</strong> {parsedBlueprint.blueprint.specialization}</p>
                <p><strong>Mission Statement:</strong> {parsedBlueprint.blueprint.mission_statement_draft}</p>
                <p><strong>Setup Time:</strong> {parsedBlueprint.blueprint.estimated_time_to_operational_setup_days} days</p>

                <h4>👥 Key AI Employee Roles</h4>
                <ul>
                  {parsedBlueprint.blueprint.key_ai_employee_roles.map((role, index) => (
                    <li key={index} style={{ marginBottom: '10px' }}>
                      <strong>{role.role_title}</strong> (Reports to: {role.reports_to})
                      <ul style={{ marginTop: '5px' }}>
                        {role.responsibilities.map((resp, respIndex) => (
                          <li key={respIndex}>{resp}</li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ul>

                <h4>📋 Initial SOP Ideas</h4>
                <ul>
                  {parsedBlueprint.blueprint.initial_sop_ideas.map((sop, index) => (
                    <li key={index}>{sop}</li>
                  ))}
                </ul>

                <h4>🔧 Technical Details</h4>
                <p><strong>Model Used:</strong> {parsedBlueprint.model_used}</p>
                <p><strong>Workflow Type:</strong> {parsedBlueprint.workflow_type}</p>
                <p><strong>Validation Status:</strong> {parsedBlueprint.validation_result.status} - {parsedBlueprint.validation_result.message}</p>
              </div>
            </div>
          )}

          {taskResult.task.status !== 'completed_langgraph_blueprint' && (
            <div style={{ marginTop: '15px', padding: '10px', backgroundColor: '#fff3cd', borderRadius: '4px' }}>
              <p>⏳ Task is still processing. Check back in a few moments for the complete blueprint.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
