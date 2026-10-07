import os

print("="*65)
print(" CÔNG CỤ THIẾT LẬP API KEY CHUẨN 100% CHO AI DUY PHONG (V9)")
print("="*65)
print("Hướng dẫn: Copy Key của anh và Paste (hoặc chuột phải) vào đây.")
print("Nếu AI nào chưa có Key, anh cứ ấn phím Enter để bỏ qua nhé.\n")

openai = input("1. Nhập API Key OPENAI (bắt đầu bằng sk-...): ").strip()
claude = input("2. Nhập API Key CLAUDE (bắt đầu bằng sk-ant-...): ").strip()
gemini = input("3. Nhập API Key GEMINI (bắt đầu bằng AIza...): ").strip()
deepseek = input("4. Nhập API Key DEEPSEEK (bắt đầu bằng sk-...): ").strip()

content = f"""OPENAI_API_KEY="{openai}"
OPENAI_MODEL="gpt-4o"
GEMINI_API_KEY="{gemini}"
GEMINI_MODEL="gemini-1.5-pro"
DEEPSEEK_API_KEY="{deepseek}"
DEEPSEEK_MODEL="deepseek-chat"
CLAUDE_API_KEY="{claude}"
CLAUDE_MODEL="claude-3-5-sonnet-20240620"
TELEGRAM_BOT_TOKEN="{TELEGRAM_BOT_TOKEN_HOLDER}"
TELEGRAM_ADMIN_CHAT_ID="7594576473"
PORT=5050
"""

# Chỉnh lại TOKEN rỗng mặc định để script Python không bị lỗi chưa định nghĩa
content = content.replace("{TELEGRAM_BOT_TOKEN_HOLDER}", "")

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
with open(env_path, "w", encoding="utf-8") as f:
    f.write(content)

print("\n" + "="*65)
print("✅ [THÀNH CÔNG] HỆ THỐNG ĐÃ TẠO FILE .env CHUẨN SẠCH 100%!")
print("="*65)
print("Bây giờ anh hãy gõ lệnh khởi động Web như bình thường:")
print("👉 python app.py")
print("="*65)
