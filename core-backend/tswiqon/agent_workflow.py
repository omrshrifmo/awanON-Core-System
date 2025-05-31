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
    
    # Enhanced system prompt for final validation and completion with explicit field requirements
    system_prompt = (
        "You are a final validation AI. Create a complete and valid company blueprint JSON. "
        "The output MUST be a valid JSON object that perfectly conforms to the CompanyBlueprintV1 model. "
        "Respond with *ONLY* the complete JSON object and nothing else. "
        "Do not include any markdown formatting like ```json or ``` at the beginning or end. "
        "Do not include any explanatory text or conversation outside of the JSON structure itself. "
        
        "CRITICAL: The JSON must contain ALL these exact fields: "
        "1. company_name_suggestion: string (creative name for the AI company) "
        "2. specialization: string (the business specialization from the task) "
        "3. mission_statement_draft: string (meaningful mission statement, minimum 20 characters) "
        "4. key_ai_employee_roles: array of 2-5 objects, each with: "
        "   - role_title: string (job title) "
        "   - responsibilities: array of strings (2-4 responsibilities) "
        "   - reports_to: string or null (who they report to) "
        "5. initial_sop_ideas: array of 3-5 strings (Standard Operating Procedure ideas) "
        "6. estimated_time_to_operational_setup_days: number (days to setup, optional but recommended) "
        
        "Example structure: "
        "{"
        "  \"company_name_suggestion\": \"AI Solutions Corp\", "
        "  \"specialization\": \"AI-powered legal document review\", "
        "  \"mission_statement_draft\": \"To revolutionize legal document review through advanced AI technology\", "
        "  \"key_ai_employee_roles\": ["
        "    {"
        "      \"role_title\": \"AI Legal Analyst\", "
        "      \"responsibilities\": [\"Review legal documents\", \"Ensure compliance\"], "
        "      \"reports_to\": \"Chief Legal Officer\""
        "    }"
        "  ], "
        "  \"initial_sop_ideas\": [\"Document intake process\", \"Quality assurance protocol\"], "
        "  \"estimated_time_to_operational_setup_days\": 30"
        "}"
    )
    
    task_context = f"Task: {state['task_details']}\nTarget Company: {state['target_company_name']}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Create a complete blueprint based on: {task_context}\n\nRefine this existing blueprint: {json.dumps(refined_blueprint)}"}
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
            state['final_blueprint'] = validated_blueprint.model_dump()
            state['validation_result'] = {"status": "success", "message": "Blueprint validated successfully"}
            logging.info("Blueprint validation successful")
            
        except ValidationError as e:
            logging.error(f"Pydantic validation failed: {e}")
            
            # Try to fix common validation issues programmatically
            fixed_blueprint = final_blueprint.copy()
            
            # Ensure required fields exist with proper defaults
            if 'company_name_suggestion' not in fixed_blueprint or not fixed_blueprint['company_name_suggestion']:
                fixed_blueprint['company_name_suggestion'] = f"AI Solutions for {state['task_details'][:50]}"
            
            if 'specialization' not in fixed_blueprint or not fixed_blueprint['specialization']:
                fixed_blueprint['specialization'] = state['task_details']
                
            if 'mission_statement_draft' not in fixed_blueprint or len(fixed_blueprint.get('mission_statement_draft', '')) < 20:
                fixed_blueprint['mission_statement_draft'] = f"To revolutionize {state['task_details']} through innovative AI solutions that deliver exceptional value to our clients and transform the industry."
                
            if 'key_ai_employee_roles' not in fixed_blueprint or not isinstance(fixed_blueprint.get('key_ai_employee_roles'), list) or len(fixed_blueprint.get('key_ai_employee_roles', [])) == 0:
                fixed_blueprint['key_ai_employee_roles'] = [
                    {
                        "role_title": "AI Solutions Architect",
                        "responsibilities": ["Design AI system architecture", "Oversee technical implementation", "Ensure scalability and performance"],
                        "reports_to": "Chief Technology Officer"
                    },
                    {
                        "role_title": "AI Operations Manager",
                        "responsibilities": ["Manage daily AI operations", "Ensure quality standards", "Coordinate with client teams"],
                        "reports_to": "AI Solutions Architect"
                    },
                    {
                        "role_title": "AI Data Specialist",
                        "responsibilities": ["Manage data pipelines", "Ensure data quality", "Implement data governance"],
                        "reports_to": "AI Solutions Architect"
                    }
                ]
                
            if 'initial_sop_ideas' not in fixed_blueprint or not isinstance(fixed_blueprint.get('initial_sop_ideas'), list) or len(fixed_blueprint.get('initial_sop_ideas', [])) < 3:
                fixed_blueprint['initial_sop_ideas'] = [
                    "SOP for Client Onboarding and Requirements Gathering",
                    "SOP for AI Model Development and Testing",
                    "SOP for Quality Assurance and Validation",
                    "SOP for Client Delivery and Support",
                    "SOP for Data Security and Privacy Compliance"
                ]
            
            if 'estimated_time_to_operational_setup_days' not in fixed_blueprint:
                fixed_blueprint['estimated_time_to_operational_setup_days'] = 30
            
            try:
                # Try validation again with fixed blueprint
                validated_blueprint = CompanyBlueprintV1(**fixed_blueprint)
                state['final_blueprint'] = validated_blueprint.model_dump()
                state['validation_result'] = {"status": "success_with_fixes", "message": "Blueprint validated after automatic fixes", "original_error": str(e)}
                logging.info("Blueprint validation successful after automatic fixes")
                
            except ValidationError as e2:
                logging.error(f"Validation failed even after fixes: {e2}")
                state['validation_result'] = {"status": "failed", "message": str(e2), "blueprint": fixed_blueprint, "original_error": str(e)}
                state['error'] = f"Validation failed: {str(e2)}"
            
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