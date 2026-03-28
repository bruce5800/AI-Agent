"""Configuration for the multi-agent debate system."""

import os
from dotenv import load_dotenv

load_dotenv()

# DeepSeek API config (OpenAI-compatible)
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

# Debate config
MAX_WORDS_PER_TURN = 200
DEBATE_ROUNDS = 3  # Number of back-and-forth rounds
FREE_DEBATE_EXCHANGES = 6  # Number of exchanges in free debate

# Default debater profiles
PRO_DEBATERS = [
    {
        "name": "正方一辩",
        "role": "正方一辩（开篇立论）",
        "personality": "逻辑严密，善于用数据和事实构建论证框架",
        "style": "沉稳有力，条理清晰",
    },
    {
        "name": "正方二辩",
        "role": "正方二辩（攻辩质询）",
        "personality": "思维敏捷，擅长抓住对方逻辑漏洞进行追问",
        "style": "犀利直接，步步紧逼",
    },
    {
        "name": "正方三辩",
        "role": "正方三辩（总结陈词）",
        "personality": "视野开阔，善于从宏观角度升华论点",
        "style": "感性与理性结合，收束有力",
    },
]

CON_DEBATERS = [
    {
        "name": "反方一辩",
        "role": "反方一辩（开篇立论）",
        "personality": "善于另辟蹊径，从对方忽视的角度切入",
        "style": "从容不迫，论证扎实",
    },
    {
        "name": "反方二辩",
        "role": "反方二辩（攻辩质询）",
        "personality": "观察力强，善于发现对方论证中的矛盾",
        "style": "尖锐但不失风度，善用反问",
    },
    {
        "name": "反方三辩",
        "role": "反方三辩（总结陈词）",
        "personality": "表达力强，善于用生动的案例打动人心",
        "style": "慷慨激昂，富有感染力",
    },
]
