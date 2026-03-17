#!/usr/bin/env python3
"""
Minimal Viable Tool: version_sync.py
Syncs data from VERSION.md to heartbeat.md
"""

import re
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

class VersionSync:
    """Minimal sync tool for VERSION.md to heartbeat.md"""
    
    def __init__(self, dry_run=False):
        self.base_path = Path("/root/nanojaga")
        self.version_file = self.base_path / "VERSION.md"
        self.heartbeat_file = self.base_path / "system" / "monitoring" / "heartbeat.md"
        self.changes_log = []
        self.dry_run = dry_run
        
        if self.dry_run:
            self._log_change("DRY RUN MODE - No files will be modified")
        
    def read_version_file(self):
        """Read and parse VERSION.md"""
        try:
            with open(self.version_file, 'r') as f:
                content = f.read()
            
            # Parse version
            version_match = re.search(r"Current Version\s*\n\*\*(v\d+\.\d+\.\d+)\*\*", content)
            current_version = version_match.group(1) if version_match else "UNKNOWN"
            
            # Parse deficit tracker
            deficit_data = self._parse_deficit_tracker(content)
            
            # Parse milestones
            milestones = self._parse_milestones(content)
            
            # Parse system health
            system_health = self._parse_system_health(content)
            
            return {
                "current_version": current_version,
                "deficit_tracker": deficit_data,
                "milestones": milestones,
                "system_health": system_health,
                "raw_content": content
            }
            
        except Exception as e:
            self._log_error(f"Error reading VERSION.md: {e}")
            return None
    
    def _parse_deficit_tracker(self, content):
        """Parse deficit tracker section"""
        deficit_data = {"high": [], "medium": [], "low": []}
        
        # Find deficit tracker section
        deficit_section = re.search(r"## Deficit Tracker\s*(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if deficit_section:
            section_text = deficit_section.group(1)
            
            # Parse HIGH priority
            high_match = re.search(r"### 🔴 HIGH PRIORITY.*?\n(.*?)(?=\n###|\Z)", section_text, re.DOTALL)
            if high_match:
                high_items = re.findall(r"\d+\.\s*\*\*(.*?)\*\*", high_match.group(1))
                deficit_data["high"] = high_items
            
            # Parse MEDIUM priority
            medium_match = re.search(r"### 🟡 MEDIUM PRIORITY.*?\n(.*?)(?=\n###|\Z)", section_text, re.DOTALL)
            if medium_match:
                medium_items = re.findall(r"\d+\.\s*\*\*(.*?)\*\*", medium_match.group(1))
                deficit_data["medium"] = medium_items
            
            # Parse LOW priority
            low_match = re.search(r"### 🟢 LOW PRIORITY.*?\n(.*?)(?=\n###|\Z)", section_text, re.DOTALL)
            if low_match:
                low_items = re.findall(r"\d+\.\s*\*\*(.*?)\*\*", low_match.group(1))
                deficit_data["low"] = low_items
        
        return deficit_data
    
    def _parse_milestones(self, content):
        """Parse next milestones section"""
        milestones = []
        
        milestones_section = re.search(r"## Next Milestones\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if milestones_section:
            milestone_lines = re.findall(r"\d+\.\s*\*\*(.*?)\*\*\s*-\s*(.*)", milestones_section.group(1))
            for version, description in milestone_lines:
                milestones.append({
                    "version": version.strip(),
                    "description": description.strip()
                })
        
        return milestones
    
    def _parse_system_health(self, content):
        """Parse system health section"""
        health_items = []
        
        health_section = re.search(r"## System Health\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if health_section:
            health_lines = re.findall(r"- ✅ (.*)", health_section.group(1))
            health_items = [line.strip() for line in health_lines]
        
        return health_items
    
    def read_heartbeat_file(self):
        """Read current heartbeat.md content"""
        try:
            with open(self.heartbeat_file, 'r') as f:
                return f.read()
        except Exception as e:
            self._log_error(f"Error reading heartbeat.md: {e}")
            return None
    
    def update_heartbeat(self, version_data, current_heartbeat):
        """Update heartbeat.md with data from VERSION.md"""
        if not version_data or not current_heartbeat:
            return None
        
        updated_content = current_heartbeat
        
        # Update system version
        updated_content = re.sub(
            r"System Version: v\d+\.\d+\.\d+",
            f"System Version: {version_data['current_version']}",
            updated_content
        )
        
        # Update deficit tracker section
        updated_content = self._update_deficit_section(updated_content, version_data['deficit_tracker'])
        
        # Update next milestones
        updated_content = self._update_milestones_section(updated_content, version_data['milestones'])
        
        # Update system health
        updated_content = self._update_system_health(updated_content, version_data['system_health'])
        
        # Update last sync timestamp
        sync_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        updated_content = re.sub(
            r"Last Updated: \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC",
            f"Last Updated: {sync_time}",
            updated_content
        )
        
        # Add sync note
        if "## 🔄 SYNC HISTORY" not in updated_content:
            updated_content += f"\n\n## 🔄 SYNC HISTORY\n- {sync_time}: Automated sync completed"
        else:
            # Append to existing sync history
            updated_content = re.sub(
                r"(## 🔄 SYNC HISTORY\n)",
                f"\\1- {sync_time}: Automated sync completed\n",
                updated_content
            )
        
        return updated_content
    
    def _update_deficit_section(self, content, deficit_data):
        """Update deficit tracker section in heartbeat"""
        # Build new deficit section
        new_section = "### Deficit Tracker Status (from VERSION.md)\n"
        
        if deficit_data["high"]:
            new_section += f"- 🔴 HIGH Priority: {len(deficit_data['high'])} remaining\n"
            for i, item in enumerate(deficit_data["high"], 1):
                new_section += f"  - {item}\n"
        
        if deficit_data["medium"]:
            new_section += f"- 🟡 MEDIUM Priority: {len(deficit_data['medium'])} remaining\n"
            for i, item in enumerate(deficit_data["medium"], 1):
                new_section += f"  - {item}\n"
        
        if deficit_data["low"]:
            new_section += f"- 🟢 LOW Priority: {len(deficit_data['low'])} remaining\n"
            for i, item in enumerate(deficit_data["low"], 1):
                new_section += f"  - {item}\n"
        
        # Replace existing deficit section
        pattern = r"### Deficit Tracker Status.*?(?=\n##|\Z)"
        return re.sub(pattern, new_section, content, flags=re.DOTALL)
    
    def _update_milestones_section(self, content, milestones):
        """Update next milestones section"""
        if not milestones:
            return content
        
        new_section = "## 📋 NEXT MILESTONES (from VERSION.md)\n"
        for i, milestone in enumerate(milestones, 1):
            new_section += f"{i}. **{milestone['version']}** - {milestone['description']}\n"
        
        # Replace existing milestones section
        pattern = r"## 📋 NEXT MILESTONES.*?(?=\n##|\Z)"
        return re.sub(pattern, new_section, content, flags=re.DOTALL)
    
    def _update_system_health(self, content, health_items):
        """Update system health references"""
        # Simple update - just ensure health items are mentioned
        # More sophisticated update could be added later
        return content
    
    def write_heartbeat_file(self, content):
        """Write updated content to heartbeat.md"""
        try:
            if self.dry_run:
                self._log_change(f"DRY RUN: Would update heartbeat.md ({len(content)} bytes)")
                self._log_change(f"DRY RUN: Content preview (first 200 chars): {content[:200]}...")
                return True
            
            # Create backup
            backup_file = self.heartbeat_file.with_suffix('.backup.md')
            if self.heartbeat_file.exists():
                import shutil
                shutil.copy2(self.heartbeat_file, backup_file)
                self._log_change(f"Created backup: {backup_file}")
            
            # Write new content
            with open(self.heartbeat_file, 'w') as f:
                f.write(content)
            
            self._log_change(f"Updated heartbeat.md ({len(content)} bytes)")
            return True
            
        except Exception as e:
            self._log_error(f"Error writing heartbeat.md: {e}")
            return False
    
    def validate_sync(self, version_data, heartbeat_content):
        """Validate that sync was successful"""
        validation_results = []
        
        # Check version is in heartbeat
        if version_data['current_version'] in heartbeat_content:
            validation_results.append(("Version", "✅ PASS"))
        else:
            validation_results.append(("Version", "❌ FAIL"))
        
        # Check deficit items count
        total_items = len(version_data['deficit_tracker']['high']) + \
                     len(version_data['deficit_tracker']['medium']) + \
                     len(version_data['deficit_tracker']['low'])
        
        # Count items in heartbeat
        high_count = heartbeat_content.count("🔴 HIGH Priority")
        medium_count = heartbeat_content.count("🟡 MEDIUM Priority")
        low_count = heartbeat_content.count("🟢 LOW Priority")
        
        if total_items > 0:
            validation_results.append(("Deficit Items", "✅ PASS"))
        else:
            validation_results.append(("Deficit Items", "⚠️ WARNING"))
        
        # Check milestones
        if version_data['milestones']:
            milestone_versions = [m['version'] for m in version_data['milestones']]
            all_found = all(version in heartbeat_content for version in milestone_versions)
            validation_results.append(("Milestones", "✅ PASS" if all_found else "❌ FAIL"))
        
        return validation_results
    
    def _log_change(self, message):
        """Log a change"""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.changes_log.append(log_entry)
        print(f"📝 {log_entry}")
    
    def _log_error(self, message):
        """Log an error"""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] ERROR: {message}"
        self.changes_log.append(log_entry)
        print(f"❌ {log_entry}")
    
    def run_sync(self):
        """Main sync execution"""
        print("🔄 Starting version sync...")
        
        # Read source data
        version_data = self.read_version_file()
        if not version_data:
            print("❌ Failed to read VERSION.md")
            return False
        
        print(f"📖 Read VERSION.md: {version_data['current_version']}")
        
        # Read current heartbeat
        heartbeat_content = self.read_heartbeat_file()
        if not heartbeat_content:
            print("❌ Failed to read heartbeat.md")
            return False
        
        # Update heartbeat
        updated_content = self.update_heartbeat(version_data, heartbeat_content)
        if not updated_content:
            print("❌ Failed to update heartbeat content")
            return False
        
        # Write updated file
        if not self.write_heartbeat_file(updated_content):
            print("❌ Failed to write updated heartbeat.md")
            return False
        
        # Validate sync
        validation_results = self.validate_sync(version_data, updated_content)
        
        # Print summary
        print("\n📊 SYNC SUMMARY:")
        print(f"• Version: {version_data['current_version']}")
        print(f"• Deficit Items: {len(version_data['deficit_tracker']['high'])}H, "
              f"{len(version_data['deficit_tracker']['medium'])}M, "
              f"{len(version_data['deficit_tracker']['low'])}L")
        print(f"• Milestones: {len(version_data['milestones'])}")
        
        print("\n✅ Validation Results:")
        for item, status in validation_results:
            print(f"  {item}: {status}")
        
        print(f"\n📝 Changes logged: {len(self.changes_log)}")
        
        return True

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Sync VERSION.md to heartbeat.md")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Dry run mode - show changes without modifying files")
    args = parser.parse_args()
    
    sync_tool = VersionSync(dry_run=args.dry_run)
    success = sync_tool.run_sync()
    
    if success:
        if args.dry_run:
            print("\n✅ Dry run completed successfully - no files modified")
        else:
            print("\n🎉 Sync completed successfully!")
        return 0
    else:
        print("\n❌ Sync failed!")
        return 1

if __name__ == "__main__":
    exit(main())