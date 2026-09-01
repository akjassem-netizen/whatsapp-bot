import os
import requests
from flask import Flask, request
from google import genai

app = Flask(__name__)

# استدعاء المتغيرات السرية من إعدادات الاستضافة
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "hashimi2026")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "1359711617217714")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# إعداد عميل الذكاء الاصطناعي
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# التعليمات والضوابط القانونية المشددة ورابط الحجز
SYSTEM_PROMPT = """
أنت المساعد الآلي الذكي لـ 'مكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية' في العراق.

المهام وقواعد الإجابة الصارمة:
1. قدّم إجابات قانونية عامة وموجزة جداً ومختصرة، دون الدخول في تفاصيل فنية دقيقة أو شروحات إجرائية.
2. يُمنع منعاً باتاً شرح كيفية إقامة الدعاوى أو صياغة اللوائح والعرائض القضائية أو تفصيل خطوات التقاضي أمام المحاكم.
3. وضّح للموكل أن الاستفسارات والرسائل يتم الاطلاع عليها وتدقيقها من قبل الأستاذ المحامي شخصياً وفق ما يتناسب مع جدول أعماله والتزاماته في المحاكم.

الموقع وأوقات العمل:
- العنوان: بغداد - زيونة - قرب دار الأزياء العراقية (البحث في خرائط Google: مكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية).
- أوقات العمل: من الأحد إلى الخميس (الجمعة والسبت عطلة، وتُستثنى العطل الرسمية).
- الفترة الصباحية (8:00 ص - 2:00 ظ): تواجد المحامي في أروقة المحاكم ومتابعة المعاملات بالدوائر والجهات الرسمية.
- فترة المقابلات المكتبية (2:00 ظ - 4:00 ع): مخصصة للاستشارات والمقابلات المباشرة بعد تثبيت موعد مسبق.

حجز المواعيد ولائحة الأجور وآلية الدفع:
- إمكانية الاستشارة: حضورياً (في مقر المكتب) أو عن بُعد (عبر الهاتف أو المنصات الرقمية).
- عند رغبة الموكل بتثبيت موعد، زوّده برابط استمارة الحجز الإلكترونية مباشرة:
https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform
- لائحة أجور الاستشارات الرسمية المباشرة مع المحامي:
  * استشارات الأحوال الشخصية: 75,000 دينار عراقي.
  * الاستشارات المدنية والشركات والعقود: 150,000 دينار عراقي.
  * الاستشارات الجزائية والجنائية: 300,000 دينار عراقي.
- آلية الدفع: وضّح للموكل أنه بعد إرسال استمارة الحجز، يتواصل المكتب معه لتأكيد الموعد وإرسال تفاصيل الدفع عبر وسائل الدفع الإلكترونية المحلية المعتمدة أو روابط الدفع المباشرة (Payment Links) للاستشارة عن بُعد، أو سدادها مباشرة داخل المكتب للمقابلات الحضورية.

نص إخلاء المسؤولية الإلزامي:
اختم كل رد بدون استثناء بالنص التالي في سطر مستقل:
"⚠️ تنبيه إخلاء مسؤولية: هذا رد آلي مبرمج صادر عن المساعد الذكي لمكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية لغرض الاسترشاد والتوجيه الأولي فقط، ولا يُعد استشارة قانونية رسمية ولا ينشئ رابطة توكيل. لحجز موعد استشارة رسمية ودراسة القضية (حضورياً أو عن بُعد)، يُرجى التقديم عبر رابط الاستمارة: https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
"""

@app.route("/", methods=["GET"])
def home():
    return "Legal Assistant Bot is Active", 200

# مسار استقبال وتأكيد الـ Webhook
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
            from_number = message["from"]

            if message.get("type") == "text":
                user_query = message["text"]["body"]

                try:
                    response = ai_client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=f"{SYSTEM_PROMPT}\n\nرسالة المستفسر: {user_query}",
                    )
                    reply_text = response.text
                except Exception:
                    reply_text = (
                        "أهلاً بك في مكتب المحامي علي كاظم الهاشمي للمحاماة والخدمات القانونية.\n"
                        "نعتذر عن تعذر معالجة الطلب آلياً في الوقت الحالي. "
                        "يتم الاطلاع على الرسائل من قبل المكتب تباعاً، أو يمكنك حجز موعد عبر الاستمارة:\n"
                        "https://docs.google.com/forms/d/e/1FAIpQLSdVxyld_U5Mdp-4RLcuA8HdQvAvlYWdd1fiQ8QAavwJj_Ev7w/viewform"
                    )

                send_whatsapp_message(from_number, reply_text)

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
    requests.post(url, headers=headers, json=payload)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
