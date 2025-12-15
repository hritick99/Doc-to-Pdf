from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List
import uuid
import os
import shutil
from datetime import datetime

from app.database import get_db, engine
from app.models import Base, Job, File as FileModel, JobStatus
from app.schemas import JobCreateResponse, JobStatusResponse, FileStatusResponse
from app.utils import ensure_directories, get_job_temp_dir, extract_docx_files
from app.tasks import process_job
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DOCX to PDF Conversion Service",
    description="Asynchronous bulk document conversion service",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    ensure_directories()
    logger.info("Application started, storage directories initialized")

@app.get("/")
async def root():
    return {
        "service": "DOCX to PDF Conversion Service",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/jobs", response_model=JobCreateResponse, status_code=202)
async def create_job(
    file: UploadFile = File(..., description="Zip file containing DOCX files"),
    db: Session = Depends(get_db)
):
  
    # Validate file type
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="File must be a zip archive")
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    try:
        # Save uploaded zip to temporary location
        temp_dir = get_job_temp_dir(job_id)
        zip_path = os.path.join(temp_dir, "upload.zip")
        
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Saved uploaded zip for job {job_id}")
        
        # Extract DOCX files
        docx_files = extract_docx_files(zip_path, temp_dir)
        
        if not docx_files:
            raise HTTPException(
                status_code=400,
                detail="No DOCX files found in the uploaded zip"
            )
        
        logger.info(f"Extracted {len(docx_files)} DOCX files for job {job_id}")
        
        # Create job record in database
        job = Job(
            id=job_id,
            status=JobStatus.PENDING,
            file_count=len(docx_files)
        )
        db.add(job)
        
        # Create file records
        for filename in docx_files:
            file_record = FileModel(
                job_id=job_id,
                filename=filename
            )
            db.add(file_record)
        
        db.commit()
        logger.info(f"Created job {job_id} with {len(docx_files)} files")
        
        # Enqueue job for processing (asynchronous)
        process_job.delay(job_id, docx_files)
        
        return JobCreateResponse(
            job_id=job_id,
            file_count=len(docx_files)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")

@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
   
    
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Build response
    response = JobStatusResponse(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
        files=[
            FileStatusResponse(
                filename=f.filename,
                status=f.status,
                error_message=f.error_message
            )
            for f in job.files
        ]
    )
    
    # Add download URL if job is completed
    if job.status == JobStatus.COMPLETED:
        response.download_url = f"/api/v1/jobs/{job_id}/download"
    
    return response

@app.get("/api/v1/jobs/{job_id}/download")
async def download_results(job_id: str, db: Session = Depends(get_db)):
    
    
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed yet. Current status: {job.status}"
        )
    
    zip_path = os.path.join(os.getenv("STORAGE_PATH", "/app/storage"), "output", f"{job_id}.zip")
    
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Result file not found")
    
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"converted_{job_id}.zip"
    )

@app.delete("/api/v1/jobs/{job_id}")
async def delete_job(job_id: str, db: Session = Depends(get_db)):
   
    
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Clean up files
    from app.utils import cleanup_job_files
    cleanup_job_files(job_id)
    
    # Delete from database
    db.delete(job)
    db.commit()
    
    return {"message": f"Job {job_id} deleted successfully"}