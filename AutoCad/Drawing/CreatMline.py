import win32com.client
import pythoncom

def batch_create_mline(list_params):
    """
    Tạo nhiều Mline trong AutoCAD theo batch.
    list_params: list các dict, mỗi dict gồm:
        {
            'points': [(x1, y1, z1), (x2, y2, z2)],
            'layer': 'LayerName',
            'style': 'StyleName',
            'scale': 1.0
        }
    Trả về: list kết quả (handle hoặc None nếu lỗi)
    """
    results = []
    try:
        acad = win32com.client.Dispatch("AutoCAD.Application")
        doc = acad.ActiveDocument
        ms = doc.ModelSpace
        # Đảm bảo các layer cần thiết đã tồn tại
        existing_layers = set(layer_obj.Name for layer_obj in doc.Layers)
        for param in list_params:
            layer = param.get('layer', '0')
            if layer not in existing_layers:
                try:
                    doc.Layers.Add(layer)
                    existing_layers.add(layer)
                except Exception as e:
                    print(f"Không thể tạo layer {layer}: {e}")
        # Tạo từng Mline liên tiếp (batch)
        for param in list_params:
            try:
                points = param['points']
                layer = param.get('layer', '0')
                style = param.get('style', 'Standard')
                scale = param.get('scale', 1.0)
                # Hỗ trợ batch: nếu points là list nhiều hơn 2 điểm, sẽ tạo liên tiếp các đoạn (A,B), (B,C), (C,D)...
                if len(points) < 2:
                    raise ValueError("Cần ít nhất 2 điểm để tạo Mline.")
                # Tạo từng đoạn liên tiếp nếu nhiều hơn 2 điểm
                for i in range(len(points) - 1):
                    seg_points = [points[i], points[i+1]]
                    flat_points = []
                    for pt in seg_points:
                        if len(pt) == 2:
                            flat_points.extend([pt[0], pt[1], 0])
                        else:
                            flat_points.extend(pt)
                    points_array = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, flat_points)
                    # Set style trước khi tạo MLine
                    try:
                        doc.SetVariable("CMLSTYLE", style)
                        doc.SetVariable("CMLSCALE", scale)
                    except Exception as e:
                        print(f"Không thể set biến hệ thống MLSTYLE: {e}")
                    mline = ms.AddMLine(points_array)
                    mline.Layer = layer
                    mline.MLineScale = scale
                    results.append(str(mline.Handle))
            except Exception as e:
                print(f"Lỗi khi tạo Mline batch: {e}")
                import traceback
                traceback.print_exc()
                results.append(None)
        doc.Regen(1)
        return results
    except Exception as e:
        print(f"Lỗi batch_create_mline: {e}")
        import traceback
        traceback.print_exc()
        return [None] * len(list_params)

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