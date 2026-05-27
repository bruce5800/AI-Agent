"""ToolAgent — bridges OpenAI function calling with MCP tool execution.

This is the core component: an agent that can autonomously call tools
(read/write files, run commands, etc.) in a loop until it produces a final answer.

Streaming model
---------------
Each LLM round is a single `stream=True` call. We accumulate two things from
the chunk stream:
  - `accumulated_content`: text deltas (yielded to the UI as they arrive)
  - `accumulated_tool_calls`: tool-call deltas merged by `index`

If the round emits any tool_calls, we execute them and loop again. Otherwise
the accumulated content is the final answer and we break out.

History
-------
`self.history` stores the **full OpenAI-format conversation** including
intermediate `assistant`-with-`tool_calls` messages and their matching `tool`
result messages. This keeps the agent coherent across multiple
`run_with_tools` invocations (e.g. the test-fix loop) — it remembers which
files it already read/wrote, instead of re-discovering on every iteration.
"""

import json
from typing import Generator

from agents.base import BaseAgent
from core.config import API_KEY, API_BASE_URL, MODEL_NAME, MAX_TOOL_ITERATIONS
from core.models import DevMessage, Phase, MessageType, ToolCall
from mcp_servers.registry import get_openai_functions_for_role, execute_tool


def _merge_tool_call_delta(slots: list[dict], tc_delta) -> None:
    """Merge a single streamed tool_call delta into `slots`, indexed by `tc_delta.index`."""
    idx = tc_delta.index
    while len(slots) <= idx:
        slots.append({
            "id": "",
            "type": "function",
            "function": {"name": "", "arguments": ""},
        })
    slot = slots[idx]
    if getattr(tc_delta, "id", None):
        slot["id"] = tc_delta.id
    if getattr(tc_delta, "type", None):
        slot["type"] = tc_delta.type
    fn = getattr(tc_delta, "function", None)
    if fn is not None:
        if getattr(fn, "name", None):
            slot["function"]["name"] += fn.name
        if getattr(fn, "arguments", None):
            slot["function"]["arguments"] += fn.arguments


class ToolAgent(BaseAgent):
    """Agent with MCP tool-calling capabilities.

    Single streaming LLM call per round; tool_calls accumulated from delta chunks.
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
        # Start from system + accumulated history + new user message.
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_message})

        final_text = ""
        finished = False

        for _ in range(MAX_TOOL_ITERATIONS):
            stream = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=self.tools or None,
                tool_choice="auto" if self.tools else None,
                temperature=0.7,
                max_tokens=4000,
                stream=True,
            )

            accumulated_content = ""
            accumulated_tool_calls: list[dict] = []

            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # Stream text deltas to UI as soon as they arrive.
                if getattr(delta, "content", None):
                    accumulated_content += delta.content
                    yield DevMessage(
                        speaker=self.name,
                        content=delta.content,
                        phase=phase,
                        msg_type=MessageType.TEXT,
                        is_chunk=True,
                    )

                # Merge tool_call deltas into their index slots.
                if getattr(delta, "tool_calls", None):
                    for tc_delta in delta.tool_calls:
                        _merge_tool_call_delta(accumulated_tool_calls, tc_delta)

            # --- Decide branch: tool calls vs. final text ---
            if accumulated_tool_calls:
                # Append the assistant message that requested the tool calls.
                # OpenAI spec allows null content alongside tool_calls.
                messages.append({
                    "role": "assistant",
                    "content": accumulated_content or None,
                    "tool_calls": accumulated_tool_calls,
                })

                for tc in accumulated_tool_calls:
                    tool_name = tc["function"]["name"]
                    raw_args = tc["function"]["arguments"] or "{}"
                    try:
                        tool_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                    yield DevMessage(
                        speaker=self.name,
                        content=f"调用工具: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})",
                        phase=phase,
                        msg_type=MessageType.TOOL_CALL,
                        metadata={"tool_name": tool_name, "tool_args": tool_args},
                    )

                    result = execute_tool(self.workspace, tool_name, tool_args)

                    tool_call_record = ToolCall(
                        tool_name=tool_name,
                        arguments=tool_args,
                        result=result[:500] if result else None,
                    )

                    yield DevMessage(
                        speaker=self.name,
                        content=result[:500] if result else "(empty result)",
                        phase=phase,
                        msg_type=MessageType.TOOL_RESULT,
                        metadata={"tool_name": tool_name, "tool_call": tool_call_record},
                    )

                    # Surface todo_write to the UI as a TODO_UPDATE event so
                    # the sidebar checklist refreshes mid-stream.
                    if tool_name == "todo_write":
                        from mcp_servers.todo_server import load_todos
                        yield DevMessage(
                            speaker=self.name,
                            content="(todos updated)",
                            phase=phase,
                            msg_type=MessageType.TODO_UPDATE,
                            metadata={"todos": load_todos(self.workspace)},
                        )

                    if tool_name == "write_file" and "path" in tool_args:
                        yield DevMessage(
                            speaker=self.name,
                            content=f"Created/updated: {tool_args['path']}",
                            phase=phase,
                            msg_type=MessageType.FILE_CHANGE,
                            metadata={"file_path": tool_args["path"]},
                        )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result or "",
                    })

                # Continue loop — LLM will process tool results in next round.
                continue

            # --- No tool calls: this is the final answer ---
            final_text = accumulated_content.strip()

            # Emit the consolidated (non-chunk) final message so engine.py
            # can capture it as `review_text` etc.
            yield DevMessage(
                speaker=self.name,
                content=final_text,
                phase=phase,
                msg_type=MessageType.TEXT,
                is_chunk=False,
            )

            messages.append({"role": "assistant", "content": final_text})
            finished = True
            break

        if not finished:
            # Hit MAX_TOOL_ITERATIONS without converging.
            yield DevMessage(
                speaker=self.name,
                content=f"(达到最大工具调用次数 {MAX_TOOL_ITERATIONS}，提前结束)",
                phase=phase,
                msg_type=MessageType.ERROR,
                is_chunk=False,
            )

        # Persist the full expanded conversation (drop the system message at [0]).
        # Next run_with_tools call will see all prior tool calls and results.
        self.history = messages[1:]

        return final_text
