"""
Lấy tên toàn bộ file trong một thư mục.
Hỗ trợ: lọc theo phần mở rộng, quét đệ quy thư mục con.
"""

import os
import sys

# Fix encoding cho Windows console (hỗ trợ tiếng Việt)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stdin.encoding != "utf-8":
    sys.stdin.reconfigure(encoding="utf-8")


def get_file_names(
    folder_path: str,
    extension: str | None = None,
    recursive: bool = False,
) -> list[str]:
    """
    Lấy danh sách tên file trong thư mục.

    Args:
        folder_path: Đường dẫn thư mục cần quét.
        extension:   Lọc theo phần mở rộng (VD: ".dwg", ".py"). None = lấy tất cả.
        recursive:   True = quét cả thư mục con. False = chỉ thư mục gốc.

    Returns:
        Danh sách tên file (chỉ tên, không bao gồm đường dẫn).
    """
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(f"Thư mục không tồn tại: {folder_path}")

    ext = extension.lower() if extension else None
    files = []

    if recursive:
        for root, _, filenames in os.walk(folder_path):
            for name in filenames:
                if ext is None or name.lower().endswith(ext):
                    files.append(name)
    else:
        for name in os.listdir(folder_path):
            full_path = os.path.join(folder_path, name)
            if os.path.isfile(full_path):
                if ext is None or name.lower().endswith(ext):
                    files.append(name)

    return sorted(files)


# ── Chạy thử ──
if __name__ == "__main__":
    # ============ CẤU HÌNH TẠI ĐÂY ============
    folder = r"C:\\ProgramData\\Autodesk\\ApplicationPlugins\\Htools.bundle\\Contents\\Windows\\Library\\CTN\\uPVC\\Phụ kiện"   # Đường dẫn thư mục cần quét
    ext = None                        # Lọc phần mở rộng: ".dwg", ".py", None = tất cả
    rec = False                       # True = quét cả thư mục con
    # ============================================

    result = get_file_names(folder, extension=ext, recursive=rec)
    print(f"\nTim thay {len(result)} file:")
    for f in result:
        print(f"  {f}")
