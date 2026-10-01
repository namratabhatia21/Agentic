import httpx
import pytest

from app.config import Settings
from app.tools import ALL_TOOLS, TOOLS_BY_NAME, ToolContext
from app.tools.base import ToolError
from app.tools.calculator import safe_eval


@pytest.fixture
async def ctx():
    async with httpx.AsyncClient() as http:
        yield ToolContext(settings=Settings(), http=http)


@pytest.mark.parametrize(
    "expr,expected",
    [("2+3*4", 14), ("(1+2)**3", 27), ("sqrt(16)", 4.0), ("-5 // 2", -3), ("round(pi, 2)", 3.14)],
)
def test_calculator(expr, expected):
    assert safe_eval(expr) == expected


@pytest.mark.parametrize(
    "expr", ["__import__('os')", "open('x')", "2**100000", "1/0", "a.b", "[1,2]"]
)
def test_calculator_rejects_unsafe(expr):
    with pytest.raises(ToolError):
        safe_eval(expr)


def test_tool_names_unique_and_definitions_valid():
    names = [t.name for t in ALL_TOOLS]
    assert len(names) == len(set(names))
    for tool in ALL_TOOLS:
        d = tool.definition()
        assert d["input_schema"]["type"] == "object"
        assert d["input_schema"]["additionalProperties"] is False
        assert d["eager_input_streaming"] is True
        assert len(d["description"]) > 20


async def test_run_validates_input(ctx):
    content, is_error = await TOOLS_BY_NAME["calculator"].run({"expr": "1"}, ctx)
    assert is_error and "Invalid input" in content
    content, is_error = await TOOLS_BY_NAME["calculator"].run("not a dict", ctx)
    assert is_error
    content, is_error = await TOOLS_BY_NAME["calculator"].run({"expression": "6*7"}, ctx)
    assert (content, is_error) == ("42", False)


async def test_time_tool(ctx):
    content, is_error = await TOOLS_BY_NAME["get_current_time"].run(
        {"timezone": "Asia/Kolkata"}, ctx
    )
    assert not is_error and "Asia/Kolkata" in content
    content, is_error = await TOOLS_BY_NAME["get_current_time"].run({"timezone": "Mars/Base"}, ctx)
    assert is_error


async def test_db_tools_without_db(ctx):
    content, is_error = await TOOLS_BY_NAME["query_database"].run({"sql": "select 1"}, ctx)
    assert is_error and "unavailable" in content


async def test_sql_rejects_multiple_statements(ctx):
    ctx.readonly_db = object()
    content, is_error = await TOOLS_BY_NAME["query_database"].run(
        {"sql": "select 1; drop table x"}, ctx
    )
    assert is_error and "single statement" in content


async def test_weather_uses_open_meteo():
    def handler(request: httpx.Request) -> httpx.Response:
        if "geocoding" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"name": "Paris", "country": "France", "latitude": 48.85, "longitude": 2.35}
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "current": {
                    "time": "2026-10-01T12:00",
                    "temperature_2m": 18.2,
                    "apparent_temperature": 17.0,
                    "relative_humidity_2m": 60,
                    "wind_speed_10m": 9,
                    "weather_code": 2,
                },
                "daily": {
                    "time": ["2026-10-01"],
                    "temperature_2m_min": [11],
                    "temperature_2m_max": [19],
                    "precipitation_sum": [0.2],
                    "weather_code": [3],
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        ctx = ToolContext(settings=Settings(), http=http)
        content, is_error = await TOOLS_BY_NAME["get_weather"].run({"location": "Paris"}, ctx)
    assert not is_error
    assert "Paris, France" in content and "18.2°C" in content
