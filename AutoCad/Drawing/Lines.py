"""
Lines.py – Vẽ Line trong AutoCAD (hỗ trợ batch).

Hỗ trợ:
    - Vẽ 1 đường thẳng (2 điểm)
    - Vẽ chuỗi line liên tiếp (polyline-style nhưng dùng Line)
    - Vẽ nhiều đường thẳng độc lập cùng lúc (batch)
    - Thiết lập Layer, Color, Linetype cho từng line

Sử dụng:
    from AutoCad.Drawing.Lines import create_lines

    # Một đường thẳng
    result = create_lines(lines=[
        {"start": [0, 0, 0], "end": [600, 0, 0]}
    ])

    # Chuỗi line liên tiếp (polyline-like)
    result = create_lines(lines=[
        {"start": [0,0,0],   "end": [600,0,0],   "layer": "M-PIPE"},
        {"start": [600,0,0], "end": [600,600,0], "layer": "M-PIPE"},
        {"start": [600,600,0], "end": [0,600,0], "layer": "M-PIPE"},
    ])

    # Nhiều line độc lập, khác layer
    result = create_lines(lines=[
        {"start": "0,0",     "end": "1000,0",   "layer": "M-PIPE", "color": 1},
        {"start": "500,500", "end": "500,1000", "layer": "M-DUCT", "color": 3},
    ])
"""

from AutoCad.Drawing._drawing_common import (
    get_logger,
    com_session,
    connect_acad,
    ensure_layers_batch,
    load_linetype,
    parse_point,
    make_variant_point,
    make_empty_result,
    make_no_pywin32_result,
    make_no_acad_result,
    regen,
)

logger = get_logger(__name__)


def create_lines(
    lines: list[dict],
    create_layer_if_missing: bool = True,
) -> dict:
    """
    Vẽ một hoặc nhiều Line trong AutoCAD (batch).

    Args:
        lines: Danh sách các line cần vẽ. Mỗi phần tử là dict:
            {
                "start":     [x, y, z] | "x,y,z",   # Điểm đầu  (z mặc định 0)
                "end":       [x, y, z] | "x,y,z",   # Điểm cuối (z mặc định 0)
                "layer":     str,                    # Layer (mặc định "0")
                "color":     int | None,             # ACI color index (tuỳ chọn)
                "linetype":  str | None,             # Tên linetype (tuỳ chọn, VD: "DASHED")
            }
        create_layer_if_missing: Tự tạo layer nếu chưa tồn tại (mặc định True).

    Returns:
        Dict kết quả:
            {
                "success":  bool,
                "message":  str,
                "total":    int,
                "drawn":    int,
                "failed":   int,
                "details":  [
                    {
                        "index":     int,
                        "ok":        bool,
                        "object_id": int | None,
                        "start":     list,
                        "end":       list,
                        "layer":     str | None,
                        "error":     str | None,
                    },
                    ...
                ],
                "error": str | None,
            }
    """
    # ── Validate input ──────────────────────────────────────────────
    if not lines:
        return make_empty_result(
            "Danh sách line trống.", "EMPTY_LINES_LIST",
            total=0, drawn=0, failed=0, details=[],
        )

    # ── Import COM ──────────────────────────────────────────────────
    try:
        import pythoncom  # noqa: F401
    except ImportError:
        return make_no_pywin32_result(
            total=len(lines), drawn=0, failed=len(lines), details=[],
        )

    # ── Chạy trong COM session ──────────────────────────────────────
    with com_session():
        return _create_lines_inner(lines, create_layer_if_missing)


def _create_lines_inner(
    lines: list[dict],
    create_layer_if_missing: bool,
) -> dict:
    """Logic chính — chạy sau khi COM đã được khởi tạo."""
    from pywintypes import com_error

    # ── 1. Kết nối AutoCAD ──────────────────────────────────────────
    try:
        acad, doc, model_space = connect_acad()
    except Exception as e:
        return make_no_acad_result(
            e, total=len(lines), drawn=0, failed=len(lines), details=[],
        )

    # ── 2. Thu thập layers cần tạo trước ────────────────────────────
    layers_needed = {ln.get("layer", "0") for ln in lines}
    ensure_layers_batch(doc, layers_needed, create_layer_if_missing)

    # ── 3. Vẽ từng line (batch) ─────────────────────────────────────
    details = []
    drawn = 0
    failed = 0

    for idx, line_spec in enumerate(lines):
        result = _draw_single_line(doc, model_space, line_spec, idx)
        details.append(result)
        if result["ok"]:
            drawn += 1
        else:
            failed += 1

    # ── 4. Regen ────────────────────────────────────────────────────
    regen(doc)

    # ── 5. Tổng hợp kết quả ────────────────────────────────────────
    total = len(lines)
    all_ok = (failed == 0)

    if all_ok:
        msg = f"Đã vẽ thành công {drawn}/{total} line."
    elif drawn > 0:
        msg = f"Vẽ line một phần: {drawn}/{total} thành công, {failed} thất bại."
    else:
        msg = f"Không thể vẽ bất kỳ line nào ({total} thất bại)."

    logger.info(msg)

    return {
        "success": all_ok or drawn > 0,
        "message": msg,
        "total": total,
        "drawn": drawn,
        "failed": failed,
        "details": details,
        "error": None if all_ok else f"{failed}/{total} line thất bại.",
    }


def _draw_single_line(doc, model_space, line_spec: dict, index: int) -> dict:
    """
    Vẽ 1 line trong AutoCAD.

    Returns:
        {
            "index":     int,
            "ok":        bool,
            "object_id": int | None,
            "start":     list,
            "end":       list,
            "layer":     str | None,
            "error":     str | None,
        }
    """
    from pywintypes import com_error

    # ── Parse start / end ───────────────────────────────────────────
    try:
        start_pt = parse_point(line_spec.get("start"))
    except Exception as e:
        return _fail_line(index, error=f"start không hợp lệ: {e}")

    try:
        end_pt = parse_point(line_spec.get("end"))
    except Exception as e:
        return _fail_line(index, start=list(start_pt), error=f"end không hợp lệ: {e}")

    # ── Tạo VARIANT cho điểm ───────────────────────────────────────
    start_var = make_variant_point(start_pt)
    end_var = make_variant_point(end_pt)

    layer = line_spec.get("layer", "0")
    color = line_spec.get("color")
    linetype = line_spec.get("linetype")

    # ── Vẽ line ─────────────────────────────────────────────────────
    try:
        line_obj = model_space.AddLine(start_var, end_var)
        logger.info(
            f"[{index}] Line ({start_pt[0]},{start_pt[1]},{start_pt[2]}) → "
            f"({end_pt[0]},{end_pt[1]},{end_pt[2]})"
        )
    except com_error as e:
        return _fail_line(
            index,
            start=list(start_pt),
            end=list(end_pt),
            error=f"Lỗi COM khi vẽ line: {e}",
        )

    # ── Đặt Layer ───────────────────────────────────────────────────
    try:
        if layer and layer != "0":
            line_obj.Layer = layer
    except com_error as e:
        logger.warning(f"[{index}] Không thể đặt layer '{layer}': {e}")

    # ── Đặt Color (ACI) ────────────────────────────────────────────
    if color is not None:
        try:
            line_obj.Color = int(color)
        except Exception as e:
            logger.warning(f"[{index}] Không thể đặt color {color}: {e}")

    # ── Đặt Linetype ───────────────────────────────────────────────
    if linetype:
        try:
            # Đảm bảo linetype đã được load
            load_linetype(doc, linetype)
            line_obj.Linetype = linetype
        except Exception as e:
            logger.warning(f"[{index}] Không thể đặt linetype '{linetype}': {e}")

    # ── Lấy ObjectID ────────────────────────────────────────────────
    try:
        obj_id = int(line_obj.ObjectID)
    except Exception:
        obj_id = None

    return {
        "index": index,
        "ok": True,
        "object_id": obj_id,
        "start": list(start_pt),
        "end": list(end_pt),
        "layer": layer,
        "error": None,
    }


# ── Hàm tiện ích ────────────────────────────────────────────────────────────


def _fail_line(
    index: int,
    start: list | None = None,
    end: list | None = None,
    error: str = "",
) -> dict:
    """Tạo dict kết quả lỗi cho 1 line."""
    return {
        "index": index,
        "ok": False,
        "object_id": None,
        "start": start or [],
        "end": end or [],
        "layer": None,
        "error": error,
    }


# ── Chạy trực tiếp để test ──────────────────────────────────────────────────
if __name__ == "__main__":
    import json as _json

    test_lines = [
        {"start": [0, 0, 0], "end": [1000, 0, 0], "layer": "0"},
        {"start": [1000, 0, 0], "end": [1000, 500, 0], "layer": "0"},
        {"start": "1000,500", "end": "0,500"},
    ]

    print("=" * 60)
    print(f"Test vẽ {len(test_lines)} line")
    print("=" * 60)

    result = create_lines(test_lines)
    print(_json.dumps(result, indent=2, ensure_ascii=False))
