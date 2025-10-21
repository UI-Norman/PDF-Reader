import redis
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pypdf import PdfReader
import google.generativeai as genai
import io
import base64
import requests
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image
import pdfplumber
import time
from .config import settings
from .models import ParserType, ProcessingStatus, ProcessingResult


class RedisService:
    """Service for Redis operations including Streams"""
    
    def __init__(self):
        # TWO Redis clients: one for binary data, one for text
        self.client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True  # For text data
        )
        
        self.binary_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=False  # For binary data (PDFs)
        )
        
        self._initialize_stream()
    
    def _initialize_stream(self):
        """Initialize Redis Stream and consumer group"""
        try:
            self.client.xgroup_create(
                name=settings.stream_name,
                groupname=settings.consumer_group,
                id='0',
                mkstream=True
            )
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
    
    def add_job_to_queue(self, job_id: str, filename: str, 
                         pdf_data: bytes, parser: ParserType) -> str:
        """Add a processing job to Redis Stream"""
        
        # Store PDF data as binary using binary_client
        pdf_key = f"pdf:{job_id}"
        self.binary_client.set(pdf_key, pdf_data, ex=3600)
        print(f" Stored PDF data for job {job_id} at {pdf_key}")
        
        # Add job to stream
        message_id = self.client.xadd(
            settings.stream_name,
            {
                'job_id': job_id,
                'filename': filename,
                'parser': parser.value,
                'pdf_key': pdf_key,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        print(f" Added job {job_id} to stream with message ID {message_id}")
        
        # Initialize job status
        result = ProcessingResult(
            job_id=job_id,
            filename=filename,
            parser=parser,
            status=ProcessingStatus.PENDING,
            created_at=datetime.utcnow().isoformat()
        )
        self.save_result(result)
        print(f" Saved initial PENDING status for job {job_id}")
        
        return message_id
    
    def get_pdf_data(self, pdf_key: str) -> Optional[bytes]:
        """Retrieve PDF binary data from Redis"""
        data = self.binary_client.get(pdf_key)
        if data is None:
            print(f" No PDF data found for key {pdf_key}")
        return data
    
    def save_result(self, result: ProcessingResult):
        """Save processing result to Redis"""
        key = f"result:{result.job_id}"
        self.client.set(
            key,
            json.dumps(result.dict(exclude_none=True)),
            ex=3600  # Expire after 1 hour
        )
        print(f" Saved result for job {result.job_id}")
    
    def get_result(self, job_id: str) -> Optional[ProcessingResult]:
        """Retrieve processing result from Redis"""
        key = f"result:{job_id}"
        data = self.client.get(key)
        if data:
            return ProcessingResult(**json.loads(data))
        print(f" No result found for job {job_id}")
        return None
    
    def acknowledge_message(self, message_id: str):
        """Acknowledge a processed message in the stream"""
        self.client.xack(settings.stream_name, settings.consumer_group, message_id)
        print(f"  Acknowledged message {message_id}")
    
    def read_from_stream(self, count: int = 1, block: Optional[int] = None) -> list:
        """Read messages from the Redis Stream"""
        try:
            messages = self.client.xreadgroup(
                groupname=settings.consumer_group,
                consumername=settings.consumer_name,
                streams={settings.stream_name: '>'},
                count=count,
                block=block
            )
            return messages
        except Exception as e:
            print(f"   ❌ Error reading from stream: {str(e)}")
            return []


class PDFProcessingService:
    """Service for PDF processing operations"""
    
    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    
    def is_image_based_pdf(self, pdf_data: bytes) -> bool:
        """Lightweight check if the PDF is image-based (scanned) - used only for PyPDF fallback logic"""
        try:
            pdf_file = io.BytesIO(pdf_data)
            reader = PdfReader(pdf_file)
            for page_num, page in enumerate(reader.pages[:1], 1):  # Check only first page
                text = page.extract_text()
                if not text or len(text.strip()) < 10:
                    print(f"   ℹ️ Detected image-based PDF on page {page_num}")
                    return True
            print(f"   ℹ️ Detected non-scanned PDF with selectable text")
            return False
        except Exception as e:
            print(f"  Error checking PDF type: {str(e)}")
            return False
    
    def extract_with_pypdf(self, pdf_data: bytes) -> str:
        """Extract text from PDF using PyPDF, with OCR fallback for scanned documents"""
        try:
            pdf_file = io.BytesIO(pdf_data)
            reader = PdfReader(pdf_file)
            
            if len(reader.pages) == 0:
                raise Exception("PDF has no pages")
            
            text_content = []
            is_scanned = self.is_image_based_pdf(pdf_data)
            
            for page_num, page in enumerate(reader.pages, 1):
                try:
                    if not is_scanned:
                        page_text = page.extract_text()
                        if page_text and page_text.strip():
                            text_content.append(f"## Page {page_num}\n\n{page_text}\n")
                            print(f" Extracted text from page {page_num}")
                            continue
                    print(f"   ℹ️ No text or scanned PDF on page {page_num}, attempting OCR...")
                    images = convert_from_bytes(pdf_data, first_page=page_num, last_page=page_num)
                    if images:
                        ocr_text = pytesseract.image_to_string(images[0], lang='eng')
                        if ocr_text and ocr_text.strip():
                            text_content.append(f"## Page {page_num} (OCR)\n\n{ocr_text}\n")
                            print(f" OCR extracted text from page {page_num}")
                        else:
                            print(f" OCR found no text on page {page_num}")
                except Exception as e:
                    print(f" Error processing page {page_num}: {str(e)}")
            
            if not text_content:
                raise Exception("No text could be extracted from the PDF")
            
            return "\n".join(text_content)
        
        except Exception as e:
            print(f"  PyPDF extraction error: {str(e)}")
            raise Exception(f"PyPDF extraction failed: {str(e)}")
    
    def process_with_gemini(self, pdf_data: bytes, filename: str = "document.pdf", is_summary_only: bool = True, retries: int = 3) -> str:
        """Process PDF using Google Gemini - handles ALL PDF types automatically (scanned, non-scanned, semi-scanned, with errors)"""
        for attempt in range(1, retries + 1):
            try:
                print(f" Uploading PDF to Gemini (Attempt {attempt}): filename={filename}, size={len(pdf_data)} bytes")
                upload_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={settings.gemini_api_key}"
                files = {
                    'file': (filename, pdf_data, 'application/pdf')
                }
                
                # INCREASED TIMEOUT FOR LARGE FILES
                upload_timeout = 120  # 2 minutes for upload
                upload_response = requests.post(upload_url, files=files, timeout=upload_timeout)
                upload_response.raise_for_status()
                uploaded_file = upload_response.json()['file']
                file_uri = uploaded_file['uri']
                print(f" File uploaded: {file_uri}")

                # WAIT FOR FILE TO BE READY (important for large files)
                print(f" Waiting for file to be processed by Gemini...")
                max_wait = 60  # Wait up to 60 seconds for file to be ready
                wait_interval = 2
                elapsed = 0
                
                while elapsed < max_wait:
                    # Check file status
                    status_url = f"https://generativelanguage.googleapis.com/v1beta/{uploaded_file['name']}?key={settings.gemini_api_key}"
                    status_response = requests.get(status_url, timeout=30)
                    status_response.raise_for_status()
                    file_status = status_response.json()
                    
                    state = file_status.get('state', 'PROCESSING')
                    print(f" File state: {state}")
                    
                    if state == 'ACTIVE':
                        print(f" File is ready for processing")
                        break
                    elif state == 'FAILED':
                        raise Exception(f"File upload failed on Gemini's side: {file_status.get('error', 'Unknown error')}")
                    
                    time.sleep(wait_interval)
                    elapsed += wait_interval
                
                if elapsed >= max_wait:
                    print(f" File still not ready after {max_wait}s, proceeding anyway...")

                file_part = {
                    "file_data": {
                        "file_uri": file_uri,
                        "mime_type": "application/pdf"
                    }
                }

                if is_summary_only:
                    print(f" Generating summary with Gemini...")
                    prompt = """
    Provide a comprehensive summary of this PDF document.

    Extract and analyze ALL content from the document, regardless of whether it's scanned, digital, semi-scanned, or has formatting errors.

    Your summary should:
    - Capture the main topics and key points
    - Be 3-5 paragraphs long
    - Be clear and easy to understand
    - Highlight important information, tables, or data if present
    - Include relevant details from the entire document

    Return only the summary content, no explanations or meta-commentary.
    """
                    # INCREASED TIMEOUT FOR GENERATION
                    response = self.gemini_model.generate_content(
                        [file_part, prompt],
                        request_options={'timeout': 180}  # 3 minutes for generation
                    )
                    
                    if not response.text or len(response.text.strip()) < 10:
                        print(f" Gemini returned empty or very short content")
                        return "No text could be extracted from the PDF."
                    
                    print(f" Summary generated: {len(response.text)} characters")
                    return response.text
                else:
                    print(f" Extracting full content to markdown with Gemini...")
                    prompt = """
    Extract ALL content from this PDF document and convert it to well-formatted Markdown.

    Extract everything regardless of PDF type (scanned, digital, semi-scanned, mixed content, or documents with errors).

    Requirements:
    - Preserve the complete document structure with appropriate headers (# ## ###)
    - Convert tables to markdown tables with proper alignment
    - Keep ALL text content including:
    * Paragraphs and body text
    * Bullet points and numbered lists
    * Bold, italic, and other text formatting
    * Code blocks or technical content
    * Captions, footnotes, and references
    * Headers, footers if meaningful
    - Use proper markdown syntax throughout
    - Organize content logically by sections
    - Handle complex layouts, multi-column text, and embedded fonts accurately
    - For scanned or image-based pages, apply OCR and extract all readable text
    - Maintain readability and structure even if source has errors

    Return only the complete markdown content. Do not add explanations, warnings, or meta-commentary.
    """
                    # INCREASED TIMEOUT FOR FULL CONTENT EXTRACTION
                    response = self.gemini_model.generate_content(
                        [file_part, prompt],
                        request_options={'timeout': 300}  # 5 minutes for full extraction
                    )
                    
                    if not response.text or len(response.text.strip()) < 10:
                        print(f"  Gemini returned empty or very short content")
                        return "No text could be extracted from the PDF."
                    
                    print(f"  Content extracted: {len(response.text)} characters")
                    return response.text

            except requests.exceptions.Timeout as e:
                print(f"  Timeout error (Attempt {attempt}): {str(e)}")
                if attempt == retries:
                    print(f"   ❌ Max retries reached for job")
                    return f"Processing timed out after {retries} attempts. The PDF may be too large or complex."
                print(f"  Retrying after 3 seconds...")
                time.sleep(3)
        
    def generate_summary(self, content: str) -> str:
        """Generate summary using Google Gemini (used for PyPDF path)"""
        try:
            if len(content.strip()) < 100:
                return "Document is too short to summarize effectively."
            
            content_preview = content[:10000]
            if len(content) > 10000:
                content_preview += "\n\n[Content truncated for summarization...]"
            
            print(f" Generating summary from extracted content...")
            prompt = f"""
Please provide a comprehensive summary of the following document content.

The summary should:
- Capture the main topics and key points
- Be 3-5 paragraphs long
- Be clear and easy to understand
- Highlight important information, tables, or data if present

Document content:
{content_preview}
"""
            
            response = self.gemini_model.generate_content(prompt)
            
            if not response.text:
                raise Exception("Gemini returned empty summary")
            
            print(f" Summary generated: {len(response.text)} characters")
            return response.text
        
        except Exception as e:
            print(f" Summary generation error: {str(e)}")
            raise Exception(f"Summary generation failed: {str(e)}")
    
    def process_document(self, pdf_data: bytes, parser: ParserType, filename: str = "document.pdf") -> tuple[str, str]:
        """
        Process PDF document: extract content and generate summary
        Returns: (content, summary)
        """
        content = None
        summary = None
        
        if parser == ParserType.PYPDF:
            content = self.extract_with_pypdf(pdf_data)
            summary = self.generate_summary(content)
        elif parser == ParserType.GEMINI:
            content = self.process_with_gemini(pdf_data, filename, is_summary_only=False)
            summary = self.process_with_gemini(pdf_data, filename, is_summary_only=True)
        else:
            raise ValueError(f"Unsupported parser: {parser}")
        
        return content, summary


# Global service instances
redis_service = RedisService()
pdf_service = PDFProcessingService()