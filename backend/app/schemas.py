from typing import Literal

from pydantic import BaseModel


Outcome = Literal["replied", "interested", "meeting_booked", "disqualified"]
Target = Literal["replied", "interested", "meeting_booked"]


class OutcomeUpdate(BaseModel):
    outcome: Outcome
