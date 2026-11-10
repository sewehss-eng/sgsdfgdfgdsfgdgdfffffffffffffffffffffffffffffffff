"""
Онбординг владельца.

Основная логика онбординга реализована в menu.py (_show_onboarding при /admin,
если root folder не задан) и settings.py (сохранение root folder).
Этот модуль оставлен как точка расширения; отдельных хендлеров не содержит,
чтобы не дублировать роутинг.
"""
from __future__ import annotations

# Намеренно пусто: см. bot/handlers/owner/menu.py и settings.py
