'''
This file is used to structure, validate and document data realted to action_items from call

1. user_action : Describes what the user/ customer needs to do after the call 
2. agent_action_item: Describes what the agent/ system needs to do after the call
 
'''

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