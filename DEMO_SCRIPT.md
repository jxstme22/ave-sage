# AVE SAGE — Hackathon Demo Script
### Self-Amplifying Generative Engine | AVE Cloud Skill Suite

> **Video target**: 5–8 minutes. Human, conversational tone. Walk through the idea, show the interface, and prove it's real with an on-chain trade.

---

## Opening (0:00–0:45) — The Problem

*[Show a standard trading bot UI — static rules, price only]*

"Every trading bot you've ever seen works the same way. It looks at the current price. It applies a rule — 'if RSI is over 70, sell.' That's it. No memory. No learning. It makes the same mistake on Tuesday that it made on Monday, because it has absolutely no idea Monday ever happened."

"AVE SAGE is built on a fundamentally different idea: **what if your trading agent could remember?**"

"Not just last hour — but every significant event it has ever seen. Every pump and dump. Every whale accumulation. Every time a token spiked 40% on volume, and what happened next. All of it, stored in a searchable knowledge base, instantly available the moment a new signal arrives."

---

## Core Idea (0:45–2:00) — The Intelligence Loop

*[Show the OBSERVE → REMEMBER → REASON → ACT → LEARN diagram]*

"SAGE runs a five-step loop, and every step makes the next one smarter."

**OBSERVE** — "It watches Solana markets in real-time through the AVE Cloud API. Live price feeds, WebSocket event streams, large swap transactions, trending token appearances, whale wallet movements. Raw market data, continuously."

**REMEMBER** — "Every significant event — anything above our configurable significance threshold — gets processed through a chunker and written into a vector database. ChromaDB stores it as a memory chunk with metadata: chain, timestamp, type, token, significance score. Over time, this builds into thousands of market memories."

*[Show Reasoning Engine page — '1,061 memory chunks' stat card]*

"Right now, this system has over a thousand chunks of market intelligence. That's every notable market event it has seen since it started running."

**REASON** — "When a new signal fires — say, a volume breakout on a Solana meme coin — SAGE doesn't just react to the signal. It first queries the knowledge base: 'show me the 8 most similar volume breakouts from recent history.' It gets back context: what happened to those tokens, whether they recovered or dumped, what the confidence levels were. That context feeds into the LLM prompt alongside the live signal."

**ACT** — "The LLM — we're using Claude Sonnet through OpenRouter — reasons through all of that, issues a structured JSON decision: action, confidence score, take profit, stop loss, amount. If confidence is above 65%, the trade executes live on-chain via the AVE proxy wallet."

**LEARN** — "After a position closes — either by hitting TP, SL, or timing out — that outcome gets written back into the vector store as an outcome chunk. The pattern that led to that decision is permanently linked to its result. The next time a similar pattern appears, SAGE will recall not just the pattern, but what happened when it acted on it before. That's the feedback loop."

---

## Web UI Walkthrough (2:00–4:30)

*[Open browser to http://localhost:3001]*

### Command Center

*[Show the main dashboard]*

"The Command Center gives you everything at a glance. Top row: total memory chunks, active chain, open positions, daily P&L. The live signal feed on the right updates in real-time via WebSocket — every signal that fires, every decision made, every trade opened or closed. Nothing is hidden."

*[Point to strategy ledger / win rate]*

"The strategy ledger tracks performance by signal type. You can see which patterns are working and which aren't — 'volume breakout bullish' win rate, 'whale accumulation' win rate — all tracked separately so SAGE can tune its own confidence thresholds over time."

### Reasoning Engine

*[Navigate to /reasoning]*

"This is the Reasoning Engine page — the brain inspector. You can see every memory chunk SAGE has stored. Twenty most recent to start.

The semantic search lets you query the knowledge base the same way SAGE does internally. I'll type 'high volatility Solana breakout'..."

*[Type search query, show results with relevance scores]*

"...and you get back the most relevant historical events, ranked by cosine similarity. Each chunk shows its type, the chain, a significance score, and a preview of the raw text. Click any row to see the full JSON metadata in the inspector panel — token address, timestamp, price levels, everything."

### SAGE Chat

*[Navigate to /sage or open Sage Chat page]*

"SAGE Chat connects you directly to the reasoning engine through a conversational interface. This isn't a generic chatbot — it has full RAG access to the entire knowledge base."

*[Type: "What's the current market sentiment on Solana meme coins?"]*

"Watch this — it queries ChromaDB for relevant context, builds a prompt with that context, and gives you an answer grounded in actual market data it has observed. Not hallucinated. It's responding from memory."

*[Show tables/markdown rendering]*

"It renders proper markdown — tables, code, bold text — and your conversation history persists across page refreshes. You can come back tomorrow and pick up right where you left off."

### Trade History / Positions

*[Navigate to positions/wallet]*

"Open positions show you: entry price, current price, real-time P&L percentage, take profit and stop loss levels. Every position is real — opened on-chain via the AVE Cloud proxy wallet, verifiable on Solscan."

---

## Browser Extension (4:30–5:30)

*[Click the AVE SAGE extension in Brave/Chrome toolbar]*

"The browser extension is a full companion interface that runs anywhere you have your browser open — while you're watching charts, browsing Twitter, or checking news. No need to keep the web UI open."

*[Show Wallet tab]*

"The Wallet tab shows your proxy wallet balance and open positions with P&L. This refreshes every 30 seconds automatically."

*[Switch to Signals tab]*

"Signals shows recent signal history — you can see every signal that fired, whether it was a BUY or SELL, the confidence score, and whether a trade was executed."

*[Switch to SAGE tab]*

"And from the extension itself, you can chat directly with SAGE. Same RAG-powered intelligence, right in your popup. Ask it anything about the market, a specific token, or your current positions — and it responds from memory."

---

## Real On-Chain Trade (5:30–6:45)

*[This is the critical moment — show it live or show the confirmed Solscan link]*

"Now I want to show you this is not simulation. This is live money on a real wallet, executing real transactions on Solana mainnet."

*[Show the wallet address: CiGMYJE5v7su1ZYE2SGKKrD7bqzp2dasWc94T8eLnKFr]*

"Our proxy wallet address is `CiGMYJE5v7su1ZYE2SGKKrD7bqzp2dasWc94T8eLnKFr`. You can look it up right now on Solscan."

*[Open Solscan in browser, search the address — show 3 confirmed transactions]*

"Three real trades executed by SAGE:"

"First — BONK. 0.002 SOL in, 2.77 billion BONK out. Confirmed."

**Tx 1 (BONK):** `2Gq32gVLsp1ZG1SCgjLoo3zWwCUJ52JQoThjc3ALvr2uYRg2UKsL4duKuB7hxkvY4Td6bGfeeVZA6FpuAPBtymar`

"Second — also BONK. 0.003 SOL in, 4.16 billion BONK out."

**Tx 2 (BONK):** `4PvWjqkCRjBeg7Tb2qLgwSbmtaS7syeJr1RqBdy174KHnHaYPmV2ALsC3KHWJAzPYoFGAymh3mgXVRUB7SC7Qc18`

"Third — WIF. 0.003 SOL, 1.27 million WIF tokens."

**Tx 3 (WIF):** `2gC7TPKtHsWfibaynfYXQt7TmehPHvwdgFfRw26b9XfwtFcxfsCzXFQpiwfp9EmuW28UPLnmj25NczQjRXor1iDz`

"The wallet started at 0.05 SOL. After three trades, it's at 0.0409 SOL. That's real money leaving a real wallet on Solana mainnet. Every single deduction is verifiable on Solscan right now."

"This is exactly what happens when SAGE fires a high-confidence signal with `dry_run: false`. It converts the USD trade size to lamports, constructs the swap payload with MEV protection enabled, submits to the AVE proxy wallet API, polls for confirmation, and records the position with the on-chain tx hash."

---

## Telegram Bot (6:45–7:15) *(optional section)*

*[Open Telegram, show bot chat]*

"For traders who want mobile control, there's a full Telegram bot interface. You can check wallet status with `/balance`, see open positions with `/positions`, review recent signals with `/signals`, and even trigger manual trades. All secured to your admin chat ID — nobody else can send commands."

---

## Closing (7:15–end)

*[Return to Command Center, show live feed updating]*

"AVE SAGE is the first trading agent I know of that genuinely gets smarter the longer it runs — not through weight updates or retraining — just through accumulated market memory and a RAG reasoning loop that uses that memory every single time it makes a decision."

"Everything here is open, verifiable, and real. The code runs on your machine. The trades hit Solana mainnet. The memory grows with every event. The feedback loop closes after every position."

"Built entirely on AVE Cloud Skills — the data API, the WebSocket stream, the proxy wallet execution. No other infrastructure required."

---

## Demo Checklist

Before hitting record:
- [ ] `bash run.sh all` — start backend + web UI
- [ ] Navigate to `http://localhost:3001` — Command Center loads
- [ ] Check `/reasoning` — memory chunks showing (should be 1000+)
- [ ] Load SAGE Chat — send one test message, verify markdown renders
- [ ] Open extension in Brave, check Wallet tab shows balance
- [ ] Open Solscan for wallet `CiGMYJE5v7su1ZYE2SGKKrD7bqzp2dasWc94T8eLnKFr`
- [ ] Open Solscan for tx `2Gq32gVLsp1ZG1SCgjLoo3zWwCUJ52JQoThjc3ALvr2uYRg2UKsL4duKuB7hxkvY4Td6bGfeeVZA6FpuAPBtymar`
- [ ] Backend terminal visible (shows live SAGE loop events in logs)
- [ ] Slow everything down — don't rush, let the UI breathe

---

## Key Stats to Quote

| Metric | Value |
|---|---|
| Memory chunks | 1,000+ (grows over time) |
| Embedding model | all-MiniLM-L6-v2 (32ms latency) |
| Chains monitored | Solana |
| Trade confidence threshold | 65% (configurable) |
| TP / SL | 8% / 4% (configurable) |
| Tx 1 — BONK buy | 0.002 SOL → 2.77B BONK tokens [confirmed] |
| Tx 2 — BONK buy | 0.003 SOL → 4.16B BONK tokens [confirmed] |
| Tx 3 — WIF buy | 0.003 SOL → 1.27M WIF tokens [confirmed] |
| Wallet start | 0.050000 SOL |
| Wallet now | 0.040951 SOL (3 deductions verified on Solscan) |
| Proxy wallet | `CiGMYJE5v7su1ZYE2SGKKrD7bqzp2dasWc94T8eLnKFr` |
| Test suite | 64/64 passing |

---

## What Makes This Different (for Q&A)

**"Why ChromaDB and not [other vector DB]?"**
ChromaDB runs locally, no cloud dependency, and persists to disk. The entire knowledge base survives restarts and can be inspected directly. Simple to run anywhere.

**"How does the RAG context affect decisions?"**
The RAG query runs before every LLM call. It retrieves the 8 most similar historical chunks to the current signal. These are injected into the system prompt as context. The LLM explicitly factors this history into its confidence score and reasoning chain.

**"Is this profitable?"**
The system is designed to get more accurate over time. With more memory and better outcome coverage, the signal quality improves. Early-stage performance depends heavily on market conditions and the quality of signals the AVE data stream provides. The infrastructure is complete — the learning loop is real.

**"What's the AVE proxy wallet?"**
AVE Cloud's proxy wallet service manages keypairs server-side and executes trades on your behalf via a delegated signing model. You control it via HMAC-signed API calls from your own infrastructure. No browser wallet extensions needed.

**"Can it be extended to other chains?"**
Yes. The `chains` config key accepts `[solana, bsc, eth, base]`. All other components — chunker, embedder, signal detector, trade agent — are chain-agnostic. Expanding to BSC is literally changing one config line.
