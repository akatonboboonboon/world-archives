"""
NiceGUI SPA テンプレート（API版）

3画面構成：トップ → メイン → 結果
JSONデータをAPIから取得して表示します。
"""
from nicegui import ui, app
import hashlib
import json
import os
import random
from datetime import datetime
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
USER_DATA_FILE = os.environ.get('USER_DATA_FILE', os.path.join(BASE_DIR, 'user_data.json'))
GUEST_USERNAME = '__guest__'
KAKASI_CONVERTER = pykakasi.kakasi() if pykakasi else None

def default_user_data():
    return {'users': {}}

def load_user_data():
    if not os.path.exists(USER_DATA_FILE):
        return default_user_data()
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default_user_data()
        if not isinstance(data.get('users'), dict):
            data['users'] = {}
        return data
    except Exception as e:
        print(f"Error loading user data: {e}")
        return default_user_data()

def save_user_data(data):
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
    compare_left_key = None
    compare_right_key = None
    map_country_key = None
    network_country_key = None
    collection_filter = None
    timeline_group = 'period_contemporary'
    timeline_page = 1
    timeline_items_per_page = 20

state = AppState()

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

def get_flag_url(code):
    if not code or code == 'xx':
        return 'https://placehold.co/160x100?text=No+Flag'
    return f'https://flagcdn.com/w160/{code.lower()}.png'

def get_filter_options():
    data = get_data()
    countries = data.get('countries', [])
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

def get_current_user_record(user_data=None):
    if not state.current_user:
        return None
    users = get_users(user_data)
    user = users.get(state.current_user)
    if user:
        ensure_user_defaults(user)
    return user

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
    return user

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
    ensure_user_defaults(user)
    save_user_data(user_data)
    state.current_user = username
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
    ensure_user_defaults(guest)
    save_user_data(user_data)
    state.current_user = GUEST_USERNAME
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
    save_user_data(user_data)
    state.current_user = username
    ui.notify(t('user_created'), color='positive')
    show_screen('top')
    return True

def logout_user():
    state.current_user = None
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
    save_user_data(user_data)

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
    save_user_data(user_data)
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
    save_user_data(user_data)
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
    save_user_data(user_data)
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
    save_user_data(user_data)

def collection_contains(collection_name, country):
    return country_key(country) in get_collections().get(collection_name, [])

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
    lookup = countries_by_key(data)
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
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'answer_key': answer_key,
        'selected_key': selected_key,
        'correct': bool(correct),
        'type': question_type or '',
        'mode': state.quiz_mode,
    })
    del history[200:]
    save_user_data(user_data)

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
    for country in sorted(data.get('countries', []), key=lambda c: (sort_key(c), c.get('names', {}).get('en', ''))):
        label = country_option_label(country)
        if label in label_to_key:
            label = f'{label} ({get_localized_text(country.get("capital", {}))})'
        key = country_key(country)
        label_to_key[label] = key
        key_to_label[key] = label
    return label_to_key, key_to_label

def country_map_target(country, data=None):
    data = data or get_data()
    if country.get('type') == 'Present':
        return country
    code = country.get('flag_code')
    if code and code != 'xx':
        for candidate in data.get('countries', []):
            if candidate.get('type') == 'Present' and candidate.get('flag_code') == code:
                return candidate
    target_regions = {part.strip() for part in country.get('region', '').replace('/', ',').split(',') if part.strip()}
    for candidate in data.get('countries', []):
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
    countries = data.get('countries', [])
    if not countries or not state.current_user:
        return None
    seed = f'{datetime.now().strftime("%Y-%m-%d")}:{state.current_user}'
    index = int(hashlib.sha256(seed.encode('utf-8')).hexdigest(), 16) % len(countries)
    return countries[index]

def related_countries(country, limit=6):
    data = get_data()
    target_tags = set(country.get('tags', []))
    target_regions = {part.strip() for part in country.get('region', '').replace('/', ',').split(',') if part.strip()}
    target_start = period_start(country)
    target_timeline = timeline_period(country)
    target_languages = profile_value(country, 'languages')
    target_religions = profile_value(country, 'religions')
    scored = []
    for candidate in data.get('countries', []):
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

def build_quiz():
    data = get_data()
    countries = data.get('countries', [])
    if len(countries) < 4:
        return None
    lookup = countries_by_key(data)
    answer_source = countries
    if state.quiz_mode == 'review':
        review_source = [lookup[key] for key in get_review_keys() if key in lookup]
        if not review_source:
            return None
        answer_source = review_source

    question_pools = []
    desc_candidates = [c for c in answer_source if first_sentence(get_localized_text(c.get('desc', {})))]
    capital_candidates = [
        c for c in answer_source
        if get_localized_text(c.get('capital', {})).strip() not in ['', '-']
    ]
    flag_candidates = [
        c for c in answer_source
        if c.get('flag_code') and c.get('flag_code') != 'xx'
    ]
    period_candidates = [c for c in answer_source if period_label(c)]
    if desc_candidates:
        question_pools.append(('desc', desc_candidates))
    if capital_candidates:
        question_pools.append(('capital', capital_candidates))
    if flag_candidates:
        question_pools.append(('flag', flag_candidates))
    if period_candidates:
        question_pools.append(('period', period_candidates))
    for field in PROFILE_FIELDS:
        profile_candidates = [c for c in answer_source if profile_value(c, field)]
        if profile_candidates:
            question_pools.append((f'profile_{field}', profile_candidates))
    for field in DETAIL_QUIZ_FIELDS:
        detail_candidates = [c for c in answer_source if detail_value(c, field)]
        if detail_candidates:
            question_pools.append((f'detail_{field}', detail_candidates))
    if not question_pools:
        return None

    question_type, candidates = random.choice(question_pools)
    answer = random.choice(candidates)
    distractor_count = min(quiz_option_count() - 1, len(countries) - 1)
    options = random.sample([c for c in countries if country_key(c) != country_key(answer)], distractor_count)
    options.append(answer)
    random.shuffle(options)

    return {
        'type': question_type,
        'answer_key': country_key(answer),
        'options': [country_key(option) for option in options],
        'selected_key': None,
        'answered': False,
    }

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

# ========================================
# 画面切り替え
# ========================================
@app.get('/api/data')
def get_data():
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    data = dict(data)
    for key in ['users', 'history', 'favorites']:
        data.pop(key, None)
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_history(country_data):
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
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    viewed = user.setdefault('viewed_keys', [])
    if key not in viewed:
        viewed.append(key)
    history = user.setdefault('history', [])
    history.insert(0, new_record)
    del history[50:]
    save_user_data(user_data)

def clear_history():
    user_data = load_user_data()
    user = get_current_user_record(user_data)
    if user:
        user['history'] = []
        save_user_data(user_data)

# ========================================
# 画面切り替え
# ========================================
def show_screen(screen_name):
    protected_screens = ['main', 'result', 'quiz', 'compare', 'timeline', 'map', 'network', 'account']
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
                    ui.label(f"{h['timestamp']}").classes('text-xs text-gray-400 mt-1')

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
                    ui.label(current_user_label()).classes('text-white text-sm font-bold px-2')
                def open_history():
                    refresh_history_content()
                    history_drawer.toggle()
                ui.button(icon='quiz', on_click=lambda: start_quiz('normal')).props('flat round color=white').tooltip(t('quiz'))
                ui.button(icon='map', on_click=lambda: show_screen('map')).props('flat round color=white').tooltip(t('map'))
                ui.button(icon='account_tree', on_click=lambda: show_screen('network')).props('flat round color=white').tooltip(t('network'))
                ui.button(icon='compare_arrows', on_click=lambda: show_screen('compare')).props('flat round color=white').tooltip(t('compare'))
                ui.button(icon='timeline', on_click=lambda: show_screen('timeline')).props('flat round color=white').tooltip(t('timeline'))
                ui.button(icon='account_circle', on_click=lambda: show_screen('account')).props('flat round color=white').tooltip(t('account'))
                ui.button(icon='history', on_click=open_history).props('flat round color=white')
                if state.current_user:
                    ui.button(icon='logout', on_click=logout_user).props('flat round color=white').tooltip(t('logout'))

# ========================================
# 2. メイン画面
# ========================================
with ui.column().classes('w-full h-screen items-center justify-center gap-4 bg-gray-50') as top_screen:
    top_container = ui.column().classes('items-center gap-4')
    def refresh_top_ui():
        top_container.clear()
        update_mode_classes(top_container, 'items-center gap-4', 'items-center gap-3 px-6 text-center max-w-sm')
        with top_container:
            ui.icon('public', size='4.5rem' if is_mobile_ui() else '6rem').classes('text-[#1a2332]')
            ui.label(t('app_title')).classes('text-3xl font-bold text-[#1a2332]' if is_mobile_ui() else 'text-5xl font-bold text-[#1a2332]')
            ui.label(t('subtitle')).classes('text-base text-gray-500' if is_mobile_ui() else 'text-xl text-gray-500')
            ui.button(t('switch_to_pc') if is_mobile_ui() else t('switch_to_mobile'), icon=ui_mode_icon(), on_click=toggle_ui_mode) \
                .props('outline color=primary') \
                .classes('w-full px-6 py-2 rounded-full shadow-sm font-bold' if is_mobile_ui() else 'px-8 py-2 rounded-full shadow-sm font-bold')
            if state.current_user:
                ui.badge(t('logged_in_as').format(user=current_user_label()), color='green').classes('px-3 py-2')
                daily = today_country()
                if daily:
                    with ui.card().classes('w-full max-w-md p-4 gap-2 shadow-md border border-blue-100'):
                        ui.label(t('today_country')).classes('text-sm font-bold text-blue-700')
                        with ui.row().classes('w-full items-center gap-3 no-wrap'):
                            ui.image(get_flag_url(daily.get('flag_code'))).classes('w-20 shadow border rounded')
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
            countries = data.get('countries', [])
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
                search_target = f"{name_local} {desc_local} {tag_text} {period_text} {profile_text} {detail_text} {region_text}".lower()
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
                        image_box_classes = 'w-full h-28 bg-gray-200 justify-center items-center' if is_mobile_ui() else 'w-32 bg-gray-200 justify-center items-center'
                        image_classes = 'w-full h-full object-cover' if is_mobile_ui() else 'w-full object-cover'
                        with ui.column().classes(image_box_classes):
                            ui.image(get_flag_url(c.get('flag_code'))).classes(image_classes)
                        with ui.row().classes('w-full items-start no-wrap' if is_mobile_ui() else 'flex-grow items-stretch no-wrap'):
                            with ui.column().classes('p-3 gap-1 flex-grow' if is_mobile_ui() else 'p-4 gap-1 flex-grow'):
                                ui.label(get_localized_text(c['names'])).classes('text-lg font-bold text-gray-800' if is_mobile_ui() else 'text-xl font-bold text-gray-800')
                                with ui.row().classes('gap-1 flex-wrap'):
                                    ui.badge(t('tabs', c['type']), color='blue-grey').props('outline dense')
                                    for tag in c.get('tags', [])[:3]:
                                        ui.chip(tag_label(tag)).props('dense size=xs bg-color=blue-1 text-color=blue-9')
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

            with ui.card().classes('w-full p-0 overflow-hidden'):
                with ui.row().classes('w-full bg-white p-4 gap-4 items-start flex-col' if is_mobile_ui() else 'w-full bg-white p-6 gap-6 items-start'):
                    ui.image(get_flag_url(c.get('flag_code'))).classes('w-full shadow-md border rounded' if is_mobile_ui() else 'w-48 shadow-md border rounded')
                    with ui.column().classes('w-full gap-2' if is_mobile_ui() else 'flex-grow gap-2'):
                        ui.label(get_localized_text(c['names'])).classes('text-3xl font-bold text-[#1a2332]' if is_mobile_ui() else 'text-4xl font-bold text-[#1a2332]')
                        ui.label(c['names'].get('en', '')).classes('text-lg text-gray-400 font-serif italic' if is_mobile_ui() else 'text-xl text-gray-400 font-serif italic')
                        with ui.row().classes('mt-2'):ui.badge(t('tabs', c['type']), color='green' if c['type']=='Present' else 'orange').props('text-lg')
                ui.separator()
                detail_container = ui.column().classes('w-full p-4 gap-5') if is_mobile_ui() else ui.grid(columns=2).classes('w-full p-6 gap-6')
                with detail_container:
                    with ui.column().classes('gap-4'):
                        with ui.row().classes('gap-2 w-full flex-col' if is_mobile_ui() else 'gap-2 w-full'):
                            ui.button(t('view_on_map'), icon='map', on_click=lambda country=c: set_map_country(country)) \
                                .props('color=primary') \
                                .classes('flex-grow')
                            ui.button(t('network'), icon='account_tree', on_click=lambda country=c: set_network_country(country)) \
                                .props('outline color=primary') \
                                .classes('flex-grow')
                            ui.link('📍 Google Maps', map_link, new_tab=True) \
                                .classes('flex-grow bg-green-600 text-white text-center px-4 py-2 rounded shadow hover:bg-green-700 no-underline font-bold transition')
                            ui.link('📖 Wikipedia', wiki_url, new_tab=True) \
                                .classes('flex-grow bg-gray-600 text-white text-center px-4 py-2 rounded shadow hover:bg-gray-700 no-underline font-bold transition')

                        with ui.column().classes('gap-1'):
                            ui.label(t('labels', 'capital')).classes('text-xs font-bold text-gray-400 uppercase')
                            ui.label(get_localized_text(c.get('capital', '-'))).classes('text-lg')
                        if detail_period:
                            with ui.column().classes('gap-1'):
                                ui.label(period_field_label(c)).classes('text-xs font-bold text-gray-400 uppercase')
                                ui.label(detail_period).classes('text-lg font-bold text-orange-700')
                        for label, value in profile_rows(c):
                            with ui.column().classes('gap-1'):
                                ui.label(label).classes('text-xs font-bold text-gray-400 uppercase')
                                ui.label(value).classes('text-lg')
                        with ui.column().classes('gap-1'):
                            ui.label(t('labels', 'region')).classes('text-xs font-bold text-gray-400 uppercase')
                            ui.label(region_label(c.get('region', '-'))).classes('text-lg')
                        with ui.column().classes('gap-1'):
                            ui.label(t('labels', 'tags')).classes('text-xs font-bold text-gray-400 uppercase')
                            with ui.row().classes('gap-1'):
                                for tag in c.get('tags', []):
                                    ui.chip(tag_label(tag)).props('outline color=primary')
                    with ui.column().classes('gap-1'):
                        ui.label(t('labels', 'desc')).classes('text-xs font-bold text-gray-400 uppercase')
                        ui.markdown(get_localized_text(c['desc'])).classes('text-gray-800 leading-relaxed text-lg')
                        for label, value in detail_rows(c):
                            ui.separator().classes('my-2')
                            ui.label(label).classes('text-xs font-bold text-gray-400 uppercase')
                            ui.markdown(value).classes('text-gray-800 leading-relaxed')

            with ui.card().classes('w-full p-5 gap-3'):
                with ui.row().classes('w-full justify-between items-center flex-wrap gap-2'):
                    ui.label(t('map')).classes('text-lg font-bold text-[#1a2332]')
                    ui.link('Google Maps', map_link, new_tab=True).classes('text-green-700 font-bold')
                if map_note_text:
                    ui.label(map_note_text).classes('text-sm text-gray-500')
                render_map_embed(c, height=280)

            with ui.card().classes('w-full p-5 gap-3'):
                ui.label(t('notes')).classes('text-lg font-bold text-[#1a2332]')
                note_input = ui.textarea(value=get_note_for_country(c), placeholder=t('notes')) \
                    .props('outlined autogrow') \
                    .classes('w-full')
                ui.button(t('save_note'), icon='save', on_click=lambda country=c, field=note_input: save_note_for_country(country, field.value)) \
                    .props('color=primary') \
                    .classes('self-start')

            with ui.card().classes('w-full p-5 gap-3'):
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

            related = related_countries(c)
            if related:
                with ui.card().classes('w-full p-5 gap-3'):
                    ui.label(t('related_countries')).classes('text-lg font-bold text-[#1a2332]')
                    with ui.grid(columns=1 if is_mobile_ui() else 2).classes('w-full gap-3'):
                        for related_country in related:
                            with ui.card().classes('w-full p-3 cursor-pointer hover:shadow-md transition') as related_card:
                                related_card.on('click', lambda _, x=related_country: open_country_detail(x))
                                with ui.row().classes('items-center gap-3 no-wrap'):
                                    ui.image(get_flag_url(related_country.get('flag_code'))).classes('w-16 shadow border rounded')
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
            ui.image(get_flag_url(country.get('flag_code'))).classes('w-full max-h-32 object-contain border rounded bg-gray-50')
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
        countries = data.get('countries', [])
        if len(countries) < 2:
            return
        lookup = countries_by_key(data)
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
        timeline_countries = [country for country in data.get('countries', []) if country.get('period')]
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
                            ui.image(get_flag_url(country.get('flag_code'))).classes('w-20 shadow border rounded')
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
        lookup = countries_by_key(data)
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
                ui.image(get_flag_url(country.get('flag_code'))).classes('w-20 shadow border rounded')
                with ui.column().classes('gap-1 flex-grow'):
                    ui.label(get_localized_text(country['names'])).classes('text-lg font-bold text-[#1a2332]')
                    ui.label(region_label(country.get('region', ''))).classes('text-sm text-gray-500')
                    period_text = period_label(country)
                    if period_text:
                        ui.label(period_text).classes('text-xs font-bold text-orange-700')
                    with ui.row().classes('gap-1 flex-wrap'):
                        for tag in country.get('tags', [])[:3]:
                            ui.chip(tag_label(tag)).props('dense size=xs bg-color=blue-1 text-color=blue-9')

    def refresh_network_view():
        render_header(header_container_network)
        update_mode_classes(
            network_content,
            'w-full max-w-5xl p-6 gap-6 self-center',
            'w-full max-w-md p-4 gap-4 self-center',
        )
        network_content.clear()
        data = get_data()
        lookup = countries_by_key(data)
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
# 9. アカウントページ
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
        lookup = countries_by_key(data)
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
            ui.badge(t('logged_in_as').format(user=current_user_label()), color='green').classes('px-3 py-2')
            with ui.grid(columns=1 if is_mobile_ui() else 4).classes('w-full gap-4'):
                render_stat_card(t('viewed_count'), f'{len(viewed)} / {total}', f'{int(len(viewed) / total * 100) if total else 0}%')
                render_stat_card(t('favorite_count'), str(len(favorites)))
                render_stat_card(t('review_count'), str(len(review)))
                render_stat_card(t('quiz'), f"{stats.get('correct', 0)} / {stats.get('answered', 0)}", f"{t('quiz_stats').format(correct=stats.get('correct', 0), answered=stats.get('answered', 0), streak=stats.get('streak', 0), best=stats.get('best_streak', 0))}")

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
                    preview = [lookup[key] for key in keys[:4] if key in lookup]
                    if preview:
                        with ui.row().classes('w-full gap-2 flex-wrap'):
                            for country in preview:
                                ui.chip(get_localized_text(country['names'])).props('dense outline color=primary')

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
                                ui.label(f"{quiz_category_label(entry.get('type'))} / {selected_text} / {entry.get('timestamp', '')}").classes('text-xs text-gray-500')

# ========================================
# 初期表示
# ========================================
show_screen('top')
server_port = int(os.environ.get('PORT', 8080))
print(f'Starting World Archives on 0.0.0.0:{server_port}', flush=True)
ui.run(
    title='World Archives',
    favicon='🌍',
    host='0.0.0.0',
    port=server_port,
    reload=False,
    show=False,
)
