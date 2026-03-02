# Skill: Drawing Tools - Hướng dẫn Prompt vẽ trong AutoCAD

## Tổng quan
Tài liệu này hướng dẫn cách viết Prompt để sử dụng các Drawing tools trong MCP Server, giúp người dùng vẽ và thao tác với các đối tượng trong AutoCAD MEP.
---
## 1. Vẽ Mline - Đường ống thoát nước (`draw_mline_von`)

### Mô tả
Vẽ Mline bằng lệnh tùy chỉnh **VON** — dùng để tạo đường ống **thoát nước** trong bản vẽ AutoCAD.

### Tham số
| Tham số   | Kiểu         | Mặc định     | Mô tả                                      |
|-----------|--------------|--------------|---------------------------------------------|
| points    | list[str]    | *(bắt buộc)* | Danh sách tọa độ, VD: `["0,0", "600,0"]`   |
| mlscale   | float        | 25.0         | Giá trị MlScale (kích thước ống)            |
| layer     | str          | "0"          | Tên Layer                                   |
| mlstyle   | str          | "STANDARD"   | Tên MlineStyle                              |

### Ví dụ Prompt

**Cơ bản:**
```
Vẽ đường ống thoát nước từ điểm (0,0) đến (600,0) rồi đến (600,600)
```

**Chỉ định kích thước ống và layer:**
```
Vẽ ống thoát nước mlscale 50, layer "THOAT-NUOC" qua các điểm: (0,0), (1000,0), (1000,800), (2000,800)
```

**Ngắn gọn:**
```
Vẽ mline VON từ (100,200) đến (500,200) đến (500,600), mlscale=30, layer="SAN"
```

---

## 2. Vẽ Mline - Đường ống cấp nước (`draw_mline_von_ppr`)

### Mô tả
Vẽ Mline bằng lệnh tùy chỉnh **VON_PPR** — dùng để tạo đường ống **cấp nước** trong bản vẽ AutoCAD.

### Tham số
| Tham số   | Kiểu         | Mặc định     | Mô tả                                      |
|-----------|--------------|--------------|---------------------------------------------|
| points    | list[str]    | *(bắt buộc)* | Danh sách tọa độ, VD: `["0,0", "600,0"]`   |
| mlscale   | float        | 25.0         | Giá trị MlScale (kích thước ống)            |
| layer     | str          | "0"          | Tên Layer                                   |
| mlstyle   | str          | "STANDARD"   | Tên MlineStyle                              |

### Ví dụ Prompt

**Cơ bản:**
```
Vẽ đường ống cấp nước từ (0,0) đến (800,0) đến (800,500)
```

**Chỉ định chi tiết:**
```
Vẽ ống cấp nước PPR, mlscale 20, layer "CAP-NUOC", các điểm: (0,1500), (600,1500), (600,2000)
```

---

## 3. Vẽ nhiều Mline cùng lúc - Batch (`draw_mlines_batch`)

### Mô tả
Vẽ **nhiều Mline** trong 1 phiên AutoCAD duy nhất. Hiệu quả hơn nhiều so với gọi từng lệnh riêng lẻ. Hỗ trợ trộn lẫn cả VON và VON_PPR.

### Tham số
| Tham số | Kiểu        | Mô tả                                                         |
|---------|-------------|----------------------------------------------------------------|
| mlines  | list[dict]  | Danh sách Mline, mỗi phần tử chứa: `action`, `points`, `mlscale`, `layer`, `mlstyle` |

Mỗi dict trong `mlines`:
| Key      | Kiểu      | Mặc định   | Mô tả                          |
|----------|-----------|------------|---------------------------------|
| action   | str       | *(bắt buộc)* | `"VON"` hoặc `"VON_PPR"`     |
| points   | list[str] | *(bắt buộc)* | Danh sách tọa độ             |
| mlscale  | float     | 25.0       | Giá trị MlScale                |
| layer    | str       | "0"        | Tên Layer                       |
| mlstyle  | str       | "STANDARD" | Tên MlineStyle                  |
### Ví dụ Prompt
**Vẽ cả ống cấp và thoát:**
```
Vẽ 3 đường ống cùng lúc:
1. Ống thoát nước (VON) từ (0,0) → (1000,0) → (1000,800), mlscale 25
2. Ống cấp nước (VON_PPR) từ (0,1500) → (600,1500), mlscale 20
3. Ống thoát nước (VON) từ (2000,0) → (2500,500) → (3000,0), mlscale 30
```

**Ngắn gọn:**
```
Batch vẽ: VON qua (0,0)-(500,0)-(500,300) layer "SAN", VON_PPR qua (0,800)-(400,800) layer "CAP"
```

---

## 4. Vẽ Line (`draw_lines`)

### Mô tả
Vẽ một hoặc nhiều **Line** (đoạn thẳng) trong AutoCAD. Hỗ trợ batch — vẽ nhiều line độc lập với layer, color, linetype khác nhau.

### Tham số
| Tham số                  | Kiểu      | Mặc định | Mô tả                                          |
|--------------------------|-----------|----------|-------------------------------------------------|
| lines                    | list[dict]| *(bắt buộc)* | Danh sách line cần vẽ                       |
| create_layer_if_missing  | bool      | True     | Tự tạo layer nếu chưa tồn tại                  |

Mỗi dict trong `lines`:
| Key      | Kiểu              | Mặc định | Mô tả                               |
|----------|--------------------|----------|--------------------------------------|
| start    | [x,y,z] hoặc "x,y,z" | *(bắt buộc)* | Điểm đầu                      |
| end      | [x,y,z] hoặc "x,y,z" | *(bắt buộc)* | Điểm cuối                      |
| layer    | str                | "0"      | Layer                                |
| color    | int \| None        | None     | ACI color index                      |
| linetype | str \| None        | None     | Linetype (VD: "DASHED", "CENTER")    |

### Ví dụ Prompt

**Một đường thẳng:**
```
Vẽ line từ (0,0) đến (1000,0)
```

**Nhiều line với layer và linetype:**
```
Vẽ 2 đường thẳng:
1. Từ (0,0) đến (500,0), layer "WALL", linetype "CONTINUOUS"
2. Từ (0,100) đến (500,100), layer "CENTER", linetype "CENTER"
```

**Vẽ hình chữ nhật bằng 4 line:**
```
Vẽ 4 line tạo hình chữ nhật: (0,0)→(1000,0), (1000,0)→(1000,600), (1000,600)→(0,600), (0,600)→(0,0), layer "WALL"
```

---

## 5. Vẽ Polyline (`draw_polylines`)

### Mô tả
Vẽ một hoặc nhiều **Polyline** (LWPolyline) trong AutoCAD. Hỗ trợ đóng kín (closed), cung tròn (bulge), lineweight, width.

### Tham số
| Tham số                  | Kiểu      | Mặc định | Mô tả                        |
|--------------------------|-----------|----------|-------------------------------|
| polylines                | list[dict]| *(bắt buộc)* | Danh sách polyline       |
| create_layer_if_missing  | bool      | True     | Tự tạo layer nếu chưa tồn tại|

Mỗi dict trong `polylines`:
| Key        | Kiểu                         | Mặc định | Mô tả                               |
|------------|-------------------------------|----------|--------------------------------------|
| vertices   | [[x,y],...] hoặc ["x,y",...] | *(bắt buộc)* | Danh sách đỉnh (ít nhất 2)    |
| closed     | bool                         | False    | Đóng kín polyline                    |
| layer      | str                          | "0"      | Layer                                |
| color      | int \| None                  | None     | ACI color index                      |
| linetype   | str \| None                  | None     | Linetype                             |
| lineweight | int \| None                  | None     | Lineweight                           |
| width      | float \| None                | None     | Global width                         |
| bulges     | {vertex_index: bulge_value}  | None     | Cung tròn (tùy chọn)                |

### Ví dụ Prompt

**Polyline mở:**
```
Vẽ polyline qua các điểm (0,0), (500,0), (500,300), (800,300)
```

**Polyline đóng kín (hình chữ nhật):**
```
Vẽ polyline đóng kín qua 4 điểm: (0,0), (1000,0), (1000,600), (0,600), layer "WALL"
```

**Polyline với cung tròn:**
```
Vẽ polyline qua (0,0), (500,0), (500,500), (0,500), đóng kín, có cung tròn tại đỉnh thứ 2 với bulge=0.5
```

---

## 6. Tạo Text / MText (`draw_texts`)

### Mô tả
Tạo một hoặc nhiều **Text** (đơn dòng) hoặc **MText** (nhiều dòng) trong AutoCAD.

### Tham số
| Tham số                  | Kiểu      | Mặc định | Mô tả                        |
|--------------------------|-----------|----------|-------------------------------|
| texts                    | list[dict]| *(bắt buộc)* | Danh sách text cần tạo   |
| create_layer_if_missing  | bool      | True     | Tự tạo layer nếu chưa tồn tại|

Mỗi dict trong `texts`:
| Key              | Kiểu                     | Mặc định | Mô tả                            |
|------------------|---------------------------|----------|-----------------------------------|
| content          | str                       | *(bắt buộc)* | Nội dung text                |
| insertion_point  | [x,y,z] hoặc "x,y"      | *(bắt buộc)* | Tọa độ chèn                 |
| height           | float                     | 2.5      | Chiều cao text                    |
| type             | "text" \| "mtext"         | "text"   | Loại text                         |
| width            | float \| None             | None     | Chiều rộng MText (chỉ cho mtext)  |
| layer            | str                       | "0"      | Layer                             |
| color            | int \| None               | None     | ACI color index                   |
| rotation         | float                     | 0.0      | Góc xoay (radian)                 |
| style            | str \| None               | None     | Text style name                   |

### Ví dụ Prompt

**Text đơn giản:**
```
Tạo text "ỐNG THOÁT D100" tại vị trí (500, 200), chiều cao 5
```

**Nhiều text cùng lúc:**
```
Tạo 3 text:
1. "PHÒNG KHÁCH" tại (1000, 500), cao 8, layer "TEXT"
2. "PHÒNG NGỦ" tại (3000, 500), cao 8, layer "TEXT"
3. "WC" tại (5000, 500), cao 6, layer "TEXT"
```

**MText nhiều dòng:**
```
Tạo MText "Ghi chú:\nĐường ống cấp nước DN25\nÁp lực 3 bar" tại (0, -200), chiều cao 3, chiều rộng 500, layer "NOTE"
```

---

## 7. Chèn Block (`insert_block_by_name`)

### Mô tả
Chèn **cùng 1 block** tại nhiều điểm trong AutoCAD. Tối ưu khi cần chèn lặp lại một block.

### Tham số
| Tham số                  | Kiểu        | Mặc định | Mô tả                              |
|--------------------------|-------------|----------|-------------------------------------|
| block_name               | str         | *(bắt buộc)* | Tên block hoặc đường dẫn .dwg  |
| insertion_points         | list[str]   | *(bắt buộc)* | Danh sách tọa độ chèn          |
| x_scale                  | float       | 1.0      | Tỉ lệ X                            |
| y_scale                  | float       | 1.0      | Tỉ lệ Y                            |
| z_scale                  | float       | 1.0      | Tỉ lệ Z                            |
| rotation                 | float       | 0.0      | Góc xoay (radian)                   |
| layer                    | str         | "0"      | Layer                               |
| create_layer_if_missing  | bool        | True     | Tự tạo layer nếu chưa tồn tại      |

### Ví dụ Prompt

**Chèn 1 block:**
```
Chèn block "VAN_KHOA" tại vị trí (500, 300)
```

**Chèn cùng 1 block tại nhiều điểm:**
```
Chèn block "SPRINKLER" tại 4 vị trí: (0,0), (3000,0), (6000,0), (9000,0), layer "PCCC"
```

**Chèn block có scale và xoay:**
```
Chèn block "PUMP" tại (1000, 2000), scale X=2, Y=2, xoay 90 độ (1.5708 radian), layer "EQUIP"
```

---

## 8. Chèn nhiều Block khác tên (`insert_multi_blocks`)

### Mô tả
Chèn **nhiều block khác tên** vào AutoCAD cùng lúc. Mỗi block có tên, vị trí, scale, rotation, layer riêng.

### Tham số
| Tham số                  | Kiểu        | Mặc định | Mô tả                     |
|--------------------------|-------------|----------|----------------------------|
| blocks                   | list[dict]  | *(bắt buộc)* | Danh sách block        |
| create_layer_if_missing  | bool        | True     | Tự tạo layer nếu chưa tồn tại |

Mỗi dict trong `blocks`:
| Key        | Kiểu   | Mặc định | Mô tả                           |
|------------|--------|----------|----------------------------------|
| block_name | str    | *(bắt buộc)* | Tên block hoặc đường dẫn .dwg |
| point      | "x,y,z"| *(bắt buộc)* | Tọa độ chèn                  |
| x_scale    | float  | 1.0      | Tỉ lệ X                         |
| y_scale    | float  | 1.0      | Tỉ lệ Y                         |
| z_scale    | float  | 1.0      | Tỉ lệ Z                         |
| rotation   | float  | 0.0      | Góc xoay (radian)                |
| layer      | str    | "0"      | Layer                            |

### Ví dụ Prompt

```
Chèn các block sau:
1. Block "VAN_KHOA" tại (500, 300), layer "VALVE"
2. Block "TEE" tại (1000, 300), layer "FITTING"
3. Block "ELBOW_90" tại (1000, 800), layer "FITTING"
```

---

## 9. Chèn Block có Dynamic Properties (`insert_block_with_dynamic_properties`)

### Mô tả
Chèn block có hỗ trợ **Dynamic Properties** (khối động) vào AutoCAD. Cho phép thiết lập các thuộc tính động như kích thước, hình dạng, visibility state...

### Tham số
| Tham số                  | Kiểu        | Mặc định | Mô tả                     |
|--------------------------|-------------|----------|----------------------------|
| blocks                   | list[dict]  | *(bắt buộc)* | Danh sách block        |
| create_layer_if_missing  | bool        | True     | Tự tạo layer nếu chưa tồn tại |

Mỗi dict trong `blocks`:
| Key                 | Kiểu          | Mặc định | Mô tả                                |
|---------------------|---------------|----------|---------------------------------------|
| block_name          | str           | *(bắt buộc)* | Tên block                         |
| insertion_point     | [x, y, z]     | *(bắt buộc)* | Tọa độ chèn (z mặc định 0)       |
| x_scale             | float         | 1.0      | Tỉ lệ X                              |
| y_scale             | float         | 1.0      | Tỉ lệ Y                              |
| z_scale             | float         | 1.0      | Tỉ lệ Z                              |
| rotation            | float         | 0.0      | Góc xoay (radian)                     |
| layer               | str           | "0"      | Layer                                 |
| dynamic_properties  | {name: value} | None     | Dynamic Properties cần thiết lập      |

### Ví dụ Prompt

**Chèn block động với thuộc tính:**
```
Chèn block "DOOR" tại (1000, 0) với dynamic properties: Width=900, Height=2100, layer "ARCH"
```

**Nhiều block động cùng lúc:**
```
Chèn 2 block động:
1. Block "WINDOW" tại (500, 0), dynamic properties: Width=1200, Height=1500, layer "ARCH"
2. Block "WINDOW" tại (2000, 0), dynamic properties: Width=600, Height=1500, layer "ARCH"
```

---

## 10. Đổi Layer đối tượng (`change_object_layer`)

### Mô tả
Thay đổi **Layer** của một hoặc nhiều đối tượng AutoCAD theo ObjectID. Tự tạo layer mới nếu chưa tồn tại.

### Tham số
| Tham số                  | Kiểu        | Mặc định | Mô tả                               |
|--------------------------|-------------|----------|--------------------------------------|
| object_ids               | list[int]   | *(bắt buộc)* | Danh sách ObjectID               |
| new_layer                | str         | *(bắt buộc)* | Tên layer mới                    |
| create_layer_if_missing  | bool        | True     | Tự tạo layer nếu chưa tồn tại       |

### Ví dụ Prompt

**Đổi layer 1 đối tượng:**
```
Đổi layer của đối tượng ID 2130051320 sang layer "PIPE-WATER"
```

**Đổi layer nhiều đối tượng:**
```
Chuyển các đối tượng ID 2130051320, 2130051456, 2130051892 sang layer "THOAT-NUOC"
```

> **Lưu ý:** Cần có ObjectID. Dùng các tool Get Data (như `get_all_selected_info`) để lấy ObjectID trước.

---

## 11. Di chuyển đối tượng (`move_objects`)

### Mô tả
Di chuyển một hoặc nhiều đối tượng AutoCAD theo **vector dịch chuyển**.

### Tham số
| Tham số       | Kiểu        | Mô tả                                           |
|---------------|-------------|--------------------------------------------------|
| object_ids    | list[int]   | Danh sách ObjectID cần di chuyển                 |
| displacement  | list[float] | Vector dịch chuyển [dx, dy, dz], VD: [500, 300, 0] |

### Ví dụ Prompt

```
Di chuyển đối tượng ID 2130051320 sang phải 500 đơn vị và lên trên 300 đơn vị
```

```
Move các đối tượng ID 2130051320, 2130051456 theo vector (1000, 0, 0)
```

---

## 12. Sao chép đối tượng (`copy_objects`)

### Mô tả
Sao chép một hoặc nhiều đối tượng AutoCAD theo **vector dịch chuyển**. Đối tượng gốc giữ nguyên, tạo bản sao tại vị trí mới.

### Tham số
| Tham số       | Kiểu        | Mô tả                                              |
|---------------|-------------|-----------------------------------------------------|
| object_ids    | list[int]   | Danh sách ObjectID cần sao chép                    |
| displacement  | list[float] | Vector dịch chuyển [dx, dy, dz], VD: [1000, 0, 0]  |

### Ví dụ Prompt

```
Copy đối tượng ID 2130051320 sang phải 2000 đơn vị
```

```
Sao chép các đối tượng ID 2130051320, 2130051456 theo vector (0, 3000, 0) — dịch lên trên 3000
```

---

## 13. Xóa đối tượng (`delete_objects`)

### Mô tả
Xóa một hoặc nhiều đối tượng AutoCAD theo ObjectID.

### Tham số
| Tham số    | Kiểu      | Mô tả                            |
|------------|-----------|-----------------------------------|
| object_ids | list[int] | Danh sách ObjectID cần xóa       |

### Ví dụ Prompt

```
Xóa đối tượng có ID 2130051320
```

```
Xóa các đối tượng ID: 2130051320, 2130051456, 2130051892
```

> **Cảnh báo:** Thao tác xóa không thể hoàn tác qua MCP. Hãy chắc chắn trước khi xóa.

---

## Mẹo viết Prompt hiệu quả

### 1. Cung cấp đủ thông tin
AI cần biết: **tọa độ**, **kích thước** (mlscale/height/scale), và **layer**. Nếu không cung cấp, AI sẽ hỏi lại hoặc dùng giá trị mặc định.

### 2. Dùng batch khi vẽ nhiều
Thay vì yêu cầu vẽ từng đối tượng một, hãy gom tất cả vào 1 prompt:
```
❌ Vẽ line từ (0,0) đến (100,0)
❌ Vẽ line từ (100,0) đến (100,50)
❌ Vẽ line từ (100,50) đến (0,50)

✅ Vẽ 3 line: (0,0)→(100,0), (100,0)→(100,50), (100,50)→(0,50), layer "WALL"
```

### 3. Kết hợp Get Data + Drawing
Workflow thường gặp:
1. Dùng tool Get Data để lấy thông tin đối tượng hiện có (ObjectID, tọa độ)
2. Dùng tool Drawing để vẽ/sửa/di chuyển dựa trên dữ liệu đó

```
Bước 1: "Lấy thông tin tất cả đối tượng trên layer PIPE"
Bước 2: "Di chuyển tất cả đối tượng đó sang phải 500 đơn vị"
```

### 4. Chỉ định rõ loại đối tượng
- **Ống thoát nước** → `draw_mline_von` (VON)
- **Ống cấp nước** → `draw_mline_von_ppr` (VON_PPR)
- **Đoạn thẳng đơn** → `draw_lines`
- **Đường đa tuyến** → `draw_polylines`
- **Chữ/nhãn** → `draw_texts`
- **Thiết bị/phụ kiện** → `insert_block_by_name` hoặc `insert_block_with_dynamic_properties`

### 5. Quy ước tọa độ
- Định dạng: `(x, y)` hoặc `(x, y, z)` — z mặc định = 0
- Đơn vị tính: mm (theo bản vẽ AutoCAD)
- Mũi tên `→` để chỉ hướng vẽ liên tiếp

---

## Ví dụ Prompt thực tế tổng hợp

### Vẽ hệ thống ống cho 1 phòng WC
```
Vẽ hệ ống nước phòng WC:
1. Ống thoát nước (VON): (0,0) → (0,1500) → (800,1500) → (800,0), mlscale=100, layer "THOAT"
2. Ống cấp nước (VON_PPR): (100,0) → (100,1400), mlscale=25, layer "CAP"
3. Ống cấp nước (VON_PPR): (700,0) → (700,1400), mlscale=25, layer "CAP"
```

### Chèn thiết bị vệ sinh
```
Chèn các block thiết bị:
1. Block "TOILET" tại (400, 1200), layer "SANITARY"
2. Block "LAVABO" tại (100, 800), layer "SANITARY"
3. Block "SHOWER" tại (700, 800), layer "SANITARY"
```
### Ghi chú bản vẽ
```
Tạo các text ghi chú:
1. "PHÒNG WC" tại (400, 1600), chiều cao 10, layer "TEXT-NOTE"
2. "DN100" tại (400, 750), chiều cao 5, layer "TEXT-PIPE"
3. "DN25" tại (100, 700), chiều cao 4, layer "TEXT-PIPE"
```