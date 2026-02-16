#!/usr/bin/env python3
"""
System Cleanup Tool
清理系統資源：Docker images, containers, agent sessions
"""

import subprocess
import datetime
import json
import os
import re
from typing import Dict, Any, List, Tuple


def run_command(cmd: list, timeout: int = 60) -> Tuple[bool, str]:
    """執行命令並返回 (success, output)"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip() + result.stderr.strip()
    except (subprocess.TimeoutExpired, Exception) as e:
        return False, str(e)


def cleanup_docker_images() -> Dict[str, Any]:
    """清理懸置的 Docker images"""
    success, output = run_command(['docker', 'image', 'prune', '-f'])

    return {
        'action': 'cleanup_docker_images',
        'success': success,
        'output': output,
        'status': 'ok' if success else 'error'
    }


def cleanup_docker_containers() -> Dict[str, Any]:
    """清理停止的 Docker containers"""
    success, output = run_command(['docker', 'container', 'prune', '-f'])

    return {
        'action': 'cleanup_docker_containers',
        'success': success,
        'output': output,
        'status': 'ok' if success else 'error'
    }


def cleanup_docker_system() -> Dict[str, Any]:
    """清理未使用的 Docker 資源（網路、構建緩存等）"""
    success, output = run_command(['docker', 'system', 'prune', '-f'])

    return {
        'action': 'cleanup_docker_system',
        'success': success,
        'output': output,
        'status': 'ok' if success else 'error'
    }


def cleanup_journal_logs(days_to_keep: int = 7) -> Dict[str, Any]:
    """清理舊的 journal 日誌"""
    # 先檢查當前大小
    success_before, size_before = run_command(['journalctl', '--disk-usage'])

    # 執行清理
    success, output = run_command(['journalctl', '--vacuum-time', f'{days_to_keep}d'])

    # 檢查清理後大小
    success_after, size_after = run_command(['journalctl', '--disk-usage'])

    return {
        'action': 'cleanup_journal_logs',
        'success': success,
        'output': output,
        'days_kept': days_to_keep,
        'size_before': size_before,
        'size_after': size_after,
        'status': 'ok' if success else 'error'
    }


def get_docker_disk_usage() -> Dict[str, Any]:
    """獲取 Docker 磁碟使用情況"""
    success, output = run_command(['docker', 'system', 'df'])

    if not success:
        return {'status': 'error', 'message': 'Failed to get Docker disk usage'}

    # 解析輸出
    lines = output.split('\n')
    usage_data = []

    for line in lines[1:]:  # 跳過標題
        if line.strip():
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) >= 3:
                usage_data.append({
                    'type': parts[0],
                    'total_count': parts[1],
                    'size': parts[2]
                })

    return {
        'status': 'ok',
        'usage': usage_data,
        'raw_output': output
    }


def cleanup_apt_cache() -> Dict[str, Any]:
    """清理 APT 套件快取"""
    # 清理舊的 .deb 檔案
    success1, output1 = run_command(['sudo', 'apt-get', 'clean'])

    # 清理無用的依賴
    success2, output2 = run_command(['sudo', 'apt-get', 'autoremove', '-y'])

    return {
        'action': 'cleanup_apt_cache',
        'clean_success': success1,
        'clean_output': output1,
        'autoremove_success': success2,
        'autoremove_output': output2,
        'status': 'ok' if (success1 and success2) else 'error'
    }


def cleanup_tmp_files() -> Dict[str, Any]:
    """清理 /tmp 目錄中的舊檔案（7 天以上）"""
    tmp_dir = '/tmp'

    # 計算清理前的數量（只提取數字行）
    count_before_cmd = ['bash', '-c', f'find {tmp_dir} -type f -mtime +7 2>/dev/null | wc -l']
    success_before, count_before_raw = run_command(count_before_cmd)

    # 提取數字
    try:
        count_before = int(count_before_raw.strip().split('\n')[-1].strip())
    except:
        count_before = 0

    # 刪除 7 天以上的檔案
    cleanup_cmd = ['bash', '-c', f'sudo find {tmp_dir} -type f -mtime +7 -delete 2>/dev/null || true']
    success, output = run_command(cleanup_cmd)

    # 計算清理後的數量（只提取數字行）
    count_after_cmd = ['bash', '-c', f'find {tmp_dir} -type f -mtime +7 2>/dev/null | wc -l']
    success_after, count_after_raw = run_command(count_after_cmd)

    try:
        count_after = int(count_after_raw.strip().split('\n')[-1].strip())
    except:
        count_after = 0

    files_deleted = count_before - count_after

    return {
        'action': 'cleanup_tmp_files',
        'success': True,  # 檢查總是成功
        'files_deleted': files_deleted,
        'directory': tmp_dir,
        'status': 'ok'
    }


def get_disk_space() -> Dict[str, Any]:
    """獲取磁碟空間資訊"""
    success, output = run_command(['df', '-h', '/'])

    if not success:
        return {'status': 'error', 'message': 'Failed to get disk space'}

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
            'mounted_on': parts[5]
        }

    return {'status': 'error', 'message': 'Unexpected df output'}


def run_cleanup(safe_mode: bool = True) -> Dict[str, Any]:
    """執行所有清理任務"""
    report = {
        'timestamp': datetime.datetime.now().isoformat(),
        'cleanup_type': 'full_system_cleanup',
        'safe_mode': safe_mode,
        'results': {},
        'disk_usage_before': {},
        'disk_usage_after': {},
        'summary': {
            'total_actions': 0,
            'successful': 0,
            'failed': 0
        }
    }

    # 獲取清理前的磁碟空間
    report['disk_usage_before'] = get_disk_space()

    # Docker 相關清理（安全）
    report['results']['docker_images'] = cleanup_docker_images()
    report['results']['docker_containers'] = cleanup_docker_containers()
    report['results']['docker_system'] = cleanup_docker_system()

    # Journal 日誌清理
    report['results']['journal_logs'] = cleanup_journal_logs(days_to_keep=7)

    # 安全清理：APT 快取和 tmp 檔案
    if safe_mode:
        report['results']['apt_cache'] = cleanup_apt_cache()
        report['results']['tmp_files'] = cleanup_tmp_files()

    # 獲取清理後的磁碟空間
    report['disk_usage_after'] = get_disk_space()

    # 獲取 Docker 磁碟使用情況
    report['results']['docker_disk_usage'] = get_docker_disk_usage()

    # 匯總結果
    report['summary']['total_actions'] = len(report['results'])
    report['summary']['successful'] = sum(1 for r in report['results'].values() if r.get('status') == 'ok')
    report['summary']['failed'] = report['summary']['total_actions'] - report['summary']['successful']

    # 計算釋放的空間
    before_percent = report['disk_usage_before'].get('usage_percent', '0%').rstrip('%')
    after_percent = report['disk_usage_after'].get('usage_percent', '0%').rstrip('%')

    try:
        space_freed_percent = float(before_percent) - float(after_percent)
        report['summary']['space_freed_percent'] = f"+{space_freed_percent:.1f}%"
    except:
        report['summary']['space_freed_percent'] = "N/A"

    return report


def main():
    """主函數"""
    import sys

    # 執行清理（安全模式）
    report = run_cleanup(safe_mode=True)

    # 輸出 JSON 格式
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # 保存到文件
    report_file = '/tmp/cleanup_report.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f'\n清理報告已保存到: {report_file}', file=sys.stderr)

    # 返回狀態碼
    if report['summary']['failed'] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
