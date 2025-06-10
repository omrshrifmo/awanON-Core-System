import json
import logging
from typing import Dict, Any, TypedDict, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from litellm import completion
from models import CompanyBlueprintV1
from pydantic import ValidationError
from rag_utils import query_vector_store

# Setup logging
logging.basicConfig(level=logging.INFO, format='[LangGraph Agent] %(asctime)s - %(levelname)s - %(message)s')

class AgentState(TypedDict):
    task_details: str
    target_company_name: str
    model_name: str
    analysis_result: Dict[str, Any]
    research_context: Dict[str, Any]
    research_findings: Optional[str]  # RAG retrieved documents
    blueprint_draft: Dict[str, Any]
    refined_blueprint: Dict[str, Any]
    final_blueprint: Dict[str, Any] # This will store the final output or error
    validation_result: Dict[str, Any]
    error: str # For capturing processing errors
    is_blueprint_request: Optional[bool] = True # New field for task type

def analyze_task(state: AgentState) -> dict: # Return type changed to dict
    """Step 1: Analyze the task requirements and extract key information, determine task type"""
    logging.info(f"NODE: Starting analyze_task. Task details (first 200 chars): {str(state.get('task_details'))[:200]}...")
    
    system_prompt_task_analysis = ( # Renamed for clarity in logging
        "You are a business analysis AI. Analyze the given task and extract key business requirements. "
        "Respond with a JSON object containing: "
        "- business_domain: string (the main business domain) "
        "- key_requirements: array of strings (main requirements) "
        "- target_market: string (who the target customers are) "
        "- complexity_level: string (simple/medium/complex) "
        "- is_blueprint_task: boolean (true if the request is primarily for a company blueprint, false otherwise) "
        "Respond with ONLY the JSON object, no markdown formatting."
    )
    
    messages = [
        {"role": "system", "content": system_prompt_task_analysis},
        {"role": "user", "content": f"Analyze this business task: {state['task_details']}"}
    ]
    
    analysis_output = {}
    try:
        logging.info(f"analyze_task: Sending prompt to LLM (snippet): {system_prompt_task_analysis[:100]}... User input (snippet): {state.get('task_details')[:100]}...")
        response = completion(
            model=state['model_name'],
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        llm_response_str = response.choices[0].message.content
        logging.debug(f"analyze_task: Raw LLM response: {llm_response_str}")
        response_json = json.loads(llm_response_str)

        analysis_result = {key: response_json[key] for key in response_json if key != 'is_blueprint_task'}
        is_blueprint = response_json.get("is_blueprint_task", True) # Default to True if missing

        # Original log preserved and enhanced by the NODE log at the end
        # logging.info(f"Task analysis completed: {analysis_result.get('business_domain', 'Unknown domain')}, Is Blueprint Request: {is_blueprint}")
        analysis_output = {
            "analysis_result": analysis_result,
            "is_blueprint_request": is_blueprint
        }
        
    except Exception as e:
        logging.error(f"Error in analyze_task: {e}", exc_info=True) # Added exc_info
        analysis_output = {
            "error": f"Analysis failed: {str(e)}",
            "analysis_result": {},
            "is_blueprint_request": True
        }

    logging.info(f"NODE: Finished analyze_task. Analysis result (snippet): {str(analysis_output.get('analysis_result'))[:100]}... Is blueprint request: {analysis_output.get('is_blueprint_request')}")
    return analysis_output

def research_industry(state: AgentState) -> AgentState:
    """Step 2: Research industry context using RAG from knowledge base"""
    logging.info(f"NODE: Starting research_industry. Using analysis: {str(state.get('analysis_result'))[:100]}...")
    
    if state.get('error'):
        logging.warning("research_industry: Skipping due to previous error in state.")
        return state # type: ignore # state is AgentState, but mypy might complain due to TypedDict specifics
        
    analysis = state.get('analysis_result', {})
    business_domain = analysis.get('business_domain', 'AI services')
    task_details = state.get('task_details', '')
    
    # Formulate search query based on task details and business domain
    search_query = f"Information regarding: {task_details} {business_domain} company blueprint SOP best practices"
    
    research_findings_str = "" # For logging at the end
    try:
        # Query the vector store for relevant documents
        logging.info(f"research_industry: Querying vector store with: {search_query}")
        retrieved_docs = query_vector_store(search_query, k=3)
        logging.info(f"research_industry: Retrieved {len(retrieved_docs)} documents from vector store. First doc (snippet): {str(retrieved_docs[0])[:100] if retrieved_docs else 'N/A'}")
        
        if retrieved_docs and not any("Error:" in doc for doc in retrieved_docs):
            # Join retrieved documents into a single context string
            research_findings = "\n\n---\n\n".join(retrieved_docs)
            state['research_findings'] = research_findings
            research_findings_str = research_findings # For logging
            
            # Log summary of retrieved context
            total_chars = len(research_findings)
            logging.info(f"Retrieved {len(retrieved_docs)} documents with {total_chars} characters total")
            logging.info(f"Research findings preview: {research_findings[:200]}...")
            
            # Create a structured research context for backward compatibility
            state['research_context'] = {
                "source": "RAG_knowledge_base",
                "documents_retrieved": len(retrieved_docs),
                "total_content_length": total_chars,
                "search_query": search_query,
                "summary": f"Retrieved {len(retrieved_docs)} relevant documents from knowledge base"
            }
            
        else:
            # Handle case where RAG retrieval failed or returned errors
            error_msg = "No relevant documents found in knowledge base"
            if retrieved_docs and any("Error:" in doc for doc in retrieved_docs):
                error_msg = retrieved_docs[0]  # Use the error message
            
            logging.warning(f"RAG retrieval issue: {error_msg}")
            state['research_findings'] = f"RAG retrieval note: {error_msg}"
            research_findings_str = state['research_findings'] # For logging
            state['research_context'] = {
                "source": "RAG_fallback",
                "error": error_msg,
                "search_query": search_query
            }
        
        logging.info("RAG-based research completed")
        
    except Exception as e:
        logging.error(f"Error in RAG research: {e}", exc_info=True) # Added exc_info
        state['error'] = f"RAG research failed: {str(e)}"

    logging.info(f"NODE: Finished research_industry. Research findings (first 100 chars): {research_findings_str[:100]}...")
    return state # type: ignore

def generate_blueprint(state: AgentState) -> AgentState:
    """Step 3: Generate initial company blueprint using RAG research findings"""
    logging.info(f"NODE: Starting generate_blueprint. Using research (first 100 chars): {str(state.get('research_findings'))[:100]}...")
    
    if state.get('error'):
        logging.warning("generate_blueprint: Skipping due to previous error in state.")
        return state # type: ignore
        
    analysis = state.get('analysis_result', {})
    research = state.get('research_context', {})
    research_findings = state.get('research_findings', '')
    
    system_prompt = (
        "You are an expert strategic business consultant AI. Generate a detailed company blueprint "
        "based on the analysis and research findings provided. Use the research findings from the "
        "knowledge base to inform your blueprint design, especially for SOPs and best practices. "
        "The output MUST be a valid JSON object that conforms to the CompanyBlueprintV1 Pydantic model. "
        "Respond with *ONLY* the JSON object and nothing else. Do not include any markdown formatting "
        "like ```json or ``` at the beginning or end. Do not include any explanatory text outside "
        "of the JSON structure. "
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
        f"Research Context: {json.dumps(research)}\n\n"
        f"Research Findings from Knowledge Base:\n"
        f"{research_findings}\n"
        f"---\n"
        f"Based on the above research findings, generate the blueprint incorporating relevant "
        f"best practices, SOP templates, and design principles found in the knowledge base."
    )
    
    messages = [
        {"role": "system", "content": system_prompt_blueprint_generation}, # Renamed var for logging
        {"role": "user", "content": user_content}
    ]
    
    blueprint_draft_str = "" # For logging
    try:
        logging.info(f"generate_blueprint: Sending prompt to LLM (snippet): {system_prompt_blueprint_generation[:100]}... Context (snippet): {user_content[:100]}...")
        response = completion(
            model=state['model_name'],
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        llm_response_str = response.choices[0].message.content
        logging.debug(f"generate_blueprint: Raw LLM response: {llm_response_str}")
        blueprint_draft = json.loads(llm_response_str)
        blueprint_draft_str = llm_response_str # For logging
        state['blueprint_draft'] = blueprint_draft
        logging.info("Initial blueprint generated with RAG context") # Original log kept
        
    except Exception as e:
        logging.error(f"Error in generate_blueprint: {e}", exc_info=True) # Added exc_info
        state['error'] = f"Blueprint generation failed: {str(e)}"

    logging.info(f"NODE: Finished generate_blueprint. Initial blueprint (first 100 chars): {blueprint_draft_str[:100]}...")
    return state # type: ignore

def review_and_refine(state: AgentState) -> AgentState:
    """Step 4: Review and refine the blueprint"""
    logging.info(f"NODE: Starting review_and_refine. Initial blueprint (first 100 chars): {str(state.get('blueprint_draft'))[:100]}...")
    
    if state.get('error'):
        logging.warning("review_and_refine: Skipping due to previous error in state.")
        return state # type: ignore
        
    blueprint = state.get('blueprint_draft', {})
    blueprint_str_for_log = json.dumps(blueprint) # For logging
    
    system_prompt_review_refine = ( # Renamed for clarity
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
        {"role": "system", "content": system_prompt_review_refine},
        {"role": "user", "content": f"Review and refine this blueprint: {blueprint_str_for_log}"}
    ]
    
    refined_blueprint_json_str = "" # For logging
    try:
        logging.info(f"review_and_refine: Sending prompt to LLM (snippet): {system_prompt_review_refine[:100]}... Blueprint (snippet): {blueprint_str_for_log[:100]}...")
        response = completion(
            model=state['model_name'],
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        llm_response_str = response.choices[0].message.content
        logging.debug(f"review_and_refine: Raw LLM response: {llm_response_str}")
        refined_blueprint = json.loads(llm_response_str)
        refined_blueprint_json_str = llm_response_str # For logging
        state['refined_blueprint'] = refined_blueprint
        logging.info("Blueprint refined") # Original log kept
        
    except Exception as e:
        logging.error(f"Error in review_and_refine: {e}", exc_info=True) # Added exc_info
        state['error'] = f"Blueprint refinement failed: {str(e)}"
        
    logging.info(f"NODE: Finished review_and_refine. Refined blueprint (first 100 chars): {refined_blueprint_json_str[:100]}...")
    return state # type: ignore

def validate_output(state: AgentState) -> AgentState:
    """Step 5: Validate the final blueprint against Pydantic model"""
    logging.info(f"NODE: Starting validate_output. Refined blueprint (first 100 chars): {str(state.get('refined_blueprint'))[:100]}...")
    
    if state.get('error'):
        logging.warning("validate_output: Skipping due to previous error in state.")
        return state # type: ignore
        
    refined_blueprint = state.get('refined_blueprint', {})
    blueprint_to_validate_str = json.dumps(refined_blueprint) # For logging
    
    # Enhanced system prompt for final validation and completion with explicit field requirements
    system_prompt_validation = ( # Renamed for clarity
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
        {"role": "system", "content": system_prompt_validation},
        {"role": "user", "content": f"Create a complete blueprint based on: {task_context}\n\nRefine this existing blueprint: {blueprint_to_validate_str}"}
    ]
    
    final_blueprint_str = "" # For logging
    validation_errors_json = "" # For logging
    try:
        logging.info(f"validate_output: Sending prompt to LLM (snippet): {system_prompt_validation[:100]}... Blueprint (snippet): {blueprint_to_validate_str[:100]}...")
        response = completion(
            model=state['model_name'],
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        llm_response_str = response.choices[0].message.content
        logging.debug(f"validate_output: Raw LLM response: {llm_response_str}")
        final_blueprint = json.loads(llm_response_str)
        final_blueprint_str = llm_response_str # For logging
        
        # Validate against Pydantic model
        try:
            validated_blueprint = CompanyBlueprintV1(**final_blueprint)
            state['final_blueprint'] = validated_blueprint.model_dump()
            state['validation_result'] = {"status": "success", "message": "Blueprint validated successfully"}
            logging.info("Blueprint validation successful") # Original log
            
        except ValidationError as e:
            logging.error(f"Pydantic validation failed: {e}")
            validation_errors_json = str(e) # For logging
            
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
                fixed_blueprint['key_ai_employee_roles'] = [{"role_title": "AI Lead", "responsibilities": ["Lead AI strategy"], "reports_to": "CEO"}] # Simplified
                
            if 'initial_sop_ideas' not in fixed_blueprint or not isinstance(fixed_blueprint.get('initial_sop_ideas'), list) or len(fixed_blueprint.get('initial_sop_ideas', [])) < 3:
                fixed_blueprint['initial_sop_ideas'] = ["Client Onboarding", "Project Execution", "Quality Assurance"] # Simplified
            
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
                validation_errors_json = str(e2) # For logging
                state['validation_result'] = {"status": "failed", "message": str(e2), "blueprint": fixed_blueprint, "original_error": str(e)}
                state['error'] = f"Validation failed: {str(e2)}"
            
    except Exception as e:
        logging.error(f"Error in validate_output: {e}", exc_info=True) # Added exc_info
        state['error'] = f"Final validation failed: {str(e)}"

    logging.info(f"NODE: Finished validate_output. Validation errors: {validation_errors_json}. Final blueprint (first 100 chars): {final_blueprint_str[:100]}...")
    return state # type: ignore

def create_workflow(model_name: str) -> StateGraph:
    """Create the LangGraph workflow"""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("analyze_task", analyze_task)
    workflow.add_node("research_industry", research_industry)
    workflow.add_node("generate_blueprint", generate_blueprint)
    workflow.add_node("review_and_refine", review_and_refine)
    workflow.add_node("validate_output", validate_output)
    workflow.add_node("handle_unsupported_task", handle_unsupported_task_node)

    # Define conditional routing after analysis
    def should_proceed_to_research(state: AgentState) -> str:
        # Default to True if 'is_blueprint_request' is missing, or if an error occurred in analysis
        # The analyze_task node defaults is_blueprint_request to True on error to allow flow to continue.
        # A more robust graph might have explicit error transitions from analyze_task to an error handling node or END.
        is_blueprint = state.get('is_blueprint_request', True)

        # If a critical error occurred in analyze_task that should halt normal processing
        if state.get('error') and not is_blueprint : # Example: if error exists AND it's not a blueprint request
             logging.error(f"Critical error during analysis and not a blueprint request: {state.get('error')}")
             # This specific condition might be better handled by analyze_task directly populating
             # final_blueprint with an error and is_blueprint_request=False to go to handle_unsupported_task.
             # For now, this logic primarily routes based on is_blueprint_request.
             # If analysis has an error, it might still try to proceed as a blueprint request by default.

        logging.info(f"Conditional routing: is_blueprint_request = {is_blueprint}")
        if is_blueprint:
            return "research_industry"
        else:
            return "handle_unsupported_task"

    # Define the flow
    workflow.set_entry_point("analyze_task")
    workflow.add_conditional_edges(
        "analyze_task",
        should_proceed_to_research,
        {
            "research_industry": "research_industry",
            "handle_unsupported_task": "handle_unsupported_task"
        }
    )

    workflow.add_edge("research_industry", "generate_blueprint")
    workflow.add_edge("generate_blueprint", "review_and_refine")
    workflow.add_edge("review_and_refine", "validate_output")
    workflow.add_edge("validate_output", END)
    workflow.add_edge("handle_unsupported_task", END) # Unsupported tasks go to END
    
    return workflow.compile()


def handle_unsupported_task_node(state: AgentState) -> dict:
    logging.info(f"NODE: Starting handle_unsupported_task_node. Task details (first 100 chars): {str(state.get('task_details'))[:100]}...")
    # Original log: logging.info("Unsupported task type received...") -> Covered by NODE log
    error_message = "This agent is designed to generate company blueprints. The provided request does not appear to be for a blueprint."
    error_payload = {"error": "Unsupported Task Type", "message": error_message}

    logging.info(f"NODE: Finished handle_unsupported_task_node. Error: {error_payload.get('error')}, Message: {error_payload.get('message')}")
    return {
        "final_blueprint": error_payload,
        "validation_result": {"status": "failed", "message": error_message}, # Mimic validation failure
        "error": error_message, # Set top-level error
        "status_message": f"Task failed: {error_message}" # Added for clearer status
    }

def run_agent_workflow(task_details: str, target_company_name: str, model_name: str) -> Dict[str, Any]:
    """Run the complete LangGraph workflow"""
    logging.info(f"Starting LangGraph workflow for: {target_company_name} (Task: {str(task_details)[:100]}...)") # Added task details to initial log
    
    # Create workflow
    app = create_workflow(model_name)
    
    # Initial state
    initial_state = {
        "task_details": task_details,
        "target_company_name": target_company_name,
        "model_name": model_name,
        "analysis_result": {},
        "research_context": {},
        "research_findings": None,
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
            logging.error(f"Workflow completed with error: {final_state['error']}") # Added error log
            return {
                "error": final_state['error'],
                "status_message": final_state.get('status_message', final_state['error']), # Use specific status_message if available
                "blueprint": final_state.get('final_blueprint', {}), # Include final_blueprint even if error
                "workflow_type": "langgraph_multi_step",
                "validation_result": final_state.get('validation_result', {}),
                "partial_results": { # Keep partial results for debugging
                    "analysis": final_state.get('analysis_result', {}),
                    "research": final_state.get('research_context', {}),
                    "blueprint_draft": final_state.get('blueprint_draft', {}),
                    "refined_blueprint": final_state.get('refined_blueprint', {})
                }
            }
        
        logging.info(f"Workflow completed successfully for {target_company_name}. Final blueprint (snippet): {str(final_state.get('final_blueprint'))[:100]}...") # Added success log
        return {
            "blueprint": final_state.get('final_blueprint', {}),
            "workflow_type": "langgraph_multi_step",
            "validation_result": final_state.get('validation_result', {}),
            "status_message": final_state.get('status_message', "Task completed successfully."), # Add status message
            "workflow_steps": {
                "analysis": final_state.get('analysis_result', {}),
                "research": final_state.get('research_context', {}),
                "blueprint_draft": final_state.get('blueprint_draft', {}),
                "refined_blueprint": final_state.get('refined_blueprint', {})
            }
        }
        
    except Exception as e:
        logging.error(f"Workflow execution failed with unhandled exception: {e}", exc_info=True) # Log stack trace
        return {
            "error": f"Workflow execution failed with unhandled exception: {str(e)}",
            "status_message": "Critical workflow error.",
            "workflow_type": "langgraph_multi_step"
        }