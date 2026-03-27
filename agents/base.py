"""Base agent class for all debate participants."""

from openai import OpenAI
from core.config import API_KEY, API_BASE_URL, MODEL_NAME


class BaseAgent:
    """Base class for all agents in the debate system."""

    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
        self.history: list[dict] = []

    def speak(self, user_message: str) -> str:
        """Generate a response given the current context."""
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_message})

        response = self.client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.8,
            max_tokens=500,
        )

        reply = response.choices[0].message.content.strip()

        # Save to history for context continuity
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": reply})

        return reply

    def reset(self):
        """Clear conversation history."""
        self.history.clear()
