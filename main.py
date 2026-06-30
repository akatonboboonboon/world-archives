"""
NiceGUI SPA テンプレート（API版）

3画面構成：トップ → メイン → 結果
JSONデータをAPIから取得して表示します。
"""
from nicegui import ui, app
import json
import os
import random
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(BASE_DIR, 'data.json')

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
            "countries": [],
            "history": []
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

TRANSLATIONS = load_translations()

class AppState:
    selected_country = None
    filter_type = 'All'
    filter_region = None
    filter_tag = None
    sort_mode = 'default'
    lang = 'ja'
    search_keyword = ''
    page = 1
    items_per_page = 20

state = AppState()

def t(key, subkey=None):
    lang_data = TRANSLATIONS.get(state.lang, TRANSLATIONS.get('en', {}))
    val = lang_data.get(key, key)
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
    return sorted(list(regions)), [tag_label(tag) for tag in sorted_tags]

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

# ========================================
# 画面切り替え
# ========================================
@app.get('/api/data')
def get_data():
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_history(country_data):
    data = get_data()
    name = get_localized_text(country_data['names'])
    new_record = {
        "name": name,
        "flag_code": country_data.get('flag_code'),
        "lang": state.lang,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    data['history'].insert(0, new_record)
    save_data(data)

def clear_history():
    data = get_data()
    data['history'] = []
    save_data(data)

# ========================================
# 画面切り替え
# ========================================
def show_screen(screen_name):
    if screen_name == 'top':
        clear_history()
        state.search_keyword = ''
        state.filter_region = None
        state.filter_tag = None
        state.sort_mode = 'default'
        state.page = 1
        if history_drawer.value:
            history_drawer.hide()
        refresh_top_ui()

    top_screen.set_visibility(screen_name == 'top')
    main_screen.set_visibility(screen_name == 'main')
    result_screen.set_visibility(screen_name == 'result')
    if screen_name == 'main':
        refresh_main_ui()
    if screen_name == 'result':
        refresh_result_view()

def switch_language(lang_code):
    state.lang = lang_code
    if top_screen.visible: refresh_top_ui()
    if main_screen.visible: refresh_main_ui()
    if result_screen.visible: refresh_result_view()

# ========================================
# 1. トップ画面
# ========================================
with ui.right_drawer(value=False).classes('bg-gray-100') as history_drawer:
    history_content = ui.column().classes('w-full p-4')

def jump_from_history(history_item):
    code = history_item.get('flag_code')
    hist_name = history_item.get('name')
    if not code: return

    data = get_data()
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
    data = get_data()
    histories = data.get('history', [])
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
        with ui.row().classes('w-full h-16 bg-[#1a2332] items-center px-4 justify-between shadow-md'):
            with ui.row().classes('gap-4 items-center cursor-pointer').on('click', lambda: show_screen('top')):
                ui.icon('public', color='blue-400').classes('text-2xl')
                ui.label(t('app_title')).classes('text-white font-bold text-lg')
            with ui.row().classes('gap-3 items-center'):
                with ui.dropdown_button(text=state.lang.upper(), icon='language', auto_close=True).props('flat color=white dense'):
                    ui.item('日本語 (JA)', on_click=lambda: switch_language('ja'))
                    ui.item('English (EN)', on_click=lambda: switch_language('en'))
                    ui.item('中文 (ZH)', on_click=lambda: switch_language('zh'))
                def open_history():
                    refresh_history_content()
                    history_drawer.toggle()
                ui.button(icon='history', on_click=open_history).props('flat round color=white')

# ========================================
# 2. メイン画面
# ========================================
with ui.column().classes('w-full h-screen items-center justify-center gap-4 bg-gray-50') as top_screen:
    top_container = ui.column().classes('items-center gap-4')
    def refresh_top_ui():
        top_container.clear()
        with top_container:
            ui.icon('public', size='6rem').classes('text-[#1a2332]')
            ui.label(t('app_title')).classes('text-5xl font-bold text-[#1a2332]')
            ui.label(t('subtitle')).classes('text-xl text-gray-500')
            ui.button('ENTER', on_click=lambda: show_screen('main')) \
                .classes('bg-[#1a2332] text-white px-10 py-3 rounded-full text-lg shadow-lg hover:scale-105 transition')
            with ui.row().classes('mt-8 gap-4'):
                ui.link('JA', '#').on('click', lambda: switch_language('ja'))
                ui.link('EN', '#').on('click', lambda: switch_language('en'))
                ui.link('ZH', '#').on('click', lambda: switch_language('zh'))
    refresh_top_ui()

with ui.column().classes('w-full min-h-screen bg-gray-50 gap-0') as main_screen:
    header_container_main = ui.column().classes('w-full p-0 m-0')

    with ui.column().classes('w-full max-w-5xl p-6 gap-6 self-center'):
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

        def toggle_sort():
            state.sort_mode = 'name' if state.sort_mode == 'default' else 'default'
            refresh_main_ui()

        def load_more():
            state.page += 1
            refresh_search_list()

        def refresh_main_ui():
            render_header(header_container_main)
            r_opts, t_opts = get_filter_options()

            search_area_container.clear()
            with search_area_container:
                ui.label(t('search_label')).classes('text-sm font-bold text-blue-800 mb-1')
                with ui.row().classes('w-full gap-2 items-center'):
                    ui.input(value=state.search_keyword, on_change=update_keyword) \
                        .props('rounded outlined prepend-inner-icon=search clearable') \
                        .classes('text-lg flex-grow bg-white shadow-inner') \
                        .props(f'placeholder="{t("search_ph")}"')
                    sort_icon = 'sort_by_alpha' if state.sort_mode == 'name' else 'sort'
                    sort_bg = 'bg-blue-600' if state.sort_mode == 'name' else 'bg-gray-400'
                    ui.button(icon=sort_icon, on_click=toggle_sort) \
                        .classes(f'{sort_bg} text-white px-4 py-2 shadow-md') \
                        .tooltip('Sort by Name')

                    ui.button(icon='shuffle', on_click=pick_random) \
                        .classes('bg-purple-500 text-white px-4 py-2 shadow-md')

                with ui.row().classes('w-full gap-4 mt-2'):
                    ui.select(r_opts, value=state.filter_region, label=t('labels', 'region'),on_change=lambda e: set_region_filter(e.value), clearable=True) \
                        .classes('w-48 bg-white')
                    ui.select(t_opts, value=selected_tag_label(), label=t('labels', 'tags'),on_change=lambda e: set_tag_filter(e.value), clearable=True) \
                        .classes('w-48 bg-white')

                with ui.row().classes('w-full justify-between items-center mt-4'):
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
            state.filter_region = val
            state.page = 1
            refresh_search_list()

        def set_tag_filter(val):
            state.filter_tag = normalize_tag_value(val)
            state.page = 1
            refresh_search_list()

        def refresh_search_list():
            list_container.clear()
            data = get_data()
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

                name_local = get_localized_text(c['names'])
                desc_local = get_localized_text(c['desc'])
                tag_text = ' '.join(tag_search_text(tag) for tag in c.get('tags', []))
                search_target = f"{name_local} {desc_local} {tag_text}".lower()
                if keyword in search_target:
                    filtered.append(c)
            if state.sort_mode == 'name':
                filtered.sort(key=lambda x: x['names'].get(state.lang, ''))

            total_count = len(filtered)
            current_limit = state.page * state.items_per_page
            display_list = filtered[:current_limit]

            hits_label.text = f"{min(current_limit, total_count)} / {total_count} {t('hits')}"

            with list_container:
                for c in display_list:
                    with ui.card().classes('w-full p-0 flex flex-row no-wrap items-stretch hover:shadow-md transition cursor-pointer overflow-hidden') as card:
                        card.on('click', lambda _, x=c: select_country(x))
                        with ui.column().classes('w-32 bg-gray-200 justify-center items-center'):
                            ui.image(get_flag_url(c.get('flag_code'))).classes('w-full object-cover')
                        with ui.column().classes('p-4 gap-1 flex-grow'):
                            ui.label(get_localized_text(c['names'])).classes('text-xl font-bold text-gray-800')
                            with ui.row().classes('gap-1'):
                                ui.badge(t('tabs', c['type']), color='blue-grey').props('outline dense')
                                for tag in c.get('tags', [])[:3]:
                                    ui.chip(tag_label(tag)).props('dense size=xs bg-color=blue-1 text-color=blue-9')
                            ui.label(get_localized_text(c['desc'])).classes('text-gray-500 text-sm mt-1 line-clamp-1')
                if total_count > current_limit:
                    ui.button(f'Load More ({total_count - current_limit} remaining)', on_click=load_more) \
                        .classes('w-full bg-gray-200 text-gray-600 py-2 hover:bg-gray-300 transition')

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
        result_content.clear()
        c = state.selected_country
        if not c: return
        name_en = c['names'].get('en', c['names'].get('ja'))
        map_link = f"https://www.google.com/maps/search/{name_en}"
        wiki_url = f"https://ja.wikipedia.org/wiki/{c['names'].get('ja')}"

        with result_content:
            ui.button(t('back_search'), icon='arrow_back', on_click=lambda: show_screen('main')) \
                .props('flat color=grey dense text-lg')

            with ui.card().classes('w-full p-0 overflow-hidden'):
                with ui.row().classes('w-full bg-white p-6 gap-6 items-start'):
                    ui.image(get_flag_url(c.get('flag_code'))).classes('w-48 shadow-md border rounded')
                    with ui.column().classes('flex-grow gap-2'):
                        ui.label(get_localized_text(c['names'])).classes('text-4xl font-bold text-[#1a2332]')
                        ui.label(c['names'].get('en', '')).classes('text-xl text-gray-400 font-serif italic')
                        with ui.row().classes('mt-2'):ui.badge(t('tabs', c['type']), color='green' if c['type']=='Present' else 'orange').props('text-lg')
                ui.separator()
                with ui.grid(columns=2).classes('w-full p-6 gap-6'):
                    with ui.column().classes('gap-4'):
                        with ui.row().classes('gap-2 w-full'):
                            ui.link('📍 Google Maps', map_link, new_tab=True) \
                                .classes('flex-grow bg-green-600 text-white text-center px-4 py-2 rounded shadow hover:bg-green-700 no-underline font-bold transition')
                            ui.link('📖 Wikipedia', wiki_url, new_tab=True) \
                                .classes('flex-grow bg-gray-600 text-white text-center px-4 py-2 rounded shadow hover:bg-gray-700 no-underline font-bold transition')

                        with ui.column().classes('gap-1'):
                            ui.label(t('labels', 'capital')).classes('text-xs font-bold text-gray-400 uppercase')
                            ui.label(get_localized_text(c.get('capital', '-'))).classes('text-lg')
                        with ui.column().classes('gap-1'):
                            ui.label(t('labels', 'region')).classes('text-xs font-bold text-gray-400 uppercase')
                            ui.label(c.get('region', '-')).classes('text-lg')
                        with ui.column().classes('gap-1'):
                            ui.label(t('labels', 'tags')).classes('text-xs font-bold text-gray-400 uppercase')
                            with ui.row().classes('gap-1'):
                                for tag in c.get('tags', []):
                                    ui.chip(tag_label(tag)).props('outline color=primary')
                    with ui.column().classes('gap-1'):
                        ui.label(t('labels', 'desc')).classes('text-xs font-bold text-gray-400 uppercase')
                        ui.markdown(get_localized_text(c['desc'])).classes('text-gray-800 leading-relaxed text-lg')

# ========================================
# 初期表示
# ========================================
show_screen('top')
ui.run(title='World Archives', favicon='🌍')
