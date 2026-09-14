"""
base_agent.py — Base sub-agent class for Arya multi-agent architecture.
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from agent_tools.registry import format_system_tools_prompt, get_tool_schemas_for_agent
from llm_agent import GF_MODE_PROMPT, ASSISTANT_MODE_PROMPT, _SHARED_RULES, generate_streaming_response, LOOP_MODEL
from agent_loop import run_agentic_loop, AgentLoopResult

logger = logging.getLogger("arya.agents.base")


class BaseSubAgent:
    name: str = "base"
    description: str = "Base sub-agent"
    tool_names: List[str] = []
    system_prompt_addon: str = ""

    def get_system_prompt(self, language: str = "hi", mode: str = "gf") -> str:
        """Constructs focused system prompt containing ONLY this sub-agent's allowed tools."""
        base = GF_MODE_PROMPT if mode != "assistant" else ASSISTANT_MODE_PROMPT
        base_prompt = base.format(shared=_SHARED_RULES).strip()
        if self.system_prompt_addon:
            base_prompt += "\n\n" + self.system_prompt_addon.strip()

        if self.tool_names:
            base_prompt += "\n\n" + format_system_tools_prompt(self.tool_names)
        return base_prompt.strip()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Returns TOOLS_SCHEMA subset for this sub-agent's tools."""
        return get_tool_schemas_for_agent(self.tool_names)

    def run(
        self,
        session_id: str,
        user_message: str,
        history: List[Dict],
        groq_client,
        model: str,
        emit_event_fn: Callable[[str, Dict], Any],
        execute_fn: Callable[[str, Dict], Dict],
        complexity: str = "simple",
        user_id: str = "",
        skip_memory: bool = False,
        on_rag_callback = None,
        selected_doc_ids: Optional[List[str]] = None,
        mode: str = "gf",
    ) -> Dict[str, Any]:
        """
        Executes request through either fast streaming path or agentic loop path.
        """
        sys_prompt = self.get_system_prompt(mode=mode)
        logger.info("[%s] running request (complexity=%s, tools=%d, mode=%s)", self.name, complexity, len(self.tool_names), mode)

        if complexity == "complex" and self.tool_names:
            # Complex task with action tools → run PLAN → EXECUTE → REFLECT → RETRY loop
            loop_res: AgentLoopResult = run_agentic_loop(
                user_message=user_message,
                history=history,
                groq_client=groq_client,
                model=LOOP_MODEL,
                emit_event_fn=emit_event_fn,
                execute_fn=execute_fn,
                allowed_tools=self.tool_names,
            )
            return {
                "mode": "loop",
                "narration": loop_res.summary_text,
                "loop_result": loop_res,
            }
        else:
            # Simple task or direct conversation → streaming generator with sub-agent system prompt
            chunks = []
            for chunk in generate_streaming_response(
                session_id=session_id,
                user_message=user_message,
                skip_memory=skip_memory,
                user_id=user_id,
                on_rag_callback=on_rag_callback,
                selected_doc_ids=selected_doc_ids,
                system_prompt_override=sys_prompt,
                mode=mode,
            ):
                chunks.append(chunk)

            return {
                "mode": "stream",
                "chunks": chunks,
                "full_text": "".join(chunks),
            }
