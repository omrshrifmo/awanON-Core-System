// frontend/src/apiService.ts

// Read from Vite environment variables, with fallbacks for local development
const CORE_API_BASE_URL = import.meta.env.VITE_CORE_API_URL || 'http://localhost:3000';
const BRIDGE_API_BASE_URL = import.meta.env.VITE_BRIDGE_API_URL || 'http://localhost:3001';

export const CORE_API_URL = `${CORE_API_BASE_URL}/api/v1`;
export const BRIDGE_API_URL = `${BRIDGE_API_BASE_URL}/api/v1`;

// Types for API responses
export interface UserRegistrationData {
  username: string;
  email: string;
  password: string;
}

export interface UserRegistrationResponse {
  id: number;
  username: string;
  email: string;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}
export interface TaskSubmissionResponse {
  task_id: string;
  message: string;
  status_code: number;
  target_queue: string;
}

export interface Blueprint {
  company_name_suggestion: string;
  specialization: string;
  mission_statement_draft: string;
  key_ai_employee_roles: Array<{
    role_title: string;
    responsibilities: string[];
    reports_to: string;
  }>;
  initial_sop_ideas: string[];
  estimated_time_to_operational_setup_days: number;
}

export interface TaskResult {
  blueprint: Blueprint;
  workflow_type: string;
  validation_result: {
    status: string;
    message: string;
  };
  workflow_steps: {
    analysis: any;
    research: any;
    blueprint_draft: any;
    refined_blueprint: any;
  };
  model_used: string;
}

export interface TaskStatusResponse {
  status: string;
  task: {
    task_id: string;
    target_company_name: string;
    details: string;
    status: string;
    created_at: string;
    updated_at: string;
  };
}

// Authentication functions
export const registerUser = async (username: string, email: string, password: string): Promise<UserRegistrationResponse> => {
  try {
    const response = await fetch(`${CORE_API_URL.replace('/api/v1', '')}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password }),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(`API Error: ${response.status} - ${errorData.detail || errorData.message || 'Registration failed'}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error registering user:', error);
    throw error;
  }
};

export const loginUser = async (username: string, password: string): Promise<LoginResponse> => {
  try {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(`${CORE_API_URL.replace('/api/v1', '')}/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString(),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(`API Error: ${response.status} - ${errorData.detail || errorData.message || 'Login failed'}`);
    }
    const data = await response.json();
    if (data.access_token) {
      localStorage.setItem('awanon_user_token', data.access_token); // Simple localStorage for example
    }
    return data;
  } catch (error) {
    console.error('Error logging in user:', error);
    throw error;
  }
};

export const getAuthToken = (): string | null => {
  return localStorage.getItem('awanon_user_token');
};

export const logoutUser = (): void => {
  localStorage.removeItem('awanon_user_token');
  // Potentially call a backend logout endpoint if implemented
};

export const submitNewTask = async (details: string, targetCompany: string = 'tswiqon'): Promise<TaskSubmissionResponse> => {
  try {
    const token = getAuthToken(); // Get token
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`; // Add Authorization header
    }

    const response = await fetch(`${CORE_API_URL}/tasks`, {
      method: 'POST',
      headers: headers, // Use updated headers
      body: JSON.stringify({
        details: details,
        target_company_name: targetCompany,
      }),
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(`API Error: ${response.status} - ${errorData.message || errorData.detail || 'Unknown error'}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error submitting new task:', error);
    throw error;
  }
};

export const getTaskStatus = async (taskId: string): Promise<TaskStatusResponse | null> => {
  try {
    const response = await fetch(`${BRIDGE_API_URL}/tasks/${taskId}`);
    
    if (!response.ok) {
      if (response.status === 404) {
        return null; // Task not found in bridge yet or invalid ID
      }
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(`API Error: ${response.status} - ${errorData.message || errorData.detail || 'Unknown error'}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error(`Error fetching status for task ${taskId}:`, error);
    throw error;
  }
};

// Helper function to parse blueprint from task details
export const parseBlueprint = (taskDetails: string): TaskResult | null => {
  try {
    const parsed = JSON.parse(taskDetails);
    return parsed;
  } catch (error) {
    console.error('Error parsing task details:', error);
    return null;
  }
};