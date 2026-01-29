import asyncio
import os
import sys
import time
# Cấu hình stdout/stderr để in được tiếng Việt trên Windows, tránh lỗi 'charmap'
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        # Nếu không reconfigure được thì vẫn tiếp tục, chỉ có thể bị lỗi hiển thị ký tự
        pass

# Đảm bảo có thể import MCPserver.py từ thư mục cha
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
import MCPServer.MCPserver as server


async def main() -> None:
    print("=== Test MCPserver tools với Claude AI ===")
    # 4. Test create_line tool
    time.sleep(3)
    print("\n[4] Test create_line_tool:")
    try:
        handle = await server.create_line_tool(
            start_x=0.0, start_y=0.0, start_z=0.0,
            end_x=100.0, end_y=100.0, end_z=0.0,
            layer="0"
        )
        print("Đã tạo Line với handle:", handle)
    except Exception as e:
        print("Lỗi khi gọi create_line_tool:", e)
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        # Bắt lỗi thiếu CLAUDE_API_KEY hoặc lỗi khi import MCPserver
        print("Lỗi khởi tạo MCPserver hoặc môi trường:", e)
        print("\nHãy kiểm tra lại file Key.env và biến môi trường CLAUDE_API_KEY.")
