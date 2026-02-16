#!/usr/bin/env python3
"""
OpenClaw Log Analyzer
分析 OpenClaw 和系統日誌，識別瓶頸和問題
"""

import re
import subprocess
import datetime
import json
from typing import Dict, Any, List, Tuple
from collections import defaultdict


def run_command(cmd: list, timeout: int = 30) -> str:
    """執行命令並返回輸出"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception) as e:
        return ""


def analyze_journalctl(hours: int = 24) -> Dict[str, Any]:
    """分析 systemd journal 日誌"""
    try:
        cmd = ['journalctl', '--since', f'{hours} hours ago', '--no-pager', '-u', 'openclaw']
        output = run_command(cmd)

        stats = {
            'timeout_errors': [],
            'lane_errors': [],
            'embedded_errors': [],
            'general_errors': [],
            'total_lines': len(output.split('\n')) if output else 0,
            'time_range_hours': hours
        }

        if not output:
            return {**stats, 'status': 'warning', 'message': 'No journal logs found'}

        # 分析錯誤模式
        for line in output.split('\n'):
            if 'timeout' in line.lower():
                if 'embedded' in line.lower():
                    stats['embedded_errors'].append(line)
                else:
                    stats['timeout_errors'].append(line)
            elif 'lane task error' in line.lower():
                stats['lane_errors'].append(line)
            elif 'error' in line.lower() and 'failover' not in line.lower():
                stats['general_errors'].append(line)

        return {
            **stats,
            'status': 'ok',
            'summary': {
                'timeouts': len(stats['timeout_errors']),
                'lane_errors': len(stats['lane_errors']),
                'embedded_errors': len(stats['embedded_errors']),
                'general_errors': len(stats['general_errors'])
            }
        }
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to analyze journal: {e}'}


def extract_timeout_details(logs: List[str]) -> List[Dict[str, str]]:
    """從 timeout 日誌中提取詳細資訊"""
    details = []

    for log in logs:
        # 嘗試提取 runId, sessionId 等
        run_id_match = re.search(r'runId=([a-f0-9-]+)', log)
        session_id_match = re.search(r'sessionId=([a-f0-9-]+)', log)
        timeout_match = re.search(r'timeoutMs=(\d+)', log)

        if run_id_match or session_id_match:
            details.append({
                'runId': run_id_match.group(1) if run_id_match else 'N/A',
                'sessionId': session_id_match.group(1) if session_id_match else 'N/A',
                'timeoutMs': timeout_match.group(1) if timeout_match else 'N/A',
                'log': log[:200]  # 截斷長日誌
            })

    return details


def check_agent_session_logs(agent_id: str = 'main') -> Dict[str, Any]:
    """檢查特定 agent 的 session 日誌"""
    try:
        agents_dir = f'~/.openclaw/agents/{agent_id}/sessions'
        expanded_path = subprocess.run(['bash', '-c', f'echo {agents_dir}'],
                                       capture_output=True, text=True).stdout.strip()

        if not subprocess.run(['test', '-d', expanded_path], capture_output=True).returncode == 0:
            return {'status': 'warning', 'message': f'No sessions directory for agent: {agent_id}'}

        # 列出最近的 session 文件
        cmd = ['ls', '-t', expanded_path, '|', 'head', '-10']
        result = run_command(['bash', '-c', ' '.join(cmd)])

        sessions = result.split('\n') if result else []
        recent_sessions = [s for s in sessions if s.endswith('.jsonl')]

        return {
            'status': 'ok',
            'agent_id': agent_id,
            'recent_sessions_count': len(recent_sessions),
            'sessions_directory': expanded_path
        }
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to check agent sessions: {e}'}


def analyze_docker_logs(container_name: str, hours: int = 24) -> Dict[str, Any]:
    """分析特定 Docker 容器的日誌"""
    try:
        cmd = ['docker', 'logs', '--since', f'{hours}h', container_name, '--tail', '100']
        output = run_command(cmd)

        if not output:
            return {'status': 'ok', 'message': f'No logs for container: {container_name}', 'line_count': 0}

        lines = output.split('\n')
        errors = [line for line in lines if 'error' in line.lower() or 'exception' in line.lower()]

        return {
            'status': 'ok',
            'container': container_name,
            'line_count': len(lines),
            'error_count': len(errors),
            'recent_errors': errors[:5]  # 只保留前 5 個錯誤
        }
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to analyze Docker logs: {e}'}


def identify_bottlenecks() -> Dict[str, Any]:
    """識別系統瓶頸"""
    analysis = {
        'journal': analyze_journalctl(24),
        'docker_containers': {},
        'recommendations': []
    }

    # 檢查所有運行中的 Docker 容器日誌
    cmd = ['docker', 'ps', '--format', '{{.Names}}']
    containers = run_command(cmd).split('\n')

    for container in containers:
        if container:  # 跳過空行
            analysis['docker_containers'][container] = analyze_docker_logs(container, 24)

    # 生成建議
    journal_summary = analysis['journal'].get('summary', {})
    if journal_summary.get('timeouts', 0) > 0:
        analysis['recommendations'].append({
            'priority': 'high',
            'issue': 'LLM request timeouts detected',
            'suggestion': 'Consider increasing timeoutMs or check network connectivity',
            'details': extract_timeout_details(analysis['journal'].get('timeout_errors', []))
        })

    if journal_summary.get('embedded_errors', 0) > 0:
        analysis['recommendations'].append({
            'priority': 'medium',
            'issue': 'Embedded agent errors',
            'suggestion': 'Review embedded agent configuration and error handling'
        })

    # 檢查 Docker 容器錯誤
    for container, logs in analysis['docker_containers'].items():
        if logs.get('error_count', 0) > 0:
            analysis['recommendations'].append({
                'priority': 'medium',
                'issue': f'Errors in container: {container}',
                'suggestion': 'Review container logs for application errors',
                'error_count': logs['error_count']
            })

    return analysis


def generate_report() -> Dict[str, Any]:
    """生成完整的分析報告"""
    analysis = identify_bottlenecks()

    report = {
        'timestamp': datetime.datetime.now().isoformat(),
        'analysis_type': 'log_bottleneck_analysis',
        'overall_status': 'healthy',
        'summary': {
            'total_recommendations': len(analysis.get('recommendations', [])),
            'high_priority': len([r for r in analysis.get('recommendations', []) if r.get('priority') == 'high']),
            'medium_priority': len([r for r in analysis.get('recommendations', []) if r.get('priority') == 'medium'])
        },
        'data': analysis
    }

    # 確定整體狀態
    if report['summary']['high_priority'] > 0:
        report['overall_status'] = 'warning'
    elif report['summary']['total_recommendations'] > 0:
        report['overall_status'] = 'info'

    return report


def main():
    """主函數"""
    report = generate_report()

    # 輸出 JSON 格式
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # 保存到文件
    report_file = '/tmp/log_analysis_report.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f'\n報告已保存到: {report_file}', file=__import__('sys').stderr)

    # 返回狀態碼
    import sys
    if report['overall_status'] == 'warning':
        sys.exit(2)
    elif report['summary']['total_recommendations'] > 0:
        sys.exit(3)  # 有建議但非警告
    sys.exit(0)


if __name__ == '__main__':
    main()
