import requests

# =====================================================================
# CẤU HÌNH THÔNG TIN KẾT NỐI FACEBOOK MESSENGER (FILE RIÊNG)
# =====================================================================
PAGE_ACCESS_TOKEN = "EAAOOBY49IP0BRn7rSMnP6FDkinxZChUm5ufSfXjjK5miagO43ddSfQIBgfYjN6ZCc4suYSW2EPf3GaRGZBhZCLsQQHkX7HOn6wTz0UZBiINi3WEIHKgrviFUmyfkil6QHTbT39VDFEMQ2OUVrp92CbaByDlsFmramTV88tKxEfJWXbMAsfPQUwo9GsZAxbfOrbmfAEBAZDZD"

# Danh sách ID thật của cả nhóm
LIST_USER_PSID = [
    "36106495948995752",
    "27028300910159101"
]

def send_messenger_alert_to_all(message_text):
    """Hàm duyệt qua danh sách LIST_USER_PSID để tự động bắn tin nhắn về từng máy"""
    url = f"https://graph.facebook.com/v21.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    print(f"\n🚀 [MESSENGER SERVICE] Đang gửi thông báo đến {len(LIST_USER_PSID)} người dùng ngầm...")
    
    for psid in LIST_USER_PSID:
        payload = {
            "recipient": {"id": str(psid).strip()},
            "message": {"text": message_text},
            # "messaging_type": "MESSAGE_TAG",
            # "tag": "CONFIRMED_EVENT_UPDATE"
        }
        try:
            response = requests.post(url, json=payload, timeout=5)
            res_data = response.json()
            if response.status_code == 200:
                print(f"  ✅ [Messenger] Gửi thành công đến ID: {psid}")
            else:
                print(f"  ❌ [Messenger Lỗi API] ID {psid} thất bại: {res_data.get('error', {}).get('message')}")
        except Exception as e:
            print(f"  ❌ Lỗi mạng khi gửi đến ID {psid}: {e}")