from pydantic import BaseModel
from typing import List, Literal

class DialogueItem(BaseModel):
    text: str
    speaker: Literal["female-1", "female-2", "female-3", "male-1", "male-2", "male-3"]

    @property
    def voice(self):
        return {
            "male-1": "onyx",
            "male-2": "echo",
            "male-3": "fable",
            "female-1": "alloy",
            "female-2": "shimmer",
            "female-3": "nova"
        }[self.speaker]

class Dialogue(BaseModel):
    scratchpad: str
    dialogue: List[DialogueItem]