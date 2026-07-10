"""
World Archives.

国・地域・歴史国家を検索、比較、クイズ化するNiceGUI製のWebアプリです。
国データはdata.json、ログイン後のユーザーデータはuser_data.jsonまたは
Render Disk上のUSER_DATA_FILEに保存します。
"""
from nicegui import ui, app
import base64
import hashlib
import inspect
import json
import math
import os
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from html import escape as html_escape
from urllib.parse import quote_plus

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(BASE_DIR, 'data.json')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
DATA_CACHE = None
DATA_CACHE_MTIME = None
DERIVED_DATA_CACHE = {'mtime': None, 'data_id': None, 'value': None}
SEARCH_TEXT_CACHE = {'mtime': None, 'data_id': None, 'lang': None, 'value': None}
COUNTRY_OPTION_MAP_CACHE = {'mtime': None, 'data_id': None, 'lang': None, 'value': None}
FLAG_AVATAR_OPTION_MAP_CACHE = {'mtime': None, 'data_id': None, 'lang': None, 'value': None}
USER_DATA_CACHE = None
USER_DATA_CACHE_MTIME = None
BATTLE_STATE_CACHE = None
BATTLE_STATE_CACHE_MTIME = None
QUIZ_POOL_CACHE = {'key': None, 'value': None}
BATTLE_POWER_BOUNDS_CACHE = {'mtime': None, 'value': None}
BATTLE_DRAW_POOL_CACHE = {'mtime': None, 'value': None}
RAW_PUBLIC_COUNTRY_KEYS_CACHE = {'mtime': None, 'value': None}
QUIZ_HISTORY_LIMIT = 80
QUIZ_EXTREME_TIME_LIMIT_SECONDS = 30
QUIZ_TIME_LIMIT_SECONDS = {
    'easy': 300,
    'medium': 180,
    'hard': 60,
    'extreme': QUIZ_EXTREME_TIME_LIMIT_SECONDS,
}

def file_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None

def clear_data_derived_caches():
    global DERIVED_DATA_CACHE, SEARCH_TEXT_CACHE, COUNTRY_OPTION_MAP_CACHE, FLAG_AVATAR_OPTION_MAP_CACHE, QUIZ_POOL_CACHE, RAW_PUBLIC_COUNTRY_KEYS_CACHE
    DERIVED_DATA_CACHE = {'mtime': None, 'data_id': None, 'value': None}
    SEARCH_TEXT_CACHE = {'mtime': None, 'data_id': None, 'lang': None, 'value': None}
    COUNTRY_OPTION_MAP_CACHE = {'mtime': None, 'data_id': None, 'lang': None, 'value': None}
    FLAG_AVATAR_OPTION_MAP_CACHE = {'mtime': None, 'data_id': None, 'lang': None, 'value': None}
    QUIZ_POOL_CACHE = {'key': None, 'value': None}
    RAW_PUBLIC_COUNTRY_KEYS_CACHE = {'mtime': None, 'value': None}

# 生成した国旗など、リポジトリ内に置いた画像を /assets/... で配信します。
if os.path.isdir(ASSETS_DIR):
    app.add_static_files('/assets', ASSETS_DIR)

def resolve_user_data_file():
    configured_path = os.environ.get('USER_DATA_FILE')
    if configured_path:
        return configured_path
    render_disk_path = '/var/data'
    if os.environ.get('RENDER') and os.path.isdir(render_disk_path):
        return os.path.join(render_disk_path, 'user_data.json')
    return os.path.join(BASE_DIR, 'user_data.json')

USER_DATA_FILE = resolve_user_data_file()
GUEST_USERNAME = '__guest__'
GUEST_BROWSER_KEY = 'world_archives_guest_id'
KAKASI_CONVERTER = None
PINYIN_CONVERTER = None
APP_TIMEZONE = timezone(timedelta(hours=9), 'JST')
USER_ASSETS_DIR = os.path.join(os.path.dirname(USER_DATA_FILE) or BASE_DIR, 'user_assets')
BATTLE_STATE_FILE = os.path.join(os.path.dirname(USER_DATA_FILE) or BASE_DIR, 'battle_state.json')
os.makedirs(USER_ASSETS_DIR, exist_ok=True)
app.add_static_files('/user-assets', USER_ASSETS_DIR)
ui.add_head_html("""
<style>
.wa-flag-frame .q-img,
.wa-flag-frame .q-img__container {
  height: 100%;
  width: 100%;
}
.wa-flag-frame img,
.wa-flag-frame .q-img__image {
  height: 100%;
  width: 100%;
  object-fit: cover;
  object-position: left center;
}
.wa-tag-chip {
  font-weight: 700;
  letter-spacing: 0;
}
.wa-avatar-editor {
  width: 12rem;
  height: 12rem;
  border-radius: 9999px;
  overflow: hidden;
  position: relative;
  cursor: grab;
  touch-action: none;
  background: #ffffff;
}
.wa-avatar-editor:active {
  cursor: grabbing;
}
.wa-avatar-editor img {
  position: absolute;
  left: 50%;
  top: 50%;
  object-fit: cover;
  display: block;
}
.wa-avatar-target {
  width: 1rem;
  height: 1rem;
  border: 2px solid #ffffff;
  border-radius: 9999px;
  box-shadow: 0 0 0 1px rgba(26, 35, 50, 0.75);
  position: absolute;
  pointer-events: none;
  transform: translate(-50%, -50%);
}
.wa-staff-roll-window {
  background: radial-gradient(circle at top, #283750 0%, #0b1020 58%, #050814 100%);
  color: #f8fafc;
  min-height: 70vh;
  overflow: hidden;
  position: relative;
}
.wa-staff-roll-scroll {
  animation: wa-staff-roll 44s linear forwards;
  transform: translateY(52vh);
  text-align: center;
}
.wa-staff-roll-scroll h2 {
  font-size: 2.4rem;
  font-weight: 900;
  letter-spacing: 0;
  margin-bottom: 2rem;
}
.wa-staff-roll-scroll p {
  font-size: 1.15rem;
  font-weight: 700;
  margin: 0.9rem 0;
}
html.wa-dark .wa-staff-roll-window {
  background: radial-gradient(circle at top, #283750 0%, #0b1020 58%, #050814 100%) !important;
  color: #f8fafc !important;
}
@keyframes wa-staff-roll {
  from { transform: translateY(52vh); }
  to { transform: translateY(-100%); }
}
html.wa-dark body,
html.wa-dark .nicegui-content,
html.wa-dark .q-page,
html.wa-dark .q-layout,
html.wa-dark .bg-gray-50,
html.wa-dark .bg-blue-50,
html.wa-dark .bg-gray-100,
html.wa-dark .bg-blue-100,
html.wa-dark .bg-orange-50,
html.wa-dark .bg-red-50,
html.wa-dark .bg-gray-200 {
  background: #090f1f !important;
  color: #f8fafc !important;
}
html.wa-dark .bg-white,
html.wa-dark .q-card,
html.wa-dark .q-menu,
html.wa-dark .q-drawer,
html.wa-dark .q-list,
html.wa-dark .q-expansion-item,
html.wa-dark .q-tab-panels,
html.wa-dark .q-tab-panel,
html.wa-dark .q-panel,
html.wa-dark .q-table,
html.wa-dark .q-table__container {
  background: #172033 !important;
  background-color: #172033 !important;
  color: #f8fafc !important;
}
html.wa-dark div.bg-white,
html.wa-dark .q-card.bg-white,
html.wa-dark .q-field.bg-white,
html.wa-dark .q-expansion-item.bg-white,
html.wa-dark .q-expansion-item__container,
html.wa-dark .q-expansion-item__content,
html.wa-dark .q-tab-panels.bg-white,
html.wa-dark .q-tab-panel.bg-white {
  background: #172033 !important;
  background-color: #172033 !important;
  color: #f8fafc !important;
}
html.wa-dark .text-\\[\\#1a2332\\],
html.wa-dark .text-gray-800,
html.wa-dark .text-gray-700,
html.wa-dark .text-gray-600,
html.wa-dark .text-gray-500,
html.wa-dark .text-gray-400,
html.wa-dark .text-blue-800,
html.wa-dark .text-blue-700,
html.wa-dark .text-green-700,
html.wa-dark .text-red-700,
html.wa-dark .text-orange-700,
html.wa-dark .q-item,
html.wa-dark .q-item__label,
html.wa-dark .q-tab,
html.wa-dark .q-field__label,
html.wa-dark .q-field__native,
html.wa-dark .q-field__prefix,
html.wa-dark .q-field__suffix {
  color: #f8fafc !important;
}
html.wa-dark .bg-white .text-\\[\\#1a2332\\],
html.wa-dark .bg-white .text-gray-800,
html.wa-dark .bg-white .text-gray-700,
html.wa-dark .bg-white .text-gray-600,
html.wa-dark .bg-white .text-gray-500,
html.wa-dark .bg-white .text-gray-400,
html.wa-dark .q-card .text-\\[\\#1a2332\\],
html.wa-dark .q-card .text-gray-800,
html.wa-dark .q-card .text-gray-700,
html.wa-dark .q-card .text-gray-600,
html.wa-dark .q-card .text-gray-500,
html.wa-dark .q-card .text-gray-400 {
  color: #f8fafc !important;
}
html.wa-dark .border,
html.wa-dark .border-gray-200,
html.wa-dark .border-gray-300,
html.wa-dark .border-blue-100,
html.wa-dark .q-separator {
  border-color: #475569 !important;
  background: #475569 !important;
}
html.wa-dark input,
html.wa-dark textarea,
html.wa-dark .q-field__control,
html.wa-dark .q-field__marginal {
  background: #0f172a !important;
  color: #f8fafc !important;
}
html.wa-dark .q-btn--outline:before {
  border-color: #60a5fa !important;
}
html.wa-dark .q-btn--outline {
  color: #93c5fd !important;
}
html.wa-dark .q-btn.q-btn--standard:not(.bg-primary):not(.bg-secondary):not(.bg-positive):not(.bg-negative):not(.bg-warning):not(.bg-info):not(.bg-yellow):not(.bg-blue):not(.bg-green):not(.bg-red):not(.bg-orange):not(.bg-purple) {
  background: #1f2937 !important;
  background-color: #1f2937 !important;
  color: #f8fafc !important;
}
html.wa-dark .q-btn.q-btn--standard:not(.bg-primary):not(.bg-secondary):not(.bg-positive):not(.bg-negative):not(.bg-warning):not(.bg-info):not(.bg-yellow):not(.bg-blue):not(.bg-green):not(.bg-red):not(.bg-orange):not(.bg-purple) .q-icon,
html.wa-dark .q-btn.q-btn--standard:not(.bg-primary):not(.bg-secondary):not(.bg-positive):not(.bg-negative):not(.bg-warning):not(.bg-info):not(.bg-yellow):not(.bg-blue):not(.bg-green):not(.bg-red):not(.bg-orange):not(.bg-purple) .q-btn__content {
  color: #f8fafc !important;
}
html.wa-dark .q-menu {
  background: #111827 !important;
  background-color: #111827 !important;
  color: #f8fafc !important;
  box-shadow: 0 18px 45px rgba(0, 0, 0, 0.55) !important;
}
html.wa-dark .q-menu .q-list,
html.wa-dark .q-menu .q-item {
  background: #111827 !important;
  background-color: #111827 !important;
  color: #f8fafc !important;
}
html.wa-dark .q-menu .q-item--disabled,
html.wa-dark .q-menu .disabled {
  color: #94a3b8 !important;
  opacity: 0.78 !important;
}
html.wa-dark .q-item:hover,
html.wa-dark .hover\\:bg-blue-50:hover {
  background: #22304a !important;
}
html.wa-dark .shadow,
html.wa-dark .shadow-md,
html.wa-dark .shadow-lg {
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.45) !important;
}
html.wa-dark .wa-user-pill,
html.wa-dark .rounded-full.bg-white,
html.wa-dark .q-btn.bg-white {
  background: #1e293b !important;
  background-color: #1e293b !important;
  border-color: #475569 !important;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35) !important;
}
html.wa-dark .q-field--outlined .q-field__control:before,
html.wa-dark .q-field--outlined .q-field__control:after {
  border-color: #64748b !important;
}
html.wa-dark .q-card .q-card {
  background: #111827 !important;
  background-color: #111827 !important;
}
html.wa-dark .q-chip {
  border-color: #64748b !important;
}
html.wa-dark .q-notification,
html.wa-dark .q-dialog__inner .q-card:not(.wa-staff-roll-window) {
  background: #111827 !important;
  background-color: #111827 !important;
  color: #f8fafc !important;
}
html.wa-dark .q-checkbox__bg {
  border-color: #93c5fd !important;
}
html.wa-dark .wa-battle-surface,
html.wa-dark .wa-battle-surface .bg-gray-50 {
  background: #07111f !important;
}
html.wa-dark .wa-battle-surface .q-card {
  background: #111827 !important;
  color: #e5e7eb !important;
  border: 1px solid #334155 !important;
}
html.wa-dark .wa-battle-surface .bg-white {
  background: #172033 !important;
}
html.wa-dark .wa-battle-surface .bg-blue-50,
html.wa-dark .wa-battle-surface .bg-indigo-50,
html.wa-dark .wa-battle-surface .bg-amber-50,
html.wa-dark .wa-battle-surface .bg-orange-50,
html.wa-dark .wa-battle-surface .bg-red-50 {
  background: #1f2937 !important;
}
html.wa-dark .wa-battle-surface .text-\\[\\#1a2332\\],
html.wa-dark .wa-battle-surface .text-gray-800,
html.wa-dark .wa-battle-surface .text-gray-700,
html.wa-dark .wa-battle-surface .text-gray-600,
html.wa-dark .wa-battle-surface .text-gray-500,
html.wa-dark .wa-battle-surface .text-blue-800,
html.wa-dark .wa-battle-surface .text-blue-700,
html.wa-dark .wa-battle-surface .text-indigo-800,
html.wa-dark .wa-battle-surface .text-indigo-700,
html.wa-dark .wa-battle-surface .text-amber-800,
html.wa-dark .wa-battle-surface .text-amber-700,
html.wa-dark .wa-battle-surface .text-red-800,
html.wa-dark .wa-battle-surface .text-red-700,
html.wa-dark .wa-battle-surface .text-orange-700,
html.wa-dark .wa-battle-surface .text-yellow-700 {
  color: #e5e7eb !important;
}
html.wa-dark .wa-battle-surface .q-field__control,
html.wa-dark .wa-battle-surface input,
html.wa-dark .wa-battle-surface textarea {
  background: #0f172a !important;
  color: #f8fafc !important;
}
html.wa-dark .wa-battle-surface .wa-boss-card {
  background: linear-gradient(135deg, #182235, #241936) !important;
  border-color: #7c3aed !important;
}
</style>
""")
ui.add_body_html("""
<script>
(() => {
  sessionStorage.removeItem('world_archives_route_hash_applied');
  sessionStorage.removeItem('world_archives_login_redirect');
  if (window.location.hash) {
    history.replaceState(null, '', window.location.pathname + window.location.search);
  }
})();
</script>
<style id="wa-dark-late-overrides">
html.wa-dark body .wa-dark-area,
html.wa-dark body .wa-dark-area.bg-gray-50,
html.wa-dark body .wa-dark-area.bg-gray-100,
html.wa-dark body .wa-dark-area .bg-gray-50,
html.wa-dark body .wa-dark-area .bg-gray-100 {
  background: #090f1f !important;
  background-color: #090f1f !important;
  color: #f8fafc !important;
}
html.wa-dark body .wa-dark-area .bg-white,
html.wa-dark body .wa-dark-area .q-card,
html.wa-dark body .wa-dark-area .q-tab-panels,
html.wa-dark body .wa-dark-area .q-tab-panel,
html.wa-dark body .wa-dark-area .q-expansion-item,
html.wa-dark body .wa-dark-area .q-expansion-item__container,
html.wa-dark body .wa-dark-area .q-expansion-item__content,
html.wa-dark body .q-drawer.wa-dark-area,
html.wa-dark body .q-drawer.wa-dark-area .bg-white,
html.wa-dark body .q-drawer.wa-dark-area .q-card {
  background: #172033 !important;
  background-color: #172033 !important;
  color: #f8fafc !important;
}
html.wa-dark body .wa-dark-area .text-\\[\\#1a2332\\],
html.wa-dark body .wa-dark-area .text-gray-800,
html.wa-dark body .wa-dark-area .text-gray-700,
html.wa-dark body .wa-dark-area .text-gray-600,
html.wa-dark body .wa-dark-area .text-gray-500,
html.wa-dark body .wa-dark-area .text-gray-400,
html.wa-dark body .q-drawer.wa-dark-area .text-gray-800,
html.wa-dark body .q-drawer.wa-dark-area .text-gray-700,
html.wa-dark body .q-drawer.wa-dark-area .text-gray-600,
html.wa-dark body .q-drawer.wa-dark-area .text-gray-500,
html.wa-dark body .q-drawer.wa-dark-area .text-gray-400 {
  color: #f8fafc !important;
}
html.wa-dark body .wa-dark-area .q-btn.bg-white,
html.wa-dark body .wa-dark-area .q-btn.text-grey-9,
html.wa-dark body .wa-dark-area .q-btn[style*="white"],
html.wa-dark body .wa-quiz-screen .q-btn.text-grey-9,
html.wa-dark body .wa-quiz-screen .q-btn.bg-white {
  background: #1f2937 !important;
  background-color: #1f2937 !important;
  color: #f8fafc !important;
}
html.wa-dark body .wa-dark-area .q-btn.bg-white .q-btn__content,
html.wa-dark body .wa-dark-area .q-btn.text-grey-9 .q-btn__content,
html.wa-dark body .wa-quiz-screen .q-btn.text-grey-9 .q-btn__content {
  color: #f8fafc !important;
}
html.wa-dark body .wa-dark-area .q-field,
html.wa-dark body .wa-dark-area .q-field__control,
html.wa-dark body .wa-dark-area input,
html.wa-dark body .wa-dark-area textarea {
  background: #0f172a !important;
  background-color: #0f172a !important;
  color: #f8fafc !important;
}
html.wa-dark body .wa-dark-area .border,
html.wa-dark body .wa-dark-area .border-gray-200,
html.wa-dark body .wa-dark-area .border-blue-100,
html.wa-dark body .wa-dark-area .q-separator {
  border-color: #475569 !important;
}
html.wa-dark body .q-notification,
html.wa-dark body .q-notification__message,
html.wa-dark body .q-notification__caption,
html.wa-dark body .q-dialog__inner .q-card:not(.wa-staff-roll-window),
html.wa-dark body .q-dialog__inner .q-card__section,
html.wa-dark body .q-banner,
html.wa-dark body .q-banner__content,
html.wa-dark body .nicegui-reconnect,
html.wa-dark body .nicegui-reconnect *,
html.wa-dark body [id*="reconnect"],
html.wa-dark body [id*="reconnect"] *,
html.wa-dark body [class*="reconnect"],
html.wa-dark body [class*="reconnect"] *,
html.wa-dark body [id*="connection"],
html.wa-dark body [id*="connection"] *,
html.wa-dark body [class*="connection"],
html.wa-dark body [class*="connection"] * {
  background: #111827 !important;
  background-color: #111827 !important;
  color: #f8fafc !important;
  border-color: #475569 !important;
}
html.wa-dark body .wa-staff-roll-window {
  background: radial-gradient(circle at top, #283750 0%, #0b1020 58%, #050814 100%) !important;
  color: #f8fafc !important;
}
html.wa-dark body .wa-light-fallback,
html.wa-dark body .wa-light-fallback.bg-white,
html.wa-dark body .wa-light-fallback .bg-white,
html.wa-dark body .wa-light-fallback .q-card,
html.wa-dark body .wa-light-fallback .q-tab-panels,
html.wa-dark body .wa-light-fallback .q-tab-panel,
html.wa-dark body .wa-light-fallback .q-expansion-item,
html.wa-dark body .wa-light-fallback .q-expansion-item__container,
html.wa-dark body .wa-light-fallback .q-expansion-item__content {
  background: #ffffff !important;
  background-color: #ffffff !important;
  color: #111827 !important;
}
html.wa-dark body .wa-light-fallback,
html.wa-dark body .wa-light-fallback *,
html.wa-dark body .wa-light-fallback .text-\\[\\#1a2332\\],
html.wa-dark body .wa-light-fallback .text-gray-800,
html.wa-dark body .wa-light-fallback .text-gray-700,
html.wa-dark body .wa-light-fallback .text-gray-600,
html.wa-dark body .wa-light-fallback .text-gray-500,
html.wa-dark body .wa-light-fallback .text-gray-400,
html.wa-dark body .wa-light-fallback .q-btn__content,
html.wa-dark body .wa-light-fallback .q-icon,
html.wa-dark body .wa-light-fallback .q-tab,
html.wa-dark body .wa-light-fallback .q-tab__label {
  color: #111827 !important;
}
html.wa-dark body .wa-light-fallback .q-btn--outline,
html.wa-dark body .wa-light-fallback .q-btn--outline .q-btn__content,
html.wa-dark body .wa-light-fallback .q-btn--outline .q-icon {
  background: #ffffff !important;
  background-color: #ffffff !important;
  color: #2563eb !important;
}
html.wa-dark body .wa-light-fallback input,
html.wa-dark body .wa-light-fallback textarea,
html.wa-dark body .wa-light-fallback .q-field,
html.wa-dark body .wa-light-fallback .q-field__control,
html.wa-dark body .wa-light-fallback .q-field__native,
html.wa-dark body .wa-light-fallback .q-field__label {
  background: #ffffff !important;
  background-color: #ffffff !important;
  color: #111827 !important;
}
html.wa-dark body .wa-user-pill,
html.wa-dark body .wa-user-pill * {
  background: #ffffff !important;
  background-color: #ffffff !important;
  color: #111827 !important;
  border-color: #cbd5e1 !important;
}
html.wa-dark body .wa-type-filter .q-btn.bg-white,
html.wa-dark body .wa-type-filter .q-btn.text-grey-8 {
  background: #ffffff !important;
  background-color: #ffffff !important;
  color: #111827 !important;
}
html.wa-dark body .wa-type-filter .q-btn.bg-white .q-btn__content,
html.wa-dark body .wa-type-filter .q-btn.text-grey-8 .q-btn__content {
  color: #111827 !important;
}
</style>
""")

def app_now():
    return datetime.now(APP_TIMEZONE)

def current_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def parse_timestamp_utc(value):
    try:
        raw = str(value or '').strip().replace('Z', '+00:00')
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def format_timestamp(value):
    if not value:
        return ''
    try:
        raw = str(value).strip().replace('Z', '+00:00')
        dt = datetime.fromisoformat(raw)
    except ValueError:
        try:
            dt = datetime.strptime(str(value), '%Y-%m-%d %H:%M')
        except ValueError:
            return str(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(APP_TIMEZONE).strftime('%Y-%m-%d %H:%M')

def default_user_data():
    return {'users': {}, 'known_users': [], 'friend_requests': [], 'chats': {}}

def clean_stored_username(username):
    return str(username or '').strip()

def is_stored_guest_username(username):
    username = clean_stored_username(username)
    return username == GUEST_USERNAME or username.startswith(f'{GUEST_USERNAME}:')

def social_chat_id(members, chat_type='direct'):
    clean_members = sorted({
        clean_stored_username(member)
        for member in members
        if clean_stored_username(member)
    })
    digest = hashlib.sha1('|'.join(clean_members).encode('utf-8')).hexdigest()[:16]
    if chat_type == 'group':
        return f"group:{digest}:{app_now().strftime('%Y%m%d%H%M%S')}"
    return f"direct:{digest}"

def normalize_friend_requests(value):
    requests = []
    seen = set()
    if not isinstance(value, list):
        return requests
    for item in value:
        if not isinstance(item, dict):
            continue
        sender = clean_stored_username(item.get('from'))
        receiver = clean_stored_username(item.get('to'))
        if not sender or not receiver or sender == receiver:
            continue
        if is_stored_guest_username(sender) or is_stored_guest_username(receiver):
            continue
        marker = (sender, receiver)
        if marker in seen:
            continue
        requests.append({
            'from': sender,
            'to': receiver,
            'timestamp': str(item.get('timestamp') or current_timestamp()),
        })
        seen.add(marker)
    return requests

def normalize_social_chats(value):
    chats = {}
    if not isinstance(value, dict):
        return chats
    for chat_id, chat in value.items():
        if not isinstance(chat, dict):
            continue
        members = []
        for member in chat.get('members', []):
            member = clean_stored_username(member)
            if member and not is_stored_guest_username(member) and member not in members:
                members.append(member)
        if len(members) < 2:
            continue
        messages = []
        for message in chat.get('messages', []):
            if not isinstance(message, dict):
                continue
            sender = clean_stored_username(message.get('user'))
            text = str(message.get('text') or '').strip()
            if not sender or sender not in members or not text:
                continue
            messages.append({
                'user': sender,
                'text': text[:500],
                'timestamp': str(message.get('timestamp') or current_timestamp()),
            })
        chat_type = 'group' if chat.get('type') == 'group' else 'direct'
        clean_id = str(chat_id or '').strip() or social_chat_id(members, chat_type)
        chats[clean_id] = {
            'id': clean_id,
            'type': chat_type,
            'name': str(chat.get('name') or '').strip(),
            'created_by': clean_stored_username(chat.get('created_by')),
            'members': members,
            'messages': messages[-60:],
            'created_at': str(chat.get('created_at') or current_timestamp()),
        }
    return dict(sorted(
        chats.items(),
        key=lambda item: item[1].get('messages', [{}])[-1].get('timestamp') if item[1].get('messages') else item[1].get('created_at', ''),
        reverse=True,
    )[:80])

USER_RECORD_KEYS = {
    'password_hash',
    'favorites',
    'history',
    'notes',
    'viewed_keys',
    'collections',
    'quiz_history',
    'review_keys',
    'quiz_stats',
    'avatar',
    'name_color',
    'hide_public_profile',
    'battle_wins',
    'battle_unlocked',
    'battle_unlocked_notified',
    'sengoku_unlocked',
    'sengoku_unlocked_notified',
    'sengoku_mode',
    'sengoku_medal',
    'sengoku_boss_clears',
    'all_viewed_granted',
    'friends',
    'notifications',
}

def looks_like_user_record(value):
    return isinstance(value, dict) and bool(USER_RECORD_KEYS.intersection(value.keys()))

def user_record_from_candidate(value):
    if not isinstance(value, dict):
        return None
    if looks_like_user_record(value):
        return value
    for key in ['record', 'user', 'data', 'profile']:
        record = value.get(key)
        if looks_like_user_record(record):
            return record
    return None

def normalize_sengoku_boss_clears(value):
    valid = {f'boss_{index}' for index in range(1, 9)}
    seen = set()
    clears = []
    for boss_id in value if isinstance(value, list) else []:
        boss_id = str(boss_id or '')
        if boss_id in valid and boss_id not in seen:
            clears.append(boss_id)
            seen.add(boss_id)
    return clears

def normalize_user_data_file(data):
    if not isinstance(data, dict):
        return default_user_data()
    raw_users = data.get('users')
    users = {}
    if isinstance(raw_users, dict):
        for username, record in raw_users.items():
            normalized_record = user_record_from_candidate(record)
            if normalized_record:
                clean_name = str(username or '').strip()
                if clean_name:
                    users[clean_name] = normalized_record
    elif isinstance(raw_users, list):
        for item in raw_users:
            if not isinstance(item, dict):
                continue
            username = str(item.get('username') or item.get('name') or item.get('id') or '').strip()
            record = user_record_from_candidate(item)
            if username and record:
                users[username] = record
    backup_username = str(data.get('username') or '').strip()
    if backup_username and looks_like_user_record(data.get('record')) and backup_username not in users:
        users[backup_username] = data['record']
    for key, value in list(data.items()):
        if key == 'users':
            continue
        record = user_record_from_candidate(value)
        username = str(value.get('username') or '').strip() if isinstance(value, dict) else ''
        username = username or str(key or '').strip()
        if record and username and username not in users:
            users[username] = record
    for record in users.values():
        if isinstance(record, dict):
            ensure_user_defaults(record)
    data['users'] = users
    known_users = []
    if isinstance(data.get('known_users'), list):
        known_users.extend(str(username or '').strip() for username in data['known_users'])
    known_users.extend(users.keys())
    data['known_users'] = sorted({
        username for username in known_users
        if username and username != GUEST_USERNAME and not username.startswith(f'{GUEST_USERNAME}:')
    }, key=lambda value: value.lower())
    data['friend_requests'] = normalize_friend_requests(data.get('friend_requests'))
    data['chats'] = normalize_social_chats(data.get('chats'))
    return data

def load_user_data():
    global USER_DATA_CACHE, USER_DATA_CACHE_MTIME
    if not os.path.exists(USER_DATA_FILE):
        USER_DATA_CACHE = default_user_data()
        USER_DATA_CACHE_MTIME = None
        return USER_DATA_CACHE
    mtime = file_mtime(USER_DATA_FILE)
    if USER_DATA_CACHE is not None and USER_DATA_CACHE_MTIME == mtime:
        return USER_DATA_CACHE
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        before_normalize = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        normalized = normalize_user_data_file(data)
        after_normalize = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        if after_normalize != before_normalize:
            save_user_data(normalized)
            return USER_DATA_CACHE
        USER_DATA_CACHE = normalized
        USER_DATA_CACHE_MTIME = mtime
        return USER_DATA_CACHE
    except Exception as e:
        print(f"Error loading user data: {e}")
        return default_user_data()

def save_user_data(data):
    global USER_DATA_CACHE, USER_DATA_CACHE_MTIME
    data = normalize_user_data_file(data)
    data = {
        'users': data.get('users', {}),
        'known_users': data.get('known_users', []),
        'friend_requests': data.get('friend_requests', []),
        'chats': data.get('chats', {}),
    }
    user_dir = os.path.dirname(USER_DATA_FILE)
    if user_dir:
        os.makedirs(user_dir, exist_ok=True)
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    USER_DATA_CACHE = data
    USER_DATA_CACHE_MTIME = file_mtime(USER_DATA_FILE)

def merge_unique_list(current, incoming, limit=None):
    merged = list(current) if isinstance(current, list) else []
    incoming_items = incoming if isinstance(incoming, list) else []
    for item in incoming_items:
        if item not in merged:
            merged.append(item)
    if limit:
        del merged[limit:]
    return merged

def merge_record_history(current, incoming, limit):
    merged = merge_unique_list(current, incoming)
    merged.sort(
        key=lambda item: parse_timestamp_utc(item.get('timestamp') if isinstance(item, dict) else ''),
        reverse=True,
    )
    return merged[:limit]

def quiz_stats_from_history(history):
    entries = [entry for entry in history if isinstance(entry, dict)]
    entries.sort(key=lambda entry: parse_timestamp_utc(entry.get('timestamp')), reverse=True)
    answered = len(entries)
    correct = sum(1 for entry in entries if entry.get('correct'))
    current_streak = 0
    for entry in entries:
        if entry.get('correct'):
            current_streak += 1
        else:
            break
    best_streak = 0
    running_streak = 0
    for entry in reversed(entries):
        if entry.get('correct'):
            running_streak += 1
            best_streak = max(best_streak, running_streak)
        else:
            running_streak = 0
    return {
        'answered': answered,
        'correct': correct,
        'streak': current_streak,
        'best_streak': best_streak,
    }

def normalize_quiz_stats(user):
    raw_stats = user.get('quiz_stats') if isinstance(user.get('quiz_stats'), dict) else {}
    history_stats = quiz_stats_from_history(user.get('quiz_history', []))
    normalized = {}
    for key in ['answered', 'correct', 'streak', 'best_streak']:
        try:
            raw_value = int(raw_stats.get(key, 0) or 0)
        except (TypeError, ValueError):
            raw_value = 0
        normalized[key] = max(raw_value, history_stats.get(key, 0))
    user['quiz_stats'] = normalized
    return normalized

def merge_user_record(current, incoming):
    if not isinstance(current, dict):
        current = {}
    if not isinstance(incoming, dict):
        return current
    for key, value in incoming.items():
        if key in ['favorites', 'review_keys', 'friends', 'sengoku_boss_clears']:
            current[key] = merge_unique_list(current.get(key, []), value)
        elif key == 'history':
            current[key] = merge_unique_list(current.get(key, []), value, 50)
        elif key == 'notifications' and isinstance(value, list):
            existing = normalize_notifications(current.get('notifications'))
            seen = {item.get('id') for item in existing}
            for item in normalize_notifications(value):
                if item.get('id') not in seen:
                    existing.append(item)
                    seen.add(item.get('id'))
            current[key] = sorted(
                existing,
                key=lambda item: item.get('created_at', ''),
                reverse=True,
            )[:100]
        elif key == 'notes' and isinstance(value, dict):
            notes = current.setdefault('notes', {})
            for note_key, note_value in value.items():
                notes.setdefault(note_key, note_value)
        elif key == 'collections' and isinstance(value, dict):
            collections = current.setdefault('collections', {})
            for collection_name, collection_keys in value.items():
                collections[collection_name] = merge_unique_list(
                    collections.get(collection_name, []),
                    collection_keys,
                )
        elif key == 'quiz_stats' and isinstance(value, dict):
            stats = current.setdefault('quiz_stats', {})
            for stat_key, stat_value in value.items():
                try:
                    incoming_stat = int(stat_value)
                    current_stat = int(stats.get(stat_key, 0) or 0)
                    stats[stat_key] = max(current_stat, incoming_stat)
                except (TypeError, ValueError):
                    stats.setdefault(stat_key, stat_value)
        elif key == 'viewed_keys':
            current[key] = merge_unique_list(current.get(key, []), value)
        elif key == 'quiz_history':
            current[key] = merge_record_history(current.get(key, []), value, 200)
        elif key == 'avatar' and isinstance(value, dict):
            current_avatar = current.get('avatar') if isinstance(current.get('avatar'), dict) else {}
            incoming_mode = value.get('mode')
            current_mode = current_avatar.get('mode')
            if incoming_mode in ['flag', 'upload'] or current_mode not in ['flag', 'upload']:
                current[key] = dict(value)
        elif key == 'name_color':
            current[key] = value
        elif key == 'hide_public_profile':
            current[key] = bool(current.get(key, False) or value)
        elif key == 'battle_wins' and isinstance(value, int):
            current[key] = max(current.get(key, 0), value)
        elif key in ['battle_unlocked', 'battle_unlocked_notified', 'sengoku_unlocked', 'sengoku_unlocked_notified', 'sengoku_mode', 'sengoku_medal', 'all_viewed_granted'] and isinstance(value, bool):
            current[key] = bool(current.get(key, False) or value)
        else:
            current.setdefault(key, value)
    normalize_quiz_stats(current)
    return current

LEGACY_ALL_VIEWED_MIN_COUNT = 280

def raw_country_key(country):
    names = country.get('names', {}) if isinstance(country.get('names'), dict) else {}
    capital = country.get('capital', {}) if isinstance(country.get('capital'), dict) else {}
    return '|'.join([
        names.get('en', names.get('ja', '')),
        country.get('type', ''),
        capital.get('en', capital.get('ja', '')),
    ])

def raw_public_country_keys():
    mtime = file_mtime(JSON_FILE)
    cached = RAW_PUBLIC_COUNTRY_KEYS_CACHE
    if cached.get('mtime') == mtime and isinstance(cached.get('value'), list):
        return list(cached['value'])
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return []
    keys = []
    seen = set()
    for country in data.get('countries', []):
        if not isinstance(country, dict) or country.get('hidden'):
            continue
        key = raw_country_key(country)
        if key and key not in seen:
            keys.append(key)
            seen.add(key)
    RAW_PUBLIC_COUNTRY_KEYS_CACHE['mtime'] = mtime
    RAW_PUBLIC_COUNTRY_KEYS_CACHE['value'] = list(keys)
    return keys

def restore_all_viewed_progress_if_unlocked(user):
    if not isinstance(user, dict):
        return False
    viewed = user.setdefault('viewed_keys', [])
    public_keys = raw_public_country_keys()
    public_set = set(public_keys)
    viewed_set = set(viewed)
    valid_viewed_count = len(viewed_set & public_set)
    already_current_all_viewed = bool(public_set) and public_set.issubset(viewed_set)
    legacy_unlock = (
        bool(user.get('all_viewed_granted'))
        or (
            bool(user.get('battle_unlocked') or user.get('battle_unlocked_notified') or user.get('sengoku_unlocked') or user.get('sengoku_medal'))
            and valid_viewed_count >= LEGACY_ALL_VIEWED_MIN_COUNT
        )
    )
    changed = False
    if already_current_all_viewed and not user.get('all_viewed_granted'):
        user['all_viewed_granted'] = True
        changed = True
    if (already_current_all_viewed or legacy_unlock) and not user.get('battle_unlocked'):
        user['battle_unlocked'] = True
        changed = True
    return changed

def migrate_embedded_user_data():
    if not os.path.exists(JSON_FILE):
        return
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error checking embedded user data: {e}")
        return

    embedded_users = data.get('users') if isinstance(data.get('users'), dict) else {}
    legacy_history = data.get('history') if isinstance(data.get('history'), list) else []
    legacy_favorites = data.get('favorites') if isinstance(data.get('favorites'), list) else []
    has_user_keys = any(key in data for key in ['users', 'history', 'favorites'])

    if embedded_users or legacy_history or legacy_favorites:
        user_data = load_user_data()
        users = user_data.setdefault('users', {})
        for username, record in embedded_users.items():
            users[username] = merge_user_record(users.get(username, {}), record)
        if legacy_history or legacy_favorites:
            users[GUEST_USERNAME] = merge_user_record(
                users.get(GUEST_USERNAME, {}),
                {'history': legacy_history, 'favorites': legacy_favorites},
            )
        save_user_data(user_data)

    if has_user_keys:
        for key in ['users', 'history', 'favorites']:
            data.pop(key, None)
        try:
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error removing embedded user data: {e}")

def init_json():
    """
    ファイルが存在しない場合のみ、初期データを作成する。
    """
    if not os.path.exists(JSON_FILE):
        default_data = {
            "translations": {
                'ja': {
                    'app_title': 'World Archives',
                    'subtitle': '国・地域・歴史アーカイブ検索',
                    'tabs': {'All': 'すべて', 'Present': '現存', 'Past': '過去'},
                    'labels': {'capital': '首都', 'region': '地域', 'tags': 'タグ', 'desc': '解説'}
                },
                'en': {
                    'app_title': 'World Archives',
                    'subtitle': 'Historical & Regional Archives',
                    'tabs': {'All': 'All', 'Present': 'Present', 'Past': 'Past'},
                    'labels': {'capital': 'Capital', 'region': 'Region', 'tags': 'Tags', 'desc': 'Description'}
                }
            },
            "countries": []
        }
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)

def load_translations():
    """data.json から translations セクションを読み込む"""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('translations', {})
        except Exception as e:
            print(f"Error loading translations: {e}")
            return {}
    return {}

init_json()
migrate_embedded_user_data()

TRANSLATIONS = load_translations()

class AppState:
    selected_country = None
    filter_type = 'All'
    filter_region = None
    filter_tag_group = None
    filter_tag = None
    sort_field = 'name'
    sort_order = 'asc'
    show_favorites_only = False
    favorite_filter = 'all'
    lang = 'ja'
    ui_mode = 'pc'
    current_user = None
    current_user_browser_sync_pending = False
    theme_mode = 'light'
    search_keyword = ''
    page = 1
    items_per_page = 20
    quiz = None
    quiz_difficulty = 'medium'
    quiz_mode = 'normal'
    quiz_category = 'all'
    quiz_format = 'mixed'
    quiz_scope = 'all'
    compare_left_key = None
    compare_right_key = None
    map_country_key = None
    network_country_key = None
    collection_filter = None
    timeline_group = 'period_contemporary'
    timeline_page = 1
    timeline_items_per_page = 20
    users_page = 1
    users_items_per_page = 6
    users_search_keyword = ''
    users_favorite_country_key = None
    users_browser_restore_requested = False
    public_users_browser_synced = False
    public_users_browser_sync_pending = False
    public_collection_owner = None
    public_collection_name = None
    public_collection_keys = []
    public_collection_kind = 'collection'
    battle_id = None
    battle_selected_keys = set()
    battle_attack_target = None
    battle_turn_timeout_seconds = 60
    battle_world_war_turn = 75
    battle_room_player_count = 3
    battle_team_count = 2
    battle_team_choice = 'A'
    battle_events_enabled = True
    battle_last_signature = ''
    staff_roll_room_shown = None
    sengoku_mode = False
    social_selected_chat_id = None
    social_last_signature = ''
    social_notify_user = None
    social_notify_snapshot = None
    ranking_quiz_category = 'overall'
    current_screen = 'top'
    detail_return_screen = 'main'

state = AppState()

BATTLE_QUEUE = []
BATTLE_ROOMS = {}
BATTLE_USER_ROOM = {}
BATTLE_COUNTER = 0
BOT_USERNAME = 'BOT'
BATTLE_MAX_HP = 100_000_000_000_000
BATTLE_TURN_TIMEOUT_SECONDS = 60
BATTLE_TURN_TIMEOUT_UNLIMITED = 0
BATTLE_TURN_TIMEOUT_OPTIONS = [60, 180, 300, BATTLE_TURN_TIMEOUT_UNLIMITED]
BATTLE_HEARTBEAT_INTERVAL_SECONDS = 3
BATTLE_DISCONNECT_REPLACE_SECONDS = 8
BATTLE_POWER_SCALE = 300_000
BATTLE_MAX_COMMAND = 7
BATTLE_REDRAW_COMMAND_COST = 2
BATTLE_CARD_COMMAND_COSTS = [1, 2, 4, 6, 7]
BATTLE_CARD_POWER_PERCENTS = [100, 90, 80, 70, 60]
BATTLE_DEFENSE_PERCENT = 50
BATTLE_BONUS_PER_MATCH_BPS = 5000
BATTLE_BONUS_DENOMINATOR = 10_000
BATTLE_DAMAGE_OUTPUT_PERCENT = 30
BATTLE_WORLD_WAR_TURN = 75
BATTLE_WORLD_WAR_DISABLED = 0
BATTLE_WORLD_WAR_TURN_OPTIONS = [1, 25, 50, 75, 100, BATTLE_WORLD_WAR_DISABLED]
BATTLE_WORLD_WAR_DAMAGE_MULTIPLIER = 5
BATTLE_LOG_LIMIT = 6
BATTLE_CHAT_LIMIT = 12
BATTLE_LAST_TURN_ROW_LIMIT = 9
BATTLE_AUTO_REFRESH_SECONDS = 3.0
BATTLE_PRESSURE_START_TURN = 10
BATTLE_PRESSURE_PER_TURN_BPS = 500
BATTLE_PRESSURE_MAX_EXTRA_BPS = 15_000
BATTLE_REVOLUTION_CHANCE = 0.003
BATTLE_WORLD_WAR_REVOLUTION_CHANCE = 0.009
BATTLE_REVOLUTION_MIN_TURNS = 3
BATTLE_REVOLUTION_MAX_TURNS = 7
BATTLE_RANDOM_EVENT_CHANCE = 0.03
BATTLE_RANDOM_EVENT_MIN_TURNS = 3
BATTLE_RANDOM_EVENT_MAX_TURNS = 7
BATTLE_OPERATION_CONFUSION_MISSING_CHANCE_PERCENT = 20
BATTLE_CEASEFIRE_DAMAGE_MULTIPLIER = 0.35
BATTLE_COMMAND_SURGE_RECOVERY = 2
BATTLE_SUPPLY_DROP_THRESHOLD = 2
BATTLE_BOMB_DAMAGE_PERCENT = 18
BATTLE_BOMB_CARD = 'event:hot_potato_bomb'
BATTLE_LYTTON_EVENT_WEIGHT = 0.7
BATTLE_VATICAN_DRAW_CHANCE = 0.45
BATTLE_SPECIAL_CARD_CHANCE = 0.12
BATTLE_SPECIAL_CARD_MAX_PER_HAND = 2
BATTLE_SPECIAL_CARD_PREFIX = 'event:'
BATTLE_SPECIAL_CARDS = {
    'event:supply_collapse': {'damage_percent': 1, 'weight': 1.4},
    'event:frontline_disaster': {'damage_percent': 2, 'weight': 0.75},
    'event:fallout_crisis': {'damage_percent': 4, 'weight': 0.28},
    'event:scorched_earth': {'damage_percent': 1, 'destroy_one': True, 'weight': 1.0},
    'event:relief_convoy': {'heal_percent': 3, 'weight': 0.22},
    BATTLE_BOMB_CARD: {'bomb': True, 'weight': 0},
}
BATTLE_SATRAPY_PROVINCES = [
    {'id': 'Asia', 'name': {'ja': 'アジア属州', 'en': 'Asia Satrapy', 'zh': '亚洲行省'}},
    {'id': 'Africa', 'name': {'ja': 'アフリカ属州', 'en': 'Africa Satrapy', 'zh': '非洲行省'}},
    {'id': 'Europe', 'name': {'ja': 'ヨーロッパ属州', 'en': 'Europe Satrapy', 'zh': '欧洲行省'}},
    {'id': 'North America', 'name': {'ja': '北アメリカ属州', 'en': 'North America Satrapy', 'zh': '北美洲行省'}},
    {'id': 'South America', 'name': {'ja': '南アメリカ属州', 'en': 'South America Satrapy', 'zh': '南美洲行省'}},
    {'id': 'Oceania', 'name': {'ja': 'オセアニア属州', 'en': 'Oceania Satrapy', 'zh': '大洋洲行省'}},
]

SENGOKU_BOSS_EVENT_FIELDS = {
    'revolution': 'revolution_until_turn',
    'flag_only': 'flag_only_until_turn',
    'vatican': 'vatican_until_turn',
    'replace': 'replace_until_turn',
    'bomb': 'bomb_until_turn',
    'lytton': 'lytton_until_turn',
    'damage_surge': 'damage_surge_until_turn',
    'random_target': 'random_target_until_turn',
    'ceasefire': 'ceasefire_until_turn',
    'command_surge': 'command_surge_until_turn',
    'supply_drop': 'supply_drop_until_turn',
    'blockade': 'blockade_until_turn',
}
SENGOKU_BOSS_FORCED_TURN = 999_999
DUEL_MODE = 'duel'
FFA_MODE = 'free_for_all'
TEAM_MODE = 'team'
BOT_MODE = 'bot'
BATTLE_MAX_MULTIPLAYER_PLAYERS = 9
BATTLE_MIN_MULTIPLAYER_PLAYERS = 2
BATTLE_TEAM_IDS = ['A', 'B', 'C', 'D']
BATTLE_TEAM_COLORS = {
    'A': 'red',
    'B': 'blue',
    'C': 'green',
    'D': 'purple',
}
MULTIPLAYER_MODES = {
    DUEL_MODE: 2,
    FFA_MODE: BATTLE_MAX_MULTIPLAYER_PLAYERS,
    TEAM_MODE: BATTLE_MAX_MULTIPLAYER_PLAYERS,
}
ADMIN_SEARCH_CHEAT_CODE = '上上下下左右左右BA'
SENGOKU_SEARCH_CHEAT_CODE = 'HH右NK'
SECRET_HIDDEN_COUNTRY_SEARCH_TERMS = {'ケッテン連邦'}
DEFAULT_NAME_COLOR = '#1a2332'
NAME_COLOR_OPTIONS = [
    '#1a2332',
    '#2563eb',
    '#059669',
    '#dc2626',
    '#7c3aed',
    '#ca8a04',
    '#0891b2',
    '#db2777',
]

UI_FALLBACKS = {
    'ja': {
        'sort_asc': '昇順',
        'sort_desc': '降順',
        'favorites_only': 'お気に入りのみ',
        'favorite_add': 'お気に入りに追加',
        'favorite_remove': 'お気に入りから削除',
        'quiz': 'ミニクイズ',
        'quiz_title': 'ミニクイズ',
        'quiz_next': '次の問題',
        'quiz_detail': '詳細を見る',
        'quiz_correct': '正解です',
        'quiz_wrong': '不正解です',
        'quiz_time_remaining': '残り {seconds} 秒',
        'quiz_time_up': '時間切れです',
        'quiz_capital': '首都または中心地が「{capital}」なのはどれ？',
        'quiz_desc': 'この説明に当てはまるのはどれ？',
        'quiz_flag': 'この旗の国・地域はどれ？',
        'quiz_period': '年代が「{period}」なのはどれ？',
        'quiz_profile': '{label}が「{value}」なのはどれ？',
        'quiz_category': '分野',
        'quiz_format': '形式',
        'quiz_scope': '出題範囲',
        'quiz_scope_all': '全問',
        'quiz_scope_past': '過去の国のみ',
        'quiz_scope_present': '現代の国のみ',
        'quiz_format_mixed': '混合',
        'quiz_format_info_fixed': '国を選ぶ',
        'quiz_format_country_fixed': '情報を選ぶ',
        'quiz_category_all': '総合',
        'quiz_category_flag': '国旗',
        'quiz_category_period': '年号',
        'quiz_category_capital': '首都',
        'quiz_category_tag': 'タグ',
        'quiz_category_desc': '説明',
        'quiz_category_profile': '基本データ',
        'quiz_category_detail': '詳細データ',
        'quiz_tag': '「{tag}」に当てはまる国・地域はどれ？',
        'quiz_capital_reverse': '「{country}」の首都または中心地はどれ？',
        'quiz_desc_reverse': '「{country}」の説明はどれ？',
        'quiz_flag_reverse': '「{country}」の国旗はどれ？',
        'quiz_period_reverse': '「{country}」の年代はどれ？',
        'quiz_tag_reverse': '「{country}」に当てはまるタグはどれ？',
        'quiz_profile_reverse': '「{country}」の{label}はどれ？',
        'quiz_detail_reverse': '「{country}」の{label}はどれ？',
        'quiz_select_option': 'この選択肢を選ぶ',
        'ui_mobile': 'スマホUI',
        'ui_pc': 'パソコンUI',
        'switch_to_mobile': 'スマホ表示に切替',
        'switch_to_pc': 'パソコン表示に切替',
        'page_unit': 'ページ',
        'first_page': '最初のページ',
        'prev_page': '前のページ',
        'next_page': '次のページ',
        'last_page': '最後のページ',
        'no_result': '該当する国・地域は見つかりませんでした。',
        'username': 'ユーザー名',
        'password': 'パスワード',
        'login': 'ログイン',
        'register': '新規登録',
        'logout': 'ログアウト',
        'logged_in_as': 'ログイン中: {user}',
        'login_required': 'ログインすると検索・お気に入り・履歴を使えます。',
        'auth_missing': 'ユーザー名とパスワードを入力してください。',
        'auth_invalid': 'ユーザー名またはパスワードが違います。',
        'user_exists': 'そのユーザー名は既に使われています。',
        'user_created': 'ユーザーを作成しました。',
        'login_success': 'ログインしました。',
        'logout_success': 'ログアウトしました。',
        'compare': '比較',
        'compare_title': '国を比較',
        'compare_left': '比較する国 1',
        'compare_right': '比較する国 2',
        'today_country': '今日の国',
        'view_detail': '詳細を見る',
        'notes': '自分用メモ',
        'save_note': 'メモを保存',
        'note_saved': 'メモを保存しました。',
        'related_countries': '関連する国',
        'timeline': '年表',
        'timeline_title': '歴史年表',
        'period_ancient': '古代',
        'period_medieval': '中世',
        'period_modern': '近現代',
        'period_other': 'その他',
        'difficulty': '難易度',
        'difficulty_easy': '初級',
        'difficulty_medium': '中級',
        'difficulty_hard': '上級',
        'difficulty_extreme': '超級',
        'battle_direct': '国力対戦',
        'battle_unlock_hint': '現存する国をすべて閲覧する、またはミニクイズで累計100問正解すると解放されます。ゲストでも解放できます。',
        'battle_events_setting': 'イベント',
        'battle_events_on': 'あり',
        'battle_events_off': 'なし',
        'battle_kick': 'キック',
        'battle_kicked_notice': 'この部屋からキックされています。',
        'battle_kicked_log': '{player} はホストにより退室しました。',
        'sengoku_mode': '戦国モード',
        'normal_mode': '通常モード',
        'sengoku_mode_on': '戦国モードに切り替えました。',
        'sengoku_mode_off': '通常モードに戻しました。',
        'sengoku_unlocked_notice': '戦国モードが解禁されました。',
        'sengoku_unlock_hint': '国力対戦解放後、全国家を閲覧するか、上級・総合・全問・混合のミニクイズで20問連続正解すると解放されます。',
        'theme_dark': 'ダーク',
        'theme_light': 'ライト',
        'theme_toggle': '表示テーマ',
        'quiz_stats': '正解 {correct} / {answered}・連続 {streak}・最高 {best}',
        'account': 'アカウント',
        'avatar': 'アイコン',
        'avatar_current': '現在のアイコン',
        'avatar_flag': '国旗をアイコンにする',
        'avatar_upload': '画像をアップロード',
        'avatar_reset': '標準アイコンに戻す',
        'avatar_saved': 'アイコンを更新しました。',
        'avatar_upload_failed': '画像をアップロードできませんでした。',
        'avatar_file_hint': 'PNG、JPG、WEBP、GIFを選べます。',
        'map': '地図',
        'map_title': '地図ビュー',
        'map_note': '過去の国は現在の関連地域を表示します。',
        'network': '関連ネットワーク',
        'network_title': '関連国家ネットワーク',
        'collections': 'コレクション',
        'collection_name': 'コレクション名',
        'create_collection': '作成',
        'add_to_collection': 'コレクションに追加',
        'remove_from_collection': 'コレクションから外す',
        'collection_created': 'コレクションを作成しました。',
        'collection_deleted': 'コレクションを削除しました。',
        'progress': '学習進捗',
        'viewed_count': '閲覧済み',
        'favorite_count': 'お気に入り',
        'review_count': '復習リスト',
        'quiz_history': 'クイズ履歴',
        'weakness': '弱点分析',
        'no_quiz_history': 'クイズ履歴はまだありません。',
        'no_collections': 'コレクションはまだありません。',
        'view_on_map': '地図で見る',
        'key_figures': '重要人物',
        'major_events': '主な出来事',
        'fall_reason': '滅亡・変化の理由',
        'successors': '後継・関連国家',
        'cultural_features': '文化的特徴',
    },
    'en': {
        'sort_asc': 'Ascending',
        'sort_desc': 'Descending',
        'favorites_only': 'Favorites only',
        'favorites_except': 'Not favorites',
        'favorites_all': 'No favorite filter',
        'favorite_add': 'Add favorite',
        'favorite_remove': 'Remove favorite',
        'quiz': 'Mini Quiz',
        'quiz_title': 'Mini Quiz',
        'quiz_next': 'Next Question',
        'quiz_detail': 'View Details',
        'quiz_correct': 'Correct',
        'quiz_wrong': 'Not quite',
        'quiz_time_remaining': '{seconds}s left',
        'quiz_time_up': 'Time is up',
        'quiz_capital': 'Which one has “{capital}” as its capital or main center?',
        'quiz_desc': 'Which entry matches this description?',
        'quiz_flag': 'Which country or historical state uses this flag?',
        'quiz_period': 'Which one belongs to “{period}”?',
        'quiz_profile': 'Which one has {label}: “{value}”?',
        'quiz_category': 'Category',
        'quiz_format': 'Format',
        'quiz_scope': 'Scope',
        'quiz_scope_all': 'All',
        'quiz_scope_past': 'Historical only',
        'quiz_scope_present': 'Present only',
        'quiz_format_mixed': 'Mixed',
        'quiz_format_info_fixed': 'Choose country',
        'quiz_format_country_fixed': 'Choose info',
        'quiz_category_all': 'Mixed',
        'quiz_category_flag': 'Flags',
        'quiz_category_period': 'Years',
        'quiz_category_capital': 'Capitals',
        'quiz_category_tag': 'Tags',
        'quiz_category_desc': 'Descriptions',
        'quiz_category_profile': 'Basic Data',
        'quiz_category_detail': 'Details',
        'quiz_tag': 'Which country or region matches “{tag}”?',
        'quiz_capital_reverse': 'What is the capital or main center of “{country}”?',
        'quiz_desc_reverse': 'Which description matches “{country}”?',
        'quiz_flag_reverse': 'Which flag belongs to “{country}”?',
        'quiz_period_reverse': 'Which period belongs to “{country}”?',
        'quiz_tag_reverse': 'Which tag matches “{country}”?',
        'quiz_profile_reverse': 'Which {label} matches “{country}”?',
        'quiz_detail_reverse': 'Which {label} matches “{country}”?',
        'quiz_select_option': 'Choose this option',
        'ui_mobile': 'Mobile UI',
        'ui_pc': 'Desktop UI',
        'switch_to_mobile': 'Switch to Mobile UI',
        'switch_to_pc': 'Switch to Desktop UI',
        'page_unit': 'pages',
        'first_page': 'First page',
        'prev_page': 'Previous page',
        'next_page': 'Next page',
        'last_page': 'Last page',
        'no_result': 'No countries found.',
        'username': 'Username',
        'password': 'Password',
        'login': 'Log in',
        'register': 'Register',
        'logout': 'Log out',
        'logged_in_as': 'Signed in as: {user}',
        'login_required': 'Log in to use search, favorites, and history.',
        'auth_missing': 'Enter a username and password.',
        'auth_invalid': 'The username or password is incorrect.',
        'user_exists': 'That username is already taken.',
        'user_created': 'Account created.',
        'login_success': 'Logged in.',
        'logout_success': 'Logged out.',
        'compare': 'Compare',
        'compare_title': 'Compare Countries',
        'compare_left': 'Country 1',
        'compare_right': 'Country 2',
        'today_country': "Today's Country",
        'view_detail': 'View Details',
        'notes': 'My Notes',
        'save_note': 'Save Note',
        'note_saved': 'Note saved.',
        'related_countries': 'Related Countries',
        'timeline': 'Timeline',
        'timeline_title': 'Historical Timeline',
        'period_ancient': 'Ancient',
        'period_medieval': 'Medieval',
        'period_modern': 'Modern',
        'period_other': 'Other',
        'difficulty': 'Difficulty',
        'difficulty_easy': 'Easy',
        'difficulty_medium': 'Medium',
        'difficulty_hard': 'Hard',
        'difficulty_extreme': 'Extreme',
        'battle_direct': 'Power Battle',
        'battle_unlock_hint': 'Unlock by viewing every present country or answering 100 mini quiz questions correctly. Guests can unlock it too.',
        'battle_events_setting': 'Events',
        'battle_events_on': 'On',
        'battle_events_off': 'Off',
        'battle_kick': 'Kick',
        'battle_kicked_notice': 'You were kicked from this room.',
        'battle_kicked_log': '{player} was removed by the host.',
        'sengoku_mode': 'Sengoku Mode',
        'normal_mode': 'Normal Mode',
        'sengoku_mode_on': 'Sengoku Mode enabled.',
        'sengoku_mode_off': 'Returned to Normal Mode.',
        'sengoku_unlocked_notice': 'Sengoku Mode is now unlocked.',
        'sengoku_unlock_hint': 'After unlocking Power Battle, view every country or get 20 consecutive correct answers on Hard / Overall / All / Mixed quiz settings.',
        'theme_dark': 'Dark',
        'theme_light': 'Light',
        'theme_toggle': 'Theme',
        'quiz_stats': 'Correct {correct} / {answered} - Streak {streak} - Best {best}',
        'account': 'Account',
        'avatar': 'Icon',
        'avatar_current': 'Current Icon',
        'avatar_flag': 'Use a Flag',
        'avatar_upload': 'Upload Image',
        'avatar_reset': 'Reset Icon',
        'avatar_saved': 'Icon updated.',
        'avatar_upload_failed': 'Could not upload the image.',
        'avatar_file_hint': 'PNG, JPG, WEBP, or GIF files are supported.',
        'map': 'Map',
        'map_title': 'Map View',
        'map_note': 'Historical states show a related present-day location.',
        'network': 'Network',
        'network_title': 'Related Country Network',
        'collections': 'Collections',
        'collection_name': 'Collection name',
        'create_collection': 'Create',
        'add_to_collection': 'Add to collection',
        'remove_from_collection': 'Remove from collection',
        'collection_created': 'Collection created.',
        'collection_deleted': 'Collection deleted.',
        'progress': 'Learning Progress',
        'viewed_count': 'Viewed',
        'favorite_count': 'Favorites',
        'review_count': 'Review list',
        'quiz_history': 'Quiz History',
        'weakness': 'Weakness Analysis',
        'no_quiz_history': 'No quiz history yet.',
        'no_collections': 'No collections yet.',
        'view_on_map': 'View on map',
        'key_figures': 'Key figures',
        'major_events': 'Major events',
        'fall_reason': 'Fall or transition',
        'successors': 'Successor or related states',
        'cultural_features': 'Cultural features',
    },
    'zh': {
        'sort_asc': '升序',
        'sort_desc': '降序',
        'favorites_only': '仅收藏',
        'favorite_add': '加入收藏',
        'favorite_remove': '取消收藏',
        'quiz': '小测验',
        'quiz_title': '小测验',
        'quiz_next': '下一题',
        'quiz_detail': '查看详情',
        'quiz_correct': '回答正确',
        'quiz_wrong': '回答错误',
        'quiz_time_remaining': '剩余 {seconds} 秒',
        'quiz_time_up': '时间到',
        'quiz_capital': '首都或中心地是“{capital}”的是哪一个？',
        'quiz_desc': '以下说明对应哪一个？',
        'quiz_flag': '这面旗帜对应哪个国家或历史国家？',
        'quiz_period': '年代为“{period}”的是哪一个？',
        'quiz_profile': '{label}为“{value}”的是哪一个？',
        'quiz_category': '领域',
        'quiz_format': '形式',
        'quiz_scope': '出题范围',
        'quiz_scope_all': '全部',
        'quiz_scope_past': '仅历史国家',
        'quiz_scope_present': '仅现代国家',
        'quiz_format_mixed': '混合',
        'quiz_format_info_fixed': '选择国家',
        'quiz_format_country_fixed': '选择信息',
        'quiz_category_all': '综合',
        'quiz_category_flag': '旗帜',
        'quiz_category_period': '年代',
        'quiz_category_capital': '首都',
        'quiz_category_tag': '标签',
        'quiz_category_desc': '说明',
        'quiz_category_profile': '基本数据',
        'quiz_category_detail': '详细资料',
        'quiz_tag': '哪一个国家或地区符合“{tag}”？',
        'quiz_capital_reverse': '“{country}”的首都或中心地是哪一个？',
        'quiz_desc_reverse': '哪一段说明符合“{country}”？',
        'quiz_flag_reverse': '“{country}”的旗帜是哪一面？',
        'quiz_period_reverse': '“{country}”的年代是哪一个？',
        'quiz_tag_reverse': '哪一个标签符合“{country}”？',
        'quiz_profile_reverse': '“{country}”的{label}是哪一个？',
        'quiz_detail_reverse': '“{country}”的{label}是哪一个？',
        'quiz_select_option': '选择这个选项',
        'ui_mobile': '手机界面',
        'ui_pc': '电脑界面',
        'switch_to_mobile': '切换到手机界面',
        'switch_to_pc': '切换到电脑界面',
        'page_unit': '页',
        'first_page': '第一页',
        'prev_page': '上一页',
        'next_page': '下一页',
        'last_page': '最后一页',
        'no_result': '未找到符合条件的国家或地区。',
        'username': '用户名',
        'password': '密码',
        'login': '登录',
        'register': '注册',
        'logout': '退出登录',
        'logged_in_as': '当前登录: {user}',
        'login_required': '登录后可以使用搜索、收藏和历史记录。',
        'auth_missing': '请输入用户名和密码。',
        'auth_invalid': '用户名或密码不正确。',
        'user_exists': '该用户名已被使用。',
        'user_created': '用户已创建。',
        'login_success': '已登录。',
        'logout_success': '已退出登录。',
        'compare': '比较',
        'compare_title': '国家比较',
        'compare_left': '比较国家 1',
        'compare_right': '比较国家 2',
        'today_country': '今日国家',
        'view_detail': '查看详情',
        'notes': '我的笔记',
        'save_note': '保存笔记',
        'note_saved': '笔记已保存。',
        'related_countries': '相关国家',
        'timeline': '年表',
        'timeline_title': '历史年表',
        'period_ancient': '古代',
        'period_medieval': '中世纪',
        'period_modern': '近现代',
        'period_other': '其他',
        'difficulty': '难度',
        'difficulty_easy': '初级',
        'difficulty_medium': '中级',
        'difficulty_hard': '高级',
        'difficulty_extreme': '超高级',
        'battle_direct': '国力对战',
        'battle_unlock_hint': '浏览所有现存国家，或在迷你测验中累计答对100题即可解锁。访客也可以解锁。',
        'battle_events_setting': '事件',
        'battle_events_on': '开启',
        'battle_events_off': '关闭',
        'battle_kick': '踢出',
        'battle_kicked_notice': '你已被踢出该房间。',
        'battle_kicked_log': '{player} 被房主移出房间。',
        'sengoku_mode': '战国模式',
        'normal_mode': '普通模式',
        'sengoku_mode_on': '已切换到战国模式。',
        'sengoku_mode_off': '已返回普通模式。',
        'sengoku_unlocked_notice': '战国模式已解锁。',
        'sengoku_unlock_hint': '解锁国力对战后，浏览所有国家，或在高级/综合/全问/混合设置下连续答对20题即可解锁。',
        'theme_dark': '深色',
        'theme_light': '浅色',
        'theme_toggle': '主题',
        'quiz_stats': '正确 {correct} / {answered}・连续 {streak}・最高 {best}',
        'account': '账户',
        'avatar': '头像',
        'avatar_current': '当前头像',
        'avatar_flag': '使用旗帜',
        'avatar_upload': '上传图片',
        'avatar_reset': '恢复默认头像',
        'avatar_saved': '头像已更新。',
        'avatar_upload_failed': '无法上传图片。',
        'avatar_file_hint': '支持 PNG、JPG、WEBP、GIF。',
        'map': '地图',
        'map_title': '地图视图',
        'map_note': '历史国家显示相关的现今地区。',
        'network': '关联网络',
        'network_title': '相关国家网络',
        'collections': '收藏集',
        'collection_name': '收藏集名称',
        'create_collection': '创建',
        'add_to_collection': '加入收藏集',
        'remove_from_collection': '移出收藏集',
        'collection_created': '已创建收藏集。',
        'collection_deleted': '已删除收藏集。',
        'progress': '学习进度',
        'viewed_count': '已浏览',
        'favorite_count': '收藏',
        'review_count': '复习列表',
        'quiz_history': '测验记录',
        'weakness': '薄弱点分析',
        'no_quiz_history': '还没有测验记录。',
        'no_collections': '还没有收藏集。',
        'view_on_map': '在地图中查看',
        'key_figures': '重要人物',
        'major_events': '主要事件',
        'fall_reason': '灭亡或转变原因',
        'successors': '继承或相关国家',
        'cultural_features': '文化特征',
    },
}

EXTRA_UI_FALLBACKS = {
    'ja': {
        'users': 'ユーザー',
        'users_title': 'ユーザー一覧',
        'public_users_notice': '公開されるのは学習状況だけです。パスワードとメモは表示されません。',
        'current_user_badge': '自分',
        'public_favorites': '公開お気に入り',
        'last_viewed': '最終閲覧',
        'best_streak': '最高連続正解',
        'public_collections': '公開コレクション',
        'public_collection_page': '公開コレクション',
        'open_collection_page': 'ページで見る',
        'collection_owner': '作成者',
        'back_to_users': 'ユーザー一覧へ戻る',
        'users_restore_browser': 'ブラウザ内のユーザーを再読み込み',
        'users_count': '表示ユーザー',
        'avatar_adjust': 'アイコンの表示調整',
        'avatar_adjust_hint': '丸いプレビュー上をドラッグして中心位置を動かせます。拡大率はスライダーで調整できます。',
        'avatar_zoom': '拡大率',
        'avatar_position_x': '中心位置（左右）',
        'avatar_position_y': '中心位置（上下）',
        'avatar_save_adjust': '表示位置を保存',
        'avatar_adjust_saved': '表示位置を保存しました。',
        'avatar_choose_file': '画像を選んでアップロード',
        'no_users': '表示できるユーザーはまだいません。',
        'account_settings': 'アカウント設定',
        'change_username': 'アカウント名を変更',
        'change_password': 'パスワードを変更',
        'delete_account': 'アカウントを削除',
        'new_username': '新しいアカウント名',
        'current_password': '現在のパスワード',
        'new_password': '新しいパスワード',
        'name_color': '名前の色',
        'name_color_presets': 'プリセット',
        'save_name_color': '名前の色を保存',
        'name_color_saved': '名前の色を更新しました。',
        'account_updated': 'アカウント情報を更新しました。',
        'password_changed': 'パスワードを変更しました。',
        'account_deleted': 'アカウントを削除しました。',
        'password_required': '現在のパスワードを入力してください。',
        'cannot_manage_guest': 'ゲストアカウントではこの操作はできません。',
        'delete_account_warning': '削除すると、このアカウントの学習データは戻せません。',
        'battle': '国力対戦',
        'battle_title': '国力対戦',
        'battle_locked': 'ロックされた機能',
        'unlock_condition_not_met': '解放条件が満たされていません。',
        'admin_search_cheat_applied': '管理者コードを適用しました。すべての公開国を閲覧済みにしました。',
        'battle_join': 'マッチング開始',
        'battle_waiting': '対戦相手を待っています。',
        'battle_cancel': '待機をやめる',
        'battle_refresh': '更新',
        'battle_hp': 'HP',
        'battle_hand': '手札',
        'battle_power': '国力',
        'battle_tag_bonus': 'タグ一致ボーナス',
        'battle_submit': 'この手で勝負',
        'battle_wait_opponent': '相手の選択を待っています。',
        'battle_defenseless': '手札切れのため、このターンは無防備です。',
        'battle_turn': 'ターン',
        'battle_log': '対戦ログ',
        'battle_win': '勝利',
        'battle_lose': '敗北',
        'battle_wins': '対戦勝利',
        'battle_unlocked_notice': '対戦モードが解禁されました。',
        'battle_matched': '対戦相手が見つかりました。',
        'battle_redraw': '手札を引き直す',
        'battle_redraw_used': 'このターンは引き直し済みです。',
        'battle_redraw_log': '{player} が手札を {count} 枚引き直しました。',
        'battle_steal_log': '{winner} が {loser} から {country} を奪いました。',
    },
    'en': {
        'users': 'Users',
        'users_title': 'Users',
        'public_users_notice': 'Only learning progress is shown. Passwords and personal notes are hidden.',
        'current_user_badge': 'You',
        'public_favorites': 'Public favorites',
        'last_viewed': 'Last viewed',
        'best_streak': 'Best streak',
        'public_collections': 'Public collections',
        'public_collection_page': 'Public collection',
        'open_collection_page': 'Open page',
        'collection_owner': 'Owner',
        'back_to_users': 'Back to users',
        'users_restore_browser': 'Reload browser users',
        'users_count': 'Users shown',
        'avatar_adjust': 'Icon framing',
        'avatar_adjust_hint': 'Drag on the round preview to move the center point. Use the slider for zoom.',
        'avatar_zoom': 'Zoom',
        'avatar_position_x': 'Center position X',
        'avatar_position_y': 'Center position Y',
        'avatar_save_adjust': 'Save framing',
        'avatar_adjust_saved': 'Icon framing saved.',
        'avatar_choose_file': 'Choose and upload image',
        'no_users': 'No users to show yet.',
        'account_settings': 'Account settings',
        'change_username': 'Change username',
        'change_password': 'Change password',
        'delete_account': 'Delete account',
        'new_username': 'New username',
        'current_password': 'Current password',
        'new_password': 'New password',
        'name_color': 'Name color',
        'name_color_presets': 'Presets',
        'save_name_color': 'Save name color',
        'name_color_saved': 'Name color updated.',
        'account_updated': 'Account updated.',
        'password_changed': 'Password changed.',
        'account_deleted': 'Account deleted.',
        'password_required': 'Enter your current password.',
        'cannot_manage_guest': 'This action is not available for guest accounts.',
        'delete_account_warning': 'Deleting this account permanently removes its learning data.',
        'battle': 'Power Battle',
        'battle_title': 'Power Battle',
        'battle_locked': 'Locked feature',
        'unlock_condition_not_met': 'Unlock condition is not met.',
        'admin_search_cheat_applied': 'Admin code applied. All public countries are now marked as viewed.',
        'battle_join': 'Start matching',
        'battle_waiting': 'Waiting for an opponent.',
        'battle_cancel': 'Leave queue',
        'battle_refresh': 'Refresh',
        'battle_hp': 'HP',
        'battle_hand': 'Hand',
        'battle_power': 'Power',
        'battle_power_hidden_hint': 'Power is hidden. You have seen every country, so of course you remember the data.',
        'battle_tag_bonus': 'Tag match bonus',
        'battle_submit': 'Play this hand',
        'battle_wait_opponent': 'Waiting for the opponent.',
        'battle_defenseless': 'Your hand is empty, so you are defenseless this turn.',
        'battle_turn': 'Turn',
        'battle_log': 'Battle log',
        'battle_win': 'Win',
        'battle_lose': 'Loss',
        'battle_wins': 'Battle wins',
        'battle_unlocked_notice': 'Power Battle is now unlocked.',
        'battle_matched': 'Opponent found.',
        'battle_redraw': 'Redraw hand',
        'battle_redraw_used': 'You already redrew this turn.',
        'battle_redraw_log': '{player} redrew {count} card(s).',
        'battle_steal_log': '{winner} stole {country} from {loser}.',
    },
    'zh': {
        'users': '用户',
        'users_title': '用户列表',
        'public_users_notice': '这里只显示学习进度。密码和个人笔记不会显示。',
        'current_user_badge': '自己',
        'public_favorites': '公开收藏',
        'last_viewed': '最后浏览',
        'best_streak': '最高连续答对',
        'public_collections': '公开收藏集',
        'public_collection_page': '公开收藏集',
        'open_collection_page': '打开页面',
        'collection_owner': '创建者',
        'back_to_users': '返回用户列表',
        'users_restore_browser': '重新读取浏览器用户',
        'users_count': '显示用户',
        'avatar_adjust': '头像显示调整',
        'avatar_adjust_hint': '在圆形预览上拖动即可移动中心位置。缩放请使用滑块。',
        'avatar_zoom': '缩放',
        'avatar_position_x': '中心位置（左右）',
        'avatar_position_y': '中心位置（上下）',
        'avatar_save_adjust': '保存显示位置',
        'avatar_adjust_saved': '显示位置已保存。',
        'avatar_choose_file': '选择并上传图片',
        'no_users': '还没有可显示的用户。',
        'account_settings': '账户设置',
        'change_username': '更改用户名',
        'change_password': '更改密码',
        'delete_account': '删除账户',
        'new_username': '新用户名',
        'current_password': '当前密码',
        'new_password': '新密码',
        'name_color': '名字颜色',
        'name_color_presets': '预设',
        'save_name_color': '保存名字颜色',
        'name_color_saved': '名字颜色已更新。',
        'account_updated': '账户信息已更新。',
        'password_changed': '密码已更改。',
        'account_deleted': '账户已删除。',
        'password_required': '请输入当前密码。',
        'cannot_manage_guest': '访客账户不能执行此操作。',
        'delete_account_warning': '删除后，该账户的学习数据无法恢复。',
        'battle': '国力对战',
        'battle_title': '国力对战',
        'battle_locked': '已锁定功能',
        'unlock_condition_not_met': '尚未满足解锁条件。',
        'admin_search_cheat_applied': '管理员代码已应用。所有公开国家已标记为已浏览。',
        'battle_join': '开始匹配',
        'battle_waiting': '正在等待对手。',
        'battle_cancel': '取消等待',
        'battle_refresh': '刷新',
        'battle_hp': 'HP',
        'battle_hand': '手牌',
        'battle_power': '国力',
        'battle_tag_bonus': '标签一致加成',
        'battle_submit': '用这手牌对战',
        'battle_wait_opponent': '等待对手选择。',
        'battle_defenseless': '手牌已空，本回合处于无防备状态。',
        'battle_turn': '回合',
        'battle_log': '对战记录',
        'battle_win': '胜利',
        'battle_lose': '失败',
        'battle_wins': '对战胜利',
        'battle_unlocked_notice': '国力对战已解锁。',
        'battle_matched': '已找到对手。',
        'battle_redraw': '重抽手牌',
        'battle_redraw_used': '本回合已经重抽过。',
        'battle_redraw_log': '{player} 重抽了 {count} 张牌。',
        'battle_steal_log': '{winner} 从 {loser} 手中夺取了 {country}。',
    },
}

for lang_code, labels in EXTRA_UI_FALLBACKS.items():
    UI_FALLBACKS.setdefault(lang_code, {}).update(labels)

UI_FALLBACKS.setdefault('ja', {}).update({
    'favorites_except': 'お気に入り以外',
    'favorites_all': 'お気に入り条件なし',
    'battle_power_hidden_hint': '選択中の国力は非表示です。見てきた国データを思い出して勝負しましょう。',
    'battle_mode_duel': '1対1',
    'battle_mode_free_for_all': '乱戦',
    'battle_mode_team': 'チーム戦',
    'battle_bot': 'BOTと戦う',
    'battle_spectate': '観戦する',
    'battle_spectating': '観戦中',
    'battle_leave_spectate': '観戦をやめる',
    'battle_active_rooms': '観戦できる対戦',
    'battle_no_rooms': '観戦できる対戦はありません。',
    'battle_chat': 'チャット',
    'battle_chat_placeholder': 'メッセージ',
    'battle_send': '送信',
    'battle_bonus': '一致ボーナス',
    'battle_room_players': '参加者',
    'battle_thinking_time': '思考時間',
    'battle_room_thinking_time': 'この部屋の思考時間',
    'battle_time_unlimited': '無制限',
    'battle_world_war_setting': '第三次世界大戦',
    'battle_room_world_war_setting': '第三次世界大戦開始',
    'battle_world_war_never': 'なし',
    'battle_command': '指揮力',
    'battle_command_not_enough': '指揮力が足りません。出すカードを減らすか、次のターンまで温存してください。',
    'battle_redraw_command_cost': '引き直しは指揮力を{cost}消費します。',
    'battle_redraw_command_not_enough': '引き直しに必要な指揮力が足りません。',
    'battle_team': 'チーム',
    'battle_auto_notice': '画面は自動で更新されます。',
    'battle_damage_each': '各',
    'battle_defense': '防御',
    'battle_select_card_required': 'カードを1枚以上選んでください。',
    'tag_group': 'タグ分類',
    'battle_attack_target': '攻撃対象',
    'battle_select_target_required': '攻撃対象を選んでください。',
    'battle_team_chat': 'チームチャット',
    'battle_team_chat_placeholder': 'チームだけに送るメッセージ',
    'battle_bot_replacement_log': '{player}の代わりに{bot}が参戦します。',
    'battle_surrender': '降参',
    'battle_surrender_log': '{player}が降参しました。',
    'battle_timeout_surrender_log': '{player}が長考により強制降参になりました。',
    'battle_time_left': '残り{seconds}秒',
    'battle_eliminated': '降参済みです。残りの対戦を観戦できます。',
})
UI_FALLBACKS.setdefault('en', {}).update({
    'favorites_except': 'Not favorites',
    'favorites_all': 'No favorite filter',
    'battle_power_hidden_hint': 'Power is hidden while choosing. Use what you remember from the country data.',
    'battle_mode_duel': '1v1',
    'battle_mode_free_for_all': 'Free-for-all',
    'battle_mode_team': 'Team battle',
    'battle_bot': 'Fight BOT',
    'battle_spectate': 'Spectate',
    'battle_spectating': 'Spectating',
    'battle_leave_spectate': 'Leave spectate',
    'battle_active_rooms': 'Battles to watch',
    'battle_no_rooms': 'No battles are available to watch.',
    'battle_chat': 'Chat',
    'battle_chat_placeholder': 'Message',
    'battle_send': 'Send',
    'battle_bonus': 'Match bonus',
    'battle_room_players': 'Players',
    'battle_thinking_time': 'Thinking time',
    'battle_room_thinking_time': 'Room thinking time',
    'battle_time_unlimited': 'Unlimited',
    'battle_world_war_setting': 'World War III',
    'battle_room_world_war_setting': 'World War III starts',
    'battle_world_war_never': 'None',
    'battle_command': 'Command',
    'battle_command_not_enough': 'Not enough command. Play fewer cards or save strength for the next turn.',
    'battle_redraw_command_cost': 'Redraw costs {cost} command.',
    'battle_redraw_command_not_enough': 'Not enough command to redraw.',
    'battle_team': 'Team',
    'battle_auto_notice': 'This screen updates automatically.',
    'battle_damage_each': 'each',
    'battle_defense': 'defense',
    'battle_select_card_required': 'Choose at least one card.',
    'tag_group': 'Tag group',
    'battle_attack_target': 'Target',
    'battle_select_target_required': 'Choose an attack target.',
    'battle_team_chat': 'Team chat',
    'battle_team_chat_placeholder': 'Message to your team',
    'battle_bot_replacement_log': '{bot} joins in place of {player}.',
    'battle_surrender': 'Surrender',
    'battle_surrender_log': '{player} surrendered.',
    'battle_timeout_surrender_log': '{player} was forced to surrender after thinking too long.',
    'battle_time_left': '{seconds}s left',
    'battle_eliminated': 'You have surrendered. You can keep watching the battle.',
})
UI_FALLBACKS.setdefault('zh', {}).update({
    'favorites_except': '非收藏',
    'favorites_all': '不筛选收藏',
    'battle_power_hidden_hint': '选牌时国力会隐藏。请回忆国家数据来判断。',
    'battle_mode_duel': '1对1',
    'battle_mode_free_for_all': '混战',
    'battle_mode_team': '团队战',
    'battle_bot': '与 BOT 对战',
    'battle_spectate': '观战',
    'battle_spectating': '观战中',
    'battle_leave_spectate': '停止观战',
    'battle_active_rooms': '可观战对战',
    'battle_no_rooms': '当前没有可观战对战。',
    'battle_chat': '聊天',
    'battle_chat_placeholder': '消息',
    'battle_send': '发送',
    'battle_bonus': '一致加成',
    'battle_room_players': '参加者',
    'battle_thinking_time': '思考时间',
    'battle_room_thinking_time': '本房间思考时间',
    'battle_time_unlimited': '无限制',
    'battle_world_war_setting': '第三次世界大战',
    'battle_room_world_war_setting': '第三次世界大战开始',
    'battle_world_war_never': '无',
    'battle_command': '指挥力',
    'battle_command_not_enough': '指挥力不足。请减少出牌，或留到下一回合。',
    'battle_redraw_command_cost': '重抽会消耗{cost}点指挥力。',
    'battle_redraw_command_not_enough': '指挥力不足，无法重抽。',
    'battle_team': '队伍',
    'battle_auto_notice': '画面会自动更新。',
    'battle_damage_each': '各',
    'battle_defense': '防御',
    'battle_select_card_required': '请至少选择一张牌。',
    'tag_group': '标签分类',
    'battle_attack_target': '攻击目标',
    'battle_select_target_required': '请选择攻击目标。',
    'battle_team_chat': '团队聊天',
    'battle_team_chat_placeholder': '只发给队友的消息',
    'battle_bot_replacement_log': '{bot}代替{player}参战。',
    'battle_surrender': '投降',
    'battle_surrender_log': '{player}已投降。',
    'battle_timeout_surrender_log': '{player}思考过久，被强制投降。',
    'battle_time_left': '剩余{seconds}秒',
    'battle_eliminated': '你已投降，可以继续观战。',
})

UI_FALLBACKS.setdefault('ja', {}).update({
    'battle_resume': '試合に復帰',
    'battle_resume_log': '{player}が{bot}から手札を引き継いで復帰しました。',
    'battle_world_war_title': '第三次世界大戦',
    'battle_world_war_notice': '世界規模の危機に突入しました。ダメージが5倍になり、危険カードが手札に混ざります。',
    'battle_world_war_log': '第三次世界大戦が始まりました。以後、ダメージが5倍になります。',
    'battle_revolution_title': '革命発生中',
    'battle_revolution_notice': '革命により国力の強弱が逆転しています。普段弱い国が切り札になるかもしれません。',
    'battle_revolution_start_log': '革命が発生しました。{turns}ターンの間、カードの強さが逆転します。',
    'battle_revolution_end_log': '革命が終息しました。カードの強さが通常に戻ります。',
    'battle_flag_only_title': '国旗識別戦',
    'battle_flag_only_notice': '国名が伏せられ、国旗だけを頼りにカードを選ぶ状態です。',
    'battle_flag_only_start_log': '国旗識別戦が始まりました。{turns}ターンの間、国名が伏せられます。',
    'battle_flag_only_end_log': '国旗識別戦が終了しました。国名が再表示されます。',
    'battle_vatican_title': 'バチカン市国大量発生',
    'battle_vatican_notice': '配られるカードにバチカン市国が混ざりやすくなっています。',
    'battle_vatican_start_log': 'バチカン市国が大量発生しました。{turns}ターンの間、配布カードに混ざりやすくなります。',
    'battle_vatican_end_log': 'バチカン市国大量発生が収まりました。',
    'battle_hidden_card_name': '???',
    'battle_last_turn': '直前ターンの動き',
    'battle_played_visual': '出したカード',
    'battle_defense_visual': '防御に残したカード',
    'battle_damage_visual': 'ダメージ',
    'battle_steal_visual': '奪われたカード',
    'battle_self_damage_visual': '危険カード',
    'battle_counter_visual': '防御カウンター',
    'battle_no_visual': 'まだ表示できるターン結果はありません。',
    'battle_special_card': '危険カード',
    'battle_special_damage': 'ターン終了時に自傷ダメージ',
    'battle_special_supply_collapse': '補給崩壊',
    'battle_special_frontline_disaster': '戦線崩壊',
    'battle_special_fallout_crisis': '核汚染',
    'battle_special_scorched_earth': '焦土作戦',
    'battle_special_relief_convoy': '救援船団',
    'battle_self_damage_log': '{player}の{card}が暴発し、{damage}ダメージを受けました。',
    'battle_heal_log': '{player}の{card}により、{heal}回復しました。',
    'battle_destroy_log': '{player}の{card}が{country}を巻き込み、手札から失われました。',
    'battle_counter_log': '{defender}の防御が上回り、{attacker}へ{damage}のカウンターダメージ。',
})
UI_FALLBACKS.setdefault('en', {}).update({
    'battle_resume': 'Rejoin Battle',
    'battle_resume_log': '{player} returned and took over {bot}’s hand.',
    'battle_world_war_title': 'World War III',
    'battle_world_war_notice': 'The battle has entered a world crisis. Damage is multiplied by 5 and dangerous cards can appear in hands.',
    'battle_world_war_log': 'World War III has begun. Damage is multiplied by 5 from now on.',
    'battle_revolution_title': 'Revolution Active',
    'battle_revolution_notice': 'Revolution reverses card strength. Usually weak countries may become decisive.',
    'battle_revolution_start_log': 'A revolution began. Card strength is reversed for {turns} turns.',
    'battle_revolution_end_log': 'The revolution ended. Card strength returned to normal.',
    'battle_flag_only_title': 'Flag Recognition',
    'battle_flag_only_notice': 'Country names are hidden. Choose cards by flags alone.',
    'battle_flag_only_start_log': 'Flag Recognition began. Country names are hidden for {turns} turns.',
    'battle_flag_only_end_log': 'Flag Recognition ended. Country names are visible again.',
    'battle_vatican_title': 'Vatican City Outbreak',
    'battle_vatican_notice': 'Vatican City is much more likely to appear in dealt cards.',
    'battle_vatican_start_log': 'Vatican City outbreak began. It is more likely to appear for {turns} turns.',
    'battle_vatican_end_log': 'The Vatican City outbreak ended.',
    'battle_hidden_card_name': '???',
    'battle_last_turn': 'Last Turn',
    'battle_played_visual': 'Played Cards',
    'battle_defense_visual': 'Cards Kept for Defense',
    'battle_damage_visual': 'Damage',
    'battle_steal_visual': 'Stolen Card',
    'battle_self_damage_visual': 'Danger Cards',
    'battle_counter_visual': 'Defense Counter',
    'battle_no_visual': 'No turn result to show yet.',
    'battle_special_card': 'Danger Card',
    'battle_special_damage': 'Self-damage at turn end',
    'battle_special_supply_collapse': 'Supply Collapse',
    'battle_special_frontline_disaster': 'Frontline Disaster',
    'battle_special_fallout_crisis': 'Fallout Crisis',
    'battle_special_scorched_earth': 'Scorched Earth',
    'battle_special_relief_convoy': 'Relief Convoy',
    'battle_self_damage_log': '{player} suffered {damage} damage from {card}.',
    'battle_heal_log': '{player} recovered {heal} HP from {card}.',
    'battle_destroy_log': "{player}'s {card} dragged {country} out of the hand.",
    'battle_counter_log': '{defender} countered {attacker} for {damage} damage with superior defense.',
})
UI_FALLBACKS.setdefault('zh', {}).update({
    'battle_resume': '返回战斗',
    'battle_resume_log': '{player}接管{bot}的手牌并返回战斗。',
    'battle_world_war_title': '第三次世界大战',
    'battle_world_war_notice': '战斗进入世界危机。伤害变为5倍，危险牌会混入手牌。',
    'battle_world_war_log': '第三次世界大战开始了。之后伤害变为5倍。',
    'battle_revolution_title': '革命发生中',
    'battle_revolution_notice': '革命会反转卡牌强弱。平时弱小的国家也可能成为关键。',
    'battle_revolution_start_log': '革命爆发。{turns}回合内卡牌强弱反转。',
    'battle_revolution_end_log': '革命结束。卡牌强弱恢复正常。',
    'battle_flag_only_title': '旗帜识别战',
    'battle_flag_only_notice': '国名会被隐藏，只能依靠旗帜判断卡牌。',
    'battle_flag_only_start_log': '旗帜识别战开始。{turns}回合内国名会被隐藏。',
    'battle_flag_only_end_log': '旗帜识别战结束。国名重新显示。',
    'battle_vatican_title': '梵蒂冈大量出现',
    'battle_vatican_notice': '发牌时更容易出现梵蒂冈。',
    'battle_vatican_start_log': '梵蒂冈大量出现。{turns}回合内更容易被发到手牌。',
    'battle_vatican_end_log': '梵蒂冈大量出现结束。',
    'battle_hidden_card_name': '???',
    'battle_last_turn': '上一回合',
    'battle_played_visual': '打出的牌',
    'battle_defense_visual': '留下防御的牌',
    'battle_damage_visual': '伤害',
    'battle_steal_visual': '被夺走的牌',
    'battle_self_damage_visual': '危险牌',
    'battle_counter_visual': '防御反击',
    'battle_no_visual': '还没有可显示的回合结果。',
    'battle_special_card': '危险牌',
    'battle_special_damage': '回合结束时自伤',
    'battle_special_supply_collapse': '补给崩溃',
    'battle_special_frontline_disaster': '战线崩溃',
    'battle_special_fallout_crisis': '核污染',
    'battle_special_scorched_earth': '焦土作战',
    'battle_special_relief_convoy': '救援船队',
    'battle_self_damage_log': '{player}的{card}爆发，受到{damage}伤害。',
    'battle_heal_log': '{player}因{card}恢复了{heal}。',
    'battle_destroy_log': '{player}的{card}卷入了{country}，该牌从手牌中消失。',
    'battle_counter_log': '{defender}的防御超过攻击，对{attacker}造成{damage}反击伤害。',
})

UI_FALLBACKS.setdefault('ja', {}).update({
    'rankings': 'ランキング',
    'rankings_title': 'ランキング',
    'quiz_ranking': 'クイズ正解数ランキング',
    'battle_win_ranking': '勝利数ランキング',
    'ranking_locked': 'ロックされたランキング',
    'ranking_locked_hint': '勝利数ランキングは、全国家を閲覧したユーザーだけが見られます。',
    'rank_number': '順位',
    'correct_count': '正解数',
    'answered_count': '解答数',
    'win_count': '勝利数',
    'friends': 'フレンド',
    'friends_title': 'フレンド・チャット',
    'friend_requests': 'フレンド申請',
    'friend_request_send': 'フレンド申請',
    'friend_request_sent': '申請中',
    'friend_request_received': '申請が届いています',
    'friend_accept': '承認',
    'friend_reject': '拒否',
    'friend_remove': 'フレンド解除',
    'friend_chat': '個人チャット',
    'friend_request_sent_notice': 'フレンド申請を送りました。',
    'friend_request_accepted_notice': 'フレンドになりました。',
    'friend_request_rejected_notice': 'フレンド申請を削除しました。',
    'no_friends': 'フレンドはまだいません。',
    'no_friend_requests': '届いている申請はありません。',
    'direct_chat': '個人チャット',
    'group_chat': 'グループチャット',
    'create_group_chat': 'グループを作成',
    'group_name': 'グループ名',
    'group_members': 'メンバー',
    'group_members_hint': 'フレンドの名前をカンマ区切りで入力します。',
    'chat_message': 'メッセージ',
    'chat_send': '送信',
    'chat_empty': 'まだメッセージはありません。',
    'chat_select': 'チャットを選択してください。',
    'chat_created': 'チャットを作成しました。',
    'chat_not_allowed': 'フレンド同士でのみチャットできます。',
    'friends_count': 'フレンド数',
    'ranking_overall': '総合',
    'ranking_category_title': '{category}ランキング',
    'no_ranking_data': 'ランキングに表示できるデータはまだありません。',
    'friend_request_incoming_notice': '{user}さんからフレンド申請が届きました。',
    'new_direct_chat_notice': '{name}とのチャットが始まりました。',
    'new_group_chat_notice': 'グループチャット「{name}」に追加されました。',
    'new_chat_message_notice': '{name}に新しいメッセージがあります。',
    'open_notification_target': '開く',
    'dismiss_notification': '閉じる',
})
UI_FALLBACKS.setdefault('en', {}).update({
    'rankings': 'Rankings',
    'rankings_title': 'Rankings',
    'quiz_ranking': 'Quiz Correct Ranking',
    'battle_win_ranking': 'Battle Win Ranking',
    'ranking_locked': 'Locked ranking',
    'ranking_locked_hint': 'Only users who have viewed every country can see the battle win ranking.',
    'rank_number': 'Rank',
    'correct_count': 'Correct',
    'answered_count': 'Answered',
    'win_count': 'Wins',
    'friends': 'Friends',
    'friends_title': 'Friends & Chat',
    'friend_requests': 'Friend Requests',
    'friend_request_send': 'Send request',
    'friend_request_sent': 'Request sent',
    'friend_request_received': 'Request received',
    'friend_accept': 'Accept',
    'friend_reject': 'Decline',
    'friend_remove': 'Remove friend',
    'friend_chat': 'Direct chat',
    'friend_request_sent_notice': 'Friend request sent.',
    'friend_request_accepted_notice': 'You are now friends.',
    'friend_request_rejected_notice': 'Friend request removed.',
    'no_friends': 'No friends yet.',
    'no_friend_requests': 'No incoming requests.',
    'direct_chat': 'Direct chat',
    'group_chat': 'Group chat',
    'create_group_chat': 'Create group',
    'group_name': 'Group name',
    'group_members': 'Members',
    'group_members_hint': 'Enter friend names separated by commas.',
    'chat_message': 'Message',
    'chat_send': 'Send',
    'chat_empty': 'No messages yet.',
    'chat_select': 'Select a chat.',
    'chat_created': 'Chat created.',
    'chat_not_allowed': 'Chat is available between friends only.',
    'friends_count': 'Friends',
    'ranking_overall': 'Overall',
    'ranking_category_title': '{category} Ranking',
    'no_ranking_data': 'No ranking data yet.',
    'friend_request_incoming_notice': 'Friend request from {user}.',
    'new_direct_chat_notice': 'A chat with {name} has started.',
    'new_group_chat_notice': 'You were added to “{name}”.',
    'new_chat_message_notice': 'New message in {name}.',
    'open_notification_target': 'Open',
    'dismiss_notification': 'Close',
})
UI_FALLBACKS.setdefault('zh', {}).update({
    'rankings': '排行榜',
    'rankings_title': '排行榜',
    'quiz_ranking': '测验正确数排行',
    'battle_win_ranking': '胜利数排行',
    'ranking_locked': '已锁定排行',
    'ranking_locked_hint': '胜利数排行仅限已浏览全部国家的用户查看。',
    'rank_number': '排名',
    'correct_count': '正确数',
    'answered_count': '回答数',
    'win_count': '胜利数',
    'friends': '好友',
    'friends_title': '好友与聊天',
    'friend_requests': '好友申请',
    'friend_request_send': '发送申请',
    'friend_request_sent': '已申请',
    'friend_request_received': '收到申请',
    'friend_accept': '同意',
    'friend_reject': '拒绝',
    'friend_remove': '解除好友',
    'friend_chat': '私聊',
    'friend_request_sent_notice': '已发送好友申请。',
    'friend_request_accepted_notice': '已成为好友。',
    'friend_request_rejected_notice': '已删除好友申请。',
    'no_friends': '还没有好友。',
    'no_friend_requests': '没有收到申请。',
    'direct_chat': '私聊',
    'group_chat': '群聊',
    'create_group_chat': '创建群聊',
    'group_name': '群名',
    'group_members': '成员',
    'group_members_hint': '请输入好友名，用逗号分隔。',
    'chat_message': '消息',
    'chat_send': '发送',
    'chat_empty': '还没有消息。',
    'chat_select': '请选择聊天。',
    'chat_created': '聊天已创建。',
    'chat_not_allowed': '只有好友之间可以聊天。',
    'friends_count': '好友数',
    'ranking_overall': '综合',
    'ranking_category_title': '{category}排行榜',
    'no_ranking_data': '还没有可显示的排行数据。',
    'friend_request_incoming_notice': '收到来自 {user} 的好友申请。',
    'new_direct_chat_notice': '已开始与 {name} 的聊天。',
    'new_group_chat_notice': '你已加入群聊“{name}”。',
    'new_chat_message_notice': '{name} 有新消息。',
    'open_notification_target': '打开',
    'dismiss_notification': '关闭',
})

UI_FALLBACKS.setdefault('ja', {}).update({
    'notifications': '\u901a\u77e5',
    'notification_empty': '\u901a\u77e5\u306f\u307e\u3060\u3042\u308a\u307e\u305b\u3093\u3002',
    'unread_notifications': '\u672a\u8aad: {count}',
    'mark_all_read': '\u3059\u3079\u3066\u65e2\u8aad',
    'unread': '\u672a\u8aad',
})
UI_FALLBACKS.setdefault('en', {}).update({
    'notifications': 'Notifications',
    'notification_empty': 'No notifications yet.',
    'unread_notifications': 'Unread: {count}',
    'mark_all_read': 'Mark all read',
    'unread': 'Unread',
})
UI_FALLBACKS.setdefault('zh', {}).update({
    'notifications': '\u901a\u77e5',
    'notification_empty': '\u8fd8\u6ca1\u6709\u901a\u77e5\u3002',
    'unread_notifications': '\u672a\u8bfb: {count}',
    'mark_all_read': '\u5168\u90e8\u6807\u4e3a\u5df2\u8bfb',
    'unread': '\u672a\u8bfb',
})

UI_FALLBACKS.setdefault('ja', {}).update({
    'battle_start_with_bots': 'BOTを入れて開始',
    'battle_team_count': 'チーム数',
    'battle_team_choice': '参加チーム',
    'battle_team_randomize': 'チームをランダム分け',
    'battle_team_randomized_log': '{host}がチームをランダムに振り分けました。',
    'battle_host_only': 'ホストだけが操作できます。',
    'battle_revolution_start_log': '革命が発生しました。カードの強さが逆転します。',
    'battle_flag_only_start_log': '国旗識別戦が始まりました。国名が伏せられます。',
    'battle_vatican_start_log': 'バチカン市国が大量発生しました。配布カードに混ざりやすくなります。',
    'battle_replace_title': '手札入れ替わり',
    'battle_replace_notice': '毎ターン、誰かの手札が1枚ランダムに別の国へ置き換わります。',
    'battle_replace_start_log': '手札入れ替わりが始まりました。',
    'battle_replace_log': '{player}の手札が1枚入れ替わりました: {old} -> {new}',
    'battle_bomb_title': '爆弾カード',
    'battle_bomb_notice': '爆弾は現在{player}の手札にあります。出すと相手へ移り、持ったまま終わると大ダメージです。',
    'battle_bomb_start_log': '{player}の手札に爆弾カードが入りました。',
    'battle_bomb_pass_log': '{player}が爆弾カードを{target}へ渡しました。',
    'battle_bomb_explode_log': '{player}の手札で爆弾カードが爆発し、{damage}ダメージを受けました。',
    'battle_bomb_card_hint': '場に出すと相手の手札へ移ります。持ったままイベントが終わると危険です。',
    'battle_bomb_visual': '爆弾カードの移動',
    'battle_damage_surge_title': '超火力化',
    'battle_damage_surge_notice': 'この間はダメージが大きく跳ね上がります。防御も反撃も重要です。',
    'battle_damage_surge_start_log': '超火力化が始まりました。ダメージが大きく跳ね上がります。',
    'battle_special_hot_potato_bomb': '爆弾カード',
    'battle_action_details': '処理の内訳',
    'battle_base_attack': '基礎攻撃力',
    'battle_opponent_attack': '相手攻撃力',
    'battle_power_gap': '攻撃差',
    'battle_attack_bonus_value': '攻撃ボーナス増加分',
    'battle_after_bonus': 'ボーナス後威力',
    'battle_defense_base': '基礎防御力',
    'battle_defense_bonus_value': '防御ボーナス増加分',
    'battle_final_defense': '最終防御力',
    'battle_after_defense': '防御後威力',
    'battle_turn_pressure': '長期戦補正',
    'battle_world_war_multiplier_label': '世界大戦倍率',
    'battle_event_multiplier_label': 'イベント倍率',
    'battle_final_damage': '最終ダメージ',
    'battle_final_counter': '最終反撃',
    'battle_no_damage': 'ダメージなし',
    'battle_hand_count': '手札',
    'battle_cards_before': '開始時手札',
    'battle_team_split_penalty': '分散ペナルティ',
    'battle_raw_team_attack': '分散前チーム攻撃',
})
UI_FALLBACKS.setdefault('en', {}).update({
    'battle_start_with_bots': 'Start with BOTs',
    'battle_team_count': 'Teams',
    'battle_team_choice': 'Your team',
    'battle_team_randomize': 'Randomize teams',
    'battle_team_randomized_log': '{host} randomized the teams.',
    'battle_host_only': 'Only the host can do that.',
    'battle_revolution_start_log': 'A revolution began. Card strength is reversed.',
    'battle_flag_only_start_log': 'Flag Recognition began. Country names are hidden.',
    'battle_vatican_start_log': 'Vatican City outbreak began. It is more likely to appear in dealt cards.',
    'battle_replace_title': 'Hand Shuffle',
    'battle_replace_notice': 'Each turn, one random card in someone\'s hand is replaced.',
    'battle_replace_start_log': 'Hand Shuffle began.',
    'battle_replace_log': "{player}'s hand changed: {old} -> {new}",
    'battle_bomb_title': 'Bomb Card',
    'battle_bomb_notice': 'The bomb is in {player}\'s hand. Play it to pass it on. Hold it too long and it explodes.',
    'battle_bomb_start_log': 'A bomb card entered {player}\'s hand.',
    'battle_bomb_pass_log': '{player} passed the bomb card to {target}.',
    'battle_bomb_explode_log': 'The bomb exploded in {player}\'s hand for {damage} damage.',
    'battle_bomb_card_hint': 'Play it to pass it to an opponent. Holding it when the event ends is dangerous.',
    'battle_bomb_visual': 'Bomb Movement',
    'battle_damage_surge_title': 'Overdrive Damage',
    'battle_damage_surge_notice': 'Damage is massively increased. Defense counters matter too.',
    'battle_damage_surge_start_log': 'Overdrive Damage began. Damage is massively increased.',
    'battle_special_hot_potato_bomb': 'Bomb Card',
    'battle_action_details': 'Breakdown',
    'battle_base_attack': 'Base attack',
    'battle_opponent_attack': 'Opponent attack',
    'battle_power_gap': 'Power gap',
    'battle_attack_bonus_value': 'Attack bonus gain',
    'battle_after_bonus': 'After bonus',
    'battle_defense_base': 'Base defense',
    'battle_defense_bonus_value': 'Defense bonus gain',
    'battle_final_defense': 'Final defense',
    'battle_after_defense': 'After defense',
    'battle_turn_pressure': 'Turn pressure',
    'battle_world_war_multiplier_label': 'World war',
    'battle_event_multiplier_label': 'Event',
    'battle_final_damage': 'Final damage',
    'battle_final_counter': 'Final counter',
    'battle_no_damage': 'No damage',
    'battle_hand_count': 'Cards',
    'battle_cards_before': 'Starting cards',
    'battle_team_split_penalty': 'Split penalty',
    'battle_raw_team_attack': 'Team attack before split',
})
UI_FALLBACKS.setdefault('zh', {}).update({
    'battle_start_with_bots': '加入BOT开始',
    'battle_team_count': '队伍数',
    'battle_team_choice': '参加队伍',
    'battle_team_randomize': '随机分队',
    'battle_team_randomized_log': '{host}随机分配了队伍。',
    'battle_host_only': '只有房主可以操作。',
    'battle_revolution_start_log': '革命发生了。卡牌强弱反转。',
    'battle_flag_only_start_log': '国旗识别战开始。国名会被隐藏。',
    'battle_vatican_start_log': '梵蒂冈大量出现。发牌时更容易出现。',
    'battle_replace_title': '手牌替换',
    'battle_replace_notice': '每回合会随机替换某人手牌中的一张牌。',
    'battle_replace_start_log': '手牌替换开始了。',
    'battle_replace_log': '{player}的一张手牌被替换: {old} -> {new}',
    'battle_bomb_title': '炸弹牌',
    'battle_bomb_notice': '炸弹现在在{player}手中。打出会传给对手，留下太久会爆炸。',
    'battle_bomb_start_log': '炸弹牌进入了{player}的手牌。',
    'battle_bomb_pass_log': '{player}把炸弹牌传给了{target}。',
    'battle_bomb_explode_log': '炸弹在{player}手中爆炸，造成{damage}伤害。',
    'battle_bomb_card_hint': '打出可传给对手。事件结束时还拿着会很危险。',
    'battle_bomb_visual': '炸弹移动',
    'battle_damage_surge_title': '超火力',
    'battle_damage_surge_notice': '伤害会大幅提高，防御反击也很重要。',
    'battle_damage_surge_start_log': '超火力开始。伤害会大幅提高。',
    'battle_special_hot_potato_bomb': '炸弹牌',
    'battle_action_details': '处理明细',
    'battle_base_attack': '基础攻击力',
    'battle_opponent_attack': '对手攻击力',
    'battle_power_gap': '攻击差',
    'battle_attack_bonus_value': '攻击加成增加',
    'battle_after_bonus': '加成后威力',
    'battle_defense_base': '基础防御力',
    'battle_defense_bonus_value': '防御加成增加',
    'battle_final_defense': '最终防御力',
    'battle_after_defense': '防御后威力',
    'battle_turn_pressure': '长期战补正',
    'battle_world_war_multiplier_label': '世界大战倍率',
    'battle_event_multiplier_label': '事件倍率',
    'battle_final_damage': '最终伤害',
    'battle_final_counter': '最终反击',
    'battle_no_damage': '没有伤害',
    'battle_hand_count': '手牌',
    'battle_cards_before': '开始时手牌',
    'battle_team_split_penalty': '分散惩罚',
    'battle_raw_team_attack': '分散前队伍攻击',
})

UI_FALLBACKS.setdefault('ja', {}).update({
    'battle_ceasefire_title': '停戦交渉',
    'battle_ceasefire_notice': '交渉の空気が広がり、ダメージが大きく抑えられます。',
    'battle_ceasefire_start_log': '停戦交渉が始まりました。ダメージが抑えられます。',
    'battle_command_surge_title': '司令部高揚',
    'battle_command_surge_notice': '指揮系統が活性化し、ターン終了時の指揮力回復が増えます。',
    'battle_command_surge_start_log': '司令部高揚が始まりました。指揮力が回復しやすくなります。',
    'battle_supply_drop_title': '補給投下',
    'battle_supply_drop_notice': '手札が少ないプレイヤーに、ターン終了時に小さな補給が届きます。',
    'battle_supply_drop_start_log': '補給投下が始まりました。手札が少ないと補給が届きます。',
    'battle_blockade_title': '海上封鎖',
    'battle_blockade_notice': '補給路が止まり、手札の引き直しができません。',
    'battle_blockade_start_log': '海上封鎖が始まりました。引き直しができなくなります。',
    'battle_blockade_redraw_blocked': '海上封鎖中は引き直しできません。',
})

UI_FALLBACKS.setdefault('en', {}).update({
    'battle_ceasefire_title': 'Ceasefire Talks',
    'battle_ceasefire_notice': 'Damage is greatly reduced while negotiations are in the air.',
    'battle_ceasefire_start_log': 'Ceasefire Talks began. Damage is reduced.',
    'battle_command_surge_title': 'Command Surge',
    'battle_command_surge_notice': 'Command recovery increases at the end of each turn.',
    'battle_command_surge_start_log': 'Command Surge began. Command recovers more easily.',
    'battle_supply_drop_title': 'Supply Drop',
    'battle_supply_drop_notice': 'Players with few cards receive a small resupply at turn end.',
    'battle_supply_drop_start_log': 'Supply Drop began. Low hands will receive support.',
    'battle_blockade_title': 'Naval Blockade',
    'battle_blockade_notice': 'Redraw is disabled while supply routes are blocked.',
    'battle_blockade_start_log': 'Naval Blockade began. Redraw is disabled.',
    'battle_blockade_redraw_blocked': 'Redraw is disabled during the blockade.',
})

UI_FALLBACKS.setdefault('zh', {}).update({
    'battle_ceasefire_title': '停火谈判',
    'battle_ceasefire_notice': '谈判气氛扩散，伤害会大幅降低。',
    'battle_ceasefire_start_log': '停火谈判开始。伤害会降低。',
    'battle_command_surge_title': '指挥高涨',
    'battle_command_surge_notice': '指挥系统活跃，回合结束时指挥力恢复增加。',
    'battle_command_surge_start_log': '指挥高涨开始。指挥力更容易恢复。',
    'battle_supply_drop_title': '补给投放',
    'battle_supply_drop_notice': '手牌少的玩家会在回合结束时获得少量补给。',
    'battle_supply_drop_start_log': '补给投放开始。手牌少时会获得支援。',
    'battle_blockade_title': '海上封锁',
    'battle_blockade_notice': '补给线被切断，无法重抽手牌。',
    'battle_blockade_start_log': '海上封锁开始。无法重抽手牌。',
    'battle_blockade_redraw_blocked': '海上封锁期间无法重抽。',
})

UI_FALLBACKS.setdefault('ja', {}).update({
    'battle_replace_title': '手札再分配',
    'battle_replace_notice': '全員の手札をまとめてシャッフルし、元の枚数どおりに配り直します。',
    'battle_replace_start_log': '手札再分配が始まりました。',
    'battle_replace_redistribute_log': '{players}人の手札{count}枚をまとめて再分配しました。',
})

UI_FALLBACKS.setdefault('en', {}).update({
    'battle_replace_title': 'Hand Redistribution',
    'battle_replace_notice': 'All hands are pooled, shuffled, and redealt with the same card counts.',
    'battle_replace_start_log': 'Hand Redistribution began.',
    'battle_replace_redistribute_log': 'Redistributed {count} cards across {players} players.',
})

UI_FALLBACKS.setdefault('zh', {}).update({
    'battle_replace_title': '手牌再分配',
    'battle_replace_notice': '所有人的手牌会合并洗牌，并按原本的张数重新分配。',
    'battle_replace_start_log': '手牌再分配开始。',
    'battle_replace_redistribute_log': '已将{players}名玩家的{count}张手牌重新分配。',
})

UI_FALLBACKS.setdefault('ja', {}).update({
    'battle_lytton_title': 'リットン調査団',
    'battle_lytton_notice': '調査団の報告により、相手の現在の手札が見える状態です。',
    'battle_lytton_start_log': 'リットン調査団が到着しました。相手の手札が公開されます。',
    'battle_revealed_hands': '公開された相手の手札',
})
UI_FALLBACKS.setdefault('en', {}).update({
    'battle_lytton_title': 'Lytton Commission',
    'battle_lytton_notice': 'The commission report reveals opponents current hands.',
    'battle_lytton_start_log': 'The Lytton Commission arrived. Opponents hands are revealed.',
    'battle_revealed_hands': 'Revealed opponent hands',
})
UI_FALLBACKS.setdefault('zh', {}).update({
    'battle_lytton_title': '李顿调查团',
    'battle_lytton_notice': '调查团报告公开了对手当前的手牌。',
    'battle_lytton_start_log': '李顿调查团到达。对手手牌会被公开。',
    'battle_revealed_hands': '公开的对手手牌',
})

UI_FALLBACKS.setdefault('ja', {}).update({
    'privacy_settings': '公開設定',
    'hide_public_profile': 'ユーザー一覧・ランキングに表示しない',
    'hide_public_profile_hint': 'オンにすると、他の人から見えるユーザー一覧、公開お気に入り、公開コレクション、ランキングから自分の情報を隠します。',
    'public_visibility_saved': '公開設定を保存しました。',
    'users_search': 'ユーザー検索',
    'users_search_placeholder': 'ユーザー名で探す',
    'favorite_country_filter': 'お気に入り国で絞り込み',
    'clear_user_filters': '絞り込みを解除',
    'no_user_search_results': '条件に合うユーザーはいません。',
})

UI_FALLBACKS.setdefault('en', {}).update({
    'privacy_settings': 'Privacy',
    'hide_public_profile': 'Hide me from user lists and rankings',
    'hide_public_profile_hint': 'When enabled, your public user card, favorites, collections, and ranking entries are hidden from other users.',
    'public_visibility_saved': 'Privacy setting saved.',
    'users_search': 'Search users',
    'users_search_placeholder': 'Search by username',
    'favorite_country_filter': 'Filter by favorite country',
    'clear_user_filters': 'Clear filters',
    'no_user_search_results': 'No users match these filters.',
})

UI_FALLBACKS.setdefault('zh', {}).update({
    'privacy_settings': '公开设置',
    'hide_public_profile': '不显示在用户列表和排行榜',
    'hide_public_profile_hint': '开启后，其他用户看不到你的用户卡片、公开收藏、公开合集和排行榜记录。',
    'public_visibility_saved': '公开设置已保存。',
    'users_search': '搜索用户',
    'users_search_placeholder': '按用户名搜索',
    'favorite_country_filter': '按收藏国家筛选',
    'clear_user_filters': '清除筛选',
    'no_user_search_results': '没有符合条件的用户。',
})

UI_FALLBACKS.setdefault('ja', {}).update({
    'sengoku_medal_unlocked_notice': '戦国ボス全撃破。勲章を獲得しました。',
    'staff_roll_title': 'World Archives スタッフロール',
    'staff_roll_close': '閉じる',
    'staff_roll_source_heading': '参考資料・画像・地図',
})
UI_FALLBACKS.setdefault('en', {}).update({
    'sengoku_medal_unlocked_notice': 'All Sengoku bosses cleared. Medal unlocked.',
    'staff_roll_title': 'World Archives Credits',
    'staff_roll_close': 'Close',
    'staff_roll_source_heading': 'References, Images, and Maps',
})
UI_FALLBACKS.setdefault('zh', {}).update({
    'sengoku_medal_unlocked_notice': '战国Boss全部击破。已获得勋章。',
    'staff_roll_title': 'World Archives 制作人员',
    'staff_roll_close': '关闭',
    'staff_roll_source_heading': '参考资料、图片与地图',
})

UI_FALLBACKS.setdefault('ja', {}).update({
    'battle_bomb_notice': '爆弾カードがどこかの手札にあります。持ち主は本人にだけ表示されます。',
    'battle_bomb_start_log': '爆弾カードが誰かの手札に入りました。',
    'battle_bomb_pass_log': '爆弾カードが移動しました。',
    'battle_bomb_card_hint': '場に出すと誰かの手札へ移ります。持ったままイベントが終わると危険です。',
    'battle_bomb_in_your_hand': '爆弾カードがあなたの手札にあります。',
    'battle_bomb_secret_move': '爆弾カードが移動しました。',
    'battle_bomb_lytton_explode_log': 'リットン調査団が爆弾カードを発見し、{holder}と{viewer}が{damage}ダメージに巻き込まれました。',
    'battle_bomb_lytton_notice': 'リットン調査団が爆弾カードを見つけてしまいました。爆発に巻き込まれます。',
})
UI_FALLBACKS.setdefault('en', {}).update({
    'battle_bomb_notice': "A bomb card is hidden in someone's hand. Only its holder can see it clearly.",
    'battle_bomb_start_log': "A bomb card entered someone's hand.",
    'battle_bomb_pass_log': 'The bomb card moved.',
    'battle_bomb_card_hint': "Play it to pass it to someone's hand. Holding it when the event ends is dangerous.",
    'battle_bomb_in_your_hand': 'The bomb card is in your hand.',
    'battle_bomb_secret_move': 'The bomb card moved.',
    'battle_bomb_lytton_explode_log': 'The Lytton Commission found the bomb card. {holder} and {viewer} were caught for {damage} damage.',
    'battle_bomb_lytton_notice': 'The Lytton Commission found the bomb card. You are caught in the blast.',
})
UI_FALLBACKS.setdefault('zh', {}).update({
    'battle_bomb_notice': '炸弹牌藏在某个人的手牌中。只有持有人能清楚看到。',
    'battle_bomb_start_log': '炸弹牌进入了某个人的手牌。',
    'battle_bomb_pass_log': '炸弹牌移动了。',
    'battle_bomb_card_hint': '打出可传到某个人手中。事件结束时还拿着会很危险。',
    'battle_bomb_in_your_hand': '炸弹牌在你的手牌中。',
    'battle_bomb_secret_move': '炸弹牌移动了。',
    'battle_bomb_lytton_explode_log': '李顿调查团发现了炸弹牌，{holder}和{viewer}受到{damage}伤害。',
    'battle_bomb_lytton_notice': '李顿调查团发现了炸弹牌。你被卷入爆炸。',
})

UI_FALLBACKS.setdefault('ja', {}).update({
    'battle_bomb_notice': '爆弾カードがどこかの手札にあります。持ち主にだけ分かりやすく表示されます。',
    'battle_bomb_start_log': '爆弾カードが誰かの手札に入りました。',
    'battle_bomb_pass_log': '爆弾カードが移動しました。',
    'battle_bomb_explode_log': '{player}の手札で爆弾カードが爆発し、{damage}ダメージを受けました。',
    'battle_bomb_card_hint': '場に出すと誰かの手札へ移ります。持ったままイベントが終わると危険です。',
    'battle_bomb_in_your_hand': '爆弾カードがあなたの手札にあります。',
    'battle_bomb_secret_move': '爆弾カードが移動しました。',
    'battle_bomb_lytton_explode_log': 'リットン調査団が爆弾カードを発見し、{holder}と{viewer}が{damage}ダメージに巻き込まれました。',
    'battle_bomb_lytton_notice': 'リットン調査団が爆弾カードを見つけてしまいました。爆発に巻き込まれます。',
})

UI_FALLBACKS.setdefault('ja', {}).update({
    'battle_bomb_notice': '爆弾カードがどこかの手札にあります。普通の国カードに偽装しており、出すかイベント終了時に爆発します。',
    'battle_bomb_card_hint': '国カードに偽装しています。出すと爆発します。',
    'battle_bomb_in_your_hand': '手元に爆弾カードがあります。',
})
UI_FALLBACKS.setdefault('en', {}).update({
    'battle_bomb_notice': 'A bomb card is hidden in a hand. It looks like a normal country card and explodes if played or when the event ends.',
    'battle_bomb_card_hint': 'It is disguised as a country card. Playing it detonates it.',
    'battle_bomb_in_your_hand': 'You have a bomb card in your hand.',
})
UI_FALLBACKS.setdefault('zh', {}).update({
    'battle_bomb_notice': '炸弹牌藏在某个手牌中。它会伪装成普通国家牌，打出或事件结束时会爆炸。',
    'battle_bomb_card_hint': '它伪装成国家牌。打出就会爆炸。',
    'battle_bomb_in_your_hand': '你的手中有炸弹牌。',
})

for _lang, _values in {
    'ja': {
        'battle_damage_surge_title': '作戦混乱',
        'battle_damage_surge_notice': '毎ターン、指定枚数ぴったりに近い作戦行動が求められます。指定より多くは出せず、少ないと自傷事故が起こることがあります。',
        'battle_damage_surge_start_log': '作戦混乱が始まりました。各ターンの指定枚数に注意してください。',
        'battle_event_multiplier_label': 'イベント補正',
        'battle_operation_required': '作戦指定: {count}枚',
        'battle_operation_required_help': 'このターンは{count}枚まで出せます。少ない枚数で出すと、不足1枚につき20%の確率で自傷ダメージを受けます。',
        'battle_operation_too_many': '作戦混乱中は{count}枚より多く出せません。',
        'battle_operation_self_damage_log': '{player}は作戦混乱で{missing}枚不足し、攻撃が暴発して{damage}ダメージを受けました。',
        'battle_random_target_title': '標的錯乱',
        'battle_random_target_notice': '攻撃対象がランダムになります。チーム戦では自分のチームも対象に入ります。',
        'battle_random_target_start_log': '標的錯乱が始まりました。攻撃対象がランダムになります。',
        'battle_random_target_log': '{player}の攻撃対象が{target}に変わりました。',
        'battle_random_target_self_damage_log': '{team}は標的錯乱で攻撃が味方側へ逸れ、{damage}ダメージを受けました。',
    },
    'en': {
        'battle_damage_surge_title': 'Operation Confusion',
        'battle_damage_surge_notice': 'Each turn demands a specific card count. You cannot play more than it, and playing fewer can cause self-damage.',
        'battle_damage_surge_start_log': 'Operation Confusion began. Watch the required card count each turn.',
        'battle_event_multiplier_label': 'Event',
        'battle_operation_required': 'Order: {count} cards',
        'battle_operation_required_help': 'This turn you may play up to {count} cards. If you play fewer, each missing card has a 20% chance to cause self-damage.',
        'battle_operation_too_many': 'Operation Confusion does not allow more than {count} cards.',
        'battle_operation_self_damage_log': '{player} was short by {missing} cards; the attack misfired for {damage} self-damage.',
        'battle_random_target_title': 'Target Scramble',
        'battle_random_target_notice': 'Attack targets are randomized. In team battles, your own team can also be chosen.',
        'battle_random_target_start_log': 'Target Scramble began. Attack targets are randomized.',
        'battle_random_target_log': "{player}'s target changed to {target}.",
        'battle_random_target_self_damage_log': "{team}'s attack veered into its own side for {damage} damage.",
    },
    'zh': {
        'battle_damage_surge_title': '作战混乱',
        'battle_damage_surge_notice': '每回合会指定出牌枚数。不能超过指定枚数，少出时可能受到自伤伤害。',
        'battle_damage_surge_start_log': '作战混乱开始。请注意每回合指定枚数。',
        'battle_event_multiplier_label': '事件补正',
        'battle_operation_required': '作战指定：{count}张',
        'battle_operation_required_help': '本回合最多可出{count}张。少出时，每少1张有20%概率受到自伤伤害。',
        'battle_operation_too_many': '作战混乱中不能超过{count}张。',
        'battle_operation_self_damage_log': '{player}因作战混乱少出{missing}张，攻击暴发并受到{damage}伤害。',
        'battle_random_target_title': '目标错乱',
        'battle_random_target_notice': '攻击目标会随机决定。团队战中自己的队伍也会成为目标。',
        'battle_random_target_start_log': '目标错乱开始。攻击目标会随机决定。',
        'battle_random_target_log': '{player}的攻击目标变为{target}。',
        'battle_random_target_self_damage_log': '{team}因目标错乱攻击偏向己方，受到{damage}伤害。',
    },
}.items():
    TRANSLATIONS.setdefault(_lang, {}).update(_values)
    UI_FALLBACKS.setdefault(_lang, {}).update(_values)

def t(key, subkey=None):
    lang_data = TRANSLATIONS.get(state.lang, TRANSLATIONS.get('en', {}))
    fallback = UI_FALLBACKS.get(state.lang, UI_FALLBACKS['en']).get(key, key)
    val = lang_data.get(key, fallback)
    if subkey and isinstance(val, dict):
        return val.get(subkey, subkey)
    return val

def tag_label(tag, lang=None):
    lang = lang or state.lang
    labels = TRANSLATIONS.get(lang, {}).get('tag_labels', {})
    return labels.get(tag, tag)

def tag_search_text(tag):
    values = [tag]
    for lang_data in TRANSLATIONS.values():
        label = lang_data.get('tag_labels', {}).get(tag)
        if label and label not in values:
            values.append(label)
    return ' '.join(values)

def tag_category_label(category, lang=None):
    lang = lang or state.lang
    labels = TRANSLATIONS.get(lang, {}).get('tag_category_labels', {})
    return labels.get(category, category)

def selected_tag_group_label():
    return tag_category_label(state.filter_tag_group) if state.filter_tag_group else None

def tag_categories(data=None):
    data = data or get_data()
    categories = data.get('tag_categories', {})
    return categories if isinstance(categories, dict) else {}

def get_tag_group_options():
    data = get_data()
    used_tags = derived_country_data(data)['public_tags']
    options = []
    for category, category_tags in tag_categories(data).items():
        if any(tag in used_tags for tag in category_tags):
            options.append(tag_category_label(category))
    return options

def tag_group_allowed_tags(group, data=None):
    if not group:
        return None
    categories = tag_categories(data)
    return set(categories.get(group, [])) if group in categories else None

TAG_COLOR_STYLES = {
    'UN Member': ('#eff6ff', '#1e3a8a', '#bfdbfe'),
    'European Union': ('#eef2ff', '#3730a3', '#c7d2fe'),
    'G20': ('#f0f9ff', '#075985', '#bae6fd'),
    'NATO': ('#f8fafc', '#0f172a', '#cbd5e1'),
    'Commonwealth': ('#ecfdf5', '#065f46', '#a7f3d0'),
    'Arab League': ('#fff7ed', '#9a3412', '#fed7aa'),
    'African Union': ('#f0fdf4', '#166534', '#bbf7d0'),
    'ASEAN': ('#fefce8', '#854d0e', '#fef08a'),
    'Mercosur': ('#ecfeff', '#155e75', '#a5f3fc'),
    'OPEC': ('#fff1f2', '#9f1239', '#fecdd3'),
    'Kingdom': ('#fef3c7', '#92400e', '#fde68a'),
    'Republic': ('#dcfce7', '#166534', '#bbf7d0'),
    'Federation': ('#dbeafe', '#1d4ed8', '#bfdbfe'),
    'Confederation': ('#fae8ff', '#86198f', '#f5d0fe'),
    'Empire': ('#ede9fe', '#5b21b6', '#ddd6fe'),
    'Sultanate': ('#ffedd5', '#9a3412', '#fed7aa'),
    'Khanate': ('#fef9c3', '#713f12', '#fde68a'),
    'Caliphate': ('#ccfbf1', '#115e59', '#99f6e4'),
    'City-State': ('#e0f2fe', '#0369a1', '#bae6fd'),
    'Duchy & Principality': ('#fce7f3', '#9d174d', '#fbcfe8'),
    'Colonial Empire': ('#fee2e2', '#991b1b', '#fecaca'),
    'Socialist State': ('#ffe4e6', '#be123c', '#fecdd3'),
    'Constitutional Monarchy': ('#ecfccb', '#3f6212', '#d9f99d'),
    'Military Government': ('#e5e7eb', '#1f2937', '#d1d5db'),
    'Revolutionary State': ('#ffedd5', '#c2410c', '#fed7aa'),
    'Maritime Power': ('#cffafe', '#0e7490', '#a5f3fc'),
    'Trade Hub': ('#fef3c7', '#a16207', '#fde68a'),
    'Nomadic Power': ('#f5f5f4', '#44403c', '#d6d3d1'),
    'Silk Road': ('#fef9c3', '#854d0e', '#fde68a'),
    'Steppe Empire': ('#f4f4f5', '#3f3f46', '#d4d4d8'),
    'Island Nation': ('#dffafe', '#155e75', '#a5f3fc'),
    'Ancient Civilization': ('#fefce8', '#713f12', '#fde68a'),
    'Medieval Dynasty': ('#f3e8ff', '#6b21a8', '#e9d5ff'),
    'Early Modern State': ('#f0f9ff', '#0c4a6e', '#bae6fd'),
    'Modern Nation-State': ('#f8fafc', '#334155', '#cbd5e1'),
    'Industrial Power': ('#f1f5f9', '#0f172a', '#cbd5e1'),
    'Resource Economy': ('#ecfdf5', '#047857', '#a7f3d0'),
    'Multilingual State': ('#faf5ff', '#7e22ce', '#e9d5ff'),
    'Religious Center': ('#f5f3ff', '#4c1d95', '#ddd6fe'),
    'Cultural Sphere': ('#fdf2f8', '#831843', '#fbcfe8'),
}

TAG_COLOR_PALETTE = [
    ('#eff6ff', '#1e3a8a', '#bfdbfe'),
    ('#ecfdf5', '#065f46', '#a7f3d0'),
    ('#fff7ed', '#9a3412', '#fed7aa'),
    ('#f5f3ff', '#5b21b6', '#ddd6fe'),
    ('#fdf2f8', '#9d174d', '#fbcfe8'),
    ('#ecfeff', '#155e75', '#a5f3fc'),
    ('#fefce8', '#713f12', '#fde68a'),
    ('#f8fafc', '#334155', '#cbd5e1'),
]

def tag_color_style(tag):
    if tag in TAG_COLOR_STYLES:
        return TAG_COLOR_STYLES[tag]
    index = int(hashlib.sha256(str(tag).encode('utf-8')).hexdigest(), 16) % len(TAG_COLOR_PALETTE)
    return TAG_COLOR_PALETTE[index]

def tag_chip(tag, dense=True):
    props = 'dense size=xs' if dense else 'dense'
    bg, fg, border = tag_color_style(tag)
    return (
        ui.chip(tag_label(tag))
        .props(props)
        .classes('wa-tag-chip')
        .style(f'background-color: {bg} !important; color: {fg} !important; border: 1px solid {border} !important;')
    )

def selected_tag_label():
    return tag_label(state.filter_tag) if state.filter_tag else None

def region_label(region, lang=None):
    if not region:
        return ''
    lang = lang or state.lang
    labels = TRANSLATIONS.get(lang, {}).get('region_labels', {})
    return labels.get(region, region)

def region_search_text(region):
    values = [region]
    for lang_data in TRANSLATIONS.values():
        label = lang_data.get('region_labels', {}).get(region)
        if label and label not in values:
            values.append(label)
    return ' '.join(values)

def selected_region_label():
    return region_label(state.filter_region) if state.filter_region else None

def get_localized_text(data_dict):
    if isinstance(data_dict, dict):
        return data_dict.get(state.lang, data_dict.get('en', ''))
    return str(data_dict)

# hidden=True の国はサプライズ用です。検索で名前を入れた時だけ表示します。
def is_hidden_country(country):
    return bool(country.get('hidden'))

def can_show_hidden_country(country, keyword):
    if not is_hidden_country(country):
        return True
    term = str(keyword or '').strip().casefold()
    if not term:
        return False
    return any(term == allowed.casefold() for allowed in SECRET_HIDDEN_COUNTRY_SEARCH_TERMS)

def public_country_list(data=None):
    return derived_country_data(data)['public_countries']

def public_countries_by_key(data=None):
    return derived_country_data(data)['public_by_key']

def get_flag_url(code):
    if not code or code == 'xx':
        return 'https://placehold.co/160x100?text=No+Flag'
    if isinstance(code, str) and code.startswith('asset:'):
        return f"/assets/{code.split(':', 1)[1].lstrip('/')}"
    if isinstance(code, str) and code.startswith(('http://', 'https://')):
        return code
    return f'https://flagcdn.com/w160/{code.lower()}.png'

def render_flag_frame(country, frame_classes, image_classes='w-full h-full object-cover'):
    with ui.column().classes(f'wa-flag-frame {frame_classes} overflow-hidden bg-gray-100 justify-center items-center gap-0').style('aspect-ratio: 3 / 2;'):
        ui.image(get_flag_url(country.get('flag_code'))).classes(image_classes)

def get_filter_options():
    data = get_data()
    cache = derived_country_data(data)
    regions = cache['public_regions']
    tags = set()
    allowed_tags = tag_group_allowed_tags(state.filter_tag_group, data)
    source_tags = cache['public_tags']
    if allowed_tags is None:
        tags = source_tags
    else:
        tags = {tag for tag in source_tags if tag in allowed_tags}
    sorted_tags = sorted(tags, key=lambda tag: tag_label(tag).lower())
    sorted_regions = sorted(regions, key=lambda region: region_label(region).lower())
    return [region_label(region) for region in sorted_regions], [tag_label(tag) for tag in sorted_tags]

def normalize_region_value(value):
    if not value:
        return None
    data = get_data()
    regions = derived_country_data(data)['public_regions']
    if value in regions:
        return value
    for region in regions:
        labels = [region_label(region, lang) for lang in TRANSLATIONS]
        if value in labels:
            return region
    return value

def normalize_tag_value(value):
    if not value:
        return None
    data = get_data()
    tags = derived_country_data(data)['public_tags']
    if value in tags:
        return value
    for tag in tags:
        labels = [tag_label(tag, lang) for lang in TRANSLATIONS]
        if value in labels:
            return tag
    return value

def normalize_tag_group_value(value):
    if not value:
        return None
    data = get_data()
    categories = tag_categories(data)
    if value in categories:
        return value
    for category in categories:
        labels = [tag_category_label(category, lang) for lang in TRANSLATIONS]
        if value in labels:
            return category
    return value

def country_key(country):
    names = country.get('names', {})
    capital = country.get('capital', {})
    return '|'.join([
        names.get('en', names.get('ja', '')),
        country.get('type', ''),
        capital.get('en', capital.get('ja', '')),
    ])

def derived_country_data(data=None):
    global DERIVED_DATA_CACHE
    data = data or get_data()
    mtime = DATA_CACHE_MTIME or file_mtime(JSON_FILE)
    data_id = id(data)
    cached = DERIVED_DATA_CACHE.get('value')
    if cached and DERIVED_DATA_CACHE.get('mtime') == mtime and DERIVED_DATA_CACHE.get('data_id') == data_id:
        return cached

    countries = list(data.get('countries', []))
    public_countries = [country for country in countries if not is_hidden_country(country)]
    all_by_key = {country_key(country): country for country in countries}
    public_by_key = {country_key(country): country for country in public_countries}
    public_keys = list(public_by_key.keys())
    public_regions = {country.get('region') for country in public_countries if country.get('region')}
    public_tags = {tag for country in public_countries for tag in country.get('tags', [])}
    value = {
        'countries': countries,
        'public_countries': public_countries,
        'all_by_key': all_by_key,
        'public_by_key': public_by_key,
        'public_keys': public_keys,
        'public_regions': public_regions,
        'public_tags': public_tags,
    }
    DERIVED_DATA_CACHE = {'mtime': mtime, 'data_id': data_id, 'value': value}
    return value

def clean_username(username):
    return (username or '').strip()

def guest_username_from_id(guest_id):
    guest_id = re.sub(r'[^A-Za-z0-9_-]', '', str(guest_id or ''))[:64]
    return f'{GUEST_USERNAME}:{guest_id}' if guest_id else GUEST_USERNAME

async def browser_guest_username():
    script = f"""
    (() => {{
      const key = '{GUEST_BROWSER_KEY}';
      let guestId = localStorage.getItem(key);
      if (!guestId) {{
        guestId = (window.crypto && window.crypto.randomUUID)
          ? window.crypto.randomUUID()
          : `${{Date.now()}}-${{Math.random().toString(36).slice(2)}}`;
        localStorage.setItem(key, guestId);
      }}
      return guestId;
    }})()
    """
    try:
        guest_id = await ui.run_javascript(script)
    except Exception as e:
        print(f"Browser guest id fallback used: {e}", flush=True)
        guest_id = str(uuid.uuid4())
    return guest_username_from_id(guest_id)

def password_hash(username, password):
    return hashlib.sha256(f'{username}:{password}'.encode('utf-8')).hexdigest()

def get_users(user_data=None):
    user_data = user_data or load_user_data()
    if not isinstance(user_data.get('users'), dict):
        user_data['users'] = {}
    return user_data['users']

def is_guest_record(username, record=None):
    return (
        username == GUEST_USERNAME
        or str(username).startswith(f'{GUEST_USERNAME}:')
        or (isinstance(record, dict) and bool(record.get('is_guest')))
    )

def is_current_user_guest():
    return is_guest_record(state.current_user, get_current_user_record())

def get_current_user_record(user_data=None):
    if not state.current_user:
        return None
    users = get_users(user_data)
    user = users.get(state.current_user)
    if user:
        ensure_user_defaults(user)
    return user

def get_named_user_record(username, user_data=None):
    username = clean_username(username)
    if not username:
        return None
    users = get_users(user_data)
    user = users.get(username)
    if user:
        ensure_user_defaults(user)
    return user

def clamp_number(value, min_value, max_value, default):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(min_value, min(max_value, number))

def default_avatar_adjustment():
    return {'zoom': 100, 'position_x': 50, 'position_y': 50}

def normalize_name_color(value):
    color = str(value or '').strip()
    if re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        return color.lower()
    return DEFAULT_NAME_COLOR

def user_name_color(user=None):
    if user is None:
        user = get_current_user_record()
    if isinstance(user, dict):
        return normalize_name_color(user.get('name_color'))
    return DEFAULT_NAME_COLOR

def user_pill_text_color(user=None):
    return '#111827' if state.theme_mode == 'dark' else user_name_color(user)

def normalize_avatar_adjustment(avatar):
    if not isinstance(avatar, dict):
        return {'mode': 'default', **default_avatar_adjustment()}
    avatar['zoom'] = int(clamp_number(avatar.get('zoom'), 20, 300, 100))
    avatar['position_x'] = int(clamp_number(avatar.get('position_x'), 0, 100, 50))
    avatar['position_y'] = int(clamp_number(avatar.get('position_y'), 0, 100, 50))
    return avatar

def compact_avatar_record(avatar):
    if not isinstance(avatar, dict):
        return {'mode': 'default', **default_avatar_adjustment()}
    avatar = dict(avatar)
    if avatar.get('mode') == 'upload' and avatar.get('file'):
        avatar.pop('data_url', None)
    elif isinstance(avatar.get('data_url'), str) and len(avatar.get('data_url', '')) > 512_000:
        avatar.pop('data_url', None)
    return normalize_avatar_adjustment(avatar)

def normalize_notifications(value):
    if not isinstance(value, list):
        return []
    notifications = []
    for item in value:
        if not isinstance(item, dict):
            continue
        message = str(item.get('message') or '').strip()
        if not message:
            continue
        created_at = str(item.get('created_at') or item.get('timestamp') or current_timestamp())
        raw_id = str(item.get('id') or '').strip()
        if not raw_id:
            raw_id = hashlib.sha256(f"{message}:{created_at}:{item.get('chat_id', '')}".encode('utf-8')).hexdigest()[:16]
        notifications.append({
            'id': raw_id,
            'message': message[:500],
            'chat_id': str(item.get('chat_id') or '').strip(),
            'kind': str(item.get('kind') or 'social').strip() or 'social',
            'created_at': created_at,
            'read': bool(item.get('read')),
        })
    return sorted(notifications, key=lambda item: item.get('created_at', ''), reverse=True)[:50]

def ensure_user_defaults(user):
    for key in ['favorites', 'history', 'review_keys', 'viewed_keys', 'quiz_history', 'friends', 'notifications', 'sengoku_boss_clears']:
        if not isinstance(user.get(key), list):
            user[key] = []
    del user['history'][80:]
    del user['quiz_history'][QUIZ_HISTORY_LIMIT:]
    del user['review_keys'][80:]
    user['notifications'] = normalize_notifications(user.get('notifications'))
    for key in ['notes', 'collections']:
        if not isinstance(user.get(key), dict):
            user[key] = {}
    user.setdefault('quiz_stats', {
        'answered': 0,
        'correct': 0,
        'streak': 0,
        'best_streak': 0,
    })
    normalize_quiz_stats(user)
    user['avatar'] = compact_avatar_record(user.get('avatar'))
    user['name_color'] = normalize_name_color(user.get('name_color'))
    user['hide_public_profile'] = bool(user.get('hide_public_profile'))
    if not isinstance(user.get('battle_wins'), int):
        user['battle_wins'] = 0
    if not isinstance(user.get('battle_unlocked'), bool):
        user['battle_unlocked'] = bool(user.get('battle_unlocked_notified'))
    if not isinstance(user.get('battle_unlocked_notified'), bool):
        user['battle_unlocked_notified'] = False
    if not isinstance(user.get('sengoku_unlocked'), bool):
        user['sengoku_unlocked'] = False
    if not isinstance(user.get('sengoku_unlocked_notified'), bool):
        user['sengoku_unlocked_notified'] = False
    if not isinstance(user.get('sengoku_mode'), bool):
        user['sengoku_mode'] = False
    if not isinstance(user.get('sengoku_medal'), bool):
        user['sengoku_medal'] = False
    user['sengoku_boss_clears'] = normalize_sengoku_boss_clears(user.get('sengoku_boss_clears', []))
    if not isinstance(user.get('all_viewed_granted'), bool):
        user['all_viewed_granted'] = False
    restore_all_viewed_progress_if_unlocked(user)
    return user

BROWSER_BACKUP_KEY = 'world_archives_user_backups'
PUBLIC_BROWSER_BACKUP_KEY = 'world_archives_public_user_backups'

def sync_current_user_to_browser(user_data=None):
    if not state.current_user:
        return
    user_data = user_data or load_user_data()
    user = user_data.get('users', {}).get(state.current_user)
    if not user:
        return
    ensure_user_defaults(user)
    payload = {
        'username': state.current_user,
        'record': user,
        'updated_at': current_timestamp(),
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    script = f"""
    (() => {{
      const payload = {payload_json};
      const key = '{BROWSER_BACKUP_KEY}';
      let backups = {{}};
      try {{
        backups = JSON.parse(localStorage.getItem(key) || '{{}}');
      }} catch (error) {{
        backups = {{}};
      }}
      const existingPayload = backups[payload.username];
      const existingRecord = existingPayload && (existingPayload.record || existingPayload);
      if (existingRecord && payload.record) {{
        const fields = ['answered', 'correct', 'streak', 'best_streak'];
        payload.record.quiz_stats = payload.record.quiz_stats || {{}};
        const existingStats = existingRecord.quiz_stats || {{}};
        fields.forEach(field => {{
          payload.record.quiz_stats[field] = Math.max(
            Number(payload.record.quiz_stats[field] || 0),
            Number(existingStats[field] || 0),
          );
        }});
        const viewed = [];
        const viewedSeen = new Set();
        (payload.record.viewed_keys || []).forEach(item => {{
          if (!item || viewedSeen.has(item)) return;
          viewedSeen.add(item);
          viewed.push(item);
        }});
        payload.record.viewed_keys = viewed;
        const seenQuiz = new Set();
        const mergedQuizHistory = [];
        [...(payload.record.quiz_history || []), ...(existingRecord.quiz_history || [])].forEach(item => {{
          if (!item || typeof item !== 'object') return;
          const marker = JSON.stringify([
            item.timestamp || '',
            item.answer_key || '',
            item.selected_key || '',
            item.type || '',
            !!item.correct,
          ]);
          if (seenQuiz.has(marker)) return;
          seenQuiz.add(marker);
          mergedQuizHistory.push(item);
        }});
        mergedQuizHistory.sort((a, b) => String(b.timestamp || '').localeCompare(String(a.timestamp || '')));
        payload.record.quiz_history = mergedQuizHistory.slice(0, {QUIZ_HISTORY_LIMIT});
      }}
      backups[payload.username] = payload;
      const knownKey = 'world_archives_known_usernames';
      let known = [];
      try {{
        known = JSON.parse(localStorage.getItem(knownKey) || '[]');
      }} catch (error) {{
        known = [];
      }}
      if (!known.includes(payload.username)) known.push(payload.username);
      try {{
        localStorage.setItem(key, JSON.stringify(backups));
      }} catch (error) {{
        const compactPayload = JSON.parse(JSON.stringify(payload));
        if (compactPayload.record && compactPayload.record.avatar) {{
          delete compactPayload.record.avatar.data_url;
        }}
        backups[payload.username] = compactPayload;
        Object.values(backups).forEach(item => {{
          if (item && item.record && item.record.avatar) {{
            delete item.record.avatar.data_url;
          }}
        }});
        localStorage.setItem(key, JSON.stringify(backups));
      }}
      localStorage.setItem(knownKey, JSON.stringify(known));
    }})();
    """
    try:
        ui.run_javascript(script)
    except Exception as e:
        print(f"Browser backup skipped: {e}", flush=True)

def flush_current_user_browser_sync():
    state.current_user_browser_sync_pending = False
    sync_current_user_to_browser()

def queue_current_user_browser_sync(delay=3.0):
    if state.current_user_browser_sync_pending:
        return
    state.current_user_browser_sync_pending = True
    try:
        ui.timer(delay, flush_current_user_browser_sync, once=True)
    except Exception as e:
        state.current_user_browser_sync_pending = False
        print(f"Browser backup scheduling skipped: {e}", flush=True)

def remove_browser_backup(username):
    if not username:
        return
    script = f"""
    (() => {{
      const key = '{BROWSER_BACKUP_KEY}';
      let backups = {{}};
      try {{
        backups = JSON.parse(localStorage.getItem(key) || '{{}}');
      }} catch (error) {{
        backups = {{}};
      }}
      delete backups[{json.dumps(username)}];
      localStorage.setItem(key, JSON.stringify(backups));
    }})();
    """
    try:
        ui.run_javascript(script)
    except Exception as e:
        print(f"Browser backup removal skipped: {e}", flush=True)

def persist_current_user_data(user_data, immediate_browser=False):
    save_user_data(user_data)
    state.public_users_browser_synced = False
    if immediate_browser:
        sync_current_user_to_browser(user_data)
    else:
        queue_current_user_browser_sync()

def remember_known_user(username, user_data):
    username = clean_username(username)
    if not username or is_guest_record(username):
        return
    known_users = user_data.setdefault('known_users', [])
    if username not in known_users:
        known_users.append(username)

def request_browser_backup_restore():
    script = f"""
    (async () => {{
      const backupKey = '{BROWSER_BACKUP_KEY}';
      const knownKey = 'world_archives_known_usernames';
      const collected = {{}};
      const knownUsers = new Set();
      const userFields = ['password_hash', 'favorites', 'history', 'notes', 'viewed_keys', 'collections', 'quiz_history', 'review_keys', 'quiz_stats', 'avatar', 'name_color', 'hide_public_profile', 'battle_wins', 'battle_unlocked', 'battle_unlocked_notified', 'sengoku_unlocked', 'sengoku_unlocked_notified', 'sengoku_mode', 'sengoku_medal', 'sengoku_boss_clears', 'all_viewed_granted', 'friends', 'notifications'];
      const looksLikeRecord = value => !!(value && typeof value === 'object' && userFields.some(field => Object.prototype.hasOwnProperty.call(value, field)));
      const mergeRecord = (username, value) => {{
        if (!username || !value || typeof value !== 'object') return;
        const cleanName = String(username);
        knownUsers.add(cleanName);
        const record = looksLikeRecord(value) ? value : (looksLikeRecord(value.record) ? value.record : null);
        if (!record) return;
        const existingPayload = collected[cleanName];
        const existingRecord = looksLikeRecord(existingPayload)
          ? existingPayload
          : (existingPayload && looksLikeRecord(existingPayload.record) ? existingPayload.record : null);
        if (existingRecord) {{
          const mergedRecord = Object.assign({{}}, existingRecord, record);
          if (existingRecord.password_hash && !record.password_hash) {{
            mergedRecord.password_hash = existingRecord.password_hash;
          }}
          collected[cleanName] = {{username: cleanName, record: mergedRecord}};
        }} else {{
          collected[cleanName] = {{username: cleanName, record}};
        }}
      }};
      const collectPayload = value => {{
        if (!value) return;
        let parsed = value;
        if (typeof parsed === 'string') {{
          try {{
            parsed = JSON.parse(parsed);
          }} catch (error) {{
            return;
          }}
        }}
        if (!parsed || typeof parsed !== 'object') return;
        if (Array.isArray(parsed.known_users)) {{
          parsed.known_users.forEach(username => {{
            if (username) knownUsers.add(String(username));
          }});
        }}
        if (parsed.users && typeof parsed.users === 'object') {{
          if (Array.isArray(parsed.users)) {{
            parsed.users.forEach(record => mergeRecord(record && (record.username || record.name || record.id), record));
          }} else {{
            Object.entries(parsed.users).forEach(([username, record]) => mergeRecord(username, {{record}}));
          }}
          return;
        }}
        if (parsed.username) {{
          knownUsers.add(String(parsed.username));
          mergeRecord(parsed.username, parsed.record ? parsed : {{record: parsed}});
          return;
        }}
        Object.entries(parsed).forEach(([username, record]) => {{
          if (record && typeof record === 'object') {{
            mergeRecord(record.username || username, record);
          }}
        }});
      }};
      collectPayload(localStorage.getItem(backupKey));
      try {{
        collectPayload({{known_users: JSON.parse(localStorage.getItem(knownKey) || '[]')}});
      }} catch (error) {{}}
      if (!Object.keys(collected).length && !knownUsers.size) return;
      try {{
        await fetch('/api/restore-user-backups', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{
            users: collected,
            known_users: Array.from(knownUsers),
          }}),
        }});
      }} catch (error) {{
        console.warn('World Archives backup restore failed', error);
      }}
    }})();
    """
    try:
        ui.run_javascript(script)
    except Exception as e:
        print(f"Browser restore skipped: {e}", flush=True)

def public_user_backup_payload():
    user_data = load_user_data()
    users = get_users(user_data)
    lookup = public_countries_by_key()
    known_users = [
        username for username in user_data.get('known_users', [])
        if (
            username
            and not is_guest_record(username)
            and not (isinstance(users.get(username), dict) and users[username].get('hide_public_profile'))
        )
    ]
    public_users = {}
    for username, record in users.items():
        if is_guest_record(username, record) or not isinstance(record, dict):
            continue
        ensure_user_defaults(record)
        if record.get('hide_public_profile'):
            continue
        avatar = dict(record.get('avatar', {})) if isinstance(record.get('avatar'), dict) else {'mode': 'default'}
        avatar.pop('data_url', None)
        collections = record.get('collections', {}) if isinstance(record.get('collections'), dict) else {}
        public_users[username] = {
            'favorites': [key for key in record.get('favorites', []) if key in lookup],
            'history': record.get('history', [])[:50] if isinstance(record.get('history'), list) else [],
            'viewed_keys': [key for key in record.get('viewed_keys', []) if key in lookup],
            'collections': {
                name: [key for key in keys if key in lookup]
                for name, keys in collections.items()
                if isinstance(keys, list)
            },
            'quiz_stats': record.get('quiz_stats', {}) if isinstance(record.get('quiz_stats'), dict) else {},
            'review_keys': [key for key in record.get('review_keys', []) if key in lookup],
            'avatar': avatar,
            'name_color': user_name_color(record),
            'hide_public_profile': bool(record.get('hide_public_profile')),
            'battle_wins': int(record.get('battle_wins', 0) or 0),
            'battle_unlocked': bool(record.get('battle_unlocked')),
            'battle_unlocked_notified': bool(record.get('battle_unlocked_notified')),
            'sengoku_unlocked': bool(record.get('sengoku_unlocked')),
            'sengoku_medal': bool(record.get('sengoku_medal')),
            'friends': [
                friend for friend in record.get('friends', [])
                if clean_stored_username(friend) and not is_stored_guest_username(friend)
            ],
        }
    return {
        'users': public_users,
        'known_users': known_users,
        'updated_at': current_timestamp(),
    }

def sync_public_users_to_browser(force=False):
    state.public_users_browser_sync_pending = False
    if state.public_users_browser_synced and not force:
        return
    payload = public_user_backup_payload()
    if not payload.get('users') and not payload.get('known_users'):
        return
    payload_json = json.dumps(payload, ensure_ascii=False)
    script = f"""
    (() => {{
      const key = '{PUBLIC_BROWSER_BACKUP_KEY}';
      const payload = {payload_json};
      try {{
        localStorage.setItem(key, JSON.stringify(payload));
      }} catch (error) {{
        Object.values(payload.users || {{}}).forEach(item => {{
          const record = item && item.record ? item.record : item;
          if (record && record.avatar) {{
            delete record.avatar.data_url;
          }}
        }});
        localStorage.setItem(key, JSON.stringify(payload));
      }}
    }})();
    """
    try:
        ui.run_javascript(script)
        state.public_users_browser_synced = True
    except Exception as e:
        print(f"Public browser backup skipped: {e}", flush=True)

def schedule_public_users_browser_sync(delay=0.8, force=False):
    if state.public_users_browser_sync_pending and not force:
        return
    state.public_users_browser_sync_pending = True
    try:
        ui.timer(delay, lambda: sync_public_users_to_browser(force=force), once=True)
    except Exception as e:
        state.public_users_browser_sync_pending = False
        print(f"Public browser backup scheduling skipped: {e}", flush=True)

def backup_labels():
    labels = {
        'ja': {
            'section': 'バックアップ',
            'export': 'バックアップを書き出す',
            'import': 'バックアップを読み込む',
            'restore_browser': 'ブラウザ保存から復元',
            'exported': 'バックアップを書き出しました。',
            'imported': 'バックアップを読み込みました。',
            'invalid': 'バックアップファイルを読み込めませんでした。',
        },
        'en': {
            'section': 'Backup',
            'export': 'Export backup',
            'import': 'Import backup',
            'restore_browser': 'Restore from browser',
            'exported': 'Backup exported.',
            'imported': 'Backup imported.',
            'invalid': 'Could not read the backup file.',
        },
        'zh': {
            'section': '备份',
            'export': '导出备份',
            'import': '导入备份',
            'restore_browser': '从浏览器恢复',
            'exported': '已导出备份。',
            'imported': '已导入备份。',
            'invalid': '无法读取备份文件。',
        },
    }
    return labels.get(state.lang, labels['en'])

def detail_tab_labels():
    labels = {
        'ja': {'basic': '基本データ', 'desc': '解説', 'map': '地図', 'personal': 'メモ・コレクション', 'related': '関連国家'},
        'en': {'basic': 'Basic', 'desc': 'Details', 'map': 'Map', 'personal': 'Notes & Collections', 'related': 'Related'},
        'zh': {'basic': '基本资料', 'desc': '说明', 'map': '地图', 'personal': '笔记与收藏集', 'related': '相关国家'},
    }
    return labels.get(state.lang, labels['en'])

def help_labels():
    labels = {
        'ja': {
            'nav': 'かんたんガイド',
            'detail_nav': '詳しい説明',
            'title': 'World Archives かんたんガイド',
            'intro': 'まずはこの順番で触ると迷いにくいです。画面の形に合わせて、押す場所だけ先に覚えましょう。',
            'steps': [
                ('login', 'ログイン', '学習記録を残すなら通常ログイン。試すだけならゲストログインで入れます。'),
                ('search', '探す', '検索欄に国名やタグを入れ、地域・タグ分類・年代順で絞り込みます。'),
                ('open_in_new', '読む', '国カードを開くと、基本データ、解説、地図、メモ、関連国家を確認できます。'),
                ('quiz', '覚える', 'ミニクイズは総合と分野別を選べます。間違えた国は復習モードに入ります。'),
            ],
            'mock_title': '画面で見る操作',
            'mocks': [
                ('検索画面', '検索欄・並び替え・地域・タグ分類を使って、見たい国だけに絞ります。'),
                ('詳細画面', '基本データ、解説、地図、メモ、関連国家をタブで切り替えます。'),
                ('クイズ画面', '分野を選び、問題に答えます。答えた後は詳細画面へ戻れます。'),
            ],
        },
        'en': {
            'nav': 'Quick Guide',
            'detail_nav': 'Detailed Guide',
            'title': 'World Archives Quick Guide',
            'intro': 'Start here. This guide shows the main actions in the same shape as the app screens.',
            'steps': [
                ('login', 'Log in', 'Use a normal account to save progress, or guest login for a quick trial.'),
                ('search', 'Search', 'Use keywords, regions, tag groups, and period sorting to narrow the list.'),
                ('open_in_new', 'Read', 'Open a country card to view basic data, details, maps, notes, and related countries.'),
                ('quiz', 'Review', 'Choose mixed or category quizzes. Missed countries go into review mode.'),
            ],
            'mock_title': 'Screen-Based Guide',
            'mocks': [
                ('Search Screen', 'Filter countries with the search box, sorting, regions, and tag groups.'),
                ('Detail Screen', 'Switch between basic data, details, map, notes, and related countries.'),
                ('Quiz Screen', 'Choose a category, answer, then open the detail page from the result.'),
            ],
        },
        'zh': {
            'nav': '简易指南',
            'detail_nav': '详细说明',
            'title': 'World Archives简易指南',
            'intro': '先看这里。这个页面按照实际画面的形状说明主要操作。',
            'steps': [
                ('login', '登录', '普通账号会保存进度；只想试用时可以用访客登录。'),
                ('search', '搜索', '用关键词、地区、标签分类和年代排序缩小列表。'),
                ('open_in_new', '阅读', '打开国家卡片后，可以查看基本资料、说明、地图、笔记和相关国家。'),
                ('quiz', '复习', '小测验可以选择综合或分领域，答错的国家会进入复习模式。'),
            ],
            'mock_title': '按画面理解操作',
            'mocks': [
                ('搜索画面', '使用搜索框、排序、地区和标签分类筛选国家。'),
                ('详情画面', '在基本资料、说明、地图、笔记和相关国家之间切换。'),
                ('测验画面', '选择领域并答题，答题后可以打开该国家详情。'),
            ],
        },
    }
    return labels.get(state.lang, labels['en'])

def detailed_help_labels():
    labels = {
        'ja': {
            'title': 'World Archives 詳しい説明',
            'intro': '機能ごとの目的と使い分けをまとめています。操作に慣れてから、困った時に読むページです。',
            'sections': [
                ('ログインと保存', '通常ログインでは、お気に入り、閲覧履歴、メモ、コレクション、クイズ結果、対戦成績が保存されます。ゲストログインはすぐ試すための入口です。'),
                ('検索と絞り込み', '国名だけでなく、地域、タグ、言語、宗教、説明文、基本データから検索できます。タグ分類を先に選ぶと、タグの候補を絞れます。'),
                ('詳細ページ', '基本データでは首都、成立年、人口、面積、言語、宗教などを確認できます。解説、地図、メモ、関連国家はタブで切り替えます。'),
                ('ミニクイズ', '総合、国旗、年号、首都、タグ、説明、基本データ、詳細データに分かれています。情報から国を選ぶ問題と、国から情報を選ぶ問題の両方が出ます。'),
                ('復習モード', '間違えた国は復習リストに入ります。復習モードで正解すると、復習リストから外れます。'),
                ('比較・年表・地図・ネットワーク', '比較は2つの国を並べ、年表は時代順に整理し、地図は場所を確認し、ネットワークは関連国家をたどるために使います。'),
                ('アカウントと共有', 'アカウントページではアイコン、名前色、バックアップ、公開お気に入り、公開コレクションを管理できます。パスワードと個人メモは他人に表示されません。'),
                ('国力対戦', '全国家を閲覧すると解禁される対戦機能です。国の面積と人口をもとにした国力で勝負し、タグや地域の一致で強力なボーナスが入ります。'),
                ('データの保護', 'Render更新や環境変更の前には、アカウントページからバックアップを書き出しておくと安心です。'),
            ],
        },
        'en': {
            'title': 'World Archives Detailed Guide',
            'intro': 'This page explains what each feature is for. Use it after the quick guide when you want more detail.',
            'sections': [
                ('Login and Saving', 'Normal accounts save favorites, history, notes, collections, quiz results, and battle records. Guest login is for quick trials.'),
                ('Search and Filters', 'Search by name, region, tags, language, religion, descriptions, and basic data. Choose a tag group first to reduce tag choices.'),
                ('Detail Pages', 'Basic data includes capital, founding period, population, area, languages, and religions. Details, maps, notes, and related countries are organized by tabs.'),
                ('Mini Quiz', 'Categories include mixed, flags, years, capitals, tags, descriptions, basic data, and details. Questions appear in both directions.'),
                ('Review Mode', 'Missed countries enter the review list. Correct answers in review mode remove them from that list.'),
                ('Compare, Timeline, Map, Network', 'Compare places two countries side by side. Timeline sorts history, Map checks location, and Network follows related countries.'),
                ('Account and Sharing', 'The account page manages avatar, name color, backups, public favorites, and public collections. Passwords and personal notes are hidden from others.'),
                ('Power Battle', 'Unlocked after viewing every country. It uses area and population for power, with strong bonuses from matching tags and regions.'),
                ('Data Protection', 'Export a backup from the account page before redeploying or changing environments.'),
            ],
        },
        'zh': {
            'title': 'World Archives详细说明',
            'intro': '这里按功能说明用途。看完简易指南后，想了解细节时使用这一页。',
            'sections': [
                ('登录与保存', '普通账号会保存收藏、浏览记录、笔记、收藏集、测验结果和对战记录。访客登录用于快速试用。'),
                ('搜索与筛选', '可以按名称、地区、标签、语言、宗教、说明和基本数据搜索。先选标签分类可以减少标签候选。'),
                ('详情页', '基本资料包含首都、成立年代、人口、面积、语言和宗教。说明、地图、笔记和相关国家用标签页切换。'),
                ('小测验', '包括综合、旗帜、年代、首都、标签、说明、基本数据和详细资料。题目会同时出现正向和反向形式。'),
                ('复习模式', '答错的国家会进入复习列表。在复习模式答对后，会从列表中移除。'),
                ('比较、年表、地图、网络', '比较用于并排查看两个国家，年表按时代整理，地图确认位置，网络查看相关国家。'),
                ('账号与共享', '账号页可以管理头像、名字颜色、备份、公开收藏和公开收藏集。密码和个人笔记不会公开。'),
                ('国力对战', '浏览所有国家后解锁。根据面积和人口计算国力，标签或地区一致会得到强力加成。'),
                ('数据保护', '重新部署或更换环境前，建议从账号页导出备份。'),
            ],
        },
    }
    return labels.get(state.lang, labels['en'])

def current_user_backup_payload():
    if not state.current_user:
        return None
    user_data = load_user_data()
    user = user_data.get('users', {}).get(state.current_user)
    if not user:
        return None
    ensure_user_defaults(user)
    return {
        'username': state.current_user,
        'record': user,
        'updated_at': current_timestamp(),
    }

def safe_backup_filename(username):
    safe_name = ''.join(ch if ch.isalnum() else '_' for ch in (username or 'user'))[:40] or 'user'
    return f'world_archives_backup_{safe_name}.json'

def export_current_user_backup():
    labels = backup_labels()
    payload = current_user_backup_payload()
    if not payload:
        ui.notify(t('login_required'), color='warning')
        return
    data_text = json.dumps(payload, ensure_ascii=False, indent=2)
    filename = safe_backup_filename(payload['username'])
    script = f"""
    (() => {{
      const data = {json.dumps(data_text)};
      const blob = new Blob([data], {{type: 'application/json;charset=utf-8'}});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = {json.dumps(filename)};
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }})();
    """
    ui.run_javascript(script)
    sync_current_user_to_browser()
    ui.notify(labels['exported'], color='positive')

def normalize_backup_payload(payload):
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {}
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get('users'), dict):
        return {
            username: {'record': user_record_from_candidate(record)}
            for username, record in payload['users'].items()
            if user_record_from_candidate(record)
        }
    if isinstance(payload.get('users'), list):
        restored = {}
        for item in payload['users']:
            if not isinstance(item, dict):
                continue
            username = clean_username(item.get('username') or item.get('name') or item.get('id'))
            record = user_record_from_candidate(item)
            if username and record:
                restored[username] = {'record': record}
        return restored
    if payload.get('username') and isinstance(payload.get('record'), dict):
        record = user_record_from_candidate(payload.get('record'))
        return {payload['username']: {'record': record}} if record else {}
    if payload.get('username') and looks_like_user_record(payload):
        username = payload.get('username')
        record = dict(payload)
        record.pop('username', None)
        record.pop('updated_at', None)
        return {username: {'record': record}}
    restored = {}
    for username, value in payload.items():
        record = user_record_from_candidate(value)
        if record:
            restored[username] = {'record': record}
    if not restored:
        record = user_record_from_candidate(payload)
        if record:
            username = clean_username(payload.get('username') or payload.get('name') or payload.get('id') or GUEST_USERNAME)
            restored[username] = {'record': record}
    return restored

def apply_restored_progress_snapshot(user, record):
    if not isinstance(user, dict) or not isinstance(record, dict):
        return
    if isinstance(record.get('viewed_keys'), list):
        user['viewed_keys'] = merge_unique_list([], record.get('viewed_keys', []))
    for key in [
        'battle_unlocked',
        'battle_unlocked_notified',
        'sengoku_unlocked',
        'sengoku_unlocked_notified',
        'sengoku_mode',
        'sengoku_medal',
        'all_viewed_granted',
    ]:
        if key in record and isinstance(record.get(key), bool):
            user[key] = bool(record.get(key))
    touched_progress = any(
        key in record
        for key in [
            'viewed_keys',
            'quiz_stats',
            'quiz_history',
            'battle_unlocked',
            'sengoku_unlocked',
            'sengoku_mode',
            'all_viewed_granted',
        ]
    )
    if not touched_progress:
        return
    viewed = set(user.get('viewed_keys', []))
    all_needed = set(all_public_country_keys())
    present_needed = set(battle_unlock_country_keys())
    stats = normalize_quiz_stats(user)
    all_viewed = bool(all_needed) and all_needed.issubset(viewed)
    battle_allowed = (
        (bool(present_needed) and present_needed.issubset(viewed))
        or int(stats.get('correct', 0) or 0) >= 100
    )
    sengoku_allowed = battle_allowed and (all_viewed or sengoku_quiz_streak(user) >= 20)
    user['all_viewed_granted'] = all_viewed
    if not battle_allowed:
        user['battle_unlocked'] = False
        user['battle_unlocked_notified'] = False
    if not sengoku_allowed:
        user['sengoku_unlocked'] = False
        user['sengoku_unlocked_notified'] = False
        user['sengoku_mode'] = False
        user['sengoku_medal'] = False
        user['sengoku_boss_clears'] = []

def restore_user_backup_payload(payload, target_username=None, target_password=None, import_mode=False):
    target_username = clean_username(target_username)
    target_password = str(target_password or '')
    known_from_payload = []
    if isinstance(payload, dict) and isinstance(payload.get('known_users'), list):
        known_from_payload = [clean_username(username) for username in payload['known_users']]
    backups = normalize_backup_payload(payload)
    user_data = load_user_data()
    users = user_data.setdefault('users', {})
    for username in known_from_payload:
        remember_known_user(username, user_data)
    restored = 0
    for raw_username, backup in backups.items():
        if not isinstance(backup, dict):
            continue
        record = user_record_from_candidate(backup)
        if not record:
            continue
        username = clean_username(raw_username)
        if is_guest_record(username, record):
            if not target_username:
                if not import_mode:
                    continue
                username = guest_username_from_id(str(uuid.uuid4()))
                record = dict(record)
                record['is_guest'] = True
            else:
                username = target_username
                record = dict(record)
                record['is_guest'] = is_guest_record(target_username)
                if target_password and not record.get('password_hash') and not is_guest_record(target_username):
                    record['password_hash'] = password_hash(target_username, target_password)
        if not username:
            continue
        if target_username and username == target_username and target_password and not record.get('password_hash') and not is_guest_record(username):
            record = dict(record)
            record['password_hash'] = password_hash(username, target_password)
        remember_known_user(username, user_data)
        existing = users.get(username, {})
        existing_password_hash = ''
        if not is_guest_record(username, existing) and isinstance(existing, dict):
            existing_password_hash = str(existing.get('password_hash') or '')
        if (
            not is_guest_record(username, existing)
            and not (isinstance(existing, dict) and existing.get('password_hash'))
            and not record.get('password_hash')
        ):
            continue
        users[username] = merge_user_record(users.get(username, {}), record)
        if not is_guest_record(username, users[username]):
            if target_username and username == target_username and target_password:
                users[username]['password_hash'] = password_hash(username, target_password)
            elif existing_password_hash:
                users[username]['password_hash'] = existing_password_hash
            elif record.get('password_hash'):
                users[username]['password_hash'] = record['password_hash']
        apply_restored_progress_snapshot(users[username], record)
        ensure_user_defaults(users[username])
        restored += 1
    if restored or known_from_payload:
        save_user_data(user_data)
        if state.current_user in users:
            sync_current_user_to_browser(user_data)
    return restored

async def await_if_needed(value):
    if inspect.isawaitable(value):
        return await value
    return value

async def read_file_like_upload(source):
    if source is None or not hasattr(source, 'read'):
        return None
    if hasattr(source, 'seek'):
        try:
            await await_if_needed(source.seek(0))
        except Exception:
            pass
    return await await_if_needed(source.read())

async def read_backup_upload_text(event):
    content = getattr(event, 'content', None)
    raw = None
    if isinstance(content, str):
        return content
    if isinstance(content, (bytes, bytearray)):
        raw = bytes(content)
    else:
        raw = await read_file_like_upload(content)
    if raw is None and hasattr(event, 'file'):
        raw = await read_file_like_upload(getattr(event, 'file'))
    if raw is None:
        raw = getattr(event, 'bytes', None) or getattr(event, 'data', None) or getattr(event, 'value', None)
        raw = await await_if_needed(raw)
    if isinstance(raw, str):
        return raw
    if isinstance(raw, bytearray):
        raw = bytes(raw)
    if isinstance(raw, bytes):
        for encoding in ['utf-8-sig', 'utf-8', 'cp932']:
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
    raise ValueError(f'Unsupported upload content: {type(content).__name__}')

def parse_backup_json(raw):
    raw = str(raw or '').lstrip('\ufeff').strip()
    if not raw:
        raise ValueError('Backup file is empty')
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        starts = [index for index in [raw.find('{'), raw.find('[')] if index >= 0]
        ends = [index for index in [raw.rfind('}'), raw.rfind(']')] if index >= 0]
        if not starts or not ends:
            raise
        start = min(starts)
        end = max(ends)
        if start > end:
            raise
        return json.loads(raw[start:end + 1])

async def import_user_backup_file(event, target_username=None, target_password=None, refresh_after=True, login_after=False):
    labels = backup_labels()
    try:
        raw = await read_backup_upload_text(event)
        payload = parse_backup_json(raw)
        explicit_target = clean_username(target_username)
        target = explicit_target if explicit_target else state.current_user
        restored = restore_user_backup_payload(
            payload,
            target_username=target,
            target_password=target_password,
            import_mode=True,
        )
    except Exception as e:
        filename = getattr(event, 'name', '') or getattr(event, 'filename', '')
        print(f'Backup import failed: {filename} / {e}', flush=True)
        ui.notify(labels['invalid'], color='negative')
        return 0
    if restored:
        ui.notify(labels['imported'], color='positive')
        if login_after and target and target_password:
            login_user(target, target_password)
            return restored
        if refresh_after and state.current_user:
            refresh_account_view()
    else:
        ui.notify(labels['invalid'], color='warning')
    return restored

def enter_restored_guest(guest_username):
    user_data = load_user_data()
    guest = get_users(user_data).get(guest_username)
    if not guest:
        return False
    guest['is_guest'] = True
    state.current_user = guest_username
    state.users_browser_restore_requested = False
    ensure_user_defaults(guest)
    unlocked_now = mark_battle_unlock_if_ready(guest)
    sengoku_unlocked_now = mark_sengoku_unlock_if_ready(guest)
    state.sengoku_mode = bool(guest.get('sengoku_mode') and guest.get('sengoku_unlocked'))
    persist_current_user_data(user_data)
    reset_social_notification_state()
    if unlocked_now:
        ui.notify(t('battle_unlocked_notice'), color='positive')
    if sengoku_unlocked_now:
        ui.notify(t('sengoku_unlocked_notice'), color='positive')
    show_screen('top')
    return True

async def import_guest_backup_file(event):
    guest_id = str(uuid.uuid4())
    guest_username = guest_username_from_id(guest_id)
    try:
        ui.run_javascript(f"localStorage.setItem('{GUEST_BROWSER_KEY}', {json.dumps(guest_id)});")
    except Exception as e:
        print(f"Guest id browser save skipped: {e}", flush=True)
    restored = await import_user_backup_file(
        event,
        target_username=guest_username,
        refresh_after=False,
    )
    if restored:
        enter_restored_guest(guest_username)

def restore_from_browser_backup():
    labels = backup_labels()
    request_browser_backup_restore()
    ui.notify(labels['restore_browser'], color='info')

def current_user_label():
    if is_guest_record(state.current_user):
        return t('guest_user')
    return state.current_user or ''

def user_badge_marks(user):
    if not isinstance(user, dict):
        return ''
    marks = []
    if user.get('sengoku_unlocked'):
        marks.append('👹')
    if user.get('sengoku_medal'):
        marks.append('🏅')
    if all_sengoku_bosses_cleared(user):
        marks.append('🏅')
    unique_marks = []
    for mark in marks:
        if mark not in unique_marks:
            unique_marks.append(mark)
    return ''.join(unique_marks)

def display_user_name(username, user=None):
    name = str(username or '').strip()
    marks = user_badge_marks(user)
    return f'{name} {marks}'.strip()

def current_user_display_name(user=None):
    return display_user_name(current_user_label(), user)

def icon_label(text, icon, label_classes='font-bold text-[#1a2332]', icon_classes='text-blue-600', row_classes='items-center gap-2'):
    with ui.row().classes(row_classes):
        ui.icon(icon).classes(icon_classes)
        label = ui.label(text).classes(label_classes)
    return label

def page_heading(text, icon):
    return icon_label(
        text,
        icon,
        'text-3xl font-bold text-[#1a2332]',
        'text-blue-600',
        'w-full items-center gap-3',
    )

def info_field(label, value, icon='info', value_classes='text-lg text-gray-800'):
    with ui.column().classes('gap-1'):
        icon_label(
            label,
            icon,
            'text-xs font-bold text-gray-400 uppercase',
            'text-blue-400',
            'items-center gap-1',
        )
        ui.label(value).classes(value_classes)

def profile_row_icon(label):
    label_text = str(label or '')
    icon_map = {
        t('labels', 'population'): 'groups',
        t('labels', 'area'): 'square_foot',
        t('labels', 'languages'): 'translate',
        t('labels', 'religions'): 'church',
    }
    return icon_map.get(label_text, 'fact_check')

def country_field_icon(label):
    label_text = str(label or '')
    if label_text == t('labels', 'capital'):
        return 'location_city'
    if label_text == t('labels', 'region'):
        return 'public'
    if label_text == t('labels', 'tags'):
        return 'sell'
    if label_text == t('labels', 'desc'):
        return 'article'
    if label_text in [t('labels', 'population'), t('labels', 'area'), t('labels', 'languages'), t('labels', 'religions')]:
        return profile_row_icon(label_text)
    return 'event'

def sengoku_boss_definitions():
    return [
        {
            'id': 'boss_1',
            'name': {'ja': 'アッカド帝国', 'en': 'Akkadian Empire', 'zh': '阿卡德帝国'},
            'summary': {'ja': '最初期の大帝国を冠する第一戦。戦国モード強化BOTの基本形です。', 'en': 'The first boss, named after one of the earliest empires. A standard enhanced BOT.', 'zh': '以早期大帝国命名的第一战。强化BOT的基础形态。'},
            'mode': BOT_MODE,
            'enemy_count': 1,
            'hp_multiplier': 1,
            'bot_hp_percent': 70,
            'bot_card_limit': 2,
            'bot_choice_pool': 4,
            'bot_strategy': 'training',
            'player_hand_bonus': 1,
            'timeout': 180,
            'forced_events': [],
        },
        {
            'id': 'boss_2',
            'name': {'ja': 'アケメネス朝ペルシア', 'en': 'Achaemenid Persia', 'zh': '阿契美尼德波斯'},
            'summary': {'ja': '敵HPが10倍。6つの属州シールドが残り1つにつきダメージを10%軽減します。対応する地域共鳴を3回当てるとその州が崩れ、敵HP上限を永久に15%下げます。王の道は低頻度で少しだけ回復します。', 'en': 'Enemy HP is 10x. Each remaining satrapy shield reduces damage by 10%. Three matching regional resonances break that province and permanently lower max HP by 15%. Royal Road supplies heal a little and less often.', 'zh': '敌方HP为10倍。每个尚存行省护盾会减少10%伤害。对应地域共鸣命中三次后会击破该行省，并永久降低敌方HP上限15%。王道补给频率较低且回复较少。'},
            'mode': BOT_MODE,
            'enemy_count': 1,
            'hp_multiplier': 10,
            'satrapy_provinces': [province['id'] for province in BATTLE_SATRAPY_PROVINCES],
            'satrapy_shield_hits': 3,
            'satrapy_hp_drop_percent': 15,
            'satrapy_guard_card_limit': 1,
            'royal_road_interval': 5,
            'royal_road_heal_percent': 2,
            'timeout': 180,
            'forced_events': ['lytton'],
        },
        {
            'id': 'boss_3',
            'name': {'ja': 'ローマ帝国', 'en': 'Roman Empire', 'zh': '罗马帝国'},
            'summary': {'ja': '地中海世界の巨大帝国。常時バチカン市国大量発生と補給投下が起こり、敵のバチカン市国は別カードへ変化します。', 'en': 'A Mediterranean superpower. Vatican outbreak and Supply Drop stay active, but the boss converts its Vatican cards.', 'zh': '地中海世界的巨大帝国。梵蒂冈大量出现与补给投下常驻，但敌方会把梵蒂冈卡变成其他卡。'},
            'mode': BOT_MODE,
            'enemy_count': 1,
            'hp_multiplier': 1,
            'bot_card_limit': 1,
            'bot_choice_pool': 12,
            'bot_strategy': 'training',
            'timeout': 180,
            'forced_events': ['vatican', 'supply_drop'],
            'vatican_immunity': True,
        },
        {
            'id': 'boss_4',
            'name': {'ja': '唐', 'en': 'Tang Dynasty', 'zh': '唐'},
            'summary': {'ja': '東アジアの大帝国。常時海上封鎖が発生し、制限時間は30秒です。', 'en': 'A major East Asian empire. Naval Blockade is always active and turns last 30 seconds.', 'zh': '东亚大帝国。海上封锁常驻，每回合限时30秒。'},
            'mode': BOT_MODE,
            'enemy_count': 1,
            'hp_multiplier': 1,
            'player_hand_bonus': 1,
            'timeout': 60,
            'forced_events': ['blockade', 'damage_surge'],
        },
        {
            'id': 'boss_5',
            'name': {'ja': 'モンゴル帝国', 'en': 'Mongol Empire', 'zh': '蒙古帝国'},
            'summary': {'ja': 'ユーラシアを横断した超巨大帝国。味方BOTを含む2対2のチーム戦で、常に国名が伏せられます。敵チームHPは半分です。', 'en': 'A trans-Eurasian empire. This is a 2v2 team battle with an allied BOT and hidden country names. The enemy team has half HP.', 'zh': '横跨欧亚的超大帝国。包含友方BOT的2对2团队战，国名常时隐藏。敌队HP减半。'},
            'mode': TEAM_MODE,
            'enemy_count': 2,
            'player_ally_count': 1,
            'hp_multiplier': 1,
            'enemy_team_hp_percent': 50,
            'timeout': 180,
            'forced_events': ['flag_only', 'random_target'],
        },
        {
            'id': 'boss_6',
            'name': {'ja': 'オスマン帝国', 'en': 'Ottoman Empire', 'zh': '奥斯曼帝国'},
            'summary': {'ja': '長く続いた三大陸の帝国。革命・停戦・カードシャッフルが常に発生します。', 'en': 'A long-lived empire across three continents. Revolution, Ceasefire, and card redistribution stay active.', 'zh': '横跨三大洲的长寿帝国。革命、停战与卡牌再分配常驻。'},
            'mode': BOT_MODE,
            'enemy_count': 1,
            'hp_multiplier': 1,
            'timeout': 180,
            'forced_events': ['revolution', 'ceasefire', 'replace'],
        },
        {
            'id': 'boss_7',
            'name': {'ja': '大英帝国', 'en': 'British Empire', 'zh': '大英帝国'},
            'summary': {'ja': '世界規模の海洋帝国。常時第三次世界大戦状態で、暴発カードが多く混じり、敵は2回行動します。', 'en': 'A global maritime empire. World War is always active, dangerous cards appear more often, and the boss acts twice.', 'zh': '世界规模的海洋帝国。第三次世界大战状态常驻，危险卡更多，敌方会行动两次。'},
            'mode': BOT_MODE,
            'enemy_count': 1,
            'hp_multiplier': 1,
            'timeout': 180,
            'forced_events': ['world_war'],
            'special_pressure': True,
            'enemy_extra_actions': 2,
        },
        {
            'id': 'boss_8',
            'name': {'ja': 'ソビエト連邦', 'en': 'Soviet Union', 'zh': '苏联'},
            'summary': {'ja': '最後に立ちはだかる近現代の超大国。全イベント級の混沌、3ターンごとの爆弾、敵HP10倍、2回行動、属州シールド、王の道、指揮力無限が襲いかかります。味方側にも支援BOTとHP・手札・指揮力補助があります。', 'en': 'The final modern superpower boss. Nearly every event is active, bombs recur every 3 turns, and the enemy has 10x HP, double actions, satrapy shields, Royal Road supplies, and effectively infinite command. Your side gains an ally BOT and HP, hand, and command support.', 'zh': '最终的近现代超级大国。几乎所有事件常驻，炸弹每3回合出现，敌方拥有10倍HP、两次行动、行省护盾、王道补给和近乎无限的指挥力。己方也会获得友方BOT，以及HP、手牌和指挥力支援。'},
            'mode': TEAM_MODE,
            'enemy_count': 3,
            'player_ally_count': 1,
            'hp_multiplier': 10,
            'enemy_team_hp_multiplier': 10,
            'player_team_hp_multiplier': 5,
            'player_hand_bonus': 1,
            'player_command_bonus': 1,
            'timeout': 30,
            'forced_events': ['world_war', 'vatican', 'supply_drop', 'blockade', 'flag_only', 'revolution', 'ceasefire', 'replace', 'lytton', 'damage_surge', 'random_target', 'command_surge'],
            'bomb_every_turns': 3,
            'satrapy_provinces': [province['id'] for province in BATTLE_SATRAPY_PROVINCES],
            'satrapy_shield_hits': 3,
            'satrapy_hp_drop_percent': 15,
            'satrapy_guard_card_limit': 1,
            'royal_road_interval': 5,
            'royal_road_heal_percent': 2,
            'enemy_extra_actions': 2,
            'vatican_immunity': True,
            'special_pressure': True,
            'command_infinite': True,
        },
    ]

def sengoku_boss_by_id(boss_id):
    boss_id = str(boss_id or '')
    for boss in sengoku_boss_definitions():
        if boss['id'] == boss_id:
            return boss
    return None

def localized_boss_text(boss, key):
    value = (boss or {}).get(key, {})
    if isinstance(value, dict):
        return value.get(state.lang, value.get('ja', value.get('en', '')))
    return str(value or '')

def normalize_sengoku_boss_clears(value):
    valid = [boss['id'] for boss in sengoku_boss_definitions()]
    seen = set()
    clears = []
    for boss_id in value if isinstance(value, list) else []:
        boss_id = str(boss_id or '')
        if boss_id in valid and boss_id not in seen:
            clears.append(boss_id)
            seen.add(boss_id)
    return clears

def sengoku_boss_clear_count(user):
    return len(normalize_sengoku_boss_clears((user or {}).get('sengoku_boss_clears', [])))

def sengoku_boss_is_cleared(user, boss_id):
    return str(boss_id or '') in normalize_sengoku_boss_clears((user or {}).get('sengoku_boss_clears', []))

def sengoku_boss_is_unlocked(user, boss_id):
    bosses = sengoku_boss_definitions()
    ids = [boss['id'] for boss in bosses]
    if boss_id not in ids:
        return False
    return ids.index(boss_id) <= sengoku_boss_clear_count(user)

def all_sengoku_bosses_cleared(user):
    return sengoku_boss_clear_count(user) >= len(sengoku_boss_definitions())

def next_sengoku_boss_id(boss_id):
    ids = [boss['id'] for boss in sengoku_boss_definitions()]
    boss_id = str(boss_id or '')
    if boss_id not in ids:
        return None
    index = ids.index(boss_id) + 1
    return ids[index] if index < len(ids) else None

def show_staff_roll():
    credits = [
        ('総監督', 'あかとんぼ'),
        ('発案', 'あかとんぼ'),
        ('企画', 'あかとんぼ'),
        ('編纂', 'あかとんぼ'),
        ('歴史資料監修', 'あかとんぼ'),
        ('国旗収集', 'あかとんぼ'),
        ('地図導線設計', 'あかとんぼ'),
        ('ミニクイズ構成', 'あかとんぼ'),
        ('国力対戦原案', 'あかとんぼ'),
        ('戦国モード設計', 'あかとんぼ'),
        ('タグ分類方針', 'あかとんぼ'),
        ('ユーザー機能構想', 'あかとんぼ'),
        ('面接発表準備', 'あかとんぼ'),
        ('最後まで粘った人', 'あかとんぼ'),
    ]
    references = [
        'Wikipedia',
        'Google Maps',
        'Wikimedia Commons',
        'flagcdn.com',
        'CIA World Factbook',
        'World Bank Open Data',
    ]
    with ui.dialog() as dialog, ui.card().classes('wa-staff-roll-window w-full max-w-3xl p-0'):
        ui.button(icon='close', on_click=dialog.close).props('flat round color=white') \
            .classes('absolute top-2 right-2 z-10')
        with ui.column().classes('wa-staff-roll-scroll w-full px-8 py-10 gap-1'):
            ui.label(t('staff_roll_title')).classes('text-4xl font-black text-white mb-8')
            ui.label('戦国ボス八将 完全制覇').classes('text-2xl font-black text-yellow-200 mb-8')
            for role, name in credits:
                ui.label(role).classes('text-sm font-bold text-blue-200 mt-3')
                ui.label(name).classes('text-2xl font-black text-white')
            ui.label(t('staff_roll_source_heading')).classes('text-xl font-black text-yellow-200 mt-12 mb-3')
            for source in references:
                ui.label(source).classes('text-lg font-bold text-white')
            ui.label('協力').classes('text-sm font-bold text-blue-200 mt-12')
            ui.label('Codex').classes('text-3xl font-black text-white mb-16')
        ui.button(t('staff_roll_close'), icon='close', on_click=dialog.close).props('outline color=white') \
            .classes('absolute bottom-3 right-3 z-10')
    dialog.open()

def login_user(username, password):
    username = clean_username(username)
    if not username or not password:
        ui.notify(t('auth_missing'), color='warning')
        return False
    user_data = load_user_data()
    user = get_users(user_data).get(username)
    if user and not is_guest_record(username, user) and not user.get('password_hash'):
        user['password_hash'] = password_hash(username, password)
        ensure_user_defaults(user)
        save_user_data(user_data)
    if not user or user.get('password_hash') != password_hash(username, password):
        ui.notify(t('auth_invalid'), color='negative')
        return False
    state.current_user = username
    state.users_browser_restore_requested = False
    ensure_user_defaults(user)
    remember_known_user(username, user_data)
    unlocked_now = mark_battle_unlock_if_ready(user)
    sengoku_unlocked_now = mark_sengoku_unlock_if_ready(user)
    state.sengoku_mode = bool(user.get('sengoku_mode') and user.get('sengoku_unlocked'))
    persist_current_user_data(user_data)
    ui.timer(1.2, lambda: sync_current_user_to_browser(load_user_data()), once=True)
    reset_social_notification_state(show_existing=True)
    ui.notify(t('login_success'), color='positive')
    if unlocked_now:
        ui.notify(t('battle_unlocked_notice'), color='positive')
    if sengoku_unlocked_now:
        ui.notify(t('sengoku_unlocked_notice'), color='positive')
    show_screen('top')
    return True

async def guest_login():
    guest_username = await browser_guest_username()
    user_data = load_user_data()
    users = get_users(user_data)
    guest = users.setdefault(guest_username, {
        'password_hash': '',
        'favorites': [],
        'history': [],
        'notes': {},
        'viewed_keys': [],
        'collections': {},
        'quiz_history': [],
        'review_keys': [],
        'quiz_stats': {
            'answered': 0,
            'correct': 0,
            'streak': 0,
            'best_streak': 0,
        },
    })
    guest['is_guest'] = True
    state.current_user = guest_username
    state.users_browser_restore_requested = False
    ensure_user_defaults(guest)
    unlocked_now = mark_battle_unlock_if_ready(guest)
    sengoku_unlocked_now = mark_sengoku_unlock_if_ready(guest)
    state.sengoku_mode = bool(guest.get('sengoku_mode') and guest.get('sengoku_unlocked'))
    persist_current_user_data(user_data)
    reset_social_notification_state()
    ui.notify(t('guest_login_success'), color='positive')
    if unlocked_now:
        ui.notify(t('battle_unlocked_notice'), color='positive')
    if sengoku_unlocked_now:
        ui.notify(t('sengoku_unlocked_notice'), color='positive')
    show_screen('top')
    return True

def register_user(username, password):
    username = clean_username(username)
    if not username or not password:
        ui.notify(t('auth_missing'), color='warning')
        return False
    user_data = load_user_data()
    users = get_users(user_data)
    if is_guest_record(username):
        ui.notify(t('user_exists'), color='warning')
        return False
    existing_user = users.get(username)
    if isinstance(existing_user, dict) and not existing_user.get('password_hash') and not is_guest_record(username, existing_user):
        existing_user['password_hash'] = password_hash(username, password)
        ensure_user_defaults(existing_user)
        remember_known_user(username, user_data)
        state.current_user = username
        state.users_browser_restore_requested = False
        state.sengoku_mode = bool(existing_user.get('sengoku_mode') and existing_user.get('sengoku_unlocked'))
        persist_current_user_data(user_data)
        reset_social_notification_state()
        ui.notify(t('user_created'), color='positive')
        show_screen('top')
        return True
    if username in users:
        ui.notify(t('user_exists'), color='warning')
        return False
    users[username] = {
        'password_hash': password_hash(username, password),
        'favorites': [],
        'history': [],
        'notes': {},
        'viewed_keys': [],
        'collections': {},
        'quiz_history': [],
        'review_keys': [],
        'quiz_stats': {
            'answered': 0,
            'correct': 0,
            'streak': 0,
            'best_streak': 0,
        },
    }
    remember_known_user(username, user_data)
    state.current_user = username
    state.users_browser_restore_requested = False
    state.sengoku_mode = False
    persist_current_user_data(user_data)
    reset_social_notification_state()
    ui.notify(t('user_created'), color='positive')
    show_screen('top')
    return True

def logout_user():
    state.current_user = None
    state.users_browser_restore_requested = False
    state.selected_country = None
    state.search_keyword = ''
    state.filter_region = None
    state.filter_tag_group = None
    state.filter_tag = None
    state.sort_field = 'name'
    state.show_favorites_only = False
    state.favorite_filter = 'all'
    state.collection_filter = None
    state.page = 1
    state.social_notify_user = None
    state.social_notify_snapshot = None
    state.social_last_signature = ''
    state.social_selected_chat_id = None
    state.sengoku_mode = False
    ui.notify(t('logout_success'), color='info')
    show_screen('top')

def current_password_is_valid(user, password):
    if not state.current_user or not password:
        return False
    return user.get('password_hash') == password_hash(state.current_user, password)

def rename_current_account(new_username, current_password):
    old_username = state.current_user
    if not old_username:
        ui.notify(t('login_required'), color='warning')
        return False
    if is_guest_record(old_username):
        ui.notify(t('cannot_manage_guest'), color='warning')
        return False
    new_username = clean_username(new_username)
    if not new_username or not current_password:
        ui.notify(t('auth_missing'), color='warning')
        return False
    user_data = load_user_data()
    users = get_users(user_data)
    user = users.get(old_username)
    if not user or not current_password_is_valid(user, current_password):
        ui.notify(t('auth_invalid'), color='negative')
        return False
    if is_guest_record(new_username) or (new_username != old_username and new_username in users):
        ui.notify(t('user_exists'), color='warning')
        return False
    if new_username == old_username:
        ui.notify(t('account_updated'), color='info')
        return True
    remove_user_from_battle_state(old_username)
    record = users.pop(old_username)
    ensure_user_defaults(record)
    record['password_hash'] = password_hash(new_username, current_password)
    users[new_username] = record
    rename_user_references(user_data, old_username, new_username)
    remember_known_user(new_username, user_data)
    state.current_user = new_username
    state.battle_id = None
    state.battle_selected_keys = set()
    persist_current_user_data(user_data)
    remove_browser_backup(old_username)
    ui.notify(t('account_updated'), color='positive')
    refresh_current_screen()
    return True

def change_current_password(current_password, new_password):
    if not state.current_user:
        ui.notify(t('login_required'), color='warning')
        return False
    if is_current_user_guest():
        ui.notify(t('cannot_manage_guest'), color='warning')
        return False
    if not current_password or not new_password:
        ui.notify(t('auth_missing'), color='warning')
        return False
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user or not current_password_is_valid(user, current_password):
        ui.notify(t('auth_invalid'), color='negative')
        return False
    user['password_hash'] = password_hash(state.current_user, new_password)
    persist_current_user_data(user_data)
    ui.notify(t('password_changed'), color='positive')
    refresh_current_screen()
    return True

def delete_current_account(current_password):
    username = state.current_user
    if not username:
        ui.notify(t('login_required'), color='warning')
        return False
    if is_guest_record(username):
        ui.notify(t('cannot_manage_guest'), color='warning')
        return False
    if not current_password:
        ui.notify(t('password_required'), color='warning')
        return False
    user_data = load_user_data()
    users = get_users(user_data)
    user = users.get(username)
    if not user or not current_password_is_valid(user, current_password):
        ui.notify(t('auth_invalid'), color='negative')
        return False
    remove_user_from_battle_state(username)
    users.pop(username, None)
    remove_user_references(user_data, username)
    save_user_data(user_data)
    remove_browser_backup(username)
    state.current_user = None
    state.selected_country = None
    state.battle_id = None
    state.battle_selected_keys = set()
    ui.notify(t('account_deleted'), color='info')
    show_screen('top')
    return True

def set_current_name_color(color_value):
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        ui.notify(t('login_required'), color='warning')
        return False
    user['name_color'] = normalize_name_color(color_value)
    persist_current_user_data(user_data)
    ui.notify(t('name_color_saved'), color='positive')
    refresh_current_screen()
    return True

def set_current_public_visibility(hidden):
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        ui.notify(t('login_required'), color='warning')
        return False
    user['hide_public_profile'] = bool(hidden)
    persist_current_user_data(user_data, immediate_browser=True)
    state.public_users_browser_synced = False
    ui.notify(t('public_visibility_saved'), color='positive')
    refresh_current_screen()
    return True

def non_guest_usernames(user_data=None):
    user_data = user_data or load_user_data()
    users = get_users(user_data)
    return [
        username for username in users
        if username and not is_guest_record(username, users.get(username))
    ]

def ensure_friend_list(user):
    ensure_user_defaults(user)
    clean_friends = []
    for friend in user.get('friends', []):
        friend = clean_username(friend)
        if friend and not is_guest_record(friend) and friend not in clean_friends:
            clean_friends.append(friend)
    user['friends'] = clean_friends
    return clean_friends

def sync_friendship(user_data, first, second, add=True):
    users = get_users(user_data)
    first_user = users.get(first)
    second_user = users.get(second)
    if not first_user or not second_user:
        return False
    first_friends = ensure_friend_list(first_user)
    second_friends = ensure_friend_list(second_user)
    if add:
        if second not in first_friends:
            first_friends.append(second)
        if first not in second_friends:
            second_friends.append(first)
    else:
        if second in first_friends:
            first_friends.remove(second)
        if first in second_friends:
            second_friends.remove(first)
    return True

def friend_request_between(user_data, sender, receiver):
    for request in user_data.setdefault('friend_requests', []):
        if request.get('from') == sender and request.get('to') == receiver:
            return request
    return None

def remove_friend_request_between(user_data, first, second):
    user_data['friend_requests'] = [
        request for request in user_data.setdefault('friend_requests', [])
        if not (
            (request.get('from') == first and request.get('to') == second)
            or (request.get('from') == second and request.get('to') == first)
        )
    ]

def friend_status(target_username, user_data=None):
    current = state.current_user
    target = clean_username(target_username)
    if not current or not target or current == target:
        return 'self'
    user_data = user_data or load_user_data()
    current_user = get_users(user_data).get(current)
    if not current_user:
        return 'none'
    if target in ensure_friend_list(current_user):
        return 'friends'
    if friend_request_between(user_data, current, target):
        return 'sent'
    if friend_request_between(user_data, target, current):
        return 'received'
    return 'none'

def send_friend_request(target_username):
    current = state.current_user
    target = clean_username(target_username)
    if not current or is_guest_record(current):
        ui.notify(t('login_required'), color='warning')
        return False
    if not target or target == current:
        return False
    user_data = load_user_data()
    users = get_users(user_data)
    if target not in users or is_guest_record(target, users.get(target)):
        ui.notify(t('chat_not_allowed'), color='warning')
        return False
    status = friend_status(target, user_data)
    if status == 'friends':
        open_direct_chat(target)
        return True
    if status == 'received':
        return accept_friend_request(target)
    if status != 'sent':
        user_data.setdefault('friend_requests', []).append({
            'from': current,
            'to': target,
            'timestamp': current_timestamp(),
        })
    persist_current_user_data(user_data)
    ui.notify(t('friend_request_sent_notice'), color='positive')
    refresh_current_screen()
    return True

def accept_friend_request(sender_username):
    current = state.current_user
    sender = clean_username(sender_username)
    if not current or not sender:
        return False
    user_data = load_user_data()
    if not friend_request_between(user_data, sender, current):
        return False
    sync_friendship(user_data, current, sender, add=True)
    remove_friend_request_between(user_data, current, sender)
    ensure_direct_chat_record(user_data, current, sender)
    persist_current_user_data(user_data)
    ui.notify(t('friend_request_accepted_notice'), color='positive')
    refresh_current_screen()
    return True

def reject_friend_request(other_username):
    current = state.current_user
    other = clean_username(other_username)
    if not current or not other:
        return False
    user_data = load_user_data()
    remove_friend_request_between(user_data, current, other)
    persist_current_user_data(user_data)
    ui.notify(t('friend_request_rejected_notice'), color='info')
    refresh_current_screen()
    return True

def remove_friend(other_username):
    current = state.current_user
    other = clean_username(other_username)
    if not current or not other:
        return False
    user_data = load_user_data()
    sync_friendship(user_data, current, other, add=False)
    remove_friend_request_between(user_data, current, other)
    persist_current_user_data(user_data)
    refresh_current_screen()
    return True

def ensure_direct_chat_record(user_data, first, second):
    chat_id = social_chat_id([first, second], 'direct')
    chats = user_data.setdefault('chats', {})
    if chat_id not in chats:
        chats[chat_id] = {
            'id': chat_id,
            'type': 'direct',
            'name': '',
            'created_by': first,
            'members': sorted([first, second], key=lambda value: value.lower()),
            'messages': [],
            'created_at': current_timestamp(),
        }
    return chat_id

def open_direct_chat(target_username):
    current = state.current_user
    target = clean_username(target_username)
    if not current or not target:
        ui.notify(t('login_required'), color='warning')
        return False
    user_data = load_user_data()
    if friend_status(target, user_data) != 'friends':
        ui.notify(t('chat_not_allowed'), color='warning')
        return False
    state.social_selected_chat_id = ensure_direct_chat_record(user_data, current, target)
    persist_current_user_data(user_data)
    show_screen('social')
    return True

def parse_group_members(text):
    raw_items = re.split(r'[,、\s]+', str(text or ''))
    members = []
    for item in raw_items:
        username = clean_username(item)
        if username and username not in members:
            members.append(username)
    return members

def create_group_chat(group_name, member_text):
    current = state.current_user
    if not current or is_guest_record(current):
        ui.notify(t('login_required'), color='warning')
        return False
    user_data = load_user_data()
    current_user = get_current_user_record(user_data)
    friend_set = set(ensure_friend_list(current_user)) if current_user else set()
    requested = parse_group_members(member_text)
    members = [current]
    for member in requested:
        if member in friend_set and member not in members:
            members.append(member)
    if len(members) < 2:
        ui.notify(t('chat_not_allowed'), color='warning')
        return False
    chats = user_data.setdefault('chats', {})
    chat_id = social_chat_id(members, 'group')
    while chat_id in chats:
        chat_id = f"{social_chat_id(members, 'group')}:{random.randint(1000, 9999)}"
    chats[chat_id] = {
        'id': chat_id,
        'type': 'group',
        'name': str(group_name or '').strip() or t('group_chat'),
        'created_by': current,
        'members': members,
        'messages': [],
        'created_at': current_timestamp(),
    }
    state.social_selected_chat_id = chat_id
    persist_current_user_data(user_data)
    ui.notify(t('chat_created'), color='positive')
    refresh_current_screen()
    return True

def current_user_chats(user_data=None):
    current = state.current_user
    if not current:
        return []
    user_data = user_data or load_user_data()
    chats = normalize_social_chats(user_data.get('chats'))
    items = [
        chat for chat in chats.values()
        if current in chat.get('members', [])
    ]
    return sorted(
        items,
        key=lambda chat: chat.get('messages', [{}])[-1].get('timestamp') if chat.get('messages') else chat.get('created_at', ''),
        reverse=True,
    )

def social_chat_title(chat):
    if chat.get('type') == 'group':
        return chat.get('name') or t('group_chat')
    other_members = [member for member in chat.get('members', []) if member != state.current_user]
    return other_members[0] if other_members else t('direct_chat')

def social_activity_snapshot(username=None, user_data=None):
    username = username or state.current_user
    if not username:
        return {'requests': [], 'chats': []}
    user_data = user_data or load_user_data()
    incoming = [
        {
            'from': request.get('from', ''),
            'timestamp': request.get('timestamp', ''),
        }
        for request in user_data.setdefault('friend_requests', [])
        if request.get('to') == username
    ]
    chats = []
    for chat in current_user_chats(user_data):
        messages = chat.get('messages', [])
        last_message = messages[-1] if messages else {}
        chats.append({
            'id': chat.get('id', ''),
            'type': chat.get('type', 'direct'),
            'name': social_chat_title(chat),
            'members': sorted(chat.get('members', [])),
            'created_at': chat.get('created_at', ''),
            'created_by': chat.get('created_by', ''),
            'message_count': len(messages),
            'last_user': last_message.get('user', ''),
            'last_timestamp': last_message.get('timestamp', ''),
        })
    return {
        'requests': sorted(incoming, key=lambda item: (item.get('from', ''), item.get('timestamp', ''))),
        'chats': sorted(chats, key=lambda item: item.get('id', '')),
    }

def social_activity_signature(snapshot=None):
    snapshot = snapshot or social_activity_snapshot()
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True)

def open_social_notification_target(chat_id=None):
    if chat_id:
        state.social_selected_chat_id = str(chat_id)
    show_screen('social')

def current_notifications(user=None):
    user = user or get_current_user_record()
    if not user:
        return []
    user['notifications'] = normalize_notifications(user.get('notifications'))
    return user['notifications']

def unread_notification_count(user=None):
    return sum(1 for item in current_notifications(user) if not item.get('read'))

def notification_event_id(event):
    raw_id = str(event.get('id') or '').strip()
    if raw_id:
        return raw_id
    marker = f"{event.get('kind', 'social')}:{event.get('chat_id', '')}:{event.get('created_at', '')}:{event.get('message', '')}"
    return hashlib.sha256(marker.encode('utf-8')).hexdigest()[:16]

def store_notification_events(events, username=None):
    username = username or state.current_user
    if not username or is_guest_record(username):
        return []
    user_data = load_user_data()
    user = get_named_user_record(username, user_data)
    if not user:
        return []
    notifications = current_notifications(user)
    seen = {item.get('id') for item in notifications}
    added = []
    for event in events:
        message = str(event.get('message') or '').strip()
        if not message:
            continue
        item = {
            'id': notification_event_id(event),
            'message': message,
            'chat_id': str(event.get('chat_id') or '').strip(),
            'kind': str(event.get('kind') or 'social').strip() or 'social',
            'created_at': str(event.get('created_at') or current_timestamp()),
            'read': False,
        }
        if item['id'] in seen:
            continue
        notifications.insert(0, item)
        seen.add(item['id'])
        added.append(item)
    if added:
        user['notifications'] = normalize_notifications(notifications)
        persist_current_user_data(user_data) if username == state.current_user else save_user_data(user_data)
    return added

def mark_notification_read(notification_id=None, mark_all=False):
    if not state.current_user or is_current_user_guest():
        return
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        return
    changed = False
    for item in current_notifications(user):
        if mark_all or item.get('id') == notification_id:
            if not item.get('read'):
                item['read'] = True
                changed = True
    if changed:
        persist_current_user_data(user_data)

def open_notification_item(notification):
    notification_id = notification.get('id')
    chat_id = notification.get('chat_id') or None
    mark_notification_read(notification_id)
    notification_drawer.hide()
    open_social_notification_target(chat_id)

def show_social_action_notification(message, chat_id=None, notification_id=None):
    ui.notify(message, color='info')
    def open_from_dialog():
        if notification_id:
            mark_notification_read(notification_id)
        dialog.close()
        open_social_notification_target(chat_id)

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md p-5 gap-4'):
        ui.label(message).classes('text-base font-bold text-[#1a2332]')
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button(t('dismiss_notification'), on_click=dialog.close).props('flat color=grey')
            ui.button(
                t('open_notification_target'),
                icon='open_in_new',
                on_click=open_from_dialog,
            ).props('color=primary')
    dialog.open()

def social_notification_events(previous, current):
    if not previous:
        return []
    events = []
    previous_requests = {
        (request.get('from'), request.get('timestamp'))
        for request in previous.get('requests', [])
    }
    for request in current.get('requests', []):
        marker = (request.get('from'), request.get('timestamp'))
        if marker not in previous_requests:
            events.append({
                'id': f"friend-request:{request.get('from', '')}:{request.get('timestamp', '')}",
                'kind': 'friend_request',
                'message': t('friend_request_incoming_notice').format(user=request.get('from', '')),
                'chat_id': None,
                'created_at': request.get('timestamp') or current_timestamp(),
            })

    previous_chats = {chat.get('id'): chat for chat in previous.get('chats', [])}
    for chat in current.get('chats', []):
        chat_id = chat.get('id')
        old = previous_chats.get(chat_id)
        if not old:
            if chat.get('created_by') != state.current_user:
                label_key = 'new_group_chat_notice' if chat.get('type') == 'group' else 'new_direct_chat_notice'
                events.append({
                    'id': f"chat-created:{chat_id}:{chat.get('created_at', '')}",
                    'kind': 'chat',
                    'message': t(label_key).format(name=chat.get('name') or t('direct_chat')),
                    'chat_id': chat_id,
                    'created_at': chat.get('created_at') or current_timestamp(),
                })
            continue
        if (
            chat.get('message_count', 0) > old.get('message_count', 0)
            and chat.get('last_user')
            and chat.get('last_user') != state.current_user
        ):
            events.append({
                'id': f"chat-message:{chat_id}:{chat.get('last_user', '')}:{chat.get('last_timestamp', '')}:{chat.get('message_count', 0)}",
                'kind': 'chat_message',
                'message': t('new_chat_message_notice').format(name=chat.get('name') or t('direct_chat')),
                'chat_id': chat_id,
                'created_at': chat.get('last_timestamp') or current_timestamp(),
            })
    return events

def social_notification_messages(previous, current):
    return [event['message'] for event in social_notification_events(previous, current)]

def reset_social_notification_state(show_existing=False):
    if not state.current_user:
        state.social_notify_user = None
        state.social_notify_snapshot = None
        state.social_last_signature = ''
        return
    snapshot = social_activity_snapshot()
    state.social_notify_user = state.current_user
    state.social_notify_snapshot = snapshot
    state.social_last_signature = social_activity_signature(snapshot)
    if show_existing and snapshot.get('requests'):
        existing_events = [
            {
                'id': f"friend-request:{request.get('from', '')}:{request.get('timestamp', '')}",
                'kind': 'friend_request',
                'message': t('friend_request_incoming_notice').format(user=request.get('from', '')),
                'chat_id': None,
                'created_at': request.get('timestamp') or current_timestamp(),
            }
            for request in snapshot.get('requests', [])
        ]
        added = store_notification_events(existing_events)
        if added:
            show_social_action_notification(f"{t('friend_request_received')} ({len(added)})")

def send_social_chat_message(chat_id, text):
    current = state.current_user
    message = str(text or '').strip()
    if not current or not message:
        return False
    user_data = load_user_data()
    chats = user_data.setdefault('chats', {})
    chat = chats.get(str(chat_id))
    if not chat or current not in chat.get('members', []):
        ui.notify(t('chat_not_allowed'), color='warning')
        return False
    chat.setdefault('messages', []).append({
        'user': current,
        'text': message[:500],
        'timestamp': current_timestamp(),
    })
    del chat['messages'][:-120]
    state.social_selected_chat_id = str(chat_id)
    persist_current_user_data(user_data)
    refresh_current_screen()
    return True

def rename_user_references(user_data, old_username, new_username):
    for record in get_users(user_data).values():
        if isinstance(record, dict):
            friends = ensure_friend_list(record)
            record['friends'] = [new_username if friend == old_username else friend for friend in friends]
    for request in user_data.setdefault('friend_requests', []):
        if request.get('from') == old_username:
            request['from'] = new_username
        if request.get('to') == old_username:
            request['to'] = new_username
    for chat in user_data.setdefault('chats', {}).values():
        if not isinstance(chat, dict):
            continue
        chat['members'] = [new_username if member == old_username else member for member in chat.get('members', [])]
        for message in chat.get('messages', []):
            if isinstance(message, dict) and message.get('user') == old_username:
                message['user'] = new_username

def remove_user_references(user_data, username):
    for record in get_users(user_data).values():
        if isinstance(record, dict):
            friends = ensure_friend_list(record)
            if username in friends:
                friends.remove(username)
    user_data['friend_requests'] = [
        request for request in user_data.setdefault('friend_requests', [])
        if request.get('from') != username and request.get('to') != username
    ]
    for chat_id, chat in list(user_data.setdefault('chats', {}).items()):
        if not isinstance(chat, dict):
            continue
        if username in chat.get('members', []):
            chat['members'] = [member for member in chat.get('members', []) if member != username]
        if len(chat.get('members', [])) < 2:
            user_data['chats'].pop(chat_id, None)

def favorite_keys(data=None):
    user = get_current_user_record()
    if not user:
        return set()
    return set(user.setdefault('favorites', []))

def current_favorite_filter():
    value = getattr(state, 'favorite_filter', None)
    if value in ['all', 'only', 'except']:
        return value
    return 'only' if getattr(state, 'show_favorites_only', False) else 'all'

def set_favorite_filter(value):
    value = value if value in ['all', 'only', 'except'] else 'all'
    state.favorite_filter = value
    state.show_favorites_only = value == 'only'

def next_favorite_filter():
    order = ['all', 'only', 'except']
    current = current_favorite_filter()
    return order[(order.index(current) + 1) % len(order)]

def favorite_filter_label():
    current = current_favorite_filter()
    if current == 'only':
        return t('favorites_only')
    if current == 'except':
        return t('favorites_except')
    return t('favorites_all')

def favorite_filter_icon():
    current = current_favorite_filter()
    if current == 'only':
        return 'star'
    if current == 'except':
        return 'star_border'
    return 'stars'

def favorite_filter_color():
    current = current_favorite_filter()
    if current == 'only':
        return 'amber'
    if current == 'except':
        return 'blue-grey'
    return 'grey'

def is_favorite(country, data=None):
    return country_key(country) in favorite_keys(data)

def toggle_favorite(country):
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        ui.notify(t('login_required'), color='warning')
        return
    favorites = user.setdefault('favorites', [])
    key = country_key(country)
    if key in favorites:
        favorites.remove(key)
    else:
        favorites.append(key)
    persist_current_user_data(user_data)

def get_note_for_country(country, data=None):
    user = get_current_user_record()
    if not user:
        return ''
    return user.setdefault('notes', {}).get(country_key(country), '')

def save_note_for_country(country, note_text):
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        ui.notify(t('login_required'), color='warning')
        return
    notes = user.setdefault('notes', {})
    key = country_key(country)
    text = (note_text or '').strip()
    if text:
        notes[key] = text
    else:
        notes.pop(key, None)
    persist_current_user_data(user_data)
    ui.notify(t('note_saved'), color='positive')

def get_quiz_stats(data=None):
    user = get_current_user_record()
    if not user:
        return {'answered': 0, 'correct': 0, 'streak': 0, 'best_streak': 0}
    return normalize_quiz_stats(user)

def get_review_keys(data=None):
    user = get_current_user_record()
    if not user:
        return []
    return user.setdefault('review_keys', [])

def get_collections():
    user = get_current_user_record()
    if not user:
        return {}
    collections = user.setdefault('collections', {})
    return collections if isinstance(collections, dict) else {}

def create_collection(name):
    name = (name or '').strip()
    if not name:
        return
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        ui.notify(t('login_required'), color='warning')
        return
    collections = user.setdefault('collections', {})
    collections.setdefault(name, [])
    persist_current_user_data(user_data)
    ui.notify(t('collection_created'), color='positive')

def delete_collection(name):
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        return
    collections = user.setdefault('collections', {})
    collections.pop(name, None)
    if state.collection_filter == name:
        state.collection_filter = None
    persist_current_user_data(user_data)
    ui.notify(t('collection_deleted'), color='info')

def toggle_collection_country(collection_name, country):
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        ui.notify(t('login_required'), color='warning')
        return
    key = country_key(country)
    collection = user.setdefault('collections', {}).setdefault(collection_name, [])
    if key in collection:
        collection.remove(key)
    else:
        collection.append(key)
    persist_current_user_data(user_data)

def collection_contains(collection_name, country):
    return country_key(country) in get_collections().get(collection_name, [])

def displayable_flag_code(code):
    return bool(code) and code != 'xx'

QUIZ_FLAG_EXCLUDED_TOKENS = {
    'umayyad_flag.svg',
    'banner_of_arms_kingdom_of_castille_habsbourg_style.svg',
    'flag_of_the_kingdom_of_naples.svg',
    'flag_of_ragusa.svg',
}

def has_quiz_visual_flag_code(code):
    if not displayable_flag_code(code):
        return False
    normalized = str(code or '').strip().lower()
    return not any(token in normalized for token in QUIZ_FLAG_EXCLUDED_TOKENS)

def avatar_user_dir(username=None):
    username = username or state.current_user or 'guest'
    digest = hashlib.sha1(username.encode('utf-8')).hexdigest()[:16]
    path = os.path.join(USER_ASSETS_DIR, 'avatars', digest)
    os.makedirs(path, exist_ok=True)
    return path

def user_asset_url(relative_path, version=None):
    url = f"/user-assets/{relative_path.replace(os.sep, '/')}"
    if version:
        url += f"?v={version}"
    return url

def avatar_mime_from_extension(ext):
    return {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
        '.gif': 'image/gif',
    }.get(str(ext or '').lower(), 'image/png')

def avatar_data_url_from_content(ext, content):
    if not isinstance(content, (bytes, bytearray)):
        return ''
    encoded = base64.b64encode(content).decode('ascii')
    return f'data:{avatar_mime_from_extension(ext)};base64,{encoded}'

def avatar_data_url_from_file(avatar):
    if not isinstance(avatar, dict) or avatar.get('mode') != 'upload' or not avatar.get('file'):
        return ''
    file_path = os.path.join(USER_ASSETS_DIR, avatar['file'])
    if not os.path.exists(file_path) or os.path.getsize(file_path) > 3 * 1024 * 1024:
        return ''
    ext = os.path.splitext(file_path)[1].lower()
    try:
        with open(file_path, 'rb') as f:
            return avatar_data_url_from_content(ext, f.read())
    except OSError:
        return ''

def current_user_avatar_url(user=None):
    if user is None:
        user = get_current_user_record()
    if not user:
        return None
    avatar = user.get('avatar') if isinstance(user.get('avatar'), dict) else {}
    if avatar.get('mode') == 'upload' and avatar.get('file'):
        file_path = os.path.join(USER_ASSETS_DIR, avatar['file'])
        if os.path.exists(file_path):
            return user_asset_url(avatar['file'], avatar.get('version'))
        if isinstance(avatar.get('data_url'), str) and avatar['data_url'].startswith('data:image/'):
            return avatar['data_url']
    if avatar.get('mode') == 'flag' and avatar.get('country_key'):
        country = public_countries_by_key().get(avatar['country_key'])
        if country and displayable_flag_code(country.get('flag_code')):
            return get_flag_url(country.get('flag_code'))
    return None

def avatar_adjustment(source=None):
    avatar = source if isinstance(source, dict) and source.get('mode') else None
    if not avatar and isinstance(source, dict):
        avatar = source.get('avatar') if isinstance(source.get('avatar'), dict) else {}
    avatar = normalize_avatar_adjustment(dict(avatar or {}))
    return {
        'zoom': avatar.get('zoom', 100),
        'position_x': avatar.get('position_x', 50),
        'position_y': avatar.get('position_y', 50),
    }

def avatar_crop_geometry(zoom, x, y):
    zoom = int(clamp_number(zoom, 20, 300, 100))
    x = int(clamp_number(x, 0, 100, 50))
    y = int(clamp_number(y, 0, 100, 50))
    return {
        'zoom': zoom,
        'x': x,
        'y': y,
        'left': x,
        'top': y,
    }

def render_avatar_image(avatar_url, source, classes, icon_size='4rem', icon_classes='text-gray-400', live=True):
    if avatar_url:
        adjust = avatar_adjustment(source)
        crop = avatar_crop_geometry(adjust['zoom'], adjust['position_x'], adjust['position_y'])
        zoom = crop['zoom']
        x = crop['x']
        y = crop['y']
        left = crop['left']
        top = crop['top']
        src = html_escape(str(avatar_url), quote=True)
        live_attr = 'data-wa-avatar-live="current"' if live else ''
        with ui.element('div').classes(f'{classes} overflow-hidden relative'):
            ui.html(
                f'<img class="wa-avatar-crop-image" {live_attr} src="{src}" '
                f'data-wa-zoom="{zoom}" data-wa-x="{x}" data-wa-y="{y}" '
                f'style="position:absolute;left:{left:.4f}%;top:{top:.4f}%;width:{zoom}%;height:auto;'
                f'max-width:none;max-height:none;object-fit:contain;object-position:center center;'
                f'transform:translate(-50%, -50%);display:block;">',
                sanitize=False,
            )
    else:
        ui.icon('account_circle', size=icon_size).classes(icon_classes)

def render_avatar_drag_editor(avatar_url, source):
    adjust = avatar_adjustment(source)
    crop = avatar_crop_geometry(adjust['zoom'], adjust['position_x'], adjust['position_y'])
    zoom = crop['zoom']
    x = crop['x']
    y = crop['y']
    editor_id = f"avatar-editor-{random.randint(100000, 999999)}"
    save_id = f"{editor_id}-save"
    status_id = f"{editor_id}-status"
    username = state.current_user or ''
    src = html_escape(str(avatar_url), quote=True)
    save_text = html_escape(t('avatar_save_adjust'), quote=True)
    ui.html(
        f'''
        <div class="flex flex-col gap-2 items-center">
          <div id="{editor_id}" class="wa-avatar-editor border shadow bg-white">
            <img src="{src}" style="left:{x}%;top:{y}%;width:{zoom}%;height:auto;max-width:none;max-height:none;object-fit:contain;object-position:center center;transform:translate(-50%, -50%);">
            <div class="wa-avatar-target" style="left:{x}%;top:{y}%;"></div>
          </div>
          <button id="{save_id}" type="button" class="q-btn q-btn-item non-selectable no-outline q-btn--outline q-btn--rectangle text-primary q-btn--actionable q-focusable q-hoverable q-btn--dense px-3 py-1">
            {save_text}
          </button>
          <div id="{status_id}" class="text-xs text-gray-500"></div>
        </div>
        ''',
        sanitize=False,
    )
    script = f"""
    (() => {{
      const frame = document.getElementById({json.dumps(editor_id)});
      if (!frame || frame.dataset.ready === '1') return;
      frame.dataset.ready = '1';
      const image = frame.querySelector('img');
      const target = frame.querySelector('.wa-avatar-target');
      const saveButton = document.getElementById({json.dumps(save_id)});
      const status = document.getElementById({json.dumps(status_id)});
      let x = {x};
      let y = {y};
      const zoom = {zoom};
      let dragging = false;
      const clamp = value => Math.max(0, Math.min(100, value));
      const applyToImage = img => {{
        img.style.width = `${{zoom}}%`;
        img.style.height = 'auto';
        img.style.maxWidth = 'none';
        img.style.maxHeight = 'none';
        img.style.left = `${{x}}%`;
        img.style.top = `${{y}}%`;
        img.style.objectFit = 'contain';
        img.style.objectPosition = 'center center';
        img.style.transform = 'translate(-50%, -50%)';
        img.dataset.waZoom = String(zoom);
        img.dataset.waX = String(Math.round(x));
        img.dataset.waY = String(Math.round(y));
      }};
      const apply = () => {{
        applyToImage(image);
        target.style.left = `${{x}}%`;
        target.style.top = `${{y}}%`;
        document.querySelectorAll('[data-wa-avatar-live="current"]').forEach(applyToImage);
      }};
      const setFromPointer = event => {{
        const rect = frame.getBoundingClientRect();
        x = clamp(((event.clientX - rect.left) / rect.width) * 100);
        y = clamp(((event.clientY - rect.top) / rect.height) * 100);
        apply();
      }};
      const save = async () => {{
        try {{
          await fetch('/api/avatar-adjust', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
              username: {json.dumps(username)},
              position_x: Math.round(x),
              position_y: Math.round(y),
            }}),
          }});
          if (status) status.textContent = {json.dumps(t('avatar_adjust_saved'))};
          return true;
        }} catch (error) {{
          console.warn('Avatar position save failed', error);
          if (status) status.textContent = {json.dumps(t('avatar_upload_failed'))};
          return false;
        }}
      }};
      if (saveButton) {{
        saveButton.addEventListener('click', event => {{
          event.preventDefault();
          save();
        }});
      }}
      frame.addEventListener('pointerdown', event => {{
        event.preventDefault();
        dragging = true;
        frame.setPointerCapture(event.pointerId);
        setFromPointer(event);
      }});
      frame.addEventListener('pointermove', event => {{
        if (!dragging) return;
        event.preventDefault();
        setFromPointer(event);
      }});
      const finish = event => {{
        if (!dragging) return;
        dragging = false;
        try {{ frame.releasePointerCapture(event.pointerId); }} catch (error) {{}}
        save();
      }};
      frame.addEventListener('pointerup', finish);
      frame.addEventListener('pointercancel', finish);
      apply();
    }})();
    """
    ui.timer(0.1, lambda script=script: ui.run_javascript(script), once=True)

def flag_avatar_option_maps(data=None):
    global FLAG_AVATAR_OPTION_MAP_CACHE
    data = data or get_data()
    mtime = DATA_CACHE_MTIME or file_mtime(JSON_FILE)
    data_id = id(data)
    lang = state.lang
    cached = FLAG_AVATAR_OPTION_MAP_CACHE.get('value')
    if (
        cached
        and FLAG_AVATAR_OPTION_MAP_CACHE.get('mtime') == mtime
        and FLAG_AVATAR_OPTION_MAP_CACHE.get('data_id') == data_id
        and FLAG_AVATAR_OPTION_MAP_CACHE.get('lang') == lang
    ):
        return cached

    label_to_key = {}
    key_to_label = {}
    for country in public_country_list(data):
        if not displayable_flag_code(country.get('flag_code')):
            continue
        label = country_option_label(country)
        key = country_key(country)
        label_to_key[label] = key
        key_to_label[key] = label
    value = (label_to_key, key_to_label)
    FLAG_AVATAR_OPTION_MAP_CACHE = {'mtime': mtime, 'data_id': data_id, 'lang': lang, 'value': value}
    return value

def current_avatar_country_label(user=None):
    user = user or get_current_user_record()
    avatar = user.get('avatar') if user and isinstance(user.get('avatar'), dict) else {}
    if avatar.get('mode') != 'flag':
        return None
    _, key_to_label = flag_avatar_option_maps()
    return key_to_label.get(avatar.get('country_key'))

def is_public_profile_hidden(record):
    return isinstance(record, dict) and bool(record.get('hide_public_profile'))

def public_user_profiles():
    user_data = load_user_data()
    users = get_users(user_data)
    known_usernames = set(users.keys())
    if isinstance(user_data.get('known_users'), list):
        known_usernames.update(clean_username(username) for username in user_data['known_users'])
    lookup = public_countries_by_key()
    profiles = []
    for username in sorted((name for name in known_usernames if name), key=lambda item: item.lower()):
        record = users.get(username, {})
        if is_guest_record(username, record):
            continue
        if not isinstance(record, dict):
            record = {}
        ensure_user_defaults(record)
        if is_public_profile_hidden(record):
            continue
        favorites = [key for key in record.get('favorites', []) if key in lookup]
        viewed = [key for key in record.get('viewed_keys', []) if key in lookup]
        review = [key for key in record.get('review_keys', []) if key in lookup]
        collections = record.get('collections', {}) if isinstance(record.get('collections'), dict) else {}
        public_collections = [
            {'name': name, 'keys': [key for key in keys if key in lookup]}
            for name, keys in collections.items()
            if isinstance(keys, list)
        ]
        stats = record.get('quiz_stats', {}) if isinstance(record.get('quiz_stats'), dict) else {}
        history = record.get('history', []) if isinstance(record.get('history'), list) else []
        latest_history = history[0] if history and isinstance(history[0], dict) else {}
        friends = [
            friend for friend in record.get('friends', [])
            if clean_stored_username(friend) and not is_stored_guest_username(friend)
        ]
        profiles.append({
            'username': username,
            'name_color': user_name_color(record),
            'avatar_url': current_user_avatar_url(record),
            'avatar': record.get('avatar', {}),
            'friends': friends,
            'favorites': favorites,
            'viewed_count': len(viewed),
            'review_count': len(review),
            'collection_count': len(public_collections),
            'collections': public_collections,
            'answered': stats.get('answered', 0),
            'correct': stats.get('correct', 0),
            'best_streak': stats.get('best_streak', 0),
            'battle_wins': record.get('battle_wins', 0),
            'battle_unlocked': bool(record.get('battle_unlocked')),
            'sengoku_unlocked': bool(record.get('sengoku_unlocked')),
            'sengoku_medal': bool(record.get('sengoku_medal')),
            'sengoku_boss_clears': normalize_sengoku_boss_clears(record.get('sengoku_boss_clears', [])),
            'all_viewed': set(all_public_country_keys()).issubset(set(viewed)),
            'last_viewed': format_timestamp(latest_history.get('timestamp')),
        })
    return profiles

def set_avatar_country(label):
    label_to_key, _ = flag_avatar_option_maps()
    key = label_to_key.get(label)
    if not key:
        return
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        ui.notify(t('login_required'), color='warning')
        return
    user['avatar'] = {'mode': 'flag', 'country_key': key, **default_avatar_adjustment()}
    persist_current_user_data(user_data)
    ui.notify(t('avatar_saved'), color='positive')
    refresh_current_screen()

def update_avatar_adjustment(field, value):
    allowed_fields = {
        'zoom': (20, 300, 100),
        'position_x': (0, 100, 50),
        'position_y': (0, 100, 50),
    }
    if field not in allowed_fields:
        return
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        return
    avatar = user.setdefault('avatar', {'mode': 'default'})
    if avatar.get('mode') not in ['flag', 'upload']:
        return
    min_value, max_value, default = allowed_fields[field]
    avatar[field] = int(clamp_number(value, min_value, max_value, default))
    persist_current_user_data(user_data)
    refresh_current_screen()

def save_avatar_adjustment_values(values):
    user_data = load_user_data()
    username = clean_username((values or {}).get('username')) or state.current_user
    user = get_named_user_record(username, user_data)
    if not user:
        return False
    avatar = user.setdefault('avatar', {'mode': 'default'})
    if avatar.get('mode') not in ['flag', 'upload']:
        return False
    if 'zoom' in values:
        avatar['zoom'] = int(clamp_number(values.get('zoom'), 20, 300, avatar.get('zoom', 100)))
    if 'position_x' in values:
        avatar['position_x'] = int(clamp_number(values.get('position_x'), 0, 100, avatar.get('position_x', 50)))
    if 'position_y' in values:
        avatar['position_y'] = int(clamp_number(values.get('position_y'), 0, 100, avatar.get('position_y', 50)))
    persist_current_user_data(user_data)
    return True

def reset_avatar():
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        return
    user['avatar'] = {'mode': 'default', **default_avatar_adjustment()}
    persist_current_user_data(user_data)
    ui.notify(t('avatar_saved'), color='positive')
    refresh_current_screen()

def save_avatar_image_content(filename, content, username=None):
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
    ext = os.path.splitext(filename or '')[1].lower()
    if ext not in allowed_extensions:
        raise ValueError('unsupported image extension')
    if isinstance(content, str):
        content = content.encode('utf-8')
    if not isinstance(content, (bytes, bytearray)):
        raise ValueError('invalid image content')
    if not content or len(content) > 3 * 1024 * 1024:
        raise ValueError('invalid image size')
    user_data = load_user_data()
    username = clean_username(username) or state.current_user
    user = get_named_user_record(username, user_data)
    if not user:
        raise PermissionError('login required')
    folder = avatar_user_dir(username)
    for name in os.listdir(folder):
        if name.startswith('avatar.'):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass
    saved_filename = f'avatar{ext}'
    saved_path = os.path.join(folder, saved_filename)
    with open(saved_path, 'wb') as f:
        f.write(content)
    relative_file = os.path.relpath(saved_path, USER_ASSETS_DIR)
    user['avatar'] = {
        'mode': 'upload',
        'file': relative_file.replace(os.sep, '/'),
        'version': app_now().strftime('%Y%m%d%H%M%S'),
        **default_avatar_adjustment(),
    }
    persist_current_user_data(user_data)
    return True

def upload_avatar_image(event):
    try:
        content_source = event.content
        if hasattr(content_source, 'seek'):
            try:
                content_source.seek(0)
            except Exception:
                pass
        content = content_source.read() if hasattr(content_source, 'read') else content_source
        save_avatar_image_content(event.name, content, state.current_user)
        ui.notify(t('avatar_saved'), color='positive')
        refresh_current_screen()
    except Exception as e:
        print(f'Avatar upload failed: {e}', flush=True)
        ui.notify(t('avatar_upload_failed'), color='negative')

def render_avatar_upload_control():
    upload_id = f"avatar-upload-{random.randint(100000, 999999)}"
    button_id = f"{upload_id}-button"
    status_id = f"{upload_id}-status"
    button_text = html_escape(t('avatar_choose_file'))
    username = state.current_user or ''
    ui.html(
        f'''
        <div class="w-full flex flex-col gap-2">
          <input id="{upload_id}" type="file" accept="image/png,image/jpeg,image/webp,image/gif" style="display:none;">
          <button id="{button_id}" type="button" class="q-btn q-btn-item non-selectable no-outline q-btn--standard q-btn--rectangle bg-primary text-white q-btn--actionable q-focusable q-hoverable q-btn--dense px-4 py-2">
            {button_text}
          </button>
          <div id="{status_id}" class="text-xs text-gray-500"></div>
        </div>
        ''',
        sanitize=False,
    )
    script = f"""
    (() => {{
      const input = document.getElementById({json.dumps(upload_id)});
      const button = document.getElementById({json.dumps(button_id)});
      const status = document.getElementById({json.dumps(status_id)});
      if (!input || input.dataset.ready === '1') return;
      input.dataset.ready = '1';
      if (button) {{
        button.addEventListener('click', event => {{
          event.preventDefault();
          input.click();
        }});
      }}
      input.addEventListener('change', async () => {{
        const file = input.files && input.files[0];
        if (!file) return;
        if (file.size > 8 * 1024 * 1024) {{
          if (status) status.textContent = {json.dumps(t('avatar_upload_failed'))};
          input.value = '';
          return;
        }}
        const reader = new FileReader();
        reader.onerror = () => {{
          if (status) status.textContent = {json.dumps(t('avatar_upload_failed'))};
        }};
        reader.onload = async () => {{
          try {{
            const response = await fetch('/api/avatar-upload', {{
              method: 'POST',
              headers: {{'Content-Type': 'application/json'}},
              body: JSON.stringify({{
                name: file.name,
                username: {json.dumps(username)},
                content: reader.result,
              }}),
            }});
            const result = await response.json();
            if (!response.ok || !result.ok) throw new Error(result.error || 'upload failed');
            if (status) status.textContent = {json.dumps(t('avatar_saved'))};
            window.location.reload();
          }} catch (error) {{
            console.warn('Avatar upload failed', error);
            if (status) status.textContent = {json.dumps(t('avatar_upload_failed'))};
          }} finally {{
            input.value = '';
          }}
        }};
        reader.readAsDataURL(file);
      }});
    }})();
    """
    ui.timer(0.1, lambda script=script: ui.run_javascript(script), once=True)

def get_quiz_history():
    user = get_current_user_record()
    if not user:
        return []
    return user.setdefault('quiz_history', [])

def quiz_is_reverse(question_type):
    return str(question_type or '').endswith('_reverse')

def quiz_base_type(question_type):
    question_type = str(question_type or '')
    return question_type[:-8] if question_type.endswith('_reverse') else question_type

def quiz_category_label(question_type):
    question_type = quiz_base_type(question_type)
    if question_type == 'capital':
        return t('labels', 'capital')
    if question_type == 'flag':
        return t('quiz_flag')
    if question_type == 'period':
        return t('period')
    if question_type == 'tag':
        return t('quiz_category_tag')
    if question_type == 'desc':
        return t('labels', 'desc')
    if question_type and question_type.startswith('profile_'):
        return t('labels', question_type.replace('profile_', '', 1))
    if question_type and question_type.startswith('detail_'):
        return t(question_type.replace('detail_', '', 1))
    return t('quiz')

def quiz_weakness_rows(limit=6):
    history = get_quiz_history()
    data = get_data()
    lookup = public_countries_by_key(data)
    counters = {}
    for entry in history:
        if entry.get('correct'):
            continue
        answer = lookup.get(entry.get('answer_key'))
        labels = [quiz_category_label(entry.get('type'))]
        if answer:
            labels.extend(tag_label(tag) for tag in answer.get('tags', [])[:2])
            region = region_label(answer.get('region', ''))
            if region:
                labels.append(region)
        for label in labels:
            if label:
                counters[label] = counters.get(label, 0) + 1
    return sorted(counters.items(), key=lambda item: (-item[1], item[0]))[:limit]

def update_quiz_stats(correct, answer_key=None, review_mode=False, selected_key=None, question_type=None):
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        return
    stats = normalize_quiz_stats(user)
    stats['answered'] = stats.get('answered', 0) + 1
    if correct:
        stats['correct'] = stats.get('correct', 0) + 1
        stats['streak'] = stats.get('streak', 0) + 1
    else:
        stats['streak'] = 0
    stats['best_streak'] = max(stats.get('best_streak', 0), stats.get('streak', 0))
    if answer_key:
        review = user.setdefault('review_keys', [])
        if correct and review_mode:
            if answer_key in review:
                review.remove(answer_key)
        elif not correct and answer_key not in review:
            review.insert(0, answer_key)
            del review[80:]
    history = user.setdefault('quiz_history', [])
    history.insert(0, {
        'timestamp': current_timestamp(),
        'answer_key': answer_key,
        'selected_key': selected_key,
        'correct': bool(correct),
        'type': question_type or '',
        'mode': state.quiz_mode,
        'difficulty': state.quiz_difficulty,
        'category': state.quiz_category,
        'scope': state.quiz_scope,
        'format': state.quiz_format,
    })
    del history[QUIZ_HISTORY_LIMIT:]
    normalize_quiz_stats(user)
    battle_unlocked_now = mark_battle_unlock_if_ready(user)
    sengoku_unlocked_now = mark_sengoku_unlock_if_ready(user)
    persist_current_user_data(user_data)
    if battle_unlocked_now:
        ui.notify(t('battle_unlocked_notice'), color='positive')
    if sengoku_unlocked_now:
        ui.notify(t('sengoku_unlocked_notice'), color='positive')

def get_kakasi_converter():
    global KAKASI_CONVERTER
    if KAKASI_CONVERTER is not None:
        return KAKASI_CONVERTER
    try:
        import pykakasi
        KAKASI_CONVERTER = pykakasi.kakasi()
    except Exception:
        KAKASI_CONVERTER = False
    return KAKASI_CONVERTER or None

def get_pinyin_converter():
    global PINYIN_CONVERTER
    if PINYIN_CONVERTER is not None:
        return PINYIN_CONVERTER
    try:
        from pypinyin import lazy_pinyin as converter
        PINYIN_CONVERTER = converter
    except Exception:
        PINYIN_CONVERTER = False
    return PINYIN_CONVERTER or None

def sort_key(country):
    name = get_localized_text(country.get('names', {}))
    kakasi_converter = get_kakasi_converter() if state.lang == 'ja' else None
    if kakasi_converter:
        try:
            return ''.join(item.get('hira') or item.get('kana') or item.get('orig', '') for item in kakasi_converter.convert(name))
        except Exception:
            pass
    pinyin_converter = get_pinyin_converter() if state.lang == 'zh' else None
    if pinyin_converter:
        try:
            return ' '.join(pinyin_converter(name))
        except Exception:
            pass
    return name.casefold()

def period_start(country):
    start = (country.get('period') or {}).get('start')
    return start if isinstance(start, int) else None

def period_end(country):
    end = (country.get('period') or {}).get('end')
    return end if isinstance(end, int) else None

def period_label(country):
    period = country.get('period') or {}
    label = period.get('label')
    if isinstance(label, dict):
        return get_localized_text(label)
    if label:
        return str(label)
    return ''

def period_field_label(country):
    if country.get('type') == 'Present':
        return t('labels', 'founded')
    return t('labels', 'period')

PROFILE_FIELDS = ['population', 'area', 'languages', 'religions']
DETAIL_FIELDS = ['key_figures', 'major_events', 'fall_reason', 'successors', 'cultural_features']
DETAIL_QUIZ_FIELDS = ['major_events', 'fall_reason', 'cultural_features']

def profile_value(country, field):
    profile = country.get('profile') or {}
    value = profile.get(field)
    if isinstance(value, dict):
        return get_localized_text(value)
    if value is None:
        return ''
    return str(value)

def profile_rows(country):
    rows = []
    for field in PROFILE_FIELDS:
        value = profile_value(country, field)
        if value:
            rows.append((t('labels', field), value))
    return rows

def profile_search_text(country):
    values = []
    profile = country.get('profile') or {}
    for field in PROFILE_FIELDS:
        value = profile.get(field)
        if isinstance(value, dict):
            values.extend(str(text) for text in value.values() if text)
        elif value:
            values.append(str(value))
    return ' '.join(values)

def detail_value(country, field):
    details = country.get('details') or {}
    value = details.get(field)
    if isinstance(value, dict):
        return get_localized_text(value)
    if isinstance(value, list):
        return ' / '.join(str(item) for item in value if item)
    if value is None:
        return ''
    return str(value)

def detail_rows(country):
    rows = []
    for field in DETAIL_FIELDS:
        value = detail_value(country, field)
        if value:
            rows.append((t(field), value))
    return rows

def detail_search_text(country):
    values = []
    details = country.get('details') or {}
    for field in DETAIL_FIELDS:
        value = details.get(field)
        if isinstance(value, dict):
            values.extend(str(text) for text in value.values() if text)
        elif isinstance(value, list):
            values.extend(str(item) for item in value if item)
        elif value:
            values.append(str(value))
    return ' '.join(values)

def localized_values(value):
    if isinstance(value, dict):
        return [str(item) for item in value.values() if item]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []

def country_search_index(data=None):
    global SEARCH_TEXT_CACHE
    data = data or get_data()
    mtime = DATA_CACHE_MTIME or file_mtime(JSON_FILE)
    data_id = id(data)
    lang = state.lang
    cached = SEARCH_TEXT_CACHE.get('value')
    if (
        cached
        and SEARCH_TEXT_CACHE.get('mtime') == mtime
        and SEARCH_TEXT_CACHE.get('data_id') == data_id
        and SEARCH_TEXT_CACHE.get('lang') == lang
    ):
        return cached

    index = {}
    for country in derived_country_data(data)['countries']:
        values = []
        values.extend(localized_values(country.get('names', {})))
        values.extend(localized_values(country.get('capital', {})))
        values.extend(localized_values(country.get('desc', {})))
        values.extend(tag_search_text(tag) for tag in country.get('tags', []))
        period = country.get('period') or {}
        values.extend(localized_values(period.get('label', {})))
        values.append(str(period.get('start', '')))
        values.append(str(period.get('end') or ''))
        values.append(profile_search_text(country))
        values.append(detail_search_text(country))
        values.append(region_search_text(country.get('region', '')))
        index[country_key(country)] = ' '.join(str(value) for value in values if value).casefold()

    SEARCH_TEXT_CACHE = {'mtime': mtime, 'data_id': data_id, 'lang': lang, 'value': index}
    return index

def country_list_sort_key(country):
    if state.sort_field == 'period':
        start = period_start(country)
        end = period_end(country)
        if start is None:
            return (1, 0, sort_key(country), country.get('names', {}).get('en', ''))
        start_value = -start if state.sort_order == 'desc' else start
        end_for_sort = end if end is not None else start
        end_value = -end_for_sort if state.sort_order == 'desc' else end_for_sort
        return (0, start_value, end_value, sort_key(country), country.get('names', {}).get('en', ''))
    return (sort_key(country), country.get('names', {}).get('en', ''))

def timeline_sort_key(country):
    start = period_start(country)
    end = period_end(country)
    if start is None:
        return (1, sort_key(country), country.get('names', {}).get('en', ''))
    return (0, start, end if end is not None else start, sort_key(country), country.get('names', {}).get('en', ''))

def first_sentence(text):
    text = (text or '').strip()
    if not text:
        return ''
    marks = ['。', '.', '！', '!', '？', '?']
    positions = [text.find(mark) for mark in marks if text.find(mark) != -1]
    if not positions:
        return text
    return text[:min(positions) + 1]

DETAIL_QUIZ_BLOCKED_PHRASES = [
    'データ上の成立・建国時期',
    'The recorded foundation or establishment',
    '数据中记录的成立',
]

def split_quiz_sentences(text):
    text = (text or '').strip()
    if not text:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r'(?<=[。.!！？?])\s*', text)
        if sentence.strip()
    ]

def strip_period_only_intro(sentence):
    sentence = (sentence or '').strip()
    patterns = [
        r'^(?:紀元前)?\d+年(?:頃)?(?:[〜～\-—–](?:紀元前)?\d+年(?:頃)?)?に活動(?:し、|。|\.)\s*',
        r'^(?:c\.\s*)?\d+(?:\s*BCE|\s*CE)?(?:\s*[-–—]\s*(?:c\.\s*)?\d+(?:\s*BCE|\s*CE)?)?\s+active(?:,|\.| and )\s*',
        r'^\d+年(?:前)?(?:[—\-]\d+年(?:前)?)?活动(?:，|。)\s*',
    ]
    cleaned = sentence
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE).strip()
    return cleaned

def detail_quiz_sentence(country, field):
    value = detail_value(country, field)
    if not value:
        return ''
    normalized_value = normalized_text(value)
    if any(normalized_text(phrase) in normalized_value for phrase in DETAIL_QUIZ_BLOCKED_PHRASES):
        return ''
    for sentence in split_quiz_sentences(value):
        cleaned = strip_period_only_intro(sentence)
        normalized_sentence = normalized_text(cleaned)
        if not cleaned or any(normalized_text(phrase) in normalized_sentence for phrase in DETAIL_QUIZ_BLOCKED_PHRASES):
            continue
        if len(normalized_sentence) < 12:
            continue
        return cleaned
    return ''

def countries_by_key(data=None):
    return derived_country_data(data)['all_by_key']

def country_option_label(country):
    local_name = get_localized_text(country.get('names', {}))
    en_name = country.get('names', {}).get('en', '')
    if en_name and en_name != local_name:
        return f'{local_name} / {en_name}'
    return local_name

def country_option_maps(data=None):
    global COUNTRY_OPTION_MAP_CACHE
    data = data or get_data()
    mtime = DATA_CACHE_MTIME or file_mtime(JSON_FILE)
    data_id = id(data)
    lang = state.lang
    cached = COUNTRY_OPTION_MAP_CACHE.get('value')
    if (
        cached
        and COUNTRY_OPTION_MAP_CACHE.get('mtime') == mtime
        and COUNTRY_OPTION_MAP_CACHE.get('data_id') == data_id
        and COUNTRY_OPTION_MAP_CACHE.get('lang') == lang
    ):
        return cached

    label_to_key = {}
    key_to_label = {}
    for country in sorted(public_country_list(data), key=lambda c: (sort_key(c), c.get('names', {}).get('en', ''))):
        label = country_option_label(country)
        if label in label_to_key:
            label = f'{label} ({get_localized_text(country.get("capital", {}))})'
        key = country_key(country)
        label_to_key[label] = key
        key_to_label[key] = label
    value = (label_to_key, key_to_label)
    COUNTRY_OPTION_MAP_CACHE = {'mtime': mtime, 'data_id': data_id, 'lang': lang, 'value': value}
    return value

MAP_QUERY_OVERRIDES = {
    'Aztec Empire': 'Templo Mayor, Mexico City, Mexico',
    'Ayutthaya Kingdom': 'Ayutthaya Historical Park, Thailand',
    'Crown of Aragon': 'Zaragoza, Spain',
    'United Arab Republic': 'Cairo, Egypt',
    'Ancient Egypt': 'Giza Necropolis, Egypt',
    'Byzantine Empire': 'Istanbul, Turkey',
    'Eastern Roman Empire': 'Istanbul, Turkey',
    'Holy Roman Empire': 'Aachen, Germany',
    'Inca Empire': 'Cusco, Peru',
    'Mongol Empire': 'Karakorum, Mongolia',
    'Ottoman Empire': 'Istanbul, Turkey',
    'Roman Empire': 'Rome, Italy',
    'Soviet Union': 'Moscow, Russia',
    'Umayyad Caliphate': 'Damascus, Syria',
    'Abbasid Caliphate': 'Baghdad, Iraq',
    'Mamluk Sultanate': 'Cairo, Egypt',
    'Western Roman Empire': 'Ravenna, Italy',
    'British Empire': 'London, United Kingdom',
    'Spanish Empire': 'Madrid, Spain',
    'French Colonial Empire': 'Paris, France',
    'Dutch Empire': 'Amsterdam, Netherlands',
    'Austrian Empire': 'Vienna, Austria',
    'Zhou Dynasty': "Luoyang, Henan, China",
    'Shang Dynasty': 'Yinxu, Anyang, Henan, China',
    'Maurya Empire': 'Patna, Bihar, India',
    'Gupta Empire': 'Patna, Bihar, India',
    'Chola Empire': 'Thanjavur, Tamil Nadu, India',
    'Maratha Empire': 'Raigad Fort, Maharashtra, India',
    'Carthage': 'Carthage, Tunisia',
    'Neo-Babylonian Empire': 'Babylon, Iraq',
    'Macedonian Empire': 'Pella, Greece',
    'Ptolemaic Kingdom': 'Alexandria, Egypt',
    'Sumer': 'Ur, Iraq',
    'Akkadian Empire': 'Baghdad, Iraq',
    'Kushan Empire': 'Bagram, Afghanistan',
    'Gokturk Khaganate': 'Otuken, Mongolia',
    'Sukhothai Kingdom': 'Sukhothai Historical Park, Thailand',
    'Lan Xang': 'Luang Prabang, Laos',
    'Almohad Caliphate': 'Marrakesh, Morocco',
    'Ethiopian Empire': 'Addis Ababa, Ethiopia',
    'Kingdom of Armenia': 'Artashat, Armenia',
    'Kingdom of Georgia': 'Tbilisi, Georgia',
    'Almoravid Dynasty': 'Marrakesh, Morocco',
    'Kanem-Bornu Empire': 'Lake Chad',
    'Oyo Empire': 'Oyo, Nigeria',
    'Benin Empire': 'Benin City, Nigeria',
    'Great Zimbabwe': 'Great Zimbabwe National Monument, Zimbabwe',
    'Merovingian Kingdom': 'Paris, France',
    'Ostrogothic Kingdom': 'Ravenna, Italy',
    'Lombard Kingdom': 'Pavia, Italy',
    'Kingdom of Hungary': 'Buda Castle, Budapest, Hungary',
    'Crimean Khanate': 'Bakhchysarai, Crimea',
    'Minoan Civilization': 'Knossos, Crete, Greece',
    'Mycenaean Greece': 'Mycenae, Greece',
    'Phoenicia': 'Tyre, Lebanon',
    'Lydia': 'Sardis, Turkey',
    'Urartu': 'Van Fortress, Turkey',
    'Mitanni': 'Tell Fekheriye, Syria',
    'Elam': 'Susa, Iran',
    'Dacia': 'Sarmizegetusa Regia, Romania',
    'Thrace': 'Kazanlak, Bulgaria',
    'Kingdom of Macedon': 'Pella, Greece',
    'Teutonic Order': 'Malbork Castle, Poland',
    'Kingdom of Naples': 'Naples, Italy',
    'Bulgarian Empire': 'Pliska, Bulgaria',
    'Rashidun Caliphate': 'Medina, Saudi Arabia',
    'Fatimid Caliphate': 'Cairo, Egypt',
    'Ayyubid Sultanate': 'Cairo, Egypt',
    'Ghaznavid Empire': 'Ghazni, Afghanistan',
    'Khwarazmian Empire': 'Konye-Urgench, Turkmenistan',
    'Qin Dynasty': 'Xianyang, Shaanxi, China',
    'Sui Dynasty': "Xi'an, Shaanxi, China",
    'Liao Dynasty': 'Liao Shangjing Site, Inner Mongolia, China',
    'Tibetan Empire': 'Lhasa, Tibet',
    'Nanzhao': 'Dali, Yunnan, China',
    'Dali Kingdom': 'Dali Old Town, Yunnan, China',
    'Balhae': "Shangjing Longquanfu, Ning'an, Heilongjiang, China",
    'Baekje': 'Buyeo, South Korea',
    'Muromachi Shogunate': 'Kyoto, Japan',
    'Tokugawa Shogunate': 'Edo Castle, Tokyo, Japan',
    'Seljuk Empire': 'Isfahan, Iran',
    'Sultanate of Rum': 'Konya, Turkey',
    'Samanid Empire': 'Bukhara, Uzbekistan',
    'Buyid Dynasty': 'Shiraz, Iran',
    'Zengid Dynasty': 'Mosul, Iraq',
    'Crown of Castile': 'Toledo, Spain',
    'Kingdom of Sardinia': 'Turin, Italy',
    'Kingdom of Serbia': 'Belgrade, Serbia',
    'Kingdom of Croatia': 'Nin, Croatia',
    'Kingdom of Navarre': 'Pamplona, Spain',
    'Angevin Empire': 'Angers, France',
    'Duchy of Normandy': 'Rouen, France',
    'Duchy of Milan': 'Milan, Italy',
    'Duchy of Savoy': 'Chambery, France',
    'Republic of Ragusa': 'Dubrovnik, Croatia',
    'Kingdom of Portugal': 'Lisbon, Portugal',
    'Funan': 'Oc Eo, Vietnam',
    'Chenla': 'Sambor Prei Kuk, Cambodia',
    'Dvaravati': 'Nakhon Pathom, Thailand',
    'Lanna Kingdom': 'Chiang Mai, Thailand',
    'Sultanate of Aceh': 'Banda Aceh, Indonesia',
    'Sultanate of Demak': 'Demak, Indonesia',
    'Etruscan Civilization': 'Tarquinia, Italy',
    'Armenian Kingdom of Cilicia': 'Kozan, Adana, Turkey',
    'Khazar Khaganate': 'Astrakhan, Russia',
    'Chagatai Khanate': 'Almaliq, Xinjiang, China',
    'Kievan Rus': 'Kyiv, Ukraine',
    'Volga Bulgaria': 'Bolgar, Tatarstan, Russia',
    'First Bulgarian Empire': 'Pliska, Bulgaria',
    'Second Bulgarian Empire': 'Veliko Tarnovo, Bulgaria',
    'Great Moravia': 'Mikulcice, Czechia',
    'Pskov Republic': 'Pskov, Russia',
    'Hanseatic League': 'Lubeck, Germany',
    'Livonian Order': 'Cesis, Latvia',
    'County of Flanders': 'Ghent, Belgium',
    'Burgundian State': 'Dijon, France',
    'Kingdom of Galicia-Volhynia': 'Halych, Ukraine',
    'Kingdom of Asturias': 'Oviedo, Spain',
    'Kingdom of Leon': 'Leon, Spain',
    'County of Barcelona': 'Barcelona, Spain',
    'Kingdom of Sicily': 'Palermo, Italy',
    'Principality of Wallachia': 'Targoviste, Romania',
    'Principality of Moldavia': 'Suceava, Romania',
    'Nogai Horde': 'Astrakhan, Russia',
    'White Horde': 'Sighnaq, Kazakhstan',
    'Pala Empire': 'Patna, Bihar, India',
    'Pandya Dynasty': 'Madurai, India',
    'Hephthalite Empire': 'Balkh, Afghanistan',
    'Kara-Khanid Khanate': 'Balasagun, Kyrgyzstan',
    'Kara Khitai': 'Balasagun, Kyrgyzstan',
    'Qara Qoyunlu': 'Tabriz, Iran',
    'Aq Qoyunlu': 'Tabriz, Iran',
    'Hoysala Empire': 'Belur, Karnataka, India',
    'Vijayanagara Empire': 'Hampi, Karnataka, India',
    'Bengal Sultanate': 'Gaur, West Bengal, India',
    'Bahmani Sultanate': 'Gulbarga, Karnataka, India',
    'Rashtrakuta Empire': 'Malkhed, Karnataka, India',
    'Satavahana Dynasty': 'Paithan, Maharashtra, India',
    'Ashanti Empire': 'Kumasi, Ghana',
    'Luba Kingdom': 'Upemba Depression, Democratic Republic of the Congo',
    'Lunda Empire': 'Musumba, Democratic Republic of the Congo',
    'Merina Kingdom': 'Antananarivo, Madagascar',
    'Adal Sultanate': 'Harar, Ethiopia',
    'Kilwa Sultanate': 'Kilwa Kisiwani, Tanzania',
    'Makuria': 'Old Dongola, Sudan',
    'Alodia': 'Soba, Sudan',
    'Wari Empire': 'Wari archaeological site, Ayacucho, Peru',
    'Moche Civilization': 'Huacas de Moche, Trujillo, Peru',
    'Nazca Civilization': 'Cahuachi, Nazca, Peru',
    'Muisca Confederation': 'Bogota, Colombia',
    'Tairona': 'Ciudad Perdida, Colombia',
    'Norte Chico Civilization': 'Caral, Peru',
    'Zapotec Civilization': 'Monte Alban, Oaxaca, Mexico',
    'Mixtec Civilization': 'Tilantongo, Oaxaca, Mexico',
    'Purepecha Empire': 'Tzintzuntzan, Michoacan, Mexico',
    'League of Mayapan': 'Mayapan, Yucatan, Mexico',
    'Kiche Kingdom of Qumarkaj': 'Qumarkaj, Guatemala',
    'Itza Kingdom': 'Flores, Peten, Guatemala',
    'Powhatan Confederacy': 'Werowocomoco, Virginia, United States',
    'Cahokia': 'Cahokia Mounds, Illinois, United States',
    'Hohokam': 'Casa Grande Ruins National Monument, Arizona, United States',
    'Ancestral Puebloans': 'Chaco Culture National Historical Park, New Mexico, United States',
    'Nok Culture': 'Nok, Kaduna, Nigeria',
    'Sao Civilization': 'Lake Chad',
    'Jolof Empire': 'Linguere, Senegal',
    'Kaabu Empire': 'Kansala, Guinea-Bissau',
    'Bamana Empire': 'Segou, Mali',
    'Wassoulou Empire': 'Bissandugu, Guinea',
    'Kong Empire': 'Kong, Ivory Coast',
    'Mossi Kingdoms': 'Ouagadougou, Burkina Faso',
    'Dagbon Kingdom': 'Yendi, Ghana',
    'Sokoto Caliphate': 'Sokoto, Nigeria',
    'Wadai Empire': 'Abeche, Chad',
    'Sultanate of Darfur': 'Al-Fashir, Sudan',
    'Funj Sultanate': 'Sennar, Sudan',
    'Kingdom of Rwanda': 'Nyanza, Rwanda',
    'Kingdom of Burundi': 'Gitega, Burundi',
    'Buganda Kingdom': 'Mengo, Kampala, Uganda',
    'Bunyoro Kingdom': 'Hoima, Uganda',
    'Rozvi Empire': 'Danangombe, Zimbabwe',
    'Maravi Empire': 'Lake Malawi',
    'Lozi Kingdom': 'Lealui, Zambia',
    'Gaza Empire': 'Mandlakazi, Mozambique',
    'Kingdom of Ndongo': 'Kabasa, Angola',
    'Kingdom of Matamba': 'Matamba, Angola',
    'Kingdom of Loango': 'Loango, Republic of the Congo',
    'Kuba Kingdom': 'Nsheng, Democratic Republic of the Congo',
    'Kingdom of Nri': 'Nri, Anambra, Nigeria',
    'Sultanate of Zanzibar': 'Stone Town, Zanzibar, Tanzania',
    'Greco-Bactrian Kingdom': 'Balkh, Afghanistan',
    'Indo-Greek Kingdom': 'Taxila, Pakistan',
    'Indo-Scythian Kingdom': 'Sirkap, Taxila, Pakistan',
    'Indo-Parthian Kingdom': 'Taxila, Pakistan',
    'Western Satraps': 'Ujjain, India',
    'Shunga Empire': 'Patna, Bihar, India',
    'Kanva Dynasty': 'Patna, Bihar, India',
    'Chera Dynasty': 'Kodungallur, Kerala, India',
    'Pallava Dynasty': 'Kanchipuram, Tamil Nadu, India',
    'Kadamba Dynasty': 'Banavasi, Karnataka, India',
    'Western Chalukya Empire': 'Basavakalyan, Karnataka, India',
    'Eastern Chalukyas': 'Vengi, Andhra Pradesh, India',
    'Chalukya Dynasty': 'Badami, Karnataka, India',
    'Sena Dynasty': 'Nabadwip, West Bengal, India',
    'Gajapati Empire': 'Cuttack, Odisha, India',
    'Ahom Kingdom': 'Sivasagar, Assam, India',
    'Kamarupa Kingdom': 'Guwahati, Assam, India',
    'Kakatiya Dynasty': 'Warangal, Telangana, India',
    'Yadava Dynasty': 'Daulatabad Fort, Maharashtra, India',
    'Malwa Sultanate': 'Mandu, Madhya Pradesh, India',
    'Gujarat Sultanate': 'Ahmedabad, Gujarat, India',
    'Jaunpur Sultanate': 'Jaunpur, Uttar Pradesh, India',
    'Madurai Sultanate': 'Madurai, Tamil Nadu, India',
    'Mysore Kingdom': 'Mysuru, Karnataka, India',
    'Travancore': 'Thiruvananthapuram, Kerala, India',
    'Hyderabad State': 'Hyderabad, Telangana, India',
    'Kalat Khanate': 'Kalat, Balochistan, Pakistan',
    'Khotan Kingdom': 'Hotan, Xinjiang, China',
    'Kingdom of Qocho': 'Gaochang, Turpan, Xinjiang, China',
    'Yarkent Khanate': 'Yarkant County, Xinjiang, China',
    'Dzungar Khanate': 'Yining, Xinjiang, China',
    'Kazakh Khanate': 'Sighnaq, Kazakhstan',
    'Khanate of Bukhara': 'Bukhara, Uzbekistan',
    'Khanate of Khiva': 'Khiva, Uzbekistan',
    'Kokand Khanate': 'Kokand, Uzbekistan',
    'Saffarid Dynasty': 'Zaranj, Afghanistan',
    'Tahirid Dynasty': 'Nishapur, Iran',
    'Ziyarid Dynasty': 'Gorgan, Iran',
    'Artuqids': 'Mardin, Turkey',
    'Danishmendids': 'Sivas, Turkey',
    'Eldiguzids': 'Tabriz, Iran',
    'Qutb Shahi Dynasty': 'Golconda Fort, Hyderabad, India',
    'Adil Shahi Dynasty': 'Bijapur, Karnataka, India',
}

def map_override_query(country):
    names = country.get('names', {})
    return MAP_QUERY_OVERRIDES.get(names.get('en')) or MAP_QUERY_OVERRIDES.get(get_localized_text(names))

def normalize_map_place(value):
    text = str(value or '').strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'^(the|The)\s+', '', text)
    return text.strip(' .。')

def present_day_map_place(country):
    explicit = country.get('map_place') or country.get('map_target')
    if isinstance(explicit, dict):
        explicit = explicit.get('en') or get_localized_text(explicit)
    if explicit:
        return normalize_map_place(explicit)

    successor_text = ((country.get('details') or {}).get('successors') or {}).get('en', '')
    match = re.search(r'present-day region around ([A-Za-z][A-Za-z\s.&/-]*?)(?: and neighboring states|[.,]|$)', successor_text)
    if match:
        return normalize_map_place(match.group(1))

    region = country.get('region', '')
    parenthesized = re.search(r'\(([^)]+)\)', region)
    if parenthesized:
        return normalize_map_place(parenthesized.group(1))
    return ''

def present_country_for_map_place(place, data=None):
    if not place:
        return None
    data = data or get_data()
    normalized_place = normalize_map_place(place).casefold()
    for candidate in public_country_list(data):
        if candidate.get('type') != 'Present':
            continue
        names = candidate.get('names', {})
        possible_names = {
            normalize_map_place(name).casefold()
            for name in names.values()
            if name
        }
        if normalized_place in possible_names:
            return candidate
    return None

def historical_map_center(country):
    capital = country.get('capital', {})
    value = capital.get('en') or get_localized_text(capital)
    value = normalize_map_place(value)
    if not value or value == '-':
        return ''
    return normalize_map_place(re.split(r'\s*/\s*|,', value)[0])

def country_map_target(country, data=None):
    data = data or get_data()
    if country.get('hide_external_links'):
        return None
    if country.get('type') == 'Present':
        return country
    return present_country_for_map_place(present_day_map_place(country), data)

def country_map_query(country, data=None):
    override = map_override_query(country)
    if override:
        return override
    if country.get('type') == 'Present':
        return country.get('names', {}).get('en') or get_localized_text(country.get('names', {}))
    place = present_day_map_place(country)
    center = historical_map_center(country)
    if center and place:
        return f'{center}, {place}'
    if place:
        return place
    if center:
        return center
    return country.get('region') or get_localized_text(country.get('names', {}))

def country_maps_url(country):
    return f"https://www.google.com/maps/search/{quote_plus(country_map_query(country))}"

def country_map_embed_url(country):
    return f"https://maps.google.com/maps?output=embed&q={quote_plus(country_map_query(country))}"

def render_map_embed(country, height=420):
    embed_url = country_map_embed_url(country)
    iframe_html = (
        f'<iframe src="{html_escape(embed_url, quote=True)}" '
        f'style="width:100%;height:{height}px;border:0;border-radius:8px;" '
        'loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>'
    )
    try:
        ui.html(iframe_html, sanitize=False).classes('w-full')
    except TypeError:
        ui.element('iframe') \
            .props(f'src="{embed_url}" loading=lazy referrerpolicy=no-referrer-when-downgrade') \
            .classes('w-full') \
            .style(f'height:{height}px;border:0;border-radius:8px;')

def map_target_note(country):
    target = country_map_target(country)
    if not target or country_key(target) == country_key(country):
        place = present_day_map_place(country)
        if country.get('type') == 'Past' and place:
            return f"{t('map_note')} {place}"
        return ''
    return f"{t('map_note')} {get_localized_text(target.get('names', {}))}"

def set_map_country(country):
    state.map_country_key = country_key(country)
    show_screen('map')

def set_network_country(country):
    state.network_country_key = country_key(country)
    show_screen('network')

DETAIL_RETURN_SCREENS = {
    'main', 'quiz', 'compare', 'timeline', 'map', 'network',
    'account', 'users', 'public_collection', 'rankings', 'social',
}

def result_return_screen():
    screen = getattr(state, 'detail_return_screen', 'main')
    return screen if screen in DETAIL_RETURN_SCREENS and state.current_user else ('main' if state.current_user else 'top')

def open_country_detail(country, return_screen=None):
    source_screen = return_screen or getattr(state, 'current_screen', 'main')
    if source_screen in DETAIL_RETURN_SCREENS:
        state.detail_return_screen = source_screen
    elif source_screen != 'result':
        state.detail_return_screen = 'main'
    state.selected_country = country
    add_history(country)
    show_screen('result')

def today_country():
    data = get_data()
    countries = public_country_list(data)
    if not countries or not state.current_user:
        return None
    seed = f'{app_now().strftime("%Y-%m-%d")}:{state.current_user}'
    index = int(hashlib.sha256(seed.encode('utf-8')).hexdigest(), 16) % len(countries)
    return countries[index]

def related_countries(country, limit=6):
    data = get_data()
    explicit_related = explicit_related_countries(country, data)
    if explicit_related:
        return explicit_related[:limit]
    target_tags = set(country.get('tags', []))
    target_regions = {part.strip() for part in country.get('region', '').replace('/', ',').split(',') if part.strip()}
    target_start = period_start(country)
    target_timeline = timeline_period(country)
    target_languages = profile_value(country, 'languages')
    target_religions = profile_value(country, 'religions')
    scored = []
    for candidate in public_country_list(data):
        if country_key(candidate) == country_key(country):
            continue
        candidate_tags = set(candidate.get('tags', []))
        candidate_regions = {part.strip() for part in candidate.get('region', '').replace('/', ',').split(',') if part.strip()}
        score = len(target_tags & candidate_tags) * 2 + len(target_regions & candidate_regions)
        if target_timeline == timeline_period(candidate):
            score += 2
        candidate_start = period_start(candidate)
        if target_start is not None and candidate_start is not None:
            diff = abs(target_start - candidate_start)
            if diff <= 25:
                score += 4
            elif diff <= 100:
                score += 2
        if target_languages and target_languages == profile_value(candidate, 'languages'):
            score += 2
        if target_religions and target_religions == profile_value(candidate, 'religions'):
            score += 2
        if score:
            scored.append((score, sort_key(candidate), candidate))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [candidate for _, _, candidate in scored[:limit]]

def explicit_related_countries(country, data=None):
    data = data or get_data()
    wanted_names = country.get('related', [])
    if not wanted_names:
        return []
    countries = public_country_list(data)
    related = []
    for wanted in wanted_names:
        wanted_lower = str(wanted).lower()
        for candidate in countries:
            names = candidate.get('names', {})
            if any(str(name).lower() == wanted_lower for name in names.values()):
                related.append(candidate)
                break
    return related

def timeline_period(country):
    start = period_start(country)
    if start is None:
        return 'period_other'
    if start < 500:
        return 'period_ancient'
    if start < 1500:
        return 'period_medieval'
    if start < 1945:
        return 'period_modern'
    return 'period_contemporary'

def quiz_option_count():
    return {'easy': 3, 'medium': 4, 'hard': 5, 'extreme': 8}.get(state.quiz_difficulty, 4)

def quiz_time_limit_seconds():
    return QUIZ_TIME_LIMIT_SECONDS.get(state.quiz_difficulty)

def prepare_quiz_timer(quiz):
    if not isinstance(quiz, dict):
        return quiz
    limit = quiz_time_limit_seconds()
    quiz['timer_token'] = str(uuid.uuid4())
    quiz['started_at_ts'] = app_now().timestamp()
    quiz['time_limit_seconds'] = limit
    quiz['deadline_ts'] = (quiz['started_at_ts'] + limit) if limit else None
    quiz['timed_out'] = False
    return quiz

def quiz_remaining_seconds(quiz):
    if not isinstance(quiz, dict) or quiz.get('answered') or not quiz.get('deadline_ts'):
        return None
    return max(0, math.ceil(float(quiz.get('deadline_ts') or 0) - app_now().timestamp()))

def quiz_difficulty_options():
    options = ['easy', 'medium', 'hard']
    if state.sengoku_mode and sengoku_is_user_eligible():
        options.append('extreme')
    return options

QUIZ_CATEGORY_OPTIONS = [
    ('all', 'quiz_category_all'),
    ('flag', 'quiz_category_flag'),
    ('period', 'quiz_category_period'),
    ('capital', 'quiz_category_capital'),
    ('tag', 'quiz_category_tag'),
    ('desc', 'quiz_category_desc'),
    ('profile', 'quiz_category_profile'),
    ('detail', 'quiz_category_detail'),
]

QUIZ_FORMAT_OPTIONS = [
    ('mixed', 'quiz_format_mixed'),
    ('info_fixed', 'quiz_format_info_fixed'),
    ('country_fixed', 'quiz_format_country_fixed'),
]

QUIZ_SCOPE_OPTIONS = [
    ('all', 'quiz_scope_all'),
    ('past', 'quiz_scope_past'),
    ('present', 'quiz_scope_present'),
]

QUIZ_RANKING_CATEGORIES = [
    ('overall', 'ranking_overall'),
    ('flag', 'quiz_category_flag'),
    ('period', 'quiz_category_period'),
    ('capital', 'quiz_category_capital'),
    ('tag', 'quiz_category_tag'),
    ('desc', 'quiz_category_desc'),
    ('profile', 'quiz_category_profile'),
    ('detail', 'quiz_category_detail'),
]

def quiz_type_group(question_type):
    question_type = quiz_base_type(question_type)
    if question_type in ['flag', 'period', 'capital', 'tag', 'desc']:
        return question_type
    if question_type.startswith('profile_'):
        return 'profile'
    if question_type.startswith('detail_'):
        return 'detail'
    return 'other'

def quiz_ranking_category_label(category):
    for key, label_key in QUIZ_RANKING_CATEGORIES:
        if key == category:
            return t(label_key)
    return t('ranking_overall')

def quiz_stats_for_ranking(record, category):
    ensure_user_defaults(record)
    if category == 'overall':
        stats = record.get('quiz_stats', {}) if isinstance(record.get('quiz_stats'), dict) else {}
        return {
            'answered': int(stats.get('answered', 0) or 0),
            'correct': int(stats.get('correct', 0) or 0),
            'best_streak': int(stats.get('best_streak', 0) or 0),
        }
    answered = 0
    correct = 0
    for entry in record.get('quiz_history', []):
        if not isinstance(entry, dict):
            continue
        if quiz_type_group(entry.get('type')) != category:
            continue
        answered += 1
        if entry.get('correct'):
            correct += 1
    return {'answered': answered, 'correct': correct, 'best_streak': 0}

def quiz_ranking_profiles(category):
    user_data = load_user_data()
    users = get_users(user_data)
    public_profiles = {profile['username']: profile for profile in public_user_profiles()}
    rows = []
    for username, record in users.items():
        if is_guest_record(username, record) or not isinstance(record, dict):
            continue
        ensure_user_defaults(record)
        if is_public_profile_hidden(record):
            continue
        stats = quiz_stats_for_ranking(record, category)
        if category != 'overall' and stats['answered'] <= 0:
            continue
        profile = public_profiles.get(username, {
            'username': username,
            'name_color': DEFAULT_NAME_COLOR,
            'avatar_url': None,
            'avatar': {'mode': 'default'},
        })
        row = dict(profile)
        row['ranking_answered'] = stats['answered']
        row['ranking_correct'] = stats['correct']
        row['ranking_best_streak'] = stats['best_streak']
        rows.append(row)
    return sorted(
        rows,
        key=lambda profile: (
            -int(profile.get('ranking_correct', 0) or 0),
            int(profile.get('ranking_answered', 0) or 0),
            profile.get('username', '').lower(),
        ),
    )

def quiz_question_matches_category(question_type):
    category = getattr(state, 'quiz_category', 'all')
    question_type = quiz_base_type(question_type)
    if category == 'all':
        return True
    if category in ['flag', 'period', 'capital', 'tag', 'desc']:
        return question_type == category
    if category == 'profile':
        return question_type.startswith('profile_')
    if category == 'detail':
        return question_type.startswith('detail_')
    return True

def quiz_question_matches_format(question_type):
    quiz_format = getattr(state, 'quiz_format', 'mixed')
    if quiz_format == 'info_fixed':
        return not quiz_is_reverse(question_type)
    if quiz_format == 'country_fixed':
        return quiz_is_reverse(question_type)
    return True

def quiz_country_matches_scope(country):
    scope = getattr(state, 'quiz_scope', 'all')
    country_type = str(country.get('type') or '')
    if scope == 'past':
        return country_type == 'Past'
    if scope == 'present':
        return country_type == 'Present'
    return True

def quiz_country_pool(data=None):
    return [country for country in public_country_list(data) if quiz_country_matches_scope(country)]

def quiz_base_question_types():
    question_types = ['desc', 'capital', 'tag', 'flag', 'period']
    question_types.extend(f'profile_{field}' for field in PROFILE_FIELDS)
    question_types.extend(f'detail_{field}' for field in DETAIL_QUIZ_FIELDS)
    return question_types

def quiz_pool_cache_key(countries):
    return (
        DATA_CACHE_MTIME,
        state.lang,
        getattr(state, 'quiz_scope', 'all'),
        len(countries),
    )

def quiz_pool_data(countries):
    cache_key = quiz_pool_cache_key(countries)
    if QUIZ_POOL_CACHE.get('key') == cache_key and QUIZ_POOL_CACHE.get('value'):
        return QUIZ_POOL_CACHE['value']

    tag_counts = quiz_tag_counts(countries)
    tag_options = all_quiz_tags(countries, tag_counts)
    base_question_types = quiz_base_question_types()
    option_candidate_keys = {
        question_type: [
            country_key(country)
            for country in quiz_candidates_for_type(countries, question_type, tag_counts, len(countries))
        ]
        for question_type in base_question_types
    }
    pool = {
        'tag_counts': tag_counts,
        'tag_options': tag_options,
        'base_question_types': base_question_types,
        'option_candidate_keys': option_candidate_keys,
    }
    QUIZ_POOL_CACHE['key'] = cache_key
    QUIZ_POOL_CACHE['value'] = pool
    return pool

def resolve_quiz_candidates(candidate_keys, lookup):
    return [lookup[key] for key in candidate_keys if key in lookup]

def has_quiz_flag(country):
    return has_quiz_visual_flag_code(country.get('flag_code'))

def normalized_text(value):
    return str(value or '').strip().casefold()

def country_name_set(country):
    names = country.get('names', {})
    if not isinstance(names, dict):
        return {normalized_text(names)}
    return {normalized_text(value) for value in names.values() if normalized_text(value)}

def quiz_tag_counts(countries):
    counts = {}
    for country in countries:
        for tag in set(country.get('tags', [])):
            counts[tag] = counts.get(tag, 0) + 1
    return counts

def eligible_quiz_tags_for_country(country, countries, tag_counts=None, tag_total=None):
    tags = [tag for tag in country.get('tags', []) if tag]
    if not tags:
        return []
    counts = tag_counts or quiz_tag_counts(countries)
    total = tag_total if tag_total is not None else len(countries)
    return [
        tag for tag in tags
        if counts.get(tag, 0) >= 2 and counts.get(tag, 0) < total
    ]

def choose_quiz_tag(country, countries, tag_counts=None, tag_total=None):
    tags = eligible_quiz_tags_for_country(country, countries, tag_counts, tag_total)
    return random.choice(tags) if tags else None

def quiz_display_value(country, question_type):
    question_type = quiz_base_type(question_type)
    if question_type == 'capital':
        return get_localized_text(country.get('capital', {}))
    if question_type == 'flag':
        return ''
    if question_type == 'period':
        return period_label(country)
    if question_type == 'desc':
        return first_sentence(get_localized_text(country.get('desc', {})))
    if question_type.startswith('profile_'):
        field = question_type.replace('profile_', '', 1)
        return profile_value(country, field)
    if question_type.startswith('detail_'):
        field = question_type.replace('detail_', '', 1)
        return detail_quiz_sentence(country, field)
    return ''

def quiz_reverse_field_label(question_type):
    question_type = quiz_base_type(question_type)
    if question_type.startswith('profile_'):
        return t('labels', question_type.replace('profile_', '', 1))
    if question_type.startswith('detail_'):
        return t(question_type.replace('detail_', '', 1))
    return ''

def normalized_flag_identity(country):
    code = str(country.get('flag_code') or '').strip()
    lower = code.lower()
    equivalences = [
        ('flag-japan', ['jp', 'flag_of_japan.svg']),
        ('flag-france', ['fr', 'flag_of_france.svg']),
        ('flag-sweden', ['se', 'flag_of_sweden.svg']),
        ('flag-tonga', ['to', 'flag_of_tonga.svg']),
    ]
    for identity, tokens in equivalences:
        if lower in tokens or any(token in lower for token in tokens):
            return identity
    return lower

def quiz_question_value(country, question_type):
    question_type = quiz_base_type(question_type)
    if question_type == 'capital':
        return normalized_text(get_localized_text(country.get('capital', {})))
    if question_type == 'flag':
        return normalized_flag_identity(country)
    if question_type == 'period':
        return normalized_text(period_label(country))
    if question_type == 'desc':
        return normalized_text(first_sentence(get_localized_text(country.get('desc', {}))))
    if question_type.startswith('profile_'):
        field = question_type.replace('profile_', '', 1)
        return normalized_text(profile_value(country, field))
    if question_type.startswith('detail_'):
        field = question_type.replace('detail_', '', 1)
        return normalized_text(detail_quiz_sentence(country, field))
    return ''

def quiz_option_signature(label=None, image=None):
    image_signature = str(image or '').strip().casefold()
    if image_signature:
        return ('image', image_signature)
    return ('label', normalized_text(label))

def quiz_candidates_for_type(countries, question_type, tag_counts=None, tag_total=None):
    question_type = quiz_base_type(question_type)
    if question_type == 'desc':
        return [c for c in countries if quiz_question_value(c, question_type)]
    if question_type == 'capital':
        return [c for c in countries if quiz_question_value(c, question_type) not in ['', '-']]
    if question_type == 'tag':
        return [c for c in countries if eligible_quiz_tags_for_country(c, countries, tag_counts, tag_total)]
    if question_type == 'flag':
        return [c for c in countries if has_quiz_flag(c)]
    if question_type == 'period':
        return [c for c in countries if quiz_question_value(c, question_type)]
    if question_type.startswith('profile_'):
        return [c for c in countries if quiz_question_value(c, question_type)]
    if question_type.startswith('detail_'):
        return [c for c in countries if quiz_question_value(c, question_type)]
    return []

def build_quiz_options(answer, question_type, countries, candidates=None):
    desired_count = quiz_option_count()
    answer_key = country_key(answer)
    answer_names = country_name_set(answer)
    answer_value = quiz_question_value(answer, question_type)
    selected = [answer]
    used_keys = {answer_key}
    used_names = set(answer_names)
    used_values = {answer_value} if answer_value else set()

    candidates = list(candidates) if candidates is not None else quiz_candidates_for_type(countries, question_type)
    random.shuffle(candidates)
    for candidate in candidates:
        key = country_key(candidate)
        if key in used_keys:
            continue
        candidate_names = country_name_set(candidate)
        if used_names.intersection(candidate_names):
            continue
        candidate_value = quiz_question_value(candidate, question_type)
        if candidate_value and candidate_value in used_values:
            continue
        selected.append(candidate)
        used_keys.add(key)
        used_names.update(candidate_names)
        if candidate_value:
            used_values.add(candidate_value)
        if len(selected) >= desired_count:
            break

    if len(selected) < 2:
        return []
    random.shuffle(selected)
    return selected

def build_tag_quiz_options(answer, tag, countries):
    desired_count = quiz_option_count()
    answer_key = country_key(answer)
    selected = [answer]
    used_keys = {answer_key}
    used_names = set(country_name_set(answer))

    candidates = [
        country for country in countries
        if tag not in country.get('tags', []) and country_key(country) != answer_key
    ]
    random.shuffle(candidates)
    for candidate in candidates:
        key = country_key(candidate)
        if key in used_keys:
            continue
        candidate_names = country_name_set(candidate)
        if used_names.intersection(candidate_names):
            continue
        selected.append(candidate)
        used_keys.add(key)
        used_names.update(candidate_names)
        if len(selected) >= desired_count:
            break

    if len(selected) < 2:
        return []
    random.shuffle(selected)
    return selected

def all_quiz_tags(countries, tag_counts=None):
    counts = tag_counts or quiz_tag_counts(countries)
    total = len(countries)
    return sorted(
        [tag for tag, count in counts.items() if count >= 2 and count < total],
        key=lambda tag: tag_label(tag).lower(),
    )

def reverse_quiz_answer_option(answer, question_type, countries, tag_counts=None, tag_total=None):
    base_type = quiz_base_type(question_type)
    if base_type == 'tag':
        tag = choose_quiz_tag(answer, countries, tag_counts, tag_total)
        if not tag:
            return None
        return {
            'value': tag,
            'label': tag_label(tag),
            'image': None,
            'tag': tag,
        }
    if base_type == 'flag':
        value = quiz_question_value(answer, base_type)
        if not value:
            return None
        return {
            'value': value,
            'label': t('quiz_select_option'),
            'image': get_flag_url(answer.get('flag_code')),
        }
    value = quiz_question_value(answer, base_type)
    label = quiz_display_value(answer, base_type)
    if not value or not label or label == '-':
        return None
    return {'value': value, 'label': label, 'image': None}

def build_reverse_quiz_options(answer, question_type, countries, tag_counts=None, candidates_by_type=None, all_tags=None):
    desired_count = quiz_option_count()
    base_type = quiz_base_type(question_type)
    answer_payload = reverse_quiz_answer_option(answer, question_type, countries, tag_counts, len(countries))
    if not answer_payload:
        return None

    answer_value = answer_payload['value']
    options = [answer_value]
    labels = {answer_value: answer_payload.get('label', str(answer_value))}
    images = {}
    if answer_payload.get('image'):
        images[answer_value] = answer_payload['image']
    used_signatures = {
        quiz_option_signature(
            answer_payload.get('label', str(answer_value)),
            answer_payload.get('image'),
        )
    }

    if base_type == 'tag':
        tag_options = all_tags if all_tags is not None else all_quiz_tags(countries, tag_counts)
        candidates = [tag for tag in tag_options if tag != answer_value and tag not in answer.get('tags', [])]
        random.shuffle(candidates)
        for tag in candidates:
            label = tag_label(tag)
            signature = quiz_option_signature(label)
            if signature in used_signatures:
                continue
            options.append(tag)
            labels[tag] = label
            used_signatures.add(signature)
            if len(options) >= desired_count:
                break
    else:
        candidates = list((candidates_by_type or {}).get(base_type) or quiz_candidates_for_type(countries, base_type, tag_counts))
        random.shuffle(candidates)
        for candidate in candidates:
            if country_key(candidate) == country_key(answer):
                continue
            value = quiz_question_value(candidate, base_type)
            if not value or value in options:
                continue
            label = quiz_display_value(candidate, base_type)
            image = None
            if base_type == 'flag':
                label = t('quiz_select_option')
                image = get_flag_url(candidate.get('flag_code'))
            if not label and not image:
                continue
            signature = quiz_option_signature(label, image)
            if signature in used_signatures:
                continue
            options.append(value)
            labels[value] = label
            if image:
                images[value] = image
            used_signatures.add(signature)
            if len(options) >= desired_count:
                break

    if len(options) < 2:
        return None
    random.shuffle(options)
    payload = {
        'options': options,
        'answer_option': answer_value,
        'option_labels': labels,
        'option_images': images,
        'option_mode': 'value',
    }
    if answer_payload.get('tag'):
        payload['tag'] = answer_payload['tag']
    return payload

def build_quiz():
    data = get_data()
    countries = quiz_country_pool(data)
    if len(countries) < 4:
        return None
    lookup = public_countries_by_key(data)
    pool = quiz_pool_data(countries)
    tag_counts = pool['tag_counts']
    tag_options = pool['tag_options']
    option_candidate_keys = pool['option_candidate_keys']
    answer_source_keys = None
    if state.quiz_mode == 'review':
        review_source = [lookup[key] for key in get_review_keys() if key in lookup]
        if not review_source:
            return None
        answer_source_keys = {country_key(country) for country in review_source}

    base_question_types = pool['base_question_types']
    question_types = []
    for question_type in base_question_types:
        question_types.append(question_type)
        question_types.append(f'{question_type}_reverse')

    question_pools = []
    for question_type in question_types:
        if not quiz_question_matches_format(question_type):
            continue
        if not quiz_question_matches_category(question_type):
            continue
        candidates = option_candidate_keys.get(quiz_base_type(question_type), [])
        if answer_source_keys is not None:
            candidates = [key for key in candidates if key in answer_source_keys]
        if candidates:
            question_pools.append((question_type, candidates))
    if not question_pools:
        return None

    resolved_candidates_cache = {}

    def resolved_candidates_for(question_type, candidate_keys):
        base_type = quiz_base_type(question_type)
        if base_type not in resolved_candidates_cache:
            resolved_candidates_cache[base_type] = resolve_quiz_candidates(candidate_keys, lookup)
        return resolved_candidates_cache[base_type]

    for _ in range(45):
        question_type, candidate_keys = random.choice(question_pools)
        answer_key = random.choice(candidate_keys)
        answer = lookup.get(answer_key)
        if not answer:
            continue
        candidates = resolved_candidates_for(question_type, candidate_keys)
        quiz_tag = None
        reverse_payload = None
        if quiz_is_reverse(question_type):
            reverse_payload = build_reverse_quiz_options(
                answer,
                question_type,
                countries,
                tag_counts=tag_counts,
                candidates_by_type={quiz_base_type(question_type): candidates},
                all_tags=tag_options,
            )
            if not reverse_payload:
                continue
            options = reverse_payload['options']
            quiz_tag = reverse_payload.get('tag')
        elif quiz_base_type(question_type) == 'tag':
            quiz_tag = choose_quiz_tag(answer, countries, tag_counts, len(countries))
            if not quiz_tag:
                continue
            options = build_tag_quiz_options(answer, quiz_tag, countries)
        else:
            options = build_quiz_options(
                answer,
                question_type,
                countries,
                candidates=candidates,
            )
        if options:
            if reverse_payload:
                option_values = list(options)
            else:
                option_values = [country_key(option) for option in options]
            quiz = {
                'type': question_type,
                'answer_key': country_key(answer),
                'options': option_values,
                'selected_key': None,
                'answered': False,
            }
            if reverse_payload:
                quiz.update(reverse_payload)
            if quiz_tag:
                quiz['tag'] = quiz_tag
            return quiz

    return None

def quiz_view_parts(quiz, answer):
    raw_question_type = quiz.get('type')
    question_type = quiz_base_type(raw_question_type)
    country_name = get_localized_text(answer.get('names', {}))
    if quiz_is_reverse(raw_question_type):
        if question_type == 'capital':
            return t('quiz_capital_reverse').format(country=country_name), '', None
        if question_type == 'flag':
            return t('quiz_flag_reverse').format(country=country_name), '', None
        if question_type == 'period':
            return t('quiz_period_reverse').format(country=country_name), '', None
        if question_type == 'tag':
            return t('quiz_tag_reverse').format(country=country_name), '', None
        if question_type == 'desc':
            return t('quiz_desc_reverse').format(country=country_name), '', None
        if question_type.startswith('profile_'):
            return t('quiz_profile_reverse').format(country=country_name, label=quiz_reverse_field_label(question_type)), '', None
        if question_type.startswith('detail_'):
            return t('quiz_detail_reverse').format(country=country_name, label=quiz_reverse_field_label(question_type)), '', None
    if question_type == 'capital':
        capital = get_localized_text(answer.get('capital', {}))
        question = t('quiz_capital').format(capital=capital)
        return question, '', None
    elif question_type == 'flag':
        question = t('quiz_flag')
        image = get_flag_url(answer.get('flag_code'))
        return question, '', image
    elif question_type == 'period':
        question = t('quiz_period').format(period=period_label(answer))
        return question, '', None
    elif question_type == 'tag':
        question = t('quiz_tag').format(tag=tag_label(quiz.get('tag')))
        return question, '', None
    elif question_type.startswith('profile_'):
        field = question_type.replace('profile_', '', 1)
        value = profile_value(answer, field)
        question = t('quiz_profile').format(label=t('labels', field), value=value)
        return question, '', None
    elif question_type.startswith('detail_'):
        field = question_type.replace('detail_', '', 1)
        value = detail_quiz_sentence(answer, field)
        question = t('quiz_profile').format(label=t(field), value=first_sentence(value))
        return question, '', None
    else:
        question = t('quiz_desc')
        description = first_sentence(get_localized_text(answer.get('desc', {})))
        return question, description, None

def start_quiz(mode=None):
    if not state.current_user:
        ui.notify(t('login_required'), color='warning')
        show_screen('top')
        return
    if mode:
        state.quiz_mode = mode
    if state.quiz_difficulty not in quiz_difficulty_options():
        state.quiz_difficulty = 'hard'
    state.quiz = prepare_quiz_timer(build_quiz())
    if state.quiz_mode == 'review' and not state.quiz:
        ui.notify(t('review_empty'), color='info')
        state.quiz_mode = 'normal'
        state.quiz = prepare_quiz_timer(build_quiz())
    show_screen('quiz')

def set_quiz_difficulty(difficulty):
    if difficulty not in quiz_difficulty_options():
        difficulty = 'hard'
    state.quiz_difficulty = difficulty
    start_quiz()

def set_quiz_category(category):
    state.quiz_category = category
    start_quiz()

def set_quiz_format(quiz_format):
    if quiz_format not in [key for key, _ in QUIZ_FORMAT_OPTIONS]:
        quiz_format = 'mixed'
    state.quiz_format = quiz_format
    start_quiz()

def set_quiz_scope(scope):
    if scope not in [key for key, _ in QUIZ_SCOPE_OPTIONS]:
        scope = 'all'
    state.quiz_scope = scope
    start_quiz()

def quiz_answer_option(quiz):
    return quiz.get('answer_option') or quiz.get('answer_key')

def crown_marks(count):
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 0
    return '👑' * max(0, count)

def raw_profile_value(country, field):
    value = (country.get('profile') or {}).get(field)
    if isinstance(value, dict):
        return value.get('en') or value.get('ja') or next((v for v in value.values() if v), '')
    return value or ''

def parse_profile_number(value):
    text = str(value or '')
    match = re.search(r'\d+(?:[,.]\d+)*', text)
    if not match:
        return 1
    number = float(match.group(0).replace(',', ''))
    lower = text.lower()
    if 'billion' in lower:
        number *= 1_000_000_000
    elif 'million' in lower:
        number *= 1_000_000
    elif 'thousand' in lower:
        number *= 1_000
    elif '億' in text or '亿' in text:
        number *= 100_000_000
    elif '万' in text:
        number *= 10_000
    return max(1, number)

def parse_optional_profile_number(value):
    text = str(value or '')
    match = re.search(r'\d+(?:[,.]\d+)*', text)
    if not match:
        return None
    try:
        number = float(match.group(0).replace(',', ''))
    except ValueError:
        return None
    lower = text.lower()
    if 'billion' in lower:
        number *= 1_000_000_000
    elif 'million' in lower:
        number *= 1_000_000
    elif 'thousand' in lower:
        number *= 1_000
    elif '億' in text or '亿' in text:
        number *= 100_000_000
    elif '万' in text:
        number *= 10_000
    return number if number > 0 else None

def area_population_product_label():
    labels = {
        'ja': '面積×人口',
        'en': 'Area x Population',
        'zh': '面积×人口',
    }
    return labels.get(state.lang, labels['en'])

def area_population_product_value(country):
    area = parse_optional_profile_number(raw_profile_value(country, 'area'))
    population = parse_optional_profile_number(raw_profile_value(country, 'population'))
    if area is None or population is None:
        return ''
    return format_battle_number(int(area * population))

def country_battle_raw_power(country):
    area = parse_profile_number(raw_profile_value(country, 'area'))
    population = parse_profile_number(raw_profile_value(country, 'population'))
    return max(1, int(area * population))

def country_battle_power(country):
    raw_power = country_battle_raw_power(country)
    return max(1, int(math.sqrt(raw_power) * BATTLE_POWER_SCALE))

def format_battle_number(value):
    try:
        return f'{int(value):,}'
    except (TypeError, ValueError):
        return str(value)

def battle_country_list(data=None):
    data = data or get_data()
    return list(data.get('countries', []))

def battle_country_keys(data=None):
    return [country_key(country) for country in battle_country_list(data)]

def battle_unlock_country_keys(data=None):
    return [country_key(country) for country in public_country_list(data) if country.get('type') == 'Present']

def all_public_country_keys(data=None):
    return [country_key(country) for country in public_country_list(data)]

def user_viewed_all_public_countries(user, data=None):
    if not user:
        return False
    ensure_user_defaults(user)
    needed = set(all_public_country_keys(data))
    return bool(needed) and needed.issubset(set(user.get('viewed_keys', [])))

def battle_country_lookup(data=None):
    return {country_key(country): country for country in battle_country_list(data)}

def is_battle_bot(username):
    return str(username or '').startswith(BOT_USERNAME)

def battle_world_war_active(room):
    start_turn = battle_room_world_war_turn(room)
    if start_turn == BATTLE_WORLD_WAR_DISABLED:
        return bool((room or {}).get('world_war_started'))
    try:
        return int((room or {}).get('turn', 1)) >= start_turn or bool((room or {}).get('world_war_started'))
    except (TypeError, ValueError):
        return bool((room or {}).get('world_war_started'))

def battle_revolution_active(room):
    try:
        return int((room or {}).get('turn', 1)) <= int((room or {}).get('revolution_until_turn', 0) or 0)
    except (TypeError, ValueError):
        return False

def battle_flag_only_active(room):
    try:
        return int((room or {}).get('turn', 1)) <= int((room or {}).get('flag_only_until_turn', 0) or 0)
    except (TypeError, ValueError):
        return False

def battle_vatican_active(room):
    try:
        return int((room or {}).get('turn', 1)) <= int((room or {}).get('vatican_until_turn', 0) or 0)
    except (TypeError, ValueError):
        return False

def battle_replace_active(room):
    try:
        return int((room or {}).get('turn', 1)) <= int((room or {}).get('replace_until_turn', 0) or 0)
    except (TypeError, ValueError):
        return False

def battle_bomb_active(room):
    try:
        return int((room or {}).get('turn', 1)) <= int((room or {}).get('bomb_until_turn', 0) or 0)
    except (TypeError, ValueError):
        return False

def battle_lytton_active(room):
    try:
        return int((room or {}).get('turn', 1)) <= int((room or {}).get('lytton_until_turn', 0) or 0)
    except (TypeError, ValueError):
        return False

def battle_damage_surge_active(room):
    try:
        return int((room or {}).get('turn', 1)) <= int((room or {}).get('damage_surge_until_turn', 0) or 0)
    except (TypeError, ValueError):
        return False

def battle_operation_confusion_active(room):
    return battle_room_events_enabled(room) and battle_damage_surge_active(room)

def battle_random_target_active(room):
    try:
        return (
            battle_room_events_enabled(room)
            and (room or {}).get('mode') in [FFA_MODE, TEAM_MODE]
            and int((room or {}).get('turn', 1)) <= int((room or {}).get('random_target_until_turn', 0) or 0)
        )
    except (TypeError, ValueError):
        return False

def battle_ceasefire_active(room):
    try:
        return int((room or {}).get('turn', 1)) <= int((room or {}).get('ceasefire_until_turn', 0) or 0)
    except (TypeError, ValueError):
        return False

def battle_command_surge_active(room):
    try:
        return int((room or {}).get('turn', 1)) <= int((room or {}).get('command_surge_until_turn', 0) or 0)
    except (TypeError, ValueError):
        return False

def battle_supply_drop_active(room):
    try:
        return int((room or {}).get('turn', 1)) <= int((room or {}).get('supply_drop_until_turn', 0) or 0)
    except (TypeError, ValueError):
        return False

def battle_blockade_active(room):
    try:
        return int((room or {}).get('turn', 1)) <= int((room or {}).get('blockade_until_turn', 0) or 0)
    except (TypeError, ValueError):
        return False

def battle_exclusive_event_active(room):
    return any([
        battle_revolution_active(room),
        battle_flag_only_active(room),
        battle_vatican_active(room),
        battle_replace_active(room),
        battle_bomb_active(room),
        battle_lytton_active(room),
        battle_damage_surge_active(room),
        battle_random_target_active(room),
        battle_ceasefire_active(room),
        battle_command_surge_active(room),
        battle_supply_drop_active(room),
        battle_blockade_active(room),
    ])

def battle_event_damage_multiplier(room, player=None):
    if not battle_room_events_enabled(room):
        return 1
    multiplier = 1
    if battle_ceasefire_active(room):
        multiplier *= BATTLE_CEASEFIRE_DAMAGE_MULTIPLIER
    return multiplier

def battle_group_event_damage_multiplier(room, players):
    multipliers = [battle_event_damage_multiplier(room, player) for player in players or []]
    return max(multipliers) if multipliers else battle_event_damage_multiplier(room)

def ensure_battle_operation_required_count(room):
    if not battle_operation_confusion_active(room):
        return None
    turn = int((room or {}).get('turn', 1) or 1)
    try:
        current_turn = int((room or {}).get('operation_required_turn', 0) or 0)
        current_count = int((room or {}).get('operation_required_count', 0) or 0)
    except (TypeError, ValueError):
        current_turn = 0
        current_count = 0
    if current_turn != turn or current_count < 1 or current_count > 5:
        room['operation_required_turn'] = turn
        room['operation_required_count'] = random.randint(1, 5)
    return int(room.get('operation_required_count', 1) or 1)

def operation_confusion_missing_count(room, entry):
    required = ensure_battle_operation_required_count(room)
    if not required or not entry or entry.get('defenseless'):
        return 0
    return max(0, required - len(entry.get('keys', [])))

def operation_confusion_triggered(room, entry):
    missing = operation_confusion_missing_count(room, entry)
    if missing <= 0:
        return False, 0
    chance = min(100, missing * BATTLE_OPERATION_CONFUSION_MISSING_CHANCE_PERCENT)
    return random.randint(1, 100) <= chance, missing

def operation_confusion_group_triggered(room, entries, players):
    triggered = []
    missing_total = 0
    for player in players:
        hit, missing = operation_confusion_triggered(room, entries.get(player))
        if hit:
            triggered.append(player)
            missing_total += missing
    return triggered, missing_total

def record_operation_confusion_self_damage(room, actor_label, damage, missing, result_parts, visual=None, player=None, team=None):
    damage = max(0, int(damage or 0))
    if team is not None:
        dealt = battle_apply_team_self_damage(room, team, damage)
    else:
        dealt = battle_apply_damage_to_player_or_team(room, player or actor_label, damage)
    result_parts.append(t('battle_operation_self_damage_log').format(
        player=actor_label,
        missing=missing,
        damage=format_battle_number(dealt),
    ))
    if isinstance(visual, dict):
        visual.setdefault('self_damage', []).append({
            'player': actor_label,
            'name': t('battle_damage_surge_title'),
            'damage': dealt,
        })
    return dealt

def apply_random_target_event(room, entries, result_parts):
    if not battle_random_target_active(room):
        return
    players = active_battle_players(room)
    if room.get('mode') == FFA_MODE:
        for player, entry in entries.items():
            if entry.get('defenseless') or entry.get('power', 0) <= 0:
                continue
            candidates = [target for target in players if target != player]
            if not candidates:
                continue
            target = random.choice(candidates)
            entry['target'] = target
            result_parts.append(t('battle_random_target_log').format(player=player, target=target))
        return
    if room.get('mode') == TEAM_MODE:
        teams = room.get('teams', {})
        team_hp = ensure_battle_team_hp(room)
        alive_teams = sorted({
            teams.get(player)
            for player in players
            if teams.get(player) and team_hp.get(teams.get(player), 0) > 0
        })
        if not alive_teams:
            return
        for player, entry in entries.items():
            if entry.get('defenseless') or entry.get('power', 0) <= 0:
                continue
            target = random.choice(alive_teams)
            entry['target'] = target
            result_parts.append(t('battle_random_target_log').format(
                player=player,
                target=f"{t('battle_team')} {target}",
            ))

def battle_vatican_country_key(data=None):
    for country in battle_country_list(data):
        names = country.get('names', {})
        values = names.values() if isinstance(names, dict) else [names]
        joined = ' '.join(str(value or '').casefold() for value in values)
        if 'vatican' in joined or 'バチカン' in joined or '梵蒂冈' in joined:
            return country_key(country)
    return None

def battle_special_card_label(key):
    suffix = str(key or '').replace(BATTLE_SPECIAL_CARD_PREFIX, '', 1)
    return t(f'battle_special_{suffix}')

def is_battle_special_card(key):
    return str(key or '') in BATTLE_SPECIAL_CARDS

def is_battle_playable_special_card(key):
    return str(key or '') == BATTLE_BOMB_CARD

def is_battle_selectable_card(key):
    return not is_battle_special_card(key) or is_battle_playable_special_card(key)

def is_battle_power_card(key):
    return not is_battle_special_card(key)

def battle_special_card_damage(key, hp_limit=BATTLE_MAX_HP):
    card = BATTLE_SPECIAL_CARDS.get(str(key or ''), {})
    if not card.get('damage_percent'):
        return 0
    try:
        hp_limit = int(hp_limit)
    except (TypeError, ValueError):
        hp_limit = BATTLE_MAX_HP
    return max(1, hp_limit * int(card.get('damage_percent', 1)) // 100)

def battle_special_card_heal(key, hp_limit=BATTLE_MAX_HP):
    card = BATTLE_SPECIAL_CARDS.get(str(key or ''), {})
    if not card.get('heal_percent'):
        return 0
    try:
        hp_limit = int(hp_limit)
    except (TypeError, ValueError):
        hp_limit = BATTLE_MAX_HP
    return max(1, hp_limit * int(card.get('heal_percent', 1)) // 100)

def battle_power_bounds():
    global BATTLE_POWER_BOUNDS_CACHE
    mtime = file_mtime(JSON_FILE)
    cached = BATTLE_POWER_BOUNDS_CACHE.get('value')
    if cached and BATTLE_POWER_BOUNDS_CACHE.get('mtime') == mtime:
        return cached
    powers = [country_battle_power(country) for country in battle_country_list()]
    if not powers:
        value = (1, 1)
    else:
        value = (min(powers), max(powers))
    BATTLE_POWER_BOUNDS_CACHE = {'mtime': mtime, 'value': value}
    return value

def battle_card_power_for_key(key, lookup=None, room=None):
    lookup = lookup or battle_country_lookup()
    country = lookup.get(key)
    if not country:
        return 0
    power = country_battle_power(country)
    if battle_revolution_active(room):
        min_power, max_power = battle_power_bounds()
        return max(1, max_power + min_power - power)
    return power

def battle_bomb_cover_key(room, lookup=None):
    if not isinstance(room, dict):
        return None
    lookup = lookup or battle_country_lookup()
    cover_key = str(room.get('bomb_cover_key') or '')
    if cover_key in lookup:
        return cover_key
    candidates = [key for key in battle_country_keys() if key in lookup]
    if not candidates:
        return None
    cover_key = random.choice(candidates)
    room['bomb_cover_key'] = cover_key
    return cover_key

def battle_bomb_cover_country(room, lookup=None):
    lookup = lookup or battle_country_lookup()
    key = battle_bomb_cover_key(room, lookup)
    return lookup.get(key) if key else None

def battle_card_display_name(key, lookup=None, room=None, reveal_bomb=False):
    if is_battle_special_card(key):
        if str(key or '') == BATTLE_BOMB_CARD and not reveal_bomb:
            country = battle_bomb_cover_country(room, lookup)
            if country:
                return get_localized_text(country.get('names', {}))
        return battle_special_card_label(key)
    lookup = lookup or battle_country_lookup()
    country = lookup.get(key)
    if country and battle_flag_only_active(room):
        return t('battle_hidden_card_name')
    return get_localized_text(country.get('names', {})) if country else str(key)

def battle_mode_label(mode):
    if mode == FFA_MODE:
        return t('battle_mode_free_for_all')
    if mode == TEAM_MODE:
        return t('battle_mode_team')
    if mode == BOT_MODE:
        return t('battle_bot')
    return t('battle_mode_duel')

def _legacy_battle_help_labels():
    labels = {
        'ja': {
            'title': '国力対戦の遊び方',
            'sections': [
                (
                    'まず何をする？',
                    [
                        '配られた5枚の国カードから、今回勝負に出す国を1枚以上選びます。',
                        '出さなかった国は防御に回ります。全部出して押し切るか、守りを残すかを考えて選びましょう。',
                        '手札がなくなるまで新しい国は補充されません。空になった次のターンは無防備になり、その後で新しい5枚が配られます。',
                        'カードを出すには指揮力を使います。守りに残すカードが多いほど次のターンに指揮力が戻ります。',
                        '各ターンに1回だけ、指揮力を使って今の手札をすべて捨て、同じ枚数を引き直せます。',
                        '思考時間は部屋ごとに1分・3分・5分・無制限から選べます。時間切れになると降参扱いになり、1対1とBOT戦ではその場で決着し、乱戦とチーム戦ではその枠をBOTが引き継ぎます。',
                    ],
                ),
                (
                    '勝敗とダメージ',
                    [
                        f'HPが0になると負けです。開始時のHPは{format_battle_number(BATTLE_MAX_HP)}です。',
                        '出した国の国力を比べ、強い側が相手にダメージを与えます。',
                        '国力は面積と人口をもとにしますが、巨大国家だけが突出しすぎないように平方根で圧縮しています。',
                        '複数枚出すと、2枚目以降は少しずつ力が抑えられます。たくさん出すほど強い一方、手札切れの危険も増えます。',
                        'ダメージは国力の差から相手の防御を引いて決まります。防御は受けるダメージを減らします。',
                        '防御が攻撃を上回った場合は、上回った分がカウンターダメージとして攻撃側に返ります。',
                        '長引くほど少しずつダメージが伸び、部屋で選んだターン以降は第三次世界大戦でさらに激しくなります。開始しない設定にもできます。',
                        '第三次世界大戦中は危険カードが混ざることがあり、ターン終了時に自分へダメージを与えて消えます。',
                        'さらに低確率で革命が起こり、カードの強弱がしばらく逆転します。',
                        'まれに国名が伏せられる、手札が入れ替わる、爆弾カードが回る、ダメージが大きく跳ね上がるなどのイベントも発生します。',
                        'ダメージを与えると、相手の残り手札から1枚奪えます。BOT戦の勝利数はランキングに入りません。',
                    ],
                ),
                (
                    'モード別ルール',
                    [
                        '1対1では、相手と正面から国力をぶつけ合います。',
                        '乱戦では、自分で攻撃対象を指定して攻撃します。誰を狙うかも作戦です。',
                        'チーム戦では、チーム全員がそれぞれ手札を出します。出した国はチームの総攻撃、出さなかった国はチームの総防御になります。',
                        f'チーム戦のHPは「{format_battle_number(BATTLE_MAX_HP)} x チーム人数」です。人数差がある場合は、多い側の人数に合わせて両チームのHPをそろえます。',
                        'チーム戦ではチームチャットを使えます。どの国を出すか、守りを残すかを相談できます。',
                    ],
                ),
                (
                    '一致ボーナス',
                    [
                        '同じターンに出した国同士、または防御に残した国同士で、タグや地域が重なると強力なボーナスが入ります。',
                        '1枚だけでは発動しません。相手のカードとの一致も関係ありません。',
                        '一致したタグや地域が1種類増えるごとに、攻撃または防御が+50%されます。1個で1.5倍、2個で2倍のように伸びるため、国の組み合わせが勝敗を大きく左右します。',
                    ],
                ),
            ],
        },
        'en': {
            'title': 'How to Play Power Battle',
            'sections': [
                ('What to do first', [
                    'Choose at least one country card from the five cards in your hand.',
                    'Cards you do not play become defense. Decide whether to attack hard or keep protection.',
                    'New cards are not drawn until your hand is empty. After an empty-hand turn, you draw five new cards.',
                    'Playing cards uses command. Keeping more cards for defense restores more command next turn.',
                    'Once per turn, you can spend command to discard your hand and redraw the same number of cards.',
                    'Each room can use 1 minute, 3 minutes, 5 minutes, or unlimited thinking time. If time runs out, you surrender. Duel and bot battles end immediately; free-for-all and team slots are taken over by bots.',
                ]),
                ('Damage and victory', [
                    f'You lose when your HP reaches 0. Starting HP is {format_battle_number(BATTLE_MAX_HP)}.',
                    'The side with higher country power deals damage.',
                    'Country power is based on area and population, compressed with a square root so huge countries do not dominate too completely.',
                    'Playing several cards is powerful, but the second and later cards are slightly reduced. Going all in can leave you exposed later.',
                    'Damage is based on the power gap after defense. Defense reduces incoming damage.',
                    'If defense exceeds the attack, the excess becomes counter damage back to the attacker.',
                    'Damage gradually rises in long battles, and World War III makes the battle much harsher from the turn chosen for the room. It can also be disabled.',
                    'During World War III, dangerous cards can appear. They damage you at turn end and are discarded.',
                    'A low-chance revolution can also reverse card strength for a while.',
                    'Rare events can also hide country names, replace a hand card, pass a bomb card around, or massively increase damage.',
                    'When you deal damage, you steal one remaining card from the opponent. Bot battle wins are not counted in rankings.',
                ]),
                ('Battle modes', [
                    'In 1v1, you directly compare power with your opponent.',
                    'In free-for-all, you choose which player to attack.',
                    'In team battles, each team combines played cards into total attack and saved cards into total defense.',
                    f'Team HP is {format_battle_number(BATTLE_MAX_HP)} times team size. If teams are uneven, both sides use the larger team size.',
                    'Team battles include a team chat so you can coordinate attacks and defense.',
                ]),
                ('Match Bonus', [
                    'If your played cards share tags or regions, or your saved defense cards share tags or regions, you get a strong bonus.',
                    'One card alone cannot trigger it. Opponent cards are not included.',
                    'Each repeated tag or region adds +50% to attack or defense: one match makes it 1.5x, two matches make it 2x, and stacked matches can decide the turn.',
                ]),
            ],
        },
        'zh': {
            'title': '国力对战玩法',
            'sections': [
                ('先做什么？', [
                    '从5张国家卡中选择至少1张作为本回合出战的国家。',
                    '没有打出的国家会用于防御。要全力进攻还是保留防守，需要自己判断。',
                    '手牌用完前不会补充。手牌为空的回合会处于无防备状态，之后重新抽5张。',
                    '出牌会消耗指挥力。保留为防御的牌越多，下回合恢复的指挥力越多。',
                    '每回合可以消耗指挥力弃掉当前手牌，并重抽同样张数一次。',
                    '每个房间可选择1分钟、3分钟、5分钟或无限制思考时间。超时会自动投降；1对1和BOT战会立即结束，混战和团队战的位置会由BOT接替。',
                ]),
                ('伤害与胜利', [
                    f'HP变为0就会失败。开始时HP为{format_battle_number(BATTLE_MAX_HP)}。',
                    '比较出战国家的国力，较高的一方造成伤害。',
                    '国力根据面积和人口计算，但会用平方根压缩，避免巨大国家过度碾压。',
                    '打出多张牌会更强，但第2张以后的力量会逐渐降低。一次打光很强，也更容易陷入手牌不足。',
                    '伤害由国力差再扣除防御决定。防御会减少受到的伤害。',
                    '如果防御超过攻击，超过的部分会作为反击伤害返还给攻击方。',
                    '战斗拖得越久，伤害会逐渐提高；从房间选择的回合开始，第三次世界大战会让战斗更加激烈。也可以设为不发生。',
                    '第三次世界大战期间，手牌中可能出现危险牌。危险牌会在回合结束时造成自伤并被弃掉。',
                    '还可能低概率发生革命，使卡牌强弱暂时反转。',
                    '还会低概率出现隐藏国名、只能看旗帜判断，或梵蒂冈更容易出现的事件。',
                    '造成伤害时，可以从对手剩余手牌中夺取1张。BOT战的胜场不计入排行。',
                ]),
                ('模式规则', [
                    '1对1中，直接与对手比较国力。',
                    '混战中，需要自己指定攻击目标。',
                    '团队战中，队友打出的牌合计为总攻击，未打出的牌合计为总防御。',
                    f'团队HP为{format_battle_number(BATTLE_MAX_HP)}乘以队伍人数。人数不同时，双方都按人数较多的一方计算。',
                    '团队战可以使用团队聊天，和队友商量进攻与防御。',
                ]),
                ('一致加成', [
                    '本回合打出的国家之间，或留下防御的国家之间，如果标签或地区重复，就会得到强力加成。',
                    '只用1张牌不会发动。对手的牌不会参与计算。',
                    '每个重复的标签或地区会让攻击或防御增加+50%。一个一致为1.5倍，两个一致为2倍，组合会大幅影响胜负。',
                ]),
            ],
        },
    }
    return labels.get(state.lang, labels['en'])

def battle_help_labels():
    labels = {
        'ja': {
            'title': '国力対戦の遊び方',
            'quick_title': 'まずは画面の流れだけ覚えましょう',
            'quick_intro': '難しい計算は後回しで大丈夫です。手札を選び、相手を決め、勝負ボタンを押すのが基本です。',
            'quick_steps': [
                ('style', '手札を見る', '配られた5枚の国カードから、勝負に出す国を選びます。'),
                ('shield', '残すカードを決める', '選ばなかった国は守りに回ります。全部出すと攻撃は強いですが、守りが薄くなります。'),
                ('my_location', '相手を選ぶ', '乱戦では攻撃対象を選びます。1対1とチーム戦では相手は自動で決まります。'),
                ('sports_martial_arts', '勝負する', '「この手で勝負」を押すとターンが進み、ダメージとログが表示されます。'),
            ],
            'mock': {
                'hand': '手札',
                'attack': '攻撃に出す',
                'defense': '守りに残す',
                'target': '攻撃対象',
                'submit': 'この手で勝負',
                'surrender': '降参',
                'redraw': '引き直し',
            },
            'detail_title': '詳しいルール',
            'detail_intro': '勝敗の決まり方やボーナスを確認したい時はこちらを見ます。',
            'sections': [
                ('ターンの進め方', [
                    '手札5枚の中から1枚以上を選んで出します。',
                    '出さなかったカードは防御に回ります。攻撃と防御のバランスを考えるのが大事です。',
                    '手札が空になるまで新しいカードは補充されません。空になった次のターンは無防備になり、その後で新しい5枚が配られます。',
                    'カードを出すには指揮力を使います。守りに残すカードが多いほど次のターンに指揮力が戻ります。',
                    '各ターンに1回だけ、指揮力を使って現在の手札をすべて捨て、同じ枚数を引き直せます。',
                    '思考時間は部屋ごとに1分・3分・5分・無制限から選べます。時間切れになると降参扱いになり、1対1とBOT戦ではその場で決着し、乱戦とチーム戦ではその枠をBOTが引き継ぎます。',
                ]),
                ('国力とダメージ', [
                    f'HPが0になると負けです。開始時のHPは{format_battle_number(BATTLE_MAX_HP)}です。',
                    '国力は、国の面積と人口をもとに計算されます。広く、人口の多い国ほど強くなりやすいです。',
                    '国力は面積と人口をもとにしますが、巨大国家だけが突出しすぎないように平方根で圧縮しています。',
                    '複数枚を出すと総攻撃は上がりますが、2枚目以降は少しずつ力が抑えられます。',
                    '相手の防御を上回った分がダメージになります。防御は受けるダメージを減らします。',
                    '防御が攻撃を上回った場合は、上回った分がカウンターダメージとして攻撃側に返ります。',
                    '長引くほど少しずつダメージが伸び、部屋で選んだターン以降は第三次世界大戦でさらに激しくなります。開始しない設定にもできます。',
                    '第三次世界大戦中は危険カードが手札に混ざることがあり、ターン終了時に自分へダメージを与えて消えます。',
                    '低確率で革命が起こると、カードの強弱がしばらく逆転します。',
                    'まれに国名が伏せられて国旗だけで選ぶイベントや、バチカン市国が配られやすくなるイベントも発生します。',
                    'ダメージを与えると、相手の残り手札から1枚を奪えます。BOT戦の勝利数はランキングには入りません。',
                ]),
                ('対戦モード', [
                    '1対1では、相手と正面から国力を比べます。',
                    '乱戦では、攻撃したい相手を自分で選びます。',
                    'チーム戦では、チーム全員が出したカードを総攻撃力、残したカードを総防御力として合計します。',
                    f'チーム戦のHPは「{format_battle_number(BATTLE_MAX_HP)} x チーム人数」です。人数差がある時は、多い側の人数に合わせます。',
                    'チーム戦ではチーム内チャットで相談できます。',
                ]),
                ('一致ボーナス', [
                    '同じターンに自分が出したカード同士、または防御に残したカード同士でタグや地域が重なると強力なボーナスが入ります。',
                    '1枚だけでは発動しません。相手のカードとの一致も判定しません。',
                    '重なったタグや地域が増えるごとに、攻撃または防御が少し上がります。大逆転用ではなく、接戦を少し有利にする仕組みです。',
                ]),
            ],
        },
        'en': {
            'title': 'How to Play Power Battle',
            'quick_title': 'Learn the screen flow first',
            'quick_intro': 'You can ignore the deeper math at first. Pick cards, choose a target, and submit your hand.',
            'quick_steps': [
                ('style', 'Check Your Hand', 'Choose at least one country from the five cards in your hand.'),
                ('shield', 'Keep Defense', 'Unplayed cards become defense. Going all in gives power but leaves you open.'),
                ('my_location', 'Choose Target', 'In free-for-all, choose who to attack. Duel and team modes decide this automatically.'),
                ('sports_martial_arts', 'Submit', 'Press the submit button to resolve the turn and show damage in the log.'),
            ],
            'mock': {
                'hand': 'Hand',
                'attack': 'Attack',
                'defense': 'Defense',
                'target': 'Target',
                'submit': 'Submit Hand',
                'surrender': 'Surrender',
                'redraw': 'Redraw',
            },
            'detail_title': 'Detailed Rules',
            'detail_intro': 'Open this when you want to check damage, bonuses, and each battle mode.',
            'sections': [
                ('Turn Flow', [
                    'Choose at least one country card from the five cards in your hand.',
                    'Cards you do not play become defense, so balance attack and protection.',
                    'New cards are not drawn until your hand is empty. After an empty-hand turn, you draw five new cards.',
                    'Playing cards uses command. Keeping more cards for defense restores more command next turn.',
                    'Once per turn, you can spend command to discard your hand and redraw the same number of cards.',
                    'Each room can use 1 minute, 3 minutes, 5 minutes, or unlimited thinking time. If time runs out, you surrender. Duel and bot battles end immediately; free-for-all and team slots are taken over by bots.',
                ]),
                ('Power and Damage', [
                    f'You lose when your HP reaches 0. Starting HP is {format_battle_number(BATTLE_MAX_HP)}.',
                    'Country power is based on area and population. Larger, more populous countries tend to be stronger.',
                    'Power uses area and population, but it is compressed with a square root so huge countries do not dominate too completely.',
                    'Playing several cards raises total attack, but the second and later cards are slightly reduced.',
                    'Damage is the power gap after defense. Defense reduces incoming damage.',
                    'If defense exceeds the attack, the excess becomes counter damage back to the attacker.',
                    'Damage gradually rises in long battles, and World War III makes the battle much harsher from the turn chosen for the room. It can also be disabled.',
                    'During World War III, dangerous cards can appear. They damage you at turn end and are discarded.',
                    'A low-chance revolution can also reverse card strength for a while.',
                    'Rare events can also hide country names so you must read flags, or make Vatican City appear more often.',
                    'When you deal damage, you steal one remaining card from the opponent. Bot battle wins are not counted in rankings.',
                ]),
                ('Battle Modes', [
                    'In 1v1, you directly compare power with your opponent.',
                    'In free-for-all, you choose which player to attack.',
                    'In team battles, each team combines played cards into total attack and saved cards into total defense.',
                    f'Team HP is {format_battle_number(BATTLE_MAX_HP)} times team size. If teams are uneven, both sides use the larger team size.',
                    'Team battles include a team chat so you can coordinate attacks and defense.',
                ]),
                ('Match Bonus', [
                    'If your played cards share tags or regions, or your saved defense cards share tags or regions, you get a strong bonus.',
                    'One card alone cannot trigger it. Opponent cards are not included.',
                    'Each repeated tag or region adds +50% to attack or defense: one match makes it 1.5x, two matches make it 2x, and stacked matches can decide the turn.',
                ]),
            ],
        },
        'zh': {
            'title': '国力对战玩法',
            'quick_title': '先记住画面流程',
            'quick_intro': '一开始不用记复杂计算。选择手牌、决定目标、按下出牌按钮即可。',
            'quick_steps': [
                ('style', '查看手牌', '从5张国家卡中选择至少1张作为本回合出牌。'),
                ('shield', '保留防御', '没有出的牌会变成防御。全力攻击很强，但防御会变薄。'),
                ('my_location', '选择目标', '乱战需要自己选择攻击目标。1对1和团队战会自动决定。'),
                ('sports_martial_arts', '确认出牌', '按下出牌按钮后，本回合结算，并在日志中显示伤害。'),
            ],
            'mock': {
                'hand': '手牌',
                'attack': '攻击',
                'defense': '防御',
                'target': '目标',
                'submit': '确认出牌',
                'surrender': '投降',
                'redraw': '重抽',
            },
            'detail_title': '详细规则',
            'detail_intro': '想确认伤害、加成和模式规则时，请查看这里。',
            'sections': [
                ('回合流程', [
                    '从5张手牌中选择至少1张国家卡出牌。',
                    '没有出的牌会用于防御，所以要考虑攻击和防御的平衡。',
                    '手牌用完前不会补牌。手牌为空后的下一回合会变成无防备状态，之后重新抽5张。',
                    '出牌会消耗指挥力。保留为防御的牌越多，下回合恢复的指挥力越多。',
                    '每回合可以消耗指挥力将当前手牌全部弃掉，并重抽相同张数。',
                    '每个房间可选择1分钟、3分钟、5分钟或无限制思考时间。超时会被视为投降；1对1和BOT战会立即结束，混战和团队战的位置会由BOT接手。',
                ]),
                ('国力与伤害', [
                    f'HP变成0就失败。开始时HP为{format_battle_number(BATTLE_MAX_HP)}。',
                    '国力根据面积和人口计算。面积大、人口多的国家通常更强。',
                    '国力根据面积和人口计算，但会用平方根压缩，避免巨大国家过度碾压。',
                    '同时出多张牌会提高总攻击，但第2张以后会稍微降低效果。',
                    '伤害由扣除防御后的国力差决定。防御会减少受到的伤害。',
                    '如果防御超过攻击，超过的部分会作为反击伤害返还给攻击方。',
                    '战斗拖得越久，伤害会逐渐提高；从房间选择的回合开始，第三次世界大战会让战斗更加激烈。也可以设为不发生。',
                    '第三次世界大战期间，手牌中可能出现危险牌。危险牌会在回合结束时造成自伤并被弃掉。',
                    '低概率发生革命时，卡牌强弱会暂时反转。',
                    '还会低概率出现隐藏国名、只能看旗帜判断，或梵蒂冈更容易出现的事件。',
                    '造成伤害时，可以从对手剩余手牌中夺取1张。BOT战胜利不会计入排行榜。',
                ]),
                ('对战模式', [
                    '1对1会直接和对手比较国力。',
                    '乱战中可以自己选择攻击目标。',
                    '团队战中，全队出的牌合计为总攻击力，没出的牌合计为总防御力。',
                    f'团队战HP为“{format_battle_number(BATTLE_MAX_HP)} x 团队人数”。人数不同时，会按人数较多的一方计算双方HP。',
                    '团队战可以使用队伍聊天来商量攻击和防御。',
                ]),
                ('一致加成', [
                    '同一回合中，自己出的牌之间，或保留防御的牌之间，如果标签或地区重复，会获得强力加成。',
                    '只有1张牌时不会发动。也不会和对手的牌进行比较。',
                    '重复的标签或地区越多，攻击或防御会大幅提高。一个一致为1.5倍，两个一致为2倍，组合会明显影响胜负。',
                ]),
            ],
        },
    }
    return labels.get(state.lang, labels['en'])

def battle_mode_size(mode):
    return MULTIPLAYER_MODES.get(mode, 2)

def normalize_battle_player_count(value, mode=FFA_MODE):
    if mode == DUEL_MODE or mode == BOT_MODE:
        return 2
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 3
    return max(BATTLE_MIN_MULTIPLAYER_PLAYERS, min(BATTLE_MAX_MULTIPLAYER_PLAYERS, count))

def selected_battle_player_count(mode=FFA_MODE):
    return normalize_battle_player_count(getattr(state, 'battle_room_player_count', 3), mode)

def normalize_battle_team_count(value):
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 2
    return max(2, min(len(BATTLE_TEAM_IDS), count))

def selected_battle_team_count():
    return normalize_battle_team_count(getattr(state, 'battle_team_count', 2))

def normalize_battle_team_choice(value, team_count=None):
    team_count = normalize_battle_team_count(team_count if team_count is not None else selected_battle_team_count())
    valid = BATTLE_TEAM_IDS[:team_count]
    choice = str(value or '').upper()
    return choice if choice in valid else valid[0]

def normalize_battle_timeout_seconds(value):
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = BATTLE_TURN_TIMEOUT_SECONDS
    if seconds not in BATTLE_TURN_TIMEOUT_OPTIONS:
        return BATTLE_TURN_TIMEOUT_SECONDS
    return seconds

def battle_timeout_label(seconds):
    try:
        raw_seconds = int(seconds)
    except (TypeError, ValueError):
        raw_seconds = None
    if raw_seconds == 30:
        return '30秒' if state.lang == 'ja' else '30 sec'
    seconds = normalize_battle_timeout_seconds(seconds)
    if seconds == BATTLE_TURN_TIMEOUT_UNLIMITED:
        return t('battle_time_unlimited')
    minutes = max(1, seconds // 60)
    if state.lang == 'ja':
        return f'{minutes}分'
    if state.lang == 'zh':
        return f'{minutes}分钟'
    return f'{minutes} min'

def selected_battle_timeout_seconds():
    return normalize_battle_timeout_seconds(getattr(state, 'battle_turn_timeout_seconds', BATTLE_TURN_TIMEOUT_SECONDS))

def battle_room_timeout_seconds(room):
    try:
        seconds = int((room or {}).get('turn_timeout_seconds'))
    except (TypeError, ValueError):
        seconds = BATTLE_TURN_TIMEOUT_SECONDS
    if is_sengoku_boss_room(room) and seconds == 30:
        return 30
    return normalize_battle_timeout_seconds(seconds)

def normalize_battle_world_war_turn(value):
    try:
        turn = int(value)
    except (TypeError, ValueError):
        turn = BATTLE_WORLD_WAR_TURN
    if turn not in BATTLE_WORLD_WAR_TURN_OPTIONS:
        return BATTLE_WORLD_WAR_TURN
    return turn

def battle_world_war_turn_label(turn):
    turn = normalize_battle_world_war_turn(turn)
    if turn == BATTLE_WORLD_WAR_DISABLED:
        return t('battle_world_war_never')
    if state.lang == 'ja':
        return f'{turn}ターン目'
    if state.lang == 'zh':
        return f'第{turn}回合'
    return f'Turn {turn}'

def selected_battle_world_war_turn():
    return normalize_battle_world_war_turn(getattr(state, 'battle_world_war_turn', BATTLE_WORLD_WAR_TURN))

def battle_room_world_war_turn(room):
    return normalize_battle_world_war_turn((room or {}).get('world_war_turn'))

def selected_battle_events_enabled():
    return bool(getattr(state, 'battle_events_enabled', True))

def battle_room_events_enabled(room):
    return bool((room or {}).get('events_enabled', True))

def sengoku_boss_for_room(room):
    return sengoku_boss_by_id((room or {}).get('sengoku_boss_id'))

def is_sengoku_boss_room(room):
    return bool(sengoku_boss_for_room(room))

def sengoku_boss_player_team(room):
    return str((sengoku_boss_for_room(room) or {}).get('player_team', 'A') or 'A')

def sengoku_boss_enemy_team(room):
    return str((sengoku_boss_for_room(room) or {}).get('enemy_team', 'B') or 'B')

def is_sengoku_boss_player_side(room, player):
    boss = sengoku_boss_for_room(room)
    if not boss or not player:
        return False
    if (room or {}).get('mode') == TEAM_MODE:
        return (room or {}).get('teams', {}).get(player) == sengoku_boss_player_team(room)
    return not is_battle_bot(player)

def is_sengoku_boss_enemy_bot(room, player):
    boss = sengoku_boss_for_room(room)
    if not boss or not player or not is_battle_bot(player):
        return False
    if (room or {}).get('mode') == TEAM_MODE:
        return (room or {}).get('teams', {}).get(player) == sengoku_boss_enemy_team(room)
    return True

def battle_boss_label(labels):
    return labels.get(state.lang, labels.get('ja', labels.get('en', '')))

def battle_satrapy_provinces(room):
    boss = sengoku_boss_for_room(room)
    province_ids = list((boss or {}).get('satrapy_provinces', []) or [])
    if not province_ids:
        try:
            legacy_count = int((boss or {}).get('satrapy_shields', 0) or 0)
        except (TypeError, ValueError):
            legacy_count = 0
        province_ids = [province['id'] for province in BATTLE_SATRAPY_PROVINCES[:max(0, legacy_count)]]
    known = {province['id']: province for province in BATTLE_SATRAPY_PROVINCES}
    return [known[province_id] for province_id in province_ids if province_id in known]

def battle_satrapy_shield_total(room):
    return len(battle_satrapy_provinces(room))

def battle_satrapy_shield_strength(room):
    try:
        return max(1, int((sengoku_boss_for_room(room) or {}).get('satrapy_shield_hits', 1) or 1))
    except (TypeError, ValueError):
        return 1

def battle_satrapy_province_label(province):
    labels = (province or {}).get('name', {})
    if isinstance(labels, dict):
        return labels.get(state.lang, labels.get('ja', labels.get('en', str((province or {}).get('id', '')))))
    return str(labels or (province or {}).get('id', ''))

def battle_satrapy_state(room):
    provinces = battle_satrapy_provinces(room)
    if not provinces:
        return {}, set()
    damage = room.setdefault('satrapy_shield_damage', {})
    if not isinstance(damage, dict):
        damage = {}
        room['satrapy_shield_damage'] = damage
    broken_raw = room.setdefault('satrapy_broken_provinces', [])
    if isinstance(broken_raw, int):
        broken_raw = [province['id'] for province in provinces[:max(0, broken_raw)]]
    if not isinstance(broken_raw, list):
        broken_raw = []
    broken = {str(province_id) for province_id in broken_raw}
    old_broken_count = room.get('satrapy_shields_broken')
    if old_broken_count and not broken:
        try:
            count = int(old_broken_count)
        except (TypeError, ValueError):
            count = 0
        broken.update(province['id'] for province in provinces[:max(0, count)])
    province_ids = {province['id'] for province in provinces}
    for province_id in list(damage):
        if province_id not in province_ids:
            damage.pop(province_id, None)
    for province in provinces:
        province_id = province['id']
        try:
            damage[province_id] = max(0, int(damage.get(province_id, 0) or 0))
        except (TypeError, ValueError):
            damage[province_id] = 0
    broken = {province_id for province_id in broken if province_id in province_ids}
    room['satrapy_broken_provinces'] = sorted(broken)
    room['satrapy_shields_broken'] = len(broken)
    return damage, broken

def battle_satrapy_shields_broken(room):
    _, broken = battle_satrapy_state(room or {})
    return len(broken)

def battle_satrapy_shields_remaining(room):
    return max(0, battle_satrapy_shield_total(room) - battle_satrapy_shields_broken(room))

def battle_satrapy_shield_reduction_percent(room):
    return max(0, battle_satrapy_shields_remaining(room) * 10)

def battle_satrapy_hp_drop_percent(room):
    try:
        return max(0, int((sengoku_boss_for_room(room) or {}).get('satrapy_hp_drop_percent', 0) or 0))
    except (TypeError, ValueError):
        return 0

def battle_royal_road_interval(room):
    try:
        return max(0, int((sengoku_boss_for_room(room) or {}).get('royal_road_interval', 0) or 0))
    except (TypeError, ValueError):
        return 0

def battle_royal_road_heal_percent(room):
    try:
        return max(0, int((sengoku_boss_for_room(room) or {}).get('royal_road_heal_percent', 0) or 0))
    except (TypeError, ValueError):
        return 0

def battle_satrapy_resonant_provinces(room, keys):
    provinces = battle_satrapy_provinces(room)
    if not provinces:
        return []
    province_ids = {province['id'] for province in provinces}
    lookup = battle_country_lookup()
    counts = {province_id: 0 for province_id in province_ids}
    for key in keys or []:
        country = lookup.get(key)
        if not country:
            continue
        country_regions = {
            region.strip()
            for region in str(country.get('region') or '').replace('/', ',').split(',')
            if region.strip()
        }
        for province_id in province_ids & country_regions:
            counts[province_id] += 1
    return [province_id for province_id, count in counts.items() if count >= 2]

def battle_reduce_damage_by_satrapy_shields(room, damage, breakdown=None):
    damage = max(0, int(damage or 0))
    if damage <= 0:
        return 0
    reduction_percent = battle_satrapy_shield_reduction_percent(room)
    reduced = max(1, damage * max(0, 100 - reduction_percent) // 100)
    if isinstance(breakdown, dict):
        breakdown['satrapy_shield_reduction_percent'] = reduction_percent
        breakdown['satrapy_shield_reduced_damage'] = max(0, damage - reduced)
        breakdown['satrapy_damage_after_reduction'] = reduced
        if int(breakdown.get('damage', -1) or -1) == damage:
            breakdown['damage'] = reduced
        elif int(breakdown.get('counter', -1) or -1) == damage:
            breakdown['counter'] = reduced
    return reduced

def battle_apply_satrapy_shields(room, attack_keys, incoming_damage=0, breakdown=None):
    provinces = battle_satrapy_provinces(room)
    if not provinces or battle_satrapy_shields_remaining(room) <= 0:
        return ''
    damage_map, broken = battle_satrapy_state(room)
    strength = battle_satrapy_shield_strength(room)
    resonant = set(battle_satrapy_resonant_provinces(room, attack_keys))
    hit_notes = []
    break_notes = []
    for province in provinces:
        province_id = province['id']
        if province_id in broken or province_id not in resonant:
            continue
        damage_map[province_id] = min(strength, int(damage_map.get(province_id, 0) or 0) + 1)
        label = battle_satrapy_province_label(province)
        if damage_map[province_id] >= strength:
            broken.add(province_id)
            break_notes.append(label)
        else:
            hit_notes.append(f'{label} {damage_map[province_id]}/{strength}')
    room['satrapy_broken_provinces'] = sorted(broken)
    room['satrapy_shields_broken'] = len(broken)
    remaining = battle_satrapy_shields_remaining(room)
    reduction_percent = battle_satrapy_shield_reduction_percent(room)
    if isinstance(breakdown, dict):
        breakdown['satrapy_shield_incoming_damage'] = max(0, int(incoming_damage or 0))
        breakdown['satrapy_shields_remaining'] = remaining
        breakdown['satrapy_shield_reduction_percent'] = reduction_percent
        breakdown['satrapy_hits'] = hit_notes
        breakdown['satrapy_breaks'] = break_notes
    if break_notes:
        return battle_boss_label({
            'ja': f"属州シールドが攻撃を{reduction_percent}%軽減。{', '.join(break_notes)}が崩壊し、敵HP上限が永久に低下しました。",
            'en': f"Satrapy shields reduced damage by {reduction_percent}%. {', '.join(break_notes)} broke, permanently lowering enemy max HP.",
            'zh': f"行省护盾使伤害降低{reduction_percent}%。{', '.join(break_notes)}破裂，敌方HP上限永久下降。",
        })
    if hit_notes:
        return battle_boss_label({
            'ja': f"属州シールドが攻撃を{reduction_percent}%軽減。地域共鳴で {', '.join(hit_notes)} に亀裂が入りました。",
            'en': f"Satrapy shields reduced damage by {reduction_percent}%. Regional resonance cracked {', '.join(hit_notes)}.",
            'zh': f"行省护盾使伤害降低{reduction_percent}%。地域共鸣使 {', '.join(hit_notes)} 出现裂痕。",
        })
    return battle_boss_label({
        'ja': f'属州シールドが攻撃を{reduction_percent}%軽減。対応する地域共鳴がないため、シールドには傷が入りませんでした。',
        'en': f'Satrapy shields reduced damage by {reduction_percent}%. No matching regional resonance cracked a shield.',
        'zh': f'行省护盾使伤害降低{reduction_percent}%。没有对应地域共鸣，因此护盾没有受损。',
    })

def battle_shared_tag_region_labels(left_keys, right_keys):
    shared_tags = battle_tags_for_keys(left_keys) & battle_tags_for_keys(right_keys)
    shared_regions = battle_regions_for_keys(left_keys) & battle_regions_for_keys(right_keys)
    labels = [tag_label(tag) for tag in sorted(shared_tags, key=lambda tag: tag_label(tag).lower())]
    labels.extend(region_label(region) for region in sorted(shared_regions, key=lambda region: region_label(region).lower()))
    return labels

def sengoku_boss_forced_events(room):
    boss = sengoku_boss_for_room(room)
    return set((boss or {}).get('forced_events', []))

def battle_player_hp_limit(room, player):
    limit = BATTLE_MAX_HP
    boss = sengoku_boss_for_room(room)
    if boss and is_sengoku_boss_enemy_bot(room, player) and (room or {}).get('mode') != TEAM_MODE:
        try:
            limit *= max(1, int(boss.get('hp_multiplier', 1) or 1))
        except (TypeError, ValueError):
            pass
        try:
            hp_percent = int(boss.get('bot_hp_percent', 100) or 100)
            if hp_percent > 0:
                limit = max(1, limit * hp_percent // 100)
        except (TypeError, ValueError):
            pass
        shield_drop = battle_satrapy_shields_broken(room) * battle_satrapy_hp_drop_percent(room)
        if shield_drop > 0:
            limit = max(1, limit * max(10, 100 - shield_drop) // 100)
    return limit

def battle_deal_count_for_player(room, player):
    count = 5
    boss = sengoku_boss_for_room(room)
    if boss and is_sengoku_boss_player_side(room, player):
        try:
            count *= max(1, int(boss.get('player_hand_multiplier', 1) or 1))
        except (TypeError, ValueError):
            pass
        try:
            count += max(0, int(boss.get('player_hand_bonus', 0) or 0))
        except (TypeError, ValueError):
            pass
    return count

def apply_sengoku_boss_forced_state(room):
    boss = sengoku_boss_for_room(room)
    if not boss:
        return
    forced_events = set(boss.get('forced_events', []))
    if 'world_war' in forced_events:
        room['world_war_started'] = True
    for event_name, field in SENGOKU_BOSS_EVENT_FIELDS.items():
        if event_name in forced_events:
            room[field] = max(int(room.get(field, 0) or 0), SENGOKU_BOSS_FORCED_TURN)
    if boss.get('command_infinite'):
        for player in room.get('players', []):
            if is_sengoku_boss_enemy_bot(room, player):
                room.setdefault('command', {})[player] = BATTLE_MAX_COMMAND

def battle_player_command_limit(room, player):
    limit = BATTLE_MAX_COMMAND
    boss = sengoku_boss_for_room(room)
    if boss and is_sengoku_boss_player_side(room, player):
        try:
            limit += max(0, int(boss.get('player_command_bonus', 0) or 0))
        except (TypeError, ValueError):
            pass
    return max(1, limit)

def battle_player_command(room, player):
    command_map = (room or {}).setdefault('command', {})
    boss = sengoku_boss_for_room(room)
    if boss and boss.get('command_infinite') and is_sengoku_boss_enemy_bot(room, player):
        command_map[player] = BATTLE_MAX_COMMAND
        return BATTLE_MAX_COMMAND
    limit = battle_player_command_limit(room, player)
    try:
        current = int(command_map.get(player, limit))
    except (TypeError, ValueError):
        current = limit
    current = max(0, min(limit, current))
    command_map[player] = current
    return current

def battle_enemy_extra_actions(room, player=None, team=None):
    boss = sengoku_boss_for_room(room)
    if not boss:
        return 1
    if team is not None:
        if team != sengoku_boss_enemy_team(room):
            return 1
    elif not is_sengoku_boss_enemy_bot(room, player):
        return 1
    try:
        return max(1, int(boss.get('enemy_extra_actions', 1) or 1))
    except (TypeError, ValueError):
        return 1

def battle_apply_enemy_extra_actions(room, damage, source_player=None, source_team=None, breakdown=None):
    actions = battle_enemy_extra_actions(room, source_player, source_team)
    if actions <= 1 or damage <= 0:
        return damage
    boosted = int(damage * actions)
    if isinstance(breakdown, dict):
        breakdown['boss_extra_actions'] = actions
        breakdown['boss_extra_action_damage'] = max(0, boosted - int(damage))
        breakdown['damage'] = boosted
    return boosted

def set_battle_player_command(room, player, value):
    limit = battle_player_command_limit(room, player)
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = limit
    room.setdefault('command', {})[player] = max(0, min(limit, value))

def battle_command_cost_for_count(count):
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 0
    if count <= 0:
        return 0
    return BATTLE_CARD_COMMAND_COSTS[min(count, len(BATTLE_CARD_COMMAND_COSTS)) - 1]

def battle_max_playable_card_count(command, hand_count):
    try:
        command = int(command)
        hand_count = int(hand_count)
    except (TypeError, ValueError):
        return 0
    max_count = 0
    for count in range(1, max(0, hand_count) + 1):
        if battle_command_cost_for_count(count) <= command:
            max_count = count
    return max_count

def recover_battle_command_after_turn(room, player, submitted, defenseless=False):
    current = battle_player_command(room, player)
    if defenseless:
        bonus = BATTLE_COMMAND_SURGE_RECOVERY if battle_command_surge_active(room) else 0
        set_battle_player_command(room, player, current + 3 + bonus)
        return
    keys = list((submitted or {}).get('keys', []))
    defense_keys = list((submitted or {}).get('defense_keys', []))
    spent = int((submitted or {}).get('command_cost', battle_command_cost_for_count(len(keys))) or 0)
    recovery = 1 + min(4, len(defense_keys))
    if battle_command_surge_active(room):
        recovery += BATTLE_COMMAND_SURGE_RECOVERY
    set_battle_player_command(room, player, current - spent + recovery)

def battle_time_left_text(room):
    seconds = battle_turn_time_left(room)
    if seconds is None:
        return t('battle_time_unlimited')
    return t('battle_time_left').format(seconds=seconds)

def normalize_battle_queue_entry(entry):
    if isinstance(entry, dict):
        username = clean_username(entry.get('username'))
        mode = str(entry.get('mode') or DUEL_MODE)
        timeout_seconds = normalize_battle_timeout_seconds(entry.get('turn_timeout_seconds'))
        world_war_turn = normalize_battle_world_war_turn(entry.get('world_war_turn'))
        player_count = normalize_battle_player_count(entry.get('player_count'), mode)
        team_count = normalize_battle_team_count(entry.get('team_count'))
        team_choice = normalize_battle_team_choice(entry.get('team_choice'), team_count)
        events_enabled = bool(entry.get('events_enabled', True))
    else:
        username = clean_username(entry)
        mode = DUEL_MODE
        timeout_seconds = BATTLE_TURN_TIMEOUT_SECONDS
        world_war_turn = BATTLE_WORLD_WAR_TURN
        player_count = 2
        team_count = 2
        team_choice = 'A'
        events_enabled = True
    if mode not in MULTIPLAYER_MODES:
        mode = DUEL_MODE
    if not username:
        return None
    return {
        'username': username,
        'mode': mode,
        'turn_timeout_seconds': timeout_seconds,
        'world_war_turn': world_war_turn,
        'player_count': normalize_battle_player_count(player_count, mode),
        'team_count': team_count,
        'team_choice': team_choice,
        'events_enabled': events_enabled,
    }

def default_battle_state():
    return {
        'queue': [],
        'rooms': {},
        'user_room': {},
        'spectator_room': {},
        'counter': 0,
    }

def normalize_battle_state(value):
    if not isinstance(value, dict):
        return default_battle_state()
    state_data = default_battle_state()
    if isinstance(value.get('queue'), list):
        queue_entries = []
        seen = set()
        for entry in value['queue']:
            normalized = normalize_battle_queue_entry(entry)
            if not normalized:
                continue
            marker = normalized['username']
            if marker not in seen:
                queue_entries.append(normalized)
                seen.add(marker)
        state_data['queue'] = queue_entries
    if isinstance(value.get('rooms'), dict):
        state_data['rooms'] = value['rooms']
    if isinstance(value.get('user_room'), dict):
        state_data['user_room'] = {
            clean_username(username): str(room_id)
            for username, room_id in value['user_room'].items()
            if clean_username(username) and room_id
        }
    if isinstance(value.get('spectator_room'), dict):
        state_data['spectator_room'] = {
            clean_username(username): str(room_id)
            for username, room_id in value['spectator_room'].items()
            if clean_username(username) and room_id
        }
    try:
        state_data['counter'] = int(value.get('counter', 0))
    except (TypeError, ValueError):
        state_data['counter'] = 0
    return state_data

def load_battle_state():
    global BATTLE_STATE_CACHE, BATTLE_STATE_CACHE_MTIME
    if not os.path.exists(BATTLE_STATE_FILE):
        BATTLE_STATE_CACHE = default_battle_state()
        BATTLE_STATE_CACHE_MTIME = None
        return BATTLE_STATE_CACHE
    mtime = file_mtime(BATTLE_STATE_FILE)
    if BATTLE_STATE_CACHE is not None and BATTLE_STATE_CACHE_MTIME == mtime:
        return BATTLE_STATE_CACHE
    try:
        with open(BATTLE_STATE_FILE, 'r', encoding='utf-8') as f:
            BATTLE_STATE_CACHE = normalize_battle_state(json.load(f))
            BATTLE_STATE_CACHE_MTIME = mtime
            return BATTLE_STATE_CACHE
    except Exception as e:
        print(f'Error loading battle state: {e}', flush=True)
        return default_battle_state()

def trim_battle_visual_rows(rows):
    if not isinstance(rows, list):
        return []
    return rows[:BATTLE_LAST_TURN_ROW_LIMIT]

def trim_battle_last_turn(last_turn):
    if not isinstance(last_turn, dict):
        return {}
    trimmed = dict(last_turn)
    for key in ['played', 'damage', 'counters', 'steals', 'self_damage', 'bombs', 'replacements']:
        trimmed[key] = trim_battle_visual_rows(trimmed.get(key))
    return trimmed

def trim_battle_room_for_storage(room):
    room['log'] = list(room.get('log', []))[:BATTLE_LOG_LIMIT]
    room['chat'] = list(room.get('chat', []))[:BATTLE_CHAT_LIMIT]
    room['team_chat'] = list(room.get('team_chat', []))[:BATTLE_CHAT_LIMIT]
    room['last_turn'] = trim_battle_last_turn(room.get('last_turn', {}))
    return room

def save_battle_state(state_data):
    global BATTLE_STATE_CACHE, BATTLE_STATE_CACHE_MTIME
    state_data = normalize_battle_state(state_data)
    battle_dir = os.path.dirname(BATTLE_STATE_FILE)
    if battle_dir:
        os.makedirs(battle_dir, exist_ok=True)
    for room in state_data.get('rooms', {}).values():
        if isinstance(room, dict):
            trim_battle_room_for_storage(room)
    with open(BATTLE_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state_data, f, ensure_ascii=False, separators=(',', ':'))
    BATTLE_STATE_CACHE = state_data
    BATTLE_STATE_CACHE_MTIME = file_mtime(BATTLE_STATE_FILE)

def save_battle_room_snapshot(room):
    if not isinstance(room, dict) or not room.get('id'):
        return
    state_data = load_battle_state()
    state_data.setdefault('rooms', {})[str(room.get('id'))] = room
    save_battle_state(state_data)

def battle_team_hp_limit(room, team=None):
    teams = room.get('teams', {})
    counts = {}
    for player in room.get('players', []):
        player_team = teams.get(player)
        if player_team:
            counts[player_team] = counts.get(player_team, 0) + 1
    base_limit = BATTLE_MAX_HP * max(counts.values(), default=1)
    boss = sengoku_boss_for_room(room)

    def adjusted_limit(team_name):
        limit = base_limit
        if boss and team_name:
            if team_name == sengoku_boss_enemy_team(room):
                try:
                    limit *= max(1, int(boss.get('enemy_team_hp_multiplier', 1) or 1))
                except (TypeError, ValueError):
                    pass
                try:
                    percent = int(boss.get('enemy_team_hp_percent', 100) or 100)
                    if percent > 0:
                        limit = max(1, limit * percent // 100)
                except (TypeError, ValueError):
                    pass
                shield_drop = battle_satrapy_shields_broken(room) * battle_satrapy_hp_drop_percent(room)
                if shield_drop > 0:
                    limit = max(1, limit * max(10, 100 - shield_drop) // 100)
            if team_name == sengoku_boss_player_team(room):
                try:
                    limit *= max(1, int(boss.get('player_team_hp_multiplier', 1) or 1))
                except (TypeError, ValueError):
                    pass
                try:
                    percent = int(boss.get('player_team_hp_percent', 100) or 100)
                    if percent > 0:
                        limit = max(1, limit * percent // 100)
                except (TypeError, ValueError):
                    pass
        return max(1, int(limit))

    if team:
        return adjusted_limit(team)
    if counts:
        return max(adjusted_limit(team_name) for team_name in counts)
    return max(1, int(base_limit))

def ensure_battle_team_hp(room):
    if room.get('mode') != TEAM_MODE:
        return {}
    teams = room.setdefault('teams', {})
    if not teams:
        for index, player in enumerate(room.get('players', [])):
            teams[player] = 'A' if index % 2 == 0 else 'B'
    team_hp = room.setdefault('team_hp', {})
    for team in set(teams.values()):
        limit = battle_team_hp_limit(room, team)
        try:
            current_hp = int(team_hp.get(team, limit))
        except (TypeError, ValueError):
            current_hp = limit
        team_hp[team] = max(0, min(current_hp, limit))
    return team_hp

def normalize_battle_room(room):
    room.setdefault('redraw_turns', {})
    room.setdefault('reload_after_turn', [])
    room.setdefault('submitted', {})
    room.setdefault('log', [])
    room.setdefault('chat', [])
    room.setdefault('team_chat', [])
    room.setdefault('spectators', [])
    room.setdefault('bot_owners', {})
    room.setdefault('player_seen_at', {})
    room.setdefault('last_turn', {})
    room.setdefault('command', {})
    room.setdefault('world_war_started', False)
    room.setdefault('events_enabled', True)
    room.setdefault('sengoku_mode', False)
    room.setdefault('sengoku_boss_id', None)
    room.setdefault('satrapy_shield_damage', {})
    room.setdefault('satrapy_broken_provinces', [])
    room.setdefault('kicked', [])
    room.setdefault('revolution_until_turn', 0)
    room.setdefault('flag_only_until_turn', 0)
    room.setdefault('vatican_until_turn', 0)
    room.setdefault('replace_until_turn', 0)
    room.setdefault('bomb_until_turn', 0)
    room.setdefault('lytton_until_turn', 0)
    room.setdefault('damage_surge_until_turn', 0)
    room.setdefault('random_target_until_turn', 0)
    room.setdefault('operation_required_turn', 0)
    room.setdefault('operation_required_count', 0)
    room.setdefault('ceasefire_until_turn', 0)
    room.setdefault('command_surge_until_turn', 0)
    room.setdefault('supply_drop_until_turn', 0)
    room.setdefault('blockade_until_turn', 0)
    room.setdefault('bomb_holder', None)
    room.setdefault('bomb_cover_key', None)
    if room.get('bomb_holder') and not room.get('bomb_cover_key'):
        battle_bomb_cover_key(room)
    room.setdefault('mode', DUEL_MODE)
    room.setdefault('teams', {})
    room['player_count'] = normalize_battle_player_count(room.get('player_count', len(room.get('players', []))), room.get('mode', DUEL_MODE))
    room['team_count'] = normalize_battle_team_count(room.get('team_count', 2))
    room.setdefault('host', next((player for player in room.get('players', []) if not is_battle_bot(player)), None))
    room.setdefault('bot', False)
    room['turn_timeout_seconds'] = battle_room_timeout_seconds(room)
    room['world_war_turn'] = battle_room_world_war_turn(room)
    apply_sengoku_boss_forced_state(room)
    room.setdefault('turn_started_at', current_timestamp())
    hp = room.setdefault('hp', {})
    now_stamp = current_timestamp()
    seen = room.setdefault('player_seen_at', {})
    for player in room.get('players', []):
        hp_limit = battle_player_hp_limit(room, player)
        try:
            current_hp = int(hp.get(player, hp_limit))
        except (TypeError, ValueError):
            current_hp = hp_limit
        hp[player] = max(0, min(current_hp, hp_limit))
        if not is_battle_bot(player):
            seen.setdefault(player, now_stamp)
        battle_player_command(room, player)
    ensure_battle_team_hp(room)
    return room

def prune_empty_battle_rooms(state_data):
    rooms = state_data.setdefault('rooms', {})
    user_room = state_data.setdefault('user_room', {})
    spectator_room = state_data.setdefault('spectator_room', {})
    for room_id, room in list(rooms.items()):
        has_player_user = any(mapped_room == room_id for mapped_room in user_room.values())
        spectators = [name for name in room.get('spectators', []) if spectator_room.get(name) == room_id]
        room['spectators'] = spectators
        if not has_player_user and not spectators:
            rooms.pop(room_id, None)

def battle_unlimited_disconnect_replacement_enabled(room):
    return (
        room
        and not room.get('winner')
        and room.get('mode') in [FFA_MODE, TEAM_MODE]
        and battle_room_timeout_seconds(room) == BATTLE_TURN_TIMEOUT_UNLIMITED
    )

def seconds_since_timestamp(value):
    if not value:
        return 0
    return max(0, int((datetime.now(timezone.utc) - parse_timestamp_utc(value)).total_seconds()))

def mark_battle_player_seen(room, username):
    username = clean_username(username)
    if not username or is_battle_bot(username) or username not in room.get('players', []):
        return False
    seen = room.setdefault('player_seen_at', {})
    last_seen = seen.get(username)
    if last_seen and seconds_since_timestamp(last_seen) < BATTLE_HEARTBEAT_INTERVAL_SECONDS:
        return False
    seen[username] = current_timestamp()
    return True

def replace_disconnected_unlimited_battle_players(room, state_data=None):
    if not battle_unlimited_disconnect_replacement_enabled(room):
        return False
    changed = False
    seen = room.setdefault('player_seen_at', {})
    for player in list(active_battle_players(room)):
        if is_battle_bot(player):
            continue
        last_seen = seen.get(player)
        if not last_seen:
            seen[player] = current_timestamp()
            changed = True
            continue
        if seconds_since_timestamp(last_seen) < BATTLE_DISCONNECT_REPLACE_SECONDS:
            continue
        if replace_battle_player_with_bot(room, player, state_data, keep_submission=True):
            changed = True
    if changed:
        submit_bot_players(room)
    return changed

def restore_battle_player_from_bot(room, username, state_data=None):
    username = clean_username(username)
    if not username or room.get('winner') or room.get('mode') not in [FFA_MODE, TEAM_MODE]:
        return False
    bot_owners = room.setdefault('bot_owners', {})
    bot_name = next((bot for bot, owner in bot_owners.items() if owner == username), None)
    if not bot_name or bot_name not in room.get('players', []):
        return False

    players = room.setdefault('players', [])
    players[players.index(bot_name)] = username
    hp = room.setdefault('hp', {})
    hp[username] = max(1, int(hp.pop(bot_name, BATTLE_MAX_HP) or BATTLE_MAX_HP))
    room.setdefault('hands', {})[username] = list(room.setdefault('hands', {}).pop(bot_name, deal_battle_hand(room)))
    room.setdefault('command', {})[username] = room.setdefault('command', {}).pop(bot_name, BATTLE_MAX_COMMAND)
    room['reload_after_turn'] = [username if name == bot_name else name for name in room.get('reload_after_turn', [])]
    room.setdefault('redraw_turns', {})[username] = room.setdefault('redraw_turns', {}).pop(bot_name, 0)
    if bot_name in room.setdefault('submitted', {}):
        room['submitted'][username] = room['submitted'].pop(bot_name)
    for submitted in room.setdefault('submitted', {}).values():
        if clean_username(submitted.get('target')) == bot_name:
            submitted['target'] = username
    if room.get('mode') == TEAM_MODE:
        teams = room.setdefault('teams', {})
        teams[username] = teams.pop(bot_name, 'A')
        ensure_battle_team_hp(room)
    room['spectators'] = [name for name in room.get('spectators', []) if name != username]
    room.setdefault('player_seen_at', {})[username] = current_timestamp()
    bot_owners.pop(bot_name, None)
    append_battle_log(room, t('battle_resume_log').format(player=username, bot=bot_name))
    if state_data is not None:
        state_data.setdefault('user_room', {})[username] = room.get('id')
        state_data.setdefault('spectator_room', {}).pop(username, None)
    return True

def battle_room_for_user(username, state_data=None):
    username = clean_username(username)
    if not username:
        return None
    state_data = state_data or load_battle_state()
    room_id = state_data.get('user_room', {}).get(username) or state_data.get('spectator_room', {}).get(username)
    room = state_data.get('rooms', {}).get(room_id)
    if room and username in room.get('kicked', []):
        state_data.get('user_room', {}).pop(username, None)
        state_data.get('spectator_room', {}).pop(username, None)
        save_battle_state(state_data)
        if username == state.current_user:
            state.battle_id = None
        return None
    if room and (username in room.get('players', []) or username in room.get('spectators', [])):
        normalize_battle_room(room)
        changed = False
        before_operation = (room.get('operation_required_turn'), room.get('operation_required_count'))
        ensure_battle_operation_required_count(room)
        if before_operation != (room.get('operation_required_turn'), room.get('operation_required_count')):
            changed = True
        if username in room.get('spectators', []) and restore_battle_player_from_bot(room, username, state_data):
            changed = True
        if username in room.get('players', []) and mark_battle_player_seen(room, username):
            changed = True
        if changed:
            save_battle_state(state_data)
        if username == state.current_user:
            state.battle_id = room_id
        return room
    if room_id:
        state_data.get('user_room', {}).pop(username, None)
        state_data.get('spectator_room', {}).pop(username, None)
        save_battle_state(state_data)
    if username == state.current_user:
        state.battle_id = None
    return None

def battle_waiting_users(state_data=None):
    state_data = state_data or load_battle_state()
    users = []
    for entry in state_data.get('queue', []):
        normalized = normalize_battle_queue_entry(entry)
        if normalized:
            users.append(normalized['username'])
    return users

def is_current_user_waiting_for_battle():
    return state.current_user in battle_waiting_users()

def current_user_battle_queue_entry(state_data=None):
    state_data = state_data or load_battle_state()
    username = clean_username(state.current_user)
    for entry in state_data.get('queue', []):
        normalized = normalize_battle_queue_entry(entry)
        if normalized and normalized['username'] == username:
            return normalized
    return None

def remove_user_from_battle_state(username):
    username = clean_username(username)
    if not username:
        return
    state_data = load_battle_state()
    queue = state_data.setdefault('queue', [])
    state_data['queue'] = [
        entry for entry in queue
        if not (normalize_battle_queue_entry(entry) and normalize_battle_queue_entry(entry)['username'] == username)
    ]
    room_id = state_data.setdefault('user_room', {}).pop(username, None)
    spectator_room_id = state_data.setdefault('spectator_room', {}).pop(username, None)
    if spectator_room_id and spectator_room_id != room_id:
        spectator_room = state_data.setdefault('rooms', {}).get(spectator_room_id)
        if spectator_room:
            spectator_room['spectators'] = [name for name in spectator_room.get('spectators', []) if name != username]
    room = state_data.setdefault('rooms', {}).get(room_id)
    if room:
        for player in room.get('players', []):
            if player != username:
                state_data['user_room'].pop(player, None)
        for spectator in room.get('spectators', []):
            state_data['spectator_room'].pop(spectator, None)
        state_data['rooms'].pop(room_id, None)
    save_battle_state(state_data)

def battle_is_user_eligible(username=None, user=None):
    username = username or state.current_user
    if not username:
        return False
    if user is None:
        user_data = load_user_data()
        user = get_users(user_data).get(username)
    if not user:
        return False
    ensure_user_defaults(user)
    if user.get('battle_unlocked'):
        return True
    needed = set(battle_unlock_country_keys())
    viewed = set(user.get('viewed_keys', []))
    stats = normalize_quiz_stats(user)
    viewed_present = bool(needed) and needed.issubset(viewed)
    quiz_mastered = int(stats.get('correct', 0) or 0) >= 100
    return viewed_present or quiz_mastered

def mark_battle_unlock_if_ready(user):
    if not state.current_user or not user:
        return False
    ensure_user_defaults(user)
    already_notified = bool(user.get('battle_unlocked_notified'))
    if not battle_is_user_eligible(user=user):
        return False
    user['battle_unlocked'] = True
    if already_notified:
        return False
    user['battle_unlocked_notified'] = True
    return True

def sengoku_quiz_streak(user):
    if not user:
        return 0
    ensure_user_defaults(user)
    streak = 0
    for entry in user.get('quiz_history', []):
        if not isinstance(entry, dict):
            break
        if not entry.get('correct'):
            break
        if (
            entry.get('difficulty') == 'hard'
            and entry.get('category') == 'all'
            and entry.get('scope') == 'all'
            and entry.get('format') == 'mixed'
            and entry.get('mode') == 'normal'
        ):
            streak += 1
            continue
        break
    return streak

def sengoku_is_user_eligible(username=None, user=None):
    username = username or state.current_user
    if not username:
        return False
    if user is None:
        user_data = load_user_data()
        user = get_users(user_data).get(username)
    if not user:
        return False
    ensure_user_defaults(user)
    if user.get('sengoku_unlocked'):
        return True
    if not battle_is_user_eligible(username=username, user=user):
        return False
    return user_viewed_all_public_countries(user) or sengoku_quiz_streak(user) >= 20

def mark_sengoku_unlock_if_ready(user):
    if not state.current_user or not user:
        return False
    ensure_user_defaults(user)
    already_notified = bool(user.get('sengoku_unlocked_notified'))
    if not sengoku_is_user_eligible(user=user):
        return False
    user['sengoku_unlocked'] = True
    if already_notified:
        return False
    user['sengoku_unlocked_notified'] = True
    return True

def set_sengoku_mode(enabled):
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user or not sengoku_is_user_eligible(user=user):
        ui.notify(t('unlock_condition_not_met'), color='warning')
        return False
    user['sengoku_mode'] = bool(enabled)
    state.sengoku_mode = bool(enabled)
    if not state.sengoku_mode and state.quiz_difficulty == 'extreme':
        state.quiz_difficulty = 'hard'
        state.quiz = None
    persist_current_user_data(user_data, immediate_browser=True)
    ui.notify(t('sengoku_mode_on' if enabled else 'sengoku_mode_off'), color='positive' if enabled else 'info')
    refresh_current_screen()
    return True

def apply_admin_search_cheat(keyword):
    if str(keyword or '').strip() != ADMIN_SEARCH_CHEAT_CODE:
        return False
    if not state.current_user:
        ui.notify(t('login_required'), color='warning')
        return True

    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        ui.notify(t('login_required'), color='warning')
        return True

    viewed = user.setdefault('viewed_keys', [])
    for key in all_public_country_keys():
        if key not in viewed:
            viewed.append(key)
    user['all_viewed_granted'] = True
    unlocked_now = mark_battle_unlock_if_ready(user)
    sengoku_unlocked_now = mark_sengoku_unlock_if_ready(user)
    persist_current_user_data(user_data)
    ui.notify(t('admin_search_cheat_applied'), color='positive')
    if unlocked_now:
        ui.notify(t('battle_unlocked_notice'), color='positive')
    if sengoku_unlocked_now:
        ui.notify(t('sengoku_unlocked_notice'), color='positive')
    return True

def apply_sengoku_search_cheat(keyword):
    if str(keyword or '').strip() != SENGOKU_SEARCH_CHEAT_CODE:
        return False
    if not state.current_user:
        ui.notify(t('login_required'), color='warning')
        return True
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        ui.notify(t('login_required'), color='warning')
        return True
    if not battle_is_user_eligible(user=user):
        ui.notify(t('unlock_condition_not_met'), color='warning')
        return True
    user['sengoku_unlocked'] = True
    user['sengoku_unlocked_notified'] = True
    persist_current_user_data(user_data)
    ui.notify(t('sengoku_unlocked_notice'), color='positive')
    refresh_current_screen()
    return True

def battle_draw_pool():
    global BATTLE_DRAW_POOL_CACHE
    mtime = file_mtime(JSON_FILE)
    cached = BATTLE_DRAW_POOL_CACHE.get('value')
    if cached and BATTLE_DRAW_POOL_CACHE.get('mtime') == mtime:
        return cached
    countries = battle_country_list()
    ranked = sorted(
        ((country_key(country), country_battle_power(country)) for country in countries),
        key=lambda item: item[1],
        reverse=True,
    )
    total = max(1, len(ranked) - 1)
    pool = []
    for index, (key, power) in enumerate(ranked):
        rank_ratio = index / total
        weight = 0.08 + (0.92 * rank_ratio)
        pool.append({'key': key, 'weight': weight, 'power': power})
    BATTLE_DRAW_POOL_CACHE = {'mtime': mtime, 'value': pool}
    return pool

def weighted_battle_country_sample(count, room=None):
    pool = [dict(item) for item in battle_draw_pool()]
    if count <= 0 or not pool:
        return []
    if battle_revolution_active(room):
        for item in pool:
            item['weight'] = max(0.01, 1.08 - float(item.get('weight', 0.08) or 0.08))
    selected = []
    for _ in range(min(count, len(pool))):
        total_weight = sum(max(0.01, item.get('weight', 0.01)) for item in pool)
        marker = random.random() * total_weight
        cursor = 0
        chosen_index = 0
        for index, item in enumerate(pool):
            cursor += max(0.01, item.get('weight', 0.01))
            if cursor >= marker:
                chosen_index = index
                break
        selected.append(pool.pop(chosen_index)['key'])
    return selected

def random_battle_special_cards(count):
    if count <= 0:
        return []
    keys = [
        key for key, card in BATTLE_SPECIAL_CARDS.items()
        if float(card.get('weight', 0) or 0) > 0
    ]
    if not keys:
        return []
    weights = [max(0.01, float(BATTLE_SPECIAL_CARDS[key].get('weight', 1))) for key in keys]
    return random.choices(keys, weights=weights, k=count)

def draw_non_vatican_battle_cards(count, room=None):
    vatican_key = battle_vatican_country_key()
    cards = []
    attempts = 0
    while len(cards) < count and attempts < count * 8:
        attempts += 1
        for key in weighted_battle_country_sample(count - len(cards), room):
            if key != vatican_key:
                cards.append(key)
            if len(cards) >= count:
                break
    return cards[:count]

def apply_sengoku_boss_hand_modifiers(room, player):
    boss = sengoku_boss_for_room(room)
    if not boss or not is_battle_bot(player):
        return
    if boss.get('vatican_immunity') and is_sengoku_boss_enemy_bot(room, player):
        vatican_key = battle_vatican_country_key()
        if vatican_key:
            hand = room.setdefault('hands', {}).setdefault(player, [])
            replacements = draw_non_vatican_battle_cards(hand.count(vatican_key), room)
            for index, key in enumerate(list(hand)):
                if key == vatican_key and replacements:
                    hand[index] = replacements.pop(0)
    if boss.get('command_infinite') and is_sengoku_boss_enemy_bot(room, player):
        room.setdefault('command', {})[player] = BATTLE_MAX_COMMAND

def draw_battle_cards(count=5, room=None):
    count = max(0, int(count or 0))
    if count <= 0:
        return []
    special_count = 0
    if battle_room_events_enabled(room) and battle_world_war_active(room) and count > 1:
        special_count = sum(1 for _ in range(count) if random.random() < BATTLE_SPECIAL_CARD_CHANCE)
        special_count = min(special_count, BATTLE_SPECIAL_CARD_MAX_PER_HAND, count - 1)
    normal_count = max(0, count - special_count)
    cards = weighted_battle_country_sample(normal_count, room)
    if battle_room_events_enabled(room) and battle_vatican_active(room):
        vatican_key = battle_vatican_country_key()
        if vatican_key:
            cards = [
                vatican_key if random.random() < BATTLE_VATICAN_DRAW_CHANCE else key
                for key in cards
            ]
            power_indexes = [index for index, key in enumerate(cards) if is_battle_power_card(key)]
            if len(power_indexes) > 1 and all(cards[index] == vatican_key for index in power_indexes):
                replacement = draw_non_vatican_battle_cards(1, room)
                if replacement:
                    cards[power_indexes[-1]] = replacement[0]
    if special_count:
        specials = random_battle_special_cards(special_count)
        cards.extend(specials)
        random.shuffle(cards)
    boss = sengoku_boss_for_room(room)
    if boss and boss.get('special_pressure') and battle_world_war_active(room) and count > 1:
        extra_limit = min(3, max(1, count - 1))
        current_specials = sum(1 for key in cards if is_battle_special_card(key))
        extra_count = max(0, extra_limit - current_specials)
        if extra_count:
            cards = cards[:max(0, count - extra_count)] + random_battle_special_cards(extra_count)
            random.shuffle(cards)
    return cards

def deal_battle_hand(room=None, count=5):
    return draw_battle_cards(count, room)

def current_battle_room():
    return battle_room_for_user(state.current_user, load_battle_state_with_timeouts())

def current_battle_room_snapshot(state_data=None):
    state_data = state_data or load_battle_state()
    username = clean_username(state.current_user)
    room_id = state_data.get('user_room', {}).get(username) or state_data.get('spectator_room', {}).get(username)
    room = state_data.get('rooms', {}).get(room_id)
    if isinstance(room, dict):
        return room
    return None

def battle_teams_for_players(players, mode, team_choices=None, team_count=2):
    if mode != TEAM_MODE:
        return {}
    team_choices = team_choices or {}
    team_count = normalize_battle_team_count(team_count)
    valid = BATTLE_TEAM_IDS[:team_count]
    return {
        player: normalize_battle_team_choice(team_choices.get(player, valid[index % len(valid)]), team_count)
        for index, player in enumerate(players)
    }

def create_battle_bot_names(players, target_count):
    used = set(players)
    names = []
    index = 1
    while len(players) + len(names) < target_count:
        name = BOT_USERNAME if index == 1 else f'{BOT_USERNAME}{index}'
        index += 1
        if name in used:
            continue
        used.add(name)
        names.append(name)
    return names

def create_battle_room(*players, state_data=None, mode=DUEL_MODE, bot=False, turn_timeout_seconds=None, world_war_turn=None, player_count=None, team_count=None, team_choices=None, host=None, events_enabled=True, sengoku_mode=False, sengoku_boss_id=None):
    state_data = state_data or load_battle_state()
    players = [clean_username(player) for player in players if clean_username(player)]
    if len(players) < 2:
        return None
    try:
        raw_timeout_seconds = int(turn_timeout_seconds)
    except (TypeError, ValueError):
        raw_timeout_seconds = None
    turn_timeout_seconds = 30 if sengoku_boss_id and raw_timeout_seconds == 30 else normalize_battle_timeout_seconds(turn_timeout_seconds)
    world_war_turn = normalize_battle_world_war_turn(world_war_turn)
    player_count = normalize_battle_player_count(player_count or len(players), mode)
    team_count = normalize_battle_team_count(team_count or 2)
    host = clean_username(host) or next((player for player in players if not is_battle_bot(player)), players[0])
    state_data['counter'] = int(state_data.get('counter', 0)) + 1
    room_id = f"battle-{state_data['counter']}"
    teams = battle_teams_for_players(players, mode, team_choices, team_count)
    room = {
        'id': room_id,
        'mode': mode,
        'players': players,
        'host': host,
        'player_count': player_count,
        'team_count': team_count,
        'teams': teams,
        'hp': {player: BATTLE_MAX_HP for player in players},
        'team_hp': {},
        'hands': {},
        'reload_after_turn': [],
        'redraw_turns': {},
        'command': {player: BATTLE_MAX_COMMAND for player in players},
        'submitted': {},
        'log': [],
        'chat': [],
        'team_chat': [],
        'spectators': [],
        'bot_owners': {},
        'player_seen_at': {player: current_timestamp() for player in players if not is_battle_bot(player)},
        'last_turn': {},
        'world_war_started': False,
        'world_war_turn': world_war_turn,
        'events_enabled': bool(events_enabled),
        'sengoku_mode': bool(sengoku_mode),
        'sengoku_boss_id': str(sengoku_boss_id or ''),
        'satrapy_shield_damage': {},
        'satrapy_broken_provinces': [],
        'revolution_until_turn': 0,
        'flag_only_until_turn': 0,
        'vatican_until_turn': 0,
        'replace_until_turn': 0,
        'bomb_until_turn': 0,
        'lytton_until_turn': 0,
        'damage_surge_until_turn': 0,
        'random_target_until_turn': 0,
        'operation_required_turn': 0,
        'operation_required_count': 0,
        'ceasefire_until_turn': 0,
        'command_surge_until_turn': 0,
        'supply_drop_until_turn': 0,
        'blockade_until_turn': 0,
        'bomb_holder': None,
        'bomb_cover_key': None,
        'turn_timeout_seconds': turn_timeout_seconds,
        'turn': 1,
        'turn_started_at': current_timestamp(),
        'winner': None,
        'bot': bool(bot),
        'kicked': [],
    }
    apply_sengoku_boss_forced_state(room)
    for player in players:
        room.setdefault('command', {})[player] = battle_player_command_limit(room, player)
    room['hands'] = {player: deal_battle_hand(room, battle_deal_count_for_player(room, player)) for player in players}
    for player in players:
        hp_limit = battle_player_hp_limit(room, player)
        room['hp'][player] = hp_limit
    ensure_battle_team_hp(room)
    state_data.setdefault('rooms', {})[room_id] = room
    for player in players:
        if not is_battle_bot(player):
            state_data.setdefault('user_room', {})[player] = room_id
    save_battle_state(state_data)
    if state.current_user in room['players']:
        state.battle_id = room_id
    return room

def create_bot_battle():
    username = state.current_user
    if not battle_is_user_eligible(username):
        ui.notify(t('unlock_condition_not_met'), color='warning')
        return
    state_data = load_battle_state()
    if battle_room_for_user(username, state_data):
        refresh_battle_view()
        return
    create_battle_room(
        username,
        BOT_USERNAME,
        state_data=state_data,
        mode=BOT_MODE,
        bot=True,
        turn_timeout_seconds=selected_battle_timeout_seconds(),
        world_war_turn=selected_battle_world_war_turn(),
        player_count=2,
        events_enabled=selected_battle_events_enabled(),
        sengoku_mode=bool(state.sengoku_mode),
    )
    ui.notify(t('battle_matched'), color='positive')
    refresh_battle_view()

def create_sengoku_boss_battle(boss_id, replace_current=False):
    username = state.current_user
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not username or not user or not sengoku_is_user_eligible(user=user) or not state.sengoku_mode:
        ui.notify(t('unlock_condition_not_met'), color='warning')
        return
    boss = sengoku_boss_by_id(boss_id)
    if not boss or not sengoku_boss_is_unlocked(user, boss['id']):
        ui.notify('このボスはまだ解放されていません。', color='warning')
        return
    state_data = load_battle_state()
    current_room = battle_room_for_user(username, state_data)
    if current_room:
        if replace_current and current_room.get('winner') and is_sengoku_boss_room(current_room):
            state_data.setdefault('user_room', {}).pop(username, None)
            state_data.setdefault('spectator_room', {}).pop(username, None)
            current_room['spectators'] = [name for name in current_room.get('spectators', []) if name != username]
            prune_empty_battle_rooms(state_data)
            state.battle_id = None
            state.battle_selected_keys = set()
        else:
            refresh_battle_view()
            return
    enemy_count = max(1, int(boss.get('enemy_count', 1) or 1))
    player_ally_count = max(0, int(boss.get('player_ally_count', 0) or 0))
    players = [username]
    ally_bots = create_battle_bot_names(players, len(players) + player_ally_count)
    players.extend(ally_bots)
    enemy_bots = create_battle_bot_names(players, len(players) + enemy_count)
    players.extend(enemy_bots)
    team_choices = {}
    if boss.get('mode') == TEAM_MODE:
        player_team = str(boss.get('player_team', 'A') or 'A')
        enemy_team = str(boss.get('enemy_team', 'B') or 'B')
        team_choices = {username: player_team}
        for player in ally_bots:
            team_choices[player] = player_team
        for player in enemy_bots:
            team_choices[player] = enemy_team
    room = create_battle_room(
        *players,
        state_data=state_data,
        mode=boss.get('mode', BOT_MODE),
        bot=True,
        turn_timeout_seconds=boss.get('timeout', 180),
        world_war_turn=75,
        player_count=len(players),
        team_count=2,
        team_choices=team_choices,
        events_enabled=True,
        sengoku_mode=True,
        sengoku_boss_id=boss['id'],
    )
    if room:
        if ally_bots:
            room['boss_player_allies'] = ally_bots
        append_battle_log(room, f"ボス戦: {localized_boss_text(boss, 'name')}")
        save_battle_state(state_data)
    ui.notify(f"{localized_boss_text(boss, 'name')} に挑戦します。", color='positive')
    refresh_battle_view()

def battle_queue_entry_matches(entry, mode, turn_timeout_seconds, world_war_turn, player_count, team_count, events_enabled=None):
    return (
        entry.get('mode') == mode
        and entry.get('turn_timeout_seconds') == turn_timeout_seconds
        and entry.get('world_war_turn') == world_war_turn
        and entry.get('player_count') == player_count
        and (mode != TEAM_MODE or entry.get('team_count') == team_count)
        and (events_enabled is None or bool(entry.get('events_enabled', True)) == bool(events_enabled))
    )

def start_current_battle_queue_now():
    username = state.current_user
    state_data = load_battle_state()
    current_entry = current_user_battle_queue_entry(state_data)
    if not current_entry:
        refresh_battle_view()
        return
    if battle_room_for_user(username, state_data):
        refresh_battle_view()
        return
    mode = current_entry.get('mode', DUEL_MODE)
    player_count = normalize_battle_player_count(current_entry.get('player_count'), mode)
    team_count = normalize_battle_team_count(current_entry.get('team_count'))
    players = [username]
    team_choices = {username: normalize_battle_team_choice(current_entry.get('team_choice'), team_count)}
    remaining_queue = []
    for entry in state_data.setdefault('queue', []):
        normalized = normalize_battle_queue_entry(entry)
        if not normalized or normalized.get('username') == username:
            continue
        if (
            len(players) < player_count
            and battle_is_user_eligible(normalized['username'])
            and battle_queue_entry_matches(
                normalized,
                mode,
                current_entry.get('turn_timeout_seconds'),
                current_entry.get('world_war_turn'),
                player_count,
                team_count,
                current_entry.get('events_enabled', True),
            )
        ):
            players.append(normalized['username'])
            team_choices[normalized['username']] = normalize_battle_team_choice(normalized.get('team_choice'), team_count)
        else:
            remaining_queue.append(normalized)
    players.extend(create_battle_bot_names(players, player_count))
    state_data['queue'] = remaining_queue
    create_battle_room(
        *players,
        state_data=state_data,
        mode=mode,
        bot=any(is_battle_bot(player) for player in players),
        turn_timeout_seconds=current_entry.get('turn_timeout_seconds'),
        world_war_turn=current_entry.get('world_war_turn'),
        player_count=player_count,
        team_count=team_count,
        team_choices=team_choices,
        host=username,
        events_enabled=current_entry.get('events_enabled', True),
        sengoku_mode=bool(state.sengoku_mode),
    )
    ui.notify(t('battle_matched'), color='positive')
    refresh_battle_view()

def join_battle_queue(mode=DUEL_MODE):
    username = state.current_user
    if not battle_is_user_eligible(username):
        ui.notify(t('unlock_condition_not_met'), color='warning')
        return
    mode = mode if mode in MULTIPLAYER_MODES else DUEL_MODE
    turn_timeout_seconds = selected_battle_timeout_seconds()
    world_war_turn = selected_battle_world_war_turn()
    player_count = selected_battle_player_count(mode)
    team_count = selected_battle_team_count()
    team_choice = normalize_battle_team_choice(getattr(state, 'battle_team_choice', 'A'), team_count)
    events_enabled = selected_battle_events_enabled()
    state_data = load_battle_state()
    if battle_room_for_user(username, state_data):
        refresh_battle_view()
        return
    queue = state_data.setdefault('queue', [])
    waiting = []
    normalized_queue = []
    for entry in queue:
        normalized = normalize_battle_queue_entry(entry)
        if not normalized:
            continue
        if normalized['username'] == username:
            continue
        if not battle_is_user_eligible(normalized['username']):
            continue
        normalized_queue.append(normalized)
    for normalized in normalized_queue:
        waiting_user = normalized['username']
        if not battle_queue_entry_matches(normalized, mode, turn_timeout_seconds, world_war_turn, player_count, team_count, selected_battle_events_enabled()):
            continue
        waiting.append(waiting_user)
        if len(waiting) >= player_count - 1:
            break
    if len(waiting) >= player_count - 1:
        players = waiting[:player_count - 1] + [username]
        used = set(players)
        team_choices = {
            entry['username']: normalize_battle_team_choice(entry.get('team_choice'), team_count)
            for entry in normalized_queue
            if entry['username'] in used
        }
        team_choices[username] = team_choice
        state_data['queue'] = [entry for entry in normalized_queue if entry['username'] not in used]
        create_battle_room(
            *players,
            state_data=state_data,
            mode=mode,
            turn_timeout_seconds=turn_timeout_seconds,
            world_war_turn=world_war_turn,
            player_count=player_count,
            team_count=team_count,
            team_choices=team_choices,
            host=players[0],
            events_enabled=events_enabled,
            sengoku_mode=bool(state.sengoku_mode),
        )
        ui.notify(t('battle_matched'), color='positive')
        refresh_battle_view()
        return
    normalized_queue.append({
        'username': username,
        'mode': mode,
        'turn_timeout_seconds': turn_timeout_seconds,
        'world_war_turn': world_war_turn,
        'player_count': player_count,
        'team_count': team_count,
        'team_choice': team_choice,
        'events_enabled': events_enabled,
    })
    state_data['queue'] = normalized_queue
    save_battle_state(state_data)
    refresh_battle_view()

def cancel_battle_queue():
    username = state.current_user
    state_data = load_battle_state()
    queue = state_data.setdefault('queue', [])
    state_data['queue'] = [
        entry for entry in queue
        if not (normalize_battle_queue_entry(entry) and normalize_battle_queue_entry(entry)['username'] == username)
    ]
    save_battle_state(state_data)
    refresh_battle_view()

def randomize_current_battle_teams():
    username = state.current_user
    state_data = load_battle_state()
    room = battle_room_for_user(username, state_data)
    if not room or room.get('winner') or room.get('mode') != TEAM_MODE:
        refresh_battle_view()
        return
    if clean_username(room.get('host')) != username or int(room.get('turn', 1) or 1) != 1 or room.get('submitted'):
        ui.notify(t('battle_host_only'), color='warning')
        return
    team_count = normalize_battle_team_count(room.get('team_count'))
    teams = BATTLE_TEAM_IDS[:team_count]
    players = list(room.get('players', []))
    random.shuffle(players)
    room['teams'] = {
        player: teams[index % len(teams)]
        for index, player in enumerate(players)
    }
    room['team_hp'] = {}
    ensure_battle_team_hp(room)
    append_battle_log(room, t('battle_team_randomized_log').format(host=username))
    save_battle_state(state_data)
    refresh_battle_view()

def leave_finished_battle(join_again=False):
    username = state.current_user
    state_data = load_battle_state()
    room = battle_room_for_user(username, state_data)
    if room:
        state.battle_turn_timeout_seconds = battle_room_timeout_seconds(room)
        state.battle_world_war_turn = battle_room_world_war_turn(room)
        state_data.setdefault('user_room', {}).pop(username, None)
        state_data.setdefault('spectator_room', {}).pop(username, None)
        room['spectators'] = [name for name in room.get('spectators', []) if name != username]
        prune_empty_battle_rooms(state_data)
        save_battle_state(state_data)
    state.battle_id = None
    state.battle_selected_keys = set()
    if join_again:
        join_battle_queue()
    else:
        refresh_battle_view()

def add_battle_win(username):
    user_data = load_user_data()
    users = get_users(user_data)
    user = users.get(username)
    if not user:
        return
    ensure_user_defaults(user)
    user['battle_wins'] = int(user.get('battle_wins', 0)) + 1
    save_user_data(user_data)
    if username == state.current_user:
        sync_current_user_to_browser(user_data)

def award_sengoku_boss_clear_if_needed(username, room):
    username = clean_username(username)
    boss = sengoku_boss_for_room(room)
    if not username or not boss or is_battle_bot(username):
        return False
    winner = room.get('winner')
    user_won = winner == username
    if isinstance(winner, str) and winner.startswith('team:'):
        user_won = room.get('teams', {}).get(username) == winner.split(':', 1)[1]
    if not user_won:
        return False
    user_data = load_user_data()
    user = get_users(user_data).get(username)
    if not user:
        return False
    ensure_user_defaults(user)
    clears = normalize_sengoku_boss_clears(user.get('sengoku_boss_clears', []))
    newly_cleared = boss['id'] not in clears
    if newly_cleared:
        clears.append(boss['id'])
    user['sengoku_boss_clears'] = normalize_sengoku_boss_clears(clears)
    completed = all_sengoku_bosses_cleared(user)
    newly_awarded = completed and not bool(user.get('sengoku_medal'))
    if completed:
        user['sengoku_medal'] = True
    room['sengoku_boss_cleared_by'] = username
    room['sengoku_boss_clear_count'] = sengoku_boss_clear_count(user)
    save_user_data(user_data)
    if username == state.current_user:
        sync_current_user_to_browser(user_data)
        if newly_cleared:
            ui.notify(f"{localized_boss_text(boss, 'name')} を撃破しました。", color='positive')
        if newly_awarded:
            ui.notify(t('sengoku_medal_unlocked_notice'), color='positive')
            if state.staff_roll_room_shown != room.get('id'):
                state.staff_roll_room_shown = room.get('id')
                ui.timer(0.2, show_staff_roll, once=True)
    return newly_cleared or newly_awarded

def is_sengoku_medal_battle(room, winner):
    winner = clean_username(winner)
    if not winner or is_battle_bot(winner) or not isinstance(room, dict):
        return False
    human_players = [player for player in room.get('players', []) if not is_battle_bot(player)]
    return (
        room.get('mode') == BOT_MODE
        and bool(room.get('bot'))
        and bool(room.get('sengoku_mode'))
        and len(human_players) == 1
        and human_players[0] == winner
        and battle_room_timeout_seconds(room) == BATTLE_TURN_TIMEOUT_SECONDS
        and battle_room_world_war_turn(room) == BATTLE_WORLD_WAR_DISABLED
        and not battle_room_events_enabled(room)
    )

def award_sengoku_medal_if_needed(username, room):
    username = clean_username(username)
    if award_sengoku_boss_clear_if_needed(username, room):
        return True
    return False

def battle_base_powers_for_keys(keys, room=None):
    lookup = battle_country_lookup()
    return [battle_card_power_for_key(key, lookup, room) for key in keys if key in lookup]

def battle_power_for_keys(keys, room=None):
    powers = sorted(battle_base_powers_for_keys(keys, room), reverse=True)
    total = 0
    for index, power in enumerate(powers):
        percent = BATTLE_CARD_POWER_PERCENTS[min(index, len(BATTLE_CARD_POWER_PERCENTS) - 1)]
        total += max(1, power * percent // 100)
    return total

def battle_bonus_scale(labels):
    return BATTLE_BONUS_DENOMINATOR + (BATTLE_BONUS_PER_MATCH_BPS * len(labels))

def battle_bonus_multiplier(labels, revolution=False):
    scale = battle_bonus_scale(labels)
    if revolution and labels:
        return BATTLE_BONUS_DENOMINATOR / scale
    return scale / BATTLE_BONUS_DENOMINATOR

def apply_battle_bonus_value(value, labels, revolution=False):
    value = max(0, int(value))
    scale = battle_bonus_scale(labels)
    if revolution and labels:
        return value * BATTLE_BONUS_DENOMINATOR // scale
    return value * scale // BATTLE_BONUS_DENOMINATOR

def battle_defense_breakdown_for_keys(keys, room=None):
    labels = repeated_battle_bonus_labels(keys)
    base_defense = battle_power_for_keys(keys, room) * BATTLE_DEFENSE_PERCENT // 100
    return apply_battle_bonus_value(base_defense, labels), battle_bonus_multiplier(labels), labels

def battle_defense_detail_for_keys(keys, room=None):
    labels = repeated_battle_bonus_labels(keys)
    base_defense = battle_power_for_keys(keys, room) * BATTLE_DEFENSE_PERCENT // 100
    final_defense = apply_battle_bonus_value(base_defense, labels)
    return {
        'base': base_defense,
        'final': final_defense,
        'bonus_value': max(0, final_defense - base_defense),
        'multiplier': battle_bonus_multiplier(labels),
        'labels': labels,
    }

def battle_defense_for_keys(keys, room=None):
    defense, _, _ = battle_defense_breakdown_for_keys(keys, room)
    return defense

def battle_tags_for_keys(keys):
    lookup = battle_country_lookup()
    tags = set()
    for key in keys:
        country = lookup.get(key)
        if country:
            tags.update(country.get('tags', []))
    return tags

def battle_regions_for_keys(keys):
    lookup = battle_country_lookup()
    regions = set()
    for key in keys:
        country = lookup.get(key)
        if not country:
            continue
        for region in str(country.get('region') or '').replace('/', ',').split(','):
            region = region.strip()
            if region:
                regions.add(region)
    return regions

def repeated_battle_bonus_labels(keys):
    if len(keys) < 2:
        return []

    lookup = battle_country_lookup()
    tag_counts = {}
    region_counts = {}
    for key in keys:
        country = lookup.get(key)
        if not country:
            continue

        for tag in set(country.get('tags', [])):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

        card_regions = set()
        for region in str(country.get('region') or '').replace('/', ',').split(','):
            region = region.strip()
            if region:
                card_regions.add(region)
        for region in card_regions:
            region_counts[region] = region_counts.get(region, 0) + 1

    repeated_tags = sorted(
        [tag for tag, count in tag_counts.items() if count >= 2],
        key=lambda tag: tag_label(tag).lower(),
    )
    repeated_regions = sorted(
        [region for region, count in region_counts.items() if count >= 2],
        key=lambda region: region_label(region).lower(),
    )
    return [tag_label(tag) for tag in repeated_tags] + [region_label(region) for region in repeated_regions]

def battle_bonus_for_keys(keys, room=None):
    labels = repeated_battle_bonus_labels(keys)
    return battle_bonus_multiplier(labels, battle_revolution_active(room)), labels

def format_battle_multiplier(multiplier):
    text = f'{float(multiplier):.3f}'.rstrip('0').rstrip('.')
    return text or '1'

def format_signed_battle_number(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return str(value)
    sign = '+' if value >= 0 else '-'
    return f'{sign}{format_battle_number(abs(value))}'

def battle_bonus_text(labels, multiplier):
    if not labels:
        return ''
    return f" / {t('battle_bonus')} x{format_battle_multiplier(multiplier)}: {', '.join(labels[:5])}"

def battle_defense_bonus_text(labels, multiplier):
    if not labels:
        return ''
    return f" / {t('battle_defense')} {t('battle_bonus')} x{format_battle_multiplier(multiplier)}: {', '.join(labels[:5])}"

def battle_log_label(labels):
    return labels.get(state.lang, labels.get('en', ''))

def battle_played_cards_title():
    return battle_log_label({
        'ja': '\u51fa\u3057\u305f\u30ab\u30fc\u30c9',
        'en': 'Played cards',
        'zh': '\u6253\u51fa\u7684\u724c',
    })

def battle_no_cards_label():
    return battle_log_label({
        'ja': '\u306a\u3057',
        'en': 'none',
        'zh': '\u65e0',
    })

def battle_defenseless_log_label():
    return battle_log_label({
        'ja': '\u7121\u9632\u5099',
        'en': 'defenseless',
        'zh': '\u65e0\u9632\u5907',
    })

def battle_country_names_for_keys(keys, lookup=None, room=None):
    lookup = lookup or battle_country_lookup()
    names = []
    for key in keys:
        names.append(battle_card_display_name(key, lookup, room))
    return names

def battle_visual_card(key, lookup=None, room=None, reveal_bomb=False):
    lookup = lookup or battle_country_lookup()
    if is_battle_special_card(key):
        if str(key or '') == BATTLE_BOMB_CARD and not reveal_bomb:
            country = battle_bomb_cover_country(room, lookup)
            if country:
                return {
                    'key': key,
                    'name': get_localized_text(country.get('names', {})),
                    'special': False,
                    'disguised_bomb': True,
                    'flag': get_flag_url(country.get('flag_code')),
                }
        return {
            'key': key,
            'name': battle_special_card_label(key),
            'special': True,
            'damage': battle_special_card_damage(key),
            'heal': battle_special_card_heal(key),
            'destroy_one': bool(BATTLE_SPECIAL_CARDS.get(str(key), {}).get('destroy_one')),
            'flag': None,
        }
    country = lookup.get(key)
    if not country:
        return {'key': key, 'name': str(key), 'special': False, 'flag': None}
    return {
        'key': key,
        'name': battle_card_display_name(key, lookup, room) or str(key),
        'special': False,
        'flag': get_flag_url(country.get('flag_code')),
    }

def battle_visual_payload(room, entries):
    lookup = battle_country_lookup()
    return {
        'turn': int(room.get('turn', 1) or 1),
        'world_war': battle_world_war_active(room),
        'revolution': battle_revolution_active(room),
        'flag_only': battle_flag_only_active(room),
        'vatican': battle_vatican_active(room),
        'replace': battle_replace_active(room),
        'bomb': battle_bomb_active(room),
        'lytton': battle_lytton_active(room),
        'damage_surge': battle_damage_surge_active(room) or bool((sengoku_boss_for_room(room) or {}).get('player_damage_surge')),
        'random_target': battle_random_target_active(room),
        'ceasefire': battle_ceasefire_active(room),
        'command_surge': battle_command_surge_active(room),
        'supply_drop': battle_supply_drop_active(room),
        'blockade': battle_blockade_active(room),
        'played': [
            {
                'player': player,
                'defenseless': bool(entries.get(player, {}).get('defenseless')),
                'power': int(entries.get(player, {}).get('power', 0) or 0),
                'defense': int(entries.get(player, {}).get('defense', 0) or 0),
                'defense_base': int(entries.get(player, {}).get('defense_base', 0) or 0),
                'defense_bonus_value': int(entries.get(player, {}).get('defense_bonus_value', 0) or 0),
                'defense_multiplier': entries.get(player, {}).get('defense_multiplier', 1),
                'defense_bonus_labels': list(entries.get(player, {}).get('defense_bonus_labels', [])),
                'hand_count_before': len(room.setdefault('hands', {}).get(player, [])),
                'target': entries.get(player, {}).get('target'),
                'cards': [battle_visual_card(key, lookup, room) for key in entries.get(player, {}).get('keys', [])],
                'defense_cards': [battle_visual_card(key, lookup, room) for key in entries.get(player, {}).get('defense_keys', [])],
            }
            for player in room.get('players', [])
            if player in entries
        ],
        'damage': [],
        'counters': [],
        'steals': [],
        'self_damage': [],
        'bombs': [],
        'replacements': [],
    }

def battle_played_cards_log(room, entries):
    lookup = battle_country_lookup()
    parts = []
    for player in room.get('players', []):
        entry = entries.get(player, {})
        if entry.get('defenseless'):
            card_text = battle_defenseless_log_label()
        else:
            names = battle_country_names_for_keys(entry.get('keys', []), lookup, room)
            card_text = ', '.join(names) if names else battle_no_cards_label()
        parts.append(f'{player}: {card_text}')
    if not parts:
        return ''
    return f"{battle_played_cards_title()}: {' / '.join(parts)}"

def battle_entry_for_player(room, player):
    submitted = room.setdefault('submitted', {}).get(player, {})
    keys = list(submitted.get('keys', []))
    defense_keys = list(submitted.get('defense_keys', []))
    defense = int(submitted.get('defense', 0) or 0)
    defense_base = int(submitted.get('defense_base', 0) or 0)
    defense_multiplier = 1
    defense_bonus_labels = []
    defense_bonus_value = 0
    power = int(submitted.get('power', 0) or 0)
    if keys:
        power = battle_power_for_keys(keys, room)
    if defense_keys:
        defense_detail = battle_defense_detail_for_keys(defense_keys, room)
        defense = defense_detail['final']
        defense_base = defense_detail['base']
        defense_multiplier = defense_detail['multiplier']
        defense_bonus_labels = defense_detail['labels']
        defense_bonus_value = defense_detail['bonus_value']
    return {
        'keys': keys,
        'power': power,
        'defense': defense,
        'defense_base': defense_base,
        'defense_bonus_value': defense_bonus_value,
        'defense_keys': defense_keys,
        'defense_multiplier': defense_multiplier,
        'defense_bonus_labels': defense_bonus_labels,
        'defenseless': bool(submitted.get('defenseless')),
        'target': clean_username(submitted.get('target')),
    }

def battle_turn_pressure_scale(turn):
    try:
        turn = int(turn)
    except (TypeError, ValueError):
        turn = 1
    extra_turns = max(0, turn - BATTLE_PRESSURE_START_TURN)
    extra_bps = min(BATTLE_PRESSURE_MAX_EXTRA_BPS, extra_turns * BATTLE_PRESSURE_PER_TURN_BPS)
    return BATTLE_BONUS_DENOMINATOR + extra_bps

def apply_battle_turn_pressure(value, turn):
    return max(0, int(value) * battle_turn_pressure_scale(turn) // BATTLE_BONUS_DENOMINATOR)

def battle_damage_breakdown(win_power, lose_power, defense, labels, turn=1, world_war=False, event_multiplier=1, defense_base=None, defense_labels=None, defense_multiplier=1, counter_event_multiplier=None, revolution=False):
    power_gap = max(0, int(win_power) - int(lose_power))
    defense = max(0, int(defense or 0))
    attack_after_bonus = apply_battle_bonus_value(power_gap, labels, revolution)
    attack_bonus_value = attack_after_bonus - power_gap
    blocked_damage = max(0, attack_after_bonus - defense)
    counter_base = max(0, defense - attack_after_bonus)
    pressured_damage = apply_battle_turn_pressure(blocked_damage, turn)
    pressured_counter = apply_battle_turn_pressure(counter_base, turn)
    world_war_multiplier = BATTLE_WORLD_WAR_DAMAGE_MULTIPLIER if world_war else 1
    event_multiplier = max(0.01, float(event_multiplier or 1))
    counter_event_multiplier = event_multiplier if counter_event_multiplier is None else max(0.01, float(counter_event_multiplier or 1))
    damage = int(pressured_damage * world_war_multiplier * event_multiplier * BATTLE_DAMAGE_OUTPUT_PERCENT / 100)
    counter = int(pressured_counter * world_war_multiplier * counter_event_multiplier * BATTLE_DAMAGE_OUTPUT_PERCENT / 100)
    if defense_base is None:
        defense_base = defense
    defense_base = max(0, int(defense_base or 0))
    return {
        'win_power': int(win_power),
        'lose_power': int(lose_power),
        'power_gap': power_gap,
        'attack_bonus_multiplier': battle_bonus_multiplier(labels, revolution),
        'attack_bonus_labels': list(labels or []),
        'attack_bonus_value': attack_bonus_value,
        'attack_after_bonus': attack_after_bonus,
        'revolution_bonus_inverted': bool(revolution and labels),
        'defense_base': defense_base,
        'defense': defense,
        'defense_bonus_value': max(0, defense - defense_base),
        'defense_bonus_multiplier': float(defense_multiplier or 1),
        'defense_bonus_labels': list(defense_labels or []),
        'after_defense': blocked_damage,
        'counter_base': counter_base,
        'turn_pressure_multiplier': battle_turn_pressure_scale(turn) / BATTLE_BONUS_DENOMINATOR,
        'world_war_multiplier': world_war_multiplier,
        'event_multiplier': event_multiplier,
        'counter_event_multiplier': counter_event_multiplier,
        'damage_output_multiplier': BATTLE_DAMAGE_OUTPUT_PERCENT / 100,
        'damage': max(0, damage),
        'counter': max(0, counter),
    }

def battle_damage_after_defense(win_power, lose_power, defense, labels, hp_limit=None, turn=1, world_war=False, event_multiplier=1):
    return battle_damage_breakdown(win_power, lose_power, defense, labels, turn, world_war, event_multiplier)['damage']

def battle_damage_and_counter(win_power, lose_power, defense, labels, turn=1, world_war=False, event_multiplier=1):
    breakdown = battle_damage_breakdown(win_power, lose_power, defense, labels, turn, world_war, event_multiplier)
    return breakdown['damage'], breakdown['counter']

def battle_defense_text(entry):
    defense = int((entry or {}).get('defense', 0) or 0)
    if defense <= 0:
        return ''
    labels = (entry or {}).get('defense_bonus_labels', [])
    multiplier = (entry or {}).get('defense_multiplier', 1)
    return f" / {t('battle_defense')} {format_battle_number(defense)}{battle_defense_bonus_text(labels, multiplier)}"

def battle_group_defense_text(entries, players):
    defense = sum(int(entries.get(player, {}).get('defense', 0) or 0) for player in players)
    if defense <= 0:
        return ''
    labels = []
    for player in players:
        labels.extend(entries.get(player, {}).get('defense_bonus_labels', []))
    unique_labels = sorted(set(labels))
    bonus_note = f" / {t('battle_defense')} {t('battle_bonus')}: {', '.join(unique_labels[:5])}" if unique_labels else ''
    return f" / {t('battle_defense')} {format_battle_number(defense)}{bonus_note}"

def remove_submitted_cards_and_reload(room):
    players = active_battle_players(room)
    reload_set = set(room.get('reload_after_turn', []))
    defenseless_players = set()
    for player in players:
        submitted = battle_entry_for_player(room, player)
        hand = room.setdefault('hands', {}).setdefault(player, [])
        if submitted.get('defenseless'):
            defenseless_players.add(player)
            reload_set.discard(player)
        else:
            for key in submitted.get('keys', []):
                if key in hand:
                    hand.remove(key)
    return reload_set, defenseless_players

def steal_remaining_cards(room, winners, losers, defenseless_players, result_parts, visual=None, entries=None):
    lookup = battle_country_lookup()
    winners = [winner for winner in winners if winner in room.get('players', [])]
    losers = [loser for loser in losers if loser in room.get('players', []) and loser not in defenseless_players]
    if not winners or not losers:
        return
    for index, loser in enumerate(losers):
        loser_hand = room.setdefault('hands', {}).setdefault(loser, [])
        stealable = [key for key in loser_hand if key in lookup or key == BATTLE_BOMB_CARD]
        if stealable:
            stolen_key = random.choice(stealable)
            loser_hand.remove(stolen_key)
        else:
            submitted = entries.get(loser, {}) if isinstance(entries, dict) else {}
            played_cards = [key for key in submitted.get('keys', []) if key in lookup]
            if not played_cards:
                continue
            stolen_key = random.choice(played_cards)
        winner = winners[index % len(winners)]
        winner_hand = room.setdefault('hands', {}).setdefault(winner, [])
        winner_hand.append(stolen_key)
        if stolen_key == BATTLE_BOMB_CARD:
            room['bomb_holder'] = winner
        stolen_name = battle_card_display_name(stolen_key, lookup, room)
        result_parts.append(t('battle_steal_log').format(winner=winner, loser=loser, country=stolen_name))
        if visual is not None:
            visual.setdefault('steals', []).append({
                'winner': winner,
                'loser': loser,
                'key': stolen_key,
                'name': stolen_name,
                'card': battle_visual_card(stolen_key, lookup, room),
            })

def battle_bomb_damage(room):
    hp_limit = battle_team_hp_limit(room) if room.get('mode') == TEAM_MODE else BATTLE_MAX_HP
    return max(1, hp_limit * BATTLE_BOMB_DAMAGE_PERCENT // 100)

def battle_bomb_explosion_log(player, cover_name, damage, reason='played'):
    labels = {
        'ja': {
            'played': '{player}が{card}を出した瞬間、それが爆弾カードとして爆発し、{damage}ダメージを受けました。',
            'expired': 'イベント終了時、{player}の手元の{card}が爆弾カードとして爆発し、{damage}ダメージを受けました。',
        },
        'en': {
            'played': '{player} played {card}, but it was a hidden bomb and exploded for {damage} damage.',
            'expired': 'At the end of the event, {player}\'s {card} was revealed as a bomb and exploded for {damage} damage.',
        },
        'zh': {
            'played': '{player}打出了{card}，但它其实是炸弹牌，爆炸造成{damage}伤害。',
            'expired': '事件结束时，{player}手中的{card}被发现是炸弹牌，爆炸造成{damage}伤害。',
        },
    }
    template = labels.get(state.lang, labels['en']).get(reason, labels.get(state.lang, labels['en'])['played'])
    return template.format(player=player, card=cover_name, damage=format_battle_number(damage))

def battle_explode_bomb(room, holder, result_parts, visual=None, reason='played'):
    holder = clean_username(holder)
    if not holder:
        return 0
    lookup = battle_country_lookup()
    cover_card = battle_visual_card(BATTLE_BOMB_CARD, lookup, room, reveal_bomb=False)
    cover_name = cover_card.get('name') or battle_card_display_name(BATTLE_BOMB_CARD, lookup, room)
    bomb_card = battle_visual_card(BATTLE_BOMB_CARD, lookup, room, reveal_bomb=True)
    remove_all_battle_bomb_cards(room)
    room['bomb_holder'] = None
    room['bomb_until_turn'] = 0
    damage = battle_bomb_damage(room)
    dealt = battle_apply_damage_to_player_or_team(room, holder, damage)
    if dealt:
        result_parts.append(battle_bomb_explosion_log(holder, cover_name, dealt, reason))
        if isinstance(visual, dict):
            visual.setdefault('bombs', []).append({
                'player': holder,
                'cover_name': cover_name,
                'card': cover_card,
                'bomb_card': bomb_card,
                'damage': dealt,
                'reason': reason,
            })
    room['bomb_cover_key'] = None
    return dealt

def resolve_battle_bomb_detonations(room, entries, result_parts, visual=None):
    if not battle_bomb_active(room):
        return
    detonators = [
        player
        for player, entry in entries.items()
        if BATTLE_BOMB_CARD in entry.get('keys', [])
    ]
    for player in detonators:
        battle_explode_bomb(room, player, result_parts, visual, reason='played')

def apply_battle_special_card_damage(room, result_parts, visual):
    if not battle_room_events_enabled(room) or not battle_world_war_active(room):
        return
    hp = room.setdefault('hp', {})
    lookup = battle_country_lookup()
    for player in active_battle_players(room):
        hand = room.setdefault('hands', {}).setdefault(player, [])
        specials = [key for key in hand if is_battle_special_card(key) and not is_battle_playable_special_card(key)]
        for key in specials:
            if key in hand:
                hand.remove(key)
            hp_limit = battle_team_hp_limit(room) if room.get('mode') == TEAM_MODE else BATTLE_MAX_HP
            damage = battle_special_card_damage(key, hp_limit)
            heal = battle_special_card_heal(key, hp_limit)
            team = room.get('teams', {}).get(player)
            if room.get('mode') == TEAM_MODE:
                team_hp = ensure_battle_team_hp(room)
                if team:
                    team_hp[team] = max(0, min(hp_limit, team_hp.get(team, hp_limit) - damage + heal))
            else:
                hp[player] = max(0, min(hp_limit, hp.get(player, hp_limit) - damage + heal))
            card_name = battle_special_card_label(key)
            if damage:
                result_parts.append(t('battle_self_damage_log').format(player=player, card=card_name, damage=format_battle_number(damage)))
            if heal:
                result_parts.append(t('battle_heal_log').format(player=player, card=card_name, heal=format_battle_number(heal)))
            destroyed_card = None
            if BATTLE_SPECIAL_CARDS.get(key, {}).get('destroy_one'):
                destroyable = [item for item in hand if item in lookup]
                if destroyable:
                    destroyed_key = random.choice(destroyable)
                    hand.remove(destroyed_key)
                    destroyed_country = lookup.get(destroyed_key)
                    destroyed_card = battle_visual_card(destroyed_key, lookup, room)
                    destroyed_name = battle_card_display_name(destroyed_key, lookup, room) if destroyed_country else destroyed_key
                    result_parts.append(t('battle_destroy_log').format(player=player, card=card_name, country=destroyed_name))
            visual.setdefault('self_damage', []).append({
                'player': player,
                'key': key,
                'name': card_name,
                'damage': damage,
                'heal': heal,
                'destroyed_card': destroyed_card,
                'card': {**battle_visual_card(key, lookup, room), 'damage': damage, 'heal': heal},
            })

def finish_battle_turn(room, reload_set, defenseless_players):
    for player in defenseless_players:
        room.setdefault('hands', {})[player] = deal_battle_hand(room, battle_deal_count_for_player(room, player))
    for player in room.get('players', []):
        if room.setdefault('hp', {}).get(player, 0) <= 0:
            continue
        recover_battle_command_after_turn(
            room,
            player,
            room.setdefault('submitted', {}).get(player, {}),
            player in defenseless_players,
        )
        if not room.setdefault('hands', {}).setdefault(player, []):
            reload_set.add(player)
        else:
            reload_set.discard(player)
        if battle_supply_drop_active(room) and len(room.setdefault('hands', {}).setdefault(player, [])) <= BATTLE_SUPPLY_DROP_THRESHOLD:
            room['hands'][player].extend(draw_battle_cards(1, room))
    room['reload_after_turn'] = list(reload_set)
    room['submitted'] = {}
    room['turn'] = int(room.get('turn', 1)) + 1
    room['turn_started_at'] = current_timestamp()

def append_battle_log(room, text):
    if not text:
        return
    room.setdefault('log', []).insert(0, text)
    del room['log'][BATTLE_LOG_LIMIT:]

def active_battle_players(room):
    hp = room.setdefault('hp', {})
    if room.get('mode') == TEAM_MODE:
        teams = room.get('teams', {})
        team_hp = ensure_battle_team_hp(room)
        return [
            player for player in room.get('players', [])
            if hp.get(player, BATTLE_MAX_HP) > 0 and team_hp.get(teams.get(player), BATTLE_MAX_HP) > 0
        ]
    return [player for player in room.get('players', []) if hp.get(player, BATTLE_MAX_HP) > 0]

def battle_turn_elapsed_seconds(room):
    started_at = parse_timestamp_utc(room.get('turn_started_at'))
    return max(0, int((datetime.now(timezone.utc) - started_at).total_seconds()))

def battle_turn_time_left(room):
    timeout_seconds = battle_room_timeout_seconds(room)
    if timeout_seconds == BATTLE_TURN_TIMEOUT_UNLIMITED:
        return None
    return max(0, timeout_seconds - battle_turn_elapsed_seconds(room))

def battle_event_duration():
    return random.randint(BATTLE_RANDOM_EVENT_MIN_TURNS, BATTLE_RANDOM_EVENT_MAX_TURNS)

def battle_future_event_until_turn(turn):
    return int(turn or 1) + battle_event_duration()

def battle_find_bomb_holder(room):
    hands = room.setdefault('hands', {})
    holder = clean_username(room.get('bomb_holder'))
    if holder and BATTLE_BOMB_CARD in hands.get(holder, []):
        return holder
    for player, hand in hands.items():
        if BATTLE_BOMB_CARD in hand:
            room['bomb_holder'] = player
            return player
    room['bomb_holder'] = None
    return None

def remove_all_battle_bomb_cards(room):
    removed = 0
    for hand in room.setdefault('hands', {}).values():
        while BATTLE_BOMB_CARD in hand:
            hand.remove(BATTLE_BOMB_CARD)
            removed += 1
    return removed

def battle_apply_damage_to_player_or_team(room, player, damage):
    damage = max(0, int(damage or 0))
    if damage <= 0:
        return 0
    if room.get('mode') == TEAM_MODE:
        team = room.get('teams', {}).get(player)
        team_hp = ensure_battle_team_hp(room)
        if not team:
            return 0
        before = int(team_hp.get(team, battle_team_hp_limit(room, team)) or 0)
        team_hp[team] = max(0, before - damage)
        return before - team_hp[team]
    hp = room.setdefault('hp', {})
    before = int(hp.get(player, BATTLE_MAX_HP) or 0)
    hp[player] = max(0, before - damage)
    return before - hp[player]

def battle_apply_direct_damage(room, target, damage, source=None, breakdown=None, attack_keys=None):
    damage = max(0, int(damage or 0))
    hp = room.setdefault('hp', {})
    if damage <= 0:
        return 0, ''
    shield_message = ''
    if battle_satrapy_shields_remaining(room) > 0 and is_sengoku_boss_enemy_bot(room, target):
        shield_message = battle_apply_satrapy_shields(room, attack_keys or [], damage, breakdown)
        damage = battle_reduce_damage_by_satrapy_shields(room, damage, breakdown)
        hp_limit = battle_player_hp_limit(room, target)
        hp[target] = min(hp.get(target, hp_limit), hp_limit)
    before = hp.get(target, battle_player_hp_limit(room, target))
    hp[target] = max(0, before - damage)
    return before - hp[target], shield_message

def battle_apply_team_direct_damage(room, target_team, damage, source_team=None, attack_keys=None, breakdown=None):
    damage = max(0, int(damage or 0))
    team_hp = ensure_battle_team_hp(room)
    if damage <= 0 or not target_team:
        return 0, ''
    shield_message = ''
    if battle_satrapy_shields_remaining(room) > 0 and target_team == sengoku_boss_enemy_team(room):
        shield_message = battle_apply_satrapy_shields(room, attack_keys or [], damage, breakdown)
        damage = battle_reduce_damage_by_satrapy_shields(room, damage, breakdown)
        hp_limit = battle_team_hp_limit(room, target_team)
        team_hp[target_team] = min(team_hp.get(target_team, hp_limit), hp_limit)
    before = team_hp.get(target_team, battle_team_hp_limit(room, target_team))
    team_hp[target_team] = max(0, before - damage)
    return before - team_hp[target_team], shield_message

def battle_apply_team_self_damage(room, target_team, damage):
    damage = max(0, int(damage or 0))
    if damage <= 0 or not target_team:
        return 0
    team_hp = ensure_battle_team_hp(room)
    before = int(team_hp.get(target_team, battle_team_hp_limit(room, target_team)) or 0)
    team_hp[target_team] = max(0, before - damage)
    return before - team_hp[target_team]

def battle_apply_royal_road_supply(room, entries, result_parts, visual=None):
    interval = battle_royal_road_interval(room)
    heal_percent = battle_royal_road_heal_percent(room)
    if interval <= 0 or heal_percent <= 0:
        return
    turn = int(room.get('turn', 1) or 1)
    if turn % interval != 0:
        return
    if room.get('mode') == TEAM_MODE:
        enemy_team = sengoku_boss_enemy_team(room)
        team_hp = ensure_battle_team_hp(room)
        if team_hp.get(enemy_team, 0) <= 0:
            return
        human_keys = []
        enemy_keys = []
        for player, entry in entries.items():
            if room.get('teams', {}).get(player) == sengoku_boss_player_team(room):
                human_keys.extend(entry.get('keys', []))
            elif room.get('teams', {}).get(player) == enemy_team:
                enemy_keys.extend(entry.get('keys', []))
                enemy_keys.extend(entry.get('defense_keys', []))
        shared_labels = battle_shared_tag_region_labels(human_keys, enemy_keys)
        if shared_labels:
            result_parts.append(battle_boss_label({
                'ja': f"王の道の補給を遮断: {', '.join(shared_labels[:4])}",
                'en': f"Royal Road supplies blocked: {', '.join(shared_labels[:4])}",
                'zh': f"王道补给被切断: {', '.join(shared_labels[:4])}",
            }))
            if isinstance(visual, dict):
                visual.setdefault('boss_effects', []).append({'type': 'royal_road_blocked', 'labels': shared_labels[:4]})
            return
        hp_limit = battle_team_hp_limit(room, enemy_team)
        before = team_hp.get(enemy_team, hp_limit)
        heal = max(1, hp_limit * heal_percent // 100)
        team_hp[enemy_team] = min(hp_limit, before + heal)
        actual = team_hp[enemy_team] - before
        if actual > 0:
            result_parts.append(battle_boss_label({
                'ja': f'王の道の補給: 敵軍が {format_battle_number(actual)} 回復',
                'en': f'Royal Road supplies: enemy team recovered {format_battle_number(actual)}',
                'zh': f'王道补给: 敌方队伍恢复 {format_battle_number(actual)}',
            }))
            if isinstance(visual, dict):
                visual.setdefault('boss_effects', []).append({'type': 'royal_road_heal', 'target': enemy_team, 'heal': actual})
        return
    enemies = [player for player in room.get('players', []) if is_sengoku_boss_enemy_bot(room, player) and room.setdefault('hp', {}).get(player, 0) > 0]
    humans = [player for player in room.get('players', []) if not is_battle_bot(player) and room.setdefault('hp', {}).get(player, 0) > 0]
    if not enemies or not humans:
        return
    enemy = enemies[0]
    human = humans[0]
    human_keys = list((entries.get(human) or {}).get('keys', []))
    enemy_entry = entries.get(enemy) or {}
    enemy_keys = list(enemy_entry.get('keys', [])) + list(enemy_entry.get('defense_keys', []))
    shared_labels = battle_shared_tag_region_labels(human_keys, enemy_keys)
    if shared_labels:
        result_parts.append(battle_boss_label({
            'ja': f"王の道の補給を遮断: {', '.join(shared_labels[:4])}",
            'en': f"Royal Road supplies blocked: {', '.join(shared_labels[:4])}",
            'zh': f"王道补给被切断: {', '.join(shared_labels[:4])}",
        }))
        if isinstance(visual, dict):
            visual.setdefault('boss_effects', []).append({'type': 'royal_road_blocked', 'labels': shared_labels[:4]})
        return
    hp_limit = battle_player_hp_limit(room, enemy)
    before = room.setdefault('hp', {}).get(enemy, hp_limit)
    heal = max(1, hp_limit * heal_percent // 100)
    room['hp'][enemy] = min(hp_limit, before + heal)
    actual = room['hp'][enemy] - before
    if actual > 0:
        result_parts.append(battle_boss_label({
            'ja': f'王の道の補給: {enemy} が {format_battle_number(actual)} 回復',
            'en': f'Royal Road supplies: {enemy} recovered {format_battle_number(actual)}',
            'zh': f'王道补给: {enemy} 恢复 {format_battle_number(actual)}',
        }))
        if isinstance(visual, dict):
            visual.setdefault('boss_effects', []).append({'type': 'royal_road_heal', 'target': enemy, 'heal': actual})

def battle_expire_bomb_event(room, result_parts, visual=None):
    holder = battle_find_bomb_holder(room)
    if not holder:
        remove_all_battle_bomb_cards(room)
        room['bomb_holder'] = None
        room['bomb_cover_key'] = None
        return
    battle_explode_bomb(room, holder, result_parts, visual, reason='expired')

def battle_start_bomb_event(room, turn, result_parts, until_turn=None):
    players = active_battle_players(room)
    if not players:
        return
    remove_all_battle_bomb_cards(room)
    holder = random.choice(players)
    hand = room.setdefault('hands', {}).setdefault(holder, [])
    if BATTLE_BOMB_CARD not in hand:
        hand.append(BATTLE_BOMB_CARD)
    room['bomb_holder'] = holder
    room['bomb_cover_key'] = None
    battle_bomb_cover_key(room)
    room['bomb_until_turn'] = int(until_turn) if until_turn is not None else battle_future_event_until_turn(turn)
    result_parts.append(t('battle_bomb_start_log').format(player=holder))

def battle_apply_replace_event(room, result_parts):
    if not battle_replace_active(room):
        return
    hands = room.setdefault('hands', {})
    player_counts = []
    pooled_cards = []
    for player in active_battle_players(room):
        hand = list(hands.setdefault(player, []))
        player_counts.append((player, len(hand)))
        pooled_cards.extend(hand)
    if not pooled_cards:
        return
    random.shuffle(pooled_cards)
    cursor = 0
    for player, count in player_counts:
        hands[player] = pooled_cards[cursor:cursor + count]
        cursor += count
    battle_find_bomb_holder(room)
    result_parts.append(t('battle_replace_redistribute_log').format(
        count=len(pooled_cards),
        players=len(player_counts),
    ))

def update_battle_crisis_state(room, result_parts=None, visual=None):
    result_parts = result_parts if result_parts is not None else []
    turn = int(room.get('turn', 1) or 1)
    world_war_turn = battle_room_world_war_turn(room)
    if world_war_turn != BATTLE_WORLD_WAR_DISABLED and turn >= world_war_turn and not room.get('world_war_started'):
        room['world_war_started'] = True
        message = t('battle_world_war_log')
        result_parts.append(message)

    for field in [
        'revolution_until_turn',
        'flag_only_until_turn',
        'vatican_until_turn',
        'replace_until_turn',
        'lytton_until_turn',
        'damage_surge_until_turn',
        'random_target_until_turn',
        'ceasefire_until_turn',
        'command_surge_until_turn',
        'supply_drop_until_turn',
        'blockade_until_turn',
    ]:
        if int(room.get(field, 0) or 0) and turn > int(room.get(field, 0) or 0):
            room[field] = 0
    if int(room.get('bomb_until_turn', 0) or 0) and turn > int(room.get('bomb_until_turn', 0) or 0):
        room['bomb_until_turn'] = 0
        battle_expire_bomb_event(room, result_parts, visual)

    if not battle_room_events_enabled(room):
        return

    boss = sengoku_boss_for_room(room)
    try:
        bomb_every_turns = int((boss or {}).get('bomb_every_turns', 0) or 0)
    except (TypeError, ValueError):
        bomb_every_turns = 0
    if bomb_every_turns > 0 and (turn - 1) % bomb_every_turns == 0 and not battle_find_bomb_holder(room):
        battle_start_bomb_event(room, turn, result_parts, turn + bomb_every_turns - 1)

    if not battle_revolution_active(room):
        revolution_chance = BATTLE_WORLD_WAR_REVOLUTION_CHANCE if room.get('world_war_started') else BATTLE_REVOLUTION_CHANCE
        if random.random() < revolution_chance:
            duration = random.randint(BATTLE_REVOLUTION_MIN_TURNS, BATTLE_REVOLUTION_MAX_TURNS)
            room['revolution_until_turn'] = turn + duration - 1
            result_parts.append(t('battle_revolution_start_log'))
            return

    random_events = []
    if not battle_flag_only_active(room):
        random_events.append(('flag_only_until_turn', 'battle_flag_only_start_log', 1.0))
    if not battle_vatican_active(room) and battle_vatican_country_key():
        random_events.append(('vatican_until_turn', 'battle_vatican_start_log', 0.9))
    if not battle_replace_active(room):
        random_events.append(('replace_until_turn', 'battle_replace_start_log', 0.9))
    if not bomb_every_turns and not battle_bomb_active(room) and not battle_find_bomb_holder(room):
        random_events.append(('bomb_until_turn', 'battle_bomb_start_log', 0.65))
    if not battle_lytton_active(room):
        random_events.append(('lytton_until_turn', 'battle_lytton_start_log', BATTLE_LYTTON_EVENT_WEIGHT))
    if not battle_damage_surge_active(room):
        random_events.append(('damage_surge_until_turn', 'battle_damage_surge_start_log', 0.65))
    if room.get('mode') in [FFA_MODE, TEAM_MODE] and not is_sengoku_boss_room(room) and not battle_random_target_active(room):
        random_events.append(('random_target_until_turn', 'battle_random_target_start_log', 0.55))
    if not battle_ceasefire_active(room):
        random_events.append(('ceasefire_until_turn', 'battle_ceasefire_start_log', 0.75))
    if not battle_command_surge_active(room):
        random_events.append(('command_surge_until_turn', 'battle_command_surge_start_log', 0.7))
    if not battle_supply_drop_active(room):
        random_events.append(('supply_drop_until_turn', 'battle_supply_drop_start_log', 0.65))
    if not battle_blockade_active(room):
        random_events.append(('blockade_until_turn', 'battle_blockade_start_log', 0.55))
    if random_events and random.random() < BATTLE_RANDOM_EVENT_CHANCE:
        field, start_key, _ = random.choices(
            random_events,
            weights=[item[2] for item in random_events],
            k=1,
        )[0]
        if field == 'bomb_until_turn':
            battle_start_bomb_event(room, turn, result_parts)
        else:
            room[field] = battle_future_event_until_turn(turn)
            result_parts.append(t(start_key))

def set_battle_winner_if_finished(room):
    players = room.get('players', [])
    mode = room.get('mode', DUEL_MODE)
    count_wins = mode != BOT_MODE and not room.get('bot') and not any(is_battle_bot(player) for player in players)
    if mode == TEAM_MODE:
        teams = room.get('teams', {})
        team_hp = ensure_battle_team_hp(room)
        alive_teams = {
            teams.get(player)
            for player in players
            if teams.get(player) and room.setdefault('hp', {}).get(player, 0) > 0 and team_hp.get(teams.get(player), 0) > 0
        }
        if not alive_teams:
            room['winner'] = 'draw'
            return True
        if len(alive_teams) == 1:
            winning_team = next(iter(alive_teams))
            winners = [
                player for player in players
                if teams.get(player) == winning_team and room.setdefault('hp', {}).get(player, 0) > 0
            ]
            room['winner'] = f"team:{winning_team}"
            if is_sengoku_boss_room(room):
                for winner in winners:
                    award_sengoku_boss_clear_if_needed(winner, room)
            if count_wins:
                for winner in winners:
                    if not is_battle_bot(winner):
                        add_battle_win(winner)
            return True
        return False
    alive = [player for player in players if room.setdefault('hp', {}).get(player, 0) > 0]
    if not alive:
        room['winner'] = 'draw'
        return True
    if len(alive) == 1:
        room['winner'] = alive[0]
        award_sengoku_medal_if_needed(alive[0], room)
        if count_wins and not is_battle_bot(alive[0]):
            add_battle_win(alive[0])
        return True
    return False

def next_battle_bot_name(room):
    used = set(room.get('players', []))
    if BOT_USERNAME not in used:
        return BOT_USERNAME
    index = 2
    while f'{BOT_USERNAME}{index}' in used:
        index += 1
    return f'{BOT_USERNAME}{index}'

def replace_battle_player_with_bot(room, player, state_data=None, keep_submission=False):
    player = clean_username(player)
    if not player or is_battle_bot(player) or player not in room.get('players', []):
        return None
    bot_name = next_battle_bot_name(room)
    players = room.setdefault('players', [])
    players[players.index(player)] = bot_name
    room.setdefault('hp', {})[bot_name] = max(1, int(room.setdefault('hp', {}).pop(player, BATTLE_MAX_HP) or BATTLE_MAX_HP))
    room.setdefault('hands', {})[bot_name] = list(room.setdefault('hands', {}).pop(player, deal_battle_hand(room)))
    room.setdefault('command', {})[bot_name] = room.setdefault('command', {}).pop(player, BATTLE_MAX_COMMAND)
    if not room['hands'].get(bot_name):
        room['hands'][bot_name] = deal_battle_hand(room)
    if player in room.setdefault('reload_after_turn', []):
        room['reload_after_turn'] = [bot_name if name == player else name for name in room.get('reload_after_turn', [])]
    room.setdefault('redraw_turns', {})[bot_name] = room.setdefault('redraw_turns', {}).pop(player, 0)
    submitted_entry = room.setdefault('submitted', {}).pop(player, None)
    if keep_submission and submitted_entry is not None:
        room['submitted'][bot_name] = submitted_entry
    for submitted in room.setdefault('submitted', {}).values():
        if clean_username(submitted.get('target')) == player:
            submitted['target'] = bot_name
    if room.get('mode') == TEAM_MODE:
        teams = room.setdefault('teams', {})
        teams[bot_name] = teams.pop(player, 'A')
        ensure_battle_team_hp(room)
    room.setdefault('bot_owners', {})[bot_name] = player
    spectators = room.setdefault('spectators', [])
    if player not in spectators:
        spectators.append(player)
    if state_data is not None:
        state_data.setdefault('user_room', {}).pop(player, None)
        state_data.setdefault('spectator_room', {})[player] = room.get('id')
    append_battle_log(room, t('battle_bot_replacement_log').format(player=player, bot=bot_name))
    return bot_name

def apply_battle_surrender(room, player, state_data=None, timeout=False):
    player = clean_username(player)
    if not player or room.get('winner') or player not in room.get('players', []):
        return False
    if room.setdefault('hp', {}).get(player, BATTLE_MAX_HP) <= 0:
        return False
    surrender_key = 'battle_timeout_surrender_log' if timeout else 'battle_surrender_log'
    append_battle_log(room, t(surrender_key).format(player=player))
    if room.get('mode') in [DUEL_MODE, BOT_MODE]:
        room['hp'][player] = 0
        room.setdefault('submitted', {}).pop(player, None)
        set_battle_winner_if_finished(room)
        return True
    if replace_battle_player_with_bot(room, player, state_data):
        submit_bot_players(room)
        set_battle_winner_if_finished(room)
        return True
    room['hp'][player] = 0
    room.setdefault('submitted', {}).pop(player, None)
    set_battle_winner_if_finished(room)
    return True

def resolve_battle_turn(room):
    result_parts = []
    pre_turn_visual = {'bombs': []}
    update_battle_crisis_state(room, result_parts, pre_turn_visual)
    players = active_battle_players(room)
    if len(players) < 2:
        if result_parts:
            room.setdefault('log', []).insert(0, f"{t('battle_turn')} {room.get('turn', 1)}: {' / '.join(result_parts)}")
            del room['log'][BATTLE_LOG_LIMIT:]
            room['last_turn'] = trim_battle_last_turn({
                'turn': int(room.get('turn', 1) or 1),
                'world_war': battle_world_war_active(room),
                'revolution': battle_revolution_active(room),
                'flag_only': battle_flag_only_active(room),
                'vatican': battle_vatican_active(room),
                'replace': battle_replace_active(room),
                'bomb': bool(pre_turn_visual.get('bombs')) or battle_bomb_active(room),
                'lytton': battle_lytton_active(room),
                'damage_surge': battle_damage_surge_active(room),
                'random_target': battle_random_target_active(room),
                'ceasefire': battle_ceasefire_active(room),
                'command_surge': battle_command_surge_active(room),
                'supply_drop': battle_supply_drop_active(room),
                'blockade': battle_blockade_active(room),
                'played': [],
                'damage': [],
                'counters': [],
                'steals': [],
                'self_damage': [],
                'bombs': pre_turn_visual.get('bombs', []),
                'replacements': [],
            })
        set_battle_winner_if_finished(room)
        return
    entries = {player: battle_entry_for_player(room, player) for player in players}
    apply_random_target_event(room, entries, result_parts)
    reload_set, defenseless_players = remove_submitted_cards_and_reload(room)
    result_parts.insert(0, battle_played_cards_log(room, entries))
    visual = battle_visual_payload(room, entries)
    if pre_turn_visual.get('bombs'):
        visual.setdefault('bombs', []).extend(pre_turn_visual.get('bombs', []))
    winners = []
    losers = []
    mode = room.get('mode', DUEL_MODE)
    event_multiplier = battle_event_damage_multiplier(room)

    if mode == TEAM_MODE:
        teams = room.get('teams', {})
        team_hp = ensure_battle_team_hp(room)
        team_keys = {}
        team_power = {}
        team_defense = {}
        team_defense_base = {}
        team_defense_labels = {}
        team_players = {}
        for player, entry in entries.items():
            team = teams.get(player, 'A')
            team_players.setdefault(team, []).append(player)
            team_keys.setdefault(team, []).extend(entry['keys'])
            team_power[team] = team_power.get(team, 0) + entry['power']
            team_defense[team] = team_defense.get(team, 0) + entry.get('defense', 0)
            team_defense_base[team] = team_defense_base.get(team, 0) + entry.get('defense_base', 0)
            team_defense_labels.setdefault(team, []).extend(entry.get('defense_bonus_labels', []))
        alive_teams = [
            team for team in sorted(set(teams.get(player) for player in players if teams.get(player)))
            if team_hp.get(team, 0) > 0
        ]
        team_targets = {}
        for player, entry in entries.items():
            if entry.get('defenseless') or entry.get('power', 0) <= 0:
                continue
            source_team = teams.get(player)
            valid_target_teams = alive_teams if battle_random_target_active(room) else [team for team in alive_teams if team != source_team]
            target_team = str(entry.get('target') or '').strip()
            if target_team not in valid_target_teams:
                target_team = valid_target_teams[0] if valid_target_teams else None
            if not source_team or not target_team:
                continue
            team_targets.setdefault(source_team, {}).setdefault(target_team, []).append(player)
        for source_team, target_groups in team_targets.items():
            split_count = max(1, len(target_groups))
            for target_team, attack_players in target_groups.items():
                if team_hp.get(source_team, 0) <= 0 or team_hp.get(target_team, 0) <= 0:
                    continue
                attack_keys = []
                raw_power = 0
                for player in attack_players:
                    entry = entries.get(player, {})
                    attack_keys.extend(entry.get('keys', []))
                    raw_power += int(entry.get('power', 0) or 0)
                win_power = max(1, raw_power // split_count) if raw_power else 0
                lose_power = team_power.get(target_team, 0)
                multiplier, labels = battle_bonus_for_keys(attack_keys, room)
                defense_base = team_defense_base.get(target_team, 0)
                defense_multiplier = (team_defense.get(target_team, 0) / defense_base) if defense_base else 1
                target_players = [player for player in team_players.get(target_team, []) if room['hp'].get(player, 0) > 0]
                source_players = [player for player in team_players.get(source_team, []) if room['hp'].get(player, 0) > 0]
                breakdown = battle_damage_breakdown(
                    win_power,
                    lose_power,
                    team_defense.get(target_team, 0),
                    labels,
                    room.get('turn', 1),
                    battle_world_war_active(room),
                    battle_group_event_damage_multiplier(room, attack_players),
                    defense_base=defense_base,
                    defense_labels=sorted(set(team_defense_labels.get(target_team, []))),
                    defense_multiplier=defense_multiplier,
                    counter_event_multiplier=battle_group_event_damage_multiplier(room, target_players),
                    revolution=battle_revolution_active(room),
                )
                breakdown['raw_team_attack'] = raw_power
                breakdown['split_count'] = split_count
                breakdown['split_penalty_value'] = max(0, raw_power - win_power)
                damage, counter = breakdown['damage'], breakdown['counter']
                damage = battle_apply_enemy_extra_actions(room, damage, source_team=source_team, breakdown=breakdown)
                confused_players, missing_total = operation_confusion_group_triggered(room, entries, attack_players)
                if confused_players:
                    team_label = f"{t('battle_team')} {source_team}"
                    actor_label = f"{team_label} ({', '.join(confused_players)})"
                    dealt = battle_apply_team_self_damage(room, source_team, damage)
                    visual['damage'].append({
                        'source': actor_label,
                        'target': actor_label,
                        'damage': dealt,
                        'breakdown': breakdown,
                        'outcome': 'self_damage' if dealt else 'blocked',
                    })
                    visual.setdefault('self_damage', []).append({
                        'player': actor_label,
                        'name': t('battle_damage_surge_title'),
                        'damage': dealt,
                    })
                    result_parts.append(t('battle_operation_self_damage_log').format(
                        player=actor_label,
                        missing=missing_total,
                        damage=format_battle_number(dealt),
                    ))
                    continue
                if battle_random_target_active(room) and target_team == source_team:
                    breakdown = battle_damage_breakdown(
                        win_power,
                        0,
                        0,
                        labels,
                        room.get('turn', 1),
                        battle_world_war_active(room),
                        battle_group_event_damage_multiplier(room, attack_players),
                        defense_base=0,
                        defense_labels=[],
                        defense_multiplier=1,
                        counter_event_multiplier=1,
                        revolution=battle_revolution_active(room),
                    )
                    breakdown['raw_team_attack'] = raw_power
                    breakdown['split_count'] = split_count
                    breakdown['split_penalty_value'] = max(0, raw_power - win_power)
                    damage = battle_apply_enemy_extra_actions(room, breakdown['damage'], source_team=source_team, breakdown=breakdown)
                    damage = battle_apply_team_self_damage(room, source_team, damage)
                    team_label = f"{t('battle_team')} {source_team}"
                    visual['damage'].append({
                        'source': team_label,
                        'target': team_label,
                        'damage': damage,
                        'breakdown': breakdown,
                        'outcome': 'self_damage' if damage else 'blocked',
                    })
                    if damage > 0:
                        visual.setdefault('self_damage', []).append({
                            'player': team_label,
                            'name': t('battle_random_target_title'),
                            'damage': damage,
                        })
                    result_parts.append(t('battle_random_target_self_damage_log').format(
                        team=team_label,
                        damage=format_battle_number(damage),
                    ))
                    continue
                if damage:
                    damage, shield_message = battle_apply_team_direct_damage(room, target_team, damage, source_team, attack_keys, breakdown)
                    if shield_message:
                        result_parts.append(shield_message)
                    if damage > 0:
                        winners.extend(source_players)
                        losers.extend(target_players)
                visual['damage'].append({
                    'source': f"{t('battle_team')} {source_team}",
                    'target': f"{t('battle_team')} {target_team}",
                    'damage': damage,
                    'breakdown': breakdown,
                    'outcome': 'damage' if damage else 'blocked',
                })
                if counter:
                    counter, counter_shield_message = battle_apply_team_direct_damage(
                        room,
                        source_team,
                        counter,
                        target_team,
                        team_keys.get(target_team, []),
                        breakdown,
                    )
                    if counter_shield_message:
                        result_parts.append(counter_shield_message)
                    if counter > 0:
                        winners.extend(target_players)
                        losers.extend(source_players)
                    visual['counters'].append({
                        'source': f"{t('battle_team')} {target_team}",
                        'target': f"{t('battle_team')} {source_team}",
                        'damage': counter,
                        'breakdown': breakdown,
                    })
                    result_parts.append(t('battle_counter_log').format(
                        defender=f"{t('battle_team')} {target_team}",
                        attacker=f"{t('battle_team')} {source_team}",
                        damage=format_battle_number(counter),
                    ))
                defense_note = battle_group_defense_text(entries, target_players)
                split_note = f" / {t('battle_team_split_penalty')} x1/{split_count}" if split_count > 1 else ''
                result_parts.append(f"{t('battle_team')} {source_team} -> {t('battle_team')} {target_team}: {t('battle_team')} {target_team} -{format_battle_number(damage)}{defense_note}{battle_bonus_text(labels, multiplier)}{split_note}")
    elif mode == FFA_MODE:
        damage_events = []
        for attacker in players:
            entry = entries.get(attacker, {})
            if entry.get('defenseless'):
                continue
            target = clean_username(entry.get('target'))
            if target not in players or target == attacker or room['hp'].get(target, 0) <= 0:
                result_parts.append(f"{attacker}: {t('battle_select_target_required')}")
                continue
            if entry.get('power', 0) <= entries[target].get('power', 0):
                breakdown = battle_damage_breakdown(
                    entry.get('power', 0),
                    entries[target].get('power', 0),
                    entries[target].get('defense', 0),
                    [],
                    room.get('turn', 1),
                    battle_world_war_active(room),
                    battle_event_damage_multiplier(room, attacker),
                    defense_base=entries[target].get('defense_base', 0),
                    defense_labels=entries[target].get('defense_bonus_labels', []),
                    defense_multiplier=entries[target].get('defense_multiplier', 1),
                    counter_event_multiplier=battle_event_damage_multiplier(room, target),
                )
                visual['damage'].append({
                    'source': attacker,
                    'target': target,
                    'damage': 0,
                    'breakdown': breakdown,
                    'outcome': 'overpowered',
                })
                result_parts.append(f"{attacker} -> {target}: draw")
                continue
            multiplier, labels = battle_bonus_for_keys(entry.get('keys', []), room)
            breakdown = battle_damage_breakdown(
                entry.get('power', 0),
                entries[target].get('power', 0),
                entries[target].get('defense', 0),
                labels,
                room.get('turn', 1),
                battle_world_war_active(room),
                battle_event_damage_multiplier(room, attacker),
                defense_base=entries[target].get('defense_base', 0),
                defense_labels=entries[target].get('defense_bonus_labels', []),
                defense_multiplier=entries[target].get('defense_multiplier', 1),
                counter_event_multiplier=battle_event_damage_multiplier(room, target),
                revolution=battle_revolution_active(room),
            )
            damage, counter = breakdown['damage'], breakdown['counter']
            damage_events.append((attacker, target, damage, counter, labels, multiplier, breakdown))
        for attacker, target, damage, counter, labels, multiplier, breakdown in damage_events:
            damage = battle_apply_enemy_extra_actions(room, damage, source_player=attacker, breakdown=breakdown)
            confused, missing = operation_confusion_triggered(room, entries.get(attacker))
            if confused:
                dealt = record_operation_confusion_self_damage(
                    room,
                    attacker,
                    damage,
                    missing,
                    result_parts,
                    visual,
                    player=attacker,
                )
                visual['damage'].append({
                    'source': attacker,
                    'target': attacker,
                    'damage': dealt,
                    'breakdown': breakdown,
                    'outcome': 'self_damage' if dealt else 'blocked',
                })
                continue
            damage, shield_message = battle_apply_direct_damage(room, target, damage, attacker, breakdown, entries.get(attacker, {}).get('keys', []))
            if shield_message:
                result_parts.append(shield_message)
            if counter:
                counter, counter_shield_message = battle_apply_direct_damage(room, attacker, counter, target, breakdown, entries.get(target, {}).get('defense_keys', []))
                if counter_shield_message:
                    result_parts.append(counter_shield_message)
            if damage > 0:
                winners.append(attacker)
                losers.append(target)
            visual['damage'].append({
                'source': attacker,
                'target': target,
                'damage': damage,
                'breakdown': breakdown,
                'outcome': 'damage' if damage else 'blocked',
            })
            if counter > 0:
                winners.append(target)
                losers.append(attacker)
                visual['counters'].append({
                    'source': target,
                    'target': attacker,
                    'damage': counter,
                    'breakdown': breakdown,
                })
                result_parts.append(t('battle_counter_log').format(
                    defender=target,
                    attacker=attacker,
                    damage=format_battle_number(counter),
                ))
            result_parts.append(f"{attacker} -> {target}: {target} -{format_battle_number(damage)}{battle_defense_text(entries[target])}{battle_bonus_text(labels, multiplier)}")
    else:
        player_one, player_two = players[:2]
        power_one = entries[player_one]['power']
        power_two = entries[player_two]['power']
        if power_one > power_two:
            multiplier, labels = battle_bonus_for_keys(entries[player_one]['keys'], room)
            breakdown = battle_damage_breakdown(
                power_one,
                power_two,
                entries[player_two].get('defense', 0),
                labels,
                room.get('turn', 1),
                battle_world_war_active(room),
                battle_event_damage_multiplier(room, player_one),
                defense_base=entries[player_two].get('defense_base', 0),
                defense_labels=entries[player_two].get('defense_bonus_labels', []),
                defense_multiplier=entries[player_two].get('defense_multiplier', 1),
                counter_event_multiplier=battle_event_damage_multiplier(room, player_two),
                revolution=battle_revolution_active(room),
            )
            damage, counter = breakdown['damage'], breakdown['counter']
            damage = battle_apply_enemy_extra_actions(room, damage, source_player=player_one, breakdown=breakdown)
            confused, missing = operation_confusion_triggered(room, entries.get(player_one))
            if confused:
                dealt = record_operation_confusion_self_damage(
                    room,
                    player_one,
                    damage,
                    missing,
                    result_parts,
                    visual,
                    player=player_one,
                )
                visual['damage'].append({
                    'source': player_one,
                    'target': player_one,
                    'damage': dealt,
                    'breakdown': breakdown,
                    'outcome': 'self_damage' if dealt else 'blocked',
                })
            else:
                damage, shield_message = battle_apply_direct_damage(room, player_two, damage, player_one, breakdown, entries[player_one].get('keys', []))
                if shield_message:
                    result_parts.append(shield_message)
                if counter:
                    counter, counter_shield_message = battle_apply_direct_damage(room, player_one, counter, player_two, breakdown, entries[player_two].get('defense_keys', []))
                    if counter_shield_message:
                        result_parts.append(counter_shield_message)
                    if counter > 0:
                        winners = [player_two]
                        losers = [player_one]
                if damage > 0:
                    winners = [player_one]
                    losers = [player_two]
                visual['damage'].append({
                    'source': player_one,
                    'target': player_two,
                    'damage': damage,
                    'breakdown': breakdown,
                    'outcome': 'damage' if damage else 'blocked',
                })
                if counter > 0:
                    visual['counters'].append({
                        'source': player_two,
                        'target': player_one,
                        'damage': counter,
                        'breakdown': breakdown,
                    })
                    result_parts.append(t('battle_counter_log').format(
                        defender=player_two,
                        attacker=player_one,
                        damage=format_battle_number(counter),
                    ))
                result_parts.append(f"{player_one} vs {player_two}: {player_two} -{format_battle_number(damage)}{battle_defense_text(entries[player_two])}{battle_bonus_text(labels, multiplier)}")
        elif power_two > power_one:
            multiplier, labels = battle_bonus_for_keys(entries[player_two]['keys'], room)
            breakdown = battle_damage_breakdown(
                power_two,
                power_one,
                entries[player_one].get('defense', 0),
                labels,
                room.get('turn', 1),
                battle_world_war_active(room),
                battle_event_damage_multiplier(room, player_two),
                defense_base=entries[player_one].get('defense_base', 0),
                defense_labels=entries[player_one].get('defense_bonus_labels', []),
                defense_multiplier=entries[player_one].get('defense_multiplier', 1),
                counter_event_multiplier=battle_event_damage_multiplier(room, player_one),
                revolution=battle_revolution_active(room),
            )
            damage, counter = breakdown['damage'], breakdown['counter']
            damage = battle_apply_enemy_extra_actions(room, damage, source_player=player_two, breakdown=breakdown)
            confused, missing = operation_confusion_triggered(room, entries.get(player_two))
            if confused:
                dealt = record_operation_confusion_self_damage(
                    room,
                    player_two,
                    damage,
                    missing,
                    result_parts,
                    visual,
                    player=player_two,
                )
                visual['damage'].append({
                    'source': player_two,
                    'target': player_two,
                    'damage': dealt,
                    'breakdown': breakdown,
                    'outcome': 'self_damage' if dealt else 'blocked',
                })
            else:
                damage, shield_message = battle_apply_direct_damage(room, player_one, damage, player_two, breakdown, entries[player_two].get('keys', []))
                if shield_message:
                    result_parts.append(shield_message)
                if counter:
                    counter, counter_shield_message = battle_apply_direct_damage(room, player_two, counter, player_one, breakdown, entries[player_one].get('defense_keys', []))
                    if counter_shield_message:
                        result_parts.append(counter_shield_message)
                    if counter > 0:
                        winners = [player_one]
                        losers = [player_two]
                if damage > 0:
                    winners = [player_two]
                    losers = [player_one]
                visual['damage'].append({
                    'source': player_two,
                    'target': player_one,
                    'damage': damage,
                    'breakdown': breakdown,
                    'outcome': 'damage' if damage else 'blocked',
                })
                if counter > 0:
                    visual['counters'].append({
                        'source': player_one,
                        'target': player_two,
                        'damage': counter,
                        'breakdown': breakdown,
                    })
                    result_parts.append(t('battle_counter_log').format(
                        defender=player_one,
                        attacker=player_two,
                        damage=format_battle_number(counter),
                    ))
                result_parts.append(f"{player_one} vs {player_two}: {player_one} -{format_battle_number(damage)}{battle_defense_text(entries[player_one])}{battle_bonus_text(labels, multiplier)}")
        else:
            breakdown = battle_damage_breakdown(power_one, power_two, 0, [], room.get('turn', 1), battle_world_war_active(room), event_multiplier)
            visual['damage'].append({
                'source': player_one,
                'target': player_two,
                'damage': 0,
                'breakdown': breakdown,
                'outcome': 'draw',
            })
            result_parts.append(f"{player_one} vs {player_two}: draw")

    resolve_battle_bomb_detonations(room, entries, result_parts, visual)
    battle_apply_royal_road_supply(room, entries, result_parts, visual)
    steal_remaining_cards(room, list(dict.fromkeys(winners)), list(dict.fromkeys(losers)), defenseless_players, result_parts, visual, entries)
    apply_battle_special_card_damage(room, result_parts, visual)
    result_text = ' / '.join(result_parts) if result_parts else 'draw'
    room.setdefault('log', []).insert(0, f"{t('battle_turn')} {room.get('turn', 1)}: {result_text}")
    del room['log'][BATTLE_LOG_LIMIT:]
    room['last_turn'] = trim_battle_last_turn(visual)
    finish_battle_turn(room, reload_set, defenseless_players)
    post_turn_parts = []
    battle_apply_replace_event(room, post_turn_parts)
    if post_turn_parts:
        append_battle_log(room, f"{t('battle_turn')} {room.get('turn', 1)}: {' / '.join(post_turn_parts)}")
    set_battle_winner_if_finished(room)

def toggle_battle_card(key, checked):
    selected = set(state.battle_selected_keys or set())
    if checked:
        selected.add(key)
    else:
        selected.discard(key)
    state.battle_selected_keys = selected

def choose_bot_battle_cards(hand, room=None, player=None):
    playable = [key for key in hand if is_battle_selectable_card(key)]
    if not playable:
        return []
    command = battle_player_command(room, player) if room is not None and player else BATTLE_MAX_COMMAND
    max_playable = battle_max_playable_card_count(command, len(playable))
    required_count = ensure_battle_operation_required_count(room) if room is not None else None
    if required_count:
        max_playable = min(max_playable, required_count)
    if max_playable <= 0:
        return []
    human_players = [name for name in active_battle_players(room) if not is_battle_bot(name)] if room else []
    if room and room.get('sengoku_mode') and player and is_battle_bot(player) and len(human_players) <= 1:
        boss = sengoku_boss_for_room(room)
        if boss and not is_sengoku_boss_enemy_bot(room, player):
            max_cards = min(len(playable), random.randint(1, max_playable))
            return random.sample(playable, max_cards)
        try:
            if boss and boss.get('bot_card_limit'):
                max_playable = min(max_playable, max(1, int(boss.get('bot_card_limit') or max_playable)))
        except (TypeError, ValueError):
            pass
        if boss and is_sengoku_boss_enemy_bot(room, player) and battle_satrapy_shields_remaining(room) > 0:
            try:
                guard_limit = max(1, int(boss.get('satrapy_guard_card_limit', 1) or 1))
            except (TypeError, ValueError):
                guard_limit = 1
            max_playable = min(max_playable, guard_limit)
        playable = sorted(playable, key=lambda key: battle_card_power_for_key(key, room=room), reverse=True)
        if boss and boss.get('bot_strategy') == 'training':
            try:
                pool_size = max(max_playable, int(boss.get('bot_choice_pool', max_playable) or max_playable))
            except (TypeError, ValueError):
                pool_size = max_playable
            pool = playable[:max(1, min(len(playable), pool_size))]
            count = min(len(pool), random.randint(1, max_playable))
            return random.sample(pool, count)
        return playable[:max_playable]
    max_cards = min(len(playable), random.randint(1, max_playable))
    return random.sample(playable, max_cards)

def submit_bot_players(room):
    for player in room.get('players', []):
        if room.setdefault('hp', {}).get(player, 0) <= 0:
            continue
        if not is_battle_bot(player) or player in room.setdefault('submitted', {}):
            continue
        reload_set = set(room.get('reload_after_turn', []))
        apply_sengoku_boss_hand_modifiers(room, player)
        hand = room.setdefault('hands', {}).setdefault(player, [])
        playable_hand = [key for key in hand if is_battle_selectable_card(key)]
        defenseless = player in reload_set or not hand or not playable_hand or battle_player_command(room, player) < battle_command_cost_for_count(1)
        selected = [] if defenseless else choose_bot_battle_cards(hand, room, player)
        if not selected and not defenseless:
            defenseless = True
        selected_set = set(selected)
        defense_keys = [] if defenseless else [key for key in hand if key not in selected_set and is_battle_power_card(key)]
        command_cost = 0 if defenseless else battle_command_cost_for_count(len(selected))
        target = None
        if room.get('mode') == FFA_MODE and not defenseless:
            targets = [name for name in active_battle_players(room) if name != player]
            target = random.choice(targets) if targets else None
        elif room.get('mode') == TEAM_MODE and not defenseless:
            teams = room.get('teams', {})
            own_team = teams.get(player)
            targets = sorted({
                teams.get(name)
                for name in active_battle_players(room)
                if teams.get(name) and teams.get(name) != own_team
            })
            target = random.choice(targets) if targets else None
        room['submitted'][player] = {
            'keys': selected,
            'power': 0 if defenseless else battle_power_for_keys(selected, room),
            'defense_keys': defense_keys,
            'defense': 0 if defenseless else battle_defense_for_keys(defense_keys, room),
            'command_cost': command_cost,
            'defenseless': defenseless,
            'target': target,
        }

def battle_all_players_submitted(room):
    submitted = room.get('submitted', {})
    return all(player in submitted for player in active_battle_players(room))

def process_battle_timeouts(state_data):
    changed = False
    for room in state_data.setdefault('rooms', {}).values():
        if not isinstance(room, dict):
            continue
        normalize_battle_room(room)
        if room.get('winner'):
            continue
        if replace_disconnected_unlimited_battle_players(room, state_data):
            changed = True
        before_bot = json.dumps(room.get('submitted', {}), ensure_ascii=False, sort_keys=True)
        submit_bot_players(room)
        if json.dumps(room.get('submitted', {}), ensure_ascii=False, sort_keys=True) != before_bot:
            changed = True
        if battle_all_players_submitted(room):
            resolve_battle_turn(room)
            changed = True
            continue
        timeout_seconds = battle_room_timeout_seconds(room)
        if timeout_seconds == BATTLE_TURN_TIMEOUT_UNLIMITED:
            continue
        if battle_turn_elapsed_seconds(room) < timeout_seconds:
            continue
        timed_out_players = [
            player for player in active_battle_players(room)
            if player not in room.get('submitted', {}) and not is_battle_bot(player)
        ]
        for player in timed_out_players:
            changed = apply_battle_surrender(room, player, state_data, timeout=True) or changed
        if not room.get('winner') and battle_all_players_submitted(room):
            resolve_battle_turn(room)
            changed = True
    return changed

def load_battle_state_with_timeouts():
    state_data = load_battle_state()
    if process_battle_timeouts(state_data):
        save_battle_state(state_data)
    return state_data

def submit_battle_hand():
    username = state.current_user
    state_data = load_battle_state_with_timeouts()
    room = battle_room_for_user(username, state_data)
    if not room or room.get('winner') or not username or username not in room.get('players', []):
        refresh_battle_view()
        return
    if username in room.get('submitted', {}):
        ui.notify(t('battle_wait_opponent'), color='info')
        return
    reload_set = set(room.get('reload_after_turn', []))
    hand = room['hands'].setdefault(username, [])
    playable_hand = [key for key in hand if is_battle_selectable_card(key)]
    defenseless = username in reload_set or not hand or not playable_hand or battle_player_command(room, username) < battle_command_cost_for_count(1)
    selected = [] if defenseless else [key for key in hand if key in state.battle_selected_keys and is_battle_selectable_card(key)]
    if not defenseless and not selected:
        vatican_key = battle_vatican_country_key()
        if vatican_key and playable_hand and set(playable_hand) == {vatican_key}:
            selected = [vatican_key]
        else:
            ui.notify(t('battle_select_card_required'), color='warning')
            return
    required_count = ensure_battle_operation_required_count(room)
    if required_count and not defenseless and len(selected) > required_count:
        ui.notify(t('battle_operation_too_many').format(count=required_count), color='warning')
        return
    command_cost = 0 if defenseless else battle_command_cost_for_count(len(selected))
    if command_cost > battle_player_command(room, username):
        ui.notify(t('battle_command_not_enough'), color='warning')
        return
    target = None
    if battle_random_target_active(room) and room.get('mode') in [FFA_MODE, TEAM_MODE]:
        target = None
    elif room.get('mode') == FFA_MODE and not defenseless:
        active_targets = [player for player in active_battle_players(room) if player != username]
        target = clean_username(state.battle_attack_target)
        if target not in active_targets:
            ui.notify(t('battle_select_target_required'), color='warning')
            return
    elif room.get('mode') == TEAM_MODE and not defenseless:
        teams = room.get('teams', {})
        own_team = teams.get(username)
        active_targets = sorted({
            teams.get(player)
            for player in active_battle_players(room)
            if teams.get(player) and teams.get(player) != own_team
        })
        target = str(state.battle_attack_target or '').strip()
        if target not in active_targets:
            ui.notify(t('battle_select_target_required'), color='warning')
            return
    selected_set = set(selected)
    defense_keys = [] if defenseless else [key for key in hand if key not in selected_set and is_battle_power_card(key)]
    room['submitted'][username] = {
        'keys': selected,
        'power': 0 if defenseless else battle_power_for_keys(selected, room),
        'defense_keys': defense_keys,
        'defense': 0 if defenseless else battle_defense_for_keys(defense_keys, room),
        'command_cost': command_cost,
        'defenseless': defenseless,
        'target': target,
    }
    submit_bot_players(room)
    state.battle_selected_keys = set()
    state.battle_attack_target = None
    if battle_all_players_submitted(room):
        resolve_battle_turn(room)
    save_battle_state(state_data)
    refresh_battle_view()

def surrender_battle():
    username = state.current_user
    state_data = load_battle_state()
    room = battle_room_for_user(username, state_data)
    if not room or room.get('winner') or not username or username not in room.get('players', []):
        refresh_battle_view()
        return
    if apply_battle_surrender(room, username, state_data):
        state.battle_selected_keys = set()
        state.battle_attack_target = None
        if not room.get('winner') and battle_all_players_submitted(room):
            resolve_battle_turn(room)
        save_battle_state(state_data)
    refresh_battle_view()

def kick_battle_player(target_username):
    host = clean_username(state.current_user)
    target = clean_username(target_username)
    state_data = load_battle_state()
    room = battle_room_for_user(host, state_data)
    if not room or room.get('winner') or room.get('host') != host or not target or target == host:
        refresh_battle_view()
        return
    room.setdefault('kicked', [])
    if target not in room['kicked']:
        room['kicked'].append(target)
    if target in room.get('players', []):
        bot_name = replace_battle_player_with_bot(room, target, state_data)
        if bot_name:
            room['spectators'] = [name for name in room.get('spectators', []) if name != target]
            state_data.setdefault('spectator_room', {}).pop(target, None)
            state_data.setdefault('user_room', {}).pop(target, None)
            append_battle_log(room, t('battle_kicked_log').format(player=target))
            submit_bot_players(room)
            if battle_all_players_submitted(room):
                resolve_battle_turn(room)
    else:
        room['spectators'] = [name for name in room.get('spectators', []) if name != target]
        state_data.setdefault('spectator_room', {}).pop(target, None)
        append_battle_log(room, t('battle_kicked_log').format(player=target))
    save_battle_state(state_data)
    refresh_battle_view()

def redraw_battle_hand():
    username = state.current_user
    state_data = load_battle_state_with_timeouts()
    room = battle_room_for_user(username, state_data)
    if not room or room.get('winner') or not username or username not in room.get('players', []):
        refresh_battle_view()
        return
    if username in room.get('submitted', {}):
        ui.notify(t('battle_wait_opponent'), color='info')
        return
    if battle_blockade_active(room):
        ui.notify(t('battle_blockade_redraw_blocked'), color='warning')
        return
    if username in set(room.get('reload_after_turn', [])):
        ui.notify(t('battle_defenseless'), color='warning')
        return
    turn = int(room.get('turn', 1))
    redraw_turns = room.setdefault('redraw_turns', {})
    if int(redraw_turns.get(username, 0) or 0) == turn:
        ui.notify(t('battle_redraw_used'), color='warning')
        return
    current_command = battle_player_command(room, username)
    if current_command < BATTLE_REDRAW_COMMAND_COST + battle_command_cost_for_count(1):
        ui.notify(t('battle_redraw_command_not_enough'), color='warning')
        return
    hand = room.setdefault('hands', {}).setdefault(username, [])
    count = len(hand)
    if count <= 0:
        ui.notify(t('battle_defenseless'), color='warning')
        return
    room['hands'][username] = draw_battle_cards(count, room)
    set_battle_player_command(room, username, current_command - BATTLE_REDRAW_COMMAND_COST)
    redraw_turns[username] = turn
    state.battle_selected_keys = set()
    state.battle_attack_target = None
    save_battle_state(state_data)
    refresh_battle_view()

def active_battle_rooms():
    state_data = load_battle_state_with_timeouts()
    rooms = []
    for room in state_data.get('rooms', {}).values():
        if not isinstance(room, dict) or room.get('winner') or is_sengoku_boss_room(room):
            continue
        players = room.get('players', [])
        if players:
            rooms.append(room)
    return sorted(rooms, key=lambda room: str(room.get('id', '')))

def spectate_battle_room(room_id):
    username = state.current_user
    if not username:
        ui.notify(t('login_required'), color='warning')
        return
    state_data = load_battle_state()
    room = state_data.get('rooms', {}).get(str(room_id))
    if not room or room.get('winner') or is_sengoku_boss_room(room):
        refresh_battle_view()
        return
    if username in room.get('kicked', []):
        ui.notify(t('battle_kicked_notice'), color='warning')
        refresh_battle_view()
        return
    if username in room.get('players', []):
        state.battle_id = room.get('id')
        refresh_battle_view()
        return
    spectators = room.setdefault('spectators', [])
    if username not in spectators:
        spectators.append(username)
    state_data.setdefault('spectator_room', {})[username] = room.get('id')
    state.battle_id = room.get('id')
    save_battle_state(state_data)
    refresh_battle_view()

def leave_battle_spectate():
    username = state.current_user
    state_data = load_battle_state()
    room_id = state_data.setdefault('spectator_room', {}).pop(username, None)
    room = state_data.setdefault('rooms', {}).get(room_id)
    if room:
        room['spectators'] = [name for name in room.get('spectators', []) if name != username]
    prune_empty_battle_rooms(state_data)
    save_battle_state(state_data)
    state.battle_id = None
    refresh_battle_view()

def send_battle_chat(message):
    username = state.current_user
    text = str(message or '').strip()
    if not username or not text:
        return
    state_data = load_battle_state()
    room = battle_room_for_user(username, state_data)
    if not room:
        refresh_battle_view()
        return
    if is_sengoku_boss_room(room):
        refresh_battle_view()
        return
    room.setdefault('chat', []).insert(0, {
        'user': username,
        'text': text[:160],
        'timestamp': current_timestamp(),
    })
    del room['chat'][BATTLE_CHAT_LIMIT:]
    save_battle_state(state_data)
    refresh_battle_view()

def send_battle_team_chat(message):
    username = state.current_user
    text = str(message or '').strip()
    if not username or not text:
        return
    state_data = load_battle_state()
    room = battle_room_for_user(username, state_data)
    if not room or room.get('mode') != TEAM_MODE or username not in room.get('players', []):
        refresh_battle_view()
        return
    if is_sengoku_boss_room(room):
        refresh_battle_view()
        return
    team = room.get('teams', {}).get(username)
    if not team:
        refresh_battle_view()
        return
    room.setdefault('team_chat', []).insert(0, {
        'team': team,
        'user': username,
        'text': text[:160],
        'timestamp': current_timestamp(),
    })
    del room['team_chat'][BATTLE_CHAT_LIMIT:]
    save_battle_state(state_data)
    refresh_battle_view()

def battle_last_turn_signature(last_turn):
    if not isinstance(last_turn, dict):
        return {}
    def rows_signature(rows):
        compact = []
        for row in rows[:8] if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            compact.append({
                'source': row.get('source') or row.get('winner') or row.get('player'),
                'target': row.get('target') or row.get('loser'),
                'name': row.get('name') or row.get('cover_name') or ((row.get('card') or {}).get('name') if isinstance(row.get('card'), dict) else None),
                'damage': row.get('damage'),
                'heal': row.get('heal'),
                'outcome': row.get('outcome'),
            })
        return compact
    return {
        'turn': last_turn.get('turn'),
        'events': {
            key: bool(last_turn.get(key))
            for key in ['world_war', 'revolution', 'flag_only', 'vatican', 'replace', 'bomb', 'lytton', 'damage_surge', 'random_target', 'ceasefire', 'command_surge', 'supply_drop', 'blockade']
        },
        'played_count': len(last_turn.get('played', [])) if isinstance(last_turn.get('played'), list) else 0,
        'damage': rows_signature(last_turn.get('damage', [])),
        'counters': rows_signature(last_turn.get('counters', [])),
        'steals': rows_signature(last_turn.get('steals', [])),
        'self_damage': rows_signature(last_turn.get('self_damage', [])),
        'bombs': rows_signature(last_turn.get('bombs', [])),
    }

def battle_screen_signature(state_data=None):
    state_data = state_data or load_battle_state_with_timeouts()
    room = battle_room_for_user(state.current_user, state_data)
    if room:
        payload = {
            'room': room.get('id'),
            'sengoku_boss_id': room.get('sengoku_boss_id'),
            'turn': room.get('turn'),
            'turn_timeout_seconds': battle_room_timeout_seconds(room),
            'world_war_turn': battle_room_world_war_turn(room),
            'winner': room.get('winner'),
            'hp': room.get('hp', {}),
            'team_hp': room.get('team_hp', {}),
            'teams': room.get('teams', {}),
            'player_count': room.get('player_count'),
            'team_count': room.get('team_count'),
            'satrapy_shields_broken': room.get('satrapy_shields_broken', 0),
            'satrapy_shield_damage': room.get('satrapy_shield_damage', {}),
            'satrapy_broken_provinces': room.get('satrapy_broken_provinces', []),
            'hands_count': {
                player: len(room.setdefault('hands', {}).get(player, []))
                for player in room.get('players', [])
            },
            'command': room.get('command', {}),
            'submitted': sorted(room.get('submitted', {}).keys()),
            'reload': sorted(room.get('reload_after_turn', [])),
            'log_head': room.get('log', [])[:1],
            'chat_head': room.get('chat', [])[:1],
            'team_chat_head': room.get('team_chat', [])[:1],
            'spectators': sorted(room.get('spectators', [])),
            'bot_owners': room.get('bot_owners', {}),
            'world_war_started': room.get('world_war_started'),
            'revolution_until_turn': room.get('revolution_until_turn'),
            'flag_only_until_turn': room.get('flag_only_until_turn'),
            'vatican_until_turn': room.get('vatican_until_turn'),
            'replace_until_turn': room.get('replace_until_turn'),
            'bomb_until_turn': room.get('bomb_until_turn'),
            'lytton_until_turn': room.get('lytton_until_turn'),
            'damage_surge_until_turn': room.get('damage_surge_until_turn'),
            'random_target_until_turn': room.get('random_target_until_turn'),
            'operation_required_turn': room.get('operation_required_turn'),
            'operation_required_count': room.get('operation_required_count'),
            'ceasefire_until_turn': room.get('ceasefire_until_turn'),
            'command_surge_until_turn': room.get('command_surge_until_turn'),
            'supply_drop_until_turn': room.get('supply_drop_until_turn'),
            'blockade_until_turn': room.get('blockade_until_turn'),
            'bomb_holder': room.get('bomb_holder'),
            'bomb_cover_key': room.get('bomb_cover_key'),
            'last_turn': battle_last_turn_signature(room.get('last_turn', {})),
        }
    else:
        payload = {
            'queue': state_data.get('queue', []),
            'rooms': [
                {
                    'id': room.get('id'),
                    'sengoku_boss_id': room.get('sengoku_boss_id'),
                    'mode': room.get('mode'),
                    'turn_timeout_seconds': battle_room_timeout_seconds(room),
                    'world_war_turn': battle_room_world_war_turn(room),
                    'player_count': room.get('player_count'),
                    'team_count': room.get('team_count'),
                    'players': room.get('players', []),
                    'teams': room.get('teams', {}),
                    'turn': room.get('turn'),
                    'winner': room.get('winner'),
                }
                for room in state_data.get('rooms', {}).values()
                if isinstance(room, dict) and not room.get('winner') and not is_sengoku_boss_room(room)
            ],
        }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)

# ========================================
# 画面切り替え
# ========================================
@app.get('/api/data')
def get_data():
    global DATA_CACHE, DATA_CACHE_MTIME
    mtime = file_mtime(JSON_FILE)
    if DATA_CACHE is not None and DATA_CACHE_MTIME == mtime:
        return DATA_CACHE
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        DATA_CACHE = json.load(f)
    DATA_CACHE_MTIME = mtime
    clear_data_derived_caches()
    return DATA_CACHE

@app.post('/api/restore-user-backups')
async def restore_user_backups(payload: dict):
    restored = restore_user_backup_payload(payload)
    if restored:
        print(f'Restored {restored} browser user backup(s) to {USER_DATA_FILE}', flush=True)
    return {'ok': True, 'restored': restored}

@app.post('/api/avatar-adjust')
async def save_avatar_adjustment(payload: dict):
    ok = save_avatar_adjustment_values(payload)
    return {'ok': ok}

@app.post('/api/avatar-upload')
async def upload_avatar_from_browser(payload: dict):
    try:
        raw_content = payload.get('content', '')
        if isinstance(raw_content, str) and raw_content.startswith('data:'):
            raw_content = raw_content.split(',', 1)[1]
        content = base64.b64decode(raw_content)
        save_avatar_image_content(payload.get('name', ''), content, payload.get('username'))
        return {'ok': True}
    except Exception as e:
        print(f'Avatar browser upload failed: {e}', flush=True)
        return {'ok': False, 'error': str(e)}

def save_data(data):
    global DATA_CACHE, DATA_CACHE_MTIME
    data = dict(data)
    for key in ['users', 'history', 'favorites']:
        data.pop(key, None)
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    DATA_CACHE = data
    DATA_CACHE_MTIME = file_mtime(JSON_FILE)
    clear_data_derived_caches()

def add_history(country_data):
    if is_hidden_country(country_data):
        return
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if not user:
        return
    key = country_key(country_data)
    name = get_localized_text(country_data['names'])
    new_record = {
        "key": key,
        "name": name,
        "flag_code": country_data.get('flag_code'),
        "lang": state.lang,
        "timestamp": current_timestamp()
    }
    viewed = user.setdefault('viewed_keys', [])
    if key not in viewed:
        viewed.append(key)
    public_keys = set(all_public_country_keys())
    if public_keys and public_keys.issubset(set(viewed)):
        user['all_viewed_granted'] = True
    history = user.setdefault('history', [])
    history.insert(0, new_record)
    del history[50:]
    unlocked_now = mark_battle_unlock_if_ready(user)
    sengoku_unlocked_now = mark_sengoku_unlock_if_ready(user)
    persist_current_user_data(user_data)
    if unlocked_now:
        ui.notify(t('battle_unlocked_notice'), color='positive')
    if sengoku_unlocked_now:
        ui.notify(t('sengoku_unlocked_notice'), color='positive')

def clear_history():
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if user:
        user['history'] = []
        persist_current_user_data(user_data)

# ========================================
# 画面切り替え
# ========================================
SCREEN_HASHES = {
    'login': 'login',
    'top': 'home',
    'main': 'search',
    'result': 'detail',
    'quiz': 'quiz',
    'compare': 'compare',
    'timeline': 'timeline',
    'map': 'map',
    'network': 'network',
    'account': 'account',
    'users': 'users',
    'public_collection': 'collection',
    'battle': 'battle',
    'rankings': 'rankings',
    'social': 'friends',
    'help': 'help',
    'help_detail': 'help-detail',
}

HASH_SCREENS = {
    **{hash_value: screen for screen, hash_value in SCREEN_HASHES.items()},
    '': 'top',
    'signin': 'login',
    'sign-in': 'login',
    'top': 'top',
    'home': 'top',
    'main': 'main',
    'countries': 'main',
    'country': 'result',
    'detail': 'result',
    'chat': 'social',
    'social': 'social',
    'guide': 'help',
    'help_detail': 'help_detail',
}

def hash_for_screen(screen_name):
    return SCREEN_HASHES.get(screen_name, 'home')

def screen_from_hash(hash_value):
    normalized = str(hash_value or '').strip().lstrip('#').split('?', 1)[0].split('&', 1)[0].casefold()
    return HASH_SCREENS.get(normalized, 'top')

def update_browser_hash(screen_name):
    return

def request_hash_route_from_browser(force=False):
    return

def request_login_redirect_from_browser():
    return

def consume_pending_hash_screen():
    return

@app.post('/api/hash-route')
async def route_from_hash(payload: dict):
    return {'ok': False, 'disabled': True}

def show_screen(screen_name, update_hash=True, notify=True):
    protected_screens = ['main', 'result', 'quiz', 'compare', 'timeline', 'map', 'network', 'account', 'users', 'public_collection', 'battle', 'rankings', 'social']
    if screen_name in protected_screens and not state.current_user:
        if notify:
            ui.notify(t('login_required'), color='warning')
        screen_name = 'top'
    if screen_name == 'result' and not state.selected_country:
        screen_name = 'main' if state.current_user else 'top'
    if screen_name == 'public_collection' and not state.public_collection_keys:
        screen_name = 'users' if state.current_user else 'top'

    if screen_name == 'top':
        state.search_keyword = ''
        state.filter_region = None
        state.filter_tag_group = None
        state.filter_tag = None
        state.sort_field = 'name'
        state.sort_order = 'asc'
        state.show_favorites_only = False
        state.favorite_filter = 'all'
        state.collection_filter = None
        state.page = 1
        if history_drawer.value:
            history_drawer.hide()
        if notification_drawer.value:
            notification_drawer.hide()
        refresh_top_ui()

    top_screen.set_visibility(screen_name == 'top')
    main_screen.set_visibility(screen_name == 'main')
    result_screen.set_visibility(screen_name == 'result')
    quiz_screen.set_visibility(screen_name == 'quiz')
    compare_screen.set_visibility(screen_name == 'compare')
    timeline_screen.set_visibility(screen_name == 'timeline')
    map_screen.set_visibility(screen_name == 'map')
    network_screen.set_visibility(screen_name == 'network')
    account_screen.set_visibility(screen_name == 'account')
    users_screen.set_visibility(screen_name == 'users')
    public_collection_screen.set_visibility(screen_name == 'public_collection')
    battle_screen.set_visibility(screen_name == 'battle')
    rankings_screen.set_visibility(screen_name == 'rankings')
    social_screen.set_visibility(screen_name == 'social')
    help_screen.set_visibility(screen_name == 'help')
    help_detail_screen.set_visibility(screen_name == 'help_detail')
    if screen_name == 'main':
        refresh_main_ui()
    if screen_name == 'result':
        refresh_result_view()
    if screen_name == 'quiz':
        refresh_quiz_view()
    if screen_name == 'compare':
        refresh_compare_view()
    if screen_name == 'timeline':
        refresh_timeline_view()
    if screen_name == 'map':
        refresh_map_view()
    if screen_name == 'network':
        refresh_network_view()
    if screen_name == 'account':
        refresh_account_view()
    if screen_name == 'users':
        refresh_users_view()
    if screen_name == 'public_collection':
        refresh_public_collection_view()
    if screen_name == 'battle':
        refresh_battle_view()
    if screen_name == 'rankings':
        refresh_rankings_view()
    if screen_name == 'social':
        refresh_social_view()
    if screen_name == 'help':
        refresh_help_view()
    if screen_name == 'help_detail':
        refresh_help_detail_view()
    state.current_screen = screen_name

def switch_language(lang_code):
    state.lang = lang_code
    if top_screen.visible: refresh_top_ui()
    if main_screen.visible: refresh_main_ui()
    if result_screen.visible: refresh_result_view()
    if quiz_screen.visible: refresh_quiz_view()
    if compare_screen.visible: refresh_compare_view()
    if timeline_screen.visible: refresh_timeline_view()
    if map_screen.visible: refresh_map_view()
    if network_screen.visible: refresh_network_view()
    if account_screen.visible: refresh_account_view()
    if users_screen.visible: refresh_users_view()
    if public_collection_screen.visible: refresh_public_collection_view()
    if battle_screen.visible: refresh_battle_view()
    if rankings_screen.visible: refresh_rankings_view()
    if social_screen.visible: refresh_social_view()
    if notification_drawer.value: refresh_notification_content()
    if help_screen.visible: refresh_help_view()
    if help_detail_screen.visible: refresh_help_detail_view()

def is_mobile_ui():
    return state.ui_mode == 'mobile'

def update_mode_classes(element, pc_classes, mobile_classes):
    element.classes(
        remove=f'{pc_classes} {mobile_classes}',
        add=mobile_classes if is_mobile_ui() else pc_classes,
    )

def refresh_current_screen():
    if top_screen.visible:
        refresh_top_ui()
    if main_screen.visible:
        refresh_main_ui()
    if result_screen.visible:
        refresh_result_view()
    if quiz_screen.visible:
        refresh_quiz_view()
    if compare_screen.visible:
        refresh_compare_view()
    if timeline_screen.visible:
        refresh_timeline_view()
    if map_screen.visible:
        refresh_map_view()
    if network_screen.visible:
        refresh_network_view()
    if account_screen.visible:
        refresh_account_view()
    if users_screen.visible:
        refresh_users_view()
    if public_collection_screen.visible:
        refresh_public_collection_view()
    if battle_screen.visible:
        refresh_battle_view()
    if rankings_screen.visible:
        refresh_rankings_view()
    if social_screen.visible:
        refresh_social_view()
    if help_screen.visible:
        refresh_help_view()
    if help_detail_screen.visible:
        refresh_help_detail_view()

def toggle_ui_mode():
    state.ui_mode = 'pc' if is_mobile_ui() else 'mobile'
    refresh_current_screen()

def apply_theme():
    is_dark = state.theme_mode == 'dark'
    script = f"""
    (() => {{
      document.documentElement.classList.toggle('wa-dark', {json.dumps(is_dark)});
      localStorage.setItem('world_archives_theme', {json.dumps(state.theme_mode)});
    }})();
    """
    try:
        ui.run_javascript(script)
    except Exception as e:
        print(f"Theme update skipped: {e}", flush=True)

def toggle_theme():
    state.theme_mode = 'light' if state.theme_mode == 'dark' else 'dark'
    apply_theme()
    refresh_current_screen()

def ui_mode_tooltip():
    return t('switch_to_pc') if is_mobile_ui() else t('switch_to_mobile')

def ui_mode_icon():
    return 'desktop_windows' if is_mobile_ui() else 'smartphone'

# ========================================
# 1. トップ画面
# ========================================
with ui.right_drawer(value=False).classes('wa-dark-area bg-gray-100') as history_drawer:
    history_content = ui.column().classes('w-full p-4')

with ui.right_drawer(value=False).classes('wa-dark-area bg-gray-100') as notification_drawer:
    notification_content = ui.column().classes('w-full p-4')

def jump_from_history(history_item):
    data = get_data()
    hist_key = history_item.get('key')
    if hist_key:
        target_country = countries_by_key(data).get(hist_key)
        if target_country:
            history_drawer.hide()
            open_country_detail(target_country, return_screen='main')
            return
    code = history_item.get('flag_code')
    hist_name = history_item.get('name')
    if not code: return

    candidates = [c for c in data['countries'] if c.get('flag_code') == code]
    target_country = None
    for c in candidates:
        if hist_name in c['names'].values():
            target_country = c
            break
    if not target_country and candidates:
        target_country = candidates[0]

    if target_country:
        history_drawer.hide()
        open_country_detail(target_country, return_screen='main')

def refresh_history_content():
    history_content.clear()
    user = get_current_user_record()
    histories = user.get('history', []) if user else []
    with history_content:
        with ui.row().classes('w-full justify-between items-center mb-4'):
            icon_label(t('history'), 'history', 'text-xl font-bold text-gray-700', 'text-blue-500')
            ui.button(icon='close', on_click=lambda: history_drawer.toggle()).props('flat round dense')
        if not histories:
            ui.label(t('history_empty')).classes('text-gray-400')
        with ui.column().classes('w-full gap-2'):
            for h in histories:
                with ui.card().classes('wa-light-fallback w-full p-3 bg-white text-sm border-l-4 border-blue-500 cursor-pointer hover:bg-blue-50 transition') as card:
                    card.on('click', lambda _, item=h: jump_from_history(item))
                    ui.label(h['name']).classes('font-bold text-gray-800')
                    ui.label(format_timestamp(h.get('timestamp'))).classes('text-xs text-gray-400 mt-1')

def open_history_box():
    refresh_history_content()
    if notification_drawer.value:
        notification_drawer.hide()
    history_drawer.toggle()

def open_notifications_box():
    refresh_notification_content()
    if history_drawer.value:
        history_drawer.hide()
    notification_drawer.toggle()

def mark_all_notifications_read():
    mark_notification_read(mark_all=True)
    refresh_notification_content()
    refresh_current_screen()

def refresh_notification_content():
    notification_content.clear()
    user = get_current_user_record()
    notifications = current_notifications(user) if user else []
    unread_count = unread_notification_count(user)
    with notification_content:
        with ui.row().classes('w-full justify-between items-center mb-4'):
            icon_label(t('notifications'), 'notifications', 'text-xl font-bold text-gray-700', 'text-blue-500')
            ui.button(icon='close', on_click=lambda: notification_drawer.toggle()).props('flat round dense')
        if notifications:
            with ui.row().classes('w-full justify-between items-center mb-2'):
                icon_label(t('unread_notifications').format(count=unread_count), 'mark_email_unread', 'text-sm font-bold text-gray-500', 'text-orange-500')
                ui.button(t('mark_all_read'), icon='done_all', on_click=mark_all_notifications_read).props('flat dense color=primary')
        else:
            ui.label(t('notification_empty')).classes('text-gray-400')
        with ui.column().classes('w-full gap-2'):
            for item in notifications:
                border = 'border-orange-500' if not item.get('read') else 'border-gray-300'
                bg = 'bg-orange-50' if not item.get('read') else 'bg-white'
                with ui.card().classes(f'wa-light-fallback w-full p-3 text-sm border-l-4 {border} {bg} cursor-pointer hover:bg-blue-50 transition') as card:
                    card.on('click', lambda _, notification=item: open_notification_item(notification))
                    with ui.row().classes('w-full justify-between items-start gap-2 no-wrap'):
                        ui.label(item.get('message', '')).classes('font-bold text-gray-800 whitespace-normal break-words')
                        if not item.get('read'):
                            ui.badge(t('unread'), color='orange')
                    ui.label(format_timestamp(item.get('created_at'))).classes('text-xs text-gray-400 mt-1')

def render_header(container):
    container.clear()
    apply_theme()
    with container:
        header_classes = 'w-full min-h-16 bg-[#1a2332] items-center px-3 py-2 justify-between shadow-md flex-wrap gap-2' if is_mobile_ui() else 'w-full h-16 bg-[#1a2332] items-center px-4 justify-between shadow-md'
        title_classes = 'text-white font-bold text-base' if is_mobile_ui() else 'text-white font-bold text-lg'
        action_classes = 'gap-1 items-center' if is_mobile_ui() else 'gap-3 items-center'
        with ui.row().classes(header_classes):
            with ui.row().classes('gap-3 items-center cursor-pointer').on('click', lambda: show_screen('top')):
                ui.icon('public', color='blue-400').classes('text-2xl')
                ui.label(t('app_title')).classes(title_classes)
            with ui.row().classes(action_classes):
                ui.button(icon=ui_mode_icon(), on_click=toggle_ui_mode).props('flat round color=white').tooltip(ui_mode_tooltip())
                ui.button(
                    icon='dark_mode' if state.theme_mode == 'light' else 'light_mode',
                    on_click=toggle_theme,
                ).props('flat round color=white').tooltip(t('theme_toggle'))
                with ui.dropdown_button(text=state.lang.upper(), icon='language', auto_close=True).props('flat color=white dense'):
                    ui.item('日本語 (JA)', on_click=lambda: switch_language('ja'))
                    ui.item('English (EN)', on_click=lambda: switch_language('en'))
                    ui.item('中文 (ZH)', on_click=lambda: switch_language('zh'))
                if state.current_user:
                    ui.button(icon='search', on_click=lambda: show_screen('main')) \
                        .props('flat round color=white') \
                        .tooltip(t('back_search'))
                    ui.button(icon='history', on_click=open_history_box) \
                        .props('flat round color=white') \
                        .tooltip(t('history'))
                    header_user = get_current_user_record()
                    with ui.row().classes('gap-2 items-center cursor-pointer').on('click', lambda: show_screen('account')):
                        render_avatar_image(
                            current_user_avatar_url(header_user),
                            header_user,
                            'w-8 h-8 rounded-full border-2 border-white shadow bg-white flex-shrink-0',
                            icon_size='2rem',
                            icon_classes='text-white',
                        )
                        header_name = current_user_display_name(header_user)
                        ui.label(header_name) \
                            .classes('wa-user-pill text-sm font-bold px-2 py-1 rounded-full bg-white shadow-sm') \
                            .style(f'color: {user_pill_text_color(header_user)};')
                    if header_user and sengoku_is_user_eligible(user=header_user):
                        ui.button(
                            t('normal_mode') if state.sengoku_mode else t('sengoku_mode'),
                            icon='local_fire_department',
                            on_click=lambda: set_sengoku_mode(not state.sengoku_mode),
                        ).props('flat color=white dense')
                    unread_count = unread_notification_count(header_user)
                    if unread_count:
                        ui.button(str(unread_count), icon='notifications', on_click=open_notifications_box) \
                            .props('flat color=white dense') \
                            .tooltip(t('notifications'))
                    else:
                        ui.button(icon='notifications', on_click=open_notifications_box) \
                            .props('flat round color=white') \
                            .tooltip(t('notifications'))
                menu_text = {'ja': '機能', 'en': 'Features', 'zh': '功能'}.get(state.lang, 'Features')
                with ui.dropdown_button(text=menu_text, icon='apps', auto_close=True).props('flat color=white dense'):
                    ui.item(help_labels()['nav'], on_click=lambda: show_screen('help'))
                    ui.item(help_labels()['detail_nav'], on_click=lambda: show_screen('help_detail'))
                    ui.separator()
                    if state.current_user and battle_is_user_eligible(user=get_current_user_record()):
                        ui.item(t('battle_direct'), on_click=lambda: show_screen('battle'))
                    ui.separator()
                    ui.item(t('quiz'), on_click=lambda: start_quiz('normal'))
                    ui.item(t('map'), on_click=lambda: show_screen('map'))
                    ui.item(t('network'), on_click=lambda: show_screen('network'))
                    ui.item(t('compare'), on_click=lambda: show_screen('compare'))
                    ui.item(t('timeline'), on_click=lambda: show_screen('timeline'))
                    ui.item(t('users'), on_click=lambda: show_screen('users'))
                    ui.item(t('rankings'), on_click=lambda: show_screen('rankings'))
                    ui.item(t('friends'), on_click=lambda: show_screen('social'))
                    ui.item(t('account'), on_click=lambda: show_screen('account'))
                if state.current_user:
                    ui.button(icon='logout', on_click=logout_user).props('flat round color=white').tooltip(t('logout'))

# ========================================
# 2. メイン画面
# ========================================
with ui.column().classes('wa-dark-area w-full h-screen items-center justify-center gap-4 bg-gray-50') as top_screen:
    top_container = ui.column().classes('items-center gap-4')
    def refresh_top_ui():
        top_container.clear()
        apply_theme()
        update_mode_classes(top_container, 'items-center gap-4', 'items-center gap-3 px-6 text-center max-w-sm')
        with top_container:
            ui.icon('public', size='4.5rem' if is_mobile_ui() else '6rem').classes('text-[#1a2332]')
            ui.label(t('app_title')).classes('text-3xl font-bold text-[#1a2332]' if is_mobile_ui() else 'text-5xl font-bold text-[#1a2332]')
            ui.label(t('subtitle')).classes('text-base text-gray-500' if is_mobile_ui() else 'text-xl text-gray-500')
            ui.button(t('switch_to_pc') if is_mobile_ui() else t('switch_to_mobile'), icon=ui_mode_icon(), on_click=toggle_ui_mode) \
                .props('outline color=primary') \
                .classes('w-full px-6 py-2 rounded-full shadow-sm font-bold' if is_mobile_ui() else 'px-8 py-2 rounded-full shadow-sm font-bold')
            ui.button(t('theme_light') if state.theme_mode == 'dark' else t('theme_dark'), icon='light_mode' if state.theme_mode == 'dark' else 'dark_mode', on_click=toggle_theme) \
                .props('outline color=primary') \
                .classes('w-full px-6 py-2 rounded-full shadow-sm font-bold' if is_mobile_ui() else 'px-8 py-2 rounded-full shadow-sm font-bold')
            ui.button(help_labels()['nav'], icon='help', on_click=lambda: show_screen('help')) \
                .props('outline color=primary') \
                .classes('w-full px-6 py-2 rounded-full shadow-sm font-bold' if is_mobile_ui() else 'px-8 py-2 rounded-full shadow-sm font-bold')
            ui.button(help_labels()['detail_nav'], icon='menu_book', on_click=lambda: show_screen('help_detail')) \
                .props('outline color=grey') \
                .classes('w-full px-6 py-2 rounded-full shadow-sm font-bold' if is_mobile_ui() else 'px-8 py-2 rounded-full shadow-sm font-bold')
            if state.current_user:
                top_user = get_current_user_record()
                top_name = current_user_display_name(top_user)
                ui.label(t('logged_in_as').format(user=top_name)) \
                    .classes('wa-user-pill px-3 py-2 rounded-full bg-white border shadow-sm text-sm font-bold') \
                    .style(f'color: {user_pill_text_color(top_user)};')
                daily = today_country()
                if daily:
                    with ui.card().classes('w-full max-w-md p-4 gap-2 shadow-md border border-blue-100'):
                        ui.label(t('today_country')).classes('text-sm font-bold text-blue-700')
                        with ui.row().classes('w-full items-center gap-3 no-wrap'):
                            render_flag_frame(daily, 'w-24 flex-shrink-0 shadow border rounded')
                            with ui.column().classes('gap-1 flex-grow'):
                                ui.label(get_localized_text(daily['names'])).classes('text-xl font-bold text-[#1a2332]')
                                ui.label(first_sentence(get_localized_text(daily.get('desc', {})))).classes('text-sm text-gray-500 line-clamp-2')
                        ui.button(t('view_detail'), icon='open_in_new', on_click=lambda c=daily: open_country_detail(c)) \
                            .props('outline color=primary') \
                            .classes('w-full')
                ui.button('ENTER', on_click=lambda: show_screen('main')) \
                    .classes('w-full bg-[#1a2332] text-white px-8 py-3 rounded-full text-base shadow-lg hover:scale-105 transition' if is_mobile_ui() else 'bg-[#1a2332] text-white px-10 py-3 rounded-full text-lg shadow-lg hover:scale-105 transition')
                ui.button(t('quiz'), icon='quiz', on_click=lambda: start_quiz('normal')) \
                    .classes('w-full bg-blue-600 text-white px-8 py-2 rounded-full shadow hover:bg-blue-700 transition' if is_mobile_ui() else 'bg-blue-600 text-white px-8 py-2 rounded-full shadow hover:bg-blue-700 transition')
                ui.button(t('quiz_mode_review'), icon='school', on_click=lambda: start_quiz('review')) \
                    .props('outline color=primary') \
                    .classes('w-full px-8 py-2 rounded-full shadow-sm' if is_mobile_ui() else 'px-8 py-2 rounded-full shadow-sm')
                with ui.row().classes('w-full gap-2 justify-center flex-wrap'):
                    ui.button(t('map'), icon='map', on_click=lambda: show_screen('map')) \
                        .props('outline color=primary') \
                        .classes('flex-grow' if is_mobile_ui() else 'px-6')
                    ui.button(t('network'), icon='account_tree', on_click=lambda: show_screen('network')) \
                        .props('outline color=primary') \
                        .classes('flex-grow' if is_mobile_ui() else 'px-6')
                    ui.button(t('compare'), icon='compare_arrows', on_click=lambda: show_screen('compare')) \
                        .props('outline color=primary') \
                        .classes('flex-grow' if is_mobile_ui() else 'px-6')
                    ui.button(t('timeline'), icon='timeline', on_click=lambda: show_screen('timeline')) \
                        .props('outline color=primary') \
                        .classes('flex-grow' if is_mobile_ui() else 'px-6')
                    ui.button(t('account'), icon='account_circle', on_click=lambda: show_screen('account')) \
                        .props('outline color=primary') \
                        .classes('flex-grow' if is_mobile_ui() else 'px-6')
                ui.button(t('logout'), icon='logout', on_click=logout_user) \
                    .props('outline color=grey') \
                    .classes('w-full px-6 py-2 rounded-full' if is_mobile_ui() else 'px-8 py-2 rounded-full')
            else:
                with ui.card().classes('w-full max-w-sm p-5 gap-3 shadow-md'):
                    ui.label(t('login_required')).classes('text-sm text-gray-500 text-center')
                    username_input = ui.input(label=t('username')).props('outlined dense').classes('w-full')
                    password_input = ui.input(label=t('password'), password=True, password_toggle_button=True).props('outlined dense').classes('w-full')
                    with ui.row().classes('w-full gap-2 items-center'):
                        ui.button(t('login'), icon='login', on_click=lambda: login_user(username_input.value, password_input.value)) \
                            .classes('flex-grow bg-[#1a2332] text-white')
                        ui.button(t('register'), icon='person_add', on_click=lambda: register_user(username_input.value, password_input.value)) \
                            .props('outline color=primary') \
                            .classes('flex-grow')
                    ui.button(t('guest_login'), icon='person', on_click=guest_login) \
                        .props('outline color=grey') \
                        .classes('w-full')
                    ui.button(backup_labels()['restore_browser'], icon='cloud_sync', on_click=restore_from_browser_backup) \
                        .props('outline color=primary') \
                        .classes('w-full')
                    ui.label(backup_labels()['import']).classes('text-xs font-bold text-gray-500')
                    ui.upload(on_upload=import_guest_backup_file, auto_upload=True) \
                        .props('accept=.json') \
                        .classes('w-full')
            with ui.row().classes('mt-8 gap-4'):
                ui.link('JA', '#').on('click', lambda: switch_language('ja'))
                ui.link('EN', '#').on('click', lambda: switch_language('en'))
                ui.link('ZH', '#').on('click', lambda: switch_language('zh'))
    refresh_top_ui()

# ========================================
# 使い方ページ
# ========================================
with ui.column().classes('wa-dark-area w-full min-h-screen bg-gray-50 gap-0') as help_screen:
    header_container_help = ui.column().classes('w-full p-0 m-0')
    help_content = ui.column().classes('w-full max-w-5xl p-8 gap-5 self-center')

    def render_help_mock(index, title, body):
        with ui.column().classes('wa-light-fallback w-full p-4 gap-3 bg-white border border-gray-200 rounded shadow-sm'):
            with ui.row().classes('w-full items-center gap-2'):
                ui.badge(str(index), color='primary')
                ui.label(title).classes('text-lg font-bold text-[#1a2332]')
            ui.label(body).classes('text-sm text-gray-600 leading-relaxed')
            if index == 1:
                ui.input(value='', placeholder=t('search_ph')).props('outlined dense readonly prepend-inner-icon=search').classes('w-full')
                with ui.row().classes('w-full gap-2 flex-wrap'):
                    ui.button(t('sort_name'), icon='sort_by_alpha').props('outline color=primary dense')
                    ui.button(t('sort_period'), icon='event').props('outline color=primary dense')
                    ui.button(t('labels', 'region')).props('outline color=grey dense')
                    ui.button(t('tag_group'), icon='sell').props('outline color=grey dense')
            elif index == 2:
                with ui.row().classes('w-full gap-2 flex-wrap'):
                    ui.button(t('labels', 'capital'), icon='info').props('outline color=primary dense')
                    ui.button(t('labels', 'desc'), icon='article').props('outline color=primary dense')
                    ui.button(t('map'), icon='map').props('outline color=primary dense')
                    ui.button(t('notes'), icon='edit_note').props('outline color=primary dense')
                with ui.row().classes('w-full gap-2 flex-wrap'):
                    for tag in ['UN Member', 'Republic', 'Maritime Power']:
                        tag_chip(tag)
            else:
                with ui.row().classes('w-full gap-2 flex-wrap'):
                    for key, label_key in QUIZ_CATEGORY_OPTIONS[:5]:
                        ui.button(t(label_key)).props('outline color=primary dense')
                ui.button(t('quiz_next'), icon='refresh').props('outline color=primary dense').classes('self-start')

    def refresh_help_view():
        render_header(header_container_help)
        update_mode_classes(
            help_content,
            'w-full max-w-5xl p-8 gap-5 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        help_content.clear()
        labels = help_labels()
        with help_content:
            ui.label(labels['title']).classes('text-3xl font-bold text-[#1a2332]')
            ui.label(labels['intro']).classes('text-gray-600 text-lg leading-relaxed')
            with ui.grid(columns=1 if is_mobile_ui() else 4).classes('w-full gap-3'):
                for icon, title, body in labels['steps']:
                    with ui.column().classes('wa-light-fallback w-full p-4 gap-2 bg-white border border-blue-100 rounded shadow-sm'):
                        ui.icon(icon, size='2rem').classes('text-blue-600')
                        ui.label(title).classes('text-lg font-bold text-[#1a2332]')
                        ui.label(body).classes('text-sm text-gray-600 leading-relaxed')
            ui.label(labels['mock_title']).classes('text-2xl font-bold text-[#1a2332] mt-2')
            with ui.grid(columns=1 if is_mobile_ui() else 3).classes('w-full gap-4'):
                for index, (title, body) in enumerate(labels['mocks'], start=1):
                    render_help_mock(index, title, body)
            with ui.row().classes('w-full gap-2 flex-col' if is_mobile_ui() else 'w-full gap-3'):
                ui.button('ENTER', icon='search', on_click=lambda: show_screen('main')) \
                    .props('color=primary') \
                    .classes('w-full' if is_mobile_ui() else '')
                ui.button(labels['detail_nav'], icon='menu_book', on_click=lambda: show_screen('help_detail')) \
                    .props('outline color=primary') \
                    .classes('w-full' if is_mobile_ui() else '')
                ui.button(t('back_home'), icon='home', on_click=lambda: show_screen('top')) \
                    .props('outline color=grey') \
                    .classes('w-full' if is_mobile_ui() else '')

with ui.column().classes('wa-dark-area w-full min-h-screen bg-gray-50 gap-0') as help_detail_screen:
    header_container_help_detail = ui.column().classes('w-full p-0 m-0')
    help_detail_content = ui.column().classes('w-full max-w-4xl p-8 gap-5 self-center')

    def refresh_help_detail_view():
        render_header(header_container_help_detail)
        update_mode_classes(
            help_detail_content,
            'w-full max-w-4xl p-8 gap-5 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        help_detail_content.clear()
        labels = detailed_help_labels()
        with help_detail_content:
            ui.label(labels['title']).classes('text-3xl font-bold text-[#1a2332]')
            ui.label(labels['intro']).classes('text-gray-600 text-lg leading-relaxed')
            with ui.column().classes('w-full gap-3'):
                for title, body in labels['sections']:
                    with ui.expansion(title, icon='menu_book').classes('wa-light-fallback w-full bg-white border border-gray-200 rounded shadow-sm'):
                        ui.markdown(body).classes('text-gray-700 leading-relaxed p-4')
            with ui.row().classes('w-full gap-2 flex-col' if is_mobile_ui() else 'w-full gap-3'):
                ui.button(help_labels()['nav'], icon='help', on_click=lambda: show_screen('help')) \
                    .props('outline color=primary') \
                    .classes('w-full' if is_mobile_ui() else '')
                ui.button('ENTER', icon='search', on_click=lambda: show_screen('main')) \
                    .props('color=primary') \
                    .classes('w-full' if is_mobile_ui() else '')
                ui.button(t('back_home'), icon='home', on_click=lambda: show_screen('top')) \
                    .props('outline color=grey') \
                    .classes('w-full' if is_mobile_ui() else '')

with ui.column().classes('wa-dark-area w-full min-h-screen bg-gray-50 gap-0') as main_screen:
    header_container_main = ui.column().classes('w-full p-0 m-0')

    with ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center') as main_content:
        search_area_container = ui.card().classes('w-full p-6 bg-blue-50 shadow-sm border border-blue-100')
        list_container = ui.column().classes('w-full gap-4')
        hits_label = ui.label()

        region_options, tag_options = get_filter_options()

        def update_keyword(e):
            state.page = 1
            if apply_admin_search_cheat(e.value) or apply_sengoku_search_cheat(e.value):
                state.search_keyword = ''
                refresh_main_ui()
                return
            state.search_keyword = e.value
            refresh_search_list()

        def pick_random():
            data = get_data()
            countries = public_country_list(data)
            if countries:
                target = random.choice(countries)
                select_country(target)
                ui.notify(f'Random Pick: {get_localized_text(target["names"])}')

        def toggle_sort_order():
            state.sort_order = 'desc' if state.sort_order == 'asc' else 'asc'
            state.page = 1
            refresh_main_ui()

        def toggle_sort_field():
            state.sort_field = 'period' if state.sort_field == 'name' else 'name'
            state.page = 1
            refresh_main_ui()

        def toggle_favorites_filter():
            set_favorite_filter(next_favorite_filter())
            state.page = 1
            refresh_main_ui()

        def set_collection_filter(value):
            state.collection_filter = value
            state.page = 1
            refresh_search_list()

        def toggle_card_favorite(country):
            toggle_favorite(country)
            refresh_search_list()

        def change_page(page):
            state.page = page
            refresh_search_list()

        def refresh_main_ui():
            render_header(header_container_main)
            r_opts, t_opts = get_filter_options()
            tag_group_opts = get_tag_group_options()
            update_mode_classes(
                main_content,
                'w-full max-w-5xl p-6 gap-6 self-center',
                'w-full max-w-md p-4 gap-4 self-center',
            )
            update_mode_classes(
                search_area_container,
                'w-full p-6 bg-blue-50 shadow-sm border border-blue-100',
                'w-full p-4 bg-blue-50 shadow-sm border border-blue-100',
            )

            search_area_container.clear()
            with search_area_container:
                icon_label(t('search_label'), 'search', 'text-sm font-bold text-blue-800 mb-1', 'text-blue-600', 'items-center gap-1')
                with ui.row().classes('w-full gap-2 items-stretch flex-wrap' if is_mobile_ui() else 'w-full gap-2 items-center'):
                    ui.input(value=state.search_keyword, on_change=update_keyword) \
                        .props('rounded outlined prepend-inner-icon=search clearable') \
                        .classes('wa-light-fallback text-base w-full bg-white shadow-inner' if is_mobile_ui() else 'wa-light-fallback text-lg flex-grow bg-white shadow-inner') \
                        .props(f'placeholder="{t("search_ph")}"')
                    sort_field_icon = 'event' if state.sort_field == 'period' else 'sort_by_alpha'
                    sort_field_label = t('sort_period') if state.sort_field == 'period' else t('sort_name')
                    ui.button(sort_field_label, icon=sort_field_icon, on_click=toggle_sort_field) \
                        .classes('bg-sky-700 text-white px-3 py-2 shadow-md flex-grow' if is_mobile_ui() else 'bg-sky-700 text-white px-4 py-2 shadow-md') \
                        .tooltip(sort_field_label)
                    sort_icon = 'arrow_downward' if state.sort_order == 'asc' else 'arrow_upward'
                    sort_bg = 'bg-blue-600'
                    sort_label = t('sort_asc') if state.sort_order == 'asc' else t('sort_desc')
                    ui.button(sort_label, icon=sort_icon, on_click=toggle_sort_order) \
                        .classes(f'{sort_bg} text-white px-3 py-2 shadow-md flex-grow' if is_mobile_ui() else f'{sort_bg} text-white px-4 py-2 shadow-md') \
                        .tooltip(sort_label)

                    ui.button(icon='shuffle', on_click=pick_random) \
                        .classes('bg-purple-500 text-white px-3 py-2 shadow-md flex-grow' if is_mobile_ui() else 'bg-purple-500 text-white px-4 py-2 shadow-md')

                    ui.button(t('quiz'), icon='quiz', on_click=lambda: start_quiz('normal')) \
                        .classes('bg-emerald-600 text-white px-3 py-2 shadow-md flex-grow' if is_mobile_ui() else 'bg-emerald-600 text-white px-4 py-2 shadow-md')

                with ui.row().classes('w-full gap-2 mt-2 flex-col' if is_mobile_ui() else 'w-full gap-4 mt-2'):
                    ui.select(r_opts, value=selected_region_label(), label=t('labels', 'region'),on_change=lambda e: set_region_filter(e.value), clearable=True) \
                        .props('prepend-inner-icon=public') \
                        .classes('w-full bg-white' if is_mobile_ui() else 'w-48 bg-white')
                    ui.select(tag_group_opts, value=selected_tag_group_label(), label=t('tag_group'), on_change=lambda e: set_tag_group_filter(e.value), clearable=True) \
                        .props('prepend-inner-icon=category') \
                        .classes('w-full bg-white' if is_mobile_ui() else 'w-48 bg-white')
                    ui.select(t_opts, value=selected_tag_label(), label=t('labels', 'tags'),on_change=lambda e: set_tag_filter(e.value), clearable=True) \
                        .props('prepend-inner-icon=sell') \
                        .classes('w-full bg-white' if is_mobile_ui() else 'w-48 bg-white')
                    ui.button(favorite_filter_label(), icon=favorite_filter_icon(), on_click=toggle_favorites_filter) \
                        .props(f'color={favorite_filter_color()}') \
                        .classes('w-full px-4 py-2 shadow-md' if is_mobile_ui() else 'px-4 py-2 shadow-md')
                    collection_names = list(get_collections().keys())
                    if collection_names:
                        ui.select(collection_names, value=state.collection_filter, label=t('collections'), on_change=lambda e: set_collection_filter(e.value), clearable=True) \
                            .classes('w-full bg-white' if is_mobile_ui() else 'w-48 bg-white')

                with ui.row().classes('w-full gap-3 items-stretch mt-4 flex-col' if is_mobile_ui() else 'w-full justify-between items-center mt-4'):
                    with ui.button_group().props('unelevated').classes('wa-type-filter'):
                        for key in ['All', 'Present', 'Past']:
                            label = t('tabs', key)
                            selected = state.filter_type == key
                            type_icon = {'All': 'apps', 'Present': 'flag', 'Past': 'history_edu'}[key]
                            button = ui.button(label, icon=type_icon, on_click=lambda e, k=key: set_type_filter(k)) \
                                .props('color=blue text-color=white' if selected else 'color=white text-color=black')
                            if not selected:
                                button.classes('text-black')
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('analytics').classes('text-blue-500')
                        ui.label('').bind_text_from(hits_label, 'text').classes('text-gray-500 font-bold text-lg')

            refresh_search_list()

        def set_type_filter(val):
            state.filter_type = val
            state.page = 1
            refresh_main_ui()
        def set_region_filter(val):
            state.filter_region = normalize_region_value(val)
            state.page = 1
            refresh_search_list()

        def set_tag_group_filter(val):
            state.filter_tag_group = normalize_tag_group_value(val)
            allowed_tags = tag_group_allowed_tags(state.filter_tag_group)
            if allowed_tags is not None and state.filter_tag not in allowed_tags:
                state.filter_tag = None
            state.page = 1
            refresh_main_ui()

        def set_tag_filter(val):
            state.filter_tag = normalize_tag_value(val)
            state.page = 1
            refresh_search_list()

        def render_page_button(icon, label_key, target_page, disabled=False):
            props = 'flat round color=grey disable' if disabled else 'flat round color=primary'
            button = ui.button(icon=icon, on_click=lambda p=target_page: change_page(p)) \
                .props(props) \
                .tooltip(t(label_key))
            return button

        def render_pagination(total_pages):
            if total_pages <= 1:
                return
            prev_disabled = state.page <= 1
            next_disabled = state.page >= total_pages
            with ui.row().classes('w-full justify-center items-center gap-2 mt-3 flex-wrap'):
                render_page_button('first_page', 'first_page', 1, prev_disabled)
                render_page_button('chevron_left', 'prev_page', state.page - 1, prev_disabled)
                ui.label(f'{state.page} / {total_pages} {t("page_unit")}') \
                    .classes('px-3 py-2 text-gray-700 font-bold')
                render_page_button('chevron_right', 'next_page', state.page + 1, next_disabled)
                render_page_button('last_page', 'last_page', total_pages, next_disabled)

        def refresh_search_list():
            list_container.clear()
            data = get_data()
            favorites = favorite_keys(data)
            selected_collection = set(get_collections().get(state.collection_filter, [])) if state.collection_filter else set()
            raw_keyword = str(state.search_keyword or '').strip()
            keyword = raw_keyword.casefold()
            countries = derived_country_data(data)['countries']
            search_index = country_search_index(data) if keyword else {}
            filtered = []
            for c in countries:
                # サプライズ用の国は、専用の合言葉が完全一致した時だけ一覧に入れます。
                if is_hidden_country(c):
                    if can_show_hidden_country(c, raw_keyword):
                        filtered.append(c)
                    continue
                if state.filter_type != 'All' and c['type'] != state.filter_type:
                    continue
                if state.filter_region and state.filter_region != c.get('region'):
                    continue
                if state.filter_tag and state.filter_tag not in c.get('tags', []):
                    continue
                favorite_filter = current_favorite_filter()
                key = country_key(c)
                if favorite_filter == 'only' and key not in favorites:
                    continue
                if favorite_filter == 'except' and key in favorites:
                    continue
                if state.collection_filter and key not in selected_collection:
                    continue

                if not keyword or keyword in search_index.get(key, ''):
                    filtered.append(c)
            if state.sort_field == 'period':
                filtered.sort(key=country_list_sort_key)
            else:
                filtered.sort(
                    key=country_list_sort_key,
                    reverse=state.sort_order == 'desc',
                )

            total_count = len(filtered)
            total_pages = max(1, (total_count + state.items_per_page - 1) // state.items_per_page)
            state.page = max(1, min(state.page, total_pages))
            start_index = (state.page - 1) * state.items_per_page
            end_index = min(start_index + state.items_per_page, total_count)
            display_list = filtered[start_index:end_index]

            if total_count:
                hits_label.text = f"{start_index + 1}-{end_index} / {total_count} {t('hits')} | {state.page} / {total_pages} {t('page_unit')}"
            else:
                hits_label.text = f"0 / 0 {t('hits')}"

            with list_container:
                if not display_list:
                    ui.label(t('no_result')).classes('w-full text-center text-gray-500 py-8')
                for c in display_list:
                    card_classes = 'w-full p-0 flex flex-col hover:shadow-md transition cursor-pointer overflow-hidden' if is_mobile_ui() else 'w-full p-0 flex flex-row no-wrap items-stretch hover:shadow-md transition cursor-pointer overflow-hidden'
                    with ui.card().classes(card_classes) as card:
                        card.on('click', lambda _, x=c: select_country(x))
                        flag_frame_classes = 'w-full rounded-none' if is_mobile_ui() else 'w-48 flex-shrink-0 rounded-none'
                        render_flag_frame(c, flag_frame_classes)
                        with ui.row().classes('w-full items-start no-wrap' if is_mobile_ui() else 'flex-grow items-stretch no-wrap'):
                            with ui.column().classes('p-3 gap-1 flex-grow' if is_mobile_ui() else 'p-4 gap-1 flex-grow'):
                                ui.label(get_localized_text(c['names'])).classes('text-lg font-bold text-gray-800' if is_mobile_ui() else 'text-xl font-bold text-gray-800')
                                with ui.row().classes('gap-1 flex-wrap'):
                                    ui.badge(t('tabs', c['type']), color='blue-grey').props('outline dense')
                                    for tag in c.get('tags', [])[:3]:
                                        tag_chip(tag)
                                card_period = period_label(c)
                                if card_period:
                                    ui.label(card_period).classes('text-xs font-bold text-orange-700')
                                ui.label(get_localized_text(c['desc'])).classes('text-gray-500 text-sm mt-1 line-clamp-2' if is_mobile_ui() else 'text-gray-500 text-sm mt-1 line-clamp-1')
                            fav_icon = 'star' if country_key(c) in favorites else 'star_border'
                            ui.button(icon=fav_icon, on_click=lambda _, x=c: toggle_card_favorite(x)) \
                                .props('flat round color=amber') \
                                .classes('self-start mt-2 mr-2' if is_mobile_ui() else 'self-center mr-3')
                render_pagination(total_pages)

        def select_country(country):
            open_country_detail(country, return_screen='main')

# ========================================
# 3. 結果画面
# ========================================
with ui.column().classes('wa-dark-area w-full min-h-screen bg-gray-50 gap-0') as result_screen:
    header_container_result = ui.column().classes('w-full p-0 m-0')
    result_content = ui.column().classes('w-full max-w-4xl p-8 gap-6 self-center')

    def refresh_result_view():
        render_header(header_container_result)
        update_mode_classes(
            result_content,
            'w-full max-w-4xl p-8 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        result_content.clear()
        c = state.selected_country
        if not c: return
        map_link = country_maps_url(c)
        wiki_url = f"https://ja.wikipedia.org/wiki/{c['names'].get('ja')}"
        detail_period = period_label(c)
        map_note_text = map_target_note(c)
        hide_external_links = bool(c.get('hide_external_links'))

        with result_content:
            with ui.row().classes('w-full gap-2 items-stretch flex-col' if is_mobile_ui() else 'w-full justify-between items-center'):
                ui.button(t('back_search'), icon='arrow_back', on_click=lambda: show_screen(result_return_screen())) \
                    .props('flat color=grey dense text-lg') \
                    .classes('w-full' if is_mobile_ui() else '')
                favorite_label = t('favorite_remove') if is_favorite(c) else t('favorite_add')
                favorite_icon = 'star' if is_favorite(c) else 'star_border'
                ui.button(favorite_label, icon=favorite_icon, on_click=lambda: (toggle_favorite(c), refresh_result_view())) \
                    .props('color=amber') \
                    .classes('w-full' if is_mobile_ui() else '')

            tabs = detail_tab_labels()
            related = related_countries(c)

            with ui.card().classes('wa-light-fallback w-full p-0 overflow-hidden bg-white'):
                with ui.row().classes('wa-light-fallback w-full bg-white p-4 gap-4 items-start flex-col' if is_mobile_ui() else 'wa-light-fallback w-full bg-white p-6 gap-6 items-start'):
                    render_flag_frame(
                        c,
                        'w-full shadow-md border rounded' if is_mobile_ui() else 'w-56 flex-shrink-0 shadow-md border rounded',
                    )
                    with ui.column().classes('w-full gap-2' if is_mobile_ui() else 'flex-grow gap-2'):
                        ui.label(get_localized_text(c['names'])).classes('text-3xl font-bold text-[#1a2332]' if is_mobile_ui() else 'text-4xl font-bold text-[#1a2332]')
                        ui.label(c['names'].get('en', '')).classes('text-lg text-gray-400 font-serif italic' if is_mobile_ui() else 'text-xl text-gray-400 font-serif italic')
                        with ui.row().classes('mt-2'):
                            ui.badge(t('tabs', c['type']), color='green' if c['type']=='Present' else 'orange').props('text-lg')

                ui.separator()
                with ui.tabs().props('dense inline-label mobile-arrows outside-arrows').classes('wa-light-fallback w-full bg-white text-[#1a2332]') as detail_tabs:
                    basic_tab = ui.tab(tabs['basic'], icon='info')
                    desc_tab = ui.tab(tabs['desc'], icon='article')
                    if not hide_external_links:
                        map_tab = ui.tab(tabs['map'], icon='map')
                    personal_tab = ui.tab(tabs['personal'], icon='edit_note')
                    related_tab = ui.tab(tabs['related'], icon='account_tree')

                with ui.tab_panels(detail_tabs, value=basic_tab).classes('wa-light-fallback w-full bg-white'):
                    with ui.tab_panel(basic_tab).classes('p-4' if is_mobile_ui() else 'p-6'):
                        detail_container = ui.column().classes('w-full gap-5') if is_mobile_ui() else ui.grid(columns=2).classes('w-full gap-6')
                        with detail_container:
                            with ui.column().classes('gap-4'):
                                if not hide_external_links:
                                    with ui.row().classes('gap-2 w-full flex-col' if is_mobile_ui() else 'gap-2 w-full flex-wrap'):
                                        ui.button(t('view_on_map'), icon='map', on_click=lambda country=c: set_map_country(country)) \
                                            .props('color=primary') \
                                            .classes('flex-grow')
                                        ui.button(t('network'), icon='account_tree', on_click=lambda country=c: set_network_country(country)) \
                                            .props('outline color=primary') \
                                            .classes('flex-grow')
                                        ui.link('Google Maps', map_link, new_tab=True) \
                                            .classes('flex-grow bg-green-600 text-white text-center px-4 py-2 rounded shadow hover:bg-green-700 no-underline font-bold transition')
                                        ui.link('Wikipedia', wiki_url, new_tab=True) \
                                            .classes('flex-grow bg-gray-600 text-white text-center px-4 py-2 rounded shadow hover:bg-gray-700 no-underline font-bold transition')

                                info_field(t('labels', 'capital'), get_localized_text(c.get('capital', '-')), 'location_city', 'text-lg')
                                if detail_period:
                                    info_field(period_field_label(c), detail_period, 'event', 'text-lg font-bold text-orange-700')
                                info_field(t('labels', 'region'), region_label(c.get('region', '-')), 'public', 'text-lg')
                                with ui.column().classes('gap-1'):
                                    icon_label(t('labels', 'tags'), 'sell', 'text-xs font-bold text-gray-400 uppercase', 'text-blue-400', 'items-center gap-1')
                                    with ui.row().classes('gap-1 flex-wrap'):
                                        for tag in c.get('tags', []):
                                            tag_chip(tag, dense=False)
                            with ui.column().classes('gap-4'):
                                for label, value in profile_rows(c):
                                    info_field(label, value, profile_row_icon(label), 'text-lg')

                    with ui.tab_panel(desc_tab).classes('p-4' if is_mobile_ui() else 'p-6'):
                        with ui.column().classes('w-full gap-3'):
                            icon_label(t('labels', 'desc'), 'article', 'text-xs font-bold text-gray-400 uppercase', 'text-blue-400', 'items-center gap-1')
                            ui.markdown(get_localized_text(c['desc'])).classes('text-gray-800 leading-relaxed text-lg')
                            for label, value in detail_rows(c):
                                ui.separator().classes('my-1')
                                icon_label(label, 'notes', 'text-xs font-bold text-gray-400 uppercase', 'text-blue-400', 'items-center gap-1')
                                ui.markdown(value).classes('text-gray-800 leading-relaxed')

                    if not hide_external_links:
                        with ui.tab_panel(map_tab).classes('p-4' if is_mobile_ui() else 'p-6'):
                            with ui.column().classes('w-full gap-3'):
                                with ui.row().classes('w-full justify-between items-center flex-wrap gap-2'):
                                    icon_label(t('map'), 'map', 'text-lg font-bold text-[#1a2332]', 'text-blue-600')
                                    ui.link('Google Maps', map_link, new_tab=True).classes('text-green-700 font-bold')
                                if map_note_text:
                                    ui.label(map_note_text).classes('text-sm text-gray-500')
                                render_map_embed(c, height=420 if not is_mobile_ui() else 300)

                    with ui.tab_panel(personal_tab).classes('p-4' if is_mobile_ui() else 'p-6'):
                        with ui.column().classes('w-full gap-5'):
                            with ui.column().classes('w-full gap-3'):
                                icon_label(t('notes'), 'edit_note', 'text-lg font-bold text-[#1a2332]', 'text-blue-600')
                                note_input = ui.textarea(value=get_note_for_country(c), placeholder=t('notes')) \
                                    .props('outlined autogrow') \
                                    .classes('w-full')
                                ui.button(t('save_note'), icon='save', on_click=lambda country=c, field=note_input: save_note_for_country(country, field.value)) \
                                    .props('color=primary') \
                                    .classes('self-start')

                            ui.separator()
                            with ui.column().classes('w-full gap-3'):
                                icon_label(t('collections'), 'folder', 'text-lg font-bold text-[#1a2332]', 'text-blue-600')
                                collections = get_collections()
                                if collections:
                                    with ui.row().classes('w-full gap-2 flex-wrap'):
                                        for collection_name in collections:
                                            selected = collection_contains(collection_name, c)
                                            icon = 'check_circle' if selected else 'add_circle'
                                            color = 'green' if selected else 'primary'
                                            ui.button(collection_name, icon=icon, on_click=lambda _, name=collection_name, country=c: (toggle_collection_country(name, country), refresh_result_view())) \
                                                .props(f'outline color={color} dense')
                                else:
                                    ui.label(t('no_collections')).classes('text-sm text-gray-500')
                                with ui.row().classes('w-full gap-2 items-end flex-col' if is_mobile_ui() else 'w-full gap-2 items-end'):
                                    collection_input = ui.input(label=t('collection_name')).props('outlined dense').classes('w-full' if is_mobile_ui() else 'flex-grow')
                                    ui.button(t('create_collection'), icon='create_new_folder', on_click=lambda field=collection_input: (create_collection(field.value), refresh_result_view())) \
                                        .props('color=primary') \
                                        .classes('w-full' if is_mobile_ui() else '')

                    with ui.tab_panel(related_tab).classes('p-4' if is_mobile_ui() else 'p-6'):
                        with ui.column().classes('w-full gap-3'):
                            icon_label(t('related_countries'), 'account_tree', 'text-lg font-bold text-[#1a2332]', 'text-blue-600')
                            if not related:
                                ui.label('-').classes('text-sm text-gray-500')
                            else:
                                with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-3'):
                                    for related_country in related:
                                        with ui.row().classes('w-full p-3 cursor-pointer hover:shadow-md transition border rounded items-center gap-3 no-wrap') as related_card:
                                            related_card.on('click', lambda _, x=related_country: open_country_detail(x))
                                            render_flag_frame(related_country, 'w-20 flex-shrink-0 shadow border rounded')
                                            with ui.column().classes('gap-1'):
                                                ui.label(get_localized_text(related_country['names'])).classes('font-bold text-gray-800')
                                                ui.label(region_label(related_country.get('region', ''))).classes('text-xs text-gray-500')

# ========================================
# 4. ミニクイズ画面
# ========================================
quiz_timer_label = None

with ui.column().classes('wa-dark-area wa-quiz-screen w-full min-h-screen bg-gray-50 gap-0') as quiz_screen:
    header_container_quiz = ui.column().classes('w-full p-0 m-0')
    quiz_content = ui.column().classes('w-full max-w-3xl p-8 gap-6 self-center')

    def mark_quiz_timeout(refresh=True):
        if not state.quiz or state.quiz.get('answered') or quiz_remaining_seconds(state.quiz) != 0:
            return False
        state.quiz['selected_key'] = None
        state.quiz['answered'] = True
        state.quiz['timed_out'] = True
        update_quiz_stats(
            False,
            state.quiz.get('answer_key'),
            state.quiz_mode == 'review',
            None,
            state.quiz.get('type'),
        )
        ui.notify(t('quiz_time_up'), color='warning')
        if refresh:
            refresh_quiz_view()
        return True

    def update_quiz_timer_label():
        global quiz_timer_label
        try:
            if not quiz_screen.visible or not state.quiz:
                return
            remaining = quiz_remaining_seconds(state.quiz)
            if remaining is None:
                if quiz_timer_label:
                    quiz_timer_label.set_text('')
                return
            if quiz_timer_label:
                quiz_timer_label.set_text(t('quiz_time_remaining').format(seconds=remaining))
            if remaining <= 0:
                mark_quiz_timeout(refresh=True)
        except Exception as e:
            print(f'Quiz timer update skipped: {e}', flush=True)

    def next_quiz_from_button():
        if state.quiz and not state.quiz.get('answered'):
            update_quiz_stats(
                False,
                state.quiz.get('answer_key'),
                state.quiz_mode == 'review',
                None,
                state.quiz.get('type'),
            )
        start_quiz()

    def select_quiz_option(option_key):
        if not state.quiz:
            return
        if state.quiz.get('answered'):
            return
        state.quiz['selected_key'] = option_key
        state.quiz['answered'] = True
        update_quiz_stats(
            option_key == quiz_answer_option(state.quiz),
            state.quiz.get('answer_key'),
            state.quiz_mode == 'review',
            option_key,
            state.quiz.get('type'),
        )
        refresh_quiz_view()

    def open_quiz_answer_detail():
        if not state.quiz:
            return
        country = countries_by_key().get(state.quiz['answer_key'])
        if country:
            open_country_detail(country, return_screen='quiz')

    def refresh_quiz_view():
        global quiz_timer_label
        render_header(header_container_quiz)
        update_mode_classes(
            quiz_content,
            'w-full max-w-3xl p-8 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        quiz_timer_label = None
        quiz_content.clear()
        if not state.quiz:
            state.quiz = prepare_quiz_timer(build_quiz())

        quiz = state.quiz
        if not quiz:
            with quiz_content:
                page_heading(t('quiz_title'), 'quiz')
                ui.label('No quiz data available.').classes('text-gray-500')
            return
        if quiz_remaining_seconds(quiz) == 0:
            mark_quiz_timeout(refresh=False)

        lookup = countries_by_key()
        quiz = state.quiz
        answer = lookup.get(quiz['answer_key'])
        question, description, image = quiz_view_parts(quiz, answer) if answer else ('', '', None)

        with quiz_content:
            with ui.row().classes('w-full gap-2 items-stretch flex-col' if is_mobile_ui() else 'w-full justify-between items-center'):
                icon_label(
                    t('quiz_title'),
                    'quiz',
                    'text-2xl font-bold text-[#1a2332]' if is_mobile_ui() else 'text-3xl font-bold text-[#1a2332]',
                    'text-blue-600',
                    'items-center gap-3',
                )

            stats = get_quiz_stats()
            icon_label(
                t('quiz_stats').format(
                    correct=stats.get('correct', 0),
                    answered=stats.get('answered', 0),
                    streak=stats.get('streak', 0),
                    best=stats.get('best_streak', 0),
                ),
                'bar_chart',
                'text-sm text-gray-600 font-bold',
                'text-blue-500',
                'items-center gap-2',
            )
            remaining = quiz_remaining_seconds(quiz)
            if remaining is not None:
                quiz_timer_label = ui.label(t('quiz_time_remaining').format(seconds=remaining)) \
                    .classes('self-start rounded bg-red-600 px-3 py-1 text-sm font-bold text-white shadow')
            review_count = len(get_review_keys())
            with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                icon_label(t('quiz_mode'), 'school', 'text-sm font-bold text-gray-500', 'text-blue-500', 'items-center gap-1')
                for key, label_key in [('normal', 'quiz_mode_normal'), ('review', 'quiz_mode_review')]:
                    color = 'primary' if state.quiz_mode == key else 'grey'
                    ui.button(t(label_key) if key == 'normal' else f'{t(label_key)} ({review_count})', on_click=lambda _, m=key: start_quiz(m)) \
                        .props(f'outline color={color} dense')
            with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                icon_label(t('difficulty'), 'speed', 'text-sm font-bold text-gray-500', 'text-blue-500', 'items-center gap-1')
                if state.quiz_difficulty not in quiz_difficulty_options():
                    state.quiz_difficulty = 'hard'
                for key in quiz_difficulty_options():
                    color = 'primary' if state.quiz_difficulty == key else 'grey'
                    ui.button(t(f'difficulty_{key}'), on_click=lambda _, d=key: set_quiz_difficulty(d)) \
                        .props(f'outline color={color} dense')
            with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                icon_label(t('quiz_category'), 'category', 'text-sm font-bold text-gray-500', 'text-blue-500', 'items-center gap-1')
                for key, label_key in QUIZ_CATEGORY_OPTIONS:
                    color = 'primary' if state.quiz_category == key else 'grey'
                    ui.button(t(label_key), on_click=lambda _, c=key: set_quiz_category(c)) \
                        .props(f'outline color={color} dense')
            with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                icon_label(t('quiz_scope'), 'filter_alt', 'text-sm font-bold text-gray-500', 'text-blue-500', 'items-center gap-1')
                for key, label_key in QUIZ_SCOPE_OPTIONS:
                    color = 'primary' if state.quiz_scope == key else 'grey'
                    ui.button(t(label_key), on_click=lambda _, s=key: set_quiz_scope(s)) \
                        .props(f'outline color={color} dense')
            with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                icon_label(t('quiz_format'), 'view_module', 'text-sm font-bold text-gray-500', 'text-blue-500', 'items-center gap-1')
                for key, label_key in QUIZ_FORMAT_OPTIONS:
                    color = 'primary' if state.quiz_format == key else 'grey'
                    ui.button(t(label_key), on_click=lambda _, f=key: set_quiz_format(f)) \
                        .props(f'outline color={color} dense')
            ui.button(t('quiz_next'), icon='refresh', on_click=next_quiz_from_button) \
                .props('outline color=primary') \
                .classes('w-full' if is_mobile_ui() else 'self-start')

            with ui.card().classes('wa-light-fallback w-full p-4 gap-4' if is_mobile_ui() else 'wa-light-fallback w-full p-6 gap-4'):
                ui.label(question).classes('text-lg font-bold text-gray-800' if is_mobile_ui() else 'text-xl font-bold text-gray-800')
                if description:
                    ui.markdown(description).classes('text-gray-700 text-base' if is_mobile_ui() else 'text-gray-700 text-lg')
                if image:
                    ui.image(image).classes('w-full shadow-md border rounded' if is_mobile_ui() else 'w-56 shadow-md border rounded')

                with ui.column().classes('w-full gap-2 mt-2'):
                    for option_key in quiz['options']:
                        option = lookup.get(option_key) if quiz.get('option_mode') != 'value' else None
                        is_selected = quiz.get('selected_key') == option_key
                        is_answer = quiz_answer_option(quiz) == option_key
                        if quiz.get('answered') and is_answer:
                            color = 'green'
                        elif quiz.get('answered') and is_selected:
                            color = 'red'
                        else:
                            color = 'blue' if is_selected else 'white'
                        text_color = 'white' if color in ['green', 'red', 'blue'] else 'grey-9'
                        if quiz.get('option_mode') == 'value':
                            label = quiz.get('option_labels', {}).get(option_key, str(option_key))
                            option_image = quiz.get('option_images', {}).get(option_key)
                            if option_image:
                                border_class = 'border-green-500 bg-green-50' if quiz.get('answered') and is_answer else ('border-red-500 bg-red-50' if quiz.get('answered') and is_selected else 'border-gray-200 bg-white')
                                with ui.column().classes(f'wa-light-fallback w-full gap-2 rounded border p-2 {border_class}'):
                                    ui.image(option_image).classes('w-40 shadow-sm border rounded bg-white self-center').style('aspect-ratio: 3 / 2; object-fit: cover;')
                                    ui.button(label or t('quiz_select_option'), on_click=lambda _, key=option_key: select_quiz_option(key)) \
                                        .props(f'color={color} text-color={text_color}') \
                                        .classes('w-full')
                            else:
                                ui.button(label, on_click=lambda _, key=option_key: select_quiz_option(key)) \
                                    .props(f'color={color} text-color={text_color}') \
                                    .classes('w-full justify-start text-left whitespace-normal')
                        elif option:
                            ui.button(get_localized_text(option['names']), on_click=lambda _, key=option_key: select_quiz_option(key)) \
                                .props(f'color={color} text-color={text_color}') \
                                .classes('w-full justify-start text-left')

                if quiz.get('answered') and answer:
                    correct = quiz.get('selected_key') == quiz_answer_option(quiz)
                    message = t('quiz_time_up') if quiz.get('timed_out') else (t('quiz_correct') if correct else t('quiz_wrong'))
                    badge_color = 'green' if correct else 'red'
                    with ui.row().classes('items-center gap-3 mt-4'):
                        ui.icon('check_circle' if correct else 'cancel').classes('text-green-600' if correct else 'text-red-600')
                        ui.badge(message, color=badge_color).classes('text-base px-3 py-2')
                        ui.label(get_localized_text(answer['names'])).classes('text-lg font-bold')
                    ui.button(t('quiz_detail'), icon='open_in_new', on_click=open_quiz_answer_detail) \
                        .classes('bg-[#1a2332] text-white px-4 py-2 mt-2')

# ========================================
# 5. 比較画面
# ========================================
with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as compare_screen:
    header_container_compare = ui.column().classes('w-full p-0 m-0')
    compare_content = ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center')

    def set_compare_country(side, label):
        label_to_key, _ = country_option_maps()
        key = label_to_key.get(label)
        if side == 'left':
            state.compare_left_key = key
        else:
            state.compare_right_key = key
        refresh_compare_view()

    def render_compare_column(country):
        if not country:
            return
        with ui.card().classes('w-full p-5 gap-3'):
            render_flag_frame(country, 'w-full border rounded bg-gray-50')
            ui.label(get_localized_text(country['names'])).classes('text-2xl font-bold text-[#1a2332]')
            ui.label(country.get('names', {}).get('en', '')).classes('text-sm text-gray-400 font-serif italic')
            ui.separator()
            rows = [
                (t('labels', 'capital'), get_localized_text(country.get('capital', '-'))),
            ]
            compare_period = period_label(country)
            if compare_period:
                rows.append((period_field_label(country), compare_period))
            rows.extend(profile_rows(country))
            product_value = area_population_product_value(country)
            if product_value:
                rows.append((area_population_product_label(), product_value))
            rows.extend([
                (t('labels', 'region'), region_label(country.get('region', '-'))),
                (t('labels', 'tags'), ', '.join(tag_label(tag) for tag in country.get('tags', []))),
            ])
            for label, value in rows:
                info_field(label, value, country_field_icon(label), 'text-base text-gray-800')
            icon_label(t('labels', 'desc'), 'article', 'text-xs font-bold text-gray-400 uppercase', 'text-blue-400', 'items-center gap-1')
            ui.markdown(get_localized_text(country.get('desc', {}))).classes('text-gray-700 leading-relaxed')
            ui.button(t('view_detail'), icon='open_in_new', on_click=lambda c=country: open_country_detail(c)) \
                .props('outline color=primary') \
                .classes('self-start')

    def refresh_compare_view():
        render_header(header_container_compare)
        update_mode_classes(
            compare_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        compare_content.clear()
        data = get_data()
        countries = public_country_list(data)
        if len(countries) < 2:
            return
        lookup = public_countries_by_key(data)
        label_to_key, key_to_label = country_option_maps(data)
        keys = list(lookup.keys())
        if not state.compare_left_key or state.compare_left_key not in lookup:
            state.compare_left_key = keys[0]
        if not state.compare_right_key or state.compare_right_key not in lookup:
            state.compare_right_key = keys[1]

        with compare_content:
            page_heading(t('compare_title'), 'compare_arrows')
            with ui.row().classes('w-full gap-3 flex-col' if is_mobile_ui() else 'w-full gap-4 items-center'):
                ui.select(list(label_to_key.keys()), value=key_to_label.get(state.compare_left_key), label=t('compare_left'), on_change=lambda e: set_compare_country('left', e.value)) \
                    .classes('w-full bg-white' if is_mobile_ui() else 'w-1/2 bg-white')
                ui.select(list(label_to_key.keys()), value=key_to_label.get(state.compare_right_key), label=t('compare_right'), on_change=lambda e: set_compare_country('right', e.value)) \
                    .classes('w-full bg-white' if is_mobile_ui() else 'w-1/2 bg-white')
            with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-4'):
                render_compare_column(lookup.get(state.compare_left_key))
                render_compare_column(lookup.get(state.compare_right_key))

# ========================================
# 6. 年表画面
# ========================================
with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as timeline_screen:
    header_container_timeline = ui.column().classes('w-full p-0 m-0')
    timeline_content = ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center')

    def set_timeline_group(period_key):
        state.timeline_group = period_key
        state.timeline_page = 1
        refresh_timeline_view()

    def change_timeline_page(page):
        state.timeline_page = page
        refresh_timeline_view()

    def render_timeline_page_button(icon, label_key, target_page, disabled=False):
        props = 'flat round color=grey disable' if disabled else 'flat round color=primary'
        ui.button(icon=icon, on_click=lambda p=target_page: change_timeline_page(p)) \
            .props(props) \
            .tooltip(t(label_key))

    def refresh_timeline_view():
        render_header(header_container_timeline)
        update_mode_classes(
            timeline_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        timeline_content.clear()
        data = get_data()
        period_keys = ['period_ancient', 'period_medieval', 'period_modern', 'period_contemporary', 'period_other']
        grouped = {key: [] for key in period_keys}
        timeline_countries = [country for country in public_country_list(data) if country.get('period')]
        for country in timeline_countries:
            grouped[timeline_period(country)].append(country)
        for countries in grouped.values():
            countries.sort(key=timeline_sort_key)
        if state.timeline_group not in grouped or not grouped[state.timeline_group]:
            state.timeline_group = next((key for key in period_keys if grouped[key]), 'period_other')

        selected_countries = grouped.get(state.timeline_group, [])
        total_count = len(selected_countries)
        total_pages = max(1, (total_count + state.timeline_items_per_page - 1) // state.timeline_items_per_page)
        state.timeline_page = max(1, min(state.timeline_page, total_pages))
        start_index = (state.timeline_page - 1) * state.timeline_items_per_page
        end_index = min(start_index + state.timeline_items_per_page, total_count)
        display_list = selected_countries[start_index:end_index]

        with timeline_content:
            page_heading(t('timeline_title'), 'timeline')
            with ui.row().classes('w-full gap-2 flex-wrap'):
                for period_key in period_keys:
                    count = len(grouped[period_key])
                    color = 'primary' if state.timeline_group == period_key else 'grey'
                    ui.button(f'{t(period_key)} ({count})', on_click=lambda _, key=period_key: set_timeline_group(key)) \
                        .props(f'outline color={color} dense')
            ui.label(f'{t(state.timeline_group)}: {start_index + 1 if total_count else 0}-{end_index} / {total_count} {t("hits")}') \
                .classes('text-sm text-gray-500 font-bold')
            if not display_list:
                ui.label(t('no_result')).classes('w-full text-center text-gray-500 py-8')
            with ui.column().classes('w-full gap-3'):
                for country in display_list:
                    with ui.card().classes('w-full p-4 cursor-pointer hover:shadow-md transition') as card:
                        card.on('click', lambda _, x=country: open_country_detail(x))
                        with ui.row().classes('items-start gap-3 no-wrap'):
                            render_flag_frame(country, 'w-24 flex-shrink-0 shadow border rounded')
                            with ui.column().classes('gap-1 flex-grow'):
                                with ui.row().classes('gap-2 items-center flex-wrap'):
                                    ui.label(get_localized_text(country['names'])).classes('text-lg font-bold text-gray-800')
                                    ui.badge(t('tabs', country.get('type', 'Present')), color='green' if country.get('type') == 'Present' else 'orange')
                                timeline_period_text = period_label(country)
                                if timeline_period_text:
                                    ui.label(timeline_period_text).classes('text-xs font-bold text-orange-700')
                                ui.label(region_label(country.get('region', ''))).classes('text-sm text-gray-500')
                                ui.label(first_sentence(get_localized_text(country.get('desc', {})))).classes('text-sm text-gray-600 line-clamp-2')
            if total_pages > 1:
                prev_disabled = state.timeline_page <= 1
                next_disabled = state.timeline_page >= total_pages
                with ui.row().classes('w-full justify-center items-center gap-2 mt-3 flex-wrap'):
                    render_timeline_page_button('first_page', 'first_page', 1, prev_disabled)
                    render_timeline_page_button('chevron_left', 'prev_page', state.timeline_page - 1, prev_disabled)
                    ui.label(f'{state.timeline_page} / {total_pages} {t("page_unit")}') \
                        .classes('px-3 py-2 text-gray-700 font-bold')
                    render_timeline_page_button('chevron_right', 'next_page', state.timeline_page + 1, next_disabled)
                    render_timeline_page_button('last_page', 'last_page', total_pages, next_disabled)

# ========================================
# 7. 地図ビュー
# ========================================
with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as map_screen:
    header_container_map = ui.column().classes('w-full p-0 m-0')
    map_content = ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center')

    def set_map_country_by_label(label):
        label_to_key, _ = country_option_maps()
        state.map_country_key = label_to_key.get(label)
        refresh_map_view()

    def refresh_map_view():
        render_header(header_container_map)
        update_mode_classes(
            map_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        map_content.clear()
        data = get_data()
        lookup = public_countries_by_key(data)
        label_to_key, key_to_label = country_option_maps(data)
        if not lookup:
            return
        if not state.map_country_key or state.map_country_key not in lookup:
            state.map_country_key = country_key(state.selected_country) if state.selected_country else next(iter(lookup.keys()))
        country = lookup[state.map_country_key]
        map_note_text = map_target_note(country)
        with map_content:
            page_heading(t('map_title'), 'map')
            ui.select(list(label_to_key.keys()), value=key_to_label.get(state.map_country_key), label=t('map'), on_change=lambda e: set_map_country_by_label(e.value)) \
                .classes('w-full bg-white')
            with ui.card().classes('w-full p-5 gap-4'):
                with ui.row().classes('w-full justify-between items-center flex-wrap gap-2'):
                    with ui.column().classes('gap-1'):
                        ui.label(get_localized_text(country['names'])).classes('text-2xl font-bold text-[#1a2332]')
                        if map_note_text:
                            ui.label(map_note_text).classes('text-sm text-gray-500')
                    ui.button(t('view_detail'), icon='open_in_new', on_click=lambda c=country: open_country_detail(c)) \
                        .props('outline color=primary')
                render_map_embed(country, height=520)
                ui.link('Google Maps', country_maps_url(country), new_tab=True).classes('text-green-700 font-bold')

# ========================================
# 8. 関連国家ネットワーク
# ========================================
with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as network_screen:
    header_container_network = ui.column().classes('w-full p-0 m-0')
    network_content = ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center')

    def set_network_country_by_label(label):
        label_to_key, _ = country_option_maps()
        state.network_country_key = label_to_key.get(label)
        refresh_network_view()

    def render_network_country_card(country, central=False):
        card_class = 'w-full p-5 border-2 border-blue-500 bg-blue-50' if central else 'w-full p-4 cursor-pointer hover:shadow-md transition'
        with ui.card().classes(card_class) as card:
            if not central:
                card.on('click', lambda _, c=country: set_network_country(c))
            with ui.row().classes('items-center gap-3 no-wrap'):
                render_flag_frame(country, 'w-24 flex-shrink-0 shadow border rounded')
                with ui.column().classes('gap-1 flex-grow'):
                    ui.label(get_localized_text(country['names'])).classes('text-lg font-bold text-[#1a2332]')
                    ui.label(region_label(country.get('region', ''))).classes('text-sm text-gray-500')
                    period_text = period_label(country)
                    if period_text:
                        ui.label(period_text).classes('text-xs font-bold text-orange-700')
                    with ui.row().classes('gap-1 flex-wrap'):
                        for tag in country.get('tags', [])[:3]:
                            tag_chip(tag)

    def refresh_network_view():
        render_header(header_container_network)
        update_mode_classes(
            network_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        network_content.clear()
        data = get_data()
        lookup = public_countries_by_key(data)
        label_to_key, key_to_label = country_option_maps(data)
        if not lookup:
            return
        if not state.network_country_key or state.network_country_key not in lookup:
            state.network_country_key = country_key(state.selected_country) if state.selected_country else next(iter(lookup.keys()))
        country = lookup[state.network_country_key]
        related = related_countries(country, limit=10)
        with network_content:
            page_heading(t('network_title'), 'account_tree')
            ui.select(list(label_to_key.keys()), value=key_to_label.get(state.network_country_key), label=t('network'), on_change=lambda e: set_network_country_by_label(e.value)) \
                .classes('w-full bg-white')
            render_network_country_card(country, central=True)
            with ui.row().classes('w-full justify-center'):
                ui.icon('south', size='2rem').classes('text-blue-400')
            if not related:
                ui.label(t('no_result')).classes('w-full text-center text-gray-500 py-8')
            with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-4'):
                for related_country in related:
                    render_network_country_card(related_country)
            ui.button(t('view_detail'), icon='open_in_new', on_click=lambda c=country: open_country_detail(c)) \
                .props('color=primary') \
                .classes('self-start')

# ========================================
# 9. ユーザー一覧ページ
# ========================================
with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as users_screen:
    header_container_users = ui.column().classes('w-full p-0 m-0')
    users_content = ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center')

    def render_public_user_metric(label, value):
        with ui.column().classes('gap-0 rounded border border-gray-200 bg-gray-50 p-3'):
            ui.label(label).classes('text-xs font-bold text-gray-500')
            ui.label(str(value)).classes('text-xl font-bold text-[#1a2332]')

    def render_public_country_chips(keys, lookup):
        valid_countries = [lookup[key] for key in keys if key in lookup]
        if not valid_countries:
            ui.label(t('no_result')).classes('text-xs text-gray-500')
            return
        with ui.row().classes('w-full gap-2 flex-wrap'):
            for country in valid_countries:
                chip = ui.chip(get_localized_text(country['names'])).props('dense outline color=primary').classes('cursor-pointer')
                chip.on('click', lambda _, c=country: open_country_detail(c))

    def open_public_collection_page(profile, keys, name, kind='collection'):
        state.public_collection_owner = profile.get('username')
        state.public_collection_name = name
        state.public_collection_keys = list(keys or [])
        state.public_collection_kind = kind
        show_screen('public_collection')

    def render_user_friend_controls(profile):
        username = profile.get('username')
        if not username or username == state.current_user:
            return
        status = friend_status(username)
        with ui.row().classes('w-full gap-2 flex-wrap'):
            if status == 'friends':
                ui.button(t('friend_chat'), icon='chat', on_click=lambda _, name=username: open_direct_chat(name)) \
                    .props('outline color=primary dense')
                ui.button(t('friend_remove'), icon='person_remove', on_click=lambda _, name=username: remove_friend(name)) \
                    .props('flat color=negative dense')
            elif status == 'received':
                ui.badge(t('friend_request_received'), color='orange')
                ui.button(t('friend_accept'), icon='person_add', on_click=lambda _, name=username: accept_friend_request(name)) \
                    .props('color=positive dense')
                ui.button(t('friend_reject'), icon='close', on_click=lambda _, name=username: reject_friend_request(name)) \
                    .props('outline color=negative dense')
            elif status == 'sent':
                button = ui.button(t('friend_request_sent'), icon='hourglass_empty').props('outline color=grey dense')
                button.disable()
            else:
                ui.button(t('friend_request_send'), icon='person_add', on_click=lambda _, name=username: send_friend_request(name)) \
                    .props('outline color=primary dense')

    def restore_browser_users_for_list():
        state.public_users_browser_synced = False
        request_browser_backup_restore()
        ui.notify(t('users_restore_browser'), color='info')
        ui.timer(0.8, refresh_users_view, once=True)
        ui.timer(1.8, refresh_users_view, once=True)
        schedule_public_users_browser_sync(2.0, force=True)

    def change_users_page(page):
        state.users_page = page
        refresh_users_view()

    def render_users_page_button(icon, label_key, target_page, disabled=False):
        button = ui.button(icon=icon, on_click=lambda p=target_page: change_users_page(p)) \
            .props(f'flat round dense color={"grey" if disabled else "primary"}') \
            .tooltip(t(label_key))
        if disabled:
            button.disable()

    def render_users_pagination(total_pages):
        if total_pages <= 1:
            return
        prev_disabled = state.users_page <= 1
        next_disabled = state.users_page >= total_pages
        with ui.row().classes('w-full justify-center items-center gap-2 mt-2 flex-wrap'):
            render_users_page_button('first_page', 'first_page', 1, prev_disabled)
            render_users_page_button('chevron_left', 'prev_page', state.users_page - 1, prev_disabled)
            ui.label(f'{state.users_page} / {total_pages} {t("page_unit")}') \
                .classes('px-3 py-2 text-gray-700 font-bold')
            render_users_page_button('chevron_right', 'next_page', state.users_page + 1, next_disabled)
            render_users_page_button('last_page', 'last_page', total_pages, next_disabled)

    def users_favorite_country_label():
        _, key_to_label = country_option_maps()
        return key_to_label.get(state.users_favorite_country_key)

    def set_users_search_keyword(value):
        state.users_search_keyword = str(value or '').strip()
        state.users_page = 1
        refresh_users_view()

    def set_users_favorite_country(label):
        label_to_key, _ = country_option_maps()
        state.users_favorite_country_key = label_to_key.get(label) if label else None
        state.users_page = 1
        refresh_users_view()

    def clear_users_filters():
        state.users_search_keyword = ''
        state.users_favorite_country_key = None
        state.users_page = 1
        refresh_users_view()

    def filter_public_user_profiles(profiles):
        keyword = str(state.users_search_keyword or '').strip().casefold()
        favorite_key = state.users_favorite_country_key
        if favorite_key and favorite_key not in public_countries_by_key():
            favorite_key = None
            state.users_favorite_country_key = None
        filtered = list(profiles)
        if keyword:
            filtered = [
                profile for profile in filtered
                if keyword in str(profile.get('username', '')).casefold()
            ]
        if favorite_key:
            filtered = [
                profile for profile in filtered
                if favorite_key in profile.get('favorites', [])
            ]
        return filtered

    def refresh_users_view():
        restore_started = False
        if not state.users_browser_restore_requested:
            state.users_browser_restore_requested = True
            restore_started = True
            request_browser_backup_restore()
            ui.timer(0.8, refresh_users_view, once=True)
            schedule_public_users_browser_sync(1.6, force=True)
        render_header(header_container_users)
        update_mode_classes(
            users_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        users_content.clear()
        lookup = public_countries_by_key()
        with users_content:
            page_heading(t('users_title'), 'groups')
            with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                ui.label(t('public_users_notice')).classes('text-sm text-gray-500')
                ui.button(t('users_restore_browser'), icon='cloud_sync', on_click=restore_browser_users_for_list) \
                    .props('outline color=primary dense')
            raw_profiles = public_user_profiles()
            with ui.card().classes('w-full p-4 gap-3 bg-blue-50 border border-blue-100'):
                icon_label(t('users_search'), 'person_search', 'text-sm font-bold text-blue-800', 'text-blue-600', 'items-center gap-1')
                label_to_key, _ = country_option_maps()
                country_options = list(label_to_key.keys())
                with ui.row().classes('w-full gap-2 items-end flex-col' if is_mobile_ui() else 'w-full gap-2 items-end'):
                    ui.input(
                        label=t('users_search'),
                        placeholder=t('users_search_placeholder'),
                        value=state.users_search_keyword,
                        on_change=lambda e: set_users_search_keyword(e.value),
                    ).props('outlined dense clearable').classes('w-full' if is_mobile_ui() else 'flex-grow')
                    ui.select(
                        country_options,
                        value=users_favorite_country_label(),
                        label=t('favorite_country_filter'),
                        on_change=lambda e: set_users_favorite_country(e.value),
                        clearable=True,
                    ).props('outlined dense use-input input-debounce=0').classes('w-full' if is_mobile_ui() else 'flex-grow')
                    ui.button(t('clear_user_filters'), icon='filter_alt_off', on_click=clear_users_filters) \
                        .props('outline color=primary dense') \
                        .classes('w-full' if is_mobile_ui() else '')
            profiles = filter_public_user_profiles(raw_profiles)
            if raw_profiles and not state.public_users_browser_synced:
                schedule_public_users_browser_sync(2.4 if restore_started else 0.6)
            total_count = len(profiles)
            total_pages = max(1, (total_count + state.users_items_per_page - 1) // state.users_items_per_page)
            state.users_page = max(1, min(state.users_page, total_pages))
            start_index = (state.users_page - 1) * state.users_items_per_page
            end_index = min(start_index + state.users_items_per_page, total_count)
            display_profiles = profiles[start_index:end_index]
            if not profiles:
                ui.label(t('no_user_search_results') if raw_profiles else t('no_users')).classes('text-gray-500')
                return
            icon_label(f'{t("users_count")}: {start_index + 1}-{end_index} / {total_count}', 'manage_search', 'text-sm text-gray-500 font-bold', 'text-blue-500', 'items-center gap-1')
            with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-4'):
                for profile in display_profiles:
                    with ui.card().classes('w-full p-5 gap-4'):
                        with ui.row().classes('w-full items-center gap-3 no-wrap'):
                            render_avatar_image(
                                profile.get('avatar_url'),
                                profile.get('avatar', {}),
                                'w-16 h-16 rounded-full border shadow bg-white flex-shrink-0',
                                icon_size='4rem',
                                icon_classes='text-gray-400 flex-shrink-0',
                                live=False,
                            )
                            with ui.column().classes('gap-1 flex-grow'):
                                with ui.row().classes('items-center gap-2 flex-wrap'):
                                    ui.label(display_user_name(profile['username'], profile)) \
                                        .classes('text-xl font-bold') \
                                        .style(f"color: {profile.get('name_color', DEFAULT_NAME_COLOR)};")
                                    if profile['username'] == state.current_user:
                                        ui.badge(t('current_user_badge'), color='green')
                                    if profile.get('battle_wins'):
                                        ui.label(crown_marks(profile['battle_wins'])).classes('text-lg text-yellow-600')
                                if profile.get('last_viewed'):
                                    ui.label(f"{t('last_viewed')}: {profile['last_viewed']}").classes('text-xs text-gray-500')
                        with ui.grid(columns=2).classes('w-full gap-2'):
                            render_public_user_metric(t('viewed_count'), profile['viewed_count'])
                            render_public_user_metric(t('favorite_count'), len(profile['favorites']))
                            render_public_user_metric(t('review_count'), profile['review_count'])
                            render_public_user_metric(t('collections'), profile['collection_count'])
                            render_public_user_metric(t('quiz'), f"{profile['correct']} / {profile['answered']}")
                            render_public_user_metric(t('best_streak'), profile['best_streak'])
                            render_public_user_metric(t('battle_wins'), crown_marks(profile.get('battle_wins', 0)) or '0')
                            render_public_user_metric(t('friends_count'), len(profile.get('friends', [])))
                        render_user_friend_controls(profile)
                        with ui.expansion(f"{t('public_favorites')} ({len(profile['favorites'])})", icon='star').classes('w-full'):
                            ui.button(
                                t('open_collection_page'),
                                icon='open_in_new',
                                on_click=lambda p=profile: open_public_collection_page(p, p['favorites'], t('public_favorites'), 'favorites'),
                            ).props('flat color=primary dense')
                            render_public_country_chips(profile['favorites'], lookup)
                        with ui.expansion(f"{t('public_collections')} ({len(profile['collections'])})", icon='folder').classes('w-full'):
                            if not profile['collections']:
                                ui.label(t('no_collections')).classes('text-xs text-gray-500')
                            for collection in profile['collections']:
                                with ui.column().classes('w-full gap-2 border-t border-gray-200 py-2'):
                                    with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                                        ui.button(
                                            f"{collection['name']} ({len(collection['keys'])})",
                                            icon='folder_open',
                                            on_click=lambda _, p=profile, c=collection: open_public_collection_page(p, c['keys'], c['name'], 'collection'),
                                        ).props('flat color=primary dense')
                                        ui.button(
                                            t('open_collection_page'),
                                            icon='open_in_new',
                                            on_click=lambda _, p=profile, c=collection: open_public_collection_page(p, c['keys'], c['name'], 'collection'),
                                        ).props('outline color=primary dense')
                                    render_public_country_chips(collection['keys'], lookup)
            render_users_pagination(total_pages)

# ========================================
# 10. 公開コレクションページ
# ========================================
with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as public_collection_screen:
    header_container_public_collection = ui.column().classes('w-full p-0 m-0')
    public_collection_content = ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center')

    def render_public_collection_country_card(country):
        with ui.card().classes('w-full p-4 cursor-pointer hover:shadow-md transition') as card:
            card.on('click', lambda _, c=country: open_country_detail(c))
            with ui.row().classes('w-full gap-4 items-center no-wrap'):
                render_flag_frame(country, 'w-28 flex-shrink-0 shadow border rounded')
                with ui.column().classes('gap-2 flex-grow'):
                    ui.label(get_localized_text(country['names'])).classes('text-xl font-bold text-[#1a2332]')
                    period_text = period_label(country)
                    if period_text:
                        ui.label(period_text).classes('text-sm font-bold text-orange-700')
                    ui.label(first_sentence(get_localized_text(country.get('desc', {})))).classes('text-sm text-gray-500 line-clamp-2')
                    with ui.row().classes('gap-1 flex-wrap'):
                        for tag in country.get('tags', [])[:4]:
                            tag_chip(tag)
            with ui.row().classes('w-full justify-end'):
                ui.button(t('view_detail'), icon='open_in_new', on_click=lambda _, c=country: open_country_detail(c)) \
                    .props('flat color=primary dense')

    def refresh_public_collection_view():
        render_header(header_container_public_collection)
        update_mode_classes(
            public_collection_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        public_collection_content.clear()
        lookup = public_countries_by_key()
        owner = state.public_collection_owner or ''
        title = state.public_collection_name or t('public_collection_page')
        keys = state.public_collection_keys if isinstance(state.public_collection_keys, list) else []
        countries = [lookup[key] for key in keys if key in lookup]
        with public_collection_content:
            ui.button(t('back_to_users'), icon='arrow_back', on_click=lambda: show_screen('users')) \
                .props('flat color=primary') \
                .classes('self-start')
            with ui.card().classes('w-full p-5 gap-2'):
                ui.label(title).classes('text-3xl font-bold text-[#1a2332]')
                if owner:
                    ui.label(f'{t("collection_owner")}: {owner}').classes('text-sm text-gray-500')
                ui.label(f'{len(countries)} / {len(keys)}').classes('text-sm font-bold text-gray-600')
            if not countries:
                ui.label(t('no_result')).classes('text-gray-500')
            with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-4'):
                for country in countries:
                    render_public_collection_country_card(country)

# ========================================
# 11. 国力対戦ページ
# ========================================
with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as rankings_screen:
    header_container_rankings = ui.column().classes('w-full p-0 m-0')
    rankings_content = ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center')

    def set_ranking_quiz_category(category):
        state.ranking_quiz_category = category
        refresh_rankings_view()

    def render_ranking_row(rank, profile, value, detail):
        with ui.card().classes('w-full p-4 gap-3'):
            with ui.row().classes('w-full items-center gap-3 no-wrap'):
                ui.label(f'{rank}').classes('w-10 h-10 rounded-full bg-blue-100 text-blue-800 font-bold flex items-center justify-center')
                render_avatar_image(
                    profile.get('avatar_url'),
                    profile.get('avatar', {}),
                    'w-12 h-12 rounded-full border shadow bg-white flex-shrink-0',
                    icon_size='3rem',
                    icon_classes='text-gray-400 flex-shrink-0',
                    live=False,
                )
                with ui.column().classes('gap-1 flex-grow'):
                    ui.label(display_user_name(profile['username'], profile)) \
                        .classes('text-lg font-bold') \
                        .style(f"color: {profile.get('name_color', DEFAULT_NAME_COLOR)};")
                    ui.label(detail).classes('text-xs text-gray-500')
                ui.label(str(value)).classes('text-2xl font-bold text-[#1a2332]')

    def refresh_rankings_view():
        render_header(header_container_rankings)
        update_mode_classes(
            rankings_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        rankings_content.clear()
        profiles = public_user_profiles()
        valid_categories = {key for key, _ in QUIZ_RANKING_CATEGORIES}
        if state.ranking_quiz_category not in valid_categories:
            state.ranking_quiz_category = 'overall'
        quiz_profiles = quiz_ranking_profiles(state.ranking_quiz_category)
        category_label = quiz_ranking_category_label(state.ranking_quiz_category)
        current_user = get_current_user_record()
        can_view_wins = battle_is_user_eligible(user=current_user)
        with rankings_content:
            ui.label(t('rankings_title')).classes('text-3xl font-bold text-[#1a2332]')
            with ui.card().classes('w-full p-5 gap-3'):
                ui.label(t('ranking_category_title').format(category=category_label)).classes('text-xl font-bold text-[#1a2332]')
                with ui.row().classes('w-full gap-2 flex-wrap'):
                    for category, label_key in QUIZ_RANKING_CATEGORIES:
                        color = 'primary' if state.ranking_quiz_category == category else 'grey'
                        ui.button(t(label_key), on_click=lambda _, c=category: set_ranking_quiz_category(c)) \
                            .props(f'outline color={color} dense')
                if not quiz_profiles:
                    ui.label(t('no_ranking_data')).classes('text-gray-500')
                for rank, profile in enumerate(quiz_profiles[:20], start=1):
                    render_ranking_row(
                        rank,
                        profile,
                        profile.get('ranking_correct', 0),
                        f"{t('answered_count')}: {profile.get('ranking_answered', 0)} / {t('best_streak')}: {profile.get('ranking_best_streak', 0)}",
                    )
            with ui.card().classes('w-full p-5 gap-3'):
                ui.label(t('battle_win_ranking')).classes('text-xl font-bold text-[#1a2332]')
                if not can_view_wins:
                    ui.label(t('ranking_locked')).classes('font-bold text-gray-700')
                    ui.label(t('ranking_locked_hint')).classes('text-sm text-gray-500')
                    return
                win_profiles = sorted(
                    [profile for profile in profiles if profile.get('all_viewed')],
                    key=lambda profile: (-int(profile.get('battle_wins', 0) or 0), profile.get('username', '').lower()),
                )
                if not win_profiles:
                    ui.label(t('no_users')).classes('text-gray-500')
                for rank, profile in enumerate(win_profiles[:20], start=1):
                    render_ranking_row(
                        rank,
                        profile,
                        crown_marks(profile.get('battle_wins', 0)) or '0',
                        f"{t('viewed_count')}: {profile.get('viewed_count', 0)}",
                    )

with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as social_screen:
    header_container_social = ui.column().classes('w-full p-0 m-0')
    social_content = ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center')

    def select_social_chat(chat_id):
        state.social_selected_chat_id = chat_id
        refresh_social_view()

    def render_request_list(user_data):
        current = state.current_user
        incoming = [
            request for request in user_data.setdefault('friend_requests', [])
            if request.get('to') == current
        ]
        with ui.card().classes('w-full p-5 gap-3'):
            ui.label(t('friend_requests')).classes('text-xl font-bold text-[#1a2332]')
            if not incoming:
                ui.label(t('no_friend_requests')).classes('text-gray-500')
            for request in incoming:
                sender = request.get('from')
                with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                    ui.label(sender).classes('font-bold text-gray-800')
                    with ui.row().classes('gap-2'):
                        ui.button(t('friend_accept'), icon='person_add', on_click=lambda _, name=sender: accept_friend_request(name)) \
                            .props('color=positive dense')
                        ui.button(t('friend_reject'), icon='close', on_click=lambda _, name=sender: reject_friend_request(name)) \
                            .props('outline color=negative dense')

    def render_friend_list(user_data):
        user = get_current_user_record(user_data)
        friends = ensure_friend_list(user) if user else []
        with ui.card().classes('w-full p-5 gap-3'):
            ui.label(t('friends')).classes('text-xl font-bold text-[#1a2332]')
            if not friends:
                ui.label(t('no_friends')).classes('text-gray-500')
            for friend in friends:
                with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                    ui.label(friend).classes('font-bold text-gray-800')
                    with ui.row().classes('gap-2'):
                        ui.button(t('friend_chat'), icon='chat', on_click=lambda _, name=friend: open_direct_chat(name)) \
                            .props('outline color=primary dense')
                        ui.button(t('friend_remove'), icon='person_remove', on_click=lambda _, name=friend: remove_friend(name)) \
                            .props('flat color=negative dense')

    def render_group_creator():
        with ui.card().classes('w-full p-5 gap-3'):
            ui.label(t('group_chat')).classes('text-xl font-bold text-[#1a2332]')
            group_name_input = ui.input(label=t('group_name')).props('outlined dense').classes('w-full')
            group_members_input = ui.input(label=t('group_members'), placeholder=t('group_members_hint')).props('outlined dense').classes('w-full')
            ui.button(
                t('create_group_chat'),
                icon='group_add',
                on_click=lambda: create_group_chat(group_name_input.value, group_members_input.value),
            ).props('color=primary')

    def render_chat_list(chats):
        with ui.card().classes('w-full p-5 gap-3'):
            ui.label(t('direct_chat')).classes('text-xl font-bold text-[#1a2332]')
            if not chats:
                ui.label(t('chat_select')).classes('text-gray-500')
            for chat in chats:
                selected = chat.get('id') == state.social_selected_chat_id
                color = 'primary' if selected else 'grey'
                ui.button(
                    social_chat_title(chat),
                    icon='forum' if chat.get('type') == 'group' else 'chat',
                    on_click=lambda _, chat_id=chat.get('id'): select_social_chat(chat_id),
                ).props(f'outline color={color}').classes('w-full justify-start')

    def render_selected_chat(chats):
        chat = next((item for item in chats if item.get('id') == state.social_selected_chat_id), None)
        if not chat and chats:
            chat = chats[0]
            state.social_selected_chat_id = chat.get('id')
        with ui.card().classes('w-full p-5 gap-4'):
            if not chat:
                ui.label(t('chat_select')).classes('text-gray-500')
                return
            ui.label(social_chat_title(chat)).classes('text-2xl font-bold text-[#1a2332]')
            ui.label(', '.join(chat.get('members', []))).classes('text-xs text-gray-500')
            messages = chat.get('messages', [])[-40:]
            if not messages:
                ui.label(t('chat_empty')).classes('text-gray-500')
            with ui.column().classes('w-full gap-2 max-h-96 overflow-y-auto'):
                for message in messages:
                    mine = message.get('user') == state.current_user
                    align = 'items-end' if mine else 'items-start'
                    bubble = 'bg-blue-50 border-blue-200' if mine else 'bg-gray-50 border-gray-200'
                    with ui.column().classes(f'w-full {align} gap-1'):
                        ui.label(f"{message.get('user')} / {format_timestamp(message.get('timestamp'))}").classes('text-xs text-gray-400')
                        ui.label(message.get('text', '')).classes(f'max-w-full rounded border px-3 py-2 text-sm {bubble}')
            chat_input = ui.input(label=t('chat_message')).props('outlined dense').classes('w-full')
            ui.button(t('chat_send'), icon='send', on_click=lambda: send_social_chat_message(chat.get('id'), chat_input.value)) \
                .props('color=primary')

    def refresh_social_view():
        render_header(header_container_social)
        update_mode_classes(
            social_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        social_content.clear()
        user_data = load_user_data()
        snapshot = social_activity_snapshot(user_data=user_data)
        state.social_last_signature = social_activity_signature(snapshot)
        chats = current_user_chats(user_data)
        with social_content:
            ui.label(t('friends_title')).classes('text-3xl font-bold text-[#1a2332]')
            with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-4'):
                with ui.column().classes('w-full gap-4'):
                    render_request_list(user_data)
                    render_friend_list(user_data)
                    render_group_creator()
                    render_chat_list(chats)
                render_selected_chat(chats)

def poll_social_updates():
    if not state.current_user or is_current_user_guest():
        return
    snapshot = social_activity_snapshot()
    signature = social_activity_signature(snapshot)
    if state.social_notify_user != state.current_user or state.social_notify_snapshot is None:
        state.social_notify_user = state.current_user
        state.social_notify_snapshot = snapshot
        state.social_last_signature = signature
        return
    changed = signature != state.social_last_signature
    events = social_notification_events(state.social_notify_snapshot, snapshot)
    added_notifications = store_notification_events(events)
    for event in added_notifications[:4]:
        show_social_action_notification(event['message'], event.get('chat_id'), event.get('id'))
    state.social_notify_snapshot = snapshot
    if added_notifications and notification_drawer.value:
        refresh_notification_content()
    if changed and social_screen.visible:
        refresh_social_view()
    elif changed:
        state.social_last_signature = signature
    if changed and users_screen.visible:
        refresh_users_view()

ui.timer(8.0, poll_social_updates)

with ui.column().classes('wa-battle-surface w-full min-h-screen bg-gray-50 gap-0') as battle_screen:
    header_container_battle = ui.column().classes('w-full p-0 m-0')
    battle_content = ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center')
    battle_countdown_label = {'component': None}

    def render_hp_bar(label, hp, max_hp=BATTLE_MAX_HP, detail=''):
        with ui.column().classes('w-full gap-1'):
            ui.label(f'{label}: {t("battle_hp")} {format_battle_number(hp)} / {format_battle_number(max_hp)}').classes('text-sm font-bold text-gray-700')
            if detail:
                ui.label(detail).classes('text-xs font-bold text-gray-500')
            ui.linear_progress(value=max(0, min(1, hp / max_hp if max_hp else 0))).props('color=red')

    def render_battle_help():
        help_data = battle_help_labels()
        with ui.card().classes('w-full p-0 overflow-hidden'):
            with ui.expansion(help_data['title'], icon='help_outline').classes('w-full p-2'):
                ui.label(help_data['quick_title']).classes('text-xl font-bold text-[#1a2332] px-3 pt-3')
                ui.label(help_data['quick_intro']).classes('text-sm text-gray-600 px-3')
                with ui.grid(columns=1 if is_mobile_ui() else 4).classes('w-full gap-3 p-3'):
                    for icon, title, body in help_data['quick_steps']:
                        with ui.column().classes('w-full gap-2 rounded border border-blue-100 bg-blue-50 p-3'):
                            ui.icon(icon, size='1.7rem').classes('text-blue-600')
                            ui.label(title).classes('text-sm font-bold text-[#1a2332]')
                            ui.label(body).classes('text-xs text-gray-700 leading-relaxed')
                mock = help_data['mock']
                with ui.column().classes('wa-light-fallback w-full gap-3 rounded border border-gray-200 bg-white p-4 mx-3 mb-3'):
                    ui.label(mock['hand']).classes('text-base font-bold text-[#1a2332]')
                    ui.select(['Player A', 'Player B', 'Player C'], value='Player B', label=mock['target']).props('outlined dense readonly').classes('w-full max-w-sm')
                    with ui.grid(columns=1 if is_mobile_ui() else 3).classes('w-full gap-3'):
                        with ui.column().classes('gap-2 rounded border-2 border-blue-500 bg-blue-50 p-3'):
                            ui.checkbox(value=True).props('dense')
                            ui.label(mock['attack']).classes('text-xs font-bold text-blue-700')
                            ui.label('Country Card').classes('font-bold text-[#1a2332]')
                        with ui.column().classes('gap-2 rounded border border-gray-200 bg-gray-50 p-3'):
                            ui.checkbox(value=False).props('dense')
                            ui.label(mock['defense']).classes('text-xs font-bold text-gray-600')
                            ui.label('Country Card').classes('font-bold text-[#1a2332]')
                        with ui.column().classes('gap-2 rounded border border-gray-200 bg-gray-50 p-3'):
                            ui.checkbox(value=False).props('dense')
                            ui.label(mock['defense']).classes('text-xs font-bold text-gray-600')
                            ui.label('Country Card').classes('font-bold text-[#1a2332]')
                    with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                        ui.button(mock['surrender'], icon='flag').props('outline color=negative dense')
                        ui.button(mock['redraw'], icon='refresh').props('outline color=primary dense')
                        ui.button(mock['submit'], icon='sports_martial_arts').props('color=primary dense')
                with ui.expansion(help_data['detail_title'], icon='menu_book').classes('w-full px-3 pb-3'):
                    ui.label(help_data['detail_intro']).classes('text-sm text-gray-600 pb-2')
                    with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-4'):
                        for section_title, items in help_data['sections']:
                            with ui.column().classes('wa-light-fallback w-full gap-2 rounded border border-gray-200 bg-white p-4'):
                                ui.label(section_title).classes('text-base font-bold text-[#1a2332]')
                                for item in items:
                                    with ui.row().classes('w-full items-start gap-2 no-wrap'):
                                        ui.icon('circle', size='0.45rem').classes('text-blue-500 mt-2 flex-shrink-0')
                                        ui.label(item).classes('text-sm text-gray-700 leading-relaxed whitespace-normal')

    def render_sengoku_boss_panel(user):
        if not state.sengoku_mode or not user or not sengoku_is_user_eligible(user=user):
            return
        clears = normalize_sengoku_boss_clears(user.get('sengoku_boss_clears', []))
        with ui.card().classes('wa-boss-card w-full p-5 gap-4 border border-purple-200 bg-purple-50'):
            with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                ui.label('戦国ボス戦').classes('text-2xl font-black text-purple-900')
                ui.badge(f'{len(clears)} / {len(sengoku_boss_definitions())}', color='purple')
            ui.label('過去に存在した巨大国家を冠した8体のボスを、古い時代から順番に撃破していきます。全撃破でスタッフロールが流れます。') \
                .classes('text-sm font-bold text-purple-800')
            with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-3'):
                for index, boss in enumerate(sengoku_boss_definitions(), start=1):
                    unlocked = sengoku_boss_is_unlocked(user, boss['id'])
                    cleared = sengoku_boss_is_cleared(user, boss['id'])
                    visible = unlocked or cleared
                    with ui.column().classes('wa-light-fallback w-full gap-2 rounded border border-purple-200 bg-white p-3'):
                        with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                            boss_name = localized_boss_text(boss, 'name') if visible else 'シークレット'
                            ui.label(f"{index}. {boss_name}").classes('font-black text-[#1a2332]')
                            if cleared:
                                ui.badge('撃破済み', color='green')
                            elif unlocked:
                                ui.badge('挑戦可能', color='purple')
                            else:
                                ui.badge('未解放', color='grey')
                        boss_summary = localized_boss_text(boss, 'summary') if visible else 'このボスの情報はまだ伏せられています。'
                        ui.label(boss_summary).classes('text-xs text-gray-600 leading-relaxed')
                        button = ui.button(
                            '再挑戦' if cleared else ('挑戦' if unlocked else '未解放'),
                            icon='sports_martial_arts',
                            on_click=lambda _, boss_id=boss['id']: create_sengoku_boss_battle(boss_id),
                        ).props('color=purple dense' if unlocked else 'outline color=grey dense')
                        if not unlocked:
                            button.disable()

    def render_battle_card(key, lookup, room=None):
        required_count = ensure_battle_operation_required_count(room) if room is not None else None
        selected_count = len(state.battle_selected_keys or set())

        def limit_checkbox(checkbox, selected):
            if required_count and not selected and selected_count >= required_count:
                checkbox.disable()
                checkbox.tooltip(t('battle_operation_too_many').format(count=required_count))

        if key == BATTLE_BOMB_CARD:
            country = battle_bomb_cover_country(room, lookup)
            selected = key in state.battle_selected_keys
            with ui.column().classes('wa-light-fallback gap-2 rounded border border-gray-200 bg-white p-3'):
                with ui.row().classes('w-full items-center gap-2 no-wrap'):
                    checkbox = ui.checkbox(value=selected, on_change=lambda e, k=key: toggle_battle_card(k, e.value)).props('dense')
                    limit_checkbox(checkbox, selected)
                    label = get_localized_text(country.get('names', {})) if country else battle_card_display_name(key, lookup, room)
                    ui.label(label).classes('font-bold text-[#1a2332] text-sm')
                if country:
                    render_flag_frame(country, 'w-full rounded border border-gray-200', 'w-full h-full object-cover')
            return
        if is_battle_special_card(key):
            hp_limit = battle_team_hp_limit(room) if room and room.get('mode') == TEAM_MODE else BATTLE_MAX_HP
            damage = battle_special_card_damage(key, hp_limit)
            heal = battle_special_card_heal(key, hp_limit)
            selected = key in state.battle_selected_keys
            is_bomb = BATTLE_SPECIAL_CARDS.get(key, {}).get('bomb')
            card_classes = 'gap-2 rounded border p-3'
            card_classes += ' border-pink-500 bg-pink-100 shadow-lg' if is_bomb else ' border-red-300 bg-red-50'
            with ui.column().classes(card_classes):
                with ui.row().classes('w-full items-center gap-2 no-wrap'):
                    if is_battle_playable_special_card(key):
                        checkbox = ui.checkbox(value=selected, on_change=lambda e, k=key: toggle_battle_card(k, e.value)).props('dense')
                        limit_checkbox(checkbox, selected)
                    ui.icon('priority_high' if is_bomb else 'warning').classes('text-pink-700' if is_bomb else 'text-red-600')
                    ui.label(battle_special_card_label(key)).classes('font-bold text-pink-900 text-sm' if is_bomb else 'font-bold text-red-800 text-sm')
                ui.label(t('battle_special_card')).classes('text-xs font-bold text-red-600')
                if is_bomb:
                    ui.badge(t('battle_bomb_in_your_hand'), color='pink')
                    ui.label(t('battle_bomb_card_hint')).classes('text-xs font-bold text-red-700')
                if damage:
                    ui.label(f"{t('battle_special_damage')}: {format_battle_number(damage)}").classes('text-xs text-red-700')
                if heal:
                    ui.label(f"+{format_battle_number(heal)}").classes('text-xs font-bold text-green-700')
                if BATTLE_SPECIAL_CARDS.get(key, {}).get('destroy_one'):
                    ui.label('手札1枚を道連れ').classes('text-xs font-bold text-red-700')
            return
        country = lookup.get(key)
        if not country:
            return
        selected = key in state.battle_selected_keys
        with ui.column().classes('wa-light-fallback gap-2 rounded border border-gray-200 bg-white p-3'):
            with ui.row().classes('w-full items-center gap-2 no-wrap'):
                checkbox = ui.checkbox(value=selected, on_change=lambda e, k=key: toggle_battle_card(k, e.value)).props('dense')
                limit_checkbox(checkbox, selected)
                label = t('battle_hidden_card_name') if battle_flag_only_active(room) else get_localized_text(country['names'])
                ui.label(label).classes('font-bold text-[#1a2332] text-sm')
            render_flag_frame(country, 'w-full rounded border border-gray-200', 'w-full h-full object-cover')

    def render_battle_visual_card(card):
        border = 'border-red-300 bg-red-50' if card.get('special') else 'border-gray-200 bg-white'
        fallback = '' if card.get('special') else 'wa-light-fallback '
        with ui.column().classes(f'{fallback}w-28 gap-1 rounded border p-2 {border}'):
            if card.get('flag'):
                ui.image(card.get('flag')).classes('w-full rounded border bg-white').style('aspect-ratio: 3 / 2; object-fit: cover;')
            else:
                ui.icon('warning' if card.get('special') else 'style').classes('text-red-600' if card.get('special') else 'text-blue-600')
            ui.label(card.get('name', '')).classes('text-xs font-bold text-gray-800 whitespace-normal')
            if card.get('special'):
                if card.get('damage'):
                    ui.label(f"-{format_battle_number(card.get('damage', 0))}").classes('text-xs font-bold text-red-700')
                if card.get('heal'):
                    ui.label(f"+{format_battle_number(card.get('heal', 0))}").classes('text-xs font-bold text-green-700')
                if card.get('destroy_one'):
                    ui.label('x1').classes('text-xs font-bold text-red-700')

    def render_battle_crisis_notice(room):
        shield_total = battle_satrapy_shield_total(room)
        if shield_total:
            remaining = battle_satrapy_shields_remaining(room)
            interval = battle_royal_road_interval(room)
            damage_map, broken = battle_satrapy_state(room)
            strength = battle_satrapy_shield_strength(room)
            with ui.card().classes('w-full p-5 gap-2 border-2 border-amber-400 bg-amber-50'):
                ui.label('属州シールド').classes('text-2xl font-black text-amber-900')
                ui.label(f'残り {remaining} / {shield_total} 州。各州は対応する地域共鳴3回で崩れ、崩れた州は復旧しません。').classes('text-sm font-bold text-amber-800')
                with ui.row().classes('gap-2 flex-wrap'):
                    for province in battle_satrapy_provinces(room):
                        province_id = province['id']
                        if province_id in broken:
                            ui.badge(f"{battle_satrapy_province_label(province)}: 崩壊", color='red')
                        else:
                            ui.badge(f"{battle_satrapy_province_label(province)}: {damage_map.get(province_id, 0)}/{strength}", color='amber')
                if interval:
                    ui.label(f'王の道: {interval}ターンごとに少量回復。タグや地域が重なる攻撃で遮断できます。').classes('text-sm font-bold text-amber-800')
        if battle_world_war_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-red-500 bg-red-50'):
                ui.label(t('battle_world_war_title')).classes('text-2xl font-black text-red-800')
                ui.label(t('battle_world_war_notice')).classes('text-sm font-bold text-red-700')
        if battle_revolution_active(room):
            with ui.card().classes('w-full p-5 gap-2 text-white border-2 border-yellow-200') \
                .style("background-image: linear-gradient(rgba(127,29,29,0.72), rgba(127,29,29,0.72)), url('/assets/revolution_background.svg'); background-size: cover; background-position: center;"):
                ui.label(t('battle_revolution_title')).classes('text-2xl font-black')
                ui.label(t('battle_revolution_notice')).classes('text-sm font-bold')
        if battle_flag_only_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-indigo-300 bg-indigo-50'):
                ui.label(t('battle_flag_only_title')).classes('text-2xl font-black text-indigo-800')
                ui.label(t('battle_flag_only_notice')).classes('text-sm font-bold text-indigo-700')
        if battle_vatican_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-amber-300 bg-amber-50'):
                ui.label(t('battle_vatican_title')).classes('text-2xl font-black text-amber-800')
                ui.label(t('battle_vatican_notice')).classes('text-sm font-bold text-amber-700')
        if battle_replace_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-cyan-300 bg-cyan-50'):
                ui.label(t('battle_replace_title')).classes('text-2xl font-black text-cyan-800')
                ui.label(t('battle_replace_notice')).classes('text-sm font-bold text-cyan-700')
        if battle_bomb_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-pink-300 bg-pink-50'):
                ui.label(t('battle_bomb_title')).classes('text-2xl font-black text-pink-800')
                ui.label(t('battle_bomb_notice')).classes('text-sm font-bold text-pink-700')
                if battle_find_bomb_holder(room) == state.current_user:
                    ui.badge(t('battle_bomb_in_your_hand'), color='pink')
        if battle_lytton_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-sky-300 bg-sky-50'):
                ui.label(t('battle_lytton_title')).classes('text-2xl font-black text-sky-800')
                ui.label(t('battle_lytton_notice')).classes('text-sm font-bold text-sky-700')
        if battle_damage_surge_active(room) or bool((sengoku_boss_for_room(room) or {}).get('player_damage_surge')):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-purple-400 bg-purple-50'):
                ui.label(t('battle_damage_surge_title')).classes('text-2xl font-black text-purple-800')
                ui.label(t('battle_damage_surge_notice')).classes('text-sm font-bold text-purple-700')
                required = ensure_battle_operation_required_count(room)
                if required:
                    ui.badge(t('battle_operation_required').format(count=required), color='purple')
                    ui.label(t('battle_operation_required_help').format(count=required)).classes('text-sm font-bold text-purple-700')
        if battle_random_target_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-fuchsia-300 bg-fuchsia-50'):
                ui.label(t('battle_random_target_title')).classes('text-2xl font-black text-fuchsia-800')
                ui.label(t('battle_random_target_notice')).classes('text-sm font-bold text-fuchsia-700')
        if battle_ceasefire_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-emerald-300 bg-emerald-50'):
                ui.label(t('battle_ceasefire_title')).classes('text-2xl font-black text-emerald-800')
                ui.label(t('battle_ceasefire_notice')).classes('text-sm font-bold text-emerald-700')
        if battle_command_surge_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-blue-300 bg-blue-50'):
                ui.label(t('battle_command_surge_title')).classes('text-2xl font-black text-blue-800')
                ui.label(t('battle_command_surge_notice')).classes('text-sm font-bold text-blue-700')
        if battle_supply_drop_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-lime-300 bg-lime-50'):
                ui.label(t('battle_supply_drop_title')).classes('text-2xl font-black text-lime-800')
                ui.label(t('battle_supply_drop_notice')).classes('text-sm font-bold text-lime-700')
        if battle_blockade_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-gray-400 bg-gray-100'):
                ui.label(t('battle_blockade_title')).classes('text-2xl font-black text-gray-800')
                ui.label(t('battle_blockade_notice')).classes('text-sm font-bold text-gray-700')

    def render_battle_crisis_notice(room):
        shield_total = battle_satrapy_shield_total(room)
        if shield_total:
            remaining = battle_satrapy_shields_remaining(room)
            reduction_percent = battle_satrapy_shield_reduction_percent(room)
            interval = battle_royal_road_interval(room)
            damage_map, broken = battle_satrapy_state(room)
            strength = battle_satrapy_shield_strength(room)
            with ui.card().classes('w-full p-5 gap-2 border-2 border-amber-400 bg-amber-50'):
                ui.label('属州シールド').classes('text-2xl font-black text-amber-900')
                ui.label(
                    f'残り {remaining} / {shield_total} 州。残っている州1つにつきダメージを10%軽減します'
                    f'（現在 -{reduction_percent}%）。対応する地域共鳴を3回当てると州が崩れ、敵HP上限も下がります。'
                ).classes('text-sm font-bold text-amber-800')
                with ui.row().classes('gap-2 flex-wrap'):
                    for province in battle_satrapy_provinces(room):
                        province_id = province['id']
                        if province_id in broken:
                            ui.badge(f"{battle_satrapy_province_label(province)}: 崩壊", color='red')
                        else:
                            ui.badge(f"{battle_satrapy_province_label(province)}: {damage_map.get(province_id, 0)}/{strength}", color='amber')
                if interval:
                    ui.label(
                        f'王の道: {interval}ターンごとに少量回復します。地域やタグが重なる攻撃で補給を遮断できます。'
                    ).classes('text-sm font-bold text-amber-800')
        if battle_world_war_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-red-500 bg-red-50'):
                ui.label(t('battle_world_war_title')).classes('text-2xl font-black text-red-800')
                ui.label(t('battle_world_war_notice')).classes('text-sm font-bold text-red-700')
        if battle_revolution_active(room):
            with ui.card().classes('w-full p-5 gap-2 text-white border-2 border-yellow-200') \
                .style("background-image: linear-gradient(rgba(127,29,29,0.72), rgba(127,29,29,0.72)), url('/assets/revolution_background.svg'); background-size: cover; background-position: center;"):
                ui.label(t('battle_revolution_title')).classes('text-2xl font-black')
                ui.label(t('battle_revolution_notice')).classes('text-sm font-bold')
        if battle_flag_only_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-indigo-300 bg-indigo-50'):
                ui.label(t('battle_flag_only_title')).classes('text-2xl font-black text-indigo-800')
                ui.label(t('battle_flag_only_notice')).classes('text-sm font-bold text-indigo-700')
        if battle_vatican_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-amber-300 bg-amber-50'):
                ui.label(t('battle_vatican_title')).classes('text-2xl font-black text-amber-800')
                ui.label(t('battle_vatican_notice')).classes('text-sm font-bold text-amber-700')
        if battle_replace_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-cyan-300 bg-cyan-50'):
                ui.label(t('battle_replace_title')).classes('text-2xl font-black text-cyan-800')
                ui.label(t('battle_replace_notice')).classes('text-sm font-bold text-cyan-700')
        if battle_bomb_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-pink-300 bg-pink-50'):
                ui.label(t('battle_bomb_title')).classes('text-2xl font-black text-pink-800')
                ui.label(t('battle_bomb_notice')).classes('text-sm font-bold text-pink-700')
                if battle_find_bomb_holder(room) == state.current_user:
                    ui.badge(t('battle_bomb_in_your_hand'), color='pink')
        if battle_lytton_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-sky-300 bg-sky-50'):
                ui.label(t('battle_lytton_title')).classes('text-2xl font-black text-sky-800')
                ui.label(t('battle_lytton_notice')).classes('text-sm font-bold text-sky-700')
        if battle_damage_surge_active(room) or bool((sengoku_boss_for_room(room) or {}).get('player_damage_surge')):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-purple-400 bg-purple-50'):
                ui.label(t('battle_damage_surge_title')).classes('text-2xl font-black text-purple-800')
                ui.label(t('battle_damage_surge_notice')).classes('text-sm font-bold text-purple-700')
                required = ensure_battle_operation_required_count(room)
                if required:
                    ui.badge(t('battle_operation_required').format(count=required), color='purple')
                    ui.label(t('battle_operation_required_help').format(count=required)).classes('text-sm font-bold text-purple-700')
        if battle_random_target_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-fuchsia-300 bg-fuchsia-50'):
                ui.label(t('battle_random_target_title')).classes('text-2xl font-black text-fuchsia-800')
                ui.label(t('battle_random_target_notice')).classes('text-sm font-bold text-fuchsia-700')
        if battle_ceasefire_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-emerald-300 bg-emerald-50'):
                ui.label(t('battle_ceasefire_title')).classes('text-2xl font-black text-emerald-800')
                ui.label(t('battle_ceasefire_notice')).classes('text-sm font-bold text-emerald-700')
        if battle_command_surge_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-blue-300 bg-blue-50'):
                ui.label(t('battle_command_surge_title')).classes('text-2xl font-black text-blue-800')
                ui.label(t('battle_command_surge_notice')).classes('text-sm font-bold text-blue-700')
        if battle_supply_drop_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-lime-300 bg-lime-50'):
                ui.label(t('battle_supply_drop_title')).classes('text-2xl font-black text-lime-800')
                ui.label(t('battle_supply_drop_notice')).classes('text-sm font-bold text-lime-700')
        if battle_blockade_active(room):
            with ui.card().classes('w-full p-5 gap-2 border-2 border-gray-400 bg-gray-100'):
                ui.label(t('battle_blockade_title')).classes('text-2xl font-black text-gray-800')
                ui.label(t('battle_blockade_notice')).classes('text-sm font-bold text-gray-700')

    def render_battle_revealed_hands(room, lookup, username, is_spectator):
        if not battle_lytton_active(room):
            return
        players = active_battle_players(room)
        teams = room.get('teams', {})
        if is_spectator or username not in players:
            visible_players = players
        elif room.get('mode') == TEAM_MODE:
            own_team = teams.get(username)
            visible_players = [player for player in players if teams.get(player) != own_team]
        else:
            visible_players = [player for player in players if player != username]
        if not visible_players:
            return
        with ui.card().classes('w-full p-5 gap-3 border border-sky-200 bg-sky-50'):
            ui.label(t('battle_revealed_hands')).classes('text-lg font-bold text-sky-900')
            with ui.grid(columns=1 if is_mobile_ui() else min(3, len(visible_players))).classes('w-full gap-3'):
                for player in visible_players:
                    hand = list(room.setdefault('hands', {}).get(player, []))
                    with ui.column().classes('wa-light-fallback gap-2 rounded border border-sky-100 bg-white p-3'):
                        ui.label(f"{player} / {t('battle_hand_count')} {len(hand)}").classes('font-bold text-[#1a2332]')
                        if not hand:
                            ui.label('-').classes('text-gray-500')
                        else:
                            with ui.row().classes('gap-2 flex-wrap'):
                                for key in hand:
                                    if is_battle_special_card(key):
                                        card = battle_visual_card(key, lookup, room, reveal_bomb=(key == BATTLE_BOMB_CARD))
                                        border_class = 'border-pink-300 bg-pink-50' if key == BATTLE_BOMB_CARD else 'border-red-200 bg-red-50'
                                        with ui.column().classes(f'w-28 gap-1 rounded border {border_class} p-2'):
                                            ui.icon('priority_high' if key == BATTLE_BOMB_CARD else 'warning').classes('text-pink-700' if key == BATTLE_BOMB_CARD else 'text-red-600')
                                            ui.label(card.get('name') or battle_special_card_label(key) or str(key)).classes('text-xs font-bold text-red-800 whitespace-normal')
                                        continue
                                    country = lookup.get(key)
                                    if not country:
                                        ui.badge(str(key), color='blue').classes('whitespace-normal')
                                        continue
                                    with ui.column().classes('w-28 gap-1 rounded border border-sky-100 bg-white p-2 shadow-sm'):
                                        render_flag_frame(country, 'w-full rounded border border-gray-200', 'w-full h-full object-cover')
                                        ui.label(battle_card_display_name(key, lookup, room)).classes('text-xs font-bold text-[#1a2332] whitespace-normal')

    def render_battle_last_turn(room):
        visual = room.get('last_turn') if isinstance(room.get('last_turn'), dict) else {}
        def event_text(kind, row):
            if kind == 'steal':
                return f"{row.get('loser', '')} -> {row.get('winner', '')}: {row.get('name', '')}"
            if kind == 'self_damage':
                parts = []
                if row.get('damage'):
                    parts.append(f"-{format_battle_number(row.get('damage', 0))}")
                if row.get('heal'):
                    parts.append(f"+{format_battle_number(row.get('heal', 0))}")
                if row.get('destroyed_card'):
                    parts.append('x1')
                return f"{row.get('player', '')}: {row.get('name', '')} {' '.join(parts)}"
            if kind == 'bomb':
                if row.get('damage'):
                    cover_name = row.get('cover_name') or (row.get('card') or {}).get('name') or t('battle_bomb_title')
                    return f"{row.get('player', '')}: {cover_name} -> {t('battle_bomb_title')} -{format_battle_number(row.get('damage', 0))}"
                return t('battle_bomb_secret_move')
            if kind == 'damage' and row.get('outcome') in ['draw', 'blocked', 'overpowered'] and not row.get('damage'):
                return f"{row.get('source', '')} -> {row.get('target', '')}: {t('battle_no_damage')}"
            return f"{row.get('source', '')} -> {row.get('target', '')}: -{format_battle_number(row.get('damage', 0))}"

        def render_metric(label, value, tone='gray'):
            color_class = {
                'red': 'text-red-700',
                'green': 'text-green-700',
                'blue': 'text-blue-700',
                'purple': 'text-purple-700',
                'orange': 'text-orange-700',
                'amber': 'text-amber-700',
            }.get(tone, 'text-[#1a2332]')
            with ui.column().classes('gap-1 rounded border border-gray-100 bg-gray-50 p-2'):
                ui.label(label).classes('text-[11px] font-bold text-gray-500')
                ui.label(str(value)).classes(f'text-sm font-bold {color_class}')

        def render_breakdown(row, counter=False):
            breakdown = row.get('breakdown') if isinstance(row.get('breakdown'), dict) else None
            if not breakdown:
                return
            with ui.column().classes('wa-light-fallback w-full gap-2 rounded border border-gray-200 bg-white p-3'):
                ui.label(t('battle_action_details')).classes('text-xs font-bold text-gray-500')
                with ui.grid(columns=1 if is_mobile_ui() else 4).classes('w-full gap-2'):
                    render_metric(t('battle_base_attack'), format_battle_number(breakdown.get('win_power', 0)), 'blue')
                    render_metric(t('battle_opponent_attack'), format_battle_number(breakdown.get('lose_power', 0)), 'orange')
                    render_metric(t('battle_power_gap'), format_battle_number(breakdown.get('power_gap', 0)), 'purple')
                    render_metric(
                        t('battle_attack_bonus_value'),
                        f"{format_signed_battle_number(breakdown.get('attack_bonus_value', 0))} / x{format_battle_multiplier(breakdown.get('attack_bonus_multiplier', 1))}",
                        'green',
                    )
                    render_metric(t('battle_after_bonus'), format_battle_number(breakdown.get('attack_after_bonus', 0)), 'blue')
                    render_metric(t('battle_defense_base'), format_battle_number(breakdown.get('defense_base', 0)), 'orange')
                    render_metric(
                        t('battle_defense_bonus_value'),
                        f"+{format_battle_number(breakdown.get('defense_bonus_value', 0))} / x{format_battle_multiplier(breakdown.get('defense_bonus_multiplier', 1))}",
                        'green',
                    )
                    render_metric(t('battle_final_defense'), format_battle_number(breakdown.get('defense', 0)), 'orange')
                    render_metric(t('battle_after_defense'), format_battle_number(breakdown.get('after_defense', 0)), 'purple')
                    render_metric(t('battle_turn_pressure'), f"x{format_battle_multiplier(breakdown.get('turn_pressure_multiplier', 1))}", 'purple')
                    render_metric(t('battle_world_war_multiplier_label'), f"x{format_battle_multiplier(breakdown.get('world_war_multiplier', 1))}", 'red')
                    render_metric(t('battle_event_multiplier_label'), f"x{format_battle_multiplier(breakdown.get('event_multiplier', 1))}", 'red')
                    if int(breakdown.get('boss_extra_actions', 1) or 1) > 1:
                        render_metric('ボス追加行動', f"x{breakdown.get('boss_extra_actions')} (+{format_battle_number(breakdown.get('boss_extra_action_damage', 0))})", 'red')
                    render_metric(
                        t('battle_final_counter') if counter else t('battle_final_damage'),
                        format_battle_number(breakdown.get('counter' if counter else 'damage', 0)),
                        'red' if not counter else 'orange',
                    )
                    if int(breakdown.get('satrapy_shield_reduction_percent', 0) or 0):
                        render_metric(
                            '属州シールド軽減',
                            f"-{breakdown.get('satrapy_shield_reduction_percent')}% ({format_battle_number(breakdown.get('satrapy_shield_reduced_damage', 0))})",
                            'amber',
                        )
                    if int(breakdown.get('split_count', 1) or 1) > 1:
                        render_metric(t('battle_raw_team_attack'), format_battle_number(breakdown.get('raw_team_attack', 0)), 'blue')
                        render_metric(
                            t('battle_team_split_penalty'),
                            f"x1/{breakdown.get('split_count')} (-{format_battle_number(breakdown.get('split_penalty_value', 0))})",
                            'red',
                        )
                attack_labels = breakdown.get('attack_bonus_labels', [])
                defense_labels = breakdown.get('defense_bonus_labels', [])
                if attack_labels or defense_labels:
                    with ui.row().classes('gap-2 flex-wrap'):
                        if attack_labels:
                            ui.badge(f"{t('battle_bonus')}: {', '.join(attack_labels[:6])}", color='green').classes('whitespace-normal')
                        if defense_labels:
                            ui.badge(f"{t('battle_defense')} {t('battle_bonus')}: {', '.join(defense_labels[:6])}", color='orange').classes('whitespace-normal')

        with ui.card().classes('w-full p-5 gap-4 border border-blue-100 bg-blue-50'):
            ui.label(t('battle_last_turn')).classes('text-xl font-bold text-[#1a2332]')
            if not visual:
                ui.label(t('battle_no_visual')).classes('text-gray-500')
                return
            event_keys = ['world_war', 'revolution', 'flag_only', 'vatican', 'replace', 'bomb', 'lytton', 'damage_surge', 'random_target', 'ceasefire', 'command_surge', 'supply_drop', 'blockade']
            if any(visual.get(key) for key in event_keys):
                with ui.row().classes('gap-2 flex-wrap'):
                    if visual.get('world_war'):
                        ui.badge(t('battle_world_war_title'), color='red')
                    if visual.get('revolution'):
                        ui.badge(t('battle_revolution_title'), color='orange')
                    if visual.get('flag_only'):
                        ui.badge(t('battle_flag_only_title'), color='indigo')
                    if visual.get('vatican'):
                        ui.badge(t('battle_vatican_title'), color='amber')
                    if visual.get('replace'):
                        ui.badge(t('battle_replace_title'), color='cyan')
                    if visual.get('bomb'):
                        ui.badge(t('battle_bomb_title'), color='pink')
                    if visual.get('lytton'):
                        ui.badge(t('battle_lytton_title'), color='blue')
                    if visual.get('damage_surge'):
                        ui.badge(t('battle_damage_surge_title'), color='purple')
                    if visual.get('random_target'):
                        ui.badge(t('battle_random_target_title'), color='fuchsia')
                    if visual.get('ceasefire'):
                        ui.badge(t('battle_ceasefire_title'), color='green')
                    if visual.get('command_surge'):
                        ui.badge(t('battle_command_surge_title'), color='blue')
                    if visual.get('supply_drop'):
                        ui.badge(t('battle_supply_drop_title'), color='lime')
                    if visual.get('blockade'):
                        ui.badge(t('battle_blockade_title'), color='grey')
            ui.label(t('battle_played_visual')).classes('text-sm font-bold text-gray-600')
            with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-3'):
                for item in visual.get('played', []):
                    with ui.column().classes('wa-light-fallback gap-2 rounded border border-gray-200 bg-white p-3'):
                        ui.label(item.get('player', '')).classes('font-bold text-[#1a2332]')
                        if item.get('defenseless'):
                            ui.badge(t('battle_defenseless'), color='red')
                        else:
                            with ui.row().classes('gap-2 flex-wrap'):
                                ui.badge(f"{t('battle_cards_before')}: {item.get('hand_count_before', 0)}", color='grey')
                                if item.get('target'):
                                    ui.badge(f"{t('battle_attack_target')}: {item.get('target')}", color='purple')
                                ui.badge(f"{t('battle_base_attack')}: {format_battle_number(item.get('power', 0))}", color='blue')
                                ui.badge(
                                    f"{t('battle_final_defense')}: {format_battle_number(item.get('defense', 0))}"
                                    f" (+{format_battle_number(item.get('defense_bonus_value', 0))})",
                                    color='orange',
                                )
                            if item.get('cards'):
                                ui.label(t('battle_played_visual')).classes('text-xs font-bold text-gray-500')
                                with ui.row().classes('gap-2 flex-wrap'):
                                    for card in item.get('cards', []):
                                        render_battle_visual_card(card)
                            else:
                                ui.label(battle_no_cards_label()).classes('text-gray-500')
                            if item.get('defense_cards'):
                                ui.label(t('battle_defense_visual')).classes('text-xs font-bold text-gray-500')
                                with ui.row().classes('gap-2 flex-wrap'):
                                    for card in item.get('defense_cards', []):
                                        render_battle_visual_card(card)
            events = [
                (t('battle_damage_visual'), visual.get('damage', []), 'red', 'damage'),
                (t('battle_counter_visual'), visual.get('counters', []), 'orange', 'counter'),
                (t('battle_steal_visual'), visual.get('steals', []), 'purple', 'steal'),
                (t('battle_bomb_visual'), visual.get('bombs', []), 'pink', 'bomb'),
                (t('battle_self_damage_visual'), visual.get('self_damage', []), 'red', 'self_damage'),
            ]
            for title, rows, color, kind in events:
                if not rows:
                    continue
                ui.label(title).classes('text-sm font-bold text-gray-600')
                with ui.column().classes('w-full gap-2'):
                    for row in rows:
                        with ui.row().classes('wa-light-fallback w-full items-center gap-2 flex-wrap rounded bg-white p-2'):
                            ui.badge(event_text(kind, row), color=color).classes('whitespace-normal')
                            if row.get('card'):
                                render_battle_visual_card(row.get('card'))
                            if row.get('destroyed_card'):
                                render_battle_visual_card(row.get('destroyed_card'))
                            if kind in ['damage', 'counter']:
                                render_breakdown(row, counter=kind == 'counter')

    def battle_winner_label(room):
        winner = room.get('winner')
        if isinstance(winner, str) and winner.startswith('team:'):
            return f"{t('battle_team')} {winner.split(':', 1)[1]}"
        return str(winner or '')

    def render_battle_chat(room):
        with ui.card().classes('w-full p-5 gap-3'):
            ui.label(t('battle_chat')).classes('text-xl font-bold text-[#1a2332]')
            chat_input = ui.input(placeholder=t('battle_chat_placeholder')).props('outlined dense').classes('w-full')
            ui.button(t('battle_send'), icon='send', on_click=lambda *_: send_battle_chat(chat_input.value)).props('color=primary dense')
            if not room.get('chat'):
                ui.label('-').classes('text-gray-500')
            for entry in room.get('chat', [])[:10]:
                user = entry.get('user', '')
                text = entry.get('text', '')
                stamp = format_timestamp(entry.get('timestamp'))
                ui.label(f"{user} [{stamp}]: {text}").classes('text-sm text-gray-700')

    def render_battle_team_chat(room):
        username = state.current_user
        team = room.get('teams', {}).get(username)
        if room.get('mode') != TEAM_MODE or not team or username not in room.get('players', []):
            return
        entries = [entry for entry in room.get('team_chat', []) if entry.get('team') == team]
        with ui.card().classes('w-full p-5 gap-3 border border-blue-100 bg-blue-50'):
            ui.label(t('battle_team_chat')).classes('text-xl font-bold text-[#1a2332]')
            chat_input = ui.input(placeholder=t('battle_team_chat_placeholder')).props('outlined dense').classes('w-full bg-white')
            ui.button(t('battle_send'), icon='send', on_click=lambda *_: send_battle_team_chat(chat_input.value)).props('color=primary dense')
            if not entries:
                ui.label('-').classes('text-gray-500')
            for entry in entries[:10]:
                user = entry.get('user', '')
                text = entry.get('text', '')
                stamp = format_timestamp(entry.get('timestamp'))
                ui.label(f"{user} [{stamp}]: {text}").classes('text-sm text-gray-700')

    def render_battle_room(room):
        players = room.get('players', [])
        if len(players) < 2:
            return
        username = state.current_user
        lookup = battle_country_lookup()
        winner = room.get('winner')
        mode = room.get('mode', DUEL_MODE)
        teams = room.get('teams', {})
        is_spectator = username not in players
        boss = sengoku_boss_for_room(room)

        room_card_classes = 'w-full p-5 gap-4'
        if battle_revolution_active(room):
            room_card_classes += ' border-2 border-yellow-300 text-white'
        elif battle_world_war_active(room):
            room_card_classes += ' border-2 border-red-400 bg-red-50'
        room_card = ui.card().classes(room_card_classes)
        if battle_revolution_active(room):
            room_card.style("background-image: linear-gradient(rgba(127,29,29,0.78), rgba(127,29,29,0.78)), url('/assets/revolution_background.svg'); background-size: cover; background-position: center;")
        with room_card:
            with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                title_class = 'text-xl font-bold text-white' if battle_revolution_active(room) else 'text-xl font-bold text-[#1a2332]'
                ui.label(f'{battle_mode_label(mode)} / {t("battle_turn")} {room.get("turn", 1)}').classes(title_class)
                ui.button(t('battle_refresh'), icon='refresh', on_click=refresh_battle_view).props('outline color=primary dense')
            ui.label(t('battle_auto_notice')).classes('text-xs text-white' if battle_revolution_active(room) else 'text-xs text-gray-500')
            ui.badge(f"{t('battle_room_thinking_time')}: {battle_timeout_label(battle_room_timeout_seconds(room))}", color='blue')
            ui.badge(
                f"{t('battle_room_world_war_setting')}: {battle_world_war_turn_label(battle_room_world_war_turn(room))}",
                color='red',
            )
            ui.badge(
                f"{t('battle_events_setting')}: {t('battle_events_on') if battle_room_events_enabled(room) else t('battle_events_off')}",
                color='orange',
            )
            if room.get('sengoku_mode'):
                ui.badge(t('sengoku_mode'), color='purple')
            if boss:
                ui.badge(f"ボス戦: {localized_boss_text(boss, 'name')}", color='purple')
            if mode in [FFA_MODE, TEAM_MODE]:
                ui.badge(f"{t('battle_room_players')}: {len(players)} / {room.get('player_count', len(players))}", color='green')
            if not winner:
                battle_countdown_label['component'] = ui.label(battle_time_left_text(room)).classes('text-sm font-bold text-orange-700')
            if mode == TEAM_MODE:
                if clean_username(room.get('host')) == username and int(room.get('turn', 1) or 1) == 1 and not room.get('submitted'):
                    ui.button(t('battle_team_randomize'), icon='shuffle', on_click=randomize_current_battle_teams).props('outline color=primary dense')
                team_hp = ensure_battle_team_hp(room)
                with ui.grid(columns=1 if is_mobile_ui() else min(4, len(team_hp))).classes('w-full gap-4'):
                    for team in sorted(team_hp):
                        team_limit = battle_team_hp_limit(room, team)
                        render_hp_bar(f"{t('battle_team')} {team}", team_hp.get(team, team_limit), team_limit)
                with ui.row().classes('w-full gap-2 flex-wrap'):
                    for player in players:
                        hand_count = len(room.setdefault('hands', {}).get(player, []))
                        with ui.row().classes('items-center gap-1'):
                            ui.badge(
                                f"{player}: {t('battle_team')} {teams.get(player, '-')} / {t('battle_hand_count')} {hand_count}",
                                color='blue' if room.setdefault('hp', {}).get(player, 0) > 0 else 'grey',
                            )
                            if clean_username(room.get('host')) == username and player != username and not is_battle_bot(player):
                                ui.button(t('battle_kick'), icon='person_remove', on_click=lambda _, p=player: kick_battle_player(p)).props('outline color=red dense')
            else:
                with ui.grid(columns=1 if is_mobile_ui() else min(4, len(players))).classes('w-full gap-4'):
                    for player in players:
                        hand_count = len(room.setdefault('hands', {}).get(player, []))
                        with ui.column().classes('w-full gap-2'):
                            render_hp_bar(
                                player,
                                room.setdefault('hp', {}).get(player, battle_player_hp_limit(room, player)),
                                battle_player_hp_limit(room, player),
                                f"{t('battle_hand_count')}: {hand_count}",
                            )
                            if clean_username(room.get('host')) == username and player != username and not is_battle_bot(player):
                                ui.button(t('battle_kick'), icon='person_remove', on_click=lambda _, p=player: kick_battle_player(p)).props('outline color=red dense')

            if not winner:
                render_battle_crisis_notice(room)
                render_battle_revealed_hands(room, lookup, username, is_spectator)

            if winner:
                is_winner = winner == username or (
                    isinstance(winner, str)
                    and winner.startswith('team:')
                    and teams.get(username) == winner.split(':', 1)[1]
                )
                if is_spectator:
                    ui.label(t('battle_spectating')).classes('text-2xl font-bold text-blue-700')
                else:
                    ui.label(t('battle_win') if is_winner else t('battle_lose')) \
                        .classes('text-2xl font-bold text-green-700' if is_winner else 'text-2xl font-bold text-red-700')
                ui.label(battle_winner_label(room)).classes('text-lg font-bold text-gray-700')
                with ui.row().classes('w-full gap-2 flex-wrap'):
                    if not is_spectator:
                        if boss:
                            next_boss_id = next_sengoku_boss_id(boss['id'])
                            if is_winner and next_boss_id:
                                ui.button('次のボスへ', icon='arrow_forward', on_click=lambda boss_id=next_boss_id: create_sengoku_boss_battle(boss_id, replace_current=True)).props('color=purple')
                            ui.button('再挑戦', icon='replay', on_click=lambda boss_id=boss['id']: create_sengoku_boss_battle(boss_id, replace_current=True)).props('outline color=purple')
                            ui.button('国力対戦へ戻る', icon='sports_esports', on_click=lambda: leave_finished_battle(False)).props('outline color=primary')
                        else:
                            ui.button(t('battle_join'), icon='sports_esports', on_click=lambda: leave_finished_battle(True)).props('color=primary')
                        ui.button(t('account'), icon='person', on_click=lambda: (leave_finished_battle(False), show_screen('account'))).props('outline color=primary')
                    else:
                        ui.button(t('battle_leave_spectate'), icon='visibility_off', on_click=leave_battle_spectate).props('outline color=primary')
                if not boss:
                    render_battle_team_chat(room)
                    render_battle_chat(room)
                render_battle_last_turn(room)
                return

            if is_spectator:
                ui.label(t('battle_spectating')).classes('text-sm font-bold text-blue-700')
                ui.button(t('battle_leave_spectate'), icon='visibility_off', on_click=leave_battle_spectate).props('outline color=primary dense')
            else:
                hand = room['hands'].setdefault(username, [])
                waiting_for_player = username in room.get('submitted', {})
                playable_hand = [key for key in hand if is_battle_selectable_card(key)]
                defenseless = username in set(room.get('reload_after_turn', [])) or not hand or not playable_hand or battle_player_command(room, username) < battle_command_cost_for_count(1)
                if room.setdefault('hp', {}).get(username, BATTLE_MAX_HP) <= 0:
                    ui.label(t('battle_eliminated')).classes('text-sm font-bold text-gray-600')
                elif waiting_for_player:
                    ui.label(t('battle_wait_opponent')).classes('text-sm font-bold text-blue-700')
                    ui.button(t('battle_surrender'), icon='flag', on_click=surrender_battle).props('outline color=negative dense')
                elif defenseless:
                    ui.label(t('battle_defenseless')).classes('text-sm font-bold text-red-700')
                    with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                        ui.button(t('battle_surrender'), icon='flag', on_click=surrender_battle).props('outline color=negative')
                        ui.button(t('battle_submit'), icon='shield', on_click=submit_battle_hand).props('color=red')
                else:
                    with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                        ui.label(t('battle_hand')).classes('text-lg font-bold text-[#1a2332]')
                        with ui.row().classes('items-center gap-2 flex-wrap'):
                            ui.badge(f"{t('battle_command')}: {battle_player_command(room, username)} / {battle_player_command_limit(room, username)}", color='purple')
                            ui.label(t('battle_power_hidden_hint')).classes('text-sm font-bold text-red-700')
                            turn = int(room.get('turn', 1))
                            redraw_used = int(room.setdefault('redraw_turns', {}).get(username, 0) or 0) == turn
                            redraw_button = ui.button(t('battle_redraw'), icon='refresh', on_click=redraw_battle_hand).props('outline color=primary dense')
                            redraw_button.tooltip(t('battle_redraw_command_cost').format(cost=BATTLE_REDRAW_COMMAND_COST))
                            if redraw_used:
                                redraw_button.disable()
                                redraw_button.tooltip(t('battle_redraw_used'))
                    required_count = ensure_battle_operation_required_count(room)
                    if required_count:
                        with ui.row().classes('w-full items-center gap-2 flex-wrap'):
                            ui.badge(t('battle_operation_required').format(count=required_count), color='purple')
                            ui.label(t('battle_operation_required_help').format(count=required_count)).classes('text-sm font-bold text-purple-700')
                    if battle_random_target_active(room) and mode in [FFA_MODE, TEAM_MODE]:
                        with ui.row().classes('w-full items-center gap-2 flex-wrap'):
                            ui.badge(t('battle_random_target_title'), color='fuchsia')
                            ui.label(t('battle_random_target_notice')).classes('text-sm font-bold text-fuchsia-700')
                    elif mode in [FFA_MODE, TEAM_MODE]:
                        if mode == TEAM_MODE:
                            own_team = teams.get(username)
                            target_options = sorted({
                                teams.get(player)
                                for player in active_battle_players(room)
                                if teams.get(player) and teams.get(player) != own_team
                            })
                        else:
                            target_options = [player for player in active_battle_players(room) if player != username]
                        if state.battle_attack_target not in target_options:
                            state.battle_attack_target = None
                        ui.select(
                            target_options,
                            value=state.battle_attack_target,
                            label=t('battle_attack_target'),
                            on_change=lambda e: setattr(state, 'battle_attack_target', e.value),
                        ).props('outlined dense').classes('w-full bg-white')
                    with ui.grid(columns=1 if is_mobile_ui() else 5).classes('w-full gap-3'):
                        for key in hand:
                            render_battle_card(key, lookup, room)
                    with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                        ui.button(t('battle_surrender'), icon='flag', on_click=surrender_battle).props('outline color=negative')
                        ui.button(t('battle_submit'), icon='sports_martial_arts', on_click=submit_battle_hand).props('color=primary')

        render_battle_last_turn(room)
        if not boss:
            render_battle_team_chat(room)
            render_battle_chat(room)
        with ui.card().classes('w-full p-5 gap-3'):
            ui.label(t('battle_log')).classes('text-xl font-bold text-[#1a2332]')
            if not room.get('log'):
                ui.label('-').classes('text-gray-500')
            for entry in room.get('log', []):
                ui.label(entry).classes('text-sm text-gray-700 whitespace-normal break-words')

    def refresh_battle_view():
        battle_countdown_label['component'] = None
        state.battle_last_signature = battle_screen_signature()
        render_header(header_container_battle)
        update_mode_classes(
            battle_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        battle_content.clear()
        with battle_content:
            user = get_current_user_record()
            eligible = battle_is_user_eligible(user=user)
            page_heading(t('battle_title') if eligible else t('battle_locked'), 'sports_martial_arts' if eligible else 'lock')
            if user:
                wins = int(user.get('battle_wins', 0))
                ui.label(f'{t("battle_wins")}: {crown_marks(wins) or "0"}').classes('text-lg font-bold text-yellow-700')
            if not eligible:
                with ui.card().classes('w-full p-5 gap-2'):
                    ui.label(t('battle_locked')).classes('font-bold text-gray-700')
                    ui.label(t('unlock_condition_not_met')).classes('text-sm text-gray-500')
                    ui.label(t('battle_unlock_hint')).classes('text-sm text-gray-500')
                return
            render_battle_help()

            room = current_battle_room()
            if room:
                render_battle_room(room)
                return

            render_sengoku_boss_panel(user)

            with ui.card().classes('w-full p-5 gap-4'):
                if is_current_user_waiting_for_battle():
                    ui.label(t('battle_waiting')).classes('text-lg font-bold text-blue-700')
                    waiting_entry = current_user_battle_queue_entry()
                    if waiting_entry:
                        ui.badge(
                            f"{battle_mode_label(waiting_entry.get('mode', DUEL_MODE))} / {t('battle_thinking_time')}: {battle_timeout_label(waiting_entry.get('turn_timeout_seconds'))}",
                            color='blue',
                        )
                        ui.badge(
                            f"{t('battle_room_world_war_setting')}: {battle_world_war_turn_label(waiting_entry.get('world_war_turn'))}",
                            color='red',
                        )
                        ui.badge(
                            f"{t('battle_events_setting')}: {t('battle_events_on') if waiting_entry.get('events_enabled', True) else t('battle_events_off')}",
                            color='orange',
                        )
                        ui.badge(
                            f"{t('battle_room_players')}: {waiting_entry.get('player_count', 2)}",
                            color='green',
                        )
                        if waiting_entry.get('mode') == TEAM_MODE:
                            ui.badge(
                                f"{t('battle_team_count')}: {waiting_entry.get('team_count', 2)} / {t('battle_team')} {waiting_entry.get('team_choice', 'A')}",
                                color='purple',
                            )
                    with ui.row().classes('w-full gap-2 flex-wrap'):
                        ui.button(t('battle_cancel'), icon='close', on_click=cancel_battle_queue).props('outline color=red')
                        ui.button(t('battle_start_with_bots'), icon='smart_toy', on_click=start_current_battle_queue_now).props('color=primary')
                        ui.button(t('battle_refresh'), icon='refresh', on_click=refresh_battle_view).props('outline color=primary')
                else:
                    with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                        ui.label(t('battle_thinking_time')).classes('text-sm font-bold text-gray-500')
                        for seconds in BATTLE_TURN_TIMEOUT_OPTIONS:
                            color = 'primary' if selected_battle_timeout_seconds() == seconds else 'grey'
                            ui.button(
                                battle_timeout_label(seconds),
                                on_click=lambda _, value=seconds: (
                                    setattr(state, 'battle_turn_timeout_seconds', value),
                                    refresh_battle_view(),
                                ),
                            ).props(f'outline color={color} dense')
                    with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                        ui.label(t('battle_world_war_setting')).classes('text-sm font-bold text-gray-500')
                        for turn in BATTLE_WORLD_WAR_TURN_OPTIONS:
                            color = 'red' if selected_battle_world_war_turn() == turn else 'grey'
                            ui.button(
                                battle_world_war_turn_label(turn),
                                on_click=lambda _, value=turn: (
                                    setattr(state, 'battle_world_war_turn', value),
                                    refresh_battle_view(),
                                ),
                            ).props(f'outline color={color} dense')
                    with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                        ui.label(t('battle_events_setting')).classes('text-sm font-bold text-gray-500')
                        for enabled, label_key in [(True, 'battle_events_on'), (False, 'battle_events_off')]:
                            color = 'orange' if selected_battle_events_enabled() == enabled else 'grey'
                            ui.button(
                                t(label_key),
                                on_click=lambda _, value=enabled: (
                                    setattr(state, 'battle_events_enabled', value),
                                    refresh_battle_view(),
                                ),
                            ).props(f'outline color={color} dense')
                    with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                        ui.label(t('battle_room_players')).classes('text-sm font-bold text-gray-500')
                        for count in range(BATTLE_MIN_MULTIPLAYER_PLAYERS, BATTLE_MAX_MULTIPLAYER_PLAYERS + 1):
                            color = 'primary' if selected_battle_player_count(FFA_MODE) == count else 'grey'
                            ui.button(
                                str(count),
                                on_click=lambda _, value=count: (
                                    setattr(state, 'battle_room_player_count', value),
                                    refresh_battle_view(),
                                ),
                            ).props(f'outline color={color} dense')
                    with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                        ui.label(t('battle_team_count')).classes('text-sm font-bold text-gray-500')
                        for count in range(2, len(BATTLE_TEAM_IDS) + 1):
                            color = 'primary' if selected_battle_team_count() == count else 'grey'
                            ui.button(
                                str(count),
                                on_click=lambda _, value=count: (
                                    setattr(state, 'battle_team_count', value),
                                    setattr(state, 'battle_team_choice', normalize_battle_team_choice(state.battle_team_choice, value)),
                                    refresh_battle_view(),
                                ),
                            ).props(f'outline color={color} dense')
                    with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                        ui.label(t('battle_team_choice')).classes('text-sm font-bold text-gray-500')
                        for team in BATTLE_TEAM_IDS[:selected_battle_team_count()]:
                            color = BATTLE_TEAM_COLORS.get(team, 'primary') if normalize_battle_team_choice(state.battle_team_choice, selected_battle_team_count()) == team else 'grey'
                            ui.button(
                                f"{t('battle_team')} {team}",
                                on_click=lambda _, value=team: (
                                    setattr(state, 'battle_team_choice', value),
                                    refresh_battle_view(),
                                ),
                            ).props(f'outline color={color} dense')
                    with ui.row().classes('w-full gap-2 flex-wrap'):
                        ui.button(t('battle_mode_duel'), icon='sports_esports', on_click=lambda: join_battle_queue(DUEL_MODE)).props('color=primary')
                        ui.button(t('battle_mode_free_for_all'), icon='groups', on_click=lambda: join_battle_queue(FFA_MODE)).props('color=primary')
                        ui.button(t('battle_mode_team'), icon='group_work', on_click=lambda: join_battle_queue(TEAM_MODE)).props('color=primary')
                        ui.button(t('battle_bot'), icon='smart_toy', on_click=create_bot_battle).props('outline color=primary')
            with ui.card().classes('w-full p-5 gap-3'):
                icon_label(t('battle_active_rooms'), 'visibility', 'text-xl font-bold text-[#1a2332]', 'text-blue-600')
                rooms = active_battle_rooms()
                if not rooms:
                    ui.label(t('battle_no_rooms')).classes('text-gray-500')
                for room_item in rooms:
                    players = ', '.join(room_item.get('players', []))
                    room_id = room_item.get('id')
                    with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                        ui.label(
                            f"{battle_mode_label(room_item.get('mode', DUEL_MODE))} / {players} / "
                            f"{t('battle_room_players')}: {len(room_item.get('players', []))}/{room_item.get('player_count', len(room_item.get('players', [])))} / "
                            f"{battle_timeout_label(battle_room_timeout_seconds(room_item))} / "
                            f"{t('battle_room_world_war_setting')}: {battle_world_war_turn_label(battle_room_world_war_turn(room_item))}"
                        ).classes('text-sm font-bold text-gray-700')
                        ui.button(t('battle_spectate'), icon='visibility', on_click=lambda *_, room_id=room_id: spectate_battle_room(room_id)).props('outline color=primary dense')

    def auto_refresh_battle():
        if not battle_screen.visible:
            return
        state_data = load_battle_state_with_timeouts()
        countdown_label = battle_countdown_label.get('component')
        if countdown_label:
            room = current_battle_room_snapshot(state_data)
            if room and not room.get('winner'):
                countdown_label.set_text(battle_time_left_text(room))
        signature = battle_screen_signature(state_data)
        if signature != state.battle_last_signature:
            refresh_battle_view()

    ui.timer(BATTLE_AUTO_REFRESH_SECONDS, auto_refresh_battle)

# ========================================
# 11. アカウントページ
# ========================================
with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as account_screen:
    header_container_account = ui.column().classes('w-full p-0 m-0')
    account_content = ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center')

    def render_stat_card(label, value, detail=''):
        with ui.card().classes('w-full p-4 gap-1'):
            ui.label(label).classes('text-sm font-bold text-gray-500')
            ui.label(value).classes('text-3xl font-bold text-[#1a2332]')
            if detail:
                ui.label(detail).classes('text-xs text-gray-500')

    def refresh_account_view():
        render_header(header_container_account)
        update_mode_classes(
            account_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        account_content.clear()
        user = get_current_user_record()
        data = get_data()
        lookup = public_countries_by_key(data)
        total = len(lookup)
        if not user:
            return
        favorites = user.setdefault('favorites', [])
        viewed = user.setdefault('viewed_keys', [])
        review = user.setdefault('review_keys', [])
        collections = user.setdefault('collections', {})
        stats = user.setdefault('quiz_stats', {'answered': 0, 'correct': 0, 'streak': 0, 'best_streak': 0})
        with account_content:
            page_heading(t('account'), 'account_circle')
            with ui.row().classes('w-full items-center gap-2 flex-wrap'):
                account_name = current_user_display_name(user)
                ui.label(t('logged_in_as').format(user=account_name)) \
                    .classes('wa-user-pill px-3 py-2 rounded-full bg-white border shadow-sm text-sm font-bold') \
                    .style(f'color: {user_pill_text_color(user)};')
                ui.button(t('users'), icon='groups', on_click=lambda: show_screen('users')) \
                    .props('outline color=primary dense')
                ui.button(t('rankings'), icon='leaderboard', on_click=lambda: show_screen('rankings')) \
                    .props('outline color=primary dense')
                ui.button(t('friends'), icon='forum', on_click=lambda: show_screen('social')) \
                    .props('outline color=primary dense')
            with ui.card().classes('w-full p-5 gap-4'):
                icon_label(t('avatar'), 'badge', 'text-xl font-bold text-[#1a2332]', 'text-blue-600')
                with ui.row().classes('w-full gap-4 items-center flex-col' if is_mobile_ui() else 'w-full gap-4 items-center no-wrap'):
                    avatar_url = current_user_avatar_url(user)
                    render_avatar_image(
                        avatar_url,
                        user,
                        'w-24 h-24 rounded-full border shadow bg-white flex-shrink-0',
                        icon_size='6rem',
                        icon_classes='text-gray-400',
                    )
                    with ui.column().classes('w-full gap-2'):
                        ui.label(t('avatar_current')).classes('text-sm font-bold text-gray-500')
                        label_to_key, key_to_label = flag_avatar_option_maps(data)
                        flag_options = list(label_to_key.keys())
                        ui.select(
                            flag_options,
                            value=current_avatar_country_label(user),
                            label=t('avatar_flag'),
                            on_change=lambda e: set_avatar_country(e.value),
                            clearable=True,
                        ).props('outlined dense').classes('w-full')
                        ui.label(t('avatar_upload')).classes('text-sm font-bold text-gray-500')
                        ui.label(t('avatar_file_hint')).classes('text-xs text-gray-500')
                        render_avatar_upload_control()
                        ui.button(t('avatar_reset'), icon='restart_alt', on_click=reset_avatar) \
                            .props('outline color=grey') \
                            .classes('w-full' if is_mobile_ui() else 'self-start')
                if avatar_url and user.get('avatar', {}).get('mode') in ['flag', 'upload']:
                    adjust = avatar_adjustment(user)
                    with ui.column().classes('w-full p-4 gap-3 bg-gray-50 border border-gray-200 rounded'):
                        ui.label(t('avatar_adjust')).classes('text-sm font-bold text-gray-700')
                        ui.label(t('avatar_adjust_hint')).classes('text-xs text-gray-500')
                        with ui.row().classes('w-full gap-4 items-center flex-col' if is_mobile_ui() else 'w-full gap-5 items-center no-wrap'):
                            render_avatar_drag_editor(avatar_url, user)
                            with ui.column().classes('w-full gap-1'):
                                ui.label(t('avatar_zoom')).classes('text-xs font-bold text-gray-500')
                                ui.slider(min=20, max=300, step=5, value=adjust['zoom'], on_change=lambda e: update_avatar_adjustment('zoom', e.value)) \
                                    .props('label-always')
            with ui.grid(columns=1 if is_mobile_ui() else 5).classes('w-full gap-4'):
                viewed_public_count = len([key for key in viewed if key in lookup])
                render_stat_card(t('viewed_count'), f'{viewed_public_count} / {total}', f'{int(viewed_public_count / total * 100) if total else 0}%')
                render_stat_card(t('favorite_count'), str(len(favorites)))
                render_stat_card(t('review_count'), str(len(review)))
                render_stat_card(t('quiz'), f"{stats.get('correct', 0)} / {stats.get('answered', 0)}", f"{t('quiz_stats').format(correct=stats.get('correct', 0), answered=stats.get('answered', 0), streak=stats.get('streak', 0), best=stats.get('best_streak', 0))}")
                render_stat_card(t('battle_wins'), crown_marks(user.get('battle_wins', 0)) or '0')

            with ui.card().classes('w-full p-5 gap-4'):
                icon_label(t('account_settings'), 'manage_accounts', 'text-xl font-bold text-[#1a2332]', 'text-blue-600')
                with ui.column().classes('w-full gap-2'):
                    ui.label(t('name_color')).classes('text-sm font-bold text-gray-700')
                    with ui.row().classes('w-full gap-2 items-end flex-wrap'):
                        name_color_input = ui.input(label=t('name_color'), value=user_name_color(user)).props('outlined dense type=color').classes('w-28')
                        ui.button(
                            t('save_name_color'),
                            icon='palette',
                            on_click=lambda field=name_color_input: set_current_name_color(field.value),
                        ).props('color=primary').classes('w-full' if is_mobile_ui() else '')
                    ui.label(t('name_color_presets')).classes('text-xs font-bold text-gray-500')
                    with ui.row().classes('w-full gap-2 flex-wrap items-center'):
                        for color_option in NAME_COLOR_OPTIONS:
                            ui.button(
                                '',
                                on_click=lambda value=color_option: set_current_name_color(value),
                            ).props('flat round dense') \
                                .classes('shadow-sm border border-gray-300') \
                                .style(f'background-color: {color_option}; width: 2rem; height: 2rem; min-width: 2rem;')
                with ui.column().classes('w-full gap-2 border-t border-gray-200 pt-4'):
                    ui.label(t('privacy_settings')).classes('text-sm font-bold text-gray-700')
                    ui.switch(
                        t('hide_public_profile'),
                        value=bool(user.get('hide_public_profile')),
                        on_change=lambda e: set_current_public_visibility(e.value),
                    ).props('color=primary')
                    ui.label(t('hide_public_profile_hint')).classes('text-xs text-gray-500')
                if is_current_user_guest():
                    ui.label(t('cannot_manage_guest')).classes('text-sm text-gray-500')
                else:
                    with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-4'):
                        with ui.column().classes('w-full gap-2'):
                            ui.label(t('change_username')).classes('text-sm font-bold text-gray-700')
                            new_username_input = ui.input(label=t('new_username'), value=state.current_user).props('outlined dense').classes('w-full')
                            rename_password_input = ui.input(label=t('current_password'), password=True, password_toggle_button=True).props('outlined dense').classes('w-full')
                            ui.button(
                                t('change_username'),
                                icon='manage_accounts',
                                on_click=lambda name_field=new_username_input, pass_field=rename_password_input: rename_current_account(name_field.value, pass_field.value),
                            ).props('color=primary').classes('w-full' if is_mobile_ui() else 'self-start')
                        with ui.column().classes('w-full gap-2'):
                            ui.label(t('change_password')).classes('text-sm font-bold text-gray-700')
                            current_password_input = ui.input(label=t('current_password'), password=True, password_toggle_button=True).props('outlined dense').classes('w-full')
                            new_password_input = ui.input(label=t('new_password'), password=True, password_toggle_button=True).props('outlined dense').classes('w-full')
                            ui.button(
                                t('change_password'),
                                icon='lock_reset',
                                on_click=lambda current_field=current_password_input, new_field=new_password_input: change_current_password(current_field.value, new_field.value),
                            ).props('color=primary').classes('w-full' if is_mobile_ui() else 'self-start')
                    with ui.column().classes('w-full gap-2 border-t border-gray-200 pt-4'):
                        ui.label(t('delete_account')).classes('text-sm font-bold text-red-700')
                        ui.label(t('delete_account_warning')).classes('text-xs text-gray-500')
                        delete_password_input = ui.input(label=t('current_password'), password=True, password_toggle_button=True).props('outlined dense').classes('w-full' if is_mobile_ui() else 'max-w-md')
                        ui.button(
                            t('delete_account'),
                            icon='delete_forever',
                            on_click=lambda pass_field=delete_password_input: delete_current_account(pass_field.value),
                        ).props('color=red').classes('w-full' if is_mobile_ui() else 'self-start')

            with ui.card().classes('w-full p-5 gap-3'):
                eligible = battle_is_user_eligible(user=user)
                icon_label(t('battle_title') if eligible else t('battle_locked'), 'sports_martial_arts' if eligible else 'lock', 'text-xl font-bold text-[#1a2332]', 'text-purple-600' if eligible else 'text-gray-500')
                if eligible:
                    ui.label(f'{t("battle_wins")}: {crown_marks(user.get("battle_wins", 0)) or "0"}').classes('text-sm font-bold text-yellow-700')
                    ui.button(t('battle_join'), icon='sports_esports', on_click=lambda: show_screen('battle')).props('color=primary')
                else:
                    ui.label(t('unlock_condition_not_met')).classes('text-sm text-gray-500')
                    ui.label(t('battle_unlock_hint')).classes('text-xs text-gray-500')
                ui.label(t('sengoku_unlock_hint')).classes('text-xs text-gray-500')

            backup = backup_labels()
            with ui.card().classes('w-full p-5 gap-3'):
                icon_label(backup['section'], 'cloud_sync', 'text-xl font-bold text-[#1a2332]', 'text-blue-600')
                with ui.row().classes('w-full gap-2 flex-col' if is_mobile_ui() else 'w-full gap-2 items-center flex-wrap'):
                    ui.button(backup['export'], icon='download', on_click=export_current_user_backup) \
                        .props('color=primary') \
                        .classes('w-full' if is_mobile_ui() else '')
                    ui.button(backup['restore_browser'], icon='cloud_sync', on_click=lambda: (restore_from_browser_backup(), refresh_account_view())) \
                        .props('outline color=primary') \
                        .classes('w-full' if is_mobile_ui() else '')
                ui.label(backup['import']).classes('text-sm font-bold text-gray-500')
                ui.upload(on_upload=import_user_backup_file, auto_upload=True) \
                    .props('accept=.json') \
                    .classes('w-full')

            with ui.card().classes('w-full p-5 gap-3'):
                icon_label(t('collections'), 'folder', 'text-xl font-bold text-[#1a2332]', 'text-blue-600')
                with ui.row().classes('w-full gap-2 items-end flex-col' if is_mobile_ui() else 'w-full gap-2 items-end'):
                    collection_input = ui.input(label=t('collection_name')).props('outlined dense').classes('w-full' if is_mobile_ui() else 'flex-grow')
                    ui.button(t('create_collection'), icon='create_new_folder', on_click=lambda field=collection_input: (create_collection(field.value), refresh_account_view())) \
                        .props('color=primary') \
                        .classes('w-full' if is_mobile_ui() else '')
                if not collections:
                    ui.label(t('no_collections')).classes('text-gray-500')
                for name, keys in collections.items():
                    with ui.row().classes('w-full items-center justify-between gap-2 flex-wrap border-t pt-3'):
                        ui.button(f'{name} ({len(keys)})', icon='folder', on_click=lambda _, collection=name: (setattr(state, "collection_filter", collection), show_screen('main'))) \
                            .props('flat color=primary')
                        ui.button(icon='delete', on_click=lambda _, collection=name: (delete_collection(collection), refresh_account_view())) \
                            .props('flat round color=red')
                    preview = [lookup[key] for key in keys if key in lookup]
                    if preview:
                        with ui.row().classes('w-full gap-2 flex-wrap'):
                            for country in preview:
                                chip = ui.chip(get_localized_text(country['names'])).props('dense outline color=primary').classes('cursor-pointer')
                                chip.on('click', lambda _, c=country: open_country_detail(c))

            with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-4'):
                with ui.card().classes('w-full p-5 gap-3'):
                    icon_label(t('weakness'), 'troubleshoot', 'text-xl font-bold text-[#1a2332]', 'text-red-500')
                    weakness = quiz_weakness_rows()
                    if not weakness:
                        ui.label(t('no_quiz_history')).classes('text-gray-500')
                    for label, count in weakness:
                        with ui.row().classes('w-full justify-between items-center border-b py-2'):
                            ui.label(label).classes('font-bold text-gray-700')
                            ui.badge(str(count), color='red')
                with ui.card().classes('w-full p-5 gap-3'):
                    icon_label(t('quiz_history'), 'history_edu', 'text-xl font-bold text-[#1a2332]', 'text-blue-600')
                    history = get_quiz_history()[:10]
                    if not history:
                        ui.label(t('no_quiz_history')).classes('text-gray-500')
                    for entry in history:
                        answer = lookup.get(entry.get('answer_key'))
                        selected = lookup.get(entry.get('selected_key'))
                        selected_raw = str(entry.get('selected_key') or '-')
                        result_color = 'green' if entry.get('correct') else 'red'
                        with ui.row().classes('w-full gap-2 items-center border-b py-2 no-wrap'):
                            ui.badge('OK' if entry.get('correct') else 'NG', color=result_color)
                            with ui.column().classes('gap-0 flex-grow'):
                                ui.label(get_localized_text(answer['names']) if answer else '-').classes('font-bold text-gray-800')
                                selected_text = get_localized_text(selected['names']) if selected else selected_raw[:60]
                                ui.label(f"{quiz_category_label(entry.get('type'))} / {selected_text} / {format_timestamp(entry.get('timestamp'))}").classes('text-xs text-gray-500')

# ========================================
# 初期表示
# ========================================
ui.timer(1.0, update_quiz_timer_label)
show_screen('top')
server_port = int(os.environ.get('PORT', 8080))
print(f'Starting World Archives on 0.0.0.0:{server_port}', flush=True)
print(f'User data file: {USER_DATA_FILE}', flush=True)
ui.run(
    title='World Archives',
    favicon='🌍',
    host='0.0.0.0',
    port=server_port,
    reload=False,
    show=False,
)
