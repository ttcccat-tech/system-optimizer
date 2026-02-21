#!/usr/bin/env python3
"""
Network Error Monitor
監控 OpenClaw fetch failed 錯誤，識別網絡問題
"""

import subprocess
import re
import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any


def get_openclaw_errors(hours: int = 24) -> List[Dict[str, Any]]:
    """從 journalctl 提取 OpenClaw fetch failed 錯誤"""
    try:
        cmd = [
            'journalctl',
            '--since', f'{hours} hours ago',
            '--no-pager',
            '-u', 'openclaw',
            '--output', 'cat'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        errors = []
        for line in result.stdout.split('\n'):
            if 'Non-fatal unhandled rejection' in line and 'fetch failed' in line:
                # 提取時間戳
                time_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{2}:\d{2})', line)
                timestamp = time_match.group(1) if time_match else None

                if timestamp:
                    errors.append({
                        'timestamp': timestamp,
                        'type': 'fetch_failed',
                        'raw': line
                    })

        return errors
    except Exception as e:
        print(f"Error fetching logs: {e}", file=__import__('sys').stderr)
        return []


def analyze_error_pattern(errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """分析錯誤模式"""
    if not errors:
        return {
            'total_errors': 0,
            'per_hour': 0,
            'pattern': 'none',
            'recommendation': 'No network errors detected'
        }

    # 按小時計數
    hourly_counts = defaultdict(int)
    for error in errors:
        if error['timestamp']:
            try:
                dt = datetime.fromisoformat(error['timestamp'].replace('Z', '+00:00'))
                hour_key = dt.strftime('%Y-%m-%d %H:00')
                hourly_counts[hour_key] += 1
            except:
                pass

    total_errors = len(errors)
    time_span_hours = 24  # 預設 24 小時
    per_hour = total_errors / time_span_hours

    # 判斷模式
    pattern = 'sporadic'
    recommendation = 'Network errors are sporadic. Consider monitoring over longer periods.'

    if per_hour > 10:
        pattern = 'high_frequency'
        recommendation = 'High frequency of fetch failures. Check network connectivity and external service availability.'
    elif per_hour > 2:
        pattern = 'moderate_frequency'
        recommendation = 'Moderate frequency of fetch failures. Review OpenClaw retry configuration.'

    # 檢查是否集中在特定時間
    if hourly_counts:
        max_hour = max(hourly_counts.values())
        avg_hour = total_errors / len(hourly_counts) if hourly_counts else 0

        if max_hour > avg_hour * 2:
            pattern = 'time_clustered'
            peak_hour = max(hourly_counts, key=hourly_counts.get)
            recommendation = f'Errors cluster around {peak_hour}. Possible scheduled task issues or external service degradation.'

    return {
        'total_errors': total_errors,
        'per_hour': round(per_hour, 2),
        'pattern': pattern,
        'peak_hour_count': max(hourly_counts.values()) if hourly_counts else 0,
        'hours_with_errors': len(hourly_counts),
        'recommendation': recommendation,
        'hourly_breakdown': dict(hourly_counts)
    }


def generate_network_report() -> Dict[str, Any]:
    """生成網絡監控報告"""
    errors = get_openclaw_errors(24)
    analysis = analyze_error_pattern(errors)

    report = {
        'timestamp': datetime.now().isoformat(),
        'report_type': 'network_error_monitor',
        'status': 'healthy' if analysis['total_errors'] == 0 else 'warning',
        'summary': analysis
    }

    return report


def main():
    """主函數"""
    report = generate_network_report()

    # 輸出 JSON
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # 保存到文件
    report_file = '/tmp/network_monitor_report.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f'\n報告已保存到: {report_file}', file=__import__('sys').stderr)

    # 返回狀態碼
    import sys
    if report['status'] == 'warning':
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()
