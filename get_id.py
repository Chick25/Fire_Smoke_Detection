import requests

# Dán mã Token lấy từ nút "Tạo" màu xám ở trang cấu hình Facebook của bạn vào đây
PAGE_ACCESS_TOKEN = "EAAOOBY49IP0BRn7rSMnP6FDkinxZChUm5ufSfXjjK5miagO43ddSfQIBgfYjN6ZCc4suYSW2EPf3GaRGZBhZCLsQQHkX7HOn6wTz0UZBiINi3WEIHKgrviFUmyfkil6QHTbT39VDFEMQ2OUVrp92CbaByDlsFmramTV88tKxEfJWXbMAsfPQUwo9GsZAxbfOrbmfAEBAZDZD"

url = f"https://graph.facebook.com/v21.0/me/conversations?fields=participants&access_token={PAGE_ACCESS_TOKEN}"

try:
    response = requests.get(url)
    data = response.json()
    
    if response.status_code == 200 and "data" in data:
        print("\n=== KẾT QUẢ DÒ TÌM ID NGƯỜI DÙNG ===")
        conversations = data["data"]
        if not conversations:
            print("❌ Không tìm thấy cuộc hội thoại nào. Bạn hãy lấy nick Yến Huỳnh nhắn thêm vài tin vào Page nhé!")
        for conv in conversations:
            for participant in conv.get("participants", {}).get("data", []):
                print(f"👤 Tên Facebook: {participant.get('name')}")
                print(f"🆔 Số USER_PSID chuẩn: {participant.get('id')}")
                print("-" * 40)
    else:
        print(f"❌ Lỗi API: {data}")
except Exception as e:
    print(f"❌ Lỗi kết nối: {e}")