'''
This tool class is a Pydantic model used to validate and structure data when saving the categorization of a call
the call outcome must be classified as exactly one of these three options:
1. Pending 
2. Cleared
3. Dispute

'''


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