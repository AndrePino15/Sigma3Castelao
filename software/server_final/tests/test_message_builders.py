from server import messages

def test_vote_is_yes_no():
    msg = messages.build_vote("v1", 20)
    assert msg["type"] == "vote"
    assert msg["payload"]["options"] == ["yes", "no"]
