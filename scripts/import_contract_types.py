import argparse
import os
import sys
from pathlib import Path
from typing import Iterable


CONTRACT_TYPE_NAMES = (
    '公共-房屋租赁',
    '公共-房屋维修',
    '公共-车辆租赁',
    '公共-车位租赁',
    '公共-互联网接入',
    '公共-保洁服务',
    '公共-其他购置',
    '福利-商业保险',
    '福利-员工体检',
    '福利-工作午餐',
    '福利-其他购置',
    '人资-人事服务',
    '人资-招聘服务',
    '人资-培训服务',
    '人资-外包服务',
    '人资-其他购置',
    '专项-法务服务',
    '专项-资质服务',
    '专项-其他购置',
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def discover_netbox_root() -> str | None:
    candidates = []

    # Prefer the current working directory when running from a NetBox checkout.
    candidates.append(Path.cwd())

    env_netbox_root = os.environ.get('NETBOX_ROOT')
    if env_netbox_root:
        candidates.append(Path(env_netbox_root))

    # Common Linux installation paths.
    candidates.append(Path('/opt/netbox/netbox'))
    candidates.append(Path('/srv/netbox/netbox'))
    candidates.append(Path('/usr/local/netbox/netbox'))

    # Common layout for local development: sibling "netbox/netbox" directory.
    candidates.append(PROJECT_ROOT.parent / 'netbox' / 'netbox')
    candidates.append(PROJECT_ROOT.parent / 'netbox-app' / 'netbox')

    for candidate in candidates:
        if (candidate / 'manage.py').exists() or (candidate / 'netbox').exists():
            return str(candidate)

    return None


def configure_netbox_settings(netbox_root: str | None) -> None:
    if os.environ.get('NETBOX_CONFIGURATION'):
        return

    candidates: list[tuple[Path, str, Path | None]] = []
    if netbox_root:
        root_path = Path(netbox_root)
        candidates.extend(
            [
                (root_path / 'netbox' / 'configuration.py', 'netbox.configuration', None),
                (root_path / 'configuration.py', 'configuration', root_path),
            ]
        )

    candidates.extend(
        [
            (Path('/etc/netbox/configuration.py'), 'configuration', Path('/etc/netbox')),
            (Path('/opt/netbox/configuration.py'), 'configuration', Path('/opt/netbox')),
        ]
    )

    for config_file, module_name, extra_path in candidates:
        if config_file.exists():
            if extra_path:
                sys.path.insert(0, str(extra_path))
            os.environ.setdefault('NETBOX_CONFIGURATION', module_name)
            return


def setup_django() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))

    netbox_root = discover_netbox_root()
    if netbox_root:
        sys.path.insert(0, netbox_root)

    configure_netbox_settings(netbox_root)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')

    import django

    django.setup()


def ensure_contract_types(
    names: Iterable[str] = CONTRACT_TYPE_NAMES,
    *,
    commit: bool = False,
    color: str = '9e9e9e',
) -> dict[str, list[str]]:
    from netbox_contract.models import ContractType

    created_names: list[str] = []
    existing_names: list[str] = []

    for name in names:
        contract_type = ContractType.objects.filter(name=name).first()
        if contract_type:
            existing_names.append(name)
            continue

        if commit:
            ContractType.objects.create(name=name, color=color)
        created_names.append(name)

    return {
        'created': created_names,
        'existing': existing_names,
    }


def print_summary(result: dict[str, list[str]], *, commit: bool) -> None:
    mode = '已写入数据库' if commit else '演练模式（未写入数据库）'
    print(f'合同分类导入完成，当前为{mode}。')
    print(f'新增分类数量: {len(result["created"])}')
    for name in result['created']:
        print(f'  + {name}')

    print(f'已存在分类数量: {len(result["existing"])}')
    for name in result['existing']:
        print(f'  = {name}')

    if not commit:
        print('如需正式写入，请追加 --commit 参数后重新执行。')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='批量导入合同分类（ContractType）。')
    parser.add_argument(
        '--commit',
        action='store_true',
        help='正式写入数据库；默认仅演练，不保存。',
    )
    parser.add_argument(
        '--color',
        default='9e9e9e',
        help='新建合同分类的颜色值，默认为灰色 9e9e9e。',
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        setup_django()
    except Exception as exc:
        print(
            'Django 环境初始化失败。请在 NetBox Python 环境中运行，'
            '并按需设置 NETBOX_ROOT 指向 NetBox 源码目录（含 manage.py 的目录）。',
            file=sys.stderr,
        )
        discovered_root = discover_netbox_root()
        if discovered_root:
            print(f'已探测到候选 NETBOX_ROOT: {discovered_root}', file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    result = ensure_contract_types(commit=args.commit, color=args.color)
    print_summary(result, commit=args.commit)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
