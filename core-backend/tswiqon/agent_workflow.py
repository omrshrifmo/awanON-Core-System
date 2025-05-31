import json
import logging
from typing import Dict, Any, TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from litellm import completion
from models import CompanyBlueprintV1
from pydantic import ValidationError

# Setup logging
logging.basicConfig(level=logging.INFO, format='[LangGraph Agent] %(asctime)s - %(levelname)s - %(message)s')

class AgentState(TypedDict):
    task_details: str
    target_company_name: str
    model_name: str
    analysis_result: Dict[str, Any]
    research_context: Dict[str, Any]
    blueprint_draft: Dict[str, Any]
    refined_blueprint: Dict[str, Any]
    final_blueprint: Dict[str, Any]
    validation_result: Dict[str, Any]
    error: str

def analyze_task(state: AgentState) -> AgentState:
    """Step 1: Analyze the task requirements and extract key information"""
    logging.info("Step 1: Analyzing task requirements")
    
    system_prompt = (
        "You are a business analysis AI. Analyze the given task and extract key business requirements. "
        "Respond with a JSON object containing: "
        "- business_domain: string (the main business domain) "
        "- key_requirements: array of strings (main requirements) "
        "- target_market: string (who the target customers are) "
        "- complexity_level: string (simple/medium/complex) "
        "Respond with ONLY the JSON object, no markdown formatting."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Analyze this business task: {state['task_details']}"}
    ]
    
    try:
        response = completion(
            model=state['model_name'],
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        analysis_result = json.loads(response.choices[0].message.content)
        state['analysis_result'] = analysis_result
        logging.info(f"Task analysis completed: {analysis_result.get('business_domain', 'Unknown domain')}")
        
    except Exception as e:
        logging.error(f"Error in analyze_task: {e}")
        state['error'] = f"Analysis failed: {str(e)}"
        
    return state

def research_context(state: AgentState) -> AgentState:
    """Step 2: Research industry context and best practices"""
    logging.info("Step 2: Researching industry context")
    
    if state.get('error'):
        return state
        
    analysis = state.get('analysis_result', {})
    business_domain = analysis.get('business_domain', 'AI services')
    
    system_prompt = (
        "You are an industry research AI. Based on the business domain, provide industry context. "
        "Respond with a JSON object containing: "
        "- industry_trends: array of strings (current trends) "
        "- common_challenges: array of strings (typical challenges) "
        "- success_factors: array of strings (key success factors) "
        "- competitive_landscape: string (brief overview) "
        "Respond with ONLY the JSON object, no markdown formatting."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Research industry context for: {business_domain}"}
    ]
    
    try:
        response = completion(
            model=state['model_name'],
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        research_result = json.loads(response.choices[0].message.content)
        state['research_context'] = research_result
        logging.info("Industry research completed")
        
    except Exception as e:
        logging.error(f"Error in research_context: {e}")
        state['error'] = f"Research failed: {str(e)}"
        
    return state

def generate_blueprint(state: AgentState) -> AgentState:
    """Step 3: Generate initial company blueprint"""
    logging.info("Step 3: Generating initial blueprint")
    
    if state.get('error'):
        return state
        
    analysis = state.get('analysis_result', {})
    research = state.get('research_context', {})
    
    system_prompt = (
        "You are an expert strategic business consultant AI. Generate a detailed company blueprint "
        "based on the analysis and research provided. The output MUST be a valid JSON object that "
        "conforms to the CompanyBlueprintV1 Pydantic model. Respond with *ONLY* the JSON object "
        "and nothing else. Do not include any markdown formatting like ```json or ``` at the "
        "beginning or end. Do not include any explanatory text outside of the JSON structure. "
        f"The company blueprint is for '{state['target_company_name']}'. "
        "The JSON must include these exact fields: "
        "- company_name_suggestion: string (creative name for the AI company) "
        "- specialization: string (the given specialization) "
        "- mission_statement_draft: string (at least 20 characters) "
        "- key_ai_employee_roles: array of objects with role_title, responsibilities (array), and optional reports_to "
        "- initial_sop_ideas: array of 3-5 strings for Standard Operating Procedures "
        "- estimated_time_to_operational_setup_days: number (optional) "
    )
    
    user_content = (
        f"Generate a company blueprint for: {state['task_details']}\n"
        f"Analysis: {json.dumps(analysis)}\n"
        f"Research: {json.dumps(research)}"
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    try:
        response = completion(
            model=state['model_name'],
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        blueprint_draft = json.loads(response.choices[0].message.content)
        state['blueprint_draft'] = blueprint_draft
        logging.info("Initial blueprint generated")
        
    except Exception as e:
        logging.error(f"Error in generate_blueprint: {e}")
        state['error'] = f"Blueprint generation failed: {str(e)}"
        
    return state

def review_and_refine(state: AgentState) -> AgentState:
    """Step 4: Review and refine the blueprint"""
    logging.info("Step 4: Reviewing and refining blueprint")
    
    if state.get('error'):
        return state
        
    blueprint = state.get('blueprint_draft', {})
    
    system_prompt = (
        "You are a business strategy reviewer AI. Review the provided company blueprint and refine it. "
        "Ensure all required fields are present and well-structured. The output MUST be a valid JSON "
        "object that conforms to the CompanyBlueprintV1 Pydantic model. "
        "Respond with *ONLY* the refined JSON object and nothing else. "
        "Do not include any markdown formatting. "
        "Required fields: "
        "- company_name_suggestion: string "
        "- specialization: string "
        "- mission_statement_draft: string (at least 20 characters) "
        "- key_ai_employee_roles: array of objects with role_title, responsibilities (array), and optional reports_to "
        "- initial_sop_ideas: array of 3-5 strings "
        "- estimated_time_to_operational_setup_days: number (optional) "
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Review and refine this blueprint: {json.dumps(blueprint)}"}
    ]
    
    try:
        response = completion(
            model=state['model_name'],
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        refined_blueprint = json.loads(response.choices[0].message.content)
        state['refined_blueprint'] = refined_blueprint
        logging.info("Blueprint refined")
        
    except Exception as e:
        logging.error(f"Error in review_and_refine: {e}")
        state['error'] = f"Blueprint refinement failed: {str(e)}"
        
    return state

def validate_output(state: AgentState) -> AgentState:
    """Step 5: Validate the final blueprint against Pydantic model"""
    logging.info("Step 5: Validating final blueprint")
    
    if state.get('error'):
        return state
        
    refined_blueprint = state.get('refined_blueprint', {})
    
    # Enhanced system prompt for final validation and completion
    system_prompt = (
        "You are a final validation AI. Ensure the provided blueprint is complete and valid. "
        "The output MUST be a valid JSON object that perfectly conforms to the CompanyBlueprintV1 model. "
        "Respond with *ONLY* the complete JSON object and nothing else. "
        "Do not include any markdown formatting like ```json or ``` at the beginning or end. "
        "CRITICAL: Ensure ALL required fields are present: "
        "- company_name_suggestion: string (must be present) "
        "- specialization: string (must be present) "
        "- mission_statement_draft: string (must be at least 20 characters) "
        "- key_ai_employee_roles: array of objects, each with role_title (string), responsibilities (array of strings), and optional reports_to (string) "
        "- initial_sop_ideas: array of 3-5 strings "
        "- estimated_time_to_operational_setup_days: number (optional but recommended) "
        "If any field is missing or incomplete, generate appropriate content for it."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Validate and complete this blueprint: {json.dumps(refined_blueprint)}"}
    ]
    
    try:
        response = completion(
            model=state['model_name'],
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        final_blueprint = json.loads(response.choices[0].message.content)
        
        # Validate against Pydantic model
        try:
            validated_blueprint = CompanyBlueprintV1(**final_blueprint)
            state['final_blueprint'] = final_blueprint
            state['validation_result'] = {"status": "success", "message": "Blueprint validated successfully"}
            logging.info("Blueprint validation successful")
            
        except ValidationError as e:
            logging.error(f"Pydantic validation failed: {e}")
            state['validation_result'] = {"status": "failed", "message": str(e), "blueprint": final_blueprint}
            state['error'] = f"Validation failed: {str(e)}"
            
    except Exception as e:
        logging.error(f"Error in validate_output: {e}")
        state['error'] = f"Final validation failed: {str(e)}"
        
    return state

def create_workflow(model_name: str) -> StateGraph:
    """Create the LangGraph workflow"""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("analyze_task", analyze_task)
    workflow.add_node("research_context", research_context)
    workflow.add_node("generate_blueprint", generate_blueprint)
    workflow.add_node("review_and_refine", review_and_refine)
    workflow.add_node("validate_output", validate_output)
    
    # Define the flow
    workflow.set_entry_point("analyze_task")
    workflow.add_edge("analyze_task", "research_context")
    workflow.add_edge("research_context", "generate_blueprint")
    workflow.add_edge("generate_blueprint", "review_and_refine")
    workflow.add_edge("review_and_refine", "validate_output")
    workflow.add_edge("validate_output", END)
    
    return workflow.compile()

def run_agent_workflow(task_details: str, target_company_name: str, model_name: str) -> Dict[str, Any]:
    """Run the complete LangGraph workflow"""
    logging.info(f"Starting LangGraph workflow for: {target_company_name}")
    
    # Create workflow
    app = create_workflow(model_name)
    
    # Initial state
    initial_state = {
        "task_details": task_details,
        "target_company_name": target_company_name,
        "model_name": model_name,
        "analysis_result": {},
        "research_context": {},
        "blueprint_draft": {},
        "refined_blueprint": {},
        "final_blueprint": {},
        "validation_result": {},
        "error": ""
    }
    
    try:
        # Run the workflow
        final_state = app.invoke(initial_state)
        
        if final_state.get('error'):
            return {
                "error": final_state['error'],
                "workflow_type": "langgraph_multi_step",
                "partial_results": {
                    "analysis": final_state.get('analysis_result', {}),
                    "research": final_state.get('research_context', {}),
                    "blueprint_draft": final_state.get('blueprint_draft', {}),
                    "refined_blueprint": final_state.get('refined_blueprint', {})
                }
            }
        
        return {
            "blueprint": final_state.get('final_blueprint', {}),
            "workflow_type": "langgraph_multi_step",
            "validation_result": final_state.get('validation_result', {}),
            "workflow_steps": {
                "analysis": final_state.get('analysis_result', {}),
                "research": final_state.get('research_context', {}),
                "blueprint_draft": final_state.get('blueprint_draft', {}),
                "refined_blueprint": final_state.get('refined_blueprint', {})
            }
        }
        
    except Exception as e:
        logging.error(f"Workflow execution failed: {e}")
        return {
            "error": f"Workflow execution failed: {str(e)}",
            "workflow_type": "langgraph_multi_step"
        }