import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN_HERE")
VERSION = "v2"

OWNER_ID = 6512242172
SUDO_USERS = [5193826370,]

REQUIRED_CHANNELS = [
    {"id": "@Kasukabe00", "name": "DataTrace Updates"},
    {"id": -1002661857120, "name": "DataTrace Support"},
]

START_LOG_CHANNEL = -1002763953812
SEARCH_LOG_CHANNEL = -1002763953812

ADMIN_CONTACT = "@AstronixHub"
CHANNEL_LINK_1 = "https://t.me/Kasukabe00"
CHANNEL_LINK_2 = "https://t.me/Kasukabe01"

MIN_DIAMOND_PURCHASE = 50
DIAMOND_PRICE_INR = 5
REFERRAL_REWARD_DIAMOND = 1

NUMBER_API_ENDPOINT = os.getenv(
    "NUMBER_API_ENDPOINT",
    "https://7.toxictanji0503.workers.dev/paidnumapi?num={number}",
)
NUMBER_ALT_API_ENDPOINT = os.getenv(
    "NUMBER_ALT_API_ENDPOINT",
    "https://anku-num-info-five.vercel.app/search?num={number}&key={key}",
)

API_ENDPOINTS = {
    "upi": "https://j4tnx-upi-info-api.onrender.com/upi_id=",
    "pan": "https://panapi-6g7kjm4ah-okvaipro-svgs-projects.vercel.app/api/pan?pan={pan}",
    "number": NUMBER_API_ENDPOINT,
    "number_alt": NUMBER_ALT_API_ENDPOINT,
    "vehicle_rc_pdf": "http://3.111.238.230:5004/generate_rc?number={number}",
    "ip": "https://karmali.serv00.net/ip_api.php",
    "pakistan": "https://pak-num-api.vercel.app/search",
    "aadhar_family": "https://aadharapi-5z8qp4sqw-okvaipro-svgs-projects.vercel.app/fetch",
    "aadhar": "https://dt-support.gauravyt566.workers.dev/?aadhaar={aadhar}",
    "numfb": "https://numfb-3m572zbr1-okvaipro-svgs-projects.vercel.app/lookup?number={number}&key={key}",
    "insta_profile": "https://anmolinstainfo.worldgreeker.workers.dev/user?username={username}",
    "insta_posts": "https://anmolinstainfo.worldgreeker.workers.dev/posts?username={username}",
    "bank_ifsc": "https://ifsc.razorpay.com/{ifsc}",
}

API_KEYS = {
    "number": os.getenv("NUMBER_API_KEY", "c5adb0fc9372269f"),
    "aadhar_family": "datatrace",
    "upi": "",
    "numfb": "chxprm456",
}

BRANDING_FOOTER = (
    "\n\n----------------------\n"
    f"Updates: {CHANNEL_LINK_1}\n"
    f"Support: {CHANNEL_LINK_2}\n"
    f"Contact: {ADMIN_CONTACT}"
)
