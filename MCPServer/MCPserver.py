import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
import anthropic

# 1. Khởi tạo MCP Server
mcp = FastMCP("Gemini-AutoCAD-Server")

# 2. Nạp biến môi trường từ file .env (nếu có)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "Key.env")
load_dotenv(ENV_PATH)


# --- Claude config ---
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
if not CLAUDE_API_KEY:
    raise RuntimeError(
        f"Missing CLAUDE_API_KEY environment variable for Claude client. "
        f"Expected it in environment or in .env at: {ENV_PATH}"
    )
claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
CLAUDE_MODEL = "claude-haiku-4-5-20251001"  # Hoặc model phù hợp




# Tool gọi Claude AI
@mcp.tool()
async def ask_claude(prompt: str) -> str:
    """Sử dụng Claude AI để hỗ trợ các tác vụ AutoCAD/MEP."""
    try:
        response = claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        # anthropic 1.x: response.content, anthropic 2.x: response.completion
        return getattr(response, "content", getattr(response, "completion", str(response)))
    except Exception as e:
        return f"Lỗi khi gọi Claude: {str(e)}"


# Tool kiểm tra Claude
@mcp.tool()
async def hello_claude(name: str) -> str:
    """Công cụ mẫu để kiểm tra kết nối với Claude AI."""
    try:
        prompt = f"Viết một lời chào thân thiện cho {name}."
        response = claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        return getattr(response, "content", getattr(response, "completion", str(response)))
    except Exception as e:
        return f"Lỗi khi gọi Claude: {str(e)}"
@mcp.tool()
async def sum_numbers(a: int, b: int) -> int:
    """Công cụ mẫu để tính tổng hai số."""
    return a + b

if __name__ == "__main__":
    mcp.run()