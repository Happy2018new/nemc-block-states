# nemc-block-states

网易基岩版（NEMC）方块状态、版本化方块表和状态变换库。

本库的目标是为 `better-building-editor` 提供“方块是什么状态以及变换后是什么状态”的唯一来源。它不负责编辑器 UI、Minecraft 实例、投影 actor、shader、纹理、世界写入或保存／分享。

截至 **2026-10-19**，已建立首个可独立导入的纯 Python 快照，支持 Python 2.7／3。主仓库仍使用原路径，尚未接入本库。快照的五个状态／变换／资格模块由主仓库原样同步，不能在两处分别修改规则。来源、版本边界与待迁模块见 [迁移清单](docs/SOURCE_INVENTORY.md)。

## 当前范围

- 版本化方块表和来源 SHA-256；
- 状态字段类型、aux／旧别名映射和合法状态；
- Y 轴旋转、X／Y／Z 镜像及伙伴关系；
- 双格结构、连接结构、含水／含雪资格；
- NBT schema、字段类型和版本兼容规则；
- 可供主仓库和 `nemc-block-renderer` 使用的稳定、纯数据 API。

目前实际可用的是方块名／aux／typed states／旧别名、六种状态变换、纯部件伙伴关系、固体资格和已记录的含水／含雪资格。双格事务、typed NBT、主程序集成尚未迁入；上方其余条目仍是目标范围。迁移期间主仓库实现是生成来源，只有完成接入并且两个连续更新通过后才删除重复生产规则。

## 使用与验证

在本仓库根目录运行，或将 `nemc_block_states` 目录一起放入 Addon 的可导入路径。运行时只依赖 Python 标准库，不初始化 ModSDK：

```python
from nemc_block_states import block_registry, state_transform, block_traits
from nemc_block_states.provenance import require_source, snapshot_manifest

value = block_registry.from_states('minecraft:oak_stairs', {
    'weirdo_direction': 0, 'upside_down_bit': False,
})
rotated = state_transform.transform(value, 'rotate_y90')
assert block_registry.states(rotated)['weirdo_direction'] == 2
require_source(block_registry.source_version(), block_registry.fingerprint())
```

`states()` 返回新的状态字典；`from_states()` 区分 bool 与 int；未知方向属性或不合法的原版状态不会静默通过。自定义方块可以保留名称／aux，但缺少状态定义时不能安全转换方向。

```powershell
python -m unittest discover -s tests -v
py -2.7 -m unittest discover -s tests -v
python tools/sync_from_bbe.py --source ../better-building-editor --check
python tools/verify_against_bbe.py --source ../better-building-editor
```

同步时去掉 `--check`，先在主仓库修改并通过原测试，再重新生成本库。同步工具只读取来源仓库。Python 3 的 16 项测试包含 11 项运行时测试与 5 项生成器防漏检查；Python 2.7 运行同样 11 项运行时测试，并显式跳过仅适用于 Python 3 工具的 5 项。独立测试覆盖全表 **15,858 状态 × 6 操作**及逆操作；对等检查另外核对 **503 旧别名**、**63,432 资格查询**与 **47,574 伙伴查询**。722 条成组状态还检查伙伴互反及变换后位移一致。这些是离线状态证据，不能关闭编辑器／投影外观问题。

`block_groups.group_partner(value)` 返回 `(相对位移, 伙伴方块)`，`group_is_upper()` 查询部件，`preserve_group_part()` 在替换时保留对应半部。它们由主仓库指定 AST 符号自动抽取，新增未审查依赖、符号丢失或函数内引入 import 都会使同步失败；这里不提供 `Cell`、世界观察、双箱 NBT、选区扩张或原子事务。

本快照真实来源为 **NEMC 3.9.0.401155**。用户提供的 3.10 dump 中，原版 **1,321 名称／15,839 状态**与归档旧表一致；新 dump 不内嵌精确版本。该比较不会把 3.9 traits、NBT 或渲染证据升级为 3.10 资格。`require_source()` 因此仍会拒绝直接把版本参数改成 3.10；详细来源保存在 [snapshot_manifest.json](snapshot_manifest.json)。

## 依赖和边界

状态规则不能读取 renderer 的模型或纹理，也不能通过字符串猜测 NBT。渲染库只消费本库输出的不可变状态快照。主仓库通过版本 manifest 锁定本库提交、游戏版本、方块表指纹和生成器版本；指纹不匹配时必须拒绝加载。

## 15 天交付节奏

| 更新 | 本库交付 |
| --- | --- |
| 2026-11-03 | 六种变换、方向映射、双格／伙伴关系代表例和版本 manifest；支持首期人工验收 |
| 2026-11-18 | 首版反馈、容器／床／告示牌、含水／含雪状态和来源检查 |
| 2026-12-03 | NBT schema、头颅／活塞／雕像／营火物品所需状态输入及特殊状态 |
| 2026-12-18 | 复杂组合、版本差异、旧格式映射和连接状态补齐 |
| 2027-01-02 | 兼容别名清理、缺失来源补齐和下一版本升级准备 |

每期只交付实际通过的状态子集。自动往返通过不能代替编辑器、完整投影和缺失投影的产品验收。

## 开发窗口、预算和重构

只在周日晚至周四晚 23:30—次日08:00 工作，每周最多五个窗口。三库共享每 15 天约 40 小时的有效容量；本库初始约占功能实现的一部分，默认每期功能实现约 8 小时，具体按状态阻塞调整。每期约 6 小时的重构预算包含状态 API、来源 manifest、版本检查和重复映射清理；不另加总工期。

预算使用主仓库计划中的统一规则：10 月一次性 ¥300 只作首期／阻塞缓冲；以后每月 ¥600 先支付续订费，余额按 ¥1＝1 额度用于按量请求；月度使用达到 80% 时停止非阻塞探索。每个窗口记录实际额度、用例和提交，不能把三个仓库的时间重复计入。

详细跨库迁移门槛见主仓库 `better-building-editor/docs/REPOSITORY_SPLIT_AND_MIGRATION.md`（本地工作区的相邻仓库路径）以及本库的 `docs/DEVELOPMENT_PLAN.md`。
