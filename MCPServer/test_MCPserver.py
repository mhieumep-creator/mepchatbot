import asyncio
import os
import sys
import logging
import time

# Chỉ cho phép WARNING trở lên (ẩn INFO/DEBUG)
logging.basicConfig(level=logging.WARNING)
# (tùy chọn) Giảm log riêng của anthropic và httpx
logging.getLogger("anthropic").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

# Cấu hình stdout/stderr để in được tiếng Việt trên Windows, tránh lỗi 'charmap'
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Đảm bảo có thể import MCPserver.py trong cùng thư mục
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)
import MCPserver as server


async def main() -> None:
    print("=" * 60)
    print("=== Test MCPserver – Batch: Tạo 5 Mline cùng lúc ===")
    print("=" * 60)

    # Batch: 5 Mline với các hình dạng khác nhau
    mlines = [
        {
            "action": "VON",
            "points": ["0,0", "1000,0", "1000,800"],
            "mlscale": 25.0,
            "layer": "0",
        },
        {
            "action": "VON",
            "points": ["0,1500", "0,2000", "600,2000", "600,1500"],
            "mlscale": 30.0,
            "layer": "0",
        },
        {
            "action": "VON_PPR",
            "points": ["1500,0", "2000,500", "2500,0", "3000,500", "3500,0"],
            "mlscale": 20.0,
            "layer": "0",
        },
        {
            "action": "VON",
            "points": ["4000,0", "4000,1000", "5000,1000", "5000,0"],
            "mlscale": 35.0,
            "layer": "0",
        },
        {
            "action": "VON_PPR",
            "points": ["5500,0", "6000,800", "6500,0"],
            "mlscale": 15.0,
            "layer": "0",
        },
    ]

    print(f"\nSố lượng Mline: {len(mlines)}")
    for i, m in enumerate(mlines, 1):
        print(f"  [{i}] {m['action']} | {len(m['points'])} điểm | MlScale={m['mlscale']}")

    print("\n--- Bắt đầu batch ---")
    start_time = time.time()

    try:
        result = await server.draw_mlines_batch(mlines=mlines)
        elapsed = time.time() - start_time
        print(f"\n{result}")
        print(f"\n--- Hoàn thành trong {elapsed:.2f}s ---")
    except Exception as e:
        print(f"Lỗi: {e}")

    print("\n" + "=" * 60)
    print("=== Kiểm tra AutoCAD để xem 5 Mline ===")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        print(f"Lỗi khởi tạo MCPserver hoặc môi trường: {e}")
        print("\nHãy kiểm tra lại file Key.env và biến môi trường CLAUDE_API_KEY.")
