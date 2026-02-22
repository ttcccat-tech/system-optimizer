#!/usr/bin/env python3
"""
Service Optimizer - 服務優化工具

檢測和優化運行中的服務，特別關注：
1. 生產環境部署建議（開發服務器 vs 生產服務器）
2. 服務健康檢查
3. 資源使用分析
4. 服務配置優化建議
"""

import subprocess
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Tuple
import argparse


class ServiceOptimizer:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.docker_services = []
        self.systemd_services = []
        self.recommendations = []
        self.warnings = []

    def log(self, message: str, level: str = "INFO"):
        """日誌輸出"""
        if self.verbose or level in ["WARNING", "ERROR"]:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")

    def get_docker_services(self) -> List[Dict]:
        """獲取所有運行中的 Docker 容器資訊"""
        self.log("獲取 Docker 容器資訊...")
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                check=True
            )
            services = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        data = json.loads(line)
                        services.append({
                            'name': data.get('Names', data.get('Name', 'unknown')),
                            'image': data.get('Image', 'unknown'),
                            'status': data.get('Status', 'unknown'),
                            'ports': data.get('Ports', ''),
                        })
                    except json.JSONDecodeError:
                        continue
            self.docker_services = services
            self.log(f"找到 {len(services)} 個運行中的 Docker 容器")
            return services
        except subprocess.CalledProcessError as e:
            self.log(f"獲取 Docker 容器失敗: {e}", "ERROR")
            return []

    def analyze_development_warning(self, service: Dict) -> str:
        """檢查服務是否使用開發環境配置"""
        image = service.get('image', '').lower()
        name = service.get('name', '').lower()

        # 常見的開發環境標誌
        dev_indicators = [
            'flask', 'django', 'rails', 'express',
            'dev', 'development', 'test', 'debug'
        ]

        # 檢查圖像名稱
        for indicator in dev_indicators:
            if indicator in image or indicator in name:
                return f"⚠️ 服務 {service['name']} 可能使用開發環境配置（image: {service['image']}）"

        # 檢查容器日誌中的警告
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", "10", service['name']],
                capture_output=True,
                text=True,
                check=False
            )
            logs = result.stdout.lower()
            if "development server" in logs or "do not use in production" in logs:
                return f"⚠️ 服務 {service['name']} 正在使用開發服務器（容器日誌顯示警告）"
        except subprocess.CalledProcessError:
            pass

        return None

    def get_service_resource_usage(self, service_name: str) -> Dict[str, float]:
        """獲取 Docker 容器的資源使用情況"""
        try:
            result = subprocess.run(
                ["docker", "stats", service_name, "--no-stream", "--format", "json"],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(result.stdout)
            # 解析 CPU 使用率（移除 % 符號）
            cpu = float(data['CPUPerc'].replace('%', ''))
            # 解析記憶體使用（MB）
            mem = float(data['MemUsage'].split('/')[0].replace('MiB', '').strip())
            return {'cpu_percent': cpu, 'memory_mb': mem}
        except (subprocess.CalledProcessError, KeyError, ValueError, json.JSONDecodeError):
            return {'cpu_percent': 0, 'memory_mb': 0}

    def check_service_health(self, service: Dict) -> bool:
        """檢查服務健康狀態"""
        name = service['name']
        ports = service['ports']

        # 如果有公開的 HTTP 端口，嘗試連接
        if '->' in ports:
            for port in ports.split(','):
                # 提取主機端口
                match = re.search(r'(\d+)->', port)
                if match:
                    host_port = match.group(1)
                    try:
                        result = subprocess.run(
                            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                             f"http://localhost:{host_port}"],
                            capture_output=True,
                            text=True,
                            timeout=5,
                            check=False
                        )
                        if result.stdout == '200':
                            self.log(f"✅ 服務 {name} (port {host_port}) 健康檢查通過")
                            return True
                        elif result.stdout in ['301', '302']:
                            self.log(f"✅ 服務 {name} (port {host_port}) 返回重定向 ({result.stdout})")
                            return True
                        else:
                            self.log(f"⚠️ 服務 {name} (port {host_port}) 返回 {result.stdout}", "WARNING")
                    except subprocess.TimeoutExpired:
                        self.log(f"⚠️ 服務 {name} (port {host_port}) 健康檢查超時", "WARNING")
                    except Exception as e:
                        self.log(f"❌ 服務 {name} (port {host_port}) 健康檢查失敗: {e}", "ERROR")

        return False

    def analyze_docker_services(self) -> List[Dict]:
        """分析 Docker 服務並生成優化建議"""
        results = []
        for service in self.docker_services:
            result = {
                'name': service['name'],
                'image': service['image'],
                'status': service['status'],
                'ports': service['ports'],
                'warnings': [],
                'recommendations': [],
                'resource_usage': {},
                'health_check': None
            }

            # 檢查開發環境警告
            dev_warning = self.analyze_development_warning(service)
            if dev_warning:
                result['warnings'].append(dev_warning)
                result['recommendations'].append(
                    f"建議使用生產級 WSGI 伺服器（如 Gunicorn、uWSGI）"
                )
                self.warnings.append(dev_warning)

            # 獲取資源使用情況
            resource_usage = self.get_service_resource_usage(service['name'])
            result['resource_usage'] = resource_usage

            # 資源使用警告
            if resource_usage['cpu_percent'] > 80:
                result['warnings'].append(
                    f"⚠️ CPU 使用率過高: {resource_usage['cpu_percent']:.1f}%"
                )
            if resource_usage['memory_mb'] > 1000:
                result['warnings'].append(
                    f"⚠️ 記憶體使用較高: {resource_usage['memory_mb']:.1f} MB"
                )

            # 健康檢查
            is_healthy = self.check_service_health(service)
            result['health_check'] = 'healthy' if is_healthy else 'unhealthy'

            results.append(result)

        return results

    def generate_report(self, results: List[Dict]) -> str:
        """生成優化報告"""
        report = []
        report.append("# Service Optimization Report")
        report.append(f"## Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        report.append("")

        # 摘要
        total_services = len(results)
        unhealthy_services = sum(1 for r in results if r['health_check'] == 'unhealthy')
        dev_warnings = sum(1 for r in results if 'development' in ' '.join(r['warnings']))

        report.append("## Summary")
        report.append(f"- **Total Docker Services**: {total_services}")
        report.append(f"- **Healthy Services**: {total_services - unhealthy_services}")
        report.append(f"- **Unhealthy Services**: {unhealthy_services}")
        report.append(f"- **Development Environment Warnings**: {dev_warnings}")
        report.append("")

        # 詳細服務報告
        report.append("## Service Details")
        for service in results:
            report.append(f"### {service['name']}")
            report.append(f"- **Image**: {service['image']}")
            report.append(f"- **Status**: {service['status']}")
            report.append(f"- **Ports**: {service['ports']}")
            report.append(f"- **Health**: {service['health_check']}")
            report.append(f"- **CPU Usage**: {service['resource_usage'].get('cpu_percent', 0):.1f}%")
            report.append(f"- **Memory Usage**: {service['resource_usage'].get('memory_mb', 0):.1f} MB")

            if service['warnings']:
                report.append(f"- **Warnings**:")
                for warning in service['warnings']:
                    report.append(f"  - {warning}")

            if service['recommendations']:
                report.append(f"- **Recommendations**:")
                for rec in service['recommendations']:
                    report.append(f"  - {rec}")

            report.append("")

        # 總體建議
        if self.recommendations:
            report.append("## Overall Recommendations")
            for rec in self.recommendations:
                report.append(f"- {rec}")
            report.append("")

        # 警告
        if self.warnings:
            report.append("## Warnings")
            for warning in self.warnings:
                report.append(f"- {warning}")
            report.append("")

        return '\n'.join(report)


def main():
    parser = argparse.ArgumentParser(description='Service Optimizer - 服務優化工具')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    parser.add_argument('--format', '-f', choices=['markdown', 'json'], default='markdown',
                       help='輸出格式 (默認: markdown)')
    parser.add_argument('--output', '-o', help='輸出到檔案')

    args = parser.parse_args()

    optimizer = ServiceOptimizer(verbose=args.verbose)

    # 獲取並分析服務
    docker_services = optimizer.get_docker_services()
    analysis_results = optimizer.analyze_docker_services()

    # 生成報告
    if args.format == 'json':
        report = json.dumps(analysis_results, indent=2, ensure_ascii=False)
    else:
        report = optimizer.generate_report(analysis_results)

    # 輸出報告
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"報告已保存到 {args.output}")
    else:
        print(report)


if __name__ == '__main__':
    main()
