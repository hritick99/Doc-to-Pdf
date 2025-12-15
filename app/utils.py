import os
import zipfile
import uuid
from pathlib import Path
from typing import List
import shutil

STORAGE_PATH = os.getenv("STORAGE_PATH", "/app/storage")
TEMP_PATH = os.path.join(STORAGE_PATH, "temp")
OUTPUT_PATH = os.path.join(STORAGE_PATH, "output")

def ensure_directories():
    """Create necessary directories if they don't exist"""
    Path(TEMP_PATH).mkdir(parents=True, exist_ok=True)
    Path(OUTPUT_PATH).mkdir(parents=True, exist_ok=True)

def get_job_temp_dir(job_id: str) -> str:
    """Get temporary directory for a job"""
    path = os.path.join(TEMP_PATH, job_id)
    Path(path).mkdir(parents=True, exist_ok=True)
    return path

def get_job_output_dir(job_id: str) -> str:
    """Get output directory for a job"""
    path = os.path.join(OUTPUT_PATH, job_id)
    Path(path).mkdir(parents=True, exist_ok=True)
    return path

def extract_docx_files(zip_path: str, destination: str) -> List[str]:
    """Extract DOCX files from uploaded zip"""
    docx_files = []
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file_info in zip_ref.filelist:
            # Skip directories and hidden files
            if file_info.is_dir() or file_info.filename.startswith('.'):
                continue
                
            # Only extract DOCX files
            if file_info.filename.lower().endswith('.docx'):
                # Extract with original filename (basename only)
                filename = os.path.basename(file_info.filename)
                target_path = os.path.join(destination, filename)
                
                with zip_ref.open(file_info) as source, open(target_path, 'wb') as target:
                    shutil.copyfileobj(source, target)
                
                docx_files.append(filename)
    
    return docx_files

def create_result_zip(job_id: str) -> str:
    """Create zip archive of all converted PDFs"""
    output_dir = get_job_output_dir(job_id)
    zip_path = os.path.join(OUTPUT_PATH, f"{job_id}.zip")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.endswith('.pdf'):
                    file_path = os.path.join(root, file)
                    arcname = os.path.basename(file)
                    zipf.write(file_path, arcname)
    
    return zip_path

def cleanup_job_files(job_id: str):
    """Clean up temporary and output files for a job"""
    temp_dir = get_job_temp_dir(job_id)
    output_dir = get_job_output_dir(job_id)
    
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)