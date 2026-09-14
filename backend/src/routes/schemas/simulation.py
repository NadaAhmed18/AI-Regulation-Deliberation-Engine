from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


MemoryType = Literal[
    "sliding_window",
    "summary",
    "full",
]


class MemoryConfig(BaseModel):
    type: MemoryType = "sliding_window"
    window_size: int = Field(default=4, ge=1)


class Persona(BaseModel):
    id: Optional[str] = None
    name: str
    background: str
    stance: str
    tone: str
    avatarSeed: str
    memory_config: Optional[MemoryConfig] = None


class GeneratePersonasRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    num_agents: int = Field(default=3, ge=2, le=6)
    custom_prompt: Optional[str] = None
    default_memory_type: MemoryType = "sliding_window"


class StartSimulationRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    personas: List[Persona] = Field(..., min_length=2, max_length=6)
    memory_strategy: MemoryConfig = Field(
        default_factory=MemoryConfig
    )
    visibility_matrix: Optional[Dict[str, List[str]]] = None
    stream: bool = Field(default=False, description="If True, immediately streams initialization and Turn 1 via SSE")


class StartSimulationResponse(BaseModel):
    simulation_id: str


class ContinueSimulationRequest(BaseModel):
    steps: int = Field(default=1, ge=1)
    stream: bool = Field(default=False, description="If True, streams turn execution via SSE")


class ContinueSimulationResponse(BaseModel):
    success: bool
    newTurnsCount: int


class OpinionConfig(BaseModel):
    guidance_scale_gamma: Optional[float] = None
    shift_magnitude: Optional[float] = None
    guidance_vector: Optional[float] = None
    dynamic: Optional[str] = None


class OpinionSnapshot(BaseModel):
    current_stance_score: float
    shift_magnitude: float
    influencer: Optional[str] = None
    reasoning: Optional[str] = None
    cfg: Optional[OpinionConfig] = None


class DiscussionTurn(BaseModel):
    id: str
    round_number: int
    agent_name: str
    content: str

    tools_called: List[Dict[str, Any]] = Field(
        default_factory=list
    )

    retrieved_sources: List[str] = Field(
        default_factory=list
    )

    opinion_snapshot: OpinionSnapshot

    timestamp: Optional[str] = None




class PredefinedTopic(BaseModel):
    id: Optional[str] = None
    title: str
    description: Optional[str] = None


class DebateHistoryItem(BaseModel):
    id: str
    topic: str
    status: Optional[str] = None
    created_at: Optional[Any] = None
    turn_count: int = 0


class SimulationAnalyticsRequest(BaseModel):
    current_turns: List[DiscussionTurn]
    current_personas: List[Persona]