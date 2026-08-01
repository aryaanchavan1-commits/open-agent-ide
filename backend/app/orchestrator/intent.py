from sqlalchemy.orm import Session

from ..models import Project, Task

BUILD_SEQUENCE = [
    ("product_manager", "Analyze the project request and produce requirements.", None),
    ("architect", "Design the architecture for the requested project.", None),
    ("planner", "Break the project into implementation tasks.", None),
]


def build_sequence(intent_type: str, message: str, db: Session, project: Project) -> list[tuple[str, str, str | None]]:
    if intent_type == "build":
        if project.status == "created":
            seq: list[tuple[str, str, str | None]] = list(BUILD_SEQUENCE)
            tasks = db.query(Task).filter(Task.project_id == project.id).order_by(Task.id).limit(3).all()
            pending = [t for t in tasks if t.status in ("pending", "in_progress")]
            for task in pending[:3]:
                seq.append(("coder", f"Implement task {task.task_id}: {task.title}\n{task.description}", task.task_id))
            if pending:
                seq.append(("tester", "Run the project tests and report results.", None))
            return seq
        tasks = db.query(Task).filter(Task.project_id == project.id).order_by(Task.id).limit(3).all()
        pending = [t for t in tasks if t.status in ("pending", "in_progress")]
        if pending:
            seq = [("coder", f"Implement task {pending[0].task_id}: {pending[0].title}\n{pending[0].description}", pending[0].task_id)]
            seq.append(("tester", "Run the project tests and report results.", None))
            return seq
        return [("planner", message, None), ("coder", message, None)]
    if intent_type == "plan":
        return [("planner", message, None)]
    if intent_type == "code":
        return [("coder", message, None)]
    if intent_type == "debug":
        return [("debugger", message, None)]
    if intent_type == "test":
        return [("tester", message, None)]
    if intent_type == "review":
        return [("reviewer", message, None)]
    if intent_type == "document":
        return [("documentation", message, None)]
    if intent_type == "architect":
        return [("architect", message, None)]
    if intent_type == "product":
        return [("product_manager", message, None)]
    return [("coder", message, None)]
