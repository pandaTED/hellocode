"""Performance analytics panel."""

from __future__ import annotations

from datetime import datetime, timedelta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QPushButton,
)

from .i18n import t


class MetricCard(QFrame):
    """A single metric display card."""

    def __init__(self, title: str, value: str, subtitle: str = "", theme=None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._setup_ui(title, value, subtitle)

    def _setup_ui(self, title: str, value: str, subtitle: str):
        th = self._theme
        self.setStyleSheet(f"""
            MetricCard {{
                background-color: {th.bg_surface if th else '#313244'};
                border: 1px solid {th.border if th else '#45475a'};
                border-radius: 8px;
                padding: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            color: {th.text_muted if th else '#6c7086'};
            font-size: 11px;
        """)
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"""
            color: {th.text_primary if th else '#cdd6f4'};
            font-size: 20px;
            font-weight: bold;
        """)
        layout.addWidget(self.value_label)

        self.sub_label = QLabel(subtitle)
        self.sub_label.setStyleSheet(f"""
            color: {th.text_muted if th else '#6c7086'};
            font-size: 10px;
        """)
        layout.addWidget(self.sub_label)

    def update_value(self, value: str, subtitle: str = ""):
        self.value_label.setText(value)
        if subtitle:
            self.sub_label.setText(subtitle)

    def update_title(self, title: str):
        self.title_label.setText(title)

    def update_theme(self, theme):
        self._theme = theme
        self.setStyleSheet(f"""
            MetricCard {{
                background-color: {theme.bg_surface};
                border: 1px solid {theme.border};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        self.title_label.setStyleSheet(f"color: {theme.text_muted}; font-size: 11px;")
        self.value_label.setStyleSheet(f"color: {theme.text_primary}; font-size: 20px; font-weight: bold;")
        self.sub_label.setStyleSheet(f"color: {theme.text_muted}; font-size: 10px;")


class PerformancePanel(QWidget):
    """Performance analytics display panel."""

    def __init__(self, storage, theme=None, parent=None):
        super().__init__(parent)
        self.setObjectName("sidePanel")
        self._storage = storage
        self._theme = theme
        self._metrics: dict = {
            "total_tokens": 0,
            "total_requests": 0,
            "avg_response_time": 0,
            "total_cost": 0,
            "today_tokens": 0,
            "today_requests": 0,
        }
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        th = self._theme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(12, 8, 12, 4)
        header_label = QLabel(t("performance"))
        header_label.setStyleSheet(f"""
            color: {th.text_secondary if th else '#a6adc8'};
            font-size: 13px;
            font-weight: 600;
        """)
        header.addWidget(header_label)
        header.addStretch()

        self.refresh_btn = QPushButton(t("refresh"))
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {th.text_muted if th else '#6c7086'};
                border: none;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: {th.text_primary if th else '#cdd6f4'};
            }}
        """)
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)

        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(content)
        self._cards_layout.setContentsMargins(8, 4, 8, 8)
        self._cards_layout.setSpacing(8)

        self._create_cards()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _create_cards(self):
        self.token_card = MetricCard(
            t("total_tokens"), "0",
            t("tokens_subtitle"), self._theme
        )
        self._cards_layout.addWidget(self.token_card)

        self.request_card = MetricCard(
            t("total_requests"), "0",
            t("requests_subtitle"), self._theme
        )
        self._cards_layout.addWidget(self.request_card)

        self.time_card = MetricCard(
            t("avg_response_time"), "0ms",
            t("time_subtitle"), self._theme
        )
        self._cards_layout.addWidget(self.time_card)

        self.cost_card = MetricCard(
            t("total_cost"), "$0.00",
            t("cost_subtitle"), self._theme
        )
        self._cards_layout.addWidget(self.cost_card)

        self.today_card = MetricCard(
            t("today_usage"), "0",
            t("today_subtitle"), self._theme
        )
        self._cards_layout.addWidget(self.today_card)

        self._cards_layout.addStretch()

    def refresh(self):
        self._load_metrics()
        self.token_card.update_value(
            f"{self._metrics['total_tokens']:,}",
            f"{self._metrics['today_tokens']:,} {t('today')}"
        )
        self.request_card.update_value(
            f"{self._metrics['total_requests']:,}",
            f"{self._metrics['today_requests']:,} {t('today')}"
        )
        self.time_card.update_value(
            f"{self._metrics['avg_response_time']:.0f}ms",
        )
        self.cost_card.update_value(
            f"${self._metrics['total_cost']:.2f}",
        )
        self.today_card.update_value(
            f"{self._metrics['today_tokens']:,}",
            f"{self._metrics['today_requests']:,} {t('requests')}"
        )

    def _load_metrics(self):
        try:
            stats = self._storage.get_performance_stats()
            if stats:
                self._metrics.update(stats)
        except Exception:
            pass

    def record_request(self, tokens: int, response_time_ms: float, cost: float = 0):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        if self._metrics.get("today_date") != today:
            self._metrics["today_tokens"] = 0
            self._metrics["today_requests"] = 0
            self._metrics["today_date"] = today

        self._metrics["total_tokens"] += tokens
        self._metrics["total_requests"] += 1
        self._metrics["today_tokens"] += tokens
        self._metrics["today_requests"] += 1

        n = self._metrics["total_requests"]
        old_avg = self._metrics["avg_response_time"]
        self._metrics["avg_response_time"] = old_avg + (response_time_ms - old_avg) / n
        self._metrics["total_cost"] += cost

        try:
            self._storage.update_performance_stats(self._metrics)
        except Exception:
            pass
        self.refresh()

    def update_theme(self, theme):
        self._theme = theme
        th = theme
        self.header_label.setStyleSheet(f"color: {th.text_secondary}; font-size: 13px; font-weight: 600;")
        self.refresh_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {th.text_muted}; border: none; font-size: 12px; }}")
        for card in [self.token_card, self.request_card, self.time_card, self.cost_card, self.today_card]:
            card.update_theme(theme)
        self.refresh()

    def update_language(self):
        if hasattr(self, 'header_label'):
            self.header_label.setText(t("performance"))
        self.refresh()
