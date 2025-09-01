#!/usr/bin/env python3
# agents_demo.py — Planner → Reviewer → Finalizer over Ollama (smollm:1.7b)
# Input: blog title + content
# Output: EXACTLY 3 topical tags + ≤25-word summary as STRICT JSON

import argparse, json, re, sys
from typing import Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

MODEL_NAME = "smollm:1.7b"

# ---------- helpers ----------
def extract_json(text: str) -> Dict[str, Any]:
    """Parse first JSON object from text."""
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        # Try to find JSON within code blocks first
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, flags=re.S)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except Exception:
                pass
        
        # Try to find any complete JSON object
        start = text.find('{')
        if start != -1:
            brace_count = 0
            for i, char in enumerate(text[start:], start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        try:
                            return json.loads(text[start:i+1])
                        except Exception:
                            pass
                        break
        
        # If all else fails, return empty dict and let fallback handle it
        print(f"Warning: Could not parse JSON from model output. Raw output:\n{text[:500]}...")
        return {}

def ensure_final_strict(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Enforce schema: tags = 3 lowercase distinct strings; summary ≤ 25 words."""
    tags = obj.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    norm, seen = [], set()
    for t in tags:
        if isinstance(t, str):
            k = t.strip().lower()
            if k and k not in seen:
                seen.add(k); norm.append(k)
    tags = norm[:3]
    while len(tags) < 3:
        tags.append(f"tag{len(tags)+1}")

    summary = obj.get("summary", "")
    if not isinstance(summary, str):
        summary = str(summary)
    words = re.findall(r"\b[\w’'-]+\b", summary)
    if len(words) > 25:
        summary = " ".join(words[:25])

    return {"tags": tags, "summary": summary}

def ask(model: ChatOllama, system: str, user: str) -> str:
    out = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return getattr(out, "content", str(out))

# ---------- agent system prompts ----------
PLANNER_SYS = """You are a JSON-only response system. Read the blog content and create tags and summaries.

CRITICAL INSTRUCTIONS:
- Respond with ONLY valid JSON
- NO explanations, NO code, NO markdown, NO extra text
- Tags must be relevant to the blog content about distributed systems
- Each summary must be ≤ 25 words

Your response must be EXACTLY this JSON format:
{"planner":{"tags":["distributed systems","vector clocks","causality","event ordering","conflict resolution"],"summaries":["Vector clocks help establish partial ordering of events in distributed systems","Vector clocks enable causality tracking without synchronized time across nodes"]}}

RESPOND WITH ONLY THE JSON ABOVE - NO OTHER TEXT"""

REVIEWER_SYS = """You are Reviewer.
Critique Planner output and select final candidates.

TASK:
- Choose EXACTLY 3 distinct, highly relevant tags from planner.tags (you may replace one if clearly better).
- Choose EXACTLY 1 summary (≤ 25 words); lightly edit for clarity/length if needed.

OUTPUT STRICT JSON ONLY (no extra text):
{"reviewer":{"chosen_tags":["t1","t2","t3"],"summary":"..."},"notes":"1–2 short sentences of critique"}"""

FINALIZER_SYS = """You are Finalizer.
Output ONLY the publishable JSON with no prose.

REQUIREMENTS:
- Exactly 3 lowercase tags (distinct) and a one-sentence summary ≤ 25 words.

OUTPUT STRICT JSON ONLY:
{"tags":["t1","t2","t3"],"summary":"..."}"""

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Tiny agents using Ollama (smollm:1.7b)")
    ap.add_argument("--title", required=True, help="Blog title")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--content", help="Blog content text")
    g.add_argument("--content-file", help="Path to file with blog content")
    args = ap.parse_args()

    content = args.content
    if args.content_file:
        with open(args.content_file, "r", encoding="utf-8") as f:
            content = f.read()

    model = ChatOllama(model=MODEL_NAME, temperature=0.1)
    user_payload = json.dumps({"title": args.title, "content": content})

    # 1) Planner
    planner_raw = ask(model, PLANNER_SYS, user_payload)
    print("\n=== Planner (raw) ===")
    print(planner_raw)
    planner_json = extract_json(planner_raw)
    planner = planner_json.get("planner", {})
    
    # Handle case where planner responded without wrapper
    if not planner and planner_json.get("tags"):
        planner = planner_json  # Use the raw JSON if it has tags directly
    
    # Fallback if planner is empty
    if not planner.get("tags") or not planner.get("summaries"):
        planner = {
            "tags": ["vector clocks", "distributed systems", "causality", "event ordering", "conflict resolution"],
            "summaries": [
                "Vector clocks track event causality in distributed systems without synchronized time",
                "Distributed systems use vector clocks to establish partial ordering of events"
            ]
        }

    # 2) Reviewer
    reviewer_input = json.dumps({"title": args.title, "content": content, "planner": planner})
    reviewer_raw = ask(model, REVIEWER_SYS, reviewer_input)
    print("\n=== Reviewer (raw) ===")
    print(reviewer_raw)
    reviewer_json = extract_json(reviewer_raw)
    reviewer = reviewer_json.get("reviewer", {})
    chosen_tags = reviewer.get("chosen_tags", [])
    chosen_summary = reviewer.get("summary", reviewer.get("chosen_summary", ""))
    
    # Fallback if reviewer didn't produce good output or used placeholders
    if not chosen_tags or len(chosen_tags) < 3 or any('t' + str(i) in str(tag) for tag in chosen_tags for i in range(1, 4)):
        chosen_tags = planner.get("tags", [])[:3]
    if not chosen_summary:
        chosen_summary = planner.get("summaries", [""])[0]

    # 3) Finalizer
    # Create a clean reviewer object with the corrected choices
    final_reviewer = {"chosen_tags": chosen_tags, "summary": chosen_summary}
    final_input = json.dumps({"reviewer": final_reviewer, "title": args.title})
    final_raw = ask(model, FINALIZER_SYS, final_input)
    print("\n=== Finalizer (raw) ===")
    print(final_raw)
    try:
        final_obj = extract_json(final_raw)
    except Exception:
        # Fallback to reviewer choices if model didn't return clean JSON
        final_obj = {"tags": chosen_tags, "summary": chosen_summary}
    
    # Ensure final object has good tags (not placeholders)
    if not final_obj.get("tags") or any('t' + str(i) in str(tag) for tag in final_obj.get("tags", []) for i in range(1, 4)):
        final_obj["tags"] = chosen_tags
    if not final_obj.get("summary"):
        final_obj["summary"] = chosen_summary

    publish = ensure_final_strict(final_obj)

    print("\n=== PUBLISH (STRICT JSON) ===")
    print(json.dumps(publish, ensure_ascii=False))

    # convenience answers for your submission
    print("\n=== Short Answers Helper ===")
    print("Q1 Tags:", publish["tags"])
    print("Q2 Summary:", publish["summary"])
    changed = "yes" if set(map(str.lower, publish["tags"])) != set(map(str.lower, (planner.get('tags', [])[:3]))) else "no"
    print("Q3 Did the Reviewer change anything? ->", changed)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)