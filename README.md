# 🏢 EGRUL AI Auditor & Risk Assessment Agent

An intelligent, stateful AI agent designed to automate the validation of Russian corporate requisites (EGRUL) and assess geopolitical/compliance risks. Built with a hybrid approach, combining deterministic NLP for accuracy with LLM reasoning for flexible user interaction.

*Agent takes information about the companies from site: https://ofdata.ru/databases/egrul. The site provides EGRUL data
Model that agent is based on: qwen/qwen3-235b-a22b-2507
AI-Powered Corporate Due Diligence & Sanctions Screening Agent*

## 🎯 Business Value
Manual verification of company requisites and sanctions checks is time-consuming and prone to human error. This agent reduces verification time to seconds, automatically detects data discrepancies, and provides a transparent, weighted risk score for compliance (152-FZ).

## 🚀 Key Features (DS & MLE Highlights)

- **Hybrid NLP Pipeline:** Combines deterministic Regex parsing for 100% accurate entity extraction (INN, OGRN, OKPO) with LLM reasoning. This eliminates hallucinations, filters OCR artifacts, and significantly reduces token consumption and latency.
- **Custom Risk Scoring Engine:** Developed a multi-factor, weighted risk assessment algorithm. It evaluates direct sanctions, foreign founders, management reliability, and restricted data access to output a clear compliance recommendation (🟢 Safe to 🟴 Block).
- **Agentic Orchestration (LangGraph):** Utilizes a stateful `StateGraph` architecture with conditional routing. The agent seamlessly switches between conversational reasoning (`agent_node`) and deterministic tool execution (`tool_node`).
- **Intelligent Discrepancy Resolution:** If user-provided requisites conflict with official registry data (e.g., mismatched INN/KPP), the agent proactively pauses, presents the discrepancies, and prompts the user to select the correct data source before proceeding.
- **Robust API Integration:** Features fallback logic, timeout handling, and structured JSON parsing when querying external corporate data providers (Ofdata API).

## 🏗 Architecture

The system follows an **Orchestrator + Tools** pattern:
1. **Agent Node:** Processes user input using a lightweight LLM (via OpenRouter) guided by a strict system prompt.
2. **Router:** Evaluates the conversation state to decide whether to continue chatting, execute a tool, or end the turn.
3. **Tool Node:** 
   - Extracts entities via Regex.
   - Queries the external API with optimized payload construction.
   - Runs the custom `sanctions_risk_check` algorithm.
   - Formats a structured, human-readable compliance report.

## 🛠️ Tech Stack

- **Languages:** Python 3.10+
- **AI & Orchestration:** LangGraph, LangChain, OpenRouter API (Qwen models)
- **Data Processing:** Regex, JSON, Requests
- **Concepts:** Named Entity Recognition (NER), Stateful Multi-turn Conversations, Rule-based Risk Scoring, Prompt Engineering

## ⚙️ How to Run

1. **Clone the repository:**
```bash
git clone https://github.com/ssoberin/egrul-ai-auditor.git
cd egrul-ai-auditor
```
2. **Install dependencies:**
```bash
pip install langchain langchain-openai langgraph requests typing-extensions
```
3. **Set up environment variables:**
   Create a `.env` file or directly update the script with your API keys:
   ```python
   OFFDATA_KEY = "your_ofdata_api_key"
   OPENROUTER_KEY = "your_openrouter_api_key"

**Run the agent:**
```bash
python main.py
```
*Try inputting: "Проверь компанию с ИНН 7736050003"*

## 📈 Future Improvements
Integrate asynchronous API calls (aiohttp) for concurrent multi-company checks.
Add a vector database (RAG) to cross-reference extracted requisites with unstructured PDF contracts.
Deploy as a FastAPI microservice with a Swagger UI for seamless frontend integration.

*Author: Samira Khamidullova 
Open to Data Scientist & ML Engineer roles*
