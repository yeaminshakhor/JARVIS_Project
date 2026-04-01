"""
GUI module for JARVIS AI Assistant
Contains all graphical user interface components
"""

from .main_window import (
    SimpleJarvisWindow,
    main as gui_main
)

from .monitors import (
    LargeCPUMonitor,
    LargeMemoryMonitor,
    LargeBatteryMonitor,
    SimpleCPUMonitor,
    SimpleMemoryMonitor,
    SimpleBatteryMonitor,
    SystemMonitor
)

from .notifications import (
    NotificationManager,
    NotificationDialog,
    NotificationButton,
    Notifier,
    SmartNotificationManager
)

__all__ = [
    # Main Window
    'SimpleJarvisWindow',
    'gui_main',
    
    # Monitors
    'LargeCPUMonitor',
    'LargeMemoryMonitor',
    'LargeBatteryMonitor',
    'SimpleCPUMonitor',
    'SimpleMemoryMonitor',
    'SimpleBatteryMonitor',
    'SystemMonitor',
    
    # Notifications
    'NotificationManager',
    'NotificationDialog',
    'NotificationButton',
    'Notifier',
    'SmartNotificationManager'
]