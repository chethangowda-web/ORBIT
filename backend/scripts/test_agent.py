"""Local CLI testing script for ORBIT multi-agent system."""

import asyncio
from agents.orchestrator import process_message
from db.session import async_session_factory
from db.seed import seed_database


async def run_agent_test():
    """Runs a series of test prompts through the orchestrator against seeded database."""
    print("🌱 Seeding database for agent test...")
    await seed_database()

    user_id = "00000000-0000-0000-0000-000000000001"
    space_id = "spaces/DEMOSPACE"

    prompts = [
        "Create a high priority task for John to deploy the frontend by Friday",
        "Show my pending tasks",
        "What should I focus on today?",
        "What are my overdue tasks?",
        "Give me productivity recommendations and team insights",
        "Delete the old login page task",
        "Help me understand what you can do",
    ]

    print("\n🚀 Starting Agent Pipeline Tests:\n" + "=" * 60)
    for prompt in prompts:
        print(f"\n👤 User: '{prompt}'")
        async with async_session_factory() as session:
            state = await process_message(
                user_id=user_id,
                space_id=space_id,
                message=prompt,
                session=session,
            )
            print(f"🤖 Intent: {state.get('intent')} | Active Agent: {state.get('active_agent')}")
            print(f"🛠️ Tools: {state.get('tool_calls_made')}")
            print(f"💬 Response:\n{state.get('response')}")
            if state.get("needs_confirmation"):
                print(f"⚠️ [HITL] Needs confirmation: {state.get('needs_confirmation')}")
            print("-" * 60)


if __name__ == "__main__":
    asyncio.run(run_agent_test())
