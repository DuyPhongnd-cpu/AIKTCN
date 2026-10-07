import os
print("="*60)
print(" CÀI ĐẶT API KEY VILAO TRUNG TÂM (V15) ")
print("="*60)
vk = input("1. Nhập API Key VILAO.AI (sk-...): ").strip()
print("\n--- Nhập tên Cụm máy chủ anh đã Subscribe trên Vilao ---")
print("(Nhấn Enter bỏ qua nếu muốn dùng mặc định)")
o = input("2. Tên Model cho nút OPENAI (mặc định gpt-4o-mini): ").strip() or "gpt-4o-mini"
c = input("3. Tên Model cho nút CLAUDE (VD: occ/claude-fable-5): ").strip() or "occ/claude-fable-5"
g = input("4. Tên Model cho nút GEMINI (VD: rge/models/gemini-3.5-flash): ").strip() or "rge/models/gemini-3.5-flash"
d = input("5. Tên Model cho nút DEEPSEEK (VD: deepseek-chat): ").strip() or "deepseek-chat"

lines = [
    f'VILAO_API_KEY="{vk}"',
    f'MODEL_OPENAI="{o}"',
    f'MODEL_DOC="{c}"',
    f'MODEL_CLAUDE="{c}"',
    f'MODEL_GEMINI="{g}"',
    f'MODEL_DEEPSEEK="{d}"'
]

with open(".env", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("\n✅ CÀI ĐẶT THÀNH CÔNG! Hãy gõ lệnh trương trình: python app.py")
