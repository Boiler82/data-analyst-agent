"""
Data Analyst Agent - Phase 2
Ask questions about your database in plain English.
The agent can now answer with charts as well as text.
"""

import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv
load_dotenv()   # reads the API key from the .env file
import matplotlib
matplotlib.use("Agg")               # draw charts to files, without opening windows
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd

DB_PATH = "ecommerce.db"
MODEL = "claude-sonnet-5-5"
MAX_STEPS = 10                      # safety limit so the loop can't run forever
CHART_FOLDER = Path("charts")       # where chart images are saved

# Chart colors: one calm blue for the data, soft greys for everything else
BAR_COLOR = "#2a78d6"
BACKGROUND = "#fcfcfb"
TEXT_DARK = "#0b0b0b"
TEXT_SOFT = "#52514e"
GRID = "#e4e3df"


# ---------- Helper: run a read-only query and return a DataFrame ----------
def query_to_df(query: str) -> pd.DataFrame:
    # mode=ro opens the database read-only, so the agent can't change data
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


# ---------- Tool 1: run SQL ----------
def run_sql(query: str) -> str:
    try:
        df = query_to_df(query)
        if df.empty:
            return "The query returned no rows."
        return df.head(50).to_string(index=False)   # max 50 rows back to Claude
    except Exception as e:
        # Sending the error back lets the agent fix its own query
        return f"SQL error: {e}. Fix the query and try again."


# ---------- Tool 2: make a chart ----------
def make_chart(query: str, chart_type: str, x: str, y: str,
               title: str, y_label: str = "") -> str:
    # 1. Get the data
    try:
        df = query_to_df(query)
    except Exception as e:
        return f"SQL error: {e}. Fix the query and try again."
    if df.empty:
        return "The query returned no rows, so no chart was made."
    if x not in df.columns or y not in df.columns:
        return (f"Column not found. The query returned these columns: "
                f"{list(df.columns)}. Use those names for x and y.")
    if len(df) > 30 and chart_type != "line":
        return f"Too many bars ({len(df)}). Limit the query to 30 rows or fewer."

    # 2. Draw the chart
    fig, ax = plt.subplots(figsize=(10, 6), facecolor=BACKGROUND)
    ax.set_facecolor(BACKGROUND)
    labels = df[x].astype(str)

    if chart_type == "bar":
        ax.bar(labels, df[y], color=BAR_COLOR, width=0.6)
        ax.yaxis.grid(True, color=GRID)
        plt.xticks(rotation=45 if len(df) > 6 else 0, ha="right" if len(df) > 6 else "center")
    elif chart_type == "barh":
        # Horizontal bars: best for long category names; largest at the top
        ax.barh(labels[::-1], df[y][::-1], color=BAR_COLOR, height=0.6)
        ax.xaxis.grid(True, color=GRID)
    elif chart_type == "line":
        ax.plot(labels, df[y], color=BAR_COLOR, linewidth=2)
        ax.yaxis.grid(True, color=GRID)
        step = max(1, len(df) // 12)            # show at most ~12 x labels
        ax.set_xticks(range(0, len(df), step))
        plt.xticks(rotation=45, ha="right")
    else:
        return "Unknown chart_type. Use 'bar', 'barh' or 'line'."

    # 3. Clean styling: no box, soft grid behind the data, readable text
    # Show big numbers as 1,200,000 instead of 1.2e6
    if df[y].abs().max() >= 1000:
        number_axis = ax.xaxis if chart_type == "barh" else ax.yaxis
        number_axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_SOFT, length=0)
    ax.set_title(title, loc="left", fontsize=15, color=TEXT_DARK, pad=16)
    if chart_type == "barh":
        ax.set_xlabel(y_label or y, color=TEXT_SOFT)
    else:
        ax.set_ylabel(y_label or y, color=TEXT_SOFT)
    fig.tight_layout()

    # 4. Save it with a readable file name, e.g. charts/2026-10-05_1310_late-deliveries.png
    CHART_FOLDER.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
    path = CHART_FOLDER / f"{datetime.now():%Y-%m-%d_%H%M%S}_{slug}.png"
    fig.savefig(path, dpi=150, facecolor=BACKGROUND)
    plt.close(fig)

    # 5. Open the image automatically on a Mac
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)])

    # Send the data back too, so Claude can describe the chart in words
    return f"Chart saved to {path}.\nData used:\n{df.head(30).to_string(index=False)}"


# ---------- Tool descriptions for Claude ----------
TOOLS = [
    {
        "name": "run_sql",
        "description": "Run a SQLite SELECT query on the e-commerce database and return the result as text.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "A SQLite SELECT query"}},
            "required": ["query"],
        },
    },
    {
        "name": "make_chart",
        "description": (
            "Run a SQLite SELECT query and save the result as a chart image. "
            "Use it when the user asks for a chart, or when a comparison or trend "
            "is clearer as a picture. The query must return one label column (x) "
            "and one number column (y), in the order they should appear."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A SQLite SELECT query returning the x and y columns"},
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "barh", "line"],
                    "description": "bar = compare a few categories; barh = categories with long names or a ranking; line = change over time",
                },
                "x": {"type": "string", "description": "Column name for the labels (categories or dates)"},
                "y": {"type": "string", "description": "Column name for the numbers"},
                "title": {"type": "string", "description": "A short title that states the main finding"},
                "y_label": {"type": "string", "description": "Axis label for the numbers, including units, e.g. 'Revenue (BRL)'"},
            },
            "required": ["query", "chart_type", "x", "y", "title"],
        },
    },
]

TOOL_FUNCTIONS = {"run_sql": run_sql, "make_chart": make_chart}


# ---------- Instructions for Claude, including the table structure ----------
def get_schema() -> str:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
    ).fetchall()
    conn.close()
    return "\n\n".join(r[0] for r in rows)


SYSTEM_PROMPT = f"""You are a data analyst. Answer questions about an e-commerce database
(the Olist Brazilian e-commerce dataset). Money amounts are in Brazilian reais (BRL).

Database schema:
{get_schema()}

Rules:
- Use run_sql to get data. Never guess numbers.
- Use make_chart when the user asks for a chart, or when a picture makes the answer clearer.
- Only write SELECT queries.
- If a query fails, read the error and try a corrected query.
- Finish with a short, clear answer in plain English. If you made a chart, say where it was saved.
- For trends over time, first check the number of orders per period. Leave out incomplete periods at the start or end of the data, and say which periods you left out and why."""


# ---------- The agent loop ----------
def ask(question: str) -> str:
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]

    for step in range(MAX_STEPS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        # Claude didn't ask for a tool -> this is the final answer
        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")

        # Run each tool Claude asked for and send the results back
        results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  [step {step + 1}] {block.name}: {block.input['query']}")
                tool = TOOL_FUNCTIONS[block.name]
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool(**block.input),
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