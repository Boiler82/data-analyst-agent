"""
Evaluate the Data Analyst Agent.

Asks the agent every question in eval_questions.py, compares its answer with the
correct answer (calculated by your own SQL), and prints a score.

Run all questions:        python evaluate.py
Run only question 3:      python evaluate.py 3
"""

import re
import sqlite3
import sys
import time
from datetime import datetime

import pandas as pd

from agent import ask, DB_PATH, MODEL
from eval_questions import QUESTIONS

# Added to every question, so the agent ends with an answer we can check automatically
EVAL_INSTRUCTION = (
    "\n\n(Evaluation mode: do not make charts. End your reply with one final line "
    "in the form 'FINAL: <answer>', where <answer> is only the number or the short "
    "name - no units, no extra words.)"
)


# ---------- 1. The correct answer, from your SQL ----------
def get_truth(sql: str):
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


# ---------- 2. Read the agent's answer from its 'FINAL:' line ----------
def extract_final(reply: str) -> str | None:
    matches = re.findall(r"FINAL:\s*(.+)", reply)
    if not matches:
        return None
    return matches[-1].strip().strip("*`'\". ")


def to_number(text: str) -> float | None:
    # "16,008,872.12 BRL" -> 16008872.12  and  "8.1%" -> 8.1
    match = re.search(r"-?\d[\d,]*\.?\d*", text)
    if not match:
        return None
    return float(match.group().replace(",", ""))


def normalize(text: str) -> str:
    # "Health & Beauty" -> "healthbeauty", so small spelling differences don't matter
    return re.sub(r"[^a-z0-9]", "", text.lower().replace("&", ""))


# ---------- 3. Compare the two ----------
def grade(q: dict, final: str | None, truth) -> bool:
    if final is None:
        return False
    if q["type"] == "number":
        value = to_number(final)
        return value is not None and abs(value - float(truth)) <= q["tolerance"]
    accepted = [normalize(a) for a in q["accept"]] + [normalize(str(truth))]
    return normalize(final) in accepted


# ---------- 4. Run the test ----------
def main():
    # Optional: run a single question, e.g. "python evaluate.py 3"
    selected = list(enumerate(QUESTIONS, start=1))
    if len(sys.argv) > 1:
        number = int(sys.argv[1])
        selected = [(number, QUESTIONS[number - 1])]

    rows = []
    for i, q in selected:
        print(f"\n[{i}/{len(QUESTIONS)}] ({q['level']}) {q['question']}")
        truth = get_truth(q["truth_sql"])

        start = time.time()
        try:
            reply = ask(q["question"] + EVAL_INSTRUCTION)
        except Exception as e:
            reply = f"ERROR: {e}"
        seconds = round(time.time() - start, 1)

        final = extract_final(reply)
        correct = grade(q, final, truth)
        print(f"   Correct answer: {truth}")
        print(f"   Agent answered: {final}")
        print(f"   {'✅ CORRECT' if correct else '❌ WRONG'}  ({seconds}s)")

        rows.append({
            "nr": i, "level": q["level"], "question": q["question"],
            "correct_answer": truth, "agent_answer": final,
            "correct": correct, "seconds": seconds, "full_reply": reply,
        })

    # Summary
    results = pd.DataFrame(rows)
    score = results["correct"].sum()
    total = len(results)
    print("\n" + "=" * 50)
    print(f"SCORE: {score}/{total} correct ({score / total:.0%})   model: {MODEL}")
    print(results.groupby("level", sort=False)["correct"].agg(["sum", "count"])
                 .rename(columns={"sum": "correct", "count": "questions"}))

    # Save everything, so you can read the full replies of wrong answers later
    filename = f"eval_results_{datetime.now():%Y-%m-%d_%H%M}.csv"
    results.to_csv(filename, index=False)
    print(f"\nFull results saved to {filename}")


if __name__ == "__main__":
    main()
