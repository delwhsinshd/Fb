import os
import threading
import telebot
from telebot import types
import pandas as pd

BOT_TOKEN = "8209906476:AAERmKhGa-q0W0yBI46Smtmpu8BxbKoOnwk"
bot = telebot.TeleBot(BOT_TOKEN)

# ব্যবহারকারীদের পাঠানো ডাটা ও টাইমার সংরক্ষণের ডিকশনারি
user_sessions = {}

def get_user_session(chat_id):
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            "rows": [],
            "timer": None
        }
    return user_sessions[chat_id]

def parse_line(line):
    """UID, Password এবং Cookies আলাদা করার ফাংশন"""
    line = line.strip()
    if not line:
        return None

    parts = [p.strip() for p in line.split('|')]
    uid = ""
    password = ""
    cookie = ""

    if len(parts) >= 3:
        uid = parts[0]
        password = parts[1]
        for p in parts[2:]:
            if "c_user=" in p or "xs=" in p or "datr=" in p:
                cookie = p
                break
        if not cookie:
            cookie = parts[-1]
    elif len(parts) == 2:
        uid = parts[0]
        password = parts[1]
    else:
        parts = line.split()
        if len(parts) >= 3:
            uid = parts[0]
            password = parts[1]
            cookie = " ".join(parts[2:])

    return uid, password, cookie

def send_summary_message(chat_id):
    """সব ফাইল রিসিভ হওয়ার পর সামারি ও বাটন পাঠানোর ফাংশন"""
    session = user_sessions.get(chat_id)
    if not session or not session["rows"]:
        return

    rows = session["rows"]
    total = len(rows)
    
    # সিরিয়াল অনুযায়ী কাউন্ট
    c_6156_57 = sum(1 for r in rows if str(r['UID']).startswith(('6156', '6157')))
    c_6159 = sum(1 for r in rows if str(r['UID']).startswith('6159'))
    c_1000 = sum(1 for r in rows if str(r['UID']).startswith('100'))
    c_others = total - (c_6156_57 + c_6159 + c_1000)

    # আপনার দেওয়া মেসেজ ফরম্যাট
    text = (
        f"Total {total} IDs Received.💥\n\n"
        f"6156-6157 Serial : {c_6156_57} Pcs\n"
        f"6159xxx Serial : {c_6159} Pcs\n"
        f"1000xxx Serial : {c_1000} Pcs"
    )
    if c_others > 0:
        text += f"\nOthers Serial : {c_others} Pcs"

    # 'Proccess File ✅' বাটন
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("Proccess File ✅", callback_data="process_files")
    markup.add(btn)

    bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "স্বাগতম! আপনি একসাথে একটি বা একাধিক .txt ফাইল পাঠাতে পারেন। পাঠানো শেষ হলে সামারি ও প্রসেস বাটন পাবেন।")

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    try:
        if not message.document.file_name.endswith('.txt'):
            bot.reply_to(message, f"❌ '{message.document.file_name}' এটি .txt ফাইল নয়!")
            return

        chat_id = message.chat.id
        session = get_user_session(chat_id)

        # যদি আগের কোনো টাইমার চলতে থাকে তা বাতিল করা (কারণ আরও ফাইল আসছে)
        if session["timer"] and session["timer"].is_alive():
            session["timer"].cancel()

        # ফাইল ডাউনলোড ও পড়া
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        try:
            content = downloaded_file.decode('utf-8')
        except UnicodeDecodeError:
            content = downloaded_file.decode('latin-1')

        lines = content.splitlines()

        # লাইন বাই লাইন ডাটা জমা করা
        for line in lines:
            parsed = parse_line(line)
            if parsed and parsed[0]:
                uid, password, cookie = parsed
                session["rows"].append({
                    "UID": str(uid),
                    "Password": str(password),
                    "Cookies": str(cookie)
                })

        # ২.৫ সেকেন্ড টাইমার সেট করা (একসাথে সব ফাইল টেলিগ্রাম থেকে রিসিভ করার জন্য)
        t = threading.Timer(2.5, send_summary_message, args=[chat_id])
        session["timer"] = t
        t.start()

    except Exception as e:
        bot.reply_to(message, f"এরর: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "process_files")
def process_callback(call):
    chat_id = call.message.chat.id
    session = user_sessions.get(chat_id)

    if not session or not session["rows"]:
        bot.answer_callback_query(call.id, "কোনো ডাটা পাওয়া যায়নি বা ইতিমধ্যেই প্রসেস হয়ে গেছে!", show_alert=True)
        return

    bot.answer_callback_query(call.id, "ফাইল তৈরি হচ্ছে...")
    # বাটনটি ডিসেবল বা রিমুভ করে দেওয়া যাতে ডাবল ক্লিক না হয়
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)

    rows = session["rows"]

    # ক্যাটাগরি তৈরি
    data_6156_57 = []
    data_6159 = []
    data_1000 = []
    data_others = []

    for r in rows:
        uid_str = r["UID"]
        if uid_str.startswith(('6156', '6157')):
            data_6156_57.append(r)
        elif uid_str.startswith('6159'):
            data_6159.append(r)
        elif uid_str.startswith('100'):
            data_1000.append(r)
        else:
            data_others.append(r)

    # ১. 6156/6157 Serial File
    if data_6156_57:
        filename = f"6156-6157 Serial File.xlsx"
        pd.DataFrame(data_6156_57).to_excel(filename, index=False)
        with open(filename, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"📁 6156-6157 Serial File ({len(data_6156_57)} Pcs)")
        os.remove(filename)

    # ২. 6159xxx Serial File
    if data_6159:
        filename = f"6159xxx Serial File.xlsx"
        pd.DataFrame(data_6159).to_excel(filename, index=False)
        with open(filename, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"📁 6159xxx Serial File ({len(data_6159)} Pcs)")
        os.remove(filename)

    # ৩. 1000xxx Serial File
    if data_1000:
        filename = f"1000xxx Serial File.xlsx"
        pd.DataFrame(data_1000).to_excel(filename, index=False)
        with open(filename, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"📁 1000xxx Serial File ({len(data_1000)} Pcs)")
        os.remove(filename)

    # ৪. Others Serial File (যদি থাকে)
    if data_others:
        filename = f"Others Serial File.xlsx"
        pd.DataFrame(data_others).to_excel(filename, index=False)
        with open(filename, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"📁 Others Serial File ({len(data_others)} Pcs)")
        os.remove(filename)

    # কাজ শেষ হলে মেমরি ক্লিয়ার করা
    user_sessions[chat_id]["rows"] = []
    bot.send_message(chat_id, "🎉 সব ফাইল সফলভাবে তৈরি করে পাঠানো হয়েছে!")

print("বট সফলভাবে চালু হয়েছে...")
bot.infinity_polling()
