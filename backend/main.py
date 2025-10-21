from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
from typing import Optional
import asyncio
import datetime
from .models import (
    DocumentUploadResponse, 
    JobStatusResponse, 
    ParserType, 
    ProcessingStatus
)
from .services import redis_service

app = FastAPI(
    title="PDF Processing API",
    description="Async PDF processing with Redis Streams",
    version="1.0.0",
    json_encoder=None
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "PDF Processing API",
        "status": "running",
        "endpoints": {
            "upload": "/api/upload",
            "status": "/api/status/{job_id}",
            "docs": "/docs"
        }
    }

@app.post("/api/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to process"),
    parser: ParserType = Form(ParserType.PYPDF, description="Parser type: pypdf or gemini")
):
    """
    Upload a PDF document for processing
    
    - **file**: PDF file to upload
    - **parser**: Parser to use (pypdf or gemini)
    
    Returns a job_id that can be used to check processing status
    """
    
    # Validate file is provided
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file provided"
        )
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )
    
    # Validate file size (max 10MB)
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read file: {str(e)}"
        )
    
    if not content or len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="File is empty"
        )
    
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File size must be less than 10MB"
        )
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    try:
        # Add job to Redis Stream queue
        message_id = redis_service.add_job_to_queue(
            job_id=job_id,
            filename=file.filename,
            pdf_data=content,
            parser=parser
        )
        
        if not message_id:
            raise Exception("Failed to get message ID from Redis")
        
        return DocumentUploadResponse(
            job_id=job_id,
            status=ProcessingStatus.PENDING,
            message=f"Document queued for processing. Use job_id to check status."
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue document: {str(e)}"
        )

@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a processing job
    
    - **job_id**: The job ID returned from the upload endpoint
    
    Returns the current status and results (if completed)
    """
    
    # Validate job_id format
    if not job_id or not job_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Job ID is required"
        )
    
    try:
        # Validate UUID format
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID format"
        )
    
    # Poll Redis until the job is completed or failed, with increased timeout for large PDFs
    start_time = datetime.datetime.now()
    timeout = 300  # INCREASED TO 5 MINUTES for large PDFs (19+ pages)
    poll_interval = 2  # Check every 2 seconds
    
    result = None
    
    try:
        while (datetime.datetime.now() - start_time).total_seconds() < timeout:
            result = redis_service.get_result(job_id)
            
            if result:
                # Check if job is completed or failed
                if result.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
                    break
                # If pending or processing, wait and poll again
                await asyncio.sleep(poll_interval)
            else:
                # If job not found, return 404 immediately
                raise HTTPException(
                    status_code=404,
                    detail="Job not found"
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking job status: {str(e)}"
        )
    
    # After polling, if result is still None or timed out
    if not result:
        raise HTTPException(
            status_code=408,
            detail="Request timeout: Job processing took too long"
        )
    
    # If job is still processing after timeout, return current status anyway
    if result.status in [ProcessingStatus.PENDING, ProcessingStatus.PROCESSING]:
        # Don't raise error, just return the current status
        pass
    
    # Determine progress message
    progress = None
    if result.status == ProcessingStatus.PENDING:
        progress = "Waiting in queue..."
    elif result.status == ProcessingStatus.PROCESSING:
        progress = "Processing document... This may take several minutes for large PDFs."
    elif result.status == ProcessingStatus.COMPLETED:
        progress = "Processing complete!"
    elif result.status == ProcessingStatus.FAILED:
        progress = "Processing failed"
    
    return JobStatusResponse(
        job_id=result.job_id,
        filename=result.filename,
        parser=result.parser,
        status=result.status,
        content=result.content,
        summary=result.summary,
        error=result.error,
        progress=progress
    )

@app.get("/api/health")
async def health_check():
    """Check if Redis is accessible"""
    try:
        # Test Redis connection
        redis_service.client.ping()
        
        # Verify Redis is actually working
        test_key = "health_check_test"
        redis_service.client.set(test_key, "ok", ex=10)
        test_value = redis_service.client.get(test_key)
        
        if test_value != "ok":
            raise Exception("Redis read/write test failed")
        
        return {
            "status": "healthy",
            "redis": "connected"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "redis": "disconnected",
                "error": str(e)
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)