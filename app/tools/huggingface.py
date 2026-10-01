"""Tools backed by Hugging Face: Hub search and hosted open-source models."""

import io
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app import db
from app.tools.base import Tool, ToolContext, ToolError

HUB_API = "https://huggingface.co/api"


# --- Hub search (no token needed) -------------------------------------------


class HubSearchInput(BaseModel):
    kind: Literal["models", "datasets", "spaces"] = "models"
    query: str = Field(default="", description="Search terms. Empty = no text filter.")
    task: str = Field(
        default="",
        description="Models only: pipeline tag, e.g. 'text-generation', "
        "'text-to-image', 'automatic-speech-recognition'.",
    )
    sort: Literal["trendingScore", "downloads", "likes", "createdAt", "lastModified"] = Field(
        default="trendingScore", description="'createdAt' = newest first."
    )
    limit: int = Field(default=8, ge=1, le=20)


async def _hub_search(inp: HubSearchInput, ctx: ToolContext) -> str:
    params: dict = {"sort": inp.sort, "direction": -1, "limit": inp.limit}
    if inp.query:
        params["search"] = inp.query
    if inp.task and inp.kind == "models":
        params["pipeline_tag"] = inp.task
    items = await ctx.cached_get_json(f"{HUB_API}/{inp.kind}", params)
    if not items:
        raise ToolError("Nothing found on the Hugging Face Hub")
    prefix = {"models": "", "datasets": "datasets/", "spaces": "spaces/"}[inp.kind]
    lines = []
    for it in items:
        bits = [f"{it.get('likes', 0)} likes"]
        if it.get("downloads") is not None:
            bits.append(f"{it['downloads']} downloads/month")
        if it.get("pipeline_tag"):
            bits.append(it["pipeline_tag"])
        when = it.get("createdAt") or it.get("lastModified")
        if when:
            bits.append(f"created {when[:10]}")
        lines.append(
            f"- {it['id']} ({', '.join(bits)})\n  https://huggingface.co/{prefix}{it['id']}"
        )
    return "\n".join(lines)


hub_search = Tool(
    name="search_huggingface_hub",
    description="Search the Hugging Face Hub for open-source AI models, datasets or Spaces - "
    "trending, most downloaded or newest. Use for questions about the latest open models.",
    input_model=HubSearchInput,
    handler=_hub_search,
)


# --- Hosted models (need HF_TOKEN) -------------------------------------------


def _need_hf(ctx: ToolContext):
    if ctx.hf is None:
        raise ToolError("Hugging Face inference is not configured (set HF_TOKEN)")
    return ctx.hf


class ImageInput(BaseModel):
    prompt: str = Field(description="Detailed description of the image.", max_length=1500)
    width: int = Field(default=1024, ge=256, le=1536)
    height: int = Field(default=1024, ge=256, le=1536)


async def _generate_image(inp: ImageInput, ctx: ToolContext) -> str:
    if ctx.db is None:
        raise ToolError("Image storage is unavailable")
    model = ctx.settings.hf_image_model
    try:
        image = await _need_hf(ctx).text_to_image(
            inp.prompt, model=model, width=inp.width, height=inp.height
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Image generation failed ({model}): {e}") from e
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    image_id = await db.save_image(ctx.db, inp.prompt, model, buf.getvalue())
    return (
        f"Image generated with {model}. Show it to the user by including this exact "
        f"Markdown in your answer: ![{inp.prompt[:80]}](/api/images/{image_id}.png)"
    )


generate_image = Tool(
    name="generate_image",
    description="Generate an image from a text prompt with an open-source diffusion model "
    "(FLUX.1 by default) hosted on Hugging Face.",
    input_model=ImageInput,
    handler=_generate_image,
    requires_hf_token=True,
)


class ClassifyInput(BaseModel):
    texts: list[str] = Field(
        description="One or more texts to classify (e.g. reviews, headlines).",
        min_length=1,
        max_length=20,
    )
    mode: Literal["sentiment", "zero_shot"] = Field(
        default="sentiment",
        description="'sentiment' = positive/neutral/negative; 'zero_shot' = your own labels.",
    )
    labels: list[str] = Field(
        default_factory=list, description="Candidate labels, required for zero_shot.", max_length=10
    )

    @model_validator(mode="after")
    def _labels_for_zero_shot(self):
        if self.mode == "zero_shot" and len(self.labels) < 2:
            raise ValueError("zero_shot needs at least two labels")
        return self


async def _classify(inp: ClassifyInput, ctx: ToolContext) -> str:
    hf = _need_hf(ctx)
    s = ctx.settings
    model = s.hf_sentiment_model if inp.mode == "sentiment" else s.hf_zero_shot_model
    out = []
    for i, text in enumerate(inp.texts, 1):
        try:
            if inp.mode == "sentiment":
                result = await hf.text_classification(text[:2000], model=model)
            else:
                result = await hf.zero_shot_classification(
                    text[:2000], inp.labels, model=model, multi_label=False
                )
        except Exception as e:
            raise ToolError(f"Classification failed ({model}): {e}") from e
        scores = ", ".join(f"{r.label}: {r.score:.2f}" for r in result)
        out.append(f"{i}. {text[:80]!r} -> {scores}")
    return f"Model: {model}\n" + "\n".join(out)


classify_text = Tool(
    name="classify_text",
    description="Classify texts with specialised open-source models on Hugging Face: sentiment "
    "analysis, or zero-shot classification into labels you choose. Gives consistent, "
    "reproducible scores for batches of texts.",
    input_model=ClassifyInput,
    handler=_classify,
    requires_hf_token=True,
)
