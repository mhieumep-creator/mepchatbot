import asyncio
import os
import sys
import logging
import time
# Chỉ cho phép WARNING trở lên (ẩn INFO/DEBUG)
logging.basicConfig(level=logging.WARNING)
# (tùy chọn) Giảm log riêng của google.genai và httpx
logging.getLogger("google.genai").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
# Cấu hình stdout/stderr để in được tiếng Việt trên Windows, tránh lỗi 'charmap'
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        # Nếu không reconfigure được thì vẫn tiếp tục, chỉ có thể bị lỗi hiển thị ký tự
        pass

# Đảm bảo có thể import MCPserver.py trong cùng thư mục
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)
import MCPserver as server


async def main() -> None:
    print("=== Test MCPserver tools với Claude AI ===")

    # 1. Test sum_numbers
    print("\n[1] Test sum_numbers(2, 3):")
    try:
        result = await server.sum_numbers(2, 3)
        print("Kết quả:", result)
    except Exception as e:
        print("Lỗi khi gọi sum_numbers:", e)

    time.sleep(3)
    # 2. Test hello_claude
    print("\n[2] Test hello_claude('AutoCAD user'):")
    try:
        greeting = await server.hello_claude("AutoCAD user")
        print("Phản hồi Claude:\n", greeting)
    except Exception as e:
        print("Lỗi khi gọi hello_claude:", e)

    # 3. Test ask_claude với một prompt đơn giản
    time.sleep(3)
    print("\n[3] Test ask_claude với prompt đơn giản:")
    try:
        prompt = "Giải thích ngắn gọn: AutoCAD MEP là gì?"
        answer = await server.ask_claude(prompt)
        print("Phản hồi Claude:\n", answer)
    except Exception as e:
        print("Lỗi khi gọi ask_claude:", e)
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        # Bắt lỗi thiếu CLAUDE_API_KEY hoặc lỗi khi import MCPserver
        print("Lỗi khởi tạo MCPserver hoặc môi trường:", e)
        print("\nHãy kiểm tra lại file Key.env và biến môi trường CLAUDE_API_KEY.")
