# FigFlow —— 无水印 AI 科研绘图（本地·无需 Origin）

丢进一张数据表（CSV / TXT / XLS / XLSX），说一句“我想看什么”，FigFlow 自动选图并产出
**出版级、无水印、可二次编辑**的科研图。完全本地运行，用自带的 matplotlib 引擎渲染，
**不需要安装 Origin/OriginPro，也不启动它**，所以天然没有 demo 水印。

- 矢量可编辑：`result.svg`（Inkscape / Illustrator 直接改文字、配色、版式）
- 论文可用：`result.png`（300 dpi）与 `result.pdf`
- AI 自动选图：内置 40 类科学/统计图种，自然语言意图匹配 + 列自动映射（带置信度）
- 私有安全：出图全程离线，数据不上传
- 合规：Apache-2.0，开源依赖，不含任何 OriginLab 软件 / 模板 / Logo / 水印素材

---

## 一、安装（一次性）

环境要求：**64 位 Windows 10/11**，**64 位 Python 3.11 或 3.12**（安装时勾选
“Add python.exe to PATH”）。其余依赖由安装器自动放进产品自己的 `.venv`，不污染系统。

1. 拿到完整的 `FigFlow` 文件夹（保持内部结构不变）。
2. 双击 **`setup.cmd`**。它会自动：
   - 在产品目录创建独立虚拟环境 `.venv`；
   - 安装 `requirements.txt` 中锁定版本的开源依赖（仅此步联网）；
   - 运行 `doctor` 自检；
   - 若检测到豆包，自动注册“一句话调用”的本地 Skill。
3. 看到 `=== FigFlow 安装完成 ===` 即成功。

> 想重建环境：`setup.cmd --clean`；只补注册豆包 Skill：`setup.cmd install-skill`。

---

## 二、两种用法

### 用法 A：在豆包里用自然语言（推荐给普通用户）

安装完成后，直接对豆包说，例如：

- “用 FigFlow 把这个 CSV 画成图，我想对比两组的差异”
- “帮我看这张 XRD 数据的物相”
- “把这份核磁数据画成谱图”

豆包会调用 FigFlow：识别数据 → 推荐最合适的 1–3 个图种并和你确认 → 一键出图。
图保存在**数据文件旁边**的 `<文件名>_FigFlow_<时间戳>` 文件夹里。

### 用法 B：命令行直接用

在 `FigFlow` 目录下：

```bat
figflow.cmd doctor
figflow.cmd catalog
figflow.cmd recommend "D:\data\nmr.csv" --intent "对比两张19F核磁谱"
figflow.cmd draw      "D:\data\nmr.csv" --intent "对比两张19F核磁谱"
figflow.cmd draw      "D:\data\xrd.csv" --template xrd
figflow.cmd draw      "D:\data\y.csv" --strict
```

- 不指定 `--template` 时按数据 + `--intent` 自动选图。
- `--strict` 在列映射不确定时停下来等确认（退出码 3），不硬画。
- `--output-dir` 仅在你明确想换保存位置时使用；默认写到源文件旁。
- `--formats png,svg,pdf`、`--dpi 300` 可调。

---

## 三、产物

| 文件 | 说明 |
| --- | --- |
| `result.png` | 300 dpi 位图，论文/汇报直接用 |
| `result.svg` | 矢量图，文字可编辑（svg.fonttype=none） |
| `result.pdf` | 矢量 PDF |
| `<源文件名>` | 源数据副本，便于溯源 |
| `figflow_report.json` | 图种、列映射、置信度、数据哈希、画布尺寸等留痕 |

覆盖图种（40）：NMR、XRD/Rietveld、XPS、FTIR、UV-Vis、DSC、EIS、LSV、CV、PL、XAS，
柱状/条形/堆积/百分比柱、误差折线/趋势、散点/气泡、直方/箱线/小提琴/雨云、饼图、热图、
桑基、雷达、环形网络、森林、 Bland–Altman、ROC/校准/决策曲线、混淆矩阵、SHAP、3D 轨迹等。

---

## 四、目录结构

```
FigFlow/
├─ setup.cmd              一键安装入口（用户双击）
├─ figflow.cmd            命令行启动器（用产品内 .venv）
├─ requirements.txt       锁定版本的开源依赖
├─ LICENSE                Apache-2.0 许可证正本
├─ NOTICE                 版权署名 / 修改声明 / 与 OriginLab 无关联声明
├─ README.md
├─ scripts/setup.py       安装引导（建 venv、装依赖、doctor、注册 Skill）
├─ figflow/               FigFlow 应用层（env / selector / render / cli）
├─ engine/                自包含渲染引擎（源自 editaplot 的纯 Python 核心）
│  ├─ src/origin_sciplot/ 数据分析/选型/配色/matplotlib 渲染（无 Origin/GUI 模块）
│  └─ templates/          40 个图种规格（manifest/schema/示例/契约，均可直接渲染）
└─ skill/figflow/         豆包 Skill 模板（安装时复制进豆包目录）
```

---

## 五、商业化交付（To C）说明与合规边界

**去水印的正确做法**：FigFlow 的图由开源 matplotlib 直接渲染，从源头就不含任何水印；
它**不是**去破解、补丁或绕过 Origin 试用/学习版水印。任何对 Origin 授权或水印的绕过都违反
OriginLab EULA，FigFlow 不做、也不能被用于此目的。

**可以怎么分发**：

1. 分发 `FigFlow` 文件夹源码（不含 `.venv` 体积更小），用户双击 `setup.cmd` 即用；
2. 也可由你预置好 `.venv` 后整包分发（同一 Windows/位数），但仍建议让用户跑一次 `doctor`；
3. 未来若做图形化安装器，本质仍是自动执行 `setup.cmd` 的步骤，无需管理员权限。

**Apache-2.0 义务（务必随包保留）**：

- 不得删除 `LICENSE` 与 `NOTICE`；`NOTICE` 已保留上游 EditaPlot contributors 版权并写明修改点；
- 你可以商用、修改、分发，但需保留版权/许可声明，并在你修改过的文件上注明变更；
- 不得使用 EditaPlot / OriginLab 的名义为你的产品背书；
- 不得随包分发任何 OriginLab 软件、模板、Logo、试用安装包或破解文件。

**第三方依赖**：numpy / pandas / matplotlib / openpyxl / xlrd / Pillow / PyYAML / jsonschema
均为 OSI 认可的开源许可（BSD/MIT/Apache/PSF 类）。正式商业发布前，建议把各自 LICENSE
汇总进一份第三方许可清单（`pip-licenses` 可自动生成）。

---

## 六、边界与路线图

- 不产出 Origin 工程文件（`.opju`）；可编辑性由 SVG 承担。
- 当前为 MVP：自动选图覆盖 40 类图种，建议关键图仍按 `recommend → 人工确认 → draw` 流程。
- 平台：64 位 Windows + Python 3.11/3.12；macOS/Linux 暂不支持。
