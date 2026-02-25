"""
AI Services Package

Contains all LangChain-based AI agents for the JanVedha civic complaint pipeline:
  - gemini_client   : Shared Gemini LLM setup
  - classifier_agent: Classify complaint → dept/category/language
  - routing_agent   : Confirm/adjust department routing
  - priority_agent  : Hybrid rule+ML priority scorer
  - suggestion_agent: Generate actionable recommendations
  - memory_agent    : Seasonal/recurring pattern detection
  - pipeline        : End-to-end orchestrator
"""
