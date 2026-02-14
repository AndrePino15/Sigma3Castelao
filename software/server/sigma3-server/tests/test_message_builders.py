from server import messages

def test_vote_is_yes_no():
    msg = messages.build_vote_command("v1", 20)
    assert msg["type"] == "vote"
    assert msg["payload"]["options"] == ["yes", "no"]
    assert msg["payload"]["one_vote_per_seat"] is True
    assert msg["payload"]["auto_close"] is True
