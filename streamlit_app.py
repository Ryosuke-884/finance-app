import os
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime, timedelta
import plotly.graph_objects as go
import openai

# .envから環境変数を読み込む
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# REFRESH_TOKENからIDトークンを自動取得
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
def get_id_token(refresh_token):
    url = "https://api.jquants.com/v1/token/auth_refresh"
    headers = {"Content-Type": "application/json"}
    data = {"refreshToken": refresh_token}
    res = requests.post(url, json=data, headers=headers)
    if res.status_code == 200:
        return res.json().get("idToken")
    else:
        st.error(f"IDトークン取得失敗: {res.status_code} {res.text}")
        return None

if REFRESH_TOKEN:
    ID_TOKEN = get_id_token(REFRESH_TOKEN)
else:
    ID_TOKEN = os.getenv("JQUANTS_ID_TOKEN")

GPT_TOKEN = os.getenv("GPT_TOKEN")
client = openai.OpenAI(api_key=GPT_TOKEN)

st.title("J-Quants 財務・株価グラフ可視化アプリ")

# ページ全体の横幅をさらに広げるカスタムCSS
st.markdown(
    """
    <style>
    .main .block-container, .block-container {
        max-width: 2400px !important;
        width: 99vw !important;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 上場企業リスト取得
@st.cache_data(show_spinner=False)
def get_company_list(id_token):
    url = "https://api.jquants.com/v1/listed/info"
    headers = {"Authorization": f"Bearer {id_token}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return pd.DataFrame(res.json().get("info", []))
    return pd.DataFrame([])

company_df = get_company_list(ID_TOKEN)

# 検索UIを1つに統一し、会社名または証券コードどちらでも検索できるように
def code_to_str4(code):
    # 5桁の証券コード（例: 70200）を4桁（7020）で表示
    try:
        code_int = int(float(str(code).strip()))
        if code_int % 10 == 0 and len(str(code_int)) == 5:
            return str(code_int)[:-1]
        return str(code_int)
    except Exception:
        return str(code)

search_input = st.text_input("会社名または証券コードで検索", "トヨタ")
if search_input:
    if search_input.isdigit() and len(search_input) == 4:
        # 入力が4桁なら5桁化して検索
        search_code = str(int(search_input) * 10)
        candidates = company_df[company_df["Code"].astype(str) == search_code]
    else:
        # 会社名部分一致 or 5桁コード部分一致
        candidates = company_df[
            company_df["CompanyName"].str.contains(search_input, na=False) |
            company_df["Code"].astype(str).str.contains(search_input)
        ]
else:
    st.stop()
if len(candidates) == 0:
    st.warning("該当する会社がありません。")
    st.stop()
company_name = st.selectbox(
    "会社を選択",
    candidates["CompanyName"] + "（" + candidates["Code"].apply(code_to_str4) + "）"
)
selected_code = candidates[
    candidates["CompanyName"] + "（" + candidates["Code"].apply(code_to_str4) + "）" == company_name
]["Code"].values[0]

# 財務データ取得
url_st = f"https://api.jquants.com/v1/fins/statements?code={selected_code}"
headers = {"Authorization": f"Bearer {ID_TOKEN}"}
res_st = requests.get(url_st, headers=headers)
if res_st.status_code == 200:
    st_data = res_st.json().get("statements", [])
    if st_data:
        df_st = pd.DataFrame(st_data)
        # API取得元データをアコーディオンで表示
        with st.expander("元データ"):
            st.dataframe(df_st)
        df_st = df_st[df_st["DisclosedDate"].notnull()]
        df_st["DisclosedDate"] = pd.to_datetime(df_st["DisclosedDate"], errors="coerce")
        df_st["CurrentFiscalYearEndDate"] = pd.to_datetime(df_st["CurrentFiscalYearEndDate"], errors="coerce")
        # 四半期・通期ラベル
        def make_label(row):
            year = row["CurrentFiscalYearEndDate"].year if pd.notnull(row["CurrentFiscalYearEndDate"]) else None
            period = row.get("TypeOfCurrentPeriod", "")
            if year is None:
                return None
            if "FY" in period or "通期" in period or period == "":
                return f"{year}/FY"
            q = period.replace("Quarter", "Q") if "Quarter" in period else period
            return f"{year}/{q}" if year and q else None
        df_st["PeriodLabel"] = df_st.apply(make_label, axis=1)
        df_st = df_st.sort_values(["CurrentFiscalYearEndDate", "TypeOfCurrentPeriod"])
        # 年度×四半期の全組み合わせをCurrentFiscalYearEndDateの年で作成
        all_years = sorted(df_st["CurrentFiscalYearEndDate"].dt.year.dropna().unique())
        all_quarters = ["1Q", "2Q", "3Q", "4Q"]
        q_rows = []
        for year in all_years:
            for q in all_quarters:
                if q == "4Q":
                    fy = df_st[(df_st["CurrentFiscalYearEndDate"].dt.year == year) & (df_st["TypeOfCurrentPeriod"].isin(["FY", "通期"]))]
                    q3 = df_st[(df_st["CurrentFiscalYearEndDate"].dt.year == year) & (df_st["TypeOfCurrentPeriod"] == "3Q")]
                    if len(fy) == 1 and len(q3) == 1:
                        fy_net = pd.to_numeric(fy.iloc[0]["NetSales"], errors="coerce")
                        q3_net = pd.to_numeric(q3.iloc[0]["NetSales"], errors="coerce")
                        if pd.isna(fy_net) or pd.isna(q3_net) or (q3_net > fy_net):
                            netsales_single = None
                        else:
                            netsales_single = fy_net - q3_net
                        row = fy.iloc[0].copy()
                        row["TypeOfCurrentPeriod"] = "4Q"
                        row["PeriodLabel"] = f"{year}/4Q"
                        row["NetSales_single"] = netsales_single
                        row["TotalAssets"] = pd.to_numeric(fy.iloc[0]["TotalAssets"], errors="coerce")
                        row["Equity"] = pd.to_numeric(fy.iloc[0]["Equity"], errors="coerce")
                        q_rows.append(row.to_dict())
                    else:
                        q_rows.append({"PeriodLabel": f"{year}/4Q", "TypeOfCurrentPeriod": "4Q"})
                else:
                    qdata = df_st[(df_st["CurrentFiscalYearEndDate"].dt.year == year) & (df_st["TypeOfCurrentPeriod"] == q)]
                    if len(qdata) == 1:
                        row = qdata.iloc[0].copy()
                        row["PeriodLabel"] = f"{year}/{q}"
                        if q == "1Q":
                            row["NetSales_single"] = pd.to_numeric(row["NetSales"], errors="coerce")
                        else:
                            prev_q = all_quarters[all_quarters.index(q)-1]
                            prev_data = df_st[(df_st["CurrentFiscalYearEndDate"].dt.year == year) & (df_st["TypeOfCurrentPeriod"] == prev_q)]
                            if len(prev_data) == 1:
                                row["NetSales_single"] = pd.to_numeric(row["NetSales"], errors="coerce") - pd.to_numeric(prev_data.iloc[0]["NetSales"], errors="coerce")
                            else:
                                row["NetSales_single"] = None
                        row["TotalAssets"] = pd.to_numeric(row["TotalAssets"], errors="coerce") if "TotalAssets" in row else None
                        row["Equity"] = pd.to_numeric(row["Equity"], errors="coerce") if "Equity" in row else None
                        q_rows.append(row.to_dict())
                    else:
                        q_rows.append({"PeriodLabel": f"{year}/{q}", "TypeOfCurrentPeriod": q})
        df_q = pd.DataFrame(q_rows)
        df_q = df_q[df_q["TypeOfCurrentPeriod"].isin(["1Q", "2Q", "3Q", "4Q"])]
        # PeriodLabel順序をCurrentFiscalYearEndDateの年で明示的に指定して時系列順に並べる
        years = sorted(df_q["PeriodLabel"].dropna().apply(lambda x: int(str(x)[:4])).unique())
        period_order = []
        for year in years:
            for q in ["1Q", "2Q", "3Q", "4Q"]:
                period_order.append(f"{year}/{q}")
        df_q["PeriodLabel"] = pd.Categorical(df_q["PeriodLabel"], categories=period_order, ordered=True)
        df_q = df_q.sort_values("PeriodLabel")
        # 実際にデータが存在する最初と最後の四半期を取得
        valid_periods = df_q.dropna(subset=["NetSales_single"])['PeriodLabel'].tolist()
        if valid_periods:
            min_period = valid_periods[0]
            max_period = valid_periods[-1]
            st.info(f"グラフが表示できる期間: {min_period} ～ {max_period}")
        # 四半期表示期間スライサー（データが存在する範囲のみ選択肢にする）
        period_labels = [p for p in df_q["PeriodLabel"].dropna().unique().tolist() if (min_period <= p <= max_period)]
        if len(period_labels) >= 2:
            start_idx, end_idx = st.select_slider(
                "表示する四半期期間を選択",
                options=period_labels,
                value=(period_labels[0], period_labels[-1])
            )
            start_pos = period_labels.index(start_idx)
            end_pos = period_labels.index(end_idx)
            selected_labels = period_labels[start_pos:end_pos+1]
            df_q = df_q[df_q["PeriodLabel"].isin(selected_labels)]
        # 株価も同じ期間で自動的にフィルタ
        if 'df_price' in locals() and len(df_q) > 0:
            min_period = df_q["DisclosedDate"].min()
            max_period = df_q["DisclosedDate"].max()
            df_price = df_price[(df_price["Date"] >= min_period) & (df_price["Date"] <= max_period)]
        # 数値変換（100万円単位）
        df_q["NetSales_single"] = pd.to_numeric(df_q["NetSales_single"], errors="coerce") / 1e6
        df_q["NetSales"] = pd.to_numeric(df_q["NetSales"], errors="coerce") / 1e6
        df_q["OperatingProfit"] = pd.to_numeric(df_q["OperatingProfit"], errors="coerce") / 1e6
        df_q["営業利益率"] = df_q["OperatingProfit"] / df_q["NetSales"] * 100
        df_q["TotalAssets"] = pd.to_numeric(df_q["TotalAssets"], errors="coerce") / 1e6
        df_q["Equity"] = pd.to_numeric(df_q["Equity"], errors="coerce") / 1e6
        df_q["自己資本比率"] = pd.to_numeric(df_q["Equity"], errors="coerce") / pd.to_numeric(df_q["TotalAssets"], errors="coerce") * 100
        # --- 差分計算: 各期間の単体値を追加・グラフ・GPT用データ処理はdf_qが空でない場合のみ ---
        if not df_q.empty:
            df_q = df_q.sort_values("PeriodLabel")
            df_q["OperatingProfit_single"] = df_q["OperatingProfit"].diff().fillna(df_q["OperatingProfit"])
            df_q["TotalAssets_single"] = df_q["TotalAssets"].diff().fillna(df_q["TotalAssets"])
            df_q["Equity_single"] = df_q["Equity"].diff().fillna(df_q["Equity"])
            # 売上高（単体値）・営業利益（単体値）・営業利益率（累積）のグラフ（四半期）
            fig1 = go.Figure()
            fig1.add_trace(go.Bar(x=df_q["PeriodLabel"], y=df_q["NetSales_single"], name="売上高（100万円,単体）", marker_color="royalblue"))
            fig1.add_trace(go.Bar(x=df_q["PeriodLabel"], y=df_q["OperatingProfit_single"], name="営業利益（100万円,単体）", marker_color="orange"))
            fig1.add_trace(go.Scatter(x=df_q["PeriodLabel"], y=df_q["営業利益率"], name="営業利益率(%)", yaxis="y2", mode="lines+markers", marker_color="green"))
            fig1.update_layout(
                title="売上高（単体）・営業利益（単体）・営業利益率の推移（四半期）",
                xaxis_title="四半期",
                yaxis=dict(title="金額（100万円）", zeroline=True, range=[0, max(df_q["NetSales_single"].max(), df_q["OperatingProfit_single"].max(), 1) * 1.1]),
                yaxis2=dict(title="営業利益率(%)", overlaying="y", side="right", range=[0, 100], zeroline=True),
                barmode="group"
            )
            # 総資産・純資産（累積）・自己資本比率（累積）のグラフ（四半期）
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=df_q["PeriodLabel"], y=df_q["TotalAssets"], name="総資産（100万円,累積）", marker_color="royalblue"))
            fig2.add_trace(go.Bar(x=df_q["PeriodLabel"], y=df_q["Equity"], name="純資産（100万円,累積）", marker_color="orange"))
            fig2.add_trace(go.Scatter(x=df_q["PeriodLabel"], y=df_q["自己資本比率"], name="自己資本比率(%)", yaxis="y2", mode="lines+markers", marker_color="green"))
            fig2.update_layout(
                title="総資産（累積）・純資産（累積）・自己資本比率の推移（四半期）",
                xaxis_title="四半期",
                yaxis=dict(title="金額（100万円）"),
                yaxis2=dict(title="自己資本比率(%)", overlaying="y", side="right", range=[0, 100]),
                barmode="group"
            )
        else:
            st.warning("四半期データがありません。")
        # 通期グラフはFY/通期のみ厳密に
        df_fy = df_st[df_st["TypeOfCurrentPeriod"].isin(["FY", "通期"])]
        # 必ず必要な列を計算
        if not df_fy.empty:
            df_fy = df_fy.sort_values("DisclosedDate")
            df_fy["NetSales"] = pd.to_numeric(df_fy["NetSales"], errors="coerce") / 1e6
            df_fy["OperatingProfit"] = pd.to_numeric(df_fy["OperatingProfit"], errors="coerce") / 1e6
            df_fy["営業利益率"] = df_fy["OperatingProfit"] / df_fy["NetSales"] * 100
            df_fy["TotalAssets"] = pd.to_numeric(df_fy["TotalAssets"], errors="coerce") / 1e6
            df_fy["Equity"] = pd.to_numeric(df_fy["Equity"], errors="coerce") / 1e6
            df_fy["自己資本比率"] = df_fy["Equity"] / df_fy["TotalAssets"] * 100
        # 通期グラフ
        fy_options = df_fy["PeriodLabel"].tolist()
        if fy_options:
            # 売上高・営業利益・営業利益率のグラフ（通期）
            fig3 = go.Figure()
            fig3.add_trace(go.Bar(x=df_fy["PeriodLabel"], y=df_fy["NetSales"], name="売上高（100万円）", marker_color="royalblue"))
            fig3.add_trace(go.Bar(x=df_fy["PeriodLabel"], y=df_fy["OperatingProfit"], name="営業利益（100万円）", marker_color="orange"))
            fig3.add_trace(go.Scatter(x=df_fy["PeriodLabel"], y=df_fy["営業利益率"], name="営業利益率(%)", yaxis="y2", mode="lines+markers", marker_color="green"))
            fig3.update_layout(
                title="売上高・営業利益・営業利益率の推移（通期）",
                xaxis_title="通期(FY)",
                yaxis=dict(title="金額（100万円）"),
                yaxis2=dict(title="営業利益率(%)", overlaying="y", side="right", range=[0, 100]),
                barmode="group"
            )
            # 総資産・純資産・自己資本比率のグラフ（通期）
            fig4 = go.Figure()
            fig4.add_trace(go.Bar(x=df_fy["PeriodLabel"], y=df_fy["TotalAssets"], name="総資産（100万円）", marker_color="royalblue"))
            fig4.add_trace(go.Bar(x=df_fy["PeriodLabel"], y=df_fy["Equity"], name="純資産（100万円）", marker_color="orange"))
            fig4.add_trace(go.Scatter(x=df_fy["PeriodLabel"], y=df_fy["自己資本比率"], name="自己資本比率(%)", yaxis="y2", mode="lines+markers", marker_color="green"))
            fig4.update_layout(
                title="総資産・純資産・自己資本比率の推移（通期）",
                xaxis_title="通期(FY)",
                yaxis=dict(title="金額（100万円）"),
                yaxis2=dict(title="自己資本比率(%)", overlaying="y", side="right", range=[0, 100]),
                barmode="group"
            )
    else:
        st.warning("財務データがありません。")
else:
    st.error(f"財務データAPIリクエストに失敗しました: {res_st.status_code}")
    st.text(res_st.text)

# 株価データ取得（参考表示）
url_price = f"https://api.jquants.com/v1/prices/daily_quotes?code={selected_code}"
res_price = requests.get(url_price, headers=headers)
if res_price.status_code == 200:
    price_data = res_price.json().get("daily_quotes", [])
    if price_data:
        df_price = pd.DataFrame(price_data)
        df_price["Date"] = pd.to_datetime(df_price["Date"], errors="coerce")
        # 株価も同じ期間でスライス
        if 'date_range' in locals():
            df_price = df_price[(df_price["Date"] >= pd.to_datetime(date_range[0])) & (df_price["Date"] <= pd.to_datetime(date_range[1]))]
        pass  # グラフ描画は下でまとめて行う
    else:
        st.warning("株価データがありません。")
else:
    st.error(f"株価データAPIリクエストに失敗しました: {res_price.status_code}")
    st.text(res_price.text)

# --- 株価グラフ（最初に表示） ---
if 'df_price' in locals() and not df_price.empty:
    st.markdown("## 株価グラフ")
    # 横軸を日本語表記（年月日）
    df_price_disp = df_price.copy()
    df_price_disp["日付"] = df_price_disp["Date"].dt.strftime("%Y年%m月%d日")
    st.line_chart(df_price_disp.set_index("日付")["Close"])
# --- 四半期グラフ・通期グラフ・インサイトを横並びで ---
if 'fig1' in locals() and 'fig2' in locals():
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("## 四半期グラフ")
        st.plotly_chart(fig1, use_container_width=True, key="main_fig1")
        st.plotly_chart(fig2, use_container_width=True, key="main_fig2")
        # 通期グラフも同じカラムに
        if 'fig3' in locals() and 'fig4' in locals() and fy_options:
            st.markdown("## 通期グラフ")
            st.plotly_chart(fig3, use_container_width=True, key="main_fig3")
            st.plotly_chart(fig4, use_container_width=True, key="main_fig4")
    with col2:
        st.markdown("## ChatGPTインサイト")
        if st.button("ChatGPTでインサイトを生成"):
            company_name = company_name if 'company_name' in locals() else ""
            if len(df_q) > 0:
                period_min = df_q["PeriodLabel"].iloc[0]
                period_max = df_q["PeriodLabel"].iloc[-1]
                accounting_period = f"{period_min}～{period_max}"
            else:
                accounting_period = ""
            gpt_cols = [
                "PeriodLabel",
                "NetSales_single",
                "OperatingProfit_single",
                "TotalAssets",
                "Equity",
                "営業利益率",
                "自己資本比率"
            ]
            gpt_df = df_q[gpt_cols].tail(10)
            fact_text = gpt_df.tail(4).to_markdown(index=False)
            raw_data_text = gpt_df.to_markdown(index=False)
            user_prompt = (
                "# 命令文\n"
                "あなたは証券アナリストです。決算書の内容を読み、業績サマリ、売上高・営業利益・自己資本比率の推移、なぜこのような実績になったのかという推測をするインサイトと質問を投げかけてください。推移やサマリについては実際の実績データを用いて具体的に記述してください。（例：2024/3Qの売上高は100億円でしたが2024/4Qは120億円と1.2倍に成長）質問は会社の経営者の視点でなぜどのようなことを実施したと思われるのか、または実施していくべきかを考えさせるような質問にしてください\n"
                "# 入力文\n"
                f"企業名：{company_name}\n"
                f"会計期間：{accounting_period}\n"
                f"四半期データ：\n{fact_text}\n"
                f"元データ：\n{raw_data_text}\n"
                "# 出力文\n"
                "下記項目とスキーマ、文字数の対応で出力してください。元データには累積のデータが入っているので、各期間中のデータに加工した状態で出力してください。ただの数値報告ではなく推移やインサイトを与える文章にしてね。\n"
                "業績サマリ 箇条書きで400文字以内\n"
                "売上高の推移 箇条書きで200文字以内\n"
                "営業利益の推移 箇条書きで200文字以内\n"
                "自己資本 箇条書きで200文字以内\n"
                "インサイト（質問） 箇条書きで500文字以内\n"
            )
            with st.spinner("ChatGPTがインサイトを生成中..."):
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": user_prompt}],
                    max_tokens=800,
                    temperature=0.5,
                )
                insight = response.choices[0].message.content
            st.markdown("### 💡 ChatGPTによるインサイト")
            st.code(insight, language="json") 