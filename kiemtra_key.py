import os, requests

print("="*60)
print(" CÔNG CỤ CHẨN ĐOÁN VÀ ÉP KEY VILAO (100% CHUẨN) ")
print("="*60)

key = input("👉 Anh hãy DÁN cái Key copy từ web Vilao vào đây rồi ấn Enter: ").strip()

print("\nĐang mang Key sang tận máy chủ Vilao để đối chiếu...")
url = "https://api.vilao.ai/v1/models"
headers = {"Authorization": f"Bearer {key}"}

try:
    res = requests.get(url, headers=headers, timeout=10)
    if res.status_code == 200:
        print("✅ THÀNH CÔNG RỰC RỠ! Chìa khóa này là HÀNG THẬT 100%!")
        
        env_path = ".env"
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        found = False
        for i, line in enumerate(lines):
            if line.startswith("VILAO_API_KEY="):
                lines[i] = 'VILAO_API_KEY="' + key + '"\n'
                found = True
        
        if not found:
            lines.insert(0, 'VILAO_API_KEY="' + key + '"\n')
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
            
        print("🤖 Hệ thống đã tự động ghim chặt cái chìa khóa này vào file .env!")
        print("Anh chỉ cần gõ lại: python app.py là vạn sự hanh thông!")
    else:
        print(f"\n❌ LỖI TỪ VILAO! Hãng từ chối Key này. Mã lỗi: {res.status_code}")
        print("Chi tiết:", res.text)
        print("-> NGUYÊN NHÂN: Chìa khóa anh vừa dán vào là chìa khóa SAI HOẶC BỊ HỎNG!")
        print("-> CÁCH SỬA: Anh lên lại web Vilao, tạo hẳn 1 cái Key mới tinh rồi Copy dán lại nhé!")
except Exception as e:
    print("Lỗi hệ thống mạng:", e)
