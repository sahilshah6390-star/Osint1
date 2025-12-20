import json
import logging
import tempfile
from typing import Any, Dict, List, Optional

import aiohttp

from config import API_ENDPOINTS, API_KEYS, BRANDING_FOOTER

# Constants
DEFAULT_TIMEOUT = 15
NA = "N/A"
INFO_NOT_FOUND = "Information not found."
ERROR_OCCURRED = "An error occurred."

logger = logging.getLogger(__name__)


class APIHandler:
    """
    Handles API requests for various information lookups.
    Manages HTTP sessions and formats responses.
    """

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create a reusable HTTP session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close_session(self):
        """Close the HTTP session if open."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _fetch_data(self, url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[Dict[str, Any]]:
        """
        Generic method to fetch JSON data from an API endpoint.

        Args:
            url: The API endpoint URL.
            timeout: Request timeout in seconds.

        Returns:
            Parsed JSON data or None if failed.
        """
        try:
            session = await self.get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    logger.warning(f"API request failed: {url} - Status: {resp.status}")
                    return None
                return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"Client error fetching {url}: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
        return None

    async def _fetch_text(self, url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
        """
        Generic method to fetch text data from an API endpoint.

        Args:
            url: The API endpoint URL.
            timeout: Request timeout in seconds.

        Returns:
            Text response or None if failed.
        """
        try:
            session = await self.get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    logger.warning(f"API request failed: {url} - Status: {resp.status}")
                    return None
                return await resp.text()
        except aiohttp.ClientError as e:
            logger.error(f"Client error fetching {url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
        return None

    # ---- UPI ----
    async def fetch_upi_info(self, upi_id: str) -> str:
        """Fetch and format UPI information."""
        if not upi_id:
            return INFO_NOT_FOUND

        url = f"{API_ENDPOINTS['upi']}{upi_id}"
        data = await self._fetch_data(url)
        if not data:
            return INFO_NOT_FOUND
        return self._format_upi(data, upi_id)

    async def fetch_verify_upi(self, upi_id: str) -> str:
        """Fetch and format verified UPI information with custom messages."""
        if not upi_id:
            return "no result found for your query"

        url = API_ENDPOINTS["verify"].format(query=upi_id)
        data = await self._fetch_data(url)
        if not data:
            return "no result found for your query"
        return self._format_verify(data)

    async def fetch_pan_info(self, pan: str) -> str:
        """Fetch and format PAN information."""
        if not pan:
            return INFO_NOT_FOUND

        # Block specific PAN
        if pan.upper() == "QJXPK1926B":
            return "NO INFORMATION FOUND FOR THIS NUMBER"

        url = API_ENDPOINTS["pan"].format(pan=pan.upper())
        data = await self._fetch_data(url)
        if not data:
            return INFO_NOT_FOUND
        return self._format_pan(data, pan.upper())

    def _format_upi(self, data: Dict[str, Any], upi_id: str) -> str:
        """Format UPI data into a string."""
        bank_details = data.get('bank_details_raw', {}) or {}
        vpa_details = data.get('vpa_details', {}) or data.get('user_details', {}) or {}

        lines = [
            '╔════════ UPI TO INFO ════════╗',
            f"📊 Status: {data.get('status', NA)}",
            f"💳 UPI ID: {data.get('upi_id', upi_id)}",
            '',
            '👤 [User Details]',
            f"📛 Name: {vpa_details.get('name', NA)}",
            f"💳 VPA: {vpa_details.get('vpa', upi_id)}",
            f"🏦 IFSC: {vpa_details.get('ifsc', bank_details.get('IFSC', NA))}",
        ]

        if bank_details:
            lines.extend([
                '',
                '🏦 [Bank Details]',
                f"🏠 Address: {bank_details.get('ADDRESS', NA)}",
                f"🏦 Bank: {bank_details.get('BANK', NA)}",
                f"🏢 Branch: {bank_details.get('BRANCH', NA)}",
                f"🌆 City: {bank_details.get('CITY', NA)}",
                f"📍 District: {bank_details.get('DISTRICT', NA)}",
                f"🗺 State: {bank_details.get('STATE', NA)}",
                f"🔢 MICR: {bank_details.get('MICR', NA)}",
            ])

        lines.append(BRANDING_FOOTER)
        return '\n'.join(lines)

    def _format_verify(self, data: Dict[str, Any]) -> str:
        """Format verify data into a string."""
        entries = data.get("data", {}).get("verify_chumts", [])
        if not entries or not isinstance(entries, list):
            return "no result found for your query"

        lines = [
            "━━━━━━━━━━━━━━━━━━━",
            "🔍 VERIFY UPI RESULT",
            "━━━━━━━━━━━━━━━━━━━",
            "",
        ]
        for idx, entry in enumerate(entries, 1):
            if not isinstance(entry, dict):
                continue
            lines.extend([
                f"📱 ENTRY {idx}",
                f"📛 NAME: {entry.get('name', NA)}",
                f"💳 VPA: {entry.get('vpa', NA)}",
                f"🏦 IFSC: {entry.get('ifsc', NA)}",
                f"💳 ACC NO: {entry.get('acc_no', NA)}",
                f"📞 UPI NUMBER: {entry.get('upi_number', NA)}",
                f"🏪 MERCHANT: {entry.get('is_merchant', False)}",
                f"✅ VERIFIED: {entry.get('is_merchant_verified', False)}",
                "",
            ])
        lines.append(BRANDING_FOOTER)
        return "\n".join(lines)

    def _format_pan(self, data: Dict[str, Any], pan: str) -> str:
        """Format PAN data into a string."""
        if not isinstance(data, dict) or not data.get("success"):
            return INFO_NOT_FOUND

        lines = [
            "━━━━━━━━━━━━━━━━━━━",
            "🔍 PAN INFO RESULT",
            "━━━━━━━━━━━━━━━━━━━",
            "",
            f"🆔 PAN: {pan}",
            f"📛 FULL NAME: {data.get('fullName', NA)}",
            f"👤 FIRST NAME: {data.get('firstName', NA)}",
            f"👤 LAST NAME: {data.get('lastName', NA)}",
            f"📅 DOB: {data.get('dob', NA)}",
            f"✅ STATUS: {data.get('panStatus', NA)}",
            BRANDING_FOOTER,
        ]
        return "\n".join(lines)

    # ---- Number ----
    async def fetch_number_info(self, number: str) -> str:
        """Fetch and format number information."""
        if not number:
            return "No number provided."

        # Block specific numbers
        if number in ["7000996857", "7724814462"]:
            return "NO INFORMATION FOUND FOR THIS NUMBER"

        url = API_ENDPOINTS["number"].format(mob_number=number, number=number)
        data = await self._fetch_data(url)
        if not data:
            return "Number lookup failed."
        return self._format_number(data)

    def _format_number(self, data: Any) -> str:
        """Format number data into a string."""
        entries: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            # Handle nested data.result structure
            if "data" in data and isinstance(data["data"], dict) and "result" in data["data"]:
                entries = data["data"]["result"]
            else:
                entries = (
                    data.get("data")
                    or data.get("result")
                    or data.get("results")
                    or data.get("records")
                    or data.get("record")
                    or []
                )
            # If still empty, try to locate the first list of dicts inside the payload
            if not entries:
                for value in data.values():
                    if isinstance(value, list) and value and isinstance(value[0], dict):
                        entries = value
                        break
            # If a single dict with name/mobile, treat it as one entry
            if not entries and all(k in data for k in ("name", "mobile")):
                entries = [data]
        elif isinstance(data, list):
            entries = [d for d in data if isinstance(d, dict)]

        if not entries or not isinstance(entries, list):
            return INFO_NOT_FOUND

        lines = [
            "━━━━━━━━━━━━━━━━━━━",
            "🔍 NUMBER TO INFO RESULT",
            "━━━━━━━━━━━━━━━━━━━",
            "",
        ]
        for idx, entry in enumerate(entries, 1):
            if not isinstance(entry, dict):
                continue
            address = (entry.get("address") or "").replace("!", ", ").strip() or NA
            email = entry.get("email") or NA
            if email == "":
                email = NA
            id_value = entry.get("id_number") or entry.get("id") or NA
            lines.extend([
                f"📱 ENTRY {idx}",
                f"📛 NAME: {entry.get('name', NA)}",
                f"👨‍👦 FATHER NAME: {entry.get('father_name', NA)}",
                f"📞 MOBILE: {entry.get('mobile', NA)}",
                f"🏠 ADDRESS: {address}",
                f"📡 CIRCLE: {entry.get('circle', NA)}",
                f"🆔 ID: {id_value}",
                f"📧 EMAIL: {email}",
                "",
            ])
        lines.append(BRANDING_FOOTER)
        return "\n".join(lines)

    # ---- Aadhar ----
    async def fetch_aadhar_info(self, aadhar: str) -> str:
        """Fetch and format Aadhar information."""
        if not aadhar:
            return INFO_NOT_FOUND

        url = API_ENDPOINTS["aadhar"].format(aadhar=aadhar)
        data = await self._fetch_data(url)
        if not data:
            return INFO_NOT_FOUND
        return self._format_aadhar(data)

    def _format_aadhar(self, data: Any) -> str:
        """Format Aadhar data into a string."""
        entries: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            entries = data.get("data") or data.get("result") or []
        elif isinstance(data, list):
            entries = data

        if not entries:
            return "⚠️ No information found for this Aadhar."

        lines = ["╔════════ AADHAR INFO ════════╗", ""]
        for idx, entry in enumerate(entries, 1):
            if not isinstance(entry, dict):
                continue
            address = (entry.get("address") or "").replace("!", ", ").strip() or NA
            alt_mobile = entry.get("alt") or entry.get("alt_mobile") or NA
            lines.extend([
                f"[Entry #{idx}]",
                f"Name: {entry.get('name', NA)}",
                f"Father: {entry.get('fname') or entry.get('father_name', NA)}",
                f"Mobile: {entry.get('mobile', NA)}",
                f"Alt Mobile: {alt_mobile}",
                f"Address: {address}",
                f"Circle: {entry.get('circle', NA)}",
                f"ID: {entry.get('id', NA)}",
                "",
            ])
        lines.append(BRANDING_FOOTER)
        return "\n".join(lines)

    async def fetch_numbers_from_aadhar(self, aadhar: str) -> str:
        """Fetch associated mobile numbers from Aadhar number (reverse lookup)."""
        if not aadhar:
            return INFO_NOT_FOUND

        url = API_ENDPOINTS["aadhar"].format(aadhar=aadhar)
        data = await self._fetch_data(url)
        if not data:
            return INFO_NOT_FOUND
        return self._format_numbers_from_aadhar(data)

    def _format_numbers_from_aadhar(self, data: Any) -> str:
        """Extract and format mobile numbers from Aadhar data."""
        entries: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            entries = data.get("data") or data.get("result") or []
        elif isinstance(data, list):
            entries = data

        if not entries:
            return "⚠️ No mobile numbers found for this Aadhar."

        numbers = []
        for entry in entries:
            if isinstance(entry, dict):
                mobile = entry.get('mobile')
                alt_mobile = entry.get('alt_mobile') or entry.get('alt')
                if mobile and mobile != NA:
                    numbers.append(mobile)
                if alt_mobile and alt_mobile != NA and alt_mobile != mobile:
                    numbers.append(alt_mobile)

        if not numbers:
            return "⚠️ No mobile numbers found for this Aadhar."

        lines = [
            "╔════════ REVERSE AADHAR ════════╗",
            f"Aadhar: {aadhar}",
            "",
            "[Associated Mobile Numbers]",
        ]
        for idx, number in enumerate(set(numbers), 1):  # Use set to remove duplicates
            lines.append(f"{idx}. {number}")

        lines.append(BRANDING_FOOTER)
        return "\n".join(lines)

    async def fetch_aadhar_family(self, aadhar: str) -> str:
        """Fetch and format Aadhar family information."""
        if not aadhar:
            return INFO_NOT_FOUND

        url = f"{API_ENDPOINTS['aadhar_family']}?aadhaar={aadhar}&key={API_KEYS['aadhar_family']}"
        data = await self._fetch_data(url)
        if not data:
            return INFO_NOT_FOUND
        return self._format_aadhar_family(data)

    def _format_aadhar_family(self, data: Dict[str, Any]) -> str:
        """Format Aadhar family data into a string."""
        if not isinstance(data, dict) or not data:
            return "⚠️ No family information found."

        members = data.get("memberDetailsList") or data.get("members") or []
        if not isinstance(members, list):
            members = []

        lines = [
            "╔════════ AADHAR FAMILY ════════╗",
            f"RC ID: {data.get('rcId', NA)}",
            f"Scheme: {data.get('schemeName', NA)}",
            f"District: {data.get('homeDistName', NA)}",
            f"State: {data.get('homeStateName', NA)}",
            "",
            "[Members]",
        ]

        if not members:
            lines.append("No members listed.")
        else:
            for idx, member in enumerate(members, 1):
                if not isinstance(member, dict):
                    continue
                lines.append(f"{idx}. {member.get('memberName', member.get('member_name', NA))} - {member.get('releationship_name', member.get('relationship', NA))}")

        lines.append(BRANDING_FOOTER)
        return "\n".join(lines)

    # ---- IP ----
    async def fetch_ip_info(self, ip: str) -> str:
        """Fetch and format IP information."""
        if not ip:
            return INFO_NOT_FOUND

        url = f"{API_ENDPOINTS['ip']}?ip={ip}"
        text = await self._fetch_text(url)
        if not text:
            return INFO_NOT_FOUND
        return "\n".join(["🌐 IP Info", "━━━━━━━━━━━━", text.strip(), BRANDING_FOOTER])

    # ---- Telegram ----
    async def fetch_telegram_info(self, username: str) -> str:
        """Fetch and format Telegram user information."""
        if not username:
            return INFO_NOT_FOUND

        url = f"{API_ENDPOINTS['telegram']}?user={username}"
        data = await self._fetch_data(url)
        if not data:
            return INFO_NOT_FOUND
        return self._format_telegram(data)

    def _format_telegram(self, data: Dict[str, Any]) -> str:
        """Format Telegram data into a string."""
        user_data = data.get("data", data) if isinstance(data, dict) else data
        if not user_data:
            return "⚠️ Information not found."

        lines = [
            "╔════════ TELEGRAM STATS ════════╗",
            "━━━━━━━━━━━━",
            f"Name: {user_data.get('first_name', NA)} {user_data.get('last_name', '')}".strip(),
            f"User ID: {user_data.get('id', user_data.get('user_id', NA))}",
            f"Is Bot: {user_data.get('is_bot', False)}",
            f"Active: {user_data.get('is_active', False)}",
            "",
            "[Stats]",
            f"Total Groups: {user_data.get('total_groups', 0)}",
            f"Admin In Groups: {user_data.get('adm_in_groups', 0)}",
            f"Total Messages: {user_data.get('total_msg_count', 0)}",
            f"Messages In Groups: {user_data.get('msg_in_groups_count', 0)}",
            f"First Msg: {user_data.get('first_msg_date', NA)}",
            f"Last Msg: {user_data.get('last_msg_date', NA)}",
            BRANDING_FOOTER,
        ]
        return "\n".join(lines)

    async def fetch_telegram_alt(self, username: str) -> str:
        """Fetch and format alternative Telegram information."""
        if not username:
            return INFO_NOT_FOUND

        url = API_ENDPOINTS["tg_user_alt"].format(username=username)
        data = await self._fetch_data(url)
        if not data:
            return INFO_NOT_FOUND
        return self._format_telegram_alt(data, username)

    def _format_telegram_alt(self, data: Dict[str, Any], username: str) -> str:
        """Format alternative Telegram data."""
        if not isinstance(data, dict):
            return "⚠️ Information not found."
        if data.get("success") is False:
            return "⚠️ Information not found."

        payload = data.get("data") or {}
        profile = payload.get("profile", {}) if isinstance(payload, dict) else {}
        contacts = payload.get("contacts", {}) if isinstance(payload, dict) else {}
        activity = payload.get("activity", {}) if isinstance(payload, dict) else {}
        media = payload.get("media", {}) if isinstance(payload, dict) else {}
        photos = media.get("profile_photos", {}) if isinstance(media, dict) else {}

        lines = [
            "╔════════ TELEGRAM USER ════════╗",
            f"Username: {data.get('username', username)}",
            f"Name: {profile.get('name', NA)}",
            f"Bio: {profile.get('bio', NA)}",
            f"Verified: {profile.get('verified', False)} | Premium: {profile.get('premium', False)}",
            "",
            "[Contacts]",
            f"Link: {contacts.get('telegram_link', NA)}",
            f"DM: {contacts.get('direct_message', NA)}",
            "",
            "[Activity]",
            f"Status: {activity.get('online_status', NA)}",
            f"Last seen: {activity.get('last_seen', NA)}",
            f"Subscribers: {activity.get('subscribers', NA)}",
        ]

        if photos.get("profile_picture"):
            lines.extend([
                "",
                f"Profile Pic: {photos.get('profile_picture')}",
                f"Photo ID: {photos.get('photo_id', NA)}",
            ])

        lines.append(BRANDING_FOOTER)
        return "\n".join(lines)

    # ---- Pakistan ----
    async def fetch_pakistan_info(self, number: str) -> str:
        """Fetch and format Pakistan number information."""
        if not number:
            return "No number provided."

        url = f"{API_ENDPOINTS['pakistan']}?number={number}"
        data = await self._fetch_data(url)
        if not data:
            return f"⚠️ Pakistan lookup failed."
        return self._format_pakistan(data)

    def _format_pakistan(self, data: Any) -> str:
        """Format Pakistan data into a string."""
        results: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            if isinstance(data.get("results"), list):
                results = data["results"]
            elif isinstance(data.get("data"), list):
                results = data["data"]
            else:
                for value in data.values():
                    if isinstance(value, list):
                        results = value
                        break
        elif isinstance(data, list):
            results = data

        if not results:
            return "Information not found."

        lines = ["╔════════ PAKISTAN INFO ════════╗", ""]
        for idx, entry in enumerate(results, 1):
            lines.extend([
                f"[Result #{idx}]",
                f"Name: {entry.get('Name', entry.get('name', NA))}",
                f"CNIC: {entry.get('CNIC', entry.get('cnic', NA))}",
                f"Mobile: {entry.get('Mobile', entry.get('mobile', NA))}",
                f"Address: {entry.get('Address', entry.get('address', NA))}",
                "",
            ])
        lines.append(BRANDING_FOOTER)
        return "\n".join(lines)

    # ---- Instagram profile ----
    async def fetch_instagram_profile(self, username: str) -> str:
        """Fetch and format Instagram profile information."""
        if not username:
            return f"⚠️ No username provided."

        url = API_ENDPOINTS["insta_profile"].format(username=username)
        data = await self._fetch_data(url)
        if not data:
            return f"⚠️ Instagram profile lookup failed."
        return self._format_instagram_profile(data)

    def _format_instagram_profile(self, data: Dict[str, Any]) -> str:
        """Format Instagram profile data."""
        lines = [
            "╔════════ INSTAGRAM PROFILE ════════╗",
            f"Username: {data.get('username', NA)}",
            f"Name: {data.get('full_name', NA)}",
            f"Bio: {data.get('biography', NA)}",
            f"Followers: {data.get('followers', NA)} | Following: {data.get('following', NA)}",
            f"Posts: {data.get('posts', NA)}",
            f"Private: {data.get('is_private', False)} | Verified: {data.get('is_verified', False)}",
        ]
        if data.get("profile_pic"):
            lines.append(f"Profile Pic: {data.get('profile_pic')}")
        lines.append(BRANDING_FOOTER)
        return "\n".join(lines)

    # ---- Instagram posts ----
    async def fetch_instagram_posts(self, username: str) -> str:
        """Fetch and format Instagram posts."""
        if not username:
            return "⚠️ No username provided."

        url = API_ENDPOINTS["insta_posts"].format(username=username)
        data = await self._fetch_data(url)
        if not data:
            return f"⚠️ Instagram posts lookup failed."
        return self._format_instagram_posts(data)

    def _format_instagram_posts(self, data: Dict[str, Any]) -> str:
        """Format Instagram posts data."""
        username = data.get("username", NA)
        posts = data.get("posts", [])
        if not posts:
            return "⚠️ No posts found."

        lines = [
            "╔════════ INSTAGRAM POSTS ════════╗",
            f"Username: {username}",
        ]

        for idx, post in enumerate(posts[:5], 1):
            caption = (post.get("caption") or NA).strip()
            if len(caption) > 250:
                caption = caption[:247] + "..."
            lines.extend([
                "",
                f"[Post #{idx}]",
                f"ID: {post.get('id', NA)}",
                f"Caption: {caption}",
                f"Likes: {post.get('likes', NA)} | Comments: {post.get('comments', NA)}",
                f"Video: {post.get('is_video', False)}",
                f"URL: {post.get('url', NA)}",
                f"Thumb: {post.get('thumbnail_url', post.get('image_url', NA))}",
            ])

        lines.append(BRANDING_FOOTER)
        return "\n".join(lines)

    # ---- Bank IFSC ----
    async def fetch_ifsc_info(self, ifsc: str) -> str:
        """Fetch and format IFSC information."""
        if not ifsc:
            return f"⚠️ No IFSC provided."

        url = API_ENDPOINTS["bank_ifsc"].format(ifsc=ifsc)
        data = await self._fetch_data(url)
        if not data:
            return f"⚠️ IFSC lookup failed."
        return self._format_ifsc(data)

    def _format_ifsc(self, data: Dict[str, Any]) -> str:
        """Format IFSC data."""
        lines = [
            "╔════════ BANK IFSC ════════╗",
            f"BANK: {data.get('BANK', NA)}",
            f"IFSC: {data.get('IFSC', NA)} | BANKCODE: {data.get('BANKCODE', NA)}",
            f"BRANCH: {data.get('BRANCH', NA)}",
            f"ADDRESS: {data.get('ADDRESS', NA)}",
            f"CITY: {data.get('CITY', NA)} | DISTRICT: {data.get('DISTRICT', NA)} | STATE: {data.get('STATE', NA)}",
            f"ISO: {data.get('ISO3166', NA)}",
            f"NEFT: {data.get('NEFT', False)} | RTGS: {data.get('RTGS', False)} | IMPS: {data.get('IMPS', False)} | UPI: {data.get('UPI', False)}",
            BRANDING_FOOTER,
        ]
        return "\n".join(lines)

    # ---- Vehicle basic ----
    async def fetch_vehicle_basic(self, plate: str) -> str:
        """Fetch and format basic vehicle information."""
        if not plate:
            return f"⚠️ No plate provided."

        url = API_ENDPOINTS["vehicle_basic"].format(number=plate)
        data = await self._fetch_data(url, timeout=20)
        if not data:
            return f"⚠️ Vehicle lookup failed."
        return self._format_vehicle_basic(data)

    def _format_vehicle_basic(self, data: Dict[str, Any]) -> str:
        """Format basic vehicle data."""
        vehicle = data.get("data") or data.get("response") or data
        if not isinstance(vehicle, dict) or not vehicle:
            return "⚠️ No info found for this plate."

        challan = vehicle.get("challan_info") or vehicle
        puc = vehicle.get("puc_info") or {}

        lines = [
            "╔════════ VEHICLE INFO ════════╗",
            f"🪪 Owner: {challan.get('owner_name', vehicle.get('owner_name', vehicle.get('owner', NA)))}",
            f"🚘 Plate: {challan.get('registration_no', vehicle.get('license_plate', vehicle.get('registration_number', NA)))}",
            f"🏢 RTO: {challan.get('registration_authority', NA)}",
            f"🗓 Registered: {challan.get('registration_date', vehicle.get('registration_date', NA))}",
            f"🚗 Model: {challan.get('maker_model', vehicle.get('brand_model', vehicle.get('model', NA)))}",
            f"🏷 Brand: {challan.get('brand_name', vehicle.get('brand', NA))}",
            f"🎨 Color: {challan.get('vehicle_color', vehicle.get('color', NA))}",
            f"⛽ Fuel: {challan.get('fuel_type', vehicle.get('fuel_type', NA))}",
            f"📦 Class/Type: {challan.get('vehicle_class', NA)} / {challan.get('vehicle_type', NA)}",
            f"🛡 RC Status: {challan.get('rc_status', vehicle.get('rc_status', NA))}",
            f"🔧 Chassis: {challan.get('chassis_no', vehicle.get('chassis_number', NA))}",
            f"⚙️ Engine: {challan.get('engine_no', vehicle.get('engine_number', NA))}",
            f"🧾 Insurance: {challan.get('insurance_company', NA)} (till {challan.get('insurance_upto', NA)})",
            f"♻️ PUC till: {challan.get('puc_upto', puc.get('rc_pucc_upto', NA))}",
            f"🏋️ Unladen Wt: {challan.get('unload_weight', NA)} | Seats: {challan.get('seat_capacity', NA)}",
            f"🏠 Address: {vehicle.get('present_address', vehicle.get('address', NA))}",
            BRANDING_FOOTER,
        ]
        return "\n".join(lines)

    # ---- Vehicle advanced ----
    async def fetch_vehicle_advanced(self, plate: str) -> str:
        """Fetch and format advanced vehicle information."""
        if not plate:
            return f"⚠️ No plate provided."

        url = API_ENDPOINTS["vehicle_adv"].format(number=plate)
        data = await self._fetch_data(url, timeout=20)
        if not data:
            return f"⚠️ Advanced vehicle lookup failed."
        return self._format_vehicle_advanced(data)

    def _format_vehicle_advanced(self, data: Dict[str, Any]) -> str:
        """Format advanced vehicle data."""
        root = data.get("response") or data.get("data") or data
        vehicle = root.get("data") or root
        if not isinstance(vehicle, dict) or not vehicle:
            return "⚠️ No info found for this plate."

        body_desc = vehicle.get("body_type_desc")
        if isinstance(body_desc, dict):
            body_desc = ", ".join(f"{k}:{v}" for k, v in body_desc.items())

        lines = [
            "╔════════ VEHICLE ADV ════════╗",
            f"🪪 Owner: {vehicle.get('owner_name', NA)}",
            f"👤 Father: {vehicle.get('father_name', NA)}",
            f"🚘 Plate: {vehicle.get('registration_no', vehicle.get('license_plate', vehicle.get('vehicle_no', NA)))}",
            f"🏢 RTO: {vehicle.get('registration_authority', NA)}",
            f"🗓 Registered: {vehicle.get('registration_date', NA)}",
            f"🚗 Model: {vehicle.get('maker_model', vehicle.get('brand_model', vehicle.get('model', NA)))}",
            f"🏷 Brand: {vehicle.get('brand_name', vehicle.get('brand', NA))}",
            f"📦 Class/Type: {vehicle.get('vehicle_class', vehicle.get('class', NA))} / {vehicle.get('vehicle_type', NA)}",
            f"⛽ Fuel: {vehicle.get('fuel_type', NA)} | Norms: {vehicle.get('fuel_norms', NA)}",
            f"🎨 Color: {vehicle.get('vehicle_color', vehicle.get('color', NA))}",
            f"🏋️ Unladen Wt: {vehicle.get('unload_weight', NA)} | Seats: {vehicle.get('seat_capacity', NA)}",
            f"🗓 Fitness: {vehicle.get('fitness_upto', NA)} | Insurance: {vehicle.get('insurance_upto', NA)}",
            f"♻️ PUC till: {vehicle.get('puc_upto', NA)}",
            f"🔧 Chassis: {vehicle.get('chassis_no', vehicle.get('chassis_number', NA))}",
            f"⚙️ Engine: {vehicle.get('engine_no', vehicle.get('engine_number', NA))}",
            f"🏗 Body: {body_desc or NA}",
            f"📄 RC Status: {vehicle.get('rc_status', NA)} | Ownership: {vehicle.get('ownership_desc', NA)}",
            f"📞 Mobile: {root.get('mobile_no', NA)}",
            BRANDING_FOOTER,
        ]
        return "\n".join(lines)

    # ---- Vehicle owner ----
    async def fetch_vhowner(self, reg: str) -> str:
        """Fetch and format vehicle owner information."""
        if not reg:
            return f"⚠️ No registration number provided."

        url = API_ENDPOINTS["vhowner"].format(reg=reg)
        data = await self._fetch_data(url, timeout=20)
        if not data:
            return f"⚠️ Vehicle owner lookup failed."
        return self._format_vhowner(data)

    def _format_vhowner(self, data: Dict[str, Any]) -> str:
        """Format vehicle owner data."""
        if not data.get("success"):
            return "⚠️ No info found for this registration."

        vehicle_data = data.get("data", {})
        mobile_no = vehicle_data.get("mobile_no", NA)

        lines = [
            "╔════════ VEHICLE OWNER ════════╗",
            f"🚘 Registration: {data.get('reg_no', NA)}",
            f"📞 Mobile Number: {mobile_no}",
            BRANDING_FOOTER,
        ]
        return "\n".join(lines)

    # ---- Vehicle RC PDF ----
    async def fetch_vehicle_rc_pdf(self, plate: str) -> Optional[str]:
        """Fetch vehicle RC PDF and save to temp file."""
        if not plate:
            return None

        url = API_ENDPOINTS["vehicle_rc_pdf"].format(number=plate)
        try:
            session = await self.get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return None
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(await resp.read())
                    return tmp_file.name
        except Exception as e:
            logger.error(f"Error fetching PDF for {plate}: {e}")
            return None
