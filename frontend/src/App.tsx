import { useState, useEffect } from 'react'
import './App.css'
import { 
  submitNewTask, 
  getTaskStatus, 
  parseBlueprint, 
  registerUser, 
  loginUser, 
  getAuthToken, 
  logoutUser,
  TaskSubmissionResponse, 
  TaskStatusResponse, 
  TaskResult,
  UserRegistrationResponse 
} from './apiService'

function App() {
  // Task-related state
  const [taskDetails, setTaskDetails] = useState('')
  const [submittedTaskId, setSubmittedTaskId] = useState<string | null>(null)
  const [taskResult, setTaskResult] = useState<TaskStatusResponse | null>(null)
  const [parsedBlueprint, setParsedBlueprint] = useState<TaskResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Authentication state
  const [token, setToken] = useState<string | null>(null)
  const [currentUser, setCurrentUser] = useState<UserRegistrationResponse | null>(null)
  const [showLogin, setShowLogin] = useState(true) // true for login, false for register
  
  // Auth form state
  const [authUsername, setAuthUsername] = useState('')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  // Check for existing token on app load
  useEffect(() => {
    const existingToken = getAuthToken()
    if (existingToken) {
      setToken(existingToken)
      // In a real app, you might want to validate the token with a /auth/me endpoint
    }
  }, [])

  // Authentication handlers
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!authUsername.trim() || !authEmail.trim() || !authPassword.trim()) {
      setAuthError('Please fill in all fields')
      return
    }

    setAuthLoading(true)
    setAuthError(null)

    try {
      const userData = await registerUser(authUsername, authEmail, authPassword)
      setCurrentUser(userData)
      // Auto-login after registration
      const loginData = await loginUser(authUsername, authPassword)
      setToken(loginData.access_token)
      setAuthUsername('')
      setAuthEmail('')
      setAuthPassword('')
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!authUsername.trim() || !authPassword.trim()) {
      setAuthError('Please enter username and password')
      return
    }

    setAuthLoading(true)
    setAuthError(null)

    try {
      const loginData = await loginUser(authUsername, authPassword)
      setToken(loginData.access_token)
      setAuthUsername('')
      setAuthPassword('')
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = () => {
    logoutUser()
    setToken(null)
    setCurrentUser(null)
    setSubmittedTaskId(null)
    setTaskResult(null)
    setParsedBlueprint(null)
    setError(null)
  }

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

  // If not authenticated, show login/register form
  if (!token) {
    return (
      <div style={{ maxWidth: '400px', margin: '0 auto', padding: '20px' }}>
        <h1>🤖 awanON AI Task Submission</h1>
        <p>Please {showLogin ? 'login' : 'register'} to access the task submission system</p>

        <div style={{ marginBottom: '20px' }}>
          <button 
            onClick={() => setShowLogin(true)}
            style={{
              padding: '8px 16px',
              backgroundColor: showLogin ? '#007bff' : '#f8f9fa',
              color: showLogin ? 'white' : '#333',
              border: '1px solid #007bff',
              borderRadius: '4px 0 0 4px',
              cursor: 'pointer'
            }}
          >
            Login
          </button>
          <button 
            onClick={() => setShowLogin(false)}
            style={{
              padding: '8px 16px',
              backgroundColor: !showLogin ? '#007bff' : '#f8f9fa',
              color: !showLogin ? 'white' : '#333',
              border: '1px solid #007bff',
              borderRadius: '0 4px 4px 0',
              cursor: 'pointer'
            }}
          >
            Register
          </button>
        </div>

        <form onSubmit={showLogin ? handleLogin : handleRegister}>
          <div style={{ marginBottom: '15px' }}>
            <label htmlFor="authUsername" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Username:
            </label>
            <input 
              id="authUsername"
              type="text"
              value={authUsername} 
              onChange={(e) => setAuthUsername(e.target.value)} 
              placeholder="Enter your username"
              style={{ 
                width: '100%', 
                padding: '10px', 
                border: '1px solid #ccc', 
                borderRadius: '4px',
                fontSize: '14px'
              }}
              required 
            />
          </div>

          {!showLogin && (
            <div style={{ marginBottom: '15px' }}>
              <label htmlFor="authEmail" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                Email:
              </label>
              <input 
                id="authEmail"
                type="email"
                value={authEmail} 
                onChange={(e) => setAuthEmail(e.target.value)} 
                placeholder="Enter your email"
                style={{ 
                  width: '100%', 
                  padding: '10px', 
                  border: '1px solid #ccc', 
                  borderRadius: '4px',
                  fontSize: '14px'
                }}
                required 
              />
            </div>
          )}

          <div style={{ marginBottom: '15px' }}>
            <label htmlFor="authPassword" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Password:
            </label>
            <input 
              id="authPassword"
              type="password"
              value={authPassword} 
              onChange={(e) => setAuthPassword(e.target.value)} 
              placeholder="Enter your password"
              style={{ 
                width: '100%', 
                padding: '10px', 
                border: '1px solid #ccc', 
                borderRadius: '4px',
                fontSize: '14px'
              }}
              required 
            />
          </div>

          <button 
            type="submit" 
            disabled={authLoading}
            style={{
              width: '100%',
              padding: '10px 20px',
              backgroundColor: authLoading ? '#ccc' : '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: authLoading ? 'not-allowed' : 'pointer',
              fontSize: '16px'
            }}
          >
            {authLoading ? (showLogin ? 'Logging in...' : 'Registering...') : (showLogin ? 'Login' : 'Register')}
          </button>
        </form>

        {authError && (
          <div style={{ 
            backgroundColor: '#f8d7da', 
            color: '#721c24', 
            padding: '15px', 
            borderRadius: '4px', 
            marginTop: '20px',
            border: '1px solid #f5c6cb'
          }}>
            <strong>Error:</strong> {authError}
          </div>
        )}
      </div>
    )
  }

  // If authenticated, show the main task submission interface
  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1>🤖 awanON AI Task Submission</h1>
          <p>Submit a task to generate an AI-powered company blueprint</p>
        </div>
        <button 
          onClick={handleLogout}
          style={{
            padding: '8px 16px',
            backgroundColor: '#dc3545',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Logout
        </button>
      </div>

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
