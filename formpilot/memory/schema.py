"""Pydantic schemas for FormPilot.

Defines the data contracts between scraper, brain, cli, and memory.
All models are immutable-by-convention (do not mutate after creation).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """Google Forms field types supported by FormPilot."""

    SHORT_TEXT = "short_text"  # Single line text
    PARAGRAPH = "paragraph"  # Multi-line text
    RADIO = "radio"  # Single choice
    CHECKBOX = "checkbox"  # Multiple choice
    DROPDOWN = "dropdown"  # Select from list
    LINEAR_SCALE = "linear_scale"  # 1-5 or 1-10 scale
    UNKNOWN = "unknown"  # Fallback for unrecognized types


class Question(BaseModel):
    """A single question extracted from a Google Form."""

    index: int = Field(..., ge=0, description="Question index within page (0-based)")
    text: str = Field(..., min_length=1, description="Question text (may include instructions)")
    field_type: FieldType = Field(..., description="Type of input field")
    options: list[str] = Field(
        default_factory=list,
        description="Available options for radio/checkbox/dropdown",
    )
    required: bool = Field(default=False, description="Whether the field is mandatory")
    has_media: bool = Field(
        default=False,
        description="Question has image/video (skip AI, ask user)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional extracted data (selector, position, etc.)",
    )


class ExtractedForm(BaseModel):
    """Result of extracting one page of a Google Form."""

    url: str = Field(..., description="Form URL")
    page_number: int = Field(..., ge=1, description="Current page (1-indexed)")
    total_pages_estimate: int | None = Field(
        default=None,
        description="Estimated total pages, if detectable",
    )
    questions: list[Question] = Field(
        default_factory=list,
        description="Questions on this page",
    )
    is_last_page: bool = Field(
        default=False,
        description="Whether this is the final page (has Submit button)",
    )


class Answer(BaseModel):
    """An answer to a question, with metadata about its source."""

    question_index: int = Field(..., ge=0, description="References Question.index")
    value: str = Field(..., description="Answer value (option text or free-form)")
    source: str = Field(
        ...,
        description="Where the answer came from: 'profile', 'vector', 'llm', 'user', 'skip'",
    )
    needs_cli: bool = Field(
        default=False,
        description="True if AI could not answer and user must be asked",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score (0-1)",
    )


class MemoryHit(BaseModel):
    """A single memory retrieval result."""

    question: str = Field(..., description="Original question text")
    answer: str = Field(..., description="Stored answer")
    similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity score (1.0 = identical)",
    )
    source: str = Field(..., description="Memory source: 'sqlite' or 'chroma'")
    timestamp: datetime | None = Field(
        default=None,
        description="When the memory was stored",
    )


class FormSession(BaseModel):
    """A single form-filling session, logged for audit and debugging."""

    url: str = Field(..., description="Form URL")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = Field(default=None)
    mode: str = Field(default="draft", description="'draft' or 'auto'")
    status: str = Field(
        default="pending",
        description="'pending', 'success', 'failed', 'aborted'",
    )
    total_pages: int = Field(default=0, ge=0)
    total_questions: int = Field(default=0, ge=0)
    questions_answered_by_ai: int = Field(default=0, ge=0)
    questions_answered_by_user: int = Field(default=0, ge=0)
    notes: str = Field(default="", description="Free-form notes")
