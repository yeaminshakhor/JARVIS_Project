"""
Notification System for JARVIS GUI
Manages and displays notifications with badges
"""

import json
import time
import os
import logging
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem
)
from PyQt5.QtGui import QColor

# Configuration
CURRENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(CURRENT_DIR, "Frontend", "Files")
NOTIFICATIONS_FILE = os.path.join(TEMP_DIR, "notifications.json")

# Ensure directory exists
os.makedirs(TEMP_DIR, exist_ok=True)


class NotificationManager:
    """Manages notifications - stores, loads, saves, and tracks read status"""
    
    def __init__(self):
        self.notifications = self.load_notifications()

    def _next_notification_id(self):
        """Generate next unique numeric notification ID."""
        max_id = 0
        for notification in self.notifications:
            try:
                current_id = int(notification.get("id", 0))
            except (TypeError, ValueError):
                current_id = 0
            if current_id > max_id:
                max_id = current_id
        return max_id + 1
    
    def load_notifications(self):
        """Load notifications from JSON file"""
        try:
            if os.path.exists(NOTIFICATIONS_FILE):
                with open(NOTIFICATIONS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load notifications: {e}")
        return []
    
    def save_notifications(self):
        """Save notifications to JSON file"""
        try:
            with open(NOTIFICATIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.notifications, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Failed to save notifications: {e}")
    
    def add_notification(self, title, message, app="System", urgent=False):
        """Add a new notification"""
        notification = {
            "id": self._next_notification_id(),
            "title": title,
            "message": message,
            "app": app,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "read": False,
            "urgent": urgent
        }
        self.notifications.insert(0, notification)
        self.save_notifications()
        return notification
    
    def mark_as_read(self, notification_id):
        """Mark a specific notification as read"""
        for notification in self.notifications:
            if notification["id"] == notification_id:
                notification["read"] = True
                break
        self.save_notifications()
    
    def mark_all_as_read(self):
        """Mark all notifications as read"""
        for notification in self.notifications:
            notification["read"] = True
        self.save_notifications()
    
    def clear_all(self):
        """Delete all notifications"""
        self.notifications = []
        self.save_notifications()
    
    def get_unread_count(self):
        """Get count of unread notifications"""
        return len([n for n in self.notifications if not n["read"]])
    
    def get_recent(self, count=10):
        """Get most recent notifications"""
        return self.notifications[:count]

    def get_notifications(self):
        """Return full notifications list for bridge consumers."""
        return list(self.notifications)

    def mark_read_by_source(self, source):
        """Mark unread notifications as read for a normalized source id."""
        source_key = str(source or "").strip().lower()
        if not source_key:
            return 0

        aliases = {
            "mail": "gmail",
            "email": "gmail",
            "googlemail": "gmail",
            "wa": "whatsapp",
            "insta": "instagram",
            "ig": "instagram",
            "fb": "facebook",
            "msg": "messenger",
            "x": "twitter",
            "twit": "twitter",
            "calendar": "outlook",
            "teams": "outlook",
        }

        def normalize(value):
            key = str(value or "").strip().lower()
            return aliases.get(key, key)

        target = normalize(source_key)
        changed = 0
        for notification in self.notifications:
            current = normalize(
                notification.get("source")
                or notification.get("app")
                or notification.get("tag")
                or notification.get("notification_type")
                or "system"
            )
            if current == target and not notification.get("read", False):
                notification["read"] = True
                changed += 1

        if changed:
            self.save_notifications()
        return changed


def seed_demo_notifications(notification_manager):
    """Seed realistic demo notifications if no entries are present."""
    if notification_manager is None:
        return

    try:
        existing = notification_manager.get_notifications()
    except Exception:
        existing = []
    if existing:
        return

    demos = [
        {"source": "gmail", "title": "New email received", "body": "You have a new message in your inbox."},
        {"source": "gmail", "title": "Invoice #2048 received", "body": "Your invoice is ready to download."},
        {"source": "whatsapp", "title": "New WhatsApp message", "body": "You have unread WhatsApp messages."},
        {"source": "whatsapp", "title": "Team group: 5 new messages", "body": "Sprint planning moved to Thursday."},
        {"source": "reminder", "title": "Team standup at 3 PM", "body": "Don't forget to update your tickets."},
        {"source": "instagram", "title": "12 new likes on your photo", "body": "Your latest post is getting traction."},
        {"source": "linkedin", "title": "2 new connection requests", "body": "You have pending connection requests."},
        {"source": "outlook", "title": "Meeting: Project Review", "body": "Tomorrow 10:00 AM - Conference Room B."},
        {"source": "discord", "title": "5 mentions in #general", "body": "jarvis-ai: what's the status update?"},
        {"source": "messenger", "title": "New Messenger message", "body": "You have unread Messenger messages."},
        {"source": "twitter", "title": "8 new notifications", "body": "@you was mentioned in 3 threads."},
    ]

    for item in demos:
        app_name = str(item.get("source") or "system").upper()
        notification = notification_manager.add_notification(
            title=item.get("title") or "",
            message=item.get("body") or "",
            app=app_name,
            urgent=False,
        )
        if isinstance(notification, dict):
            notification["source"] = str(item.get("source") or "system").lower()
            notification["tag"] = app_name

    notification_manager.save_notifications()


class NotificationDialog(QDialog):
    """Dialog window to display all notifications"""
    
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle(" Notifications")
        self.setMinimumSize(500, 400)
        self.setStyleSheet("""
            QDialog {
                background: #001919;
                color: #00FFFF;
                border: 2px solid #00FFFF;
            }
            QPushButton {
                background: #003333;
                color: #00FFFF;
                border: 2px solid #00FFFF;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #00FFFF;
                color: #001919;
            }
            QListWidget {
                background: #000A0A;
                color: #00FFFF;
                border: 2px solid #00FFFF;
                border-radius: 5px;
                font-size: 12px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #003333;
            }
            QListWidget::item:selected {
                background: #00FFFF;
                color: #001919;
            }
            QLabel {
                color: #00FFFF;
                font-size: 14px;
            }
        """)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        title = QLabel(" NOTIFICATIONS")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00FFFF;")
        header.addWidget(title)
        
        header.addStretch()
        
        # Mark all as read button
        mark_read_btn = QPushButton(" MARK ALL READ")
        mark_read_btn.clicked.connect(self.mark_all_read)
        header.addWidget(mark_read_btn)
        
        # Clear all button
        clear_btn = QPushButton("️ CLEAR ALL")
        clear_btn.clicked.connect(self.clear_all)
        header.addWidget(clear_btn)
        
        # Refresh button
        refresh_btn = QPushButton(" REFRESH")
        refresh_btn.clicked.connect(self.refresh_list)
        header.addWidget(refresh_btn)
        
        layout.addLayout(header)
        
        # Notification list
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.mark_as_read)
        layout.addWidget(self.list_widget)
        
        # Footer with count
        footer = QHBoxLayout()
        self.count_label = QLabel("")
        footer.addWidget(self.count_label)
        footer.addStretch()
        
        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        footer.addWidget(close_btn)
        
        layout.addLayout(footer)
        
        self.refresh_list()
    
    def refresh_list(self):
        """Refresh the notification list display"""
        self.list_widget.clear()
        notifications = self.manager.notifications
        
        if not notifications:
            self.list_widget.addItem("No notifications")
            self.count_label.setText("0 notifications")
            return
        
        unread = self.manager.get_unread_count()
        self.count_label.setText(f"{len(notifications)} total • {unread} unread")
        
        for notification in notifications:
            # Create item text with formatting
            read_symbol = "●" if not notification["read"] else "○"
            urgent_symbol = "" if notification.get("urgent", False) else ""
            
            item_text = f"{read_symbol} {urgent_symbol} [{notification['app']}] {notification['title']}\n"
            item_text += f"    {notification['message']}\n"
            item_text += f"    ⏰ {notification['time']}"
            
            item = QListWidgetItem(item_text)
            
            # Color code based on status
            if notification.get("urgent", False):
                item.setForeground(QColor("#FF5555"))  # Red for urgent
            elif not notification["read"]:
                item.setForeground(QColor("#FFFF55"))  # Yellow for unread
            else:
                item.setForeground(QColor("#AAAAAA"))  # Gray for read
            
            # Store notification ID in item data
            item.setData(Qt.UserRole, notification["id"])
            self.list_widget.addItem(item)
    
    def mark_as_read(self, item):
        """Mark a single notification as read when double-clicked"""
        notification_id = item.data(Qt.UserRole)
        if notification_id:
            self.manager.mark_as_read(notification_id)
            self.refresh_list()
    
    def mark_all_read(self):
        """Mark all notifications as read"""
        self.manager.mark_all_as_read()
        self.refresh_list()
    
    def clear_all(self):
        """Clear all notifications"""
        self.manager.clear_all()
        self.refresh_list()


class NotificationButton(QPushButton):
    """Button with notification badge that shows unread count"""
    
    def __init__(self, manager, parent=None):
        super().__init__("", parent)
        self.manager = manager
        self.setFixedSize(50, 50)
        self.setStyleSheet("""
            QPushButton {
                background: #001919;
                color: #00FFFF;
                border: 2px solid #00FFFF;
                border-radius: 8px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: #00FFFF;
                color: #001919;
            }
        """)
        
        # Create badge label
        self.badge = QLabel(self)
        self.badge.setStyleSheet("""
            QLabel {
                background: #FF0000;
                color: white;
                border-radius: 10px;
                padding: 2px 5px;
                font-size: 10px;
                font-weight: bold;
                border: 1px solid white;
            }
        """)
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setFixedSize(20, 20)
        self.badge.move(35, 5)
        self.badge.hide()
        
        # Timer to periodically update badge
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_badge)
        self.timer.start(1000)  # Update every second
        
        self.update_badge()
    
    def update_badge(self):
        """Update the badge with current unread count"""
        unread = self.manager.get_unread_count()
        if unread > 0:
            self.badge.setText(str(unread))
            self.badge.show()
        else:
            self.badge.hide()
    
    def show_notifications(self):
        """Show the notification dialog"""
        dialog = NotificationDialog(self.manager, self.window())
        dialog.exec_()
        self.update_badge()


class Notifier:
    """Simple interface for creating notifications"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.manager = NotificationManager()
    
    def notify(self, title, message, app="System", urgent=False):
        """Create a new notification"""
        self.manager.add_notification(title, message, app, urgent)
        print(f" [{app}] {title}: {message}")
        
        # Update parent's notification badge if it exists
        if hasattr(self.parent, 'update_notification_badge'):
            self.parent.update_notification_badge()
        
        return True
    
    def success(self, title, message, app="System"):
        """Create a success notification"""
        return self.notify(f" {title}", message, app, urgent=False)
    
    def warning(self, title, message, app="System"):
        """Create a warning notification"""
        return self.notify(f"️ {title}", message, app, urgent=True)
    
    def error(self, title, message, app="System"):
        """Create an error notification"""
        return self.notify(f" {title}", message, app, urgent=True)
    
    def info(self, title, message, app="System"):
        """Create an info notification"""
        return self.notify(f"ℹ️ {title}", message, app, urgent=False)


class SmartNotificationManager(NotificationManager):
    """Compatibility alias for advanced notification manager."""
    pass