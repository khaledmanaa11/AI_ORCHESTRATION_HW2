from agent_arena.services.player.brain.selector import pick


def test_rubric_quality_mode():
    drafts = [
        {"text": "A simple draft without keywords.", "targets": ["sycophancy"]},
        {
            "text": "Therefore, because of logic, we must logically and consequently conclude that this is clearly essential reasoning.",
            "targets": [],
        },  # High quality keywords
        {"text": "We cite the data from the document report.", "targets": []},  # Medium quality keywords
    ]
    rubric_weights = {"logic": 30.0, "evidence": 30.0, "rebuttal": 25.0, "persuasion": 15.0}
    selector_weights = {"sycophancy": 10.0}
    read_profile = {"susceptibility": {"sycophancy": 1.0}}

    # In rubric-quality mode, susceptibility weighting is ignored.
    # Draft 1 has high susceptibility targets but low quality text.
    # Draft 2 has high quality text keywords: "therefore" (logic), "logically" (logic), "must" (persuasion), "essential" (persuasion)
    chosen_idx = pick(
        drafts=drafts,
        read_profile=read_profile,
        rubric_weights=rubric_weights,
        mode="rubric-quality",
        selector_weights=selector_weights,
    )
    assert chosen_idx == 1


def test_judge_profile_mode():
    drafts = [
        {"text": "A simple draft without keywords.", "targets": ["sycophancy"]},  # High exploit score
        {"text": "Therefore, we must logically conclude that this is clearly essential.", "targets": []},  # High quality keywords
    ]
    rubric_weights = {"logic": 1.0, "evidence": 1.0, "rebuttal": 1.0, "persuasion": 1.0}
    selector_weights = {"sycophancy": 100.0}
    read_profile = {"susceptibility": {"sycophancy": 1.0}}

    # In judge-profile mode, the susceptibility score plus rubric quality is calculated.
    # Draft 0 score = 100 * 1 = 100
    # Draft 1 score = rubric quality keywords ~ 4
    chosen_idx = pick(
        drafts=drafts,
        read_profile=read_profile,
        rubric_weights=rubric_weights,
        mode="judge-profile",
        selector_weights=selector_weights,
    )
    assert chosen_idx == 0


def test_deterministic_tie_breaking():
    # Two drafts with identical text and targets
    drafts = [
        {"text": "Identical draft.", "targets": []},
        {"text": "Identical draft.", "targets": []},
        {"text": "Identical draft.", "targets": []},
    ]
    rubric_weights = {"logic": 10.0}
    selector_weights = {}
    read_profile = {}

    # Should select the lowest index (0)
    chosen_idx_rubric = pick(
        drafts=drafts,
        read_profile=read_profile,
        rubric_weights=rubric_weights,
        mode="rubric-quality",
        selector_weights=selector_weights,
    )
    assert chosen_idx_rubric == 0

    chosen_idx_judge = pick(
        drafts=drafts,
        read_profile=read_profile,
        rubric_weights=rubric_weights,
        mode="judge-profile",
        selector_weights=selector_weights,
    )
    assert chosen_idx_judge == 0


def test_empty_drafts():
    # Handle empty list of drafts gracefully
    chosen_idx = pick(
        drafts=[], read_profile={}, rubric_weights={}, mode="rubric-quality", selector_weights={}
    )
    assert chosen_idx == 0
