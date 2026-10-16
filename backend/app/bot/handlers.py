"""Command and callback query handlers for RaktSetu Telegram Bot."""

import html
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from backend.app.bot.client import DiscoveryApiClient, DiscoveryApiError
from backend.app.bot.config import BotConfig
from backend.app.bot.formatter import (
    format_api_error_message,
    format_discovery_results,
    format_empty_results,
    format_help_message,
    format_start_message,
)
from backend.app.models.blood_bank import SUPPORTED_BLOOD_GROUPS, SUPPORTED_CITIES


def build_blood_group_keyboard() -> InlineKeyboardMarkup:
    """Build interactive inline keyboard for ABO/Rh blood group selection."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("A+", callback_data="group:A+"),
                InlineKeyboardButton("A-", callback_data="group:A-"),
                InlineKeyboardButton("B+", callback_data="group:B+"),
                InlineKeyboardButton("B-", callback_data="group:B-"),
            ],
            [
                InlineKeyboardButton("AB+", callback_data="group:AB+"),
                InlineKeyboardButton("AB-", callback_data="group:AB-"),
                InlineKeyboardButton("O+", callback_data="group:O+"),
                InlineKeyboardButton("O-", callback_data="group:O-"),
            ],
            [
                InlineKeyboardButton("All Blood Groups", callback_data="group:All"),
            ],
        ]
    )


def build_city_keyboard(blood_group: str) -> InlineKeyboardMarkup:
    """Build interactive inline keyboard for target city selection."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Delhi", callback_data=f"search:{blood_group}:Delhi"),
                InlineKeyboardButton("Lucknow", callback_data=f"search:{blood_group}:Lucknow"),
            ],
            [
                InlineKeyboardButton(
                    "Delhi & Lucknow (All)",
                    callback_data=f"search:{blood_group}:All",
                ),
            ],
            [
                InlineKeyboardButton("« Back to Blood Groups", callback_data="back:groups"),
            ],
        ]
    )


def _normalize_group(group: str) -> Optional[str]:
    """Validate and normalize user-provided blood group string."""
    cleaned = group.strip().upper()
    if cleaned == "ALL":
        return "All"
    if cleaned in SUPPORTED_BLOOD_GROUPS:
        return cleaned
    return None


def _normalize_city(city: str) -> Optional[str]:
    """Validate and normalize user-provided city string."""
    cleaned = city.strip().title()
    if cleaned.upper() in ("ALL", "BOTH", "ALL CITIES"):
        return "All"
    if cleaned in SUPPORTED_CITIES:
        return cleaned
    return None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.effective_message:
        return
    config: Optional[BotConfig] = context.bot_data.get("config")
    web_url = config.web_url if config else None
    text = format_start_message(web_url=web_url)
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.effective_message:
        return
    config: Optional[BotConfig] = context.bot_data.get("config")
    web_url = config.web_url if config else None
    text = format_help_message(web_url=web_url)
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def execute_discovery_and_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    blood_group: Optional[str],
    city: Optional[str],
    is_callback: bool = False,
) -> None:
    """Execute discovery search via client and reply with clinical formatting."""
    config: BotConfig = context.bot_data.get("config") or BotConfig(bot_token="")
    client: DiscoveryApiClient = context.bot_data.get("api_client") or DiscoveryApiClient(
        base_url=config.api_base_url,
        timeout=config.request_timeout,
    )

    query_city = None if city in (None, "All") else city
    query_group = None if blood_group in (None, "All") else blood_group

    try:
        response = await client.get_blood_banks(city=query_city, blood_group=query_group)
        facilities, total_count = client.filter_and_rank_facilities(
            response,
            blood_group=query_group,
            max_facilities=config.max_facilities,
        )

        if not facilities:
            text = format_empty_results(
                blood_group=blood_group,
                city=city,
                web_url=config.web_url,
            )
        else:
            text = format_discovery_results(
                facilities=facilities,
                total_count=total_count,
                blood_group=blood_group,
                city=city,
                web_url=config.web_url,
            )
    except DiscoveryApiError:
        text = format_api_error_message()
    except Exception:
        text = format_api_error_message()

    if is_callback and update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /find command with optional direct arguments or interactive keyboard."""
    if not update.effective_message:
        return

    args = context.args or []

    # Case 1: Direct arguments provided e.g. /find O+ Delhi
    if len(args) >= 2:
        group_raw = args[0]
        city_raw = " ".join(args[1:])

        normalized_group = _normalize_group(group_raw)
        normalized_city = _normalize_city(city_raw)

        if not normalized_group:
            valid_groups = ", ".join(sorted(SUPPORTED_BLOOD_GROUPS))
            err_msg = (
                f"❌ Invalid blood group <code>{html.escape(group_raw)}</code>.\n"
                f"Supported groups: {valid_groups}, or <code>All</code>.\n\n"
                "Please select your blood group below:"
            )
            await update.effective_message.reply_text(
                err_msg,
                reply_markup=build_blood_group_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return

        if not normalized_city:
            valid_cities = ", ".join(sorted(SUPPORTED_CITIES))
            err_msg = (
                f"❌ Invalid city <code>{html.escape(city_raw)}</code>.\n"
                f"Supported cities: {valid_cities}, or <code>All</code>.\n\n"
                f"Select target city for group <b>{normalized_group}</b>:"
            )
            await update.effective_message.reply_text(
                err_msg,
                reply_markup=build_city_keyboard(normalized_group),
                parse_mode=ParseMode.HTML,
            )
            return

        await execute_discovery_and_reply(
            update,
            context,
            blood_group=normalized_group,
            city=normalized_city,
        )
        return

    # Case 2: Incomplete single argument provided
    if len(args) == 1:
        group_raw = args[0]
        normalized_group = _normalize_group(group_raw)
        if normalized_group:
            await update.effective_message.reply_text(
                f"🩸 Selected Blood Group: <b>{normalized_group}</b>\nNow choose target city:",
                reply_markup=build_city_keyboard(normalized_group),
                parse_mode=ParseMode.HTML,
            )
            return

    # Case 3: No arguments, interactive selection flow
    prompt = (
        "🩸 <b>Select Required Blood Group:</b>\n"
        "Choose an ABO/Rh blood group to discover reported hospital facilities:"
    )
    await update.effective_message.reply_text(
        prompt,
        reply_markup=build_blood_group_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle interactive inline keyboard button clicks."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    data = query.data or ""

    if data.startswith("group:"):
        selected_group = data.split(":", 1)[1]
        grp_display = html.escape(selected_group if selected_group != "All" else "All Groups")
        await query.edit_message_text(
            f"🩸 Selected Blood Group: <b>{grp_display}</b>\n"
            "Now select target city to search:",
            reply_markup=build_city_keyboard(selected_group),
            parse_mode=ParseMode.HTML,
        )
        return

    if data == "back:groups":
        prompt = (
            "🩸 <b>Select Required Blood Group:</b>\n"
            "Choose an ABO/Rh blood group to discover reported hospital facilities:"
        )
        await query.edit_message_text(
            prompt,
            reply_markup=build_blood_group_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    if data.startswith("search:"):
        parts = data.split(":")
        if len(parts) >= 3:
            selected_group = parts[1]
            selected_city = parts[2]
            grp_display = html.escape(selected_group if selected_group != "All" else "All Groups")
            city_display = html.escape(selected_city if selected_city != "All" else "Delhi & Lucknow")

            await query.edit_message_text(
                f"⏳ Searching e-RaktKosh records for <b>{grp_display}</b> in <b>{city_display}</b>...",
                parse_mode=ParseMode.HTML,
            )

            await execute_discovery_and_reply(
                update,
                context,
                blood_group=selected_group,
                city=selected_city,
                is_callback=True,
            )
