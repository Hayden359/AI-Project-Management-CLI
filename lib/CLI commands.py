"""Project-management models, JSON storage, and command-line interface."""

import argparse
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional, Sequence, TypeVar
from uuid import uuid4

Record = TypeVar("Record")


@dataclass
class User:
    id: str
    name: str
    email: str
    project_ids: list[str] = field(default_factory=list)


@dataclass
class Project:
    id: str
    owner_id: str
    title: str
    description: str
    task_ids: list[str] = field(default_factory=list)


@dataclass
class Task:
    id: str
    title: str
    description: str
    project_ids: list[str] = field(default_factory=list)
    contributor_ids: list[str] = field(default_factory=list)
    completed: bool = False


class ProjectManager:
    """Manage users, projects, and tasks in a JSON file."""

    def __init__(self, data_file: str | Path = "project_data.json") -> None:
        self.data_file = Path(data_file)
        self.users: dict[str, User] = {}
        self.projects: dict[str, Project] = {}
        self.tasks: dict[str, Task] = {}
        self._load()

    def add_user(self, name: str, email: str) -> User:
        name = self._required_text(name, "User name")
        email = self._required_text(email, "User Email")
        if any(
            user.email.casefold() == email.casefold()
            for user in self.users.values()
        ):
            raise ValueError(f"A user with '{email}' already exists.")

        user = User(id=self._new_id(), name=name, email=email)
        self.users[user.id] = user
        self._save()
        return user

    def list_users(self) -> list[User]:
        return sorted(self.users.values(), key=lambda user: user.name.casefold())

    def add_project(
        self, user_identifier: str, title: str, description: str = ""
    ) -> Project:
        owner = self.get_user(user_identifier)
        title = self._required_text(title, "Project title")
        description = description.strip()
        if any(
            project.owner_id == owner.id
            and project.title.casefold() == title.casefold()
            for project in self.projects.values()
        ):
            raise ValueError(
                f"User '{owner.name}' already has a project titled '{title}'."
            )

        project = Project(
            id=self._new_id(),
            owner_id=owner.id,
            title=title,
            description=description,
        )
        self.projects[project.id] = project
        owner.project_ids.append(project.id)
        self._save()
        return project

    def list_projects(self, user_identifier: Optional[str] = None) -> list[Project]:
        if user_identifier is None:
            projects = list(self.projects.values())
        else:
            user = self.get_user(user_identifier)
            projects = [
                self.projects[project_id]
                for project_id in user.project_ids
                if project_id in self.projects
            ]
        return sorted(projects, key=lambda project: project.title.casefold())

    def edit_project(
        self,
        project_identifier: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Project:
        project = self.get_project(project_identifier)
        if title is None and description is None:
            raise ValueError("Input a new title or description.")
        if title is not None:
            title = self._required_text(title, "Project title")
            if any(
                other.id != project.id
                and other.owner_id == project.owner_id
                and other.title.casefold() == title.casefold()
                for other in self.projects.values()
            ):
                raise ValueError(
                    f"The '{title}' project already exists for this user."
                )
            project.title = title
        if description is not None:
            project.description = description.strip()
        self._save()
        return project

    def add_task(
        self,
        project_identifiers: Sequence[str],
        title: str,
        description: str = "",
        contributor_identifiers: Sequence[str] = (),
    ) -> Task:
        if not project_identifiers:
            raise ValueError("At least one project is required.")
        projects = [self.get_project(identifier) for identifier in project_identifiers]
        if len({project.id for project in projects}) != len(projects):
            raise ValueError("A project can be listed only once for a task.")

        title = self._required_text(title, "Task title")
        description = description.strip()
        contributors = [
            self.get_user(identifier) for identifier in contributor_identifiers
        ]
        if len({user.id for user in contributors}) != len(contributors):
            raise ValueError("A contributor can only be listed only once for a task.")

        task = Task(
            id=self._new_id(),
            title=title,
            description=description,
            project_ids=[project.id for project in projects],
            contributor_ids=[user.id for user in contributors],
        )
        self.tasks[task.id] = task
        for project in projects:
            project.task_ids.append(task.id)
        self._save()
        return task

    def list_tasks(self, project_identifier: str) -> list[Task]:
        project = self.get_project(project_identifier)
        tasks = [
            self.tasks[task_id]
            for task_id in project.task_ids
            if task_id in self.tasks
        ]
        return sorted(tasks, key=lambda task: task.title.casefold())

    def edit_task(
        self,
        task_identifier: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Task:
        task = self.get_task(task_identifier)
        if title is None and description is None:
            raise ValueError("Input a new title or description.")
        if title is not None:
            task.title = self._required_text(title, "Task title")
        if description is not None:
            task.description = description.strip()
        self._save()
        return task

    def assign_task(self, project_identifier: str, task_identifier: str) -> Task:
        project = self.get_project(project_identifier)
        task = self.get_task(task_identifier)
        if project.id in task.project_ids:
            raise ValueError(
                f"'{task.title}' is a tast already assigned to project '{project.title}'."
            )
        task.project_ids.append(project.id)
        project.task_ids.append(task.id)
        self._save()
        return task

    def complete_task(self, project_identifier: str, task_identifier: str) -> Task:
        project = self.get_project(project_identifier)
        task = self.get_task(task_identifier)
        if project.id not in task.project_ids:
            raise ValueError(
                f"'{task.title}' is not assigned to project '{project.title}'."
            )
        task.completed = True
        self._save()
        return task

    def get_user(self, identifier: str) -> User:
        return self._resolve(identifier, self.users, "user", ("name", "email"))

    def get_project(self, identifier: str) -> Project:
        return self._resolve(identifier, self.projects, "project", ("title",))

    def get_task(self, identifier: str) -> Task:
        return self._resolve(identifier, self.tasks, "task", ("title",))

    @staticmethod
    def _resolve(
        identifier: str,
        records: dict[str, Record],
        kind: str,
        fields: tuple[str, ...],
    ) -> Record:
        identifier = ProjectManager._required_text(
            identifier, f"{kind.title()} identifier"
        )
        if identifier in records:
            return records[identifier]
        matches = [
            record
            for record in records.values()
            if any(
                getattr(record, field_name).casefold() == identifier.casefold()
                for field_name in fields
            )
        ]
        if not matches:
            raise ValueError(f"No {kind} matches '{identifier}'.")
        if len(matches) > 1:
            raise ValueError(
                f"'{identifier}' matches multiple {kind}s; use a unique name or ID."
            )
        return matches[0]

    @staticmethod
    def _required_text(value: str, label: str) -> str:
        if value is None or not value.strip():
            raise ValueError(f"{label} cannot be empty.")
        return value.strip()

    @staticmethod
    def _new_id() -> str:
        return str(uuid4())

    def _load(self) -> None:
        if not self.data_file.exists():
            return
        with self.data_file.open(encoding="utf-8") as data_file:
            data = json.load(data_file)
        self.users = {item["id"]: User(**item) for item in data.get("users", [])}
        self.projects = {item["id"]: Project(**item) for item in data.get("projects", [])}
        self.tasks = {item["id"]: Task(**item) for item in data.get("tasks", [])}

    def _save(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "users": [asdict(user) for user in self.users.values()],
            "projects": [asdict(project) for project in self.projects.values()],
            "tasks": [asdict(task) for task in self.tasks.values()],
        }
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.data_file.parent,
                prefix=f".{self.data_file.name}.",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(data, temporary_file, indent=2)
                temporary_file.write("\n")
            os.replace(temporary_path, self.data_file)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage users, projects, and tasks from the command line."
    )
    parser.add_argument(
        "--data-file",
        default=os.environ.get("PROJECT_MANAGER_DATA", "project_data.json"),
        help="JSON file used to persist data (default: project_data.json).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    add_user = commands.add_parser("add-user", help="Create a user.")
    add_user.add_argument("--name", required=True)
    add_user.add_argument("--email", required=True)

    commands.add_parser("list-users", help="List all users.")

    add_project = commands.add_parser(
        "add-project", help="Create a project for a user."
    )
    add_project.add_argument("--user", required=True, help="User name, email, or ID.")
    add_project.add_argument("--title", required=True)
    add_project.add_argument("--description", default="")

    list_projects = commands.add_parser("list-projects", help="List projects.")
    list_projects.add_argument(
        "--user", help="Optionally filter by user name, email, or ID."
    )

    edit_project = commands.add_parser(
        "edit-project", help="Edit a project's title or description."
    )
    edit_project.add_argument("--project", required=True)
    edit_project.add_argument("--title")
    edit_project.add_argument("--description")

    add_task = commands.add_parser("add-task", help="Create and assign a task.")
    add_task.add_argument(
        "--project",
        action="append",
        required=True,
        help="Project title or ID, repeat to assign the task to multiple projects.",
    )
    add_task.add_argument("--title", required=True)
    add_task.add_argument("--description", default="")
    add_task.add_argument(
        "--contributor",
        action="append",
        default=[],
        help="Contributor name, email, or ID.",
    )

    assign_task = commands.add_parser(
        "assign-task", help="Assign an existing task to another project."
    )
    assign_task.add_argument("--project", required=True)
    assign_task.add_argument("--task", required=True)

    edit_task = commands.add_parser(
        "edit-task", help="Edit a task's title or description."
    )
    edit_task.add_argument("--task", required=True)
    edit_task.add_argument("--title")
    edit_task.add_argument("--description")

    complete_task = commands.add_parser(
        "complete-task", help="Mark a project's task as complete."
    )
    complete_task.add_argument("--project", required=True)
    complete_task.add_argument("--task", required=True)

    list_tasks = commands.add_parser("list-tasks", help="List tasks for a project.")
    list_tasks.add_argument("--project", required=True)

    summarize = commands.add_parser(
    "summarize-project",
    help="Ask the configured AI service to summarize a project.",
    )
    summarize.add_argument("--project", required=True)
    summarize.add_argument("--model", default="llama3.2")

    return parser


def _format_project(manager: ProjectManager, project: Project) -> str:
    owner = manager.users[project.owner_id]
    return (
        f"{project.title} (owner: {owner.name}; ID: {project.id})\n"
        f"  {project.description}"
    )


def _format_task(manager: ProjectManager, task: Task) -> str:
    status = "complete" if task.completed else "open"
    contributors = ", ".join(
        manager.users[user_id].name
        for user_id in task.contributor_ids
        if user_id in manager.users
    ) or "none"
    projects = ", ".join(
        f"{manager.projects[project_id].title} ({project_id})"
        for project_id in task.project_ids
        if project_id in manager.projects
    ) or "none"
    return (
        f"{task.title} [{status}] (ID: {task.id})\n"
        f"  Projects: {projects}\n"
        f"  Contributors: {contributors}\n"
        f"  {task.description}"
    )


def _summarize_project(
    manager: ProjectManager, project_identifier: str, model_name: str
) -> str:
    project = manager.get_project(project_identifier)
    tasks = manager.list_tasks(project.id)
    task_details = "\n".join(
        f"- {task.title} ({'complete' if task.completed else 'open'}): "
        f"{task.description or 'No description'}"
        for task in tasks
    ) or "No tasks have been assigned."
    prompt = (
        "Summarize this project for its owner. Use only the supplied details and "
        "do not invent information.\n"
        f"Project: {project.title}\n"
        f"Description: {project.description or 'No description'}\n"
        f"Tasks:\n{task_details}"
    )
    try:
        from .ai_client import OllamaChatClient
    except ImportError:
        from ai_client import OllamaChatClient

    summary = OllamaChatClient(model_name=model_name).send(prompt)
    return f"Project summary: {project.title}\n{summary}"


def run_command(args: argparse.Namespace, manager: ProjectManager) -> str:
    if args.command == "add-user":
        user = manager.add_user(args.name, args.email)
        return f"Added user {user.name} <{user.email}> (ID: {user.id})."
    if args.command == "list-users":
        users = manager.list_users()
        return "\n".join(
            f"{user.name} <{user.email}> (ID: {user.id})" for user in users
        ) or "No users found."
    if args.command == "add-project":
        project = manager.add_project(args.user, args.title, args.description)
        return f"Added project:\n{_format_project(manager, project)}"
    if args.command == "list-projects":
        projects = manager.list_projects(args.user)
        return "\n".join(
            _format_project(manager, project) for project in projects
        ) or "No projects found."
    if args.command == "edit-project":
        project = manager.edit_project(args.project, args.title, args.description)
        return f"Updated project:\n{_format_project(manager, project)}"
    if args.command == "add-task":
        task = manager.add_task(
            args.project, args.title, args.description, args.contributor
        )
        return f"Added task:\n{_format_task(manager, task)}"
    if args.command == "assign-task":
        task = manager.assign_task(args.project, args.task)
        project = manager.get_project(args.project)
        return f"Assigned task '{task.title}' to project '{project.title}'."
    if args.command == "edit-task":
        task = manager.edit_task(args.task, args.title, args.description)
        return f"Updated task:\n{_format_task(manager, task)}"
    if args.command == "complete-task":
        task = manager.complete_task(args.project, args.task)
        return f"Marked task '{task.title}' complete."
    if args.command == "list-tasks":
        tasks = manager.list_tasks(args.project)
        return "\n".join(_format_task(manager, task) for task in tasks) or "No tasks found."
    if args.command == "summarize-project":
        return _summarize_project(manager, args.project, args.model)
    raise ValueError(f"Unsupported command: {args.command}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        manager = ProjectManager(args.data_file)
        print(run_command(args, manager))
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except (ImportError, RuntimeError) as error:
        print(f"Service Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
