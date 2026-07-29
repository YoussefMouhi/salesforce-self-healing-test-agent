from pathlib import Path
from generator import generate_scenario, save_scenario

stories = Path("user_stories/stories.txt").read_text().strip().split("\n")

for story in stories:
    story = story.strip()
    if not story:
        continue
    print(f"\n--- Generating for: {story[:60]}... ---")
    try:
        scenario = generate_scenario(story)

        base_id = scenario["scenario_id"]
        candidate_id = base_id
        suffix = 2
        while Path("scenarios") / f"{candidate_id}.json" in Path("scenarios").glob("*.json"):
            candidate_id = f"{base_id}_{suffix}"
            suffix += 1
        if candidate_id != base_id:
            print(f"WARNING: scenario_id '{base_id}' collided with an existing file, renamed to '{candidate_id}'")
            scenario["scenario_id"] = candidate_id

        path = save_scenario(scenario)
        print(f"OK -> {path}")
    except Exception as e:
        print(f"FAILED: {e}")
