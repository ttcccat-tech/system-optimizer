#!/usr/bin/env python3
"""
OpenClaw System Report Generator
自動生成系統健康和優化報告
"""

import json
import subprocess
import datetime
import os
from typing import Dict, Any, List


def run_command(cmd: list, timeout: int = 30) -> str:
    """執行命令並返回輸出"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception) as e:
        return ""


def load_json_report(filepath: str) -> Dict[str, Any]:
    """加載 JSON 報告"""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}


def get_git_status() -> Dict[str, Any]:
    """獲取 Git 狀態"""
    try:
        # 檢查是否在 git 倉庫中
        result = run_command(['git', 'rev-parse', '--git-dir'])
        if not result:
            return {'status': 'not_in_repo', 'message': 'Not a git repository'}

        # 獲取分支
        branch = run_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])

        # 獲取未提交的更改
        status = run_command(['git', 'status', '--porcelain'])

        # 獲取最新提交
        last_commit = run_command(['git', 'log', '-1', '--format=%h - %s'])

        return {
            'status': 'ok',
            'branch': branch,
            'has_changes': len(status) > 0,
            'changes_count': len([line for line in status.split('\n') if line.strip()]),
            'last_commit': last_commit
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def get_network_stats() -> Dict[str, Any]:
    """獲取網絡統計"""
    try:
        # 檢查網絡接口
        result = run_command(['ip', '-o', 'link', 'show'])

        interfaces = []
        for line in result.split('\n'):
            if line:
                parts = line.split(':')
                if len(parts) >= 2:
                    ifname = parts[1].strip()
                    if not ifname.startswith('lo'):
                        interfaces.append(ifname)

        # 檢查開放端口
        listening = run_command(['ss', '-tlnp'])
        listening_count = len([line for line in listening.split('\n') if 'LISTEN' in line])

        return {
            'status': 'ok',
            'interfaces': interfaces,
            'listening_ports': listening_count
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def generate_system_report() -> Dict[str, Any]:
    """生成完整的系統報告"""
    timestamp = datetime.datetime.now().isoformat()

    # 加載各個報告
    health_report = load_json_report('/tmp/health_report.json')
    log_report = load_json_report('/tmp/log_analysis_report.json')
    cleanup_report = load_json_report('/tmp/cleanup_report.json')

    # 獲取 Git 狀態
    git_status = get_git_status()

    # 獲取網絡統計
    network_stats = get_network_stats()

    # 檢查 Docker 容器狀態
    docker_containers = []
    cmd = ['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}\t{{.Ports}}']
    result = run_command(cmd)
    if result:
        lines = result.split('\n')
        docker_containers = [line for line in lines if line and not line.startswith('NAMES')]

    report = {
        'timestamp': timestamp,
        'report_type': 'nightly_system_report',
        'overall_status': 'healthy',

        # 系統健康
        'health': health_report.get('overall', {}),

        # 日誌分析
        'log_analysis': log_report.get('summary', {}),

        # 清理結果
        'cleanup': {
            'disk_before': cleanup_report.get('disk_usage_before', {}),
            'disk_after': cleanup_report.get('disk_usage_after', {}),
            'summary': cleanup_report.get('summary', {})
        },

        # Git 狀態
        'git': git_status,

        # 網絡統計
        'network': network_stats,

        # Docker 容器
        'docker': {
            'container_count': len(docker_containers),
            'containers': docker_containers[:5]  # 只顯示前 5 個
        },

        # 系統負載
        'system': {
            'uptime': run_command(['uptime'])
        }
    }

    # 計算整體狀態
    issues = []

    if health_report.get('overall', {}).get('status') != 'healthy':
        issues.append('System health check failed')

    if log_report.get('summary', {}).get('high_priority', 0) > 0:
        issues.append('High priority log issues detected')

    disk_usage_percent = cleanup_report.get('disk_usage_after', {}).get('usage_percent', '0%').replace('%', '')
    try:
        disk_usage_num = float(disk_usage_percent) if disk_usage_percent else 0
    except ValueError:
        disk_usage_num = 0

    if disk_usage_num > 80:
        issues.append('Disk usage above 80%')

    if issues:
        report['overall_status'] = 'warning'
        report['issues'] = issues

    return report


def save_report(report: Dict[str, Any], filepath: str = '/tmp/nightly_system_report.json'):
    """保存報告到文件"""
    with open(filepath, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return filepath


def print_summary(report: Dict[str, Any]):
    """打印報告摘要"""
    print("\n" + "=" * 60)
    print("Nightly System Report Summary")
    print("=" * 60)
    print(f"Timestamp: {report['timestamp']}")
    print(f"Status: {report['overall_status'].upper()}")

    if report['overall_status'] != 'healthy':
        print("\n⚠️  Issues:")
        for issue in report.get('issues', []):
            print(f"  - {issue}")

    print("\nSystem Health:")
    health = report.get('health', {})
    print(f"  Disk: {health.get('disk', {}).get('usage_percent', 'N/A')} used")
    print(f"  Memory: {health.get('memory', {}).get('used', 'N/A')} / {health.get('memory', {}).get('total', 'N/A')}")
    print(f"  Load: {health.get('load', {}).get('1min', 'N/A')} / {health.get('load', {}).get('5min', 'N/A')} / {health.get('load', {}).get('15min', 'N/A')}")

    print("\nLog Analysis:")
    log = report.get('log_analysis', {})
    print(f"  Recommendations: {log.get('total_recommendations', 0)}")
    print(f"  High Priority: {log.get('high_priority', 0)}")
    print(f"  Medium Priority: {log.get('medium_priority', 0)}")

    print("\nCleanup Results:")
    cleanup = report.get('cleanup', {}).get('summary', {})
    print(f"  Actions: {cleanup.get('successful', 0)}/{cleanup.get('total_actions', 0)} successful")

    disk_before = report.get('cleanup', {}).get('disk_before', {}).get('usage_percent', 'N/A')
    disk_after = report.get('cleanup', {}).get('disk_after', {}).get('usage_percent', 'N/A')
    print(f"  Disk Usage: {disk_before}% → {disk_after}%")

    print("\nDocker:")
    docker = report.get('docker', {})
    print(f"  Running Containers: {docker.get('container_count', 0)}")

    print("\nGit:")
    git = report.get('git', {})
    if git.get('status') == 'ok':
        print(f"  Branch: {git.get('branch', 'N/A')}")
        print(f"  Last Commit: {git.get('last_commit', 'N/A')}")
        print(f"  Uncommitted Changes: {git.get('changes_count', 0)}")
    else:
        print(f"  Status: {git.get('status', 'N/A')}")

    print("\n" + "=" * 60)


def main():
    """主函數"""
    report = generate_system_report()

    # 保存報告
    filepath = save_report(report)
    print(f"\n完整報告已保存到: {filepath}")

    # 打印摘要
    print_summary(report)

    # 保存 Markdown 格式
    md_filepath = filepath.replace('.json', '.md')
    with open(md_filepath, 'w') as f:
        f.write(f"# Nightly System Report\n\n")
        f.write(f"**Generated:** {report['timestamp']}\n\n")
        f.write(f"## Status\n\n{report['overall_status'].upper()}\n\n")

        if report['overall_status'] != 'healthy':
            f.write("## Issues\n\n")
            for issue in report.get('issues', []):
                f.write(f"- {issue}\n")

    print(f"Markdown 報告已保存到: {md_filepath}")


if __name__ == '__main__':
    main()
