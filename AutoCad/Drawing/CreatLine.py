import win32com.client
import pythoncom

def create_line(start_point, end_point, layer="0"):
    try:
        acad = win32com.client.Dispatch("AutoCAD.Application")
        doc = acad.ActiveDocument
        ms = doc.ModelSpace

        # ✅ QUAN TRỌNG: Chuyển tuple thành array
        start_array = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, start_point)
        end_array = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, end_point)

        # Đảm bảo layer tồn tại
        layer_exists = False
        for layer_obj in doc.Layers:
            if layer_obj.Name == layer:
                layer_exists = True
                break
        
        if not layer_exists:
            doc.Layers.Add(layer)

        # Tạo Line với array
        line = ms.AddLine(start_array, end_array)
        line.Layer = layer

        return str(line.Handle)
        
    except Exception as e:
        print(f"Loi khi tao line: {e}")
        import traceback
        traceback.print_exc()  # In chi tiết lỗi
        return None
