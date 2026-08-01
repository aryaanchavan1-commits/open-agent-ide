from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    local: bool = False
    size_bytes: int = 0
    capabilities: list[str] = []


class ProviderError(Exception):
    pass


class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        system: Optional[str] = None,
    ) -> str:
        ...

    @abstractmethod
    def stream_chat(
        self,
        messages: list[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        system: Optional[str] = None,
    ) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...

    async def generate_plan(
        self, description: str, context: str = "", model: Optional[str] = None
    ) -> str:
        return await self.chat(
            [
                ChatMessage(
                    role="system",
                    content=(
                        "You are a software planning assistant. Break a software project "
                        "description into structured tasks. Reply with valid JSON only."
                    ),
                ),
                ChatMessage(role="user", content=f"Project description:\n{description}\n\nContext:\n{context}"),
            ],
            model=model,
            json_mode=True,
        )

    async def generate_code(
        self, specification: str, context: str = "", model: Optional[str] = None
    ) -> str:
        return await self.chat(
            [
                ChatMessage(
                    role="system",
                    content="You are an expert software engineer. Write clean, working code for the specification.",
                ),
                ChatMessage(role="user", content=f"Specification:\n{specification}\n\nExisting code context:\n{context}"),
            ],
            model=model,
        )

    async def analyze_code(
        self, code: str, context: str = "", model: Optional[str] = None
    ) -> str:
        return await self.chat(
            [
                ChatMessage(
                    role="system",
                    content="You are a senior code reviewer. Identify bugs, security issues, and improvements. Be specific.",
                ),
                ChatMessage(role="user", content=f"Code to review:\n{code}\n\nContext:\n{context}"),
            ],
            model=model,
        )
