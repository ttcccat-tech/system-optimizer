#!/usr/bin/env python3
"""
System Trend Analyzer - 系統趨勢分析器
追蹤系統資源使用趨勢，檢測異常和潛在問題
"""

import subprocess
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import statistics


class TrendAnalyzer:
    """系統趨勢分析器"""

    def __init__(self, data_dir: str = "/tmp/system_trends"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().isoformat()

    def run_command(self, cmd: List[str]) -> str:
        """執行 shell 命令"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout.strip()
        except Exception as e:
            return ""

    def get_current_stats(self) -> Dict[str, Any]:
        """獲取當前系統統計數據"""
        stats = {
            "timestamp": self.timestamp,
            "disk": {},
            "memory": {},
            "load": {},
            "docker": {}
        }

        # 磁盤使用
        df_output = self.run_command(["df", "-h", "/"])
        if df_output:
            lines = df_output.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 5:
                    stats["disk"] = {
                        "size": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "usage_percent": parts[4]
                    }

        # 記憶體使用
        mem_output = self.run_command(["free", "-h"])
        if mem_output:
            lines = mem_output.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 4:
                    stats["memory"] = {
                        "total": parts[1],
                        "used": parts[2],
                        "free": parts[3],
                        "available": parts[6] if len(parts) > 6 else "N/A"
                    }

        # 系統負載
        load_output = self.run_command(["uptime"])
        if load_output:
            # 負載通常在最後一行，格式：load average: 0.01, 0.03, 0.00
            if "load average" in load_output:
                load_part = load_output.split("load average:")[1].strip()
                loads = [float(x.strip()) for x in load_part.split(',')]
                stats["load"] = {
                    "1min": loads[0],
                    "5min": loads[1],
                    "15min": loads[2]
                }

        # Docker 狀態
        docker_output = self.run_command(["docker", "ps", "--format", "{{json .}}"])
        containers = []
        for line in docker_output.split('\n'):
            if line:
                try:
                    containers.append(json.loads(line))
                except:
                    pass
        stats["docker"] = {
            "total": len(containers),
            "running": len([c for c in containers if c.get("Status", "").startswith("Up")])
        }

        return stats

    def save_stats(self, stats: Dict[str, Any]) -> None:
        """保存統計數據"""
        filename = self.data_dir / f"stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(stats, f, indent=2)

    def load_recent_stats(self, hours: int = 24) -> List[Dict[str, Any]]:
        """加載最近的統計數據"""
        stats = []
        cutoff_time = datetime.now() - timedelta(hours=hours)

        for file in sorted(self.data_dir.glob("stats_*.json")):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    # 解析時間戳
                    file_time = datetime.fromisoformat(data.get("timestamp", file.stem))
                    if file_time > cutoff_time:
                        stats.append(data)
            except:
                pass

        return stats

    def extract_numeric_value(self, value: str) -> float:
        """從字符串中提取數值"""
        try:
            # 移除單位（G, M, % 等）
            value = value.replace('G', '').replace('M', '').replace('%', '')
            return float(value)
        except:
            return 0.0

    def analyze_trend(self, stats_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析趨勢"""
        if not stats_list:
            return {"status": "no_data", "message": "No historical data available"}

        analysis = {
            "status": "ok",
            "data_points": len(stats_list),
            "trends": {},
            "warnings": [],
            "anomalies": []
        }

        # 分析磁盤使用趨勢
        disk_usage = []
        for stat in stats_list:
            if stat.get("disk", {}).get("usage_percent"):
                disk_usage.append(self.extract_numeric_value(stat["disk"]["usage_percent"]))

        if disk_usage:
            disk_avg = statistics.mean(disk_usage)
            disk_latest = disk_usage[-1]
            disk_trend = disk_latest - disk_usage[0] if len(disk_usage) > 1 else 0

            analysis["trends"]["disk"] = {
                "current": disk_latest,
                "average": disk_avg,
                "trend": disk_trend,
                "trend_percent": (disk_trend / disk_avg * 100) if disk_avg > 0 else 0
            }

            if disk_latest > 80:
                analysis["warnings"].append({
                    "type": "disk",
                    "severity": "high",
                    "message": f"Disk usage is at {disk_latest}%"
                })
            elif disk_latest > 70:
                analysis["warnings"].append({
                    "type": "disk",
                    "severity": "medium",
                    "message": f"Disk usage is at {disk_latest}%"
                })

            # 檢測異常增長
            if len(disk_usage) > 3:
                growth_rate = (disk_usage[-1] - disk_usage[-4]) / 3
                if growth_rate > 2:  # 每天增長超過 2%
                    analysis["anomalies"].append({
                        "type": "disk_growth",
                        "message": f"Disk growing at {growth_rate:.2f}% per hour",
                        "severity": "medium"
                    })

        # 分析負載趨勢
        load_1min = []
        load_5min = []
        for stat in stats_list:
            if stat.get("load", {}):
                load_1min.append(stat["load"].get("1min", 0))
                load_5min.append(stat["load"].get("5min", 0))

        if load_1min:
            load_avg = statistics.mean(load_1min)
            load_max = max(load_1min)

            analysis["trends"]["load"] = {
                "current_1min": load_1min[-1],
                "current_5min": load_5min[-1] if load_5min else 0,
                "average": load_avg,
                "max": load_max
            }

            if load_avg > 2.0:
                analysis["warnings"].append({
                    "type": "load",
                    "severity": "high",
                    "message": f"High average load: {load_avg:.2f}"
                })

            # 檢測負載尖峰
            if load_max > load_avg * 3:
                analysis["anomalies"].append({
                    "type": "load_spike",
                    "message": f"Load spike detected: {load_max:.2f} (avg: {load_avg:.2f})",
                    "severity": "medium"
                })

        # Docker 容器狀態
        container_counts = []
        for stat in stats_list:
            if stat.get("docker", {}).get("total"):
                container_counts.append(stat["docker"]["total"])

        if container_counts:
            analysis["trends"]["docker"] = {
                "current": container_counts[-1],
                "average": statistics.mean(container_counts),
                "max": max(container_counts)
            }

        return analysis

    def generate_report(self) -> str:
        """生成趨勢分析報告"""
        # 保存當前統計
        current = self.get_current_stats()
        self.save_stats(current)

        # 加載歷史數據
        recent_stats = self.load_recent_stats(hours=24)

        # 分析趨勢
        analysis = self.analyze_trend(recent_stats)

        report = f"""
# System Trend Analysis Report
Generated: {self.timestamp}

## Current System Status

### Disk Usage
- Size: {current.get('disk', {}).get('size', 'N/A')}
- Used: {current.get('disk', {}).get('used', 'N/A')}
- Available: {current.get('disk', {}).get('available', 'N/A')}
- Usage: {current.get('disk', {}).get('usage_percent', 'N/A')}

### Memory Usage
- Total: {current.get('memory', {}).get('total', 'N/A')}
- Used: {current.get('memory', {}).get('used', 'N/A')}
- Free: {current.get('memory', {}).get('free', 'N/A')}
- Available: {current.get('memory', {}).get('available', 'N/A')}

### System Load
- 1 min: {current.get('load', {}).get('1min', 'N/A')}
- 5 min: {current.get('load', {}).get('5min', 'N/A')}
- 15 min: {current.get('load', {}).get('15min', 'N/A')}

### Docker Status
- Total: {current.get('docker', {}).get('total', 'N/A')}
- Running: {current.get('docker', {}).get('running', 'N/A')}

## Trend Analysis ({len(recent_stats)} data points over 24h)

"""

        if analysis.get("trends"):
            report += "### Disk Trend\n"
            if "disk" in analysis["trends"]:
                disk = analysis["trends"]["disk"]
                report += f"- Current: {disk['current']:.1f}%\n"
                report += f"- Average: {disk['average']:.1f}%\n"
                report += f"- Trend: {disk['trend']:+.1f}% ({disk['trend_percent']:+.1f}%)\n\n"

            report += "### Load Trend\n"
            if "load" in analysis["trends"]:
                load = analysis["trends"]["load"]
                report += f"- Current (1min): {load['current_1min']:.2f}\n"
                report += f"- Current (5min): {load['current_5min']:.2f}\n"
                report += f"- Average: {load['average']:.2f}\n"
                report += f"- Max: {load['max']:.2f}\n\n"

            report += "### Docker Trend\n"
            if "docker" in analysis["trends"]:
                docker = analysis["trends"]["docker"]
                report += f"- Current: {docker['current']}\n"
                report += f"- Average: {docker['average']:.1f}\n"
                report += f"- Max: {docker['max']}\n\n"

        # Warnings
        if analysis.get("warnings"):
            report += "## Warnings\n"
            for warning in analysis["warnings"]:
                severity_emoji = "🔴" if warning["severity"] == "high" else "🟡"
                report += f"- {severity_emoji} [{warning['severity'].upper()}] {warning['message']}\n"
            report += "\n"

        # Anomalies
        if analysis.get("anomalies"):
            report += "## Anomalies Detected\n"
            for anomaly in analysis["anomalies"]:
                report += f"- ⚠️ {anomaly['message']}\n"
            report += "\n"

        if not analysis.get("warnings") and not analysis.get("anomalies"):
            report += "## Summary\n"
            report += "✅ No issues detected. System is operating normally.\n"

        return report


def main():
    parser = argparse.ArgumentParser(description='系統趨勢分析工具')
    parser.add_argument('--format', choices=['json', 'text'], default='text', help='輸出格式')
    parser.add_argument('--output', '-o', help='輸出到文件')
    parser.add_argument('--data-dir', '-d', default='/tmp/system_trends', help='數據目錄')
    parser.add_argument('--hours', '-H', type=int, default=24, help='分析過去幾小時的數據')

    args = parser.parse_args()

    analyzer = TrendAnalyzer(data_dir=args.data_dir)

    if args.format == 'json':
        current = analyzer.get_current_stats()
        analyzer.save_stats(current)
        recent = analyzer.load_recent_stats(hours=args.hours)
        analysis = analyzer.analyze_trend(recent)

        result = {
            "current": current,
            "analysis": analysis,
            "data_points": len(recent)
        }
        print(json.dumps(result, indent=2))
    else:
        report = analyzer.generate_report()
        print(report)

    if args.output:
        if args.format == 'json':
            with open(args.output, 'w') as f:
                current = analyzer.get_current_stats()
                analyzer.save_stats(current)
                recent = analyzer.load_recent_stats(hours=args.hours)
                analysis = analyzer.analyze_trend(recent)
                json.dump({"current": current, "analysis": analysis}, f, indent=2)
        else:
            with open(args.output, 'w') as f:
                f.write(analyzer.generate_report())


if __name__ == '__main__':
    main()
