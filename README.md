# Travel Assistant

An AI-powered Travel Assistant built using **Retrieval-Augmented Generation (RAG)**, **LangChain Agents**, **Model Context Protocol (MCP)**, **OpenAI GPT models**, and **Chroma Vector Database**.

---

## Repository

GitHub Repository:  
https://github.com/Jasmeet02/SingaporeTravelAssistant

Clone the repository:

```bash
git clone https://github.com/Jasmeet02/SingaporeTravelAssistant
cd SingaporeTravelAssistant
```

---

## App Architecture

The application is built as a layered AI system that combines local knowledge retrieval with live external tools:

```mermaid
flowchart LR
    U[User Query] --> A[app.py\nApplication Entry Point]
    A --> AG[LangChain Agent]
    AG --> RAG[RAG Retrieval Layer]
    AG --> MCP[MCP Tool Layer]
    RAG --> V[Chroma Vector DB]
    V --> D[Travel Docs\nWikivoyage + Visit Singapore]
    MCP --> W[Weather MCP]
    MCP --> C[Currency MCP]
    AG --> LLM[OpenAI GPT Model]
    LLM --> O[Final Travel Response]
    O --> S[Sources + Citations]

```

### Core components

- **Application entry point**: `app.py` loads documents, creates the vector store, initializes the retriever, and wires the tool-using agent.
- **RAG layer**: retrieves travel knowledge from Chroma using embeddings generated from Singapore travel documents.
- **MCP tool layer**: fetches live weather and currency data from external services.
- **Agent orchestration**: decides when to use retrieval, tool calls, or both based on the user request.
- **Knowledge base**: documents stored in the `docs/` folder and indexed into the local Chroma database.
- **Conversation tracking**: session context is preserved through the history module and related state management.

### Project structure

- `app.py` — main application and orchestration logic
- `history.py` — conversation history handling
- `docs/` — source travel guides and itineraries
- `travel_mcp/` — MCP server implementations for weather and currency
- `chroma_db1/` — persisted local vector database

### Terminal UI

The app includes a terminal-based user interface that runs directly in the console.

- The CLI prompts the user for questions in the terminal.
- Responses are printed with styled formatting and source highlights.
- Users can type `quit` to exit, or `clear`/`clear_history` to reset the active session history.

### Conversation History

The app also supports conversation memory across multiple turns.

- User queries and assistant replies are stored in `conversation_history.json` via `history.py`.
- The app keeps recent messages in memory during the session and persists completed exchanges to disk.
- This allows multi-turn context, such as asking a follow-up question after an earlier answer without losing the conversation flow.

Example:

```python
# in app.py
session_messages.append({"role": "user", "content": question})
result = await agent.ainvoke({
    "messages": session_messages[-10:]
})
session_messages.append({"role": "assistant", "content": processed.strip()})
append_history(question, processed.strip())
```

The history is saved in JSON format with a timestamp, the user message, and the assistant response.

---

## Architecture

### RAG Pipeline

- Documents chunked at 400 tokens with 50-token overlap
- Embeddings generated using `text-embedding-3-small`
- Stored in Chroma Vector DB
- Retrieved chunks passed into the RAG prompt

### MCP Tools

- **Weather MCP**: retrieves current conditions and forecasts from Open-Meteo
- **Currency MCP**: converts amounts between INR, SGD, and USD

### LangChain Agent

- Orchestrates tool selection
- Ensures correct separation of destination information (RAG) and current information (MCP)
- Enforces strict rules to avoid hallucination and always cite sources

### Knowledge Base Sources

- Wikivoyage Singapore Travel Guide
- Visit Singapore Essential Information
- Visit Singapore Things To Do
- Visit Singapore Sample Itineraries

Each source is chunked, embedded, and stored with metadata including the title and URL for citation.

---

## Workflow

1. User asks a question.
2. The agent decides whether to call RAG, MCP, or both.
3. RAG retrieves relevant chunks from Chroma.
4. MCP tools fetch live data such as weather and currency.
5. The agent combines outputs into a structured response:
   - Destination Information (facts from RAG)
   - Current Information (from MCP)
   - Recommendations (LLM suggestions)
6. Sources are always listed at the end.

---

## Prompt Strategy

### RAG Prompt

- Restricts answers to retrieved context only
- Enforces a “Sources Used” section
- Prevents hallucination

### Agent Prompt

- Governs tool orchestration
- Ensures correct separation of facts vs. recommendations
- Handles missing knowledge (`RAG_STATUS: NOT_FOUND`) gracefully
- Prevents fallback to unsupported knowledge

---

## Sample Questions

### RAG Only

“Top attractions in Singapore”

→ Retrieves attractions from Wikivoyage and VisitSingapore documents


### Conversational Context**
User: Which of those are family-friendly?  
Assistant: [Filters attractions, retains context]

User: List the top 2
Assistant: [Filters attractions, retains context]

### MCP Only

“Convert 200 SGD to INR”

→ Uses the Currency MCP tool

### Combined RAG + MCP

“Plan a 3-day trip to Singapore next week and adjust for weather”

→ Retrieves itinerary suggestions from RAG
→ Fetches forecast from Weather MCP
→ Produces a weather-aware itinerary with indoor alternatives


### Error Handling

Tell me about Paris attractions

→ Handling missing knowledge and does not provide fabricated answers

## Setup

### Virtual Environment Setup

It is recommended to run the Travel Assistant inside a Python virtual environment:

```bash
# Create venv
python -m venv env

# Activate venv
# Windows
env\Scripts\activate
# Linux / macOS
source env/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure OpenAI API Key (Windows)

The Travel Assistant requires an OpenAI API key to access GPT models.

1. Sign up or log in at [OpenAI](https://platform.openai.com/).
2. Generate an API key from your account dashboard.


#### PowerShell
```powershell
 $env:OPENAI_API_KEY="your_api_key_here"
```

### Run the application

```bash
python app.py
```

---

## Deliverables Checklist

- ✅ Knowledge base from 3+ sources
- ✅ Embedding-based semantic retrieval
- ✅ Grounded answers with citations
- ✅ Weather MCP tool
- ✅ Currency MCP tool
- ✅ Combined RAG + MCP response
- ✅ Multi-turn conversation with context retention
- ✅ Clear handling of missing knowledge/tool failures
- ✅ Simple CLI interface

---
