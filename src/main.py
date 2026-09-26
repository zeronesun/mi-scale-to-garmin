
from garmin.client import GarminClient
from garmin.fit_generator import create_weight_fit_file
from xiaomi.client import XiaomiClient, fetch_merged_weights
from xiaomi.config import ConfigManager
from utils.paths import get_app_data_dir, get_default_config_path
import argparse
import sys
import logging
import json
import datetime
from pathlib import Path
import time

# Add src to path
sys.path.append(str(Path(__file__).parent))


# Configure logging - force reconfiguration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

# users.json 默认模板（无密：无 password/token 字段，空字段由引导式初始化补齐）
# prefix 带默认值（xiaomi/garmin），恢复后不再询问前缀，只问账号/邮箱
DEFAULT_TEMPLATE = {
    "users": [
        {
            "xiaomi_prefix": "xiaomi",
            "username": "",
            "model": "yunmai.scales.ms103",
            "garmin_prefix": "garmin",
            "garmin": {
                "email": "",
                "domain": "CN"
            }
        }
    ]
}


def display_weight_data(weights, limit=10):
    """Display weight data in a formatted way"""
    if not weights:
        print("No weight data found.")
        return

    print(f"\n{'='*80}")
    print(f"[INFO] Weight Data Summary - Total Records: {len(weights)}")
    print(f"{'='*80}\n")

    # Show latest records
    display_count = min(limit, len(weights))
    print(f"Showing latest {display_count} records:\n")

    for i, w in enumerate(weights[:display_count], 1):
        print(f"Record #{i} - {w.get('Date', 'N/A')}")
        print(f"  Weight: {w.get('Weight', 'N/A')} kg")
        print(f"  BMI: {w.get('BMI', 'N/A')}")

        if w.get('BodyFat'):
            print(f"  Body Fat: {w.get('BodyFat')}%")
        if w.get('BodyWater'):
            print(f"  Body Water: {w.get('BodyWater')}%")
        if w.get('MuscleMass'):
            print(f"  Muscle Mass: {w.get('MuscleMass')} kg")
        if w.get('BoneMass'):
            print(f"  Bone Mass: {w.get('BoneMass')} kg")
        if w.get('VisceralFat'):
            print(f"  Visceral Fat: {w.get('VisceralFat')}")
        if w.get('BasalMetabolism'):
            print(f"  Basal Metabolism: {w.get('BasalMetabolism')} kcal")
        if w.get('MetabolicAge'):
            print(f"  Metabolic Age: {w.get('MetabolicAge')} years")
        if w.get('BodyScore'):
            print(f"  Body Score: {w.get('BodyScore')}")
        if w.get('HeartRate'):
            print(f"  Heart Rate: {w.get('HeartRate')} bpm")

        print()

    # Statistics
    if len(weights) > 0:
        weights_values = [float(w.get('Weight'))
                          for w in weights if w.get('Weight')]
        if weights_values:
            print(f"{'='*80}")
            print(f"[INFO] Statistics")
            print(f"{'='*80}")
            print(f"  Latest Weight: {weights_values[0]} kg")
            print(
                f"  Average Weight: {sum(weights_values) / len(weights_values):.2f} kg")
            print(f"  Min Weight: {min(weights_values)} kg")
            print(f"  Max Weight: {max(weights_values)} kg")
            print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(description="Xiaomi Scale Sync to Garmin")
    parser.add_argument("--config", default=str(get_default_config_path()),
                        help="Path to users.json config file")
    parser.add_argument("--limit", type=int, default=10,
                        help="Number of records to display")
    parser.add_argument("--fit", action="store_true",
                        help="Generate FIT files for Garmin")
    parser.add_argument("--sync", action="store_true",
                        help="Upload weight data to Garmin Connect")
    parser.add_argument("--output-dir", default=str(get_app_data_dir() / 'garmin-fit'),
                        help="Directory for generated FIT files")
    parser.add_argument("--non-interactive", action="store_true",
                        help="非交互模式：需要输入时直接报错退出（计划任务/CI 用）")
    args = parser.parse_args()

    # If --sync is requested, we must also have --fit
    if args.sync:
        args.fit = True

    # 非交互保护：--non-interactive 或 stdin 非 TTY 时，需要输入直接报错退出
    from core.bootstrap import (set_interactive_override, ensure_identity,
                                prompt_password, NonInteractiveError)
    if args.non_interactive:
        set_interactive_override(False)

    config_mgr = ConfigManager(args.config)
    users = config_mgr.get_users()

    if not users:
        logger.warning(
            f"No users found in {args.config}. Please add users to the configuration file.")

        # Create a template if it doesn't exist/empty（无密模板：无 password/token 字段，
        # 空字段由启动时的引导式初始化补齐）
        if not users:
            with open(args.config, 'w') as f:
                json.dump(DEFAULT_TEMPLATE, f, indent=4)
            logger.info(f"Created template {args.config}（空字段将在下次启动时引导式补齐）")
            return

    from core.session_store import (load_xiaomi_auth, save_xiaomi_auth,
                                    migrate_token_from_users_json,
                                    SessionAccountMismatchError)
    from core.account import resolve_prefix

    for user in users:
        model = user.get("model", "yunmai.scales.ms103")
        garmin_config = user.get("garmin")

        # ② 身份字段完整性检查 + 引导式输入（只问空的，写回 users.json）
        try:
            user = ensure_identity(user, config_mgr)
        except NonInteractiveError as e:
            logger.error(str(e))
            return
        username = user["username"]

        # 脱敏标识：有前缀用前缀，无则回退到账号短哈希（B，不再用明文账号）
        xiaomi_prefix = resolve_prefix(user.get("xiaomi_prefix"), username)
        garmin_email = garmin_config.get("email") if garmin_config else ""
        garmin_prefix = resolve_prefix(user.get("garmin_prefix"), garmin_email)

        logger.info(f"Processing user: {xiaomi_prefix}")

        # 一次性迁移：旧版 users.json 内嵌 token → 独立会话文件
        migrate_token_from_users_json(config_mgr, user, xiaomi_prefix)

        # ③ 读取小米 token 会话文件（含账号哈希绑定校验 A）
        try:
            token = load_xiaomi_auth(xiaomi_prefix, xiaomi_account=username)
        except SessionAccountMismatchError as e:
            logger.error(str(e))
            token = None

        if not token:
            # token 缺失 → 终端输入密码重新认证（非交互环境报错退出）
            logger.warning(
                f"小米 token 缺失/无效（{xiaomi_prefix}），需要输入密码重新认证")
            try:
                password = prompt_password("小米密码")
            except NonInteractiveError as e:
                logger.error(str(e))
                return
            from xiaomi.login import XiaomiLogin
            login = XiaomiLogin()
            try:
                token = login.perform_login(username, password)
            finally:
                login.close()
                password = None  # 决策 4：认证后丢弃
            if not token:
                logger.error(f"小米认证失败，跳过 {xiaomi_prefix}")
                continue
            save_xiaomi_auth(xiaomi_prefix, token, xiaomi_account=username)
            logger.info(f"小米 token 已保存到会话文件（{xiaomi_prefix}）")

        client = XiaomiClient(username=username)

        if token and token.get("userId") and token.get("passToken"):
            # Set credentials from token
            client.set_credentials(
                user_id=token["userId"],
                ssecurity_encoded=token.get("ssecurity"),
                pass_token=token["passToken"]
            )

            try:
                # Validate/refresh token
                logger.info("Logging in with saved Xiaomi token...")
                new_token_data = client.login_from_token()

                # token 滚动更新 → 写回独立会话文件（不再写 users.json）
                if new_token_data:
                    save_xiaomi_auth(xiaomi_prefix, new_token_data,
                                        xiaomi_account=username)
                    logger.info("Xiaomi token refreshed and saved")

                # Fetch weights - 双源合并：旧 API 优先（实时），新 API 按时间戳补充（Zeeplife 导入数据）
                weights, legacy_count, supplement_count = fetch_merged_weights(
                    client, model)
                if weights:
                    logger.info(
                        f"Successfully retrieved {len(weights)} weight records")
                    display_weight_data(weights, limit=args.limit)

                    # Save to JSON file（统一走 get_app_data_dir：开发=项目根 data/，打包=%APPDATA%）
                    output_path = get_app_data_dir() / f"body_data_{xiaomi_prefix}.json"
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(weights, f, indent=2, ensure_ascii=False)
                    logger.info(f"Weight data saved to {output_path}")

                    # Generate FIT file if requested
                    if args.fit:
                        # Extract and validate filter configuration
                        filter_config = None
                        if garmin_config:
                            filter_config = garmin_config.get("filter")

                            # If filter is configured, validate and log
                            if filter_config and filter_config.get("enabled"):
                                try:
                                    from garmin.filter_config import FilterConfigValidator
                                    FilterConfigValidator.validate(
                                        filter_config)

                                    conditions_count = len(
                                        filter_config.get("conditions", []))
                                    logic = filter_config.get("logic", "and")
                                    logger.info(
                                        f"Weight filter enabled: {conditions_count} condition(s) "
                                        f"with '{logic.upper()}' logic"
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Invalid filter configuration: {e}")
                                    logger.warning("Proceeding without filter")
                                    filter_config = None

                        # Chunked upload logic
                        CHUNK_SIZE = 500
                        fit_output_dir = Path(args.output_dir)
                        fit_output_dir.mkdir(parents=True, exist_ok=True)
                        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

                        # Split weights into chunks
                        weight_chunks = [weights[i:i+CHUNK_SIZE]
                                        for i in range(0, len(weights), CHUNK_SIZE)]
                        total_chunks = len(weight_chunks)

                        logger.info(
                            f"体重数据共 {len(weights)} 条，将分为 {total_chunks} 个批次处理")

                        # Initialize upload results tracking
                        upload_results = {
                            'success': 0,
                            'failed': 0,
                            'duplicate': 0,
                            'failed_chunks': []
                        }

                        # Process each chunk
                        for idx, chunk in enumerate(weight_chunks, 1):
                            # Generate filename with chunk number
                            chunk_filename = fit_output_dir / \
                                f"body_{xiaomi_prefix}_{timestamp}_{idx}.fit"

                            logger.info(
                                f"处理第 {idx}/{total_chunks} 批: {len(chunk)} 条数据")

                            # Generate FIT file for this chunk
                            created_path = create_weight_fit_file(
                                chunk, chunk_filename, filter_config=filter_config
                            )

                            if created_path is None:
                                logger.warning(
                                    f"批次 {idx}/{total_chunks} 没有生成有效数据，跳过")
                                continue

                            # Sync to Garmin if requested
                            if args.sync:
                                # Initialize Garmin client on first sync
                                if 'g_client' not in locals():
                                    if garmin_config and garmin_config.get("email"):
                                        # 决策 4：密码不再从 users.json 读取；
                                        # 惰性回调：仅会话失效时才 getpass 输入（非交互环境报错）
                                        def _garmin_password_prompt():
                                            try:
                                                return prompt_password("佳明密码")
                                            except NonInteractiveError as e:
                                                logger.error(str(e))
                                                return ""

                                        g_client = GarminClient(
                                            email=garmin_config["email"],
                                            password_provider=_garmin_password_prompt,
                                            auth_domain=garmin_config.get(
                                                "domain", "CN"),
                                            session_name=garmin_prefix
                                        )

                                        if not g_client.login():
                                            logger.error(
                                                "[ERR] Garmin login failed. Synchronization aborted.")
                                            g_client = None
                                    else:
                                        logger.warning(
                                            f"[WARN] Garmin credentials missing for {xiaomi_prefix}. Skipping sync.")
                                        g_client = None

                                # Upload if client is available
                                if g_client:
                                    logger.info(
                                        f"正在上传批次 {idx}/{total_chunks} 到 Garmin Connect...")
                                    status = g_client.upload_fit(
                                        chunk_filename)

                                    if status == "SUCCESS":
                                        logger.info(
                                            f"[OK] 批次 {idx}/{total_chunks} 上传成功")
                                        upload_results['success'] += 1
                                    elif status == "DUPLICATE":
                                        logger.info(
                                            f"[INFO] 批次 {idx}/{total_chunks} 数据已存在（重复）")
                                        upload_results['duplicate'] += 1
                                    else:
                                        logger.error(
                                            f"[ERR] 批次 {idx}/{total_chunks} 上传失败: {status}")
                                        upload_results['failed'] += 1
                                        upload_results['failed_chunks'].append({
                                            'chunk': idx,
                                            'filename': str(chunk_filename),
                                            'error': status,
                                            'records': len(chunk)
                                        })

                        # Print upload summary
                        if args.sync and total_chunks > 0:
                            logger.info("=" * 80)
                            logger.info(f"[INFO] 上传汇总 - {xiaomi_prefix}")
                            logger.info(f"  总批次数: {total_chunks}")
                            logger.info(
                                f"  [OK] 成功: {upload_results['success']}")
                            logger.info(
                                f"  [INFO] 重复: {upload_results['duplicate']}")
                            logger.info(
                                f"  [ERR] 失败: {upload_results['failed']}")

                            if upload_results['failed_chunks']:
                                logger.info("\n失败的批次详情:")
                                for fail in upload_results['failed_chunks']:
                                    logger.info(
                                        f"  - 批次 {fail['chunk']}: {fail['filename']} "
                                        f"({fail['records']} 条记录) - 错误: {fail['error']}"
                                    )
                            logger.info("=" * 80)
                else:
                    logger.warning("No weight data found")

            except Exception as e:
                logger.error(f"Failed to process data for {xiaomi_prefix}: {e}")
                logger.exception("Detailed error:")
        else:
            logger.warning(
                f"No valid token for {xiaomi_prefix}. Please run the login tool to generate a token.")
            logger.info("Run: python src/xiaomi/login.py --config users.json")
        logger.info("Sleep 5 seconds")
        time.sleep( 5 )

    # 结束后询问：是否将 users.json 恢复为默认模板（用于反复测试引导式初始化）
    _offer_reset_to_default(args.config)


def _offer_reset_to_default(config_path):
    """询问是否把 users.json 恢复为默认模板；恢复前先把当前文件备份到 .trash/"""
    from core.bootstrap import is_interactive
    if not is_interactive():
        return
    try:
        answer = input("\n是否将 users.json 恢复为默认模板（清空账号/邮箱）？[y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if answer not in ("y", "yes"):
        return

    config_file = Path(config_path)
    if not config_file.exists():
        logger.warning(f"配置文件不存在: {config_path}，无需恢复")
        return

    # 备份当前文件到 .trash/（只移动不删除的纪律）
    trash_dir = config_file.parent / ".trash"
    trash_dir.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = trash_dir / f"users.json.bak-{ts}"
    config_file.replace(backup)
    logger.info(f"当前 users.json 已备份到 {backup}")

    with open(config_file, 'w') as f:
        json.dump(DEFAULT_TEMPLATE, f, indent=4)
    logger.info(f"已恢复为默认模板: {config_path}（下次启动将引导式补齐空字段）")


if __name__ == "__main__":
    main()
