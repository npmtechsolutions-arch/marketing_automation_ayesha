import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import the OpenAI client; fall back gracefully if not installed
try:
    from openai import OpenAI  # type: ignore[import-untyped]
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]


class AIService:
    """Wrapper around the OpenAI API for marketing content generation.

    When no API key is configured the service returns deterministic mock
    responses so that development and testing can proceed without a paid key.
    """

    def __init__(self) -> None:
        self.client = None
        if OpenAI and settings.OPENAI_API_KEY:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # ------------------------------------------------------------------
    # Content generation
    # ------------------------------------------------------------------

    def generate_content(
        self,
        prompt: str,
        platforms: list[str],
        tone: str,
        business_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate marketing copy tailored to the requested platforms and
        tone.  Returns a dict keyed by platform with generated text."""
        system_prompt = (
            "You are an expert social media marketing copywriter. "
            f"Write in a {tone} tone. "
            "Tailor the content for each requested platform, respecting "
            "character limits and best practices."
        )
        if business_context:
            system_prompt += f"\n\nBusiness context: {business_context}"

        user_prompt = (
            f"Create marketing content for the following platforms: "
            f"{', '.join(platforms)}.\n\nBrief: {prompt}"
        )

        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=2000,
                )
                content = response.choices[0].message.content
                return {
                    "status": "success",
                    "content": {p: content for p in platforms},
                    "model": "gpt-4o",
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                }
            except Exception as exc:
                logger.exception("OpenAI content generation failed")
                return self._mock_content(platforms, prompt, error=str(exc))

        return self._mock_content(platforms, prompt)

    # ------------------------------------------------------------------
    # Strategy generation
    # ------------------------------------------------------------------

    def generate_strategy(
        self,
        goal: str,
        budget: float,
        platforms: list[str],
        business_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a marketing strategy recommendation."""
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a senior marketing strategist. Provide "
                                "actionable strategy recommendations in JSON format."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Goal: {goal}\nBudget: ${budget}\n"
                                f"Platforms: {', '.join(platforms)}\n"
                                f"Context: {business_context or 'N/A'}"
                            ),
                        },
                    ],
                    temperature=0.7,
                    max_tokens=3000,
                )
                return {
                    "status": "success",
                    "strategy": response.choices[0].message.content,
                    "model": "gpt-4o",
                }
            except Exception as exc:
                logger.exception("OpenAI strategy generation failed")
                return self._mock_strategy(goal, platforms, error=str(exc))

        return self._mock_strategy(goal, platforms)

    # ------------------------------------------------------------------
    # Topic suggestions
    # ------------------------------------------------------------------

    def suggest_topics(
        self, business_context: dict[str, Any] | None = None
    ) -> list[str]:
        """Return a list of trending topic suggestions."""
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a social media trend analyst. "
                                "Return exactly 10 topic ideas as a JSON array of strings."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Suggest 10 trending content topics. "
                                f"Context: {business_context or 'general marketing'}"
                            ),
                        },
                    ],
                    temperature=0.9,
                    max_tokens=1000,
                )
                import json

                return json.loads(response.choices[0].message.content or "[]")
            except Exception:
                logger.exception("OpenAI topic suggestion failed")

        return [
            "Behind-the-scenes content showing your team culture",
            "Customer success stories and testimonials",
            "Industry trend analysis and hot takes",
            "Quick tips and how-to guides",
            "Product feature spotlights with use cases",
            "User-generated content campaigns",
            "Interactive polls and Q&A sessions",
            "Seasonal and holiday-themed content",
            "Data-driven infographics",
            "Collaboration announcements and partnerships",
        ]

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    def generate_image(self, prompt: str) -> str:
        """Generate a marketing image and return its URL."""
        if self.client:
            try:
                response = self.client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                return response.data[0].url or ""
            except Exception:
                logger.exception("OpenAI image generation failed")

        # Mock fallback
        return "https://placehold.co/1024x1024/6366f1/ffffff?text=AI+Generated+Image"

    # ------------------------------------------------------------------
    # Mock helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_content(
        platforms: list[str], prompt: str, error: str | None = None
    ) -> dict[str, Any]:
        mock = {
            p: (
                f"[Mock {p} content] Engaging post about: {prompt[:100]}... "
                "#marketing #growth"
            )
            for p in platforms
        }
        result: dict[str, Any] = {
            "status": "mock",
            "content": mock,
            "model": "mock",
            "tokens_used": 0,
        }
        if error:
            result["fallback_reason"] = error
        return result

    @staticmethod
    def _mock_strategy(
        goal: str, platforms: list[str], error: str | None = None
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "mock",
            "strategy": {
                "goal": goal,
                "recommended_platforms": platforms,
                "posting_frequency": "3-5 times per week",
                "content_mix": {
                    "educational": "40%",
                    "promotional": "20%",
                    "engagement": "25%",
                    "entertainment": "15%",
                },
                "key_actions": [
                    "Define your brand voice and visual identity",
                    "Create a content calendar with themed days",
                    "Engage with your audience within the first hour of posting",
                    "Analyze top-performing content weekly and iterate",
                ],
            },
            "model": "mock",
        }
        if error:
            result["fallback_reason"] = error
        return result
