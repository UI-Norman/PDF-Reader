import asyncio
import signal
import sys
from datetime import datetime, timezone
from typing import Optional
from .services import redis_service, pdf_service
from .models import ProcessingStatus, ProcessingResult, ParserType


class Worker:
    """Background worker that processes jobs from Redis Stream"""
    
    def __init__(self):
        self.running = False
        self.redis = redis_service
        self.pdf_processor = pdf_service
    
    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        print("\n🛑 Shutting down worker gracefully...")
        self.running = False
    
    async def process_message(self, stream_name: str, message_id: str, data: dict):
        """Process a single message from the stream"""
        job_id = data.get('job_id')
        filename = data.get('filename')
        parser = ParserType(data.get('parser'))
        pdf_key = data.get('pdf_key')
        
        print(f"\n📄 Processing job {job_id}")
        print(f"   Filename: {filename}")
        print(f"   Parser: {parser.value}")
        
        try:
            # Update status to processing
            result = self.redis.get_result(job_id)
            if result:
                result.status = ProcessingStatus.PROCESSING
                self.redis.save_result(result)
            
            # Get PDF data
            pdf_data = self.redis.get_pdf_data(pdf_key)
            if not pdf_data:
                raise Exception("PDF data not found in Redis")
            
            # Process document
            print(f" ⚙️ Extracting content...")
            content, summary = self.pdf_processor.process_document(
                pdf_data=pdf_data,
                parser=parser,
                filename=filename
            )
            
            # Log content and summary lengths, handling None for content
            if content is not None:
                print(f" Content extracted: {len(content)} chars")
            else:
                print(f"   ℹ️ No full content extracted (summary-only mode)")
            print(f" Summary generated: {len(summary)} chars")
            
            # Save result
            result = ProcessingResult(
                job_id=job_id,
                filename=filename,
                parser=parser,
                status=ProcessingStatus.COMPLETED,
                content=content,
                summary=summary,
                created_at=result.created_at if result else datetime.now(timezone.utc).isoformat(),
                completed_at=datetime.now(timezone.utc).isoformat()
            )
            self.redis.save_result(result)
            
            # Acknowledge message
            self.redis.acknowledge_message(message_id)
            
            print(f"   ✨ Job {job_id} completed successfully")
        
        except Exception as e:
            print(f"   ❌ Error processing job {job_id}: {str(e)}")
            
            # Update status to failed
            result = self.redis.get_result(job_id)
            if result:
                result.status = ProcessingStatus.FAILED
                result.error = str(e)
                result.completed_at = datetime.now(timezone.utc).isoformat()
                self.redis.save_result(result)
            
            # Acknowledge message anyway to prevent reprocessing
            self.redis.acknowledge_message(message_id)
    
    async def run(self):
        """Main worker loop"""
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        print("🚀 Worker started and listening for jobs...")
        print(f"   Stream: {self.redis.client.connection_pool.connection_kwargs['host']}:{self.redis.client.connection_pool.connection_kwargs['port']}")
        print("   Press Ctrl+C to stop\n")
        
        while self.running:
            try:
                # Read messages from stream (blocking call with timeout)
                messages = self.redis.read_from_stream(count=1, block=5000)
                
                if messages:
                    for stream_name, message_list in messages:
                        for message_id, data in message_list:
                            await self.process_message(stream_name, message_id, data)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Worker error: {str(e)}")
                await asyncio.sleep(1)
        
        print("👋 Worker stopped")


async def main():
    """Entry point for worker"""
    worker = Worker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())