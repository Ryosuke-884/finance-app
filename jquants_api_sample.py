import requests
import os

# J-Quants APIのエンドポイント例（財務データ）
BASE_URL = "https://api.jquants.com/v1"

# 事前にJ-Quantsの公式サイトでAPIトークンを取得し、環境変数にセットしておく
# 例: export JQUANTS_API_TOKEN=あなたのAPIトークン
API_TOKEN = os.environ.get("JQUANTS_API_TOKEN")

if not API_TOKEN:
    raise Exception("J-QuantsのAPIトークンが設定されていません。環境変数 'JQUANTS_API_TOKEN' をセットしてください。")

headers = {
    "Authorization": f"Bearer {API_TOKEN}"
}

# 例：トヨタ自動車（証券コード7203）の財務データを取得
code = "7203"
url = f"{BASE_URL}/listed/info?code={code}"

response = requests.get(url, headers=headers)

if response.status_code == 200:
    data = response.json()
    print(data)
else:
    print(f"APIリクエストに失敗しました: {response.status_code}")
    print(response.text) 