"""
Polyline.py – Vẽ Polyline (LWPolyline) trong AutoCAD (hỗ trợ batch).

Hỗ trợ:
    - Vẽ 1 polyline (nhiều đỉnh)
    - Vẽ nhiều polyline độc lập cùng lúc (batch)
    - Thiết lập Layer, Color, Linetype, Closed cho từng polyline
    - Hỗ trợ Bulge (cung tròn) cho từng đỉnh

Sử dụng:
    from AutoCad.Drawing.Polyline import create_polylines

    # Một polyline đơn giản (hình chữ nhật)
    result = create_polylines(polylines=[
        {
            "vertices": [[0,0], [1000,0], [1000,500], [0,500]],
            "closed": True,
            "layer": "M-PIPE",
        }
    ])

    # Nhiều polyline
    result = create_polylines(polylines=[
        {
            "vertices": ["0,0", "600,0", "600,600"],
            "layer": "M-DUCT",
            "color": 3,
        },
        {
            "vertices": [[1000,0], [1000,500], [1500,500]],
            "closed": False,
            "linetype": "DASHED",
        },
    ])

    # Polyline với Bulge (cung tròn)
    result = create_polylines(polylines=[
        {
            "vertices": [[0,0], [500,0], [500,500]],
            "bulges": {1: 0.5},  # Đỉnh index 1 có bulge = 0.5 (cung tròn)
        }
    ])
"""

from AutoCad.Drawing._drawing_common import (
    get_logger,
    com_session,
    connect_acad,
    ensure_layers_batch,
    load_linetype,
    parse_point,
    make_error_result,
    make_no_pywin32_result,
    make_no_acad_result,
    regen,
)

logger = get_logger(__name__)


def create_polylines(
    polylines: list[dict],
    create_layer_if_missing: bool = True,
) -> dict:
    """
    Vẽ một hoặc nhiều Polyline (LWPolyline) trong AutoCAD (batch).

    Args:
        polylines: Danh sách polyline cần vẽ. Mỗi phần tử là dict:
            {
                "vertices":  [[x,y], ...] | ["x,y", ...],  # Danh sách đỉnh (ít nhất 2)
                "closed":    bool,                          # Đóng polyline (mặc định False)
                "layer":     str,                           # Layer (mặc định "0")
                "color":     int | None,                    # ACI color index (tuỳ chọn)
                "linetype":  str | None,                    # Tên linetype (tuỳ chọn)
                "lineweight":int | None,                    # Lineweight (tuỳ chọn, đơn vị 0.01mm)
                "width":     float | None,                  # Global width (tuỳ chọn)
                "bulges":    dict[int, float] | None,       # {vertex_index: bulge_value}
            }
        create_layer_if_missing: Tự tạo layer nếu chưa tồn tại.

    Returns:
        Dict kết quả:
            {
                "success":  bool,
                "message":  str,
                "total":    int,
                "drawn":    int,
                "failed":   int,
                "details":  [{...}],
                "error":    str | None,
            }
    """
    if not polylines:
        return make_error_result(
            "Danh sách polyline trống.", "EMPTY_POLYLINES_LIST",
            total=0, drawn=0, failed=0, details=[],
        )

    try:
        import pythoncom  # noqa: F401
    except ImportError:
        return make_no_pywin32_result(
            total=len(polylines), drawn=0, failed=len(polylines), details=[],
        )

    with com_session():
        return _create_polylines_inner(polylines, create_layer_if_missing)


def _create_polylines_inner(
    polylines: list[dict],
    create_layer_if_missing: bool,
) -> dict:
    """Logic chính — chạy bên trong com_session."""
    import pythoncom
    import win32com.client
    from pywintypes import com_error

    # ── 1. Kết nối AutoCAD ──────────────────────────────────────────
    try:
        acad, doc, model_space = connect_acad()
    except Exception as e:
        return make_no_acad_result(
            e, total=len(polylines), drawn=0, failed=len(polylines), details=[],
        )

    # ── 2. Tạo trước các layer cần thiết ────────────────────────────
    layers_needed = {pl.get("layer", "0") for pl in polylines}
    ensure_layers_batch(doc, layers_needed, create_layer_if_missing)

    # ── 3. Vẽ từng polyline (batch) ─────────────────────────────────
    details = []
    drawn = 0
    failed = 0

    for idx, pl_spec in enumerate(polylines):
        result = _draw_single_polyline(doc, model_space, pl_spec, idx)
        details.append(result)
        if result["ok"]:
            drawn += 1
        else:
            failed += 1

    # ── 4. Regen ────────────────────────────────────────────────────
    regen(doc)

    # ── 5. Tổng hợp kết quả ────────────────────────────────────────
    total = len(polylines)
    all_ok = (failed == 0)

    if all_ok:
        msg = f"Đã vẽ thành công {drawn}/{total} polyline."
    elif drawn > 0:
        msg = f"Vẽ polyline một phần: {drawn}/{total} thành công, {failed} thất bại."
    else:
        msg = f"Không thể vẽ bất kỳ polyline nào ({total} thất bại)."

    logger.info(msg)

    return {
        "success": all_ok or drawn > 0,
        "message": msg,
        "total": total,
        "drawn": drawn,
        "failed": failed,
        "details": details,
        "error": None if all_ok else f"{failed}/{total} polyline thất bại.",
    }


def _draw_single_polyline(doc, model_space, pl_spec: dict, index: int) -> dict:
    """
    Vẽ 1 LWPolyline trong AutoCAD.

    Returns:
        {
            "index":      int,
            "ok":         bool,
            "object_id":  int | None,
            "vertices":   int,
            "layer":      str | None,
            "closed":     bool,
            "error":      str | None,
        }
    """
    import pythoncom
    import win32com.client
    from pywintypes import com_error

    # ── Parse vertices ──────────────────────────────────────────────
    raw_vertices = pl_spec.get("vertices", [])
    if not raw_vertices or len(raw_vertices) < 2:
        return _fail_polyline(index, error="Cần ít nhất 2 đỉnh.")

    try:
        vertices_2d = []
        for v in raw_vertices:
            pt = parse_point(v)
            vertices_2d.extend([pt[0], pt[1]])  # LWPolyline chỉ dùng x, y
    except Exception as e:
        return _fail_polyline(index, error=f"Đỉnh không hợp lệ: {e}")

    # ── Tạo VARIANT cho danh sách đỉnh (flat array: x0,y0,x1,y1,...) ──
    points_var = win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8, vertices_2d
    )

    layer = pl_spec.get("layer", "0")
    color = pl_spec.get("color")
    linetype = pl_spec.get("linetype")
    lineweight = pl_spec.get("lineweight")
    width = pl_spec.get("width")
    closed = pl_spec.get("closed", False)
    bulges = pl_spec.get("bulges", {})

    # ── Vẽ LWPolyline ──────────────────────────────────────────────
    try:
        pline = model_space.AddLightWeightPolyline(points_var)
        logger.info(
            f"[{index}] Polyline {len(raw_vertices)} đỉnh"
            f" | closed={closed} | layer={layer}"
        )
    except com_error as e:
        return _fail_polyline(index, error=f"Lỗi COM khi vẽ polyline: {e}")

    # ── Closed ──────────────────────────────────────────────────────
    if closed:
        try:
            pline.Closed = True
        except Exception as e:
            logger.warning(f"[{index}] Không thể đóng polyline: {e}")

    # ── Layer ───────────────────────────────────────────────────────
    if layer and layer != "0":
        try:
            pline.Layer = layer
        except Exception as e:
            logger.warning(f"[{index}] Không thể đặt layer '{layer}': {e}")

    # ── Color ───────────────────────────────────────────────────────
    if color is not None:
        try:
            pline.Color = int(color)
        except Exception as e:
            logger.warning(f"[{index}] Không thể đặt color {color}: {e}")

    # ── Linetype ────────────────────────────────────────────────────
    if linetype:
        try:
            load_linetype(doc, linetype)
            pline.Linetype = linetype
        except Exception as e:
            logger.warning(f"[{index}] Không thể đặt linetype '{linetype}': {e}")

    # ── Lineweight ──────────────────────────────────────────────────
    if lineweight is not None:
        try:
            pline.Lineweight = int(lineweight)
        except Exception as e:
            logger.warning(f"[{index}] Không thể đặt lineweight: {e}")

    # ── Global Width ────────────────────────────────────────────────
    if width is not None:
        try:
            pline.ConstantWidth = float(width)
        except Exception as e:
            logger.warning(f"[{index}] Không thể đặt width: {e}")

    # ── Bulges (cung tròn) ──────────────────────────────────────────
    if bulges:
        for v_idx, bulge_val in bulges.items():
            try:
                pline.SetBulge(int(v_idx), float(bulge_val))
            except Exception as e:
                logger.warning(
                    f"[{index}] Không thể đặt bulge tại đỉnh {v_idx}: {e}"
                )

    # ── ObjectID ────────────────────────────────────────────────────
    try:
        obj_id = int(pline.ObjectID)
    except Exception:
        obj_id = None

    return {
        "index": index,
        "ok": True,
        "object_id": obj_id,
        "vertices": len(raw_vertices),
        "layer": layer,
        "closed": closed,
        "error": None,
    }


def _fail_polyline(index: int, error: str = "") -> dict:
    """Tạo dict kết quả lỗi cho 1 polyline."""
    return {
        "index": index,
        "ok": False,
        "object_id": None,
        "vertices": 0,
        "layer": None,
        "closed": False,
        "error": error,
    }


# ── Chạy trực tiếp để test ──────────────────────────────────────────────────
if __name__ == "__main__":
    import json as _json

    test_polylines = [
        {
            "vertices": [[0, 0], [1000, 0], [1000, 500], [0, 500]],
            "closed": True,
            "layer": "0",
        },
        {
            "vertices": ["2000,0", "3000,0", "3000,500"],
            "closed": False,
        },
    ]

    print("=" * 60)
    print(f"Test vẽ {len(test_polylines)} polyline")
    print("=" * 60)

    result = create_polylines(test_polylines)
    print(_json.dumps(result, indent=2, ensure_ascii=False))
