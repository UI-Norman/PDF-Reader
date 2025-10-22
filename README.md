# PDF Processing API / PDF Reader

A full-stack asynchronous PDF processing application with Redis Streams for queue management, supporting multiple parsing engines (PyPDF and Google Gemini AI).

## Features

### Backend
- **Asynchronous Processing**: Non-blocking PDF processing using Redis Streams
- **Multiple Parser Support**:
  - **PyPDF**: Fast extraction with OCR fallback for scanned documents
  - **Google Gemini**: AI-powered extraction handling all PDF
- **Smart OCR Integration**: Automatic fallback to Tesseract OCR for image-based PDFs
- **Job Queue Management**: Redis Streams with consumer groups for scalable processing
- **Real-time Status Tracking**: Poll job status with progress indicators
- **Error Handling**: Comprehensive error handling with retry mechanisms
- **Large File Support**: Handles PDFs up to 10MB with extended timeouts

### Frontend
- **Modern React UI**: Clean, responsive interface with gradient design
- **File Upload**: Drag-and-drop PDF upload with validation
- **Parser Selection**: Choose between PyPDF and Gemini parsers
- **Real-time Updates**: Automatic status polling during processing
- **Results Display**: View extracted content and AI-generated summaries
- **Mobile Responsive**: Works seamlessly on all device sizes

## Architecture

```
┌──────────┐      ┌──────────┐      ┌──────────┐
│  React   │─────►│ FastAPI  │─────►│  Redis   │
│ Frontend │      │   API    │      │  Stream  │
└──────────┘      └──────────┘      └──────────┘
                        │                 │
                        │                 ▼
                        │           ┌──────────┐
                        └──────────►│  Worker  │
                                    └──────────┘
                                         │
                                         ▼
                                   ┌─────────────┐
                                   │   Gemini    │
                                   │     API     │
                                   └─────────────┘
```

## Project Structure

```
├── pdf-processor/
│   ├── backend/
│   │   ├── __pycache__/
│   │   ├── __init__.py
│   │   ├── config.py         
│   │   ├── main.py            
│   │   ├── models.py          
│   │   ├── services.py        
│   │   ├── test_gemini.py     
│   │   └── worker.py         
│   └── frontend/
│       ├── node_modules/
│       ├── public/
│       │   ├── favicon.ico
│       │   ├── index.html
│       │   ├── logo192.png
│       │   ├── logo512.png
│       │   ├── manifest.json
│       │   └── robots.txt
│       ├── src/
│       │   ├── App.css        
│       │   ├── App.js         
│       │   ├── App.test.js
│       │   ├── index.css      
│       │   ├── index.js       
│       │   ├── logo.svg
│       │   ├── reportWebVitals.js
│       │   └── setupTests.js
│       ├── package-lock.json  
│       └── package.json       
├── .env                       
├── docker-compose.yml         
├── README.md                  
└── requirements.txt           
```

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 16+
- Redis 6+
- Tesseract OCR
- Google Gemini API key

### Installation

#### 1. Clone the Repository

```bash
git clone <repository-url>
cd pdf-processor
```

#### 2. Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Tesseract OCR
# Ubuntu/Debian:
sudo apt-get install tesseract-ocr

# macOS:
brew install tesseract

# Windows:
# Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
```

#### 3. Configure Environment Variables

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_gemini_api_key_here
REDIS_HOST=localhost
REDIS_PORT=6379
```

#### 4. Start Redis

Using Docker:
```bash
docker-compose up -d
```

Or install locally:
```bash
# Ubuntu/Debian:
sudo apt-get install redis-server
sudo systemctl start redis

# macOS:
brew install redis
brew services start redis
```

#### 5. Frontend Setup

```bash
cd frontend
npm install
```

### Running the Application

#### Terminal 1: Start the Backend API

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

#### Terminal 2: Start the Worker

```bash
cd backend
python -m worker
```

#### Terminal 3: Start the Frontend

```bash
cd frontend
npm start
```

The frontend will be available at `http://localhost:3000`

## API Documentation

### Endpoints

#### 1. Health Check
```
GET /
```
Returns API status and available endpoints.

#### 2. Upload PDF
```
POST /api/upload
```
**Form Data:**
- `file`: PDF file 
- `parser`: "pypdf" or "gemini"

#### 3. Check Status
```
GET /api/status/{job_id}
```

#### 4. Health Check (Detailed)
```
GET /api/health
```
Returns Redis connection status.

### Interactive API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Configuration

### Processing Timeouts

- **Upload timeout**: 120 seconds
- **File processing wait**: 60 seconds
- **Generation timeout**: 180-300 seconds (depending on operation)
- **API status polling**: 300 seconds (5 minutes)
- **Frontend polling interval**: 3 seconds

### File Limits

- **Maximum file size**: 10MB
- **Supported format**: PDF only
- **Redis TTL**: 1 hour (3600 seconds)

## Testing

### Test Backend API

```bash
# Test Gemini integration
cd backend
python test_gemini.py

# Run pytest (if tests available)
pytest
```

### Test Frontend

```bash
cd frontend
npm test
```

### Manual Testing

1. Upload a text-based PDF using PyPDF parser
2. Upload a scanned PDF using PyPDF (tests OCR fallback)
3. Upload any PDF using Gemini parser (handles all types)
4. Test error handling with invalid files

## Parser Comparison

| Feature | PyPDF | Gemini AI |
|---------|-------|-----------|
| **Speed** | Fast (< 5s) | Slower (30-60s) |
| **Text PDFs** | Excellent | Excellent |
| **Scanned PDFs** | Good (OCR fallback) | Excellent |
| **Complex Layouts** | Limited | Excellent |
| **Tables** | Basic | Advanced |
| **Cost** | Free | API costs apply |
| **Accuracy** | High | Very High |
| **Summary Quality** | Good | Excellent (AI-powered) |

## Troubleshooting

### Common Issues

**1. Redis Connection Error**
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# Restart Redis
docker-compose restart redis
```

**2. Tesseract Not Found**
```bash
# Verify installation
tesseract --version
```

**3. Gemini API Errors**
- Verify your API key in `.env`


## Performance Tips

1. **For Large PDFs**: Use Gemini parser with increased timeouts
2. **For Batch Processing**: Run multiple worker instances
3. **For Production**: Use Redis Cluster and load balancer
4. **For Speed**: Use PyPDF for text-based documents

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Redis](https://redis.io/) - In-memory data structure store
- [Google Gemini](https://ai.google.dev/) - AI-powered document processing
- [PyPDF](https://pypdf2.readthedocs.io/) - PDF manipulation library
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) - Open source OCR engine
- [React](https://reactjs.org/) - Frontend library
