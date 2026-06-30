"""Internationalization (i18n) system for HelloCode GUI."""

from __future__ import annotations

# Default language is Chinese
_current_lang = "zh"


# ── Chinese translations ──
_ZH = {
    # Window
    "app_name": "HelloCode",
    "about": "关于",
    "about_title": "关于 HelloCode",
    "about_text": "HelloCode v{version}\n\n终端原生 AI 编程助手\nPySide6 图形界面",

    # Menu
    "menu_file": "文件",
    "menu_edit": "编辑",
    "menu_view": "视图",
    "menu_help": "帮助",
    "menu_theme": "主题",
    "menu_language": "语言",
    "language_english": "英语",
    "theme_midnight": "午夜",
    "theme_ocean": "海洋",
    "theme_nord": "北境",
    "theme_sunset": "日落",
    "theme_forest": "森林",

    # File menu
    "new_session": "新建会话",
    "open_folder": "打开文件夹...",
    "settings": "设置...",
    "quit": "退出",

    # Edit menu
    "clear_chat": "清空对话",

    # View menu
    "toggle_tool_panel": "切换工具面板",
    "toggle_file_browser": "切换文件浏览器",
    "toggle_task_panel": "切换任务面板",
    "toggle_session_panel": "切换会话面板",

    # Chat
    "you": "你",
    "assistant": "助手",
    "input_placeholder": "输入消息... (Enter 发送)",
    "send": "发送",
    "thinking": "思考中...",
    "ready": "就绪",
    "error": "错误",
    "error_prefix": "错误：",

    # Panels
    "sessions": "会话",
    "tasks": "任务",
    "tool_execution": "工具执行",
    "files": "文件",
    "no_sessions": "暂无会话",
    "no_tasks": "暂无任务",
    "new_session_btn": "+",
    "no_tool_calls": "暂无工具调用",
    "new_session_title": "新会话",
    "delete_session": "删除会话",
    "delete_session_title": "删除会话",
    "delete_session_confirm": "确定删除此会话及其消息吗？",
    "delete_all_sessions_title": "清空对话",
    "delete_all_sessions_confirm": "确定删除当前项目中的所有会话吗？",
    "delete": "删除",
    "clear": "清空",
    "close": "关闭",
    "ok": "确定",

    # Task status
    "status_open": "待处理",
    "status_in_progress": "进行中",
    "status_blocked": "已阻塞",
    "status_done": "已完成",
    "status_abandoned": "已放弃",

    # Tool
    "tool_question": "提问",
    "tool_selected": "已选择：{option}",
    "tool_details": "工具详情",
    "tool_label": "工具：",
    "status_label_plain": "状态：",
    "arguments_label": "参数：",
    "result_label": "结果：",
    "details": "详情",
    "tool_status_pending": "等待中",
    "tool_status_success": "成功",
    "tool_status_error": "失败",
    "tool_ok": "完成",
    "tool_fail": "失败",
    "no_result": "暂无结果",

    # Config dialog
    "settings_title": "设置",
    "tab_provider": "服务商",
    "tab_agent": "智能体",
    "tab_appearance": "外观",
    "provider_default": "默认服务商：",
    "api_key": "API 密钥：",
    "model": "模型：",
    "base_url": "基础 URL：",
    "max_tokens": "最大令牌数：",
    "temperature": "温度：",
    "agent_max_tokens": "智能体最大令牌数：",
    "theme_label": "主题：",
    "font_size": "字体大小：",
    "cancel": "取消",
    "save": "保存",
    "provider_name_required": "请输入服务商名称。",
    "provider_model_required": "请输入模型名称。",

    # Status bar
    "model_label": "模型：",
    "session_label": "会话：",
    "file_label": "文件：",
    "wait_current_run_delete_session": "请等待当前运行结束后再删除此会话。",
    "wait_current_run_open_folder": "请等待当前运行结束后再打开其他文件夹。",
    "wait_current_run_clear_sessions": "请等待当前运行结束后再清空对话。",
    "open_folder_dialog": "打开文件夹",

    # Errors
    "error_agent": "智能体错误：{error}",
    "error_llm": "LLM 错误：{error}",
    "error_rate_limit": "请求过于频繁，请稍后再试",
    "error_auth": "API 密钥无效，请检查设置",
    "error_not_found": "模型不可用，请检查配置",
    "error_timeout": "请求超时，请检查网络连接",

    # File browser
    "files_label": "文件",
    "refresh_files": "刷新文件",

    # Tasks
    "no_summary": "暂无摘要",
    "task_stats": "共 {total} 个 · 待处理 {open} 个 · 进行中 {active} 个 · 已完成 {done} 个",

    # Knowledge Base
    "knowledge_base": "知识库",
    "add_source": "添加来源",
    "add_folder": "添加文件夹",
    "add_file": "添加文件",
    "select_folder": "选择文件夹",
    "select_file": "选择文件",
    "rebuild_index": "重建索引",
    "remove_source": "移除来源",
    "indexed": "已索引",
    "indexing": "索引中",
    "index_error": "索引错误",
    "kb_files": "文件",
    "chunks": "片段",
    "total": "总计",
    "documents": "文档",
    "skipped": "跳过",
    "errors": "错误",

    # Schedules
    "schedules": "定时任务",
    "new_schedule": "新建定时任务",
    "edit_schedule": "编辑定时任务",
    "delete_schedule": "删除定时任务",
    "delete_schedule_confirm": "确定要删除此定时任务吗？",
    "schedule_name_placeholder": "输入任务名称",
    "schedule_payload_placeholder": "输入任务内容",
    "cron_expression": "Cron 表达式",
    "interval_seconds": "间隔（秒）",
    "schedule_method": "调度方式",
    "schedule_required": "请设置调度方式",
    "name_required": "请输入名称",
    "enabled": "已启用",
    "schedules_count": "个定时任务",
    "next_run": "下次执行",
    "history": "记录",
    "execution_history": "执行记录",
    "no_execution_history": "暂无执行记录",
    "execution_frequency": "执行频率",
    "multiplier": "倍数",
    "freq_second": "每秒",
    "freq_minute": "每分钟",
    "freq_hour": "每小时",
    "freq_day": "每天",
    "freq_custom_cron": "自定义 Cron",
    "interval_desc": "执行一次，间隔:",
    "cron_validation_error": "Cron 表达式需要 5 个字段 (分 时 日 月 周)",
    "save_failed": "保存失败:",
    "change_directory": "更换工作目录",
    "select_directory": "选择工作目录",
    "schedule_log": "定时任务日志",
    "refresh": "刷新",
    "no_logs": "暂无执行记录",
    "task_type_label": "类型:",
    "task_content_label": "内容:",
    "execution_result": "执行结果",
    "no_schedule_result": "暂无执行结果",
    "error_info": "错误信息",

    # Terminal
    "terminal": "终端",
    "terminal_placeholder": "输入命令... (Enter 执行)",
    "workdir": "工作目录",
    "dir_not_found": "目录不存在",
    "timeout": "超时",
    "timeout_message": "命令执行超时 (30s)",
    "exit_code": "退出码",
    "changed_to": "已切换到",
    "export": "导出",
    "export_chat": "导出对话",
    "export_success": "导出成功",
    "export_failed": "导出失败",
    "no_messages_to_export": "没有可导出的消息",
    "chat_session": "对话会话",
    "exported_at": "导出时间",
    "session_id": "会话 ID",

    # Bookmarks
    "bookmarks": "书签",
    "add_bookmark": "添加书签",
    "remove_bookmark": "移除书签",
    "bookmark_note": "备注",
    "no_bookmarks": "暂无书签",

    # Performance
    "performance": "性能统计",
    "total_tokens": "总 Token 数",
    "tokens_subtitle": "累计消耗",
    "total_requests": "总请求数",
    "requests_subtitle": "累计请求",
    "avg_response_time": "平均响应时间",
    "time_subtitle": "最近平均",
    "total_cost": "总费用",
    "cost_subtitle": "累计成本",
    "today_usage": "今日用量",
    "today_subtitle": "今日 Token",
    "today": "今日",
    "requests": "次请求",

    # Tabs
    "confirm": "确认",
    "tab_running_confirm": "此标签页正在运行任务，确定要关闭吗？",
    "new_tab": "新建标签页",
    "select_tab_type": "选择标签类型",
    "chat_tab": "对话",
    "terminal_tab": "终端",
    "enable": "启用",
    "disable": "禁用",
    "name": "名称",
    "task_type": "任务类型",
    "last_run": "上次执行",
    "actions": "操作",
}

# ── English translations ──
_EN = {
    # Window
    "app_name": "HelloCode",
    "about": "About",
    "about_title": "About HelloCode",
    "about_text": "HelloCode v{version}\n\nTerminal-native AI coding assistant\nPySide6 GUI interface",

    # Menu
    "menu_file": "File",
    "menu_edit": "Edit",
    "menu_view": "View",
    "menu_help": "Help",
    "menu_theme": "Theme",
    "menu_language": "Language",
    "language_english": "English",
    "theme_midnight": "Midnight",
    "theme_ocean": "Ocean",
    "theme_nord": "Nord",
    "theme_sunset": "Sunset",
    "theme_forest": "Forest",

    # File menu
    "new_session": "New Session",
    "open_folder": "Open Folder...",
    "settings": "Settings...",
    "quit": "Quit",

    # Edit menu
    "clear_chat": "Clear Chat",

    # View menu
    "toggle_tool_panel": "Toggle Tool Panel",
    "toggle_file_browser": "Toggle File Browser",
    "toggle_task_panel": "Toggle Task Panel",
    "toggle_session_panel": "Toggle Session Panel",

    # Chat
    "you": "You",
    "assistant": "Assistant",
    "input_placeholder": "Type your message... (Enter to send)",
    "send": "Send",
    "thinking": "Thinking...",
    "ready": "Ready",
    "error": "Error",
    "error_prefix": "Error: ",

    # Panels
    "sessions": "Sessions",
    "tasks": "Tasks",
    "tool_execution": "Tool Execution",
    "files": "Files",
    "no_sessions": "No sessions",
    "no_tasks": "No tasks",
    "new_session_btn": "+",
    "no_tool_calls": "No tool calls yet",
    "new_session_title": "New Session",
    "delete_session": "Delete Session",
    "delete_session_title": "Delete Session",
    "delete_session_confirm": "Delete this session and its messages?",
    "delete_all_sessions_title": "Clear Conversations",
    "delete_all_sessions_confirm": "Delete all sessions in this project?",
    "delete": "Delete",
    "clear": "Clear",
    "close": "Close",
    "ok": "OK",

    # Task status
    "status_open": "Open",
    "status_in_progress": "In Progress",
    "status_blocked": "Blocked",
    "status_done": "Done",
    "status_abandoned": "Abandoned",

    # Tool
    "tool_question": "Question",
    "tool_selected": "Selected: {option}",
    "tool_details": "Tool Details",
    "tool_label": "Tool: ",
    "status_label_plain": "Status: ",
    "arguments_label": "Arguments:",
    "result_label": "Result:",
    "details": "Details",
    "tool_status_pending": "Pending",
    "tool_status_success": "Success",
    "tool_status_error": "Error",
    "tool_ok": "OK",
    "tool_fail": "FAIL",
    "no_result": "(no result yet)",

    # Config dialog
    "settings_title": "Settings",
    "tab_provider": "Provider",
    "tab_agent": "Agent",
    "tab_appearance": "Appearance",
    "provider_default": "Default Provider:",
    "api_key": "API Key:",
    "model": "Model:",
    "base_url": "Base URL:",
    "max_tokens": "Max Tokens:",
    "temperature": "Temperature:",
    "agent_max_tokens": "Agent Max Tokens:",
    "theme_label": "Theme:",
    "font_size": "Font Size:",
    "cancel": "Cancel",
    "save": "Save",
    "provider_name_required": "Please enter a provider name.",
    "provider_model_required": "Please enter a model name.",

    # Status bar
    "model_label": "Model: ",
    "session_label": "Session: ",
    "file_label": "File: ",
    "wait_current_run_delete_session": "Wait for the current run to finish before deleting this session.",
    "wait_current_run_open_folder": "Wait for the current run to finish before opening another folder.",
    "wait_current_run_clear_sessions": "Wait for the current run to finish before clearing conversations.",
    "open_folder_dialog": "Open Folder",

    # Errors
    "error_agent": "Agent error: {error}",
    "error_llm": "LLM error: {error}",
    "error_rate_limit": "Too many requests, please try again later",
    "error_auth": "Invalid API key, please check settings",
    "error_not_found": "Model not available, please check configuration",
    "error_timeout": "Request timed out, please check network connection",

    # File browser
    "files_label": "Files",
    "refresh_files": "Refresh files",

    # Tasks
    "no_summary": "No summary",
    "task_stats": "{total} total · {open} open · {active} active · {done} done",

    # Knowledge Base
    "knowledge_base": "Knowledge Base",
    "add_source": "Add Source",
    "add_folder": "Add Folder",
    "add_file": "Add File",
    "select_folder": "Select Folder",
    "select_file": "Select File",
    "rebuild_index": "Rebuild Index",
    "remove_source": "Remove Source",
    "indexed": "Indexed",
    "indexing": "Indexing",
    "index_error": "Index Error",
    "kb_files": "files",
    "chunks": "chunks",
    "total": "Total",
    "documents": "documents",
    "skipped": "skipped",
    "errors": "errors",

    # Schedules
    "schedules": "Schedules",
    "new_schedule": "New Schedule",
    "edit_schedule": "Edit Schedule",
    "delete_schedule": "Delete Schedule",
    "delete_schedule_confirm": "Are you sure you want to delete this schedule?",
    "schedule_name_placeholder": "Enter schedule name",
    "schedule_payload_placeholder": "Enter task payload",
    "cron_expression": "Cron Expression",
    "interval_seconds": "Interval (seconds)",
    "schedule_method": "Schedule Method",
    "schedule_required": "Please set a schedule method",
    "name_required": "Please enter a name",
    "enabled": "enabled",
    "schedules_count": "schedules",
    "next_run": "Next Run",
    "history": "History",
    "execution_history": "Execution History",
    "no_execution_history": "No execution history",
    "execution_frequency": "Frequency",
    "multiplier": "Multiplier",
    "freq_second": "Every second",
    "freq_minute": "Every minute",
    "freq_hour": "Every hour",
    "freq_day": "Every day",
    "freq_custom_cron": "Custom Cron",
    "interval_desc": "interval:",
    "cron_validation_error": "Cron expression needs 5 fields (min hour day month weekday)",
    "save_failed": "Save failed:",
    "change_directory": "Change Directory",
    "select_directory": "Select Directory",
    "schedule_log": "Schedule Log",
    "refresh": "Refresh",
    "no_logs": "No logs yet",
    "task_type_label": "Type:",
    "task_content_label": "Content:",
    "execution_result": "Result",
    "no_schedule_result": "No result",
    "error_info": "Error",

    # Terminal
    "terminal": "Terminal",
    "terminal_placeholder": "Type command... (Enter to execute)",
    "workdir": "Working Directory",
    "dir_not_found": "Directory not found",
    "timeout": "Timeout",
    "timeout_message": "Command timed out (30s)",
    "exit_code": "Exit code",
    "changed_to": "Changed to",
    "export": "Export",
    "export_chat": "Export Chat",
    "export_success": "Export successful",
    "export_failed": "Export failed",
    "no_messages_to_export": "No messages to export",
    "chat_session": "Chat Session",
    "exported_at": "Exported at",
    "session_id": "Session ID",

    # Bookmarks
    "bookmarks": "Bookmarks",
    "add_bookmark": "Add Bookmark",
    "remove_bookmark": "Remove Bookmark",
    "bookmark_note": "Note",
    "no_bookmarks": "No bookmarks",

    # Performance
    "performance": "Performance",
    "total_tokens": "Total Tokens",
    "tokens_subtitle": "All time",
    "total_requests": "Total Requests",
    "requests_subtitle": "All time",
    "avg_response_time": "Avg Response Time",
    "time_subtitle": "Recent average",
    "total_cost": "Total Cost",
    "cost_subtitle": "All time",
    "today_usage": "Today's Usage",
    "today_subtitle": "Today's tokens",
    "today": "Today",
    "requests": "requests",

    # Tabs
    "confirm": "Confirm",
    "tab_running_confirm": "This tab has a running task. Close anyway?",
    "new_tab": "New Tab",
    "select_tab_type": "Select Tab Type",
    "chat_tab": "Chat",
    "terminal_tab": "Terminal",
    "enable": "Enable",
    "disable": "Disable",
    "name": "Name",
    "task_type": "Task Type",
    "last_run": "Last Run",
    "actions": "Actions",
}

TRANSLATIONS = {
    "zh": _ZH,
    "en": _EN,
}


def set_language(lang: str) -> None:
    """Set the current language."""
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang


def get_language() -> str:
    """Get the current language."""
    return _current_lang


def get_language_names() -> list[str]:
    """Get available language names."""
    return list(TRANSLATIONS.keys())


def t(key: str, **kwargs) -> str:
    """Translate a key to the current language.

    Args:
        key: Translation key
        **kwargs: Format arguments for string interpolation

    Returns:
        Translated string, or key itself if not found
    """
    translations = TRANSLATIONS.get(_current_lang, TRANSLATIONS.get("zh", {}))
    text = translations.get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text
