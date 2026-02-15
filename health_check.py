#!/usr/bin/env python3
"""
System Health Check Tool
檢查系統健康狀態並生成報告
"""

import json
import subprocess
import datetime
import os
from typing import Dict, Any


def run_command(cmd: list) -> str:
    """執行命令並返回輸出"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        return ""


def check_disk() -> Dict[str, Any]:
    """檢查磁碟使用情況"""
    try:
        output = run_command(['df', '-h', '/'])
        lines = output.split('\n')
        if len(lines) >= 2:
            parts = lines[1].split()
            return {
                'status': 'ok',
                'filesystem': parts[0],
                'size': parts[1],
                'used': parts[2],
                'available': parts[3],
                'usage_percent': parts[4],
                'warning': int(parts[4].rstrip('%')) > 80
            }
    except Exception:
        pass
    return {'status': 'error', 'message': 'Unable to check disk usage'}


def check_memory() -> Dict[str, Any]:
    """檢查記憶體使用情況"""
    try:
        output = run_command(['free', '-h'])
        lines = output.split('\n')
        if len(lines) >= 2:
            parts = lines[1].split()
            total = parts[1]
            used = parts[2]
            available = parts[-1]
            return {
                'status': 'ok',
                'total': total,
                'used': used,
                'available': available,
                'warning': 'Gi' in used and float(used.replace('Gi', '')) > 6.0
            }
    except Exception:
        pass
    return {'status': 'error', 'message': 'Unable to check memory'}


def check_load() -> Dict[str, Any]:
    """檢查系統負載"""
    try:
        output = run_command(['uptime'])
        if 'load average:' in output:
            load_part = output.split('load average:')[1].strip()
            loads = [float(x.strip(',')) for x in load_part.split()]
            return {
                'status': 'ok',
                '1min': loads[0],
                '5min': loads[1],
                '15min': loads[2],
                'warning': loads[0] > 2.0
            }
    except Exception:
        pass
    return {'status': 'error', 'message': 'Unable to check load'}


def check_docker() -> Dict[str, Any]:
    """檢查 Docker 容器狀態"""
    try:
        output = run_command(['docker', 'ps', '-a', '--format', '{{.Names}}|{{.Status}}'])
        containers = []
        for line in output.split('\n'):
            if line:
                name, status = line.split('|', 1)
                is_running = 'Up' in status
                containers.append({
                    'name': name,
                    'status': status,
                    'running': is_running
                })

        total = len(containers)
        running = sum(1 for c in containers if c['running'])

        return {
            'status': 'ok',
            'total': total,
            'running': running,
            'stopped': total - running,
            'containers': containers,
            'warning': running < total  # 有容器停止
        }
    except Exception as e:
        return {'status': 'error', 'message': f'Unable to check Docker: {e}'}


def check_openclaw() -> Dict[str, Any]:
    """檢查 OpenClaw 狀態"""
    try:
        # 檢查 OpenClaw 進程
        output = run_command(['pgrep', '-f', 'openclaw'])
        if output:
            return {
                'status': 'ok',
                'running': True,
                'pid': output.split('\n')[0]
            }
        return {
            'status': 'warning',
            'running': False,
            'message': 'OpenClaw process not found'
        }
    except Exception as e:
        return {'status': 'error', 'message': f'Unable to check OpenClaw: {e}'}


def check_agent_sessions() -> Dict[str, Any]:
    """檢查 agent sessions 大小"""
    try:
        agents_dir = os.path.expanduser('~/.openclaw/agents')
        if not os.path.exists(agents_dir):
            return {'status': 'ok', 'message': 'No agents directory found'}

        output = run_command(['du', '-sh', agents_dir])
        if output:
            size = output.split()[0]
            return {
                'status': 'ok',
                'size': size,
                'path': agents_dir
            }
    except Exception as e:
        return {'status': 'error', 'message': f'Unable to check sessions: {e}'}


def generate_report() -> Dict[str, Any]:
    """生成完整的健康報告"""
    report = {
        'timestamp': datetime.datetime.now().isoformat(),
        'checks': {
            'disk': check_disk(),
            'memory': check_memory(),
            'load': check_load(),
            'docker': check_docker(),
            'openclaw': check_openclaw(),
            'agent_sessions': check_agent_sessions()
        },
        'overall': {
            'status': 'healthy',
            'warnings': [],
            'errors': []
        }
    }

    # 匯總警告和錯誤
    for name, check in report['checks'].items():
        if check.get('status') == 'error':
            report['overall']['errors'].append(f'{name}: {check.get("message", "Unknown error")}')
        elif check.get('warning'):
            report['overall']['warnings'].append(f'{name}: Warning condition detected')

    # 確定整體狀態
    if report['overall']['errors']:
        report['overall']['status'] = 'error'
    elif report['overall']['warnings']:
        report['overall']['status'] = 'warning'

    return report


def main():
    """主函數"""
    report = generate_report()

    # 輸出 JSON 格式
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # 保存到文件
    report_file = '/tmp/health_report.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f'\n報告已保存到: {report_file}', file=__import__('sys').stderr)

    # 返回狀態碼
    import sys
    if report['overall']['status'] == 'error':
        sys.exit(1)
    elif report['overall']['status'] == 'warning':
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()
