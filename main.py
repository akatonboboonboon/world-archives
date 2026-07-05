"""
World Archives.

国・地域・歴史国家を検索、比較、クイズ化するNiceGUI製のWebアプリです。
国データはdata.json、ログイン後のユーザーデータはuser_data.jsonまたは
Render Disk上のUSER_DATA_FILEに保存します。
"""
from nicegui import ui, app
import hashlib
import json
import os
import random
import re
from datetime import datetime, timedelta, timezone
from html import escape as html_escape
from urllib.parse import quote_plus

try:
    import pykakasi
except ImportError:
    pykakasi = None

try:
    from pypinyin import lazy_pinyin
except ImportError:
    lazy_pinyin = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(BASE_DIR, 'data.json')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')

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
KAKASI_CONVERTER = pykakasi.kakasi() if pykakasi else None
APP_TIMEZONE = timezone(timedelta(hours=9), 'JST')
USER_ASSETS_DIR = os.path.join(os.path.dirname(USER_DATA_FILE) or BASE_DIR, 'user_assets')
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
</style>
""")

def app_now():
    return datetime.now(APP_TIMEZONE)

def current_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

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
    return {'users': {}}

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
    'battle_wins',
}

def looks_like_user_record(value):
    return isinstance(value, dict) and bool(USER_RECORD_KEYS.intersection(value.keys()))

def normalize_user_data_file(data):
    if not isinstance(data, dict):
        return default_user_data()
    users = data.get('users') if isinstance(data.get('users'), dict) else {}
    backup_username = str(data.get('username') or '').strip()
    if backup_username and looks_like_user_record(data.get('record')) and backup_username not in users:
        users[backup_username] = data['record']
    for key, value in list(data.items()):
        if key == 'users':
            continue
        if looks_like_user_record(value) and key not in users:
            users[key] = value
    data['users'] = users
    return data

def load_user_data():
    if not os.path.exists(USER_DATA_FILE):
        return default_user_data()
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return normalize_user_data_file(data)
    except Exception as e:
        print(f"Error loading user data: {e}")
        return default_user_data()

def save_user_data(data):
    data = normalize_user_data_file(data)
    data = {'users': data.get('users', {})}
    user_dir = os.path.dirname(USER_DATA_FILE)
    if user_dir:
        os.makedirs(user_dir, exist_ok=True)
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def merge_unique_list(current, incoming, limit=None):
    merged = list(current) if isinstance(current, list) else []
    incoming_items = incoming if isinstance(incoming, list) else []
    for item in incoming_items:
        if item not in merged:
            merged.append(item)
    if limit:
        del merged[limit:]
    return merged

def merge_user_record(current, incoming):
    if not isinstance(current, dict):
        current = {}
    if not isinstance(incoming, dict):
        return current
    for key, value in incoming.items():
        if key in ['favorites', 'review_keys']:
            current[key] = merge_unique_list(current.get(key, []), value)
        elif key == 'history':
            current[key] = merge_unique_list(current.get(key, []), value, 50)
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
                if isinstance(stat_value, int):
                    stats[stat_key] = max(stats.get(stat_key, 0), stat_value)
                else:
                    stats.setdefault(stat_key, stat_value)
        elif key in ['viewed_keys', 'quiz_history']:
            current[key] = merge_unique_list(current.get(key, []), value, 200)
        elif key == 'battle_wins' and isinstance(value, int):
            current[key] = max(current.get(key, 0), value)
        else:
            current.setdefault(key, value)
    return current

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
    filter_tag = None
    sort_field = 'name'
    sort_order = 'asc'
    show_favorites_only = False
    lang = 'ja'
    ui_mode = 'pc'
    current_user = None
    search_keyword = ''
    page = 1
    items_per_page = 20
    quiz = None
    quiz_difficulty = 'medium'
    quiz_mode = 'normal'
    quiz_category = 'all'
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
    users_browser_restore_requested = False
    battle_id = None
    battle_selected_keys = set()

state = AppState()

BATTLE_QUEUE = []
BATTLE_ROOMS = {}
BATTLE_USER_ROOM = {}
BATTLE_COUNTER = 0
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
        'quiz_capital': '首都または中心地が「{capital}」なのはどれ？',
        'quiz_desc': 'この説明に当てはまるのはどれ？',
        'quiz_flag': 'この旗の国・地域はどれ？',
        'quiz_category': '分野',
        'quiz_category_all': '総合',
        'quiz_category_flag': '国旗',
        'quiz_category_period': '年号',
        'quiz_category_capital': '首都',
        'quiz_category_desc': '説明',
        'quiz_category_profile': '基本データ',
        'quiz_category_detail': '詳細データ',
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
        'favorite_add': 'Add favorite',
        'favorite_remove': 'Remove favorite',
        'quiz': 'Mini Quiz',
        'quiz_title': 'Mini Quiz',
        'quiz_next': 'Next Question',
        'quiz_detail': 'View Details',
        'quiz_correct': 'Correct',
        'quiz_wrong': 'Not quite',
        'quiz_capital': 'Which one has “{capital}” as its capital or main center?',
        'quiz_desc': 'Which entry matches this description?',
        'quiz_flag': 'Which country or historical state uses this flag?',
        'quiz_category': 'Category',
        'quiz_category_all': 'Mixed',
        'quiz_category_flag': 'Flags',
        'quiz_category_period': 'Years',
        'quiz_category_capital': 'Capitals',
        'quiz_category_desc': 'Descriptions',
        'quiz_category_profile': 'Basic Data',
        'quiz_category_detail': 'Details',
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
        'quiz_capital': '首都或中心地是“{capital}”的是哪一个？',
        'quiz_desc': '以下说明对应哪一个？',
        'quiz_flag': '这面旗帜对应哪个国家或历史国家？',
        'quiz_category': '领域',
        'quiz_category_all': '综合',
        'quiz_category_flag': '旗帜',
        'quiz_category_period': '年代',
        'quiz_category_capital': '首都',
        'quiz_category_desc': '说明',
        'quiz_category_profile': '基本数据',
        'quiz_category_detail': '详细资料',
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
        'users_restore_browser': 'ブラウザ内のユーザーを再読み込み',
        'users_count': '表示ユーザー',
        'avatar_adjust': 'アイコンの表示調整',
        'avatar_adjust_hint': '丸いプレビュー上をドラッグして中心位置を動かせます。拡大率はスライダーで調整できます。',
        'avatar_zoom': '拡大率',
        'avatar_position_x': '中心位置（左右）',
        'avatar_position_y': '中心位置（上下）',
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
        'battle_locked': 'すべての国を閲覧すると、国力対戦が解放されます。',
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
        'users_restore_browser': 'Reload browser users',
        'users_count': 'Users shown',
        'avatar_adjust': 'Icon framing',
        'avatar_adjust_hint': 'Drag on the round preview to move the center point. Use the slider for zoom.',
        'avatar_zoom': 'Zoom',
        'avatar_position_x': 'Center position X',
        'avatar_position_y': 'Center position Y',
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
        'battle_locked': 'View every country to unlock Power Battle.',
        'battle_join': 'Start matching',
        'battle_waiting': 'Waiting for an opponent.',
        'battle_cancel': 'Leave queue',
        'battle_refresh': 'Refresh',
        'battle_hp': 'HP',
        'battle_hand': 'Hand',
        'battle_power': 'Power',
        'battle_tag_bonus': 'Tag match bonus',
        'battle_submit': 'Play this hand',
        'battle_wait_opponent': 'Waiting for the opponent.',
        'battle_defenseless': 'Your hand is empty, so you are defenseless this turn.',
        'battle_turn': 'Turn',
        'battle_log': 'Battle log',
        'battle_win': 'Win',
        'battle_lose': 'Loss',
        'battle_wins': 'Battle wins',
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
        'users_restore_browser': '重新读取浏览器用户',
        'users_count': '显示用户',
        'avatar_adjust': '头像显示调整',
        'avatar_adjust_hint': '在圆形预览上拖动即可移动中心位置。缩放请使用滑块。',
        'avatar_zoom': '缩放',
        'avatar_position_x': '中心位置（左右）',
        'avatar_position_y': '中心位置（上下）',
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
        'battle_locked': '浏览所有国家后即可解锁国力对战。',
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
    },
}

for lang_code, labels in EXTRA_UI_FALLBACKS.items():
    UI_FALLBACKS.setdefault(lang_code, {}).update(labels)

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

def tag_chip(tag, dense=True):
    props = 'dense size=xs' if dense else 'dense'
    bg, fg, border = TAG_COLOR_STYLES.get(tag, ('#f8fafc', '#111827', '#cbd5e1'))
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

def public_country_list(data=None):
    data = data or get_data()
    return [country for country in data.get('countries', []) if not is_hidden_country(country)]

def public_countries_by_key(data=None):
    return {country_key(country): country for country in public_country_list(data)}

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
    countries = public_country_list(data)
    regions = set()
    tags = set()
    for c in countries:
        if c.get('region'):
            regions.add(c['region'])
        if c.get('tags'):
            for tag in c['tags']:
                tags.add(tag)
    sorted_tags = sorted(tags, key=lambda tag: tag_label(tag).lower())
    sorted_regions = sorted(regions, key=lambda region: region_label(region).lower())
    return [region_label(region) for region in sorted_regions], [tag_label(tag) for tag in sorted_tags]

def normalize_region_value(value):
    if not value:
        return None
    data = get_data()
    regions = {c.get('region') for c in data.get('countries', []) if c.get('region')}
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
    tags = {tag for c in data.get('countries', []) for tag in c.get('tags', [])}
    if value in tags:
        return value
    for tag in tags:
        labels = [tag_label(tag, lang) for lang in TRANSLATIONS]
        if value in labels:
            return tag
    return value

def country_key(country):
    names = country.get('names', {})
    capital = country.get('capital', {})
    return '|'.join([
        names.get('en', names.get('ja', '')),
        country.get('type', ''),
        capital.get('en', capital.get('ja', '')),
    ])

def clean_username(username):
    return (username or '').strip()

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

def get_current_user_record(user_data=None):
    if not state.current_user:
        return None
    users = get_users(user_data)
    user = users.get(state.current_user)
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

def normalize_avatar_adjustment(avatar):
    if not isinstance(avatar, dict):
        return {'mode': 'default', **default_avatar_adjustment()}
    avatar['zoom'] = int(clamp_number(avatar.get('zoom'), 50, 250, 100))
    avatar['position_x'] = int(clamp_number(avatar.get('position_x'), 0, 100, 50))
    avatar['position_y'] = int(clamp_number(avatar.get('position_y'), 0, 100, 50))
    return avatar

def ensure_user_defaults(user):
    for key in ['favorites', 'history', 'review_keys', 'viewed_keys', 'quiz_history']:
        if not isinstance(user.get(key), list):
            user[key] = []
    for key in ['notes', 'collections']:
        if not isinstance(user.get(key), dict):
            user[key] = {}
    user.setdefault('quiz_stats', {
        'answered': 0,
        'correct': 0,
        'streak': 0,
        'best_streak': 0,
    })
    if not isinstance(user.get('avatar'), dict):
        user['avatar'] = {'mode': 'default'}
    normalize_avatar_adjustment(user['avatar'])
    user['name_color'] = normalize_name_color(user.get('name_color'))
    if not isinstance(user.get('battle_wins'), int):
        user['battle_wins'] = 0
    return user

BROWSER_BACKUP_KEY = 'world_archives_user_backups'

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
      backups[payload.username] = payload;
      localStorage.setItem(key, JSON.stringify(backups));
      localStorage.setItem('world_archives_last_user', payload.username);
    }})();
    """
    try:
        ui.run_javascript(script)
    except Exception as e:
        print(f"Browser backup skipped: {e}", flush=True)

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
      if (localStorage.getItem('world_archives_last_user') === {json.dumps(username)}) {{
        localStorage.removeItem('world_archives_last_user');
      }}
    }})();
    """
    try:
        ui.run_javascript(script)
    except Exception as e:
        print(f"Browser backup removal skipped: {e}", flush=True)

def persist_current_user_data(user_data):
    save_user_data(user_data)
    sync_current_user_to_browser(user_data)

def request_browser_backup_restore():
    script = f"""
    (async () => {{
      const raw = localStorage.getItem('{BROWSER_BACKUP_KEY}');
      if (!raw) return;
      try {{
        await fetch('/api/restore-user-backups', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: raw,
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
            'nav': '使い方',
            'title': 'World Archivesの使い方',
            'intro': '国・地域・歴史国家を探し、比較し、クイズで復習するためのページです。',
            'sections': [
                ('ログイン', '通常ログインをすると、お気に入り、履歴、メモ、クイズ結果が保存されます。すぐ試したい時はゲストログインも使えます。'),
                ('検索', '国名、地域、タグ、言語、宗教、説明文などで検索できます。表示順は名前順または年代順に切り替えられます。'),
                ('詳細ページ', '基本データ、解説、地図、メモ、関連国家をタブで切り替えて確認できます。昔の国は現在の関連地域の地図を表示します。'),
                ('お気に入りとコレクション', '気になる国をお気に入りに入れたり、自分用のコレクションにまとめたりできます。'),
                ('ミニクイズと復習', '国データから問題が出ます。間違えた問題は復習モードで再挑戦できます。'),
                ('バックアップ', 'アカウントページから学習データを書き出し、別の環境で読み込めます。Renderの更新前にも保存しておくと安心です。'),
            ],
        },
        'en': {
            'nav': 'Help',
            'title': 'How to Use World Archives',
            'intro': 'Search countries, compare them, and review them with quizzes.',
            'sections': [
                ('Login', 'A normal account saves favorites, history, notes, and quiz results. Guest login is available for quick use.'),
                ('Search', 'Search by name, region, tag, language, religion, or description. Sort by name or historical period.'),
                ('Details', 'Use tabs for basic data, descriptions, maps, personal notes, and related countries. Historical states show related present-day map locations.'),
                ('Favorites and collections', 'Save interesting countries as favorites or group them into personal collections.'),
                ('Mini quiz and review', 'Quiz questions are generated from country data. Missed questions can be retried in review mode.'),
                ('Backup', 'Export your learning data from the account page and import it on another environment. This is useful before redeploying.'),
            ],
        },
        'zh': {
            'nav': '使用说明',
            'title': 'World Archives使用说明',
            'intro': '用于搜索国家、比较资料，并通过小测验复习。',
            'sections': [
                ('登录', '普通账号会保存收藏、浏览记录、笔记和测验结果。也可以使用访客登录快速体验。'),
                ('搜索', '可以按国名、地区、标签、语言、宗教或说明文字搜索，并按名称或年代排序。'),
                ('详情页', '通过标签页查看基本资料、说明、地图、笔记和相关国家。历史国家会显示相关的现代地区地图。'),
                ('收藏与收藏集', '可以把感兴趣的国家加入收藏，或整理到自己的收藏集中。'),
                ('小测验与复习', '题目会从国家数据中生成，答错的内容可以在复习模式中再次练习。'),
                ('备份', '在账户页导出学习数据，并在其他环境中导入。重新部署前建议先备份。'),
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
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get('users'), dict):
        return {username: {'record': record} for username, record in payload['users'].items()}
    if payload.get('username') and isinstance(payload.get('record'), dict):
        return {payload['username']: payload}
    return payload

def restore_user_backup_payload(payload):
    backups = normalize_backup_payload(payload)
    if not backups:
        return 0
    user_data = load_user_data()
    users = user_data.setdefault('users', {})
    restored = 0
    for raw_username, backup in backups.items():
        username = clean_username(raw_username)
        if not username or not isinstance(backup, dict):
            continue
        record = backup.get('record', backup)
        if not isinstance(record, dict):
            continue
        users[username] = merge_user_record(users.get(username, {}), record)
        ensure_user_defaults(users[username])
        restored += 1
    if restored:
        save_user_data(user_data)
        if state.current_user in users:
            sync_current_user_to_browser(user_data)
    return restored

def import_user_backup_file(event):
    labels = backup_labels()
    try:
        raw = event.content.read()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8-sig')
        payload = json.loads(raw)
        restored = restore_user_backup_payload(payload)
    except Exception as e:
        print(f'Backup import failed: {e}', flush=True)
        ui.notify(labels['invalid'], color='negative')
        return
    if restored:
        ui.notify(labels['imported'], color='positive')
        refresh_account_view()
    else:
        ui.notify(labels['invalid'], color='warning')

def restore_from_browser_backup():
    labels = backup_labels()
    request_browser_backup_restore()
    ui.notify(labels['restore_browser'], color='info')

def current_user_label():
    if state.current_user == GUEST_USERNAME:
        return t('guest_user')
    return state.current_user or ''

def login_user(username, password):
    username = clean_username(username)
    if not username or not password:
        ui.notify(t('auth_missing'), color='warning')
        return False
    user_data = load_user_data()
    user = get_users(user_data).get(username)
    if not user or user.get('password_hash') != password_hash(username, password):
        ui.notify(t('auth_invalid'), color='negative')
        return False
    state.current_user = username
    state.users_browser_restore_requested = False
    ensure_user_defaults(user)
    persist_current_user_data(user_data)
    ui.notify(t('login_success'), color='positive')
    show_screen('top')
    return True

def guest_login():
    user_data = load_user_data()
    users = get_users(user_data)
    guest = users.setdefault(GUEST_USERNAME, {
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
    state.current_user = GUEST_USERNAME
    state.users_browser_restore_requested = False
    ensure_user_defaults(guest)
    persist_current_user_data(user_data)
    ui.notify(t('guest_login_success'), color='positive')
    show_screen('top')
    return True

def register_user(username, password):
    username = clean_username(username)
    if not username or not password:
        ui.notify(t('auth_missing'), color='warning')
        return False
    user_data = load_user_data()
    users = get_users(user_data)
    if username == GUEST_USERNAME or username in users:
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
    state.current_user = username
    state.users_browser_restore_requested = False
    persist_current_user_data(user_data)
    ui.notify(t('user_created'), color='positive')
    show_screen('top')
    return True

def logout_user():
    state.current_user = None
    state.users_browser_restore_requested = False
    state.selected_country = None
    state.search_keyword = ''
    state.filter_region = None
    state.filter_tag = None
    state.sort_field = 'name'
    state.show_favorites_only = False
    state.collection_filter = None
    state.page = 1
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
    if old_username == GUEST_USERNAME:
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
    if new_username == GUEST_USERNAME or (new_username != old_username and new_username in users):
        ui.notify(t('user_exists'), color='warning')
        return False
    if new_username == old_username:
        ui.notify(t('account_updated'), color='info')
        return True
    if old_username in BATTLE_QUEUE:
        BATTLE_QUEUE.remove(old_username)
    BATTLE_USER_ROOM.pop(old_username, None)
    record = users.pop(old_username)
    ensure_user_defaults(record)
    record['password_hash'] = password_hash(new_username, current_password)
    users[new_username] = record
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
    if state.current_user == GUEST_USERNAME:
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
    if username == GUEST_USERNAME:
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
    if username in BATTLE_QUEUE:
        BATTLE_QUEUE.remove(username)
    BATTLE_USER_ROOM.pop(username, None)
    users.pop(username, None)
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

def favorite_keys(data=None):
    user = get_current_user_record()
    if not user:
        return set()
    return set(user.setdefault('favorites', []))

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
    return user.setdefault('quiz_stats', {'answered': 0, 'correct': 0, 'streak': 0, 'best_streak': 0})

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

def current_user_avatar_url(user=None):
    user = user or get_current_user_record()
    if not user:
        return None
    avatar = user.get('avatar') if isinstance(user.get('avatar'), dict) else {}
    if avatar.get('mode') == 'upload' and avatar.get('file'):
        file_path = os.path.join(USER_ASSETS_DIR, avatar['file'])
        if os.path.exists(file_path):
            return user_asset_url(avatar['file'], avatar.get('version'))
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

def render_avatar_image(avatar_url, source, classes, icon_size='4rem', icon_classes='text-gray-400', live=True):
    if avatar_url:
        adjust = avatar_adjustment(source)
        zoom = adjust['zoom']
        x = adjust['position_x']
        y = adjust['position_y']
        src = html_escape(str(avatar_url), quote=True)
        live_attr = 'data-wa-avatar-live="current"' if live else ''
        with ui.element('div').classes(f'{classes} overflow-hidden relative'):
            ui.html(
                f'<img class="wa-avatar-crop-image" {live_attr} src="{src}" '
                f'style="position:absolute;left:50%;top:50%;width:{zoom}%;height:{zoom}%;'
                f'object-fit:cover;object-position:{x}% {y}%;'
                f'transform:translate(-50%, -50%);display:block;">',
                sanitize=False,
            )
    else:
        ui.icon('account_circle', size=icon_size).classes(icon_classes)

def render_avatar_drag_editor(avatar_url, source):
    adjust = avatar_adjustment(source)
    zoom = adjust['zoom']
    x = adjust['position_x']
    y = adjust['position_y']
    editor_id = f"avatar-editor-{random.randint(100000, 999999)}"
    src = html_escape(str(avatar_url), quote=True)
    ui.html(
        f'''
        <div id="{editor_id}" class="wa-avatar-editor border shadow bg-white">
          <img src="{src}" style="width:{zoom}%;height:{zoom}%;object-position:{x}% {y}%;transform:translate(-50%, -50%);">
          <div class="wa-avatar-target" style="left:{x}%;top:{y}%;"></div>
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
      let x = {x};
      let y = {y};
      const zoom = {zoom};
      let dragging = false;
      const clamp = value => Math.max(0, Math.min(100, value));
      const applyToImage = img => {{
        img.style.width = `${{zoom}}%`;
        img.style.height = `${{zoom}}%`;
        img.style.objectPosition = `${{x}}% ${{y}}%`;
        img.style.transform = 'translate(-50%, -50%)';
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
              position_x: Math.round(x),
              position_y: Math.round(y),
            }}),
          }});
        }} catch (error) {{
          console.warn('Avatar position save failed', error);
        }}
      }};
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
    data = data or get_data()
    label_to_key = {}
    key_to_label = {}
    for country in public_country_list(data):
        if not displayable_flag_code(country.get('flag_code')):
            continue
        label = country_option_label(country)
        key = country_key(country)
        label_to_key[label] = key
        key_to_label[key] = label
    return label_to_key, key_to_label

def current_avatar_country_label(user=None):
    user = user or get_current_user_record()
    avatar = user.get('avatar') if user and isinstance(user.get('avatar'), dict) else {}
    if avatar.get('mode') != 'flag':
        return None
    _, key_to_label = flag_avatar_option_maps()
    return key_to_label.get(avatar.get('country_key'))

def public_user_profiles():
    user_data = load_user_data()
    lookup = public_countries_by_key()
    profiles = []
    for username, record in sorted(get_users(user_data).items(), key=lambda item: item[0].lower()):
        if is_guest_record(username, record) or not isinstance(record, dict):
            continue
        ensure_user_defaults(record)
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
        profiles.append({
            'username': username,
            'name_color': user_name_color(record),
            'avatar_url': current_user_avatar_url(record),
            'avatar': record.get('avatar', {}),
            'favorites': favorites,
            'viewed_count': len(viewed),
            'review_count': len(review),
            'collection_count': len(public_collections),
            'collections': public_collections,
            'answered': stats.get('answered', 0),
            'correct': stats.get('correct', 0),
            'best_streak': stats.get('best_streak', 0),
            'battle_wins': record.get('battle_wins', 0),
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
        'zoom': (50, 250, 100),
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
    user = get_current_user_record(user_data)
    if not user:
        return False
    avatar = user.setdefault('avatar', {'mode': 'default'})
    if avatar.get('mode') not in ['flag', 'upload']:
        return False
    if 'zoom' in values:
        avatar['zoom'] = int(clamp_number(values.get('zoom'), 50, 250, avatar.get('zoom', 100)))
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

def upload_avatar_image(event):
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
    try:
        ext = os.path.splitext(event.name or '')[1].lower()
        if ext not in allowed_extensions:
            raise ValueError('unsupported image extension')
        content_source = event.content
        if hasattr(content_source, 'seek'):
            try:
                content_source.seek(0)
            except Exception:
                pass
        content = content_source.read() if hasattr(content_source, 'read') else content_source
        if isinstance(content, str):
            content = content.encode('utf-8')
        if not isinstance(content, (bytes, bytearray)):
            raise ValueError('invalid image content')
        if not content or len(content) > 8 * 1024 * 1024:
            raise ValueError('invalid image size')
        user_data = load_user_data()
        user = get_current_user_record(user_data)
        if not user:
            ui.notify(t('login_required'), color='warning')
            return
        folder = avatar_user_dir(state.current_user)
        for name in os.listdir(folder):
            if name.startswith('avatar.'):
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    pass
        filename = f'avatar{ext}'
        with open(os.path.join(folder, filename), 'wb') as f:
            f.write(content)
        relative_file = os.path.relpath(os.path.join(folder, filename), USER_ASSETS_DIR)
        user['avatar'] = {
            'mode': 'upload',
            'file': relative_file.replace(os.sep, '/'),
            'version': app_now().strftime('%Y%m%d%H%M%S'),
            **default_avatar_adjustment(),
        }
        persist_current_user_data(user_data)
        ui.notify(t('avatar_saved'), color='positive')
        refresh_current_screen()
    except Exception as e:
        print(f'Avatar upload failed: {e}', flush=True)
        ui.notify(t('avatar_upload_failed'), color='negative')

def get_quiz_history():
    user = get_current_user_record()
    if not user:
        return []
    return user.setdefault('quiz_history', [])

def quiz_category_label(question_type):
    if question_type == 'capital':
        return t('labels', 'capital')
    if question_type == 'flag':
        return t('quiz_flag')
    if question_type == 'period':
        return t('period')
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
    stats = user.setdefault('quiz_stats', {'answered': 0, 'correct': 0, 'streak': 0, 'best_streak': 0})
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
    })
    del history[200:]
    persist_current_user_data(user_data)

def sort_key(country):
    name = get_localized_text(country.get('names', {}))
    if state.lang == 'ja' and KAKASI_CONVERTER:
        try:
            return ''.join(item.get('hira') or item.get('kana') or item.get('orig', '') for item in KAKASI_CONVERTER.convert(name))
        except Exception:
            pass
    if state.lang == 'zh' and lazy_pinyin:
        try:
            return ' '.join(lazy_pinyin(name))
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

def countries_by_key(data=None):
    data = data or get_data()
    return {country_key(country): country for country in data.get('countries', [])}

def country_option_label(country):
    local_name = get_localized_text(country.get('names', {}))
    en_name = country.get('names', {}).get('en', '')
    if en_name and en_name != local_name:
        return f'{local_name} / {en_name}'
    return local_name

def country_option_maps(data=None):
    data = data or get_data()
    label_to_key = {}
    key_to_label = {}
    for country in sorted(public_country_list(data), key=lambda c: (sort_key(c), c.get('names', {}).get('en', ''))):
        label = country_option_label(country)
        if label in label_to_key:
            label = f'{label} ({get_localized_text(country.get("capital", {}))})'
        key = country_key(country)
        label_to_key[label] = key
        key_to_label[key] = label
    return label_to_key, key_to_label

def country_map_target(country, data=None):
    data = data or get_data()
    if country.get('hide_external_links'):
        return None
    if country.get('type') == 'Present':
        return country
    code = country.get('flag_code')
    if code and code != 'xx':
        for candidate in public_country_list(data):
            if candidate.get('type') == 'Present' and candidate.get('flag_code') == code:
                return candidate
    target_regions = {part.strip() for part in country.get('region', '').replace('/', ',').split(',') if part.strip()}
    for candidate in public_country_list(data):
        if candidate.get('type') != 'Present':
            continue
        candidate_regions = {part.strip() for part in candidate.get('region', '').replace('/', ',').split(',') if part.strip()}
        if target_regions & candidate_regions:
            return candidate
    return None

def country_map_query(country, data=None):
    target = country_map_target(country, data)
    if target:
        return target.get('names', {}).get('en') or get_localized_text(target.get('names', {}))
    capital = get_localized_text(country.get('capital', {}))
    if capital and capital != '-':
        return capital
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
        return ''
    return f"{t('map_note')} {get_localized_text(target.get('names', {}))}"

def set_map_country(country):
    state.map_country_key = country_key(country)
    show_screen('map')

def set_network_country(country):
    state.network_country_key = country_key(country)
    show_screen('network')

def open_country_detail(country):
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
    return {'easy': 3, 'medium': 4, 'hard': 5}.get(state.quiz_difficulty, 4)

QUIZ_CATEGORY_OPTIONS = [
    ('all', 'quiz_category_all'),
    ('flag', 'quiz_category_flag'),
    ('period', 'quiz_category_period'),
    ('capital', 'quiz_category_capital'),
    ('desc', 'quiz_category_desc'),
    ('profile', 'quiz_category_profile'),
    ('detail', 'quiz_category_detail'),
]

def quiz_question_matches_category(question_type):
    category = getattr(state, 'quiz_category', 'all')
    if category == 'all':
        return True
    if category in ['flag', 'period', 'capital', 'desc']:
        return question_type == category
    if category == 'profile':
        return question_type.startswith('profile_')
    if category == 'detail':
        return question_type.startswith('detail_')
    return True

def has_quiz_flag(country):
    return displayable_flag_code(country.get('flag_code'))

def normalized_text(value):
    return str(value or '').strip().casefold()

def country_name_set(country):
    names = country.get('names', {})
    if not isinstance(names, dict):
        return {normalized_text(names)}
    return {normalized_text(value) for value in names.values() if normalized_text(value)}

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
        return normalized_text(first_sentence(detail_value(country, field)))
    return ''

def quiz_candidates_for_type(countries, question_type):
    if question_type == 'desc':
        return [c for c in countries if quiz_question_value(c, question_type)]
    if question_type == 'capital':
        return [c for c in countries if quiz_question_value(c, question_type) not in ['', '-']]
    if question_type == 'flag':
        return [c for c in countries if has_quiz_flag(c)]
    if question_type == 'period':
        return [c for c in countries if quiz_question_value(c, question_type)]
    if question_type.startswith('profile_'):
        return [c for c in countries if quiz_question_value(c, question_type)]
    if question_type.startswith('detail_'):
        return [c for c in countries if quiz_question_value(c, question_type)]
    return []

def build_quiz_options(answer, question_type, countries):
    desired_count = quiz_option_count()
    answer_key = country_key(answer)
    answer_names = country_name_set(answer)
    answer_value = quiz_question_value(answer, question_type)
    selected = [answer]
    used_keys = {answer_key}
    used_names = set(answer_names)
    used_values = {answer_value} if answer_value else set()

    candidates = quiz_candidates_for_type(countries, question_type)
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

def build_quiz():
    data = get_data()
    countries = public_country_list(data)
    if len(countries) < 4:
        return None
    lookup = public_countries_by_key(data)
    answer_source = countries
    if state.quiz_mode == 'review':
        review_source = [lookup[key] for key in get_review_keys() if key in lookup]
        if not review_source:
            return None
        answer_source = review_source

    question_types = ['desc', 'capital', 'flag', 'period']
    question_types.extend(f'profile_{field}' for field in PROFILE_FIELDS)
    question_types.extend(f'detail_{field}' for field in DETAIL_QUIZ_FIELDS)

    question_pools = []
    for question_type in question_types:
        if not quiz_question_matches_category(question_type):
            continue
        candidates = quiz_candidates_for_type(answer_source, question_type)
        if candidates:
            question_pools.append((question_type, candidates))
    if not question_pools:
        return None

    for _ in range(80):
        question_type, candidates = random.choice(question_pools)
        answer = random.choice(candidates)
        options = build_quiz_options(answer, question_type, countries)
        if options:
            return {
                'type': question_type,
                'answer_key': country_key(answer),
                'options': [country_key(option) for option in options],
                'selected_key': None,
                'answered': False,
            }

    return None

def quiz_view_parts(quiz, answer):
    question_type = quiz.get('type')
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
    elif question_type.startswith('profile_'):
        field = question_type.replace('profile_', '', 1)
        value = profile_value(answer, field)
        question = t('quiz_profile').format(label=t('labels', field), value=value)
        return question, '', None
    elif question_type.startswith('detail_'):
        field = question_type.replace('detail_', '', 1)
        value = detail_value(answer, field)
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
    state.quiz = build_quiz()
    if state.quiz_mode == 'review' and not state.quiz:
        ui.notify(t('review_empty'), color='info')
        state.quiz_mode = 'normal'
        state.quiz = build_quiz()
    show_screen('quiz')

def set_quiz_difficulty(difficulty):
    state.quiz_difficulty = difficulty
    start_quiz()

def set_quiz_category(category):
    state.quiz_category = category
    start_quiz()

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

def country_battle_power(country):
    area = parse_profile_number(raw_profile_value(country, 'area'))
    population = parse_profile_number(raw_profile_value(country, 'population'))
    power = int(area * population)
    while power > 9999:
        power //= 10
    return max(1, power)

def battle_country_list(data=None):
    data = data or get_data()
    return list(data.get('countries', []))

def battle_country_keys(data=None):
    return [country_key(country) for country in battle_country_list(data)]

def battle_unlock_country_keys(data=None):
    return [country_key(country) for country in public_country_list(data)]

def battle_country_lookup(data=None):
    return {country_key(country): country for country in battle_country_list(data)}

def battle_is_user_eligible(username=None, user=None):
    username = username or state.current_user
    if not username or username == GUEST_USERNAME:
        return False
    if user is None:
        user_data = load_user_data()
        user = get_users(user_data).get(username)
    if not user:
        return False
    ensure_user_defaults(user)
    needed = set(battle_unlock_country_keys())
    if not needed:
        return False
    return needed.issubset(set(user.get('viewed_keys', [])))

def deal_battle_hand():
    keys = battle_country_keys()
    if len(keys) <= 5:
        return list(keys)
    return random.sample(keys, 5)

def current_battle_room():
    username = state.current_user
    if not username:
        return None
    room_id = state.battle_id or BATTLE_USER_ROOM.get(username)
    room = BATTLE_ROOMS.get(room_id)
    if room and username in room.get('players', []):
        state.battle_id = room_id
        return room
    state.battle_id = None
    BATTLE_USER_ROOM.pop(username, None)
    return None

def create_battle_room(player_one, player_two):
    global BATTLE_COUNTER
    BATTLE_COUNTER += 1
    room_id = f'battle-{BATTLE_COUNTER}'
    room = {
        'id': room_id,
        'players': [player_one, player_two],
        'hp': {player_one: 10000, player_two: 10000},
        'hands': {player_one: deal_battle_hand(), player_two: deal_battle_hand()},
        'reload_after_turn': [],
        'submitted': {},
        'log': [],
        'turn': 1,
        'winner': None,
    }
    BATTLE_ROOMS[room_id] = room
    BATTLE_USER_ROOM[player_one] = room_id
    BATTLE_USER_ROOM[player_two] = room_id
    if state.current_user in room['players']:
        state.battle_id = room_id
    return room

def join_battle_queue():
    username = state.current_user
    if not battle_is_user_eligible(username):
        ui.notify(t('battle_locked'), color='warning')
        return
    if current_battle_room():
        refresh_battle_view()
        return
    for waiting_user in list(BATTLE_QUEUE):
        if waiting_user == username:
            continue
        if not battle_is_user_eligible(waiting_user):
            BATTLE_QUEUE.remove(waiting_user)
            continue
        BATTLE_QUEUE.remove(waiting_user)
        create_battle_room(waiting_user, username)
        ui.notify(t('battle_title'), color='positive')
        refresh_battle_view()
        return
    if username not in BATTLE_QUEUE:
        BATTLE_QUEUE.append(username)
    refresh_battle_view()

def cancel_battle_queue():
    username = state.current_user
    if username in BATTLE_QUEUE:
        BATTLE_QUEUE.remove(username)
    refresh_battle_view()

def leave_finished_battle(join_again=False):
    username = state.current_user
    room = current_battle_room()
    if room:
        BATTLE_USER_ROOM.pop(username, None)
        if not any(BATTLE_USER_ROOM.get(player) == room['id'] for player in room.get('players', [])):
            BATTLE_ROOMS.pop(room['id'], None)
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

def battle_power_for_keys(keys):
    lookup = battle_country_lookup()
    return sum(country_battle_power(lookup[key]) for key in keys if key in lookup)

def battle_tags_for_keys(keys):
    lookup = battle_country_lookup()
    tags = set()
    for key in keys:
        country = lookup.get(key)
        if country:
            tags.update(country.get('tags', []))
    return tags

def shared_battle_tag_labels(first_keys, second_keys):
    shared_tags = sorted(battle_tags_for_keys(first_keys) & battle_tags_for_keys(second_keys), key=lambda tag: tag_label(tag).lower())
    return [tag_label(tag) for tag in shared_tags]

def resolve_battle_turn(room):
    players = room.get('players', [])
    if len(players) != 2:
        return
    player_one, player_two = players
    first = room['submitted'].get(player_one, {})
    second = room['submitted'].get(player_two, {})
    power_one = int(first.get('power', 0))
    power_two = int(second.get('power', 0))
    shared_labels = shared_battle_tag_labels(first.get('keys', []), second.get('keys', []))
    bonus_multiplier = 1.5 if shared_labels else 1
    bonus_text = f" / {t('battle_tag_bonus')} x1.5: {', '.join(shared_labels[:3])}" if shared_labels else ''
    if power_one > power_two:
        damage = int((power_one - power_two) * bonus_multiplier)
        room['hp'][player_two] = max(0, room['hp'].get(player_two, 10000) - damage)
        result_text = f"{player_one} {power_one} - {power_two} {player_two}: {player_two} -{damage}{bonus_text}"
    elif power_two > power_one:
        damage = int((power_two - power_one) * bonus_multiplier)
        room['hp'][player_one] = max(0, room['hp'].get(player_one, 10000) - damage)
        result_text = f"{player_one} {power_one} - {power_two} {player_two}: {player_one} -{damage}{bonus_text}"
    else:
        result_text = f"{player_one} {power_one} - {power_two} {player_two}: draw"

    reload_set = set(room.get('reload_after_turn', []))
    for player in players:
        submitted = room['submitted'].get(player, {})
        hand = room['hands'].setdefault(player, [])
        if submitted.get('defenseless'):
            room['hands'][player] = deal_battle_hand()
            reload_set.discard(player)
        else:
            for key in submitted.get('keys', []):
                if key in hand:
                    hand.remove(key)
            if not hand:
                reload_set.add(player)
    room['reload_after_turn'] = list(reload_set)

    room['log'].insert(0, f"{t('battle_turn')} {room.get('turn', 1)}: {result_text}")
    del room['log'][12:]
    room['submitted'] = {}
    room['turn'] = int(room.get('turn', 1)) + 1

    if room['hp'].get(player_one, 0) <= 0 or room['hp'].get(player_two, 0) <= 0:
        winner = player_two if room['hp'].get(player_one, 0) <= 0 else player_one
        room['winner'] = winner
        add_battle_win(winner)

def toggle_battle_card(key, checked):
    selected = set(state.battle_selected_keys or set())
    if checked:
        selected.add(key)
    else:
        selected.discard(key)
    state.battle_selected_keys = selected

def submit_battle_hand():
    room = current_battle_room()
    username = state.current_user
    if not room or room.get('winner') or not username:
        refresh_battle_view()
        return
    if username in room.get('submitted', {}):
        ui.notify(t('battle_wait_opponent'), color='info')
        return
    reload_set = set(room.get('reload_after_turn', []))
    hand = room['hands'].setdefault(username, [])
    defenseless = username in reload_set or not hand
    selected = [] if defenseless else [key for key in hand if key in state.battle_selected_keys]
    room['submitted'][username] = {
        'keys': selected,
        'power': 0 if defenseless else battle_power_for_keys(selected),
        'defenseless': defenseless,
    }
    state.battle_selected_keys = set()
    if len(room.get('submitted', {})) >= 2:
        resolve_battle_turn(room)
    refresh_battle_view()

# ========================================
# 画面切り替え
# ========================================
@app.get('/api/data')
def get_data():
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

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

def save_data(data):
    data = dict(data)
    for key in ['users', 'history', 'favorites']:
        data.pop(key, None)
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
    history = user.setdefault('history', [])
    history.insert(0, new_record)
    del history[50:]
    persist_current_user_data(user_data)

def clear_history():
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if user:
        user['history'] = []
        persist_current_user_data(user_data)

# ========================================
# 画面切り替え
# ========================================
def show_screen(screen_name):
    protected_screens = ['main', 'result', 'quiz', 'compare', 'timeline', 'map', 'network', 'account', 'users', 'battle']
    if screen_name in protected_screens and not state.current_user:
        ui.notify(t('login_required'), color='warning')
        screen_name = 'top'

    if screen_name == 'top':
        state.search_keyword = ''
        state.filter_region = None
        state.filter_tag = None
        state.sort_field = 'name'
        state.sort_order = 'asc'
        state.show_favorites_only = False
        state.collection_filter = None
        state.page = 1
        if history_drawer.value:
            history_drawer.hide()
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
    battle_screen.set_visibility(screen_name == 'battle')
    help_screen.set_visibility(screen_name == 'help')
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
    if screen_name == 'battle':
        refresh_battle_view()
    if screen_name == 'help':
        refresh_help_view()

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
    if battle_screen.visible: refresh_battle_view()
    if help_screen.visible: refresh_help_view()

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
    if battle_screen.visible:
        refresh_battle_view()
    if help_screen.visible:
        refresh_help_view()

def toggle_ui_mode():
    state.ui_mode = 'pc' if is_mobile_ui() else 'mobile'
    refresh_current_screen()

def ui_mode_tooltip():
    return t('switch_to_pc') if is_mobile_ui() else t('switch_to_mobile')

def ui_mode_icon():
    return 'desktop_windows' if is_mobile_ui() else 'smartphone'

# ========================================
# 1. トップ画面
# ========================================
with ui.right_drawer(value=False).classes('bg-gray-100') as history_drawer:
    history_content = ui.column().classes('w-full p-4')

def jump_from_history(history_item):
    data = get_data()
    hist_key = history_item.get('key')
    if hist_key:
        target_country = countries_by_key(data).get(hist_key)
        if target_country:
            state.selected_country = target_country
            history_drawer.hide()
            show_screen('result')
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
        state.selected_country = target_country
        history_drawer.hide()
        show_screen('result')

def refresh_history_content():
    history_content.clear()
    user = get_current_user_record()
    histories = user.get('history', []) if user else []
    with history_content:
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.label(t('history')).classes('text-xl font-bold text-gray-700')
            ui.button(icon='close', on_click=lambda: history_drawer.toggle()).props('flat round dense')
        if not histories:
            ui.label(t('history_empty')).classes('text-gray-400')
        with ui.column().classes('w-full gap-2'):
            for h in histories:
                with ui.card().classes('w-full p-3 bg-white text-sm border-l-4 border-blue-500 cursor-pointer hover:bg-blue-50 transition') as card:
                    card.on('click', lambda _, item=h: jump_from_history(item))
                    ui.label(h['name']).classes('font-bold text-gray-800')
                    ui.label(format_timestamp(h.get('timestamp'))).classes('text-xs text-gray-400 mt-1')

def render_header(container):
    container.clear()
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
                with ui.dropdown_button(text=state.lang.upper(), icon='language', auto_close=True).props('flat color=white dense'):
                    ui.item('日本語 (JA)', on_click=lambda: switch_language('ja'))
                    ui.item('English (EN)', on_click=lambda: switch_language('en'))
                    ui.item('中文 (ZH)', on_click=lambda: switch_language('zh'))
                if state.current_user:
                    header_user = get_current_user_record()
                    render_avatar_image(
                        current_user_avatar_url(header_user),
                        header_user,
                        'w-8 h-8 rounded-full border-2 border-white shadow bg-white flex-shrink-0',
                        icon_size='2rem',
                        icon_classes='text-white',
                    )
                    ui.label(current_user_label()) \
                        .classes('text-sm font-bold px-2 py-1 rounded-full bg-white shadow-sm') \
                        .style(f'color: {user_name_color(header_user)};')
                def open_history():
                    refresh_history_content()
                    history_drawer.toggle()
                menu_text = {'ja': '機能', 'en': 'Features', 'zh': '功能'}.get(state.lang, 'Features')
                with ui.dropdown_button(text=menu_text, icon='apps', auto_close=True).props('flat color=white dense'):
                    ui.item(help_labels()['nav'], on_click=lambda: show_screen('help'))
                    ui.separator()
                    ui.item(t('quiz'), on_click=lambda: start_quiz('normal'))
                    ui.item(t('map'), on_click=lambda: show_screen('map'))
                    ui.item(t('network'), on_click=lambda: show_screen('network'))
                    ui.item(t('compare'), on_click=lambda: show_screen('compare'))
                    ui.item(t('timeline'), on_click=lambda: show_screen('timeline'))
                    ui.item(t('users'), on_click=lambda: show_screen('users'))
                    ui.item(t('account'), on_click=lambda: show_screen('account'))
                    ui.separator()
                    ui.item(t('history'), on_click=open_history)
                if state.current_user:
                    ui.button(icon='logout', on_click=logout_user).props('flat round color=white').tooltip(t('logout'))

# ========================================
# 2. メイン画面
# ========================================
with ui.column().classes('w-full h-screen items-center justify-center gap-4 bg-gray-50') as top_screen:
    top_container = ui.column().classes('items-center gap-4')
    def refresh_top_ui():
        top_container.clear()
        if not state.current_user:
            request_browser_backup_restore()
        update_mode_classes(top_container, 'items-center gap-4', 'items-center gap-3 px-6 text-center max-w-sm')
        with top_container:
            ui.icon('public', size='4.5rem' if is_mobile_ui() else '6rem').classes('text-[#1a2332]')
            ui.label(t('app_title')).classes('text-3xl font-bold text-[#1a2332]' if is_mobile_ui() else 'text-5xl font-bold text-[#1a2332]')
            ui.label(t('subtitle')).classes('text-base text-gray-500' if is_mobile_ui() else 'text-xl text-gray-500')
            ui.button(t('switch_to_pc') if is_mobile_ui() else t('switch_to_mobile'), icon=ui_mode_icon(), on_click=toggle_ui_mode) \
                .props('outline color=primary') \
                .classes('w-full px-6 py-2 rounded-full shadow-sm font-bold' if is_mobile_ui() else 'px-8 py-2 rounded-full shadow-sm font-bold')
            ui.button(help_labels()['nav'], icon='help', on_click=lambda: show_screen('help')) \
                .props('outline color=primary') \
                .classes('w-full px-6 py-2 rounded-full shadow-sm font-bold' if is_mobile_ui() else 'px-8 py-2 rounded-full shadow-sm font-bold')
            if state.current_user:
                top_user = get_current_user_record()
                ui.label(t('logged_in_as').format(user=current_user_label())) \
                    .classes('px-3 py-2 rounded-full bg-white border shadow-sm text-sm font-bold') \
                    .style(f'color: {user_name_color(top_user)};')
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
                    password_input = ui.input(label=t('password')).props('outlined dense type=password').classes('w-full')
                    with ui.row().classes('w-full gap-2 items-center'):
                        ui.button(t('login'), icon='login', on_click=lambda: login_user(username_input.value, password_input.value)) \
                            .classes('flex-grow bg-[#1a2332] text-white')
                        ui.button(t('register'), icon='person_add', on_click=lambda: register_user(username_input.value, password_input.value)) \
                            .props('outline color=primary') \
                            .classes('flex-grow')
                    ui.button(t('guest_login'), icon='person', on_click=guest_login) \
                        .props('outline color=grey') \
                        .classes('w-full')
            with ui.row().classes('mt-8 gap-4'):
                ui.link('JA', '#').on('click', lambda: switch_language('ja'))
                ui.link('EN', '#').on('click', lambda: switch_language('en'))
                ui.link('ZH', '#').on('click', lambda: switch_language('zh'))
    refresh_top_ui()

# ========================================
# 使い方ページ
# ========================================
with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as help_screen:
    header_container_help = ui.column().classes('w-full p-0 m-0')
    help_content = ui.column().classes('w-full max-w-4xl p-8 gap-5 self-center')

    def refresh_help_view():
        render_header(header_container_help)
        update_mode_classes(
            help_content,
            'w-full max-w-4xl p-8 gap-5 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        help_content.clear()
        labels = help_labels()
        with help_content:
            ui.label(labels['title']).classes('text-3xl font-bold text-[#1a2332]')
            ui.markdown(labels['intro']).classes('text-gray-600 text-lg')
            with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-4'):
                for title, body in labels['sections']:
                    with ui.card().classes('w-full p-5 gap-2'):
                        ui.label(title).classes('text-xl font-bold text-[#1a2332]')
                        ui.markdown(body).classes('text-gray-700 leading-relaxed')
            with ui.row().classes('w-full gap-2 flex-col' if is_mobile_ui() else 'w-full gap-3'):
                ui.button('ENTER', icon='search', on_click=lambda: show_screen('main')) \
                    .props('color=primary') \
                    .classes('w-full' if is_mobile_ui() else '')
                ui.button(t('back_home'), icon='home', on_click=lambda: show_screen('top')) \
                    .props('outline color=grey') \
                    .classes('w-full' if is_mobile_ui() else '')

with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as main_screen:
    header_container_main = ui.column().classes('w-full p-0 m-0')

    with ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center') as main_content:
        search_area_container = ui.card().classes('w-full p-6 bg-blue-50 shadow-sm border border-blue-100')
        list_container = ui.column().classes('w-full gap-4')
        hits_label = ui.label()

        region_options, tag_options = get_filter_options()

        def update_keyword(e):
            state.search_keyword = e.value
            state.page = 1
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
            state.show_favorites_only = not state.show_favorites_only
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
                ui.label(t('search_label')).classes('text-sm font-bold text-blue-800 mb-1')
                with ui.row().classes('w-full gap-2 items-stretch flex-wrap' if is_mobile_ui() else 'w-full gap-2 items-center'):
                    ui.input(value=state.search_keyword, on_change=update_keyword) \
                        .props('rounded outlined prepend-inner-icon=search clearable') \
                        .classes('text-base w-full bg-white shadow-inner' if is_mobile_ui() else 'text-lg flex-grow bg-white shadow-inner') \
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
                        .classes('w-full bg-white' if is_mobile_ui() else 'w-48 bg-white')
                    ui.select(t_opts, value=selected_tag_label(), label=t('labels', 'tags'),on_change=lambda e: set_tag_filter(e.value), clearable=True) \
                        .classes('w-full bg-white' if is_mobile_ui() else 'w-48 bg-white')
                    fav_color = 'amber' if state.show_favorites_only else 'grey'
                    ui.button(t('favorites_only'), icon='star', on_click=toggle_favorites_filter) \
                        .props(f'color={fav_color}') \
                        .classes('w-full px-4 py-2 shadow-md' if is_mobile_ui() else 'px-4 py-2 shadow-md')
                    collection_names = list(get_collections().keys())
                    if collection_names:
                        ui.select(collection_names, value=state.collection_filter, label=t('collections'), on_change=lambda e: set_collection_filter(e.value), clearable=True) \
                            .classes('w-full bg-white' if is_mobile_ui() else 'w-48 bg-white')

                with ui.row().classes('w-full gap-3 items-stretch mt-4 flex-col' if is_mobile_ui() else 'w-full justify-between items-center mt-4'):
                    with ui.button_group().props('unelevated'):
                        for key in ['All', 'Present', 'Past']:
                            label = t('tabs', key)
                            color = 'blue' if state.filter_type == key else 'white'
                            text_color = 'white' if state.filter_type == key else 'grey-8'
                            ui.button(label, on_click=lambda e, k=key: set_type_filter(k)) \
                                .props(f'color={color} text-color={text_color}')
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
            keyword = state.search_keyword.lower() if state.search_keyword else ""
            countries = data.get('countries', [])
            filtered = []
            for c in countries:
                # サプライズ用の国は、検索語がある時だけ候補に入れます。
                if is_hidden_country(c) and not keyword:
                    continue
                if state.filter_type != 'All' and c['type'] != state.filter_type:
                    continue
                if state.filter_region and state.filter_region != c.get('region'):
                    continue
                if state.filter_tag and state.filter_tag not in c.get('tags', []):
                    continue
                if state.show_favorites_only and country_key(c) not in favorites:
                    continue
                if state.collection_filter and country_key(c) not in selected_collection:
                    continue

                name_local = get_localized_text(c['names'])
                name_text = ' '.join(str(name) for name in c.get('names', {}).values())
                desc_local = get_localized_text(c['desc'])
                tag_text = ' '.join(tag_search_text(tag) for tag in c.get('tags', []))
                period = c.get('period') or {}
                period_text = ' '.join([
                    period_label(c),
                    str(period.get('start', '')),
                    str(period.get('end') or ''),
                ])
                profile_text = profile_search_text(c)
                detail_text = detail_search_text(c)
                region_text = region_search_text(c.get('region', ''))
                search_target = f"{name_local} {name_text} {desc_local} {tag_text} {period_text} {profile_text} {detail_text} {region_text}".lower()
                if keyword in search_target:
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
            state.selected_country = country
            add_history(country)
            show_screen('result')

# ========================================
# 3. 結果画面
# ========================================
with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as result_screen:
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
                ui.button(t('back_search'), icon='arrow_back', on_click=lambda: show_screen('main')) \
                    .props('flat color=grey dense text-lg') \
                    .classes('w-full' if is_mobile_ui() else '')
                favorite_label = t('favorite_remove') if is_favorite(c) else t('favorite_add')
                favorite_icon = 'star' if is_favorite(c) else 'star_border'
                ui.button(favorite_label, icon=favorite_icon, on_click=lambda: (toggle_favorite(c), refresh_result_view())) \
                    .props('color=amber') \
                    .classes('w-full' if is_mobile_ui() else '')

            tabs = detail_tab_labels()
            related = related_countries(c)

            with ui.card().classes('w-full p-0 overflow-hidden bg-white'):
                with ui.row().classes('w-full bg-white p-4 gap-4 items-start flex-col' if is_mobile_ui() else 'w-full bg-white p-6 gap-6 items-start'):
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
                with ui.tabs().props('dense inline-label mobile-arrows outside-arrows').classes('w-full bg-white text-[#1a2332]') as detail_tabs:
                    basic_tab = ui.tab(tabs['basic'], icon='info')
                    desc_tab = ui.tab(tabs['desc'], icon='article')
                    if not hide_external_links:
                        map_tab = ui.tab(tabs['map'], icon='map')
                    personal_tab = ui.tab(tabs['personal'], icon='edit_note')
                    related_tab = ui.tab(tabs['related'], icon='account_tree')

                with ui.tab_panels(detail_tabs, value=basic_tab).classes('w-full bg-white'):
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

                                with ui.column().classes('gap-1'):
                                    ui.label(t('labels', 'capital')).classes('text-xs font-bold text-gray-400 uppercase')
                                    ui.label(get_localized_text(c.get('capital', '-'))).classes('text-lg')
                                if detail_period:
                                    with ui.column().classes('gap-1'):
                                        ui.label(period_field_label(c)).classes('text-xs font-bold text-gray-400 uppercase')
                                        ui.label(detail_period).classes('text-lg font-bold text-orange-700')
                                with ui.column().classes('gap-1'):
                                    ui.label(t('labels', 'region')).classes('text-xs font-bold text-gray-400 uppercase')
                                    ui.label(region_label(c.get('region', '-'))).classes('text-lg')
                                with ui.column().classes('gap-1'):
                                    ui.label(t('labels', 'tags')).classes('text-xs font-bold text-gray-400 uppercase')
                                    with ui.row().classes('gap-1 flex-wrap'):
                                        for tag in c.get('tags', []):
                                            tag_chip(tag, dense=False)
                            with ui.column().classes('gap-4'):
                                for label, value in profile_rows(c):
                                    with ui.column().classes('gap-1'):
                                        ui.label(label).classes('text-xs font-bold text-gray-400 uppercase')
                                        ui.label(value).classes('text-lg')

                    with ui.tab_panel(desc_tab).classes('p-4' if is_mobile_ui() else 'p-6'):
                        with ui.column().classes('w-full gap-3'):
                            ui.label(t('labels', 'desc')).classes('text-xs font-bold text-gray-400 uppercase')
                            ui.markdown(get_localized_text(c['desc'])).classes('text-gray-800 leading-relaxed text-lg')
                            for label, value in detail_rows(c):
                                ui.separator().classes('my-1')
                                ui.label(label).classes('text-xs font-bold text-gray-400 uppercase')
                                ui.markdown(value).classes('text-gray-800 leading-relaxed')

                    if not hide_external_links:
                        with ui.tab_panel(map_tab).classes('p-4' if is_mobile_ui() else 'p-6'):
                            with ui.column().classes('w-full gap-3'):
                                with ui.row().classes('w-full justify-between items-center flex-wrap gap-2'):
                                    ui.label(t('map')).classes('text-lg font-bold text-[#1a2332]')
                                    ui.link('Google Maps', map_link, new_tab=True).classes('text-green-700 font-bold')
                                if map_note_text:
                                    ui.label(map_note_text).classes('text-sm text-gray-500')
                                render_map_embed(c, height=420 if not is_mobile_ui() else 300)

                    with ui.tab_panel(personal_tab).classes('p-4' if is_mobile_ui() else 'p-6'):
                        with ui.column().classes('w-full gap-5'):
                            with ui.column().classes('w-full gap-3'):
                                ui.label(t('notes')).classes('text-lg font-bold text-[#1a2332]')
                                note_input = ui.textarea(value=get_note_for_country(c), placeholder=t('notes')) \
                                    .props('outlined autogrow') \
                                    .classes('w-full')
                                ui.button(t('save_note'), icon='save', on_click=lambda country=c, field=note_input: save_note_for_country(country, field.value)) \
                                    .props('color=primary') \
                                    .classes('self-start')

                            ui.separator()
                            with ui.column().classes('w-full gap-3'):
                                ui.label(t('collections')).classes('text-lg font-bold text-[#1a2332]')
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
                            ui.label(t('related_countries')).classes('text-lg font-bold text-[#1a2332]')
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
with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as quiz_screen:
    header_container_quiz = ui.column().classes('w-full p-0 m-0')
    quiz_content = ui.column().classes('w-full max-w-3xl p-8 gap-6 self-center')

    def select_quiz_option(option_key):
        if not state.quiz:
            return
        if state.quiz.get('answered'):
            return
        state.quiz['selected_key'] = option_key
        state.quiz['answered'] = True
        update_quiz_stats(
            option_key == state.quiz.get('answer_key'),
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
            state.selected_country = country
            add_history(country)
            show_screen('result')

    def refresh_quiz_view():
        render_header(header_container_quiz)
        update_mode_classes(
            quiz_content,
            'w-full max-w-3xl p-8 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        quiz_content.clear()
        if not state.quiz:
            state.quiz = build_quiz()

        quiz = state.quiz
        if not quiz:
            with quiz_content:
                ui.label(t('quiz_title')).classes('text-3xl font-bold text-[#1a2332]')
                ui.label('No quiz data available.').classes('text-gray-500')
            return

        lookup = countries_by_key()
        answer = lookup.get(quiz['answer_key'])
        question, description, image = quiz_view_parts(quiz, answer) if answer else ('', '', None)

        with quiz_content:
            with ui.row().classes('w-full gap-2 items-stretch flex-col' if is_mobile_ui() else 'w-full justify-between items-center'):
                ui.label(t('quiz_title')).classes('text-2xl font-bold text-[#1a2332]' if is_mobile_ui() else 'text-3xl font-bold text-[#1a2332]')
                ui.button(t('quiz_next'), icon='refresh', on_click=start_quiz).props('outline color=primary').classes('w-full' if is_mobile_ui() else '')

            stats = get_quiz_stats()
            ui.label(t('quiz_stats').format(
                correct=stats.get('correct', 0),
                answered=stats.get('answered', 0),
                streak=stats.get('streak', 0),
                best=stats.get('best_streak', 0),
            )).classes('text-sm text-gray-600 font-bold')
            review_count = len(get_review_keys())
            with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                ui.label(t('quiz_mode')).classes('text-sm font-bold text-gray-500')
                for key, label_key in [('normal', 'quiz_mode_normal'), ('review', 'quiz_mode_review')]:
                    color = 'primary' if state.quiz_mode == key else 'grey'
                    ui.button(t(label_key) if key == 'normal' else f'{t(label_key)} ({review_count})', on_click=lambda _, m=key: start_quiz(m)) \
                        .props(f'outline color={color} dense')
            with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                ui.label(t('difficulty')).classes('text-sm font-bold text-gray-500')
                for key in ['easy', 'medium', 'hard']:
                    color = 'primary' if state.quiz_difficulty == key else 'grey'
                    ui.button(t(f'difficulty_{key}'), on_click=lambda _, d=key: set_quiz_difficulty(d)) \
                        .props(f'outline color={color} dense')
            with ui.row().classes('w-full gap-2 items-center flex-wrap'):
                ui.label(t('quiz_category')).classes('text-sm font-bold text-gray-500')
                for key, label_key in QUIZ_CATEGORY_OPTIONS:
                    color = 'primary' if state.quiz_category == key else 'grey'
                    ui.button(t(label_key), on_click=lambda _, c=key: set_quiz_category(c)) \
                        .props(f'outline color={color} dense')

            with ui.card().classes('w-full p-4 gap-4' if is_mobile_ui() else 'w-full p-6 gap-4'):
                ui.label(question).classes('text-lg font-bold text-gray-800' if is_mobile_ui() else 'text-xl font-bold text-gray-800')
                if description:
                    ui.markdown(description).classes('text-gray-700 text-base' if is_mobile_ui() else 'text-gray-700 text-lg')
                if image:
                    ui.image(image).classes('w-full shadow-md border rounded' if is_mobile_ui() else 'w-56 shadow-md border rounded')

                with ui.column().classes('w-full gap-2 mt-2'):
                    for option_key in quiz['options']:
                        option = lookup.get(option_key)
                        if not option:
                            continue
                        is_selected = quiz.get('selected_key') == option_key
                        is_answer = quiz.get('answer_key') == option_key
                        if quiz.get('answered') and is_answer:
                            color = 'green'
                        elif quiz.get('answered') and is_selected:
                            color = 'red'
                        else:
                            color = 'blue' if is_selected else 'white'
                        text_color = 'white' if color in ['green', 'red', 'blue'] else 'grey-9'
                        ui.button(get_localized_text(option['names']), on_click=lambda _, key=option_key: select_quiz_option(key)) \
                            .props(f'color={color} text-color={text_color}') \
                            .classes('w-full justify-start text-left')

                if quiz.get('answered') and answer:
                    correct = quiz.get('selected_key') == quiz.get('answer_key')
                    message = t('quiz_correct') if correct else t('quiz_wrong')
                    badge_color = 'green' if correct else 'red'
                    with ui.row().classes('items-center gap-3 mt-4'):
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
            rows.extend([
                (t('labels', 'region'), region_label(country.get('region', '-'))),
                (t('labels', 'tags'), ', '.join(tag_label(tag) for tag in country.get('tags', []))),
            ])
            for label, value in rows:
                ui.label(label).classes('text-xs font-bold text-gray-400 uppercase')
                ui.label(value).classes('text-base text-gray-800')
            ui.label(t('labels', 'desc')).classes('text-xs font-bold text-gray-400 uppercase')
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
            ui.label(t('compare_title')).classes('text-3xl font-bold text-[#1a2332]')
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
            ui.label(t('timeline_title')).classes('text-3xl font-bold text-[#1a2332]')
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
            ui.label(t('map_title')).classes('text-3xl font-bold text-[#1a2332]')
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
            ui.label(t('network_title')).classes('text-3xl font-bold text-[#1a2332]')
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

    def restore_browser_users_for_list():
        request_browser_backup_restore()
        ui.notify(t('users_restore_browser'), color='info')
        ui.timer(0.8, refresh_users_view, once=True)

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

    def refresh_users_view():
        if not state.users_browser_restore_requested:
            state.users_browser_restore_requested = True
            request_browser_backup_restore()
            ui.timer(0.8, refresh_users_view, once=True)
        render_header(header_container_users)
        update_mode_classes(
            users_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        users_content.clear()
        lookup = public_countries_by_key()
        with users_content:
            ui.label(t('users_title')).classes('text-3xl font-bold text-[#1a2332]')
            with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                ui.label(t('public_users_notice')).classes('text-sm text-gray-500')
                ui.button(t('users_restore_browser'), icon='cloud_sync', on_click=restore_browser_users_for_list) \
                    .props('outline color=primary dense')
            profiles = public_user_profiles()
            total_count = len(profiles)
            total_pages = max(1, (total_count + state.users_items_per_page - 1) // state.users_items_per_page)
            state.users_page = max(1, min(state.users_page, total_pages))
            start_index = (state.users_page - 1) * state.users_items_per_page
            end_index = min(start_index + state.users_items_per_page, total_count)
            display_profiles = profiles[start_index:end_index]
            if not profiles:
                ui.label(t('no_users')).classes('text-gray-500')
                return
            ui.label(f'{t("users_count")}: {start_index + 1}-{end_index} / {total_count}') \
                .classes('text-sm text-gray-500 font-bold')
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
                                    ui.label(profile['username']) \
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
                        with ui.expansion(f"{t('public_favorites')} ({len(profile['favorites'])})", icon='star').classes('w-full'):
                            render_public_country_chips(profile['favorites'], lookup)
                        with ui.expansion(f"{t('public_collections')} ({len(profile['collections'])})", icon='folder').classes('w-full'):
                            if not profile['collections']:
                                ui.label(t('no_collections')).classes('text-xs text-gray-500')
                            for collection in profile['collections']:
                                with ui.column().classes('w-full gap-2 border-t border-gray-200 py-2'):
                                    ui.label(f"{collection['name']} ({len(collection['keys'])})").classes('text-sm font-bold text-gray-700')
                                    render_public_country_chips(collection['keys'], lookup)
            render_users_pagination(total_pages)

# ========================================
# 10. 国力対戦ページ
# ========================================
with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as battle_screen:
    header_container_battle = ui.column().classes('w-full p-0 m-0')
    battle_content = ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center')

    def render_hp_bar(label, hp):
        with ui.column().classes('w-full gap-1'):
            ui.label(f'{label}: {t("battle_hp")} {hp} / 10000').classes('text-sm font-bold text-gray-700')
            ui.linear_progress(value=max(0, min(1, hp / 10000))).props('color=red')

    def render_battle_card(key, lookup):
        country = lookup.get(key)
        if not country:
            return
        power = country_battle_power(country)
        selected = key in state.battle_selected_keys
        with ui.column().classes('gap-2 rounded border border-gray-200 bg-white p-3'):
            with ui.row().classes('w-full items-center gap-2 no-wrap'):
                ui.checkbox(value=selected, on_change=lambda e, k=key: toggle_battle_card(k, e.value)).props('dense')
                ui.label(get_localized_text(country['names'])).classes('font-bold text-[#1a2332] text-sm')
            render_flag_frame(country, 'w-full rounded border border-gray-200', 'w-full h-full object-cover')
            ui.label(f'{t("battle_power")}: {power}').classes('text-xs font-bold text-red-700')

    def render_battle_room(room):
        players = room.get('players', [])
        if len(players) != 2:
            return
        username = state.current_user
        opponent = players[0] if players[1] == username else players[1]
        lookup = battle_country_lookup()
        winner = room.get('winner')

        with ui.card().classes('w-full p-5 gap-4'):
            with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                ui.label(f'{t("battle_turn")} {room.get("turn", 1)}').classes('text-xl font-bold text-[#1a2332]')
                ui.button(t('battle_refresh'), icon='refresh', on_click=refresh_battle_view).props('outline color=primary dense')
            with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-4'):
                render_hp_bar(username, room['hp'].get(username, 10000))
                render_hp_bar(opponent, room['hp'].get(opponent, 10000))

            if winner:
                is_winner = winner == username
                ui.label(t('battle_win') if is_winner else t('battle_lose')) \
                    .classes('text-2xl font-bold text-green-700' if is_winner else 'text-2xl font-bold text-red-700')
                with ui.row().classes('w-full gap-2 flex-wrap'):
                    ui.button(t('battle_join'), icon='sports_esports', on_click=lambda: leave_finished_battle(True)).props('color=primary')
                    ui.button(t('account'), icon='person', on_click=lambda: (leave_finished_battle(False), show_screen('account'))).props('outline color=primary')
                return

            hand = room['hands'].setdefault(username, [])
            waiting_for_player = username in room.get('submitted', {})
            defenseless = username in set(room.get('reload_after_turn', [])) or not hand
            if waiting_for_player:
                ui.label(t('battle_wait_opponent')).classes('text-sm font-bold text-blue-700')
            elif defenseless:
                ui.label(t('battle_defenseless')).classes('text-sm font-bold text-red-700')
                ui.button(t('battle_submit'), icon='shield', on_click=submit_battle_hand).props('color=red')
            else:
                with ui.row().classes('w-full justify-between items-center gap-2 flex-wrap'):
                    ui.label(t('battle_hand')).classes('text-lg font-bold text-[#1a2332]')
                    ui.label(f'{t("battle_power")}: {battle_power_for_keys(state.battle_selected_keys)}').classes('text-sm font-bold text-red-700')
                with ui.grid(columns=1 if is_mobile_ui() else 5).classes('w-full gap-3'):
                    for key in hand:
                        render_battle_card(key, lookup)
                ui.button(t('battle_submit'), icon='sports_martial_arts', on_click=submit_battle_hand).props('color=primary')

        with ui.card().classes('w-full p-5 gap-3'):
            ui.label(t('battle_log')).classes('text-xl font-bold text-[#1a2332]')
            if not room.get('log'):
                ui.label('-').classes('text-gray-500')
            for entry in room.get('log', []):
                ui.label(entry).classes('text-sm text-gray-700')

    def refresh_battle_view():
        render_header(header_container_battle)
        update_mode_classes(
            battle_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        battle_content.clear()
        with battle_content:
            ui.label(t('battle_title')).classes('text-3xl font-bold text-[#1a2332]')
            user = get_current_user_record()
            if user:
                wins = int(user.get('battle_wins', 0))
                ui.label(f'{t("battle_wins")}: {crown_marks(wins) or "0"}').classes('text-lg font-bold text-yellow-700')
            if not battle_is_user_eligible(user=user):
                unlock_keys = set(battle_unlock_country_keys())
                total = len(unlock_keys)
                viewed = len(set((user or {}).get('viewed_keys', [])) & unlock_keys) if user else 0
                with ui.card().classes('w-full p-5 gap-2'):
                    ui.label(t('battle_locked')).classes('font-bold text-gray-700')
                    ui.label(f'{viewed} / {total}').classes('text-sm text-gray-500')
                return

            room = current_battle_room()
            if room:
                render_battle_room(room)
                return

            with ui.card().classes('w-full p-5 gap-4'):
                if state.current_user in BATTLE_QUEUE:
                    ui.label(t('battle_waiting')).classes('text-lg font-bold text-blue-700')
                    with ui.row().classes('w-full gap-2 flex-wrap'):
                        ui.button(t('battle_cancel'), icon='close', on_click=cancel_battle_queue).props('outline color=red')
                        ui.button(t('battle_refresh'), icon='refresh', on_click=refresh_battle_view).props('outline color=primary')
                else:
                    ui.button(t('battle_join'), icon='sports_esports', on_click=join_battle_queue).props('color=primary')

    def auto_refresh_battle():
        if not battle_screen.visible:
            return
        room = current_battle_room()
        if state.current_user in BATTLE_QUEUE or (room and (state.current_user in room.get('submitted', {}) or room.get('winner'))):
            refresh_battle_view()

    ui.timer(2.5, auto_refresh_battle)

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
            ui.label(t('account')).classes('text-3xl font-bold text-[#1a2332]')
            with ui.row().classes('w-full items-center gap-2 flex-wrap'):
                ui.label(t('logged_in_as').format(user=current_user_label())) \
                    .classes('px-3 py-2 rounded-full bg-white border shadow-sm text-sm font-bold') \
                    .style(f'color: {user_name_color(user)};')
                ui.button(t('users'), icon='groups', on_click=lambda: show_screen('users')) \
                    .props('outline color=primary dense')
            with ui.card().classes('w-full p-5 gap-4'):
                ui.label(t('avatar')).classes('text-xl font-bold text-[#1a2332]')
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
                        ui.upload(on_upload=upload_avatar_image, auto_upload=True) \
                            .props('accept=image/png,image/jpeg,image/webp,image/gif max-files=1 max-file-size=8388608') \
                            .classes('w-full')
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
                                ui.slider(min=50, max=250, step=5, value=adjust['zoom'], on_change=lambda e: update_avatar_adjustment('zoom', e.value)) \
                                    .props('label-always')
            with ui.grid(columns=1 if is_mobile_ui() else 5).classes('w-full gap-4'):
                render_stat_card(t('viewed_count'), f'{len(viewed)} / {total}', f'{int(len(viewed) / total * 100) if total else 0}%')
                render_stat_card(t('favorite_count'), str(len(favorites)))
                render_stat_card(t('review_count'), str(len(review)))
                render_stat_card(t('quiz'), f"{stats.get('correct', 0)} / {stats.get('answered', 0)}", f"{t('quiz_stats').format(correct=stats.get('correct', 0), answered=stats.get('answered', 0), streak=stats.get('streak', 0), best=stats.get('best_streak', 0))}")
                render_stat_card(t('battle_wins'), crown_marks(user.get('battle_wins', 0)) or '0')

            with ui.card().classes('w-full p-5 gap-4'):
                ui.label(t('account_settings')).classes('text-xl font-bold text-[#1a2332]')
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
                if state.current_user == GUEST_USERNAME:
                    ui.label(t('cannot_manage_guest')).classes('text-sm text-gray-500')
                else:
                    with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-4'):
                        with ui.column().classes('w-full gap-2'):
                            ui.label(t('change_username')).classes('text-sm font-bold text-gray-700')
                            new_username_input = ui.input(label=t('new_username'), value=state.current_user).props('outlined dense').classes('w-full')
                            rename_password_input = ui.input(label=t('current_password')).props('outlined dense type=password').classes('w-full')
                            ui.button(
                                t('change_username'),
                                icon='manage_accounts',
                                on_click=lambda name_field=new_username_input, pass_field=rename_password_input: rename_current_account(name_field.value, pass_field.value),
                            ).props('color=primary').classes('w-full' if is_mobile_ui() else 'self-start')
                        with ui.column().classes('w-full gap-2'):
                            ui.label(t('change_password')).classes('text-sm font-bold text-gray-700')
                            current_password_input = ui.input(label=t('current_password')).props('outlined dense type=password').classes('w-full')
                            new_password_input = ui.input(label=t('new_password')).props('outlined dense type=password').classes('w-full')
                            ui.button(
                                t('change_password'),
                                icon='lock_reset',
                                on_click=lambda current_field=current_password_input, new_field=new_password_input: change_current_password(current_field.value, new_field.value),
                            ).props('color=primary').classes('w-full' if is_mobile_ui() else 'self-start')
                    with ui.column().classes('w-full gap-2 border-t border-gray-200 pt-4'):
                        ui.label(t('delete_account')).classes('text-sm font-bold text-red-700')
                        ui.label(t('delete_account_warning')).classes('text-xs text-gray-500')
                        delete_password_input = ui.input(label=t('current_password')).props('outlined dense type=password').classes('w-full' if is_mobile_ui() else 'max-w-md')
                        ui.button(
                            t('delete_account'),
                            icon='delete_forever',
                            on_click=lambda pass_field=delete_password_input: delete_current_account(pass_field.value),
                        ).props('color=red').classes('w-full' if is_mobile_ui() else 'self-start')

            with ui.card().classes('w-full p-5 gap-3'):
                ui.label(t('battle_title')).classes('text-xl font-bold text-[#1a2332]')
                if battle_is_user_eligible(user=user):
                    ui.label(f'{t("battle_wins")}: {crown_marks(user.get("battle_wins", 0)) or "0"}').classes('text-sm font-bold text-yellow-700')
                    ui.button(t('battle_join'), icon='sports_esports', on_click=lambda: show_screen('battle')).props('color=primary')
                else:
                    ui.label(t('battle_locked')).classes('text-sm text-gray-500')

            backup = backup_labels()
            with ui.card().classes('w-full p-5 gap-3'):
                ui.label(backup['section']).classes('text-xl font-bold text-[#1a2332]')
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
                ui.label(t('collections')).classes('text-xl font-bold text-[#1a2332]')
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
                    ui.label(t('weakness')).classes('text-xl font-bold text-[#1a2332]')
                    weakness = quiz_weakness_rows()
                    if not weakness:
                        ui.label(t('no_quiz_history')).classes('text-gray-500')
                    for label, count in weakness:
                        with ui.row().classes('w-full justify-between items-center border-b py-2'):
                            ui.label(label).classes('font-bold text-gray-700')
                            ui.badge(str(count), color='red')
                with ui.card().classes('w-full p-5 gap-3'):
                    ui.label(t('quiz_history')).classes('text-xl font-bold text-[#1a2332]')
                    history = get_quiz_history()[:10]
                    if not history:
                        ui.label(t('no_quiz_history')).classes('text-gray-500')
                    for entry in history:
                        answer = lookup.get(entry.get('answer_key'))
                        selected = lookup.get(entry.get('selected_key'))
                        result_color = 'green' if entry.get('correct') else 'red'
                        with ui.row().classes('w-full gap-2 items-center border-b py-2 no-wrap'):
                            ui.badge('OK' if entry.get('correct') else 'NG', color=result_color)
                            with ui.column().classes('gap-0 flex-grow'):
                                ui.label(get_localized_text(answer['names']) if answer else '-').classes('font-bold text-gray-800')
                                selected_text = get_localized_text(selected['names']) if selected else '-'
                                ui.label(f"{quiz_category_label(entry.get('type'))} / {selected_text} / {format_timestamp(entry.get('timestamp'))}").classes('text-xs text-gray-500')

# ========================================
# 初期表示
# ========================================
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
