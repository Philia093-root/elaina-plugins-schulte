"""
舒尔特方格训练 — 5×5 回调按钮，按 1→25 顺序点击计时
带web面板，可设置渲染图页脚、配色和返回指令
需开启并配置图床才能发送图片，否则以文本形式发送
"""

import asyncio
import io
import os
import random
import secrets
import sqlite3
import struct
import threading
import time
import urllib.request
from datetime import datetime

import aiohttp.web
from core.base.config import cfg
from core.base.logger import PLUGIN, get_logger
from core.plugin.decorators import handler, on_load, on_unload

# Web 面板扩展（如果可用）
try:
    from core.plugin.web_pages import register_page, register_route, unregister_page, unregister_route
    HAS_WEB_PAGES = True
except ImportError:
    HAS_WEB_PAGES = False

__plugin_meta__ = {
    'name': '舒尔特方格(带web面板)',
    'author': '涟',
    'description': '5×5 舒尔特方格反应力训练，全服 TOP20 排行，个人成绩卡片，带web面板和配色设置',
    'version': '0.9.3',
    'github': 'https://github.com/Philia093-root/elaina-plugins-schulte/',
}

log = get_logger(PLUGIN, '舒尔特')

GRID_SIZE = 5
TOTAL = GRID_SIZE * GRID_SIZE
RANK_LIMIT = 20

# ==================== 预设配色方案 ====================
# 每个方案包含：背景色、头部渐变色(起始, 结束), 强调色, 文字主色, 次级文字色, 装饰透明色, 阴影色, 奖牌色(金,银,铜), 分割线色
PRESET_COLORS = {
    '粉红': {
        'bg': (253, 240, 245),
        'header_start': (255, 105, 180),
        'header_end': (255, 182, 193),
        'accent': (199, 21, 133),
        'text': (45, 30, 40),
        'sub': (177, 135, 152),
        'shadow': (219, 112, 147, 30),
        'deco_alpha': (255, 192, 203, 28),
        'medals': ((255, 182, 193), (238, 130, 170), (197, 101, 130)),
        'divider': (235, 210, 220)
    },
    '薄荷': {
        'bg': (240, 253, 245),
        'header_start': (102, 204, 153),
        'header_end': (153, 230, 204),
        'accent': (0, 153, 102),
        'text': (30, 45, 40),
        'sub': (128, 177, 152),
        'shadow': (112, 219, 147, 30),
        'deco_alpha': (192, 255, 203, 28),
        'medals': ((153, 230, 204), (130, 210, 170), (101, 180, 130)),
        'divider': (210, 240, 220)
    },
    '蓝紫': {
        'bg': (240, 242, 253),
        'header_start': (130, 105, 220),
        'header_end': (182, 165, 240),
        'accent': (80, 40, 180),
        'text': (35, 30, 45),
        'sub': (135, 130, 177),
        'shadow': (147, 112, 219, 30),
        'deco_alpha': (203, 192, 255, 28),
        'medals': ((182, 165, 240), (170, 140, 230), (130, 101, 197)),
        'divider': (220, 210, 235)
    },
    '暖阳': {
        'bg': (253, 248, 240),
        'header_start': (255, 180, 80),
        'header_end': (255, 215, 150),
        'accent': (200, 120, 20),
        'text': (45, 40, 30),
        'sub': (177, 155, 120),
        'shadow': (219, 180, 80, 30),
        'deco_alpha': (255, 225, 180, 28),
        'medals': ((255, 215, 150), (230, 190, 120), (180, 150, 90)),
        'divider': (235, 220, 200)
    },
    '森林': {
        'bg': (240, 248, 235),
        'header_start': (60, 160, 80),
        'header_end': (120, 200, 130),
        'accent': (20, 120, 40),
        'text': (30, 45, 35),
        'sub': (120, 160, 130),
        'shadow': (80, 200, 100, 30),
        'deco_alpha': (180, 240, 190, 28),
        'medals': ((120, 200, 130), (100, 180, 110), (80, 150, 90)),
        'divider': (200, 230, 205)
    },
    '海洋': {
        'bg': (235, 248, 253),
        'header_start': (40, 150, 220),
        'header_end': (120, 200, 240),
        'accent': (0, 90, 180),
        'text': (30, 40, 50),
        'sub': (120, 160, 190),
        'shadow': (80, 160, 220, 30),
        'deco_alpha': (180, 220, 255, 28),
        'medals': ((120, 200, 240), (100, 180, 220), (80, 150, 200)),
        'divider': (200, 225, 240)
    },
    '暮光': {
        'bg': (250, 240, 245),
        'header_start': (200, 80, 130),
        'header_end': (230, 150, 180),
        'accent': (160, 40, 80),
        'text': (50, 30, 40),
        'sub': (180, 130, 150),
        'shadow': (200, 100, 140, 30),
        'deco_alpha': (255, 200, 220, 28),
        'medals': ((230, 150, 180), (210, 130, 160), (180, 100, 130)),
        'divider': (240, 210, 220)
    },
    '樱花': {
        'bg': (255, 245, 248),
        'header_start': (255, 140, 170),
        'header_end': (255, 190, 210),
        'accent': (210, 50, 90),
        'text': (50, 30, 35),
        'sub': (190, 140, 155),
        'shadow': (255, 150, 180, 30),
        'deco_alpha': (255, 210, 225, 28),
        'medals': ((255, 190, 210), (240, 160, 180), (210, 130, 150)),
        'divider': (255, 220, 230)
    },
    '柠檬': {
        'bg': (255, 252, 235),
        'header_start': (255, 210, 50),
        'header_end': (255, 235, 130),
        'accent': (200, 160, 0),
        'text': (50, 45, 20),
        'sub': (190, 175, 100),
        'shadow': (255, 220, 80, 30),
        'deco_alpha': (255, 240, 180, 28),
        'medals': ((255, 235, 130), (240, 210, 100), (210, 180, 70)),
        'divider': (245, 235, 200)
    },
    '薰衣草': {
        'bg': (248, 245, 255),
        'header_start': (170, 130, 220),
        'header_end': (210, 180, 240),
        'accent': (110, 60, 170),
        'text': (40, 30, 50),
        'sub': (160, 140, 190),
        'shadow': (180, 140, 220, 30),
        'deco_alpha': (220, 200, 255, 28),
        'medals': ((210, 180, 240), (190, 160, 220), (160, 130, 200)),
        'divider': (230, 215, 245)
    },
    '珊瑚': {
        'bg': (253, 242, 240),
        'header_start': (255, 120, 100),
        'header_end': (255, 170, 150),
        'accent': (200, 60, 40),
        'text': (50, 35, 30),
        'sub': (190, 140, 130),
        'shadow': (255, 130, 110, 30),
        'deco_alpha': (255, 200, 190, 28),
        'medals': ((255, 170, 150), (240, 150, 130), (210, 120, 100)),
        'divider': (245, 220, 215)
    },
    '冰蓝': {
        'bg': (240, 250, 255),
        'header_start': (80, 190, 230),
        'header_end': (150, 220, 250),
        'accent': (0, 130, 180),
        'text': (30, 45, 55),
        'sub': (130, 175, 200),
        'shadow': (100, 200, 240, 30),
        'deco_alpha': (180, 230, 255, 28),
        'medals': ((150, 220, 250), (130, 200, 230), (100, 170, 200)),
        'divider': (210, 235, 245)
    },
    '蜜桃': {
        'bg': (255, 245, 240),
        'header_start': (255, 160, 130),
        'header_end': (255, 200, 180),
        'accent': (210, 90, 60),
        'text': (50, 35, 30),
        'sub': (200, 150, 135),
        'shadow': (255, 170, 140, 30),
        'deco_alpha': (255, 220, 200, 28),
        'medals': ((255, 200, 180), (240, 180, 160), (210, 150, 130)),
        'divider': (250, 225, 215)
    },
    '星空': {
        'bg': (235, 235, 250),
        'header_start': (80, 60, 160),
        'header_end': (140, 120, 210),
        'accent': (40, 20, 120),
        'text': (30, 25, 50),
        'sub': (140, 130, 180),
        'shadow': (120, 100, 200, 30),
        'deco_alpha': (200, 180, 240, 28),
        'medals': ((140, 120, 210), (120, 100, 190), (100, 80, 160)),
        'divider': (215, 210, 235)
    },
    '抹茶': {
        'bg': (245, 250, 235),
        'header_start': (120, 180, 100),
        'header_end': (170, 210, 140),
        'accent': (60, 130, 40),
        'text': (35, 45, 30),
        'sub': (150, 180, 135),
        'shadow': (130, 200, 110, 30),
        'deco_alpha': (210, 240, 190, 28),
        'medals': ((170, 210, 140), (150, 190, 120), (120, 160, 100)),
        'divider': (225, 235, 210)
    },
    '玫瑰': {
        'bg': (255, 240, 242),
        'header_start': (220, 80, 110),
        'header_end': (240, 150, 170),
        'accent': (180, 40, 70),
        'text': (50, 30, 35),
        'sub': (200, 130, 145),
        'shadow': (220, 100, 130, 30),
        'deco_alpha': (255, 200, 210, 28),
        'medals': ((240, 150, 170), (220, 130, 150), (190, 100, 120)),
        'divider': (250, 215, 220)
    },
    '天空': {
        'bg': (240, 248, 255),
        'header_start': (100, 180, 255),
        'header_end': (160, 210, 255),
        'accent': (30, 120, 220),
        'text': (30, 40, 55),
        'sub': (140, 175, 210),
        'shadow': (110, 190, 255, 30),
        'deco_alpha': (190, 225, 255, 28),
        'medals': ((160, 210, 255), (140, 190, 235), (110, 160, 210)),
        'divider': (215, 235, 250)
    },
    '奶油': {
        'bg': (255, 250, 240),
        'header_start': (255, 210, 150),
        'header_end': (255, 230, 190),
        'accent': (200, 140, 70),
        'text': (50, 40, 30),
        'sub': (200, 175, 140),
        'shadow': (255, 220, 160, 30),
        'deco_alpha': (255, 240, 210, 28),
        'medals': ((255, 230, 190), (240, 210, 170), (210, 180, 140)),
        'divider': (250, 235, 220)
    },
    '浆果': {
        'bg': (250, 235, 240),
        'header_start': (180, 70, 120),
        'header_end': (210, 130, 160),
        'accent': (150, 30, 70),
        'text': (50, 30, 40),
        'sub': (190, 130, 150),
        'shadow': (200, 90, 130, 30),
        'deco_alpha': (240, 200, 215, 28),
        'medals': ((210, 130, 160), (190, 110, 140), (160, 90, 120)),
        'divider': (240, 210, 220)
    },
    '石墨': {
        'bg': (245, 245, 245),
        'header_start': (120, 120, 140),
        'header_end': (180, 180, 200),
        'accent': (60, 60, 80),
        'text': (40, 40, 45),
        'sub': (160, 160, 175),
        'shadow': (160, 160, 180, 30),
        'deco_alpha': (210, 210, 225, 28),
        'medals': ((180, 180, 200), (160, 160, 180), (140, 140, 160)),
        'divider': (220, 220, 230)
    }
}

# ==================== 全局配置变量 ====================
F_text = '昔涟'
F_sign = '♡'
F_sign_enabled = True
COLOR_SCHEME = PRESET_COLORS['粉红']  # 默认
MENU_t = '/返回'  # 返回按钮指令，可在web面板修改

_CONFIG_LOCK = threading.Lock()

def get_menu_btns1():
    return [
        [
            {'text': '开始训练', 'type': 2, 'data': '/开始训练'},
            {'text': '返回', 'type': 2, 'data': MENU_t},
            {'text': '舒尔特排行', 'type': 2, 'data': '/舒尔特排行'},
        ],
    ]

def get_menu_btns2():
    return [
        [
            {'text': '再来一次', 'type': 2, 'data': '/开始训练'},
            {'text': '返回', 'type': 2, 'data': MENU_t},
            {'text': '舒尔特排行', 'type': 2, 'data': '/舒尔特排行'},
        ],
    ]

# ==================== 通用工具 ====================

def _get_bot(event):
    from core.application import get_app
    app = get_app()
    return app.get_bot(event.appid) if app else None

def _get_hosting():
    from core.application import get_app
    app = get_app()
    mm = app.module_manager if app else None
    return mm.get('image_hosting') if mm else None

# ==================== 数据库 ====================

_BASE = os.path.dirname(os.path.abspath(__file__))
_conn_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_sessions: dict[str, dict] = {}
_session_lock = threading.Lock()

def _db_path() -> str:
    data_dir = os.path.join(_BASE, 'data')
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'ShuErTe.db')

def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_db_path(), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS records (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL,
                username    TEXT DEFAULT '',
                group_id    TEXT DEFAULT '',
                duration_ms INTEGER NOT NULL,
                created_at  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_records_duration ON records(duration_ms);
            CREATE INDEX IF NOT EXISTS idx_records_user ON records(user_id);

            -- 配置表
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        _conn.commit()
        log.info('舒尔特数据库: %s', _db_path())
    return _conn

def _now_str() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def _save_record(user_id: str, username: str, duration_ms: int) -> None:
    with _conn_lock:
        _db().execute(
            'INSERT INTO records (user_id, username, group_id, duration_ms, created_at) VALUES (?,?,?,?,?)',
            (user_id, username or '', '', duration_ms, _now_str()),
        )
        _db().commit()

def _best_records(limit: int = RANK_LIMIT) -> list[dict]:
    with _conn_lock:
        rows = _db().execute(
            'SELECT r.user_id, r.username, r.duration_ms, r.created_at '
            'FROM records r '
            'WHERE r.id = ('
            '  SELECT id FROM records '
            '  WHERE user_id = r.user_id '
            '  ORDER BY duration_ms ASC, id ASC '
            '  LIMIT 1'
            ') '
            'ORDER BY r.duration_ms ASC '
            'LIMIT ?',
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]

def _user_best(user_id: str) -> int | None:
    with _conn_lock:
        row = _db().execute(
            'SELECT MIN(duration_ms) AS best FROM records WHERE user_id=?',
            (user_id,),
        ).fetchone()
    if row and row['best'] is not None:
        return int(row['best'])
    return None

def _all_records(limit: int = 20) -> list[dict]:
    """获取最近的记录（用于web面板）"""
    with _conn_lock:
        rows = _db().execute(
            'SELECT id, user_id, username, duration_ms, created_at '
            'FROM records '
            'ORDER BY created_at DESC, id DESC '
            'LIMIT ?',
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]

def _stats() -> dict:
    """统计信息：总人数、总记录数、最快用时"""
    with _conn_lock:
        cur = _db().execute('SELECT COUNT(DISTINCT user_id) AS users, COUNT(*) AS total FROM records')
        row = cur.fetchone()
        users = row['users'] if row else 0
        total = row['total'] if row else 0
        cur = _db().execute('SELECT MIN(duration_ms) AS fastest FROM records')
        row2 = cur.fetchone()
        fastest = row2['fastest'] if row2 and row2['fastest'] is not None else None
    return {'users': users, 'total': total, 'fastest': fastest}

# ==================== 配置管理 ====================

def _init_config():
    """从数据库加载配置到全局变量，若不存在则写入默认值"""
    global F_text, F_sign, F_sign_enabled, COLOR_SCHEME, MENU_t
    with _CONFIG_LOCK:
        cur = _db().execute('SELECT key, value FROM config')
        config = {row['key']: row['value'] for row in cur.fetchall()}
        defaults = {
            'f_text': '昔涟',
            'f_sign': '♡',
            'f_sign_enabled': 'true',
            'color_scheme': '粉红',
            'menu_t': '/返回'
        }
        for k, v in defaults.items():
            if k not in config:
                config[k] = v
                with _conn_lock:
                    _db().execute('REPLACE INTO config (key, value) VALUES (?, ?)', (k, v))
                    _db().commit()
        F_text = config['f_text']
        F_sign = config['f_sign']
        F_sign_enabled = config['f_sign_enabled'].lower() == 'true'
        scheme_name = config.get('color_scheme', '粉红')
        if scheme_name in PRESET_COLORS:
            COLOR_SCHEME = PRESET_COLORS[scheme_name]
        else:
            COLOR_SCHEME = PRESET_COLORS['粉红']
        MENU_t = config.get('menu_t', '/返回')

def _set_config(key: str, value: str):
    """更新配置并立即保存到数据库，同时更新全局变量"""
    global F_text, F_sign, F_sign_enabled, COLOR_SCHEME, MENU_t
    with _CONFIG_LOCK:
        with _conn_lock:
            _db().execute('REPLACE INTO config (key, value) VALUES (?, ?)', (key, value))
            _db().commit()
        if key == 'f_text':
            F_text = value
        elif key == 'f_sign':
            F_sign = value
        elif key == 'f_sign_enabled':
            F_sign_enabled = value.lower() == 'true'
        elif key == 'color_scheme':
            if value in PRESET_COLORS:
                COLOR_SCHEME = PRESET_COLORS[value]
        elif key == 'menu_t':
            MENU_t = value

def _get_config(key: str) -> str | None:
    """获取单个配置（从数据库直接读取，保证最新）"""
    with _conn_lock:
        row = _db().execute('SELECT value FROM config WHERE key=?', (key,)).fetchone()
        return row['value'] if row else None

# ==================== 头像工具 ====================

def _download_avatar(user_id: str, appid: str, size=128) -> 'Image.Image | None':
    url = f'https://q.qlogo.cn/qqapp/{appid}/{user_id}/5'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = resp.read()
        from PIL import Image
        img = Image.open(io.BytesIO(data)).convert('RGBA')
        img = img.resize((size, size), Image.LANCZOS)
        return img
    except Exception as e:
        log.debug('头像下载失败 %s: %s', user_id, e)
        return None

def _circle_avatar(img, size=128):
    from PIL import Image, ImageDraw
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result

# ==================== 排行榜图片渲染 ====================

try:
    from PIL import Image, ImageDraw, ImageFilter
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

_RANK_FONT_DIR = os.path.join(_BASE, 'fonts')
_RANK_FONT_PATHS = [
    '/usr/share/fonts/truetype/msyh.ttc',
    'C:/Windows/Fonts/msyh.ttc',
    'C:/Windows/Fonts/simhei.ttf',
    '/System/Library/Fonts/PingFang.ttc',
    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
]

_RANK_FONT = None
_RANK_FONT_BOLD = None

def _rank_find_font():
    global _RANK_FONT, _RANK_FONT_BOLD
    if _RANK_FONT:
        return _RANK_FONT, _RANK_FONT_BOLD

    for p in _RANK_FONT_PATHS:
        if os.path.isfile(p):
            _RANK_FONT = p
            _RANK_FONT_BOLD = p
            return _RANK_FONT, _RANK_FONT_BOLD

    if os.path.isdir(_RANK_FONT_DIR):
        for root, _, files in os.walk(_RANK_FONT_DIR):
            for f in sorted(files):
                if f.lower().endswith(('.ttf', '.ttc', '.otf')):
                    p = os.path.join(root, f)
                    _RANK_FONT = p
                    _RANK_FONT_BOLD = p
                    return _RANK_FONT, _RANK_FONT_BOLD

    return None, None

def _rank_font(size, bold=False):
    if not _HAS_PIL:
        return None
    reg, bold_path = _rank_find_font()
    if not reg:
        return None
    from PIL import ImageFont
    return ImageFont.truetype(bold_path if bold and bold_path else reg, size)

def _rank_fmt_duration(ms: int) -> str:
    return f'{ms / 1000:.2f}s'

def _rank_mask_id(uid: str) -> str:
    return uid[:3] + '****' if len(uid) > 6 else uid

# ==================== 图片绘制（主题配色） ====================

def _get_color_scheme():
    """获取当前配色方案"""
    return COLOR_SCHEME

def _rank_card_shadow(img, box, radius, scheme):
    x0, y0, x1, y1 = box
    pad = 32
    layer = Image.new('RGBA', (x1 - x0 + pad * 2, y1 - y0 + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(
        (pad, pad + 4, pad + (x1 - x0), pad + 4 + (y1 - y0)),
        radius=radius, fill=scheme['shadow'],
    )
    layer = layer.filter(ImageFilter.GaussianBlur(10))
    img.paste(layer, (x0 - pad, y0 - pad), layer)

def _rank_card(img, d, box, scheme, radius=18):
    _rank_card_shadow(img, box, radius, scheme)
    d.rounded_rectangle(box, radius=radius, fill=(255, 255, 255))

def _draw_tian_logo(img, cx, cy, size=96,
                    solid=(255, 255, 255, 115),
                    hollow=(255, 255, 255, 115),
                    width=1,
                    gap=6,
                    clockwise=True):
    """
    绘制一个顺时针倾斜32°的田字形装饰（四个小方块之间有间距）。
    cx, cy：图案旋转后中心点坐标
    size：旋转前整体边长（2x2 小正方形的总边长）
    gap：四个小方块之间的间距（像素）
    """
    if not _HAS_PIL:
        return

    a = (size - gap) // 2  # 每个小方块的实际边长（扣除间距）
    offset = gap // 2      # 间距偏移

    # 创建透明图层，先画轴对齐的田字
    layer = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # 对角一对实心：右上、左下实心
    d.rectangle((offset + a, offset, size - offset, offset + a), fill=solid)          # 右上
    d.rectangle((offset, offset + a, offset + a, size - offset), fill=solid)          # 左下

    # 对角一对空心：左上、右下空心（只画描边）
    d.rectangle((offset, offset, offset + a, offset + a), outline=hollow, width=width)          # 左上
    d.rectangle((offset + a, offset + a, size - offset, size - offset), outline=hollow, width=width)  # 右下

    # 顺时针旋转32°：Pillow 的 rotate 正角度为逆时针，所以传 -32
    angle = -32 if clockwise else 32
    rotated = layer.rotate(angle, expand=True, resample=Image.BICUBIC)

    # 以(cx, cy)为中心粘贴到主图
    img.paste(rotated, (cx - rotated.width // 2, cy - rotated.height // 2), rotated)

# ---------- 排行榜双栏卡片 ----------

def _draw_card(img, d, x, y, card_w, card_h, rows_sub, start_rank, row_h, appid, scheme):
    _rank_card(img, d, (x, y, x + card_w, y + card_h), scheme)

    if not rows_sub:
        tip_f = _rank_font(24)
        sign = F_sign if F_sign_enabled else ''
        tip = f"{sign} 等你来挑战 {sign}" if sign else "等你来挑战"
        tw = d.textlength(tip, tip_f)
        d.text((x + (card_w - tw) / 2, y + card_h / 2 - 12), tip, font=tip_f, fill=scheme['sub'])
        return

    avatar_size = 44
    medals = scheme['medals']
    for i, r in enumerate(rows_sub):
        iy = y + 20 + i * row_h
        rank_no = start_rank + i

        # 仅前3名绘制背景
        if rank_no <= 3:
            medal = medals[min(i, 2)] if start_rank == 1 else medals[min(rank_no - 1, 2)]
            mx0, my0 = x + 24, iy + 18
            mx1, my1 = x + 56, iy + 50
            d.ellipse((mx0, my0, mx1, my1), fill=medal)
            num_color = (255, 255, 255)
        else:
            # 无背景，使用主题色
            mx0, my0 = x + 24, iy + 18  # 保持占位，便于对齐
            mx1, my1 = x + 56, iy + 50
            num_color = scheme['text']

        nf = _rank_font(22, bold=True)
        tnum = str(rank_no)
        tw = d.textlength(tnum, nf)
        # 数字居中绘制（有背景时居中于椭圆，无背景时居中于相同区域）
        d.text((mx0 + (32 - tw) / 2, my0 + 2), tnum, font=nf, fill=num_color)

        ax = x + 72
        ay = iy + 18
        avatar_drawn = False
        if appid:
            av = _download_avatar(r['user_id'], appid, avatar_size)
            if av:
                av = _circle_avatar(av, avatar_size)
                img.paste(av, (ax, ay), av)
                avatar_drawn = True

        name_x = ax + (avatar_size + 14 if avatar_drawn else 0)
        name = r.get('username') or _rank_mask_id(r['user_id'])
        uf = _rank_font(26, bold=True)
        d.text((name_x, iy + 14), name, font=uf, fill=scheme['text'])

        dur = _rank_fmt_duration(r['duration_ms'])
        sf = _rank_font(24, bold=True)
        sw = d.textlength(dur, sf)
        d.text((x + card_w - 24 - sw, iy + 16), dur, font=sf, fill=scheme['accent'])

        if i < len(rows_sub) - 1:
            d.line(
                (x + 24, iy + row_h - 4, x + card_w - 24, iy + row_h - 4),
                fill=scheme['divider'], width=1,
            )

def render_rank_image(rows, my_best=None, appid=None):
    if not _HAS_PIL:
        return None
    if not _rank_find_font()[0]:
        return None
    if not rows:
        return None

    scheme = _get_color_scheme()

    W = 1100
    pad = 36
    gap = 30
    header_h = 130
    row_h = 82
    footer_h = 70

    left_rows = rows[:10]
    right_rows = rows[10:20]
    max_rows = max(len(left_rows), len(right_rows))

    card_w = (W - 2 * pad - gap) // 2
    card_h = max_rows * row_h + 40

    card_y = header_h - 30
    H = card_y + card_h + footer_h + pad

    img = Image.new('RGB', (W, H), scheme['bg'])
    d = ImageDraw.Draw(img)

    # 渐变头部
    for i in range(header_h):
        t = i / header_h
        r = int(scheme['header_start'][0] + (scheme['header_end'][0] - scheme['header_start'][0]) * t)
        g = int(scheme['header_start'][1] + (scheme['header_end'][1] - scheme['header_start'][1]) * t)
        b = int(scheme['header_start'][2] + (scheme['header_end'][2] - scheme['header_start'][2]) * t)
        d.line([(0, i), (W, i)], fill=(r, g, b))

    # 头部装饰：半透明圆形
    deco = Image.new('RGBA', (W, header_h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    dd.ellipse((W - 280, -140, W + 60, 200), fill=scheme['deco_alpha'])
    dd.ellipse((-100, 100, 180, 380), fill=scheme['deco_alpha'])
    img.paste(deco, (0, 0), deco)

    # 右上角田字装饰（放大、半透明，位于顶栏和排行卡片之间）
    _draw_tian_logo(img, W - 110, 80, size=96,
                    solid=(255, 255, 255, 115),
                    hollow=(255, 255, 255, 115),
                    width=4,
                    gap=3)

    # 标题与副标题
    title_f = _rank_font(38, bold=True)
    d.text((pad, 38), '舒尔特方格 · 排行榜', font=title_f, fill=(255, 255, 255))
    sub_f = _rank_font(22)
    sign = F_sign if F_sign_enabled else ''
    sub_text = f"{sign} {F_text} · 舒尔特方格 {sign}" if sign else f"{F_text} · 舒尔特方格"
    d.text((pad, 92), sub_text, font=sub_f, fill=(255, 228, 241))

    # 左右两栏卡片
    left_x = pad
    _draw_card(img, d, left_x, card_y, card_w, card_h, left_rows, 1, row_h, appid, scheme)

    right_x = pad + card_w + gap
    _draw_card(img, d, right_x, card_y, card_w, card_h, right_rows, 11, row_h, appid, scheme)

    # 页脚
    footer_f = _rank_font(20)
    sign = F_sign if F_sign_enabled else ''
    if sign:
        footer = f"{sign}{F_text} · 舒尔特方格"
    else:
        footer = f"{F_text} · 舒尔特方格"
    if my_best:
        footer += f'  |  你的最佳 {_rank_fmt_duration(my_best)}'
        if sign:
            footer += sign
    else:
        if sign:
            footer += sign
    fw = d.textlength(footer, footer_f)
    d.text(((W - fw) / 2, H - 42), footer, font=footer_f, fill=scheme['sub'])

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()

# ---------- 个人成绩卡片 ----------

def render_personal_result_image(user_id, username, duration_ms, my_best, appid):
    """渲染个人挑战完成后的粉色成绩卡片（使用当前配色）"""
    if not _HAS_PIL:
        return None
    if not _rank_find_font()[0]:
        return None

    scheme = _get_color_scheme()

    W = 600
    H = 380
    header_h = 90
    card_pad = 30
    card_w = W - 2 * card_pad
    card_h = H - header_h - card_pad - 10
    card_x, card_y = card_pad, header_h - 20

    img = Image.new('RGB', (W, H), scheme['bg'])
    d = ImageDraw.Draw(img)

    # 渐变头部
    for i in range(header_h):
        t = i / header_h
        r = int(scheme['header_start'][0] + (scheme['header_end'][0] - scheme['header_start'][0]) * t)
        g = int(scheme['header_start'][1] + (scheme['header_end'][1] - scheme['header_start'][1]) * t)
        b = int(scheme['header_start'][2] + (scheme['header_end'][2] - scheme['header_start'][2]) * t)
        d.line([(0, i), (W, i)], fill=(r, g, b))

    # 右上角田字装饰
    _draw_tian_logo(img, W - 55, 45, size=56,
                    solid=(255, 255, 255, 115),
                    hollow=(255, 255, 255, 115),
                    width=4,
                    gap=3)

    # 标题
    title_f = _rank_font(32, bold=True)
    d.text((card_pad, 28), '舒尔特方格', font=title_f, fill=(255, 255, 255))
    sub_f = _rank_font(18)

    # 白色卡片
    _rank_card(img, d, (card_x, card_y, card_x + card_w, card_y + card_h), scheme)

    # 头像
    avatar_size = 70
    av = None
    if appid:
        av = _download_avatar(user_id, appid, avatar_size)
        if av:
            av = _circle_avatar(av, avatar_size)

    avatar_x = card_x + 36
    avatar_y = card_y + 30
    if av:
        img.paste(av, (avatar_x, avatar_y), av)

    # 用户名
    name_x = avatar_x + avatar_size + 20
    name_y = avatar_y + 8
    name_f = _rank_font(20, bold=True)
    name = username or _rank_mask_id(user_id)
    d.text((name_x, name_y), name, font=name_f, fill=scheme['text'])

    # 本次用时
    dur_str = _rank_fmt_duration(duration_ms)
    dur_f = _rank_font(48, bold=True)
    dur_w = d.textlength(dur_str, dur_f)
    dur_x = card_x + (card_w - dur_w) / 2
    dur_y = avatar_y + avatar_size + 30
    d.text((dur_x, dur_y), dur_str, font=dur_f, fill=scheme['accent'])

    # “本次用时”标签
    label_f = _rank_font(22)
    label = "本   次   用   时"
    lw = d.textlength(label, label_f)
    d.text((card_x + (card_w - lw) / 2, dur_y - 30), label, font=label_f, fill=scheme['sub'])

    # 最佳成绩
    best_y = dur_y + 60
    if my_best is not None:
        best_str = f"> 个人最佳：{_rank_fmt_duration(my_best)} <"
        best_f = _rank_font(20, bold=True)
        bw = d.textlength(best_str, best_f)
        d.text((card_x + (card_w - bw) / 2, best_y), best_str, font=best_f, fill=scheme['accent'])
    else:
        new_str = "新纪录！已保存"
        new_f = _rank_font(24, bold=True)
        nw = d.textlength(new_str, new_f)
        d.text((card_x + (card_w - nw) / 2, best_y), new_str, font=new_f, fill=scheme['accent'])

    # 底部水印
    footer_f = _rank_font(18)
    sign = F_sign if F_sign_enabled else ''
    if sign:
        footer = f"{sign} {F_text} · 舒尔特方格 {sign}"
    else:
        footer = f"{F_text} · 舒尔特方格"
    fw = d.textlength(footer, footer_f)
    d.text(((W - fw) / 2, H - 30), footer, font=footer_f, fill=scheme['sub'])

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()

async def _upload_rank_image(bot, image_bytes):
    hosting = _get_hosting()
    if not hosting:
        return None
    try:
        return await hosting.upload_any(image_bytes, 'shuerte_rank.png', token_manager=bot.token_manager)
    except Exception as e:
        log.error('图片上传失败: %s', e)
        return None

# ==================== 对局 ====================

def _fmt_duration(ms: int) -> str:
    return f'{ms / 1000:.2f} 秒'

def _new_session(user_id: str, username: str) -> dict:
    nums = list(range(1, TOTAL + 1))
    random.shuffle(nums)
    sid = secrets.token_hex(4)
    return {
        'sid': sid,
        'user_id': user_id,
        'username': username or '',
        'grid': nums,
        'next': 1,
        'start': time.time(),
    }

def _get_session(user_id: str) -> dict | None:
    with _session_lock:
        return _sessions.get(user_id)

def _set_session(user_id: str, session: dict | None) -> None:
    with _session_lock:
        if session is None:
            _sessions.pop(user_id, None)
        else:
            _sessions[user_id] = session

def _find_session_by_sid(sid: str) -> dict | None:
    with _session_lock:
        for s in _sessions.values():
            if s.get('sid') == sid:
                return s
    return None

def _build_start_message(user_id: str) -> str:
    return '\n'.join([
        '**舒尔特方格训练**',
        f'测试者：<@{user_id}>',
        '>以最快速度按顺序点击数字按钮',
    ])

def _grid_buttons(session: dict) -> list:
    sid = session['sid']
    rows = []
    for r in range(GRID_SIZE):
        row = []
        for c in range(GRID_SIZE):
            num = session['grid'][r * GRID_SIZE + c]
            row.append({
                'text': str(num),
                'data': f'st|{sid}|{num}',
                'type': 1,
            })
        rows.append(row)
    return rows

# ==================== 排行榜消息 ====================

async def _build_rank_message(event, rows, my_best):
    bot = _get_bot(event)
    appid = getattr(event, 'appid', None)

    if bot and rows:
        try:
            image = await asyncio.to_thread(
                render_rank_image, rows, my_best, appid
            )
            if image:
                url = await _upload_rank_image(bot, image)
                if url:
                    w, h = struct.unpack('>II', image[16:24])
                    return f'<@{event.user_id}>![舒尔特TOP20 #{w}px #{h}px]({url})'
        except Exception as e:
            log.error('舒尔特排行榜图片渲染失败: %s', e, exc_info=True)

    lines = [f'<@{event.user_id}>', '📊 **舒尔特排行**']
    if not rows:
        lines.append('>暂无记录，发送「开始训练」挑战吧！')
    else:
        for i, r in enumerate(rows[:20], 1):
            name = r.get('username') or _rank_mask_id(r['user_id'])
            dur = _rank_fmt_duration(r['duration_ms'])
            lines.append(f'>**{i}.** {name} — `{dur}`')

    if my_best:
        lines.append(f'>🏅 你的最佳：**{_fmt_duration(my_best)}**')

    return '\n'.join(lines)

# ==================== 指令 ====================

@handler(r'^/?开始训练$', name='开始训练', desc='开始 5×5 舒尔特方格', ignore_at_check=True)
async def cmd_start(event, match):
    uid = event.user_id or ''
    if not uid:
        return await event.reply('❌ 无法识别用户', buttons=get_menu_btns1())

    if _get_session(uid):
        _set_session(uid, None)

    session = _new_session(uid, getattr(event, 'username', '') or '')
    _set_session(uid, session)

    try:
        await event.reply(
            _build_start_message(uid),
            buttons=_grid_buttons(session),
            skip_suffix=True,
        )
    except Exception as e:
        _set_session(uid, None)
        log.error('开始训练失败: %s', e)
        await event.reply(f'❌ 开始失败：{e}', buttons=get_menu_btns1())

@handler(r'^/?结束训练$', name='结束训练', desc='放弃当前训练', ignore_at_check=True)
async def cmd_stop(event, match):
    uid = event.user_id or ''
    if _get_session(uid):
        _set_session(uid, None)
        await event.reply('🛑 已结束当前训练', buttons=get_menu_btns2())
    else:
        await event.reply('ℹ️ 你当前没有进行中的训练', buttons=get_menu_btns1())

@handler(r'^/?舒尔特排行$', name='舒尔特排行', desc='全服最快完成排行 TOP20', ignore_at_check=True)
async def cmd_rank(event, match):
    rows = await asyncio.to_thread(_best_records, RANK_LIMIT)
    my_best = await asyncio.to_thread(_user_best, event.user_id or '')
    text = await _build_rank_message(event, rows, my_best)
    await event.reply(text, buttons=get_menu_btns1(), skip_suffix=True)

# ==================== 按钮交互 ====================

_CODE_OK = 0
_CODE_FAIL = 1
_CODE_NO_PERM = 4

async def _ack(event, code):
    try:
        event.set_callback_code(code)
    except Exception:
        pass
    try:
        await event.ack_interaction(code)
    except Exception:
        pass

async def _reply_later(event, text, *, buttons=None):
    try:
        await event.reply(text, buttons=buttons, skip_suffix=True)
    except Exception as e:
        log.warning('交互后续消息失败: %s', e)

@handler(
    r'^st\|([0-9a-f]+)\|(\d+)$',
    name='舒尔特点击',
    desc='处理方格数字点击',
    event_types=['INTERACTION_CREATE'],
    priority=10,
)
async def on_grid_click(event, match):
    sid = match.group(1)
    num = int(match.group(2))
    uid = event.user_id or ''

    session = _find_session_by_sid(sid)
    if not session:
        await _ack(event, _CODE_FAIL)
        return

    if session['user_id'] != uid:
        await _ack(event, _CODE_NO_PERM)
        await event.reply(
            f'**⚠️ 无法操作**\n<@{uid}>\n>这是 <@{session["user_id"]}> 的训练方格',
            buttons=get_menu_btns1(),
            skip_suffix=True,
        )
        return

    if num != session['next']:
        _set_session(uid, None)
        await _ack(event, _CODE_FAIL)
        await event.reply(
            f'**测试结束**\n>应点击：**{session["next"]}**，你点了：**{num}**',
            buttons=get_menu_btns2(),
            skip_suffix=True,
        )
        return

    await _ack(event, _CODE_OK)

    if num >= TOTAL:
        duration_ms = int((time.time() - session['start']) * 1000)
        _set_session(uid, None)
        await asyncio.to_thread(
            _save_record,
            uid,
            session.get('username') or getattr(event, 'username', '') or '',
            duration_ms,
        )
        my_best = await asyncio.to_thread(_user_best, uid)

        bot = _get_bot(event)
        appid = getattr(event, 'appid', None)
        image_sent = False

        if bot:
            try:
                image = await asyncio.to_thread(
                    render_personal_result_image,
                    uid,
                    session.get('username') or getattr(event, 'username', ''),
                    duration_ms,
                    my_best,
                    appid,
                )
                if image:
                    url = await _upload_rank_image(bot, image)
                    if url:
                        w, h = struct.unpack('>II', image[16:24])
                        msg = f'<@{uid}>![舒尔特成绩 #{w}px #{h}px]({url})'
                        await _reply_later(event, msg, buttons=get_menu_btns2())
                        image_sent = True
            except Exception as e:
                log.error('个人成绩图片渲染/发送失败: %s', e, exc_info=True)

        if not image_sent:
            # 兜底文本
            lines = [
                f'<@{uid}>',
                '🎉 **恭喜完成！**',
                f'>本次用时：**{_fmt_duration(duration_ms)}**',
            ]
            if my_best:
                lines.append(f'>🏅 你的最佳：**{_fmt_duration(my_best)}**')
            lines.append('>已写入排行榜，发送「舒尔特排行」查看')
            await _reply_later(event, '\n'.join(lines), buttons=get_menu_btns2())
        return

    session['next'] = num + 1
    _set_session(uid, session)

# ==================== Web 面板 ====================

if HAS_WEB_PAGES:
    _PAGE_KEY = 'shuerte-dashboard'
    _ROUTE_STATS = '/api/ext/shuerte/stats'
    _ROUTE_TOP = '/api/ext/shuerte/top'
    _ROUTE_RECENT = '/api/ext/shuerte/recent'
    _ROUTE_CONFIG = '/api/ext/shuerte/config'

    def _generate_dashboard_html():
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>舒尔特方格</title>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
            <style>
                * { box-sizing: border-box; }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                    background: #fef6f9;
                    margin: 0;
                    padding: 20px;
                    color: #2d1e28;
                }
                .container {
                    max-width: 1400px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 24px;
                    box-shadow: 0 8px 30px rgba(199,21,133,0.08);
                    padding: 30px 35px 40px;
                }
                .header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    border-bottom: 3px solid #ffb6c1;
                    padding-bottom: 12px;
                    margin-bottom: 20px;
                }
                .header h1 {
                    color: #c71585;
                    font-weight: 600;
                    font-size: 32px;
                    margin: 0;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }
                .header h1 i { color: #c71585; }
                .header .refresh-all {
                    background: #fff0f5;
                    border: none;
                    border-radius: 30px;
                    padding: 8px 18px;
                    font-size: 15px;
                    color: #c71585;
                    cursor: pointer;
                    transition: 0.2s;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .header .refresh-all:hover {
                    background: #ffd9e5;
                }
                .header .refresh-all i { font-size: 16px; }

                /* 统计卡片 */
                .stats {
                    display: flex;
                    gap: 30px;
                    flex-wrap: wrap;
                    background: #fff0f5;
                    border-radius: 16px;
                    padding: 18px 25px;
                    margin-bottom: 20px;
                    position: relative;
                    align-items: center;
                }
                .stats .stat-item {
                    display: flex;
                    flex-direction: column;
                    flex: 1 1 120px;
                }
                .stats .stat-label {
                    font-size: 14px;
                    color: #b17f98;
                    letter-spacing: 0.5px;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                }
                .stats .stat-label i { width: 18px; color: #c71585; }
                .stats .stat-value {
                    font-size: 28px;
                    font-weight: 600;
                    color: #c71585;
                }
                .stats .refresh-stats {
                    position: absolute;
                    right: 20px;
                    top: 50%;
                    transform: translateY(-50%);
                    background: transparent;
                    border: none;
                    color: #b17f98;
                    font-size: 20px;
                    cursor: pointer;
                    transition: 0.2s;
                    padding: 8px;
                }
                .stats .refresh-stats:hover {
                    color: #c71585;
                    transform: translateY(-50%) rotate(60deg);
                }

                /* 设置卡片 */
                .settings-card {
                    background: #fff9fb;
                    border-radius: 16px;
                    border: 1px solid #f5e6ed;
                    padding: 16px 22px;
                    margin-bottom: 20px;
                    display: flex;
                    flex-wrap: wrap;
                    align-items: flex-end;
                    gap: 20px;
                }
                .settings-card .setting-item {
                    display: flex;
                    flex-direction: column;
                    flex: 1 1 120px;
                }
                .settings-card .setting-item label {
                    font-size: 14px;
                    color: #b17f98;
                    margin-bottom: 4px;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                }
                .settings-card .setting-item input[type="text"],
                .settings-card .setting-item select {
                    padding: 6px 12px;
                    border: 1px solid #f5e6ed;
                    border-radius: 30px;
                    font-size: 15px;
                    background: white;
                    color: #2d1e28;
                    transition: 0.2s;
                }
                .settings-card .setting-item input[type="text"]:focus,
                .settings-card .setting-item select:focus {
                    border-color: #c71585;
                    outline: none;
                    box-shadow: 0 0 0 2px rgba(199,21,133,0.1);
                }
                .settings-card .setting-item select {
                    appearance: none;
                    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%23b17f98' stroke-width='1.5' fill='none'/%3E%3C/svg%3E");
                    background-repeat: no-repeat;
                    background-position: right 12px center;
                    padding-right: 36px;
                }
                .settings-card .setting-item .toggle-wrap {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                .settings-card .setting-item .toggle-wrap input[type="checkbox"] {
                    width: 40px;
                    height: 22px;
                    appearance: none;
                    background: #e0d0d8;
                    border-radius: 30px;
                    position: relative;
                    cursor: pointer;
                    transition: 0.2s;
                    flex-shrink: 0;
                }
                .settings-card .setting-item .toggle-wrap input[type="checkbox"]:checked {
                    background: #c71585;
                }
                .settings-card .setting-item .toggle-wrap input[type="checkbox"]::after {
                    content: '';
                    position: absolute;
                    top: 2px;
                    left: 2px;
                    width: 18px;
                    height: 18px;
                    background: white;
                    border-radius: 50%;
                    transition: 0.2s;
                }
                .settings-card .setting-item .toggle-wrap input[type="checkbox"]:checked::after {
                    left: 20px;
                }
                .settings-card .save-btn {
                    background: #c71585;
                    border: none;
                    border-radius: 30px;
                    padding: 8px 24px;
                    color: white;
                    font-size: 15px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: 0.2s;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    margin-left: auto;
                }
                .settings-card .save-btn:hover {
                    background: #a0116a;
                }
                .settings-card .save-btn i { font-size: 16px; }
                .settings-card .save-msg {
                    font-size: 14px;
                    color: #c71585;
                    margin-left: 10px;
                    opacity: 0;
                    transition: 0.3s;
                }
                .settings-card .save-msg.show { opacity: 1; }

                /* 双栏主体 */
                .dashboard-main {
                    display: flex;
                    gap: 30px;
                    margin-top: 10px;
                }
                .col-left {
                    flex: 2;
                    min-width: 0;
                }
                .col-right {
                    flex: 1;
                    min-width: 0;
                }

                .card {
                    background: white;
                    border-radius: 18px;
                    box-shadow: 0 4px 16px rgba(199,21,133,0.06);
                    padding: 18px 20px 20px;
                    border: 1px solid #f5e6ed;
                    margin-bottom: 20px;
                }
                .card-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 14px;
                }
                .card-header .title {
                    font-size: 20px;
                    font-weight: 600;
                    color: #2d1e28;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                .card-header .title i {
                    color: #c71585;
                    width: 24px;
                }
                .card-header .title small {
                    font-weight: 400;
                    font-size: 14px;
                    color: #b17f98;
                }
                .card-header .refresh-btn {
                    background: #fef6f9;
                    border: none;
                    border-radius: 30px;
                    padding: 5px 14px;
                    font-size: 14px;
                    color: #b17f98;
                    cursor: pointer;
                    transition: 0.2s;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                }
                .card-header .refresh-btn:hover {
                    background: #ffd9e5;
                    color: #c71585;
                }
                .card-header .refresh-btn i { font-size: 14px; }

                /* 表格样式 */
                .table-wrap {
                    overflow-x: auto;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 15px;
                }
                th {
                    background: #ffd9e5;
                    color: #2d1e28;
                    font-weight: 600;
                    padding: 10px 14px;
                    text-align: left;
                }
                td {
                    padding: 10px 14px;
                    border-bottom: 1px solid #f5e6ed;
                }
                tr:last-child td { border-bottom: none; }
                .rank-badge {
                    display: inline-block;
                    width: 28px;
                    height: 28px;
                    line-height: 28px;
                    text-align: center;
                    border-radius: 50%;
                    background: #ffb6c1;
                    color: white;
                    font-weight: 600;
                    font-size: 14px;
                }
                .rank-gold { background: #f5a0b0; }
                .rank-silver { background: #e8a0b8; }
                .rank-bronze { background: #d8a0b8; }
                .duration {
                    font-weight: 500;
                    color: #c71585;
                }
                .time {
                    color: #8a7a82;
                    font-size: 13px;
                }
                .empty {
                    text-align: center;
                    color: #b17f98;
                    padding: 20px 0;
                }
                .loading-text {
                    text-align: center;
                    color: #b17f98;
                    padding: 20px 0;
                }
                .footer {
                    margin-top: 30px;
                    text-align: center;
                    color: #b17f98;
                    font-size: 14px;
                    border-top: 1px solid #f5e6ed;
                    padding-top: 20px;
                }
                .fa-spin { animation: fa-spin 1s infinite linear; }
                @keyframes fa-spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                /* 响应式 */
                @media (max-width: 900px) {
                    .dashboard-main { flex-direction: column; }
                    .stats .refresh-stats { position: static; transform: none; margin-left: auto; }
                    .stats { flex-wrap: wrap; }
                    .settings-card { flex-direction: column; align-items: stretch; }
                    .settings-card .save-btn { margin-left: 0; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <!-- 头部 -->
                <div class="header">
                    <h1><i class="fas fa-table"></i> 舒尔特方格</h1>
                    <button class="refresh-all" onclick="loadAll()">
                        <i class="fas fa-sync-alt"></i> 刷新全部
                    </button>
                </div>

                <!-- 统计卡片 -->
                <div class="stats" id="stats">
                    <div class="stat-item">
                        <span class="stat-label"><i class="fas fa-users"></i> 参与人数</span>
                        <span class="stat-value" id="stat-users">—</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label"><i class="fas fa-file-alt"></i> 总记录数</span>
                        <span class="stat-value" id="stat-total">—</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label"><i class="fas fa-bolt"></i> 全服最快</span>
                        <span class="stat-value" id="stat-fastest">—</span>
                    </div>
                    <button class="refresh-stats" onclick="loadStats()" title="刷新统计">
                        <i class="fas fa-sync-alt"></i>
                    </button>
                </div>

                <!-- 设置卡片 -->
                <div class="settings-card" id="settings-card">
                    <div class="setting-item">
                        <label><i class="fas fa-font"></i> 页脚文字</label>
                        <input type="text" id="f-text-input" placeholder="例：昔涟">
                    </div>
                    <div class="setting-item">
                        <label><i class="fas fa-icons"></i> 两端符号</label>
                        <input type="text" id="f-sign-input" placeholder="例：♡">
                    </div>
                    <div class="setting-item">
                        <label><i class="fas fa-toggle-on"></i> 显示符号</label>
                        <div class="toggle-wrap">
                            <input type="checkbox" id="f-sign-enabled">
                            <span id="sign-status-label" style="font-size:14px;color:#b17f98;">启用</span>
                        </div>
                    </div>
                    <div class="setting-item">
                        <label><i class="fas fa-palette"></i> 渲染图配色</label>
                        <select id="color-scheme-select">
                            <option value="粉红">粉红</option>
                            <option value="薄荷">薄荷</option>
                            <option value="蓝紫">蓝紫</option>
                            <option value="暖阳">暖阳</option>
                            <option value="森林">森林</option>
                            <option value="海洋">海洋</option>
                            <option value="暮光">暮光</option>
                            <option value="樱花">樱花</option>
                            <option value="柠檬">柠檬</option>
                            <option value="薰衣草">薰衣草</option>
                            <option value="珊瑚">珊瑚</option>
                            <option value="冰蓝">冰蓝</option>
                            <option value="蜜桃">蜜桃</option>
                            <option value="星空">星空</option>
                            <option value="抹茶">抹茶</option>
                            <option value="玫瑰">玫瑰</option>
                            <option value="天空">天空</option>
                            <option value="奶油">奶油</option>
                            <option value="浆果">浆果</option>
                            <option value="石墨">石墨</option>
                        </select>
                    </div>
                    <div class="setting-item">
                        <label><i class="fas fa-undo-alt"></i> 返回指令</label>
                        <input type="text" id="menu-t-input" placeholder="例：/返回">
                    </div>
                    <button class="save-btn" onclick="saveConfig()">
                        <i class="fas fa-save"></i> 保存设置
                    </button>
                    <span class="save-msg" id="save-msg">✅ 已保存</span>
                </div>

                <!-- 主体双栏 -->
                <div class="dashboard-main">
                    <!-- 左栏：最佳排行 -->
                    <div class="col-left">
                        <div class="card">
                            <div class="card-header">
                                <span class="title">
                                    <i class="fas fa-trophy"></i> 最佳排行 TOP20
                                    <small>（个人最快用时）</small>
                                </span>
                                <button class="refresh-btn" onclick="loadTop()">
                                    <i class="fas fa-sync-alt"></i> 刷新
                                </button>
                            </div>
                            <div class="table-wrap" id="top-container">
                                <div class="loading-text"><i class="fas fa-spinner fa-spin"></i> 加载中...</div>
                            </div>
                        </div>
                    </div>

                    <!-- 右栏：最近记录 -->
                    <div class="col-right">
                        <div class="card">
                            <div class="card-header">
                                <span class="title">
                                    <i class="fas fa-clock"></i> 最近完成
                                    <small>（最新20条）</small>
                                </span>
                                <button class="refresh-btn" onclick="loadRecent()">
                                    <i class="fas fa-sync-alt"></i> 刷新
                                </button>
                            </div>
                            <div class="table-wrap" id="recent-container">
                                <div class="loading-text"><i class="fas fa-spinner fa-spin"></i> 加载中...</div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="footer">舒尔特方格</div>
            </div>

            <script>
                // ===== 配置管理 =====
                async function loadConfig() {
                    try {
                        const res = await fetch('/api/ext/shuerte/config');
                        if (!res.ok) throw new Error('加载配置失败');
                        const config = await res.json();
                        document.getElementById('f-text-input').value = config.f_text || '';
                        document.getElementById('f-sign-input').value = config.f_sign || '';
                        const enabled = config.f_sign_enabled === 'true';
                        document.getElementById('f-sign-enabled').checked = enabled;
                        document.getElementById('sign-status-label').textContent = enabled ? '启用' : '禁用';
                        // 配色
                        const scheme = config.color_scheme || '粉红';
                        const select = document.getElementById('color-scheme-select');
                        for (let opt of select.options) {
                            if (opt.value === scheme) {
                                opt.selected = true;
                                break;
                            }
                        }
                        document.getElementById('menu-t-input').value = config.menu_t || '/返回';
                    } catch(e) {
                        console.error('加载配置失败:', e);
                    }
                }

                document.getElementById('f-sign-enabled').addEventListener('change', function() {
                    document.getElementById('sign-status-label').textContent = this.checked ? '启用' : '禁用';
                });

                async function saveConfig() {
                    const f_text = document.getElementById('f-text-input').value.trim();
                    const f_sign = document.getElementById('f-sign-input').value.trim();
                    const f_sign_enabled = document.getElementById('f-sign-enabled').checked ? 'true' : 'false';
                    const color_scheme = document.getElementById('color-scheme-select').value;
                    const menu_t = document.getElementById('menu-t-input').value.trim() || '/返回';
                    try {
                        const res = await fetch('/api/ext/shuerte/config', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ f_text, f_sign, f_sign_enabled, color_scheme, menu_t })
                        });
                        if (!res.ok) throw new Error('保存失败');
                        const msg = document.getElementById('save-msg');
                        msg.textContent = '✅ 保存成功';
                        msg.classList.add('show');
                        setTimeout(() => msg.classList.remove('show'), 3000);
                    } catch(e) {
                        alert('保存配置失败: ' + e.message);
                    }
                }

                // ===== 统计、排行、最近记录 =====
                async function fetchData(url) {
                    const res = await fetch(url);
                    if (!res.ok) throw new Error('网络错误');
                    return res.json();
                }

                function formatDuration(ms) {
                    return (ms/1000).toFixed(2) + 's';
                }

                async function loadStats() {
                    try {
                        const stats = await fetchData('/api/ext/shuerte/stats');
                        document.getElementById('stat-users').textContent = stats.users || 0;
                        document.getElementById('stat-total').textContent = stats.total || 0;
                        document.getElementById('stat-fastest').textContent = stats.fastest ? formatDuration(stats.fastest) : '无';
                    } catch(e) {
                        document.getElementById('stat-users').textContent = '❌';
                        document.getElementById('stat-total').textContent = '❌';
                        document.getElementById('stat-fastest').textContent = '❌';
                    }
                }

                async function loadTop() {
                    const container = document.getElementById('top-container');
                    container.innerHTML = '<div class="loading-text"><i class="fas fa-spinner fa-spin"></i> 加载中...</div>';
                    try {
                        const rows = await fetchData('/api/ext/shuerte/top');
                        if (!rows || rows.length === 0) {
                            container.innerHTML = '<div class="empty">暂无记录</div>';
                            return;
                        }
                        let html = '<table><thead><tr><th style="width:60px;">#</th><th>玩家</th><th style="width:140px;">用时</th><th style="width:160px;">达成时间</th></tr></thead><tbody>';
                        rows.forEach((r, i) => {
                            const cls = i === 0 ? 'rank-gold' : (i === 1 ? 'rank-silver' : (i === 2 ? 'rank-bronze' : ''));
                            const name = r.username || (r.user_id ? r.user_id.slice(0,3)+'****' : '未知');
                            html += `<tr><td><span class="rank-badge ${cls}">${i+1}</span></td><td><strong>${name}</strong></td><td class="duration">${formatDuration(r.duration_ms)}</td><td class="time">${r.created_at}</td></tr>`;
                        });
                        html += '</tbody></table>';
                        container.innerHTML = html;
                    } catch(e) {
                        container.innerHTML = '<div class="empty"><i class="fas fa-exclamation-triangle"></i> 加载失败，请重试</div>';
                    }
                }

                async function loadRecent() {
                    const container = document.getElementById('recent-container');
                    container.innerHTML = '<div class="loading-text"><i class="fas fa-spinner fa-spin"></i> 加载中...</div>';
                    try {
                        const rows = await fetchData('/api/ext/shuerte/recent');
                        if (!rows || rows.length === 0) {
                            container.innerHTML = '<div class="empty">暂无记录</div>';
                            return;
                        }
                        let html = '<table><thead><tr><th>玩家</th><th style="width:140px;">用时</th><th style="width:160px;">完成时间</th></tr></thead><tbody>';
                        rows.forEach(r => {
                            const name = r.username || (r.user_id ? r.user_id.slice(0,3)+'****' : '未知');
                            html += `<tr><td><strong>${name}</strong></td><td class="duration">${formatDuration(r.duration_ms)}</td><td class="time">${r.created_at}</td></tr>`;
                        });
                        html += '</tbody></table>';
                        container.innerHTML = html;
                    } catch(e) {
                        container.innerHTML = '<div class="empty"><i class="fas fa-exclamation-triangle"></i> 加载失败，请重试</div>';
                    }
                }

                async function loadAll() {
                    await Promise.all([loadStats(), loadTop(), loadRecent()]);
                }

                // 页面加载
                window.onload = function() {
                    loadConfig();
                    loadAll();
                };
            </script>
        </body>
        </html>
        """

    # 注册侧边栏页面
    register_page(
        key=_PAGE_KEY,
        label='舒尔特数据',
        source='plugin',
        source_name='shuerte',
        html=_generate_dashboard_html(),
    )

    # ===== API 路由 =====
    @register_route('GET', _ROUTE_STATS, auth=False)
    async def api_stats(request):
        stats = await asyncio.to_thread(_stats)
        return aiohttp.web.json_response(stats)

    @register_route('GET', _ROUTE_TOP, auth=False)
    async def api_top(request):
        rows = await asyncio.to_thread(_best_records, 20)
        return aiohttp.web.json_response(rows)

    @register_route('GET', _ROUTE_RECENT, auth=False)
    async def api_recent(request):
        rows = await asyncio.to_thread(_all_records, 20)
        return aiohttp.web.json_response(rows)

    @register_route('GET', _ROUTE_CONFIG, auth=False)
    async def api_get_config(request):
        """获取当前配置"""
        with _conn_lock:
            cur = _db().execute('SELECT key, value FROM config')
            config = {row['key']: row['value'] for row in cur.fetchall()}
        return aiohttp.web.json_response(config)

    @register_route('POST', _ROUTE_CONFIG, auth=False)
    async def api_set_config(request):
        """更新配置"""
        data = await request.json()
        f_text = data.get('f_text', '').strip()
        f_sign = data.get('f_sign', '').strip()
        f_sign_enabled = data.get('f_sign_enabled', 'true')
        color_scheme = data.get('color_scheme', '粉红')
        menu_t = data.get('menu_t', '/返回').strip()
        # 校验
        if not f_text:
            f_text = '昔涟'
        if not f_sign:
            f_sign = '♡'
        if f_sign_enabled not in ('true', 'false'):
            f_sign_enabled = 'true'
        if color_scheme not in PRESET_COLORS:
            color_scheme = '粉红'
        if not menu_t:
            menu_t = '/返回'
        # 保存
        await asyncio.to_thread(_set_config, 'f_text', f_text)
        await asyncio.to_thread(_set_config, 'f_sign', f_sign)
        await asyncio.to_thread(_set_config, 'f_sign_enabled', f_sign_enabled)
        await asyncio.to_thread(_set_config, 'color_scheme', color_scheme)
        await asyncio.to_thread(_set_config, 'menu_t', menu_t)
        return aiohttp.web.json_response({'ok': True})

    def _unregister_web():
        try:
            unregister_page(_PAGE_KEY)
        except Exception:
            pass
        try:
            unregister_route(_ROUTE_STATS)
        except Exception:
            pass
        try:
            unregister_route(_ROUTE_TOP)
        except Exception:
            pass
        try:
            unregister_route(_ROUTE_RECENT)
        except Exception:
            pass
        try:
            unregister_route(_ROUTE_CONFIG)
        except Exception:
            pass

# ==================== 生命周期 ====================

@on_load
async def _init():
    await asyncio.to_thread(_db)
    await asyncio.to_thread(_init_config)
    _rank_find_font()
    log.info('舒尔特方格插件已加载')

@on_unload
def _cleanup():
    global _conn
    with _session_lock:
        _sessions.clear()
    with _conn_lock:
        if _conn:
            _conn.close()
            _conn = None
    if HAS_WEB_PAGES:
        _unregister_web()
    log.info('舒尔特方格插件已卸载')