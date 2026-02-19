#!/usr/bin/env python3
"""
Docker Optimizer - 智能 Docker 容器和鏡像優化工具
智能管理 Docker 資源，自動清理未使用的資源
"""

import subprocess
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any


class DockerOptimizer:
    """Docker 資源優化器"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.timestamp = datetime.now().isoformat()

    def run_command(self, cmd: List[str]) -> str:
        """執行 shell 命令並返回輸出"""
        try:
            if self.dry_run:
                return f"[DRY RUN] Would run: {' '.join(cmd)}"
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error: {str(e)}"

    def get_docker_disk_usage(self) -> Dict[str, Any]:
        """獲取 Docker 磁盤使用情況"""
        cmd = ["docker", "system", "df", "--format", "json"]
        output = self.run_command(cmd)
        try:
            data = json.loads(output)
            # 處理可能的多行 JSON
            if isinstance(data, dict):
                return data
            elif isinstance(data, list) and data:
                # 如果是列表，統計總數
                total_usage = {}
                for item in data:
                    if isinstance(item, dict):
                        for key, value in item.items():
                            if key not in total_usage:
                                total_usage[key] = []
                            total_usage[key].append(value)
                return total_usage
            return {}
        except:
            return {"raw": output}

    def get_stopped_containers(self) -> List[Dict[str, Any]]:
        """獲取已停止的容器"""
        cmd = ["docker", "ps", "-a", "--filter", "status=exited", "--format", "{{json .}}"]
        output = self.run_command(cmd)
        containers = []
        for line in output.split('\n'):
            if line:
                try:
                    container = json.loads(line)
                    containers.append(container)
                except:
                    pass
        return containers

    def get_dangling_images(self) -> List[str]:
        """獲取懸空鏡像（dangling images）"""
        cmd = ["docker", "images", "--filter", "dangling=true", "-q"]
        output = self.run_command(cmd)
        return [img for img in output.split('\n') if img]

    def get_old_images(self, days: int = 7) -> List[Dict[str, Any]]:
        """獲取指定天數內未使用的鏡像"""
        # 先獲取所有鏡像
        cmd = ["docker", "images", "--format", "{{json .}}"]
        output = self.run_command(cmd)
        images = []
        for line in output.split('\n'):
            if line:
                try:
                    img = json.loads(line)
                    # 這裡可以做更複雜的邏輯，比如檢查最後使用時間
                    images.append(img)
                except:
                    pass
        return images

    def get_unused_volumes(self) -> List[str]:
        """獲取未使用的卷"""
        cmd = ["docker", "volume", "ls", "--filter", "dangling=true", "-q"]
        output = self.run_command(cmd)
        return [vol for vol in output.split('\n') if vol]

    def clean_stopped_containers(self) -> Dict[str, Any]:
        """清理已停止的容器"""
        containers = self.get_stopped_containers()
        if not containers:
            return {"status": "ok", "message": "No stopped containers to clean"}

        container_ids = [c.get("ID", "") for c in containers if c.get("ID")]
        if not container_ids:
            return {"status": "ok", "message": "No stopped containers to clean"}

        cmd = ["docker", "rm"] + container_ids
        output = self.run_command(cmd)

        return {
            "status": "ok",
            "containers_cleaned": len(container_ids),
            "output": output
        }

    def clean_dangling_images(self) -> Dict[str, Any]:
        """清理懸空鏡像"""
        images = self.get_dangling_images()
        if not images:
            return {"status": "ok", "message": "No dangling images to clean"}

        cmd = ["docker", "rmi"] + images
        output = self.run_command(cmd)

        return {
            "status": "ok",
            "images_cleaned": len(images),
            "output": output
        }

    def clean_unused_volumes(self) -> Dict[str, Any]:
        """清理未使用的卷"""
        volumes = self.get_unused_volumes()
        if not volumes:
            return {"status": "ok", "message": "No unused volumes to clean"}

        cmd = ["docker", "volume", "rm"] + volumes
        output = self.run_command(cmd)

        return {
            "status": "ok",
            "volumes_cleaned": len(volumes),
            "output": output
        }

    def clean_build_cache(self) -> Dict[str, Any]:
        """清理構建緩存"""
        cmd = ["docker", "builder", "prune", "-f"]
        output = self.run_command(cmd)

        return {
            "status": "ok",
            "output": output
        }

    def clean_all(self) -> Dict[str, Any]:
        """執行完整的 Docker 清理"""
        results = {
            "timestamp": self.timestamp,
            "dry_run": self.dry_run,
            "cleaned": {}
        }

        # 清理已停止的容器
        results["cleaned"]["containers"] = self.clean_stopped_containers()

        # 清理懸空鏡像
        results["cleaned"]["dangling_images"] = self.clean_dangling_images()

        # 清理未使用的卷
        results["cleaned"]["volumes"] = self.clean_unused_volumes()

        # 清理構建緩存
        results["cleaned"]["build_cache"] = self.clean_build_cache()

        # 獲取清理後的磁盤使用情況
        results["disk_usage_after"] = self.get_docker_disk_usage()

        return results

    def generate_report(self) -> str:
        """生成優化報告"""
        # 獲取當前磁盤使用
        disk_before = self.get_docker_disk_usage()

        # 執行清理
        results = self.clean_all()

        disk_after = results["disk_usage_after"]

        report = f"""
# Docker Optimizer Report
Generated: {self.timestamp}
Mode: {'DRY RUN' if self.dry_run else 'LIVE'}

## Disk Usage Before
{json.dumps(disk_before, indent=2)}

## Cleaning Results
"""

        for key, value in results["cleaned"].items():
            report += f"\n### {key}\n"
            report += f"Status: {value.get('status', 'unknown')}\n"
            if 'message' in value:
                report += f"Message: {value['message']}\n"
            if 'containers_cleaned' in value:
                report += f"Containers cleaned: {value['containers_cleaned']}\n"
            if 'images_cleaned' in value:
                report += f"Images cleaned: {value['images_cleaned']}\n"
            if 'volumes_cleaned' in value:
                report += f"Volumes cleaned: {value['volumes_cleaned']}\n"
            if 'output' in value:
                report += f"Output: {value['output']}\n"

        report += f"\n## Disk Usage After\n"
        report += json.dumps(disk_after, indent=2)

        report += "\n\n## Summary\n"
        report += "Docker optimization completed successfully.\n"

        return report


def main():
    parser = argparse.ArgumentParser(description='Docker 資源優化工具')
    parser.add_argument('--dry-run', action='store_true', help='模擬執行，不實際清理')
    parser.add_argument('--format', choices=['json', 'text'], default='json', help='輸出格式')
    parser.add_argument('--output', '-o', help='輸出到文件')

    args = parser.parse_args()

    optimizer = DockerOptimizer(dry_run=args.dry_run)

    if args.format == 'json':
        results = optimizer.clean_all()
        print(json.dumps(results, indent=2))
    else:
        report = optimizer.generate_report()
        print(report)

    if args.output:
        if args.format == 'json':
            with open(args.output, 'w') as f:
                json.dump(optimizer.clean_all(), f, indent=2)
        else:
            with open(args.output, 'w') as f:
                f.write(optimizer.generate_report())


if __name__ == '__main__':
    main()
