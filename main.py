import os
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

مهمتك الرد على استفسارات المراجعين باحترافية وفق القواعد الصارمة التالية:

1. سياسة الاتصال الهاتفي (مهم جداً):
- يُمنع منعاً باتاً اختلاق أي رقم هاتف من عندك (مثل 0770 أو غيرها).
- إذا سأل المراجع "أقدر اتصل؟" أو طلب التواصل هاتفياً:
  وضّح له بلطف أن الاتصال الهاتفي والتواصل المباشر مع الأستاذ المحامي متاح ومرحب به، ولكنه يتم حصراً *بعد تثبيت الحجز وتحديد الموعد ودفع الأجور إلكترونياً عبر الاستمارة الإلكترونية*، وذلك لترتيب جدول أعمال الأستاذ المحامي ولضمان دراسة ملف القضية قبل الاتصال.

2. سياسة الأجور والأتعاب المرنة:
- تبدأ أجور الاستشارات القانونية في المكتب من 75,000 دينار عراقي لقضايا الأحوال الشخصية والمسائل البسيطة، ومن 150,000 دينار لقضايا الشركات والعقود، ومن 300,000 دينار للمسائل الجزائية.
- وضّح للمراجع أن الأجر النهائي الدقيق يُحدد من قبل الأستاذ المحامي بناءً على دراسة موضوع القضية وساعات العمل المطلوبة، وذلك بعد ملء الاستمارة الإلكترونية.
- الدفع إلكتروني حصراً ومسبقاً لتثبيت الحجز بعد تحديد الأجر (عبر الحسابات والمحافظ الإلكترونية)، ولا يُقبل الدفع النقدي (الكاش) نهائياً حتى داخل مقر المكتب.
- الموقع: بغداد - زيونة - قرب دار الأزياء العراقية.
- أوقات المقابلات المكتبية: (2:00 ظهراً - 4:00 عصراً) بحجز مسبق من الأحد إلى الخميس.
- رابط الاستمارة الإلكترونية: https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform

3. قاعدة لغة الرد والتنبيه القانوني (صارم جداً):
- إذا كتب المراجع بأي لغة أجنبية (مثل الإنجليزية)، يجب أن يكون الرد الموجه له بالكامل (من أول كلمة إلى آخر كلمة) بتلك اللغة حصراً.
- يُمنع منعاً باتاً كتابة التنبيه القانوني باللغة العربية للعميل الأجنبي! يجب ترجمته كاملاً إلى نفس لغة العميل.
- نص التنبيه بالإنجليزية يكون هكذا تماماً:
  "⚖️ Notice: This is an automated preliminary guidance and does not constitute formal legal advice. To confirm a consultation appointment, review the case file, and determine the final fees, please apply via the electronic form: https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
- (ولأي لغة أخرى مثل البنغالية أو الكردية ترجم نفس المعنى لتلك اللغة).

4. تنسيق المخرجات الإلزامي:
ضع ردك بالشكل التالي بدقة:
[REPLY_START]
(نص الرد الموجه للمراجع بلغته هو فقط شاملاً التنبيه المترجم والرابط، بدون أي حرف عربي إذا كان المراجع أجنبياً)
[REPLY_END]

إذا كانت رسالة المراجع بأي لغة غير العربية، أضف هذا القسم في النهاية:
[ADMIN_TRANS_START]
ترجمة سؤال المراجع: (شرح عربي موجز لمطلب العميل)
ترجمة الرد المرسل إليه: (شرح عربي موجز لما تم إخباره به)
[ADMIN_TRANS_END]
(إذا كانت رسالة المراجع بالعربية، لا تضع قسم ADMIN_TRANS_START نهائياً).
"""

def get_active_groq_model():
    """الكاشف التلقائي لأفضل موديل نشط في حساب Groq"""
    url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    preferred = [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "qwen/qwen3.6-27b",
        "llama-3.1-8b-instant"
    ]
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            active_ids = [m["id"] for m in res.json().get("data", [])]
            for pref in preferred:
                if pref in active_ids:
                    return pref
            for mid in active_ids:
                m_low = mid.lower()
                if not any(x in m_low for x in ["whisper", "orpheus", "guard", "embed", "tts"]):
                    return mid
    except Exception:
        pass
    return "openai/gpt-oss-20b"

def generate_ai_response(user_query):
    if not GROQ_API_KEY:
        return None, "مفتاح GROQ_API_KEY غير مضاف في متغيرات Render"

    active_model = get_active_groq_model()
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": active_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.1
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        if response.status_code == 200:
            raw_text = response.json()["choices"][0]["message"]["content"]
            return raw_text, None
        else:
            return None, f"{active_model}: {response.text}"
    except Exception as e:
        return None, str(e)

def parse_ai_response(raw_text, user_query):
    is_arabic = bool(re.search(r'[\u0600-\u06FF]', user_query))
    client_reply = ""
    admin_trans = ""

    # استخراج رد الزبون بدقة
    if "[REPLY_START]" in raw_text and "[REPLY_END]" in raw_text:
        client_reply = raw_text.split("[REPLY_START]")[1].split("[REPLY_END]")[0].strip()
    elif "[ADMIN_TRANS_START]" in raw_text:
        client_reply = raw_text.split("[ADMIN_TRANS_START]")[0].strip()
    else:
        client_reply = raw_text.strip()

    # استخراج ترجمة الإدارة
    if "[ADMIN_TRANS_START]" in raw_text and "[ADMIN_TRANS_END]" in raw_text:
        admin_trans = raw_text.split("[ADMIN_TRANS_START]")[1].split("[ADMIN_TRANS_END]")[0].strip()
    elif "[ADMIN_TRANS_START]" in raw_text:
        admin_trans = raw_text.split("[ADMIN_TRANS_START]")[1].strip()

    # تنظيف أي وسوم متبقية
    for tag in ["[REPLY_START]", "[REPLY_END]", "[ADMIN_TRANS_START]", "[ADMIN_TRANS_END]"]:
        client_reply = client_reply.replace(tag, "").strip()
        if admin_trans:
            admin_trans = admin_trans.replace(tag, "").strip()

    # فلتر أمان برمجي صارم لحذف أي أرقام هواتف قد يخترعها الذكاء
    client_reply = re.sub(r'(\*?07[3-9]\d{1}[- ]?\d{6,8}\*?|\*?1234567[^\s]*\*?)', '', client_reply).strip()

    # إذا كان المستفسر أجنبياً وظهر تنبيه بالعربي بالخطأ في الرد، نقوم بإزالته أو استبداله بالإنجليزية
    if not is_arabic and "تنبيه:" in client_reply:
        notice_en = (
            "⚖️ Notice: This is an automated preliminary guidance and does not constitute formal legal advice. "
            "To confirm a consultation appointment, review the case file, and determine the final fees, "
            "please apply via the electronic booking form: "
            "https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
        )
        client_reply = re.sub(r'⚖️\s*تنبيه.*', notice_en, client_reply, flags=re.DOTALL).strip()

    return client_reply, admin_trans, is_arabic

def process_message_background(message):
    try:
        from_number = message["from"]
        msg_type = message.get("type")

        # 1. الرسائل المكتوبة
        if msg_type == "text":
            user_query = message["text"]["body"]
            print(f"Message from {from_number}: {user_query}", flush=True)

            raw_ai_reply, error_detail = generate_ai_response(user_query)

            if not raw_ai_reply:
                client_reply = (
                    "أهلاً بك في مكتب المحامي علي كاظم الهاشمي.\n"
                    "يرجى حجز موعد استشارة رسمي عبر الرابط التالي لتحديد الأتعاب وتثبيت الموعد:\n"
                    "https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
                )
                admin_trans = None
                is_arabic = True
                if error_detail and from_number != ADMIN_PHONE:
                    send_whatsapp_message(ADMIN_PHONE, f"⚠️ *خطأ فني في الذكاء الاصطناعي:*\n{error_detail}")
            else:
                client_reply, admin_trans, is_arabic = parse_ai_response(raw_ai_reply, user_query)

            # إرسال الرد للمراجع بلغته الصافية فقط
            send_whatsapp_message(from_number, client_reply)

            # إرسال التقرير الإداري المترجم للأستاذ المحامي على هاتفه الشخصي
            if from_number != ADMIN_PHONE:
                if is_arabic or not admin_trans:
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
                        f"🌐 *التقرير المترجم للأستاذ المحامي:*\n{admin_trans}"
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
        print(f"Error in background: {e}", flush=True)

@app.route("/", methods=["GET"])
def home():
    return "Legal Assistant Bot is Active (Groq Perfected)", 200

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
