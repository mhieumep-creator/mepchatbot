import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
import google.genai as genai

# 1. Khởi tạo MCP Server
mcp = FastMCP("Gemini-AutoCAD-Server")

# 2. Nạp biến môi trường từ file .env (nếu có)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "Key.env")
load_dotenv(ENV_PATH)

# 3. Lấy API key từ biến môi trường GEMINI_API_KEY (không hardcode key trong code)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError(
        f"Missing GEMINI_API_KEY environment variable for Gemini client. "
        f"Expected it in environment or in .env at: {ENV_PATH}"
    )

# Cấu hình SDK google-genai bằng Client (không dùng configure)
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-2.0-flash"


@mcp.tool()
async def ask_gemini(prompt: str) -> str:
    """Sử dụng Gemini (google-genai) để hỗ trợ các tác vụ AutoCAD/MEP."""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Lỗi khi gọi Gemini: {str(e)}"
@mcp.tool()
async def hello_gemini(name: str) -> str:
    """Công cụ mẫu để kiểm tra kết nối với Gemini."""
    try:
        prompt = f"Viết một lời chào thân thiện cho {name}."
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Lỗi khi gọi Gemini: {str(e)}"
@mcp.tool()
async def sum_numbers(a: int, b: int) -> int:
    """Công cụ mẫu để tính tổng hai số."""
    return a + b

if __name__ == "__main__":
    mcp.run()