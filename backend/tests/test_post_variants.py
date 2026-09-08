"""One post, customised per platform.

Two things carry the weight here. Resolution: a variant overrides the master
only where it is not NULL, so a variant that exists to set a first comment
still tracks the master content as it is edited. And validation: each target is
checked against *its own* provider's capabilities, so a 400-character post
fails X and passes LinkedIn rather than failing the whole post.
"""

import uuid

import pytest
from sqlalchemy import select

from app.connectors.base import resolve_content, variant_for_slug
from app.models.media import Media, MediaKind
from app.models.post import Post, PostStatus
from app.models.post_variant import PostVariant

pytestmark = pytest.mark.asyncio

PASSWORD = "hunter2-correct-horse"


@pytest.fixture
async def composer(
    db_session, user_factory, account_factory, organization_factory,
    social_account_factory,
):
    """A post targeting several platforms, ready to customise."""

    async def _make(slugs=("twitter", "linkedin"), content="Master content", **post_kw):
        owner = await user_factory(password=PASSWORD)
        organization = await organization_factory(owner)
        account = await account_factory(owner, organization=organization)
        accounts = [
            await social_account_factory(owner, account, slug=slug) for slug in slugs
        ]
        post = Post(
            id=uuid.uuid4(),
            user_id=owner.id,
            account_id=account.id,
            content=content,
            status=PostStatus.DRAFT,
            target_accounts=[
                {"social_account_id": str(sa.id), "platform_name": sa.account_name}
                for sa in accounts
            ],
            **post_kw,
        )
        db_session.add(post)
        await db_session.flush()
        return {
            "owner": owner, "organization": organization, "account": account,
            "accounts": accounts, "post": post,
            "account_id": account.id, "post_id": post.id,
        }

    return _make


def _url(account_id, post_id, suffix=""):
    return f"/api/v1/accounts/{account_id}/posts/{post_id}{suffix}"


async def _add_variant(db_session, post_id, slug, **fields):
    variant = PostVariant(
        id=uuid.uuid4(), post_id=post_id, platform_slug=slug, **fields
    )
    db_session.add(variant)
    await db_session.flush()
    return variant


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

async def test_no_variant_means_the_master_content(db_session, composer):
    ctx = await composer()
    resolved = resolve_content(ctx["post"], "twitter", None)

    assert resolved.content == "Master content"
    assert resolved.overridden == ()
    assert resolved.is_customised is False


async def test_a_variant_overrides_only_what_it_sets(db_session, composer):
    """The heart of the design: NULL means inherit.

    A variant created to add a first comment must not freeze that platform's
    copy of the content at whatever the master said when it was created.
    """
    ctx = await composer()
    variant = await _add_variant(
        db_session, ctx["post_id"], "twitter", first_comment="More in the replies"
    )

    resolved = resolve_content(ctx["post"], "twitter", variant)
    assert resolved.content == "Master content", "content was not overridden"
    assert resolved.first_comment == "More in the replies"
    assert resolved.overridden == ("first_comment",)


async def test_an_empty_override_is_not_the_same_as_inheriting(db_session, composer):
    """`""` is a deliberate choice to publish no text; None is "use the
    master". Collapsing them would republish the master over the author's
    explicit decision."""
    ctx = await composer()
    variant = await _add_variant(db_session, ctx["post_id"], "twitter", content="")

    resolved = resolve_content(ctx["post"], "twitter", variant)
    assert resolved.content == ""
    assert "content" in resolved.overridden


async def test_each_platform_resolves_independently(db_session, composer):
    ctx = await composer(slugs=("twitter", "linkedin"))
    await _add_variant(
        db_session, ctx["post_id"], "twitter", content="Short version"
    )
    db_session.expire_all()
    post = (
        await db_session.execute(select(Post).where(Post.id == ctx["post_id"]))
    ).scalar_one()

    assert resolve_content(post, "twitter", variant_for_slug(post, "twitter")).content == "Short version"
    assert resolve_content(post, "linkedin", variant_for_slug(post, "linkedin")).content == "Master content"


async def test_variant_lookup_is_case_and_alias_tolerant(db_session, composer):
    ctx = await composer()
    await _add_variant(db_session, ctx["post_id"], "twitter", content="X version")
    db_session.expire_all()
    post = (
        await db_session.execute(select(Post).where(Post.id == ctx["post_id"]))
    ).scalar_one()

    assert variant_for_slug(post, "twitter") is not None
    assert variant_for_slug(post, "TWITTER") is not None
    assert variant_for_slug(post, "linkedin") is None


# ---------------------------------------------------------------------------
# Publishing uses the variant
# ---------------------------------------------------------------------------

async def test_publishing_sends_the_variant_content(
    db_session, composer, monkeypatch
):
    """The point of the whole feature: what a platform receives is its own
    version, not the master."""
    from app.connectors import registry
    from app.connectors.base import Capabilities, PublishResult, SocialProvider
    from app.services import publishing

    sent: dict[str, str] = {}

    class Recorder(SocialProvider):
        slug = "twitter"
        name = "Recorder"
        capabilities = Capabilities(max_chars=280)

        async def publish_post(self, content, media, social_account):
            sent[content.platform] = content.content
            return PublishResult(status="published", external_post_id="rec_1")

    ctx = await composer(slugs=("twitter",))
    await _add_variant(
        db_session, ctx["post_id"], "twitter", content="The X-specific text"
    )
    monkeypatch.setitem(registry._PROVIDERS, "twitter", Recorder())

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _session():
        yield db_session

    monkeypatch.setattr(publishing, "AsyncSessionLocal", lambda: _session())
    monkeypatch.setattr(db_session, "commit", db_session.flush)

    post = (
        await db_session.execute(select(Post).where(Post.id == ctx["post_id"]))
    ).scalar_one()
    jobs = await publishing.create_jobs_for_post(db_session, post)
    for job in jobs:
        await publishing.execute_job(job.id)

    assert sent["twitter"] == "The X-specific text"


async def test_publishing_falls_back_to_the_master(db_session, composer, monkeypatch):
    from app.connectors import registry
    from app.connectors.base import Capabilities, PublishResult, SocialProvider
    from app.services import publishing

    sent: dict[str, str] = {}

    class Recorder(SocialProvider):
        slug = "twitter"
        name = "Recorder"
        capabilities = Capabilities(max_chars=280)

        async def publish_post(self, content, media, social_account):
            sent[content.platform] = content.content
            return PublishResult(status="published", external_post_id="rec_1")

    ctx = await composer(slugs=("twitter",))
    monkeypatch.setitem(registry._PROVIDERS, "twitter", Recorder())

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _session():
        yield db_session

    monkeypatch.setattr(publishing, "AsyncSessionLocal", lambda: _session())
    monkeypatch.setattr(db_session, "commit", db_session.flush)

    post = (
        await db_session.execute(select(Post).where(Post.id == ctx["post_id"]))
    ).scalar_one()
    for job in await publishing.create_jobs_for_post(db_session, post):
        await publishing.execute_job(job.id)

    assert sent["twitter"] == "Master content"


# ---------------------------------------------------------------------------
# Validation matrix
# ---------------------------------------------------------------------------

async def test_over_length_fails_only_the_platform_it_exceeds(
    client, auth_header, db_session, composer
):
    """The composer's hardcoded 2,200 counter is what this replaces: 400
    characters is fine on LinkedIn (3,000) and over the limit on X (280)."""
    ctx = await composer(slugs=("twitter", "linkedin"), content="A" * 400)

    response = await client.post(
        _url(ctx["account_id"], ctx["post_id"], "/validate"),
        headers=auth_header(ctx["owner"]),
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["valid"] is False
    by_platform = {p["platform"]: p for p in body["platforms"]}

    assert by_platform["twitter"]["ok"] is False
    assert by_platform["twitter"]["character_limit"] == 280
    assert by_platform["twitter"]["character_count"] == 400
    assert any(e["field"] == "content" for e in by_platform["twitter"]["errors"])

    assert by_platform["linkedin"]["ok"] is True
    assert by_platform["linkedin"]["character_limit"] == 3000
    assert by_platform["linkedin"]["errors"] == []


async def test_a_variant_can_make_an_over_length_post_valid(
    client, auth_header, db_session, composer
):
    """Which is the reason variants exist -- trim for X without touching what
    LinkedIn receives."""
    ctx = await composer(slugs=("twitter", "linkedin"), content="A" * 400)
    await _add_variant(db_session, ctx["post_id"], "twitter", content="Short enough")

    body = (
        await client.post(
            _url(ctx["account_id"], ctx["post_id"], "/validate"),
            headers=auth_header(ctx["owner"]),
        )
    ).json()

    assert body["valid"] is True
    by_platform = {p["platform"]: p for p in body["platforms"]}
    assert by_platform["twitter"]["character_count"] == len("Short enough")
    assert by_platform["linkedin"]["character_count"] == 400


async def test_hashtags_count_toward_the_limit(
    client, auth_header, db_session, composer
):
    """They are stored separately but published in the body, so a count that
    ignores them under-reports and the author finds out at publish time."""
    ctx = await composer(
        slugs=("twitter",), content="A" * 270, hashtags=["marketing", "socialmedia"]
    )

    body = (
        await client.post(
            _url(ctx["account_id"], ctx["post_id"], "/validate"),
            headers=auth_header(ctx["owner"]),
        )
    ).json()
    assert body["platforms"][0]["character_count"] > 270
    assert body["valid"] is False


async def test_an_empty_post_is_refused(client, auth_header, composer):
    ctx = await composer(slugs=("twitter",), content="")
    body = (
        await client.post(
            _url(ctx["account_id"], ctx["post_id"], "/validate"),
            headers=auth_header(ctx["owner"]),
        )
    ).json()
    assert body["valid"] is False
    assert "post nothing" in body["errors"][0]["message"]


async def test_a_post_with_no_targets_is_refused(
    client, auth_header, db_session, user_factory, account_factory
):
    owner = await user_factory(password=PASSWORD)
    account = await account_factory(owner)
    post = Post(
        id=uuid.uuid4(), user_id=owner.id, account_id=account.id,
        content="Nowhere to go", status=PostStatus.DRAFT, target_accounts=[],
    )
    db_session.add(post)
    await db_session.flush()

    body = (
        await client.post(
            _url(account.id, post.id, "/validate"), headers=auth_header(owner)
        )
    ).json()
    assert body["valid"] is False
    assert body["errors"][0]["field"] == "target_accounts"


async def test_media_rules_come_from_the_provider(
    client, auth_header, db_session, composer, user_factory
):
    """X's connector drops media silently, so its Capabilities report
    supports_images=False -- and attaching an image has to be an error rather
    than a surprise at publish time."""
    ctx = await composer(slugs=("twitter", "linkedin"))
    image = Media(
        id=uuid.uuid4(), account_id=ctx["account_id"], filename="pic.png",
        s3_key=f"media/{ctx['account_id']}/{uuid.uuid4().hex}.png",
        mime_type="image/png", kind=MediaKind.IMAGE, size_bytes=1000,
        width=100, height=100, alt_text="Described",
    )
    db_session.add(image)
    await db_session.flush()
    ctx["post"].media_urls = [str(image.id)]
    await db_session.flush()

    body = (
        await client.post(
            _url(ctx["account_id"], ctx["post_id"], "/validate"),
            headers=auth_header(ctx["owner"]),
        )
    ).json()
    by_platform = {p["platform"]: p for p in body["platforms"]}

    assert by_platform["twitter"]["ok"] is False
    assert any("images" in e["message"] for e in by_platform["twitter"]["errors"])
    assert by_platform["linkedin"]["ok"] is True


async def test_missing_alt_text_warns_without_blocking(
    client, auth_header, db_session, composer
):
    """Worth telling an author about; refusing to let them schedule over it
    would be the tool overruling them."""
    ctx = await composer(slugs=("linkedin",))
    image = Media(
        id=uuid.uuid4(), account_id=ctx["account_id"], filename="undescribed.png",
        s3_key=f"media/{ctx['account_id']}/{uuid.uuid4().hex}.png",
        mime_type="image/png", kind=MediaKind.IMAGE, size_bytes=1000,
    )
    db_session.add(image)
    await db_session.flush()
    ctx["post"].media_urls = [str(image.id)]
    await db_session.flush()

    body = (
        await client.post(
            _url(ctx["account_id"], ctx["post_id"], "/validate"),
            headers=auth_header(ctx["owner"]),
        )
    ).json()
    alt = [e for e in body["errors"] if e["field"] == "alt_texts"]
    assert alt and alt[0]["severity"] == "warning"
    assert body["valid"] is True, "a warning must not block"


async def test_oversized_video_fails_on_the_platform_that_caps_it(
    client, auth_header, db_session, composer
):
    ctx = await composer(slugs=("instagram",))
    video = Media(
        id=uuid.uuid4(), account_id=ctx["account_id"], filename="long.mp4",
        s3_key=f"media/{ctx['account_id']}/{uuid.uuid4().hex}.mp4",
        mime_type="video/mp4", kind=MediaKind.VIDEO, size_bytes=5_000_000,
        duration_seconds=600.0,  # Instagram caps at 90
    )
    db_session.add(video)
    await db_session.flush()
    ctx["post"].media_urls = [str(video.id)]
    await db_session.flush()

    body = (
        await client.post(
            _url(ctx["account_id"], ctx["post_id"], "/validate"),
            headers=auth_header(ctx["owner"]),
        )
    ).json()
    assert body["valid"] is False
    assert any("600s" in e["message"] for e in body["errors"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

async def test_variant_crud(client, auth_header, db_session, composer):
    ctx = await composer()
    headers = auth_header(ctx["owner"])
    base = _url(ctx["account_id"], ctx["post_id"], "/variants")

    created = await client.put(
        f"{base}/twitter", headers=headers,
        json={"content": "Short", "first_comment": "Thread below"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["platform_slug"] == "twitter"
    assert set(created.json()["overrides"]) == {"content", "first_comment"}

    listing = await client.get(base, headers=headers)
    assert len(listing.json()) == 1

    updated = await client.put(
        f"{base}/twitter", headers=headers, json={"content": "Shorter"}
    )
    assert updated.json()["content"] == "Shorter"
    assert updated.json()["first_comment"] == "Thread below", (
        "an omitted field must keep its value, not be cleared"
    )

    removed = await client.delete(f"{base}/twitter", headers=headers)
    assert removed.status_code == 200
    assert "follows the master" in removed.json()["message"]
    assert (await client.get(base, headers=headers)).json() == []


async def test_variant_slug_is_normalised(client, auth_header, composer):
    """"x", "X (Twitter)" and "twitter" address one variant -- otherwise a
    post could carry two versions for the same platform."""
    ctx = await composer()
    headers = auth_header(ctx["owner"])
    base = _url(ctx["account_id"], ctx["post_id"], "/variants")

    await client.put(f"{base}/x", headers=headers, json={"content": "A"})
    await client.put(f"{base}/twitter", headers=headers, json={"content": "B"})

    listing = (await client.get(base, headers=headers)).json()
    assert len(listing) == 1
    assert listing[0]["platform_slug"] == "twitter"
    assert listing[0]["content"] == "B"


async def test_preview_matches_what_publishing_would_send(
    client, auth_header, db_session, composer
):
    """It uses the same resolver, so a preview cannot disagree with what goes
    out -- which is the only way a preview is worth showing."""
    ctx = await composer()
    await _add_variant(db_session, ctx["post_id"], "twitter", content="X copy")

    headers = auth_header(ctx["owner"])
    tw = (await client.get(
        _url(ctx["account_id"], ctx["post_id"], "/variants/twitter/preview"),
        headers=headers,
    )).json()
    li = (await client.get(
        _url(ctx["account_id"], ctx["post_id"], "/variants/linkedin/preview"),
        headers=headers,
    )).json()

    assert tw["content"] == "X copy" and tw["overrides"] == ["content"]
    assert li["content"] == "Master content" and li["overrides"] == []


async def test_deleting_an_absent_variant_is_404(client, auth_header, composer):
    ctx = await composer()
    response = await client.delete(
        _url(ctx["account_id"], ctx["post_id"], "/variants/youtube"),
        headers=auth_header(ctx["owner"]),
    )
    assert response.status_code == 404


async def test_variants_require_content_create(
    client, auth_header, composer, user_factory, member_factory
):
    from app.models.team_member import InvitationStatus, TeamRole

    ctx = await composer()
    viewer = await user_factory()
    await member_factory(
        viewer, ctx["account"], role=TeamRole.VIEWER,
        invitation_status=InvitationStatus.ACCEPTED,
    )
    base = _url(ctx["account_id"], ctx["post_id"], "/variants")

    assert (await client.get(base, headers=auth_header(viewer))).status_code == 200
    assert (
        await client.put(f"{base}/twitter", headers=auth_header(viewer),
                         json={"content": "x"})
    ).status_code == 403


async def test_another_workspace_cannot_reach_the_variants(
    client, auth_header, composer, user_factory, account_factory
):
    ctx = await composer()
    stranger = await user_factory()
    await account_factory(stranger, name="Stranger")

    response = await client.get(
        _url(ctx["account_id"], ctx["post_id"], "/variants"),
        headers=auth_header(stranger),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Cascade
# ---------------------------------------------------------------------------

async def test_variants_are_removed_with_the_post(db_session, composer):
    """A variant without its post is unreachable rows accumulating forever."""
    ctx = await composer()
    await _add_variant(db_session, ctx["post_id"], "twitter", content="X")
    await _add_variant(db_session, ctx["post_id"], "linkedin", content="LI")

    post = (
        await db_session.execute(select(Post).where(Post.id == ctx["post_id"]))
    ).scalar_one()
    await db_session.delete(post)
    await db_session.flush()

    remaining = (
        await db_session.execute(
            select(PostVariant).where(PostVariant.post_id == ctx["post_id"])
        )
    ).scalars().all()
    assert remaining == []


async def test_one_variant_per_platform(db_session, composer):
    """Two would make "which one publishes?" ambiguous at exactly the moment
    it matters."""
    from sqlalchemy.exc import IntegrityError

    ctx = await composer()
    await _add_variant(db_session, ctx["post_id"], "twitter", content="First")
    with pytest.raises(IntegrityError):
        await _add_variant(db_session, ctx["post_id"], "twitter", content="Second")
    await db_session.rollback()
