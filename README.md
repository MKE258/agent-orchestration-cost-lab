# 编排对照实验工具包

同一个迁移任务，用不同模型分工各跑几轮，比较门禁通过率、改对数和账单。

## 文件

| 文件 | 作用 |
| --- | --- |
| `TASK.md` | 交给 Agent 的任务模板，换成你的迁移 |
| `rubric.md` | 逐文件评分键，**第一轮之前写好** |
| `targets.txt` | 你自己建：要迁移的文件，每行一个相对路径 |
| `base/` | 你自己建：这些文件的原始副本，保持相对路径 |
| `base.sha256` | 你自己建：在 `base/` 里对 targets 逐个 `sha256sum` |
| `run.sh` | 跑一轮：`RUNS_DIR=<仓库外的目录> bash run.sh A 1`；组别 A–F 见脚本 |
| `gate.py` | 门禁，不调用模型：残留路径、语法、改动范围、脱敏是否保留。先改开头的 `MACHINE` 正则 |
| `usage.py` | 两种算法拆账单：CLI 的 result.modelUsage，以及会话 jsonl 按模型和角色（主会话 / advisor / 子 Agent）按官方价重算 |
| `prices.json` | 官方价目表（2026-10-09 读取），按完整模型 ID；用前去官方页面核对 |
| `review.py` | 盲审：新会话按 `rubric.md` 和 TASK.md 全文判每个 diff，看不到组别 |
| `selftest.sh` | 离线自测，不调用模型 |

## 先自测

```bash
bash selftest.sh
```

不调用模型。用一个写死路径的单文件夹具，确认门禁会拦原文件、放行改好的文件，盲审包里带着 TASK.md 全文。需要 Python 3、Git Bash 或任意 bash。

## 跑之前必看

1. **版本以脚本实际调起的那次为准。** 看 `stream.jsonl` 第一条 init 事件里的 `claude_code_version`，别拿另一个终端的 `claude --version` 代替：作者机器上，从 Claude 桌面版里启动的 shell 读到的全局 npm 是桌面版（MSIX 包）私有目录里的旧副本 2.1.280，外部终端已是 2.1.295。2.1.280 里 `--agents` 写 `"model":"haiku"` 实际跑 Haiku 4.5、写 `"sonnet"` 实际跑 Sonnet 5，`--model claude-sonnet-5-5` 的 costUSD 是官方价 2 倍；2.1.293、2.1.295 没有这两个问题。
2. **`run.sh` 不是沙箱。** 无头模式下 Read / Glob 能读整块盘。作者 12 轮里有 1 轮去真实目录做了只读核对。写操作没有越界，但别在副本里放不想让模型看到的东西，也别指望它看不到真实目录。
3. Opus 当主模型时，作者这台机器上的 Claude Code 默认带 advisor，`--disallowedTools advisor` 和 `CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL=0` 在 2.1.280、2.1.293 上都关不掉；它的消耗只在 `usage.iterations` 里，`usage.py` 会单列。
4. 门禁全过不等于能用。迁移完，在真实机器上把新路径求值一次，看目标存不存在。
5. `run.sh` 把每轮证据写到工具包**上一级**的 `evidence/runs/<组别><轮次>/`（stream.jsonl、out/、gate.txt）。之后在工具包目录里跑 `python usage.py ../evidence/runs` 出账单，`python review.py ../evidence/runs ../evidence/review` 出盲审。
6. `review.py` 会把 `TASK.md` 全文附给盲审。别只在审稿说明里转述任务，作者第一次就是转述漏了半句，把改对的判成了错。
