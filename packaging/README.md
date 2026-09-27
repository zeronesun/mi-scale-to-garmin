# packaging/ — 打包链

本目录集中存放 PyInstaller 打包相关的全部**定义**（构建脚本、runtime hook、图标工具）。构建产物与中间垃圾不在此目录：

- 最终产物 → `dist/<dev|release>/<platform>/`（gitignore）
- 中间产物（workpath + spec）→ `.pyinstaller/`（gitignore，可再生，随时可删）

## 文件

| 文件 | 用途 |
|------|------|
| `build.py` | **唯一构建入口**。本地与 CI 共用，PyInstaller 参数单一来源（CI 不再复制参数） |
| `pyi_rth_inspect.py` | PyInstaller runtime hook：打包后在用户代码前执行，patch `inspect.getsource*`（打包环境无源码文件）+ 禁用 logfire 的 pydantic 集成。GUI 和 CLI 构建都使用（与 PyQt6 无关，原名 `pyi_rth_pyqt6.py` 有误导，2026-09-27 改名） |
| `make_icon.py` | PNG 转多尺寸 ICO（16~256），生成 `src/gui/resources/icons/app_icon.ico` 供 `--icon` 使用 |

## 构建命令

```bash
pip install -r requirements/build.txt   # PyInstaller 等（GUI 另需 requirements/gui.txt）

python packaging/build.py gui           # GUI（onedir 文件夹）
python packaging/build.py cli           # CLI（onefile 单文件）
python packaging/build.py all           # 全部
python packaging/build.py all --release # 输出到 dist/release/（默认 dist/dev/）
```

- 从任何工作目录调用均可：`build.py` 启动时 `os.chdir` 到项目根，hook 用绝对路径引用
- 平台自动检测（PyInstaller 不支持交叉编译——Linux/macOS 产物需在对应系统上构建）
- 图标：`src/gui/resources/icons/app_icon.ico` 存在时 GUI 构建自动加 `--icon`

## 产物目录

```
dist/
├── dev/                    # 开发验证产物（默认）
│   ├── windows/  mi-scale-to-garmin-gui/（文件夹）+ mi-scale-to-garmin-cli.exe
│   └── linux/    mi-scale-to-garmin-cli（ELF，需 glibc，Alpine 不兼容）
└── release/                # 发布候选（--release）
    └── <platform>/...      # 结构同上
```

## 与 CI 的关系

`.github/workflows/build-release.yml`（tag `v*.*.*` 触发）直接调用 `python packaging/build.py gui`，与本地构建行为完全一致。产物从 `dist/dev/<platform>/` 取，打成 zip/dmg 上传 Release。

## 历史

- 2026-09-27：目录结构重构——`build.py`、`pyi_rth_pyqt6.py`（改名 `pyi_rth_inspect.py`）、`scripts/make_icon.py` 收拢入本目录；PyInstaller workpath/spec 从根目录 `build/` 迁至 `.pyinstaller/`；CI 硬编码参数段删除，改调 `build.py`
