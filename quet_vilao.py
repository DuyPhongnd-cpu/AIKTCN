import os, requests

print("="*60)
print(" ĐANG QUÉT KHO MÁY CHỦ CỦA VILAO.AI...")
print("="*60)

key = ""
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip().lstrip('\ufeff')
            if line.startswith("OPENAI_API_KEY"):
                key = line.split("=")[1].strip().strip('"').strip("'")
                break

if not key or key == "***":
    print("Lỗi: Anh chưa nhập Key Vilao!")
else:
    url = "https://api.vilao.ai/v1/models"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            print("\n✅ VILAO CẤP QUYỀN CHO TÀI KHOẢN 50K CỦA ANH DÙNG CÁC KHO NÀY:")
            data = res.json().get("data", [])
            for m in data:
                print(f"👉 {m.get('id')}")
            print("\n=======================================================")
            print("Anh bôi đen copy 1 cái tên ở trên,")
            print("dán đè vào OPENAI_MODEL trong .env nhé!")
        else:
            print("Lỗi từ Vilao:", res.text)
    except Exception as e:
        print("Lỗi mạng:", e)
