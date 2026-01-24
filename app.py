import streamlit as st
import os
import google.generativeai as genai
from PIL import Image
import fitz  # PyMuPDF
import pandas as pd
import io
import streamlit as st
import os
import google.generativeai as genai
from PIL import Image
import fitz  # PyMuPDF
import pandas as pd
import io
# from dotenv import load_dotenv # <--- KHI LÊN CLOUD THÌ KHÔNG CẦN DÒNG NÀY NỮA, AI SẼ TỰ HIỂU QUA SECRETS

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="MEP Project AI", page_icon="🔐", layout="wide")

# --- HÀM KIỂM TRA MẬT KHẨU ---
def check_password():
    """Trả về True nếu đăng nhập thành công."""
    
    # Nếu chưa đăng nhập
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    # Giao diện đăng nhập
    st.markdown("## 🔒 Khu vực hạn chế - Chỉ dành cho Kỹ sư MEP")
    password = st.text_input("Nhập mật khẩu truy cập:", type="password")
    
    if st.button("Đăng nhập"):
        # Lấy mật khẩu từ cấu hình bí mật của Streamlit Cloud
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state.password_correct = True
            st.rerun() # Tải lại trang để vào trong
        else:
            st.error("❌ Mật khẩu sai!")
            
    return False

if not check_password():
    st.stop() # Dừng lại, không chạy code bên dưới nếu chưa đăng nhập

# --- PHẦN CODE CŨ CỦA BẠN BẮT ĐẦU TỪ ĐÂY ---
# Thay dòng lấy API Key cũ bằng dòng này (để lấy từ Cloud)
api_key = st.secrets["GOOGLE_API_KEY"] 

if not api_key:
    st.error("❌ Chưa cấu hình API Key trên Cloud.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash') 

# ... (Dán toàn bộ phần code xử lý PDF, Chatbot cũ của bạn vào dưới đây) ...
# --- CẤU HÌNH ---
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

st.set_page_config(page_title="MEP Project Manager AI", page_icon="🏗️", layout="wide")

if not api_key:
    st.error("❌ Chưa tìm thấy API Key. Hãy kiểm tra file .env")
    st.stop()

genai.configure(api_key=api_key)
# Dùng bản Flash 2.5 hoặc Pro mới nhất để có cửa sổ ngữ cảnh lớn (xử lý nhiều ảnh)
model = genai.GenerativeModel('gemini-2.5-flash') 

# --- HÀM HỖ TRỢ ---
def pdf_to_images(pdf_file):
    """Chuyển toàn bộ các trang PDF thành danh sách ảnh"""
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    images = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Zoom x2 để ảnh nét, AI đọc chữ bé tốt hơn
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    return images

def text_to_excel(text_content):
    """Xuất Excel từ dữ liệu AI trả về (Hỗ trợ nhiều bảng)"""
    try:
        csv_data = ""
        if "```csv" in text_content:
            csv_data = text_content.split("```csv")[1].split("```")[0].strip()
        elif "```" in text_content:
            csv_data = text_content.split("```")[1].split("```")[0].strip()
        else:
            return None 

        # Dùng separator | để an toàn
        df = pd.read_csv(io.StringIO(csv_data), sep="|", on_bad_lines='skip')
        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Tong_Hop_BOQ')
        return output.getvalue()
    except:
        return None

# --- QUẢN LÝ TRẠNG THÁI (SESSION STATE) ---
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "uploaded_images" not in st.session_state:
    st.session_state.uploaded_images = []
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- GIAO DIỆN ---
st.title("🏗️ Trợ Lý Dự Án MEP (Đa Trang & Tổng Hợp)")

# 1. Sidebar: Upload & Xem trước
with st.sidebar:
    st.header("📁 Hồ sơ dự án")
    uploaded_file = st.file_uploader("Upload bộ bản vẽ (PDF nhiều trang):", type=["pdf"])
    
    if uploaded_file:
        if not st.session_state.uploaded_images:
            with st.spinner("Đang tách trang & số hóa bản vẽ..."):
                st.session_state.uploaded_images = pdf_to_images(uploaded_file)
                st.success(f"Đã nạp {len(st.session_state.uploaded_images)} trang bản vẽ!")
                
                # Reset chat khi có file mới
                st.session_state.chat_session = None
                st.session_state.messages = []

    # Hiển thị Gallery thu nhỏ
    if st.session_state.uploaded_images:
        st.divider()
        st.write("📖 **Danh sách bản vẽ:**")
        preview_page = st.number_input("Xem trang số:", 1, len(st.session_state.uploaded_images), 1)
        st.image(st.session_state.uploaded_images[preview_page-1], caption=f"Trang {preview_page}", use_container_width=True)

# 2. Logic Khởi tạo Chatbot (Nạp toàn bộ ảnh vào context)
if st.session_state.uploaded_images and st.session_state.chat_session is None:
    
    # SYSTEM PROMPT: KỊCH BẢN CHO AI
    system_instruction = [
        """
        Bạn là Chuyên gia QS (Quantity Surveyor) & Kỹ sư MEP trưởng. 
        Bạn đang nắm trong tay trọn bộ hồ sơ bản vẽ (nhiều trang).
        
        NHIỆM VỤ CỐT LÕI:
        1. BÓC TÁCH TOÀN DIỆN:
           - Thiết bị (Equipment): Bơm, Quạt, Tủ điện, Điều hòa, Van...
           - Ống & Dây (Pipes/Wires): Phân loại kích thước, ước lượng chiều dài.
           - Phụ kiện (Fittings/Accessories): Co, cút, tê, măng sông, đai treo, hộp chia ngả (tự ước lượng theo % đường ống nếu không đếm được, thường là 10-15% ống).
        
        2. TƯ DUY HỆ THỐNG & LIỀN MẠCH:
           - Kết hợp thông tin từ Sơ đồ nguyên lý (thường ở trang đầu) với Mặt bằng thi công (các trang sau) để hiểu rõ hệ thống.
           - Nếu dây đi từ trang này sang trang kia, hãy tính tổng.
        
        3. TỰ TÌM THÔNG SỐ (AUTO-DETECT):
           - Tự đọc các ghi chú (Text Note) để tìm: Cao độ trần (CH), Cao độ lắp đặt (MH).
           - NẾU KHÔNG THẤY: Hãy dừng lại và hỏi người dùng ngay. Tuyệt đối không đoán mò cao độ.
           - Công thức tính trục đứng (Vertical): (Cao độ trần - Cao độ thiết bị) + Dây chờ đầu cuối.
        
        4. ĐỊNH DẠNG XUẤT (BẮT BUỘC):
           - Trả về bảng dữ liệu trong thẻ ```csv ... ```
           - Ngăn cách cột bằng dấu gạch đứng (|).
           - Cột: STT | He_Thong (Dien/Nuoc/HVAC) | Ten_Vat_Tu | Quy_Cach | Don_Vi | So_Luong_Mat_Bang | So_Luong_Truc_Dung | Tong_Cong | Ghi_Chu
        """
    ]
    
    # Nạp toàn bộ ảnh vào danh sách input đầu tiên
    initial_history = system_instruction + st.session_state.uploaded_images + ["Hãy bắt đầu phân tích bộ bản vẽ này. Tổng hợp sơ bộ xem đây là dự án gì?"]
    
    # Khởi tạo Chat
    try:
        st.session_state.chat_session = model.start_chat(history=[
            {
                "role": "user",
                "parts": initial_history
            }
        ])
        
        # Lấy lời chào từ AI
        response = st.session_state.chat_session.send_message("Tóm tắt ngắn gọn quy mô dự án và liệt kê các hệ thống chính bạn nhìn thấy.")
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        
    except Exception as e:
        st.error(f"Lỗi khởi tạo AI (Có thể file quá nặng): {e}")

# 3. Giao diện Chat
if not st.session_state.uploaded_images:
    st.info("👈 Vui lòng upload file PDF ở bên trái.")
    st.stop()

# Hiển thị lịch sử chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and "```csv" in msg["content"]:
            excel_data = text_to_excel(msg["content"])
            if excel_data:
                st.download_button("📥 Tải Bảng Tổng Hợp (.xlsx)", excel_data, "TongHop_MEP.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=str(msg))

# Khu vực nhập liệu
if prompt := st.chat_input("Nhập lệnh (Vd: Bóc tách toàn bộ hệ Điện, trần cao 3.2m..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Đang rà soát toàn bộ các trang bản vẽ..."):
            try:
                # Gửi tin nhắn tiếp theo (AI đã nhớ toàn bộ ảnh từ lúc khởi tạo)
                response = st.session_state.chat_session.send_message(prompt)
                st.markdown(response.text)
                
                # Check bảng Excel
                excel_data = text_to_excel(response.text)
                if excel_data:
                    st.download_button("📥 Tải Bảng Tổng Hợp (.xlsx)", excel_data, "TongHop_MEP.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Lỗi: {e}. (Gợi ý: Nếu file quá nhiều trang, hãy tách nhỏ ra).")

