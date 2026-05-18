from pydantic import BaseModel, EmailStr
from typing import Optional


class LeadSchema(BaseModel):
    name: str
    email: EmailStr
    company: str
    website: str
    notes: Optional[str] = None
