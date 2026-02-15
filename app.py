import os
import datetime
import re
import urllib.parse
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# LINE Developersでメモした値を環境変数から読み込む
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# --- あなたが作った解析ロジック ---
def advanced_parse(text):
    now = datetime.datetime.now()
    person_match = re.search(r'([^ ]+?)([さん|様|君|氏])と?', text)
    person = person_match.group(0).replace("と", "") if person_match else ""
    
    target_date = now
    if "明日" in text: target_date += datetime.timedelta(days=1)
    elif "明後日" in text: target_date += datetime.timedelta(days=2)
        
    hour_match = re.search(r'(\d{1,2})時', text)
    hour = int(hour_match.group(1)) if hour_match else 12
    
    location_match = re.search(r'([^ ]+?)で', text)
    location = location_match.group(1) if location_match else ""
    
    clean_title = text
    for kw in ["明日", "明後日", "今日", r'\d{1,2}時', "で", "から", "の", person]:
        clean_title = re.sub(kw, "", clean_title)
    clean_title = clean_title.replace("と", "").strip()
    display_title = f"【{person}】{clean_title}" if person else clean_title
    
    start_dt = target_date.replace(hour=hour, minute=0, second=0)
    end_dt = start_dt + datetime.timedelta(hours=1)
    time_range = f"{start_dt.strftime('%Y%m%dT%H%M%S')}/{end_dt.strftime('%Y%m%dT%H%M%S')}"
    
    params = {"action": "TEMPLATE", "text": display_title, "dates": time_range, "location": location}
    return "https://www.google.com/calendar/render?" + urllib.parse.urlencode(params)

# --- LINEからの通知を受け取る部分 ---
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
    url = advanced_parse(event.message.text)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"カレンダー登録リンクを作成しました！\n\n{url}")
    )

if __name__ == "__main__":
    app.run()
