"""
Data Analyst Agent - Phase 1
Ask questions about an SQLite database in plain English.

Setup:
    pip install anthropic pandas
    Set the environment variable ANTHROPIC_API_KEY
    Change DB_PATH below to your e-commerce database file

Run:
    python agent.py
"""

import sqlite3
import anthropic
import pandas as pd

DB_PATH = "ecommerce.db"        # <- your database file
MODEL = "claude-sonnet-5-5"
MAX_STEPS = 10                  # safety limit so the loop can't run forever


# ---------- 1. The tool ----------
def run_sql(query: str) -> str:
    """Run a read-only SQL query and return the result as text."""
    # mode=ro opens the database read-only, so the agent can't change data
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        df = pd.read_sql_query(query, conn)
        if df.empty:
            return "The query returned no rows."
        return df.head(50).to_string(index=False)   # cap rows sent to Claude
    except Exception as e:
        # Sending the error back lets the agent fix its own query
        return f"SQL error: {e}. Fix the query and try again."
    finally:
        conn.close()


TOOLS = [{
    "name": "run_sql",
    "description": "Run a SQLite SELECT query on the e-commerce database and return the result.",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "A SQLite SELECT query"}},
        "required": ["query"],
    },
}]


# ---------- 2. The system prompt (with schema injection) ----------
def get_schema() -> str:
    """Read the table definitions so Claude knows which tables and columns exist."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
    ).fetchall()
    conn.close()
    return "\n\n".join(r[0] for r in rows)


SYSTEM_PROMPT = f"""You are a data analyst. Answer questions about an e-commerce database.

Database schema:
{get_schema()}

Rules:
- Use the run_sql tool to get data. Never guess numbers.
- Only write SELECT queries.
- If a query fails, read the error and try a corrected query.
- Finish with a short, clear answer in plain English."""


# ---------- 3. The agent loop ----------
def ask(question: str) -> str:
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]

    for step in range(MAX_STEPS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        # No tool requested -> this is the final answer
        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")

        # Run every tool Claude asked for and send the results back
        results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  [step {step + 1}] SQL: {block.input['query']}")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": run_sql(**block.input),
                })
        messages.append({"role": "user", "content": results})

    return "Stopped: reached the maximum number of steps."


if __name__ == "__main__":
    print("Data Analyst Agent - type a question, or 'quit' to exit.\n")
    while True:
        question = input("You: ").strip()
        if question.lower() in {"quit", "exit"}:
            break
        if question:
            print(f"\nAgent: {ask(question)}\n")
