from pydantic import BaseModel, Field

class SaveActionItems(BaseModel):
    """
    Tool used by the agent to save the action items.
    """
    user_action: str = Field(
        description="The action item that the USER (customer) needs to take based on the call."
    )
    agent_action_item: str = Field(
        description="The action item that the AGENT (caller/system) needs to take based on the call."
    )