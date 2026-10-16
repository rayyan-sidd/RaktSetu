"""Clinical and provenance text formatter for RaktSetu Telegram Bot."""

from datetime import datetime, timezone
import html
from typing import Optional

from backend.app.schemas.blood_bank import BloodBankRead, StockReportRead

STALE_HOURS_THRESHOLD = 24.0


def _format_utc_datetime(dt: Optional[datetime]) -> str:
    """Format datetime as UTC ISO string without microseconds."""
    if not dt:
        return "Not reported"
    utc_dt = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    utc_dt = utc_dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%d %H:%M UTC")


def _is_stale(dt: Optional[datetime], now: Optional[datetime] = None) -> bool:
    """Determine if a source timestamp is older than 24 hours."""
    if not dt:
        return False
    ref_now = now or datetime.now(timezone.utc)
    utc_dt = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    diff = (ref_now - utc_dt).total_seconds()
    return diff > (STALE_HOURS_THRESHOLD * 3600)


def format_start_message(web_url: Optional[str] = None) -> str:
    """Format welcome message for /start command with critical medical disclaimers."""
    url_section = f"\n🌐 <b>Web Console:</b> {html.escape(web_url)}\n" if web_url else ""
    return (
        "🩸 <b>RaktSetu (रक्तसेतु) — Blood Bank Discovery</b>\n"
        "<i>Bridging the gap between need and voluntary help.</i>\n\n"
        "📍 <b>Initial Scope:</b> Delhi &amp; Lucknow transfusion centers\n"
        "📋 <b>Source:</b> Official e-RaktKosh (MoHFW) snapshot feeds\n\n"
        "⚠️ <b>IMPORTANT MEDICAL &amp; SAFETY DISCLAIMER:</b>\n"
        "RaktSetu is a technical prototype and informational coordination platform. "
        "It is <b>NOT</b> an emergency medical dispatch system and does <b>NOT</b> guarantee "
        "physical blood availability.\n\n"
        "All quantities displayed are <b>unverified source snapshots</b>. Always contact "
        "and verify availability directly with the blood bank before traveling.\n\n"
        "<b>Available Commands:</b>\n"
        "• <code>/find</code> — Launch guided interactive blood search\n"
        "• <code>/find &lt;group&gt; &lt;city&gt;</code> — Quick search (e.g. <code>/find O+ Delhi</code>)\n"
        "• <code>/help</code> — Detailed instructions &amp; emergency helplines\n"
        f"{url_section}"
    )


def format_help_message(web_url: Optional[str] = None) -> str:
    """Format /help response with usage, data provenance, and emergency guidance."""
    url_section = f"\n🌐 <b>Web Portal:</b> {html.escape(web_url)}\n" if web_url else ""
    return (
        "📖 <b>RaktSetu Bot Usage Guide</b>\n\n"
        "<b>How to Search:</b>\n"
        "1. <b>Interactive:</b> Send <code>/find</code> to pick your blood group and target city via buttons.\n"
        "2. <b>Direct:</b> Send <code>/find &lt;Group&gt; &lt;City&gt;</code>\n"
        "   Examples:\n"
        "   • <code>/find O+ Delhi</code>\n"
        "   • <code>/find A- Lucknow</code>\n"
        "   • <code>/find B+ All</code>\n\n"
        "<b>Supported Blood Groups:</b> A+, A-, B+, B-, AB+, AB-, O+, O-\n"
        "<b>Supported Cities:</b> Delhi, Lucknow, All\n\n"
        "<b>Data Provenance &amp; Verification:</b>\n"
        "• Real government records from e-RaktKosh (MoHFW) are shown by default.\n"
        "• Snapshots older than 24 hours are clearly marked as <b>Stale</b>.\n"
        "• Feed reports are unverified and not a physical shelf inventory guarantee.\n\n"
        "🚨 <b>Emergency &amp; Verification Guidance:</b>\n"
        "• <b>112</b> — India's national general emergency number (for immediate police, fire, or ambulance assistance; note: 112 is general emergency assistance, not a blood bank helpline).\n"
        "• Always contact the hospital or blood bank facility directly to verify current stock before traveling.\n"
        f"{url_section}"
    )


def format_facility_card(
    bank: BloodBankRead,
    blood_group: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    """Format a single blood bank facility card with strict safe wording."""
    name = html.escape(bank.name)
    locality = html.escape(bank.locality or "Area Unspecified")
    city = html.escape(bank.city)
    category = f" • {html.escape(bank.category)}" if bank.category else ""

    lines = [
        f"🏥 <b>{name}</b>",
        f"📍 <i>{locality}, {city}</i>{category}",
    ]

    # Filter reports to queried group and include only recognized external reports
    relevant_reports: list[StockReportRead] = [
        r
        for r in bank.stock_reports
        if r.verification_status == "reported_unverified"
        and (blood_group is None or blood_group == "All" or r.blood_group == blood_group)
    ]

    positive_reports = [r for r in relevant_reports if r.units_reported > 0]

    if positive_reports:
        for r in positive_reports:
            comp = html.escape(r.blood_component)
            grp = html.escape(r.blood_group)
            lines.append(f"💉 <b>Reported:</b> {r.units_reported} units ({grp} • {comp})")
            lines.append("   <i>(Unverified snapshot • Availability not guaranteed)</i>")

            # Freshness indicator handling
            if r.freshness_indicator == "live_stock_badge" or (
                not r.source_reported_timestamp and r.freshness_indicator
            ):
                lines.append(
                    "   🟢 <b>Portal Indicator:</b> Live Stock Badge\n"
                    "   <i>Portal indicator without exact hospital update time; not a physical stock guarantee.</i>"
                )
            elif r.source_reported_timestamp:
                ts_str = _format_utc_datetime(r.source_reported_timestamp)
                is_stale = _is_stale(r.source_reported_timestamp, now=now)
                if is_stale:
                    lines.append(
                        f"   🕒 <b>Hospital Reported:</b> {ts_str}\n"
                        "   ⚠️ <b>Stale Report (&gt;24h old):</b> Inventory may not reflect current physical stock."
                    )
                else:
                    lines.append(f"   🕒 <b>Hospital Reported:</b> {ts_str}")
            elif r.retrieval_timestamp:
                ret_str = _format_utc_datetime(r.retrieval_timestamp)
                lines.append(f"   🕒 <b>Feed Retrieved:</b> {ret_str} (Hospital update time not reported)")
    else:
        lines.append(
            "⚪ <b>No stock reported in feed</b> • <i>Not confirmed out of stock</i>\n"
            "   <i>Source feed did not report positive units for this query.</i>"
        )

    source_label = html.escape(bank.source_name or "e-RaktKosh (MoHFW)")
    lines.append(f"📋 <b>Source:</b> {source_label} (Snapshot)")
    return "\n".join(lines)


def format_discovery_results(
    facilities: list[BloodBankRead],
    total_count: int,
    blood_group: Optional[str] = None,
    city: Optional[str] = None,
    web_url: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    """Format full discovery results message (capped at top facilities)."""
    grp_display = html.escape(blood_group if blood_group and blood_group != "All" else "All Groups")
    city_display = html.escape(city if city and city != "All" else "Delhi & Lucknow")
    displayed_count = len(facilities)

    header = (
        f"🔍 <b>Blood Bank Discovery Results</b>\n"
        f"<b>Target:</b> {grp_display} • {city_display}\n"
        f"<b>Reported Facilities:</b> Found {total_count} (showing top {displayed_count})\n"
        "📋 <i>Source: e-RaktKosh (MoHFW) Snapshot Feed</i>\n"
        "⚠️ <i>Reported numbers are unverified online data. Always verify directly with the blood bank.</i>\n\n"
        "────────────────────\n"
    )

    cards = [format_facility_card(b, blood_group=blood_group, now=now) for b in facilities]
    body = "\n\n────────────────────\n".join(cards)

    footer_lines = ["\n────────────────────"]
    if total_count > displayed_count:
        footer_lines.append(
            f"ℹ️ <i>Showing top {displayed_count} facilities prioritizing reported stock.</i>"
        )

    if web_url:
        clean_url = html.escape(web_url)
        footer_lines.append(f"🌐 <b>Explore all {total_count} facilities:</b> {clean_url}")

    footer_lines.append(
        "📞 <b>Important:</b> Contact the facility to cross-match and confirm blood units before dispatching."
    )

    return header + body + "\n" + "\n".join(footer_lines)


def format_empty_results(
    blood_group: Optional[str] = None,
    city: Optional[str] = None,
    web_url: Optional[str] = None,
) -> str:
    """Format message when no matching facilities report positive units."""
    grp_display = html.escape(blood_group if blood_group and blood_group != "All" else "All Groups")
    city_display = html.escape(city if city and city != "All" else "Delhi & Lucknow")

    target_grp = html.escape(blood_group if blood_group and blood_group != "All" else "O+")
    url_section = f"\n🌐 <b>Web Console:</b> {html.escape(web_url)}\n" if web_url else ""
    return (
        f"🔍 <b>No Reported Facilities Found</b>\n\n"
        f"No blood bank records in <b>{city_display}</b> reported stock for blood group <b>{grp_display}</b>.\n\n"
        "⚠️ <b>Important Context:</b>\n"
        "This indicates that no facilities in the public online feed reported positive units. "
        "It does <b>NOT</b> guarantee that blood is physically absent across all hospitals.\n\n"
        "<b>Recommended Immediate Actions:</b>\n"
        "• Contact regional hospital emergency departments or blood banks directly to confirm availability\n"
        "• For life-threatening emergencies, call <b>112</b> (India's national general emergency number; note: this is general emergency assistance, not a blood bank helpline)\n"
        f"• Try searching across all cities with <code>/find {target_grp} All</code>\n"
        f"{url_section}"
    )


def format_api_error_message() -> str:
    """Format user-safe error message when discovery API is unreachable."""
    return (
        "⚠️ <b>Discovery Service Temporarily Unavailable</b>\n\n"
        "Unable to retrieve blood bank records from the discovery API at this moment.\n"
        "Please try again shortly.\n\n"
        "🚨 <b>If this is a medical emergency:</b>\n"
        "• Contact your nearest hospital emergency department directly to check physical blood availability.\n"
        "• For life-threatening emergencies, dial <b>112</b> (India's national general emergency number; note: this is general emergency assistance, not a blood bank helpline)."
    )
