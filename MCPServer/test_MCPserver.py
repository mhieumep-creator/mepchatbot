import asyncio
import os
import sys

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
    print("=== Test MCPserver tools ===")

    # 1. Test sum_numbers
    print("\n[1] Test sum_numbers(2, 3):")
    try:
        result = await server.sum_numbers(2, 3)
        print("Kết quả:", result)
    except Exception as e:
        print("Lỗi khi gọi sum_numbers:", e)

    # 2. Test hello_gemini
    print("\n[2] Test hello_gemini('AutoCAD user'):")
    try:
        greeting = await server.hello_gemini("AutoCAD user")
        print("Phản hồi Gemini:\n", greeting)
    except Exception as e:
        print("Lỗi khi gọi hello_gemini:", e)

    # 3. Test ask_gemini với một prompt đơn giản
    print("\n[3] Test ask_gemini với prompt đơn giản:")
    try:
        prompt = "Giải thích ngắn gọn: AutoCAD MEP là gì?"
        answer = await server.ask_gemini(prompt)
        print("Phản hồi Gemini:\n", answer)
    except Exception as e:
        print("Lỗi khi gọi ask_gemini:", e)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        # Bắt lỗi thiếu GEMINI_API_KEY hoặc lỗi khi import MCPserver
        print("Lỗi khởi tạo MCPserver hoặc môi trường:", e)
        print("\nHãy kiểm tra lại file Key.env và biến môi trường GEMINI_API_KEY.")
