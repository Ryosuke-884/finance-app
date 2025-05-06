import requests

# 書類一覧APIのエンドポイント
url = "https://disclosure.edinet-fsa.go.jp/api/v1/documents.json"

# 書類一覧APIのリクエストパラメータ
params = {
  "date" : "2023-06-12",
  "type" : 2
}

# 書類一覧APIの呼び出し（SSL検証無効化）
res = requests.get(url, params=params, verify=False)

# レスポンス（JSON）の表示
if res.status_code == 200:
    data = res.json()
    results = data.get("results", [])
    print(f"取得件数: {len(results)}")
    for doc in results[:10]:
        print(f"docID: {doc.get('docID')}, edinetCode: {doc.get('edinetCode')}, secCode: {doc.get('secCode')}, filerName: {doc.get('filerName')}, 書類名: {doc.get('docDescription')}, 提出日時: {doc.get('submitDateTime')}")
else:
    print(f"APIリクエストに失敗しました: {res.status_code}")
    print(res.text) 