"""
调试脚本：对比旧 API (get_model_weights) 和新 API (get_fitness_data_by_time) 的原始返回
用法：.venv/Scripts/python.exe debug/debug_raw_data.py --config users.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

from xiaomi.client import XiaomiClient
from xiaomi.config import ConfigManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="users.json")
    args = parser.parse_args()

    config_mgr = ConfigManager(args.config)
    users = config_mgr.get_users()

    for user in users:
        username = user.get("username")
        token = user.get("token")
        model = user.get("model", "yunmai.scales.ms103")

        if not username or not token or not token.get("userId"):
            print(f"跳过 {username}: 无有效 token")
            continue

        client = XiaomiClient(username=username)
        client.set_credentials(
            user_id=token["userId"],
            ssecurity_encoded=token.get("ssecurity"),
            pass_token=token["passToken"],
        )
        client.login_from_token()

        # ===== 1. 旧 API：get_model_weights（内部已打印 RAW SCALE DATA）=====
        print("\n" + "=" * 80)
        print(f"【旧 API】get_model_weights(model={model})")
        print("=" * 80)
        weights_old = client.get_model_weights(model)
        print(f"旧 API 解析出 {len(weights_old)} 条")
        if weights_old:
            print("旧 API 解析后的字段:", sorted(weights_old[0].keys()))

        # ===== 2. 新 API：get_fitness_data_by_time（打印原始返回）=====
        print("\n" + "=" * 80)
        print("【新 API】get_fitness_data_by_time(key='weight')")
        print("=" * 80)
        fitness_data = client.get_fitness_data_by_time(key="weight")
        print(f"新 API 原始返回 {len(fitness_data)} 条")
        if fitness_data:
            print("=== RAW FITNESS DATA ===")
            print(json.dumps(fitness_data, indent=2, ensure_ascii=False))
            print("========================")
            # 打印第一条的 value 内部字段
            first = fitness_data[0]
            print("\n第一条的顶层字段:", sorted(first.keys()))
            try:
                value_data = json.loads(first.get("value", "{}"))
                print("第一条 value 内部字段:", sorted(value_data.keys()))
            except Exception as e:
                print(f"value 解析失败: {e}")


if __name__ == "__main__":
    main()