import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found! Set BOT_TOKEN in env or .env file.")

VERSION = "v2"

OWNER_ID = 6512242172
SUDO_USERS = [6512242172, 6512242172, 6512242172]

REQUIRED_CHANNELS = [
    {"id": "@Kasukabe00", "name": "Kasu Kabe Updates"},
    {"id": "@Kasukabe01", "name": "DataTrace OSINT Support"},
]

START_LOG_CHANNEL = -1002763953812
SEARCH_LOG_CHANNEL = -1002763953812

ADMIN_CONTACT = "@offx_sahil"
CHANNEL_LINK_1 = "https://t.me/Kasukabe00"
GROUP_LINK_2 = "https://t.me/Kasukabe01"

# Diamonds
MIN_DIAMOND_PURCHASE = 50
DIAMOND_PRICE_INR = 5  # per diamond
REFERRAL_REWARD_DIAMOND = 1

API_ENDPOINTS = {
    "upi": "https://j4tnx-upi-info-api.onrender.com/upi_id=",
    "verify": "https://chumt-d8kr3hc69-okvaipro-svgs-projects.vercel.app/verify?query={query}",
    "pan": "https://panapi-6g7kjm4ah-okvaipro-svgs-projects.vercel.app/api/pan?pan={pan}",
    "number": "https://no-info-api.onrender.com/num/{number}",
    "vehicle_basic": "https://vehicle-info.awsvps844.workers.dev/?key=j4tnx&vh={number}",
    "vehicle_adv": "https://vehicle-j23oe900f-okvaipro-svgs-projects.vercel.app/vehicle_info?vehicle_no={number}",
    "vhowner": "https://vehiclevnum-lwh56es5n-okvaipro-svgs-projects.vercel.app/api/vehiclevnum?reg={reg}",
    "vehicle_rc_pdf": "http://3.111.238.230:5004/generate_rc?number={number}",
    "telegram": "https://tg-info-main-nhtgganrr-okvaipro-svgs-projects.vercel.app/user-details",
    "ip": "https://karmali.serv00.net/ip_api.php",
    "pakistan": "https://pak-num-api.vercel.app/search",
    "aadhar_family": "https://aadharapi-5z8qp4sqw-okvaipro-svgs-projects.vercel.app/fetch",
    "aadhar": "https://aadharinfo.gauravcyber0.workers.dev/?aadhar={aadhar}",
    "numfb": "https://numfb-3m572zbr1-okvaipro-svgs-projects.vercel.app/lookup?number={number}&key={key}",
    "insta_profile": "https://anmolinstainfo.worldgreeker.workers.dev/user?username={username}",
    "insta_posts": "https://anmolinstainfo.worldgreeker.workers.dev/posts?username={username}",
    "tg_user_alt": "https://sourceanmol.xo.je/api.php?username={username}",
    "bank_ifsc": "https://ifsc.razorpay.com/{ifsc}",
}

API_KEYS = {
    "number": "",
    "aadhar_family": "datatrace",
    "upi": "",
    "vehicle": "j4tnx",
    "vehicle_adv": "",
    "numfb": "chxprm456",
}

BRANDING_FOOTER = (
    "\n\n----------------------\n"
    f"Updates: {CHANNEL_LINK_1}\n"
    f"Support: {CHANNEL_LINK_2}\n"
    f"Contact: {ADMIN_CONTACT}"
)
