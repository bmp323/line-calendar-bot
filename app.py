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

    # --- 1. 日付解析 ---
    # 2027年10月15日 or 10月15日
    date_match = re.search(r'((\d{4})年)?(\d{1,2})月(\d{1,2})日', text)
    # 2027/10/15 or 10/15
    slash_match = re.search(r'((\d{4})/)?(\d{1,2})/(\d{1,2})', text)

    if date_match:
        y, m, d = date_match.group(2), int(date_match.group(3)), int(date_match.group(4))
        year = int(y) if y else now.year
        try: target_date = target_date.replace(year=year, month=m, day=d)
        except: pass
    elif slash_match:
        y, m, d = slash_match.group(2), int(slash_match.group(3)), int(slash_match.group(4))
        year = int(y) if y else now.year
        try: target_date = target_date.replace(year=year, month=m, day=d)
        except: pass
    
    # 日付指定がなく、明日・明後日のキーワードがある場合
    elif "明日" in text:
        target_date += datetime.timedelta(days=1)
    elif "明後日" in text:
        target_date += datetime.timedelta(days=2)

    # --- 2. 時間解析とURL生成の分岐 ---
    hour_match = re.search(r'(\d{1,2})時', text)
    
    if hour_match:
        # ■ 時間がある場合：これまで通り時間を指定
        hour = int(hour_match.group(1))
        start_dt = target_date.replace(hour=hour, minute=0, second=0)
        end_dt = start_dt + datetime.timedelta(hours=1)
        # 秒まで指定する形式 (YYYYMMDDThhmmss)
        time_range = f"{start_dt.strftime('%Y%m%dT%H%M%S')}/{end_dt.strftime('%Y%m%dT%H%M%S')}"
    else:
        # ■ 時間がない場合：終日イベントとして扱う
        # 終日の場合、URLの dates は「開始日/終了日」だが、
        # 終了日は「翌日」を指定するのがGoogleカレンダーのルール
        start_dt = target_date
        end_dt = start_dt + datetime.timedelta(days=1)
        # 時間を入れない形式 (YYYYMMDD)
        time_range = f"{start_dt.strftime('%Y%m%d')}/{end_dt.strftime('%Y%m%d')}"

    # --- 3. その他の解析 ---
    location_match = re.search(r'([^ ]+?)で', text)
    location = location_match.group(1) if location_match else ""

    person_match = re.search(r'([^ ]+?)([さん|様|君|氏])と?', text)
    person = person_match.group(0).replace("と", "") if person_match else ""

    # タイトル掃除
    clean_title = text
    remove_keywords = [
        r'((\d{4})年)?(\d{1,2})月(\d{1,2})日', r'((\d{4})/)?(\d{1,2})/(\d{1,2})',
        "明日", "明後日", "今日", r'\d{1,2}時', "で", "から", "の", person
    ]
    for kw in remove_keywords:
        clean_title = re.sub(kw, "", clean_title)
    
    clean_title = clean_title.replace("と", "").strip()
    display_title = f"【{person}】{clean_title}" if person else clean_title

    # URL生成
    params = {
        "action": "TEMPLATE",
        "text": display_title,
        "dates": time_range,
        "location": location,
        "details": f"元メッセージ: {text}"
    }
    
    # 外部ブラウザで開くオプション付き
    return "https://www.google.com/calendar/render?" + urllib.parse.urlencode(params) + "&openExternalBrowser=1"

# LINE設定
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
    try:
        url = advanced_parse(event.message.text)
        reply_msg = f"予定を作成しました！\n\n{url}"
    except Exception as e:
        print(f"Error: {e}")
        reply_msg = "解析できませんでした。"
        
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
