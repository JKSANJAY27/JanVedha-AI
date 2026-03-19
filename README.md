# JanVedha AI: AI for Local Leadership, Decision Intelligence & Public Trust

## 🌍 The Problem

Local leaders and community administrators operate at the front line of public service delivery, managing citizen issues, development work, public communication, and trust. However, most grassroots governance processes remain fragmented, manual, and unstructured.

Public grievances, work progress, scheme implementation data, and citizen sentiment are often scattered across verbal complaints, paper records, and social media. This results in **poor prioritization, delayed action, lack of verifiable proof, and declining public trust**.

Furthermore, social media plays a growing role in shaping public opinion, yet it is rarely used systematically for governance. This leads to misinformation, reactive communication, and missed opportunities for transparency.

**The Challenge:** Design an AI-powered leadership and decision-support system that helps local leaders understand ground realities, prioritize effectively, execute efficiently, and communicate transparently using both on-ground data and digital public signals.

---

## 🚀 The Solution: JanVedha AI

**JanVedha AI** is a novel, hyper-local governance platform that transforms fragmented citizen grievances and unstructured social sentiment into **actionable decision intelligence**. By marrying deterministic civic data (complaints, department metrics) with probabilistic AI insights (sentiment analysis, predictive prioritization, LLM-based assistants), JanVedha provides an end-to-end command center for modern civic leadership.

### Why is this Novel?
1. **Context-Aware Hyper-Localization:** Unlike generic ticketing tools, JanVedha is inherently designed around civic architecture. Every piece of data—from a logged complaint to a social media post—is dynamically routed and mapped to specific **wards and departments**.
2. **Proactive vs. Reactive:** By integrating external social media intelligence alongside internal grievance data, leaders can spot emerging issues *before* they escalate into formal complaints or PR crises.
3. **Explainable AI Prioritization:** We move beyond chronological sorting by utilizing LightGBM & SHAP to intelligently score issues based on impact, recurrence, and urgency.
4. **Interactive Decision Intelligence:** A Gemini-powered AI chatbot acts as a real-time data analyst for every civic official, aware of their specific role, ward, and departmental access rights.

---

## ✨ Key Features Implemented

### 1. 🎥 Autonomous CCTV Sentinel (Vision AI)
*   **The Problem:** Many civic issues (garbage, waterlogging, illegal parking) occur in public view but go unreported for hours.
*   **The Solution:** Uses **OpenCV** and **Gemini 1.5 Flash** to autonomously analyze CCTV feeds.
*   **Intelligence:** It extracts frames, categorizes issues, assigns confidence scores, and suggests ticket metadata automatically.
*   **Decision Loop:** Councillors can review detections in a dedicated dashboard, verifying and converting them into formal department tickets with a single click.

### 2. 🗺️ Infrastructure Opportunity Spotter
*   **The Problem:** Repeated repairs on the same street indicate systemic infrastructure failure, not just a one-off issue.
*   **The Solution:** An interactive geospatial grid (500m x 500m) that identifies "Opportunity Zones."
*   **Metrics:** It analyzes 6+ months of historical data to track **Complaint Volume**, **Resolution Failure Rates**, and **Recurrence Scores**.
*   **AI Insight:** Top failing zones are narrated by Gemini to explain *why* the area is failing and what long-term intervention is required.

### 3. 📄 AI Development Proposal Generator
*   **The Problem:** Local leaders often lack the staff or data to draft professional, mathematically justified funding proposals.
*   **The Solution:** Generates formal municipal proposals in **.docx** format.
*   **Evidence Gathering:** Automatically queries all tickets within a 1km radius to build a bulletproof problem statement.
*   **Costing & Timelines:** Auto-estimates budgets using standard municipal cost lookups and generates structured implementation timelines.

### 4. 🎙️ Constituent Casework Log (Voice-First)
*   **The Problem:** Councillors receive dozens of verbal walk-in complaints daily; logging text manually is a bottleneck.
*   **The Solution:** A voice-to-JSON logging system using **MediaRecorder** and Gemini's audio processing.
*   **Escalation Detection:** The system automatically flags "Recurrent Grievances" if the same constituent files multiple issues in a short period.
*   **Privacy:** Features automatic phone number masking (`98XXXX3210`) for public list views while maintaining a full history for the councillor.

### 5. 📰 Media & RTI Response Assistant
*   **The Problem:** RTIs and press queries require strict data accuracy and formal formatting, often leading to delays or misinformation.
*   **The Solution:** A robust AI drafting tool grounded in live ward statistics.
*   **RTI OCR:** Uses Gemini Vision to extract queries from scanned RTI paper documents.
*   **Data Grounding:** The tool queries live ticket metrics (resolution rates, repair times) to ensure the responses are factual and not hallucinated.

### 6. 📢 Constituent Communication Center
*   **The Problem:** Communicating ward updates (water cuts, work completion) across SMS, WhatsApp, and notices takes too much time.
*   **The Solution:** A **bilingual (Tamil & English)** multichannel broadcast hub.
*   **One-Click Drafts:** Generates punchy social posts, character-limited SMS updates, and formal PDF notices (`fpdf2`) simultaneously.
*   **Verification Proofs:** Links announcements directly to specific resolved tickets, providing citizens with "Proof of Work" images.

### 7. 🛡️ Social Intel & Misinformation Flagging
*   **Intelligence:** Scrapes social media and news for ward-specific keywords.
*   **NLP:** Detects citizen sentiment spikes and explicitly flags potential misinformation campaigns.
*   **Context:** Alerts are mapped to specific wards, allowing councillors to respond to digital narratives before they escalate.

### 8. 📊 Explainable AI Prioritization & Smart Routing
*   **Algorithm:** Uses **LightGBM & SHAP** to score tickets based on impact, recurrence, and urgency.
*   **RBAC:** Strict Role-Based Access Control ensures that officials see only the data relevant to their specific department and jurisdiction.

### 9. 🤖 Gemini-Powered Decision Bot
*   **Context-Aware:** An embedded assistant that knows the user's role and data access level.
*   **Functionality:** Junior Engineers can ask about pending tasks, while Commissioners can query high-level city trends and bottlenecks.

### 10. 🏛️ Role-Specific Real-Time Dashboards
*   **Visualization:** Interactive Leaflet maps and Recharts-powered analytics offer unmatched visibility into execution status and public trust metrics.

---

## 📸 Screenshots & Showcase

<p align="center">
  <img src="images/WhatsApp%20Image%202026-03-14%20at%204.06.52%20PM.jpeg" width="48%" alt="Dashboard Screenshot 1" />
  <img src="images/WhatsApp%20Image%202026-03-14%20at%204.18.15%20PM.jpeg" width="48%" alt="Dashboard Screenshot 2" />
</p>

<p align="center">
  <img src="images/WhatsApp%20Image%202026-03-14%20at%204.18.19%20PM.jpeg" width="48%" alt="Dashboard Screenshot 3" />
  <img src="images/WhatsApp%20Image%202026-03-14%20at%204.18.27%20PM.jpeg" width="48%" alt="Dashboard Screenshot 4" />
</p>

<p align="center">
  <img src="images/WhatsApp%20Image%202026-03-14%20at%204.18.31%20PM.jpeg" width="48%" alt="Dashboard Screenshot 5" />
  <img src="images/WhatsApp%20Image%202026-03-14%20at%204.18.34%20PM.jpeg" width="48%" alt="Dashboard Screenshot 6" />
</p>

<p align="center">
  <img src="images/WhatsApp%20Image%202026-03-14%20at%204.18.38%20PM.jpeg" width="48%" alt="Dashboard Screenshot 7" />
</p>

---

## 🛠 Tech Stack

- **Frontend:** Next.js 16, React 19, Tailwind CSS v4, Framer Motion, Recharts, React Leaflet.
- **Backend:** FastAPI, Python 3.11+, **Beanie ODM** (Motor) for MongoDB.
- **AI / ML Ecosystem:** LangChain, Google Gemini 2.5 (Pro & Flash), LightGBM & SHAP (Prioritization), IndicBERT (Sentiment), Prophet (Forecasting).
- **Libraries:** **OpenCV** (Vision Extraction), **python-docx** (Proposal Generation), **fpdf2** (Bilingual PDF Generation), AsyncPRAW & BeautifulSoup (Scraping).

---

## 🧪 Testing the Application 

### 1. Seed the Database
Populate your local MongoDB with cameras, alerts, and historical ticket data:

```bash
cd backend
python scripts/seed_cameras.py
python scripts/seed_demo_alerts.py
python scripts/seed_demo_tickets.py
python scripts/seed_demo_casework.py
```

### 2. Login Credentials
Access the various dashboards using the credentials below.

| Role | Email | Password | Notable Features |
| :--- | :--- | :--- | :--- |
| **Commissioner** | `admin@janvedha.com` | `password123` | City-wide Vision Alerts, Social Intel |
| **Ward Councillor** | `councillor@janvedha.com` | `password123` | Casework Inbox, Proposal Gen, Comms |
| **Ward Supervisor** | `pgo@janvedha.com` | `password123` | Ticket Verification, Proof Review |
| **Junior Engineer** | `water@janvedha.com` | `password123` | Dept-specific ticket routing |

*(Note: Additional JE accounts for D03 to D14 follow the format `je.dXX@janvedha.ai` with password `Password123` where `XX` is the department ID).*

### 3. Citizen Experience
You can register a new account from the web portal to test the public complaint submission process, which automatically mandates ward selection and categorizes the ticket for backend routing.
