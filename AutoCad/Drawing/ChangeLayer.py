import win32com.client

def change_layer_by_handle(handle_string, new_layer_name):
    """
    Đổi layer cho đối tượng AutoCAD theo handle.
    Yêu cầu AutoCAD đang mở và có bản vẽ active.
    """
    try:
        acad = win32com.client.Dispatch("AutoCAD.Application")
        doc = acad.ActiveDocument
        ms = doc.ModelSpace

        # Tìm đối tượng theo handle
        for obj in ms:
            if hasattr(obj, 'Handle') and obj.Handle == handle_string:
                # Kiểm tra layer đã tồn tại chưa
                layer_names = [layer.Name for layer in doc.Layers]
                if new_layer_name not in layer_names:
                    doc.Layers.Add(new_layer_name)
                # Đổi layer
                obj.Layer = new_layer_name
                return True
        return False
    except Exception as e:
        print(f"Lỗi khi đổi layer: {e}")
        return False