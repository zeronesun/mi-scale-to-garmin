"""
将 PNG 转为多尺寸 ICO（16/32/48/64/128/256）

用法（项目根目录）:
    .venv\\Scripts\\python.exe scripts\\make_icon.py <源png路径> [-o 输出ico路径]

默认输出: src/gui/resources/icons/app_icon.ico
依赖: Pillow（构建工具链，见 requirements-build.txt）
"""
import argparse
import sys
from pathlib import Path

from PIL import Image

# 标准 Windows 图标尺寸（256 在 ICO 内以 PNG 压缩存储，其余为 BMP）
ICON_SIZES = [16, 32, 48, 64, 128, 256]


def make_icon(src: Path, out: Path) -> None:
    """读取源图，缩放为多尺寸并写入 ICO"""
    im = Image.open(src).convert("RGBA")
    print(f"源图: {im.size[0]}x{im.size[1]}")

    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, format="ICO", sizes=[(s, s) for s in ICON_SIZES])

    size_kb = out.stat().st_size / 1024
    print(f"已生成: {out}（{size_kb:.1f} KB，尺寸 {ICON_SIZES}）")


def main() -> int:
    parser = argparse.ArgumentParser(description="PNG 转多尺寸 ICO")
    parser.add_argument("src", type=Path, help="源 PNG 图片路径")
    parser.add_argument(
        "-o", "--out",
        type=Path,
        default=Path("src/gui/resources/icons/app_icon.ico"),
        help="输出 ICO 路径（默认 src/gui/resources/icons/app_icon.ico）",
    )
    args = parser.parse_args()

    if not args.src.exists():
        print(f"[ERR] 源文件不存在: {args.src}", file=sys.stderr)
        return 1

    make_icon(args.src, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
