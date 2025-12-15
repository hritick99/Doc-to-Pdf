from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.models import JobStatus, FileStatus

class FileStatusResponse(BaseModel):
    filename: str
    status: FileStatus
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True

class JobCreateResponse(BaseModel):
    job_id: str
    file_count: int

class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    download_url: Optional[str] = None
    files: List[FileStatusResponse]
    
    class Config:
        from_attributes = True