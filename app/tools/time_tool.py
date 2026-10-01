from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolContext, ToolError


class TimeInput(BaseModel):
    timezone: str = Field(default="UTC", description="IANA timezone, e.g. 'Europe/Paris'.")


async def _now(inp: TimeInput, ctx: ToolContext) -> str:
    try:
        tz = ZoneInfo(inp.timezone)
    except ZoneInfoNotFoundError as e:
        raise ToolError(f"Unknown timezone: {inp.timezone}") from e
    now = datetime.now(tz)
    return f"{now.isoformat(timespec='seconds')} ({now.strftime('%A')}, {inp.timezone})"


current_time = Tool(
    name="get_current_time",
    description="Get the current date and time in a timezone. Use whenever the answer depends "
    'on today\'s date ("latest", "this week", ages, deadlines).',
    input_model=TimeInput,
    handler=_now,
)
