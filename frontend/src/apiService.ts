// frontend/src/apiService.ts

const CORE_API_URL = 'http://localhost:3000/api/v1';
const BRIDGE_API_URL = 'http://localhost:3001/api/v1';

// Types for API responses
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

export const submitNewTask = async (details: string, targetCompany: string = 'tswiqon'): Promise<TaskSubmissionResponse> => {
  try {
    const response = await fetch(`${CORE_API_URL}/tasks`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
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