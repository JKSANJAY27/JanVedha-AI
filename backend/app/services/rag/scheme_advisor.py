"""
Scheme Eligibility Advisor (Generator)

Uses Gemini 2.5 Flash to generate a structured eligibility assessment based on 
reranked document chunks. Employs Langfuse decorators for tracing every step.
"""
import json
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai

# Import Langfuse observability decorator
from langfuse import observe

from app.core.config import settings
from app.services.rag.hybrid_retriever import get_hybrid_retriever
from app.services.rag.reranker import get_reranker

logger = logging.getLogger(__name__)

# Configure Gemini using JanVedha's global API key
genai.configure(api_key=settings.GEMINI_API_KEY)
MODEL_NAME = "gemini-2.5-flash"

SYSTEM_PROMPT = """
You are an expert government scheme advisor for JanVedha, an AI platform for civic administration.
A local councillor has provided a profile of a constituent. Your task is to analyze the provided government scheme documents and assess the constituent's eligibility for each scheme.

Return ONLY a valid JSON object with exactly the following structure:
{
  "eligible_schemes": [
    {
      "scheme_name": "string",
      "confidence": "HIGH",
      "reason": "string (Why they are eligible based on the profile)",
      "documents_required": ["string"],
      "application_process": "string",
      "contact_office": "string",
      "source_citations": ["string (e.g. pmay_u_2_0.md:chunk_3)"]
    }
  ],
  "partial_schemes": [
     // Same structure as above, but for schemes where confidence is MEDIUM due to missing profile info
  ],
  "ineligible_schemes": [
     // Same structure, but confidence is LOW and reason explains why they DO NOT qualify
  ],
  "missing_info": [
    "string (Crucial details missing from the profile needed to make a final determination)"
  ]
}

STRICT RULES:
1. Base your answer STRICTLY on the provided context documents. DO NOT hallucinate scheme details.
2. If a scheme's criteria clearly contradict the profile, put it in ineligible_schemes.
3. If criteria are met, put it in eligible_schemes.
4. If criteria MIGHT be met but data is missing, put it in partial_schemes and list the missing info.
5. In source_citations, you MUST use the exact 'source' and 'chunk_index' from the provided metadata (e.g., source:chunk_index).
"""

class SchemeAdvisor:
    def __init__(self):
        self.retriever = get_hybrid_retriever()
        self.reranker = get_reranker()
        self.model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)
        
    @observe(name="assess_eligibility")
    def assess_eligibility(self, profile_text: str, ward_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes the end-to-end RAG pipeline: Retrieve -> Rerank -> Generate.
        Traced by Langfuse.
        """
        logger.info(f"Assessing eligibility for profile: {profile_text[:50]}...")
        
        # 1. Retrieve
        candidates = self._retrieve_docs(profile_text)
        
        if not candidates:
            return {"error": "No relevant scheme documents found in the database."}
        
        # 2. Rerank
        reranked = self._rerank_docs(profile_text, candidates)
        
        # 3. Generate Assessment
        return self._generate_assessment(profile_text, reranked, ward_context)
        
    @observe(name="hybrid_retrieval", as_type="generation")
    def _retrieve_docs(self, query: str) -> List[Dict[str, Any]]:
        # This will be traced as a child span of 'assess_eligibility'
        return self.retriever.retrieve(query)
        
    @observe(name="cross_encoder_reranking", as_type="generation")
    def _rerank_docs(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.reranker.rerank(query, candidates)
        
    @observe(name="gemini_generation", as_type="generation")
    def _generate_assessment(
        self, 
        profile_text: str, 
        docs: List[Dict[str, Any]], 
        ward_context: Optional[str] = None
    ) -> Dict[str, Any]:
        
        # Build context string
        context_parts = []
        for i, doc in enumerate(docs):
            source = doc.get("metadata", {}).get("source", "unknown")
            chunk_idx = doc.get("metadata", {}).get("chunk_index", i)
            context_parts.append(f"--- Document Source: {source}:chunk_{chunk_idx} ---\n{doc['text']}")
            
        context_str = "\n\n".join(context_parts)
        ward_info = f"\nConstituent Ward Context: {ward_context}" if ward_context else ""
        
        # Required format for Gemini 2.5 Flash structured output
        prompt = f"""
Constituent Profile:
{profile_text}
{ward_info}

Context Documents:
{context_str}

Analyze the profile against the context documents and output the JSON array.
"""
        
        try:
            # Generate with JSON validation
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                )
            )
            return json.loads(response.text)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON output: {e}")
            logger.debug(f"Raw output: {response.text}")
            return {
                "error": "Failed to generate valid assessment structure",
                "raw_output": response.text
            }
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            return {"error": str(e)}

# Singleton
_advisor_instance = None
def get_scheme_advisor() -> SchemeAdvisor:
    global _advisor_instance
    if _advisor_instance is None:
        _advisor_instance = SchemeAdvisor()
    return _advisor_instance
