"""
eval/test_generator.py

Reads your indexed chunks from the in-memory document store and uses
llama-3.1-8b on Groq to generate (question, ground_truth) pairs.

Run standalone:
    python -m eval.test_generator

Writes: eval/test_set.json
"""

import json
import time
import random
import os
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL_NAME

_client = Groq(api_key=GROQ_API_KEY)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "test_set.json")
TARGET_PAIRS = 50
CHUNKS_PER_CALL = 3   # how many chunks to send per generation call

_GEN_PROMPT = """\
You are creating evaluation questions for a RAG system over research papers.

Given these text chunks from a research paper, generate {n} question-answer pairs.

Rules:
- Questions must be answerable ONLY from the given chunks — no outside knowledge
- Ground truth answers must be specific and concise (1–3 sentences)
- Vary question types: factual, methodological, result-based
- Do NOT ask vague questions like "What is this paper about?"

CHUNKS:
{chunks}

Respond ONLY with a JSON array, no markdown:
[
  {{"question": "...", "ground_truth": "...", "source_chunk": 1}},
  ...
]"""


def _generate_pairs_from_chunks(chunks: list[dict], n: int = 2) -> list[dict]:
    chunk_block = "\n\n---\n\n".join(
        f"[Chunk {i+1} | {c.get('metadata',{}).get('pdf','?')} p.{c.get('metadata',{}).get('page','?')}]:\n{c['text'][:500]}"
        for i, c in enumerate(chunks)
    )
    prompt = _GEN_PROMPT.format(n=n, chunks=chunk_block)

    for attempt in range(3):
        try:
            response = _client.chat.completions.create(
                model=GROQ_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.4,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.lower().startswith("json"):
                    raw = raw[4:]
            pairs = json.loads(raw.strip())
            # Attach metadata so run_eval knows which PDF each Q came from
            for p in pairs:
                p["pdf"] = chunks[0].get("metadata", {}).get("pdf", "unknown")
                p["doc_id"] = chunks[0].get("metadata", {}).get("doc_id", "")
            return pairs
        except json.JSONDecodeError:
            print(f"  JSON parse failed attempt {attempt+1}, retrying…")
            time.sleep(5)
        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 20 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s…")
                time.sleep(wait)
            else:
                print(f"  Error: {e}")
                time.sleep(5)
    return []


def generate_test_set(target: int = TARGET_PAIRS) -> list[dict]:
    """
    Sample chunks from the live index and generate Q&A pairs until
    we hit the target count.
    """
    # Import here to avoid circular imports at module level
    from pipeline.indexer import get_documents

    all_docs = get_documents()
    # Only use text chunks — image captions make poor eval questions
    text_docs = [d for d in all_docs if d.get("type") == "text"]

    if not text_docs:
        print("[test_generator] No text chunks found — upload PDFs first.")
        return []

    print(f"[test_generator] {len(text_docs)} text chunks available across your PDFs.")

    # Shuffle so we sample from all PDFs evenly
    random.shuffle(text_docs)

    all_pairs: list[dict] = []
    idx = 0
    calls = 0

    while len(all_pairs) < target and idx < len(text_docs):
        batch = text_docs[idx: idx + CHUNKS_PER_CALL]
        idx += CHUNKS_PER_CALL
        n_to_gen = min(2, target - len(all_pairs))

        print(f"  Generating {n_to_gen} pairs from chunks {idx-CHUNKS_PER_CALL}–{idx}…")
        pairs = _generate_pairs_from_chunks(batch, n=n_to_gen)
        all_pairs.extend(pairs)
        calls += 1

        print(f"  Progress: {len(all_pairs)}/{target} pairs")

        # Polite delay to stay inside free-tier TPM limits
        time.sleep(4)

    all_pairs = all_pairs[:target]
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_pairs, f, indent=2, ensure_ascii=False)

    print(f"\n[test_generator] Saved {len(all_pairs)} pairs → {OUTPUT_PATH}")
    return all_pairs


if __name__ == "__main__":
    # Need the app state loaded before we can read chunks
    from pipeline.indexer import load_state
    load_state()
    generate_test_set()
