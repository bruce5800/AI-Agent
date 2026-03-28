"""ToolAgent — bridges OpenAI function calling with MCP tool execution.

This is the core component: an agent that can autonomously call tools
(read/write files, run commands, etc.) in a loop until it produces a final answer.
"""

import json
from typing import Generator

from agents.base import BaseAgent
from core.config import API_KEY, API_BASE_URL, MODEL_NAME, MAX_TOOL_ITERATIONS
from core.models import DevMessage, Phase, MessageType, ToolCall
from mcp_servers.registry import get_openai_functions_for_role, execute_tool


class ToolAgent(BaseAgent):
    """Agent with MCP tool-calling capabilities.

    Extends BaseAgent with a tool-calling loop:
    1. Call LLM with available tools
    2. If LLM requests tool calls → execute them → feed results back → repeat
    3. If LLM produces final text → stream it out
    """

    def __init__(self, name: str, role: str, system_prompt: str, workspace: str):
        super().__init__(name=name, system_prompt=system_prompt)
        self.role = role
        self.workspace = workspace
        self.tools = get_openai_functions_for_role(role)

    def run_with_tools(
        self,
        user_message: str,
        phase: Phase,
    ) -> Generator[DevMessage, None, str]:
        """Execute an agentic tool-calling loop.

        Yields DevMessage for each event (tool calls, tool results, streaming text).
        Returns the final complete text response.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_message})

        full_reply = ""

        for iteration in range(MAX_TOOL_ITERATIONS):
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=self.tools if self.tools else None,
                tool_choice="auto" if self.tools else None,
                temperature=0.7,
                max_tokens=4000,
            )

            choice = response.choices[0]

            # --- Handle tool calls ---
            if choice.message.tool_calls:
                # Append assistant message with tool calls
                messages.append(choice.message.model_dump())

                for tc in choice.message.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        tool_args = {}

                    # Yield tool call event
                    yield DevMessage(
                        speaker=self.name,
                        content=f"调用工具: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})",
                        phase=phase,
                        msg_type=MessageType.TOOL_CALL,
                        metadata={"tool_name": tool_name, "tool_args": tool_args},
                    )

                    # Execute the tool
                    result = execute_tool(self.workspace, tool_name, tool_args)

                    # Track tool call
                    tool_call_record = ToolCall(
                        tool_name=tool_name,
                        arguments=tool_args,
                        result=result[:500] if result else None,
                    )

                    # Yield tool result event
                    yield DevMessage(
                        speaker=self.name,
                        content=result[:500] if result else "(empty result)",
                        phase=phase,
                        msg_type=MessageType.TOOL_RESULT,
                        metadata={"tool_name": tool_name, "tool_call": tool_call_record},
                    )

                    # If it was a write_file, also yield a file change event
                    if tool_name == "write_file" and "path" in tool_args:
                        yield DevMessage(
                            speaker=self.name,
                            content=f"Created/updated: {tool_args['path']}",
                            phase=phase,
                            msg_type=MessageType.FILE_CHANGE,
                            metadata={"file_path": tool_args["path"]},
                        )

                    # Append tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result or "",
                    })

                # Continue loop — LLM will process tool results
                continue

            # --- Final text response (no more tool calls) ---
            final_text = choice.message.content or ""
            full_reply = final_text.strip()

            # Stream the final text token by token
            # (Re-call with stream=True for the same messages to get streaming)
            if full_reply:
                stream = self.client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=4000,
                    stream=True,
                )
                streamed_text = ""
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        streamed_text += delta
                        yield DevMessage(
                            speaker=self.name,
                            content=delta,
                            phase=phase,
                            msg_type=MessageType.TEXT,
                            is_chunk=True,
                        )
                full_reply = streamed_text.strip() or full_reply

            # Yield complete message
            yield DevMessage(
                speaker=self.name,
                content=full_reply,
                phase=phase,
                msg_type=MessageType.TEXT,
                is_chunk=False,
            )
            break

        # Save to history
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": full_reply})

        return full_reply
