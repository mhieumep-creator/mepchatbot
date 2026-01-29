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

        # Set biến hệ thống MLINESCALE trước khi tạo MLINE
        try:
            doc.SetVariable("MLINESCALE", scale)
        except Exception as e:
            print(f"KHONG THE SETBIEN HE THONG MLINESCALE: {e}")

        # Tạo Mline
        mline = ms.AddMLine(points_array)
        mline.Layer = layer
        mline.StyleName = style
        mline.MLineScale = scale

        # Refresh drawing
        doc.Regen(1)  # acAllViewports = 1

        return str(mline.Handle)
    except Exception as e:
        print(f"Loi khi tao Mline: {e}")
        import traceback
        traceback.print_exc()
        return None

# Ví dụ sử dụng
create_mline([(0, 0), (100, 0), (100, 100), (0, 100)], layer="STANDARD", style="0", scale=2.0)