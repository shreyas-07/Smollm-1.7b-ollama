import json
from langchain_ollama import ChatOllama
import argparse
import time


def wait_ollama(base_url, max_retries=5):
    """Check if Ollama service is running"""
    import requests
    for i in range(max_retries):
        try:
            response = requests.get(f"{base_url}/api/version", timeout=3)
            if response.status_code == 200:
                return True
        except Exception:
            time.sleep(1)
    return False


def ask_ollama(prompt, model="phi3:3.8b", base_url="http://127.0.0.1:11434"):
    """Send prompt to Ollama using LangChain and return response"""
    llm = ChatOllama(
        model=model,
        temperature=0.2,
        base_url=base_url,
        num_ctx=2048,
        format="json",
    )
    response = llm.invoke(prompt)
    return response.content


def planner_prompt(topic, content):
    """Prompt for Planner agent to generate tags and summary with thought and message."""
    content_section = f"\nContent to analyze: {content}\n" if content else ""
    return f'''You are Planner.
Analyze the topic and content carefully. Check if the topic matches the content.

First, write a brief thought about whether the topic and content align.
Then, write a one-sentence message about your analysis.
Generate tags and summary based on the ACTUAL CONTENT, not just the topic title.

CRITICAL: You must provide EXACTLY 3 tags - no more, no less.

If topic and content don't match, add this to issues: "Topic does not match content"

Respond ONLY with a JSON object in this format:
{{
    "thought": "...",
    "message": "...",
    "data": {{
        "tags": ["tag1", "tag2", "tag3"],
        "summary": "..."
    }},
    "issues": []
}}

Topic: {topic}{content_section}
'''


def reviewer_prompt(topic, planner_output, content):
    """Prompt for Reviewer agent to validate and possibly revise tags/summary, with thought and message."""
    content_section = f"\nContent to analyze: {content}\n" if content else ""
    return f'''You are Reviewer.
Your job is to IMPROVE the Planner's output by checking:
1. Do the tags match the ACTUAL CONTENT (not just the topic title)?
2. Is the summary accurate for the ACTUAL CONTENT?
3. Does the topic title match the content? If not, flag it as an issue.

CRITICAL REQUIREMENTS:
- You must provide EXACTLY 3 tags - no more, no less
- If topic and content are mismatched, you MUST:
  * Create tags based on the ACTUAL CONTENT
  * Write summary based on the ACTUAL CONTENT  
  * Add to issues: "Title '[topic]' does not match content about [actual content topic]"

Make changes when needed. Don't just copy the Planner's output.

Respond ONLY with a JSON object in this format:
{{
    "thought": "...",
    "message": "...",
    "data": {{
        "tags": ["tag1", "tag2", "tag3"],
        "summary": "..."
    }},
    "issues": []
}}

Topic: {topic}{content_section}
Planner JSON: {json.dumps(planner_output, ensure_ascii=False)}
'''


def finalizer(planner_json, reviewer_json, topic, content, email):
    """Combine and print the finalized output and publish package."""
    finalized = {
        "thought": reviewer_json.get("thought", ""),
        "message": reviewer_json.get("message", ""),
        "data": reviewer_json.get("data", {}),
        "issues": reviewer_json.get("issues", []),
    }
    print("\n=== Finalized output ===\n")
    print(json.dumps(finalized, indent=2, ensure_ascii=False))

    publish = {
        "title": topic,
        "content": content,
        "email": email,
        "thought": planner_json.get("thought", ""),
        "message": planner_json.get("message", ""),
        "agents": [
            {"role": "Planner", "summary": planner_json.get("data", {}).get("summary", "") or planner_json.get("summary", "")},
            {"role": "Reviewer", "summary": reviewer_json.get("data", {}).get("summary", "") or reviewer_json.get("summary", "")},
        ],
        "final": reviewer_json.get("data", {})
    }
    print("\n=== Publish Package ===\n")
    print(json.dumps(publish, indent=2, ensure_ascii=False))
    return finalized


def main():
    """Main function to orchestrate the multi-agent workflow"""
    parser = argparse.ArgumentParser(description="Two-agent (Planner, Reviewer) demo with JSON output.")
    parser.add_argument("--model", default="phi3:3.8b", type=str, help="Ollama model to use")
    parser.add_argument("--title", type=str, help="Topic to analyze", required=True)
    parser.add_argument("--content", type=str, help="Content to analyze for the given topic", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--email", default="shravankumar.nagarajan@sjsu.edu", type=str, help="Email of the user")
    args = parser.parse_args()

    topic = args.title
    content = args.content
    email = args.email
    print(f"Topic: {topic}")
    if content:
        print(f"Content: {content[:100]}{'...' if len(content) > 100 else ''}")

    if not wait_ollama(args.base_url):
        print("Cannot connect to Ollama. Please ensure it's running.")
        return

    print("\n--- Planner ---\n")
    planner_raw = ask_ollama(planner_prompt(topic, content), args.model, args.base_url)
    print(planner_raw)
    try:
        planner_json = json.loads(planner_raw[planner_raw.find('{'):planner_raw.rfind('}') + 1])
    except Exception:
        print("Planner did not return valid JSON.")
        return

    print("\n--- Reviewer ---\n")
    reviewer_raw = ask_ollama(reviewer_prompt(topic, planner_json, content), args.model, args.base_url)
    print(reviewer_raw)
    try:
        reviewer_json = json.loads(reviewer_raw[reviewer_raw.find('{'):reviewer_raw.rfind('}') + 1])
    except Exception:
        print("Reviewer did not return valid JSON.")
        return

    finalizer(planner_json, reviewer_json, topic, content, email)


if __name__ == "__main__":
    main()
