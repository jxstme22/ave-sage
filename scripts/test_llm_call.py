"""Test LLM call directly to debug response format."""
import asyncio
import httpx
import os
import json

async def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL", "minimax/minimax-m2.7")
    
    print(f"Model: {model}")
    print(f"API key: {api_key[:20]}...")
    
    prompt = """SIGNAL RECEIVED
===============
Type: trending_entry
Token: PEPE (solana)
Base Confidence: 0.80
RAG Confidence Boost: +0.05
Final Confidence: 0.85
Direction: long
Notes: Trending #1 with low risk (0) and positive momentum

TASK: Based on this signal and historical memory, decide whether to act.
Output only valid JSON per the schema in your system prompt."""

    system = """You are AVE SAGE, an on-chain market intelligence agent.
Your response MUST be valid JSON with this exact schema:
{
  "action": "buy" | "sell" | "skip" | "watch",
  "confidence_adjustment": float between -0.2 and 0.2,
  "amount_usd_multiplier": float between 0.25 and 1.0,
  "reasoning": "concise explanation of the decision",
  "key_factors": ["factor1", "factor2"],
  "risk_flags": ["any concerns, or empty list"],
  "rag_summary": "one sentence summary"
}
Be concise. No preamble. Only valid JSON."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/ave-sage",
                "X-Title": "AVE SAGE",
            },
            json={
                "model": model,
                "max_tokens": 512,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        print(f"\nStatus: {resp.status_code}")
        data = resp.json()
        print(f"Response keys: {data.keys()}")
        if "choices" in data:
            msg = data["choices"][0]["message"]
            print(f"Content type: {type(msg.get('content'))}")
            print(f"Content: {repr(msg.get('content'))}")
            print(f"Finish reason: {data['choices'][0].get('finish_reason')}")
        elif "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(json.dumps(data, indent=2))

asyncio.run(main())
