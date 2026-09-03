# Firebreak product demo voiceover synthesis (edge-tts)
import asyncio, json, os
import edge_tts

VOICE = "zh-CN-YunxiNeural"   # male voice · narration feel
OUT = os.path.join(os.path.dirname(__file__), "audio")
os.makedirs(OUT, exist_ok=True)

SCENES = [
    {"id": "01", "text": "The backtest looks great, yet it refuses to place the order. Is there a more counter-intuitive stock-trading system than this?"},
    {"id": "02", "text": "Almost everyone is building an investment system, but ... what we're missing is often not a better signal, but something to stop an overly pretty backtest chart."},
    {"id": "03", "text": "Firebreak, a deterministic firewall between research and trading. AI handles the planning; only code holds the final veto."},
    {"id": "04", "text": "Open Firebreak in the workspace. Submit a research task in natural language; the LLM only plans the tool calls, six real actions execute step by step, and a deterministic risk gate delivers the final verdict."},
    {"id": "05", "text": "First, look at the synthetic data. The annualized backtest looks impressive, but among the four hard gates, both data source and production readiness are blocked — verdict BLOCKED, and no order intent is ever created."},
    {"id": "06", "text": "Now switch to real, production-ready data. All four gates are green, verdict ELIGIBLE — but it still waits for your final approval; the system never places an order automatically."},
    {"id": "07", "text": "Why can't you fool it? The model has only PLAN_ONLY permission and cannot rewrite the gates; every decision is written to an immutable chained-hash log; and forty-two property-based tests protect the full set of invariants."},
    {"id": "08", "text": "For reviewers and agents: open webmcp and llms.txt — the Agent does not click any interface, it invokes real actions directly. Firebreak: a backtest can be pretty, but trading only trusts evidence."},
]

async def synth(scene):
    mp3 = os.path.join(OUT, f"scene{scene['id']}.mp3")
    com = edge_tts.Communicate(scene["text"], VOICE)
    await com.save(mp3)
    return scene["id"], mp3

async def main():
    results = []
    for s in SCENES:
        sid, mp3 = await synth(s)
        results.append({"id": sid, "mp3": mp3})
        print("saved", mp3)
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"voice": VOICE, "scenes": [{"id": r["id"], "file": r["mp3"]} for r in results]}, f, ensure_ascii=False, indent=2)

asyncio.run(main())
print("DONE")