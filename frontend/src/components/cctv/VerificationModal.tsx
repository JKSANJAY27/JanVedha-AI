import React, { useState } from 'react';
import { format } from 'date-fns';
import { useAuth } from '@/context/AuthContext';

interface VerificationModalProps {
  isOpen: boolean;
  onClose: () => void;
  alert: any;
  onVerify: (action: string, data: any) => Promise<boolean>;
}

export default function VerificationModal({ isOpen, onClose, alert, onVerify }: VerificationModalProps) {
  const { user } = useAuth();
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<{msg: string, color: string} | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  // Form states
  const [title, setTitle] = useState(alert?.ai_analysis?.suggested_ticket_title || '');
  const [description, setDescription] = useState(alert?.ai_analysis?.detailed_description || '');
  const [category, setCategory] = useState(alert?.ai_analysis?.issue_category || 'other');
  const [priority, setPriority] = useState(alert?.ai_analysis?.suggested_priority || 'medium');
  const [note, setNote] = useState('');

  if (!isOpen || !alert) return null;

  const { status, ai_analysis, camera_id, camera_location_description, created_at, verification } = alert;
  const isActioned = status === 'ticket_raised' || status === 'dismissed' || status === 'flagged_for_discussion' && verification?.verification_action;

  const handleAction = async (action: string) => {
    setLoadingAction(action);
    setErrorMsg(null);
    try {
      const data = {
        action,
        verifier_id: user?.id?.toString() || 'demo_user_1',
        verifier_name: user?.name || 'Demo User',
        verifier_role: user?.role || 'councillor',
        verifier_note: note,
        ...(action === 'raise_ticket' && {
          ticket_title: title,
          ticket_description: description,
          ticket_category: category,
          ticket_priority: priority,
          ward_id: alert.ward_id
        })
      };

      const success = await onVerify(action, data);
      
      if (success) {
        if (action === 'raise_ticket') setSuccessMsg({msg: 'Ticket created successfully. Assigned for action.', color: 'bg-green-100 text-green-800 border-green-200'});
        else if (action === 'dismiss') setSuccessMsg({msg: 'Alert dismissed.', color: 'bg-gray-100 text-gray-800 border-gray-200'});
        else setSuccessMsg({msg: 'Flagged for discussion.', color: 'bg-purple-100 text-purple-800 border-purple-200'});
        setTimeout(() => onClose(), 1500);
      } else {
        setErrorMsg('Failed to process action. Please try again.');
      }
    } catch (e: any) {
      setErrorMsg(e.message || 'An error occurred.');
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-[720px] flex flex-col max-h-[90vh] overflow-hidden">
        
        {/* Header */}
        <div className="px-6 py-4 border-b flex justify-between items-center bg-gray-50">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Review CCTV alert</h2>
            <p className="text-sm text-gray-500">{camera_id} — {camera_location_description}</p>
          </div>
          <button onClick={onClose} disabled={!!loadingAction} className="text-gray-400 hover:text-gray-600 p-2">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-col md:flex-row flex-1 overflow-y-auto">
          
          {/* Left Column: Image & AI */}
          <div className="w-full md:w-[55%] border-r border-gray-100 flex flex-col">
            <div className="w-full h-[240px] bg-[#1a1a1a] flex-shrink-0 relative">
              <img 
                src={alert.analysis_frame_url || `/api/cctv/alerts/${alert.alert_id}/frame`} 
                alt="Analyzed frame" 
                className="w-full h-full object-contain"
              />
            </div>
            
            <div className="p-5 flex-1 overflow-y-auto">
              <p className="text-sm text-gray-500 italic mb-4">"{ai_analysis?.what_is_visible}"</p>
              
              <div className="bg-blue-50/50 rounded-lg p-4 border border-blue-100/50 mb-4">
                <div className="flex items-center space-x-2 mb-3">
                  {ai_analysis?.issue_category && (
                    <span className="bg-white border border-gray-200 text-gray-700 text-xs px-2 py-1 rounded shadow-sm">
                      {ai_analysis.issue_category.toUpperCase()}
                    </span>
                  )}
                  {ai_analysis?.severity && (
                    <span className={`text-white text-xs px-2 py-1 rounded shadow-sm ${
                      ai_analysis.severity === 'high' ? 'bg-red-500' : ai_analysis.severity === 'medium' ? 'bg-amber-500' : 'bg-blue-500'
                    }`}>
                      {ai_analysis.severity.toUpperCase()} SEVERITY
                    </span>
                  )}
                </div>
                
                <div className="mb-3">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs text-gray-500">AI Confidence</span>
                    <span className="text-xs font-semibold">{(ai_analysis?.confidence_score * 100).toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-1.5">
                    <div className="bg-blue-600 h-1.5 rounded-full" style={{ width: `${ai_analysis?.confidence_score * 100}%` }}></div>
                  </div>
                </div>

                <p className="text-sm font-medium text-gray-900 mb-2">{ai_analysis?.issue_summary || 'No issue detected'}</p>
                
                <button onClick={() => setShowDetails(!showDetails)} className="text-xs text-blue-600 hover:underline">
                  {showDetails ? 'Hide details' : 'Show details'}
                </button>
                
                {showDetails && (
                  <div className="mt-2 text-sm text-gray-600 space-y-2">
                    <p>{ai_analysis?.detailed_description}</p>
                    {ai_analysis?.analysis_notes && (
                      <div className="bg-amber-50 border border-amber-200 p-2 rounded text-amber-800 text-xs mt-2">
                        <strong>Note:</strong> {ai_analysis.analysis_notes}
                      </div>
                    )}
                  </div>
                )}
              </div>
              
              <div className="text-xs text-gray-500 bg-gray-50 p-3 rounded border">
                <strong>Camera:</strong> {camera_id}<br />
                <strong>Location:</strong> {camera_location_description}<br />
                <strong>Detected:</strong> {format(new Date(created_at), 'dd MMM yyyy, HH:mm')}
              </div>
            </div>
          </div>

          {/* Right Column: Decision */}
          <div className="w-full md:w-[45%] bg-white p-6 flex flex-col justify-between overflow-y-auto">
            
            {successMsg ? (
               <div className={`p-4 rounded border flex items-center justify-center my-auto ${successMsg.color}`}>
                 <p className="font-medium text-center">{successMsg.msg}</p>
               </div>
            ) : isActioned ? (
              <div className="h-full flex flex-col justify-center">
                <h3 className="text-base font-semibold text-gray-900 mb-4">Verification Summary</h3>
                <div className="bg-gray-50 p-4 rounded-lg border space-y-3 text-sm">
                  <div className="flex justify-between border-b pb-2">
                    <span className="text-gray-500">Action taken:</span>
                    <span className="font-medium">{verification.verification_action}</span>
                  </div>
                  <div className="flex justify-between border-b pb-2">
                    <span className="text-gray-500">By:</span>
                    <span className="font-medium">{verification.verified_by_name} ({verification.verified_by_role})</span>
                  </div>
                  <div className="flex justify-between border-b pb-2">
                    <span className="text-gray-500">At:</span>
                    <span className="font-medium">{format(new Date(verification.verified_at), 'dd MMM yyyy, HH:mm')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Note:</span>
                    <span className="font-medium text-right max-w-[60%]">{verification.verifier_note || '—'}</span>
                  </div>
                </div>
                {alert.raised_ticket_id && (
                  <a href={`/councillor/track?ticketId=${alert.raised_ticket_id}`} className="mt-6 w-full text-center text-blue-600 hover:text-blue-800 font-medium bg-blue-50 py-2 rounded">
                    View generated ticket &rarr;
                  </a>
                )}
              </div>
            ) : (
              <>
                <div>
                  <h3 className="text-base font-semibold text-gray-900 mb-1">Your decision</h3>
                  <p className="text-xs text-gray-500 mb-4">If you decide to raise a ticket, review and confirm these details:</p>
                  
                  {errorMsg && (
                    <div className="mb-4 bg-red-50 text-red-600 p-2 text-sm rounded border border-red-200">
                      {errorMsg}
                    </div>
                  )}

                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Title</label>
                      <input type="text" value={title} onChange={e => setTitle(e.target.value)} className="w-full px-3 py-2 border rounded text-sm focus:ring-1 focus:ring-blue-500" />
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
                      <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} className="w-full px-3 py-2 border rounded text-sm focus:ring-1 focus:ring-blue-500" />
                    </div>

                    <div className="flex gap-4">
                      <div className="flex-1">
                        <label className="block text-xs font-medium text-gray-700 mb-1">Category</label>
                        <select value={category} onChange={e => setCategory(e.target.value)} className="w-full px-3 py-2 border rounded text-sm bg-white">
                          <option value="roads">Roads</option>
                          <option value="water">Water</option>
                          <option value="drainage">Drainage</option>
                          <option value="waste">Waste</option>
                          <option value="other">Other</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Priority</label>
                      <div className="flex rounded-md shadow-sm">
                        {['low', 'medium', 'high'].map(p => (
                          <button
                            key={p}
                            onClick={() => setPriority(p)}
                            className={`flex-1 text-xs py-1.5 border relative ${
                              priority === p 
                                ? (p==='high'?'bg-red-50 border-red-500 text-red-700 z-10':p==='medium'?'bg-amber-50 border-amber-500 text-amber-700 z-10':'bg-blue-50 border-blue-500 text-blue-700 z-10') 
                                : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
                            } ${p==='low'?'rounded-l-md':''} ${p==='high'?'rounded-r-md':''}`}
                          >
                            {p.charAt(0).toUpperCase() + p.slice(1)}
                            {alert.ai_analysis?.suggested_priority === p && (
                              <span className="absolute -top-2 -right-1 bg-blue-100 text-blue-800 text-[9px] px-1 rounded-sm border border-blue-200">AI</span>
                            )}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                       <label className="block text-xs font-medium text-gray-700 mb-1">Your note (optional)</label>
                       <textarea value={note} onChange={e => setNote(e.target.value)} placeholder="Add context..." rows={2} className="w-full px-3 py-2 border rounded text-sm" />
                    </div>
                  </div>
                </div>

                <div className="mt-6 space-y-2">
                  <button 
                    disabled={!!loadingAction}
                    onClick={() => handleAction('raise_ticket')}
                    className="w-full bg-green-600 hover:bg-green-700 text-white py-2 rounded font-medium shadow-sm transition-colors text-sm flex justify-center items-center"
                  >
                    {loadingAction === 'raise_ticket' ? 'Creating ticket...' : 'Raise ticket with these details'}
                  </button>
                  <button 
                    disabled={!!loadingAction}
                    onClick={() => handleAction('flag_for_discussion')}
                    className="w-full bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100 py-2 rounded font-medium transition-colors text-sm"
                  >
                    {loadingAction === 'flag_for_discussion' ? 'Flagging...' : 'Flag for team discussion'}
                  </button>
                  <button 
                    disabled={!!loadingAction}
                    onClick={() => {
                      if (window.confirm("Are you sure? This alert will be marked as dismissed.")) {
                        handleAction('dismiss');
                      }
                    }}
                    className="w-full bg-transparent hover:bg-gray-50 text-gray-500 py-2 rounded font-medium transition-colors text-sm"
                  >
                    {loadingAction === 'dismiss' ? 'Dismissing...' : 'Dismiss — not an issue'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
