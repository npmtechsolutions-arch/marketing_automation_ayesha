"""The inline AI assists: rewrite, shorten, expand, change tone, hashtags.

Five small operations that share one shape -- take the author's text, ask a
model for a variant, hand it back for the composer to apply in place. They live
here rather than as five copies inside the endpoints because the parts that are
easy to get subtly wrong are the parts they share: which provider was used,
what happens when it fails, and what gets written to ``ai_generations``.

Two rules that differ from the older ``/generate-content`` endpoint, both
deliberate:

* **A failure is a failure.** The older endpoint catches provider errors,
  substitutes mock text with the exception message interpolated into it, and
  records the row as COMPLETED. That puts an internal error string into the
  user's post and makes the AI usage log unable to answer "how often does this
  break". Here a provider error marks the row FAILED and raises; the composer
  says the assist is unavailable and leaves the author's text alone.
* **An explicitly requested provider is honoured or refused**, never silently
  swapped. Being quietly served by a different model than you asked for is the
  same class of problem as a limit that disagrees with the usage endpoint.
"""

import enum
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai_generation import (
    AIGeneration,
    AIGenerationStatus,
    GenerationType,
)

logger = logging.getLogger(__name__)


class Tone(str, enum.Enum):
    """The tones ``change-tone`` accepts.

    An enum rather than free text because the value is interpolated into the
    system prompt: an open string here is an instruction-injection hole, and
    "make it sound like X" where X is a paragraph of the caller's choosing is
    not a tone control.
    """

    PROFESSIONAL = "professional"
    CASUAL = "casual"
    FRIENDLY = "friendly"
    WITTY = "witty"
    AUTHORITATIVE = "authoritative"
    INSPIRATIONAL = "inspirational"
    URGENT = "urgent"
    EMPATHETIC = "empathetic"


class Assist(str, enum.Enum):
    REWRITE = "rewrite"
    SHORTEN = "shorten"
    EXPAND = "expand"
    CHANGE_TONE = "change_tone"
    HASHTAGS = "hashtags"


class ProviderNotConfigured(Exception):
    """The caller named a provider whose key is not set."""


class ProviderFailed(Exception):
    """The provider was called and did not answer usefully."""


# How many hashtags each platform actually wants, and in what register. Not a
# capability on the connector because it is a convention rather than a limit --
# nothing rejects a post for having four hashtags on Instagram, it just reads
# as under-tagged, and thirty on LinkedIn reads as spam.
@dataclass(frozen=True)
class HashtagStyle:
    count: int
    guidance: str


HASHTAG_STYLES: dict[str, HashtagStyle] = {
    "instagram": HashtagStyle(12, "a mix of broad discovery tags and niche ones"),
    "twitter": HashtagStyle(2, "one or two only; more reads as spam on X"),
    "linkedin": HashtagStyle(4, "professional and industry-specific, no slang"),
    "facebook": HashtagStyle(3, "few and broad; hashtags do little on Facebook"),
    "youtube": HashtagStyle(6, "searchable topic tags a viewer would type"),
}
DEFAULT_HASHTAG_STYLE = HashtagStyle(6, "broadly relevant to the topic")

# Below this there is nothing to shorten and asking a model to try produces
# either the same string or a mangled one.
MIN_SHORTEN_CHARS = 40
MAX_INPUT_CHARS = 10_000


def hashtag_style(platform: Optional[str]) -> HashtagStyle:
    return HASHTAG_STYLES.get((platform or "").lower(), DEFAULT_HASHTAG_STYLE)


def platform_limit(platform: Optional[str]) -> Optional[int]:
    """The platform's character limit, from the connector capabilities.

    Shared with the 1.7 validator on purpose: an assist that returns text the
    composer will immediately mark invalid has wasted the author's time and a
    metered AI request.
    """
    if not platform:
        return None
    try:
        from app.connectors.registry import get_provider

        return get_provider(platform).capabilities.max_chars
    except Exception:  # noqa: BLE001 - an unknown slug simply has no limit
        return None


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

# Ordered by preference when the caller expresses none.
_PROVIDERS: tuple[tuple[str, str, str], ...] = (
    ("gemini", "GEMINI_API_KEY", "gemini-3.6-flash"),
    ("openai", "OPENAI_API_KEY", "gpt-4o"),
    ("anthropic", "ANTHROPIC_API_KEY", "claude-sonnet-4-6"),
)


def configured_providers() -> list[str]:
    return [name for name, key, _ in _PROVIDERS if getattr(settings, key, "")]


def resolve_provider(requested: Optional[str] = None) -> tuple[str, str]:
    """(provider, model) for this request.

    A named provider that is not configured raises rather than falling through
    to another one. Silently answering with a different model than the caller
    asked for is indistinguishable, from the outside, from the requested one
    behaving oddly.
    """
    if requested:
        wanted = requested.lower()
        for name, key, model in _PROVIDERS:
            if name == wanted:
                if not getattr(settings, key, ""):
                    raise ProviderNotConfigured(
                        f"'{name}' has no API key configured on this deployment. "
                        f"Configured: {', '.join(configured_providers()) or 'none'}."
                    )
                return name, model
        raise ProviderNotConfigured(
            f"'{requested}' is not a provider we support. "
            f"Choose one of: {', '.join(n for n, _, _ in _PROVIDERS)}."
        )

    for name, key, model in _PROVIDERS:
        if getattr(settings, key, ""):
            return name, model
    # No keys at all: development. Mock rather than fail, so the composer is
    # usable without spending anything.
    return "mock", "mock"


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_COMMON = (
    "You are editing a social media post for the author. Return ONLY the edited "
    "text, with no preamble, no quotation marks around it and no commentary. "
    "Preserve the author's meaning, their language, and any @mentions, URLs or "
    "emoji they used unless the instruction requires changing them."
)


def build_prompts(
    assist: Assist,
    content: str,
    *,
    platform: Optional[str] = None,
    tone: Optional[Tone] = None,
) -> tuple[str, str]:
    """(system_prompt, user_prompt) for one assist."""
    limit = platform_limit(platform)
    limit_note = (
        f" The result must be at most {limit} characters, the {platform} limit."
        if limit
        else ""
    )

    if assist is Assist.REWRITE:
        system = (
            f"{_COMMON} Rewrite the post so it reads better: clearer, more "
            f"engaging, better rhythm. Keep roughly the same length.{limit_note}"
        )
    elif assist is Assist.SHORTEN:
        target = min(limit, max(MIN_SHORTEN_CHARS, int(len(content) * 0.6))) if limit \
            else max(MIN_SHORTEN_CHARS, int(len(content) * 0.6))
        system = (
            f"{_COMMON} Make the post shorter and tighter while keeping every "
            f"important point. Aim for about {target} characters.{limit_note}"
        )
    elif assist is Assist.EXPAND:
        system = (
            f"{_COMMON} Develop the post further: add useful detail, a concrete "
            f"example, or a clearer call to action. Do not invent facts, "
            f"statistics, prices or claims that are not already implied by the "
            f"author's text.{limit_note}"
        )
    elif assist is Assist.CHANGE_TONE:
        system = (
            f"{_COMMON} Rewrite the post in a {(tone or Tone.PROFESSIONAL).value} "
            f"tone. Change the register and word choice, not the substance."
            f"{limit_note}"
        )
    else:  # HASHTAGS
        style = hashtag_style(platform)
        system = (
            "You suggest hashtags for a social media post. Return ONLY a JSON "
            "array of strings, each a hashtag WITHOUT the '#' symbol, lowercase, "
            "no spaces, no punctuation. "
            f"Return about {style.count} of them for "
            f"{platform or 'this platform'}: {style.guidance}. "
            "They must be about the post's actual subject; do not add generic "
            "growth tags that are unrelated to it."
        )
        return system, content

    return system, content


# ---------------------------------------------------------------------------
# Mock, for a deployment with no keys
# ---------------------------------------------------------------------------

def mock_result(assist: Assist, content: str, *, platform=None, tone=None):
    """A believable local answer, clearly derived from the input.

    Deliberately transformational rather than random: a developer must be able
    to see that the assist ran and what it did to their text.
    """
    if assist is Assist.HASHTAGS:
        words = [
            "".join(ch for ch in word.lower() if ch.isalnum())
            for word in content.split()
        ]
        seeds = [w for w in words if len(w) > 4][: hashtag_style(platform).count]
        return seeds or ["marketing", "socialmedia"]
    if assist is Assist.SHORTEN:
        trimmed = " ".join(content.split()[: max(4, len(content.split()) // 2)])
        return trimmed.rstrip(".,;") + "."
    if assist is Assist.EXPAND:
        return content.rstrip() + "\n\nHere is a little more detail on that point."
    if assist is Assist.CHANGE_TONE:
        return f"[{(tone or Tone.PROFESSIONAL).value}] {content}"
    return f"{content} (rewritten)"


# ---------------------------------------------------------------------------
# Running one assist
# ---------------------------------------------------------------------------

@dataclass
class AssistResult:
    result: str | list[str]
    provider: str
    model: str
    generation_id: uuid.UUID
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    duration_ms: Optional[int] = None


def _parse_hashtags(raw: str, limit: int) -> list[str]:
    """Hashtags from whatever the model returned.

    Models drift between a JSON array, a comma list and a line-separated block,
    so all three are accepted rather than failing the request over formatting.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[-1] if "\n" in text else text
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            candidates = [str(x) for x in parsed]
        else:
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        candidates = [
            part for chunk in text.splitlines() for part in chunk.split(",")
        ]

    seen: list[str] = []
    for candidate in candidates:
        raw_candidate = candidate.strip()
        if not raw_candidate:
            continue
        tag = "".join(ch for ch in raw_candidate.lstrip("#").lower() if ch.isalnum())
        if tag and tag not in seen and _looks_like_a_tag(raw_candidate, tag):
            seen.append(tag)
    return seen[:limit]


def _looks_like_a_tag(original: str, cleaned: str) -> bool:
    """Whether a chunk is a hashtag rather than a fragment of a sentence.

    This exists because a model that declines -- "I\'m sorry, I can\'t help with
    that." -- splits into chunks that clean up into plausible-looking strings,
    and returning ``imsorry`` as a hashtag is worse than returning nothing.
    With every chunk rejected the caller gets "no usable hashtags", which is
    the honest answer.

    Deliberately loose: "social media!" is a tag someone means as
    ``socialmedia``. What it rules out is prose -- contractions, and phrases
    longer than a tag ever is. It is a heuristic and it will not catch a
    one-word refusal; the alternative is refusing legitimate multi-word tags,
    which costs the user more often than this costs them.
    """
    if "'" in original or "\u2019" in original:
        return False          # contractions are sentences, not tags
    if len(original.split()) > 3:
        return False
    return 2 <= len(cleaned) <= 30


async def run(
    db: AsyncSession,
    *,
    assist: Assist,
    content: str,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    platform: Optional[str] = None,
    tone: Optional[Tone] = None,
    provider: Optional[str] = None,
    callers: Optional[dict[str, Callable]] = None,
) -> AssistResult:
    """Run one assist and record it.

    ``callers`` exists for tests: the three provider functions live in the
    endpoint module, and injecting them keeps this service free of a circular
    import while letting a test supply its own.
    """
    name, model = resolve_provider(provider)

    generation = AIGeneration(
        id=uuid.uuid4(),
        user_id=user_id,
        account_id=account_id,
        generation_type=(
            GenerationType.HASHTAGS if assist is Assist.HASHTAGS else GenerationType.CAPTION
        ),
        provider=name,
        model=model,
        # The author's text is the prompt; recording it is what makes the log
        # useful for "what did this cost and on what".
        prompt=f"[{assist.value}] {content}"[:10_000],
        status=AIGenerationStatus.PENDING,
    )
    db.add(generation)
    await db.flush()

    system_prompt, user_prompt = build_prompts(
        assist, content, platform=platform, tone=tone
    )
    started = time.time()

    try:
        if name == "mock":
            raw = mock_result(assist, content, platform=platform, tone=tone)
            raw_text = json.dumps(raw) if isinstance(raw, list) else raw
            tokens_in = tokens_out = None
        else:
            if callers is None:
                from app.api.v1.endpoints import ai as ai_endpoints

                callers = {
                    "openai": ai_endpoints._call_openai,
                    "anthropic": ai_endpoints._call_anthropic,
                    "gemini": ai_endpoints._call_gemini,
                }
            raw_text, tokens_in, tokens_out = await callers[name](
                user_prompt, system_prompt, model
            )
    except Exception as exc:  # noqa: BLE001
        generation.status = AIGenerationStatus.FAILED
        generation.error_message = f"{type(exc).__name__}: {exc}"[:500]
        generation.duration_ms = int((time.time() - started) * 1000)
        await db.flush()
        logger.warning("AI assist %s failed via %s: %s", assist.value, name, exc)
        raise ProviderFailed(
            "The AI service did not respond. Your text has not been changed."
        ) from exc

    duration = int((time.time() - started) * 1000)

    if assist is Assist.HASHTAGS:
        value: str | list[str] = _parse_hashtags(
            raw_text, hashtag_style(platform).count
        )
        if not value:
            generation.status = AIGenerationStatus.FAILED
            generation.error_message = "No usable hashtags in the response"
            generation.duration_ms = duration
            await db.flush()
            raise ProviderFailed(
                "The AI service returned no usable hashtags. Try again."
            )
    else:
        value = raw_text.strip().strip('"')
        if not value:
            generation.status = AIGenerationStatus.FAILED
            generation.error_message = "Empty response"
            generation.duration_ms = duration
            await db.flush()
            raise ProviderFailed(
                "The AI service returned nothing. Your text has not been changed."
            )

    generation.response = raw_text[:20_000]
    generation.status = AIGenerationStatus.COMPLETED
    generation.tokens_input = tokens_in
    generation.tokens_output = tokens_out
    generation.duration_ms = duration
    await db.flush()

    return AssistResult(
        result=value,
        provider=name,
        model=model,
        generation_id=generation.id,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        duration_ms=duration,
    )
