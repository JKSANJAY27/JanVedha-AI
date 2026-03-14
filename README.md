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

1. **Omnichannel & AI-Structured Intake:** 
   AI systems automatically collect, structure, and categorize citizen issues. Natural language processing parses inputs and intelligently maps them to the correct department and ward ID.

2. **Ward-Based Ticket Routing & Filtering:** 
   Strict Role-Based Access Control (RBAC) ensures Junior Engineers only see issues for their specific ward and department. A robust migration and assignment engine manages jurisdictional boundaries effectively.

3. **Intelligent Prioritization Engine:** 
   Utilizes machine learning to prioritize tasks. Tickets aren't just listed; they are ranked by urgency, impact, and recurrence, allowing engineers and supervisors to focus on what matters most.

4. **Interactive Issue Maps (Geospatial Visualization):**
   Real-time maps (`react-leaflet`) visually represent the density and location of citizen issues. This geographic intelligence allows officials to spot regional systemic problems and deploy resources effectively across various zones.

5. **Proactive Citizen Issue Tracking & Status Timelines:**
   Citizens are no longer left in the dark. A dedicated tracking dashboard provides a detailed transparency timeline, allowing residents to proactively monitor the status, verification proofs, and resolution progress of their submitted issues.

6. **Geo-Tagged & Time-Stamped Verification:** 
   Ensures accountability by requiring geo-tagged and time-stamped evidence for completed work, eliminating "ghost" resolutions and verifying ground reality. Supervisors can view the resolution proofs directly via integrated modals.

7. **Smart Calendar Scheduling & Technician Assignment:**
   Built-in smart calendar widgets allow officials to seamlessly schedule public works and directly assign tasks to specific field technicians, ensuring structured and timeline-driven execution rather than ad-hoc responses.

8. **Social Intel & Misinformation Flagging (Ward-Mapped):** 
   Real-time fetching and scraping of social media and news, aggressively filtered by ward location keywords. It analyzes citizen sentiment, detects emerging issues, and explicitly flags misinformation campaigns. Features manual triggers for on-demand intelligence refresh.

9. **Advanced Councillor & Supervisor Capabilities:**
   The leadership dashboards feature specialized tools such as **Ward Benchmark Panels** (to compare execution velocity), **Ward Trust Score Cards** (measuring constituent satisfaction), **Scenario Planners**, and **Resource Health Cards**, ensuring administration is managed by metrics rather than assumptions.

10. **Gemini 2.5 Pro Chatbot Integration:** 
   An embedded context-aware AI assistant. Junior Engineers can query their department's pending tasks, while Commissioners can ask high-level questions about city-wide sentiment and bottlenecks. The bot strictly adheres to the user's data access permissions.

11. **AI-Assisted Public Communication:** 
   Generates official public updates and drafts responses through a comprehensive **Communication Log Panel** based on real-time execution data, ensuring citizens receive transparent, empathetic, and accurate information.

12. **Role-Specific Real-Time Dashboards:** 
   Customized UI for Commissioners, Councillors, Supervisors, Junior Engineers, and Citizens—offering unmatched visibility into execution status and public trust metrics through rich components like Recharts.

---

## 🛠 Tech Stack

- **Frontend:** Next.js 16, React 19, Tailwind CSS v4, Framer Motion, Recharts, React Leaflet.
- **Backend:** FastAPI, Python 3.11+, MongoDB (Motor).
- **AI / ML Ecosystem:** LangChain, Google Gemini 2.5 Pro, LightGBM & SHAP (Prioritization), HuggingFace Transformers (IndicBERT for Sentiment), Prophet (Anomaly/Spike forecasting).
- **Data Gathering:** AsyncPRAW & BeautifulSoup for robust social media and news scraping.

---

## 🧪 Testing the Application 

You can log in to the various dashboards using the seed credentials provided below to test role-specific functionalities.

### 🏛 Administrative & Leadership Roles
*These roles have broader access to view analytics, social sentiment, and cross-departmental data.*

| Role | Email | Password |
| :--- | :--- | :--- |
| **Commissioner / Super Admin** | `admin@janvedha.com` | `password123` |
| **Ward 1 Councillor** | `councillor@janvedha.com` | `password123` |
| **Ward 1 Supervisor** | `pgo@janvedha.com` | `password123` |

### 👷 Department-Specific Roles (Junior Engineers)
*These roles test the ward-based ticket routing. When logged in, they will only see tickets assigned to their specific department within their jurisdiction.*

| Department | Email | Password |
| :--- | :--- | :--- |
| **Water Supply (Dept D01)** | `water@janvedha.com` | `password123` |
| **Electrical (Dept D05)** | `dept@janvedha.com` | `password123` |
| **Health & Sanitation (Dept D08)**| `sanitation@janvedha.com`| `password123` |
| **Roads & Bridges (Dept D01)** | `je.d01@janvedha.ai` | `Password123` |
| **Buildings & Planning (Dept D02)**| `je.d02@janvedha.ai` | `Password123` |
| **Sewage & Drainage (Dept D04)** | `je.d04@janvedha.ai` | `Password123` |

*(Note: Additional JE accounts for D03 to D14 follow the format `je.dXX@janvedha.ai` with password `Password123`).*

### 🚶 Citizen / Public User Role
You can register a new account from the portal to test the public complaint submission process, which automatically mandates ward selection and categorizes the ticket for backend routing.
