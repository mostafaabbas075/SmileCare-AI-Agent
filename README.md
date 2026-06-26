# 🦷 SmileCare AI Agent - Dental Clinic Receptionist

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-Integration-green)
![Gemini](https://img.shields.io/badge/Google_Gemini-2.5_Flash-orange)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)

An intelligent, full-stack **AI Agent** designed to automate dental clinic reception tasks. Unlike standard RAG chatbots, this system features **Agentic Behavior** with dynamic tool calling, constraint validation, and session memory to handle actual business logic like booking appointments.

---

## 🎥 Project Demo & Discussion

I recently shared a full demonstration of this AI Agent in action, showcasing its reasoning, validation logic, and memory capabilities. 

👉 **[Watch the Demo & Join the Discussion on LinkedIn](YOUR_LINKEDIN_POST_LINK_HERE)**

---

## ✨ Key Features

* **🧠 Agentic Workflow & Tool Calling:** The AI doesn't just chat; it takes actions. It extracts entities (Name, Age, Phone, Date, Time) from natural language and triggers a Python backend tool to execute the booking process.
* **🛡️ Constraint Validation:** Built-in guardrails ensure the Agent never books an appointment without collecting all required patient information, gracefully asking follow-up questions until the data is complete.
* **📚 RAG (Retrieval-Augmented Generation):** Uses Qdrant Vector DB to answer queries based *only* on the clinic's actual knowledge base (doctors, pricing, working hours), preventing LLM hallucinations.
* **🔄 Conversation Memory:** Maintains stateful interactions using `SessionStorage` and Backend RAM mapping, allowing the AI to remember patient context across the conversation.
* **⚡ Modern Architecture:** Decoupled architecture with a robust FastAPI backend and a sleek Next.js (React) frontend.

---

## 🏗️ Tech Stack

### Backend
* **Framework:** FastAPI (Async)
* **AI & Orchestration:** Google GenAI SDK (Gemini 2.5 Flash), LangChain Core
* **Vector Database:** Qdrant (Local Docker container)
* **Embeddings:** HuggingFace `all-MiniLM-L6-v2` via SentenceTransformers
* **Relational DB:** PostgreSQL & SQLAlchemy (Prepared for Phase 2 persistence)

### Frontend
* **Framework:** Next.js (TypeScript/React)
* **Styling:** Tailwind CSS (Glassmorphism design)
* **State Management:** React Hooks & SessionStorage for Memory ID

### Infrastructure
* **Containerization:** Docker & Docker Compose (Multi-stage builds)

---

## 🚀 Getting Started (Local Development)

### 1. Prerequisites
* Docker & Docker Compose
* Python 3.11+
* Node.js 18+

### 2. Environment Setup
Create a `.env` file in the `backend` directory:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
POSTGRES_USER=dental_user
POSTGRES_PASSWORD=dental_password
POSTGRES_DB=dental_receptionist
POSTGRES_PORT=5432
POSTGRES_HOST=localhost
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### 3. Run Infrastructure (Databases)
Start the PostgreSQL and Qdrant containers in the background:
```bash
docker compose up -d db qdrant
```

### 4. Run Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 5. Run Frontend
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
Visit `http://localhost:3000` to interact with the Agent.

---

## 🗺️ Roadmap (Phase 2)
- [ ] **Data Persistence:** Connect the `book_dental_appointment` Mock Tool to PostgreSQL using SQLAlchemy to save real appointments.
- [ ] **Authentication:** JWT-based login for Clinic Admins.
- [ ] **CRM Dashboard:** A dedicated admin panel in the frontend to view, approve, and cancel appointments.

---
*Built with ❤️ for solving real-world business challenges using AI.*