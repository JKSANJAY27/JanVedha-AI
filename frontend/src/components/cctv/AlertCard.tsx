import React from 'react';
import { formatDistanceToNow } from 'date-fns';

interface AlertCardProps {
  alert: any;
  onReview: () => void;
  onMarkResolved?: () => void;
}

export default function AlertCard({ alert, onReview, onMarkResolved }: AlertCardProps) {
  const { status, ai_analysis, created_at, verification, camera_id, camera_location_description, area_label } = alert;
  
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high': return 'bg-red-500 text-white';
      case 'medium': return 'bg-amber-500 text-white';
      case 'low': return 'bg-blue-500 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  const getStatusBadge = () => {
    switch (status) {
      case 'pending_verification': return <span className="absolute bottom-2 left-2 bg-amber-500 text-white text-xs px-2 py-1 rounded-full font-medium">Awaiting verification</span>;
      case 'ticket_raised': return <span className="absolute bottom-2 left-2 bg-green-600 text-white text-xs px-2 py-1 rounded-full font-medium">Ticket raised</span>;
      case 'dismissed': return <span className="absolute bottom-2 left-2 bg-gray-600 text-white text-xs px-2 py-1 rounded-full font-medium">Dismissed</span>;
      case 'flagged_for_discussion': return <span className="absolute bottom-2 left-2 bg-purple-600 text-white text-xs px-2 py-1 rounded-full font-medium">Flagged</span>;
      default: return null;
    }
  };

  const isActioned = status === 'ticket_raised' || status === 'dismissed';
  const confidenceColor = ai_analysis?.confidence_score >= 0.8 ? 'bg-green-500' : (ai_analysis?.confidence_score >= 0.65 ? 'bg-amber-500' : 'bg-red-500');

  return (
    <div className={`border rounded-lg overflow-hidden bg-white shadow-sm flex flex-col ${isActioned ? 'opacity-80' : ''}`}>
      {/* Top Section - Image */}
      <div className="relative h-44 w-full bg-gray-900">
        <img 
          src={alert.analysis_frame_url || `/api/cctv/alerts/${alert.alert_id}/frame`} 
          alt="CCTV Frame" 
          className="w-full h-full object-cover" 
        />
        {isActioned && <div className="absolute inset-0 bg-black opacity-40"></div>}
        
        <span className="absolute top-2 left-2 bg-black bg-opacity-70 text-white text-xs px-2 py-1 rounded-full">
          {camera_id}
        </span>
        
        {ai_analysis?.severity && (
          <span className={`absolute top-2 right-2 text-xs px-2 py-1 rounded-full font-medium shadow-sm ${getSeverityColor(ai_analysis.severity)}`}>
            {ai_analysis.severity.charAt(0).toUpperCase() + ai_analysis.severity.slice(1)} severity
          </span>
        )}
        
        {getStatusBadge()}
      </div>

      {/* Body Section */}
      <div className="p-4 flex-grow flex flex-col">
        <div className="flex items-start mb-2">
          <svg className="w-4 h-4 text-gray-400 mt-0.5 mr-1.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
          </svg>
          <div>
            <p className="text-[13px] text-gray-600 leading-tight">{camera_location_description}</p>
            <p className="text-[11px] text-gray-400 mt-0.5">{area_label}</p>
          </div>
        </div>

        <p className="text-sm font-medium text-gray-900 mb-3 line-clamp-2 min-h-[40px]">
          {ai_analysis?.issue_summary ? ai_analysis.issue_summary : <span className="italic text-gray-400 font-normal">No reportable issue detected</span>}
        </p>

        {ai_analysis?.issue_detected && (
          <div className="mb-3">
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-gray-500">AI confidence</span>
              <span className="text-xs font-medium">{(ai_analysis.confidence_score * 100).toFixed(0)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-1.5">
              <div className={`h-1.5 rounded-full ${confidenceColor}`} style={{ width: `${ai_analysis.confidence_score * 100}%` }}></div>
            </div>
          </div>
        )}

        <div className="text-xs text-gray-400 mb-2 mt-auto">
          Detected {formatDistanceToNow(new Date(created_at), { addSuffix: true })}
        </div>

        {verification?.verified_by_name && (
          <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded border border-gray-100 mb-2">
            {verification.verification_action === 'raise_ticket' ? 'Ticket raised' : (verification.verification_action === 'dismiss' ? 'Dismissed' : 'Flagged')} by {verification.verified_by_name} ({verification.verified_by_role})
          </div>
        )}
      </div>

      {/* Footer Section */}
      <div className="p-3 bg-gray-50 border-t flex justify-end items-center">
        {(status === 'pending_verification' || status === 'flagged_for_discussion') ? (
          <button 
            onClick={onReview}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white py-1.5 px-3 rounded text-sm font-medium transition-colors"
          >
            Review & decide
          </button>
        ) : status === 'ticket_raised' ? (
          <div className="flex w-full justify-between items-center gap-2">
            <a href={`/councillor/track?ticketId=${alert.raised_ticket_id}`} className="text-blue-600 hover:text-blue-800 text-sm font-medium">View ticket &rarr;</a>
            {onMarkResolved && (
              <button 
                onClick={onMarkResolved} 
                className="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 py-1.5 px-3 rounded text-sm font-medium transition-colors shadow-sm"
              >
                Mark Resolved
              </button>
            )}
          </div>
        ) : (
          <button onClick={onReview} className="text-gray-500 hover:text-gray-700 text-sm font-medium underline">
            Re-examine
          </button>
        )}
      </div>
    </div>
  );
}
