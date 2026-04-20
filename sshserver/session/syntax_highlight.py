import typing as t
from typing import Any
import logging

logger = logging.getLogger(__name__)


# =========================================================
# BASE STYLE CONFIG (глобальные дефолты)
# =========================================================
class StyleConfig:
    """Глобальные дефолтные ANSI стили (fallback / base theme)."""

    RESET = "\x1b[0m"
    _registry: dict[str, str] = {}

    class Colors:
        BLACK   = "\x1b[30m"
        RED     = "\x1b[31m"
        GREEN   = "\x1b[32m"
        YELLOW  = "\x1b[33m"
        BLUE    = "\x1b[34m"
        MAGENTA = "\x1b[35m"
        CYAN    = "\x1b[36m"
        WHITE   = "\x1b[37m"

        BOLD_BLACK   = "\x1b[1;30m"
        BOLD_RED     = "\x1b[1;31m"
        BOLD_GREEN   = "\x1b[1;32m"
        BOLD_YELLOW  = "\x1b[1;33m"
        BOLD_BLUE    = "\x1b[1;34m"
        BOLD_MAGENTA = "\x1b[1;35m"
        BOLD_CYAN    = "\x1b[1;36m"
        BOLD_WHITE   = "\x1b[1;37m"

    # ====================== DEFAULTS ======================
    SUCCESS             = "\x1b[32m"
    WARNING             = "\x1b[33m"
    ERROR               = "\x1b[31m"

    COMPLETION          = "\x1b[36m"
    COMPLETION_SELECTED = "\x1b[7;36m"

    INLINE_HINT         = "\x1b[2;37m"

    SYNTAX_COMMAND      = "\x1b[1;34m"
    SYNTAX_SUBCOMMAND   = "\x1b[1;36m"
    SYNTAX_OPTION       = "\x1b[33m"
    SYNTAX_DEFAULT      = RESET
    SYNTAX_WS           = RESET
    SYNTAX_STRING       = "\x1b[35m"
    SYNTAX_NUMBER       = "\x1b[36m"
    SYNTAX_PATH         = "\x1b[36m"
    SYNTAX_ENV          = "\x1b[32m"
    SYNTAX_FLAG         = "\x1b[33m"
    SYNTAX_KEY          = "\x1b[34m"
    SYNTAX_VALUE        = "\x1b[35m"
    SYNTAX_BOOL         = "\x1b[33m"
    SYNTAX_NULL         = "\x1b[2;37m"
    SYNTAX_OPERATOR     = "\x1b[31m"
    SYNTAX_COMMENT      = "\x1b[2;37m"
    SYNTAX_ERROR        = ERROR
    SYNTAX_WARNING      = WARNING


    # ====================== API ======================
    @classmethod
    def define(cls, name: str, ansi: str) -> None:
        if not isinstance(ansi, str) or not ansi.startswith("\x1b"):
            raise ValueError("ANSI color must be escape sequence string")

        setattr(cls, name, ansi)
        cls._registry[name] = ansi

    @classmethod
    def _resolve_color(cls, color, bg: bool, params) -> str:
        """
        Устаревший метод – теперь реальное разрешение цвета происходит
        в StyleContext с учётом возможностей терминала.
        Оставлен для обратной совместимости.
        """
        def apply_params(base: str) -> str:
            if not params:
                return base
            prefix = ";".join(map(str, params))
            return base.replace("\x1b[", f"\x1b[{prefix};")

        if isinstance(color, str) and color.startswith("\x1b"):
            return apply_params(color)

        if isinstance(color, str) and hasattr(cls.Colors, color):
            return apply_params(getattr(cls.Colors, color))

        # Для HEX/RGB возвращаем 16-цветный вариант (fallback)
        if isinstance(color, str) and color.startswith("#"):
            r, g, b = _parse_hex(color)
            return _rgb_to_ansi16(r, g, b, bg, params)

        if isinstance(color, tuple) and len(color) == 3:
            r, g, b = color
            return _rgb_to_ansi16(r, g, b, bg, params)

        raise TypeError(f"Unsupported color format: {type(color)}")


# =========================================================
# SESSION STYLE CONTEXT (главная магия)
# =========================================================
class StyleContext:
    def __init__(self, session, base=StyleConfig):
        self.session = session
        self.base = base
        self.overrides: dict[str, str] = {}

        self._detect_capabilities()
        self._load_env_overrides()

    # -------------------------
    # terminal capabilities
    # -------------------------
    def _detect_capabilities(self):
        env = self.session.extra.get("env")

        # =========================
        # 1. USER OVERRIDE (главное)
        # =========================
        mode = (env.get("STYLE_COLOR_MODE") or "").lower()

        if mode in ("truecolor", "24bit"):
            self.truecolor = True
            self.colors256 = False
            self.basic = False
            return

        if mode in ("256", "256color"):
            self.truecolor = False
            self.colors256 = True
            self.basic = False
            return

        if mode in ("16", "basic"):
            self.truecolor = False
            self.colors256 = False
            self.basic = True
            return

        # =========================
        # 2. AUTO DETECT (fallback)
        # =========================
        term = self.session.term_type or ""
        colorterm = (self.session.colorterm or "").lower()

        self.truecolor = "truecolor" in colorterm or "24bit" in colorterm
        self.colors256 = "256color" in term
        self.basic = not (self.truecolor or self.colors256)

    # -------------------------
    # env overrides
    # -------------------------
    def _load_env_overrides(self):
        env = self.session.extra.get("env")

        raw: dict[str, str] = {}

        # 1. собрать всё
        for key, value in env.all().items():
            if key == "STYLE_COLOR_MODE":
                continue
            if key.startswith("STYLE_"):
                name = key.removeprefix("STYLE_")
                value = _normalize_ansi(value)
                raw[name] = value

        # 2. резолв с зависимостями
        for name in raw:
            try:
                ansi = self._resolve_with_refs(raw[name], raw)
                self.overrides[name] = ansi
            except Exception as e:
                logger.debug(
                    "Style override failed: %s=%s (%s)",
                    f"STYLE_{name}",
                    raw[name],
                    e
                )

    def _resolve_with_refs(self, value: str, raw: dict[str, str], depth=0) -> str:
        if depth > 5:
            raise ValueError("Recursive style reference")

        # 1. если это ссылка на другой стиль
        if value in raw:
            return self._resolve_with_refs(raw[value], raw, depth + 1)

        # 2. если это базовый стиль (имя атрибута StyleConfig)
        if hasattr(self.base, value):
            return getattr(self.base, value)

        # 3. разрешить как цвет (HEX / RGB / имя цвета из Colors)
        return self._resolve_color(value, bg=False, params=())

    # -------------------------
    # Реальное преобразование цвета с учётом truecolor/256/16
    # -------------------------
    def _resolve_color(self, color, bg: bool, params: tuple) -> str:
        """Преобразует цвет в ANSI escape с учётом возможностей терминала."""
        def apply_params(base: str) -> str:
            if not params:
                return base
            prefix = ";".join(map(str, params))
            return base.replace("\x1b[", f"\x1b[{prefix};")

        # 1. Уже готовая ANSI последовательность
        if isinstance(color, str) and color.startswith("\x1b"):
            return apply_params(color)

        # 2. Имя цвета из StyleConfig.Colors
        if isinstance(color, str) and hasattr(self.base.Colors, color):
            return apply_params(getattr(self.base.Colors, color))

        # 3. HEX / RGB
        if isinstance(color, str) and color.startswith("#"):
            r, g, b = _parse_hex(color)
        elif isinstance(color, tuple) and len(color) == 3:
            r, g, b = color
        else:
            raise TypeError(f"Unsupported color format: {type(color)}")

        # Генерируем код в зависимости от режима
        if self.truecolor:
            base = f"\x1b[{48 if bg else 38};2;{r};{g};{b}m"
        elif self.colors256:
            # Упрощённый перевод в 256-цветов (6x6x6 куб)
            code = 16 + (36 * (r // 51)) + (6 * (g // 51)) + (b // 51)
            base = f"\x1b[{48 if bg else 38};5;{code}m"
        else:
            # 16 цветов (basic)
            base = _rgb_to_ansi16(r, g, b, bg, params)
            # _rgb_to_ansi16 уже добавляет параметры, поэтому возвращаем как есть
            return base

        return apply_params(base)

    # -------------------------
    # API
    # -------------------------
    def get(self, name: str) -> str:
        if name in self.overrides:
            return self.overrides[name]
        return getattr(self.base, name, self.base.RESET)

    def apply(self, name: str, text: str) -> str:
        return f"{self.get(name)}{text}{self.base.RESET}"

    def set(self, name: str, color, bg=False, *params):
        ansi = self._resolve_color(color, bg, params)
        self.overrides[name] = ansi

    def reload(self):
        """Перечитать env и применить стили заново"""
        self.overrides.clear()
        self._detect_capabilities()
        self._load_env_overrides()


def _parse_hex(hex_color: str):
    hex_color = hex_color.lstrip("#")

    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)

    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return r, g, b


def _rgb_to_ansi16(r: int, g: int, b: int, bg: bool, params) -> str:
    brightness = (r + g + b) / 3

    if brightness < 85:
        code = 30
    elif brightness < 170:
        code = 34
    else:
        code = 37

    if bg:
        code += 10

    if params:
        return f"\x1b[{';'.join(map(str, params))};{code}m"

    return f"\x1b[{code}m"


def _normalize_ansi(value: str) -> str:
    if value.startswith("\\x1b"):
        return value.replace("\\x1b", "\x1b")
    if value.startswith("\\033"):
        return value.replace("\\033", "\x1b")
    if value.startswith("\\e"):
        return value.replace("\\e", "\x1b")
    return value