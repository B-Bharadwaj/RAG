"""
eval/judge.py

Judge agent — scores one RAG response across 3 dimensions using
llama-3.3-70b on Groq.

Input  : query (str), answer (str), chunk_texts (list[str])
Output : {"faithfulness": float, "relevancy": float,
          "context_recall": float, "reasoning": str}

All scores are 0.0 – 1.0.
Faithfulness   — every claim in the answer is grounded in the chunks.
Relevancy      — the answer directly addresses the question.
Context recall — the chunks contain enough info to answer the question.
"""

import json
import time
from groq import Groq
from config import GROQ_API_KEY

_client = Groq(api_key=GROQ_API_KEY)

# Use the big judge model — different from the 8b generator
JUDGE_MODEL = "llama-3.3-70b-versatile"

_JUDGE_PROMPT = """\
You are an expert RAG evaluation judge. Score the response below across 3 dimensions.

QUESTION:
{question}

RETRIEVED CHUNKS (what the RAG system retrieved):
{chunks}

GENERATED ANSWER:
{answer}

Score each dimension from 0.0 to 1.0 using these exact criteria:

FAITHFULNESS (0.0–1.0):
- 1.0 = every single claim in the answer can be directly traced to the chunks
- 0.7 = most claims are grounded, minor inference present
- 0.4 = answer mixes grounded facts with unsupported claims
- 0.0 = answer contradicts or ignores the chunks entirely

RELEVANCY (0.0–1.0):
- 1.0 = answer directly and completely addresses the question
- 0.7 = answer addresses the question but includes unnecessary tangents
- 0.4 = answer is partially on-topic but misses the core ask
- 0.0 = answer is completely off-topic

CONTEXT_RECALL (0.0–1.0):
- 1.0 = the retrieved chunks contain all information needed to answer well
- 0.7 = chunks contain most of what's needed, small gaps
- 0.4 = chunks are partially relevant but miss key information
- 0.0 = chunks are irrelevant — retrieval completely failed

Respond ONLY with a valid JSON object, no markdown, no explanation outside the JSON:
{{
  "faithfulness": <float>,
  "relevancy": <float>,
  "context_recall": <float>,
  "reasoning": "<one sentence explaining the weakest score and why>"
}}"""


def score(
    query: str,
    answer: str,
    chunk_texts: list[str],
    retries: int = 2,
) -> dict:
    """
    Call the judge LLM and return a score dict.

    Returns a safe fallback dict on failure so the caller never crashes.
    """
    chunks_block = "\n\n---\n\n".join(
        f"[Chunk {i+1}]: {c[:400]}" for i, c in enumerate(chunk_texts)
    )

    prompt = _JUDGE_PROMPT.format(
        question=query,
        chunks=chunks_block,
        answer=answer[:1200],   # cap to avoid token overflow
    )

    for attempt in range(retries):
        try:
            response = _client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.0,   # deterministic scoring
            )
            raw = response.choices[0].message.content.strip()

            # Strip accidental markdown fences
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]

            result = json.loads(raw.strip())

            return {
                "faithfulness":   round(float(result.get("faithfulness",   0.0)), 3),
                "relevancy":      round(float(result.get("relevancy",      0.0)), 3),
                "context_recall": round(float(result.get("context_recall", 0.0)), 3),
                "reasoning":      str(result.get("reasoning", "")),
            }

        except json.JSONDecodeError as e:
            print(f"[JUDGE] JSON parse error (attempt {attempt+1}): {e}")
            print(f"[JUDGE] Raw response: {raw[:300]}")
            time.sleep(3)

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 15 * (attempt + 1)
                print(f"[JUDGE] Rate limited, waiting {wait}s…")
                time.sleep(wait)
            else:
                print(f"[JUDGE] Unexpected error (attempt {attempt+1}): {e}")
                time.sleep(5)

    # Safe fallback — never crash the UI
    return {
        "faithfulness":   -1.0,
        "relevancy":      -1.0,
        "context_recall": -1.0,
        "reasoning":      "Judge failed after retries — check Groq rate limits.",
    }