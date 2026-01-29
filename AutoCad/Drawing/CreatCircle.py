import win32com.client
import pythoncom

def create_circle(center_point, radius, layer="0"):
    try:
        acad = win32com.client.Dispatch("AutoCAD.Application")
        doc = acad.ActiveDocument
        ms = doc.ModelSpace
        center_point = center_point
        radius = radius  # end_point truyền vào là bán kính

        center_array = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, center_point)

        # Đảm bảo layer tồn tại
        layer_exists = False
        for layer_obj in doc.Layers:
            if layer_obj.Name == layer:
                layer_exists = True
                break
        if not layer_exists:
            doc.Layers.Add(layer)

        # Tạo Circle
        circle = ms.AddCircle(center_array, radius)
        circle.Layer = layer

        return str(circle.Handle)
    except Exception as e:
        print(f"Loi khi tao circle: {e}")
        import traceback
        traceback.print_exc()
        return None
