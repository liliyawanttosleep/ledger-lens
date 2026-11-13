# -*- coding: utf-8 -*-
"""生成应用图标：一滴“流水”，水滴里是一张收支环形图。输出 icon.png / icon.ico。"""
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
N = 2048  # 超采样画布
K = N / 64  # 设计稿按 64×64 网格


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(size, c0, c1, angle=90):
    """线性渐变。angle=90 自上而下，45 为左上到右下。"""
    w = h = size
    base = Image.linear_gradient("L").resize((w, h))
    if angle == 45:
        base = base.rotate(45, resample=Image.BICUBIC, expand=True)
        s = base.size[0]
        cut = (s - w) // 2
        inner = int(w / math.sqrt(2))
        off = (s - inner) // 2
        base = base.crop((off, off, off + inner, off + inner)).resize((w, h), Image.BICUBIC)
    lut_r = [lerp(c0, c1, i / 255)[0] for i in range(256)]
    lut_g = [lerp(c0, c1, i / 255)[1] for i in range(256)]
    lut_b = [lerp(c0, c1, i / 255)[2] for i in range(256)]
    return Image.merge("RGB", (base.point(lut_r), base.point(lut_g), base.point(lut_b)))


def bezier(p0, p1, p2, p3, n=120):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def droplet_points(cx=32, cy=40, r=17.5, tip=7.5):
    pts = bezier((cx, tip), (cx, tip), (cx - r, cy - 12.5), (cx - r, cy))
    pts += [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(180, -1, -1)]
    pts += bezier((cx + r, cy), (cx + r, cy - 12.5), (cx, tip), (cx, tip))
    return [(x * K, y * K) for x, y in pts]


def build():
    # 背景：深墨蓝圆角方块 + 右上角一抹青色辉光
    bg = gradient(N, (24, 40, 62), (9, 14, 22))
    glow = Image.new("L", (N, N), 0)
    ImageDraw.Draw(glow).ellipse((N * .42, -N * .30, N * 1.22, N * .50), fill=120)
    glow = glow.filter(ImageFilter.GaussianBlur(N * .11))
    bg = Image.composite(Image.new("RGB", (N, N), (58, 196, 190)), bg, glow.point(lambda v: v * .55))
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, N - 1, N - 1), radius=int(N * .225), fill=255)
    icon = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    icon.paste(bg, (0, 0), mask)

    # 水滴
    pts = droplet_points()
    drop = Image.new("L", (N, N), 0)
    ImageDraw.Draw(drop).polygon(pts, fill=255)
    shadow = ImageChops.offset(drop, 0, int(N * .03)).filter(ImageFilter.GaussianBlur(N * .035))
    icon.paste(Image.new("RGB", (N, N), (0, 0, 0)), (0, 0), ImageChops.multiply(shadow.point(lambda v: v * .5), mask))
    icon.paste(gradient(N, (128, 246, 220), (36, 110, 214), 45), (0, 0), drop)
    # 水滴左上的高光
    hl = Image.new("L", (N, N), 0)
    ImageDraw.Draw(hl).ellipse((22.5 * K, 20 * K, 30 * K, 34 * K), fill=150)
    hl = ImageChops.multiply(hl.rotate(22, center=(26 * K, 27 * K)).filter(ImageFilter.GaussianBlur(N * .016)), drop)
    icon.paste(Image.new("RGB", (N, N), (255, 255, 255)), (0, 0), hl.point(lambda v: v * .55))

    # 环形图：白环 + 一段金色（“支出占比”）
    d = ImageDraw.Draw(icon)
    cx, cy, r, w = 32 * K, 40 * K, 8.4 * K, 5.0 * K
    box = (cx - r - w / 2, cy - r - w / 2, cx + r + w / 2, cy + r + w / 2)
    d.arc(box, 0, 360, fill=(255, 255, 255, 255), width=int(w))
    d.arc(box, -90, 20, fill=(255, 190, 64, 255), width=int(w))
    # 用背景色切出两道细缝，让金色段像被“分”出来
    for ang in (-90, 20):
        a = math.radians(ang)
        x0, y0 = cx + (r - w * .62) * math.cos(a), cy + (r - w * .62) * math.sin(a)
        x1, y1 = cx + (r + w * .62) * math.cos(a), cy + (r + w * .62) * math.sin(a)
        d.line((x0, y0, x1, y1), fill=(52, 148, 214, 255), width=int(K * .9))

    out = icon.resize((1024, 1024), Image.LANCZOS)
    out.save(os.path.join(HERE, "icon.png"))
    out.save(os.path.join(HERE, "icon.ico"), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    out.resize((256, 256), Image.LANCZOS).save(os.path.join(HERE, "icon_256.png"))
    print("icon written")


if __name__ == "__main__":
    build()
