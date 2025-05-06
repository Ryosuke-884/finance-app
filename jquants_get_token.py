import os
import requests
from dotenv import load_dotenv

# .envから環境変数を読み込む
load_dotenv()
MAILADDRESS = os.getenv("JQUANTS_ID")
PASSWORD = os.getenv("JQUANTS_PASSWORD")

# 【1】ユーザー認証でrefreshTokenを取得
auth_url = "https://api.jquants.com/v1/token/auth_user"
auth_payload = {
    "mailaddress": MAILADDRESS,
    "password": PASSWORD
}
auth_res = requests.post(auth_url, json=auth_payload)
auth_data = auth_res.json()
refresh_token = auth_data.get("refreshToken")

if not refresh_token:
    print("refreshTokenの取得に失敗しました:", auth_data)
    exit(1)

print("refreshToken:", refresh_token)

# 【2】refreshTokenでIDトークンを取得
refresh_url = f"https://api.jquants.com/v1/token/auth_refresh?refreshtoken={refresh_token}"
refresh_res = requests.post(refresh_url)
refresh_data = refresh_res.json()
id_token = refresh_data.get("idToken")

if not id_token:
    print("idTokenの取得に失敗しました:", refresh_data)
    exit(1)

print("idToken:", id_token) 