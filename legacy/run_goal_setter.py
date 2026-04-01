from jagabot.tools.goal_setter import GoalSetterTool
import sys

def main():
    tool = GoalSetterTool()
    result = tool.execute()
    print(result)
    
    # Log to heartbeat
    with open("/root/.jagabot/logs/heartbeat.log", "a") as f:
        f.write(f"\n[{__import__('datetime').datetime.now()}] Goal-Setter executed\n")
        f.write(f"Result: {result}\n")

if __name__ == "__main__":
    main()
