"""
AVE SAGE — Telegram Bot Controller
Full remote control of the SAGE trading intelligence system.
Communicates with the dashboard API to query state and manage operations.
"""

import asyncio
import json
import logging
import os
import sys

import httpx
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
)
logger = logging.getLogger("sage.telegram")

# ─── Config ──────────────────────────────────────────────────────────────────

API_BASE = f"http://{settings.dashboard.host}:{settings.dashboard.port}"
if settings.dashboard.host == "0.0.0.0":
    API_BASE = f"http://127.0.0.1:{settings.dashboard.port}"

BOT_TOKEN = settings.telegram.bot_token
ADMIN_IDS = set(settings.telegram.admin_chat_ids)


def is_admin(update: Update) -> bool:
    """Check if the user is an admin. If no admins configured, allow everyone."""
    if not ADMIN_IDS:
        return True
    return update.effective_chat.id in ADMIN_IDS


async def api_get(path: str, params: dict = None) -> dict:
    """Helper to call the SAGE dashboard API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{API_BASE}{path}", params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        return {"error": "Dashboard not running. Start with: bash run.sh dashboard"}
    except Exception as e:
        return {"error": str(e)}


async def api_post(path: str, json_body: dict = None) -> dict:
    """Helper to POST to the SAGE dashboard API."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{API_BASE}{path}", json=json_body or {})
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        return {"error": "Dashboard not running. Start with: bash run.sh"}
    except Exception as e:
        return {"error": str(e)}


# ─── Command Handlers ────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 *AVE SAGE — Trading Intelligence Bot*\n\n"
        "Self-amplifying on-chain trading agent.\n"
        "Use /help to see all available commands.\n\n"
        "Dashboard: " + API_BASE,
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *AVE SAGE Commands*\n\n"
        "*Status & Health*\n"
        "/status — System health & stats\n"
        "/health — Full system health report\n"
        "/config — View current configuration\n\n"
        "*Memory & Knowledge*\n"
        "/memory — Memory chunk statistics\n"
        "/query <text> — Search knowledge base\n"
        "/ask <question> — Ask SAGE anything\n"
        "/memhealth — Knowledge base health\n\n"
        "*Signals & Decisions*\n"
        "/signals — Recent detected signals\n"
        "/decisions [n] — Recent trade decisions\n"
        "/performance <signal\\_type> — Signal performance\n\n"
        "*Trading*\n"
        "/positions — Open positions\n"
        "/closed — Closed positions\n"
        "/feedback — Win rate & outcomes\n\n"
        "*Control*\n"
        "/dryrun <on|off> — Toggle dry run mode\n"
        "/model <name> — Switch LLM model\n"
        "/chains — List active chains\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("\u26d4 Admin only.")
        return
    await update.message.reply_text("\U0001f50d Triggering manual market scan...")
    data = await api_post("/api/scan")
    if "error" in data:
        await update.message.reply_text(f"\u274c {data['error']}")
        return
    count = data.get("events_queued", 0)
    chains = ", ".join(data.get("chains", []))
    await update.message.reply_text(
        f"\u2705 *Scan complete*\n\n"
        f"Events queued: {count}\n"
        f"Chains: {chains}\n\n"
        f"Use /signals or /decisions to see results.",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = await api_get("/health")
    if "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    mem = data.get("memory_chunks", 0)
    ts = data.get("timestamp", 0)
    await update.message.reply_text(
        f"✅ *SAGE Status*\n\n"
        f"Status: {data.get('status', 'unknown')}\n"
        f"Memory Chunks: {mem}\n"
        f"Timestamp: {ts}",
        parse_mode="Markdown",
    )


async def cmd_health(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = await api_get("/api/memory/health")
    if "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    mem = data.get("memory", {})
    outcomes = data.get("outcomes", {})
    text = (
        "🏥 *System Health*\n\n"
        f"Total Chunks: {mem.get('total_chunks', '?')}\n"
        f"Outcomes: {outcomes.get('total_outcomes', 0)}\n"
        f"Win Rate: {_fmt_pct(outcomes.get('win_rate'))}\n"
        f"Wins: {outcomes.get('wins', 0)} | Losses: {outcomes.get('losses', 0)}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_memory(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = await api_get("/api/memory/stats")
    if "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    total = data.get("total_chunks", 0)
    types = data.get("chunk_types", {})
    lines = [f"📊 *Memory Stats*\n", f"Total Chunks: {total}\n"]
    for ct, count in types.items():
        lines.append(f"  {ct}: {count}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = " ".join(ctx.args) if ctx.args else ""
    if not query:
        await update.message.reply_text("Usage: /query <search text>")
        return
    data = await api_get("/api/memory/query", {"q": query, "n": 5})
    if isinstance(data, dict) and "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    if not data:
        await update.message.reply_text("No results found.")
        return
    lines = ["🔍 *Search Results*\n"]
    for i, r in enumerate(data[:5], 1):
        doc = r.get("document", "")[:150]
        sim = r.get("similarity", 0)
        lines.append(f"{i}. (sim={sim:.2f}) {doc}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    question = " ".join(ctx.args) if ctx.args else ""
    if not question:
        await update.message.reply_text("Usage: /ask <your question>")
        return
    data = await api_get("/api/sage/ask", {"q": question})
    if "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    context = data.get("context", "No answer")
    chunks = data.get("chunks_used", 0)
    await update.message.reply_text(
        f"🧠 *SAGE Answer*\n\n{context}\n\n_({chunks} chunks used)_",
        parse_mode="Markdown",
    )


async def cmd_signals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Get recent decisions which contain signal info
    data = await api_get("/api/decisions", {"n": 10})
    if isinstance(data, dict) and "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    if not data:
        await update.message.reply_text("No signals detected yet.")
        return
    lines = ["📡 *Recent Signals*\n"]
    for d in data[:10]:
        lines.append(
            f"• {d.get('signal', '?')} — {d.get('token', '?')}/{d.get('chain', '?')} "
            f"| conf={d.get('confidence', 0):.0%}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_decisions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    n = int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else 10
    data = await api_get("/api/decisions", {"n": n})
    if isinstance(data, dict) and "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    if not data:
        await update.message.reply_text("No decisions yet.")
        return
    lines = ["🎯 *Recent Decisions*\n"]
    for d in data[:n]:
        action = d.get("action", "?").upper()
        emoji = {"BUY": "🟢", "SELL": "🔴", "SKIP": "⏭", "WATCH": "👀"}.get(action, "❓")
        lines.append(
            f"{emoji} {action} {d.get('token', '?')} — "
            f"${d.get('amount_usd', 0):.2f} | conf={d.get('confidence', 0):.0%}\n"
            f"   _{d.get('reasoning', '')[:80]}_"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_positions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = await api_get("/api/positions/open")
    if isinstance(data, dict) and "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    if not data:
        await update.message.reply_text("No open positions.")
        return
    lines = ["📈 *Open Positions*\n"]
    for p in data:
        pnl = p.get("pnl_pct", 0)
        emoji = "🟢" if pnl >= 0 else "🔴"
        lines.append(
            f"{emoji} {p.get('action', '?').upper()} {p.get('token', '?')} ({p.get('chain', '?')})\n"
            f"   Entry: ${p.get('entry', 0):.6f} | Now: ${p.get('current', 0):.6f}\n"
            f"   PnL: {pnl:+.2f}% | ${p.get('amount_usd', 0):.2f}\n"
            f"   TP: ${p.get('tp', 0):.6f} | SL: ${p.get('sl', 0):.6f}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_closed(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = await api_get("/api/positions/closed")
    if isinstance(data, dict) and "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    if not data:
        await update.message.reply_text("No closed positions.")
        return
    lines = ["📊 *Closed Positions*\n"]
    for p in data[:10]:
        pnl = p.get("pnl_pct", 0)
        emoji = "🟢" if pnl >= 0 else "🔴"
        lines.append(
            f"{emoji} {p.get('action', '?').upper()} {p.get('token', '?')} — "
            f"PnL: {pnl:+.2f}%"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_performance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            "Usage: /performance <signal\\_type> [chain]\n"
            "Example: /performance volume\\_breakout\\_bullish solana",
            parse_mode="Markdown",
        )
        return
    signal_type = ctx.args[0]
    chain = ctx.args[1] if len(ctx.args) > 1 else None
    params = {"signal_type": signal_type}
    if chain:
        params["chain"] = chain
    data = await api_get("/api/signals/performance", params)
    if "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    wr = _fmt_pct(data.get("win_rate"))
    await update.message.reply_text(
        f"📈 *Signal Performance: {signal_type}*\n\n"
        f"Sample Size: {data.get('sample_size', 0)}\n"
        f"Win Rate: {wr}\n"
        f"Avg PnL: {_fmt_pct(data.get('avg_pnl_pct'))}",
        parse_mode="Markdown",
    )


async def cmd_feedback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = await api_get("/api/feedback/stats")
    if "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    wr = _fmt_pct(data.get("win_rate"))
    await update.message.reply_text(
        f"📊 *Outcome Feedback*\n\n"
        f"Total: {data.get('total_outcomes', 0)}\n"
        f"Wins: {data.get('wins', 0)} | Losses: {data.get('losses', 0)}\n"
        f"Win Rate: {wr}\n"
        f"Avg PnL: {_fmt_pct(data.get('avg_pnl_pct'))}",
        parse_mode="Markdown",
    )


async def cmd_config(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Admin only.")
        return
    await update.message.reply_text(
        f"⚙️ *Configuration*\n\n"
        f"LLM: `{settings.agent.llm_provider}`\n"
        f"Model: `{settings.agent.reasoning_model}`\n"
        f"Dry Run: `{settings.agent.dry_run}`\n"
        f"Max Position: `${settings.agent.max_position_usd}`\n"
        f"TP: `{settings.agent.take_profit_pct*100:.0f}%` | "
        f"SL: `{settings.agent.stop_loss_pct*100:.0f}%`\n"
        f"Min Confidence: `{settings.agent.trade_confidence_min}`\n"
        f"Chains: `{', '.join(settings.ave.chains)}`\n"
        f"API Plan: `{settings.ave.api_plan}`",
        parse_mode="Markdown",
    )


async def cmd_dryrun(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Admin only.")
        return
    if not ctx.args:
        state = "ON ✅" if settings.agent.dry_run else "OFF ⚠️ (LIVE)"
        await update.message.reply_text(f"Dry run is currently: {state}")
        return
    val = ctx.args[0].lower()
    if val in ("on", "true", "1"):
        settings.agent.dry_run = True
        await update.message.reply_text("✅ Dry run enabled — trades are simulated.")
    elif val in ("off", "false", "0"):
        settings.agent.dry_run = False
        await update.message.reply_text("⚠️ Dry run disabled — LIVE TRADING ACTIVE!")
    else:
        await update.message.reply_text("Usage: /dryrun on|off")


async def cmd_model(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Admin only.")
        return
    if not ctx.args:
        await update.message.reply_text(
            f"Current model: `{settings.agent.reasoning_model}`\n\n"
            "Usage: /model <openrouter\\_model\\_name>\n"
            "Example: /model anthropic/claude-sonnet-4-20250514",
            parse_mode="Markdown",
        )
        return
    new_model = ctx.args[0]
    settings.agent.reasoning_model = new_model
    await update.message.reply_text(f"✅ Model switched to: `{new_model}`", parse_mode="Markdown")


async def cmd_chains(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chains = settings.ave.chains
    await update.message.reply_text(
        f"⛓ *Active Chains*\n\n" + "\n".join(f"• {c}" for c in chains),
        parse_mode="Markdown",
    )


async def cmd_memhealth(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = await api_get("/api/memory/health")
    if "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    await update.message.reply_text(
        f"🧠 *Memory Health*\n\n```\n{json.dumps(data, indent=2)[:1500]}\n```",
        parse_mode="Markdown",
    )


# ── Rules & Self-Improvement ─────────────────────────────────────────────────

async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = await api_get("/api/rules/status")
    if "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    halted = "🛑 HALTED" if data.get("halted") else "✅ Active"
    await update.message.reply_text(
        f"🛡️ *Trading Rules*\n\n"
        f"Status: {halted}\n"
        f"Daily P&L: ${data.get('daily_pnl_usd', 0):.2f}\n"
        f"Drawdown: {data.get('drawdown_pct', 0):.1f}%\n"
        f"Open positions: {data.get('open_positions', 0)}\n"
        f"Cooldown: {data.get('cooldown_remaining_s', 0)}s",
        parse_mode="Markdown",
    )


async def cmd_ledger(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = await api_get("/api/strategy/ledger")
    if isinstance(data, dict) and "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    if not data:
        await update.message.reply_text("📊 No strategy records yet.")
        return
    lines = ["📊 *Strategy Ledger*\n"]
    for r in data[:10]:
        wr = f"{r['win_rate']*100:.0f}%" if r.get("win_rate") is not None else "N/A"
        lines.append(
            f"• `{r['signal_type']}` ({r['chain']}): "
            f"{r['total_trades']} trades, WR={wr}, "
            f"PnL={r['total_pnl_pct']:+.1f}%, "
            f"size×{r['tuned_size_multiplier']:.1f}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_tune(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Admin only.")
        return
    data = await api_get("/api/strategy/tune")
    if isinstance(data, dict) and "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        return
    tuned = [r for r in data if r.get("source") == "tuned"]
    if not tuned:
        await update.message.reply_text("🔧 No strategies tuned yet (need ≥5 trades per type).")
        return
    lines = ["🔧 *Self-Tuned Parameters*\n"]
    for r in tuned:
        lines.append(
            f"• `{r['signal_type']}` ({r['chain']}): "
            f"TP={r['tp_pct']*100:.1f}% SL={r['sl_pct']*100:.1f}% "
            f"conf≥{r['confidence_min']:.2f} size×{r['size_multiplier']:.1f} "
            f"(WR={r['win_rate']*100:.0f}%, n={r['sample_count']})"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ─── Utilities ───────────────────────────────────────────────────────────────

def _fmt_pct(val) -> str:
    if val is None:
        return "N/A"
    return f"{val*100:.1f}%"


# ─── Bot Setup ───────────────────────────────────────────────────────────────

async def post_init(app: Application):
    """Register commands with Telegram for the menu."""
    commands = [
        BotCommand("start", "Welcome message"),
        BotCommand("help", "Show all commands"),
        BotCommand("status", "System health & stats"),
        BotCommand("health", "Full health report"),
        BotCommand("memory", "Memory statistics"),
        BotCommand("query", "Search knowledge base"),
        BotCommand("ask", "Ask SAGE anything"),
        BotCommand("signals", "Recent signals"),
        BotCommand("decisions", "Recent decisions"),
        BotCommand("positions", "Open positions"),
        BotCommand("closed", "Closed positions"),
        BotCommand("performance", "Signal performance"),
        BotCommand("feedback", "Win rate & outcomes"),
        BotCommand("config", "View configuration"),
        BotCommand("dryrun", "Toggle dry run"),
        BotCommand("model", "Switch LLM model"),
        BotCommand("chains", "Active chains"),
        BotCommand("memhealth", "Memory health"),
        BotCommand("rules", "Trading rules status"),
        BotCommand("ledger", "Strategy performance ledger"),
        BotCommand("tune", "Self-tune parameters"),
        BotCommand("scan", "Trigger manual market scan"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("[TELEGRAM] Bot commands registered")


def main():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Add it to .env")
        sys.exit(1)

    logger.info("[TELEGRAM] Starting AVE SAGE bot...")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("query", cmd_query))
    app.add_handler(CommandHandler("ask", cmd_ask))
    app.add_handler(CommandHandler("signals", cmd_signals))
    app.add_handler(CommandHandler("decisions", cmd_decisions))
    app.add_handler(CommandHandler("positions", cmd_positions))
    app.add_handler(CommandHandler("closed", cmd_closed))
    app.add_handler(CommandHandler("performance", cmd_performance))
    app.add_handler(CommandHandler("feedback", cmd_feedback))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(CommandHandler("dryrun", cmd_dryrun))
    app.add_handler(CommandHandler("model", cmd_model))
    app.add_handler(CommandHandler("chains", cmd_chains))
    app.add_handler(CommandHandler("memhealth", cmd_memhealth))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CommandHandler("ledger", cmd_ledger))
    app.add_handler(CommandHandler("tune", cmd_tune))
    app.add_handler(CommandHandler("scan", cmd_scan))

    logger.info("[TELEGRAM] Polling for updates...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
