---
name: agents-sync
anchors:
  watch-cost: "watch 轮次模型：整树协商 + 速率下限（同步面纪律）"
  gc: "gc：清单是权威、schedule 只是计划（删除对账）"
  commands: "常用命令"
---

# agents-sync — rsync over SSH 的单写者同步

本公开仓只住机制与测试。真实主机、neutral hub 路径、SSH 配置、服务装配与启动入口由调用方注入；修改部署不应产生本仓 diff。源码可独立 checkout，无需统一平台仓或 sibling 模块；不含服务切换或自动激活工具。

## 拓扑与文件身份

星型拓扑，每个节点只运行自己到同一 neutral hub 的一条双向链路。hub 无原件：受控落盘一律属 `replica` 组。每个文件恰有一个可能写者；未标记 = 本机原件，`replica` = 同步落地的副本，**不以时间戳裁决覆盖**。组名跨机一致，gid 无需一致。

- push 白名单 = 本地未标记文件；pull 保护清单 = 本地未标记文件。
- watch 固定 `-rlptDvc`、`--chown=:replica`，不使用 `-I`，也不接受 `--delete`。相同字节不重写，副本不回推。
- 原件属组不可读或路径无法安全编码时，整轮 pull 拒绝，不允许保护清单缺项。
- pull 后按 rsync 报出的已传输集补打组标记；macOS 目录恢复主组，避免目录组继承把新原件误判为副本。
- 启动闸门：组可解析、本地 chgrp 功能、端到端 chown 探针。失败拒启；远端探针只应由获准的调用方发起。

`replica-tag.py` 是**纯手动**辅助工具，默认 dry-run，不在服务链路内。信封按 `from` 解宿主，ack 按订阅者 spec 解，enable 按单一全局调度方解；UNKNOWN 保持未标记。调用方须提供与 hub/调度方一致的 `AGENTS_SYNC_HUB` 规范名；原有归属分类政策不变。

## 独立源码与根接口

`platform_paths.py` 是本仓本地薄 helper（来源逐提交记录见 `recovery/`），不导入 sibling 或退回统一仓。

- `workspace_root(source)`：非空 `PLATFORM_WORKSPACE` 优先（展开 `~`、绝对化，相对值按调用 cwd）；否则解析 source 真路径，默认源码仓的父目录。空值同未设，不要求 `.platform-root`。
- 源码身份按 realpath，软链入口不能拿软链祖先冒充 workspace。固定 release 目录应显式注入真实 workspace。
- `loop.sh` 用同一 helper 定位 workspace，真实本仓路径定位 `ssh-sync.py`；SG re-exec 和每一轮 watch 均保持该身份。空格和单引号路径按 POSIX shell word 引用，兼容 Bash 3.2。
- 本地 Python 入口（gc/ssh-sync/replica-tag）只从真实本仓目录导入 helper 和 `delete_contract`；无 agentd 运行依赖。

调用接口：

| 配置 | 语义 |
|---|---|
| `PLATFORM_WORKSPACE` | workspace 覆盖；默认本地 agents 为 `<workspace>/agents` |
| `AGENTS_SYNC_REMOTE` | `host:neutral-directory`，loop 必填；watch 可用第二位置参数覆盖；无内置生产端点 |
| `AGENTS_SYNC_HUB` | replica-tag 的规范 hub/调度方身份，运行时必填 |
| `SSH_SYNC_CONFIG` | SSH 配置；默认 `~/.ssh/config`，所有 SSH 调用使用 `-F` |
| `GC_AGENTS_DIR` | hub 权威树显式路径，优先级最高 |
| `GC_WORKSPACE` | 显式兼容覆盖：使用它的 `agents/`，state 也位于该 workspace |
| `AGENTS_SYNC_HUB_DIR` | 无前两项时可选的 neutral hub 目录；存在时使用，否则保留 `<workspace>/agents` 默认 |
| `PYTHON` | loop 的 Python 可执行文件（单个路径），默认 `python3` |

loop 缺 replica 进程凭据时只经 `sg replica` 自愈一次；已尝试仍缺组或没有 sg 时，一行 ERROR 后退出，不进入重启热循环。`/etc/group` 有组不代表旧会话具有该凭据。watch 退出按 2s 起步、有界翻倍到 60s 退避；存活至少 60s 复位。TERM/INT 带走当前子进程。服务的 process match 应由部署方按实际独立源码入口装配，不沿用统一仓相对路径假设。

## 显式前台运输：`watch --foreground`

供外部监督器直接运行 `ssh-sync.py watch ... --foreground`，不套 `loop.sh`。
旧 watch/一次性命令的默认SSH参数不变；不新增local传输入口或payload重启器。
此入口不导入rund/agentd，不要求lease文件或继承私有FD。

- 所有SSH路径（preflight、rsync `-e`、版本/诊断、probe、事件流）统一禁用
  `ControlMaster`、`ControlPersist`和ControlPath复用，并关闭
  `ForkAfterAuthentication`、`PermitLocalCommand`。配置必须由调用方控制，
  不得配置会脱组/后台化的ProxyCommand/ProxyJump/Match exec等；这些选项
  **不是任意SSH配置的安全审计/沙箱**，本候选没有验证实际OpenSSH版本。
- 首条preflight前安装TERM/INT处理；停止后不准新运输spawn，已知直接Popen
  的TERM/KILL后都真实wait。正常/异常/启动阶段都finally收口，并等探测线程
  结束，才返回前台入口。不以发送信号或join超时等同于停止。
- 通用前台命令预算30秒；原15/30秒诊断、600秒整树rsync预算保持。
  大stdin使用非agents TMPDIR内的私有匿名临时缓冲，经fd 0传入后回收，
  不是lease/协议文件；不增加stdin writer线程。旧默认运输不变。
  真实wait或pipe EOF无法取得时根可能继续阻塞，留给外部监督器确认强leader
  后对同组整体TERM/KILL；不猜退出码或以根Popen已退出证明远端退出。
- 只管理本link持有的直接运输Popen，不持运行时状态、killpg、重启watch或
  新后台worker。5→10→20→30秒事件流重连仍是业务重连，不是Service重试。
- 覆盖政策/整树校验/原件保护/GC清单和探针实现不因该选项改变。尤其启动
  probe仍含本地探针unlink和远端mktemp/rm，成功pull仍可应用GC清单；
  `--dry-run`不代表无probe副作用。调用前仍须由调用方明确授权具体树与
  probe/GC操作。前台运输候选不是完整Y/rund接线或真实同步授权。

`test_foreground.py`仅运行隔离普通Python helper，记录真实Popen身份/退出码，
覆盖大stdin重试、超时/停止、spawn登记竞窗、preflight信号、异常stream收口、
SSH参数全调用点与纯函数保护。假SSH和合成helper结果不证明实际SSH/rsync
派生树、远端退出、端到端group gate或数据一致性。测试根保留，不自动清理。
该测试须显式设置 `Y_FOREGROUND_OUTPUT` 为全新绝对目录，再运行
`python -B test_foreground.py`；它会创建私有HOME/TMPDIR/cwd，不可复用旧根。

## watch 轮次模型：整树协商 + 速率下限（同步面纪律）

一轮始终是整树 push + 整树 pull；rsync `-c` 决定是否搬运。检测器只回答是否有变更，不存路径快照、不参与覆盖裁决。

- `--debounce 0.5`：首个未消费事件窗口，持续 churn 不会无限延迟。
- `--min-cycle 3`：轮次速率下限。
- `--interval 30`：强制周期，也是任何变更重新锚定上界。树静默、检测器失效或远端断流也按周期运行。
- 每轮重协商，无可吞写的基线；失败退避后重新整树协商。空转不写搬运日志，统计按 `--stats-every` 汇总；`SSH_SYNC_DEBUG=1` 可逐轮诊断。

本地检测器：inotify_simple → watchdog/FSEvents → 无后端（仅周期驱动）。远端 SSH/inotify 流断开按 5/10/20/30s 重连，健康 60s 复位；远端缺 Python/inotify 则启动拒绝，不静默降级。SSH keepalive 防止半开连接无限阻塞。

`WATCH_EXCLUDES=[]`：当前无额外排除；历史 `*.pending` 已无写者，排除管道仍保留。gc delete-list 路径永远排除；无运行时开关改变该安全语义。

## gc：清单是权威、schedule 只是计划（删除对账）

`gc.py` 只在 hub 运行，是 per-invocation CLI（add/reap/list），无常驻服务、请求 inbox 或 snapshot diff。`delete_contract.py` 属本仓，是生成端与消费端共享的路径、保护资产、审计标记权威；不导入同名标准库 `gc` 来获取契约。

- 只有 `add` 写 schedule；`run/gc/state.json` 只是显式授权路径的待执行计划。默认宽限 300s，清单先传播，再删 hub 副本。
- `reap` 只执行到期计划。state 丢失不会自行猜测并删除：`list` 只读报告 unscheduled，需重新 add 才会排程。
- 清单累积，离线节点重连后收齐并应用删除；节点应用清单删除自己的副本/原件，后续永久拒收这些路径。hub 的受控清单落盘标 replica。
- 清单自身只通过 add 的授权压缩路径退役；不能由清单内容投票删除权威清单。
- 裸族容器（agents/task/bot/topic/queue/run）、树根同形、绝对路径、`..`、通配符、gc 自树等结构性拒绝，`--force` 也不能解除。
- `topic/dispatcher`、`queue/dispatcher` 及子路径默认保护；仅审计 `#FORCED:` 旁路解除资产保护，不解除结构保护。用户授权旁路前提由授权者负责。
- 消费侧复用同一契约，保留 300s 拒绝告警节流；删除 symlink 本身，不跟随目标。hub-only 清理豁免族政策仍由生成端执行。

## 常用命令

以下值均为示例/调用方变量，执行者应先确认授权树与目标：

```bash
PLATFORM_WORKSPACE="$WORKSPACE" AGENTS_SYNC_REMOTE="$HUB_REMOTE" bash ./loop.sh
python3 ./ssh-sync.py push ./fixture "$TEST_REMOTE" --dry-run
python3 ./ssh-sync.py --help
GC_WORKSPACE="$HUB_WORKSPACE" GC_AGENTS_DIR="$HUB_AGENTS" python3 ./gc.py list
AGENTS_SYNC_HUB="$HUB_ID" python3 ./replica-tag.py --root "$TEST_AGENTS" --self "$NODE_ID"
```

## 验证与恢复记录

`test_gc.py`、`test_protect.py`、`test_watch.py`、`test_replica_tag.py`、`test_delete_contract.py` 使用合成树；watch 的真实 rsync 用本地夹具，不 SSH。`test_platform_paths.py` / `test_independent.py` 验证根契约和无 sibling 布局；`test_loop.py` 截获 watch，不调用传输，覆盖 sg、二次 watch、真实/软链入口、引号路径和 TERM。`TEST_BASH=/path/to/bash-3.2` 可选择真实旧 Bash。

执行测试时应将 `TMPDIR`、`HOME`、workspace 放在自行创建的隔离根。恢复验收的外层 runner 还将历史 suite 的目录清理接到 agentd/safe_delete.py，仅授权该隔离临时基目录；该 runner 是任务工件，不是本仓生产依赖。详见 `recovery/ADAPTATION.md`。

`recovery/source-refs.json` 保存原 ref/OID/来源映射，`source-map.json` 逐 first-parent source 记录投影与 no-op，`projection-checks.json` 逐路径给适配前 blob/mode。原 main 是恢复 main 祖先；适配在投影后独立提交。保全 refs 不随 main 推进覆盖。

`mac-rsync-patch/` 是继承的可选平台补丁，未在本次恢复中安装或发布。部署/服务版本与激活由外部部署仓管理，本源码交付不代表任何生产切换。
