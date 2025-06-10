import { useState, useEffect } from 'react'
import './App.css'
import { 
  submitNewTask, 
  getTaskStatus, 
  // parseBlueprint, // Removed as it's no longer used
  registerUser, 
  loginUser, 
  getAuthToken, 
  logoutUser,
  TaskSubmissionResponse, 
  // TaskStatusResponse, // Removed as taskResult now uses AppTaskResult
  // TaskResult, // Removed as it's no longer used in App.tsx
  UserRegistrationResponse 
} from './apiService'
import BlueprintDisplay from './components/BlueprintDisplay'

// --- New/Updated Interface Definitions ---
interface BlueprintSuccess {
  company_name_suggestion?: string;
  specialization?: string;
  mission_statement_draft?: string;
  key_ai_employee_roles?: Array<{ role_title: string; responsibilities: string[]; reports_to?: string | null; }>;
  initial_sop_ideas?: string[];
  estimated_time_to_operational_setup_days?: number | null;
  summary?: string;
  vision?: string;
  values?: string[];
  target_audience?: string;
  marketing_channels?: string[];
  key_features_and_services?: string[];
  operational_workflow_overview?: string;
  ethical_considerations?: string;
  [key: string]: any;
}

interface BlueprintError {
  error: string;
  message?: string;
  details?: string;
  raw_output?: string;
}

type BlueprintData = BlueprintSuccess | BlueprintError;

interface TaskResultData {
  blueprint: BlueprintData;
  model_used?: string;
  // other RAG metadata fields (e.g., workflow_type, validation_result from original TaskResult)
  workflow_type?: string;
  validation_result?: { status: string; message: string; };
  workflow_steps?: any; // Keeping it flexible for now
}

// This TaskResult will be used for the taskResult state
interface AppTaskResult { // Renamed to avoid conflict with imported TaskResult for now
  task_id: string;
  status: string; // e.g., "processing", "completed_blueprint", "failed_langgraph_blueprint"
  result?: TaskResultData | null;
  target_company_name?: string;
  task_details_from_backend?: string; // Renamed to avoid conflict with taskDetails state
  created_at: string;
  updated_at: string;
  user_id?: number;
}


function App() {
  // Task-related state
  const [taskDetails, setTaskDetails] = useState('')
  const [submittedTaskId, setSubmittedTaskId] = useState<string | null>(null)
  // Updated type for taskResult state
  const [taskResult, setTaskResult] = useState<AppTaskResult | null>(null)
  // const [parsedBlueprint, setParsedBlueprint] = useState<TaskResult | null>(null) // Removed
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
    } catch (error: any) { // Updated to 'error: any' for more flexible property access
      const message = error.response?.data?.detail || error.message || 'Registration failed. Please try again.';
      setAuthError(message);
      console.error('Registration error:', error); // It's good practice to log the original error object
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
      setToken(loginData.access_token);
      // Set current user upon successful login
      // The UserRegistrationResponse interface might need adjustment if login doesn't return all fields
      // For now, using what's available (username) and placeholder/existing for others.
      const userToSet: UserRegistrationResponse = {
        username: authUsername,
        id: 0, // Assuming login doesn't return full user details like ID, email, created_at
        email: '', // Or fetch from a /me endpoint
        created_at: new Date().toISOString(),
      };
      setCurrentUser(userToSet);
      setAuthUsername('')
      setAuthPassword('')
    } catch (error: any) { // Updated to 'error: any' for more flexible property access
      const message = error.response?.data?.detail || error.message || 'Login failed. Please check your credentials.';
      setAuthError(message);
      console.error('Login error:', error); // It's good practice to log the original error object
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
    // setParsedBlueprint(null) // Removed
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
    // setParsedBlueprint(null) // Removed
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
    // setParsedBlueprint(null) // Removed

    try {
      // Assuming getTaskStatus from apiService will be updated to return AppTaskResult compatible structure
      const data: AppTaskResult | null = await getTaskStatus(submittedTaskId) as AppTaskResult | null;
      setTaskResult(data)
      
      // Logic for parsedBlueprint removed as the state itself is removed.
      // The main display logic now directly uses taskResult.result.blueprint.
      // If parseBlueprint function is still needed for some edge cases with task_details_from_backend,
      // its output would need to be handled differently or merged into taskResult state.
      // For now, removing its usage here simplifies things based on primary display logic.
      // The main display logic now directly uses taskResult.result.blueprint.
      // If task_details_from_backend was a critical fallback, its parsing (via parseBlueprint)
      // and subsequent data merging/display would need to be explicitly handled here.
      // Given the current structure, if data.result.blueprint is null/undefined,
      // the display logic has fallbacks for "Raw Task Details from Bridge" or "No detailed result".

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
              padding: '10px 20px',
              backgroundColor: showLogin ? '#007bff' : '#f8f9fa',
              color: showLogin ? 'white' : '#333',
              border: '2px solid #007bff',
              borderRadius: '6px 0 0 6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 'bold',
              transition: 'all 0.2s ease',
              boxShadow: showLogin ? '0 2px 4px rgba(0, 123, 255, 0.2)' : 'none'
            }}
          >
            Login
          </button>
          <button 
            onClick={() => setShowLogin(false)}
            style={{
              padding: '10px 20px',
              backgroundColor: !showLogin ? '#007bff' : '#f8f9fa',
              color: !showLogin ? 'white' : '#333',
              border: '2px solid #007bff',
              borderRadius: '0 6px 6px 0',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 'bold',
              transition: 'all 0.2s ease',
              boxShadow: !showLogin ? '0 2px 4px rgba(0, 123, 255, 0.2)' : 'none'
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
              padding: '12px 20px',
              backgroundColor: authLoading ? '#6c757d' : '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: authLoading ? 'not-allowed' : 'pointer',
              fontSize: '16px',
              fontWeight: 'bold',
              transition: 'background-color 0.2s ease',
              boxShadow: authLoading ? 'none' : '0 2px 4px rgba(0, 123, 255, 0.2)'
            }}
          >
            {authLoading ? 
              (showLogin ? '🔄 Logging in...' : '🔄 Registering...') : 
              (showLogin ? 'Login' : 'Register')
            }
          </button>
        </form>

        {authError && (
          <div className="error-message" style={{ 
            backgroundColor: '#f8d7da', 
            color: '#721c24', 
            padding: '15px', 
            borderRadius: '6px', 
            marginTop: '20px',
            border: '2px solid #dc3545',
            boxShadow: '0 2px 4px rgba(220, 53, 69, 0.1)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '16px' }}>❌</span>
              <div>
                <strong>Authentication Error:</strong>
                <div style={{ marginTop: '4px', fontSize: '14px' }}>{authError}</div>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  // If authenticated, show the main task submission interface
  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px' }}>
      {/* Authentication status messages */}
      {token && currentUser && <p style={{ padding: '10px', backgroundColor: '#e0f7fa', border: '1px solid #007bff', borderRadius: '4px', textAlign: 'center', marginBottom: '15px' }}>Welcome back, {currentUser.username}!</p>}
      {!token && showLogin && <p style={{ padding: '10px', backgroundColor: '#fff3cd', border: '1px solid #ffeeba', borderRadius: '4px', textAlign: 'center', marginBottom: '15px' }}>Please log in to submit tasks.</p> }
      {!token && !showLogin && <p style={{ padding: '10px', backgroundColor: '#fff3cd', border: '1px solid #ffeeba', borderRadius: '4px', textAlign: 'center', marginBottom: '15px' }}>Please register or log in to submit tasks.</p> }

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1>🤖 awanON AI Task Submission</h1>
          <p>Submit a task to generate an AI-powered company blueprint</p>
        </div>
        <button 
          onClick={handleLogout}
          style={{
            padding: '10px 20px',
            backgroundColor: '#dc3545',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 'bold',
            transition: 'background-color 0.2s ease',
            boxShadow: '0 2px 4px rgba(220, 53, 69, 0.2)'
          }}
          onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#c82333'}
          onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#dc3545'}
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
            placeholder="Enter details for the company blueprint you want to generate (e.g., 'AI company for personalized travel planning including SOPs')..."
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
            backgroundColor: isLoading ? '#6c757d' : '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isLoading ? 'not-allowed' : 'pointer',
            fontSize: '16px',
            transition: 'background-color 0.2s ease'
          }}
        >
          {isLoading ? '⏳ Submitting Task...' : 'Submit Task'}
        </button>
      </form>

      {isLoading && (
        <div style={{ 
          backgroundColor: '#e3f2fd', 
          color: '#1565c0', 
          padding: '15px', 
          borderRadius: '4px', 
          marginBottom: '20px',
          border: '1px solid #bbdefb',
          textAlign: 'center',
          fontWeight: 'bold'
        }}>
          ⏳ Processing your request...
        </div>
      )}

      {submittedTaskId && (
        <div className="success-message" style={{ 
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
              backgroundColor: isLoading ? '#6c757d' : '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              transition: 'background-color 0.2s ease'
            }}
          >
            {isLoading ? '🔄 Checking Status...' : 'Check Status'}
          </button>
        </div>
      )}

      {error && (
        <div className="error-message" style={{ 
          backgroundColor: '#f8d7da', 
          color: '#721c24', 
          padding: '20px', 
          borderRadius: '8px', 
          marginBottom: '20px',
          border: '2px solid #dc3545',
          boxShadow: '0 4px 6px rgba(220, 53, 69, 0.1)',
          position: 'relative'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '20px' }}>❌</span>
            <div>
              <strong style={{ fontSize: '16px' }}>Error:</strong>
              <p style={{ margin: '5px 0 0 0', fontSize: '14px' }}>{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Task Result Display Section - Modified */}
      {taskResult && (
        <div className="task-result-container" style={{ marginTop: '20px', padding: '15px', border: '1px solid #ccc', borderRadius: '4px' }}>
          {/* Top-level status from bridge backend */}
          <p style={{fontWeight: 'bold'}}>Task Overview (ID: {taskResult.task_id}):</p>
          <p>Status: <span style={{fontWeight: 'bold'}}>{formatStatus(taskResult.status)}</span></p>
          {taskResult.target_company_name && <p>Target Company: {taskResult.target_company_name}</p>}
          <p>Last Updated: {new Date(taskResult.updated_at).toLocaleString()}</p>
          <hr style={{margin: "15px 0"}}/>

          {/* Display based on taskResult.result and its blueprint field */}
          {taskResult.result && taskResult.result.blueprint && (
            <div className="blueprint-details-container" style={{ marginTop: '15px' }}>
              <h4>Blueprint/Result Details:</h4>
              {/* Type guard to check if blueprint is an error */}
              {((bp: any): bp is BlueprintError => typeof bp === 'object' && bp !== null && 'error' in bp)(taskResult.result.blueprint) ? (
                <div className="error-message" style={{ color: 'red', padding: '10px', border: '1px solid red', borderRadius: '4px', backgroundColor: '#ffebee' }}>
                  <p><strong>Error from Agent:</strong> {(taskResult.result.blueprint as BlueprintError).error}</p>
                  {(taskResult.result.blueprint as BlueprintError).message && <p><strong>Message:</strong> {(taskResult.result.blueprint as BlueprintError).message}</p>}
                  {(taskResult.result.blueprint as BlueprintError).details && <p><strong>Details:</strong> {(taskResult.result.blueprint as BlueprintError).details}</p>}
                  {(taskResult.result.blueprint as BlueprintError).raw_output && (
                    <>
                      <p><strong>Raw Output:</strong></p>
                      <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                        {typeof (taskResult.result.blueprint as BlueprintError).raw_output === 'object'
                          ? JSON.stringify((taskResult.result.blueprint as BlueprintError).raw_output, null, 2)
                          : (taskResult.result.blueprint as BlueprintError).raw_output}
                      </pre>
                    </>
                  )}
                </div>
              ) : (
                // If not an error, assume it's BlueprintSuccess and render with BlueprintDisplay
                // Also check overall task status for completion before showing full blueprint display
                taskResult.status.toLowerCase().includes('completed') ? (
                  <>
                    <h3 style={{ color: 'green' }}>✅ Task Completed Successfully!</h3>
                    <div style={{ marginTop: '20px' }}>
                      <h3 style={{ color: '#495057', fontSize: '24px', fontWeight: 'bold', margin: '0 0 20px 0', display: 'flex', alignItems: 'center', gap: '10px' }}>
                        🏢 Generated Company Blueprint
                      </h3>
                       <BlueprintDisplay blueprint={taskResult.result.blueprint as BlueprintSuccess} />
                       {/* Technical Details Section from previous logic - good to keep */}
                       <div style={{ marginTop: '20px', backgroundColor: '#f8f9fa', padding: '20px', borderRadius: '8px', border: '1px solid #dee2e6' }}>
                         <h4 style={{ color: '#495057', fontSize: '18px', fontWeight: 'bold', margin: '0 0 15px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                           🔧 Technical Details
                         </h4>
                         <div style={{ display: 'grid', gap: '10px', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
                           {taskResult.result.model_used && <div><strong style={{ color: '#6c757d', fontSize: '14px' }}>Model Used:</strong><p style={{ margin: '4px 0 0 0', color: '#495057' }}>{taskResult.result.model_used}</p></div>}
                           {taskResult.result.workflow_type && <div><strong style={{ color: '#6c757d', fontSize: '14px' }}>Workflow Type:</strong><p style={{ margin: '4px 0 0 0', color: '#495057' }}>{taskResult.result.workflow_type}</p></div>}
                           {taskResult.result.validation_result && <div><strong style={{ color: '#6c757d', fontSize: '14px' }}>Validation Status:</strong><p style={{ margin: '4px 0 0 0', color: '#495057' }}>{taskResult.result.validation_result.status} - {taskResult.result.validation_result.message}</p></div>}
                         </div>
                       </div>
                    </div>
                  </>
                ) : ( // Processing or other non-completed, non-error states
                    <>
                      <h3>⏳ Task Status: {formatStatus(taskResult.status) || 'Processing...'}</h3>
                      <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', marginTop: '10px', color: '#555' }}>
                          Partial/Processing Data: {JSON.stringify(taskResult.result.blueprint, null, 2)}
                      </pre>
                    </>
                )
              )}
            </div>
          )}
          {/* Fallback if taskResult.result or taskResult.result.blueprint is not available but there are details */}
          {taskResult && !taskResult.result?.blueprint && taskResult.task_details_from_backend && taskResult.task_details_from_backend !== "{}" && (
            <div style={{ marginTop: '10px' }}>
                <h4>Raw Task Details from Bridge:</h4>
                <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {taskResult.task_details_from_backend}
                </pre>
            </div>
          )}
           {taskResult && !taskResult.result && (
             <p style={{ marginTop: '10px', color: '#555' }}>No detailed result data available from the agent yet. Task may still be processing or encountered an issue without specific error details from the agent.</p>
           )}
        </div>
      )}
    </div>
  )
}

export default App
