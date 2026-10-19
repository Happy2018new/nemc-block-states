# 首个纯状态快照来源与迁移边界

更新：2026-10-19。当前阶段是独立快照，尚未切换主仓库调用路径，也没有关闭新的游戏外观问题。

## 唯一修改来源

本轮来源为相邻 `better-building-editor` 仓库中的 `behavior_pack/modern_projection/projection/`。确切来源提交、工作区变更、每个文件 SHA-256、生成器 SHA-256 及证据数据 SHA-256 都由 `tools/sync_from_bbe.py` 写入根目录的 `snapshot_manifest.json`。文件哈希优先于提交标题；有工作区变更时不能只凭提交号声称可重现。

迁移期间只在来源仓库修改五个整模块及伙伴规则的来源；本库通过同步工具重建。没有移动、删除来源文件，也没有复制 8.5 MB 原始方块表、8.8 MB 含水证据或纹理资源。原始来源只保存仓库内相对路径与哈希。`LICENSE` 逐字保留来源仓库的既有许可，未额外授权公开复用。

## 源文件分工

| 现有来源 | 归属 | 本轮处理 | 调用方处理 |
| --- | --- | --- | --- |
| `block_registry.py`、`block_registry_data.py` | state／generated | 字节相同的纯模块快照；保留 typed states、aux、旧别名、默认目录及懒加载缓存 | 原 host imports 全部保留；本库没有反向依赖 host |
| `state_transform.py` | state | 字节相同快照；六种操作、未知属性拒绝、不可表示方向异常 | `cell.py` 与 `nbt_spatial.py` 仍调用 host 版本；本轮不切换 |
| `block_traits.py`、`block_traits_data.py` | state／generated | 固体、含水和精确含雪观测资格原样快照；来源校验不放宽 | `cell`、`block_neighbors`、`geometry_palette`、液体／图层／预览引用全部保留 |
| `block_groups.py` | state + host | 第二小批次抽取 3 常量与 5 函数，提供纯部件伙伴规则；source 与 output 哈希分别保存，新增未审查依赖即拒绝生成 | `model`、`block_edits`、`jobs`、world capture、服务端及调试蓝图均不改；世界／Cell／双箱事务仍留 host |
| `nbt_spatial.py` | state schema + host／renderer 适配 | 暂留 host；root tag 访问、typed clone、位置、pair 坐标、展示框／头颅／床／陶片规则需要分开抽取 | `Cell`、`visible_actor`、`native_appearance` 与渲染使用者仍共同依赖原模块 |
| `cell.py`、`model.py`、`block_edits.py` | host | 文档不可变对象、选区、原子事务、历史保留 host | 不以拆状态库为由迁整个编辑器数据模型 |
| `block_neighbors.py` | renderer + host | 邻域观察与连接几何继续留现有路径；若抽状态规则要单独界定输入 | 不让本库读取世界或依赖 renderer |

`minecraft_py arch` 与以上五类来源的 `imports` 均在抽取前完成。独立库不包含客户端／服务端初始化、ModSDK、UI、事件监听或世界写入。

## 生成器与证据

| 内容 | 来源生成器或输入 | 本轮保存方式 |
| --- | --- | --- |
| 注册表 | `tools/generate_block_registry.py`，`tools/data/legacy_block_aliases.json`，`tools/data/block_registry_manifest.json`，归档 3.9 方块表 | 生成结果与源 SHA-256；不复制原始大表 |
| 固体资格 | `tools/generate_block_traits.py`，`native_block_metadata_nemc_3.9.0.401155.json` | 生成结果与输入哈希 |
| 含雪资格 | 同一 traits 生成器；`native_snow_overlays`、`native_snow_states`、`native_paired_snow` 的 3.9 版本输入 | 逐输入哈希；精确观测仍区分 supported／unsupported／unknown |
| 含水资格 | 同一 traits 生成器；`native_water_overlays_nemc_3.9.0.401155.json` | 生成结果与输入哈希；不由缺失证据推导否定 |
| 用户 3.10 原版等价 | `docs/reference/block_palettes/audit_nemc_3.9_to_3.10_20261017.json`、差异报告与压缩原始 dump | 源路径、文件哈希、原版规范哈希、有限比较结论；不重贴版本标签 |

3.9 全表有 1,340 名称／15,858 状态，其中 19 名称／19 状态是 host 预览代理。它们被保留是为了与来源精确对等，不代表本库要拥有 renderer 代理注册。后续独立原版数据集切换须迁移目录／别名和 manifest 后另验，不能暗删 19 项制造“纯原版”对等。

3.10 实际开发引擎可为 `3.10.0.420447`；用户 dump 本身只由用户标识为 3.10，未内嵌补丁号。该 dump 原版所有字段与 3.9 一致是状态输入复用证据；19 个旧代理底层 ID 变化和 709 个新增代理不属于新的原版方块。manifest 保留源表 3.9 的版本和全文件 SHA，`vanilla_palette_equivalence` 明确不能扩展 traits 或渲染资格。

## 当前验证和接入门槛

Python 3.13 的 11 项运行时＋5 项生成器检查通过；真实 Python 2.7 的 11 项运行时通过，5 项 Python 3 工具测试显式跳过。离线全表检查有 15,858 条 typed states、95,148 次变换、对应逆操作、503 条别名、63,432 次 traits 查询、47,574 次伙伴查询；722 条成组状态还检查互反及随六操作变换的位移一致。对等报告保存在 `docs/verification/2026-10-19-host-parity.json`。

MCDK `review` 对纯包目录直接审查，实际解析 9 个文件；不能把带 scope 时的零文件输出当作通过。现有 `state_transform._property` 长函数告警来自字节相同源代码，本次不在快照内单独重构语义。MCDK 的 `imports` 对无行为包入口的独立库暂未能解析；来源行为包的依赖扫描和独立包实际导入测试共同检查当前边界，不把“未解析”写成无依赖。

主程序下一步接入需单独添加适配器，锁定本库提交／快照、来源表 SHA 与使用范围，保留旧路径回退。双箱、门／床伙伴原子操作、NBT、保存／分享／撤销及 editor／full／missing 三类路径仍要在产品侧验证。完成这些之前，本快照不计作镜像／旋转人工验收关闭，也不删除旧实现。
