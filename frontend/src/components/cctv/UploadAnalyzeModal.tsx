import React, { useState, useRef } from 'react';

interface UploadAnalyzeModalProps {
  isOpen: boolean;
  onClose: () => void;
  cameras: any[];
  wardId: string;
  userId: string;
  onUploadSuccess: (alert: any) => void;
}

export default function UploadAnalyzeModal({ isOpen, onClose, cameras, wardId, userId, onUploadSuccess }: UploadAnalyzeModalProps) {
  const [selectedCameraId, setSelectedCameraId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  
  const [status, setStatus] = useState<'idle' | 'uploading' | 'extracting' | 'analyzing' | 'processing' | 'complete' | 'error'>('idle');
  const [result, setResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState('');
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const selectedCam = cameras.find(c => c.camera_id === selectedCameraId);

  const handleSubmit = async () => {
    if (!selectedCameraId || !file) return;
    
    setStatus('uploading');
    setErrorMsg('');
    
    try {
      const formData = new FormData();
      formData.append('media_file', file);
      formData.append('camera_id', selectedCameraId);
      formData.append('ward_id', wardId);
      formData.append('uploaded_by', userId);

      // Simulate steps for UI feel
      setTimeout(() => setStatus('extracting'), 1000);
      setTimeout(() => setStatus('analyzing'), 2000);
      
      const res = await fetch('http://localhost:8000/api/cctv/upload-and-analyze', {
        method: 'POST',
        body: formData,
      });
      
      setStatus('processing');
      
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Upload failed');
      }
      
      const data = await res.json();
      setResult(data);
      setStatus('complete');
      onUploadSuccess(data);
      
    } catch (err: any) {
      setErrorMsg(err.message || 'An error occurred during analysis.');
      setStatus('error');
    }
  };

  const renderStatus = () => {
    const steps = [
      { id: 'uploading', label: 'Uploading footage...' },
      { id: 'extracting', label: 'Extracting frame for analysis...' },
      { id: 'analyzing', label: 'Running AI civic issue detection...' },
      { id: 'processing', label: 'Processing results...' },
    ];
    
    const currIdx = steps.findIndex(s => s.id === status);
    
    return (
      <div className="p-8 text-center bg-gray-50 flex-1 flex flex-col items-center justify-center">
        <div className="inline-block animate-spin w-8 h-8 rounded-full border-4 border-gray-200 border-t-blue-600 mb-6"></div>
        <div className="space-y-4 w-full max-w-xs text-left">
          {steps.map((step, idx) => (
             <div key={step.id} className={`flex items-center text-sm ${currIdx >= idx ? 'text-gray-900 font-medium' : 'text-gray-400'}`}>
               <div className={`w-4 h-4 rounded-full mr-3 flex items-center justify-center ${currIdx > idx ? 'bg-green-500 text-white' : (currIdx === idx ? 'bg-blue-600 text-white' : 'bg-gray-200')}`}>
                 {currIdx > idx && <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>}
                 {currIdx === idx && <div className="w-1.5 h-1.5 bg-white rounded-full animate-ping"></div>}
               </div>
               {step.label}
             </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full md:w-[480px] bg-white shadow-2xl z-50 flex flex-col transform transition-transform border-l border-gray-200">
      
      {/* Header */}
      <div className="px-5 py-4 border-b flex justify-between items-center bg-white sticky top-0 z-10">
        <h2 className="text-lg font-semibold text-gray-900">Upload CCTV footage</h2>
        <button onClick={onClose} disabled={status !== 'idle' && status !== 'complete' && status !== 'error'} className="p-2 -mr-2 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100 transition-colors">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        </button>
      </div>

      <div className="bg-blue-50/50 p-4 border-b border-blue-100 flex items-start space-x-3">
        <svg className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        <p className="text-sm text-blue-800">
          <strong>Privacy notice:</strong> This system analyzes footage for civic infrastructure issues only. No facial recognition or personal identification is performed.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {status === 'idle' || status === 'error' ? (
          <div className="p-5 space-y-6">
            
            {status === 'error' && (
              <div className="bg-red-50 text-red-700 p-3 rounded-md border border-red-200 text-sm">
                <strong>Upload Failed:</strong> {errorMsg}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Select camera <span className="text-red-500">*</span></label>
              <select 
                value={selectedCameraId} 
                onChange={e => setSelectedCameraId(e.target.value)}
                className="w-full p-2.5 border border-gray-300 rounded-md shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white sm:text-sm"
              >
                <option value="">-- Choose camera source --</option>
                {cameras.map(c => (
                  <option key={c.camera_id} value={c.camera_id} disabled={c.status !== 'active'}>
                    {c.camera_id} — {c.location_description} {c.status !== 'active' ? `(${c.status})` : ''}
                  </option>
                ))}
              </select>
              
              {selectedCam && (
                <div className="mt-3 bg-gray-50 rounded-md p-3 border border-gray-200 flex items-center">
                  <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center mr-3 hidden sm:flex">
                    <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path></svg>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{selectedCam.area_label}</p>
                    <p className="text-xs text-gray-500">Lat: {selectedCam.lat.toFixed(4)}, Lng: {selectedCam.lng.toFixed(4)}</p>
                  </div>
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Upload footage <span className="text-red-500">*</span></label>
              <p className="text-xs text-gray-500 mb-3">Images up to 10MB &middot; Video clips up to 50MB</p>
              
              <div 
                className={`mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-dashed rounded-lg transition-colors ${file ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:bg-gray-50'} cursor-pointer`}
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="space-y-1 text-center">
                  {file ? (
                    <div className="flex flex-col items-center">
                      <div className="w-12 h-12 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mb-2">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                      </div>
                      <p className="text-sm text-gray-900 font-medium">{file.name}</p>
                      <p className="text-xs text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                    </div>
                  ) : (
                    <>
                      <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                        <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      <div className="flex text-sm text-gray-600 justify-center group-hover:text-blue-600">
                        <span className="font-medium text-blue-600 hover:text-blue-500">Upload a file</span>
                        <p className="pl-1">or drag and drop</p>
                      </div>
                    </>
                  )}
                </div>
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  className="hidden" 
                  accept="image/jpeg, image/png, image/webp, video/mp4, video/quicktime, video/webm"
                  onChange={handleFileChange}
                />
              </div>
            </div>
            
          </div>
        ) : status === 'complete' && result ? (
          <div className="flex-1 flex flex-col bg-gray-50">
            <div className="w-full h-[240px] bg-[#1a1a1a] relative">
              <img src={`http://localhost:8000/api/cctv/alerts/${result.alert_id}/frame`} alt="Analyzed frame" className="w-full h-full object-cover" />
            </div>
            
            <div className="p-6">
              {result.status === 'pending_verification' ? (
                <div className="bg-green-50 border border-green-200 rounded-lg p-5">
                  <h3 className="text-green-800 font-bold text-lg mb-2">Civic issue detected</h3>
                  <p className="text-green-900 text-sm font-medium mb-4">{result.issue_summary}</p>
                  
                  <div className="flex items-center space-x-3 mb-6">
                    <span className={`text-white text-xs px-2.5 py-1 rounded-full shadow-sm ${
                      result.severity === 'high' ? 'bg-red-500' : result.severity === 'medium' ? 'bg-amber-500' : 'bg-blue-500'
                    }`}>
                      {result.severity?.toUpperCase()}
                    </span>
                    <span className="text-sm font-medium text-gray-700 bg-white border px-2 py-1 rounded inline-block">
                      AI Confidence: {(result.confidence_score * 100).toFixed(0)}%
                    </span>
                  </div>
                  
                  <p className="text-sm text-green-700 mb-4">An alert has been created and placed in the verification queue.</p>
                  
                  <button onClick={onClose} className="text-green-700 font-semibold text-sm hover:underline flex items-center">
                    View in alerts queue 
                    <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                  </button>
                </div>
              ) : (
                <div className="bg-white border rounded-lg p-5 shadow-sm">
                  <div className="flex items-center text-gray-500 mb-3 font-semibold">
                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    No reportable issue detected
                  </div>
                  
                  {result.confidence_score > 0 && result.confidence_score < 0.65 && result.issue_detected && (
                     <p className="text-sm text-gray-700 mb-3 bg-amber-50 text-amber-800 p-2 rounded">
                       Low confidence detection: {(result.confidence_score*100).toFixed(0)}%
                     </p>
                  )}
                  
                  <p className="text-sm text-gray-600 mb-4 bg-gray-50 p-3 rounded">
                    <strong>AI Notes:</strong> {result.what_is_visible || result.analysis_notes || 'Image contains no apparent civic issues.'}
                  </p>
                  
                  <p className="text-xs text-gray-500 mb-6">
                    This footage has been logged but no alert was created. If you believe there is an issue, you can manually raise a ticket.
                  </p>
                  
                </div>
              )}
              
              <button onClick={() => { setStatus('idle'); setFile(null); setResult(null); }} className="mt-6 w-full py-2 bg-white border border-gray-300 text-gray-700 rounded-md shadow-sm hover:bg-gray-50 font-medium text-sm transition-colors">
                Analyze another clip
              </button>
            </div>
          </div>
        ) : (
          renderStatus()
        )}
      </div>

      {status === 'idle' && (
        <div className="p-4 border-t bg-gray-50 flex justify-end">
          <button 
            disabled={!selectedCameraId || !file}
            onClick={handleSubmit}
            className={`px-4 py-2 rounded-md font-medium text-sm shadow-sm transition-colors ${
              (!selectedCameraId || !file) 
                ? 'bg-blue-300 text-white cursor-not-allowed' 
                : 'bg-blue-600 hover:bg-blue-700 text-white'
            }`}
          >
            Analyze footage
          </button>
        </div>
      )}
    </div>
  );
}
