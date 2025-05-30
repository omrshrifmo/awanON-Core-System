from pydantic import BaseModel, Field
from typing import List, Optional

class AIEEmployeeRole(BaseModel):
    role_title: str = Field(..., description="e.g., Chief Content Strategist AI, AI Project Manager")
    responsibilities: List[str] = Field(..., description="Key responsibilities for this AI role")
    reports_to: Optional[str] = Field(None, description="Title of the role this role reports to, if any")

class CompanyBlueprintV1(BaseModel):
    company_name_suggestion: str = Field(..., description="A creative and relevant suggested name for the new AI company")
    specialization: str = Field(..., description="The declared specialization from the input task")
    mission_statement_draft: str = Field(..., min_length=20, description="A concise and impactful mission statement for this AI company (at least 20 characters)")
    key_ai_employee_roles: List[AIEEmployeeRole] = Field(..., description="A list of 2 to 5 initial key AI employee roles needed for the company's operation")
    initial_sop_ideas: List[str] = Field(..., description="A list of 3 to 5 high-level ideas for initial Standard Operating Procedures (SOPs) relevant to the company's specialization")
    estimated_time_to_operational_setup_days: Optional[int] = Field(None, description="An estimated number of days to get the basic AI company operational")

    # Example for Pydantic v2 if needed for richer examples for the LLM
    # model_config = {
    #     "json_schema_extra": {
    #         "examples": [
    #             {
    #                 "company_name_suggestion": "InsightfulQuery AI",
    #                 "specialization": "AI-Powered Market Research",
    #                 "mission_statement_draft": "To provide businesses with actionable market insights through cutting-edge AI analysis, driving strategic decision-making.",
    #                 "key_ai_employee_roles": [
    #                     {"role_title": "AI Research Lead", "responsibilities": ["Oversee AI model development for market analysis", "Ensure data integrity"], "reports_to": "Chief AI Officer (Conceptual)"},
    #                     {"role_title": "Data Insights Communicator AI", "responsibilities": ["Translate complex data into understandable reports", "Interface with client query systems"], "reports_to": "AI Research Lead"}
    #                 ],
    #                 "initial_sop_ideas": [
    #                     "SOP for New Market Research Request Intake",
    #                     "SOP for AI Model Accuracy Verification",
    #                     "SOP for Client Report Generation and Delivery"
    #                 ],
    #                 "estimated_time_to_operational_setup_days": 14
    #             }
    #         ]
    #     }
    # }