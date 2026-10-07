import os, requests

# Đoạn này máy sẽ tự chui vào file .env của anh để lấy Key Gemini
key = ""
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY"):
                key = line.split("=")[1].strip().strip('"').strip("'")
                break

if not key or key == "***":
    print("Lỗi: Không tìm thấy Key Gemini trong file .env!")
else:
    print("Đang quét kho lưu trữ của Google...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            print("\n==== DANH SÁCH MÁY CHỦ GOOGLE CẤP CHO TÀI KHOẢN CỦA ANH ====")
            for m in res.json().get("models", []):
                name = m.get("name", "")
                # Chỉ lọc các kho hỗ trợ tạo chữ (generateContent)
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    print(f"👉 Tên kho anh cần copy là: {name.replace('models/', '')}")
            print("================================================================")
        else:
            print("Lỗi từ Google: Account của anh bị chặn hoặc Key sai!")
            print(res.text)
    except Exception as e:
        print("Lỗi mạng:", e)
