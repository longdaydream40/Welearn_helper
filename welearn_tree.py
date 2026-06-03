import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

from keyboard_tree_selector import TreeNode


@dataclass
class CourseContext:
    cid: str
    uid: str
    classid: str
    course: Dict[str, Any]
    units: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SelectedChapter:
    context: CourseContext
    unit_index: int
    unit: Dict[str, Any]
    chapter: Dict[str, Any]


def build_course_tree(session) -> List[TreeNode]:
    response = session.get(
        "https://welearn.sflep.com/ajax/authCourse.aspx?action=gmc",
        headers={"Referer": "https://welearn.sflep.com/2019/student/index.aspx"},
    )
    if '\"clist\":[]}' in response.text:
        input("发生错误!!!可能是登录错误或没有课程!!!")
        exit(0)

    courses = response.json()["clist"]
    nodes = []
    for course in courses:
        label = f'完成度{course["per"]:>3}% {course["name"]}'
        nodes.append(
            TreeNode(
                key=f"course:{course['cid']}",
                label=label,
                payload={"type": "course", "course": course},
                children_loader=lambda course=course: _load_course_units(session, course),
            )
        )
    return nodes


def resolve_selected_chapters(session, selected_nodes: Sequence[TreeNode]) -> List[SelectedChapter]:
    selected: List[SelectedChapter] = []
    seen = set()

    for node in selected_nodes:
        payload = node.payload or {}
        payload_type = payload.get("type")
        if payload_type == "section":
            _append_chapter(selected, seen, payload["context"], payload["unit_index"], payload["unit"], payload["chapter"])
        elif payload_type == "unit":
            context = payload["context"]
            unit_index = payload["unit_index"]
            unit = payload["unit"]
            for chapter in fetch_unit_chapters(session, context, unit_index):
                _append_chapter(selected, seen, context, unit_index, unit, chapter)
        elif payload_type == "course":
            context = _get_course_context(session, payload["course"])
            for unit_index, unit in enumerate(_get_course_units(session, context)):
                for chapter in fetch_unit_chapters(session, context, unit_index):
                    _append_chapter(selected, seen, context, unit_index, unit, chapter)

    return selected


def fetch_unit_chapters(session, context: CourseContext, unit_index: int) -> List[Dict[str, Any]]:
    response = session.get(
        f"https://welearn.sflep.com/ajax/StudyStat.aspx?action=scoLeaves&cid={context.cid}&uid={context.uid}&unitidx={unit_index}&classid={context.classid}",
        headers={"Referer": f"https://welearn.sflep.com/2019/student/course_info.aspx?cid={context.cid}"},
    )
    if "异常" in response.text or "出错了" in response.text:
        return []
    return response.json()["info"]


def _load_course_units(session, course: Dict[str, Any]) -> List[TreeNode]:
    context = _get_course_context(session, course)
    units = _get_course_units(session, context)
    nodes = []
    for unit_index, unit in enumerate(units):
        visible = "已开放" if unit["visible"] == "true" else "未开放"
        label = f'[{visible}] {unit["unitname"]} {unit["name"]}'
        nodes.append(
            TreeNode(
                key=f"unit:{context.cid}:{unit_index}",
                label=label,
                payload={
                    "type": "unit",
                    "context": context,
                    "unit_index": unit_index,
                    "unit": unit,
                },
                children_loader=lambda context=context, unit_index=unit_index, unit=unit: _load_unit_sections(
                    session, context, unit_index, unit
                ),
            )
        )
    return nodes


def _load_unit_sections(session, context: CourseContext, unit_index: int, unit: Dict[str, Any]) -> List[TreeNode]:
    chapters = fetch_unit_chapters(session, context, unit_index)
    nodes = []
    for chapter in chapters:
        visible = "未开放" if chapter["isvisible"] == "false" else "已开放"
        complete = chapter.get("iscomplete", "")
        label = f'[{visible}] {complete} {chapter["location"]}'
        nodes.append(
            TreeNode(
                key=f"section:{context.cid}:{chapter['id']}",
                label=label,
                payload={
                    "type": "section",
                    "context": context,
                    "unit_index": unit_index,
                    "unit": unit,
                    "chapter": chapter,
                },
            )
        )
    return nodes


def _get_course_context(session, course: Dict[str, Any]) -> CourseContext:
    cached = course.get("_tree_context")
    if cached:
        return cached

    cid = str(course["cid"])
    response = session.get(f"https://welearn.sflep.com/student/course_info.aspx?cid={cid}")
    uid = re.search('"uid":(.*?),', response.text).group(1)
    classid = re.search('"classid":"(.*?)"', response.text).group(1)
    context = CourseContext(cid=cid, uid=uid, classid=classid, course=course)
    course["_tree_context"] = context
    return context


def _get_course_units(session, context: CourseContext) -> List[Dict[str, Any]]:
    if context.units:
        return context.units

    response = session.get(
        "https://welearn.sflep.com/ajax/StudyStat.aspx",
        params={"action": "courseunits", "cid": context.cid, "uid": context.uid},
        headers={"Referer": "https://welearn.sflep.com/2019/student/course_info.aspx"},
    )
    context.units = response.json()["info"]
    return context.units


def _append_chapter(
    selected: List[SelectedChapter],
    seen: set,
    context: CourseContext,
    unit_index: int,
    unit: Dict[str, Any],
    chapter: Dict[str, Any],
) -> None:
    key = (context.cid, str(chapter["id"]))
    if key in seen:
        return
    seen.add(key)
    selected.append(SelectedChapter(context=context, unit_index=unit_index, unit=unit, chapter=chapter))
