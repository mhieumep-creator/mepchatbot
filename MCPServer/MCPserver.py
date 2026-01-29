import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
import anthropic

# 1. Khởi tạo MCP Server
mcp = FastMCP("Claude-AutoCAD-Server")

# 2. Nạp biến môi trường từ file .env (nếu có)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "Key.env")
load_dotenv(ENV_PATH)


# 3. Lấy API key từ biến môi trường CLAUDE_API_KEY (không hardcode key trong code)
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
if not CLAUDE_API_KEY:
    raise RuntimeError(
        f"Missing CLAUDE_API_KEY environment variable for Claude client. "
        f"Expected it in environment or in .env at: {ENV_PATH}"
    )

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
MODEL_NAME = "claude-3-opus-20240229"  # Hoặc model Claude phù hợp


@mcp.tool()
async def ask_claude(prompt: str) -> str:
    """Sử dụng Claude (anthropic) để hỗ trợ các tác vụ AutoCAD/MEP."""
    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text if response.content else "Không có phản hồi từ Claude."
    except Exception as e:
        return f"Lỗi khi gọi Claude: {str(e)}"
@mcp.tool()
async def hello_claude(name: str) -> str:
    """Công cụ mẫu để kiểm tra kết nối với Claude."""
    try:
        prompt = f"Viết một lời chào thân thiện cho {name}."
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text if response.content else "Không có phản hồi từ Claude."
    except Exception as e:
        return f"Lỗi khi gọi Claude: {str(e)}"
@mcp.tool()
async def sum_numbers(a: int, b: int) -> int:
    """Công cụ mẫu để tính tổng hai số."""
    return a + b

if __name__ == "__main__":
    mcp.run()