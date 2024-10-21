from typing import List, Dict

from pydantic import BaseModel, Field

class ChatLabelParser(BaseModel):
    chatLabel: str = Field(description="Response from AI for conversation label")
    
class ChatParser(BaseModel):
    message: str = Field(description="Response from AI")
    isGoalStepCompleted: bool = Field(default=False, description="Indicates if the Step-1 (Goal) is completed")
    isRealityStepCompleted: bool = Field(default=False, description="Indicates if the Step-2 (Reality) is completed")
    isOptionStepCompleted: bool = Field(default=False, description="Indicates if the Step-3 (Options) is completed")
    isOptionImprovementStepCompleted: bool = Field(default=False, description="Indicates if the Step-4 (Option Improvement) is completed")
    isWillStepCompleted: bool = Field(default=False, description="Indicates if the Step-5 (Will) is completed")

