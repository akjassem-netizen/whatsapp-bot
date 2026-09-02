import os
import threading
import requests
from flask import Flask, request
from google import genai

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "hashimi2026").strip()
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "").strip().strip('"').strip("'")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "").strip().strip('"').strip("'")
raw_gemini_key = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_KEY = raw_gemini_key.strip().strip('"').strip("'") if raw_gemini_key else None

ADMIN_PHONE = "9647702956021"
PROCESSED_MESSAGES = set()

if GEMINI_API_KEY:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    ai_client = genai.Client()

SYSTEM_PROMPT = """
أنت المساعد الآلي الذكي لـ 'مكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية' في بغداد - زيونة.

قواعد الإجابة الإلزامية:
1. الإيجاز والتركيز المباشر: أجب عن سؤال المستفسر مباشرة في الجملة الأولى بدون مقدمات إنشائية.
   - إذا سأل عن الأسعار: اذكر سعر الاستشارة التي تخص طلبه مباشرة دون سرد تفاصيل المكتب، مع رابط الاستمارة.
   - إذا سأل عن الموقع: اذكر الموقع مباشرة.
   - إذا سأل عن الدوام: اذكر الأوقات مباشرة.
2. لائحة الأجور الرسمية للاستشارات:
   - استشارات الأحوال الشخصية (كالطلاق، النفقة، الحضانة): 75,000 دينار عراقي.
   - الاستشارات المدنية والشركات والعقود: 150,000 دينار عراقي.
   - الاستشارات الجزائية والجنائية: 300,000 دينار عراقي.
3. سياسة الدفع الصارمة (إلكتروني فقط):
   - الدفع إلكتروني حصراً ومسبقاً لجميع الاستشارات عبر وسائل الدفع المحلية المعتمدة أو روابط الدفع لتثبيت الموعد.
   - لا يُقبل الدفع النقدي (الكاش) نهائياً، حتى لو كانت الاستشارة حضورية داخل مقر المكتب.
4. رابط حجز المواعيد وتثبيتها:
   https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform
5. أوقات العمل والموقع:
   - العنوان: بغداد - زيونة - قرب دار الأزياء العراقية.
   - الدوام: من الأحد إلى الخميس. الفترة الصباحية (8:00 ص - 2:00 ظ) للمحاكم، والمقابلات المكتبية (2:00 ظ - 4:00 ع) بحجز مسبق.
6. يُمنع منعاً باتاً صياغة لوائح دعاوى أو تقديم شروحات إجرائية تفصيلية عبر الشات؛ بل وجّه المستفسر لحجز موعد استشارة رسمي مع الأستاذ المحامي.

نص التنبيه الختامي (يوضع في نهاية كل رد بسطرين فقط):
"⚖️ تنبيه: هذا توجيه أولي صادر آلياً ولا يعد استشارة رسمية. لتثبيت موعد استشارة ودراسة الملف رسمياً، يرجى التقديم عبر الاستمارة الإلكترونية: https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
"""

def generate_ai_response(user_query):
    full_prompt = f"{SYSTEM_PROMPT}\n\nرسالة المستفسر: {user_query}"
    # استدعاء الموديلات السريعة مباشرة وتفادي الفحص البطيء
    for candidate in ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
        try:
            res = ai_client.models.generate_content(model=candidate, contents=full_prompt)
            if res and res.text:
                return res.text
        except Exception as e:
            continue
    return None

def process_message_background(message):
    try:
        from_number = message["from"]
        msg_type = message.get("type")

        # 1. الرسائل النصية
        if msg_type == "text":
            user_query = message["text"]["body"]
            print(f"Processing text from {from_number}: {user_query}", flush=True)

            ai_reply = generate_ai_response(user_query)
            if not ai_reply:
                ai_reply = (
                    "أهلاً بك في مكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية.\n"
                    "نعتذر عن تعذر المعالجة الآلية حالياً. يتم تدقيق الرسائل من قبل المكتب تباعاً، أو يمكنك حجز موعد عبر الاستمارة:\n"
                    "https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
                )

            send_whatsapp_message(from_number, ai_reply)

            if from_number != ADMIN_PHONE:
                admin_msg = f"📩 *استفسار جديد*\n👤 *المستفسر:* +{from_number}\n💬 *النص:* {user_query}\n\n🤖 *الرد:*\n{ai_reply}"
                send_whatsapp_message(ADMIN_PHONE, admin_msg)

        # 2. الصور والمستندات
        elif msg_type in ["image", "document"]:
            media_id = message[msg_type].get("id")
            caption = message[msg_type].get("caption", "")
            doc_title = "صورة" if msg_type == "image" else "مستند PDF"

            receipt = (
                f"✅ تم استلام الـ ({doc_title}) بنجاح.\n"
                "سيتم تدقيق الأوراق وعرضها على الأستاذ المحامي وفق جدول أعماله في المحاكم.\n\n"
                "لحجز وتثبيت موعد رسمي (الدفع إلكتروني مسبقاً):\n"
                "https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
            )
            send_whatsapp_message(from_number, receipt)

            if from_number != ADMIN_PHONE:
                notice = f"📎 *وصل {doc_title} جديد للمكتب*\n👤 *من المراجع:* +{from_number}\n📝 {caption}"
                sent = send_whatsapp_media(ADMIN_PHONE, msg_type, media_id, notice)
                if not sent:
                    send_whatsapp_message(ADMIN_PHONE, notice)

        # 3. البصمات الصوتية
        elif msg_type in ["audio", "voice"]:
            audio_obj = message.get("audio") or message.get("voice") or {}
            media_id = audio_obj.get("id")

            audio_receipt = (
                "🎙️ تم استلام التسجيل الصوتي بنجاح.\n"
                "سيتم الاستماع إليه وتدقيقه من قبل الأستاذ المحامي وفق جدول أعماله.\n\n"
                "لتثبيت موعد استشارة رسمي (الدفع إلكتروني مسبقاً عبر الاستمارة):\n"
                "https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
            )
            send_whatsapp_message(from_number, audio_receipt)

            if from_number != ADMIN_PHONE and media_id:
                notice = f"🎙️ *تسجيل صوتي وارد من مستفسر*\n👤 *الرقم:* +{from_number}"
                send_whatsapp_message(ADMIN_PHONE, notice)
                send_whatsapp_media(ADMIN_PHONE, "audio", media_id)

    except Exception as e:
        print(f"Error in background processing: {e}", flush=True)

@app.route("/", methods=["GET"])
def home():
    return "Legal Assistant Bot is Active", 200

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Verification failed", 403

    if request.method == "POST":
        data = request.get_json()

        if (
            data.get("entry")
            and data["entry"][0].get("changes")
            and data["entry"][0]["changes"][0].get("value")
            and "messages" in data["entry"][0]["changes"][0]["value"]
        ):
            message = data["entry"][0]["changes"][0]["value"]["messages"][0]
            msg_id = message.get("id")

            # منع التكرار
            if msg_id in PROCESSED_MESSAGES:
                return "EVENT_RECEIVED", 200
            PROCESSED_MESSAGES.add(msg_id)
            if len(PROCESSED_MESSAGES) > 1000:
                PROCESSED_MESSAGES.clear()

            # تشغيل المعالجة في الخلفية والرد على واتساب فوراً دون انتظار
            thread = threading.Thread(target=process_message_background, args=(message,))
            thread.daemon = True
            thread.start()

        return "EVENT_RECEIVED", 200

def send_whatsapp_message(to_number, text):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }
    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

def send_whatsapp_media(to_number, media_type, media_id, caption=""):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": media_type,
        media_type: {"id": media_id}
    }
    if caption and media_type != "audio":
        payload[media_type]["caption"] = caption

    res = requests.post(url, headers=headers, json=payload)
    return res.status_code == 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
