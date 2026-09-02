import os
import json
import re
import threading
import requests
from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "hashimi2026").strip()
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "").strip().strip('"').strip("'")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "").strip().strip('"').strip("'")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip().strip('"').strip("'")

ADMIN_PHONE = "9647702956021"
PROCESSED_MESSAGES = set()

SYSTEM_PROMPT = """
أنت المساعد الآلي الذكي لـ 'مكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية' في بغداد - زيونة.

مهمتك الرد على استفسارات المراجعين بدقة وفق القواعد التالية:

1. حظر تام للأرقام الهاتفية (صارم جداً):
   - يُمنع منعاً باتاً وبأي شكل من الأشكال اختلاق، كتابة، أو ذكر أي رقم هاتف إطلاقاً (مثل أرقام 0770 أو غيرها).
   - إذا طلب المراجع رقماً هاتفياً أو أراد الاتصال، وضّح له بلطف أن المكتب لا يقدم استشارات عبر الاتصال الهاتفي المباشر دون موعد، وأن التواصل وتحديد المواعيد يتم حصراً عبر محادثة الواتساب الحالية وعبر رابط الاستمارة الإلكترونية.

2. مطابقة لغة العميل وسياسة الرد:
   - يجب أن يكون الرد الموجه للعميل مكتوباً حصراً باللغة التي كتب بها العميل (بنغالي، إنجليزي، كردي، تركي، عربي... إلخ).
   - التنبيه القانوني الإلزامي يترجم لنفس لغة العميل في نهاية رده:
     "⚖️ تنبيه: هذا توجيه أولي صادر آلياً ولا يعد استشارة رسمية. لتثبيت موعد استشارة ودراسة الملف وتحديد الأتعاب، يرجى التقديم عبر الاستمارة الإلكترونية: https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"

3. قواعد الأسعار والخدمات:
   - تبدأ أجور الاستشارات القانونية في المكتب من 75,000 دينار عراقي لقضايا الأحوال الشخصية والمسائل البسيطة، ومن 150,000 دينار لقضايا الشركات والعقود، ومن 300,000 دينار للمسائل الجزائية.
   - وضح للمراجع أن الأجر النهائي الدقيق يحدده الأستاذ المحامي بناءً على حجم القضية ودراسة الملف وساعات العمل، وذلك بعد ملء الاستمارة الإلكترونية.
   - الدفع إلكتروني حصراً ومسبقاً لتثبيت الحجز بعد تحديد الأجر، ولا يُقبل الدفع النقدي (الكاش) نهائياً حتى داخل المكتب.
   - الموقع: بغداد - زيونة - قرب دار الأزياء العراقية.
   - أوقات العمل: من الأحد إلى الخميس؛ المقابلات المكتبية (2:00 ظ - 4:00 ع) بحجز مسبق.
   - رابط الاستمارة: https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform

4. صيغة الإخراج الإلزامية (JSON ONLY):
يجب أن يكون ردك بصيغة JSON فقط متضمناً المفاتيح الثلاثة التالية بدقة دون أي نص خارجي:
{
  "client_reply": "نص الرد الكامل الموجه للمراجع بلغته هو فقط شاملاً التنبيه والرابط دون أي كلمة عربية (إلا إذا كان المراجع يتحدث العربية)",
  "query_translation_ar": "ترجمة عربية دقيقة لسؤال العميل ومطلبه",
  "reply_translation_ar": "ترجمة عربية موجزة لما أخبرت به العميل (الأسعار، الموقع، حجز الاستمارة...)"
}
"""

def generate_ai_response(user_query):
    if not GROQ_API_KEY:
        return None, None, None, "مفتاح GROQ_API_KEY غير مضاف في متغيرات Render"

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    models_to_try = [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768"
    ]

    last_err = ""
    for model_name in models_to_try:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"رسالة العميل هي: {user_query}\nأخرج النتيجة بصيغة JSON حصراً."}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            if response.status_code == 200:
                raw_content = response.json()["choices"][0]["message"]["content"]
                parsed = json.loads(raw_content)
                
                client_text = parsed.get("client_reply", "").strip()
                query_ar = parsed.get("query_translation_ar", "").strip()
                reply_ar = parsed.get("reply_translation_ar", "").strip()

                return client_text, query_ar, reply_ar, None
            else:
                last_err = f"{model_name}: {response.text}"
        except Exception as e:
            last_err = str(e)

    return None, None, None, f"Groq Error: {last_err}"

def process_message_background(message):
    try:
        from_number = message["from"]
        msg_type = message.get("type")

        # 1. الرسائل المكتوبة
        if msg_type == "text":
            user_query = message["text"]["body"]
            print(f"Message from {from_number}: {user_query}", flush=True)

            client_reply, query_ar, reply_ar, error_detail = generate_ai_response(user_query)

            if not client_reply:
                client_reply = (
                    "أهلاً بك في مكتب المحامي علي كاظم الهاشمي.\n"
                    "يرجى حجز موعد استشارة رسمي عبر الرابط التالي لتحديد الأتعاب وتثبيت الموعد:\n"
                    "https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
                )
                if error_detail and from_number != ADMIN_PHONE:
                    send_whatsapp_message(ADMIN_PHONE, f"⚠️ *خطأ فني في الذكاء الاصطناعي:*\n{error_detail}")

            # إرسال الرد للعميل بلغته الأصلية فقط
            send_whatsapp_message(from_number, client_reply)

            # إرسال التقرير الإداري المترجم للأستاذ المحامي على هاتفه الشخصي
            if from_number != ADMIN_PHONE:
                is_arabic = bool(re.search(r'[\u0600-\u06FF]', user_query))
                
                if is_arabic:
                    admin_msg = (
                        f"📩 *استفسار جديد*\n"
                        f"👤 *المستفسر:* +{from_number}\n"
                        f"💬 *السؤال:* {user_query}\n\n"
                        f"🤖 *الرد:* {client_reply}"
                    )
                else:
                    admin_msg = (
                        f"📩 *استفسار وارد (بلغة أجنبية)*\n"
                        f"👤 *المستفسر:* +{from_number}\n\n"
                        f"💬 *نص المراجع الأصلي:*\n{user_query}\n\n"
                        f"🌐 *ترجمة سؤاله للعربية:*\n{query_ar}\n\n"
                        f"📝 *ترجمة الرد المرسل إليه:*\n{reply_ar}"
                    )
                
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
    return "Legal Assistant Bot is Active (Groq JSON Powered)", 200

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
