from toolcall_doctor.cli import main


def test_help_exits_zero():
    assert main(["--help"]) == 0


def test_minimize_help_exits_zero():
    assert main(["minimize", "--help"]) == 0


def test_demo_help_exits_zero():
    assert main(["demo", "--help"]) == 0
