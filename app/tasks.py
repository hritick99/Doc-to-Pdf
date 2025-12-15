from celery import chord
from app.celery_app import celery_app
from app.database import get_db_context
from app.models import Job, File, JobStatus, FileStatus
from app.utils import get_job_temp_dir, get_job_output_dir, create_result_zip
import os
import logging
from pathlib import Path

# Pure Python conversion
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def convert_docx_to_pdf(self, job_id: str, filename: str):
    
    logger.info(f"Starting conversion for {filename} in job {job_id}")
    
    with get_db_context() as db:
        file_record = db.query(File).filter(
            File.job_id == job_id,
            File.filename == filename
        ).first()
        
        if not file_record:
            logger.error(f"File record not found: {filename}")
            return
        
        file_record.status = FileStatus.PROCESSING
        db.commit()
        
        temp_dir = get_job_temp_dir(job_id)
        output_dir = get_job_output_dir(job_id)
        
        input_path = os.path.join(temp_dir, filename)
        output_filename = Path(filename).stem + ".pdf"
        output_path = os.path.join(output_dir, output_filename)
        
        try:
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")
            
            # Read DOCX
            doc = Document(input_path)
            
            # Create PDF
            pdf = SimpleDocTemplate(output_path, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Convert paragraphs
            for para in doc.paragraphs:
                if para.text.strip():
                    p = Paragraph(para.text, styles['Normal'])
                    story.append(p)
                    story.append(Spacer(1, 12))
            
            # Build PDF
            pdf.build(story)
            
            # Verify output
            if not os.path.exists(output_path):
                raise Exception(f"PDF not created: {output_path}")
            
            file_record.status = FileStatus.COMPLETED
            file_record.error_message = None
            db.commit()
            
            logger.info(f"Successfully converted {filename} to PDF")
            return {"status": "success", "filename": filename}
            
        except Exception as e:
            error_msg = f"Conversion failed for {filename}: {str(e)}"
            logger.error(error_msg)
            
            file_record.status = FileStatus.FAILED
            file_record.error_message = str(e)
            db.commit()
            
            return {"status": "failed", "filename": filename, "error": str(e)}

@celery_app.task
def finalize_job(results, job_id: str):  # FIXED: Added 'results' parameter
  
    logger.info(f"Finalizing job {job_id}")
    
    with get_db_context() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            logger.error(f"Job not found: {job_id}")
            return
        
        completed_files = db.query(File).filter(
            File.job_id == job_id,
            File.status == FileStatus.COMPLETED
        ).count()
        
        failed_files = db.query(File).filter(
            File.job_id == job_id,
            File.status == FileStatus.FAILED
        ).count()
        
        job.completed_count = completed_files
        job.failed_count = failed_files
        
        try:
            if completed_files > 0:
                zip_path = create_result_zip(job_id)
                logger.info(f"Created result zip: {zip_path}")
            
            if failed_files == job.file_count:
                job.status = JobStatus.FAILED
            elif completed_files > 0:
                job.status = JobStatus.COMPLETED
            else:
                job.status = JobStatus.FAILED
            
            db.commit()
            logger.info(f"Job {job_id} finalized with status {job.status}")
            
        except Exception as e:
            logger.error(f"Error finalizing job {job_id}: {str(e)}")
            job.status = JobStatus.FAILED
            db.commit()

@celery_app.task
def process_job(job_id: str, filenames: list):
    
    logger.info(f"Processing job {job_id} with {len(filenames)} files")
    
    with get_db_context() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.IN_PROGRESS
            db.commit()
    
    conversion_tasks = [convert_docx_to_pdf.s(job_id, filename) for filename in filenames]
    chord(conversion_tasks)(finalize_job.s(job_id))