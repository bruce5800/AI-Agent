"""Base agent class for all development agents."""

from typing import Generator

from openai import OpenAI
from core.config import API_KEY, API_BASE_URL, MODEL_NAME


class BaseAgent:
    """Base class for all agents. Provides LLM interaction with streaming."""

    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
        self.history: list[dict] = []

    def _build_messages(self, user_message: str) -> list[dict]:
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def speak(self, user_message: str) -> str:
        """Generate a complete response."""
        messages = self._build_messages(user_message)
        response = self.client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=4000,
        )
        reply = response.choices[0].message.content.strip()
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def speak_stream(self, user_message: str) -> Generator[str, None, str]:
        """Generate a streaming response, yielding each token chunk."""
        messages = self._build_messages(user_message)
        stream = self.client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=4000,
            stream=True,
        )
        full_reply = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_reply += delta
                yield delta
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": full_reply})
        return full_reply

    def reset(self):
        self.history.clear()
