from pydantic import BaseModel


class CapabilityMapResponse(BaseModel):
    capabilities: dict[str, bool]

