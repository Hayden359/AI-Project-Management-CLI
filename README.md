# AI Project Management CLI

a command-line project management tool for a team of developers. The tool should allow administrators to manage users, projects, and tasks through structured CLI commands. The system supports:

Create and list users via the command line.
Add projects to specific users and display their associated projects.
Assign tasks to projects and mark them as complete.
Edit and persist project/task data using file I/O.
Navigate the tool with clear, user-friendly CLI commands.
Manage data relationships like one-to-many (users to projects) and many-to-many (projects to tasks with contributors).
Create and manage users, projects, and tasks.
Integrating one external package or external service feature.
Adding a reusable AI or external service client that supports one project-management command.

commands and examples

python3 "lib/CLI commands.py" add-user --name "Alex" --email "alex@example.com"
python3 "lib/CLI commands.py" list-users
python3 "lib/CLI commands.py" add-project --user "Alex" --title "CLI Tool" --description "Build project tracker"
python3 "lib/CLI commands.py" list-projects --user "Alex"
python3 "lib/CLI commands.py" add-task --project "CLI Tool" --title "Implement add-task command" --contributor "Alex"
python3 "lib/CLI commands.py" complete-task --project "CLI Tool" --task "Implement add-task command"
python3 "lib/CLI commands.py" list-tasks --project "CLI Tool"
python3 "lib/CLI commands.py" summarize-project --project "CLI Tool"


Use "edit-project --project ..." or "edit-task --task ..."  to connect a
task to multiple projects