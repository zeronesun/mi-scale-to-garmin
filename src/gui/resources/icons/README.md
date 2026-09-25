# 图标文件说明

## 当前状态

暂时没有实际的图标文件。打包时如果没有图标，PyInstaller 会使用默认图标。

## 添加自定义图标

### 准备图标文件

1. **Windows** - `.ico` 格式
   - 推荐尺寸: 256x256
   - 在线转换工具: https://convertico.com/

2. **macOS** - `.icns` 格式
   - 推荐尺寸: 1024x1024
   - 制作工具: iconutil (macOS 自带)

3. **Linux** - `.png` 格式
   - 推荐尺寸: 256x256

### 放置位置

将图标文件放在当前目录：
- `app_icon.ico` (Windows)
- `app_icon.icns` (macOS)
- `app_icon.png` (Linux)

### 更新打包脚本

修改 `build.py` 中的图标路径：
```python
'--icon=src/gui/resources/icons/app_icon.ico',
```

## 临时方案

如果没有图标，可以：
1. 使用默认图标（无图标）
2. 下载开源图标
3. 使用在线工具制作简单图标

推荐图标资源：
- https://www.flaticon.com/
- https://iconfinder.com/
- https://www.iconarchive.com/
