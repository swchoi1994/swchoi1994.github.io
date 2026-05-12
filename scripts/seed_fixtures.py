"""Seed fixtures used only when --seed-fixture is passed.

This lets us deploy a working blog before secrets are configured. The content
is hand-written placeholder material with current generic IT framing - it will
be replaced by real generated posts starting from the next scheduled run.
"""

from __future__ import annotations

FIXTURES = {
    ("en", "us"): {
        "title": "What 'agentic AI' actually means in 2026 (and what it doesn't)",
        "description": "A short, no-hype breakdown of where the US AI labs landed on agents, and what is real vs. demo-ware right now.",
        "category": "AI/ML",
        "body_markdown": (
            "Every press release out of San Francisco this year has the word \"agent\" in it. "
            "I want to give you a quick, engineer's-eye summary of what the term actually buys you in production today, "
            "and where it's still mostly a demo.\n\n"
            "## What changed in the last 12 months\n\n"
            "Two things, mostly. First, **tool use got reliable enough** for a model to chain three or four calls without you "
            "wrapping it in retry-and-pray glue. Second, **context windows crossed the 'whole-repo' line** for the major labs, "
            "which means the agent can keep a non-trivial mental model of your codebase without RAG gymnastics [1].\n\n"
            "That's it. Those two changes are doing most of the work in the demos you've seen.\n\n"
            "## What's still flaky\n\n"
            "Long-horizon planning - anything past a 20-step trajectory - still drifts. The mitigation everyone is converging on "
            "is the same: shorter loops with explicit checkpoints, plus a separate evaluator model that grades each step [2]. "
            "If you're shipping an agent into production this quarter and you're not doing both, you're going to find out the hard way.\n\n"
            "## The honest take\n\n"
            "I run a few agentic pipelines at work. The ones that survive contact with real users are boring: narrow scope, "
            "explicit success criteria, a hard step limit, and a fallback to a human or a deterministic tool. "
            "The wild open-ended demos are still mostly cherry-picked. That's fine - the tech is good enough to be useful in narrow "
            "lanes, and that's where the money is for now.\n\n"
            "If you remember one thing from this post: **scope, evaluate, fall back.**"
        ),
    },
    ("en", "china"): {
        "title": "Why China's open-weight push is reshaping the LLM cost curve",
        "description": "Open-weight Chinese frontier models are putting price pressure on the entire stack. Here's how to think about it.",
        "category": "AI/ML",
        "body_markdown": (
            "If you've been pricing out LLM workloads recently, you've noticed something: serving costs are falling faster than "
            "anyone forecast a year ago. A lot of that pressure is coming from China's open-weight releases.\n\n"
            "## The pattern\n\n"
            "Labs like DeepSeek, Qwen, and ZhipuAI have been shipping frontier-tier checkpoints under permissive licenses, "
            "often within weeks of the closed equivalents [1]. The result: anyone with H100s (or H800s, depending on which side "
            "of the export controls you're on) can host a near-GPT-4-class model.\n\n"
            "## Why it matters for engineers outside China\n\n"
            "Two reasons. **One:** your closed-API bill has a real, public benchmark now. When a hyperscaler quotes you a "
            "per-token rate, you can compare it to the cost of self-hosting an open checkpoint with similar quality. That "
            "negotiation didn't exist 18 months ago.\n\n"
            "**Two:** the open-weight models are getting trained with techniques that the closed labs are still keeping quiet. "
            "MoE routing, long-context attention tricks, and reasoning-trained variants are all visible in the open weights [2]. "
            "If you care about how these systems work, the open releases are where you actually get to read the code.\n\n"
            "## The catch\n\n"
            "Inference at scale is still hard. The model weight is the easy part; getting predictable latency on a busy node is "
            "the rest of the iceberg. Most teams I talk to end up running open models for batch and offline workloads and keeping "
            "a closed API for low-latency user-facing calls. That's a reasonable place to be in 2026.\n\n"
            "Long term, I expect the lines to keep blurring. The interesting question isn't whether open or closed wins - it's "
            "how fast the marginal cost of a token falls, and what new product shapes that unlocks."
        ),
    },
    ("ko", "korea"): {
        "title": "삼성과 SK하이닉스의 HBM 경쟁, 엔지니어 입장에서 본 짧은 정리",
        "description": "HBM(High Bandwidth Memory) 경쟁이 왜 AI 인프라에 직접 영향을 주는지, 그리고 한국 메모리 업계의 현재 위치를 짧게 정리했습니다.",
        "category": "Semiconductors",
        "body_markdown": (
            "오늘은 한국 반도체 업계의 핵심 이슈인 HBM(High Bandwidth Memory, 고대역폭 메모리) 이야기를 짧게 정리해보겠습니다. "
            "AI 인프라 비용의 상당 부분이 결국 메모리에서 나오기 때문에, 엔지니어 입장에서도 한 번쯤 짚어둘 만한 주제입니다.\n\n"
            "## 무슨 일이 있었나\n\n"
            "엔비디아의 차세대 AI 가속기에 들어가는 HBM은 사실상 **삼성전자와 SK하이닉스, 그리고 마이크론** 세 회사가 나눠 가지는 시장입니다 [1]. "
            "최근 흐름은 SK하이닉스가 HBM3E에서 한발 앞서나간 상황이고, 삼성은 다음 세대에서 다시 격차를 좁히겠다는 전략을 공식화했습니다 [2].\n\n"
            "## 왜 중요한가\n\n"
            "LLM(대규모 언어 모델) 추론 비용의 병목은 대부분 메모리 대역폭입니다. GPU 코어가 아무리 빨라도, 가중치를 가져오는 속도가 느리면 "
            "성능이 떨어지죠. 그래서 HBM 한 세대가 바뀔 때마다 토큰당 비용이 실질적으로 내려갑니다. "
            "결국 한국 메모리 업계의 경쟁력이 곧 글로벌 AI 서비스의 단가에 직접 영향을 미친다는 얘기입니다.\n\n"
            "## 조금 더 깊은 맥락\n\n"
            "한 가지 흥미로운 점은, HBM은 단순히 D램을 쌓는 기술이 아니라 **TSV(Through-Silicon Via) 패키징**과 "
            "**열 관리** 등 후공정 기술이 핵심이라는 것입니다. 그래서 양산 수율이 곧 경쟁력입니다. "
            "이 부분에서 한국 두 회사가 미국·중국 경쟁사들과 격차를 유지하고 있는 건 사실이지만, "
            "장기적으로 중국 메모리 업체들이 후공정 쪽 투자에 집중하고 있다는 점은 지켜봐야 할 부분입니다.\n\n"
            "## 마무리하며\n\n"
            "개인적으로는, AI 모델 자체의 발전 속도에 비해 메모리 쪽 이야기가 한국 IT 매체에서 너무 가볍게 다뤄지는 것 같습니다. "
            "실제로는 모델 한 세대만큼이나 큰 변화가 메모리 쪽에서 일어나고 있고, 한국이 그 변화의 한가운데에 있습니다. "
            "엔지니어 입장에서 한 번쯤 깊게 들여다볼 만한 주제라고 생각합니다."
        ),
    },
}

# Source list for citations - generic but reasonable placeholders. Replace
# with real Tavily results once the cron runs.
SEED_SOURCES = {
    ("en", "us"): [
        {"title": "Anthropic - Building with Claude agents", "url": "https://www.anthropic.com/news/agents"},
        {"title": "OpenAI - Function calling and tool use", "url": "https://platform.openai.com/docs/guides/function-calling"},
    ],
    ("en", "china"): [
        {"title": "DeepSeek - Model releases", "url": "https://www.deepseek.com/"},
        {"title": "Alibaba Qwen - Open models", "url": "https://qwenlm.github.io/"},
    ],
    ("ko", "korea"): [
        {"title": "SK hynix - HBM 사업 소개", "url": "https://www.skhynix.com/products/dram/hbm/"},
        {"title": "Samsung Semiconductor - HBM", "url": "https://semiconductor.samsung.com/dram/hbm/"},
    ],
}


def build_seed_post(lang: str, region: str, voice: dict) -> dict:
    key = (lang, region)
    if key not in FIXTURES:
        return None
    fx = FIXTURES[key]
    return {
        "title": fx["title"],
        "description": fx["description"],
        "category": fx["category"],
        "body_markdown": fx["body_markdown"],
        "sources": SEED_SOURCES.get(key, []),
        "lang": lang,
        "region": region,
    }
