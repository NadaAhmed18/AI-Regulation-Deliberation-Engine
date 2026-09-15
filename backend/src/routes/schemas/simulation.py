from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

MemoryType = Literal["sliding_window", "summary", "full"]


class MemoryConfig(BaseModel):
    type: MemoryType = "sliding_window"
    window_size: int = Field(default=4, ge=1)


class Persona(BaseModel):
    name: str
    background: str
    stance: str
    tone: str
    avatarSeed: Optional[str] = None
    memory_config: Optional[MemoryConfig] = None


class GeneratePersonasRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    num_agents: int = Field(default=3, ge=2, le=6)
    custom_prompt: Optional[str] = None
    default_memory_type: MemoryType = "sliding_window"


class StartSimulationRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    personas: List[Persona] = Field(..., min_length=2, max_length=6)
    memory_strategy: MemoryConfig = Field(default_factory=MemoryConfig)
    visibility_matrix: Optional[Dict[str, List[str]]] = None
    stream: bool = Field(default=False, description="If True, immediately begins streaming via SSE")


class ContinueSimulationRequest(BaseModel):
    steps: int = Field(default=1, ge=1)


class PredefinedTopic(BaseModel):
    id: str
    title: str
    tag: str
    description: str