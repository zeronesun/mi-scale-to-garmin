# 图标文件说明

## 当前状态

`app_icon.ico` 已就位（2026-09-27 由源图 `小米体脂秤数据同步工具图标设计.png` 1536×1536 生成，源图在项目文档库维护，不进代码库）。

两处生效点（均已自动接入，无需改代码）：
- **exe 文件图标**：`packaging/build.py` 检测到本目录存在 `app_icon.ico` 时自动加 `--icon=` 参数
- **窗口图标**（标题栏/任务栏）：`main_window.py` 的 `_set_window_icon()` 自动加载（开发版/打包版路径自适应，文件缺失时静默跳过）

## 生成源图（AI 绘图提示词）

当前 `app_icon.ico` 的源图由 AI 生成（2026-09-27）。重新生成/换风格时可用以下提示词：

```bash
设计一个 Windows 桌面应用图标（.ico，256×256 主尺寸，含 16/32/48/64/128/256 多尺寸），
应用功能：把小米体脂秤的体重/身体成分数据自动同步到佳明 Garmin Connect。

设计要求：
- 风格：现代扁平化 + 轻微渐变，圆角方形底（superellipse/squircle），适合 Windows 任务栏小尺寸显示
- 主视觉：一个简洁的体重秤轮廓（圆形表盘 + 指针或数字屏），叠加一个向上的同步箭头（或循环箭头），表达"数据上传/同步"
- 配色：主色用佳明绿（#007E3A 或 #4CAF50 系）+ 小米橙（#FF6900 系）点缀，背景浅色或白底，保证 16px 下依然清晰可辨
- 细节：16×16 尺寸下不出现细线条和文字，主体占画面 80% 以上，边缘留 5% 安全边距
- 不要：文字、logo 商标（避免小米/佳明官方 logo）、复杂阴影、写实风格
- 输出：透明背景 PNG（256×256 以上）

# mi‑scale‑to‑garmin 最终图标完整Prompt
> 风格参考你最后那张时钟样例：**轻柔和缓的2.5D微浮雕、无厚重阴影、squircle超圆角Windows应用图标，人站在圆环底部，连续无分割的环形轨道，橙→绿同步流向，三色粗段代表身体成分**

Windows desktop app icon, 256x256, vector style, soft subtle 2.5D slight emboss, NO heavy drop shadow.
Squircle super‑rounded square frame, thin soft mint‑green outer border, clean pure‑white inner background, transparent outer canvas.
Thick continuous unbroken circular ring gauge, no dividing gaps between segments.
Ring segments: bottom‑origin segment is Xiaomi orange #FF6900 (data source), next thick segment is soft cyan, the rest whole continuous ring is solid Garmin green #007E3A, three large thick color segments only, no tiny fragments.
A solid flat‑orange minimalist human stick‑figure: round head + thick torso + simple legs, feet stand firmly on the orange bottom segment of ring, figure is inside ring.
Open cyclic sync arrow integrated into the top of ring, color flows directionally: starts from Xiaomi‑orange source, smoothly transitions into Garmin‑green, visual meaning "Mi scale human‑body data sync to Garmin Connect".
No text, no logos, no fine ticks.
Graphic elements take up 80% canvas, keep safe margin for 16px windows taskbar scaling, sharp clean edges.

## 关键设计点（已全部落实你的需求）
1. ✅ 圆环**完全连续，无分段缝隙**，3个大粗色块，没有细碎小切片
2. ✅ 小人双脚**站在底部小米橙源段**，代表人体原始测量数据来自小米体脂秤
3. ✅ 同步箭头流向：**小米橙起点 → 佳明绿终点**，数据流语义：小米秤 → 同步 → Garmin
4. ✅ 三色粗段语义：小米橙（原始人体数据）、浅青（身体成分A）、佳明绿（同步目标Garmin）
5. ✅ 视觉风格对齐你认可的时钟样图：轻薄微浮雕，不厚重，Windows工具图标质感，适配任务栏小尺寸
6. ✅ 输出256×256 PNG，之后打包ICO尺寸：`16,32,48,64,128,256`
---
### 生成后导出ico的操作提示
1. 使用生成出来的256×256png原图，不要做二次压缩
2. 用ConvertICO/GIMP导入，勾选全套Windows图标尺寸
3. 16px预览校验：保证橙/青/绿三大色块可分辨，人形轮廓可识别，不会糊成一团
```

生成后源图存项目文档库（与代码库分离维护，不进本仓库）。

## 换图标流程

1. 准备一张正方形 PNG（建议 ≥512×512，透明背景；可用上方提示词让 AI 生成）
2. 项目根目录执行转换（源图任意尺寸，脚本自动缩放到 16/32/48/64/128/256 六档）：
   ```
   .venv\Scripts\python.exe packaging\make_icon.py <源png路径>
   ```
3. 重新打包：`.venv\Scripts\python.exe packaging\build.py gui`
4. 运行 exe 验证（窗口图标由 `_set_window_icon()` 自动加载，无需额外操作）

### make_icon.py 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `src`（第一个位置参数） | ✅ | 源 PNG 图片路径 |
| `-o` / `--out` | ❌ | 输出 ICO 路径，默认 `src/gui/resources/icons/app_icon.ico` |

```
# 指定输出位置
.venv\Scripts\python.exe packaging\make_icon.py 新图标.png -o 输出.ico

# 查看帮助
.venv\Scripts\python.exe packaging\make_icon.py -h
```

注意事项：
- 必须在**项目根目录**执行（默认输出路径是相对路径）
- 依赖 **Pillow**（已在 requirements/build.txt）
- 源图非正方形会被拉变形，建议用正方形
- 输出文件名建议固定 `app_icon.ico`——`packaging/build.py` 和 `_set_window_icon()` 都认这个路径，换名字要同步改两处

## ICO 多尺寸结构

`app_icon.ico` 是单文件容器，内含 6 个尺寸的图像数据（非 6 个独立文件）：

```
app_icon.ico (~91 KB)
├── 文件头 (6 B)      ← 声明内含 6 张图
├── 目录表 (96 B)     ← 每张图的尺寸/大小/偏移
├── 16×16   (673 B)   ← 标题栏小图标
├── 32×32   (1.8 KB)  ← 任务栏
├── 48×48   (3.2 KB)  ← 资源管理器大图标
├── 64×64   (5.3 KB)
├── 128×128 (18.6 KB) ← 资源管理器超大图标
└── 256×256 (62 KB)   ← 桌面图标（PNG 压缩存储）
```

Windows 按显示场景从目录表直接取对应尺寸的原生图，不做实时缩放，任何大小下都清晰。
