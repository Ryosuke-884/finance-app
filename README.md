# J-Quants API サンプル

## セットアップ手順

1. 仮想環境(venv)の作成

```bash
python3 -m venv venv
```

2. 仮想環境の有効化

- Mac/Linux:
  ```bash
  source venv/bin/activate
  ```
- Windows:
  ```cmd
  venv\Scripts\activate
  ```

3. 必要なパッケージのインストール

```bash
pip install -r requirements.txt
```

4. J-Quants APIトークンの取得・設定

- J-Quants公式サイトでAPIトークンを取得
- 環境変数にセット
  ```bash
  export JQUANTS_API_TOKEN=あなたのAPIトークン
  ```

5. サンプルコードの実行

```bash
python jquants_api_sample.py
```

---

## ファイル構成例

- jquants_api_sample.py ... J-Quants APIサンプルコード
- requirements.txt ... 必要なパッケージ
- README.md ... セットアップ手順 