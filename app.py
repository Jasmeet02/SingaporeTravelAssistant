"""Travel Assistant application entry point."""

print("[startup] Launching Travel Assistant (initializing)...", flush=True)
print("[startup] Loading knowledge base and model context. This may take a few seconds...", flush=True)

# Suppress Python warnings (third-party libs may emit them)
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
try:
    from langchain_community.document_loaders import DirectoryLoader, TextLoader
except Exception:
    try:
        from langchain.document_loaders import DirectoryLoader, TextLoader
    except Exception:
        raise ImportError(
            "Missing document loader dependency. Install `langchain-community` or `langchain` (newer versions).")
import os
import logging
import sys
import itertools
import threading

from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import Tool
import asyncio
from langchain.agents import create_agent
import time
# Configure logging: default to ERROR to suppress warnings and debug output
logging.basicConfig(level=logging.ERROR)
from history import append_history, save_history

# Config
PERSIST_DIR = "./chroma_db1"
 

# Optional colored terminal output (works well on Windows with colorama)
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
    COLOR = {
        "title": Fore.CYAN + Style.BRIGHT,
        "sep": Fore.YELLOW,
        "example": Fore.GREEN,
        "hint": Fore.MAGENTA,
        "reset": Style.RESET_ALL,
    }
except Exception:
    # colorama not installed or unavailable — fall back to no colors
    COLOR = {k: "" for k in ("title", "sep", "example", "hint", "reset")}


# Show immediate startup banner and record start time so users see any startup lag
MODULE_START = time.time()


def start_loading_indicator(label: str):
    """Start a simple terminal spinner in the background."""
    stop_event = threading.Event()

    def _animate():
        spinner = itertools.cycle(["|", "/", "-", "\\"])
        while not stop_event.wait(0.10):
            print(f"\r{label} {next(spinner)}", end="", flush=True)

    thread = threading.Thread(target=_animate, daemon=True)
    thread.start()
    return stop_event


# Start the loading state immediately, before any expensive work begins.
startup_loading = start_loading_indicator("[startup] Initializing app")

# Conversation history configuration (module-level so tools can access it)

loader = DirectoryLoader(
    "docs",
    glob="*.md",
    loader_cls=TextLoader
)

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small"
)

if os.path.exists(PERSIST_DIR) and os.listdir(PERSIST_DIR):
    print("\r[startup] Existing vector DB found; loading...", flush=True)
    logging.debug("Loading existing vector database...")

    vectorstore = Chroma(
        persist_directory=PERSIST_DIR,
        embedding_function=embeddings
    )
    startup_loading.set()
    print("\r[startup] Existing vector DB loaded.                    ", flush=True)
    print()

else:
    print("\r[startup] No persisted vector DB found; creating index...", flush=True)
    logging.debug("Creating vector database...")

    document = loader.load()

    for doc in document:
       source_file = os.path.basename(doc.metadata["source"])

       if source_file == "wikivoyage_singapore.md":
        doc.metadata["title"] = "Wikivoyage Singapore Travel Guide"
        doc.metadata["url"] = "https://en.wikivoyage.org/wiki/Singapore"

       if source_file == "visit_singapore_essental_information.md":
        doc.metadata["title"] = "Visit Singapore Travel Guide"
        doc.metadata["url"] = "https://www.visitsingapore.com/travel-tips/essential-travel-information/" 

       elif source_file == "visit_singapore_things_to_do.md":
        doc.metadata["title"] = "Visit Singapore Things To Do"
        doc.metadata["url"] = "https://www.visitsingapore.com/things-to-do/"

       elif source_file == "visit_singapore_itineraries.md":
        doc.metadata["title"] = "Visit Singapore Sample Itineraries"
        doc.metadata["url"] = "https://www.visitsingapore.com/travel-tips/travelling-to-singapore/itineraries/"

    for doc in document:
        logging.debug("metadata: %s | %s", doc.metadata.get("title"), doc.metadata.get("url"))

    from langchain_text_splitters import RecursiveCharacterTextSplitter
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
    ).split_documents(document)
    logging.debug('PDF Successfully chunked==============')
    logging.debug("Loaded %d documents", len(document))
    logging.debug("Created %d chunks", len(chunks))
    for chunk in chunks[:10]:
        logging.debug(chunk.metadata)


    vectorstore = Chroma.from_documents(chunks, embeddings, persist_directory = PERSIST_DIR)
    startup_loading.set()
    print("\r[startup] Vector DB created successfully.              ", flush=True)
    print()
print(f"[startup] Vector DB ready (took {time.time()-MODULE_START:.2f}s)", flush=True)
logging.debug("Before retriever")

retriever = vectorstore.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={
        "score_threshold": 0.3,
        "k": 10
    }
)


# ---------------------------------------------------------------------------
# 4. Prompt Template
# Grounding prompt for question answering: the model must answer ONLY from the
# retrieved context chunks, admit when it doesn't know, and stay concise.
# {input} is filled with the user's question; {context} with retrieved chunks.
# ---------------------------------------------------------------------------

template = """
You are an AI Travel Planning Assistant.

Rules:

1. Use ONLY the supplied context for destination facts.
2. Use MCP tool results for current information. 
3. Clearly identify the source of any information you provide.
4. If information is missing, say so clearly.
5. Do not invent attractions or travel details.
6. At the end of every answer include the
"Sources Used" section exactly as provided in the context metadata if available.
Do not invent sources.
Do not generate example.com URLs.
Only show URLs that exist in the retrieved context.
7. Handle unavailable tools or failed results without fabricating an answer.
8. Separate facts from recommendations.
9. If the requested destination is not present in the RAG context:

- State that the destination is not available in the knowledge base.
- Do not provide generic travel recommendations.
- Do not use your own knowledge.
- Do not infer information from other destinations.
10. Use the following format:
    Question:
    {input}

    Context:
    {context}

    Response:

"""

prompt = PromptTemplate.from_template(template)


# Now index docs_for_store into your vector DB (example with Chroma + HF embeddings)
# emb = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
# store = Chroma.from_documents(docs_for_store, embedding=emb, persist_directory="chroma_db1")
# store.persist()

def format_docs(docs):
    """Flatten retrieved chunks into a single text block for the prompt context.

    Strategy:
    - Remove chunks that are exact substrings of already-included chunks.
    - If a new chunk fully contains an existing one, replace the existing (prefer longer).
    - Stop when `limit` unique chunks are collected.
    """
    parts = []
    logging.debug("Loaded %d documents", len(docs))
    for doc in docs:
        logging.debug("SOURCE: %s", doc.metadata.get("source"))
        logging.debug(doc.page_content[:200])
        logging.debug("%s", "=" * 50)
        content = doc.page_content.strip()
        
        if not content:
            continue
                
        # Remove duplicates by substring relationship
        replaced = False
        for i, existing in enumerate(parts):
            if content in existing:
                replaced = True
                break
            if existing in content:
                # new content is more complete; replace shorter existing
                parts[i] = content
                replaced = True
                break

        if not replaced:
            parts.append(
               f"""
               Title: {doc.metadata.get('title', 'Unknown')}
               URL: {doc.metadata.get('url', 'Unknown')}
               Content:
                {content}
                """
            )

    return (
    "\n\n".join(parts) 
    if parts
    else "NO_CONTEXT_FOUND"
)



def collapse_repeated_answer_blocks(text: str) -> str:
    import re

    parts = re.split(
        r"\n---+\n|Answer:\s*",
        text
    )

    seen = set()
    out_parts = []

    for p in parts:
        s = p.strip()

        if not s:
            continue

        key = re.sub(r"\s+", " ", s).lower()

        if key in seen:
            continue

        seen.add(key)
        out_parts.append(s)

    return "\n\n---\n\n".join(out_parts)


def print_decorated_answer(text: str) -> None:
    """Print the assistant answer with a colored, boxed header and highlight sources.

    If the text contains a 'Sources Used:' section, render that heading in the
    separator color and keep the sources in-place.
    """
    header_line = "─" * 72
    print()
    print(f"{COLOR['sep']}{header_line}{COLOR['reset']}")
    print(f"{COLOR['title']}AI Travel Assistant — Plan{COLOR['reset']}")
    print(f"{COLOR['sep']}{header_line}{COLOR['reset']}")

    # If there is a Sources Used section, highlight the heading
    if "Sources Used:" in text:
        parts = text.split("Sources Used:", 1)
        body = parts[0].strip()
        sources = parts[1].strip()
        if body:
            print(body)
            print()
        print(f"{COLOR['sep']}Sources Used:{COLOR['reset']}")
        # print each source line with example color (green)
        for line in sources.splitlines():
            print(f"{COLOR['example']}{line}{COLOR['reset']}")
    else:
        print(text)

    print(f"{COLOR['sep']}{header_line}{COLOR['reset']}")




# ---------------------------------------------------------------------------
# 5. RAG Chain Assembly (Retrieval → Augmentation → Generation)
# LangChain LCEL pipeline wiring all stages together:
#   - Retrieval:    retriever fetches top-6 relevant chunks for the question.
#   - Augmentation: format_docs merges them into the prompt's {context} slot.
#   - Generation:   MLX Gemma generates the answer (max 2000 tokens, temp 0.2).
# chain.invoke(question) runs the whole pipeline end-to-end.
# ---------------------------------------------------------------------------

llm = ChatOpenAI(
         model="gpt-4o-mini",
         temperature=0.2
         )
rag_chain = (
             {
                 "context": retriever | RunnableLambda(format_docs),
                 "input": RunnablePassthrough()
             }
             | prompt
             | llm
             | StrOutputParser()
         )

def travel_rag(query: str) -> str:
    logging.debug("TRAVEL_RAG CALLED: %s", query)
    logging.debug("TOOL INPUT = [%s]", query)
  
    docs = retriever.invoke(query)

    logging.debug("Retrieved docs: %d", len(docs))

    if len(docs) == 0:
      return """
        RAG_STATUS: NOT_FOUND

        Destination information is not available in the Travel Knowledge Base.
            
    """
    response = rag_chain.invoke(query)
    llm_answer = response  # rag_chain returns the generated answer string
    
    citations = []
    seen = set()

    for d in docs:
        try:
          title = d.metadata.get("title")
          url = d.metadata.get("url")
        except Exception:
          continue

        if not title:
            continue

        key = (title, url)

        if key in seen:
          continue

        seen.add(key)

        if url:
            citations.append(
            f"- {title}\n  {url}"
        )
        else:
         citations.append(
            f"- {title}"
        )

    final_answer = (
        llm_answer
    + "\n\nSources Used:\n"
    + "\n".join(citations)
    )

    return final_answer


async def main():
     client = MultiServerMCPClient({
             "weather": {
             "command": "python",
              "args": ["travel_mcp/weather_mcp_server.py"],
              "transport": "stdio"
              },
              "currency": {
                  "command": "python",
                  "args": ["travel_mcp/currency_mcp_server.py"],
                  "transport": "stdio"
              },
              
            })
        
     mcp_tools = await client.get_tools()
    

     rag_tool = Tool(
      name="travel_knowledge",
      description="""
       MANDATORY source for Singapore travel information.

       IMPORTANT:
        Pass the user's full travel query unchanged.
        Correct examples:
        - Top attractions in Singapore
        - Singapore food
        - Singapore transportation
        - Three-day itinerary Singapore
        - Family activities in Singapore

        Incorrect examples:
        - Singapore
        - attractions
        - food

       Do NOT simplify or shorten the user's query.
      Use the complete user request as tool input.

       NEVER answer these questions without calling this tool first.

       Do NOT use for:
       - weather forecasts
       - currency conversion
     """,
    func=travel_rag
    )
     all_tools = [rag_tool] + mcp_tools
     for tool in all_tools:
      logging.debug(tool.name)

     agent = create_agent(
      model=llm,
      tools=all_tools,
      system_prompt="""
     You are an AI Travel Assistant.

    IMPORTANT:
    - NEVER answer from your own knowledge.
    - For destination information, ALWAYS use the travel_knowledge tool.
    - For all destination information, ALWAYS provide the source url of the information.
    - For weather information, ALWAYS use the weather MCP tool.
    - For currency information, ALWAYS use the currency MCP tool.
    - The travel_knowledge tool contains ONLY Singapore travel information.
    - When both travel_knowledge and weather tools are used:
      * Do not output them as separate blocks.
      * Merge the travel_knowledge context and weather forecast into a single itinerary.
      * The itinerary itself must reflect the weather forecast (e.g., indoor attractions on thunderstorm days).
      * Still include "Sources Used" with both RAG and MCP citations.
    - Do not remove destination names.
    - If the tool reports information unavailable, do not use your own knowledge.
    - Do not provide generic travel recommendations.
    - Do not invent attractions.
    - If information is unavailable, respond exactly with the tool result.
    - Format the response based on the tools used:

      If MCP was used:

      Current Information (from MCP Tool Result):
      <current information>

      If RAG data was used:

      Destination Information (from RAG Knowledge Base):
      <destination facts>

      If recommendations are provided, clearly separate them from facts:

      Recommendations:
      <recommendations>

      - When both travel_knowledge and weather tools are used:
            * Do not output them as separate blocks.
            * Merge the travel_knowledge context and weather forecast into a single itinerary.
            * The itinerary itself must reflect the weather forecast (e.g., indoor attractions on thunderstorm days).
            * Still include "Sources Used" with both RAG and MCP citations.

    - For all MCP tool responses:
       - If the tool reports an error, do not fabricate an answer. Just mention that there was an error and include the tool's error message.
    - For all responses:
        - If the response uses MCP tool data, include the MCP tool's "Sources Used" section at the end of the answer.
          Example:
          Sources Used:
          - Weather MCP Server (Open-Meteo)
        - If the response uses RAG tool data, include the RAG tool's "Sources Used" section at the end of the answer.
          Example:
          Sources Used:
          - Wikivoyage Singapore Travel Guide
          - Visit Singapore Things To Do
        - For all responses that use both MCP and RAG data, combine the "Sources Used" sections into a single section at the end of the answer.   
          Example:
          Sources Used:
          - Weather MCP Server (Open-Meteo)
          - Wikivoyage Singapore Travel Guide
          - Visit Singapore Things To Do
    - CRITICAL INSTRUCTION:
       If the travel_knowledge tool response contains:
       RAG_STATUS: NOT_FOUND
       Then:
        - Do not create an itinerary.
        - Do not recommend attractions.
        - Do not recommend activities.
        - Do not recommend restaurants.
        - Do not use your own travel knowledge.
        - Do not infer information from weather data.
        - Return the travel_knowledge tool response exactly as provided.
        - Do not call any additional tools unless they were explicitly requested by the user.
            - Do not call weather tools.
            - Do not call currency tools.

       If weather data is available at the same time:
        - You may summarize the weather.
        - You must still state that destination information is unavailable.
        - You must not create a travel plan.
   """
  )

      
    # Interactive Query Loop with multi-turn context
     session_messages = []
    # Friendly startup hint for users so they know how to interact with the demo
     print(f"\n{COLOR['sep']}╔════════════════════════════════════════════════════════════════════════╗{COLOR['reset']}")
     print(f"{COLOR['title']}║  Welcome to the AI Travel Assistant — Singapore Travel                 ║{COLOR['reset']}")
     print(f"{COLOR['sep']}╠════════════════════════════════════════════════════════════════════════╣{COLOR['reset']}")
     print(f"{COLOR['example']}║  Ask about attractions, dining, transport, itineraries, or local tips.  ║{COLOR['reset']}")
     print(f"{COLOR['example']}║  Examples: Three-day itinerary Singapore | Top hawker centres           ║{COLOR['reset']}")
     print(f"{COLOR['sep']}╚════════════════════════════════════════════════════════════════════════╝{COLOR['reset']}")
     print(f"{COLOR['hint']}Type 'quit' to exit, or 'clear' / 'clear_history' to clear conversation history.{COLOR['reset']}")
     while True:
          question = input("\nYour question (or type 'quit' / 'clear'): ")
          q_lower = question.lower().strip()
          if q_lower == "quit":
               break
          if q_lower in ("clear", "clear_history"):
               save_history([])
               session_messages = []
               print("Conversation history cleared.")
               continue

          # add user message to session context
          session_messages.append({"role": "user", "content": question})

          print(f"\n{COLOR['hint']}Thinking... retrieving travel context and checking live tools...{COLOR['reset']}")
          spinner = itertools.cycle(["|", "/", "-", "\\"])
          for _ in range(10):
              print(f"\r{COLOR['hint']}Working {next(spinner)}{COLOR['reset']}", end="", flush=True)
              time.sleep(0.15)
          print("\r" + " " * 40 + "\r", end="", flush=True)

          result = await agent.ainvoke({
                      "messages": session_messages[-10:],  # limit to last 10 messages for context
                  })
          logging.debug("agent result: %s", result)
          answer = result["messages"][-1].content

          processed = collapse_repeated_answer_blocks(answer)
          # Print the assistant's reply using the decorated, colorized formatter
          print_decorated_answer(processed.strip())

          # add assistant reply to session context and persist
          session_messages.append({"role": "assistant", "content": processed.strip()})
          logging.debug("Saving conversation history...")
          try:
               append_history(question, processed.strip())
          except Exception as exc:
               logging.debug("Failed to save conversation history: %s", exc)
     
     
  
     

if __name__ == "__main__":
   
    asyncio.run(main())