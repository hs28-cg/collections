from pydantic import BaseModel, Field

class SaveSummary(BaseModel):
    """
    Tool used by the agent to save the transcript summary.
    """
    # THE PROMPT FOR THIS TOOL goes inside the description below. 
    # This tells the LLM exactly what to focus on when generating the summary.
    summary: str = Field(
        description=(
            "Generate a 2-3 sentence summary of the call transcript. "
            "Focus on the main reason for the call, any payment agreements made, and customer sentiment."
        )
    )