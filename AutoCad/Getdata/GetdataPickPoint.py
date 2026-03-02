"""
GetdataPickPoint.py – Yêu cầu người dùng pick điểm trên bản vẽ AutoCAD
và trả về tọa độ.

Thông tin trả về cho mỗi điểm:
    - index: Thứ tự điểm (0-based)
    - x, y, z: Tọa độ điểm

Sử dụng:
    from AutoCad.Getdata.GetdataPickPoint import get_pick_point

    result = get_pick_point()              # Pick 1 điểm (mặc định)
    result = get_pick_point(num_points=3)  # Pick 3 điểm liên tiếp
    result = get_pick_point(
        num_points=2,
        prompt="Chọn điểm đầu ống: "
    )
"""

import os, sys
# Đảm bảo thư mục gốc project nằm trong sys.path (hỗ trợ chạy file trực tiếp)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from AutoCad.Getdata._acad_common import (
    get_logger, com_session, connect_acad,
    make_no_pywin32_result, make_no_acad_result,
)

logger = get_logger(__name__)


def get_pick_point(
    num_points: int = 1,
    prompt: str | None = None,
) -> dict:
    """
    Yêu cầu người dùng pick điểm trên bản vẽ AutoCAD.

    Args:
        num_points: Số điểm cần pick (mặc định 1). Đặt 0 để pick liên tục
                    cho đến khi người dùng nhấn Escape/Enter.
        prompt:     Thông báo hiển thị trên command line AutoCAD khi pick.
                    Mặc định: "Pick diem thu {i}: "

    Returns:
        {
            "success": bool,
            "message": str,
            "point_count": int,
            "points": [
                {"index": 0, "x": float, "y": float, "z": float},
                ...
            ],
            "error": str | None,
        }
    """
    try:
        import pythoncom
    except ImportError:
        return make_no_pywin32_result(point_count=0, points=[])

    with com_session():
        return _get_pick_point_inner(num_points, prompt)


def _get_pick_point_inner(num_points: int, prompt: str | None) -> dict:
    import pythoncom
    from pywintypes import com_error

    try:
        acad, doc, ms = connect_acad()
    except com_error as e:
        return make_no_acad_result(e, point_count=0, points=[])

    utility = doc.Utility
    points = []

    if num_points == 0:
        # Pick liên tục cho đến khi người dùng nhấn Escape/Enter
        i = 0
        while True:
            try:
                msg = prompt or f"Pick diem thu {i + 1} (Enter/Esc de ket thuc): "
                if i > 0 and prompt:
                    msg = f"Pick diem thu {i + 1}: "

                raw_point = utility.GetPoint(pythoncom.Missing, msg)
                pt = _parse_pick_point(raw_point)
                points.append({"index": i, "x": pt[0], "y": pt[1], "z": pt[2]})
                logger.info(f"Diem {i + 1}: ({pt[0]:.4f}, {pt[1]:.4f}, {pt[2]:.4f})")
                i += 1
            except com_error:
                # Người dùng nhấn Escape hoặc Enter → kết thúc
                logger.info(f"Ket thuc pick diem. Tong: {len(points)} diem.")
                break
            except Exception as e:
                logger.warning(f"Loi pick diem {i + 1}: {e}")
                break
    else:
        # Pick đúng num_points điểm
        for i in range(num_points):
            try:
                if prompt and num_points == 1:
                    msg = prompt
                else:
                    msg = prompt or f"Pick diem thu {i + 1}/{num_points}: "
                    if prompt and num_points > 1:
                        msg = f"{prompt} ({i + 1}/{num_points}): "

                raw_point = utility.GetPoint(pythoncom.Missing, msg)
                pt = _parse_pick_point(raw_point)
                points.append({"index": i, "x": pt[0], "y": pt[1], "z": pt[2]})
                logger.info(f"Diem {i + 1}: ({pt[0]:.4f}, {pt[1]:.4f}, {pt[2]:.4f})")
            except com_error:
                logger.info(f"Nguoi dung huy tai diem {i + 1}.")
                break
            except Exception as e:
                logger.warning(f"Loi pick diem {i + 1}: {e}")
                break

    point_count = len(points)

    if point_count == 0:
        return {
            "success": False,
            "message": "Nguoi dung da huy hoac khong pick diem nao.",
            "point_count": 0,
            "points": [],
            "error": "NO_POINT_PICKED",
        }

    msg = f"Da lay {point_count} diem thanh cong."
    logger.info(msg)

    return {
        "success": True,
        "message": msg,
        "point_count": point_count,
        "points": points,
        "error": None,
    }


def _parse_pick_point(raw) -> list[float]:
    """Chuyển đổi raw COM point từ GetPoint thành [x, y, z]."""
    pt = list(raw)
    x = float(pt[0])
    y = float(pt[1])
    z = float(pt[2]) if len(pt) > 2 else 0.0
    return [x, y, z]
