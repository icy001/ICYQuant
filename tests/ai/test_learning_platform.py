from services.ai import ExperienceReplayMemory


def test_memory():

    memory = ExperienceReplayMemory()

    memory.add("sample")

    assert memory.size() == 1