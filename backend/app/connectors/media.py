"""Media and content helpers shared by every connector.

Moved verbatim from ``app/services/platform_service.py`` (lines 7-397), which
mixed these platform-agnostic utilities with five platforms' publishing code in
one 1,480-line module. Nothing here knows about a specific platform: it
re-hosts media at a publicly reachable URL, guards against SSRF, normalises
hashtags, and renders an image+audio pair into a video for the platforms that
only accept one.

These are synchronous and blocking on purpose -- ``_render_image_audio_to_video``
shells out to ffmpeg and ``_fetch_to_file`` streams whole files. Providers call
them from inside ``asyncio.to_thread``.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)



def _upload_bytes_to_public_url(data: bytes, filename: str, content_type: str) -> str:
    """Upload raw bytes to a public host (tmpfiles.org). Returns the public URL, or
    an empty string on failure."""
    try:
        import httpx
        import re
        with httpx.Client() as client:
            res = client.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": (filename, data, content_type)},
                timeout=60.0,
            )
            if res.status_code == 200:
                resp_json = res.json()
                if resp_json.get("status") == "success":
                    url = resp_json["data"]["url"]
                    # Fetch the HTML page to parse the new signed direct download URL
                    page_res = client.get(url, timeout=30.0)
                    if page_res.status_code == 200:
                        match = re.search(r'href="(https://tmpfiles\.org/dl/[^"]+)"', page_res.text)
                        if match:
                            direct_url = match.group(1)
                            logger.info("Successfully uploaded and resolved signed direct URL: %s", direct_url)
                            return direct_url
                    # Fallback to the old method if page parsing fails
                    direct_url = url.replace("https://tmpfiles.org/", "https://tmpfiles.org/dl/")
                    logger.warning("Failed to parse signed URL, using fallback: %s", direct_url)
                    return direct_url
            logger.error("Failed to upload media to tmpfiles: status %s, response %s", res.status_code, res.text)
    except Exception as e:
        logger.exception("Error uploading media to public URL: %s", e)
    return ""


def _upload_base64_to_public_url(base64_str: str) -> str:
    try:
        import base64
        if "," in base64_str:
            header, encoded = base64_str.split(",", 1)
        else:
            header, encoded = "", base64_str
        data = base64.b64decode(encoded)

        # Detect content type
        content_type = None
        if header.startswith("data:"):
            parts = header.split(";")
            if parts:
                content_type = parts[0].replace("data:", "")

        if not content_type:
            if "image/jpeg" in header or "image/jpg" in header:
                content_type = "image/jpeg"
            elif "image/gif" in header:
                content_type = "image/gif"
            elif "image/webp" in header:
                content_type = "image/webp"
            elif "video/mp4" in header:
                content_type = "video/mp4"
            elif "video/quicktime" in header:
                content_type = "video/quicktime"
            else:
                content_type = "image/png"

        ext = content_type.split("/")[-1]
        if ext == "quicktime":
            ext = "mov"

        url = _upload_bytes_to_public_url(data, f"file.{ext}", content_type)
        if url:
            return url
    except Exception as e:
        logger.exception("Error converting base64 media to public URL: %s", e)
    return base64_str # Fallback to original


def _download_media_bytes(url: str) -> bytes:
    """Return the raw bytes of a media URL, decoding base64 data URLs directly."""
    if url.startswith("data:"):
        import base64
        encoded = url.split(",", 1)[1] if "," in url else url
        return base64.b64decode(encoded)
    import httpx
    with httpx.Client(follow_redirects=True) as client:
        r = client.get(url, timeout=60.0)
        r.raise_for_status()
        return r.content


def _is_private_host_url(url: str) -> bool:
    """True if ``url`` points at a host the public internet cannot reach.

    AI-generated images are stored under the backend's own ``/uploads`` mount,
    so in local/LAN deployments the URL is unreachable to Meta's servers and has
    to be re-hosted before publishing.
    """
    if not url.startswith(("http://", "https://")):
        return False
    import ipaddress
    import urllib.parse

    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if not host:
        return False
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def _ensure_public_media_url(url: str) -> str:
    """Return a URL that Meta's servers can fetch, re-hosting the media if needed."""
    if url.startswith("data:"):
        logger.info("Converting base64 media data to a public URL...")
        return _upload_base64_to_public_url(url)

    if _is_private_host_url(url):
        logger.info("Media URL %s is not publicly reachable — re-hosting it.", url)
        try:
            data = _download_media_bytes(url)
            filename = url.rsplit("/", 1)[-1].split("?")[0] or "file.png"
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
            content_type = {
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "gif": "image/gif",
                "webp": "image/webp",
                "mp4": "video/mp4",
                "mov": "video/quicktime",
            }.get(ext, "image/png")
            public_url = _upload_bytes_to_public_url(data, filename, content_type)
            if public_url:
                return public_url
        except Exception as e:
            logger.exception("Failed to re-host local media URL: %s", e)

    return url


def _is_public_media_url(url: str) -> bool:
    """True if the URL can be handed straight to a platform's Graph API."""
    return not url.startswith("data:") and not _is_private_host_url(url)


def _first_media_url(post: Any) -> str | None:
    """Extract the first media URL from a post's ``media_urls`` (list or JSON string)."""
    raw = getattr(post, "media_urls", None)
    if not raw:
        return None
    if isinstance(raw, list):
        return raw[0] if raw else None
    if isinstance(raw, str):
        import json
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                return parsed[0]
            return raw
        except json.JSONDecodeError:
            return raw
    return None


def _normalize_hashtags(hashtags: Any) -> list[str]:
    """Turn a post's stored hashtags into clean ``#tag`` tokens.

    Hashtags are stored as a list (usually without the leading '#'). This
    normalizes each: strips whitespace and any leading '#', removes internal
    spaces (a hashtag can't contain them), drops empties, and re-adds a single
    '#'. Accepts a JSON string list too, for safety.
    """
    if not hashtags:
        return []
    if isinstance(hashtags, str):
        import json
        try:
            hashtags = json.loads(hashtags)
        except json.JSONDecodeError:
            hashtags = [hashtags]
    if not isinstance(hashtags, (list, tuple)):
        return []
    result: list[str] = []
    for tag in hashtags:
        if not tag:
            continue
        clean = str(tag).strip().lstrip("#").strip().replace(" ", "")
        if clean:
            result.append(f"#{clean}")
    return result


def _content_with_hashtags(post: Any, limit: int | None = None) -> str:
    """Build the caption/message actually sent to a platform: the post content
    with its hashtags appended on a new line.

    If ``limit`` is given (e.g. Twitter's 280 chars), the content is trimmed so
    that content + hashtags fit, prioritizing keeping the hashtags intact.
    """
    content = (getattr(post, "content", None) or "").strip()
    tags = _normalize_hashtags(getattr(post, "hashtags", None))
    tag_str = " ".join(tags)

    if not tag_str:
        text = content
        if limit is not None and len(text) > limit:
            text = text[: max(0, limit - 3)].rstrip() + "..."
        return text

    sep = "\n\n"
    if limit is None:
        return f"{content}{sep}{tag_str}" if content else tag_str

    # Bounded (e.g. Twitter): keep hashtags, trim content to fit.
    if len(tag_str) >= limit:
        return tag_str[:limit]
    max_content = limit - len(tag_str) - len(sep)
    if max_content <= 0:
        return tag_str
    if len(content) > max_content:
        content = content[: max(0, max_content - 3)].rstrip() + "..."
    return f"{content}{sep}{tag_str}" if content else tag_str


def _assert_public_http_url(url: str) -> None:
    """Guard against SSRF.

    ``media_urls`` / ``*_music_url`` are user-supplied and fetched server-side,
    so a caller could otherwise point them at internal services or the cloud
    metadata endpoint (``169.254.169.254``). Allow only http(s) URLs whose host
    resolves exclusively to public IP addresses.
    """
    import ipaddress
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Refusing to fetch non-http(s) URL: {parsed.scheme or 'no scheme'}")
    host = parsed.hostname
    if not host:
        raise ValueError("Refusing to fetch URL with no host")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve host: {host}") from e

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
            or not ip.is_global
        ):
            raise ValueError(f"Refusing to fetch internal/non-public address for host: {host}")


def _fetch_to_file(url: str, path: str) -> None:
    """Download a URL (or decode a base64 data URL) to a local file path."""
    if url.startswith("data:"):
        import base64
        encoded = url.split(",", 1)[1] if "," in url else url
        with open(path, "wb") as f:
            f.write(base64.b64decode(encoded))
        return

    import httpx

    # SSRF protection: validate the target (and every redirect hop) resolves to
    # a public address before we connect. Redirects are followed manually so an
    # attacker-controlled 3xx cannot bounce us into internal space.
    _assert_public_http_url(url)
    current = url
    with httpx.Client(follow_redirects=False) as client:
        for _ in range(5):
            r = client.get(current, timeout=30.0)
            if r.is_redirect:
                location = r.headers.get("location")
                if not location:
                    break
                current = str(httpx.URL(str(r.url)).join(location))
                _assert_public_http_url(current)
                continue
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)
            return
    raise ValueError("Too many redirects while fetching media URL")


def _render_image_audio_to_video(
    image_url: str, audio_url: str, start_offset: float = 0, duration: float = 15
) -> str:
    """Render a still image + a trimmed audio clip into a vertical MP4 and upload
    it to a public host, returning the public video URL.

    Instagram feed photos cannot carry audio, so the only way to publish a photo
    *with* the user's selected track is to turn it into a short video (Reel).
    """
    import os
    import shutil
    import subprocess
    import tempfile

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError(
            "Cannot attach audio to a photo: the server has no ffmpeg "
            "installed to render the image + music into a video. Install ffmpeg, "
            "or post with a video file."
        )

    try:
        start = max(0.0, float(start_offset or 0))
    except (TypeError, ValueError):
        start = 0.0
    try:
        dur = float(duration) if duration else 15.0
    except (TypeError, ValueError):
        dur = 15.0

    import urllib.parse

    def get_extension(url: str, default: str) -> str:
        if url.startswith("data:"):
            try:
                mime = url.split(";")[0].split(":")[1]
                ext = mime.split("/")[-1]
                if ext == "jpeg":
                    return ".jpg"
                return f".{ext}"
            except Exception:
                return default
        else:
            parsed = urllib.parse.urlparse(url)
            path = parsed.path
            ext = os.path.splitext(path)[1]
            if ext:
                return ext
            return default

    img_ext = get_extension(image_url, ".jpg")
    audio_ext = get_extension(audio_url, ".mp3")

    tmpdir = tempfile.mkdtemp(prefix="ig_reel_")
    img_path = os.path.join(tmpdir, f"image{img_ext}")
    audio_path = os.path.join(tmpdir, f"audio{audio_ext}")
    out_path = os.path.join(tmpdir, "out.mp4")
    try:
        _fetch_to_file(image_url, img_path)
        _fetch_to_file(audio_url, audio_path)

        cmd = [
            ffmpeg, "-y",
            "-loop", "1", "-i", img_path,
            "-ss", str(start), "-i", audio_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-t", str(dur),
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p",
            "-c:v", "libx264", "-profile:v", "high", "-preset", "veryfast", "-r", "30",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart",
            out_path,
        ]
        logger.info("Rendering image + audio into a Reel video (start=%ss, dur=%ss)", start, dur)
        proc = subprocess.run(cmd, capture_output=True, timeout=180)
        if proc.returncode != 0 or not os.path.exists(out_path):
            err = proc.stderr.decode("utf-8", "ignore")[-800:]
            raise ValueError(f"Failed to render image + audio into a video: {err}")

        with open(out_path, "rb") as f:
            video_bytes = f.read()
        url = _upload_bytes_to_public_url(video_bytes, "reel.mp4", "video/mp4")
        if not url.startswith("http"):
            raise ValueError("Failed to upload the rendered Reel video to a public host.")
        return url
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

