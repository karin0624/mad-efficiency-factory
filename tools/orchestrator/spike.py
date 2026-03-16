"""Phase 0: SDK parity spike.

Verify that query() sessions support Skills, CLAUDE.md, MCP, and AskUserQuestion.

Usage:
    python -m tools.orchestrator.spike
"""

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)


async def run_spike() -> None:
    project_root = "."

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-6",
        cwd=project_root,
        setting_sources=["project"],
        permission_mode="acceptEdits",
        allowed_tools=[
            "Bash",
            "Read",
            "Write",
            "Edit",
            "Glob",
            "Grep",
            "Skill",
        ],
        max_turns=10,
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
        },
    )

    prompt = """\
以下の4つの検証を順番に実施し、各結果を報告してください:

1. **CLAUDE.md 読み込み確認**: あなたのシステムプロンプトに "Spec-Driven Development" または "cc-sdd" に関する指示が含まれていますか？含まれていれば「CLAUDE.md: OK」と報告。

2. **Skill ツール確認**: Skill ツールが利用可能か確認してください。利用可能なら `Skill(skill="kiro:spec-status")` を呼んで結果を報告。利用不可なら「Skill: UNAVAILABLE」と報告。

3. **MCP サーバー確認**: MCP memory ツール (mcp__memory__recall 等) が利用可能か確認してください。利用可能なら「MCP: OK」と報告。利用不可なら「MCP: UNAVAILABLE」と報告。

4. **ファイル操作確認**: Read ツールで `.kiro/steering/product.md` を読んで、最初の行を報告してください。

最後に以下の形式でサマリーを出力:
SPIKE_RESULT:
  CLAUDE_MD: OK/FAIL
  SKILL: OK/FAIL/UNAVAILABLE
  MCP: OK/FAIL/UNAVAILABLE
  FILE_OPS: OK/FAIL
"""

    print("=== SDK Parity Spike ===")
    print(f"Model: {options.model}")
    print(f"CWD: {project_root}")
    print()

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
                elif isinstance(block, ToolUseBlock):
                    print(f"  [Tool: {block.name}({block.input})]")
        elif isinstance(message, ResultMessage):
            print()
            print(f"--- Result ---")
            print(f"  Turns: {message.num_turns}")
            print(f"  Duration: {message.duration_ms}ms")
            usage = message.usage or {}
            in_tok = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)
            print(f"  Tokens: in={in_tok:,} / out={out_tok:,} (total={in_tok+out_tok:,})")
            print(f"  Error: {message.is_error}")
            if message.result:
                print(f"  Final: {message.result[:200]}")


if __name__ == "__main__":
    anyio.run(run_spike)
