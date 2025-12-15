# DOCX to PDF Conversion Service

A scalable microservice for bulk DOCX to PDF conversion with asynchronous processing.

## 🚀 Quick Start

### Prerequisites
- Docker Desktop installed
- 4GB RAM minimum

### Docker Configuration (Optional but Recommended)

Configure Docker to use registry mirrors for faster image downloads:

1. Open Docker Desktop
2. Go to Settings (gear icon)
3. Click on "Docker Engine"
4. Add this configuration:

```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false,
  "registry-mirrors": [
    "https://mirror.gcr.io",
    "https://dockerhub.azk8s.cn",
    "https://registry.docker-cn.com"
  ]
}
```

5. Click "Apply & Restart"

### Setup & Run

```bash
# 1. Clone the repository
git clone <repository-url>
cd docx-to-pdf-service

# 2. Start all services
docker-compose up --build -d

# 3. Verify services are running
docker-compose ps
```

Expected output:
```
NAME                    STATUS              PORTS
doc-to-pdf-api-1       Up (healthy)        0.0.0.0:8000->8000/tcp
doc-to-pdf-db-1        Up (healthy)        0.0.0.0:5432->5432/tcp
doc-to-pdf-redis-1     Up (healthy)        0.0.0.0:6379->6379/tcp
doc-to-pdf-worker-1    Up
doc-to-pdf-worker-2    Up
doc-to-pdf-flower-1    Up                  0.0.0.0:5555->5555/tcp
```

### Access Points
- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Task Monitoring**: http://localhost:5555

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Environment                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│  │   FastAPI    │   │  PostgreSQL  │   │    Redis     │   │
│  │ API Server   │───│   Database   │   │    Queue     │   │
│  │ (Port 8000)  │   │ (Port 5432)  │   │ (Port 6379)  │   │
│  └──────────────┘   └──────────────┘   └──────────────┘   │
│         │                                       │           │
│         │                                       │           │
│         ▼                                       ▼           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │      Celery Workers (2 replicas, 2 tasks each)       │  │
│  │         Processing DOCX → PDF conversions            │  │
│  └──────────────────────────────────────────────────────┘  │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────┐         ┌──────────────────────────┐    │
│  │    Flower    │         │  Shared Docker Volume    │    │
│  │ (Port 5555)  │         │  /app/storage/           │    │
│  └──────────────┘         │  - temp/  (uploads)      │    │
│                            │  - output/ (PDFs)        │    │
│                            └──────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Workflow Diagram

```
┌─────────┐
│ Client  │
└────┬────┘
     │
     │ 1. Upload ZIP with DOCX files
     ▼
┌─────────────────┐
│   FastAPI API   │
│  POST /jobs     │
└────┬────────────┘
     │
     │ 2. Extract files & Save to /temp
     │ 3. Create job in PostgreSQL
     │ 4. Enqueue tasks to Redis
     │ 5. Return job_id immediately
     │
     ▼
┌─────────────────┐
│  Redis Queue    │
│  [Task][Task]   │
└────┬────────────┘
     │
     │ 6. Workers pull tasks
     ▼
┌─────────────────────────────────────┐
│  Celery Workers (Parallel)          │
│  ┌─────────┐  ┌─────────┐          │
│  │Worker 1 │  │Worker 2 │          │
│  │Task 1   │  │Task 2   │          │
│  │Task 3   │  │Task 4   │          │
│  └─────────┘  └─────────┘          │
└────┬────────────────────────────────┘
     │
     │ 7. Read DOCX from /temp
     │ 8. Convert to PDF (python-docx + reportlab)
     │ 9. Save PDF to /output
     │ 10. Update file status in PostgreSQL
     │
     ▼
┌─────────────────┐
│  All files done │
│  Trigger finale │
└────┬────────────┘
     │
     │ 11. Create result ZIP
     │ 12. Update job status to COMPLETED
     ▼
┌─────────────────┐
│   PostgreSQL    │
│ Job: COMPLETED  │
└────┬────────────┘
     │
     │ 13. Client polls GET /jobs/{id}
     │ 14. Status: COMPLETED + download_url
     ▼
┌─────────┐
│ Client  │ 15. Download ZIP with PDFs
└─────────┘
```

### Data Flow

```
Upload → Extract → Queue → Process → Archive → Download
  ↓        ↓        ↓        ↓         ↓         ↓
 ZIP     DOCX    Redis   Workers    ZIP      Client
         files   Tasks   Convert    File
                         to PDF
```

---

## 🧪 Testing

### Run Automated Tests

```bash
# Install test dependencies
pip install requests python-docx

# Run the test
python tests/test_integration.py
```

Expected output:
```
============================================================
Testing DOCX to PDF Conversion Service
============================================================

1. Creating test documents and uploading...
   ✓ Job created: a1b2c3d4-...
   ✓ File count: 3

2. Waiting for conversion to complete...
   ✓ Conversion completed!

3. Checking individual file statuses:
   ✓ document_1.docx: COMPLETED
   ✓ document_2.docx: COMPLETED
   ✓ document_3.docx: COMPLETED

4. Downloading results...
   ✓ Downloaded: test_output_a1b2c3d4-....zip
   ✓ Size: 15234 bytes

5. Verifying zip contents:
   ✓ document_1.pdf (4567 bytes)
   ✓ document_2.pdf (4823 bytes)
   ✓ document_3.pdf (4691 bytes)

============================================================
All tests passed! ✓
============================================================
```

### Manual Testing

**Using Swagger UI (Easiest):**

1. Open http://localhost:8000/docs
2. Find `POST /api/v1/jobs` → Click "Try it out"
3. Upload a ZIP file with DOCX files → Click "Execute"
4. Copy the `job_id` from response
5. Find `GET /api/v1/jobs/{job_id}` → Paste job_id → Click "Execute"
6. Wait until status is "COMPLETED"
7. Find `GET /api/v1/jobs/{job_id}/download` → Click "Execute" → Download file

**Using cURL:**

```bash
# 1. Upload documents
curl -X POST http://localhost:8000/api/v1/jobs \
  -F "file=@documents.zip"

# Response: {"job_id":"a1b2c3d4-...","file_count":5}

# 2. Check status (replace {job_id})
curl http://localhost:8000/api/v1/jobs/{job_id}

# 3. Download results when status is COMPLETED
curl -O http://localhost:8000/api/v1/jobs/{job_id}/download
```

---

## 📚 API Endpoints

### 1. Submit Job
**POST** `/api/v1/jobs`
- Upload ZIP file with DOCX files
- Returns: `job_id` and `file_count`

### 2. Check Status
**GET** `/api/v1/jobs/{job_id}`
- Returns: job status and individual file statuses
- Status values: PENDING, IN_PROGRESS, COMPLETED, FAILED

### 3. Download Results
**GET** `/api/v1/jobs/{job_id}/download`
- Returns: ZIP file with converted PDFs
- Only available when status is COMPLETED

### 4. Health Check
**GET** `/health`
- Returns: Service health status

---

## 🛠️ Common Commands

```bash
# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f worker

# Restart services
docker-compose restart

# Stop services
docker-compose down

# Stop and remove all data
docker-compose down -v

# Scale workers
docker-compose up --scale worker=5 -d
```

---

## 🐛 Troubleshooting

**Services won't start:**
```bash
docker-compose down -v
docker system prune -f
docker-compose up --build -d
```

**Port already in use:**
```bash
# Change port in docker-compose.yml
ports:
  - "8001:8000"  # Use 8001 instead of 8000
```

**Download not working:**
```bash
# Check job status first
curl http://localhost:8000/api/v1/jobs/{job_id}

# Status must be "COMPLETED"
```

---

## 🗄️ Database Inspection

### View Database Tables

```powershell
# Connect to PostgreSQL
docker-compose exec db psql -U postgres -d docx_converter
```

Inside psql, run these commands:

```sql
-- List all tables
\dt

-- View table structure
\d jobs
\d files

-- View all jobs
SELECT * FROM jobs ORDER BY created_at DESC;

-- View all files
SELECT * FROM files;

-- Count records
SELECT COUNT(*) FROM jobs;
SELECT COUNT(*) FROM files;

-- Jobs by status
SELECT status, COUNT(*) FROM jobs GROUP BY status;

-- Files by status
SELECT status, COUNT(*) FROM files GROUP BY status;

-- View specific job files (replace job_id)
SELECT filename, status, error_message 
FROM files 
WHERE job_id = 'your-job-id-here';

-- Exit psql
\q
```

### Quick Database Queries

```powershell
# List tables (one-line)
docker-compose exec db psql -U postgres -d docx_converter -c "\dt"

# Count jobs
docker-compose exec db psql -U postgres -d docx_converter -c "SELECT COUNT(*) FROM jobs;"

# View latest job
docker-compose exec db psql -U postgres -d docx_converter -c "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 1;"
```

---

## 📁 Project Structure

```
docx-to-pdf-service/
├── app/
│   ├── main.py              # FastAPI application
│   ├── tasks.py             # Celery conversion tasks
│   ├── models.py            # Database models
│   ├── database.py          # Database connection
│   └── utils.py             # Helper functions
├── tests/
│   └── test_integration.py  # Integration tests
├── .env                     # Environment variables
├── docker-compose.yml       # Service configuration
├── Dockerfile               # Container image
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

---

## 📋 Requirements Met

✅ Bulk file upload via ZIP  
✅ Asynchronous processing with Celery  
✅ RESTful API with FastAPI  
✅ Job status tracking  
✅ Individual file status tracking  
✅ Error handling (partial failures)  
✅ Result download as ZIP  
✅ Docker containerization  
✅ Single command deployment  
✅ Scalable architecture  

---

## 🔗 Technology Stack

- Python 3.11
- FastAPI 0.104
- Celery 5.3
- PostgreSQL 15
- Redis 7
- Docker & Docker Compose

---

**Built for Backend Developer Technical Assignment**