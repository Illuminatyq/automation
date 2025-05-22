"""
Конфигурация разрешений экрана для визуального тестирования
"""

VIEWPORT_CONFIGS = {
    "desktop": {
        "small": {"width": 1024, "height": 768},
        "medium": {"width": 1366, "height": 768},
        "large": {"width": 1920, "height": 1080}
    },
    "tablet": {
        "portrait": {"width": 768, "height": 1024},
        "landscape": {"width": 1024, "height": 768}
    },
    "mobile": {
        "small": {"width": 320, "height": 568},  # iPhone 5
        "medium": {"width": 375, "height": 667},  # iPhone 6/7/8
        "large": {"width": 414, "height": 736}   # iPhone 6/7/8 Plus
    }
}

# Список всех разрешений для тестирования
ALL_VIEWPORTS = [
    ("desktop", "small"),
    ("desktop", "medium"),
    ("desktop", "large"),
    ("tablet", "portrait"),
    ("tablet", "landscape"),
    ("mobile", "small"),
    ("mobile", "medium"),
    ("mobile", "large")
] 