import json


def show_agent_output(agent_name: str, data):
    print(f"\n{'='*60}")
    print(f"  {agent_name.upper()} OUTPUT")
    print(f"{'='*60}")
    if isinstance(data, dict):
        print(json.dumps(data, indent=2))
    else:
        # For large code blocks, show a summary
        text = str(data)
        if len(text) > 800:
            print(text[:800] + f"\n... [{len(text)} chars total]")
        else:
            print(text)
    print(f"{'='*60}\n")
