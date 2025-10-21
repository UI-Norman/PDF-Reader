from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum
from datetime import datetime


class ParserType(str, Enum):
    """Available PDF parser types"""
    PYPDF = "pypdf"
    GEMINI = "gemini"


class ProcessingStatus(str, Enum):
    """Processing job status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentUploadRequest(BaseModel):
    """Request model for document upload"""
    parser: ParserType = Field(
        default=ParserType.PYPDF,
        description="Parser to use for PDF extraction"
    )


class DocumentUploadResponse(BaseModel):
    """Response after document upload"""
    job_id: str
    status: ProcessingStatus
    message: str


class ProcessingResult(BaseModel):
    """Processing result stored in Redis"""
    job_id: str
    filename: str
    parser: ParserType
    status: ProcessingStatus
    content: Optional[str] = None
    summary: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Response for job status query"""
    job_id: str
    filename: str
    parser: ParserType
    status: ProcessingStatus
    content: Optional[str] = None
    summary: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[str] = None