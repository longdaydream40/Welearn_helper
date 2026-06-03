import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple


ChildrenLoader = Callable[[], List["TreeNode"]]


@dataclass
class TreeNode:
    key: str
    label: str
    payload: Any = None
    children_loader: Optional[ChildrenLoader] = None
    selectable: bool = True
    children: Optional[List["TreeNode"]] = field(default=None, init=False)

    @property
    def expandable(self) -> bool:
        return self.children_loader is not None

    def load_children(self) -> List["TreeNode"]:
        if self.children_loader is None:
            return []
        if self.children is None:
            self.children = self.children_loader()
        return self.children


@dataclass
class _LevelState:
    title: str
    nodes: List[TreeNode]
    cursor: int = 0
    offset: int = 0


def select_tree(title: str, root_nodes: Sequence[TreeNode]) -> List[TreeNode]:
    return _select_tree(title, root_nodes, _read_key)


def _select_tree(title: str, root_nodes: Sequence[TreeNode], read_key: Callable[[], str]) -> List[TreeNode]:
    _enable_ansi_on_windows()
    selected_keys: Set[str] = set()
    selected_nodes: Dict[str, TreeNode] = {}
    stack: List[_LevelState] = [_LevelState(title=title, nodes=list(root_nodes))]
    message = ""

    while True:
        level = stack[-1]
        item_count = _item_count(level, len(stack) > 1)
        if item_count <= 0:
            level.cursor = 0
        elif level.cursor >= item_count:
            level.cursor = item_count - 1

        _render(level, stack, selected_keys, selected_nodes, message)
        message = ""
        key = read_key()

        if key == "up":
            if item_count:
                level.cursor = max(0, level.cursor - 1)
        elif key == "down":
            if item_count:
                level.cursor = min(item_count - 1, level.cursor + 1)
        elif key in ("left", "backspace", "esc"):
            if len(stack) > 1:
                stack.pop()
        elif key in ("right", "enter"):
            current = _current_node(level, len(stack) > 1)
            if current == "__done__":
                if selected_nodes:
                    _clear_screen()
                    return list(selected_nodes.values())
                message = "请至少选择一个条目后再确认。"
            elif current == "__back__":
                if len(stack) > 1:
                    stack.pop()
            elif isinstance(current, TreeNode):
                if current.expandable:
                    children = current.load_children()
                    if children:
                        stack.append(_LevelState(title=current.label, nodes=children, cursor=1))
                    else:
                        message = "当前条目没有可进入的下级。"
                else:
                    message = "当前条目已经是末级，按空格可切换选中。"
        elif key == "space":
            current = _current_node(level, len(stack) > 1)
            if isinstance(current, TreeNode):
                if not current.selectable:
                    message = "当前条目不可选。"
                elif current.key in selected_keys:
                    selected_keys.remove(current.key)
                    selected_nodes.pop(current.key, None)
                else:
                    selected_keys.add(current.key)
                    selected_nodes[current.key] = current
        elif key in ("q", "ctrl_c"):
            _clear_screen()
            raise KeyboardInterrupt


def _item_count(level: _LevelState, has_parent: bool) -> int:
    return len(level.nodes) + 1 + (1 if has_parent else 0)


def _current_node(level: _LevelState, has_parent: bool) -> Any:
    index = level.cursor
    if has_parent:
        if index == 0:
            return "__back__"
        index -= 1
    if index < len(level.nodes):
        return level.nodes[index]
    return "__done__"


def _render(
    level: _LevelState,
    stack: Sequence[_LevelState],
    selected_keys: Set[str],
    selected_nodes: Dict[str, TreeNode],
    message: str,
) -> None:
    terminal = shutil.get_terminal_size(fallback=(100, 30))
    header_lines = 7
    visible_rows = max(5, terminal.lines - header_lines)
    items: List[Tuple[Any, str]] = [(node, _node_text(node, selected_keys)) for node in level.nodes]
    if len(stack) > 1:
        items.insert(0, ("__back__", "  <- 返回上一级"))
    items.append(("__done__", "  [完成] 选好了"))

    if level.cursor >= len(items):
        level.cursor = max(0, len(items) - 1)
    if level.cursor < level.offset:
        level.offset = level.cursor
    if level.cursor >= level.offset + visible_rows:
        level.offset = level.cursor - visible_rows + 1
    level.offset = max(0, min(level.offset, max(0, len(items) - visible_rows)))

    _clear_screen()
    path = " / ".join(item.title for item in stack)
    print(f"{title_line(path)}")
    print("↑/↓移动  Enter进入目录/确认  Space选中/取消  ←/Backspace返回  Q退出")
    print(f"已选中: {len(selected_nodes)}")
    if message:
        print(f"\033[33m{message}\033[0m")
    else:
        print("")
    print("-" * min(terminal.columns, 100))

    for row_index, (item, text) in enumerate(items[level.offset : level.offset + visible_rows], start=level.offset):
        active = row_index == level.cursor
        color = None
        if item == "__done__":
            color = "36"
        elif item == "__back__":
            color = "37"
        elif isinstance(item, TreeNode) and item.key in selected_keys:
            color = "32"

        if active:
            style = f"7;{color}" if color else "7"
            line = f"\033[{style}m{text}\033[0m"
        elif color:
            line = _color(text, color)
        else:
            line = text
        print(line)

    if len(items) > visible_rows:
        print("-" * min(terminal.columns, 100))
        print(f"{level.offset + 1}-{min(level.offset + visible_rows, len(items))}/{len(items)}")


def _node_text(node: TreeNode, selected_keys: Set[str]) -> str:
    marker = "[x]" if node.key in selected_keys else "[ ]"
    kind = "[+]" if node.expandable else "[-]"
    return f"  {marker} {kind} {node.label}"


def title_line(path: str) -> str:
    return f"\033[1m{path}\033[0m"


def _color(text: str, color: str) -> str:
    return f"\033[{color}m{text}\033[0m"


def _clear_screen() -> None:
    print("\033[2J\033[H", end="")


def _enable_ansi_on_windows() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def _read_key() -> str:
    if os.name == "nt":
        import msvcrt

        while True:
            char = msvcrt.getwch()
            if char in ("\x00", "\xe0"):
                code = msvcrt.getwch()
                return {
                    "H": "up",
                    "P": "down",
                    "K": "left",
                    "M": "right",
                }.get(code, "")
            if char == "\r":
                return "enter"
            if char == " ":
                return "space"
            if char == "\x08":
                return "backspace"
            if char == "\x1b":
                return "esc"
            if char == "\x03":
                return "ctrl_c"
            if char.lower() == "q":
                return "q"
    else:
        import sys
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            char = sys.stdin.read(1)
            if char == "\x1b":
                next_chars = sys.stdin.read(2)
                if next_chars == "[A":
                    return "up"
                if next_chars == "[B":
                    return "down"
                if next_chars == "[D":
                    return "left"
                if next_chars == "[C":
                    return "right"
                return "esc"
            if char in ("\r", "\n"):
                return "enter"
            if char == " ":
                return "space"
            if char in ("\x7f", "\b"):
                return "backspace"
            if char == "\x03":
                return "ctrl_c"
            if char.lower() == "q":
                return "q"
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ""
