---
name: figwright
description: Analyze a local scientific table (CSV/TXT/XLS/XLSX) and turn it into a publication-informed, watermark-free figure with AI-driven chart selection; output editable SVG plus high-resolution PNG and PDF, fully local, with no Origin required. Use when a user drops in data and asks to draw/plot/chart it in natural language, or asks for NMR, XRD, XPS, FTIR, UV-Vis, DSC, EIS, LSV, CV, PL, bar, scatter, line, histogram, box/violin/raincloud, pie, heatmap, sankey, radar, forest, bubble, ROC/calibration/decision curves, SHAP, 3D trajectory, and similar scientific or statistical charts. Do not use on macOS/Linux. By default never install/launch Origin and produce no .opju (pure matplotlib, watermark-free); use the optional experimental `origin` backend ONLY when the user explicitly needs an editable .opju AND affirms a locally installed, activated licensed Origin/OriginPro 2021+ — it is gated by `figwright origin-smoke` (Learning/Trial = degraded = refused), and never removes any watermark.
---

# Figwright

把一张只读的数据表，用一句自然语言变成一张出版级、**无水印、可二次编辑**的科研图。
Figwright 在本地运行，用自带的 matplotlib 引擎出图，**不需要、也不会启动 Origin**，因此不产生任何
demo 水印；矢量产物是 SVG（可用 Inkscape/Illustrator 编辑文字与配色），同时给 300 dpi PNG 与 PDF。

## 调用方式

- 一律使用**本 Skill 目录下的 `figwright.cmd`**（安装时已写入本机绝对路径），用绝对路径调用，
  不要让用户自己选 Python。
- 若启动器提示“尚未安装”，读取同目录 `figwright-home.json` 里的 `product_home`，请用户双击该目录下的
  `setup.cmd` 完成一次性安装（仅安装时联网下载开源依赖），装好后再继续。
- 所有命令输出 JSON 到 stdout，便于读取；面向用户时只讲结论，不要直接倾倒原始 JSON。

## 标准流程（新手路径）

1. `figwright.cmd doctor`：确认引擎、依赖、模板就绪（`ready=true`、`origin_required=false`、
   `watermark=false`）。新机器或换 Python 后先跑一次。
2. 用户给文件并表达目的后，运行
   `figwright.cmd recommend "<数据文件>" --intent "<用户的自然语言目的>"`。
   系统会真实试拟合每个图种并排序，返回 `recommendations`、`auto_selected` 与命中词。
3. 用大白话只反馈：识别到的数据形状、最推荐的 1–3 个图种及理由、还需用户拍板的一个小问题。
   - `gate.needs_user_confirm=false` 且 `auto_selection_margin` 领先明显（首选与次选拉开差距）：
     可直接推荐首选并请用户确认。
   - 出现以下任一情况，**不要直接自动出图**，只追问必要的那一两个问题：
     `gate.needs_user_confirm=true`、`auto_selection_ambiguous=true`（意图没命中且候选同分，
     常见于无表头/结构很差、兜底图种想接管时）、候选分接近、`requires_confirmation=true`、
     或列角色/单位有歧义。不要猜测未知数值列的含义。
4. 用户确认后出图：
   `figwright.cmd draw "<数据文件>" --intent "<目的>"`（自动选图）
   或 `figwright.cmd draw "<数据文件>" --template <id>`（用户指定图种）。
   需要在列映射不确定时强制停下来确认，加 `--strict`（此时退出码为 3、`status=needs_confirmation`，
   按返回的 `assignments/reasons` 与用户核对后再画）。
5. 默认在**源文件旁边**生成 `<文件名>_Figwright_<时间戳>` 文件夹，内含
   `result.png`、`result.svg`、`result.pdf`、源数据副本与 `figwright_report.json`。
   普通情况不要改输出目录；用户明确要求别处时才用 `--output-dir`。
6. 打开 `result.png` 做人工视觉检查：坐标轴方向、单位、图例是否齐全无裁切、中文是否正常。
   告诉用户 SVG 可编辑、PNG/PDF 可直接用于论文/汇报；如实说明这是 publication-informed，
   不宣称“Nature 同款/期刊保证录用”。

想浏览全部图种时用 `figwright.cmd catalog`（可 `--family <族>` 过滤）。

## 可选：Origin 工程后端（仅当用户明确要 `.opju`）

默认永远走上面的 matplotlib 路径（无水印）。**只有**当用户明确说“我必须要能在 Origin 里打开的
`.opju` 工程文件”，并确认本机已安装并激活**正版 Origin/OriginPro 2021+** 时，才考虑可选后端；
不要主动推荐，也不要为“去水印”使用它。

1. 若 `doctor` 的 `origin_backend.environment.installed` 不为 true，提示用户运行一次
   `setup.cmd install-origin`（独立环境，仅安装时联网）。
2. 先跑 `figwright.cmd origin-smoke`，把 JSON 的 `status` 作为唯一依据：
   - `passed`（能真正存出非空 `result.opju`）→ 正版环境，可继续；
   - `degraded`（学习/试用、工程保存受限）→ **停止**，明确告知无法产出正式 `.opju`、Figwright
     不去水印；引导用户改用默认 matplotlib 出无水印图。不要尝试任何绕过。
3. 仅在 `passed` 后出工程（必须带正版声明标志）：
   `figwright.cmd draw "<文件>" --template <id> --backend origin --confirm-licensed-origin`。
   退出码 `5`=未声明正版、`6`=自检 degraded 已拦截、`4`=Origin 技术错误。
4. 该后端为 **experimental**：如实告知用户，不要把学习版导出的带水印 PNG 当成果。

## 科学与数据边界

- 源文件只读：绝不改写、补全缺失列或编造数据。
- Figwright 只做“展示”，不擅自做平滑、拟合、归一化、去噪、峰指认、统计检验或剔除离群点；
  这些只有用户明确要求且该图种支持时才进行。
- 自动选图是**建议**不是定论：以用户的科学问题和数据结构为准；能画但会误导的图要明确拒绝并说明。
- NMR/XRD/XPS 等专业谱图遵循各自坐标惯例（如 NMR 化学位移由大到小、XPS 结合能由高到低）。

## 权限与范围

- 读取：用户指定的数据表。
- 写入：源文件旁的产物目录，以及 Figwright 产品目录。
- 网络：仅一次性 `setup.cmd` 安装依赖时使用；出图全程离线、不上传数据。
- 仅支持 64 位 Windows + Python 3.11/3.12；不支持 macOS/Linux/虚拟机出图链路。
- 默认后端不安装、不修改、不绕过任何 Origin/OriginPro 授权；无水印来自 matplotlib 原生渲染，而非去除水印。
- 可选 Origin 后端只在用户明确要 `.opju`、声明确有正版、且 `origin-smoke` 为 `passed` 时使用；
  学习/试用（degraded）一律拒绝，绝不去除 demo 水印或破解授权。
