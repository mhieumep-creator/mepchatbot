import win32com.client
import pythoncom

def create_mline(points, layer="0", style="Standard", scale=1.0):
    """
    Tạo Mline trong AutoCAD.
    points: list các tuple (x, y, z) hoặc (x, y)
    layer: tên layer
    style: tên style Mline
    scale: hệ số scale
    """
    try:
        # Chỉ cho phép đúng 2 điểm
        if len(points) < 2:
            raise ValueError("Cần ít nhất 2 điểm để tạo Mline.")
        if len(points) > 2:
            print("Chỉ lấy 2 điểm đầu tiên để tạo Mline.")
            points = points[:2]

        acad = win32com.client.Dispatch("AutoCAD.Application")
        doc = acad.ActiveDocument
        ms = doc.ModelSpace

        # Chuyển points thành array kiểu double
        flat_points = []
        for pt in points:
            if len(pt) == 2:
                flat_points.extend([pt[0], pt[1], 0])
            else:
                flat_points.extend(pt)
        points_array = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, flat_points)

        # Đảm bảo layer tồn tại
        layer_exists = False
        for layer_obj in doc.Layers:
            if layer_obj.Name == layer:
                layer_exists = True
                break
        if not layer_exists:
            doc.Layers.Add(layer)
            if len(points) != 2:
                raise ValueError("Hàm này chỉ nhận đúng 2 điểm (đầu-cuối)")

        # Set style trước khi tạo MLine (không set được qua property)
        try:
                    # 1. Thiết lập style TRƯỚC KHI tạo MLine
            doc.SetVariable("CMLSTYLE", style)  # Set current MLine style
            doc.SetVariable("CMLSCALE", scale)  # Set MLine scale
        except Exception as e:
            print(f"Không thể set biến hệ thống MLSTYLE: {e}")

        mline = ms.AddMLine(points_array)
        mline.Layer = layer
        # Không set được StyleName trực tiếp, chỉ set được khi tạo qua biến hệ thống
        mline.MLineScale = scale

        # Refresh drawing
        doc.Regen(1)  # acAllViewports = 1

        return str(mline.Handle)
    except Exception as e:
        print(f"Loi khi tao Mline: {e}")
        import traceback
        traceback.print_exc()
        return None