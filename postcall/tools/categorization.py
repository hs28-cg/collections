from pydantic import BaseModel, Field

class SaveCategorization(BaseModel):
    """
    Tool used by the agent to save the categorization.
    """
    category: str = Field(
        description=(
            "Categorize the overall outcome of the call. "
            "You MUST classify the call exactly as ONE of the following: "
            "'pending', 'cleared', or 'dispute'."
        )
    )