import streamlit as st
import os
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF
import pandas as pd
import io

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="MEP AI Locator", page_icon="🎯", layout="wide")

# --- HÀM KIỂM TRA MẬT KHẨU ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct:
        return True
    
    st.markdown("## 🔒 Đăng nhập hệ thống MEP AI")
    password = st.text_input("Mật khẩu:", type="password")
    if st.button("Truy cập"):
        # Lấy pass từ Secrets hoặc file .env nếu chạy local
        try:
            true_pass = st.secrets["APP_PASSWORD"]
        except:
            true_pass = "123456" # Pass mặc định khi chạy local
            
        if password == true_pass:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Sai mật khẩu!")
    return False

if not check_password():
    st.stop()

# --- CẤU HÌNH AI ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
except:
    # Fallback cho chạy local
    api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    st.error("❌ Thiếu API Key.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash') 

# --- HÀM XỬ LÝ ẢNH & VẼ LƯỚI (CORE FEATURE) ---
def add_grid_to_image(image, rows=8, cols=8):
    """Vẽ lưới tọa độ lên ảnh để AI định vị"""
    draw = ImageDraw.Draw(image)
    width, height = image.size
    step_x = width / cols
    step_y = height / rows
    
    # Vẽ lưới màu đỏ
    for i in range(cols + 1):
        line_x = i * step_x
        draw.line([(line_x, 0), (line_x, height)], fill="red", width=3)
        # Đánh số cột (1, 2, 3...)
        if i < cols:
            draw.text((line_x + 10, 10), str(i + 1), fill="red", font_size=40)

    for i in range(rows + 1):
        line_y = i * step_y
        draw.line([(0, line_y), (width, line_y)], fill="red", width=3)
        # Đánh chữ hàng (A, B, C...)
        if i < rows:
            label = chr(65 + i) # ASCII A=65
            draw.text((10, line_y + 10), label, fill="red", font_size=40)
            
    return image

def pdf_to_images_with_grid(pdf_file):
    """Chuyển PDF -> Ảnh -> Vẽ Lưới"""
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    images = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # Zoom x2 cho nét
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Thêm lưới ngay lập tức
        img_with_grid = add_grid_to_image(img)
        images.append(img_with_grid)
    return images

def text_to_excel(text_content):
    try:
        csv_data = ""
        if "```csv" in text_content:
            csv_data = text_content.split("```csv")[1].split("```")[0].strip()
        elif "```" in text_content:
            csv_data = text_content.split("```")[1].split("```")[0].strip()
        else:
            return None 

        df = pd.read_csv(io.StringIO(csv_data), sep="|", on_bad_lines='skip')
        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='BOQ_Dinh_Vi')
        return output.getvalue()
    except:
        return None

# --- SESSION STATE ---
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "uploaded_images" not in st.session_state:
    st.session_state.uploaded_images = []
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- GIAO DIỆN CHÍNH ---
st.title("🎯 MEP AI Locator (Bóc tách có định vị)")

with st.sidebar:
    st.header("📁 Hồ sơ bản vẽ")
    uploaded_file = st.file_uploader("Upload PDF:", type=["pdf"])
    
    if uploaded_file:
        if not st.session_state.uploaded_images:
            with st.spinner("Đang số hóa và tạo lưới tọa độ..."):
                st.session_state.uploaded_images = pdf_to_images_with_grid(uploaded_file)
                st.success(f"Đã xử lý {len(st.session_state.uploaded_images)} trang!")
                st.session_state.chat_session = None
                st.session_state.messages = []

    if st.session_state.uploaded_images:
        st.divider()
        st.write("👀 **Xem trước bản vẽ có lưới:**")
        p_idx = st.number_input("Trang:", 1, len(st.session_state.uploaded_images), 1)
        st.image(st.session_state.uploaded_images[p_idx-1], caption=f"Trang {p_idx} (Lưới A-H, 1-8)", use_container_width=True)

# --- LOGIC CHATBOT ---
if st.session_state.uploaded_images and st.session_state.chat_session is None:
    
    system_instruction = [
        """
        Bạn là Chuyên gia QS MEP. Bạn đang xem các bản vẽ ĐÃ ĐƯỢC KẺ LƯỚI TỌA ĐỘ (Grid A-H, 1-8).
        
        NHIỆM VỤ QUAN TRỌNG NHẤT: TRACEABILITY (TRUY XUẤT NGUỒN GỐC)
        Khi bạn đếm hoặc đo bóc bất kỳ thiết bị nào, bạn BẮT BUỘC phải chỉ ra nó nằm ở ô lưới nào.
        
        QUY TẮC BÓC TÁCH:
        1. Tìm thiết bị/ống/dây.
        2. Xác định vị trí lưới (Ví dụ: Tủ điện nằm ở ô A1, Bơm nằm ở ô C4-C5).
        3. Nếu số lượng nhiều (ví dụ đèn), hãy liệt kê vùng (Ví dụ: Các ô A2, A3, B2).
        4. Tự tìm cao độ trong ghi chú text. Nếu không thấy -> Hỏi người dùng.
        
        ĐỊNH DẠNG XUẤT BẢNG (Bắt buộc dùng dấu |):
        Trả về bảng trong thẻ ```csv ... ``` với các cột:
        STT | Ten_Vat_Tu | Quy_Cach | Don_Vi | So_Luong | Vi_Tri_Tren_Ban_Ve (Grid) | Ghi_Chu
        
        Ví dụ cột Vi_Tri: "A1, B2" hoặc "Rải rác từ C1 đến C4".
        """
    ]
    
    init_history = system_instruction + st.session_state.uploaded_images + ["Bắt đầu phân tích. Hãy xác nhận bạn đã nhìn thấy lưới tọa độ màu đỏ?"]
    
    try:
        st.session_state.chat_session = model.start_chat(history=[{"role": "user", "parts": init_history}])
        response = st.session_state.chat_session.send_message("Tóm tắt nội dung các trang và xác nhận lưới tọa độ.")
        st.session_state.messages.append({"role": "assistant", "content": response.text})
    except Exception as e:
        st.error(f"Lỗi khởi tạo: {e}")

if not st.session_state.uploaded_images:
    st.info("👈 Upload PDF bên trái để bắt đầu.")
    st.stop()

# Hiển thị Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and "```csv" in msg["content"]:
            excel_data = text_to_excel(msg["content"])
            if excel_data:
                st.download_button("📥 Tải Excel (Có Vị Trí Grid)", excel_data, "BOQ_Locator.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=str(msg))

if prompt := st.chat_input("Ví dụ: Đếm số lượng đèn Downlight và chỉ rõ vị trí..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Đang soi từng ô lưới..."):
            try:
                response = st.session_state.chat_session.send_message(prompt)
                st.markdown(response.text)
                
                excel_data = text_to_excel(response.text)
                if excel_data:
                    st.download_button("📥 Tải Excel (Có Vị Trí)", excel_data, "BOQ_Final.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Lỗi: {e}")
