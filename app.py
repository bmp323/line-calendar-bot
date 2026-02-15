import os
import datetime
import re
import urllib.parse
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# LINE Developersの設定値
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

def advanced_parse(text):
    now = datetime.datetime.now()
    target_date = now  # デフォルトは今日

    # --- 1. 具体的な日付の解析 (2027年10月15日 や 10月15日) ---
    # パターン: (西暦年)? 月 日
    date_match = re.search(r'((\d{4})年)?(\d{1,2})月(\d{1,2})日', text)
    # パターン: (西暦年)? / / (2027/10/15 や 10/15)
    slash_match = re.search(r'((\d{4})/)?(\d{1,2})/(\d{1,2})', text)

    if date_match:
        year_str = date_match.group(2)
        month = int(date_match.group(3))
        day = int(date_match.group(4))
        year = int(year_str) if year_str else now.year
        # 年またぎの配慮（例: 今が12月で「1月」と言われたら来年と解釈するなど）は今回は割愛し、指定がなければ今年のまま
        try:
            target_date = target_date.replace(year=year, month=month, day=day)
        except ValueError:
            pass # 存在しない日付などは無視して今日にする
            
    elif slash_match:
        year_str = slash_match.group(2)
        month = int(slash_match.group(3))
        day = int(slash_match.group(4))
        year = int(year_str) if year_str else now.year
        try:
            target_date = target_date.replace(year=year, month=month, day=day)
        except ValueError:
            pass

    # --- 2. 相対日付の解析 (明日・明後日) ---
    # 具体的な日付指定がなかった場合のみ判定
    elif "明日" in text:
        target_date += datetime.timedelta(days=1)
    elif "明後日" in text:
        target_date += datetime.timedelta(days=2)

    # --- 3. その他の要素解析 ---
    # 人物
    person_match = re.search(r'([^ ]+?)([さん|様|君|氏])と?', text)
    person = person_match.group(0).replace("と", "") if person_match else ""

    # 時間
    hour_match = re.search(r'(\d{1,2})時', text)
    hour = int(hour_match.group(1)) if hour_match else 12 # 指定なければ12時
    
    # 場所
    location_match = re.search(r'([^ ]+?)で', text)
    location = location_match.group(1) if location_match else ""

    # タイトル掃除（日付や時間をタイトルから消す）
    clean_title = text
    # 消すワードリスト
    remove_keywords = [
        r'((\d{4})年)?(\d{1,2})月(\d{1,2})日', # 日付(日本語)
        r'((\d{4})/)?(\d{1,2})/(\d{1,2})',    # 日付(スラッシュ)
        "明日", "明後日", "今日", 
        r'\d{1,2}時', "で", "から", "の", person
    ]
    for kw in remove_keywords:
        clean_title = re.sub(kw, "", clean_title)
    
    clean_title = clean_title.replace("と", "").strip()
    display_title = f"【{person}】{clean_title}" if person else clean_title

    # URL生成
    start_dt = target_date.replace(hour=hour, minute=0, second=0)
    end_dt = start_dt + datetime.timedelta(hours=1)
    time_range = f"{start_dt.strftime('%Y%m%dT%H%M%S')}/{end_dt.strftime('%Y%m%dT%H%M%S')}"
    
    params = {
        "action": "TEMPLATE",
        "text": display_title,
        "dates": time_range,
        "location": location,
        "details": f"元メッセージ: {text}"
    }
        # URL生成（末尾にLINE用のパラメータを追加）
    base_url = "https://www.google.com/calendar/render?" + urllib.parse.urlencode(params)
    return base_url + "&openExternalBrowser=1"


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # エラーで止まらないようにtry-exceptで囲む
    try:
        url = advanced_parse(event.message.text)
        reply_msg = f"予定を作成しました！\n\n{url}"
    except Exception as e:
        reply_msg = "ごめんなさい、うまく解析できませんでした。"
        print(e)
        
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_msg)
    )

if __name__ == "__main__":
    # Renderなどの環境でポートを正しく受け取るための設定
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
