from sshserver.terminal.line_editor.layout import build_layout
from sshserver.terminal.line_editor.ui import get_prompt_segments


def get_editor_layout(editor):
    return build_layout(
        buffer=editor._buffer,
        cursor=editor._cursor,
        term_width=editor.terminal.session.term_width or 80,
        prompt_segments=get_prompt_segments(editor.terminal),
    )

def layout_rows_text(layout):
    """Возвращает список строк для проверки визуала (splitlines на переносах)."""
    return layout.rendered_text.splitlines()