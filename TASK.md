# Migration task

<!-- 模板：把布局说明换成你自己的。原实验的 TASK 原文见文章。 -->

This directory mirrors part of a repository. The repository root is this directory. Describe any sibling folders the scripts refer to here.

The scripts listed in `targets.txt` hardcode paths on the author's machine: absolute paths that contain the author's user profile or documents tree.

Migrate each file so that:

1. It no longer contains an absolute path with the author's user profile or documents tree.
2. On the author's machine, with the repository layout unchanged, it still resolves the same locations it resolved before (or the location the original clearly intended).
3. Nothing else about its behaviour changes. Keep edits minimal.

Constraints:

- Edit only the files in `targets.txt`. Do not create, delete or rename other files, except notes under `_migration/`.
- You cannot run code. Read carefully instead.
- When finished, write `_migration/REPORT.md`: for each file, one or two lines on what you changed, plus anything suspicious you noticed.
