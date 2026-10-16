"""Tests for Telegram bot command and callback query handlers."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode

from backend.app.bot.client import DiscoveryApiClient, DiscoveryApiError
from backend.app.bot.config import BotConfig
from backend.app.bot.handlers import (
    build_blood_group_keyboard,
    build_city_keyboard,
    callback_query_handler,
    find_command,
    help_command,
    start_command,
)
from backend.app.schemas.blood_bank import BloodBankListResponse, BloodBankRead, StockReportRead


@pytest.fixture
def mock_context() -> MagicMock:
    """Fixture providing a mock Telegram Context with BotConfig and DiscoveryApiClient."""
    config = BotConfig(
        bot_token="test_mock_token",
        api_base_url="http://mock-api:8000",
        web_url="https://raktsetu.example.org",
        max_facilities=5,
    )
    api_client = MagicMock(spec=DiscoveryApiClient)

    context = MagicMock()
    context.bot_data = {
        "config": config,
        "api_client": api_client,
    }
    context.args = []
    return context


@pytest.fixture
def sample_response() -> BloodBankListResponse:
    """Fixture providing a sample discovery response."""
    now = datetime(2026, 10, 16, 6, 0, 0, tzinfo=timezone.utc)
    return BloodBankListResponse(
        items=[
            BloodBankRead(
                id=10,
                name="AIIMS Blood Centre",
                city="Delhi",
                locality="Ansari Nagar",
                source_type="external_source",
                source_name="e-RaktKosh (MoHFW)",
                stock_reports=[
                    StockReportRead(
                        id=1,
                        blood_bank_id=10,
                        blood_group="O+",
                        blood_component="Whole Blood",
                        units_reported=12,
                        source_name="e-RaktKosh (MoHFW)",
                        verification_status="reported_unverified",
                        source_reported_timestamp=now,
                        retrieval_timestamp=now,
                        data_timestamp=now,
                    )
                ],
            )
        ],
        count=1,
        data_notice="Sample notice",
        data_timestamp=now,
    )


import asyncio


def test_start_command_replies_with_disclaimer(mock_context: MagicMock) -> None:
    """start_command should send the formatted welcome message with medical disclaimer."""
    async def _test() -> None:
        update = MagicMock(spec=Update)
        message = MagicMock()
        message.reply_text = AsyncMock()
        update.effective_message = message

        await start_command(update, mock_context)

        message.reply_text.assert_awaited_once()
        args, kwargs = message.reply_text.call_args
        assert "IMPORTANT MEDICAL &amp; SAFETY DISCLAIMER" in args[0]
        assert kwargs.get("parse_mode") == ParseMode.HTML

    asyncio.run(_test())


def test_help_command_replies_with_helplines(mock_context: MagicMock) -> None:
    """help_command should send the usage guide and emergency guidance without 104/1075."""
    async def _test() -> None:
        update = MagicMock(spec=Update)
        message = MagicMock()
        message.reply_text = AsyncMock()
        update.effective_message = message

        await help_command(update, mock_context)

        message.reply_text.assert_awaited_once()
        args, _ = message.reply_text.call_args
        assert "104" not in args[0]
        assert "1075" not in args[0]
        assert "112" in args[0]
        assert "general emergency" in args[0]

    asyncio.run(_test())


def test_find_command_no_args_prompts_blood_group_keyboard(mock_context: MagicMock) -> None:
    """find_command with no args should send the interactive blood group inline keyboard."""
    async def _test() -> None:
        update = MagicMock(spec=Update)
        message = MagicMock()
        message.reply_text = AsyncMock()
        update.effective_message = message
        mock_context.args = []

        await find_command(update, mock_context)

        message.reply_text.assert_awaited_once()
        args, kwargs = message.reply_text.call_args
        assert "Select Required Blood Group" in args[0]
        assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)

    asyncio.run(_test())


def test_find_command_single_arg_prompts_city_keyboard(mock_context: MagicMock) -> None:
    """find_command with a single valid group should prompt for city selection."""
    async def _test() -> None:
        update = MagicMock(spec=Update)
        message = MagicMock()
        message.reply_text = AsyncMock()
        update.effective_message = message
        mock_context.args = ["O+"]

        await find_command(update, mock_context)

        message.reply_text.assert_awaited_once()
        args, kwargs = message.reply_text.call_args
        assert "Selected Blood Group: <b>O+</b>" in args[0]
        assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)

    asyncio.run(_test())


def test_find_command_valid_direct_args_executes_search(
    mock_context: MagicMock,
    sample_response: BloodBankListResponse,
) -> None:
    """find_command with valid group and city should query API and reply with results."""
    async def _test() -> None:
        update = MagicMock(spec=Update)
        message = MagicMock()
        message.reply_text = AsyncMock()
        update.effective_message = message
        mock_context.args = ["O+", "Delhi"]

        mock_client = mock_context.bot_data["api_client"]
        mock_client.get_blood_banks = AsyncMock(return_value=sample_response)
        mock_client.filter_and_rank_facilities = MagicMock(
            return_value=([sample_response.items[0]], 1)
        )

        await find_command(update, mock_context)

        mock_client.get_blood_banks.assert_awaited_once_with(city="Delhi", blood_group="O+")
        message.reply_text.assert_awaited_once()
        args, _ = message.reply_text.call_args
        assert "AIIMS Blood Centre" in args[0]
        assert "Reported:</b> 12 units (O+ • Whole Blood)" in args[0]

    asyncio.run(_test())


def test_find_command_invalid_group_shows_error_and_keyboard(mock_context: MagicMock) -> None:
    """find_command with invalid blood group should explain error and provide keyboard."""
    async def _test() -> None:
        update = MagicMock(spec=Update)
        message = MagicMock()
        message.reply_text = AsyncMock()
        update.effective_message = message
        mock_context.args = ["XYZ", "Delhi"]

        await find_command(update, mock_context)

        message.reply_text.assert_awaited_once()
        args, kwargs = message.reply_text.call_args
        assert "Invalid blood group" in args[0]
        assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)

    asyncio.run(_test())


def test_find_command_invalid_city_shows_error_and_keyboard(mock_context: MagicMock) -> None:
    """find_command with invalid city should explain error and provide city keyboard."""
    async def _test() -> None:
        update = MagicMock(spec=Update)
        message = MagicMock()
        message.reply_text = AsyncMock()
        update.effective_message = message
        mock_context.args = ["O+", "Kolkata"]

        await find_command(update, mock_context)

        message.reply_text.assert_awaited_once()
        args, kwargs = message.reply_text.call_args
        assert "Invalid city" in args[0]
        assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)

    asyncio.run(_test())


def test_callback_group_selection_shows_city_keyboard(mock_context: MagicMock) -> None:
    """Clicking a blood group button should update the message with city choices."""
    async def _test() -> None:
        update = MagicMock(spec=Update)
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = "group:B+"
        update.callback_query = query

        await callback_query_handler(update, mock_context)

        query.answer.assert_awaited_once()
        query.edit_message_text.assert_awaited_once()
        args, kwargs = query.edit_message_text.call_args
        assert "Selected Blood Group: <b>B+</b>" in args[0]
        assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)

    asyncio.run(_test())


def test_callback_back_to_groups(mock_context: MagicMock) -> None:
    """Clicking 'Back to Blood Groups' should restore the group keyboard."""
    async def _test() -> None:
        update = MagicMock(spec=Update)
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = "back:groups"
        update.callback_query = query

        await callback_query_handler(update, mock_context)

        query.answer.assert_awaited_once()
        query.edit_message_text.assert_awaited_once()
        args, kwargs = query.edit_message_text.call_args
        assert "Select Required Blood Group" in args[0]
        assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)

    asyncio.run(_test())


def test_callback_search_triggers_discovery_and_replies(
    mock_context: MagicMock,
    sample_response: BloodBankListResponse,
) -> None:
    """Clicking a city button should search discovery API and send results."""
    async def _test() -> None:
        update = MagicMock(spec=Update)
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = "search:O+:Lucknow"

        query_msg = MagicMock()
        query_msg.reply_text = AsyncMock()
        query.message = query_msg
        update.callback_query = query

        mock_client = mock_context.bot_data["api_client"]
        mock_client.get_blood_banks = AsyncMock(return_value=sample_response)
        mock_client.filter_and_rank_facilities = MagicMock(
            return_value=([sample_response.items[0]], 1)
        )

        await callback_query_handler(update, mock_context)

        query.answer.assert_awaited_once()
        query.edit_message_text.assert_awaited_once()  # progress status
        mock_client.get_blood_banks.assert_awaited_once_with(city="Lucknow", blood_group="O+")
        query_msg.reply_text.assert_awaited_once()  # formatted results
        args, _ = query_msg.reply_text.call_args
        assert "AIIMS Blood Centre" in args[0]

    asyncio.run(_test())


def test_api_error_returns_graceful_message(mock_context: MagicMock) -> None:
    """When discovery client raises DiscoveryApiError, user receives a safe error message."""
    async def _test() -> None:
        update = MagicMock(spec=Update)
        message = MagicMock()
        message.reply_text = AsyncMock()
        update.effective_message = message
        mock_context.args = ["O+", "Delhi"]

        mock_client = mock_context.bot_data["api_client"]
        mock_client.get_blood_banks = AsyncMock(side_effect=DiscoveryApiError("API offline"))

        await find_command(update, mock_context)

        message.reply_text.assert_awaited_once()
        args, _ = message.reply_text.call_args
        assert "Discovery Service Temporarily Unavailable" in args[0]
        assert "104" not in args[0]
        assert "112" in args[0]
        assert "general emergency" in args[0]

    asyncio.run(_test())
