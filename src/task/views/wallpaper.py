from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from io import BytesIO
import math

from adrf.requests import AsyncRequest
from adrf.viewsets import ViewSet
from django.core import signing
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from PIL import Image, ImageColor, ImageDraw, ImageFont
from rest_framework import status
from rest_framework.response import Response

from domain.enums.status_type import StatusType
from task.models import Task


def _day_bounds_from_iso(value: str | None):
    tz = timezone.get_current_timezone()
    now = timezone.localtime(timezone.now(), tz)
    base_date = now.date()
    if value:
        try:
            base_date = datetime.strptime(value, "%Y-%m-%d").date()
        except Exception:
            base_date = now.date()
    start = timezone.make_aware(datetime.combine(base_date, time.min), tz)
    end = start + timedelta(days=1)
    return start, end


def _parse_int(value: str | None, default: int):
    try:
        v = int(value or "")
        return v
    except Exception:
        return default


def _hex_or_none(value):
    if not value:
        return None
    s = str(value).strip()
    if s.startswith("#") and (len(s) == 7 or len(s) == 9):
        return s
    return None


def _load_font(size: int):
    for name in ["DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"]:
        try:
            return ImageFont.truetype(name, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _rgb(color: str, fallback: str):
    try:
        return ImageColor.getrgb(color)
    except Exception:
        return ImageColor.getrgb(fallback)


@dataclass(frozen=True)
class _Timed:
    title: str
    start_ts: int
    end_ts: int
    color: str | None


@dataclass(frozen=True)
class _TaskItem:
    title: str
    due_ts: int | None
    color: str | None


def _xorshift32(seed: int):
    x = seed & 0xFFFFFFFF
    while True:
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17) & 0xFFFFFFFF
        x ^= (x << 5) & 0xFFFFFFFF
        yield x & 0xFFFFFFFF


def _time_hhmm(ts: int):
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return ["—"]

    words = text.split()
    lines: list[str] = []

    def fits(s: str) -> bool:
        try:
            return draw.textlength(s, font=font) <= max_width
        except Exception:
            return len(s) <= max(6, max_width // 10)

    current = ""
    for w in words:
        if not current:
            if fits(w):
                current = w
                continue
            chunk = ""
            for ch in w:
                candidate = chunk + ch
                if fits(candidate):
                    chunk = candidate
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = ch
            if chunk:
                lines.append(chunk)
            current = ""
            continue

        candidate = f"{current} {w}"
        if fits(candidate):
            current = candidate
            continue

        lines.append(current)
        if fits(w):
            current = w
        else:
            chunk = ""
            for ch in w:
                candidate2 = chunk + ch
                if fits(candidate2):
                    chunk = candidate2
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = ch
            current = chunk

    if current:
        lines.append(current)

    return lines


def _render_wallpaper(
    *,
    width: int,
    height: int,
    date_iso: str,
    now_ts: int,
    day_start_ts: int,
    day_end_ts: int,
    timed: list[_Timed],
    items: list[_TaskItem],
    completed: int,
    total: int,
    seed: int,
):
    bg = _rgb("#0b0f17", "#0b0f17")
    grid = _rgb("#23283b", "#23283b")
    text = _rgb("#eef2ff", "#eef2ff")
    muted = _rgb("#9aa3b2", "#9aa3b2")
    accent = _rgb("#6c5ce7", "#6c5ce7")

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    pad = int(width * 0.13)
    top = int(height * 0.04)

    font_title = _load_font(int(height * 0.048))
    font_big = _load_font(int(height * 0.085))
    font_mid = _load_font(int(height * 0.028))
    font_small = _load_font(int(height * 0.022))

    remaining = max(0, total - completed)
    percent = int(round((completed / total) * 100)) if total > 0 else 0

    cx = width // 2
    cy = top + int(height * 0.30)
    r = int(min(width, height) * 0.18)
    ring_w = max(10, int(r * 0.14))

    bbox = (cx - r, cy - r, cx + r, cy + r)
    draw.ellipse(bbox, outline=grid, width=ring_w)

    if total > 0 and completed > 0:
        start_angle = -90
        end_angle = start_angle + (360 * completed / total)
        draw.arc(bbox, start=start_angle, end=end_angle, fill=accent, width=ring_w)

    pulse_t = now_ts / 7.5

    prng = _xorshift32(seed)
    particles = 140
    for _ in range(particles):
        v = next(prng)
        a = (v % 3600) / 10.0
        phase = (next(prng) % 6283) / 1000.0
        pulse = 0.65 + 0.35 * math.sin(pulse_t + phase)
        u = next(prng)
        jitter = ((u % 2000) / 2000.0) * (ring_w * 1.2 * pulse) - (ring_w * 0.6 * pulse)
        rr = r + jitter
        px = int(cx + rr * math.cos(math.radians(a)))
        py = int(cy + rr * math.sin(math.radians(a)))
        s = 2 + (next(prng) % 4)
        s = max(2, int(round(s * (0.85 + 0.3 * pulse))))
        col = accent if (next(prng) % 100) < 28 else grid
        alpha = 140 if col == accent else 90
        alpha = int(round(alpha * (0.75 + 0.35 * pulse)))
        dot = Image.new("RGBA", (s * 2 + 2, s * 2 + 2), (0, 0, 0, 0))
        ddraw = ImageDraw.Draw(dot)
        ddraw.ellipse((1, 1, 1 + s * 2, 1 + s * 2), fill=(col[0], col[1], col[2], alpha))
        img.paste(dot, (px - s - 1, py - s - 1), dot)

    remaining_text = str(remaining)
    w_num = draw.textlength(remaining_text, font=font_big)
    draw.text((cx - w_num / 2, cy - int(height * 0.06)), remaining_text, fill=text, font=font_big)

    label = "осталось задач"
    w_label = draw.textlength(label, font=font_mid)
    draw.text((cx - w_label / 2, cy + int(height * 0.02)), label, fill=muted, font=font_mid)

    stats = f"{completed}/{total} · {percent}%"
    w_stats = draw.textlength(stats, font=font_small)
    draw.text((cx - w_stats / 2, cy + int(height * 0.06)), stats, fill=muted, font=font_small)

    list_top = cy + r + int(height * 0.06)
    row_gap = int(height * 0.010)

    list_pad = max(pad, int(width * 0.18))
    x_title = list_pad
    x_due = width - list_pad
    y = list_top

    line_h = max(18, int(height * 0.026))
    bottom = height - int(height * 0.08)

    for i, item in enumerate(items):
        if y >= bottom:
            break

        dot_r = int(line_h * 0.24)
        dot_x = x_title
        dot_y = y + line_h // 2
        col = _rgb(_hex_or_none(item.color) or "#23283b", "#23283b")
        draw.ellipse((dot_x, dot_y - dot_r, dot_x + dot_r * 2, dot_y + dot_r), fill=col)

        due = ""
        if item.due_ts:
            due = _time_hhmm(item.due_ts)
        due_w = draw.textlength(due, font=font_small) if due else 0
        if due:
            due_w = draw.textlength(due, font=font_small)
            draw.text((x_due - due_w, y), due, fill=muted, font=font_small)

        title_x = dot_x + dot_r * 2 + int(line_h * 0.35)
        title_max_w = int(x_due - due_w - title_x - int(line_h * 0.4))
        lines = _wrap_text(draw, item.title, font_small, max(60, title_max_w))
        if due:
            max_lines = 2
        else:
            max_lines = 3
        lines = lines[:max_lines]
        for li, ln in enumerate(lines):
            draw.text((title_x, y + li * line_h), ln, fill=text, font=font_small)

        row_h = line_h * len(lines)
        y = y + row_h + row_gap
        if y < bottom:
            draw.line((list_pad, y - row_gap // 2, width - list_pad, y - row_gap // 2), fill=grid, width=1)
    return img



class TaskWallpaperAsyncViewSet(ViewSet):
    async def today(self, request: AsyncRequest):
        token = request.query_params.get("token")
        if not token:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            payload = signing.loads(token, salt="effi_time_wallpaper", max_age=60 * 60 * 24 * 30)
            user_id = int(payload.get("uid"))
        except Exception:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        day_start, day_end = _day_bounds_from_iso(request.query_params.get("date"))
        tz = timezone.get_current_timezone()
        now = timezone.localtime(timezone.now(), tz)
        date_iso_local = timezone.localtime(day_start, tz).date().strftime("%Y-%m-%d")

        width = _parse_int(request.query_params.get("w"), 1170)
        height = _parse_int(request.query_params.get("h"), 2532)
        width = max(720, min(2048, width))
        height = max(1280, min(4096, height))

        timed_qs = (
            Task.objects.filter(
                user_id=user_id,
                started_at__isnull=False,
                started_at__lt=day_end,
            )
            .filter(Q(finished_at__gt=day_start) | Q(finished_at__isnull=True))
            .select_related("status")
            .order_by("started_at")
        )

        timed = []
        timed_ids = set()
        timed_completed = 0
        async for t in timed_qs:
            end_dt = t.finished_at or now
            s = max(timezone.localtime(t.started_at, tz), timezone.localtime(day_start, tz))
            e = min(timezone.localtime(end_dt, tz), timezone.localtime(day_end, tz))
            if e <= s:
                continue
            timed.append(
                _Timed(
                    title=t.name,
                    start_ts=int(s.timestamp()),
                    end_ts=int(e.timestamp()),
                    color=getattr(t.status, "color", None),
                )
            )
            timed_ids.add(t.id)
            if getattr(t.status, "type", None) == StatusType.completed.value:
                timed_completed += 1

        items = [
            _TaskItem(
                title=t.title,
                due_ts=t.end_ts,
                color=t.color,
            )
            for t in timed
        ]

        deadline_qs = (
            Task.objects.filter(
                user_id=user_id,
                deadline_at__isnull=False,
                deadline_at__gte=day_start,
                deadline_at__lt=day_end,
            )
            .exclude(id__in=timed_ids)
            .select_related("status")
        )

        async for t in deadline_qs.order_by("deadline_at", "id"):
            due = timezone.localtime(t.deadline_at, tz)
            items.append(
                _TaskItem(
                    title=t.name,
                    due_ts=int(due.timestamp()),
                    color=getattr(t.status, "color", None),
                )
            )

        items.sort(key=lambda x: (x.due_ts or 0, x.title.lower()))

        total = len(timed) + await deadline_qs.acount()
        completed = timed_completed + await deadline_qs.filter(status__type=StatusType.completed.value).acount()

        seed = (int(date_iso_local.replace("-", "")) if (date_iso_local and "-" in date_iso_local) else 0) ^ (user_id * 2654435761) ^ (total << 8) ^ completed

        img = _render_wallpaper(
            width=width,
            height=height,
            date_iso=date_iso_local,
            now_ts=int(now.timestamp()),
            day_start_ts=int(timezone.localtime(day_start, tz).timestamp()),
            day_end_ts=int(timezone.localtime(day_end, tz).timestamp()),
            timed=timed,
            items=items,
            completed=completed,
            total=total,
            seed=seed,
        )

        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        data = buf.getvalue()

        resp = HttpResponse(data, content_type="image/png")
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp["Pragma"] = "no-cache"
        return resp
