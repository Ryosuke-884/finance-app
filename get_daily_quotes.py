import os
import requests
import csv
from dotenv import load_dotenv

# .envから環境変数を読み込む
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)
ID_TOKEN = os.getenv("JQUANTS_ID_TOKEN")

if not ID_TOKEN:
    print(".envにJQUANTS_ID_TOKENが設定されていません。まずはjquants_get_token.pyで取得してください。")
    exit(1)

# 取得日付
date = "2023-12-29"

# 保存先ディレクトリ
save_dir = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(save_dir, exist_ok=True)

# APIエンドポイント
url = f"https://api.jquants.com/v1/prices/daily_quotes?date={date}"
headers = {
    "Authorization": f"Bearer {ID_TOKEN}"
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    data = response.json()
    quotes = data.get("daily_quotes", [])
    if not quotes:
        print("データがありません。")
        exit(0)
    # CSVに保存
    csv_file = os.path.join(save_dir, f"daily_quotes_{date}.csv")
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=quotes[0].keys())
        writer.writeheader()
        writer.writerows(quotes)
    print(f"{csv_file} に保存しました。")
else:
    print(f"APIリクエストに失敗しました: {response.status_code}")
    print(response.text) 