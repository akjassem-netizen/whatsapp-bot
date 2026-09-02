import os
import threading
import requests
from flask import Flask, request
from google import genai

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "hashimi2026").strip()
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "").strip().strip('"').strip("'")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "").strip().strip('"').strip("'")
ADMIN_PHONE = "9647702956021"
PROCESSED_MESSAGES = set()

SYSTEM_PROMPT = """
أنت المساعد الآلي الذكي لـ 'مكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية' في بغداد - زيونة.

قواعد اللغة والردود الإلزامية:
1. مطابقة لغة المستفسر بدقة تامة:
   - يجب الرد حصراً بنفس اللغة التي كتب بها المراجع (إذا كتب بالكردية أجب بالكردية تماماً، إذا كتب بالإنجليزية أجب بالإنجليزية، إذا كتب بالفرنسية أو التركية أجب بها، وإذا كتب بالعربية أجب بالعربية).
   - ترجم نص التنبيه الختامي إلى نفس لغة المراجع.

قواعد الاستشارة الإلزامية:
1. الإيجاز والتركيز المباشر: أجب عن السؤال مباشرة في أول سطر دون مقدمات إنشائية.
   - إذا سأل عن الأسعار: اذكر سعر الاستشارة التي تخص طلبه مباشرة مع رابط الاستمارة.
   - إذا سأل عن الموقع: بغداد - زيونة - قرب دار الأزياء العراقية.
   - إذا سأل عن الدوام: من الأحد إلى الخميس؛ الفترة الصباحية للمحاكم، والمقابلات المكتبية (2:00 ظ - 4:00 ع) بحجز مسبق.
2. لائحة الأجور الرسمية للاستشارات:
   - استشارات الأحوال الشخصية (طلاق، نفقة، حضانة): 75,000 دينار عراقي (حوالي 55 دولار أمريكي).
   - الاستشارات المدنية والشركات والعقود: 150,000 دينار عراقي (حوالي 110 دولار أمريكي).
   - الاستشارات الجزائية والجنائية: 300,000 دينار عراقي (حوالي 220 دولار أمريكي).
3. سياسة الدفع:
   - الدفع إلكتروني حصراً ومسبقاً لجميع الاستشارات لتثبيت الحجز، ولا يُقبل الدفع النقدي (الكاش) نهائياً حتى داخل مقر المكتب.
4. رابط حجز المواعيد:
   https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform
5. يُمنع صياغة لوائح دعاوى تفصيلية عبر الشات؛ بل وجّه المراجع لحجز موعد استشارة رسمي مع الأستاذ المحامي.

التنبيه الختامي الإلزامي (يترجم لنفس لغة المراجع في نهاية كل رسالة):
"⚖️ تنبيه: هذا توجيه أولي صادر آلياً ولا يعد استشارة رسمية. لتثبيت موعد استشارة ودراسة الملف رسمياً، يرجى التقديم عبر الاستمارة الإلكترونية: https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
"""

def get_gemini_client():
    api_key = (
        os.environ.get("GEMINI_API_KEY") 
        or os.environ.get("GOOGLE_API_KEY") 
        or os.environ.get("API_KEY") 
        or ""
    ).strip().strip('"').strip("'")
    
    if not api_key:
        return None, "مفتاح GEMINI_API_KEY غير مضاف في إعدادات Render"
    
    try:
        client = genai.Client(api_key=api_key)
        return client, None
    except Exception as e:
        return None, f"خطأ في تشغيل العميل: {e}"

def generate_ai_response(user_query):
    client, err = get_gemini_client()
    if err:
        return None, err
        
    full_prompt = f"{SYSTEM_PROMPT}\n\nرسالة المستفسر: {user_query}"
    last_err = ""
    
    # استخدام الموديل المعتمد رسميًا حسب سجل السيرفر
    candidate_models = ["gemini-3.6-flash", "gemini-3.6-pro", "gemini-3-flash"]
    
    for model_name in candidate_models:
        try:
            res = client.models.generate_content(model=model_name, contents=full_prompt)
            if res and res.text:
                return res.text, None
        except Exception as e:
            last_err = f"{model_name}: {e}"
            print(f"Error with {model_name}: {e}", flush=True)

    # فحص احتياطي ديناميكي في حال تغير مسمى الموديل
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            if any(skip in name.lower() for skip in ["embed", "imagen", "veo", "aqa"]):
                continue
            try:
                res = client.models.generate_content(model=name, contents=full_prompt)
                if res and res.text:
                    return res.text, None
            except Exception:
                continue
    except Exception as e:
        last_err = f"Dynamic listing error: {e}"

    return None, last_err

def process_message_background(message):
    try:
        from_number = message["from"]
        msg_type = message.get("type")

        # 1. الرسائل المكتوبة
        if msg_type == "text":
            user_query = message["text"]["body"]
            print(f"Message from {from_number}: {user_query}", flush=True)

            ai_reply, error_detail = generate_ai_response(user_query)
            
            if not ai_reply:
                ai_reply = (
                    "أهلاً بك في مكتب المحامي علي كاظم الهاشمي.\n"
                    "يرجى حجز موعد استشارة رسمي عبر الرابط التالي:\n"
                    "https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
                )
                if error_detail and from_number != ADMIN_PHONE:
                    send_whatsapp_message(ADMIN_PHONE, f"⚠️ *خطأ فني في الذكاء الاصطناعي:*\n{error_detail}")

            send_whatsapp_message(from_number, ai_reply)

            if from_number != ADMIN_PHONE:
                admin_msg = f"📩 *استفسار جديد*\n👤 *المستفسر:* +{from_number}\n💬 *النص:* {user_query}\n\n🤖 *الرد:*\n{ai_reply}"
                send_whatsapp_message(ADMIN_PHONE, admin_msg)

        # 2. الصور والمستندات
        elif msg_type in ["image", "document"]:
            media_id = message[msg_type].get("id")
            caption = message[msg_type].get("caption", "")
            doc_title = "صورة" if msg_type == "image" else "مستند"

            receipt = (
                f"✅ تم استلام الـ ({doc_title}) بنجاح، وسيتم عرضه على الأستاذ المحامي وفق جدول أعماله.\n"
                f"Document/File received successfully and forwarded for legal review.\n\n"
                "لتثبيت موعد استشارة رسمي / To book an official consultation:\n"
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
                "🎙️ تم استلام التسجيل الصوتي بنجاح، وسيتم الاستماع إليه وتدقيقه من قبل الأستاذ المحامي وفق جدول أعماله.\n"
                "Voice note received successfully and forwarded to the attorney for review.\n\n"
                "لتثبيت موعد استشارة رسمي / To book an official consultation:\n"
                "https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
            )
            send_whatsapp_message(from_number, audio_receipt)

            if from_number != ADMIN_PHONE and media_id:
                notice = f"🎙️ *تسجيل صوتي وارد من مستفسر*\n👤 *الرقم:* +{from_number}"
                send_whatsapp_message(ADMIN_PHONE, notice)
                send_whatsapp_media(ADMIN_PHONE, "audio", media_id)

    except Exception as e:
        print(f"Error: {e}", flush=True)

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

            if msg_id in PROCESSED_MESSAGES:
                return "EVENT_RECEIVED", 200
            PROCESSED_MESSAGES.add(msg_id)
            if len(PROCESSED_MESSAGES) > 1000:
                PROCESSED_MESSAGES.clear()

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
