import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [file, setFile] = useState(null);
  const [parser, setParser] = useState('pypdf');
  const [jobId, setJobId] = useState('');
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleParserChange = (e) => {
    setParser(e.target.value);
  };

  const handleUpload = async () => {
    if (!file) {
      alert('Please select a PDF file');
      return;
    }

    setLoading(true);
    setStatus(null);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('parser', parser);

    try {
      console.log('Uploading file:', file.name, 'Parser:', parser);
      const response = await axios.post('http://localhost:8000/api/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setJobId(response.data.job_id);
      alert(`File uploaded! Job ID: ${response.data.job_id}`);
    } catch (error) {
      console.error('Upload error:', error);
      setStatus({ status: 'failed', error: error.response?.data?.detail || error.message });
      setLoading(false);
    }
  };

  const pollStatus = (id) => {
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`http://localhost:8000/api/status/${id}`, {
          timeout: 310000  // 5+ minutes timeout (slightly longer than backend)
        });
        setStatus(response.data);
        console.log('Status update:', response.data);

        if (response.data.status === 'completed' || response.data.status === 'failed') {
          clearInterval(interval);
          setLoading(false);
        }
      } catch (error) {
        console.error('Status check failed:', error);
        
        // Don't fail immediately on timeout - keep polling
        if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
          console.log('Request timed out, continuing to poll...');
          return; // Continue polling
        }
        
        setStatus({ status: 'failed', error: error.response?.data?.detail || error.message });
        setLoading(false);
        clearInterval(interval);
      }
    }, 3000); // Poll every 3 seconds
    
    return () => clearInterval(interval);
  };

  const checkStatus = async () => {
    if (!jobId) {
      alert('Please enter a job ID');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.get(`http://localhost:8000/api/status/${jobId}`);
      setStatus(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Status check failed:', error);
      setStatus({ status: 'failed', error: error.response?.data?.detail || error.message });
      setLoading(false);
    }
  };

  useEffect(() => {
    let cleanup;
    if (jobId && !status?.status) {
      cleanup = pollStatus(jobId);
    }
    return cleanup;
  }, [jobId]);

  return (
    <div className="App">
      <header className="App-header">
        <h1>📄 PDF Processor</h1>
        
        <div className="upload-section">
          <h2>Upload PDF</h2>
          
          <input 
            id="file-input"
            type="file" 
            accept=".pdf" 
            onChange={handleFileChange}
            disabled={loading}
          />
          
          <div className="parser-select">
            <label>
              <input
                type="radio"
                value="pypdf"
                checked={parser === 'pypdf'}
                onChange={handleParserChange}
                disabled={loading}
              />
              PyPDF
            </label>
            
            <label>
              <input
                type="radio"
                value="gemini"
                checked={parser === 'gemini'}
                onChange={handleParserChange}
                disabled={loading}
              />
              Gemini
            </label>
          </div>
          
          <button onClick={handleUpload} disabled={loading || !file}>
            {loading ? 'Processing... Please wait.' : 'Upload & Process'}
          </button>
        </div>

        <div className="status-section">
          <h2>Check Status</h2>
          
          <input
            type="text"
            placeholder="Enter Job ID"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            disabled={loading}
          />
          
          <button onClick={checkStatus} disabled={loading}>
            Check Status
          </button>
        </div>

        {status && (
          <div className="result-section">
            <h2>Results</h2>
            
            <div className="info">
              <p><strong>Filename:</strong> {status.filename}</p>
              <p><strong>Parser:</strong> {status.parser}</p>
              <p><strong>Status:</strong> {status.status}</p>
              {status.progress && <p><strong>Progress:</strong> {status.progress}</p>}
            </div>

            {status.error && (
              <div className="error" style={{ color: 'red' }}>
                <h3>❌ Error</h3>
                <p>{status.error}</p>
                <p>Suggestion: Try uploading a text-based PDF or switching parsers.</p>
              </div>
            )}

            {status.summary && (
              <div className="summary">
                <h3>📝 Summary</h3>
                <p>{status.summary}</p>
              </div>
            )}

            {status.content && (
              <div className="content">
                <h3>📄 Full Content</h3>
                <pre>{status.content}</pre>
              </div>
            )}

            {status.status === 'pending' || status.status === 'processing' ? (
              <div className="info">
                <p>Processing may take a few seconds, especially for scanned PDFs. Please wait...</p>
              </div>
            ) : null}
          </div>
        )}
      </header>
    </div>
  );
}

export default App;